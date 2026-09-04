"""Corrections service (OPS-03): the stock-correction write built on the ledger.

D-09: the operator corrects stock in one of two modes — counted (enters the
physically counted quantity; the service computes
qty_delta = counted - current cached Product.quantity) or delta (enters a
signed value, written as-is). D-10: a correction is ALWAYS a `correction` op
through record_operation — products.quantity is never edited directly — and
a zero net delta is rejected gracefully with NO row written. D-11: the
payload carries an optional note plus the input mode ({"note", "mode"}).

Single-write-path contract: Operation rows and products.quantity are
written ONLY through app.services.ledger.record_operation (WR-03).
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Batch, Product
from app.services.dictionary import lookup as dictionary_lookup
from app.services.ledger import parse_op_date, record_operation

MODE_ERROR = "Неверный режим."
CODE_ERROR = "Укажите код товара."
BATCH_REQUIRED_ERROR = "Выберите партию."
COUNT_QTY_ERROR = "Укажите фактический остаток — целое число не меньше нуля."
DELTA_QTY_ERROR = "Укажите изменение — целое число, отличное от нуля."
ZERO_NET_ERROR = "Остаток не изменился — нечего сохранять."
SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."


def register_correction(
    session: Session,
    *,
    code: str,
    mode: str,
    value_raw: str,
    note: str,
    batch_id: str = "",
    confirm: str = "",
    op_date: str = "",
) -> tuple[dict | None, dict[str, str]]:
    """Register one stock correction atomically; returns (result, errors).

    Success: ({"product": ..., "operation": ..., "new_qty": ...}, {}).
    Failure: (None, errors) with RU messages — NOTHING is staged or written
    on any validation error, including the D-10 zero-net-delta rejection.

    DATE-01/DATE-02: `op_date` is the operator's business date for this
    correction — the day the stock discrepancy actually applies to, which is
    not always the day it was typed in. Empty means «today» and is NOT an
    error (parse_op_date returns None and record_operation's Python-side
    fallback supplies the local day). A malformed or future value sets
    errors["op_date"] and writes ZERO rows.

    LOT-05: the correction targets a specific batch (batch_id). Count mode is
    diffed against the PICKED batch's quantity, not the product total
    (Pitfall 7). A per-batch over-removal warn-but-allow gate returns
    ({"oversell": {...}}, {}) with ZERO writes when `confirm != "1"` and the
    net removal exceeds the batch's remaining (criterion 4).
    """
    # T-05-12/V5: server-side allow-list — the mode radio is not trusted.
    if mode not in ("count", "delta"):
        return None, {"mode": MODE_ERROR}

    code = code.strip()
    if not code:
        return None, {"code": CODE_ERROR}

    # Pitfall 5: active-only lookup — a soft-deleted product's code is unknown.
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is None:
        return None, {"code": f"Товар с кодом „{code}“ не найден."}

    # LOT-05/T-09-12: the correction MUST target a specific batch. The client
    # id is untrusted — reject an empty/unknown id or one that belongs to
    # another product BEFORE any parsing or write.
    batch = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
    if batch is None or batch.product_id != product.id:
        return None, {"batch": BATCH_REQUIRED_ERROR}

    errors: dict[str, str] = {}
    s = value_raw.strip()
    qty_delta = 0
    if mode == "count":
        # T-05-13: unsigned int >= 0 only. Pitfall 7/T-09-13: the counted
        # quantity is diffed against the PICKED batch's remaining, never the
        # product total — a recount of one batch cannot corrupt a sibling.
        if s.isascii() and s.isdigit():
            counted = int(s)
            qty_delta = counted - batch.quantity
        else:
            errors["quantity"] = COUNT_QTY_ERROR
    else:
        # T-05-13: SIGNED nonzero int — allow one leading '-'.
        body = s[1:] if s.startswith("-") else s
        if body != "" and body.isascii() and body.isdigit():
            qty_delta = int(s)
        else:
            errors["quantity"] = DELTA_QTY_ERROR

    # DATE-02: validated WITH the quantity, so a correction submitted with both
    # a bad value and a bad date surfaces both messages in one 422 instead of
    # making the operator fix them one round-trip at a time. Deliberately
    # placed AFTER the shipped mode/code/product/batch guards so their
    # precedence is byte-unchanged: a correction naming an unknown product
    # still fails on the code, exactly as it did before this phase.
    business_date = parse_op_date(op_date, errors)

    if errors:
        return None, errors

    # D-10: a zero net delta is rejected gracefully — no row written.
    if qty_delta == 0:
        return None, {"quantity": ZERO_NET_ERROR}

    # D-09/criterion 4: warn-but-allow over-removal check BEFORE any write,
    # scoped to the PICKED batch's remaining (T-09-14: recomputed server-side
    # against the current Batch.quantity on every POST — confirm is never
    # trusted alone).
    if confirm != "1" and -qty_delta > batch.quantity:
        return (
            {
                "oversell": {
                    "product": product,
                    "available": batch.quantity,
                    "requested": -qty_delta,
                }
            },
            {},
        )

    try:
        op = record_operation(
            session,
            type_="correction",
            product_id=product.id,
            qty_delta=qty_delta,
            payload={"note": note.strip() or None, "mode": mode},
            batch_id=batch.id,
            # DATE-01: a correction writes ONE row and derives no artifact from
            # the date, so the possibly-None parsed value is passed straight
            # through and record_operation's Python-side fallback is the SINGLE
            # place «today» is resolved. Resolving it here as well would be a
            # second definition of today for no gain — the write-off precedent
            # (app/services/writeoffs.py, plan 33-10). Contrast register_transfer,
            # which writes TWO rows and therefore MUST resolve once up front.
            business_date=business_date,
            commit=True,
        )
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}

    return {"product": product, "operation": op, "new_qty": product.quantity}, {}


def lookup_prefill(session: Session, code: str) -> dict | None:
    """Pre-fill data for the correction-form lookup. Read-only.

    Active product first: name + current cached quantity (needed for the
    counted-mode hint). Dictionary fallback: name only, quantity None.
    Unknown code -> None (the route answers 204).
    """
    code = code.strip()
    if not code:
        return None
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is not None:
        return {"name": product.name, "quantity": product.quantity}
    entry = dictionary_lookup(session, code)
    if entry is not None:
        return {"name": entry.name, "quantity": None}
    return None
