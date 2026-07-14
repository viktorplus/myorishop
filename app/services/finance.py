"""Finance service (D-00b): the SINGLE write path for cash_movements.

record_cash_movement is the only code that inserts cash_movements rows.
Everything else reads. compute_balance is a cacheless live SUM of
amount_cents — never a cached/projected column (D-00b, Pitfall 4).
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import CASH_CATEGORIES, CashMovement


def next_seq(session: Session, device_id: str) -> int:
    """Next per-device sequence number.

    Called ONLY inside record_cash_movement's transaction (mirrors
    ledger.next_seq): single writer + WAL serializes writes;
    UNIQUE(device_id, seq) is the loud backstop against any race.
    """
    current = session.scalar(
        select(func.max(CashMovement.seq)).where(CashMovement.device_id == device_id)
    )
    return (current or 0) + 1


def record_cash_movement(
    session: Session,
    *,
    category: str,
    amount_cents: int,
    sale_id: str | None = None,
    note: str | None = None,
    commit: bool = True,
) -> CashMovement:
    """Append one immutable cash_movements row.

    This is the ONLY sanctioned write path for cash_movements (D-00b).
    Audit fields are stamped from settings, mirroring
    ledger.record_operation. amount_cents is SIGNED integer cents passed
    through as-is — callers pass a positive credit or a negative debit;
    NEVER coerce to float/Decimal (D-00b).

    WR-03: commit=False stages the row without committing so a caller can
    combine several writes into one transaction (mirrors record_operation's
    commit flag).
    """
    if category not in CASH_CATEGORIES:
        raise ValueError(f"unknown cash category: {category!r}")

    mv = CashMovement(
        id=new_id(),
        category=category,
        amount_cents=amount_cents,
        sale_id=sale_id,
        note=note,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(mv)
    if commit:
        session.commit()
    return mv


def compute_balance(session: Session) -> int:
    """Recompute the whole-till cash balance from the ledger alone (D-00b).

    Live SUM(amount_cents) — no WHERE clause, no cache. 0 on an empty
    ledger; the signed sum otherwise.
    """
    return session.scalar(select(func.coalesce(func.sum(CashMovement.amount_cents), 0)))
