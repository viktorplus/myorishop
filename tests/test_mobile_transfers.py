"""Mobile Перемещение (transfer) wizard tests (WH-03/UI-01).

Isolated via mobile_client_factory (Phase 11 Plan 01 foundation) — proves the
mobile wizard produces the identical two-row register_transfer() write as
desktop, with the same destination-exclusion and zero-write-until-confirmed
guardrail semantics.
"""

from datetime import date, timedelta

from sqlalchemy import select

from app.config import settings
from app.core import local_today_iso, new_id
from app.models import Batch, Operation, Warehouse
from app.routes import mobile_transfers
from app.services.ledger import OP_DATE_FUTURE_ERROR


def _second_warehouse(session, name="Склад Б"):
    wh = Warehouse(id=new_id(), name=name)
    session.add(wh)
    session.commit()
    return wh


def _source_batch(session, stocked_product):
    """The stocked_product fixture's single open batch (qty 8, price 1500)."""
    from app.services.batches import open_batches

    batches = open_batches(session, stocked_product.id)
    assert len(batches) == 1
    return batches[0]


# --- Task 1: route skeleton + steps Товар/Партия --------------------------


def test_transfers_step_batch_shows_source_warehouse_line(
    mobile_client_factory, session, stocked_product
):
    source = _source_batch(session, stocked_product)
    source_wh = session.get(Warehouse, source.warehouse_id)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post("/m/transfers/step/batch", data={"code": stocked_product.code})

    assert response.status_code == 200
    assert "Цена:" in response.text
    assert "Срок годности:" in response.text
    assert "Остаток:" in response.text
    assert f"Склад: {source_wh.name}" in response.text
    assert 'class="mobile-card"' in response.text


def test_transfers_step_batch_shows_resolved_name(mobile_client_factory, session, stocked_product):
    """D-14: the batch step response shows the code and name between the step
    indicator and "Выберите партию", sourced from lookup_prefill's captured
    (no longer discarded) result."""
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post("/m/transfers/step/batch", data={"code": stocked_product.code})

    assert response.status_code == 200
    assert f"<strong>{stocked_product.code}</strong> — {stocked_product.name}" in response.text


def test_transfers_batch_pick_carries_name_into_dest_step(
    mobile_client_factory, session, stocked_product
):
    """D-14: tapping a batch card carries the name forward via the card's own
    hx-vals (step 2 has no enclosing form to auto-forward hidden fields)."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    batch_response = client.post(
        "/m/transfers/step/batch", data={"code": stocked_product.code}
    )
    # hx-vals is JSON (tojson escapes non-ASCII), so assert on the key, not
    # the literal Cyrillic name text.
    assert '"name":' in batch_response.text

    response = client.get(
        "/m/transfers/step/batch-pick",
        params={"batch_id": source.id, "code": stocked_product.code, "name": stocked_product.name},
    )

    assert response.status_code == 200
    assert f"<strong>{stocked_product.code}</strong> — {stocked_product.name}" in response.text
    assert f'name="name" value="{stocked_product.name}"' in response.text


def test_transfers_step_batch_hx_vals_batch_id_survives_html_attribute(
    mobile_client_factory, session, stocked_product
):
    """quick-260813-ezt: tojson escapes ' not " — a double-quoted hx-vals
    attribute silently truncates at the payload's first '"', dropping
    batch_id. This one response renders BOTH the batch-pick card and the
    Назад button of transfers_step_batch.html, so the guard assertion
    covers both fixed spots in this file."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post("/m/transfers/step/batch", data={"code": stocked_product.code})

    assert response.status_code == 200
    assert (
        f'hx-vals=\'{{"batch_id": "{source.id}", "code": "{stocked_product.code}", "name":'
        in response.text
    )
    assert 'hx-vals="{' not in response.text


