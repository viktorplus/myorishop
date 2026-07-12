"""SAL-01..05 executable contract for the sale basket slice.

Interface contract for Plans 04-02 (basket transaction), 04-03 (oversell
warn/confirm), and 04-05 (customer picker). Module path and signatures
below are fixed — implement against them, do not rename.

Phase 9 (LOT-02/D-04/D-09): every sale line now REQUIRES a picked batch.
`register_sale` gains a 4th `batch_ids` array, aligned to code[]/qty[]/price[];
a line with no resolvable/owned batch is rejected with «Выберите партию.»
and the per-batch oversell warning is scoped to the picked batch's remaining
quantity (not the product total). Service tests fetch the seeded batch id via
open_batches so the parallel array stays aligned.

Naming convention (used by -k filters): route/e2e tests are prefixed
test_web_; everything else is service level.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import Batch, Operation, Product
from app.services import catalog
from app.services.batches import open_batches
from app.services.ledger import compute_stock, record_operation
from app.services.sales import lookup_prefill, recent_sales, register_sale  # noqa: F401


def _sale_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "sale")).all()


def _only_batch(session, product):
    """The single open batch id seeded by the stocked_product / batch fixtures."""
    return open_batches(session, product.id)[0].id


def _two_batches(session, product, warehouse, qty_a, qty_b):
    """Seed two ledger-backed batches (qty_a, qty_b) for one product (D-09 tests)."""
    a = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    b = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add_all([a, b])
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=qty_a,
        unit_price_cents=1000, batch_id=a.id,
    )
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=qty_b,
        unit_price_cents=1000, batch_id=b.id,
    )
    return a, b


def _batch(session, product, warehouse, qty, expiry=None, price=None, comment=None):
    """Seed one ledger-backed batch with the given readable attributes."""
    b = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=0,
        expiry=expiry,
        price_cents=price,
        comment=comment,
    )
    session.add(b)
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=qty,
        unit_price_cents=price if price is not None else 1000, batch_id=b.id,
    )
    return b


# --- Service level ---


def test_stock_decrements_for_basket_sale(session, stocked_product):
    """SAL-01: a 2-line basket writes 2 sale ops; stock drops by summed qty."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code, stocked_product.code],
        qtys=["2", "3"],
        prices=["15,00", "14,00"],
        batch_ids=[bid, bid],
    )
    assert errors == {}
    assert result

    ops = _sale_ops(session)
    assert len(ops) == 2
    assert all(op.qty_delta < 0 for op in ops)
    assert stocked_product.quantity == 8 - 5
    assert compute_stock(session, stocked_product.id) == 8 - 5


def test_missing_batch_id_rejected_zero_writes(session, stocked_product):
    """LOT-02/D-04: a line with no picked batch is rejected; 0 writes."""
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[""],
    )
    assert result is None
    assert errors.get("batch-0") == "Выберите партию."
    assert _sale_ops(session) == []


def test_foreign_batch_id_rejected_zero_writes(session, stocked_product, product, warehouse):
    """T-09-08: a batch belonging to another product is rejected; 0 writes."""
    other = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add(other)
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=3,
        unit_price_cents=1000, batch_id=other.id,
    )
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[other.id],
    )
    assert result is None
    assert errors.get("batch-0") == "Выберите партию."
    assert _sale_ops(session) == []


def test_committed_sale_decrements_batch_quantity(session, stocked_product):
    """D-11: a committed sale line decrements the picked Batch.quantity too."""
    bid = _only_batch(session, stocked_product)
    batch_before = session.get(Batch, bid)
    assert batch_before.quantity == 8
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["3"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    session.refresh(batch_before)
    assert batch_before.quantity == 8 - 3
    assert stocked_product.quantity == 8 - 3


def test_per_batch_oversell_scopes_to_picked_batch(session, product, warehouse):
    """Criterion 4/D-09: overselling batch A ignores batch B's stock."""
    a, b = _two_batches(session, product, warehouse, qty_a=2, qty_b=10)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[product.code],
        qtys=["5"],
        prices=["10,00"],
        batch_ids=[a.id],
    )
    assert errors == {}
    oversell = result.get("oversell")
    assert oversell
    assert oversell[0]["available"] == 2
    assert oversell[0]["requested"] == 5
    assert _sale_ops(session) == []


