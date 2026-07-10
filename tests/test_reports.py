"""Unit tests for app.services.reports (RPT-01): sales/profit aggregation.

Pins the NULL-cost-safe profit contract (RESEARCH Pitfall 2: a sale line
with unknown unit_cost_cents must never silently inflate profit by its
full revenue) and the "reports are historical, never filter
Product.deleted_at" contract (RESEARCH Pitfall 5).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.core import local_day_bounds_utc, new_id
from app.models import WRITEOFF_REASONS, Product
from app.services.ledger import record_operation
from app.services.reports import (
    sales_profit_report,
    stale_products,
    top_selling_products,
    writeoff_report,
)
from app.services.stock import (
    all_active_products,
    effective_low_stock_threshold,
    low_stock_products,
)

DAY = date(2026, 7, 10)
TZ = "Europe/Moscow"


def _record_sale_at(
    session,
    monkeypatch,
    iso: str,
    *,
    product: Product,
    qty: int,
    price_cents: int,
    cost_cents: int | None = None,
):
    """Record one sale operation with a caller-controlled created_at.

    Monkeypatches the SAME name record_operation calls internally
    (app.services.ledger.utcnow_iso), so the stamped created_at is exactly
    the iso string given here — needed to place sales precisely inside or
    outside a period boundary for the tests below.
    """
    import app.services.ledger as ledger_module

    monkeypatch.setattr(ledger_module, "utcnow_iso", lambda: iso)
    return record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-qty,
        unit_cost_cents=cost_cents,
        unit_price_cents=price_cents,
    )


def test_sales_report_null_cost(session, product, monkeypatch):
    """RESEARCH Pitfall 2: a cost-unknown line's revenue counts, its cost/profit does not."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_sale_at(
        session,
        monkeypatch,
        mid_day_iso,
        product=product,
        qty=1,
        price_cents=1500,
        cost_cents=1000,
    )
    _record_sale_at(
        session,
        monkeypatch,
        mid_day_iso,
        product=product,
        qty=1,
        price_cents=1500,
        cost_cents=None,
    )

    report = sales_profit_report(session, start_iso, end_iso)
    totals = report["totals"]
    assert totals["units_sold"] == 2
    assert totals["revenue_cents"] == 3000
    assert totals["cost_cents"] == 1000
    # NOT 3000-1000=2000 — that would silently inflate profit by the
    # cost-unknown line's full revenue (the exact Pitfall 2 bug).
    assert totals["profit_cents"] == 500
    assert totals["cost_unknown_count"] == 1
    assert report["cost_unknown_count"] == 1


def test_sales_report_by_product_sorted_by_qty_desc(session, product, monkeypatch):
    other = Product(id=new_id(), code="TEST-002", name="Другой товар", quantity=0)
    session.add(other)
    session.commit()

    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_sale_at(
        session, monkeypatch, mid_day_iso, product=product, qty=1, price_cents=1000, cost_cents=500
    )
    _record_sale_at(
        session, monkeypatch, mid_day_iso, product=other, qty=5, price_cents=1000, cost_cents=500
    )

    report = sales_profit_report(session, start_iso, end_iso)
    by_product = report["by_product"]
    assert len(by_product) == 2
    assert by_product[0]["product"] is other
    assert by_product[0]["qty"] == 5
    assert by_product[1]["product"] is product
    assert by_product[1]["qty"] == 1


