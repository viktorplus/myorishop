"""Service-level tests for app.services.dashboard (DASH-01..05).

Task 1: dashboard_now / catalog_status / period_metrics / dashboard_metrics.
Task 2 (stock_summary / recent_operations / dashboard_context composer)
lands in a later commit on this same plan.

Monkeypatch pattern: dashboard.py calls `datetime.now(tz)` internally (not
an injectable `today` param, per the plan's artifact list), so tests freeze
`dashboard.datetime` the same way tests/test_finance_reports.py monkeypatches
`utcnow_iso` — replace the module attribute with a stand-in whose `.now()`
returns a fixed value.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core import local_day_bounds_utc, new_id
from app.models import ActiveCatalog, Batch, Warehouse
from app.services import dashboard
from app.services.dashboard import (
    WEEKDAY_LABELS,
    catalog_status,
    dashboard_metrics,
    dashboard_now,
    period_metrics,
)
from app.services.finance import record_cash_movement
from app.services.ledger import record_operation

TZ = "Europe/Moscow"


def _ensure_batch(session, product):
    """A valid batch id for a product (mirrors tests/test_reports.py::_ensure_batch)."""
    batch = session.scalars(select(Batch).where(Batch.product_id == product.id)).first()
    if batch is None:
        warehouse = session.scalars(select(Warehouse)).first()
        if warehouse is None:
            warehouse = Warehouse(id=new_id(), name="Склад")
            session.add(warehouse)
            session.flush()
        batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
        session.add(batch)
        session.flush()
    return batch.id


def _record_sale_at(session, monkeypatch, iso, *, product, qty, price_cents, cost_cents=None):
    """Mirrors tests/test_reports.py::_record_sale_at."""
    import app.services.ledger as ledger_module

    batch_id = _ensure_batch(session, product)
    monkeypatch.setattr(ledger_module, "utcnow_iso", lambda: iso)
    return record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-qty,
        unit_cost_cents=cost_cents,
        unit_price_cents=price_cents,
        batch_id=batch_id,
    )


def _record_cash_at(session, monkeypatch, iso, *, category, amount_cents):
    """Mirrors tests/test_finance_reports.py::_record_cash_at."""
    import app.services.finance as finance_module

    monkeypatch.setattr(finance_module, "utcnow_iso", lambda: iso)
    return record_cash_movement(session, category=category, amount_cents=amount_cents)


class _FrozenDatetime:
    """Stand-in for the `datetime` class name inside app.services.dashboard."""

    _fixed: datetime

    @classmethod
    def now(cls, tz=None):  # noqa: ARG003 — tz ignored, _fixed already carries the right tz
        return cls._fixed


def _freeze_now(monkeypatch, fixed: datetime):
    frozen = type("Frozen", (_FrozenDatetime,), {"_fixed": fixed})
    monkeypatch.setattr(dashboard, "datetime", frozen)
    return frozen


# --- dashboard_now (DASH-01) -------------------------------------------------


def test_dashboard_now_returns_weekday_date_time():
    result = dashboard_now(TZ)
    assert set(result) == {"weekday", "date", "time"}
    now = datetime.now(ZoneInfo(TZ))
    assert result["weekday"] == WEEKDAY_LABELS[now.weekday()]


# --- catalog_status (DASH-02) ------------------------------------------------


def test_catalog_status_none_when_no_catalog_row():
    assert catalog_status(None, date(2026, 5, 20)) is None


def test_catalog_status_none_when_both_fields_blank():
    catalog = ActiveCatalog(id=new_id(), number=None, close_date=None)
    assert catalog_status(catalog, date(2026, 5, 20)) is None


def test_catalog_status_future_close_date_not_closed():
    today = date(2026, 5, 20)
    catalog = ActiveCatalog(
        id=new_id(), number="326", close_date=(today + timedelta(days=5)).isoformat()
    )
    result = catalog_status(catalog, today)
    assert result["days_left"] == 5
    assert result["closed"] is False


def test_catalog_status_past_close_date_is_closed():
    today = date(2026, 5, 20)
    catalog = ActiveCatalog(
        id=new_id(), number="326", close_date=(today - timedelta(days=1)).isoformat()
    )
    result = catalog_status(catalog, today)
    assert result["days_left"] == -1
    assert result["closed"] is True


def test_catalog_status_number_only_has_no_countdown():
    today = date(2026, 5, 20)
    catalog = ActiveCatalog(id=new_id(), number="326", close_date=None)
    result = catalog_status(catalog, today)
    assert result == {"number": "326", "close_date": None, "days_left": None, "closed": False}


# --- period_metrics (DASH-03, D-07/D-08) ------------------------------------


def test_period_metrics_net_profit_is_addition_not_subtraction(session, product, monkeypatch):
    day = date(2026, 7, 10)
    _record_sale_at(
        session,
        monkeypatch,
        "2026-07-10T10:00:00+00:00",
        product=product,
        qty=1,
        price_cents=1000,
        cost_cents=600,
    )
    _record_cash_at(
        session,
        monkeypatch,
        "2026-07-10T11:00:00+00:00",
        category="withdrawal_rent",
        amount_cents=-200,
    )

    result = period_metrics(session, day, day, TZ)
    assert result["revenue_cents"] == 1000
    assert result["expense_cents"] == -200
    # 400 + (-200) == 200 (addition) — NEVER 400 - 200 == 600 (D-08 regression guard).
    assert result["profit_cents"] == 200


# --- dashboard_metrics (DASH-03, D-09 3x generalization) --------------------


def test_dashboard_metrics_week_and_month_boundaries_match_resolve_period(
    session, product, monkeypatch
):
    """Boundaries must match app/routes/reports.py::_resolve_period byte-for-byte.

    A sale inside a window is counted; one just outside the half-open
    boundary is excluded (mirrors test_expense_total_half_open_bounds).
    """
    import app.routes.reports as reports_module

    fixed = datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo(TZ))  # Wednesday
    frozen = _freeze_now(monkeypatch, fixed)
    monkeypatch.setattr(reports_module, "datetime", frozen)

    period = reports_module._resolve_period("", "", TZ)
    week_start = date.fromisoformat(period["presets"]["week"]["from"])
    week_end = date.fromisoformat(period["presets"]["week"]["to"])
    month_start = date.fromisoformat(period["presets"]["month"]["from"])
    month_end = date.fromisoformat(period["presets"]["month"]["to"])

    # Sale ON week_start: inside both week and month.
    week_start_iso, _ = local_day_bounds_utc(week_start, week_start, TZ)
    _record_sale_at(
        session, monkeypatch, week_start_iso, product=product, qty=1, price_cents=500
    )
    # Sale the day BEFORE week_start: excluded from week, still inside month.
    before_week = week_start - timedelta(days=1)
    before_week_iso, _ = local_day_bounds_utc(before_week, before_week, TZ)
    _record_sale_at(
        session, monkeypatch, before_week_iso, product=product, qty=1, price_cents=700
    )

    metrics = dashboard_metrics(session, TZ)

    assert metrics["today"]["revenue_cents"] == 0
    assert metrics["week"]["revenue_cents"] == 500
    assert metrics["month"]["revenue_cents"] == 1200

    # Cross-check against reports.py's own boundary formulas directly.
    expected_week = period_metrics(session, week_start, week_end, TZ)
    expected_month = period_metrics(session, month_start, month_end, TZ)
    assert metrics["week"] == expected_week
    assert metrics["month"] == expected_month
