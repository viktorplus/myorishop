"""Receipts service (RCP-01/RCP-02): the goods-intake write built on the ledger.

D-01: one receipt entry = one product line = one receipt op, qty_delta > 0.
D-05: an unknown code auto-creates the product card + product_created op in
the SAME transaction. D-06: the receipt op snapshots unit_cost_cents and
unit_price_cents; payload carries catalog_cents. D-07: for an EXISTING
product the entered prices update the card via one price_change op per
CHANGED field (CAT-04 machinery). PD-8: prices are optional (empty string
-> NULL) and an empty field never clears a card price — receipts are
additive, unlike the edit form where empty means NULL.

Single-write-path contract: Operation rows and products.quantity are
written ONLY through app.services.ledger.record_operation — every call
here stages with commit=False and ONE commit closes the transaction (WR-03).
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Batch, Operation, Product
from app.services.batches import active_warehouses
from app.services.catalog import DUPLICATE_CODE_ERROR, parse_optional_cents
from app.services.dictionary import lookup as dictionary_lookup
from app.services.ledger import record_operation

QTY_ERROR = "Укажите количество — целое число больше нуля."
# D-02 (Phase 8 D-07 carried forward): zero active warehouses blocks the receipt.
NO_WAREHOUSES_ERROR = (
    "Нет активных складов. Чтобы оформить приход, сначала создайте склад."
)
WAREHOUSE_ERROR = "Выберите склад."
# D-01: the chooser demands an explicit top-up-or-new decision.
BATCH_CHOICE_ERROR = "Выберите партию для пополнения или «Новая партия»."
EXPIRY_ERROR = "Укажите срок годности в формате ГГГГ-ММ-ДД."


def parse_optional_expiry(
    raw: str, errors: dict[str, str], key: str = "expiry"
) -> str | None:
    """Validate an optional ISO expiry (LOT-03), mirroring parse_optional_cents.

    Empty (after strip) -> None: expiry is optional. Otherwise the value must
    be an ISO yyyy-mm-dd date — which `<input type="date">` always posts,
    regardless of locale — normalized via `date.fromisoformat`. Form values
    are untrusted (V5), so the browser's ISO guarantee is re-checked
    server-side: any other input sets the RU error under `key` and returns
    None (nothing is written).
    """
    s = raw.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        errors[key] = EXPIRY_ERROR
        return None


def register_receipt(
    session: Session,
    *,
    code: str,
    name: str,
    qty_raw: str,
    cost_raw: str,
    sale_raw: str,
    catalog_raw: str,
    warehouse_id: str,
    batch_choice: str,
    expiry_raw: str = "",
    location_raw: str = "",
    comment_raw: str = "",
) -> tuple[dict | None, dict[str, str]]:
    """Register one goods receipt atomically; returns (result, errors).

    Success: ({"product": ..., "operation": ..., "batch": ...}, {}). Failure:
    (None, errors) with RU messages — NOTHING is staged or written on any
    validation error. For an EXISTING product the typed name is ignored
    (renames go through /products/{id}/edit — PD-9).

    D-01/D-02: a receipt is the batch birth path. `warehouse_id` must name an
    active warehouse (re-checked server-side — a stale form could post a
    deleted/zero-warehouse state); `batch_choice` is either "new" (create a
    Batch snapshotting the entered «Цена продажи» plus optional
    expiry/location/comment) or an existing batch id to top up (its frozen
    price_cents is NEVER rewritten). Pitfall 10 / T-09-04: a client batch id is
    untrusted — its product AND warehouse ownership are re-validated before any
    write.
    """
    errors: dict[str, str] = {}
    code = code.strip()  # PD-2: normalize codes at write time
    name = name.strip()
    warehouse_id = warehouse_id.strip()
    batch_choice = batch_choice.strip()

    if not code:
        errors["code"] = "Укажите код товара."
    if not name:
        errors["name"] = "Укажите название."

    # D-01: qty_delta strictly positive integer; corrections are Phase 5.
    qty_text = qty_raw.strip()
    qty = int(qty_text) if qty_text.isdigit() else 0
    if qty <= 0:
        errors["quantity"] = QTY_ERROR

    cost_cents = parse_optional_cents(cost_raw, errors, "cost")
    sale_cents = parse_optional_cents(sale_raw, errors, "sale")
    catalog_cents = parse_optional_cents(catalog_raw, errors, "catalog")

    # D-02 / T-09-05: server-side active-warehouse re-check. Zero active
    # warehouses is a blocking state (Phase 8 D-07 carried forward); a stale
    # form could still submit a deleted or blank warehouse id.
    active_ids = {w.id for w in active_warehouses(session)}
    if not active_ids:
        errors["warehouse"] = NO_WAREHOUSES_ERROR
    elif warehouse_id not in active_ids:
        errors["warehouse"] = WAREHOUSE_ERROR

    # V5: batch_choice allow-list — exactly "new" or a resolvable batch id
    # (the id is resolved after the product is known). Empty = nothing chosen.
    if not batch_choice:
        errors["batch_choice"] = BATCH_CHOICE_ERROR

    # LOT-03: validate the optional expiry only on the new-batch path.
    expiry: str | None = None
    if batch_choice == "new":
        expiry = parse_optional_expiry(expiry_raw, errors, "expiry")

    if errors:
        return None, errors

    # Pitfall 5: active-only lookup — a soft-deleted product's code
    # auto-creates a NEW card instead of tripping the IN-01 guard.
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()

    if product is None:
        # D-05: auto-create the card inside the same transaction.
        product = Product(
            id=new_id(),
            code=code,
            name=name,
            # D-27: unconditional Python lower — SQLite cannot fold Cyrillic.
            name_lc=name.lower(),
            category=None,
            cost_cents=cost_cents,
            sale_cents=sale_cents,
            catalog_cents=catalog_cents,
            quantity=0,
        )
        session.add(product)
        record_operation(
            session,
            type_="product_created",
            product_id=product.id,
            qty_delta=0,
            payload={"code": code, "name": name},
            commit=False,
        )
    else:
        # D-07: entered prices update the existing card, one price_change op
        # per CHANGED non-empty field — same payload shape as
        # catalog.update_product. PD-8: None (empty input) never clears a
        # card price. PD-9: the typed name is ignored (no product_edited op).
        entered = {
            "cost_cents": cost_cents,
            "sale_cents": sale_cents,
            "catalog_cents": catalog_cents,
        }
        # PD-8: a receipt has no min_sale input, so this loop iterates the
        # fields a receipt CAN set (not the full app.services.catalog
        # _PRICE_FIELDS set, which also includes min_sale_cents as of
        # Phase 7 PRICE-01) — min_sale_cents is untouched by receipts.
        for field in entered:
            if entered[field] is None or entered[field] == getattr(product, field):
                continue
            # Pitfall 7: snapshot the old value BEFORE mutating the card.
            old = getattr(product, field)
            record_operation(
                session,
                type_="price_change",
                product_id=product.id,
                qty_delta=0,
                payload={"field": field, "old_cents": old, "new_cents": entered[field]},
                commit=False,
            )
            setattr(product, field, entered[field])

    # D-01/D-02: resolve-or-create the batch in the SAME transaction (mirror
    # the product auto-create above). A new batch snapshots the entered
    # «Цена продажи» (sale_cents) — there is NO separate batch price input; a
    # top-up leaves the chosen batch's frozen price_cents untouched. Pitfall 10
    # / T-09-04: re-validate product AND warehouse ownership of a submitted
    # batch id before writing — a stale/crafted POST is untrusted.
    if batch_choice == "new":
        batch = Batch(
            id=new_id(),
            product_id=product.id,
            warehouse_id=warehouse_id,
            expiry=expiry,
            price_cents=sale_cents,
            location=location_raw.strip() or None,
            comment=comment_raw.strip() or None,
            quantity=0,
            is_legacy=0,
        )
        session.add(batch)
    else:
        batch = session.get(Batch, batch_choice)
        if (
            batch is None
            or batch.product_id != product.id
            or batch.warehouse_id != warehouse_id
        ):
            # Discards any staged product auto-create — zero writes on reject.
            session.rollback()
            return None, {"batch_choice": BATCH_CHOICE_ERROR}

    # D-06: snapshot the entered prices on the immutable receipt op; D-11: the
    # batch_id threads the ledger line to its lot (dual quantity projection).
    op = record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=qty,
        unit_cost_cents=cost_cents,
        unit_price_cents=sale_cents,
        payload={"catalog_cents": catalog_cents},
        batch_id=batch.id,
        commit=False,
    )

    # WR-03/WR-04: single transaction close; a duplicate-code race fires
    # uq_products_code_active here and becomes the shared RU error.
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, {"code": DUPLICATE_CODE_ERROR}
    return {"product": product, "operation": op, "batch": batch}, {}


def lookup_prefill(session: Session, code: str) -> dict | None:
    """Pre-fill data for the receipt-form lookup (D-03 / RCP-02). Read-only.

    Active product first: its name plus current card prices (the route
    decides which price fields actually fill — PD-10). Dictionary fallback:
    name only. Unknown code -> None (the route answers 204).
    """
    code = code.strip()
    if not code:
        return None
    # Pitfall 5: active-only — a soft-deleted product's code behaves as unknown.
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is not None:
        return {
            "source": "product",
            "name": product.name,
            "prices": {
                "cost": product.cost_cents,
                "sale": product.sale_cents,
                "catalog": product.catalog_cents,
            },
        }
    entry = dictionary_lookup(session, code)
    if entry is not None:
        return {"source": "dictionary", "name": entry.name, "prices": None}
    return None


def recent_receipts(session: Session, limit: int = 10) -> list[dict]:
    """Last N receipt ops joined to their products, newest first (D-04)."""
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(Operation.type == "receipt")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
