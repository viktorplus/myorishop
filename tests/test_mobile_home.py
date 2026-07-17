"""Phase 11 Plan 02: /m/ home tile grid (D-03).

Extended Phase 23 Plan 07 (DASH-01..05): the same 10-tile nav grid stays
FIRST and UNTOUCHED (Pitfall 1 regression guard — see the structural
ordering test below), with the dashboard_context() content appended below
it in mobile's own card/2-column layout (D-10).
"""

from sqlalchemy import select

from app.core import new_id
from app.models import Batch, Warehouse
from app.routes import mobile_home
from app.services.ledger import record_operation

EXPECTED_HREFS = [
    "/m/sales",
    "/m/receipts",
    "/m/search",
    "/m/writeoff",
    "/m/corrections",
    "/m/transfers",
    "/m/history",
    "/m/reports/expiry",
]


def test_mobile_home_renders_all_tiles_in_order(mobile_client_factory):
    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert "<h1>MyOriShop</h1>" in body
    assert "<nav>" not in body

    positions = [body.index(f'href="{href}"') for href in EXPECTED_HREFS]
    assert positions == sorted(positions)


def test_mobile_home_dashboard_content_is_below_the_untouched_nav_grid(mobile_client_factory):
    """Pitfall 1 structural regression guard: the 10th nav tile («Экспорт
    кассы») must textually precede the new «Показатели» heading — dashboard
    content is provably BELOW the grid, never replacing it."""
    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert body.index('href="/m/finance/report"') < body.index("<h2>Показатели</h2>")


def test_mobile_home_empty_catalog_state_renders_link_and_tiles_still_render(mobile_client_factory):
    """DASH-02 empty state never blocks the rest of the page — no
    ActiveCatalog row is seeded, so the empty-state link renders, and the
    metric tiles/feed heading still render regardless."""
    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert 'Активный каталог не задан. <a href="/catalogs">Указать номер и дату закрытия</a>.' in body
    assert "Сегодня" in body
    assert "Неделя" in body
    assert "Месяц" in body
    assert "Склад" in body


def _ensure_batch(session, product):
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


def test_mobile_home_receipt_feed_card_omits_profit_and_customer(
    session, product, mobile_client_factory
):
    batch_id = _ensure_batch(session, product)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=1000,
        unit_price_cents=1500,
        batch_id=batch_id,
    )

    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert "Прибыль" not in body
    assert "Покупатель" not in body
    assert "Кол-во" in body
    assert "Себестоимость" in body


def test_mobile_home_sale_feed_card_shows_profit_and_customer(
    session, product, mobile_client_factory
):
    batch_id = _ensure_batch(session, product)
    record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-1,
        unit_cost_cents=600,
        unit_price_cents=1000,
        batch_id=batch_id,
    )

    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert "Прибыль" in body
    assert "Покупатель: <span class=\"muted\">Розница</span>" in body
