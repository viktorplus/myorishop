"""Transfer service tests (WH-03): register_transfer + recent_transfers.

Pitfall 1 backstop: "transfer" must be registered in THREE runtime
collections at once (OPERATION_TYPES, OPERATION_TYPE_LABELS,
STOCK_AFFECTING_TYPES) or record_operation silently mistreats it.
"""

from datetime import date, timedelta

from sqlalchemy import select

from app.config import settings
from app.core import local_today_iso, new_id
from app.models import OPERATION_TYPE_LABELS, OPERATION_TYPES, Batch, Operation, Warehouse
from app.services.batches import open_batches
from app.services.ledger import (
    OP_DATE_FORMAT_ERROR,
    OP_DATE_FUTURE_ERROR,
    STOCK_AFFECTING_TYPES,
    rebuild_stock,
    record_operation,
)
from app.services.transfers import QTY_ERROR, recent_transfers, register_transfer


def test_transfer_type_registered():
    assert "transfer" in OPERATION_TYPES
    assert "transfer" in OPERATION_TYPE_LABELS
    assert OPERATION_TYPE_LABELS["transfer"]
    assert "transfer" in STOCK_AFFECTING_TYPES


def _second_warehouse(session):
    """Seed and return a second active warehouse (destination for transfers)."""
    wh = Warehouse(id=new_id(), name="Склад Б")
    session.add(wh)
    session.commit()
    return wh


def _source_batch(
    session, stocked_product, qty=8, price_cents=1500, expiry=None, comment=None, location=None
):
    """Return the pre-seeded stocked_product's open batch, adjusted to `qty`.

    stocked_product fixture already has a batch with 8 units (receipt at
    unit_price_cents=1500). If a caller wants different price/expiry/comment/
    location we build a fresh dedicated batch+receipt so those fields are
    under test control.
    """
    warehouse_id = None
    batches = open_batches(session, stocked_product.id)
    assert len(batches) == 1
    batch = batches[0]
    if price_cents != 1500 or expiry or comment or location:
        # Build a dedicated batch so price/expiry/comment/location are exact.
        warehouse_id = batch.warehouse_id
        batch = Batch(
            id=new_id(),
            product_id=stocked_product.id,
            warehouse_id=warehouse_id,
            name="Партия для теста",
            expiry=expiry,
            price_cents=price_cents,
            location=location,
            comment=comment,
            quantity=0,
            is_legacy=0,
        )
        session.add(batch)
        session.commit()
        record_operation(
            session,
            type_="receipt",
            product_id=stocked_product.id,
            qty_delta=qty,
            batch_id=batch.id,
        )
        return batch
    if qty != 8:
        # Adjust quantity via a correction-style receipt/writeoff delta.
        delta = qty - batch.quantity
        record_operation(
            session,
            type_="receipt" if delta > 0 else "writeoff",
            product_id=stocked_product.id,
            qty_delta=delta,
            batch_id=batch.id,
        )
    return batch


def test_transfer_writes_two_rows(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    assert errors == {}
    assert result is not None
    from sqlalchemy import select

    from app.models import Operation

    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert len(ops) == 2
    deltas = sorted(op.qty_delta for op in ops)
    assert deltas == [-3, 3]
    batch_ids = {op.batch_id for op in ops}
    assert batch_ids == {source.id, result["dest"].id}


def test_transfer_qty_echo_is_int_not_raw_string(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    assert errors == {}
    assert result["qty"] == 3
    assert isinstance(result["qty"], int)


def test_transfer_projections(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)
    before_product_qty = stocked_product.quantity
    before_source_qty = source.quantity

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    assert errors == {}
    assert stocked_product.quantity == before_product_qty
    assert source.quantity == before_source_qty - 3
    assert result["dest"].quantity == 3


def test_dest_batch_inherits_history(session, stocked_product):
    source = _source_batch(
        session,
        stocked_product,
        qty=5,
        price_cents=0,
        expiry="2026-12-31",
        comment="комментарий",
        location="Полка 3",
    )
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="2",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    assert errors == {}
    dest = result["dest"]
    assert dest.price_cents == 0
    assert dest.expiry == "2026-12-31"
    assert dest.comment == "комментарий"
    assert dest.location == "Полка 3"
    assert dest.name == source.name
    assert dest.warehouse_id == dest_wh.id
    assert dest.is_legacy == 0
    assert dest.id != source.id


def test_full_transfer_empties_source(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="8",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    assert errors == {}
    assert source.quantity == 0
    remaining = open_batches(session, stocked_product.id, source.warehouse_id)
    assert source.id not in {b.id for b in remaining}


def test_over_qty_confirm_gate(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="20",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )
    assert errors == {}
    assert result == {
        "oversell": {"available": source.quantity, "requested": 20, "product": stocked_product}
    }
    from sqlalchemy import select

    from app.models import Operation

    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []

    result2, errors2 = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="20",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
        confirm="1",
    )
    assert errors2 == {}
    ops2 = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert len(ops2) == 2


def test_same_warehouse_blank_overrides_blocked(session, stocked_product):
    from sqlalchemy import select

    from app.models import Operation
    from app.services.transfers import SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR

    source = _source_batch(session, stocked_product, qty=8)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=source.warehouse_id,
    )
    assert result is None
    assert errors == {"form": SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR}

    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []


def test_same_warehouse_with_expiry_override_creates_split_batch(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8, comment="исходный комментарий")
    before_source_qty = source.quantity

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=source.warehouse_id,
        new_expiry="2027-01-01",
    )

    assert errors == {}
    dest = result["dest"]
    assert dest.warehouse_id == source.warehouse_id
    assert dest.expiry == "2027-01-01"
    assert dest.comment == source.comment
    assert dest.id != source.id
    assert source.quantity == before_source_qty - 3
    assert dest.quantity == 3


