"""FIN-01/02/06 append-only tests for the cash ledger (Phase 15, Plan 01).

IMPORTANT: this module imports only app.models / app.core / app.config —
no app.services.finance (that service lands in Plan 02). Keeping this
module free of that import keeps it collectible at Wave 1.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import CashMovement  # noqa: F401  (CASH_CATEGORIES: contract symbol)


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
