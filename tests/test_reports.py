"""Unit tests for app.services.reports (RPT-01): sales/profit aggregation.

Pins the NULL-cost-safe profit contract (RESEARCH Pitfall 2: a sale line
with unknown unit_cost_cents must never silently inflate profit by its
full revenue) and the "reports are historical, never filter
Product.deleted_at" contract (RESEARCH Pitfall 5).
"""

from datetime import date

from app.core import local_day_bounds_utc, new_id
from app.models import Product
from app.services.ledger import record_operation
from app.services.reports import sales_profit_report

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
