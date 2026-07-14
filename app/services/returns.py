"""Returns service (OPS-02): the sale-linked return vertical slice.

D-05: the entry point is a specific origin `sale` op (a recent-sales /
purchase-history row), never a bare product code. D-06: a return writes one
`return` op with qty_delta>0 carrying sale_id + product_id. D-07: price/cost
symmetry — copy the origin sale op's FROZEN unit_price_cents/unit_cost_cents,
NEVER the current product card (preserves SAL-05 profit correctness). D-08:
partial returns are allowed; returnable = sold - already-returned aggregated
per sale_id+product_id, enforced before any write.

Single-write-path contract: the `return` op is written ONLY through
app.services.ledger.record_operation.

D-08 batch inheritance: a return NEVER re-asks for a batch — it restores stock
to the ORIGIN sale op's batch. When the origin is a pre-Phase-9 sale (NULL
batch_id), the return targets the product's legacy batch; if that product was
sold out at migration (ledger stock <= 0, so D-13 seeded no legacy batch), the
legacy batch is LAZILY created here with the frozen D-14 field values. That
lazy-create is the deliberate THIRD batch birth path (alongside the 0008
migration seed and the receipt flow) — the only way D-08 works for every
legacy sale while keeping the single-write-path invariant.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Batch, Operation, Product
from app.services import finance
from app.services.batches import legacy_batch
from app.services.ledger import record_operation

# D-14 frozen literals (re-declared, NEVER imported from the migration): the
# lazy-created legacy batch mirrors migration 0008's seed contract exactly.
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"  # 0007 D-03 contract
LEGACY_BATCH_COMMENT = "Остаток до внедрения партий"

QTY_ERROR = "Укажите количество — целое число больше нуля."
ORIGIN_NOT_FOUND_ERROR = "Исходная продажа не найдена."
FULLY_RETURNED_ERROR = "Эта позиция уже возвращена полностью."
PRODUCT_UNAVAILABLE_ERROR = "Товар недоступен для возврата."
SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."


def _over_cap_error(remaining: int) -> str:
    return f"Нельзя вернуть больше, чем доступно ({remaining})."


def sold_qty(session: Session, sale_id: str, product_id: str) -> int:
    """Total quantity sold on this sale_id+product_id (always positive).

    Sale ops carry a negative qty_delta; negate to a positive sold count.
    """
    sold = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.sale_id == sale_id,
            Operation.product_id == product_id,
            Operation.type == "sale",
        )
    )
    return -sold


def returnable_qty(session: Session, sale_id: str, product_id: str) -> int:
    """D-08: sold - already-returned, aggregated per sale_id+product_id."""
    returned = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.sale_id == sale_id,
            Operation.product_id == product_id,
            Operation.type == "return",
        )
    )
    return sold_qty(session, sale_id, product_id) - returned


def resolve_return_batch(session: Session, origin: Operation) -> Batch | None:
    """The batch a return of `origin` targets (D-08), WITHOUT creating anything.

    Batched origin -> its own batch. Pre-Phase-9 (NULL batch_id) origin -> the
    product's seeded legacy batch, or None when none exists yet (the return
    write path will lazily create it). Read-only: safe for the display path.
    """
    if origin.batch_id is not None:
        return session.get(Batch, origin.batch_id)
    return legacy_batch(session, origin.product_id)


def _resolve_or_create_return_batch_id(session: Session, origin: Operation) -> str:
    """The batch id a return WRITE must attribute stock to (D-08).

    Batched origin -> origin.batch_id. NULL-batch origin -> the product's legacy
    batch id, lazily creating that legacy batch (frozen D-14 contract, quantity
    0) inside the caller's transaction when the product has none (Open Q1 — the
    third batch birth path). record_operation then increments its quantity.
    """
    if origin.batch_id is not None:
        return origin.batch_id
    batch = legacy_batch(session, origin.product_id)
    if batch is None:
        batch = Batch(
            id=new_id(),
            product_id=origin.product_id,
            warehouse_id=DEFAULT_WAREHOUSE_ID,
            expiry=None,
            price_cents=None,
            location=None,
            comment=LEGACY_BATCH_COMMENT,
            quantity=0,
            is_legacy=1,
        )
        session.add(batch)
        session.flush()  # materialize batch.id for record_operation to resolve
    return batch.id


def register_return(
    session: Session, *, origin_op_id: str, qty_raw: str
) -> tuple[dict | None, dict[str, str]]:
    """Register one sale-linked return; returns (result, errors).

    Success: ({"product": ..., "operation": ..., "remaining": ...}, {}).
    Failure: (None, errors) with RU messages — ZERO writes on any
    validation error (D-08: the returnable cap is enforced before any
    write).
    """
    # T-05-08: only a real, linked sale op is returnable — reject a
    # missing/forged/non-sale origin before anything else.
    origin = session.get(Operation, origin_op_id)
    if origin is None or origin.type != "sale" or origin.sale_id is None:
        return None, {"form": ORIGIN_NOT_FOUND_ERROR}

    # WR-01 analog: isascii()+isdigit() guard before int() (sales.py:92-93) —
    # a non-ASCII "digit" character would otherwise raise inside int().
    qty_text = qty_raw.strip()
    qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
    if qty <= 0:
        return None, {"quantity": QTY_ERROR}

    # D-08: cap by the aggregate remaining for this sale_id+product_id —
    # zero writes before the cap is checked.
    remaining = returnable_qty(session, origin.sale_id, origin.product_id)
    if remaining <= 0:
        return None, {"quantity": FULLY_RETURNED_ERROR}
    if qty > remaining:
        return None, {"quantity": _over_cap_error(remaining)}

    try:
        # D-08: restore stock to the ORIGIN op's batch (or the product's legacy
        # batch, lazily created when absent) — the return never re-asks.
        batch_id = _resolve_or_create_return_batch_id(session, origin)
        op = record_operation(
            session,
            type_="return",
            product_id=origin.product_id,
            qty_delta=qty,
            unit_price_cents=origin.unit_price_cents,  # D-07 frozen copy
            unit_cost_cents=origin.unit_cost_cents,  # D-07 frozen copy
            sale_id=origin.sale_id,
            batch_id=batch_id,
            payload={"origin_op_id": origin.id},
            commit=False,
        )

        # FIN-02/D-00d: the debit is computed INDEPENDENTLY from the
        # return's own qty x the origin op's FROZEN unit_price_cents —
        # never reconciled against or read from the prior sale credit row.
        debit = qty * (origin.unit_price_cents or 0)
        if debit:
            finance.record_cash_movement(
                session,
                category="return",
                amount_cents=-debit,
                sale_id=origin.sale_id,
                commit=False,
            )

        # T-15-03: close the return op + the cash debit in ONE commit.
        session.commit()
    except ValueError:
        # Pitfall 7: record_operation raises ValueError for a soft-deleted
        # product (IN-01 guard) — surface an RU 4xx, never a raw 500.
        session.rollback()
        return None, {"form": PRODUCT_UNAVAILABLE_ERROR}
    except IntegrityError:
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}

    return {
        "product": session.get(Product, origin.product_id),
        "operation": op,
        "remaining": remaining - qty,
    }, {}
