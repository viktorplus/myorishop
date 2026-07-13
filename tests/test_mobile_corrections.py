"""Mobile Корректировка wizard tests (Plan 11-06): steps + guardrails.

Built entirely against `mobile_client_factory` (Plan 01) — the real
app.main router registration happens in Plan 09, not here.
"""

from app.core import new_id
from app.models import Batch, Operation
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


# --- Task 2: steps Режим/Значение + final write + guardrail ---


def _correction_ops(session):
    return session.query(Operation).filter(Operation.type == "correction").all()


def test_mobile_correction_step_mode_and_value_render_expected_labels(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    mode_response = client.post(
        "/m/corrections/step/mode", data={"code": product.code, "batch_id": batch.id}
    )
    assert mode_response.status_code == 200
    assert "Шаг 3 из 4" in mode_response.text
    assert 'value="count"' in mode_response.text
    assert 'value="delta"' in mode_response.text
    assert "Пересчёт (фактический остаток)" in mode_response.text
    assert "Изменение (±)" in mode_response.text

    count_value_response = client.post(
        "/m/corrections/step/value",
        data={"code": product.code, "batch_id": batch.id, "mode": "count", "batch_qty": "5"},
    )
    assert count_value_response.status_code == 200
    assert "Шаг 4 из 4" in count_value_response.text
    assert "Фактический остаток" in count_value_response.text
    assert "Остаток в партии: 5" in count_value_response.text

    delta_value_response = client.post(
        "/m/corrections/step/value",
        data={"code": product.code, "batch_id": batch.id, "mode": "delta", "batch_qty": "5"},
    )
    assert delta_value_response.status_code == 200
    assert "Изменение (+ или −)" in delta_value_response.text


def test_mobile_correction_count_mode_happy_path(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post(
        "/m/corrections",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "mode": "count",
            "value": "8",
            "note": "",
            "confirm": "",
        },
    )

    assert response.status_code == 200
    assert "Корректировка сохранена" in response.text
    session.expire_all()
    session.refresh(batch)
    session.refresh(product)
    assert batch.quantity == 8
    assert product.quantity == 8
    ops = _correction_ops(session)
    assert len(ops) == 1
    assert ops[0].qty_delta == 3  # counted(8) - batch-quantity-before-write(5)
    assert ops[0].batch_id == batch.id


def test_mobile_correction_delta_mode_happy_path(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post(
        "/m/corrections",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "mode": "delta",
            "value": "-2",
            "note": "",
            "confirm": "",
        },
    )

    assert response.status_code == 200
    assert "Корректировка сохранена" in response.text
    session.expire_all()
    session.refresh(batch)
    assert batch.quantity == 3
    ops = _correction_ops(session)
    assert len(ops) == 1
    assert ops[0].qty_delta == -2


def test_mobile_correction_over_removal_warns_then_confirms(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    warn_response = client.post(
        "/m/corrections",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "mode": "delta",
            "value": "-10",
            "note": "",
            "confirm": "",
        },
    )

    assert warn_response.status_code == 200
    assert "В партии не хватает остатка" in warn_response.text
    assert _correction_ops(session) == []

    confirm_response = client.post(
        "/m/corrections",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "mode": "delta",
            "value": "-10",
            "note": "",
            "confirm": "1",
        },
    )

    assert confirm_response.status_code == 200
    assert "Корректировка сохранена" in confirm_response.text
    session.expire_all()
    session.refresh(batch)
    assert batch.quantity == -5  # batch may go negative on confirm
    ops = _correction_ops(session)
    assert len(ops) == 1
    assert ops[0].qty_delta == -10


def test_mobile_correction_step_batch_has_no_mobile_back_link(
    mobile_client_factory, session, product, warehouse
):
    _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post("/m/corrections/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert 'class="mobile-back"' not in response.text


def test_mobile_correction_step_mode_and_value_show_header_and_own_back_target(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    mode_response = client.post(
        "/m/corrections/step/mode",
        data={"code": product.code, "name": product.name, "batch_id": batch.id},
    )
    assert mode_response.status_code == 200
    assert f"<strong>{product.code}</strong> — {product.name}" in mode_response.text
    assert f"Склад: {warehouse.name}" in mode_response.text
    assert 'hx-post="/m/corrections/step/batch"' in mode_response.text
    assert 'class="mobile-back"' not in mode_response.text

    value_response = client.post(
        "/m/corrections/step/value",
        data={
            "code": product.code,
            "name": product.name,
            "batch_id": batch.id,
            "mode": "count",
            "batch_qty": "5",
        },
    )
    assert value_response.status_code == 200
    assert f"<strong>{product.code}</strong> — {product.name}" in value_response.text
    assert f"Склад: {warehouse.name}" in value_response.text
    assert 'hx-post="/m/corrections/step/mode"' in value_response.text
    assert 'class="mobile-back"' not in value_response.text


def test_mobile_correction_start_hx_request_returns_bare_fragment(mobile_client_factory):
    client = mobile_client_factory(mobile_corrections.router)

    hx_response = client.get("/m/corrections", headers={"HX-Request": "true"})
    assert hx_response.status_code == 200
    assert "<html" not in hx_response.text

    full_response = client.get("/m/corrections")
    assert full_response.status_code == 200
    assert "<html" in full_response.text


def test_mobile_correction_zero_net_delta_rejected(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post(
        "/m/corrections",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "mode": "count",
            "value": "5",
            "note": "",
            "confirm": "",
        },
    )

    assert response.status_code == 422
    assert "Остаток не изменился" in response.text
    session.expire_all()
    session.refresh(batch)
    assert batch.quantity == 5
    assert _correction_ops(session) == []
