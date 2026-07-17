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

from datetime import date

import pytest
from sqlalchemy import select

from app.core import format_ru_date
from app.models import Customer, CustomerContact
from app.services.batches import open_batches
from app.services.customers import (
    ADDRESS_TOO_LONG_ERROR,
    CONTACT_VALUE_TOO_LONG_ERROR,
    _period_starts,
    contacts_by_kind,
    create_customer,
    get_customer,
    list_customers_view,
    purchase_history,
    search_customers,
    spend_totals,
    spend_view,
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


def test_create_customer_stores_address(session):
    """CUST-05: create with an address, assert customer.address reads back exactly."""
    customer, errors = create_customer(
        session, name="Анна", surname="", consultant_number="", address="ул. Ленина, 10"
    )
    assert errors == {}
    assert customer.address == "ул. Ленина, 10"


def test_update_customer_changes_address(session, customer):
    """CUST-05: update_customer changes an existing customer's address."""
    updated, errors = update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        address="ул. Мира, 5",
    )
    assert errors == {}
    assert updated.address == "ул. Мира, 5"


def test_customer_address_blank_stores_none(session):
    """CUST-05: address="" and address="   " both store None, not ""."""
    empty, errors = create_customer(
        session, name="Анна", surname="", consultant_number="", address=""
    )
    assert errors == {}
    assert empty.address is None

    whitespace, errors = create_customer(
        session, name="Ольга", surname="", consultant_number="", address="   "
    )
    assert errors == {}
    assert whitespace.address is None


def test_customer_address_too_long_rejected(session):
    """WR-05: a 301-char address is rejected, nothing is written."""
    before = len(session.scalars(select(Customer)).all())
    customer, errors = create_customer(
        session, name="Анна", surname="", consultant_number="", address="a" * 301
    )
    assert customer is None
    assert errors == {"address": ADDRESS_TOO_LONG_ERROR}
    assert len(session.scalars(select(Customer)).all()) == before


def test_contacts_validation_discards_blank_rows(session):
    """CUST-01..04: blank/whitespace-only values are discarded, never written."""
    customer, errors = create_customer(
        session,
        name="Анна",
        surname="",
        consultant_number="",
        contacts={"phone": ["+7900", "", "   "]},
    )
    assert errors == {}
    rows = session.scalars(
        select(CustomerContact).where(CustomerContact.customer_id == customer.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].value == "+7900"


def test_contacts_validation_rejects_unknown_kind(session):
    """T-21-09: an unknown kind is a programmer error, not a form error."""
    with pytest.raises(ValueError):
        create_customer(
            session,
            name="Анна",
            surname="",
            consultant_number="",
            contacts={"fax": ["123"]},
        )


def test_contacts_validation_value_too_long(session):
    """WR-05: a 301-char value is rejected per-kind, writes zero rows."""
    before = len(session.scalars(select(CustomerContact)).all())
    customer, errors = create_customer(
        session,
        name="Анна",
        surname="",
        consultant_number="",
        contacts={"phone": ["a" * 301]},
    )
    assert customer is None
    assert errors == {"phone": CONTACT_VALUE_TOO_LONG_ERROR}
    assert len(session.scalars(select(CustomerContact)).all()) == before


def test_contacts_replace_does_not_duplicate(session, customer):
    """CUST-01..04: re-saving replaces contacts rather than duplicating them."""
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={"phone": ["+7900", "+7901"]},
    )
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={"phone": ["+7900"]},
    )
    rows = session.scalars(
        select(CustomerContact).where(CustomerContact.customer_id == customer.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].value == "+7900"


def test_contacts_replace_none_leaves_contacts_untouched(session, customer):
    """contacts=None -> existing rows survive untouched."""
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={"phone": ["+7900", "+7901"]},
    )
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts=None,
    )
    rows = session.scalars(
        select(CustomerContact).where(CustomerContact.customer_id == customer.id)
    ).all()
    assert len(rows) == 2


def test_contacts_phone_multiple_values_persist(session, customer):
    """CUST-01: three phones save and read back in submitted order."""
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={"phone": ["+7900", "+7901", "+7902"]},
    )
    result = contacts_by_kind(session, customer.id)
    assert [row.value for row in result["phone"]] == ["+7900", "+7901", "+7902"]


def test_contacts_telegram_multiple_values_persist(session, customer):
    """CUST-02: two Telegram handles save and read back."""
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={"telegram": ["@anna", "@anna_shop"]},
    )
    result = contacts_by_kind(session, customer.id)
    assert [row.value for row in result["telegram"]] == ["@anna", "@anna_shop"]


def test_contacts_email_multiple_values_persist(session, customer):
    """CUST-03: two emails save and read back."""
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={"email": ["anna@example.com", "shop@example.com"]},
    )
    result = contacts_by_kind(session, customer.id)
    assert [row.value for row in result["email"]] == ["anna@example.com", "shop@example.com"]