def test_same_warehouse_with_comment_override_creates_split_batch(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8, expiry="2026-06-01")

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=source.warehouse_id,
        new_comment="вскрыт образец",
    )

    assert errors == {}
    dest = result["dest"]
    assert dest.comment == "вскрыт образец"
    assert dest.expiry == source.expiry


def test_cross_warehouse_override_wins_over_source(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8, expiry="2026-06-01", comment="старый")
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
        new_expiry="2027-01-01",
        new_comment="вскрыт образец",
    )

    assert errors == {}
    dest = result["dest"]
    assert dest.expiry == "2027-01-01"
    assert dest.comment == "вскрыт образец"


def test_cross_warehouse_blank_overrides_still_inherits_unchanged(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8, expiry="2026-06-01", comment="старый")
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    assert errors == {}
    dest = result["dest"]
    assert dest.expiry == source.expiry
    assert dest.comment == source.comment


def _eur_warehouse(session):
    """Seed and return a second active warehouse with a different currency."""
    wh = Warehouse(id=new_id(), name="Склад EUR", currency="EUR")
    session.add(wh)
    session.commit()
    return wh


def test_cross_currency_transfer_blank_cost_rejected_zero_writes(session, stocked_product):
    """CUR-02: a cross-currency transfer with a blank cost is rejected, zero writes."""
    from sqlalchemy import select

    from app.models import Operation
    from app.services.transfers import COST_REQUIRED_ERROR

    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _eur_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )
    assert result is None
    assert errors == {"cost": COST_REQUIRED_ERROR}
    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []


def test_cross_currency_transfer_with_cost_succeeds(session, stocked_product):
    """CUR-02: a cross-currency transfer with an entered cost writes the
    destination batch's cost_cents from the entered value."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _eur_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
        cost_raw="9,50",
    )
    assert errors == {}
    assert result["dest"].cost_cents == 950


def test_same_currency_transfer_blank_cost_inherits_source(session, stocked_product):
    """CUR-02: a same-currency transfer with a blank cost inherits source.cost_cents."""
    source = _source_batch(session, stocked_product, qty=8)
    source.cost_cents = 400
    session.commit()
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )
    assert errors == {}
    assert result["dest"].cost_cents == 400


def test_same_warehouse_override_field_with_only_whitespace_treated_as_blank(
    session, stocked_product
):
    from sqlalchemy import select

    from app.models import Operation
    from app.services.transfers import SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR

    source = _source_batch(session, stocked_product, qty=8)

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=source.warehouse_id,
        new_expiry="   ",
        new_comment="",
    )

    assert result is None
    assert errors == {"form": SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR}
    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []


def test_reject_tampered_ids(session, stocked_product, product):
    """product fixture is a DIFFERENT product (code TEST-001, zero stock)."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    # Foreign batch: batch_id belongs to `product`, not `stocked_product`.
    foreign_batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=dest_wh.id,
        quantity=0,
    )
    session.add(foreign_batch)
    session.commit()

    result, errors = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=foreign_batch.id,
        dest_warehouse_id=dest_wh.id,
    )
    assert result is None
    assert "batch" in errors

    # Unknown/inactive dest warehouse.
    result2, errors2 = register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id="does-not-exist",
    )
    assert result2 is None
    assert "warehouse" in errors2

    from sqlalchemy import select

    from app.models import Operation

    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []


