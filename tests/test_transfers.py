"""Transfer service tests (WH-03): register_transfer + recent_transfers.

Pitfall 1 backstop: "transfer" must be registered in THREE runtime
collections at once (OPERATION_TYPES, OPERATION_TYPE_LABELS,
STOCK_AFFECTING_TYPES) or record_operation silently mistreats it.
"""

from app.core import new_id
from app.models import OPERATION_TYPE_LABELS, OPERATION_TYPES, Batch, Warehouse
from app.services.batches import open_batches
from app.services.ledger import STOCK_AFFECTING_TYPES, rebuild_stock, record_operation
from app.services.transfers import recent_transfers, register_transfer


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


def test_transfer_batch_pick_dest_excludes_source(client, session, stocked_product):
    source = _source_batch(session, stocked_product, qty=8)
    dest_wh = _second_warehouse(session)

    response = client.get(
        "/transfers/batch-pick",
        params={"batch_id": source.id, "code": stocked_product.code},
    )

    assert response.status_code == 200
    assert f'value="{source.id}"' in response.text
    assert f'value="{dest_wh.id}"' in response.text
    assert f'value="{source.warehouse_id}"' not in response.text


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
