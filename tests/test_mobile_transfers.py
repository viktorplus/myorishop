"""Mobile Перемещение (transfer) wizard tests (WH-03/UI-01).

Isolated via mobile_client_factory (Phase 11 Plan 01 foundation) — proves the
mobile wizard produces the identical two-row register_transfer() write as
desktop, with the same destination-exclusion and zero-write-until-confirmed
guardrail semantics.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import Batch, Operation, Warehouse
from app.routes import mobile_transfers


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


def test_transfers_batch_pick_dest_exclu_source_warehouse(
    mobile_client_factory, session, stocked_product
):
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.get(
        "/m/transfers/step/batch-pick",
        params={"batch_id": source.id, "code": stocked_product.code},
    )

    assert response.status_code == 200
    assert f'value="{dest_wh.id}"' in response.text
    assert f'value="{source.warehouse_id}"' not in response.text
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


def test_transfers_dest_list_excludes_source_even_with_two_warehouses(
    mobile_client_factory, session, stocked_product
):
    source = _source_batch(session, stocked_product)
    dest_wh = _second_warehouse(session)
    client = mobile_client_factory(mobile_transfers.router)

    response = client.post(
        "/m/transfers/step/dest",
        data={"code": stocked_product.code, "batch_id": source.id},
    )

    assert response.status_code == 200
    assert f'value="{dest_wh.id}"' in response.text
    assert f'value="{source.warehouse_id}"' not in response.text


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
