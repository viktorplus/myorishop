"""Mobile Места хранения (todo 2026-08-31): GET /m/locations — card view.

Reuses locations.list_locations_view unchanged, so the place-derivation and
sorting contracts are pinned once in tests/test_locations.py. What is pinned
HERE is the mobile wiring: card links that are real navigation paths, the
HX response shape (cards + oob pagination, no page chrome), and the toolbar
entry point.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import Batch, Product, Warehouse
from app.routes import mobile_locations, mobile_products, nav_section


def _stock(session, *, code, name, quantity=1, comment=None, expiry=None):
    """One product with one batch holding `quantity` pieces at `comment`."""
    warehouse = session.scalars(select(Warehouse)).first()
    if warehouse is None:
        warehouse = Warehouse(id=new_id(), name="Офис")
        session.add(warehouse)
        session.commit()
    product = Product(id=new_id(), code=code, name=name, name_lc=name.lower(), quantity=quantity)
    session.add(product)
    session.commit()
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=quantity,
        comment=comment,
        expiry=expiry,
    )
    session.add(batch)
    session.commit()
    return product, batch


def test_mobile_locations_lists_place_cards(mobile_client_factory, session):
    _stock(session, code="M1", name="Товар", quantity=6, comment="полка 59")
    client = mobile_client_factory(mobile_locations.router)

    response = client.get("/m/locations")

    assert response.status_code == 200
    body = response.text
    assert "полка 59" in body
    assert "Позиций: 1 · Штук: 6" in body
    # the card is the nav path into the place — assert the rendered link
    assert 'href="/m/locations?place=%D0%BF%D0%BE%D0%BB%D0%BA%D0%B0%2059"' in body


def test_mobile_locations_place_cards_link_to_batch_edit(mobile_client_factory, session):
    _, batch = _stock(session, code="M2", name="Товар", comment="полка 1")
    client = mobile_client_factory(mobile_locations.router)

    response = client.get("/m/locations", params={"place": "полка 1"})

    assert response.status_code == 200
    assert f'href="/m/batches/{batch.id}/edit"' in response.text


def test_mobile_locations_search_by_code_answers_where_it_lies(mobile_client_factory, session):
    _stock(session, code="35532", name="Парфюмерная вода", comment="полка 39")
    _stock(session, code="30355", name="Другое", comment="полка 40")
    client = mobile_client_factory(mobile_locations.router)

    response = client.get("/m/locations", params={"q": "35532"})

    assert response.status_code == 200
    assert "полка 39" in response.text
    # the non-matching product is gone from the CARDS (its place still shows
    # in the picker's <option> list, which always offers every place)
    assert "Другое" not in response.text


def test_mobile_locations_empty_state(mobile_client_factory, session):
    client = mobile_client_factory(mobile_locations.router)

    response = client.get("/m/locations")

    assert response.status_code == 200
    assert "Мест хранения пока нет." in response.text


def test_hx_request_returns_cards_plus_oob_pagination_without_chrome(
    mobile_client_factory, session
):
    """CR-01 precedent: the two structural siblings arrive together, never
    nested, so a search swap cannot destroy the pagination control."""
    _stock(session, code="M3", name="Товар", comment="полка 1")
    client = mobile_client_factory(mobile_locations.router)

    response = client.get("/m/locations", headers={"HX-Request": "true"})

    body = response.text
    assert response.status_code == 200
    assert '<div id="location-cards">' in body
    assert '<div id="location-pagination" hx-swap-oob="true">' in body
    assert "<!doctype html>" not in body.lower()  # no page chrome


def test_mobile_locations_registered_in_real_app(client):
    assert client.get("/m/locations").status_code == 200


def test_mobile_products_toolbar_reaches_locations(mobile_client_factory, product):
    client = mobile_client_factory(mobile_products.router)

    response = client.get("/m/products")

    assert response.status_code == 200
    assert 'href="/m/locations"' in response.text


def test_nav_section_highlights_products():
    assert nav_section("/m/locations") == "products"
