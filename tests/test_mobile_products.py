"""Phase 24 Plan 06 (MOB-01): GET /m/products — mobile Товары page."""

from app.routes import mobile_products


def test_mobile_products_page_renders(mobile_client_factory, product):
    client = mobile_client_factory(mobile_products.router)
    response = client.get("/m/products")

    assert response.status_code == 200
    body = response.text
    assert product.code in body
    assert product.name in body


def test_mobile_products_empty_state(mobile_client_factory):
    client = mobile_client_factory(mobile_products.router)
    response = client.get("/m/products")

    assert response.status_code == 200
    assert "Товаров пока нет." in response.text


def test_mobile_products_registered_in_real_app(client):
    response = client.get("/m/products")
    assert response.status_code == 200


def test_mobile_products_toolbar_reaches_transfers_corrections_search(
    mobile_client_factory, product
):
    """CR-01 (24-REVIEW.md) / 24-VERIFICATION.md gap closure: the mobile
    home tile grid removal (D-10) deleted the only mobile nav path to
    /m/transfers, /m/corrections, and /m/search. This asserts the mobile
    Товары toolbar renders working <a href> links to all three — rendered-
    link presence, not just direct-URL 200 (which
    tests/test_mobile_wiring.py::test_every_mobile_tile_path_is_reachable
    already proves and cannot catch this class of regression)."""
    client = mobile_client_factory(mobile_products.router)
    response = client.get("/m/products")

    assert response.status_code == 200
    assert 'href="/m/transfers"' in response.text
    assert 'href="/m/corrections"' in response.text
    assert 'href="/m/search"' in response.text
