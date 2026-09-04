"""Mobile write-off wizard tests (Phase 11 Plan 05, UI-01/LOT-05).

Uses `mobile_client_factory` (Plan 01 foundation) to test
app.routes.mobile_writeoff.router in isolation, exactly like every other
Phase 11 feature plan. Asserts the wizard produces the SAME register_writeoff
write as desktop, with the same zero-write-until-confirmed oversell guardrail.
"""

from datetime import date, timedelta

from app.config import settings
from app.core import local_today_iso, new_id
from app.models import WRITEOFF_REASONS, Batch, Operation, Product
from app.routes import mobile_writeoff
from app.services.ledger import OP_DATE_FUTURE_ERROR


def _make_batch(session, product, warehouse, quantity, **kwargs):
    batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=quantity,
        **kwargs,
    )
    session.add(batch)
    session.commit()
    return batch


def test_mobile_writeoff_start_prefills_code_from_query(mobile_client_factory, product):
    """quick-260813-i28: ?code= prefills the Код field, both cold and HX-Request."""
    client = mobile_client_factory(mobile_writeoff.router)

    cold = client.get("/m/writeoff", params={"code": product.code})
    assert cold.status_code == 200
    assert f'value="{product.code}"' in cold.text

    hx = client.get(
        "/m/writeoff", params={"code": product.code}, headers={"HX-Request": "true"}
    )
    assert hx.status_code == 200
    assert f'value="{product.code}"' in hx.text


def test_batch_step_lists_open_batches_and_includes_picker(
    mobile_client_factory, session, product, warehouse
):
    _make_batch(session, product, warehouse, quantity=5)
    client = mobile_client_factory(mobile_writeoff.router)

    response = client.post("/m/writeoff/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert "Выберите партию" in response.text
    assert 'id="batch-wrap"' in response.text
    assert "Остаток: 5 шт." in response.text
    assert "Далее" in response.text


def test_empty_batches_blocks_forward_progress(mobile_client_factory, session, product, warehouse):
    # Product has zero open batches (none created).
    client = mobile_client_factory(mobile_writeoff.router)

    response = client.post("/m/writeoff/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert "Нет партий с остатком." in response.text
    assert "Далее" not in response.text


def test_batch_step_unknown_code_shows_error_on_step_one(mobile_client_factory, session):
    client = mobile_client_factory(mobile_writeoff.router)

    response = client.post("/m/writeoff/step/batch", data={"code": "NOPE-404"})

    assert response.status_code == 422
    assert "не найден" in response.text


def test_batch_pick_revalidates_ownership_against_another_product(
    mobile_client_factory, session, product, warehouse
):
    other = Product(id=new_id(), code="OTHER-1", name="Другой товар", quantity=0)
    session.add(other)
    session.commit()
    foreign_batch = _make_batch(session, other, warehouse, quantity=3)

    client = mobile_client_factory(mobile_writeoff.router)

    # Attempt to pick a batch that belongs to a DIFFERENT product than `code`.
    response = client.get(
        "/m/writeoff/step/batch-pick",
        params={"batch_id": foreign_batch.id, "code": product.code},
    )

    assert response.status_code == 200
    # Not echoed as selected — ownership check rejected it (T-11-13).
    assert 'class="mobile-card selected"' not in response.text


def test_full_happy_path_writes_one_writeoff_operation_with_reason(
    mobile_client_factory, session, product, warehouse
):
    batch = _make_batch(session, product, warehouse, quantity=10)
    client = mobile_client_factory(mobile_writeoff.router)

    resp = client.post(
        "/m/writeoff",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "3",
            "reason_code": "damaged",
            "note": "Разбилось",
        },
    )

    assert resp.status_code == 200
    assert "Списание сохранено" in resp.text

    ops = session.query(Operation).filter(Operation.type == "writeoff").all()
    assert len(ops) == 1
    assert ops[0].qty_delta == -3
    assert ops[0].payload["reason_code"] == "damaged"
    assert ops[0].payload["note"] == "Разбилось"
    assert ops[0].batch_id == batch.id

    session.refresh(product)
    session.refresh(batch)
    assert product.quantity == -3  # fixture product starts at 0 (D-11 cache delta)
    assert batch.quantity == 7


def test_missing_reason_code_422s_with_ru_error_and_writes_zero_rows(
    mobile_client_factory, session, product, warehouse
):
    batch = _make_batch(session, product, warehouse, quantity=10)
    client = mobile_client_factory(mobile_writeoff.router)

    resp = client.post(
        "/m/writeoff",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "2",
            "reason_code": "",
            "note": "",
        },
    )

    assert resp.status_code == 422
    assert "Выберите причину списания." in resp.text
    assert session.query(Operation).filter(Operation.type == "writeoff").count() == 0


