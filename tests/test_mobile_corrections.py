"""Mobile Корректировка wizard tests (Plan 11-06): steps + guardrails.

Built entirely against `mobile_client_factory` (Plan 01) — the real
app.main router registration happens in Plan 09, not here.
"""

from app.core import new_id
from app.models import Batch
from app.routes import mobile_corrections
from app.services.ledger import record_operation


def _seed_batch(session, product, warehouse, quantity):
    batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add(batch)
    session.commit()
    if quantity:
        record_operation(
            session,
            type_="receipt",
            product_id=product.id,
            qty_delta=quantity,
            unit_cost_cents=1000,
            unit_price_cents=1500,
            batch_id=batch.id,
        )
    session.expire_all()
    return batch


# --- Task 1: steps Товар/Партия ---


def test_mobile_correction_batch_step_lists_open_batches(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post("/m/corrections/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert "Шаг 2 из 4" in response.text
    assert "Остаток: 5 шт." in response.text
    assert batch.id in response.text


def test_mobile_correction_batch_pick_revalidates_ownership(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.get(
        "/m/corrections/step/batch-pick", params={"batch_id": batch.id, "code": product.code}
    )

    assert response.status_code == 200
    assert 'class="mobile-card selected"' in response.text
    # A foreign batch id is rejected — never trusted as selected.
    foreign_response = client.get(
        "/m/corrections/step/batch-pick", params={"batch_id": "nope", "code": product.code}
    )
    assert "selected" not in foreign_response.text.split("mobile-card")[1]


def test_mobile_correction_empty_batches_blocks_forward_progress(
    mobile_client_factory, session, product
):
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post("/m/corrections/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert "Нет партий с остатком." in response.text
    assert "Далее" not in response.text
