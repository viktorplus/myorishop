"""Phase 11 Plan 04: mobile sale wizard (Товар -> Партия -> Количество и
цена -> Корзина -> Оформить продажу).

Uses `mobile_client_factory` (Plan 01 foundation) to test `mobile_sales.router`
in isolation, without app.main registration (that happens in Plan 09).

Phase 22 Plan 02 (D-04/D-11) added the block below: the mobile customer
selector + D-11 batch-card basket-preservation fix are strict-xfail red-side
pins (22-04/22-07 land the feature), except `test_mobile_walkin` and
`test_batch_step_echoes_acc_when_supplied`, which already pass under today's
code and are pinned as plain regression guards instead — see each test's
docstring.
"""

import re

import pytest
from sqlalchemy import select

from app.core import new_id
from app.models import Batch, CatalogPrice, Operation, Sale
from app.routes import mobile_sales
from app.services.ledger import record_operation


def _client(mobile_client_factory):
    return mobile_client_factory(mobile_sales.router)


def _sale_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "sale")).all()


# ---------------------------------------------------------------------------
# Step "Товар" (product_step)
# ---------------------------------------------------------------------------


def test_product_step_unknown_code_shows_error_no_forward(mobile_client_factory, session):
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": "NOPE-404"})
    assert resp.status_code == 422
    assert "не найден" in resp.text
    # No batch/qty-price step markup should have been rendered.
    assert "Выберите партию" not in resp.text
    assert "Количество и цена" not in resp.text


def test_product_step_dictionary_source_skips_to_qty_price(mobile_client_factory, session):
    from app.services.dictionary import add_entry

    add_entry(session, code="DICT-01", name="Словарный товар")

    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": "DICT-01"})
    assert resp.status_code == 200
    assert "Количество и цена" in resp.text
    assert "Выберите партию" not in resp.text


def test_product_step_single_batch_auto_selects_and_shows_batch_step(
    mobile_client_factory, session, product, warehouse
):
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=_seed_batch(session, product, warehouse, quantity=0).id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": product.code})
    assert resp.status_code == 200
    assert "Выберите партию" in resp.text
    assert "Партия выбрана автоматически — единственная" in resp.text
    # Forward control must still be present (D-06: not silently skipped).
    assert "Далее" in resp.text


def test_product_step_multi_batch_shows_product_name(
    mobile_client_factory, session, product, warehouse
):
    """D-13: the batch step response must show the product name, not just the code."""
    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b1.id,
    )
    b2 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=4,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b2.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": product.code})
    assert resp.status_code == 200
    assert "Выберите партию" in resp.text
    assert f"<strong>{product.code}</strong> — {product.name}" in resp.text


def test_product_step_dictionary_source_shows_dictionary_name(mobile_client_factory, session):
    """D-13: the dictionary-only path shows the dictionary name on qty-price step."""
    from app.services.dictionary import add_entry

    add_entry(session, code="DICT-03", name="Словарный товар 3")

    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": "DICT-03"})
    assert resp.status_code == 200
    assert "Количество и цена" in resp.text
    assert "<strong>DICT-03</strong> — Словарный товар 3" in resp.text


def _seed_batch(session, product, warehouse, quantity=0):
    b = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=quantity)
    session.add(b)
    session.commit()
    return b


# ---------------------------------------------------------------------------
# Step "Партия" (batch_step / empty_batches)
# ---------------------------------------------------------------------------


def test_batch_step_empty_batches_blocks_forward(mobile_client_factory, session, product):
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": product.code})
    assert resp.status_code == 200
    assert "Нет партий с остатком." in resp.text
    assert "Далее" not in resp.text


def test_batch_step_tap_reselects_with_ownership_check(
    mobile_client_factory, session, product, warehouse
):
    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b1.id,
    )
    b2 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=4,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b2.id,
    )
    client = _client(mobile_client_factory)
    resp = client.get("/m/sales/step/batch", params={"batch_id": b2.id, "code": product.code})
    assert resp.status_code == 200
    assert 'class="mobile-card selected"' in resp.text
    assert "Далее" in resp.text


