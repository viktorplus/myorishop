"""Reports read service (RPT-01/RPT-03/RPT-04): Phase 6 is 100% read-only.

No operation types are added here and no ledger writes happen here — every
function in this module only ever SELECTs. Portable ORM only, no
SQLite-specific SQL (D-05 sync-readiness), matching every other service in
this codebase.
"""

from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import DEFAULT_CURRENCY
from app.models import WRITEOFF_REASONS, Batch, Operation, Product, Warehouse


def operation_currency_clause(currency: str):
    """LOCKED decision: the shared currency predicate for Operation-based reports.

    `Operation.batch_id` is nullable (pre-Phase-9 legacy rows, which predate
    any warehouse/currency concept). Currency resolves via
    `Operation.batch_id -> Batch.warehouse_id -> Warehouse.currency`, falling
    back to `DEFAULT_CURRENCY` (RUB) when `batch_id IS NULL` — matching
    migration 0023's backfill (every pre-existing row has always been RUB).

    Callers MUST reach this predicate through an OUTER join chain
    (`.outerjoin(Batch, Operation.batch_id == Batch.id)
    .outerjoin(Warehouse, Batch.warehouse_id == Warehouse.id)`) — an INNER
    join would silently DROP legacy rows from every currency's report
    instead of counting the NULL ones under RUB, which is a
    data-loss-shaped bug. This is ONE shared helper, never re-implemented
    inline per report.
    """
    return func.coalesce(Warehouse.currency, DEFAULT_CURRENCY) == currency


# Home-placement rationale: this module imports only `app.config`, `app.core`
# and `app.models`, so `export.py`, `operations.py`, `customers.py`,
# `finance_reports.py` and `warehouses.py` can all import from it without a
# cycle — and `dashboard.py:25` already does today. `app/core.py` is NOT the
# home because it imports no SQLAlchemy at all.
def business_date_expr(model):
    """The shared READ expression for the business date (DATE-03/DATE-08).

    `model` is the mapped class that carries the column — `Operation` or
    `CashMovement`; both tables have it and five different service modules
    need the same expression, so it is parameterised rather than duplicated.

    `business_date` is NULLABLE with no default of any kind, and that NULL is
    a meaningful sentinel: it means "this row was written by a client that
    predates the column". The fallback is `substr(created_at, 1, 10)`, so such
    a row is bucketed by its entry date instead of VANISHING from every
    period-scoped report — which is what makes DATE-08 a live property rather
    than a fixture-only branch. It cannot be replaced by a one-off backfill:
    rows arriving from an un-upgraded client AFTER the migration have
    `business_date IS NULL` forever.

    The two-format asymmetry is deliberate and must NOT be "unified":
    this READ fallback is a UTC prefix and is knowingly NOT the tz-correct
    local day — for a row a pre-update client wrote there is no better
    information available, and DATE-08 only requires that the row still
    appears, bucketed by its entry date. Migration 0027's BACKFILL, by
    contrast, holds the full timestamp and MUST be tz-correct (it converts
    through ZoneInfo), or an evening row moves into the wrong month.

    Callers MUST obey the CLOSED bounds contract of `core.business_date_bounds`
    — `>= start` AND `<= end`, never `<` (see that docstring). This must also
    stay a portable ORM construct: `func.substr` renders as `substr(...)` on
    both SQLite and PostgreSQL. Never reach for `strftime`, `date_trunc`,
    `::date` or `SUBSTRING(... FROM ... FOR ...)` (CLAUDE.md PC-2). This is ONE
    shared helper, never re-implemented inline per report.
    """
    return func.coalesce(model.business_date, func.substr(model.created_at, 1, 10))