def test_oversell_warns_with_zero_rows_then_confirm_completes(
    mobile_client_factory, session, product, warehouse
):
    batch = _make_batch(session, product, warehouse, quantity=2)
    client = mobile_client_factory(mobile_writeoff.router)

    warn_resp = client.post(
        "/m/writeoff",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "5",
            "reason_code": "damaged",
            "note": "",
        },
    )

    assert warn_resp.status_code == 200
    assert "Товара не хватает в партии" in warn_resp.text
    assert "в партии 2, списываете 5." in warn_resp.text
    assert session.query(Operation).filter(Operation.type == "writeoff").count() == 0

    confirm_resp = client.post(
        "/m/writeoff",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "5",
            "reason_code": "damaged",
            "note": "",
            "confirm": "1",
        },
    )

    assert confirm_resp.status_code == 200
    assert "Списание сохранено" in confirm_resp.text
    ops = session.query(Operation).filter(Operation.type == "writeoff").all()
    assert len(ops) == 1
    assert ops[0].qty_delta == -5


def test_reason_step_renders_one_row_per_writeoff_reason(
    mobile_client_factory, session, product, warehouse
):
    batch = _make_batch(session, product, warehouse, quantity=4)
    client = mobile_client_factory(mobile_writeoff.router)

    resp = client.post(
        "/m/writeoff/step/reason",
        data={"code": product.code, "batch_id": batch.id, "qty": "1"},
    )

    assert resp.status_code == 200
    for label in WRITEOFF_REASONS.values():
        assert label in resp.text
    assert 'type="radio" name="reason_code"' in resp.text
    assert 'class="visually-hidden"' in resp.text


def test_qty_and_reason_steps_show_header_and_own_back_target(
    mobile_client_factory, session, product, warehouse
):
    batch = _make_batch(session, product, warehouse, quantity=5)
    client = mobile_client_factory(mobile_writeoff.router)

    qty_resp = client.post(
        "/m/writeoff/step/qty",
        data={"code": product.code, "batch_id": batch.id, "name": product.name},
    )
    assert qty_resp.status_code == 200
    assert f"<strong>{product.code}</strong> — {product.name}" in qty_resp.text
    assert f"Склад: {warehouse.name}" in qty_resp.text
    assert 'hx-post="/m/writeoff/step/batch"' in qty_resp.text
    assert "onclick=\"history.back()\"" not in qty_resp.text

    reason_resp = client.post(
        "/m/writeoff/step/reason",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "1",
            "name": product.name,
        },
    )
    assert reason_resp.status_code == 200
    assert f"<strong>{product.code}</strong> — {product.name}" in reason_resp.text
    assert f"Склад: {warehouse.name}" in reason_resp.text
    assert 'hx-post="/m/writeoff/step/qty"' in reason_resp.text
    assert "onclick=\"history.back()\"" not in reason_resp.text


# --- DATE-01/DATE-02 (Phase 33 plan 10): the wizard-wide business date ---


def _today_plus(days: int) -> str:
    return (
        date.fromisoformat(local_today_iso(settings.display_tz)) + timedelta(days=days)
    ).isoformat()