def test_batch_step_card_tap_still_shows_product_name(
    mobile_client_factory, session, product, warehouse
):
    """D-13: a batch-card tap re-render (GET) must still show the product name,
    sourced from the `product` row this handler already queries — no new lookup."""
    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b1.id,
    )
    b2 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=4,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b2.id,
    )
    client = _client(mobile_client_factory)
    resp = client.get("/m/sales/step/batch", params={"batch_id": b2.id, "code": product.code})
    assert resp.status_code == 200
    assert f"<strong>{product.code}</strong> — {product.name}" in resp.text


def test_batch_step_shows_per_card_warehouse_when_batches_span_two_warehouses(
    mobile_client_factory, session, product, warehouse
):
    from app.core import new_id
    from app.models import Warehouse

    warehouse2 = Warehouse(id=new_id(), name="Второй склад")
    session.add(warehouse2)
    session.commit()

    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b1.id,
    )
    b2 = _seed_batch(session, product, warehouse2, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=4,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b2.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": product.code})
    assert resp.status_code == 200
    assert f"Склад: {warehouse.name}" in resp.text
    assert "Склад: Второй склад" in resp.text


def test_qty_price_step_shows_warehouse_once_batch_picked(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/qty-price", data={"code": product.code, "batch_id": batch.id})
    assert resp.status_code == 200
    assert f"Склад: {warehouse.name}" in resp.text


def test_basket_line_shows_warehouse(mobile_client_factory, session, product, warehouse):
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post(
        "/m/sales/step/basket-add",
        data={"code": product.code, "qty": "2", "price": "9,00", "batch_id": batch.id},
    )
    assert resp.status_code == 200
    assert f"Склад: {warehouse.name}" in resp.text


def test_batch_step_foreign_batch_id_rejected(mobile_client_factory, session, product, warehouse):
    other_product_batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=2,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=other_product_batch.id,
    )
    from app.core import new_id as _new_id
    from app.models import Product

    other_product = Product(id=_new_id(), code="OTHER-01", name="Другой товар", quantity=0)
    session.add(other_product)
    session.commit()
    foreign_batch = _seed_batch(session, other_product, warehouse, quantity=5)

    client = _client(mobile_client_factory)
    resp = client.get(
        "/m/sales/step/batch", params={"batch_id": foreign_batch.id, "code": product.code}
    )
    assert resp.status_code == 200
    # The foreign batch must not be echoed as selected.
    assert 'class="mobile-card selected"' not in resp.text


# ---------------------------------------------------------------------------
# Step "Количество и цена"
# ---------------------------------------------------------------------------


def test_qty_price_step_back_returns_to_batch_step_when_batch_step_was_shown(
    mobile_client_factory, session, product, warehouse
):
    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b1.id,
    )
    b2 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=4,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b2.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": product.code})
    assert resp.status_code == 200
    assert "Выберите партию" in resp.text

    # "Далее" without picking a card (batch_id="").
    resp = client.post("/m/sales/step/qty-price", data={"code": product.code, "batch_id": ""})
    assert resp.status_code == 200
    assert 'hx-get="/m/sales/step/batch"' in resp.text
    assert 'hx-vals=\'{"back": "1"}\'' not in resp.text

    # Simulate what the "Назад" click would send (htmx closest-form GET).
    resp = client.get("/m/sales/step/batch", params={"code": product.code})
    assert resp.status_code == 200
    assert "Выберите партию" in resp.text


def test_qty_price_step_back_returns_to_product_step_for_dictionary_match(
    mobile_client_factory, session
):
    from app.services.dictionary import add_entry

    add_entry(session, code="DICT-02", name="Словарный товар 2")

    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": "DICT-02"})
    assert resp.status_code == 200
    assert "Количество и цена" in resp.text
    assert 'hx-post="/m/sales/step/product"' in resp.text
    assert 'hx-vals=\'{"back": "1"}\'' in resp.text
    assert 'hx-get="/m/sales/step/batch"' not in resp.text


