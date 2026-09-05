"""Unit tests for app.services.reports (RPT-01): sales/profit aggregation.

Pins the NULL-cost-safe profit contract (RESEARCH Pitfall 2: a sale line
with unknown unit_cost_cents must never silently inflate profit by its
full revenue) and the "reports are historical, never filter
Product.deleted_at" contract (RESEARCH Pitfall 5).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.core import business_date_bounds, new_id
from app.models import WRITEOFF_REASONS, Batch, Product, Warehouse
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


def _local_day_of(iso: str) -> str:
    """The tz-correct LOCAL calendar day of a UTC timestamp, as ISO 'yyyy-mm-dd'.

    Phase 33 (DATE-03): the seeding helpers below stamp this as the row's
    `business_date`, reproducing exactly what migration 0027's backfill computes
    for a pre-existing row. Without it every fixture would carry
    record_operation's default — TODAY's real local day — and land in today's
    bucket instead of the fixture's, which is not what any of these tests mean.

    It is a tz-correct conversion, NOT `iso[:10]`: at Europe/Moscow
    '2026-07-10T21:00:00+00:00' is local July 11, and the local-midnight-straddle
    tests below depend on that distinction.
    """
    return datetime.fromisoformat(iso).astimezone(ZoneInfo(TZ)).date().isoformat()


def _ensure_batch(session, product):
    """A valid batch id for a product. Reports aggregate by product/type, so any
    batch of that product satisfies the mandatory D-12 write-path guard (Plan
    09-05) without changing what the report tests measure."""
    batch = session.scalars(
        select(Batch).where(Batch.product_id == product.id)
    ).first()
    if batch is None:
        warehouse = session.scalars(select(Warehouse)).first()
        if warehouse is None:
            warehouse = Warehouse(id=new_id(), name="Склад")
            session.add(warehouse)
            session.flush()
        batch = Batch(
            id=new_id(),
            product_id=product.id,
            warehouse_id=warehouse.id,
            quantity=0,
        )
        session.add(batch)
        session.flush()
    return batch.id


def _record_sale_at(
    session,
    monkeypatch,
    iso: str,
    *,
    product: Product,
    qty: int,
    price_cents: int,
    cost_cents: int | None = None,
    business_date: str | None = None,
):
    """Record one sale operation with a caller-controlled created_at.

    Monkeypatches the SAME name record_operation calls internally
    (app.services.ledger.utcnow_iso), so the stamped created_at is exactly
    the iso string given here — needed to place sales precisely inside or
    outside a period boundary for the tests below.

    Phase 33 (DATE-03): `business_date` defaults to the tz-correct local day OF
    `iso`, so a fixture written "at" a past timestamp also carries that past
    business date and the switched period reports still see it where the test
    means it to be. Pass `business_date` explicitly to build a BACK-DATED row
    (business date and entry date deliberately in different periods).
    """
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
        business_date=business_date or _local_day_of(iso),
    )


def test_sales_report_null_cost(session, product, monkeypatch):
    """RESEARCH Pitfall 2: a cost-unknown line's revenue counts, its cost/profit does not."""
    start_iso, end_iso = business_date_bounds(DAY, DAY)
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

    start_iso, end_iso = business_date_bounds(DAY, DAY)
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
    start_iso, end_iso = business_date_bounds(DAY, DAY)
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
    start_iso, end_iso = business_date_bounds(DAY, DAY)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    _record_sale_at(
        session, monkeypatch, mid_day_iso, product=product, qty=1, price_cents=1000, cost_cents=500
    )
    product.deleted_at = "2026-07-11T00:00:00+00:00"
    session.commit()

    report = sales_profit_report(session, start_iso, end_iso)
    assert len(report["by_product"]) == 1
    assert report["by_product"][0]["product"] is product


