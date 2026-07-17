"""Phase 11 Plan 02: /m/ home page (D-03).

Extended Phase 23 Plan 07 (DASH-01..05): dashboard_context() content renders
below the page heading (D-10). Phase 24 Plan 05 (D-09/D-10/MOB-01) removed
the old 10-tile nav grid entirely — navigation is now provided by the
persistent top-docked tab bar in mobile_base.html, inherited by every /m/*
page including this one.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import Batch, Warehouse
from app.routes import mobile_home
from app.services.ledger import record_operation

EXPECTED_TABBAR_HREFS = [
    "/m/",
    "/m/products",
    "/m/sales",
    "/m/customers",
    "/m/history",
    "/m/reports/expiry",
    "/m/finance",
]


def test_mobile_home_renders_tabbar_hrefs_in_order(mobile_client_factory):
    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert "<h1>MyOriShop</h1>" in body
    assert "<nav>" not in body

    positions = [body.index(f'href="{href}"') for href in EXPECTED_TABBAR_HREFS]
    assert positions == sorted(positions)


def test_mobile_home_dashboard_content_renders_below_tabbar(mobile_client_factory):
    """D-09/D-10/D-12 regression guard: the tab bar renders above the
    «Показатели» heading, the old tile grid is gone, and the removed
    Экспорт кассы CTA never reappears."""
    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert body.index("mobile-tabbar") < body.index("<h2>Показатели</h2>")
    assert "mobile-tile-grid" not in body
    assert "/m/finance/report" not in body


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
    # Scoped to the feed section — the metric tiles above it legitimately
    # render their own «Прибыль» (Сегодня/Неделя/Месяц), so a whole-body
    # check would false-negative regardless of the feed card's content.
    feed_section = response.text.split("<h2>Последние операции</h2>", 1)[1]
    assert "Прибыль" not in feed_section
    assert "Покупатель" not in feed_section
    assert "Кол-во" in feed_section
    assert "Себестоимость" in feed_section


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
    feed_section = response.text.split("<h2>Последние операции</h2>", 1)[1]
    assert "Прибыль" in feed_section
    assert 'Покупатель: <span class="muted">Розница</span>' in feed_section
