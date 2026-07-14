"""Operations read service (OPS-04): the /history browsing slice.

Read-only — no writes happen here. All stock writes still go through the
single write path (app.services.ledger.record_operation). Portable ORM
only, no SQLite-specific SQL (D-05 sync-readiness).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OPERATION_TYPES, Batch, Operation, Product
from app.services.pagination import LIST_PAGE_SIZE

# D-06/D-07/T-14-03: fixed sort allow-list — an unknown/tampered `sort` value
# falls back to the default order via `.get(sort, default)`, never string-
# interpolated into `order_by()`.
_SORT_MAP = {
    "oldest": (Operation.created_at.asc(), Operation.seq.asc()),
}
_DEFAULT_ORDER = (Operation.created_at.desc(), Operation.seq.desc())


def history_view(
    session: Session,
    *,
    type_filter: str | None = None,
    product_id: str | None = None,
    sort: str = "",
    page: int = 0,
    page_size: int = LIST_PAGE_SIZE,
) -> dict:
    """Paginated, filtered, sorted read over the whole operation ledger (D-01..D-07/D-13/D-15).

    Newest-first by default (created_at desc, seq desc); `sort="oldest"`
    reverses that (D-06/D-07). Returns a real total-count-based page
    (`total`/`total_pages`) instead of a `has_next` sentinel (D-02). An
    unknown/tampered `type_filter` is ignored (treated as no filter) rather
    than raising (T-05-20); an out-of-range `page` is clamped server-side
    into `[0, total_pages - 1]` (T-14-04).

    D-15: LEFT OUTER JOIN Batch so each row carries its batch (or None for a
    pre-Phase-9 NULL batch_id op) — batch attribution is resolved at READ time;
    the append-only ledger is NEVER rewritten.
    """
    order_by = _SORT_MAP.get(sort, _DEFAULT_ORDER)
    stmt = (
        select(Operation, Product, Batch)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Batch, Operation.batch_id == Batch.id)
        .order_by(*order_by)
    )
    count_stmt = (
        select(func.count())
        .select_from(Operation)
        .join(Product, Operation.product_id == Product.id)
    )
    if type_filter and type_filter in OPERATION_TYPES:
        stmt = stmt.where(Operation.type == type_filter)
        count_stmt = count_stmt.where(Operation.type == type_filter)
    if product_id:
        stmt = stmt.where(Operation.product_id == product_id)
        count_stmt = count_stmt.where(Operation.product_id == product_id)

    total = session.scalar(count_stmt) or 0
    total_pages = max(1, -(-total // page_size))
    page = max(0, min(page, total_pages - 1))

    stmt = stmt.limit(page_size).offset(page * page_size)
    rows = session.execute(stmt).all()
    return {
        "rows": [{"op": op, "product": p, "batch": b} for op, p, b in rows],
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "type_filter": type_filter or "",
        "product_id": product_id or "",
        "sort": sort or "",
    }


def filter_products(session: Session) -> list[Product]:
    """Active products ordered by name_lc, for the «Товар» history filter."""
    return list(
        session.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
        ).all()
    )
