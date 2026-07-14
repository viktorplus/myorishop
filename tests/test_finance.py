"""FIN-01/02/06 append-only + balance/contract tests for the cash ledger
(Phase 15, Plan 01 + Plan 02).

Plan 02 adds app.services.finance import (compute_balance, next_seq,
record_cash_movement) now that the service exists.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import CashMovement  # noqa: F401  (CASH_CATEGORIES: contract symbol)
from app.services.finance import compute_balance, next_seq, record_cash_movement


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