def test_qty_price_step_prefills_price_from_batch(
    mobile_client_factory, session, product, warehouse
):
    # Batch.price_cents is a receipt-creation-time snapshot (D-02), not
    # something record_operation sets — assign it directly, matching what
    # the real receipt route does when a batch is created.
    batch = _seed_batch(session, product, warehouse, quantity=0)
    batch.price_cents = 1234
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=6,
        unit_cost_cents=500,
        unit_price_cents=1234,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/qty-price", data={"code": product.code, "batch_id": batch.id})
    assert resp.status_code == 200
    assert "12,34" in resp.text
    assert "Цена подставлена из партии" in resp.text
    # D-13: sourced from the `product` row this handler already queries.
    assert f"<strong>{product.code}</strong> — {product.name}" in resp.text


def test_qty_price_step_batch_hint_states_sale_only_scope(
    mobile_client_factory, session, product, warehouse
):
    """D-17/D-23: mobile batch-sourced hint states the sale-only scope."""
    batch = _seed_batch(session, product, warehouse, quantity=0)
    batch.price_cents = 1234
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=6,
        unit_cost_cents=500,
        unit_price_cents=1234,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/qty-price", data={"code": product.code, "batch_id": batch.id})
    assert resp.status_code == 200
    assert "Цена подставлена из партии" in resp.text
    assert "сохранится только в этой продаже" in resp.text


def test_qty_price_step_card_hint_states_sale_only_scope(
    mobile_client_factory, session, product, warehouse
):
    """D-17/D-23: mobile card-sourced hint (NULL-price batch falls back to
    the card, D-14) states the sale-only scope."""
    product.sale_cents = 4200
    session.commit()
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=500,
        unit_price_cents=None,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/qty-price", data={"code": product.code, "batch_id": batch.id})
    assert resp.status_code == 200
    assert "Цена подставлена из карточки товара" in resp.text
    assert "сохранится только в этой продаже" in resp.text


# --- Plan 18-08: data-ref-cents colour-cue wiring (PROD-06) -----------------


def test_qty_price_step_carries_data_ref_cents(mobile_client_factory, session, product, warehouse):
    """PROD-06/D-20: the mobile sale wizard's ONLY price input carries
    data-ref-cents = the code's CATALOG consumer_cents reference (D-05/D-08/
    D-22), independent of the batch/card fill value."""
    session.add(
        CatalogPrice(
            id=new_id(),
            code=product.code,
            year=2026,
            number=1,
            consumer_cents=1500,
            consultant_cents=900,
        )
    )
    session.commit()
    batch = _seed_batch(session, product, warehouse, quantity=0)
    batch.price_cents = 1234
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=6,
        unit_cost_cents=500,
        unit_price_cents=1234,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/qty-price", data={"code": product.code, "batch_id": batch.id})
    assert resp.status_code == 200
    assert 'data-ref-cents="1500"' in resp.text


def test_qty_price_step_no_catalog_row_shows_no_cue(
    mobile_client_factory, session, product, warehouse
):
    """D-07: no CatalogPrice row for the code -> no data-ref-cents."""
    batch = _seed_batch(session, product, warehouse, quantity=0)
    batch.price_cents = 1234
    session.commit()
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=6,
        unit_cost_cents=500,
        unit_price_cents=1234,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/qty-price", data={"code": product.code, "batch_id": batch.id})
    assert resp.status_code == 200
    assert "data-ref-cents" not in resp.text


def test_qty_price_step_dictionary_source_carries_data_ref_cents(mobile_client_factory, session):
    """The dictionary-only-match branch (skip-to-step-3, no batch) also
    threads the CATALOG reference independently of the dictionary match."""
    from app.services.dictionary import add_entry

    add_entry(session, code="DICT-01", name="Словарный товар")
    session.add(
        CatalogPrice(
            id=new_id(),
            code="DICT-01",
            year=2026,
            number=1,
            consumer_cents=2500,
            consultant_cents=1800,
        )
    )
    session.commit()

    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": "DICT-01"})
    assert resp.status_code == 200
    assert 'data-ref-cents="2500"' in resp.text


