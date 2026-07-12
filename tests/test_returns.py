"""OPS-02 executable contract for the sale-linked return slice.

Interface contract for the Wave 3 return service/route. Module path and
signatures below are fixed — implement against them, do not rename.

This file is RED by design until app.services.returns lands: the module
import fails collection entirely (mirrors tests/test_sales.py from Phase 4).
Do NOT stub the service here.

Naming convention (used by -k filters, per 05-VALIDATION.md's
Requirements -> Test Map): route/e2e tests are prefixed test_web_;
everything else is service level. Selectors: link_and_freeze,
returnable_cap, entry_point.
"""

from sqlalchemy import select

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Batch, Operation, Product, Sale, Warehouse
from app.services.batches import legacy_batch, open_batches
from app.services.ledger import compute_stock, next_seq, record_operation
from app.services.returns import register_return, returnable_qty  # noqa: F401

# 0007 D-03 seeded default warehouse (frozen copy — the lazy-created legacy
# batch's warehouse target; mirrors app.services.returns.DEFAULT_WAREHOUSE_ID).
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"
LEGACY_COMMENT = "Остаток до внедрения партий"


def _return_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "return")).all()


def _make_sale(
    session, product, qty, unit_price_cents=1500, unit_cost_cents=1000, batch_id=None
):
    """Build a real BATCHED sale inline: one Sale header + one `sale` op through
    the single write path (mirrors tests/test_ledger.py::test_record_operation_sets_sale_id).

    Phase 9: a sale is batch-attributed. When no batch_id is given, the first
    open batch of the product is used, so the origin op carries a batch_id the
    return can inherit (D-08) and the sale survives the mandatory D-12 flip.
    """
    header = Sale(
        id=new_id(),
        customer_id=None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
    if batch_id is None:
        batches = open_batches(session, product.id)
        batch_id = batches[0].id if batches else None
    op = record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-qty,
        unit_cost_cents=unit_cost_cents,
        unit_price_cents=unit_price_cents,
        sale_id=header.id,
        batch_id=batch_id,
    )
    return header, op