def test_contacts_social_multiple_values_persist(session, customer):
    """CUST-04: two free-form social links, verbatim, no normalization."""
    link_with_query = "https://vk.com/anna?utm_source=x&y=1"
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={"social": ["https://instagram.com/anna", link_with_query]},
    )
    result = contacts_by_kind(session, customer.id)
    assert [row.value for row in result["social"]] == [
        "https://instagram.com/anna",
        link_with_query,
    ]


def test_contacts_by_kind_returns_all_kinds_for_bare_customer(session, customer):
    """A customer with zero contacts still gets all four keys, each []."""
    result = contacts_by_kind(session, customer.id)
    assert list(result.keys()) == ["phone", "telegram", "email", "social"]
    assert result == {"phone": [], "telegram": [], "email": [], "social": []}


def test_contacts_all_kinds_are_independent(session, customer):
    """Saving all four kinds at once: each reads back only its own values."""
    update_customer(
        session,
        customer.id,
        name=customer.name,
        surname="",
        consultant_number="",
        contacts={
            "phone": ["+7900"],
            "telegram": ["@anna"],
            "email": ["anna@example.com"],
            "social": ["https://vk.com/anna"],
        },
    )
    result = contacts_by_kind(session, customer.id)
    assert [row.value for row in result["phone"]] == ["+7900"]
    assert [row.value for row in result["telegram"]] == ["@anna"]
    assert [row.value for row in result["email"]] == ["anna@example.com"]
    assert [row.value for row in result["social"]] == ["https://vk.com/anna"]


def test_spend_totals_month_quarter_year_with_injected_today(session, product, customer, past_sale):
    """CUST-07: three genuinely different totals via an injected mid-quarter today (Pitfall 7)."""
    today = date(2026, 5, 20)
    past_sale(
        customer, product, created_at="2026-05-10T10:00:00+00:00", qty=1, unit_price_cents=2000
    )
    past_sale(
        customer, product, created_at="2026-04-15T10:00:00+00:00", qty=1, unit_price_cents=3000
    )
    past_sale(
        customer, product, created_at="2026-02-10T10:00:00+00:00", qty=1, unit_price_cents=5000
    )

    totals = spend_totals(session, customer.id, today=today)
    assert totals == {"month": 2000, "quarter": 5000, "year": 10000}


def test_spend_totals_period_starts_boundary_table():
    """CUST-07: `_period_starts` against the documented quarter-boundary table."""
    assert _period_starts(date(2026, 7, 17))["quarter"] == date(2026, 7, 1)
    assert _period_starts(date(2026, 3, 31))["quarter"] == date(2026, 1, 1)
    assert _period_starts(date(2026, 12, 31))["quarter"] == date(2026, 10, 1)
    assert _period_starts(date(2026, 1, 1))["quarter"] == date(2026, 1, 1)


def test_spend_net_of_returns_subtracts(session, product, customer, past_sale):
    """CUST-07/D-06: a return at the frozen price subtracts from the window total."""
    today = date(2026, 5, 20)
    sale, _ = past_sale(
        customer, product, created_at="2026-05-10T10:00:00+00:00", qty=10, unit_price_cents=1000
    )
    past_sale(
        customer,
        product,
        created_at="2026-05-12T10:00:00+00:00",
        qty=4,
        unit_price_cents=1000,
        type_="return",
        sale=sale,
    )

    totals = spend_totals(session, customer.id, today=today)
    assert totals["month"] == 6000


def test_spend_window_excludes_sale_outside_period(session, product, customer, past_sale):
    """CUST-07: a sale 2 months before `today` is excluded from month but present in year."""
    today = date(2026, 5, 20)
    past_sale(
        customer, product, created_at="2026-03-15T10:00:00+00:00", qty=1, unit_price_cents=1000
    )

    totals = spend_totals(session, customer.id, today=today)
    assert totals["month"] == 0
    assert totals["year"] == 1000


def test_spend_empty_customer_returns_zero_not_none(session, customer):
    """CUST-07/Pitfall 4: a customer with zero orders returns 0, never None, in every window."""
    totals = spend_totals(session, customer.id, today=date(2026, 5, 20))
    assert totals["month"] is not None
    assert totals["quarter"] is not None
    assert totals["year"] is not None
    assert totals == {"month": 0, "quarter": 0, "year": 0}


def test_spend_null_price_line_does_not_crash_sum(session, product, customer, past_sale):
    """CUST-07/Pitfall 4: a NULL unit_price_cents line contributes 0 and does not crash SUM()."""
    today = date(2026, 5, 20)
    past_sale(
        customer, product, created_at="2026-05-05T10:00:00+00:00", qty=1, unit_price_cents=None
    )
    past_sale(
        customer, product, created_at="2026-05-06T10:00:00+00:00", qty=1, unit_price_cents=2000
    )

    totals = spend_totals(session, customer.id, today=today)
    assert totals["month"] == 2000
    assert isinstance(totals["month"], int)


def test_spend_view_start_iso_is_a_string(session, customer):
    """The `| ru_date` TypeError guard: every `spend_view` start_iso is a string."""
    view = spend_view(session, customer.id, today=date(2026, 7, 17))
    for period in view.values():
        assert isinstance(period["start_iso"], str)
    assert format_ru_date(view["month"]["start_iso"]) == "01.07.2026"


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
