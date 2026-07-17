"""Dashboard composer service (DASH-01..05): the single read-only call
Главная needs.

Zero ledger writes — 100% read composition over already-shipped Phase
6/16/17 reporting services. Per D-09, this is achieved by generalizing two
existing single-purpose shapes rather than inventing new aggregation logic:
`_metrics_context`'s single-period composition (app/routes/finance.py)
becomes 3 simultaneous periods here (`period_metrics`/`dashboard_metrics`),
and `recent_sales`'s type-locked feed query (app/services/sales.py) becomes
a 6-type feed (`recent_operations`). `stock_summary`'s product_count is the
one genuinely new SQL aggregation this module adds.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import local_day_bounds_utc
from app.models import ActiveCatalog, Batch, Customer, Operation, Product, Sale
from app.services.active_catalog import get_active_catalog
from app.services.finance_reports import cash_expense_total, stock_valuation
from app.services.ledger import STOCK_AFFECTING_TYPES
from app.services.reports import sales_profit_report

# Indexed by date.weekday() (Monday=0..Sunday=6) — DASH-01.
WEEKDAY_LABELS = [
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
]


def dashboard_now(tz_name: str) -> dict:
    """Current date/weekday/time in the given tz (DASH-01)."""
    now = datetime.now(ZoneInfo(tz_name))
    return {
        "weekday": WEEKDAY_LABELS[now.weekday()],
        "date": now.strftime("%d.%m.%Y"),
        "time": now.strftime("%H:%M"),
    }


def catalog_status(catalog: ActiveCatalog | None, today: date) -> dict | None:
    """Active-catalog countdown or empty state (DASH-02).

    None when there is no row, or the row exists but both `number` and
    `close_date` are blank/None (23-CONTEXT.md's placeholder-state rule —
    an empty catalog is not an error). `days_left`/`closed` are only
    computed when `close_date` is actually set; both stay None/False when
    only `number` is set.
    """
    if catalog is None:
        return None
    if not catalog.number and not catalog.close_date:
        return None
    days_left: int | None = None
    closed = False
    if catalog.close_date:
        days_left = (date.fromisoformat(catalog.close_date) - today).days
        closed = days_left < 0
    return {
        "number": catalog.number,
        "close_date": catalog.close_date,
        "days_left": days_left,
        "closed": closed,
    }


def period_metrics(session: Session, start_day: date, end_day: date, tz_name: str) -> dict:
    """Revenue/net-profit/expense for one local calendar-day range (DASH-03).

    Mirrors app/routes/finance.py::_metrics_context's single-period shape:
    `expense_cents` is cash_expense_total's raw (already-negative) value —
    D-07's expense definition (cash-ledger withdrawals + returns, the SAME
    set Финансы uses, never cost-of-goods-sold) — rendered as-is, never
    negated here. `profit_cents` is the NET figure: gross + expense, D-08,
    addition only (never subtraction).
    """
    start_iso, end_iso = local_day_bounds_utc(start_day, end_day, tz_name)
    gross = sales_profit_report(session, start_iso, end_iso)
    expense_cents = cash_expense_total(session, start_iso, end_iso)
    return {
        "revenue_cents": gross["totals"]["revenue_cents"],
        "profit_cents": gross["totals"]["profit_cents"] + expense_cents,
        "expense_cents": expense_cents,
    }


def dashboard_metrics(session: Session, tz_name: str) -> dict:
    """today/week/month period_metrics (DASH-03), D-09's 3x generalization.

    Boundary formulas replicated locally (not imported from app.routes.reports
    — services do not import routes in this codebase), byte-for-byte
    identical to _resolve_period's own Monday-start-week / calendar-month
    math so Главная never disagrees with /reports or /finance.
    """
    today = datetime.now(ZoneInfo(tz_name)).date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return {
        "today": period_metrics(session, today, today, tz_name),
        "week": period_metrics(session, week_start, week_end, tz_name),
        "month": period_metrics(session, month_start, month_end, tz_name),
    }


def stock_summary(session: Session) -> dict:
    """Stock valuation + distinct-code count (DASH-04).

    product_count is a single SQL count aggregation (never a Python loop,
    Don't-Hand-Roll table) — the one genuinely new aggregation this plan
    adds; nothing existing computes it today.
    """
    product_count = session.scalar(
        select(func.count())
        .select_from(Product)
        .where(Product.deleted_at.is_(None), Product.quantity > 0)
    )
    return {**stock_valuation(session), "product_count": product_count}


def recent_operations(session: Session, limit: int = 10) -> list[dict]:
    """Last N stock-affecting ops joined to product/batch/customer (DASH-05).

    D-09's generalization of sales.py::recent_sales's exact double-outerjoin
    shape to all 6 STOCK_AFFECTING_TYPES. Both the Sale and Customer
    outerjoins MUST stay outer (Pitfall 4) — a receipt/writeoff/correction/
    transfer row has sale_id IS NULL by construction and must still appear;
    a walk-in sale has customer_id IS NULL and must still appear.
    """
    rows = session.execute(
        select(Operation, Product, Batch, Customer)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Batch, Operation.batch_id == Batch.id)
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
        .where(Operation.type.in_(STOCK_AFFECTING_TYPES))
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [
        {"op": op, "product": product, "batch": batch, "customer": customer}
        for op, product, batch, customer in rows
    ]


def dashboard_context(session: Session, tz_name: str) -> dict:
    """The single composer call app/routes/home.py and mobile_home.py need.

    Never raises when no ActiveCatalog row exists (DASH-02's empty-state
    contract) — every other key renders unconditionally regardless of the
    catalog state.
    """
    today = datetime.now(ZoneInfo(tz_name)).date()
    return {
        **dashboard_now(tz_name),
        "catalog": catalog_status(get_active_catalog(session), today),
        "metrics": dashboard_metrics(session, tz_name),
        "stock": stock_summary(session),
        "feed": recent_operations(session, limit=10),
    }