# ---------------------------------------------------------------------------
# Basket assembly + final write (register_sale parity + guardrails)
# ---------------------------------------------------------------------------


def _add_line(
    client, code, qty, price, batch_id, code_acc=(), qty_acc=(), price_acc=(), batch_acc=()
):
    """Call basket-add and return the (code_acc, qty_acc, price_acc, batch_acc)
    tuple grown by this line — mirrors what the browser's hidden fields would
    carry forward after this response."""
    resp = client.post(
        "/m/sales/step/basket-add",
        data={
            "code": code,
            "qty": qty,
            "price": price,
            "batch_id": batch_id,
            "code_acc[]": list(code_acc),
            "qty_acc[]": list(qty_acc),
            "price_acc[]": list(price_acc),
            "batch_acc[]": list(batch_acc),
        },
    )
    assert resp.status_code == 200
    return (*code_acc, code), (*qty_acc, qty), (*price_acc, price), (*batch_acc, batch_id)


def test_single_line_sale_with_auto_batch_writes_one_operation(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(client, product.code, "2", "9,00", batch.id)
    resp = client.post(
        "/m/sales",
        data={
            "code_acc[]": list(code_acc),
            "qty_acc[]": list(qty_acc),
            "price_acc[]": list(price_acc),
            "batch_acc[]": list(batch_acc),
        },
    )
    assert resp.status_code == 200
    assert "Продажа оформлена" in resp.text
    ops = _sale_ops(session)
    assert len(ops) == 1
    assert ops[0].product_id == product.id
    assert ops[0].qty_delta == -2
    assert ops[0].batch_id == batch.id


def test_two_line_basket_writes_two_operations_attributed_correctly(
    mobile_client_factory, session, product, warehouse
):
    from app.core import new_id as _new_id
    from app.models import Product

    p2 = Product(id=_new_id(), code="TEST-002", name="Второй товар", quantity=0)
    session.add(p2)
    session.commit()

    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=b1.id,
    )
    b2 = _seed_batch(session, p2, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=p2.id,
        qty_delta=4,
        unit_cost_cents=300,
        unit_price_cents=700,
        batch_id=b2.id,
    )

    client = _client(mobile_client_factory)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(client, product.code, "1", "9,00", b1.id)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(
        client, p2.code, "2", "7,00", b2.id, code_acc, qty_acc, price_acc, batch_acc
    )
    resp = client.post(
        "/m/sales",
        data={
            "code_acc[]": list(code_acc),
            "qty_acc[]": list(qty_acc),
            "price_acc[]": list(price_acc),
            "batch_acc[]": list(batch_acc),
        },
    )
    assert resp.status_code == 200
    ops = _sale_ops(session)
    assert len(ops) == 2
    by_product = {op.product_id: op for op in ops}
    assert by_product[product.id].batch_id == b1.id
    assert by_product[product.id].qty_delta == -1
    assert by_product[p2.id].batch_id == b2.id
    assert by_product[p2.id].qty_delta == -2


def test_price_below_minimum_warns_zero_writes_then_confirm_writes(
    mobile_client_factory, session, product, warehouse
):
    product.min_sale_cents = 2000
    session.commit()
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(
        client, product.code, "1", "10,00", batch.id
    )
    form = {
        "code_acc[]": list(code_acc),
        "qty_acc[]": list(qty_acc),
        "price_acc[]": list(price_acc),
        "batch_acc[]": list(batch_acc),
    }
    resp = client.post("/m/sales", data=form)
    assert resp.status_code == 200
    assert "Цена ниже минимальной" in resp.text
    assert len(_sale_ops(session)) == 0

    resp = client.post("/m/sales", data={**form, "confirm": "1"})
    assert resp.status_code == 200
    assert "Продажа оформлена" in resp.text
    assert len(_sale_ops(session)) == 1


