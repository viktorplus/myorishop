"""Mobile Корректировка wizard tests (Plan 11-06): steps + guardrails.

Built entirely against `mobile_client_factory` (Plan 01) — the real
app.main router registration happens in Plan 09, not here.
"""

from datetime import date, timedelta

from app.config import settings
from app.core import local_today_iso, new_id
from app.models import Batch, Operation
from app.routes import mobile_corrections
from app.services.corrections import DELTA_QTY_ERROR
from app.services.ledger import (
    OP_DATE_FORMAT_ERROR,
    OP_DATE_FUTURE_ERROR,
    record_operation,
)


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


def test_mobile_correction_batch_step_hx_vals_batch_id_survives_html_attribute(
    mobile_client_factory, session, product, warehouse
):
    """quick-260813-ezt: tojson escapes ' not " — a double-quoted hx-vals
    attribute silently truncates at the payload's first '"', dropping
    batch_id. Pins the single-quoted rendered attribute shape."""
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post("/m/corrections/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert f'hx-vals=\'{{"batch_id": "{batch.id}", "code": "{product.code}"}}\'' in response.text
    assert 'hx-vals="{' not in response.text


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


# --- DATE-01/DATE-02: «Дата операции» on the mobile корректировка final step -


def test_mobile_correction_value_step_renders_prefilled_date_field(
    mobile_client_factory, session, product, warehouse
):
    """The date rides the FINAL step (D-11): корректировка has no persistent
    shell, so the field belongs to the terminal screen, as the LAST field
    before the actions row."""
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)
    today = local_today_iso(settings.display_tz)

    response = client.post(
        "/m/corrections/step/value",
        data={"code": product.code, "batch_id": batch.id, "mode": "count"},
    )

    assert response.status_code == 200
    assert 'name="op_date"' in response.text
    assert f'value="{today}"' in response.text
    assert f'max="{today}"' in response.text
    assert "Дата операции" in response.text
    assert 'aria-describedby="op_date-error"' in response.text
    # LAST field before the actions row, and inside the step's own <form>.
    assert response.text.index('name="op_date"') > response.text.index('id="note"')
    assert response.text.index('name="op_date"') < response.text.index('class="mobile-actions"')


def test_mobile_correction_earlier_steps_carry_the_date_but_render_no_input(
    mobile_client_factory, session, product, warehouse
):
    """WR-03 (33-REVIEW iteration 3) — this test's contract is DELIBERATELY INVERTED.

    It used to assert «no earlier fragment mentions op_date», reasoning that
    nothing swapped before the terminal screen could then carry a stale value.
    That reasoning had the failure mode backwards. The date input lives on step
    4, and step 4's «Назад» posts to /step/mode with hx-include="closest form" —
    so the typed date WAS sent; it was simply not declared or re-emitted, and
    step 4 came back with no `form` key at all, falling through to today.
    Unlike value/note, which come back visibly empty, the date came back
    plausible and correctly formatted, so the correction was booked on the wrong
    day with no cue, into an append-only ledger with no сторно until Phase 34.

    The D-11 half that still holds is the VISIBLE one, and it is what this test
    now pins: earlier steps carry the value in a hidden input and render NO date
    field, so there is still exactly one editable date in the wizard.
    """
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    product_step = client.get(
        "/m/corrections", headers={"HX-Request": "true"}, params={"op_date": "2026-08-15"}
    )
    batch_step = client.post(
        "/m/corrections/step/batch",
        data={"code": product.code, "op_date": "2026-08-15"},
    )
    mode_step = client.post(
        "/m/corrections/step/mode",
        data={
            "code": product.code,
            "batch_id": batch.id,
            "name": product.name,
            "op_date": "2026-08-15",
        },
    )

    for fragment in (product_step, batch_step, mode_step):
        assert fragment.status_code == 200
        assert '<input type="hidden" name="op_date" value="2026-08-15">' in fragment.text
        assert 'type="date"' not in fragment.text
        assert "Дата операции" not in fragment.text


