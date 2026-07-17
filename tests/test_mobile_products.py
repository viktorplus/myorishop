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