def test_transfers_step_dest_hx_vals_back_button_is_single_quoted(
    mobile_client_factory, session, stocked_product
):
    """quick-260813-ezt: covers the fifth fixed line (transfers_step_dest.html
    Назад button) — single-quoted hx-vals carries code intact."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers/step/dest",
        data={"code": stocked_product.code, "batch_id": source.id},
    )

    assert response.status_code == 200
    assert f'hx-vals=\'{{"code": "{stocked_product.code}"}}\'' in response.text
    assert 'hx-vals="{' not in response.text


def test_transfers_step_dest_does_not_drop_a_posted_op_date(
    mobile_client_factory, session, stocked_product
):
    """IN-02 (33-REVIEW): the one `_render_dest_step` caller that dropped the date.

    Nothing posts to this route today (the dest step is entered via
    `GET /m/transfers/step/batch-pick`), so this is a tripwire, not a
    regression test for a live path: if the route is ever wired up, a typed
    back-date must not silently reset to today. D-11 puts the date field on
    THIS step for the transfer wizard, so the omission was on the exact screen
    that owns it.
    """
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers/step/dest",
        data={
            "code": stocked_product.code,
            "batch_id": source.id,
            "op_date": "2026-07-10",
        },
    )

    assert response.status_code == 200
    assert 'value="2026-07-10"' in response.text
    assert f'value="{local_today_iso(settings.display_tz)}"' not in response.text


def test_transfers_create_carries_name_through_oversell_retry(
    mobile_client_factory, session, stocked_product
):
    """D-14: the final submit's error/oversell/success re-renders continue to
    show the name, carried via the hidden name field transfers_create already
    receives as a Form value."""
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "20",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    assert response.status_code == 200
    assert "Товара не хватает в партии" in response.text
    assert f"<strong>{stocked_product.code}</strong> — {stocked_product.name}" in response.text
    assert f'name="name" value="{stocked_product.name}"' in response.text


def test_transfers_step_batch_empty_batches_blocks_forward(mobile_client_factory, session, product):
    # `product` fixture has zero stock/batches.
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post("/m/transfers/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert "Нет партий с остатком." in response.text
    assert 'class="mobile-card"' not in response.text


def test_transfers_batch_pick_dest_includes_source_warehouse(
    mobile_client_factory, session, stocked_product
):
    """D-09: the source warehouse is now a selectable destination radio
    option — a same-warehouse split is reachable from the mobile wizard."""
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.get(
        "/m/transfers/step/batch-pick",
        params={"batch_id": source.id, "code": stocked_product.code},
    )

    assert response.status_code == 200
    assert f'value="{dest_wh.id}"' in response.text
    assert f'value="{source.warehouse_id}"' in response.text
    assert f'value="{source.id}"' in response.text  # batch_id echoed forward


def test_transfers_batch_pick_rejects_foreign_batch(
    mobile_client_factory, session, stocked_product, product
):
    """`product` fixture is a DIFFERENT product — its batch must not be
    accepted as the transfer source for `stocked_product`'s code (T-11-19)."""
    dest_wh = _second_warehouse(session)
    foreign_batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=dest_wh.id,
        quantity=5,
    )
    session.add(foreign_batch)
    session.commit()
    client = mobile_client_factory(mobile_transfers.router)

    response = client.get(
        "/m/transfers/step/batch-pick",
        params={"batch_id": foreign_batch.id, "code": stocked_product.code},
    )

    assert response.status_code == 200
    # Falls back to re-rendering the batch step, not the dest step.
    assert "Выберите партию" in response.text
    assert "Куда и количество" not in response.text


# --- Task 2: step Куда и количество + final write + guardrail -------------


def test_transfers_happy_path_writes_two_rows_and_preserves_history(
    mobile_client_factory, session, stocked_product
):
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    assert response.status_code == 200
    assert "Перемещение сохранено" in response.text

    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert len(ops) == 2
    deltas = sorted(op.qty_delta for op in ops)
    assert deltas == [-3, 3]

    session.refresh(source)
    assert source.quantity == 5

    from app.services.batches import open_batches

    dest_batches = open_batches(session, stocked_product.id, dest_wh.id)
    assert len(dest_batches) == 1
    dest_batch = dest_batches[0]
    assert dest_batch.quantity == 3
    # WH-03: cost/price history preserved at the destination.
    assert dest_batch.price_cents == source.price_cents
    assert dest_batch.expiry == source.expiry
    assert dest_batch.comment == source.comment
    assert dest_batch.location == source.location