def test_sales_report_excludes_outside_period(session, product, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    just_inside = "2026-07-10T20:59:59+00:00"  # 23:59:59 local, still July 10
    just_outside = "2026-07-10T21:00:00+00:00"  # 00:00:00 local July 11 — next local day

    _record_sale_at(
        session, monkeypatch, just_inside, product=product, qty=1, price_cents=1000, cost_cents=500
    )
    _record_sale_at(
        session, monkeypatch, just_outside, product=product, qty=9, price_cents=1000, cost_cents=500
    )

    report = sales_profit_report(session, start_iso, end_iso)
    assert report["totals"]["units_sold"] == 1


def test_sales_report_includes_deleted_product_for_past_period(session, product, monkeypatch):
    """RESEARCH Pitfall 5: sales/profit reports are historical — never filter deleted_at."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_sale_at(
        session, monkeypatch, mid_day_iso, product=product, qty=1, price_cents=1000, cost_cents=500
    )
    product.deleted_at = "2026-07-11T00:00:00+00:00"
    session.commit()

    report = sales_profit_report(session, start_iso, end_iso)
    assert len(report["by_product"]) == 1
    assert report["by_product"][0]["product"] is product


def _record_writeoff_at(
    session,
    monkeypatch,
    iso: str,
    *,
    product: Product,
    qty: int,
    reason_code: str,
):
    """Record one write-off operation with a caller-controlled created_at.

    Mirrors _record_sale_at above — monkeypatches app.services.ledger's
    utcnow_iso so the stamped created_at lands exactly where the test needs
    it relative to a period boundary.
    """
    import app.services.ledger as ledger_module

    monkeypatch.setattr(ledger_module, "utcnow_iso", lambda: iso)
    return record_operation(
        session,
        type_="writeoff",
        product_id=product.id,
        qty_delta=-qty,
        payload={"reason_code": reason_code, "note": ""},
    )


def test_writeoff_report_groups_by_reason(session, product, monkeypatch):
    """Result order follows WRITEOFF_REASONS' own key order (damaged, expired, ...)."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_writeoff_at(
        session, monkeypatch, mid_day_iso, product=product, qty=3, reason_code="expired"
    )
    _record_writeoff_at(
        session, monkeypatch, mid_day_iso, product=product, qty=2, reason_code="damaged"
    )

    report = writeoff_report(session, start_iso, end_iso)
    by_reason = report["by_reason"]
    assert [entry["reason_code"] for entry in by_reason] == ["damaged", "expired"]
    assert by_reason[0]["qty"] == 2
    assert by_reason[0]["label"] == WRITEOFF_REASONS["damaged"]
    assert by_reason[1]["qty"] == 3
    assert by_reason[1]["label"] == WRITEOFF_REASONS["expired"]
    assert report["total_qty"] == 5