def test_sales_report_scopes_by_currency(session, product, monkeypatch):
    """CUR-02: RUB and EUR sales in the same period never mix into one total."""
    start_iso, end_iso = business_date_bounds(DAY, DAY)
    mid_day_iso = "2026-07-10T10:00:00+00:00"

    rub_warehouse = Warehouse(id=new_id(), name="Склад RUB")
    eur_warehouse = Warehouse(id=new_id(), name="Склад EUR", currency="EUR")
    session.add_all([rub_warehouse, eur_warehouse])
    session.commit()
    rub_batch = Batch(id=new_id(), product_id=product.id, warehouse_id=rub_warehouse.id, quantity=0)
    eur_batch = Batch(id=new_id(), product_id=product.id, warehouse_id=eur_warehouse.id, quantity=0)
    session.add_all([rub_batch, eur_batch])
    session.commit()

    import app.services.ledger as ledger_module

    monkeypatch.setattr(ledger_module, "utcnow_iso", lambda: mid_day_iso)
    record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-1,
        unit_cost_cents=500,
        unit_price_cents=1000,
        batch_id=rub_batch.id,
        business_date=_local_day_of(mid_day_iso),
    )
    record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-2,
        unit_cost_cents=500,
        unit_price_cents=1000,
        batch_id=eur_batch.id,
        business_date=_local_day_of(mid_day_iso),
    )

    rub_report = sales_profit_report(session, start_iso, end_iso, currency="RUB")
    eur_report = sales_profit_report(session, start_iso, end_iso, currency="EUR")
    assert rub_report["totals"]["units_sold"] == 1
    assert eur_report["totals"]["units_sold"] == 2


def test_sales_report_legacy_null_batch_row_buckets_as_rub(session, product, past_sale, customer):
    """LOCKED decision: a batch_id=None (pre-Phase-9) sale counts under RUB,
    via the shared operation_currency_clause outer join — never dropped, and
    MUST NOT appear under any other currency."""
    start_iso, end_iso = business_date_bounds(DAY, DAY)
    mid_day_iso = "2026-07-10T10:00:00+00:00"
    past_sale(
        customer, product, created_at=mid_day_iso, qty=1, unit_price_cents=1000, batch_id=None
    )

    rub_report = sales_profit_report(session, start_iso, end_iso, currency="RUB")
    uah_report = sales_profit_report(session, start_iso, end_iso, currency="UAH")
    eur_report = sales_profit_report(session, start_iso, end_iso, currency="EUR")
    assert rub_report["totals"]["units_sold"] == 1
    assert uah_report["totals"]["units_sold"] == 0
    assert eur_report["totals"]["units_sold"] == 0


def _record_writeoff_at(
    session,
    monkeypatch,
    iso: str,
    *,
    product: Product,
    qty: int,
    reason_code: str,
    business_date: str | None = None,
):
    """Record one write-off operation with a caller-controlled created_at.

    Mirrors _record_sale_at above — monkeypatches app.services.ledger's
    utcnow_iso so the stamped created_at lands exactly where the test needs
    it relative to a period boundary, and defaults business_date to the
    tz-correct local day of that timestamp (see _record_sale_at's docstring).
    """
    import app.services.ledger as ledger_module

    batch_id = _ensure_batch(session, product)
    monkeypatch.setattr(ledger_module, "utcnow_iso", lambda: iso)
    return record_operation(
        session,
        type_="writeoff",
        product_id=product.id,
        qty_delta=-qty,
        payload={"reason_code": reason_code, "note": ""},
        batch_id=batch_id,
        business_date=business_date or _local_day_of(iso),
    )


def test_writeoff_report_groups_by_reason(session, product, monkeypatch):
    """Result order follows WRITEOFF_REASONS' own key order (damaged, expired, ...)."""
    start_iso, end_iso = business_date_bounds(DAY, DAY)
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
    start_iso, end_iso = business_date_bounds(DAY, DAY)
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
    start_iso, end_iso = business_date_bounds(DAY, DAY)
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
    start_iso, end_iso = business_date_bounds(DAY, DAY)
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


def test_web_reports_sales_renders_currency_select_rub_default(client):
    """CUR-02: /reports/sales renders a non-empty currency select, RUB preselected."""
    response = client.get("/reports/sales")
    assert response.status_code == 200
    assert '<select id="currency" name="currency"' in response.text
    assert '<option value="RUB" selected>' in response.text


