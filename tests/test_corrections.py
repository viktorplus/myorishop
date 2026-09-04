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

from datetime import date, timedelta

from sqlalchemy import select

from app.config import settings
from app.core import local_today_iso, new_id
from app.models import Batch, Operation, Product, Warehouse
from app.services.batches import open_batches
from app.services.corrections import DELTA_QTY_ERROR, register_correction  # noqa: F401
from app.services.ledger import (
    OP_DATE_FORMAT_ERROR,
    OP_DATE_FUTURE_ERROR,
    compute_stock,
    record_operation,
)


def _correction_ops(session):
    return session.scalars(select(Operation).where(Operation.type == "correction")).all()


def _only_batch(session, product):
    """The single open batch of a fixture product (LOT-05: correction needs one)."""
    return open_batches(session, product.id)[0]


def _two_batch_product(session):
    """A product with batch A (qty 3) and batch B (qty 10); total 13.

    Used to prove the count-mode diff is against the PICKED batch's quantity,
    not the product total (Pitfall 7), and that over-removal is batch-scoped
    (criterion 4)."""
    product = Product(id=new_id(), code="MB-002", name="Многопартийный", quantity=0)
    session.add(product)
    warehouse = Warehouse(id=new_id(), name="Склад МБ")
    session.add(warehouse)
    session.commit()
    batch_a = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    batch_b = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0)
    session.add_all([batch_a, batch_b])
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=3, batch_id=batch_a.id
    )
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=10, batch_id=batch_b.id
    )
    session.expire_all()
    return product, batch_a, batch_b


# --- Service level ---


def test_count_vs_delta(session, stocked_product):
    """OPS-03/D-09: counted mode writes qty_delta = counted - the picked
    Batch.quantity; delta mode writes the signed entered value as-is."""
    batch = _only_batch(session, stocked_product)
    count_result, count_errors = register_correction(
        session, code=stocked_product.code, mode="count", value_raw="5", note="",
        batch_id=batch.id,
    )
    assert count_errors == {}
    assert count_result
    count_op = _correction_ops(session)[-1]
    assert count_op.qty_delta == 5 - 8  # counted(5) - batch-quantity-before-write(8)
    assert count_op.batch_id == batch.id

    session.expire_all()
    assert stocked_product.quantity == 5
    assert compute_stock(session, stocked_product.id) == 5

    delta_result, delta_errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="-2", note="",
        batch_id=batch.id,
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
    batch = _only_batch(session, stocked_product)
    result, errors = register_correction(
        session, code=stocked_product.code, mode="count", value_raw="8", note="",
        batch_id=batch.id,
    )
    assert result is None
    assert errors
    assert _correction_ops(session) == []


def test_ledger_equals_cache(session, stocked_product):
    """OPS-03/D-10: after a correction, Product.quantity == compute_stock() —
    products.quantity was never edited outside record_operation."""
    batch = _only_batch(session, stocked_product)
    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="4", note="stocktake",
        batch_id=batch.id,
    )
    assert errors == {}
    op = _correction_ops(session)[-1]
    assert op.qty_delta == 4
    assert op.payload["mode"] == "delta"

    session.expire_all()
    assert stocked_product.quantity == compute_stock(session, stocked_product.id)


def test_correction_requires_batch(session, stocked_product):
    """LOT-05: a correction with no resolvable batch is rejected with
    «Выберите партию.» and writes nothing."""
    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="4", note="",
        batch_id="",
    )
    assert result is None
    assert errors == {"batch": "Выберите партию."}
    assert _correction_ops(session) == []


def test_correction_foreign_batch_rejected(session, stocked_product):
    """LOT-05/T-09-12: a batch owned by another product is rejected; 0 writes."""
    _other, foreign_a, _foreign_b = _two_batch_product(session)
    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="4", note="",
        batch_id=foreign_a.id,
    )
    assert result is None
    assert errors == {"batch": "Выберите партию."}
    assert _correction_ops(session) == []


def test_count_diff_against_batch_not_product(session):
    """Pitfall 7/T-09-13: a count of 5 on batch A (qty 3) writes qty_delta =
    5 - 3 = 2 (NOT 5 - product_total_13); batch B (qty 10) is untouched."""
    _product, batch_a, batch_b = _two_batch_product(session)
    result, errors = register_correction(
        session, code="MB-002", mode="count", value_raw="5", note="",
        batch_id=batch_a.id,
    )
    assert errors == {}
    assert result
    op = _correction_ops(session)[-1]
    assert op.qty_delta == 5 - 3  # against batch A's 3, not the product total 13
    assert op.batch_id == batch_a.id

    session.expire_all()
    assert batch_a.quantity == 5
    assert batch_b.quantity == 10  # sibling batch untouched


