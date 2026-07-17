"""Phase 24 Plan 06 (MOB-01): GET /m/customers — mobile Покупатели page."""

from app.routes import mobile_customers


def test_mobile_customers_page_renders(mobile_client_factory, customer):
    client = mobile_client_factory(mobile_customers.router)
    response = client.get("/m/customers")

    assert response.status_code == 200
    body = response.text
    assert customer.name in body
    assert customer.surname in body


def test_mobile_customers_empty_state(mobile_client_factory, session):
    client = mobile_client_factory(mobile_customers.router)
    response = client.get("/m/customers")

    assert response.status_code == 200
    assert "Покупателей пока нет." in response.text


def test_mobile_customers_registered_in_real_app(client):
    response = client.get("/m/customers")
    assert response.status_code == 200
