"""Service-level tests for app.services.finance_reports (FIN-08/FIN-11/FIN-12).

Read-only aggregation tests: cash_expense_total (net-profit expense set,
D-01a), stock_valuation (product-level, NULL-price exclusion, D-02),
cash_flow_report (income-vs-expense grouping reconciled with
cash_expense_total, D-05).
"""

from datetime import date

from app.core import local_day_bounds_utc, new_id
from app.models import Product
from app.services.finance import record_cash_movement
from app.services.finance_reports import (
    cash_expense_total,
    cash_flow_report,
    stock_valuation,
)

DAY = date(2026, 7, 10)
TZ = "Europe/Moscow"


def _record_cash_at(session, monkeypatch, iso, *, category, amount_cents):
    """Record one cash movement with a caller-controlled created_at.

    Monkeypatches app.services.finance.utcnow_iso (mirrors
    tests/test_reports.py::_record_sale_at's ledger monkeypatch) so the
    stamped created_at is exactly the iso string given here — needed to
    place movements precisely inside or outside a period boundary.
    """
    import app.services.finance as finance_module

    monkeypatch.setattr(finance_module, "utcnow_iso", lambda: iso)
    return record_cash_movement(session, category=category, amount_cents=amount_cents)


# --- cash_expense_total (FIN-11 / D-01a) ------------------------------------


def test_expense_total_sums_withdrawal_and_return(session, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    _record_cash_at(
        session, monkeypatch, mid, category="withdrawal_supplier", amount_cents=-1000
    )
    _record_cash_at(session, monkeypatch, mid, category="return", amount_cents=-500)

    assert cash_expense_total(session, start_iso, end_iso) == -1500


def test_expense_total_excludes_income_categories(session, monkeypatch):
    """A deposit_opening (+) and a sale (+) in the same period are EXCLUDED."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    _record_cash_at(
        session, monkeypatch, mid, category="deposit_opening", amount_cents=5000
    )
    _record_cash_at(session, monkeypatch, mid, category="sale", amount_cents=3000)
    _record_cash_at(
        session, monkeypatch, mid, category="withdrawal_rent", amount_cents=-800
    )

    assert cash_expense_total(session, start_iso, end_iso) == -800


def test_expense_total_empty_period_is_zero(session):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    assert cash_expense_total(session, start_iso, end_iso) == 0


def test_expense_total_half_open_bounds(session, monkeypatch):
    """A row stamped exactly at end_iso is EXCLUDED; a row at start_iso is INCLUDED."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    _record_cash_at(
        session, monkeypatch, start_iso, category="withdrawal_rent", amount_cents=-800
    )
    _record_cash_at(
        session, monkeypatch, end_iso, category="withdrawal_rent", amount_cents=-900
    )

    assert cash_expense_total(session, start_iso, end_iso) == -800


