"""CST-01/02 executable contract for the customer CRUD + purchase-history slice.

Interface contract for Plan 04-04 (customers CRUD/search/history). Module
path and signatures below are fixed — implement against them, do not rename.

This file is RED by design until 04-04 lands: app.services.customers does
not exist yet, so the whole module fails to collect. Do NOT stub the
service here.

Naming convention (used by -k filters): route/e2e tests are prefixed
test_web_; everything else is service level. Selectors mirror
04-VALIDATION.md's Requirements -> Test Map (crud, search, history,
history_frozen).
"""

from app.services.customers import (
    create_customer,
    get_customer,
    purchase_history,
    search_customers,
    update_customer,
)
from app.services.sales import register_sale  # noqa: F401 (used to seed linked sales)
from sqlalchemy import select

from app.models import Customer

# --- Service level ---


def test_create_customer_maintains_search_lc(session):
    """CST-01/D-07: search_lc is the lowercased "name surname consultant"."""
    customer, errors = create_customer(
        session, name="Анна", surname="Иванова", consultant_number="12345"
    )
    assert errors == {}
    assert customer.search_lc == "анна иванова 12345"


def test_create_customer_requires_name(session):
    """CST-01: blank name -> RU error, nothing written."""
    before = len(session.scalars(select(Customer)).all())
    customer, errors = create_customer(session, name="  ", surname="", consultant_number="")
    assert customer is None
    assert errors["name"] == "Укажите имя покупателя."
    assert len(session.scalars(select(Customer)).all()) == before


def test_update_customer_changes_fields_and_refreshes_search_lc(session, customer):
    """CST-01: update_customer mutates fields and recomputes search_lc."""
    updated, errors = update_customer(
        session,
        customer.id,
        name="Анна",
        surname="Петрова",
        consultant_number="99999",
    )
    assert errors == {}
    assert updated.surname == "Петрова"
    assert updated.search_lc == "анна петрова 99999"


def test_get_customer_returns_none_for_unknown_id(session):
    """get_customer(unknown) -> None."""
    assert get_customer(session, "no-such-id") is None


def test_search_customers_folds_cyrillic(session, customer):
    """CST-01: query "ан" matches "Анна" via the Python-folded search_lc shadow."""
    matches = search_customers(session, "ан")
    assert customer in matches


def test_search_customers_capped_at_20(session):
    """CST-01: search results are capped at 20 rows."""
    for i in range(25):
        create_customer(session, name=f"Покупатель{i}", surname="", consultant_number="")
    matches = search_customers(session, "")
    assert len(matches) <= 20


def test_purchase_history_returns_rows_for_customer(session, stocked_product, customer):
    """CST-02: purchase_history shows product, date, qty for THAT customer only."""
    result, errors = register_sale(
        session,
        customer_id=customer.id,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
    )
    assert errors == {}

    rows = purchase_history(session, customer.id)
    assert len(rows) == 1
    assert rows[0]["product"].id == stocked_product.id
    assert -rows[0]["op"].qty_delta == 2


def test_purchase_history_frozen(session, stocked_product, customer):
    """CST-02: history reads the FROZEN unit_price_cents, not the current card price."""
    result, errors = register_sale(
        session,
        customer_id=customer.id,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
    )
    assert errors == {}

    stocked_product.sale_cents = 999999
    session.commit()

    rows = purchase_history(session, customer.id)
    assert rows[0]["op"].unit_price_cents == 1500


# --- Web slice (routes + templates) ---


def test_web_customers_list(client):
    """/customers: RU title «Покупатели»."""
    response = client.get("/customers")
    assert response.status_code == 200
    assert "Покупатели" in response.text


def test_web_customer_create_redirect(client):
    """POST /customers -> 303 redirect to /customers on success."""
    response = client.post(
        "/customers",
        data={"name": "Ольга", "surname": "Сидорова", "consultant_number": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/customers"


def test_web_customer_detail_history(client, session, stocked_product, customer):
    """Detail page shows «История покупок» + the frozen price."""
    result, errors = register_sale(
        session,
        customer_id=customer.id,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
    )
    assert errors == {}

    response = client.get(f"/customers/{customer.id}")
    assert response.status_code == 200
    assert "История покупок" in response.text
    assert stocked_product.name in response.text


def test_web_nav_has_customers_link(client):
    """Nav gains the customers entry: Покупатели -> /customers."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/customers"' in response.text
    assert "Покупатели" in response.text