def _make_legacy_sale(
    session, product, qty, unit_price_cents=1500, unit_cost_cents=1000
):
    """Simulate a pre-Phase-9 sale: a raw NULL-batch_id ledger row inserted
    directly, bypassing record_operation (which after the mandatory D-12 flip
    rejects a stock-affecting op with no batch). This is exactly the legacy
    data shape the return path's inheritance fallback must handle (D-08)."""
    header = Sale(
        id=new_id(),
        customer_id=None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
    op = Operation(
        id=new_id(),
        type="sale",
        product_id=product.id,
        qty_delta=-qty,
        unit_cost_cents=unit_cost_cents,
        unit_price_cents=unit_price_cents,
        sale_id=header.id,
        batch_id=None,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(op)
    product.quantity = Product.quantity + (-qty)
    session.commit()
    return header, op


# --- Service level ---


def test_link_and_freeze(session, stocked_product):
    """OPS-02/D-06/D-07: a return writes a `return` op (qty_delta>0); sale_id
    + unit_price_cents/unit_cost_cents are copied from the ORIGIN sale op,
    NOT from the current product card."""
    header, sale_op = _make_sale(
        session, stocked_product, qty=2, unit_price_cents=1500, unit_cost_cents=1000
    )

    # Card prices change AFTER the sale — the return must still freeze the
    # ORIGIN sale line's amounts, never the current card (D-07).
    stocked_product.sale_cents = 9999
    stocked_product.cost_cents = 8888
    session.commit()

    result, errors = register_return(session, origin_op_id=sale_op.id, qty_raw="1")
    assert errors == {}
    assert result

    ops = _return_ops(session)
    assert len(ops) == 1
    op = ops[0]
    assert op.qty_delta == 1
    assert op.sale_id == header.id
    assert op.unit_price_cents == 1500
    assert op.unit_cost_cents == 1000

    session.expire_all()
    assert stocked_product.quantity == 8 - 2 + 1
    assert compute_stock(session, stocked_product.id) == 8 - 2 + 1


def test_returnable_cap(session, stocked_product):
    """OPS-02/D-08: returnable = sold - already-returned per sale_id+product_id;
    over-return is rejected; a partial return respects what remains."""
    header, sale_op = _make_sale(session, stocked_product, qty=3)

    assert returnable_qty(session, header.id, stocked_product.id) == 3

    over_result, over_errors = register_return(session, origin_op_id=sale_op.id, qty_raw="4")
    assert over_result is None
    assert over_errors
    assert _return_ops(session) == []

    partial_result, partial_errors = register_return(session, origin_op_id=sale_op.id, qty_raw="2")
    assert partial_errors == {}
    assert partial_result
    assert returnable_qty(session, header.id, stocked_product.id) == 1

    exceeding_result, exceeding_errors = register_return(
        session, origin_op_id=sale_op.id, qty_raw="2"
    )
    assert exceeding_result is None
    assert exceeding_errors
    assert len(_return_ops(session)) == 1  # only the first partial return landed


# --- Batch inheritance (D-08, LOT-05) ---


def test_return_inherits_origin_batch(session, stocked_product):
    """D-08: a return of a BATCHED sale restores stock to the ORIGIN op's batch
    (the return op inherits origin.batch_id and the batch quantity increments)."""
    batch = open_batches(session, stocked_product.id)[0]
    _header, sale_op = _make_sale(session, stocked_product, qty=2, batch_id=batch.id)
    assert sale_op.batch_id == batch.id

    result, errors = register_return(session, origin_op_id=sale_op.id, qty_raw="1")
    assert errors == {}
    assert result

    ops = _return_ops(session)
    assert len(ops) == 1
    assert ops[0].batch_id == batch.id

    session.expire_all()
    # batch quantity: 8 (receipt) - 2 (sale) + 1 (return) = 7
    assert session.get(Batch, batch.id).quantity == 7


def test_return_targets_seeded_legacy_batch(session, product, warehouse):
    """D-08: a return of a pre-Phase-9 (NULL batch_id) sale for a product WITH a
    seeded legacy batch targets that legacy batch — no re-ask, no new batch."""
    legacy = Batch(
        id=new_id(),
        product_id=product.id,
        warehouse_id=warehouse.id,
        quantity=0,
        is_legacy=1,
        comment=LEGACY_COMMENT,
    )
    session.add(legacy)
    session.commit()

    _header, sale_op = _make_legacy_sale(session, product, qty=3)

    result, errors = register_return(session, origin_op_id=sale_op.id, qty_raw="2")
    assert errors == {}
    assert result

    ops = _return_ops(session)
    assert len(ops) == 1
    assert ops[0].batch_id == legacy.id
    session.expire_all()
    assert session.get(Batch, legacy.id).quantity == 2


def test_return_lazy_creates_legacy_batch(session, product):
    """Open Q1: a return of a NULL-batch sale for a product with NO legacy batch
    lazily creates one (is_legacy=1, «Остаток до внедрения партий») inside the
    return transaction and completes without error (the third batch birth path)."""
    # The lazy-created legacy batch targets the seeded default warehouse.
    session.add(Warehouse(id=DEFAULT_WAREHOUSE_ID, name="Основной склад"))
    session.commit()

    _header, sale_op = _make_legacy_sale(session, product, qty=2)
    assert legacy_batch(session, product.id) is None  # none seeded

    result, errors = register_return(session, origin_op_id=sale_op.id, qty_raw="1")
    assert errors == {}
    assert result

    lb = legacy_batch(session, product.id)
    assert lb is not None
    assert lb.is_legacy == 1
    assert lb.comment == LEGACY_COMMENT
    assert lb.warehouse_id == DEFAULT_WAREHOUSE_ID

    ops = _return_ops(session)
    assert len(ops) == 1
    assert ops[0].batch_id == lb.id
    session.expire_all()
    assert session.get(Batch, lb.id).quantity == 1


# --- Web slice (routes + templates) ---


def test_web_return_shows_readonly_origin_batch_line(client, session, stocked_product):
    """D-08: the return form shows the target batch as a READ-ONLY muted line —
    no picker, no batch input."""
    batch = open_batches(session, stocked_product.id)[0]
    header, _op = _make_sale(session, stocked_product, qty=2, batch_id=batch.id)

    response = client.get(
        "/returns", params={"sale_id": header.id, "product_id": stocked_product.id}
    )
    assert response.status_code == 200
    assert "Возврат в партию:" in response.text
    # D-08: no batch picker and no batch input on the return form.
    assert 'name="batch_id"' not in response.text
    assert "batch_picker" not in response.text


def test_web_return_legacy_shows_legacy_label(client, session, product):
    """UAT gate 8: a return of a legacy (NULL batch_id) sale shows
    «Возврат в партию: Остаток до внедрения партий»."""
    header, _op = _make_legacy_sale(session, product, qty=2)

    response = client.get(
        "/returns", params={"sale_id": header.id, "product_id": product.id}
    )
    assert response.status_code == 200
    assert "Возврат в партию: Остаток до внедрения партий" in response.text


def test_web_return_entry_point(client, session, stocked_product):
    """OPS-02: GET /returns?sale_id=&product_id= wires the origin op's
    frozen price into the return form."""
    header, _sale_op = _make_sale(session, stocked_product, qty=2, unit_price_cents=1500)

    response = client.get(
        "/returns", params={"sale_id": header.id, "product_id": stocked_product.id}
    )
    assert response.status_code == 200
    assert stocked_product.name in response.text
    assert "15,00" in response.text  # frozen sale price rendered via | cents


def test_web_return_origin_not_found_uses_422(client):
    """CR-02: an unresolvable origin returns 422 (htmx-swappable per
    base.html's responseHandling allow-list), not 404 (silently discarded)."""
    response = client.get(
        "/returns",
        params={"sale_id": "", "product_id": "", "origin_op_id": "bogus-id"},
    )
    assert response.status_code == 422
    assert "Исходная продажа не найдена." in response.text


def test_web_return_survives_unexpected_error(client, session, stocked_product, monkeypatch):
    """CR-03: an unexpected (non-ValueError/IntegrityError) exception must
    not crash via an unhandled PendingRollbackError when the except block
    re-queries the (now-tainted) session for the error context.

    A failed flush (duplicate primary key) is what genuinely leaves a
    SQLAlchemy Session needing an explicit rollback() before further use —
    unlike a plain failed SELECT, which SQLite does not poison a
    transaction over (Postgres would, SQLite does not)."""
    from sqlalchemy.exc import IntegrityError

    import app.services.returns as returns_service
    from app.models import Product

    _header, sale_op = _make_sale(session, stocked_product, qty=2)

    def _boom(*args, **kwargs):
        # Taint the session with a failed flush, mirroring a session left
        # needing rollback() after record_operation's own commit fails for
        # a reason other than ValueError/IntegrityError.
        session.add(Product(id=stocked_product.id, code="DUP", name="dup", quantity=0))
        try:
            session.flush()
        except IntegrityError:
            pass
        raise RuntimeError("boom")

    monkeypatch.setattr(returns_service, "record_operation", _boom)

    response = client.post("/returns", data={"origin_op_id": sale_op.id, "qty": "1"})
    assert response.status_code == 422
    assert "Не удалось сохранить" in response.text