def test_writeoff_report_excludes_reason_with_zero_writeoffs(session, product, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_writeoff_at(
        session, monkeypatch, mid_day_iso, product=product, qty=1, reason_code="lost"
    )

    report = writeoff_report(session, start_iso, end_iso)
    reason_codes = [entry["reason_code"] for entry in report["by_reason"]]
    assert reason_codes == ["lost"]
    assert "damaged" not in reason_codes
    assert "expired" not in reason_codes


def test_writeoff_report_includes_deleted_product_for_past_period(session, product, monkeypatch):
    """RESEARCH Pitfall 5: same rule as sales_profit_report - never filter deleted_at."""
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_writeoff_at(
        session, monkeypatch, mid_day_iso, product=product, qty=1, reason_code="damaged"
    )
    product.deleted_at = "2026-07-11T00:00:00+00:00"
    session.commit()

    report = writeoff_report(session, start_iso, end_iso)
    assert report["total_qty"] == 1
    assert report["by_reason"][0]["lines"][0]["product"] is product


def test_writeoff_report_excludes_outside_period(session, product, monkeypatch):
    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    just_inside = "2026-07-10T20:59:59+00:00"  # 23:59:59 local, still July 10
    just_outside = "2026-07-10T21:00:00+00:00"  # 00:00:00 local July 11

    _record_writeoff_at(
        session, monkeypatch, just_inside, product=product, qty=1, reason_code="damaged"
    )
    _record_writeoff_at(
        session, monkeypatch, just_outside, product=product, qty=9, reason_code="damaged"
    )

    report = writeoff_report(session, start_iso, end_iso)
    assert report["total_qty"] == 1


def test_web_reports_landing_links_to_sales(client):
    response = client.get("/reports")
    assert response.status_code == 200
    assert 'href="/reports/sales"' in response.text


def test_web_reports_sales_today_default(client):
    """D-01: no query params defaults to today's preset; active preset has no secondary class."""
    response = client.get("/reports/sales")
    assert response.status_code == 200
    assert ">Сегодня</a>" in response.text
    assert ">Неделя</a>" in response.text
    assert ">Месяц</a>" in response.text

    today_start = response.text.index(">Сегодня</a>")
    today_anchor = response.text[: today_start + len(">Сегодня</a>")]
    today_anchor = today_anchor[today_anchor.rindex("<a "):]
    assert "secondary" not in today_anchor

    week_start = response.text.index(">Неделя</a>")
    week_anchor = response.text[: week_start + len(">Неделя</a>")]
    week_anchor = week_anchor[week_anchor.rindex("<a "):]
    assert "secondary" in week_anchor


def test_web_reports_sales_invalid_date_shows_ru_error(client):
    response = client.get("/reports/sales", params={"from": "not-a-date", "to": "2026-07-10"})
    assert response.status_code == 200
    assert "Некорректная дата." in response.text


def test_web_reports_sales_hx_request_returns_partial_only(client):
    """D-03/CR-01: an HX-Request returns only the results fragment, no chrome."""
    response = client.get("/reports/sales", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "<nav" not in response.text


def test_web_nav_has_reports_link(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/reports"' in response.text


def test_effective_threshold_zero_not_fallback(session, product):
    """RESEARCH/Pitfall 3: an explicit 0 threshold never falls back to global default."""
    product.low_stock_threshold = 0
    product.quantity = 0
    session.commit()
    assert effective_low_stock_threshold(product) == 0
    assert product in low_stock_products(session)

    product.quantity = 1
    session.commit()
    assert effective_low_stock_threshold(product) == 0
    assert product not in low_stock_products(session)


def test_low_stock_uses_global_fallback(session, product):
    """A product with no per-product threshold uses settings.low_stock_threshold."""
    assert product.low_stock_threshold is None
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=settings.low_stock_threshold,
        unit_cost_cents=100,
        unit_price_cents=200,
    )
    assert effective_low_stock_threshold(product) == settings.low_stock_threshold
    assert product in low_stock_products(session)


def test_low_stock_excludes_deleted_products(session, product):
    product.low_stock_threshold = 0
    product.quantity = 0
    product.deleted_at = "2026-07-10T00:00:00+00:00"
    session.commit()
    assert product not in low_stock_products(session)


def test_low_stock_products_sorted_by_quantity_ascending(session, product):
    other = Product(
        id=new_id(), code="TEST-002", name="Другой товар", quantity=3, low_stock_threshold=10
    )
    session.add(other)
    product.low_stock_threshold = 10
    product.quantity = 1
    session.commit()

    result = low_stock_products(session)
    assert [p.id for p in result] == [product.id, other.id]


def test_all_active_products_excludes_deleted(session, product):
    other = Product(id=new_id(), code="TEST-003", name="Удалённый товар", quantity=0)
    other.deleted_at = "2026-07-10T00:00:00+00:00"
    session.add(other)
    session.commit()

    result = all_active_products(session)
    assert product in result
    assert other not in result


def test_web_reports_stock_lists_low_stock_and_full_table(client, session, product):
    product.low_stock_threshold = 0
    product.quantity = 0
    session.commit()

    response = client.get("/reports/stock")
    assert response.status_code == 200
    assert "Мало на складе" in response.text
    assert "Все товары" in response.text
    assert product.code in response.text
    assert "Мало" in response.text


def test_web_reports_stock_no_low_stock_shows_empty_state(client, session, product):
    product.low_stock_threshold = 0
    product.quantity = 1
    session.commit()

    response = client.get("/reports/stock")
    assert response.status_code == 200
    assert "Товаров с низким остатком нет." in response.text
    # full table still lists the product, but with no "Мало" status
    assert product.code in response.text


def test_web_reports_landing_links_to_stock(client):
    response = client.get("/reports")
    assert response.status_code == 200
    assert 'href="/reports/stock"' in response.text


def test_web_reports_writeoffs_groups_by_reason(client, session, product):
    record_operation(
        session,
        type_="writeoff",
        product_id=product.id,
        qty_delta=-3,
        payload={"reason_code": "expired", "note": ""},
    )
    record_operation(
        session,
        type_="writeoff",
        product_id=product.id,
        qty_delta=-2,
        payload={"reason_code": "damaged", "note": ""},
    )

    response = client.get("/reports/writeoffs")
    assert response.status_code == 200
    assert "Причина" in response.text
    assert "Кол-во, шт." in response.text
    assert WRITEOFF_REASONS["damaged"] in response.text
    assert WRITEOFF_REASONS["expired"] in response.text
    # order follows WRITEOFF_REASONS' own key order (damaged before expired)
    assert response.text.index(WRITEOFF_REASONS["damaged"]) < response.text.index(
        WRITEOFF_REASONS["expired"]
    )


def test_web_reports_writeoffs_empty_state(client):
    response = client.get("/reports/writeoffs")
    assert response.status_code == 200
    assert "За выбранный период списаний не было." in response.text


def test_web_reports_writeoffs_hx_request_returns_partial_only(client):
    response = client.get("/reports/writeoffs", headers={"HX-Request": "true"})
    assert response.status_code == 200
    assert "<html" not in response.text
    assert "<nav" not in response.text


def test_web_reports_landing_links_to_writeoffs(client):
    response = client.get("/reports")
    assert response.status_code == 200
    assert 'href="/reports/writeoffs"' in response.text


def _iso_days_ago(n: int) -> str:
    """UTC ISO timestamp for local 'now minus n days' (real clock, not DAY fixture).

    stale_products uses the real datetime.now(settings.display_tz) (not a
    caller-supplied period), so these tests must place sales relative to the
    actual current local date, not the fixed DAY constant used elsewhere.
    """
    local_now = datetime.now(ZoneInfo(TZ))
    target = local_now - timedelta(days=n)
    return target.astimezone(UTC).isoformat(timespec="seconds")


def test_top_selling_orders_by_units(session, product, monkeypatch):
    other = Product(id=new_id(), code="TEST-002", name="Другой товар", quantity=0)
    session.add(other)
    session.commit()

    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_sale_at(
        session, monkeypatch, mid_day_iso, product=product, qty=3, price_cents=1000, cost_cents=500
    )
    _record_sale_at(
        session, monkeypatch, mid_day_iso, product=other, qty=5, price_cents=1000, cost_cents=500
    )

    result = top_selling_products(session, start_iso, end_iso)
    assert result[0]["product"] is other
    assert result[0]["units_sold"] == 5
    assert result[1]["product"] is product
    assert result[1]["units_sold"] == 3


def test_top_selling_respects_limit(session, monkeypatch):
    products = []
    for i in range(11):
        p = Product(id=new_id(), code=f"TS-{i:03d}", name=f"Товар {i}", quantity=0)
        session.add(p)
        products.append(p)
    session.commit()

    start_iso, end_iso = local_day_bounds_utc(DAY, DAY, TZ)
    mid_day_iso = "2026-07-10T10:00:00+00:00"
    for p in products:
        _record_sale_at(
            session, monkeypatch, mid_day_iso, product=p, qty=1, price_cents=1000, cost_cents=500
        )

    result = top_selling_products(session, start_iso, end_iso)
    assert len(result) == 10


def test_stale_includes_never_sold(session, product):
    """A genuinely never-sold active product appears with days_since=None (LEFT OUTER JOIN)."""
    result = stale_products(session)
    assert len(result) == 1
    assert result[0]["product"] is product
    assert result[0]["last_sale_iso"] is None
    assert result[0]["days_since"] is None


def test_stale_threshold_zero_not_fallback(session, product, monkeypatch):
    """Pitfall 3 applied to stale_days: explicit 0 never falls back to settings.stale_days.

    A sale from yesterday IS included (more than 0 days since); a sale from
    TODAY is excluded (not yet more than 0 days since).
    """
    product.stale_days = 0
    session.commit()

    yesterday_iso = _iso_days_ago(1)
    _record_sale_at(
        session, monkeypatch, yesterday_iso, product=product, qty=1, price_cents=1000,
        cost_cents=500,
    )

    result = stale_products(session)
    matching = [row for row in result if row["product"].id == product.id]
    assert len(matching) == 1
    assert matching[0]["days_since"] == 1

    today_iso = _iso_days_ago(0)
    _record_sale_at(
        session, monkeypatch, today_iso, product=product, qty=1, price_cents=1000, cost_cents=500
    )

    result = stale_products(session)
    matching = [row for row in result if row["product"].id == product.id]
    assert matching == []


def test_stale_excludes_soft_deleted_never_sold_product(session, product):
    product.deleted_at = "2026-07-10T00:00:00+00:00"
    session.commit()

    result = stale_products(session)
    assert result == []


def test_web_reports_products_top_selling_ranked(client, session, product):
    other = Product(id=new_id(), code="TEST-002", name="Другой товар", quantity=0)
    session.add(other)
    session.commit()

    record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-3,
        unit_price_cents=1000,
    )
    record_operation(
        session,
        type_="sale",
        product_id=other.id,
        qty_delta=-5,
        unit_price_cents=1000,
    )

    response = client.get("/reports/products")
    assert response.status_code == 200
    assert "Топ продаж" in response.text
    assert response.text.index(other.name) < response.text.index(product.name)


def test_web_reports_products_stale_shows_never_sold_as_nikogda(client, product):
    response = client.get("/reports/products")
    assert response.status_code == 200
    assert "Никогда" in response.text
    assert product.code in response.text


def test_web_reports_products_stale_independent_of_bad_period(client, product):
    response = client.get("/reports/products", params={"from": "garbage"})
    assert response.status_code == 200
    assert "Некорректная дата." in response.text
    # stale section still renders correctly despite the top-selling half's error
    assert "Никогда" in response.text
    assert product.code in response.text


def test_web_reports_landing_links_to_all_four_reports(client):
    response = client.get("/reports")
    assert response.status_code == 200
    assert 'href="/reports/sales"' in response.text
    assert 'href="/reports/stock"' in response.text
    assert 'href="/reports/writeoffs"' in response.text
    assert 'href="/reports/products"' in response.text
