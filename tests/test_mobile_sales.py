"""Phase 11 Plan 04: mobile sale wizard (Товар -> Партия -> Количество и
цена -> Корзина -> Оформить продажу).

Uses `mobile_client_factory` (Plan 01 foundation) to test `mobile_sales.router`
in isolation, without app.main registration (that happens in Plan 09).
"""

from app.core import new_id
from app.models import Batch
from app.routes import mobile_sales
from app.services.ledger import record_operation


def _client(mobile_client_factory):
    return mobile_client_factory(mobile_sales.router)


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