def test_writeoff_shell_renders_the_prefilled_date_above_the_wizard_step(
    mobile_client_factory,
):
    """D-11: the date input lives in the persistent shell, BEFORE #wizard-step,
    so htmx never swaps it — the position is what makes it wizard-wide."""
    client = mobile_client_factory(mobile_writeoff.router)
    response = client.get("/m/writeoff")
    assert response.status_code == 200
    today = local_today_iso(settings.display_tz)
    assert "Дата операции" in response.text
    assert 'name="op_date"' in response.text
    assert f'value="{today}" max="{today}"' in response.text
    assert response.text.index('name="op_date"') < response.text.index('id="wizard-step"')
    assert response.text.index('name="op_date"') < response.text.index("Шаг 1 из 4")


def test_writeoff_wizard_steps_never_re_emit_the_date(
    mobile_client_factory, session, product, warehouse
):
    """D-11: zero hidden-field threading — the shell is the ONLY place the date
    exists, so no swapped step may carry a second copy of it."""
    batch = _make_batch(session, product, warehouse, quantity=10)
    client = mobile_client_factory(mobile_writeoff.router)
    today = local_today_iso(settings.display_tz)

    qty_step = client.post(
        "/m/writeoff/step/qty",
        data={"code": product.code, "batch_id": batch.id, "op_date": today},
    )
    assert qty_step.status_code == 200
    assert "op_date" not in qty_step.text

    reason_step = client.post(
        "/m/writeoff/step/reason",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "2",
            "op_date": today,
        },
    )
    assert reason_step.status_code == 200
    assert "Шаг 4 из 4" in reason_step.text
    assert "op_date" not in reason_step.text


def test_mobile_writeoff_writes_the_shell_date(
    mobile_client_factory, session, product, warehouse
):
    """The value typed on step 1 reaches the final write untouched."""
    batch = _make_batch(session, product, warehouse, quantity=10)
    back_date = _today_plus(-14)
    client = mobile_client_factory(mobile_writeoff.router)

    resp = client.post(
        "/m/writeoff",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "3",
            "reason_code": "damaged",
            "note": "",
            "op_date": back_date,
        },
    )

    assert resp.status_code == 200
    ops = session.query(Operation).filter(Operation.type == "writeoff").all()
    assert len(ops) == 1
    assert ops[0].business_date == back_date


def test_mobile_writeoff_future_date_error_is_the_first_element_of_the_step(
    mobile_client_factory, session, product, warehouse
):
    """D-14 intent / CF-UI-1: the refusal renders as the FIRST element of the
    swapped step (the DOM node right after the shell's still-filled input),
    exactly once, and as a per-field <p class="error"> — never swept into the
    .error-block that loops every other message on this screen."""
    batch = _make_batch(session, product, warehouse, quantity=10)
    client = mobile_client_factory(mobile_writeoff.router)

    resp = client.post(
        "/m/writeoff",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "qty": "3",
            "reason_code": "damaged",
            "note": "",
            "op_date": _today_plus(1),
        },
    )

    assert resp.status_code == 422
    text = resp.text
    assert f'<p class="error">{OP_DATE_FUTURE_ERROR}</p>' in text
    assert text.count(OP_DATE_FUTURE_ERROR) == 1
    assert text.index(OP_DATE_FUTURE_ERROR) < text.index("Шаг 4 из 4")
    assert f'<div class="error-block">{OP_DATE_FUTURE_ERROR}</div>' not in text
    assert session.query(Operation).filter(Operation.type == "writeoff").count() == 0


def test_writeoff_start_hx_request_returns_bare_fragment(mobile_client_factory):
    client = mobile_client_factory(mobile_writeoff.router)

    hx_response = client.get("/m/writeoff", headers={"HX-Request": "true"})
    assert hx_response.status_code == 200
    assert "<html" not in hx_response.text

    full_response = client.get("/m/writeoff")
    assert full_response.status_code == 200
    assert "<html" in full_response.text
