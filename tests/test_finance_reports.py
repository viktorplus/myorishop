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


# --- web: /finance/metrics + tiles context on /finance (17-02 Task 1) -------


def test_web_finance_metrics_hx_returns_tiles_partial(client):
    """An HX-Request GET returns ONLY the tiles partial (finance_tiles.html);
    a plain GET returns the full /finance page chrome (mirrors
    test_web_export_page's route-shape assertions). finance.html itself is
    not required to *visually* embed the tiles yet — that wiring is Task 2's
    job (D-04 "Показатели" section) — this task only proves the route
    branches correctly and the tiles partial renders on its own."""
    hx_response = client.get("/finance/metrics", headers={"HX-Request": "true"})
    assert hx_response.status_code == 200
    assert "metric-tile" in hx_response.text
    assert "<h1>Баланс кассы</h1>" not in hx_response.text

    plain_response = client.get("/finance/metrics")
    assert plain_response.status_code == 200
    assert "<h1>Баланс кассы</h1>" in plain_response.text


def test_web_finance_page_renders_tiles(session, client):
    """GET /finance still returns 200 with the existing balance/forms/history
    chrome intact, and the route's _metrics_context computes net profit as a
    plain addition of gross profit + cash_expense_total (never a subtraction,
    D-01a). Visually embedding the tiles into finance.html is Task 2's job."""
    from app.routes.finance import _metrics_context
    from app.services.finance import record_cash_movement

    record_cash_movement(session, category="withdrawal_rent", amount_cents=-800)

    response = client.get("/finance")
    assert response.status_code == 200
    assert "<h1>Баланс кассы</h1>" in response.text

    context = _metrics_context(session, "", "")
    assert context["metrics"]["net_profit_cents"] == (
        context["metrics"]["gross_profit_cents"] - 800
    )
    assert context["valuation"] is not None


# --- web: finance_tiles.html markup/copy + finance.html wiring (Task 2) -----


def test_web_finance_net_caveat_present(client):
    """The MANDATORY net-profit cash-outflow caveat line (D-01b) is a visible
    .muted line on /finance itself, not hidden behind a title= tooltip."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert (
        "Денежный поток: валовая прибыль минус снятия и возвраты за период. "
        "Это не бухгалтерская прибыль."
    ) in response.text


def test_web_finance_tiles_caveat_hx(client):
    """Same MANDATORY caveat line is present in the /finance/metrics HX partial."""
    response = client.get("/finance/metrics", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "не бухгалтерская прибыль" in response.text


def test_web_finance_stock_tile_point_in_time_cue(client):
    """The stock-valuation tile carries the "на текущий момент" cue (D-04b) so
    the operator sees it deliberately ignores the period selector."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert "на текущий момент" in response.text
    assert "По закупке" in response.text
    assert "По продаже" in response.text


