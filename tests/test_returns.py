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

from app.services.returns import register_return, returnable_qty  # noqa: F401
from sqlalchemy import select

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Operation, Sale
from app.services.ledger import compute_stock, record_operation


def _return_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "return")).all()


def _make_sale(session, product, qty, unit_price_cents=1500, unit_cost_cents=1000):
    """Build a real sale inline: one Sale header + one `sale` op (mirrors
    tests/test_ledger.py::test_record_operation_sets_sale_id)."""
    header = Sale(
        id=new_id(),
        customer_id=None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
    op = record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-qty,
        unit_cost_cents=unit_cost_cents,
        unit_price_cents=unit_price_cents,
        sale_id=header.id,
    )
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


# --- Web slice (routes + templates) ---


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
    import app.services.returns as returns_service
    from app.models import Product
    from sqlalchemy.exc import IntegrityError

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
