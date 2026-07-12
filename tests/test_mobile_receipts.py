"""Phase 11 Plan 03: mobile Приход wizard tests (UI-01).

Uses `mobile_client_factory` (Phase 11 Plan 01 foundation) to test
app/routes/mobile_receipts.py in isolation, without app.main registration.

Naming: "step_batch" selects the Task 1 slice (steps 1-2 — route skeleton +
Товар/Партия screens); the remaining tests cover steps 3-4 (Количество/Цены,
Подтверждение) and the final write, added in Task 2.
"""

from app.core import new_id
from app.models import Batch
from app.routes import mobile_receipts

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
