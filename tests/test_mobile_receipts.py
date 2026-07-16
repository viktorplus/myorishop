"""Phase 11 Plan 03: mobile Приход wizard tests (UI-01).

Uses `mobile_client_factory` (Phase 11 Plan 01 foundation) to test
app/routes/mobile_receipts.py in isolation, without app.main registration.

Naming: "step_batch" selects the Task 1 slice (steps 1-2 — route skeleton +
Товар/Партия screens); the remaining tests cover steps 3-4 (Количество/Цены,
Подтверждение) and the final write, added in Task 2.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import Batch, CatalogPrice, Operation
from app.routes import mobile_receipts
from app.services.dictionary import add_entry

# --- Task 1: steps 1-2 (Товар, Партия chooser) ---


def test_web_step_batch_zero_warehouses_blocks_step_one(mobile_client_factory, session):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.get("/m/receipts")
    assert response.status_code == 200
    assert (
        "Нет активных складов. Чтобы оформить приход, сначала создайте склад."
        in response.text
    )
    assert 'href="/warehouses"' in response.text
    assert "hx-post" not in response.text  # no forward control at all


def test_web_step_batch_page_renders_step_one(mobile_client_factory, session, warehouse):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.get("/m/receipts")
    assert response.status_code == 200
    assert "Шаг 1 из 4" in response.text
    assert f'value="{warehouse.id}"' in response.text
    assert 'name="code"' in response.text
    assert 'hx-post="/m/receipts/step/batch"' in response.text


def test_web_step_batch_new_code_shows_new_batch_only_and_name_input(
    mobile_client_factory, session, warehouse
):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": "9999", "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert "Шаг 2 из 4" in response.text
    assert "Новая партия" in response.text
    assert "Пополнить партию" not in response.text
    # unknown code everywhere -> operator must type a name (D-05 auto-create)
    assert "Название товара" in response.text
    assert 'name="name"' in response.text


def test_web_step_batch_existing_product_lists_open_batch_and_carries_name(
    mobile_client_factory, session, product, warehouse
):
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=3,
        price_cents=1250,
    )
    session.add(batch)
    session.commit()

    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": product.code, "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert "Пополнить партию" in response.text
    assert "Новая партия" in response.text
    # resolved name carried forward as a hidden field, not a visible input
    assert f'value="{product.name}"' in response.text
    assert "Название товара" not in response.text


def test_web_step_batch_zero_warehouses_defensive_block(mobile_client_factory, session):
    """Race condition: warehouse deactivated between step 1 GET and step 2 POST."""
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": "9999", "warehouse_id": "stale-id"}
    )
    assert response.status_code == 200
    assert (
        "Нет активных складов. Чтобы оформить приход, сначала создайте склад."
        in response.text
    )
    assert "Далее" not in response.text


def test_web_step_batch_existing_product_forwards_cost_price(
    mobile_client_factory, session, product, warehouse
):
    """D-06: an existing Product's cost pre-fills as a hidden field; unset
    sale renders empty (PD-8 shape, not literal "None")."""
    product.cost_cents = 1250
    session.commit()

    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": product.code, "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert '<input type="hidden" name="cost" value="12,50">' in response.text
    assert '<input type="hidden" name="sale" value="">' in response.text


def test_web_step_batch_catalog_source_forwards_cost_and_sale(
    mobile_client_factory, session, warehouse
):
    """D-01: a code unknown to Product but present in CatalogPrice forwards
    cost/sale from the catalog source — sale is filled from the consumer
    price (ПЦ) (D-02 superseded, mobile layer). The catalog price field
    itself is removed from the receipt slice (Pitfall 1)."""
    session.add(
        CatalogPrice(
            id=new_id(),
            code="5555",
            year=2026,
            number=1,
            consumer_cents=1500,
            consultant_cents=900,
        )
    )
    session.commit()

    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": "5555", "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert '<input type="hidden" name="cost" value="9,00">' in response.text
    assert '<input type="hidden" name="sale" value="15,00">' in response.text


def test_web_step_batch_unknown_code_forwards_empty_prices(
    mobile_client_factory, session, warehouse
):
    """Code unknown everywhere -> both hidden price inputs render empty."""
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": "no-such-code", "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert '<input type="hidden" name="cost" value="">' in response.text
    assert '<input type="hidden" name="sale" value="">' in response.text


# --- Task 2: steps 3-4 (Количество/Цены, Подтверждение) + final write ---


def test_web_step_details_shows_new_batch_fields_when_new(mobile_client_factory, session):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/details",
        data={"code": "9999", "warehouse_id": "wh-1", "name": "Крем", "batch_choice": "new"},
    )
    assert response.status_code == 200
    assert "Шаг 3 из 4" in response.text
    assert 'name="qty"' in response.text
    assert 'name="expiry"' in response.text
    assert 'name="location"' in response.text
    assert "стеллаж А3" in response.text  # placeholder, verbatim from desktop


def test_web_step_details_shows_visible_code_and_name_readout(mobile_client_factory, session):
    """D-12: step 3 always shows a bolded code, plus name when known."""
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/details",
        data={"code": "9999", "warehouse_id": "wh-1", "name": "Крем", "batch_choice": "new"},
    )
    assert response.status_code == 200
    assert "<strong>9999</strong> — Крем" in response.text


def test_web_step_details_readout_omits_dash_when_name_empty(mobile_client_factory, session):
    """D-12: an unknown code with no name yet renders the code alone, with no
    trailing em-dash."""
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/details",
        data={"code": "9999", "warehouse_id": "wh-1", "name": "", "batch_choice": "new"},
    )
    assert response.status_code == 200
    assert "<strong>9999</strong>" in response.text
    assert "—" not in response.text


def test_web_step_details_omits_new_batch_fields_for_topup(
    mobile_client_factory, session, product, warehouse
):
    batch = Batch(
        id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=2
    )
    session.add(batch)
    session.commit()

    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/details",
        data={
            "code": product.code,
            "warehouse_id": warehouse.id,
            "name": product.name,
            "batch_choice": batch.id,
        },
    )
    assert response.status_code == 200
    assert 'name="qty"' in response.text
    assert 'name="expiry"' not in response.text
    assert 'name="location"' not in response.text
    assert 'name="comment"' not in response.text


def test_web_step_confirm_renders_summary(mobile_client_factory, session):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/confirm",
        data={
            "code": "9999",
            "warehouse_id": "wh-1",
            "name": "Крем",
            "batch_choice": "new",
            "qty": "5",
            "cost": "",
            "sale": "",
        },
    )
    assert response.status_code == 200
    assert "Шаг 4 из 4" in response.text
    assert "Подтверждение" in response.text
    assert "Сохранить приход" in response.text
    assert "9999" in response.text
    assert "Крем" in response.text


def test_web_receipt_create_new_batch_happy_path(mobile_client_factory, session, warehouse):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts",
        data={
            "code": "9999",
            "name": "Губная помада",
            "qty": "5",
            "cost": "10",
            "sale": "12,50",
            "warehouse_id": warehouse.id,
            "batch_choice": "new",
        },
    )
    assert response.status_code == 200
    assert "Приход сохранён: Губная помада — 5 шт." in response.text
    assert "Добавить ещё" in response.text
    assert "На главную" in response.text

    ops = session.scalars(select(Operation).where(Operation.type == "receipt")).all()
    assert len(ops) == 1
    assert ops[0].qty_delta == 5


def test_web_receipt_create_topup_happy_path(
    mobile_client_factory, session, product, warehouse
):
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=2,
        price_cents=1000,
    )
    session.add(batch)
    session.commit()

    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts",
        data={
            "code": product.code,
            "name": product.name,
            "qty": "3",
            "cost": "",
            "sale": "",
            "warehouse_id": warehouse.id,
            "batch_choice": batch.id,
        },
    )
    assert response.status_code == 200
    assert f"Приход сохранён: {product.name} — 3 шт." in response.text

    session.refresh(batch)
    assert batch.quantity == 5  # 2 + 3, same batch topped up
    assert batch.price_cents == 1000  # frozen — never rewritten by a top-up


# --- Task 2 (13-03): ?code= pre-fill + step 2's own hx-get "Назад" ---


def test_step_batch_back_no_longer_a_plain_link(mobile_client_factory, session, warehouse):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": "9999", "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert '<a class="button secondary" href="/m/receipts"' not in response.text


def test_step_batch_back_is_hx_get_to_receipts(mobile_client_factory, session, warehouse):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": "9999", "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert 'hx-get="/m/receipts"' in response.text


def test_get_receipts_hx_request_returns_bare_fragment_with_code(
    mobile_client_factory, session, warehouse
):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.get(
        "/m/receipts", params={"code": "TEST-001"}, headers={"HX-Request": "true"}
    )
    assert response.status_code == 200
    assert "<html" not in response.text
    assert 'value="TEST-001"' in response.text


def test_get_receipts_plain_still_renders_full_page_with_code(
    mobile_client_factory, session, warehouse
):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.get("/m/receipts", params={"code": "TEST-001"})
    assert response.status_code == 200
    assert "<html" in response.text
    assert 'value="TEST-001"' in response.text


# --- Task 3 (13-03): visible code/name/warehouse header on step 2 (UI-02) ---


def test_step_batch_shows_code_name_and_warehouse_header(
    mobile_client_factory, session, product, warehouse
):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": product.code, "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert f"<strong>{product.code}</strong> — {product.name}" in response.text
    assert f"Склад: {warehouse.name}" in response.text


def test_step_batch_unknown_code_still_shows_warehouse_header(
    mobile_client_factory, session, warehouse
):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts/step/batch", data={"code": "9999", "warehouse_id": warehouse.id}
    )
    assert response.status_code == 200
    assert f"Склад: {warehouse.name}" in response.text
    assert "<strong>9999</strong>" in response.text
    assert "<strong>9999</strong> —" not in response.text


def test_web_receipt_create_validation_error_writes_zero_rows(
    mobile_client_factory, session, product, warehouse
):
    client = mobile_client_factory(mobile_receipts.router)
    response = client.post(
        "/m/receipts",
        data={
            "code": product.code,
            "name": product.name,
            "qty": "0",  # invalid — must be a positive int
            "cost": "",
            "sale": "",
            "warehouse_id": warehouse.id,
            "batch_choice": "new",
        },
    )
    assert response.status_code == 422
    assert "Подтверждение" in response.text
    assert "Укажите количество — целое число больше нуля." in response.text
    assert session.scalars(select(Operation)).all() == []