def test_rebuild_invariant_after_transfer(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    rebuild_stock(session)  # must not raise


def test_recent_transfers_lists_outbound_row(session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    register_transfer(
        session,
        code=stocked_product.code,
        name=stocked_product.name,
        qty_raw="3",
        batch_id=source.id,
        dest_warehouse_id=dest_wh.id,
    )

    rows = recent_transfers(session)
    assert len(rows) == 1
    assert rows[0]["op"].qty_delta == -3
    assert rows[0]["product"].id == stocked_product.id


# --- Route/integration tests (WH-03 wiring) -------------------------------


def test_transfers_page_renders(client):
    response = client.get("/transfers")
    assert response.status_code == 200
    assert 'id="code"' in response.text
    assert "Переместить" in response.text


def test_transfer_lookup_fills(client, session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)

    response = client.get("/transfers/lookup", params={"code": stocked_product.code})

    assert response.status_code == 200
    assert stocked_product.name in response.text
    assert f'value="{source.id}"' in response.text


def test_transfer_batch_pick_dest_includes_source_warehouse(client, session, stocked_product):
    """D-09: the source batch's own warehouse is now a selectable destination
    (same-warehouse split), alongside any other active warehouse."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    response = client.get(
        "/transfers/batch-pick",
        params={"batch_id": source.id, "code": stocked_product.code},
    )

    assert response.status_code == 200
    assert f'value="{source.id}"' in response.text
    assert f'value="{dest_wh.id}"' in response.text
    assert f'value="{source.warehouse_id}"' in response.text


def test_transfer_post_moves_stock(client, session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    response = client.post(
        "/transfers",
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
    assert "recent-transfers" in response.text

    session.refresh(source)
    assert source.quantity == 5
    dest_batches = open_batches(session, stocked_product.id, dest_wh.id)
    assert len(dest_batches) == 1
    assert dest_batches[0].quantity == 3


def test_transfer_post_oversell_then_confirm(client, session, stocked_product):
    from sqlalchemy import select

    from app.models import Operation

    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    response = client.post(
        "/transfers",
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
        "/transfers",
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


def test_transfer_in_history(client, session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    client.post(
        "/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    response = client.get("/history")

    assert response.status_code == 200
    assert "Перемещение" in response.text
    assert "-3" in response.text
    assert "+3" in response.text


def test_transfer_create_ownership_guard_does_not_echo_foreign_batch(
    client, session, stocked_product, product
):
    """D-10: a client-submitted batch_id naming another product's batch is
    never echoed back into the picker on POST /transfers' error branch."""
    dest_wh = _second_warehouse(session)

    foreign_batch = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=dest_wh.id,
        quantity=0,
    )
    session.add(foreign_batch)
    session.commit()

    response = client.post(
        "/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": foreign_batch.id,
            "dest_warehouse_id": dest_wh.id,
        },
    )

    assert response.status_code == 422
    assert foreign_batch.id not in response.text


def test_transfer_post_success_qty_echo_matches_parsed_int(client, session, stocked_product):
    """D-11 regression guard: the success message uses the actual transferred
    integer quantity (result["qty"]) rather than the raw form string."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    response = client.post(
        "/transfers",
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


def test_transfer_post_same_warehouse_with_expiry_override_succeeds(
    client, session, stocked_product
):
    """D-05/D-07/D-09 end-to-end: a same-warehouse split reachable via a raw
    form POST, ahead of the template UI (Plan 20-07)."""
    source = _source_batch(session, stocked_product, qty=8)

    response = client.post(
        "/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": source.warehouse_id,
            "new_expiry": "2027-01-01",
            "new_comment": "",
        },
    )

    assert response.status_code == 200
    assert "Перемещение сохранено" in response.text

    session.expire_all()
    dest_batches = [
        b
        for b in open_batches(session, stocked_product.id, source.warehouse_id)
        if b.id != source.id
    ]
    assert len(dest_batches) == 1
    assert dest_batches[0].quantity == 3
    assert dest_batches[0].expiry == "2027-01-01"


def test_transfer_post_same_warehouse_blank_overrides_shows_form_error(
    client, session, stocked_product
):
    from sqlalchemy import select

    from app.models import Operation
    from app.services.transfers import SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR

    source = _source_batch(session, stocked_product, qty=8)

    response = client.post(
        "/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": source.warehouse_id,
        },
    )

    assert response.status_code == 422
    assert SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR in response.text

    ops = session.scalars(select(Operation).where(Operation.type == "transfer")).all()
    assert ops == []


def test_transfer_batch_pick_shows_override_fields(client, session, stocked_product):
    """Plan 20-07/UI-SPEC decision 9: the override fields render as soon as a
    source batch is picked, with the UI-SPEC-locked Russian copy."""
    source = _source_batch(session, stocked_product, qty=8)

    response = client.get(
        "/transfers/batch-pick",
        params={"batch_id": source.id, "code": stocked_product.code},
    )

    assert response.status_code == 200
    assert 'name="new_expiry"' in response.text
    assert 'name="new_comment"' in response.text
    assert "Новый срок годности" in response.text
    assert "Новое состояние или комментарий" in response.text


def test_transfer_post_same_warehouse_blank_overrides_error_visible_in_form(
    client, session, stocked_product
):
    """Template-level proof that errors.form correctly reaches
    transfer_form.html's existing error-block slot (complements the
    route-level assertion in test_transfer_post_same_warehouse_blank_overrides_
    shows_form_error, which doesn't check the rendering container)."""
    from app.services.transfers import SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR

    source = _source_batch(session, stocked_product, qty=8)

    response = client.post(
        "/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "3",
            "batch_id": source.id,
            "dest_warehouse_id": source.warehouse_id,
        },
    )

    assert response.status_code == 422
    assert 'class="error-block"' in response.text
    assert SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR in response.text