def test_per_batch_oversell_same_batch_two_lines_aggregated(session, product, warehouse):
    """Pitfall 8: the SAME batch on two lines is summed before the check."""
    a, _ = _two_batches(session, product, warehouse, qty_a=6, qty_b=10)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[product.code, product.code],
        qtys=["4", "4"],
        prices=["10,00", "10,00"],
        batch_ids=[a.id, a.id],
    )
    assert errors == {}
    oversell = result.get("oversell")
    assert oversell
    assert len(oversell) == 1
    assert oversell[0]["available"] == 6
    assert oversell[0]["requested"] == 8
    assert _sale_ops(session) == []


def test_empty_basket_returns_error(session):
    """SAL-01: zero lines cannot be finalized; 0 writes (D-03)."""
    result, errors = register_sale(
        session, customer_id=None, codes=[], qtys=[], prices=[], batch_ids=[]
    )
    assert result is None
    assert "Добавьте хотя бы одну строку, чтобы оформить продажу." in errors.values()
    assert _sale_ops(session) == []


def test_one_transaction_all_or_nothing(session, stocked_product):
    """SAL-01: an unknown code on any line aborts the WHOLE basket (one transaction)."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code, "UNKNOWN-CODE"],
        qtys=["1", "1"],
        prices=["15,00", "15,00"],
        batch_ids=[bid, bid],
    )
    assert result is None
    assert errors
    assert _sale_ops(session) == []


def test_price_override_uses_entered_price(session, stocked_product):
    """SAL-02: entered price overrides the card sale_cents; snapshot = entered price."""
    stocked_product.sale_cents = 1500
    session.commit()
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["20,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    op = _sale_ops(session)[0]
    assert op.unit_price_cents == 2000


def test_customer_link_sets_header_customer_id(session, stocked_product, customer):
    """SAL-03: a sale with customer_id set links the header to that customer."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=customer.id,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result["header"].customer_id == customer.id


def test_customer_link_walkin_customer_id_null(session, stocked_product):
    """SAL-03/D-04: a walk-in sale (no customer) is valid; header.customer_id is NULL."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id="",
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result["header"].customer_id is None


def test_snapshot_frozen_after_price_change(session, stocked_product):
    """SAL-05: unit_cost/unit_price freeze at write; later card edits don't touch the op."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[bid],
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


def test_null_cost_allowed_sale_succeeds(session, product, warehouse):
    """SAL-05/D-12: NULL card cost -> op cost NULL, sale is NOT blocked."""
    batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add(batch)
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=5, batch_id=batch.id
    )
    assert product.cost_cents is None

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[product.code],
        qtys=["1"],
        prices=["10,00"],
        batch_ids=[batch.id],
    )
    assert errors == {}
    op = _sale_ops(session)[0]
    assert op.unit_cost_cents is None


def test_null_cost_empty_price_rejected(session, stocked_product):
    """SAL-05/D-12: an empty per-line price is rejected; 0 writes."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=[""],
        batch_ids=[bid],
    )
    assert result is None
    assert "Укажите цену продажи." in errors.values()
    assert _sale_ops(session) == []


def test_negative_price_rejected_without_min_sale_configured(session, stocked_product):
    """CR-01/gap-fix: a negative price is rejected even when min_sale_cents is unset."""
    assert stocked_product.min_sale_cents is None
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["-5,00"],
        batch_ids=[bid],
    )
    assert result is None
    assert catalog.PRICE_ERROR in errors.values()
    assert _sale_ops(session) == []


def test_negative_price_rejected_with_min_sale_configured(session, stocked_product):
    """CR-01/gap-fix: the negative-price guard fires independently of below_minimum."""
    stocked_product.min_sale_cents = 2000
    session.commit()
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["-5,00"],
        batch_ids=[bid],
    )
    assert result is None
    assert catalog.PRICE_ERROR in errors.values()
    assert _sale_ops(session) == []


def test_web_sale_negative_price_rejected(client, session, stocked_product):
    """CR-01/gap-fix: POST /sales with a negative price[] returns 422, 0 writes."""
    bid = _only_batch(session, stocked_product)
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["-5,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 422
    assert catalog.PRICE_ERROR in response.text
    assert _sale_ops(session) == []


def test_oversell_blocks_without_confirm(session, stocked_product):
    """SAL-04: requesting more than stock with no confirm -> oversell signal, 0 writes."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["100"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result.get("oversell")
    assert result["oversell"][0]["available"] == 8
    assert _sale_ops(session) == []


