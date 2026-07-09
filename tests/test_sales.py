"""SAL-01..05 executable contract for the sale basket slice.

Interface contract for Plans 04-02 (basket transaction), 04-03 (oversell
warn/confirm), and 04-05 (customer picker). Module path and signatures
below are fixed — implement against them, do not rename.

This file is RED by design until those waves land: app.services.sales does
not exist yet (neither does app.services.customers, imported for the
customer-link fixtures/setup), so the whole module fails to collect.
Do NOT stub the services here — the whole point of Wave 0 is a failing
contract that later waves turn green.

Naming convention (used by -k filters): route/e2e tests are prefixed
test_web_; everything else is service level. Selectors mirror
04-VALIDATION.md's Requirements -> Test Map (stock, empty_basket,
one_transaction, price_override, customer_link, snapshot, null_cost,
oversell).
"""

from app.services.sales import lookup_prefill, recent_sales, register_sale  # noqa: F401
from sqlalchemy import select

from app.models import Operation
from app.services.ledger import compute_stock, record_operation


def _sale_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "sale")).all()


# --- Service level ---


def test_stock_decrements_for_basket_sale(session, stocked_product):
    """SAL-01: a 2-line basket writes 2 sale ops; stock drops by summed qty."""
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code, stocked_product.code],
        qtys=["2", "3"],
        prices=["15,00", "14,00"],
    )
    assert errors == {}
    assert result

    ops = _sale_ops(session)
    assert len(ops) == 2
    assert all(op.qty_delta < 0 for op in ops)
    assert stocked_product.quantity == 8 - 5
    assert compute_stock(session, stocked_product.id) == 8 - 5


def test_empty_basket_returns_error(session):
    """SAL-01: zero lines cannot be finalized; 0 writes (D-03)."""
    result, errors = register_sale(session, customer_id=None, codes=[], qtys=[], prices=[])
    assert result is None
    assert "Добавьте хотя бы одну строку, чтобы оформить продажу." in errors.values()
    assert _sale_ops(session) == []


def test_one_transaction_all_or_nothing(session, stocked_product):
    """SAL-01: an unknown code on any line aborts the WHOLE basket (one transaction)."""
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code, "UNKNOWN-CODE"],
        qtys=["1", "1"],
        prices=["15,00", "15,00"],
    )
    assert result is None
    assert errors
    assert _sale_ops(session) == []


def test_price_override_uses_entered_price(session, stocked_product):
    """SAL-02: entered price overrides the card sale_cents; snapshot = entered price."""
    stocked_product.sale_cents = 1500
    session.commit()

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["20,00"],
    )
    assert errors == {}
    op = _sale_ops(session)[0]
    assert op.unit_price_cents == 2000


def test_customer_link_sets_header_customer_id(session, stocked_product, customer):
    """SAL-03: a sale with customer_id set links the header to that customer."""
    result, errors = register_sale(
        session,
        customer_id=customer.id,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
    )
    assert errors == {}
    assert result["header"].customer_id == customer.id


def test_customer_link_walkin_customer_id_null(session, stocked_product):
    """SAL-03/D-04: a walk-in sale (no customer) is valid; header.customer_id is NULL."""
    result, errors = register_sale(
        session,
        customer_id="",
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
    )
    assert errors == {}
    assert result["header"].customer_id is None


def test_snapshot_frozen_after_price_change(session, stocked_product):
    """SAL-05: unit_cost/unit_price freeze at write; later card edits don't touch the op."""
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
    )
    assert errors == {}
    op = _sale_ops(session)[0]
    frozen_cost, frozen_price = op.unit_cost_cents, op.unit_price_cents

    stocked_product.cost_cents = 99999
    stocked_product.sale_cents = 88888
    session.commit()

    session.refresh(op)
    assert op.unit_cost_cents == frozen_cost
    assert op.unit_price_cents == frozen_price


def test_null_cost_allowed_sale_succeeds(session, product):
    """SAL-05/D-12: NULL card cost -> op cost NULL, sale is NOT blocked."""
    record_operation(session, type_="receipt", product_id=product.id, qty_delta=5)
    assert product.cost_cents is None

    result, errors = register_sale(
        session, customer_id=None, codes=[product.code], qtys=["1"], prices=["10,00"]
    )
    assert errors == {}
    op = _sale_ops(session)[0]
    assert op.unit_cost_cents is None