def _eur_warehouse(session, name="Склад EUR"):
    wh = Warehouse(id=new_id(), name=name, currency="EUR")
    session.add(wh)
    session.commit()
    return wh


def test_transfers_create_cross_currency_blank_cost_rejected_zero_writes(
    mobile_client_factory, session, stocked_product
):
    """CUR-02: a cross-currency transfer with a blank cost is rejected, zero writes."""
    source = _source_batch(session, stocked_product)
    dest_wh = _eur_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    assert response.status_code == 422
    assert "Укажите себестоимость партии" in response.text
    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []


def test_transfers_create_cross_currency_with_cost_succeeds(
    mobile_client_factory, session, stocked_product
):
    """CUR-02: a cross-currency transfer with an entered cost writes the
    destination batch's cost_cents from the entered value."""
    source = _source_batch(session, stocked_product)
    dest_wh = _eur_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
            "cost": "9,50",
        },
    )

    assert response.status_code == 200
    assert "Перемещение сохранено" in response.text
    from app.services.batches import open_batches

    dest_batch = open_batches(session, stocked_product.id, dest_wh.id)[0]
    assert dest_batch.cost_cents == 950


def test_transfers_create_same_currency_blank_cost_inherits_source(
    mobile_client_factory, session, stocked_product
):
    """CUR-02: a same-currency transfer with a blank cost inherits source.cost_cents."""
    source = _source_batch(session, stocked_product)
    source.cost_cents = 400
    session.commit()
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    assert response.status_code == 200
    from app.services.batches import open_batches

    dest_batch = open_batches(session, stocked_product.id, dest_wh.id)[0]
    assert dest_batch.cost_cents == 400


def test_transfers_dest_list_includes_source_even_with_two_warehouses(
    mobile_client_factory, session, stocked_product
):
    """D-09: even with a second warehouse available, the source warehouse
    stays in the destination list (no exclusion filter)."""
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers/step/dest",
        data={"code": stocked_product.code, "batch_id": source.id},
    )

    assert response.status_code == 200
    assert f'value="{dest_wh.id}"' in response.text
    assert f'value="{source.warehouse_id}"' in response.text


def test_transfers_create_same_warehouse_with_override_succeeds(
    mobile_client_factory, session, stocked_product
):
    """D-05/D-07/D-09: a same-warehouse split reaches register_transfer from
    the mobile wizard when an override (new_expiry here) is supplied."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": source.warehouse_id,
            "new_expiry": "2027-01-01",
        },
    )

    assert response.status_code == 200
    assert "Перемещение сохранено" in response.text

    from app.services.batches import open_batches

    dest_batches = [
        b
        for b in open_batches(session, stocked_product.id, source.warehouse_id)
        if b.id != source.id
    ]
    assert len(dest_batches) == 1
    assert dest_batches[0].quantity == 3


def test_transfers_create_same_warehouse_blank_overrides_shows_form_error(
    mobile_client_factory, session, stocked_product
):
    """D-06: same warehouse with both overrides blank -> 422, error text
    shown, zero new transfer Operation rows written."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": source.warehouse_id,
        },
    )

    assert response.status_code == 422
    from app.services.transfers import SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR

    assert SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR in response.text
    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []


def test_transfers_create_qty_saved_matches_parsed_int(
    mobile_client_factory, session, stocked_product
):
    """D-11 regression guard: the mobile success message shows the actual
    transferred integer quantity from the service result, not the raw form
    string."""
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    assert response.status_code == 200
    assert "3 шт." in response.text


