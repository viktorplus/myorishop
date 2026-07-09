"""Write-off service (OPS-01): the stock-removal write built on the ledger.

D-01/D-02: one write-off = one `writeoff` op, qty_delta < 0. The reason is a
hybrid — a required category (`reason_code`, validated server-side against
the WRITEOFF_REASONS allow-list, V5) plus an optional free-text `note` — both
stored verbatim in `Operation.payload` as `{"reason_code", "note"}`.

D-04: write-off is by existing product code only (never auto-creates a
product, unlike receipts); quantity is a required positive int; there are no
price fields. Stock may go to/through zero — a warn-but-allow oversell check
(mirrors the Phase 4 SAL-04 sale oversell) runs BEFORE any write and blocks
with zero writes unless `confirm == "1"`.

Single-write-path contract: Operation rows and products.quantity are written
ONLY through app.services.ledger.record_operation.
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import WRITEOFF_REASONS, Operation, Product
from app.services.ledger import record_operation

QTY_ERROR = "Укажите количество — целое число больше нуля."
REASON_ERROR = "Выберите причину списания."
PRODUCT_NOT_FOUND_TMPL = "Товар с кодом „{code}“ не найден. Сначала оприходуйте товар."
SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."


def register_writeoff(
    session: Session,
    *,
    code: str,
    name: str,
    qty_raw: str,
    reason_code: str,
    note: str,
    confirm: str = "",
) -> tuple[dict | None, dict[str, str]]:
    """Register one write-off atomically; returns (result, errors).

    Success: ({"product": ..., "operation": ...}, {}). Validation failure:
    (None, errors) with RU messages — nothing is staged on any error. The
    oversell warn-but-allow step returns ({"oversell": {...}}, {}) with ZERO
    writes when `confirm != "1"` and the requested qty exceeds cached stock;
    `confirm == "1"` skips the check and writes (stock may go negative).

    `name` is accepted for form-echo symmetry with the receipt/sale services
    but is never used to rename or auto-create a product — write-off never
    creates a card (D-04); a typed name change goes through /products/{id}/edit.
    """
    errors: dict[str, str] = {}
    code = code.strip()
    if not code:
        errors["code"] = "Укажите код товара."

    # D-04: qty_delta strictly positive integer. WR-01 guard: isdigit() alone
    # accepts non-ASCII "digit" characters int() cannot parse; isascii()
    # first routes anything unparsable to the RU error instead of a raise.
    qty_text = qty_raw.strip()
    qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
    if qty <= 0:
        errors["quantity"] = QTY_ERROR

    # V5: server-side allow-list — the <select> alone is never trusted.
    if reason_code not in WRITEOFF_REASONS:
        errors["reason"] = REASON_ERROR

    if errors:
        return None, errors

    # Active-only lookup — a soft-deleted product's code is unknown; a
    # write-off never auto-creates a card (unlike receipts, D-05).
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is None:
        return None, {"code": PRODUCT_NOT_FOUND_TMPL.format(code=code)}

    # D-04/T-05-03: warn-but-allow oversell check BEFORE any write.
    if confirm != "1" and qty > product.quantity:
        return (
            {
                "oversell": {
                    "product": product,
                    "available": product.quantity,
                    "requested": qty,
                }
            },
            {},
        )

    try:
        op = record_operation(
            session,
            type_="writeoff",
            product_id=product.id,
            qty_delta=-qty,
            payload={"reason_code": reason_code, "note": note.strip()},
            commit=True,
        )
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}

    return {"product": product, "operation": op}, {}


def recent_writeoffs(session: Session, limit: int = 10) -> list[dict]:
    """Last N write-off ops joined to their products, newest first (D-04)."""
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(Operation.type == "writeoff")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