def test_null_cost_empty_price_rejected(session, stocked_product):
    """SAL-05/D-12: an empty per-line price is rejected; 0 writes."""
    result, errors = register_sale(
        session, customer_id=None, codes=[stocked_product.code], qtys=["1"], prices=[""]
    )
    assert result is None
    assert "Укажите цену продажи." in errors.values()
    assert _sale_ops(session) == []


def test_oversell_blocks_without_confirm(session, stocked_product):
    """SAL-04: requesting more than stock with no confirm -> oversell signal, 0 writes."""
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["100"],
        prices=["15,00"],
    )
    assert errors == {}
    assert result.get("oversell")
    assert _sale_ops(session) == []


def test_oversell_confirm_writes_negative_stock(session, stocked_product):
    """SAL-04/D-09: confirm=1 skips the block; sale writes and stock may go negative."""
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["100"],
        prices=["15,00"],
        confirm="1",
    )
    assert errors == {}
    assert not result.get("oversell")
    assert stocked_product.quantity < 0


def test_oversell_aggregates_duplicate_lines(session, stocked_product):
    """Pitfall 6: 2 lines of the SAME product are summed before the stock check.

    stocked_product has 8 in stock; 5 + 5 = 10 > 8 -> oversells even though
    each individual line (5) would pass alone.
    """
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code, stocked_product.code],
        qtys=["5", "5"],
        prices=["15,00", "15,00"],
    )
    assert errors == {}
    assert result.get("oversell")
    assert _sale_ops(session) == []


# --- Web slice (routes + templates) ---


def test_web_sale_page_renders_form(client):
    """/sales/new: RU title «Продажа» + the basket table."""
    response = client.get("/sales/new")
    assert response.status_code == 200
    assert "Продажа" in response.text
    assert 'id="basket-rows"' in response.text
    assert "Оформить продажу" in response.text


def test_web_sale_post_success_shows_confirmation(client, stocked_product):
    """D-02: success -> «Продажа оформлена:» + 200 partial (never a full page)."""
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Продажа оформлена:" in response.text
    assert "<html" not in response.text


def test_web_sale_post_empty_basket_422(client):
    """Empty basket -> 422 with the empty-basket RU error."""
    response = client.post(
        "/sales",
        data={"code[]": [], "qty[]": [], "price[]": [], "customer_id": "", "confirm": ""},
    )
    assert response.status_code == 422
    assert "Добавьте хотя бы одну строку, чтобы оформить продажу." in response.text


def test_web_sale_lookup_prefills_price(client, session, stocked_product):
    """Per-line lookup pre-fills Цена продажи from the product card sale_cents."""
    stocked_product.sale_cents = 1500
    session.commit()

    response = client.get(
        "/sales/lookup", params={"code": stocked_product.code, "name": "", "price": ""}
    )
    assert response.status_code == 200
    assert stocked_product.name in response.text


def test_web_sale_oversell_shows_warning_and_confirm_writes(client, stocked_product):
    """SAL-04: oversell POST (no confirm) warns + writes 0; confirm=1 re-POST writes."""
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["100"],
            "price[]": ["15,00"],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Товара не хватает на складе" in response.text
    assert "Продать всё равно" in response.text

    confirm_response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["100"],
            "price[]": ["15,00"],
            "customer_id": "",
            "confirm": "1",
        },
    )
    assert confirm_response.status_code == 200
    assert "Продажа оформлена:" in confirm_response.text


def test_web_nav_has_sales_link(client):
    """Nav gains the sales entry: Продажи -> /sales/new."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/sales/new"' in response.text
    assert "Продажи" in response.text


def test_web_recent_sales_oob_refresh(client, stocked_product):
    """POST success refreshes the recent-sales list out-of-band."""
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert 'id="recent-sales"' in response.text
    assert 'hx-swap-oob="true"' in response.text


def test_web_customer_search_returns_rows(client, customer):
    """GET /sales/customer-search?q= returns picker rows matching the query."""
    response = client.get("/sales/customer-search", params={"q": "Анна"})
    assert response.status_code == 200
    assert customer.name in response.text


def test_web_customer_quick_create_returns_chip(client):
    """POST /sales/customer returns a chip carrying the new customer's id."""
    response = client.post(
        "/sales/customer",
        data={"name": "Мария", "surname": "Петрова", "consultant_number": ""},
    )
    assert response.status_code == 200
    assert "Мария" in response.text
    assert 'name="customer_id"' in response.text


def test_web_sale_links_selected_customer(client, stocked_product, customer):
    """A sale POSTed with a selected customer_id links the sale to that customer."""
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "customer_id": customer.id,
            "confirm": "",
        },
    )
    assert response.status_code == 200
