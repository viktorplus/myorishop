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

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Operation, Product
from app.services.catalog import _PRICE_FIELDS, DUPLICATE_CODE_ERROR, parse_optional_cents
from app.services.ledger import record_operation

QTY_ERROR = "Укажите количество — целое число больше нуля."


def register_receipt(
    session: Session,
    *,
    code: str,
    name: str,
    qty_raw: str,
    cost_raw: str,
    sale_raw: str,
    catalog_raw: str,
) -> tuple[dict | None, dict[str, str]]:
    """Register one goods receipt atomically; returns (result, errors).

    Success: ({"product": ..., "operation": ...}, {}). Failure: (None, errors)
    with RU messages — NOTHING is staged or written on any validation error.
    For an EXISTING product the typed name is ignored (renames go through
    /products/{id}/edit — RESEARCH Open Question 1 / PD-9 preview).
    """
    errors: dict[str, str] = {}
    code = code.strip()  # PD-2: normalize codes at write time
    name = name.strip()

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
        for field in _PRICE_FIELDS:
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

    # D-06: snapshot the entered prices on the immutable receipt op.
    op = record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=qty,
        unit_cost_cents=cost_cents,
        unit_price_cents=sale_cents,
        payload={"catalog_cents": catalog_cents},
        commit=False,
    )

    # WR-03/WR-04: single transaction close; a duplicate-code race fires
    # uq_products_code_active here and becomes the shared RU error.
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, {"code": DUPLICATE_CODE_ERROR}
    return {"product": product, "operation": op}, {}


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