def test_transfer_post_422_echoes_typed_override_values(client, session, stocked_product):
    """The override fields' typed values survive a 422 re-render triggered by
    an unrelated validation error (invalid qty), not just a successful round
    trip."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    response = client.post(
        "/transfers",
        data={
            "code": stocked_product.code,
            "name": stocked_product.name,
            "qty": "abc",
            "batch_id": source.id,
            "dest_warehouse_id": dest_wh.id,
            "new_expiry": "2027-01-01",
            "new_comment": "повреждена упаковка",
        },
    )

    assert response.status_code == 422
    assert 'value="2027-01-01"' in response.text
    assert 'value="повреждена упаковка"' in response.text


# --- NAV-07: GET /transfers?code= prefill (D-14, V5) -----------------------


def test_web_transfers_page_prefills_code_and_batches(client, stocked_product):
    """The product name and its one open batch resolve server-side on the
    very first render — no re-selection step."""
    response = client.get("/transfers", params={"code": stocked_product.code})

    assert response.status_code == 200
    assert f'value="{stocked_product.code}"' in response.text
    assert stocked_product.name in response.text
    # Proves the batch picker resolved a real batch, not the empty state.
    assert "Нет партий с остатком." not in response.text


def test_web_transfers_page_unmatched_code_renders_empty_form(client):
    """An unmatched code silently renders an empty form — never a 500, never
    an unescaped echo of the raw query param (V5 Security Domain)."""
    response = client.get("/transfers", params={"code": "NOPE-NOPE"})

    assert response.status_code == 200
    assert 'value="NOPE-NOPE"' in response.text
    # The code is only ever echoed via the escaped `value="..."` attribute —
    # never as freestanding unescaped text elsewhere on the page.
    assert response.text.count("NOPE-NOPE") == 1


def test_web_transfers_lookup_unmatched_code_still_returns_204(client):
    """Regression guard: the _resolve_transfer_lookup extraction in Task 1
    must not change this endpoint's pre-existing 204 contract."""
    response = client.get("/transfers/lookup", params={"code": "NOPE-NOPE"})

    assert response.status_code == 204


# --- DATE-01/DATE-02: the business date on перемещение (VA-14) --------------


def _transfer_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "transfer")).all()


def test_backdated_transfer_dates_BOTH_of_its_ledger_rows_identically(
    session, stocked_product
):
    """T-33-31: a transfer is TWO rows and one operation. Both halves carry the
    SAME business date — asserted as a set of size one, by identity, not by
    comparing each row to a literal, so a future edit that re-derives the date
    per row reddens even if both derivations happen to agree on the day."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session, code=stocked_product.code, name="", qty_raw="3",
        batch_id=source.id, dest_warehouse_id=dest_wh.id, op_date="2026-08-15",
    )

    assert errors == {}
    assert result is not None
    ops = _transfer_ops(session)
    assert len(ops) == 2
    assert sorted(op.qty_delta for op in ops) == [-3, 3]
    # The load-bearing assertion: ONE business date across BOTH halves.
    assert len({op.business_date for op in ops}) == 1
    assert ops[0].business_date == "2026-08-15"
    # created_at still records when it was typed in (T-33-18).
    assert all(op.created_at[:10] != "2026-08-15" for op in ops)


def test_transfer_without_op_date_stamps_today_on_both_rows(session, stocked_product):
    """An empty value means «today» — and the resolve-once rule still holds, so
    the two rows cannot straddle local midnight."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    _result, errors = register_transfer(
        session, code=stocked_product.code, name="", qty_raw="3",
        batch_id=source.id, dest_warehouse_id=dest_wh.id, op_date="",
    )

    assert errors == {}
    ops = _transfer_ops(session)
    assert len(ops) == 2
    assert len({op.business_date for op in ops}) == 1
    assert ops[0].business_date == local_today_iso(settings.display_tz)