def test_mobile_correction_back_from_the_final_step_preserves_a_typed_date(
    mobile_client_factory, session, product, warehouse
):
    """WR-03: the reachable round trip — step 4 → «Назад» → «Далее» → step 4."""
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)
    today = local_today_iso(settings.display_tz)

    # «Назад» from step 4 posts the whole step-4 form, op_date included.
    back = client.post(
        "/m/corrections/step/mode",
        data={
            "code": product.code,
            "name": product.name,
            "batch_id": batch.id,
            "batch_qty": "5",
            "mode": "delta",
            "value": "-2",
            "note": "",
            "op_date": "2026-08-15",
        },
    )
    assert back.status_code == 200

    # «Далее» from step 3 re-enters step 4 — the date must come back as typed.
    forward = client.post(
        "/m/corrections/step/value",
        data={
            "code": product.code,
            "name": product.name,
            "batch_id": batch.id,
            "batch_qty": "5",
            "mode": "delta",
            "op_date": "2026-08-15",
        },
    )
    assert forward.status_code == 200
    assert 'value="2026-08-15"' in forward.text
    assert f'value="{today}"' not in forward.text


def test_mobile_correction_step_value_still_defaults_to_today_without_a_carried_date(
    mobile_client_factory, session, product, warehouse
):
    """The carry must not change a COLD entry into step 4."""
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)
    today = local_today_iso(settings.display_tz)

    response = client.post(
        "/m/corrections/step/value",
        data={
            "code": product.code,
            "name": product.name,
            "batch_id": batch.id,
            "mode": "delta",
        },
    )
    assert response.status_code == 200
    assert f'value="{today}"' in response.text


def test_mobile_correction_backdated_post_stores_the_business_date(
    mobile_client_factory, session, product, warehouse
):
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post(
        "/m/corrections",
        data={
            "code": product.code, "batch_id": batch.id, "mode": "delta",
            "value": "-2", "note": "", "confirm": "", "op_date": "2026-08-15",
        },
    )

    assert response.status_code == 200
    ops = _correction_ops(session)
    assert len(ops) == 1
    assert ops[0].business_date == "2026-08-15"


def test_mobile_correction_future_date_error_renders_once_beside_the_field(
    mobile_client_factory, session, product, warehouse
):
    """D-14: the message renders as a per-key <p class="error"> under the input
    and is EXCLUDED from the loop-all .error-block — so it appears exactly once
    and never as a detached top-of-screen block. The typed value is echoed back
    so the operator corrects rather than retypes."""
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)
    tomorrow = (
        date.fromisoformat(local_today_iso(settings.display_tz)) + timedelta(days=1)
    ).isoformat()

    response = client.post(
        "/m/corrections",
        data={
            "code": product.code, "batch_id": batch.id, "mode": "delta",
            "value": "-2", "note": "", "confirm": "", "op_date": tomorrow,
        },
    )

    assert response.status_code == 422
    # Exactly once — the loop exclusion works and the message is not duplicated.
    assert response.text.count(OP_DATE_FUTURE_ERROR) == 1
    assert f'<p class="error" id="op_date-error">{OP_DATE_FUTURE_ERROR}</p>' in response.text
    # And NOT inside the whole-screen block.
    assert f'<div class="error-block">\n    <p>{OP_DATE_FUTURE_ERROR}' not in response.text
    assert "error-block" not in response.text
    # The typed date survives the re-render.
    assert f'value="{tomorrow}"' in response.text
    assert _correction_ops(session) == []


def test_mobile_correction_date_error_does_not_suppress_other_errors(
    mobile_client_factory, session, product, warehouse
):
    """The exclusion removes op_date from the block WITHOUT swallowing the
    other messages — a bad value plus a bad date shows both, each in its own
    place, and the block is still emitted for the non-date one."""
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post(
        "/m/corrections",
        data={
            "code": product.code, "batch_id": batch.id, "mode": "delta",
            "value": "abc", "note": "", "confirm": "", "op_date": "15.08.2026",
        },
    )

    assert response.status_code == 422
    assert response.text.count(OP_DATE_FORMAT_ERROR) == 1
    assert f'<p class="error" id="op_date-error">{OP_DATE_FORMAT_ERROR}</p>' in response.text
    # The quantity error still rides the loop-all block.
    assert "error-block" in response.text
    assert DELTA_QTY_ERROR in response.text
    assert _correction_ops(session) == []


def test_mobile_correction_step_strings_unchanged(
    mobile_client_factory, session, product, warehouse
):
    """No wizard gained a step: the final screen still says «Шаг 4 из 4»."""
    batch = _seed_batch(session, product, warehouse, 5)
    client = mobile_client_factory(mobile_corrections.router)

    response = client.post(
        "/m/corrections/step/value",
        data={"code": product.code, "batch_id": batch.id, "mode": "count"},
    )

    assert '<p class="mobile-step-indicator">Шаг 4 из 4</p>' in response.text
