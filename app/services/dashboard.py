"""Dashboard composer service (DASH-01..05): the single read-only call
Главная needs.

Zero ledger writes — 100% read composition over already-shipped Phase
6/16/17 reporting services. Per D-09, this is achieved by generalizing two
existing single-purpose shapes rather than inventing new aggregation logic:
`_metrics_context`'s single-period composition (app/routes/finance.py)
becomes 3 simultaneous periods here (`period_metrics`/`dashboard_metrics`).
Task 2 (stock_summary/recent_operations/dashboard_context) lands in a
later commit on this same plan.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core import local_day_bounds_utc
from app.models import ActiveCatalog
from app.services.finance_reports import cash_expense_total
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
