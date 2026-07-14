"""FIN-01/02/06 append-only + balance/contract tests for the cash ledger
(Phase 15, Plan 01 + Plan 02).

Plan 02 adds app.services.finance import (compute_balance, next_seq,
record_cash_movement) now that the service exists.

Plan 03 adds the integration tests proving the sale-credit / return-debit
hooks wired into app.services.sales.register_sale and
app.services.returns.register_return (credit, sale_rollback, debit,
partial, atomic).
"""

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import CashMovement, Operation  # noqa: F401  (CASH_CATEGORIES: contract symbol)
from app.services.batches import open_batches
from app.services.finance import compute_balance, next_seq, record_cash_movement
from app.services.returns import register_return
from app.services.sales import register_sale


def _cash_count(session):
    return session.scalar(select(func.count()).select_from(CashMovement))


def test_cash_movement_append_only_update_is_rejected(session):
    """D-00a: UPDATE on cash_movements is blocked at the database level."""
    session.add(
        CashMovement(
            id=new_id(),
            category="sale",
            amount_cents=12500,
            device_id=settings.device_id,
            seq=1,
            created_at=utcnow_iso(),
            created_by=settings.operator_name,
        )
    )
    session.commit()

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("UPDATE cash_movements SET amount_cents = 99"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_cash_movement_append_only_delete_is_rejected(session):
    """D-00a: DELETE on cash_movements is blocked at the database level."""
    session.add(
        CashMovement(
            id=new_id(),
            category="sale",
            amount_cents=12500,
            device_id=settings.device_id,
            seq=1,
            created_at=utcnow_iso(),
            created_by=settings.operator_name,
        )
    )
    session.commit()

    with pytest.raises((OperationalError, IntegrityError)) as exc_info:
        session.execute(text("DELETE FROM cash_movements"))
    assert "append-only" in str(exc_info.value)
    session.rollback()


def test_balance_empty_is_zero(session):
    """D-00b: compute_balance on an empty ledger returns 0."""
    assert compute_balance(session) == 0


def test_balance_sums_mixed(session):
    """D-00b: compute_balance is the live signed SUM(amount_cents)."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    record_cash_movement(session, category="return", amount_cents=-5000)
    assert compute_balance(session) == 7500


def test_contract_stamps_audit_and_seq(session):
    """D-00b/FND-03: record_cash_movement stamps audit fields and increments
    seq per device (mirrors test_ledger.py:test_audit_trail)."""
    mv1 = record_cash_movement(session, category="sale", amount_cents=12500)
    mv2 = record_cash_movement(session, category="return", amount_cents=-5000)

    assert mv1.created_by == settings.operator_name
    assert isinstance(mv1.created_at, str) and mv1.created_at

    assert mv1.seq == 1
    assert mv2.seq == 2
    assert next_seq(session, settings.device_id) == 3


def test_contract_unknown_category_raises(session):
    """T-15-02: an unknown category raises ValueError and stages no row
    (mirrors test_ledger.py:test_record_operation_unknown_product_raises_value_error)."""
    with pytest.raises(ValueError, match="unknown cash category"):
        record_cash_movement(session, category="bogus", amount_cents=1)
    session.rollback()
    assert session.scalar(text("SELECT COUNT(*) FROM cash_movements")) == 0


# --- Plan 03 integration: sale credit / return debit hooks ---


def test_sale_credits_till(session, stocked_product):
    """FIN-01: a committed sale of total T writes exactly one +T cash row,
    category="sale", linked by sale_id; balance rises by T."""
    bid = open_batches(session, stocked_product.id)[0].id
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result
    total_cents = result["total_cents"]
    header_id = result["header"].id

    rows = list(session.scalars(select(CashMovement)))
    assert len(rows) == 1
    assert rows[0].amount_cents == total_cents
    assert rows[0].category == "sale"
    assert rows[0].sale_id == header_id
    assert compute_balance(session) == total_cents


def test_sale_rollback_writes_zero_cash(session, stocked_product):
    """T-15-03: a sale forced down its no-write path (oversell without
    confirm) writes zero cash rows; balance unchanged."""
    bid = open_batches(session, stocked_product.id)[0].id
    result, errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["100"],  # exceeds the batch's available quantity (8)
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert errors == {}
    assert result and "oversell" in result
    assert _cash_count(session) == 0
    assert compute_balance(session) == 0


def test_full_return_restores_balance(session, stocked_product):
    """FIN-02: a sale-linked return debits -(qty x frozen unit_price_cents),
    category="return"; a FULL return restores the pre-sale balance."""
    bid = open_batches(session, stocked_product.id)[0].id
    pre_sale_balance = compute_balance(session)

    sale_result, sale_errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert sale_errors == {}
    header_id = sale_result["header"].id
    sale_op = session.scalars(
        select(Operation).where(Operation.sale_id == header_id, Operation.type == "sale")
    ).first()

    return_result, return_errors = register_return(
        session, origin_op_id=sale_op.id, qty_raw="2"
    )
    assert return_errors == {}
    assert return_result

    debit_row = session.scalars(
        select(CashMovement).where(CashMovement.category == "return")
    ).first()
    assert debit_row.amount_cents == -(2 * 1500)
    assert compute_balance(session) == pre_sale_balance


def test_partial_return_debits_independently(session, stocked_product):
    """FIN-02/D-00d: a partial return debits only returned_qty x the frozen
    unit_price_cents, computed independently of the full sale credit."""
    bid = open_batches(session, stocked_product.id)[0].id
    sale_result, sale_errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["4"],
        prices=["20,00"],  # 2000 cents/unit, distinct from the card price
        batch_ids=[bid],
    )
    assert sale_errors == {}
    header_id = sale_result["header"].id
    sale_op = session.scalars(
        select(Operation).where(Operation.sale_id == header_id, Operation.type == "sale")
    ).first()

    return_result, return_errors = register_return(
        session, origin_op_id=sale_op.id, qty_raw="1"
    )
    assert return_errors == {}
    assert return_result

    debit_row = session.scalars(
        select(CashMovement).where(CashMovement.category == "return")
    ).first()
    # Independent partial debit (1 x 2000), NOT the full credit (4 x 2000).
    assert debit_row.amount_cents == -(1 * 2000)
    assert debit_row.amount_cents != -sale_result["total_cents"]


def test_return_is_atomic(session, stocked_product):
    """T-15-03: after a successful return, the count of `return` ops equals
    the count of `return` cash rows (both written, one transaction)."""
    bid = open_batches(session, stocked_product.id)[0].id
    sale_result, sale_errors = register_sale(
        session,
        customer_id=None,
        codes=[stocked_product.code],
        qtys=["2"],
        prices=["15,00"],
        batch_ids=[bid],
    )
    assert sale_errors == {}
    header_id = sale_result["header"].id
    sale_op = session.scalars(
        select(Operation).where(Operation.sale_id == header_id, Operation.type == "sale")
    ).first()

    return_result, return_errors = register_return(
        session, origin_op_id=sale_op.id, qty_raw="2"
    )
    assert return_errors == {}
    assert return_result

    return_op_count = session.scalar(
        select(func.count()).select_from(Operation).where(Operation.type == "return")
    )
    return_cash_count = session.scalar(
        select(func.count()).select_from(CashMovement).where(CashMovement.category == "return")
    )
    assert return_op_count == return_cash_count == 1


# --- Plan 04: balance page render (FIN-06) ---


def test_page_empty_shows_zero(client):
    """FIN-06: GET /finance renders «Баланс кассы» with 0,00 on an empty ledger."""
    response = client.get("/finance")
    assert response.status_code == 200
    assert "Баланс кассы" in response.text
    assert "0,00" in response.text


def test_page_shows_balance(client, session):
    """FIN-06: GET /finance renders the live balance via the cents filter."""
    record_cash_movement(session, category="sale", amount_cents=12500)
    response = client.get("/finance")
    assert response.status_code == 200
    assert "125,00" in response.text


def test_mobile_page_shows_balance(mobile_client_factory, session):
    """FIN-06: GET /m/finance mirrors the desktop page on its own router."""
    from app.routes import mobile_finance

    record_cash_movement(session, category="sale", amount_cents=12500)
    mobile_client = mobile_client_factory(mobile_finance.router)
    response = mobile_client.get("/m/finance")
    assert response.status_code == 200
    assert "Баланс кассы" in response.text
    assert "125,00" in response.text
