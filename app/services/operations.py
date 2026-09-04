"""Operations read service (OPS-04): the /history browsing slice.

Read-only — no writes happen here. All stock writes still go through the
single write path (app.services.ledger.record_operation). Portable ORM
only, no SQLite-specific SQL (D-05 sync-readiness).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    OPERATION_TYPES,
    Batch,
    Customer,
    Operation,
    Product,
    Sale,
    User,
    Warehouse,
)
from app.services.catalog import category_options
from app.services.customers import search_customers
from app.services.ledger import STOCK_AFFECTING_TYPES
from app.services.pagination import LIST_PAGE_SIZE
from app.services.reports import business_date_expr

# D-06/D-07/T-14-03: fixed sort allow-list — an unknown/tampered `sort` value
# falls back to the default order via `.get(sort, default)`, never string-
# interpolated into `order_by()`.
#
# Phase 33 D-22/DATE-04 — DO NOT "finish the job" here. This phase switches
# /history's period FILTER to the business date (below) and deliberately leaves
# the display ORDER on `created_at`, and adds no business-date sort option.
# `created_at` keeps all three of its jobs, display order included: «что я
# только что ввёл?» is answered by entry order, so a row entered now but
# back-dated a year must still appear at the top. Anyone switching _SORT_MAP or
# _DEFAULT_ORDER to `business_date` reddens
# tests/test_history.py::test_recent_feeds_still_order_by_created_at (VA-17).
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

# DATE-06/D-20/T-33-35: fixed allow-list for the «Задним числом» filter, the
# same discipline as `_SORT_MAP.get(sort, default)` above — an unknown or
# tampered value falls back to «Все» (no filter at all). The string itself
# NEVER reaches SQL: it only selects one of the two fixed ORM predicates built
# in `history_view`, and is never string-interpolated into a query.
_DATED_FILTERS = ("backdated", "same_day")


def _is_backdated(op: Operation, tz: ZoneInfo) -> bool:
    """True when this row's business date differs from the day it was ENTERED.

    THE MARKER AND THE FILTER COMPARE DIFFERENT THINGS, DELIBERATELY (33-14
    locked decision, `33-UI-SPEC.md` § Interaction Contract §6):

    * this marker compares `business_date` against the **LOCAL calendar day**
      of `created_at`, resolved with `settings.display_tz`;
    * the `dated` SQL predicate in `history_view` compares it against
      `substr(created_at, 1, 10)` — the **UTC** day — because that is the only
      form expressible in portable ORM (a local day in SQL needs
      `datetime(created_at, '+3 hours')` on SQLite or `created_at::date` on
      PostgreSQL, both banned by CLAUDE.md PC-2), and a stored marker column is
      out (the ledger is append-only and only four columns land this phase).

    Migration 0027's backfill is tz-correct, so for every normal historical row
    `business_date == local_day(created_at)` by construction — while the UTC
    prefix differs for every row entered between 21:00 and 24:00 UTC at
    Europe/Moscow (roughly 00:00-03:00 local). Using the UTC prefix HERE would
    falsely stamp «задним числом» on a share of perfectly normal rows and make
    DATE-07's «existing operations keep reporting exactly as they do today»
    visibly false in the UI.

    Accepted consequence: «Только задним числом» can return a row that carries
    no marker (the filter over-includes in that night window); the converse
    never happens, so no marked row is ever lost. Computing the marker in
    Python AFTER the page was fetched is not an option — `total` would then
    disagree with the rows and pagination would break, the exact defect
    `test_history_period_count_agrees_with_its_own_rows` pins. Pinned by
    `tests/test_history.py::test_backdated_filter_and_marker_diverge_only_on_utc_straddle`.

    DATE-08: a `business_date IS NULL` row (pushed by a pre-0027 client) is
    NEVER marked — it must render byte-identically to today.
    """
    if op.business_date is None:
        return False
    # Reuse audit (CLAUDE.md): app/core.py has `iso_to_local` (formats a
    # timestamp for DISPLAY) and `local_today_iso` (today only); neither yields
    # the local calendar DAY of an arbitrary stored timestamp. This is the only
    # caller, so it stays private here — move it beside `local_today_iso` if a
    # second one ever appears.
    local_day = datetime.fromisoformat(op.created_at).astimezone(tz).date().isoformat()
    return op.business_date != local_day


def history_view(
    session: Session,
    *,
    type_filter: str | None = None,
    product_id: str | None = None,
    customer: str | None = None,
    category: str | None = None,
    start_iso: str | None = None,
    end_iso: str | None = None,
    author_id: str | None = None,
    dated: str = "",
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
    Phase 33/DATE-03: `start_iso`/`end_iso` are now DATE-ONLY ISO days
    ('yyyy-mm-dd') produced by `app.core.business_date_bounds`, NOT the UTC
    timestamp bounds the routes used to build — the period is
    matched against `business_date_expr(Operation)` over a CLOSED range. Passing
    a full timestamp here silently drops rows (a date string sorts before its own
    'T...' suffix), so the caller must use `business_date_bounds`.
    `category` and `customer` are resolved to a bounded candidate set in
    PYTHON (T-23-04/T-23-05: never string-interpolated/lower()'d in SQL —
    SQLite lower()/LIKE cannot fold Cyrillic, D-27), then applied via a
    parameterized `.in_()`. `customer` is applied ONLY when `type_filter` is
    "sale" or "return" (D-05/T-23-06) — a defence-in-depth guard that ignores
    the filter for every other type regardless of caller intent.

    Phase 33/DATE-05/DATE-06: every row additionally carries `business_day`
    (the `String(10)` ISO business date, or None) and `is_backdated` (see
    `_is_backdated` — the marker compares against the LOCAL day of
    `created_at`, the `dated` predicate below against the UTC day, and that
    divergence is deliberate). `dated` is an allow-listed filter
    ("" / "backdated" / "same_day", `_DATED_FILTERS`) and is echoed back in the
    result dict so the surface's <select> can re-select itself after a swap.
    """
    order_by = _SORT_MAP.get(sort, _DEFAULT_ORDER)
    stmt = (
        select(Operation, Product, Batch, Warehouse, Customer, User)
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
        # USER-06 (Plan 08): LEFT OUTER JOIN the author — NEVER inner — so a
        # pre-auth NULL-author row (created_by frozen to "operator", author_id
        # NULL) is never dropped from the unfiltered view (RESEARCH Pitfall 2).
        # Surfaces the LIVE display_name per row; the template falls back to
        # the frozen created_by text when this join yields None.
        .outerjoin(User, Operation.author_id == User.id)
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

    # DATE-03: the period filter buckets by the BUSINESS date (the day the goods
    # actually moved), not by the entry timestamp — `business_date_expr` falls
    # back to substr(created_at, 1, 10) for a NULL column (DATE-08), so a row
    # pushed by a pre-0027 client is still bucketed, never dropped.
    # Bounds are the CLOSED [start_day, end_day] contract (`business_date_bounds`):
    # `>=` AND `<=`, never `<`.
    # T-33-22: these two predicates MUST move together — switching `stmt` alone
    # (or `count_stmt` alone) makes the pager's total disagree with its own rows,
    # and nothing but an explicit `len(rows) == total` assertion catches it.
    if start_iso is not None and end_iso is not None:
        period = (
            business_date_expr(Operation) >= start_iso,
            business_date_expr(Operation) <= end_iso,
        )
        stmt = stmt.where(*period)
        count_stmt = count_stmt.where(*period)

    # USER-06: optional author filter — additive, combines with AND, applied to
    # BOTH stmt and count_stmt (mirrors the customer/category kwarg blocks).
    # Parameterized `.where(...)` only (T-25-08-01): an unknown/absent id simply
    # matches no rows, never a raw 500. Pre-auth NULL-author rows do not match a
    # selected user — correct, they predate auth.
    if author_id:
        stmt = stmt.where(Operation.author_id == author_id)
        count_stmt = count_stmt.where(Operation.author_id == author_id)

    # DATE-06/D-20: the «Задним числом» filter. The comparison is against the
    # UTC day `substr(created_at, 1, 10)` — NOT the local day the `is_backdated`
    # marker uses — because only that form is expressible in portable ORM; see
    # `_is_backdated`'s docstring for the full trade-off and the test that pins
    # it. T-33-22: like the period predicate above, this MUST land on BOTH
    # `stmt` and `count_stmt` or the pager's total disagrees with its own rows.
    # T-33-35: `dated` is resolved through `_DATED_FILTERS` first, so only a
    # fixed ORM predicate is ever built — the operator's string never reaches SQL.
    dated_key = dated if dated in _DATED_FILTERS else ""
    if dated_key:
        entry_day_utc = func.substr(Operation.created_at, 1, 10)
        if dated_key == "backdated":
            dated_where = (
                Operation.business_date.is_not(None),
                Operation.business_date != entry_day_utc,
            )
        else:
            # DATE-08: the negation must KEEP a `business_date IS NULL` row (one
            # pushed by a pre-0027 client) instead of vanishing it — such a row
            # was not back-dated, so it belongs to «Только в день операции».
            # `NULL != x` is NULL in SQL, so the IS NULL branch is load-bearing.
            dated_where = (
                or_(
                    Operation.business_date.is_(None),
                    Operation.business_date == entry_day_utc,
                ),
            )
        stmt = stmt.where(*dated_where)
        count_stmt = count_stmt.where(*dated_where)

    total = session.scalar(count_stmt) or 0
    total_pages = max(1, -(-total // page_size))
    page = max(0, min(page, total_pages - 1))

    stmt = stmt.limit(page_size).offset(page * page_size)
    rows = session.execute(stmt).all()
    tz = ZoneInfo(settings.display_tz)
    return {
        "rows": [
            {
                "op": op,
                "product": p,
                "batch": b,
                "warehouse": w,
                "customer": c,
                # USER-06: live author (or None for a pre-auth NULL-author row —
                # the template then falls back to the frozen created_by text).
                "author": u,
                # DATE-05 (D-18/D-19): the PRIMARY date both surfaces render.
                # A String(10) ISO day, so templates MUST use `| ru_date` —
                # `| local_dt` would build a naive datetime and print a bogus
                # time. None for a DATE-08 pre-0027 row.
                "business_day": op.business_date,
                # DATE-06: the marker. False for every NULL-business_date row.
                "is_backdated": _is_backdated(op, tz),
            }
            for op, p, b, w, c, u in rows
        ],
        "page": page,
        "total": total,
        "total_pages": total_pages,
        "type_filter": type_filter or "",
        "product_id": product_id or "",
        "author_id": author_id or "",
        # DATE-06: echoed back NORMALISED (an unknown value comes back as "")
        # so the fourth <select> re-selects itself after an htmx swap and
        # `qs_parts` can carry it onto every pagination link (HIST-02).
        "dated": dated_key,
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
