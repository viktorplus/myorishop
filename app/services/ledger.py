"""Ledger service (D-09/D-11/D-17): the SINGLE write path for stock changes.

record_operation is the only code that inserts operations rows or touches
products.quantity. Everything else reads. Cached quantity is a projection
of SUM(operations.qty_delta) and is always recomputable (FND-01).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import OPERATION_TYPES, Batch, Operation, Product

# D-12: the stock-affecting operation types. A batch_id is MANDATORY for these
# (they move stock into/out of a specific lot); the remaining OPERATION_TYPES
# are qty_delta==0 audit rows that must stay batch-less (batch_id is None).
STOCK_AFFECTING_TYPES = frozenset({"receipt", "sale", "writeoff", "return", "correction"})


def next_seq(session: Session, device_id: str) -> int:
    """Next per-device sequence number.

    Called ONLY inside record_operation's transaction (Pitfall 6):
    single writer + WAL serializes writes; UNIQUE(device_id, seq)
    is the loud backstop against any race.
    """
    current = session.scalar(
        select(func.max(Operation.seq)).where(Operation.device_id == device_id)
    )
    return (current or 0) + 1


def record_operation(
    session: Session,
    *,
    type_: str,
    product_id: str,
    qty_delta: int,
    unit_cost_cents: int | None = None,
    unit_price_cents: int | None = None,
    payload: dict | None = None,
    sale_id: str | None = None,
    batch_id: str | None = None,
    commit: bool = True,
) -> Operation:
    """Append one immutable ledger row and update the cached stock projection.

    This is the ONLY sanctioned write path for operations and
    products.quantity (FND-01). Audit fields are stamped from settings
    (FND-03, D-17). Everything happens in one transaction (D-09).

    WR-03: callers staging SEVERAL ops for one logical change pass
    commit=False for every call and issue ONE session.commit() at the end,
    so a crash cannot leave a partially written audit trail. next_seq still
    works: autoflush flushes pending ops before its max(seq) query.

    sale_id (D-03) links a `sale` op back to its Sale header; it is set at
    INSERT time only — the operations_no_update trigger ABORTs any later
    UPDATE. All other callers keep working untouched (default None).

    batch_id (D-10/D-11/D-12) attributes this ledger line to a Batch. It is
    now MANDATORY for stock-affecting types (STOCK_AFFECTING_TYPES): a missing
    batch raises ValueError — the single-write-path enforcement backstop for
    LOT-05 across all current and future callers. Audit types (qty_delta==0)
    stay batch-less: passing a batch_id to one raises ValueError. When a batch
    is supplied it is resolved and validated (ownership backstop: a
    client-submitted batch_id naming another product's batch is rejected), and
    Batch.quantity is incremented in the SAME transaction as Product.quantity
    (D-11).
    """
    if type_ not in OPERATION_TYPES:
        raise ValueError(f"unknown operation type: {type_!r}")

    # WR-01: validate BEFORE staging the row — session.get() autoflushes,
    # so a pending Operation with a bad FK would raise IntegrityError first.
    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"unknown product: {product_id!r}")
    # IN-01 / D-20: operations on soft-deleted products are REJECTED here,
    # in the single write path — one guard covers all current and future
    # operation types.
    if product.deleted_at is not None:
        raise ValueError(f"product is deleted: {product_id!r}")

    # D-12: the mandatory batch guard — the phase's write-path invariant.
    # Stock-affecting types REQUIRE a batch; audit types must not carry one.
    # The ownership check is the T-09 tampering mitigation — a client batch_id
    # is untrusted (mirrors the IN-01 guard).
    batch = None
    if type_ in STOCK_AFFECTING_TYPES:
        if batch_id is None:
            raise ValueError(f"batch_id is required for {type_!r} operations")
        batch = session.get(Batch, batch_id)
        if batch is None:
            raise ValueError(f"unknown batch: {batch_id!r}")
        if batch.product_id != product_id:
            raise ValueError("batch does not belong to product")
    elif batch_id is not None:
        raise ValueError(f"{type_!r} operations are batch-less")

    op = Operation(
        id=new_id(),
        type=type_,
        product_id=product_id,
        qty_delta=qty_delta,
        unit_cost_cents=unit_cost_cents,
        unit_price_cents=unit_price_cents,
        payload=payload,
        sale_id=sale_id,
        batch_id=batch_id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(op)
    # IN-02: SQL-side increment (UPDATE ... SET quantity = quantity + ?) —
    # atomic, no stale-ORM-value window. Same transaction (D-09).
    product.quantity = Product.quantity + qty_delta
    # D-11: dual projection — the per-lot cache updates in the same
    # transaction with the same SQL-side increment.
    if batch is not None:
        batch.quantity = Batch.quantity + qty_delta
    if commit:
        session.commit()
    return op


def compute_stock(session: Session, product_id: str) -> int:
    """Recompute stock for one product from the ledger alone (FND-01)."""
    return session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.product_id == product_id
        )
    )


def compute_batch_stock(session: Session, batch: Batch) -> int:
    """Recompute one batch's quantity from the ledger alone (D-11).

    Normal batch: SUM(qty_delta WHERE batch_id = batch.id).
    Legacy batch: also absorbs the frozen NULL bucket —
        SUM(qty_delta WHERE product_id = batch.product_id AND batch_id IS NULL)
    — so pre-Phase-9 rows (D-15) stay accounted for without a data rewrite.
    """
    total = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.batch_id == batch.id
        )
    )
    if batch.is_legacy:
        total += session.scalar(
            select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
                Operation.product_id == batch.product_id,
                Operation.batch_id.is_(None),
            )
        )
    return total


def rebuild_stock(session: Session) -> None:
    """Repair every cached quantity from the ledger and assert the invariant.

    Two passes (D-11): (1) recompute each Product.quantity (the batch-agnostic
    rollup, unchanged); (2) recompute each Batch.quantity. Then assert per
    product that Product.quantity == SUM(its batch quantities) PLUS the
    uncaptured NULL bucket — the latter added only for products the migration
    seeded NO legacy batch for (ledger stock <= 0, D-13). Raises on mismatch.
    """
    for product in session.scalars(select(Product)).all():
        product.quantity = compute_stock(session, product.id)

    batch_total_by_product: dict[str, int] = {}
    legacy_products: set[str] = set()
    for batch in session.scalars(select(Batch)).all():
        batch.quantity = compute_batch_stock(session, batch)
        batch_total_by_product[batch.product_id] = (
            batch_total_by_product.get(batch.product_id, 0) + batch.quantity
        )
        if batch.is_legacy:
            legacy_products.add(batch.product_id)

    for product in session.scalars(select(Product)).all():
        expected = batch_total_by_product.get(product.id, 0)
        if product.id not in legacy_products:
            # No legacy batch captured this product's NULL bucket — add it.
            expected += session.scalar(
                select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
                    Operation.product_id == product.id,
                    Operation.batch_id.is_(None),
                )
            )
        if product.quantity != expected:
            raise ValueError(f"stock invariant violated for product {product.id!r}")

    session.commit()


def ledger_view(session: Session) -> dict:
    """Read helper for routes (fat services, D-11).

    Returns the first active product, the latest operations and the
    ledger-recomputed stock for that product (None when no product).
    """
    product = session.scalars(
        select(Product)
        .where(Product.deleted_at.is_(None))
        .order_by(Product.created_at)
        .limit(1)
    ).first()
    operations = session.scalars(
        select(Operation)
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(50)
    ).all()
    computed_qty = compute_stock(session, product.id) if product else None
    return {"product": product, "operations": operations, "computed_qty": computed_qty}