def test_basket_add_shows_korzina_step_indicator(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post(
        "/m/sales/step/basket-add",
        data={"code": product.code, "qty": "2", "price": "9,00", "batch_id": batch.id},
    )
    assert resp.status_code == 200
    assert '<p class="mobile-step-indicator">Корзина</p>' in resp.text


def test_sales_page_prefills_code_from_query_param(mobile_client_factory, session):
    client = _client(mobile_client_factory)
    resp = client.get("/m/sales", params={"code": "TEST-001"})
    assert resp.status_code == 200
    assert 'value="TEST-001"' in resp.text


def test_oversell_warns_zero_writes_then_confirm_writes(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(client, product.code, "5", "9,00", batch.id)
    form = {
        "code_acc[]": list(code_acc),
        "qty_acc[]": list(qty_acc),
        "price_acc[]": list(price_acc),
        "batch_acc[]": list(batch_acc),
    }
    resp = client.post("/m/sales", data=form)
    assert resp.status_code == 200
    assert "Товара не хватает в партии" in resp.text
    assert len(_sale_ops(session)) == 0

    resp = client.post("/m/sales", data={**form, "confirm": "1"})
    assert resp.status_code == 200
    assert "Продажа оформлена" in resp.text
    assert len(_sale_ops(session)) == 1


# ---------------------------------------------------------------------------
# D-04: mobile customer selector (22-06/22-07) + D-11: batch-card basket fix
# ---------------------------------------------------------------------------


@pytest.mark.xfail(strict=True, reason="D-04: mobile customer selector lands in 22-06/22-07")
def test_mobile_customer_selector_renders_on_basket(
    mobile_client_factory, session, product, warehouse
):
    """22-UI-SPEC.md Interaction 9: the Корзина screen renders the 3-way
    selector above the basket cards, mirroring desktop (D-02 default:
    `existing` checked)."""
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post(
        "/m/sales/step/basket-add",
        data={"code": product.code, "qty": "2", "price": "9,00", "batch_id": batch.id},
    )
    assert resp.status_code == 200
    body = resp.text
    assert 'id="m-customer-header"' in body
    assert 'name="customer_mode" value="new"' in body
    assert 'name="customer_mode" value="existing"' in body
    assert 'name="customer_mode" value="anon"' in body
    existing_radio = re.search(r'name="customer_mode" value="existing"[^>]*checked', body)
    assert existing_radio is not None

    selector_index = body.index('id="m-customer-header"')
    first_card_index = body.index('class="mobile-card"')
    assert selector_index < first_card_index


@pytest.mark.xfail(strict=True, reason="D-04: mobile customer selector lands in 22-06/22-07")
def test_mobile_links_customer(mobile_client_factory, session, product, warehouse, customer):
    """Retires the `customer_id=""` hardcode at mobile_sales.py:346."""
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(client, product.code, "2", "9,00", batch.id)
    resp = client.post(
        "/m/sales",
        data={
            "code_acc[]": list(code_acc),
            "qty_acc[]": list(qty_acc),
            "price_acc[]": list(price_acc),
            "batch_acc[]": list(batch_acc),
            "customer_id": customer.id,
        },
    )
    assert resp.status_code == 200
    sale = session.scalars(select(Sale).order_by(Sale.created_at.desc())).first()
    assert sale is not None
    assert sale.customer_id == customer.id


def test_mobile_walkin(mobile_client_factory, session, product, warehouse):
    """D-05: the mobile walk-in path (no customer_id posted) must not regress.

    Deviation from the plan's xfail grouping (Rule 1 — test-suite-green
    invariant takes priority): unlike its sibling D-04 tests, this assertion
    ALREADY holds under today's code — mobile_sales.py:346 hardcodes
    `customer_id=""`, which register_sale's `customer_id or None`
    (services/sales.py:254) already coerces to NULL regardless of what is
    posted. Marking an already-passing assertion `xfail(strict=True)` would
    XPASS and break this plan's "the full suite stays green" truth, so it is
    pinned as a plain regression guard instead — it must still be passing
    once 22-06/22-07 wire the real selector in.
    """
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(client, product.code, "2", "9,00", batch.id)
    resp = client.post(
        "/m/sales",
        data={
            "code_acc[]": list(code_acc),
            "qty_acc[]": list(qty_acc),
            "price_acc[]": list(price_acc),
            "batch_acc[]": list(batch_acc),
        },
    )
    assert resp.status_code == 200
    sale = session.scalars(select(Sale).order_by(Sale.created_at.desc())).first()
    assert sale is not None
    assert sale.customer_id is None


@pytest.mark.xfail(strict=True, reason="D-04: mobile customer selector lands in 22-06/22-07")
def test_mobile_selector_swap_acc_survives(mobile_client_factory, session, product, warehouse):
    """22-UI-SPEC.md Interaction 9: the mode radio MUST target
    `#m-customer-header`, never `#wizard-step` — swapping `#wizard-step`
    would wipe the basket's `code_acc[]` hidden inputs."""
    batch = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=500,
        unit_price_cents=900,
        batch_id=batch.id,
    )
    client = _client(mobile_client_factory)
    code_acc, qty_acc, price_acc, batch_acc = _add_line(client, product.code, "2", "9,00", batch.id)
    resp = client.get(
        "/m/sales/customer-mode",
        params={
            "customer_mode": "new",
            "code_acc[]": list(code_acc),
            "qty_acc[]": list(qty_acc),
            "price_acc[]": list(price_acc),
            "batch_acc[]": list(batch_acc),
        },
    )
    assert resp.status_code == 200
    assert 'id="m-customer-header"' in resp.text
    assert 'id="wizard-step"' not in resp.text


@pytest.mark.xfail(strict=True, reason="D-11: batch-card hx-include lands in 22-07")
def test_batch_card_preserves_basket(mobile_client_factory, session, product, warehouse):
    """22-RESEARCH.md Pitfall 3 (empirically-verified defect): the batch-card
    tap must carry `hx-include="closest form"` or the accumulated basket's
    `code_acc[]` hidden inputs are dropped from the GET request. This suite
    has no browser runtime, so only the markup half of the fix is provable
    here (see `test_batch_step_echoes_acc_when_supplied` for the endpoint's
    half of the contract)."""
    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b1.id,
    )
    b2 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=4,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b2.id,
    )
    client = _client(mobile_client_factory)
    resp = client.post("/m/sales/step/product", data={"code": product.code})
    assert resp.status_code == 200
    card_match = re.search(r'<button[^>]*hx-get="/m/sales/step/batch"[^>]*>', resp.text)
    assert card_match is not None, "expected a batch-card button targeting /m/sales/step/batch"
    assert 'hx-include="closest form"' in card_match.group(0)


def test_batch_step_echoes_acc_when_supplied(mobile_client_factory, session, product, warehouse):
    """Pins the endpoint half of the D-11 fix: `GET /m/sales/step/batch`
    already declares the 4 `*_acc[]` Query params and its template already
    re-echoes them as hidden inputs — this must keep working so a later
    refactor cannot drop it. May already pass today; that is expected."""
    b1 = _seed_batch(session, product, warehouse, quantity=0)
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=3,
        unit_cost_cents=100,
        unit_price_cents=200,
        batch_id=b1.id,
    )
    client = _client(mobile_client_factory)
    resp = client.get(
        "/m/sales/step/batch",
        params={
            "code": product.code,
            "code_acc[]": ["OTHER-01"],
            "qty_acc[]": ["1"],
            "price_acc[]": ["5,00"],
            "batch_acc[]": ["some-batch-id"],
        },
    )
    assert resp.status_code == 200
    assert '<input type="hidden" name="code_acc[]" value="OTHER-01">' in resp.text
    assert '<input type="hidden" name="qty_acc[]" value="1">' in resp.text
    assert '<input type="hidden" name="price_acc[]" value="5,00">' in resp.text
    assert '<input type="hidden" name="batch_acc[]" value="some-batch-id">' in resp.text