def test_transfers_step_dest_shows_override_fields(
    mobile_client_factory, session, stocked_product
):
    """UI-SPEC decision 12: step 3 shows the same two override fields as
    desktop, placed after Количество and before the Назад/Переместить
    buttons."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers/step/dest",
        data={"code": stocked_product.code, "batch_id": source.id},
    )

    assert response.status_code == 200
    assert 'name="new_expiry"' in response.text
    assert 'name="new_comment"' in response.text

    text = response.text
    qty_index = text.index('name="qty"')
    new_expiry_index = text.index('name="new_expiry"')
    new_comment_index = text.index('name="new_comment"')
    actions_index = text.index('class="mobile-actions"')

    assert qty_index < new_expiry_index < new_comment_index < actions_index


def test_transfers_oversell_then_confirm_zero_writes_until_confirmed(
    mobile_client_factory, session, stocked_product
):
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "20",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    assert response.status_code == 200
    assert "Товара не хватает в партии" in response.text
    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []

    response2 = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "20",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
            "confirm": "1",
        },
    )

    assert response2.status_code == 200
    assert "Перемещение сохранено" in response2.text
    ops2 = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert len(ops2) == 2


def test_transfers_zero_open_batches_blocks_batch_step(mobile_client_factory, session, product):
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post("/m/transfers/step/batch", data={"code": product.code})

    assert response.status_code == 200
    assert "Нет партий с остатком." in response.text
    assert 'hx-get="/m/transfers/step/batch-pick"' not in response.text


def test_transfers_step_product_page_renders(mobile_client_factory):
    client = mobile_client_factory(mobile_transfers.router)

    response = client.get("/m/transfers")

    assert response.status_code == 200
    assert 'id="code"' in response.text
    assert "Шаг 1 из 3" in response.text


# --- 13-04: transfers step 2 "Назад" hx-get + UI-02 regression guard ------


def test_transfers_step_batch_back_is_hx_get_not_plain_link(
    mobile_client_factory, session, stocked_product
):
    """D-01/D-02 uniformity: step 2's Назад must be an explicit hx-get, never
    a plain full-page <a> link (13-04 closes the gap 13-CONTEXT.md's D-06
    missed for transfers)."""
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post("/m/transfers/step/batch", data={"code": stocked_product.code})

    assert response.status_code == 200
    assert '<a class="mobile-back" href="/m/transfers"' not in response.text
    assert 'hx-get="/m/transfers"' in response.text


def test_transfers_step_product_hx_request_returns_bare_fragment_with_code(
    mobile_client_factory,
):
    """GET /m/transfers with an HX-Request header (the step-2 Назад button's
    target) returns only the bare fragment, echoing ?code= back into the
    input's value, and preserving typed code across the round trip."""
    client = mobile_client_factory(mobile_transfers.router)

    response = client.get(
        "/m/transfers",
        params={"code": "TEST-001"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert "<html" not in response.text
    assert 'value="TEST-001"' in response.text


def test_transfers_step_product_plain_get_still_full_page_with_code(
    mobile_client_factory,
):
    """A plain GET /m/transfers?code=... (no HX-Request header) still renders
    the full page — the ?code= pre-fill works on both response shapes."""
    client = mobile_client_factory(mobile_transfers.router)

    response = client.get("/m/transfers", params={"code": "TEST-001"})

    assert response.status_code == 200
    assert "<html" in response.text
    assert 'value="TEST-001"' in response.text


def test_transfers_step_batch_header_survives_back_button_refactor(
    mobile_client_factory, session, stocked_product
):
    """UI-02 regression guard: this plan's Назад-button refactor of
    transfers_step_batch.html must not disturb the pre-existing Phase 12
    visible code/name header (also covered by
    test_transfers_step_batch_shows_resolved_name above)."""
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post("/m/transfers/step/batch", data={"code": stocked_product.code})

    assert response.status_code == 200
    assert (
        f"<strong>{stocked_product.code}</strong> — {stocked_product.name}"
        in response.text
    )


# --- DATE-01/DATE-02: «Дата операции» on the mobile перемещение final step --


def _transfer_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "transfer")).all()