def test_oversell_confirm_writes_negative_stock(session, stocked_product):
    """SAL-04/D-09: confirm=1 skips the block; sale writes and stock may go negative."""
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["100"],
        prices=["15,00"],
        batch_ids=[bid],
        confirm="1",
    )
    assert errors == {}
    assert not result.get("oversell")
    assert stocked_product.quantity < 0


def test_oversell_aggregates_duplicate_lines(session, stocked_product):
    """Pitfall 6/8: 2 lines of the SAME batch are summed before the stock check.

    stocked_product has 8 in one batch; 5 + 5 = 10 > 8 -> oversells even though
    each individual line (5) would pass alone.
    """
    bid = _only_batch(session, stocked_product)
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code, stocked_product.code],
        qtys=["5", "5"],
        prices=["15,00", "15,00"],
        batch_ids=[bid, bid],
    )
    assert errors == {}
    assert result.get("oversell")
    assert _sale_ops(session) == []


def test_below_minimum_blocks_without_confirm(session, stocked_product):
    """PRICE-01/D-08/D-09: entered price below min_sale_cents -> warn, 0 writes."""
    stocked_product.min_sale_cents = 2000
    session.commit()
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result.get("below_minimum")
    assert _sale_ops(session) == []


def test_below_minimum_confirm_writes(session, stocked_product):
    """PRICE-01/D-09: confirm=1 skips the block; sale writes at the entered price."""
    stocked_product.min_sale_cents = 2000
    session.commit()
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[bid],
        confirm="1",
    )
    assert errors == {}
    assert not result.get("below_minimum")
    op = _sale_ops(session)[0]
    assert op.unit_price_cents == 1500


def test_below_minimum_boundary_equal_price_passes_silently(session, stocked_product):
    """D-10: a price exactly equal to the minimum passes silently (strict <)."""
    stocked_product.min_sale_cents = 1500
    session.commit()
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert not result.get("below_minimum")
    assert len(_sale_ops(session)) == 1


