"""Ledger service (D-09/D-11/D-17): the SINGLE write path for stock changes.

record_operation is the only code that inserts operations rows or touches
products.quantity. Everything else reads. Cached quantity is a projection
of SUM(operations.qty_delta) and is always recomputable (FND-01).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import OPERATION_TYPES, Operation, Product


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
) -> Operation:
    """Append one immutable ledger row and update the cached stock projection.

    This is the ONLY sanctioned write path for operations and
    products.quantity (FND-01). Audit fields are stamped from settings
    (FND-03, D-17). Everything happens in one transaction (D-09).
    """
    if type_ not in OPERATION_TYPES:
        raise ValueError(f"unknown operation type: {type_!r}")

    op = Operation(
        id=new_id(),
        type=type_,
        product_id=product_id,
        qty_delta=qty_delta,
        unit_cost_cents=unit_cost_cents,
        unit_price_cents=unit_price_cents,
        payload=payload,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(op)
    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"unknown product: {product_id!r}")
    product.quantity += qty_delta  # cached projection, same transaction (D-09)
    session.commit()
    return op


def compute_stock(session: Session, product_id: str) -> int:
    """Recompute stock for one product from the ledger alone (FND-01)."""
    return session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.product_id == product_id
        )
    )


def rebuild_stock(session: Session) -> None:
    """Repair every cached quantity from the ledger (including soft-deleted)."""
    products = session.scalars(select(Product)).all()
    for product in products:
        product.quantity = compute_stock(session, product.id)
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