def test_web_finance_page_untouched_surfaces(client):
    """Regression guard (D-04): the Phase 15-16 balance/forms/history includes
    still render unchanged alongside the new «Показатели» section."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert "Показатели" in response.text
    assert "<h1>Баланс кассы</h1>" in response.text
    assert "Снять деньги" in response.text
    assert "Внести деньги" in response.text
    assert "История движений" in response.text


# --- web: /finance/report + /finance/report.csv routes (17-03 Task 1) ------


def test_web_finance_report_hx_returns_partial_only(client):
    """A genuine HX-Request GET returns ONLY the results partial, never the
    full page chrome (mirrors reports_sales_page's branch, T-04)."""
    hx_response = client.get("/finance/report", headers={"HX-Request": "true"})
    assert hx_response.status_code == 200
    assert "<h1>Движения кассы за период</h1>" not in hx_response.text
    assert "Скачать CSV" not in hx_response.text


def test_web_finance_report_page_full_page(client):
    """A plain GET returns the full page chrome (title + period filter +
    CSV link + results div)."""
    response = client.get("/finance/report")
    assert response.status_code == 200
    assert "<h1>Движения кассы за период</h1>" in response.text
    assert 'href="/finance/report.csv' in response.text
    assert 'id="cashflow-results"' in response.text


def test_web_finance_report_csv_streams_period_scoped_csv(session, client, monkeypatch):
    """FIN-09: /finance/report.csv delegates to stream_cash_movements_csv and
    scopes the export to the from/to period params."""
    import app.services.finance as finance_module
    from app.services.finance import record_cash_movement

    monkeypatch.setattr(finance_module, "utcnow_iso", lambda: "2026-07-10T10:00:00+00:00")
    record_cash_movement(session, category="sale", amount_cents=1500)

    response = client.get("/finance/report.csv?from=2026-07-10&to=2026-07-10")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "cash_movements.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    assert "Когда;Категория;Комментарий;Сумма" in text
    assert "15,00" in text


# --- web: cash_flow_report.html partial content (17-03 Task 2) -------------


def test_web_finance_report_full_page(session, client, monkeypatch):
    """A plain GET /finance/report returns the FULL page containing the
    «Скачать CSV» link and the Приход/Расход sections with CASH_CATEGORIES
    labels (never hardcoded RU category strings)."""
    import app.services.finance as finance_module
    from app.services.finance import record_cash_movement

    monkeypatch.setattr(finance_module, "utcnow_iso", lambda: "2026-07-10T10:00:00+00:00")
    record_cash_movement(session, category="sale", amount_cents=3000)
    record_cash_movement(session, category="withdrawal_rent", amount_cents=-800)

    response = client.get("/finance/report?from=2026-07-10&to=2026-07-10")
    assert response.status_code == 200
    assert "Скачать CSV" in response.text
    assert "Приход" in response.text
    assert "Расход" in response.text
    assert "Продажа" in response.text
    assert "Аренда" in response.text
    assert "Итого за период" in response.text


def test_web_finance_report_hx_partial(session, client, monkeypatch):
    """A GET /finance/report with an HX-Request header returns ONLY the
    results partial, not the full page chrome (nav / period filter / CSV
    link belong to the page shell, not the swap payload)."""
    import app.services.finance as finance_module
    from app.services.finance import record_cash_movement

    monkeypatch.setattr(finance_module, "utcnow_iso", lambda: "2026-07-10T10:00:00+00:00")
    record_cash_movement(session, category="sale", amount_cents=3000)

    response = client.get(
        "/finance/report?from=2026-07-10&to=2026-07-10", headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    assert "Приход" in response.text
    assert "<h1>Движения кассы за период</h1>" not in response.text
    assert "Скачать CSV" not in response.text
    assert "preset-bar" not in response.text


def test_web_finance_report_empty_state(client):
    """An empty period (no movements) renders the empty-state copy, not the
    Приход/Расход tables."""
    response = client.get("/finance/report?from=2020-01-01&to=2020-01-01")
    assert response.status_code == 200
    assert "За выбранный период движений не было." in response.text
    assert "<h2>Приход</h2>" not in response.text


# --- web: mobile /m/finance/metrics + /m/finance/report + CSV (17-04 Task 1) -


def test_web_mobile_finance_metrics_hx_tiles(client):
    """Mirrors test_web_finance_metrics_hx_returns_tiles_partial: an HX-Request
    GET returns ONLY the SHARED tiles partial (finance_tiles.html, D-04c — no
    mobile-specific tiles partial); a plain GET returns the full /m/finance
    page chrome. GET /m/finance itself also still returns 200 with the merged
    metrics context wired into mobile_finance_page (no write path added)."""
    hx_response = client.get("/m/finance/metrics", headers={"HX-Request": "true"})
    assert hx_response.status_code == 200
    assert "metric-tile" in hx_response.text
    assert "<h1>Баланс кассы</h1>" not in hx_response.text

    plain_response = client.get("/m/finance/metrics")
    assert plain_response.status_code == 200
    assert "<h1>Баланс кассы</h1>" in plain_response.text

    page_response = client.get("/m/finance")
    assert page_response.status_code == 200


def test_web_mobile_finance_report_hx(client):
    """Mirrors test_web_finance_report_hx_returns_partial_only: a genuine
    HX-Request GET returns ONLY the shared results partial, never the full
    page chrome; a plain GET returns the full /m/finance/report page."""
    hx_response = client.get("/m/finance/report", headers={"HX-Request": "true"})
    assert hx_response.status_code == 200
    assert "<h1>Движения кассы за период</h1>" not in hx_response.text

    plain_response = client.get("/m/finance/report")
    assert plain_response.status_code == 200
    assert "<h1>Движения кассы за период</h1>" in plain_response.text


def test_web_mobile_finance_report_csv(session, client, monkeypatch):
    """Mirrors test_web_finance_report_csv_streams_period_scoped_csv (17-03
    Task 1): /m/finance/report.csv delegates to the SAME
    stream_cash_movements_csv service used by the desktop route."""
    import app.services.finance as finance_module
    from app.services.finance import record_cash_movement

    monkeypatch.setattr(finance_module, "utcnow_iso", lambda: "2026-07-10T10:00:00+00:00")
    record_cash_movement(session, category="sale", amount_cents=1500)

    response = client.get("/m/finance/report.csv?from=2026-07-10&to=2026-07-10")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "cash_movements.csv" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    assert "Когда;Категория;Комментарий;Сумма" in text
    assert "15,00" in text


# --- web: mobile finance.html «Показатели» + finance_report.html shell (17-04 Task 2) -


def test_web_mobile_finance_report_matches_desktop_subtotals(session, client, monkeypatch):
    """Mobile parity (D-04c): /m/finance/report renders the SAME income/expense
    «Итого за период» subtotals as the desktop /finance/report for an identical
    period — both delegate to the same cash_flow_report service + shared
    partials/cash_flow_report.html, only finance_base differs."""
    import app.services.finance as finance_module
    from app.services.finance import record_cash_movement

    monkeypatch.setattr(finance_module, "utcnow_iso", lambda: "2026-07-10T10:00:00+00:00")
    record_cash_movement(session, category="sale", amount_cents=3000)
    record_cash_movement(session, category="withdrawal_rent", amount_cents=-800)

    desktop = client.get("/finance/report?from=2026-07-10&to=2026-07-10")
    mobile = client.get("/m/finance/report?from=2026-07-10&to=2026-07-10")
    assert desktop.status_code == 200
    assert mobile.status_code == 200
    assert "Скачать CSV" in mobile.text
    assert 'href="/m/finance/report.csv' in mobile.text
    for needle in ("Приход", "Расход", "Продажа", "Аренда", "Итого за период"):
        assert needle in desktop.text
        assert needle in mobile.text


def test_web_mobile_finance_tiles_net_caveat(client):
    """/m/finance shows the gross/net/stock tiles (D-04) with the mandatory
    net cash-outflow caveat line (D-01b) — the Phase 15-16 balance/forms/
    history includes stay intact alongside the new «Показатели» section."""
    response = client.get("/m/finance")
    assert response.status_code == 200
    assert "Показатели" in response.text
    assert "metric-tile" in response.text
    assert (
        "Денежный поток: валовая прибыль минус снятия и возвраты за период. "
        "Это не бухгалтерская прибыль."
    ) in response.text
    assert "на текущий момент" in response.text
    assert "<h1>Баланс кассы</h1>" in response.text
    assert "Снять деньги" in response.text
    assert "Внести деньги" in response.text
    assert "История движений" in response.text


# --- web: navigation entry points to /finance/report (17-05, UAT gap closure) -


def test_web_settings_links_to_finance_report(client):
    """GET /settings (Настройки hub) contains the entry point linking
    straight to /finance/report with export/CSV wording — proving one-hop
    reachability from Настройки, which is where this entry point moved to
    (D-08), still closing the original 17-UAT.md Test 2 gap."""
    response = client.get("/settings")
    assert response.status_code == 200
    assert 'href="/finance/report"' in response.text
    assert "Экспорт кассы" in response.text


def test_web_finance_report_still_reachable_directly(client):
    """GET /finance/report is still directly reachable — the "active nav
    item" concept no longer applies since /finance/report left the top
    nav entirely (D-08)."""
    response = client.get("/finance/report")
    assert response.status_code == 200


def test_web_finance_page_report_link_is_button_styled(client):
    """GET /finance's in-page report link is now a .button-styled CTA with
    CSV wording, not the old bare unstyled inline text link."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert '<a class="button" href="/finance/report">' in response.text
    assert "CSV" in response.text


def test_web_reports_landing_finance_link_uses_csv_wording(client):
    """GET /reports's cash-movements link uses consistent CSV wording matching
    the other entry points."""
    response = client.get("/reports")
    assert response.status_code == 200
    assert 'href="/finance/report"' in response.text
    assert "CSV" in response.text


def test_web_mobile_home_tile_links_to_finance_report(client):
    """GET /m/ (mobile main page) contains a new tile linking straight to
    /m/finance/report with export/CSV wording — proving one-hop reachability
    from the mobile main page (closes 17-UAT.md Test 2, mobile side)."""
    response = client.get("/m/")
    assert response.status_code == 200
    assert 'href="/m/finance/report"' in response.text
    assert "Экспорт кассы" in response.text


def test_web_mobile_finance_page_report_link_is_button_styled(client):
    """GET /m/finance's in-page report link is now a .button-styled CTA with
    CSV wording, not the old bare unstyled inline text link."""
    response = client.get("/m/finance")
    assert response.status_code == 200
    assert '<a class="button" href="/m/finance/report">' in response.text
    assert "CSV" in response.text
