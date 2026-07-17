"""CST-01/02 executable contract for the customer CRUD + purchase-history slice.

Interface contract for Plan 04-04 (customers CRUD/search/history). Module
path and signatures below are fixed — implement against them, do not rename.

This file is RED by design until 04-04 lands: app.services.customers does
not exist yet, so the whole module fails to collect. Do NOT stub the
service here.

Naming convention (used by -k filters): route/e2e tests are prefixed
test_web_; everything else is service level. Selectors mirror
04-VALIDATION.md's Requirements -> Test Map (crud, search, history,
history_frozen). 21-VALIDATION.md Wave 0 adds past_sale_fixture (the
backdated-sale fixture smoke test).
"""

from sqlalchemy import select

from app.models import Customer
from app.services.batches import open_batches
from app.services.customers import (
    create_customer,
    get_customer,
    list_customers_view,
    purchase_history,
    search_customers,
    update_customer,
)
from app.services.sales import register_sale  # noqa: F401 (used to seed linked sales)

# --- Service level ---


def _only_batch(session, product):
    """The single open batch id seeded by the stocked_product fixture (LOT-02)."""
    return open_batches(session, product.id)[0].id


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


def test_list_customers_view_filters_independently(session):
    """LIST-02/D-04: name/surname/consultant_number filter independently — NOT the
    combined search_lc used by search_customers/customer_search_view."""
    create_customer(session, name="Анна", surname="Иванова", consultant_number="111")
    create_customer(session, name="Анна", surname="Петрова", consultant_number="222")
    create_customer(session, name="Ольга", surname="Иванова", consultant_number="333")

    by_name = list_customers_view(session, name="анна")
    assert {c.surname for c in by_name["rows"]} == {"Иванова", "Петрова"}

    by_surname = list_customers_view(session, surname="иванова")
    assert {c.name for c in by_surname["rows"]} == {"Анна", "Ольга"}

    by_consultant = list_customers_view(session, consultant_number="222")
    assert len(by_consultant["rows"]) == 1
    assert by_consultant["rows"][0].consultant_number == "222"


def test_list_customers_view_sort_surname_and_consultant(session):
    """LIST-03/D-06/D-07: sort is an allow-list; default (no sort) is name ascending."""
    create_customer(session, name="Вера", surname="Яковлева", consultant_number="003")
    create_customer(session, name="Анна", surname="Борисова", consultant_number="001")
    create_customer(session, name="Борис", surname="Антонов", consultant_number="002")

    default_names = [c.name for c in list_customers_view(session)["rows"]]
    assert default_names == sorted(default_names)

    by_surname = [c.surname for c in list_customers_view(session, sort="surname")["rows"]]
    assert by_surname == sorted(by_surname)

    by_consultant = [
        c.consultant_number for c in list_customers_view(session, sort="consultant_number")["rows"]
    ]
    assert by_consultant == sorted(by_consultant)


def test_list_customers_view_paginates(session):
    """LIST-01/D-01/D-03: 25 rows -> 20 on page 0; out-of-range page clamps, never raises."""
    for i in range(25):
        create_customer(session, name=f"Покупатель{i:02d}", surname="", consultant_number="")

    result = list_customers_view(session, page=0)
    assert len(result["rows"]) == 20
    assert result["total"] == 25
    assert result["total_pages"] == 2

    clamped = list_customers_view(session, page=99)
    assert len(clamped["rows"]) == 5


def test_purchase_history_returns_rows_for_customer(session, stocked_product, customer):
    """CST-02: purchase_history shows product, date, qty for THAT customer only."""
    result, errors = register_sale(
        session,
        customer_id=customer.id,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
        batch_ids=[_only_batch(session, stocked_product)],
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
        batch_ids=[_only_batch(session, stocked_product)],
    )
    assert errors == {}

    stocked_product.sale_cents = 999999
    session.commit()

    rows = purchase_history(session, customer.id)
    assert rows[0]["op"].unit_price_cents == 1500


def test_past_sale_fixture_seeds_backdated_op(session, past_sale, customer, stocked_product):
    """21-VALIDATION.md Wave 0: past_sale seeds a Sale+Operation pair at an
    explicit past UTC timestamp, readable via purchase_history."""
    sale, op = past_sale(customer, stocked_product, created_at="2026-01-15T10:00:00+00:00")

    assert op.created_at == "2026-01-15T10:00:00+00:00"
    assert op.qty_delta < 0
    assert op.sale_id == sale.id

    rows = purchase_history(session, customer.id)
    assert any(r["op"].id == op.id for r in rows)


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
        batch_ids=[_only_batch(session, stocked_product)],
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


def test_web_customers_search_route_retired(client):
    """LIST-02/D-04: /customers/search is retired (Pitfall 6) — header-row filters on
    the main /customers list route replace it; the sale-picker's own
    /sales/customer-search route is untouched."""
    response = client.get("/customers/search")
    assert response.status_code == 404


def test_web_customers_filter_row_narrows_results(client, session):
    """LIST-02/D-04/D-05: the surname header-row filter narrows /customers rows."""
    create_customer(session, name="Анна", surname="Иванова", consultant_number="")
    create_customer(session, name="Ольга", surname="Петрова", consultant_number="")

    response = client.get("/customers", params={"surname": "иванов"})
    assert response.status_code == 200
    assert "Иванова" in response.text
    assert "Петрова" not in response.text


def test_web_customers_pagination_bar_shows_correct_total(client, session):
    """LIST-01/D-01/D-03: 25 seeded customers -> «Страница 1 из 2»."""
    for i in range(25):
        create_customer(session, name=f"Покупатель{i:02d}", surname="", consultant_number="")

    response = client.get("/customers")
    assert response.status_code == 200
    assert "Страница 1 из 2" in response.text


def test_web_customers_page_has_no_standalone_search_input(client):
    """Pitfall 6: the old standalone q search box/route is gone; only header-row filters remain."""
    response = client.get("/customers")
    assert response.status_code == 200
    assert 'hx-get="/customers/search"' not in response.text
    assert 'name="q"' not in response.text