def test_transfers_dest_step_renders_prefilled_date_field(
    mobile_client_factory, session, stocked_product
):
    """The date rides the FINAL step (D-11): перемещение has no persistent
    shell, so the field belongs to the terminal screen, as the LAST field
    before the actions row."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)
    today = local_today_iso(settings.display_tz)

    response = client.get(
        "/m/transfers/step/batch-pick",
        params={"code": stocked_product.code, "batch_id": source.id},
    )

    assert response.status_code == 200
    assert 'name="op_date"' in response.text
    assert f'value="{today}"' in response.text
    assert f'max="{today}"' in response.text
    assert "Дата операции" in response.text
    assert 'aria-describedby="op_date-error"' in response.text
    # LAST field before the actions row, after the cost field.
    assert response.text.index('name="op_date"') > response.text.index('id="cost"')
    assert response.text.index('name="op_date"') < response.text.index('class="mobile-actions"')


def test_transfers_earlier_steps_never_emit_the_date(
    mobile_client_factory, session, stocked_product
):
    """Proof by negation (the D-11 shell-less half): the date exists on the
    FINAL step and nowhere else. No earlier fragment mentions op_date, so
    nothing htmx swaps before the terminal screen can carry a stale value, and
    a future edit that threads it as a hidden field reddens this test."""
    client = mobile_client_factory(mobile_transfers.router)

    product_step = client.get("/m/transfers", headers={"HX-Request": "true"})
    batch_step = client.post(
        "/m/transfers/step/batch", data={"code": stocked_product.code}
    )

    for fragment in (product_step, batch_step):
        assert fragment.status_code == 200
        assert "op_date" not in fragment.text


def test_transfers_backdated_post_dates_both_rows_identically(
    mobile_client_factory, session, stocked_product
):
    """T-33-31 through the mobile route: one submit, two rows, ONE date."""
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code, "name": stocked_product.name, "qty": "3",
            "batch_id": source.id, "dest_warehouse_id": dest_wh.id,
            "op_date": "2026-08-15",
        },
    )

    assert response.status_code == 200
    assert "Перемещение сохранено" in response.text
    ops = _transfer_ops(session)
    assert len(ops) == 2
    assert {op.business_date for op in ops} == {"2026-08-15"}


def test_transfers_future_date_error_renders_once_beside_the_field(
    mobile_client_factory, session, stocked_product
):
    """The message renders as a per-key <p class="error"> under the input,
    exactly once, never as a whole-screen .error-block, and the typed value
    survives the 422 re-render."""
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)
    tomorrow = (
        date.fromisoformat(local_today_iso(settings.display_tz)) + timedelta(days=1)
    ).isoformat()

    response = client.post(
        "/m/transfers",
        data={
            "code": stocked_product.code, "name": stocked_product.name, "qty": "3",
            "batch_id": source.id, "dest_warehouse_id": dest_wh.id,
            "op_date": tomorrow,
        },
    )

    assert response.status_code == 422
    assert response.text.count(OP_DATE_FUTURE_ERROR) == 1
    assert f'<p class="error" id="op_date-error">{OP_DATE_FUTURE_ERROR}</p>' in response.text
    assert "error-block" not in response.text
    assert f'value="{tomorrow}"' in response.text
    assert _transfer_ops(session) == []


def test_transfers_date_survives_the_oversell_confirm_round_trip(
    mobile_client_factory, session, stocked_product
):
    """The over-transfer warn re-renders this very step with zero writes. The
    typed date must come back with it — otherwise confirming the warning would
    silently book the transfer under today instead of the chosen day."""
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)
    payload = {
        "code": stocked_product.code, "name": stocked_product.name, "qty": "99",
        "batch_id": source.id, "dest_warehouse_id": dest_wh.id,
        "op_date": "2026-08-15",
    }

    warn = client.post("/m/transfers", data=payload)
    assert warn.status_code == 200
    assert _transfer_ops(session) == []
    assert 'value="2026-08-15"' in warn.text

    confirmed = client.post("/m/transfers", data={**payload, "confirm": "1"})
    assert confirmed.status_code == 200
    ops = _transfer_ops(session)
    assert len(ops) == 2
    assert {op.business_date for op in ops} == {"2026-08-15"}


def test_transfers_step_labels_unchanged(mobile_client_factory, session, stocked_product):
    """No wizard gained a step: the three step_label literals are untouched."""
    source = _source_batch(session, stocked_product)
    client = mobile_client_factory(mobile_transfers.router)

    dest = client.get(
        "/m/transfers/step/batch-pick",
        params={"code": stocked_product.code, "batch_id": source.id},
    )
    batch = client.post("/m/transfers/step/batch", data={"code": stocked_product.code})
    first = client.get("/m/transfers", headers={"HX-Request": "true"})

    assert '<p class="mobile-step-indicator">Шаг 3 из 3</p>' in dest.text
    assert "Шаг 2 из 3" in batch.text
    assert "Шаг 1 из 3" in first.text