def test_expense_total_net_reconciliation_is_addition(session, monkeypatch):
    """Net reconciliation: for gross profit G, G + cash_expense_total(...) — plain addition."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    _record_cash_at(
        session, monkeypatch, mid, category="withdrawal_rent", amount_cents=-800
    )

    gross_profit_cents = 5000
    expense = cash_expense_total(session, start_iso, end_iso)
    net_profit_cents = gross_profit_cents + expense
    assert net_profit_cents == 4200


# --- stock_valuation (FIN-12 / D-02) ----------------------------------------


def test_stock_valuation_sums_active_products(session):
    session.add_all(
        [
            Product(
                id=new_id(),
                code="A",
                name="Товар A",
                quantity=2,
                cost_cents=1000,
                sale_cents=1500,
            ),
            Product(
                id=new_id(),
                code="B",
                name="Товар B",
                quantity=3,
                cost_cents=500,
                sale_cents=800,
            ),
        ]
    )
    session.commit()

    result = stock_valuation(session)
    assert result["cost_value_cents"] == 3500
    assert result["sale_value_cents"] == 5400


def test_stock_valuation_excludes_null_prices_and_counts_unknown(session):
    session.add(
        Product(
            id=new_id(),
            code="C",
            name="Товар C",
            quantity=2,
            cost_cents=None,
            sale_cents=None,
        )
    )
    session.commit()

    result = stock_valuation(session)
    assert result["cost_value_cents"] == 0
    assert result["sale_value_cents"] == 0
    assert result["cost_unknown_count"] == 1
    assert result["sale_unknown_count"] == 1


def test_stock_valuation_unknown_count_restricted_to_positive_quantity(session):
    """A NULL-price product with quantity=0 is not flagged as an unknown-price caveat."""
    session.add(
        Product(
            id=new_id(),
            code="Z",
            name="Товар Z",
            quantity=0,
            cost_cents=None,
            sale_cents=None,
        )
    )
    session.commit()

    result = stock_valuation(session)
    assert result["cost_unknown_count"] == 0
    assert result["sale_unknown_count"] == 0


def test_stock_valuation_excludes_deleted_products(session):
    session.add(
        Product(
            id=new_id(),
            code="D",
            name="Товар D",
            quantity=2,
            cost_cents=1000,
            sale_cents=1500,
            deleted_at="2026-07-01T00:00:00+00:00",
        )
    )
    session.commit()

    result = stock_valuation(session)
    assert result["cost_value_cents"] == 0
    assert result["sale_value_cents"] == 0
    assert result["cost_unknown_count"] == 0
    assert result["sale_unknown_count"] == 0


def test_stock_valuation_ignores_period(session):
    """Point-in-time — takes NO period argument and is stable across repeated calls."""
    session.add(
        Product(
            id=new_id(),
            code="E",
            name="Товар E",
            quantity=1,
            cost_cents=100,
            sale_cents=200,
        )
    )
    session.commit()

    assert stock_valuation(session) == stock_valuation(session)


# --- cash_flow_report (FIN-08 / D-05) ---------------------------------------


def test_cash_flow_report_groups_income_and_expense(session, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    _record_cash_at(session, monkeypatch, mid, category="sale", amount_cents=3000)
    _record_cash_at(
        session, monkeypatch, mid, category="deposit_opening", amount_cents=1000
    )
    _record_cash_at(
        session, monkeypatch, mid, category="withdrawal_rent", amount_cents=-800
    )
    _record_cash_at(
        session, monkeypatch, mid, category="withdrawal_salary", amount_cents=-1200
    )
    _record_cash_at(session, monkeypatch, mid, category="return", amount_cents=-500)

    report = cash_flow_report(session, start_iso, end_iso)
    assert report["income"] == [
        {"category": "sale", "total_cents": 3000},
        {"category": "deposit_opening", "total_cents": 1000},
    ]
    assert report["income_total_cents"] == 4000
    expense_cats = {entry["category"] for entry in report["expense"]}
    assert expense_cats == {"withdrawal_rent", "withdrawal_salary", "return"}
    assert report["expense_total_cents"] == -2500
    assert report["movement_count"] == 5


def test_cash_flow_report_reconciles_with_expense_total(session, monkeypatch):
    """D-05 hard reconciliation: expense_total_cents == cash_expense_total for the same period."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    _record_cash_at(session, monkeypatch, mid, category="sale", amount_cents=3000)
    _record_cash_at(
        session, monkeypatch, mid, category="withdrawal_rent", amount_cents=-800
    )
    _record_cash_at(session, monkeypatch, mid, category="return", amount_cents=-500)

    report = cash_flow_report(session, start_iso, end_iso)
    assert report["expense_total_cents"] == cash_expense_total(
        session, start_iso, end_iso
    )


def test_cash_flow_report_empty_period(session):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    report = cash_flow_report(session, start_iso, end_iso)
    assert report == {
        "income": [],
        "income_total_cents": 0,
        "expense": [],
        "expense_total_cents": 0,
        "movement_count": 0,
    }


def test_cash_flow_report_half_open_bounds(session, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    _record_cash_at(session, monkeypatch, start_iso, category="sale", amount_cents=1000)
    _record_cash_at(session, monkeypatch, end_iso, category="sale", amount_cents=2000)

    report = cash_flow_report(session, start_iso, end_iso)
    assert report["income_total_cents"] == 1000
    assert report["movement_count"] == 1


def test_cash_flow_report_movement_count_matches_bucketed_rows(session, monkeypatch):
    """movement_count == len(income) + len(expense); every category lands income XOR expense."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid = "2026-07-10T10:00:00+00:00"
    _record_cash_at(session, monkeypatch, mid, category="sale", amount_cents=100)
    _record_cash_at(
        session, monkeypatch, mid, category="withdrawal_rent", amount_cents=-100
    )

    report = cash_flow_report(session, start_iso, end_iso)
    income_cats = {entry["category"] for entry in report["income"]}
    expense_cats = {entry["category"] for entry in report["expense"]}
    assert income_cats.isdisjoint(expense_cats)
    assert report["movement_count"] == len(report["income"]) + len(report["expense"])