def test_web_nav_has_reports_link(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/reports"' in response.text


def test_web_reports_sales_has_back_link(client):
    response = client.get("/reports/sales")
    assert response.status_code == 200
    assert '<p><a href="/reports">← Назад к отчётам</a></p>' in response.text


def test_web_reports_writeoffs_has_back_link(client):
    response = client.get("/reports/writeoffs")
    assert response.status_code == 200
    assert '<p><a href="/reports">← Назад к отчётам</a></p>' in response.text


def test_web_reports_stock_has_back_link(client):
    response = client.get("/reports/stock")
    assert response.status_code == 200
    assert '<p><a href="/reports">← Назад к отчётам</a></p>' in response.text


def test_web_reports_expiry_has_back_link(client):
    response = client.get("/reports/expiry")
    assert response.status_code == 200
    assert '<p><a href="/reports">← Назад к отчётам</a></p>' in response.text


def test_web_reports_products_has_back_link(client):
    response = client.get("/reports/products")
    assert response.status_code == 200
    assert '<p><a href="/reports">← Назад к отчётам</a></p>' in response.text


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
        batch_id=_ensure_batch(session, product),
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
    batch_id = _ensure_batch(session, product)
    record_operation(
        session,
        type_="writeoff",
        product_id=product.id,
        qty_delta=-3,
        payload={"reason_code": "expired", "note": ""},
        batch_id=batch_id,
    )
    record_operation(
        session,
        type_="writeoff",
        product_id=product.id,
        qty_delta=-2,
        payload={"reason_code": "damaged", "note": ""},
        batch_id=batch_id,
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

    start_iso, end_iso = business_date_bounds(DAY, DAY)
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

    start_iso, end_iso = business_date_bounds(DAY, DAY)
    mid_day_iso = "2026-07-10T10:00:00+00:00"
    for p in products:
        _record_sale_at(
            session, monkeypatch, mid_day_iso, product=p, qty=1, price_cents=1000, cost_cents=500
        )

    result = top_selling_products(session, start_iso, end_iso)
    assert len(result) == 10


# --- Phase 33 / DATE-03: the three switched reports bucket by the BUSINESS date --
#
# The shared fixture shape (VA-13) is one row whose two dates disagree: it was
# ENTERED on ENTRY_DAY but the goods moved on DAY. Every test below asserts the
# same pair — the row IS in DAY's report and is NOT in ENTRY_DAY's — which is
# the only assertion that distinguishes "switched" from "happens to agree".

ENTRY_DAY = date(2026, 9, 20)
ENTRY_DAY_ISO = "2026-09-20T10:00:00+00:00"  # 13:00 local, unambiguously Sep 20


def test_sales_report_buckets_back_dated_row_by_business_date(session, product, monkeypatch):
    """DATE-03: a sale entered on Sep 20 for goods that moved on Jul 10 belongs to JULY."""
    _record_sale_at(
        session,
        monkeypatch,
        ENTRY_DAY_ISO,
        product=product,
        qty=4,
        price_cents=1000,
        cost_cents=600,
        business_date=DAY.isoformat(),
    )

    in_business_period = sales_profit_report(session, *business_date_bounds(DAY, DAY))
    assert in_business_period["totals"]["units_sold"] == 4
    assert in_business_period["totals"]["revenue_cents"] == 4000

    # ...and it is NOT in the period it was physically entered in.
    in_entry_period = sales_profit_report(session, *business_date_bounds(ENTRY_DAY, ENTRY_DAY))
    assert in_entry_period["totals"]["units_sold"] == 0
    assert in_entry_period["by_product"] == []


def test_sales_report_includes_the_last_day_of_the_range(session, product, monkeypatch):
    """Pitfall D: the bounds contract is CLOSED — a row ON `end_day` must be IN.

    One predicate left as `< end_day` would silently drop the whole last day of
    every period the operator ever selects, and no other test in this file has a
    multi-day range that would notice.
    """
    _record_sale_at(
        session, monkeypatch, ENTRY_DAY_ISO, product=product, qty=7, price_cents=1000,
        cost_cents=500, business_date=DAY.isoformat(),
    )

    start, end = business_date_bounds(DAY - timedelta(days=2), DAY)
    assert sales_profit_report(session, start, end)["totals"]["units_sold"] == 7


def test_writeoff_report_buckets_back_dated_row_by_business_date(session, product, monkeypatch):
    """DATE-03 per REASON: a grand-total assertion would net out the bucketing error."""
    _record_writeoff_at(
        session, monkeypatch, "2026-07-10T10:00:00+00:00", product=product, qty=2,
        reason_code="damaged",
    )
    _record_writeoff_at(
        session, monkeypatch, ENTRY_DAY_ISO, product=product, qty=5, reason_code="expired",
        business_date=DAY.isoformat(),
    )

    report = writeoff_report(session, *business_date_bounds(DAY, DAY))
    by_code = {entry["reason_code"]: entry["qty"] for entry in report["by_reason"]}
    # The PER-REASON line is the assertion that matters: total_qty == 7 would also
    # hold if «expired» had been dropped and «damaged» double-counted.
    assert by_code == {"damaged": 2, "expired": 5}

    entry_period = writeoff_report(session, *business_date_bounds(ENTRY_DAY, ENTRY_DAY))
    assert entry_period["by_reason"] == []
    assert entry_period["total_qty"] == 0


def test_top_selling_ranking_follows_the_business_date(session, product, monkeypatch):
    """DATE-03: a period error here changes the RANKING, not merely a total."""
    other = Product(id=new_id(), code="TEST-002", name="Другой товар", quantity=0)
    session.add(other)
    session.commit()

    # Entered on time, 5 units.
    _record_sale_at(
        session, monkeypatch, "2026-07-10T10:00:00+00:00", product=product, qty=5,
        price_cents=1000, cost_cents=500,
    )
    # Back-dated into the SAME business day, 9 units — this is what flips the order.
    _record_sale_at(
        session, monkeypatch, ENTRY_DAY_ISO, product=other, qty=9, price_cents=1000,
        cost_cents=500, business_date=DAY.isoformat(),
    )

    ranked = top_selling_products(session, *business_date_bounds(DAY, DAY))
    assert [(row["product"].id, row["units_sold"]) for row in ranked] == [
        (other.id, 9),
        (product.id, 5),
    ]

    # Bucketed by entry date the back-dated row would rank first ALONE; it does not.
    assert top_selling_products(session, *business_date_bounds(ENTRY_DAY, ENTRY_DAY)) == []


def test_null_business_date_row_still_appears_in_all_three_reports(
    session, product, past_sale, customer
):
    """DATE-08 at the report layer: a pre-0027 row (business_date IS NULL) is
    bucketed by substr(created_at, 1, 10) through business_date_expr's COALESCE
    and must NOT vanish from a period report."""
    past_sale(customer, product, created_at="2026-07-10T10:00:00+00:00", qty=3)

    start, end = business_date_bounds(DAY, DAY)
    assert sales_profit_report(session, start, end)["totals"]["units_sold"] == 3
    assert top_selling_products(session, start, end)[0]["units_sold"] == 3


def test_stale_products_is_not_switched_to_business_date(session, product, monkeypatch):
    """D-25, pinned as a TEST so the next sweep cannot silently «finish» it.

    stale_products answers «how long since this product last MOVED» — real
    elapsed time, not the operator's bookkeeping period. A sale ENTERED today
    but back-dated a year therefore makes the product fresh (its last movement
    was today), which is the opposite of what a business-date bucket would say.
    """
    product.stale_days = 0
    session.commit()

    _record_sale_at(
        session, monkeypatch, _iso_days_ago(0), product=product, qty=1, price_cents=1000,
        cost_cents=500, business_date="2025-01-01",
    )

    # Entered today -> NOT stale, even though its business date is a year old.
    assert [row for row in stale_products(session) if row["product"].id == product.id] == []


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


def test_stale_products_reads_a_naive_created_at_as_utc(session, product, monkeypatch):
    """WR-02 (33-REVIEW iteration 3): naive == UTC, like every sibling reader.

    `merge._is_iso_timestamp` deliberately ACCEPTS a naive `created_at`, and
    `astimezone()` on a naive datetime assumes the MACHINE's OS zone — so this
    function used to disagree with `core.iso_to_local`,
    `operations.is_backdated` and migration 0027's backfill, all of which read
    naive as UTC. On s1 (OS zone UTC, display_tz Europe/Moscow) that was up to a
    full day of drift for any merged naive row.

    Formulated as an EQUIVALENCE — the same instant written naive and written
    with an explicit `+00:00` must yield the same `days_since` — because that is
    the property itself, and it is the only shape that is meaningful without
    controlling the host's OS zone. HONEST LIMITATION: on a host whose OS zone
    IS UTC the old code satisfied this by accident, so there the assertion is
    vacuous. `tests/test_core.py::test_local_day_of_reads_a_naive_value_as_utc`
    pins the rule host-independently, by passing the zone explicitly.
    """
    other = Product(id=new_id(), code="TEST-NAIVE", name="Наивная метка", quantity=0)
    other.stale_days = 0
    product.stale_days = 0
    session.add(other)
    session.commit()

    aware_iso = _iso_days_ago(5)  # always ends in "+00:00" (see _iso_days_ago)
    naive_iso = aware_iso[:-6]
    assert not naive_iso.endswith("+00:00")

    _record_sale_at(
        session, monkeypatch, aware_iso, product=product, qty=1, price_cents=1000,
        cost_cents=500, business_date="2026-01-01",
    )
    _record_sale_at(
        session, monkeypatch, naive_iso, product=other, qty=1, price_cents=1000,
        cost_cents=500, business_date="2026-01-01",
    )

    by_id = {row["product"].id: row for row in stale_products(session)}
    assert by_id[product.id]["days_since"] == by_id[other.id]["days_since"] == 5


def test_stale_products_does_not_raise_on_an_unparseable_created_at(
    session, product, monkeypatch, client
):
    """WR-02: one unrepairable row costs its own LINE, never the whole page.

    `datetime.fromisoformat` raised here and there was no `try`, so a single
    poisoned `created_at` — which a pre-0027 row may already carry, and which
    intake validation cannot retroactively repair because the ledger is
    append-only — made /reports/products a permanent 500 with no recovery path.
    That is precisely the scenario the «display never raises» rule in
    `core.iso_to_local` / `core.format_ru_date` exists for.

    The poisoned product is SKIPPED rather than reported with a fabricated
    «дней без продажи»: this list exists to be acted on, so an invented number
    would be worse than an absent row.
    """
    poisoned = Product(id=new_id(), code="TEST-BAD", name="Битая метка", quantity=0)
    poisoned.stale_days = 0
    session.add(poisoned)
    session.commit()

    _record_sale_at(
        session, monkeypatch, "не дата", product=poisoned, qty=1, price_cents=1000,
        cost_cents=500, business_date="2026-01-01",
    )

    result = stale_products(session)
    assert poisoned.id not in {row["product"].id for row in result}
    # the never-sold product beside it is still reported — one bad row, one loss
    assert product.id in {row["product"].id for row in result}

    response = client.get("/reports/products")
    assert response.status_code == 200


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
        batch_id=_ensure_batch(session, product),
    )
    record_operation(
        session,
        type_="sale",
        product_id=other.id,
        qty_delta=-5,
        unit_price_cents=1000,
        batch_id=_ensure_batch(session, other),
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


def test_expiry_report_page(client, session, product):
    """LOT-06/D-07: earliest-first list, «просрочено» marker, legacy batches excluded."""
    warehouse = Warehouse(id=new_id(), name="Склад для срока годности")
    session.add(warehouse)
    session.commit()

    future_batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2099-01-01",
        quantity=5,
    )
    past_batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry="2020-01-01",
        quantity=2,
    )
    legacy_batch_row = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        expiry=None,
        quantity=4,
        is_legacy=1,
    )
    session.add_all([future_batch, past_batch, legacy_batch_row])
    session.commit()

    response = client.get("/reports/expiry")
    assert response.status_code == 200
    assert response.text.index("01.01.2020") < response.text.index("01.01.2099")
    assert "просрочено" in response.text
    past_pos = response.text.index("01.01.2020")
    assert "просрочено" in response.text[past_pos : past_pos + 200]
    assert f'/batches/{future_batch.id}/edit"' in response.text


def test_expiry_report_page_empty_state(client):
    response = client.get("/reports/expiry")
    assert response.status_code == 200
    assert "Партий со сроком годности нет." in response.text
