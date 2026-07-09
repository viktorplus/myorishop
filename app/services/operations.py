"""Operations read service (OPS-04): the /history browsing slice.

Read-only — no writes happen here. All stock writes still go through the
single write path (app.services.ledger.record_operation). Portable ORM
only, no SQLite-specific SQL (D-05 sync-readiness).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OPERATION_TYPES, Operation, Product


def history_view(
    session: Session,
    *,
    type_filter: str | None = None,
    product_id: str | None = None,
    page: int = 0,
    page_size: int = 50,
) -> dict:
    """Paginated, filtered read over the whole operation ledger (D-13/D-15).

    Newest-first (created_at desc, seq desc). Fetches page_size + 1 rows as
    a has-next sentinel so the whole ledger is never materialized in one
    response (T-05-19). An unknown/tampered type_filter is ignored (treated
    as no filter) rather than raising (T-05-20).
    """
    stmt = (
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
    )
    if type_filter and type_filter in OPERATION_TYPES:
        stmt = stmt.where(Operation.type == type_filter)
    if product_id:
        stmt = stmt.where(Operation.product_id == product_id)
    stmt = stmt.limit(page_size + 1).offset(page * page_size)

    rows = session.execute(stmt).all()
    has_next = len(rows) > page_size
    return {
        "rows": [{"op": op, "product": p} for op, p in rows[:page_size]],
        "has_next": has_next,
        "page": page,
        "type_filter": type_filter or "",
        "product_id": product_id or "",
    }


def filter_products(session: Session) -> list[Product]:
    """Active products ordered by name_lc, for the «Товар» history filter."""
    return list(
        session.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
        ).all()
    )
