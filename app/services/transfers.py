"""Transfer service (WH-03): move stock between warehouses via two ledger rows.

D-03/D-05: a transfer of quantity N from a source batch to a destination
warehouse is TWO `transfer` operations in one transaction — a negative
qty_delta on the source batch and a positive qty_delta on a freshly created
destination batch that inherits the source's price_cents/expiry/comment/
location/name (this is HOW cost/price history survives the move). Product-
level quantity nets to zero; only the two Batch.quantity caches move.

Single-write-path contract: Operation rows and Product/Batch.quantity are
written ONLY through app.services.ledger.record_operation.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core import local_today_iso, new_id, to_cents
from app.models import Batch, Operation, Product, Warehouse
from app.services.batches import active_warehouses
from app.services.catalog import PRICE_ERROR
from app.services.ledger import parse_op_date, record_operation

QTY_ERROR = "Укажите количество — целое число больше нуля."
BATCH_REQUIRED_ERROR = "Выберите партию."
PRODUCT_NOT_FOUND_TMPL = "Товар с кодом „{code}“ не найден. Сначала оприходуйте товар."
WAREHOUSE_ERROR = "Выберите склад назначения."
SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR = (
    "Чтобы разделить партию в пределах одного склада, укажите новый срок годности или "
    "новое состояние/комментарий — иначе получится пустой дубликат партии."
)
SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."
# CUR-02: a transfer into a different-currency warehouse always requires a
# real destination cost — no conversion, no FX rate.
COST_REQUIRED_ERROR = (
    "Укажите себестоимость партии в валюте склада назначения — "
    "склады используют разную валюту."
)


def register_transfer(
    session: Session,
    *,
    code: str,
    name: str,
    qty_raw: str,
    batch_id: str = "",
    dest_warehouse_id: str = "",
    new_expiry: str = "",
    new_comment: str = "",
    cost_raw: str = "",
    confirm: str = "",
    op_date: str = "",
) -> tuple[dict | None, dict[str, str]]:
    """Register one stock transfer atomically; returns (result, errors).

    Success: ({"product": ..., "source": ..., "dest": ..., "qty": ...}, {}) where
    `qty` is the actual transferred integer quantity (D-11). Validation
    failure: (None, errors) with RU messages — nothing is staged on any
    error. The oversell warn-but-allow step returns
    ({"oversell": {...}}, {}) with ZERO writes when `confirm != "1"` and the
    requested qty exceeds the SOURCE BATCH's remaining quantity (never the
    product total — a transfer is net-zero at the product level);
    `confirm == "1"` skips the check and writes (source may go negative).

    `name` is accepted for form-echo symmetry with the receipt/write-off
    services but is never used to rename a product.

    DATE-01/DATE-02: `op_date` is the operator's business date for the move.
    Empty means «today» and is NOT an error; a malformed or future value sets
    errors["op_date"] and writes ZERO rows. Because a transfer is TWO ledger
    rows, the date is resolved exactly once and BOTH rows are stamped with the
    same value — see the pairing comment at the two record_operation calls.
    """
    errors: dict[str, str] = {}
    code = code.strip()
    if not code:
        errors["code"] = "Укажите код товара."

    # V5/WR-01: same qty guard as write-offs — isascii()+isdigit(), never a
    # bare int() (rejects non-ASCII "digit" characters int() cannot parse).
    qty_text = qty_raw.strip()
    qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
    if qty <= 0:
        errors["quantity"] = QTY_ERROR

    # DATE-02: validated WITH the code/qty pair so a transfer submitted with
    # both a bad quantity and a bad date reports both in one 422. Every guard
    # below (product, batch, warehouse, currency, split-override, oversell)
    # keeps its shipped precedence unchanged.
    business_date = parse_op_date(op_date, errors)

    if errors:
        return None, errors

    # Active-only lookup — a transfer never auto-creates a product.
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is None:
        return None, {"code": PRODUCT_NOT_FOUND_TMPL.format(code=code)}

    # T-09-01: the source batch id is untrusted — reject an empty/unknown id
    # or one that belongs to another product BEFORE any write.
    batch_id = batch_id.strip()
    source = session.get(Batch, batch_id) if batch_id else None
    if source is None or source.product_id != product.id:
        return None, {"batch": BATCH_REQUIRED_ERROR}

    # T-09-02 / Pitfall 4: the destination warehouse id is untrusted — it
    # must name an ACTIVE warehouse and must not equal the source warehouse.
    dest_warehouse_id = dest_warehouse_id.strip()
    active_ids = {w.id for w in active_warehouses(session)}
    if dest_warehouse_id not in active_ids:
        return None, {"warehouse": WAREHOUSE_ERROR}

    # CUR-02: a cross-currency transfer REQUIRES an entered destination cost
    # (no conversion — the operator states the real cost in the destination
    # warehouse's own currency); a same-currency transfer accepts an optional
    # cost and otherwise inherits the source batch's cost_cents unchanged.
    dest_warehouse = session.get(Warehouse, dest_warehouse_id)
    source_warehouse = session.get(Warehouse, source.warehouse_id)
    cost_text = cost_raw.strip()
    if dest_warehouse.currency != source_warehouse.currency:
        if not cost_text:
            return None, {"cost": COST_REQUIRED_ERROR}
        try:
            cost_cents = to_cents(cost_text)
        except ValueError:
            return None, {"cost": PRICE_ERROR}
    else:
        if not cost_text:
            cost_cents = source.cost_cents
        else:
            try:
                cost_cents = to_cents(cost_text)
            except ValueError:
                return None, {"cost": PRICE_ERROR}

    # D-06/D-07: same-warehouse split is allowed only when at least one
    # override is supplied (else it would create an empty duplicate batch).
    # .strip() discipline, never a bare truthy check (Test F).
    new_expiry_clean = new_expiry.strip() if new_expiry else ""
    new_comment_clean = new_comment.strip() if new_comment else ""
    if (
        dest_warehouse_id == source.warehouse_id
        and not new_expiry_clean
        and not new_comment_clean
    ):
        return None, {"form": SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR}

    # D-06/Pitfall 3: warn-but-allow over-transfer check BEFORE any write,
    # scoped to the SOURCE BATCH's remaining quantity (never product.quantity
    # — a transfer nets to zero at the product level).
    if confirm != "1" and qty > source.quantity:
        return (
            {
                "oversell": {
                    "product": product,
                    "available": source.quantity,
                    "requested": qty,
                }
            },
            {},
        )

    # D-05: the destination batch is created fresh, inheriting the source's
    # frozen price_cents (direct assignment, never a bare `or` — a
    # legitimate 0-cent price must survive) plus expiry/comment/location/
    # name. session.add() BEFORE either record_operation call so autoflush
    # inserts it (Pitfall 2 — record_operation's session.get(Batch, dest.id)
    # must resolve).
    dest = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=dest_warehouse_id,
        name=source.name,
        expiry=new_expiry_clean if new_expiry_clean else source.expiry,
        price_cents=source.price_cents,
        cost_cents=cost_cents,
        location=source.location,
        comment=new_comment_clean if new_comment_clean else source.comment,
        quantity=0,
        is_legacy=0,
    )
    session.add(dest)

    # DATE-01/T-33-31: the today-fallback is resolved HERE, once, into a single
    # string that both halves of the transfer are stamped with. Passing the
    # possibly-None `business_date` down instead would let each
    # record_operation call resolve «today» independently, microseconds apart —
    # identical on 364 days a year and a day apart across local midnight. A
    # transfer whose halves landed on different business dates would read as
    # stock leaving one warehouse in one period and arriving in another, the
    # two rows would never net to zero within a single period's report, and
    # Phase 34's reversal — which reverses a transfer as one unit or not at
    # all — would inherit the inconsistency. One value, both rows, always.
    resolved_business_date = business_date or local_today_iso(settings.display_tz)

    try:
        # The outbound and inbound rows are ONE operation split across two
        # ledger entries: same `resolved_business_date` on both, never
        # re-parsed and never re-derived per row.
        record_operation(
            session,
            type_="transfer",
            product_id=product.id,
            qty_delta=-qty,
            batch_id=source.id,
            business_date=resolved_business_date,
            commit=False,
        )
        record_operation(
            session,
            type_="transfer",
            product_id=product.id,
            qty_delta=qty,
            batch_id=dest.id,
            business_date=resolved_business_date,
            commit=False,
        )
        session.commit()
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}

    return {"product": product, "source": source, "dest": dest, "qty": qty}, {}


def recent_transfers(session: Session, limit: int = 10) -> list[dict]:
    """Last N outbound transfer ops joined to their products, newest first.

    Each transfer writes TWO `transfer` rows (source -qty, dest +qty); this
    filters to the outbound (negative) row so each transfer shows once.
    """
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(Operation.type == "transfer", Operation.qty_delta < 0)
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
