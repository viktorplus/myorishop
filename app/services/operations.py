"""Operations read service (OPS-04): the /history browsing slice.

Read-only — no writes happen here. All stock writes still go through the
single write path (app.services.ledger.record_operation). Portable ORM
only, no SQLite-specific SQL (D-05 sync-readiness).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import OPERATION_TYPES, Batch, Customer, Operation, Product, Sale, Warehouse
from app.services.catalog import category_options
from app.services.customers import search_customers
from app.services.ledger import STOCK_AFFECTING_TYPES
from app.services.pagination import LIST_PAGE_SIZE

# D-06/D-07/T-14-03: fixed sort allow-list — an unknown/tampered `sort` value
# falls back to the default order via `.get(sort, default)`, never string-
# interpolated into `order_by()`.
_SORT_MAP = {
    "oldest": (Operation.created_at.asc(), Operation.seq.asc()),
}
_DEFAULT_ORDER = (Operation.created_at.desc(), Operation.seq.desc())

# HIST-01 (Plan 02 Task 2, D-06): one entry per STOCK_AFFECTING_TYPES member —
# the narrowed per-type column set shown when that type is selected (short
# keys, 23-UI-SPEC.md Interaction 8's authoritative column table). No entry
# for the 3 audit types or for "no filter" (D-04/Pitfall 5): those fall back
# to the existing generic view, signaled by history_view's "columns" being
# None. This is also DASH-05's dashboard-feed column mapping (Plan 03) — one
# shared source of truth, never duplicated.
HISTORY_TYPE_COLUMNS: dict[str, tuple[str, ...]] = {
    "receipt": ("expiry", "qty", "cost"),
    "sale": ("expiry", "qty", "price", "cost", "profit", "customer"),
    "return": ("expiry", "qty", "price", "cost", "profit", "customer"),
    "writeoff": ("expiry", "qty", "cost", "reason"),
    "correction": ("expiry", "qty", "reason"),
    "transfer": ("expiry", "qty", "warehouse"),
}
assert set(HISTORY_TYPE_COLUMNS) == STOCK_AFFECTING_TYPES


def history_view(
    session: Session,
    *,
    type_filter: str | None = None,
    product_id: str | None = None,
    customer: str | None = None,
    category: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
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
    the append-only ledger is NEVER rewritten. Each row also carries its own
    `customer` (LEFT OUTER JOIN Sale then Customer via `Operation.sale_id`
    -> `Sale.customer_id`, None for a walk-in sale/non-sale op) — the
    per-type «Покупатель» column (Plan 04) needs a real Customer object,
    not just a filterable id.

    HIST-02 (Plan 02 Task 1): `customer`/`category`/`start_iso`/`end_iso` are
    additive kwargs, all combining with AND and with the existing filters.
    `category` and `customer` are resolved to a bounded candidate set in
    PYTHON (T-23-04/T-23-05: never string-interpolated/lower()'d in SQL —
    SQLite lower()/LIKE cannot fold Cyrillic, D-27), then applied via a
    parameterized `.in_()`. `customer` is applied ONLY when `type_filter` is
    "sale" or "return" (D-05/T-23-06) — a defence-in-depth guard that ignores
    the filter for every other type regardless of caller intent.
    """
    order_by = _SORT_MAP.get(sort, _DEFAULT_ORDER)
    stmt = (
        select(Operation, Product, Batch, Warehouse, Customer)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Batch, Operation.batch_id == Batch.id)
        # HIST-01: always outerjoined — cheap, Batch is already outerjoined —
        # so a transfer row (or any batched row) carries its OWN side's
        # warehouse (Pitfall 6: never a synthesized "from -> to" merge; each
        # of a transfer's two sibling rows resolves its own batch/warehouse
        # independently, exactly like qty_delta's sign already does).
        .outerjoin(Warehouse, Batch.warehouse_id == Warehouse.id)
        # HIST-01 (Plan 04): always outerjoined too — each row's own
        # Sale/Customer (or None for a walk-in/non-sale op), same 1:1
        # per-row attribution pattern as Warehouse above; never fans out
        # rows since Operation.sale_id -> Sale is at most one-to-one.
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
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

    category_q = (category or "").strip().lower()
    if category_q:
        matched_categories = [c for c in category_options(session) if category_q in c.lower()]
        stmt = stmt.where(Product.category.in_(matched_categories))
        count_stmt = count_stmt.where(Product.category.in_(matched_categories))

    customer_q = (customer or "").strip()
    if customer_q and type_filter in ("sale", "return"):
        candidate_ids = [c.id for c in search_customers(session, customer_q)]
        # T-23-07: both hops stay .outerjoin() — never .join() — so a walk-in
        # sale (Sale.customer_id IS NULL) or a non-sale op is never silently
        # dropped from the joined result set; the .in_() below is what
        # actually narrows the rows. `stmt` already outerjoins Sale
        # unconditionally (Plan 04, for per-row customer attribution) —
        # re-joining it here would duplicate the join, so only `.where(...)`
        # is added to stmt; count_stmt still needs its own outerjoin.
        stmt = stmt.where(Sale.customer_id.in_(candidate_ids))
        count_stmt = count_stmt.outerjoin(Sale, Operation.sale_id == Sale.id).where(
            Sale.customer_id.in_(candidate_ids)
        )

    if start_iso is not None and end_iso is not None:
        stmt = stmt.where(Operation.created_at >= start_iso, Operation.created_at < end_iso)
        count_stmt = count_stmt.where(
            Operation.created_at >= start_iso, Operation.created_at < end_iso
        )

    total = session.scalar(count_stmt) or 0
    total_pages = max(1, -(-total // page_size))
    page = max(0, min(page, total_pages - 1))

    stmt = stmt.limit(page_size).offset(page * page_size)
    rows = session.execute(stmt).all()
    return {
        "rows": [
            {"op": op, "product": p, "batch": b, "warehouse": w, "customer": c}
            for op, p, b, w, c in rows
        ],
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "type_filter": type_filter or "",
        "product_id": product_id or "",
        "sort": sort or "",
        # HIST-01: None for "no type selected" AND for the 3 audit types —
        # both cases are simply absent from HISTORY_TYPE_COLUMNS (D-04).
        "columns": HISTORY_TYPE_COLUMNS.get(type_filter),
    }


def filter_products(session: Session) -> list[Product]:
    """Active products ordered by name_lc, for the «Товар» history filter."""
    return list(
        session.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
        ).all()
    )