def test_transfer_future_op_date_refused_with_zero_writes(session, stocked_product):
    """DATE-02: a future date is refused in Russian; NEITHER row is written and
    no destination batch is leaked (the dest Batch is session.add()ed inside
    this function, so a validation gap here would orphan one)."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)
    before = len(_transfer_ops(session))
    batches_before = len(session.scalars(select(Batch)).all())
    qty_before = source.quantity

    tomorrow = (
        date.fromisoformat(local_today_iso(settings.display_tz)) + timedelta(days=1)
    ).isoformat()
    result, errors = register_transfer(
        session, code=stocked_product.code, name="", qty_raw="3",
        batch_id=source.id, dest_warehouse_id=dest_wh.id, op_date=tomorrow,
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FUTURE_ERROR
    assert len(_transfer_ops(session)) == before
    assert len(session.scalars(select(Batch)).all()) == batches_before
    session.expire_all()
    session.refresh(source)
    assert source.quantity == qty_before


def test_transfer_malformed_op_date_refused_with_zero_writes(session, stocked_product):
    """A typo gets the OTHER message (D-12), also with zero writes."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)
    before = len(_transfer_ops(session))

    result, errors = register_transfer(
        session, code=stocked_product.code, name="", qty_raw="3",
        batch_id=source.id, dest_warehouse_id=dest_wh.id, op_date="15.08.2026",
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FORMAT_ERROR
    assert errors["op_date"] != OP_DATE_FUTURE_ERROR
    assert len(_transfer_ops(session)) == before


def test_transfer_bad_date_and_bad_quantity_reported_together(session, stocked_product):
    """The date rides alongside the shipped code/qty validation block."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    result, errors = register_transfer(
        session, code=stocked_product.code, name="", qty_raw="0",
        batch_id=source.id, dest_warehouse_id=dest_wh.id, op_date="15.08.2026",
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FORMAT_ERROR
    assert errors["quantity"] == QTY_ERROR
    assert _transfer_ops(session) == []


# --- DATE-01: the desktop перемещение surface (wiring, via the real route) --


def test_web_transfer_form_renders_prefilled_date_field(client):
    """GET /transfers renders the field pre-filled AND capped at today."""
    today = local_today_iso(settings.display_tz)
    response = client.get("/transfers")

    assert response.status_code == 200
    assert 'name="op_date"' in response.text
    assert f'value="{today}" max="{today}"' in response.text
    assert 'class="field op-date"' in response.text
    assert "Дата операции" in response.text
    assert response.text.index('name="op_date"') < response.text.index('class="form-actions"')


def test_web_transfer_backdated_post_dates_both_rows(client, session, stocked_product):
    """The route must PASS the date to the service, and BOTH rows the single
    POST writes must carry it — the wiring twin of the service-level test."""
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    response = client.post(
        "/transfers",
        data={
            "code": stocked_product.code, "name": stocked_product.name, "qty": "3",
            "batch_id": source.id, "dest_warehouse_id": dest_wh.id,
            "op_date": "2026-08-15",
        },
    )

    assert response.status_code == 200
    ops = _transfer_ops(session)
    assert len(ops) == 2
    assert {op.business_date for op in ops} == {"2026-08-15"}


def test_web_transfer_future_date_returns_422_and_echoes_the_typed_value(
    client, session, stocked_product
):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)
    tomorrow = (
        date.fromisoformat(local_today_iso(settings.display_tz)) + timedelta(days=1)
    ).isoformat()

    response = client.post(
        "/transfers",
        data={
            "code": stocked_product.code, "name": stocked_product.name, "qty": "3",
            "batch_id": source.id, "dest_warehouse_id": dest_wh.id,
            "op_date": tomorrow,
        },
    )

    assert response.status_code == 422
    assert OP_DATE_FUTURE_ERROR in response.text
    assert f'value="{tomorrow}"' in response.text
    assert _transfer_ops(session) == []
