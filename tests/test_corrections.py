"""OPS-03 executable contract for the stock-correction slice.

Interface contract for the Wave 4 correction service/route. Module path and
signatures below are fixed — implement against them, do not rename.

This file is RED by design until app.services.corrections lands: the
module import fails collection entirely (mirrors tests/test_sales.py from
Phase 4). Do NOT stub the service here.

Naming convention (used by -k filters, per 05-VALIDATION.md's
Requirements -> Test Map): route/e2e tests are prefixed test_web_;
everything else is service level. Selectors: count_vs_delta,
zero_net_noop, ledger_equals_cache, ops_replaced.
"""

from app.services.corrections import register_correction  # noqa: F401
from sqlalchemy import select

from app.models import Operation
from app.services.ledger import compute_stock


def _correction_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "correction")).all()


# --- Service level ---


def test_count_vs_delta(session, stocked_product):
    """OPS-03/D-09: counted mode writes qty_delta = counted - current
    Product.quantity; delta mode writes the signed entered value as-is."""
    count_result, count_errors = register_correction(
        session, code=stocked_product.code, mode="count", value_raw="5", note=""
    )
    assert count_errors == {}
    assert count_result
    count_op = _correction_ops(session)[-1]
    assert count_op.qty_delta == 5 - 8  # counted(5) - quantity-before-write(8)

    session.expire_all()
    assert stocked_product.quantity == 5
    assert compute_stock(session, stocked_product.id) == 5

    delta_result, delta_errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="-2", note=""
    )
    assert delta_errors == {}
    assert delta_result
    delta_op = _correction_ops(session)[-1]
    assert delta_op.qty_delta == -2  # entered value, unmodified by current quantity

    session.expire_all()
    assert stocked_product.quantity == 3


def test_zero_net_noop(session, stocked_product):
    """OPS-03/D-10: a zero net delta writes NO row and returns a graceful
    RU rejection."""
    result, errors = register_correction(
        session, code=stocked_product.code, mode="count", value_raw="8", note=""
    )
    assert result is None
    assert errors
    assert _correction_ops(session) == []


def test_ledger_equals_cache(session, stocked_product):
    """OPS-03/D-10: after a correction, Product.quantity == compute_stock() —
    products.quantity was never edited outside record_operation."""
    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="4", note="stocktake"
    )
    assert errors == {}
    op = _correction_ops(session)[-1]
    assert op.qty_delta == 4
    assert op.payload["mode"] == "delta"

    session.expire_all()
    assert stocked_product.quantity == compute_stock(session, stocked_product.id)


# --- Web slice (routes + templates) ---


def test_web_ops_replaced(client, stocked_product):
    """OPS-03/D-12: the walking-skeleton POST /ops correction is GONE (404
    or 405) — POST /corrections is the single correction path."""
    old_response = client.post("/ops", data={"product_id": stocked_product.id, "qty_delta": "1"})
    assert old_response.status_code in (404, 405)

    new_response = client.post(
        "/corrections",
        data={"code": stocked_product.code, "mode": "delta", "value": "1", "note": ""},
    )
    assert new_response.status_code == 200