def test_min_sale_unset_never_warns_even_at_zero_entered_price(session, stocked_product):
    """D-06/success criterion 4: no min_sale_cents configured -> never warns, even at 0."""
    assert stocked_product.min_sale_cents is None
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["1"],
        prices=["0,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert not result.get("below_minimum")


def test_oversell_and_below_minimum_both_reported_together(session, stocked_product):
    """D-11/Pitfall 2: a basket tripping BOTH checks reports both in one call."""
    stocked_product.min_sale_cents = 2000
    session.commit()
    bid = _only_batch(session, stocked_product)

    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["100"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result.get("oversell")
    assert result.get("below_minimum")
    assert _sale_ops(session) == []


# --- Web slice (routes + templates) ---


def test_web_sale_page_renders_form(client):
    """/sales/new: RU title «Продажа» + the basket table."""
    response = client.get("/sales/new")
    assert response.status_code == 200
    assert "Продажа" in response.text
    assert 'id="basket-rows"' in response.text
    assert "Оформить продажу" in response.text


def test_web_sale_post_success_shows_confirmation(client, session, stocked_product):
    """D-02: success -> «Продажа оформлена:» + 200 partial (never a full page)."""
    bid = _only_batch(session, stocked_product)
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
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
        data={
            "code[]": [],
            "qty[]": [],
            "price[]": [],
            "batch_id[]": [],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 422
    assert "Добавьте хотя бы одну строку, чтобы оформить продажу." in response.text


def test_web_sale_oversell_shows_warning_and_confirm_writes(client, session, stocked_product):
    """SAL-04: oversell POST (no confirm) warns + writes 0; confirm=1 re-POST writes."""
    bid = _only_batch(session, stocked_product)
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["100"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Товара не хватает в партии" in response.text
    assert "Продать всё равно" in response.text

    confirm_response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["100"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "1",
        },
    )
    assert confirm_response.status_code == 200
    assert "Продажа оформлена:" in confirm_response.text


def test_web_sale_below_minimum_shows_warning_and_confirm_writes(client, session, stocked_product):
    """PRICE-01: below-minimum POST (no confirm) warns + writes 0; confirm=1 re-POST writes."""
    stocked_product.min_sale_cents = 2000
    session.commit()
    bid = _only_batch(session, stocked_product)

    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Цена ниже минимальной" in response.text
    assert "Продать всё равно" in response.text

    confirm_response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "1",
        },
    )
    assert confirm_response.status_code == 200
    assert "Продажа оформлена:" in confirm_response.text


def test_web_sale_both_warnings_stack_and_single_confirm_resolves_both(
    client, session, stocked_product
):
    """D-11/Pitfall 2: a basket failing both checks shows both blocks; one confirm resolves both."""
    stocked_product.min_sale_cents = 2000
    session.commit()
    bid = _only_batch(session, stocked_product)

    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["100"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Товара не хватает в партии" in response.text
    assert "Цена ниже минимальной" in response.text

    confirm_response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["100"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
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


def test_web_recent_sales_oob_refresh(client, session, stocked_product):
    """POST success refreshes the recent-sales list out-of-band."""
    bid = _only_batch(session, stocked_product)
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
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


def test_web_sale_links_selected_customer(client, session, stocked_product, customer):
    """A sale POSTed with a selected customer_id links the sale to that customer."""
    bid = _only_batch(session, stocked_product)
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": customer.id,
            "confirm": "",
        },
    )
    assert response.status_code == 200


# --- Batch picker slice (LOT-02/D-04..D-07, Phase 9) ---


def test_web_sale_lookup_renders_batch_picker_columns_in_expiry_order(
    client, session, product, warehouse
):
    """LOT-02/D-07: /sales/lookup for a 2-batch product shows the four picker
    columns, no warehouse column, batches earliest-expiry-first."""
    _batch(session, product, warehouse, qty=3, expiry="2026-12-01", comment="Поздняя")
    _batch(session, product, warehouse, qty=5, expiry="2026-01-15", comment="Ранняя")

    response = client.get(
        "/sales/lookup", params={"code[]": product.code, "name[]": "", "price[]": ""}
    )
    assert response.status_code == 200
    text = response.text
    assert "Цена" in text
    assert "Срок годности" in text
    assert "Остаток" in text
    assert "Комментарий" in text
    assert "Склад" not in text  # D-04: no warehouse column in the picker
    # D-07: earliest expiry first (NULL last), so «Ранняя» precedes «Поздняя».
    assert text.index("Ранняя") < text.index("Поздняя")
    assert "15.01.2026" in text  # ru_date renders the ISO expiry


def test_web_sale_lookup_autoselect_single_batch(client, session, product, warehouse):
    """D-06: a single-batch product auto-selects — pre-checked, highlighted, noted."""
    b = _batch(session, product, warehouse, qty=4, expiry="2026-06-01", price=999)

    response = client.get(
        "/sales/lookup", params={"code[]": product.code, "name[]": "", "price[]": ""}
    )
    assert response.status_code == 200
    text = response.text
    assert "Партия выбрана автоматически — единственная" in text
    assert b.id in text
    assert "checked" in text
    assert 'class="selected-batch"' in text


def test_web_sale_lookup_empty_state_when_no_open_batches(client, session, product):
    """A product with zero open batches shows «Нет партий с остатком.»."""
    response = client.get(
        "/sales/lookup", params={"code[]": product.code, "name[]": "", "price[]": ""}
    )
    assert response.status_code == 200
    assert "Нет партий с остатком." in response.text


def test_web_sale_batch_pick_selects_and_fills_batch_price(client, session, product, warehouse):
    """/sales/batch-pick re-renders the wrapper with the selection + oob batch price."""
    _batch(session, product, warehouse, qty=3, expiry="2026-01-15", price=1234)
    b2 = _batch(session, product, warehouse, qty=5, expiry="2026-12-01", price=5678)

    response = client.get(
        "/sales/batch-pick", params={"row": "", "batch_id": b2.id, "code": product.code}
    )
    assert response.status_code == 200
    text = response.text
    assert b2.id in text  # hidden batch_id[] value set to the pick
    assert 'class="selected-batch"' in text
    assert 'hx-swap-oob="true"' in text  # oob price fill
    assert "56,78" in text  # the picked batch's price
    assert "Цена подставлена из партии" in text


def test_web_sale_batch_pick_legacy_null_price_falls_back_to_card(
    client, session, product, warehouse
):
    """D-14: picking a NULL-price legacy batch fills the card sale_cents instead."""
    product.sale_cents = 4200
    session.commit()
    b = _batch(session, product, warehouse, qty=3, price=None)

    response = client.get(
        "/sales/batch-pick", params={"row": "", "batch_id": b.id, "code": product.code}
    )
    assert response.status_code == 200
    text = response.text
    assert "42,00" in text
    assert "Цена подставлена из карточки товара" in text


def test_web_sale_batch_drift_attribution_holds(client, session, warehouse):
    """Pitfall 2: each line's op stays attributed to its OWN picked batch."""
    p1 = Product(id=new_id(), code="DRIFT-1", name="Товар один", quantity=0)
    p2 = Product(id=new_id(), code="DRIFT-2", name="Товар два", quantity=0)
    session.add_all([p1, p2])
    session.commit()
    b1 = _batch(session, p1, warehouse, qty=5, price=1000)
    b2 = _batch(session, p2, warehouse, qty=5, price=2000)

    response = client.post(
        "/sales",
        data={
            "code[]": [p1.code, p2.code],
            "qty[]": ["1", "1"],
            "price[]": ["10,00", "20,00"],
            "batch_id[]": [b1.id, b2.id],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    ops = {op.product_id: op for op in _sale_ops(session)}
    assert ops[p1.id].batch_id == b1.id
    assert ops[p2.id].batch_id == b2.id


def test_web_sale_short_batch_array_degrades_to_missing_not_drift(
    client, session, warehouse
):
    """Pitfall 2: a short batch_id[] pads to «no batch» for the trailing line,
    never shifting an earlier pick onto it."""
    p1 = Product(id=new_id(), code="PAD-1", name="Товар один", quantity=0)
    p2 = Product(id=new_id(), code="PAD-2", name="Товар два", quantity=0)
    session.add_all([p1, p2])
    session.commit()
    b1 = _batch(session, p1, warehouse, qty=5, price=1000)
    _batch(session, p2, warehouse, qty=5, price=2000)

    response = client.post(
        "/sales",
        data={
            "code[]": [p1.code, p2.code],
            "qty[]": ["1", "1"],
            "price[]": ["10,00", "20,00"],
            "batch_id[]": [b1.id],  # only one id for two lines
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 422
    assert "Выберите партию." in response.text
    assert _sale_ops(session) == []


def test_web_sale_422_re_echoes_picked_batch(client, session, stocked_product):
    """Pitfall 3: a 422 (bad qty) re-render keeps the picked batch hidden value."""
    bid = _only_batch(session, stocked_product)
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["abc"],
            "price[]": ["15,00"],
            "batch_id[]": [bid],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 422
    assert bid in response.text  # the pick survives the re-render


def test_web_sale_oversell_body_is_batch_scoped(client, session, product, warehouse):
    """D-09: the oversell warning reads «в партии {available}» for the picked
    batch — batch B's stock never widens batch A's available."""
    a, _b = _two_batches(session, product, warehouse, qty_a=2, qty_b=10)

    response = client.post(
        "/sales",
        data={
            "code[]": [product.code],
            "qty[]": ["5"],
            "price[]": ["10,00"],
            "batch_id[]": [a.id],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 200
    assert "Товара не хватает в партии" in response.text
    assert f"{product.name}: в партии 2, продаёте 5." in response.text
    assert _sale_ops(session) == []


def test_web_sale_missing_batch_pick_returns_422(client, session, stocked_product):
    """LOT-02: submitting a line with no picked batch is a 422 «Выберите партию.»."""
    response = client.post(
        "/sales",
        data={
            "code[]": [stocked_product.code],
            "qty[]": ["1"],
            "price[]": ["15,00"],
            "batch_id[]": [""],
            "customer_id": "",
            "confirm": "",
        },
    )
    assert response.status_code == 422
    assert "Выберите партию." in response.text
    assert _sale_ops(session) == []
