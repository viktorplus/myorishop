"""Batch read helpers (D-07/D-08/D-13): the query side of batch tracking.

Batches are born only via receipts and the legacy migration (D-03); this
module never writes. It backs the sale/writeoff/correction pickers and the
receipt chooser. Read-only, session-first, RU-free (display strings live in
templates), mirroring the warehouses service shape.
"""

from sqlalchemy import nullslast, select
from sqlalchemy.orm import Session

from app.models import Batch, Product, Warehouse


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
