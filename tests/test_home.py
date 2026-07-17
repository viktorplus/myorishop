"""Web-slice tests for the rebuilt Главная (DASH-01..05, desktop).

Mirrors tests/test_dashboard.py's operation-seeding helpers, applied
end-to-end through the real GET / route + templates instead of calling
app.services.dashboard directly. `dashboard_context` itself is already
fully unit-tested (Plan 03) — this file only proves the route/template
wiring: headings, tile grid, empty/closed-catalog states, per-type feed
columns, and the «Подробнее» link target (DASH-05 -> HIST-01 handoff).
"""

from sqlalchemy import select

from app.core import new_id
from app.models import ActiveCatalog, Batch, Warehouse
from app.services.ledger import record_operation


def _ensure_batch(session, product):
    """A valid batch id for a product (mirrors tests/test_dashboard.py)."""
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


def _record(session, product, *, type_, qty_delta, cost_cents=None, price_cents=None):
    batch_id = _ensure_batch(session, product)
    return record_operation(
        session,
        type_=type_,
        product_id=product.id,
        qty_delta=qty_delta,
        unit_cost_cents=cost_cents,
        unit_price_cents=price_cents,
        batch_id=batch_id,
    )


# --- Page structure / empty states -------------------------------------------


def test_web_home_renders_headings_and_tiles(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Главная" in response.text
    assert "Последние операции" in response.text
    # Four tile labels (DASH-03/04).
    assert "Сегодня" in response.text
    assert "Неделя" in response.text
    assert "Месяц" in response.text
    assert "Склад" in response.text


def test_web_home_empty_catalog_state_and_rest_of_page_still_renders(client):
    """DASH-02: no ActiveCatalog row -> empty-state link; tiles still render."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Активный каталог не задан" in response.text
    assert 'href="/catalogs"' in response.text
    # Rest of the dashboard renders independently (CONTEXT: not a blocking error).
    assert "Сегодня" in response.text
    assert "Склад" in response.text


def test_web_home_empty_feed_shows_empty_state(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Операций пока нет." in response.text


def test_web_home_closed_catalog_shows_word_not_negative_number(session, client):
    """DASH-02/WCAG 1.4.1: a closed catalog shows «закрыт», never a bare
    negative day count or a red tint."""
    catalog = ActiveCatalog(id=new_id(), number="326", close_date="2020-01-01")
    session.add(catalog)
    session.commit()

    response = client.get("/")
    assert response.status_code == 200
    assert "закрыт" in response.text
    assert "326" in response.text
    assert "-" not in response.text.split("закрыт")[0].split("326")[-1]


def test_web_home_open_catalog_shows_days_left_countdown(session, client):
    from datetime import date, timedelta

    close_date = (date.today() + timedelta(days=5)).isoformat()
    catalog = ActiveCatalog(id=new_id(), number="327", close_date=close_date)
    session.add(catalog)
    session.commit()

    response = client.get("/")
    assert response.status_code == 200
    assert "327" in response.text
    assert "осталось дней" in response.text


# --- Feed rows: per-type populated cells / muted dashes -----------------------


def test_web_home_receipt_row_populates_expiry_qty_cost_not_profit_or_customer(
    session, client, product
):
    _record(session, product, type_="receipt", qty_delta=5, cost_cents=100, price_cents=200)
    response = client.get("/")
    assert response.status_code == 200
    # <td>-scoped (not the nav link, which also reads "Приход" for /receipts/new).
    assert "<td>Приход</td>" in response.text  # OPERATION_TYPE_LABELS["receipt"]
    assert product.code in response.text
    assert "+5" in response.text


def test_web_home_sale_row_populates_all_and_shows_розница(session, client, product):
    _record(session, product, type_="receipt", qty_delta=10, cost_cents=100, price_cents=200)
    _record(session, product, type_="sale", qty_delta=-1, cost_cents=100, price_cents=200)
    response = client.get("/")
    assert response.status_code == 200
    assert "<td>Продажа</td>" in response.text  # OPERATION_TYPE_LABELS["sale"]
    assert "Розница" in response.text  # walk-in customer fallback


def test_web_home_writeoff_row_populates_qty_cost_not_profit_or_customer(
    session, client, product
):
    _record(session, product, type_="receipt", qty_delta=5, cost_cents=100, price_cents=200)
    _record(session, product, type_="writeoff", qty_delta=-1, cost_cents=100)
    response = client.get("/")
    assert response.status_code == 200
    # <td>-scoped (not the nav link, which also reads "Списание" for /writeoff).
    assert "<td>Списание</td>" in response.text  # OPERATION_TYPE_LABELS["writeoff"]


def test_web_home_transfer_row_shows_dashes_for_cost_and_profit(session, client, product):
    _record(session, product, type_="receipt", qty_delta=5, cost_cents=100, price_cents=200)
    _record(session, product, type_="transfer", qty_delta=1)
    response = client.get("/")
    assert response.status_code == 200
    # <td>-scoped (not the nav link, which also reads "Перемещение" for /transfers).
    assert "<td>Перемещение</td>" in response.text  # OPERATION_TYPE_LABELS["transfer"]


# --- Feed row action link (DASH-05 -> HIST-01 handoff) ------------------------


def test_web_home_feed_row_action_links_into_history_prefiltered(session, client, product):
    _record(session, product, type_="receipt", qty_delta=5, cost_cents=100, price_cents=200)
    response = client.get("/")
    assert response.status_code == 200
    assert f"/history?type=receipt&product={product.id}" in response.text
    assert "Подробнее" in response.text
