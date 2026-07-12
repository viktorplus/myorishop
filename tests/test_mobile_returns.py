"""Phase 11 Plan 08 tests: mobile return flow (GET/POST /m/returns), entered
only from a history card's «Вернуть» action.

Uses mobile_client_factory (Plan 01 foundation) with BOTH mobile_history and
mobile_returns routers together — the return entry point is a link rendered
by the history card partial.
"""

from sqlalchemy import select

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Operation, Sale
from app.routes import mobile_history, mobile_returns
from app.services.batches import open_batches
from app.services.ledger import record_operation


def _client(mobile_client_factory):
    return mobile_client_factory(mobile_history.router, mobile_returns.router)


def _return_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "return")).all()


def _make_sale(session, product, qty, unit_price_cents=1500, unit_cost_cents=1000):
    """Real BATCHED sale: one Sale header + one `sale` op through the single
    write path (mirrors tests/test_returns.py::_make_sale)."""
    header = Sale(
        id=new_id(),
        customer_id=None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(header)
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


def test_tapping_return_resolves_origin_and_shows_returnable_count(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    header, sale_op = _make_sale(session, stocked_product, qty=3)

    response = client.get(
        "/m/returns",
        params={
            "sale_id": header.id,
            "product_id": stocked_product.id,
            "origin_op_id": sale_op.id,
        },
    )

    assert response.status_code == 200
    assert "Доступно к возврату: 3 из 3." in response.text


def test_valid_return_writes_operation_and_shows_success_line(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    header, sale_op = _make_sale(session, stocked_product, qty=3)

    response = client.post(
        "/m/returns", data={"origin_op_id": sale_op.id, "qty": "2"}
    )

    assert response.status_code == 200
    assert f"Возврат оформлен: {stocked_product.name} — 2 шт." in response.text
    returns = _return_ops(session)
    assert len(returns) == 1
    assert returns[0].qty_delta == 2
    assert returns[0].sale_id == header.id


def test_over_cap_qty_returns_422_with_zero_writes(
    mobile_client_factory, session, stocked_product
):
    client = _client(mobile_client_factory)
    _header, sale_op = _make_sale(session, stocked_product, qty=3)

    response = client.post(
        "/m/returns", data={"origin_op_id": sale_op.id, "qty": "5"}
    )

    assert response.status_code == 422
    assert not _return_ops(session)


def test_unresolvable_origin_shows_not_found_message_with_no_form(
    mobile_client_factory, session
):
    client = _client(mobile_client_factory)

    response = client.get("/m/returns", params={"origin_op_id": "does-not-exist"})

    assert response.status_code == 422
    assert "Исходная продажа не найдена." in response.text
    assert "<form" not in response.text