def sales_profit_report(
    session: Session,
    start_iso: str,
    end_iso: str,
    author_id: str | None = None,
    currency: str = DEFAULT_CURRENCY,
) -> dict:
    """Sales/profit totals and per-product breakdown for the CLOSED business-date period.

    DATE-03: `start_iso`/`end_iso` are date-only ISO days from
    `core.business_date_bounds` — the operator's LOCAL calendar days — and the
    range is CLOSED on both ends (`>= start` AND `<= end`, never `<`). Rows are
    bucketed by `business_date_expr(Operation)`, so a sale entered today for
    goods that moved last week lands in LAST WEEK's report. `created_at` is
    deliberately NOT consulted here (DATE-04: it keeps its audit/sync-ordering
    jobs and nothing else).

    RESEARCH Pitfall 2: unit_cost_cents is nullable — a sale line whose cost
    was never entered contributes its full revenue to totals["revenue_cents"]
    but is EXCLUDED from cost_cents/profit_cents (never treated as
    zero-cost, which would silently inflate profit by the line's whole
    revenue). Its count is surfaced separately as cost_unknown_count so the
    caller can show a visible caveat instead of a silently wrong number.

    RESEARCH Pitfall 5: this report is historical — it deliberately does
    NOT filter Product.deleted_at, so a product soft-deleted after the
    period still appears in a report for a period before its deletion.

    CUR-02: `currency` scopes the report to ONE currency, via the shared
    operation_currency_clause helper (see its docstring for the LOCKED
    legacy-row fallback rule).
    """
    stmt = (
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Batch, Operation.batch_id == Batch.id)
        .outerjoin(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(
            Operation.type == "sale",
            business_date_expr(Operation) >= start_iso,
            business_date_expr(Operation) <= end_iso,
            operation_currency_clause(currency),
        )
    )
    # RPT-01 (Plan 08): optional operator filter — extra parameterized
    # `.where(...)` mirroring the period bounds above. An unknown/absent id
    # matches no rows (T-25-08-01, never a raw 500); pre-auth NULL-author sale
    # rows are excluded when a user is selected (they predate auth). author_id
    # None reproduces the all-authors report exactly.
    if author_id:
        stmt = stmt.where(Operation.author_id == author_id)
    rows = session.execute(stmt).all()

    entries: dict[str, dict] = {}
    cost_unknown_count = 0
    for op, product in rows:
        qty = -op.qty_delta
        entry = entries.setdefault(
            product.id,
            {
                "product": product,
                "qty": 0,
                "revenue_cents": 0,
                "cost_cents": 0,
                "profit_cents": 0,
            },
        )
        entry["qty"] += qty
        revenue = (op.unit_price_cents or 0) * qty
        entry["revenue_cents"] += revenue
        if op.unit_cost_cents is not None:
            cost = op.unit_cost_cents * qty
            entry["cost_cents"] += cost
            entry["profit_cents"] += revenue - cost
        else:
            cost_unknown_count += 1

    by_product = sorted(entries.values(), key=lambda e: e["qty"], reverse=True)

    totals = {
        "units_sold": sum(e["qty"] for e in by_product),
        "revenue_cents": sum(e["revenue_cents"] for e in by_product),
        "cost_cents": sum(e["cost_cents"] for e in by_product),
        "profit_cents": sum(e["profit_cents"] for e in by_product),
        "cost_unknown_count": cost_unknown_count,
    }

    return {
        "totals": totals,
        "by_product": by_product,
        "cost_unknown_count": cost_unknown_count,
    }


def writeoff_report(session: Session, start_iso: str, end_iso: str) -> dict:
    """Write-offs in the CLOSED business-date period, grouped by reason_code.

    DATE-03: same contract as sales_profit_report — date-only bounds from
    `core.business_date_bounds`, bucketed by `business_date_expr(Operation)`,
    inclusive on both ends. A bucketing error here nets out in `total_qty` and
    shows up only on a PER-REASON line, which is why the tests assert per reason.

    RESEARCH/UI-SPEC: one row per WRITEOFF_REASONS key PRESENT in the
    period, in WRITEOFF_REASONS' own declared key order — not insertion
    order, not quantity order, so the list is stable across reports. A
    reason with zero write-offs in the period is omitted entirely.

    RESEARCH Pitfall 5 (same rule as sales_profit_report): this report is
    historical — it deliberately does NOT filter Product.deleted_at, so a
    product soft-deleted after the period still appears in a report for a
    period before its deletion.
    """
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(
            Operation.type == "writeoff",
            business_date_expr(Operation) >= start_iso,
            business_date_expr(Operation) <= end_iso,
        )
    ).all()

    by_reason: dict[str, dict] = defaultdict(lambda: {"qty": 0, "lines": []})
    for op, product in rows:
        qty = -op.qty_delta
        reason_code = (op.payload or {}).get("reason_code", "other")
        by_reason[reason_code]["qty"] += qty
        by_reason[reason_code]["lines"].append({"op": op, "product": product})

    result = [
        {
            "reason_code": code,
            "label": label,
            "qty": by_reason[code]["qty"],
            "lines": by_reason[code]["lines"],
        }
        for code, label in WRITEOFF_REASONS.items()
        if code in by_reason
    ]

    return {
        "by_reason": result,
        "total_qty": sum(entry["qty"] for entry in result),
    }


