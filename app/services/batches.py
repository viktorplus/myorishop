"""Batch service (D-07/D-08/D-13): mostly read helpers, plus one write.

Batches are born only via receipts and the legacy migration (D-03); every
helper below stays read-only and backs the sale/writeoff/correction pickers
plus the receipt chooser, RU-free (display strings live in templates),
mirroring the warehouses service shape.

`update_batch` (quick-260813-i28) is the ONE write in this module — an
operator-facing edit of name/expiry/location/comment/price_cents/cost_cents.
It NEVER writes quantity/warehouse_id/product_id/is_legacy: quantity is a
cached SUM(operations.qty_delta) projection (D-11) and correcting it
directly would desync stock from the append-only ledger; an operator
corrects stock only through Списание/Перемещение.
"""

from collections import defaultdict
from datetime import date

from sqlalchemy import nullslast, select
from sqlalchemy.orm import Session

from app.models import Batch, Product, Warehouse
from app.services.catalog import parse_optional_cents

BATCH_NOT_FOUND_ERROR = "Партия не найдена."
NAME_TOO_LONG_ERROR = "Название партии слишком длинное — не больше 220 символов."
LOCATION_TOO_LONG_ERROR = "Место хранения слишком длинное — не больше 100 символов."
COMMENT_TOO_LONG_ERROR = "Комментарий слишком длинный — не больше 200 символов."
# LOT-03/quick-260813-i28: mirrors app.services.receipts.parse_optional_expiry's
# exact behavior. Duplicated inline rather than imported — app.services.receipts
# already imports active_warehouses FROM this module, so importing back would
# be a circular import.
EXPIRY_ERROR = "Укажите срок годности в формате ГГГГ-ММ-ДД."

_NAME_MAX_LEN = 220
_LOCATION_MAX_LEN = 100
_COMMENT_MAX_LEN = 200


def open_batches(
    session: Session, product_id: str, warehouse_id: str | None = None
) -> list[Batch]:
    """Open batches (quantity > 0) for a product, D-07 order.

    Earliest expiry first, NULL expiry last, tie-broken by oldest receipt
    (created_at). `nullslast` renders portable `NULLS LAST` (verified on
    SQLite 3.50.4, native on PostgreSQL). Sale picker reads all warehouses;
    the receipt chooser passes warehouse_id to narrow to one (D-01).
    """
    stmt = select(Batch).where(Batch.product_id == product_id, Batch.quantity > 0)
    if warehouse_id is not None:
        stmt = stmt.where(Batch.warehouse_id == warehouse_id)
    return list(
        session.scalars(
            stmt.order_by(nullslast(Batch.expiry.asc()), Batch.created_at.asc())
        )
    )


def batches_for_products(session: Session, product_ids: list[str]) -> dict[str, list[Batch]]:
    """Open batches (quantity > 0) for a PAGE of products, grouped by product_id.

    Same ordering as open_batches (earliest expiry first, NULL last, then
    oldest receipt) but ONE query for the whole page instead of N+1.
    """
    if not product_ids:
        return {}
    rows = session.scalars(
        select(Batch)
        .where(Batch.product_id.in_(product_ids), Batch.quantity > 0)
        .order_by(nullslast(Batch.expiry.asc()), Batch.created_at.asc())
    )
    grouped: dict[str, list[Batch]] = defaultdict(list)
    for batch in rows:
        grouped[batch.product_id].append(batch)
    return dict(grouped)


def legacy_batch(session: Session, product_id: str) -> Batch | None:
    """The migration-seeded legacy batch for a product, or None (D-08 fallback)."""
    return session.scalars(
        select(Batch).where(Batch.product_id == product_id, Batch.is_legacy == 1)
    ).first()


def expiring_batches(session: Session) -> list[dict]:
    """Open batches (quantity > 0) with a set expiry, earliest first (LOT-06/D-07).

    NULL expiry (legacy batches) is excluded by `is_not(None)`, so
    `nullslast` is unnecessary here (unlike `open_batches`, which must show
    NULL-expiry batches too). Joined to Product + Warehouse for display.
    """
    rows = session.execute(
        select(Batch, Product, Warehouse)
        .join(Product, Batch.product_id == Product.id)
        .join(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(Batch.quantity > 0, Batch.expiry.is_not(None))
        .order_by(Batch.expiry.asc(), Batch.created_at.asc())
    ).all()
    return [{"batch": b, "product": p, "warehouse": w} for b, p, w in rows]


def active_warehouses(session: Session) -> list[Warehouse]:
    """Active (deleted_at IS NULL) warehouses, name-ordered.

    Unlike warehouses.list_warehouses (which deliberately keeps deleted rows
    for the management page), the receipt form needs active-only options.
    """
    return list(
        session.scalars(
            select(Warehouse)
            .where(Warehouse.deleted_at.is_(None))
            .order_by(Warehouse.name)
        )
    )


def update_batch(
    session: Session,
    batch_id: str,
    *,
    name_raw: str,
    expiry_raw: str,
    location_raw: str,
    comment_raw: str,
    price_raw: str,
    cost_raw: str,
) -> tuple[Batch | None, dict[str, str]]:
    """Operator edit of a batch's name/expiry/location/comment/price/cost.

    Returns (batch, {}) on success or (None, errors) with RU messages — on
    any error NOTHING is written. Every field is validated BEFORE any
    mutation, collecting ALL errors into one dict (never fail-fast on the
    first bad field, mirrors app.services.catalog.update_product's idiom).

    Every field, submitted as "" (after strip), clears the column to NULL —
    unlike receipts.register_receipt, which is additive and never clears a
    price. Never touches quantity/warehouse_id/product_id/is_legacy — they
    are not even parameters. Relies on SQLAlchemy's normal dirty-tracking: a
    genuine no-op (resubmitting the batch's own current values) assigns no
    changed attribute, so no UPDATE is emitted and the model's `onupdate`
    hook never fires; a real change advances `updated_at`.
    """
    batch = session.get(Batch, batch_id)
    if batch is None:
        return None, {"batch": BATCH_NOT_FOUND_ERROR}

    errors: dict[str, str] = {}

    name = name_raw.strip() or None
    if name is not None and len(name) > _NAME_MAX_LEN:
        errors["name"] = NAME_TOO_LONG_ERROR

    location = location_raw.strip() or None
    if location is not None and len(location) > _LOCATION_MAX_LEN:
        errors["location"] = LOCATION_TOO_LONG_ERROR

    comment = comment_raw.strip() or None
    if comment is not None and len(comment) > _COMMENT_MAX_LEN:
        errors["comment"] = COMMENT_TOO_LONG_ERROR

    expiry_s = expiry_raw.strip()
    expiry: str | None = None
    if expiry_s:
        try:
            expiry = date.fromisoformat(expiry_s).isoformat()
        except ValueError:
            errors["expiry"] = EXPIRY_ERROR

    price_cents = parse_optional_cents(price_raw, errors, "price")
    cost_cents = parse_optional_cents(cost_raw, errors, "cost")

    if errors:
        return None, errors

    batch.name = name
    batch.expiry = expiry
    batch.location = location
    batch.comment = comment
    batch.price_cents = price_cents
    batch.cost_cents = cost_cents
    session.commit()
    return batch, {}