def test_correction_over_removal(session):
    """criterion 4/D-09: removing more than the picked batch holds warns
    (available == the batch's 3) with zero writes; confirm=1 overrides and
    decrements only the picked batch."""
    _product, batch_a, batch_b = _two_batch_product(session)

    result, errors = register_correction(
        session, code="MB-002", mode="delta", value_raw="-5", note="",
        batch_id=batch_a.id,
    )
    assert errors == {}
    assert result and result.get("oversell")
    assert result["oversell"]["available"] == 3  # batch-scoped, not 13
    assert result["oversell"]["requested"] == 5
    assert _correction_ops(session) == []

    confirmed, confirm_errors = register_correction(
        session, code="MB-002", mode="delta", value_raw="-5", note="",
        batch_id=batch_a.id, confirm="1",
    )
    assert confirm_errors == {}
    assert confirmed and confirmed.get("operation")
    session.expire_all()
    assert batch_a.quantity == 3 - 5  # batch may go negative on confirm
    assert batch_b.quantity == 10  # sibling batch untouched


# --- Web slice (routes + templates) ---


def test_web_ops_replaced(client, session, stocked_product):
    """OPS-03/D-12: the walking-skeleton POST /ops correction is GONE (404
    or 405) — POST /corrections is the single correction path."""
    old_response = client.post("/ops", data={"product_id": stocked_product.id, "qty_delta": "1"})
    assert old_response.status_code in (404, 405)

    batch = _only_batch(session, stocked_product)
    new_response = client.post(
        "/corrections",
        data={
            "code": stocked_product.code,
            "mode": "delta",
            "value": "1",
            "note": "",
            "batch_id": batch.id,
        },
    )
    assert new_response.status_code == 200


# --- DATE-01/DATE-02: the business date on корректировка (VA-14) ------------


def test_correction_backdated_lands_on_the_ledger_row(session, stocked_product):
    """A past op_date is stored on the correction's ledger row, while
    created_at keeps recording when it was actually typed in (T-33-18)."""
    batch = _only_batch(session, stocked_product)

    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="2", note="",
        batch_id=batch.id, op_date="2026-08-15",
    )

    assert errors == {}
    ops = _correction_ops(session)
    assert len(ops) == 1
    assert ops[0].business_date == "2026-08-15"
    # The audit timestamp is untouched — the operator dated the operation, not
    # the moment of entry.
    assert ops[0].created_at[:10] != "2026-08-15"
    assert result["operation"].business_date == "2026-08-15"


def test_correction_without_op_date_stamps_today(session, stocked_product):
    """An empty value is not an error: it means «today», resolved by
    record_operation's Python-side fallback (the single resolution point)."""
    batch = _only_batch(session, stocked_product)

    _result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="2", note="",
        batch_id=batch.id, op_date="",
    )

    assert errors == {}
    ops = _correction_ops(session)
    assert len(ops) == 1
    assert ops[0].business_date == local_today_iso(settings.display_tz)


def test_correction_future_op_date_refused_with_zero_writes(session, stocked_product):
    """DATE-02: a future date is refused in Russian and NOTHING is written —
    asserted by counting ledger rows, not by trusting the early return."""
    batch = _only_batch(session, stocked_product)
    before = len(_correction_ops(session))
    qty_before = batch.quantity

    tomorrow = (
        date.fromisoformat(local_today_iso(settings.display_tz)) + timedelta(days=1)
    ).isoformat()
    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="2", note="",
        batch_id=batch.id, op_date=tomorrow,
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FUTURE_ERROR
    assert len(_correction_ops(session)) == before
    session.expire_all()
    session.refresh(batch)
    assert batch.quantity == qty_before


def test_correction_malformed_op_date_refused_with_zero_writes(session, stocked_product):
    """A typo gets the OTHER message (D-12: two distinct mistakes, two
    distinct messages), also with zero writes."""
    batch = _only_batch(session, stocked_product)
    before = len(_correction_ops(session))

    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="2", note="",
        batch_id=batch.id, op_date="15.08.2026",
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FORMAT_ERROR
    assert errors["op_date"] != OP_DATE_FUTURE_ERROR
    assert len(_correction_ops(session)) == before


def test_correction_bad_date_and_bad_quantity_reported_together(session, stocked_product):
    """The date is validated WITH the quantity, so one 422 carries both
    messages instead of forcing two round-trips."""
    batch = _only_batch(session, stocked_product)

    result, errors = register_correction(
        session, code=stocked_product.code, mode="delta", value_raw="abc", note="",
        batch_id=batch.id, op_date="15.08.2026",
    )

    assert result is None
    assert errors["op_date"] == OP_DATE_FORMAT_ERROR
    assert errors["quantity"] == DELTA_QTY_ERROR
    assert _correction_ops(session) == []


def test_correction_unknown_code_still_fails_on_the_code(session, stocked_product):
    """Shipped precedence is byte-unchanged: the product guard runs BEFORE the
    date parse, so an unknown code still reports the code, not the date."""
    result, errors = register_correction(
        session, code="NOPE-NOPE", mode="delta", value_raw="1", note="",
        batch_id="whatever", op_date="15.08.2026",
    )

    assert result is None
    assert "op_date" not in errors
    assert "code" in errors