def _effective_stale_days(product: Product) -> int:
    """Product's own stale_days if set (even 0), else the global default.

    Deliberately NOT imported from app.services.stock: stale_days is a
    reports-only concern distinct from stock levels, so this stays a
    separate small helper local to this module (mirrors
    app.services.stock.effective_low_stock_threshold's exact "is not None"
    discipline — Pitfall 3 — without cross-module coupling).
    """
    return product.stale_days if product.stale_days is not None else settings.stale_days


def top_selling_products(
    session: Session, start_iso: str, end_iso: str, limit: int = 10
) -> list[dict]:
    """Top products by units sold (descending) in the CLOSED business-date period.

    DATE-03: period-scoped by its own signature, so it switches with the rest of
    the family — date-only bounds from `core.business_date_bounds`, bucketed by
    `business_date_expr(Operation)`, inclusive on both ends. Getting the period
    wrong here changes the RANKING, not just a total.

    RESEARCH Pattern 4: SQL-side aggregation (func.sum/.group_by()/.order_by()
    /.limit()), not a Python accumulator — sales history can be large,
    unlike the small fixed-cardinality write-off grouping in writeoff_report.
    """
    units_sold = func.sum(-Operation.qty_delta).label("units_sold")
    stmt = (
        select(Product, units_sold)
        .join(Operation, Operation.product_id == Product.id)
        .where(
            Operation.type == "sale",
            business_date_expr(Operation) >= start_iso,
            business_date_expr(Operation) <= end_iso,
        )
        .group_by(Product.id)
        .order_by(units_sold.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    return [{"product": product, "units_sold": units} for product, units in rows]


def stale_products(session: Session) -> list[dict]:
    """Active products with no sale in longer than their effective stale_days.

    RESEARCH Pattern 4: LEFT OUTER JOIN so a product with zero matching
    Operation rows still appears in the base result set (last_sale=None,
    i.e. genuinely never sold) — a plain .join() would silently drop it.
    Independent of any period filter (RPT-04/D-03). Excludes soft-deleted
    products (RESEARCH Open Question 2: nothing actionable on a deleted
    product), unlike sales_profit_report/writeoff_report which are
    historical and deliberately do NOT filter deleted_at (Pitfall 5 — that
    rule applies to THOSE functions, not this one).
    """
    # D-25: this stays on `created_at` DELIBERATELY — do NOT "finish the sweep"
    # by switching it to business_date_expr with the rest of Phase 33. It answers
    # «how long since this product last MOVED», a question about real elapsed
    # time, not about the operator's bookkeeping period; a back-dated entry made
    # today must not make a product look freshly sold a month ago. The pre-existing
    # type asymmetry with `today_local` below (ISO timestamp vs local date) is
    # accepted as-is: pre-existing, not introduced by Phase 33.
    last_sale = func.max(Operation.created_at).label("last_sale")
    stmt = (
        select(Product, last_sale)
        .outerjoin(
            Operation,
            (Operation.product_id == Product.id) & (Operation.type == "sale"),
        )
        .where(Product.deleted_at.is_(None))
        .group_by(Product.id)
    )
    rows = session.execute(stmt).all()

    today_local: date = datetime.now(ZoneInfo(settings.display_tz)).date()

    never_sold: list[dict] = []
    stale_with_date: list[dict] = []
    for product, last_sale_iso in rows:
        if last_sale_iso is None:
            never_sold.append(
                {"product": product, "last_sale_iso": None, "days_since": None}
            )
            continue
        days_since = (
            today_local - datetime.fromisoformat(last_sale_iso).astimezone(
                ZoneInfo(settings.display_tz)
            ).date()
        ).days
        if days_since > _effective_stale_days(product):
            stale_with_date.append(
                {
                    "product": product,
                    "last_sale_iso": last_sale_iso,
                    "days_since": days_since,
                }
            )

    # Never-sold first, then stale-with-a-date sorted by days_since descending
    # (two lists concatenated, rather than one combined sort key, for clarity).
    stale_with_date.sort(key=lambda row: row["days_since"], reverse=True)
    return never_sold + stale_with_date
