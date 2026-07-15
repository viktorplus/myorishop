"""Finance service (D-00b): the SINGLE write path for cash_movements.

record_cash_movement is the only code that inserts cash_movements rows.
Everything else reads. compute_balance is a cacheless live SUM of
amount_cents — never a cached/projected column (D-00b, Pitfall 4).
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core import new_id, to_cents, utcnow_iso
from app.models import CASH_BUCKETS, CASH_CATEGORIES, CashMovement

# RU validation messages (UI-SPEC Copywriting Contract). The service is the
# security-critical tier (V5): every message is returned WITHOUT any HTML.
AMOUNT_ERROR = "Введите сумму больше нуля."
CATEGORY_ERROR = "Выберите категорию."
NOTE_REQUIRED_ERROR = "Укажите комментарий."
SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."

# D-04: these two manual categories require a non-blank free-text comment.
_NOTE_REQUIRED_CATEGORIES = frozenset({"withdrawal_other", "deposit_correction"})


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


def record_manual_movement(
    session: Session,
    *,
    category: str,
    amount_raw: str,
    note: str,
    confirm: str = "",
) -> tuple[dict | None, dict[str, str]]:
    """Manual cash entry (D-02): the thin write wrapper around the single path.

    Mirrors writeoffs.register_writeoff's validate -> gate -> single-write
    order and returns the same ``(result, errors)`` shape so the routes branch
    identically. Everything client-supplied is untrusted (V5): the category
    allow-list, the amount parse, the sign, the mandatory-comment rule and the
    negative-balance gate are all enforced HERE, never in the route.

    Success: ``({"movement": mv}, {})``. Validation failure: ``(None, errors)``
    with RU messages and ZERO writes. The negative-balance warn returns
    ``({"negative_balance": {"balance", "amount"}}, {})`` with ZERO writes when
    ``confirm != "1"`` and the withdrawal would drive the balance below zero;
    ``confirm == "1"`` writes and the balance may go negative (D-05).
    """
    errors: dict[str, str] = {}

    # (1) Direction from bucket membership — a system key ("sale"/"return") or an
    # unknown key is NOT a manual category (T-16-02, defence-in-depth on top of
    # record_cash_movement's CASH_CATEGORIES guard).
    is_withdrawal = category in CASH_BUCKETS["withdrawal"]
    is_deposit = category in CASH_BUCKETS["deposit"]
    if not (is_withdrawal or is_deposit):
        errors["category"] = CATEGORY_ERROR

    # (2) Parse the amount via the ONLY sanctioned money parser; reject
    # blank/zero/negative/non-integer server-side (T-16-01/D-02a).
    parsed = 0
    try:
        parsed = to_cents(amount_raw)
    except ValueError:
        errors["amount"] = AMOUNT_ERROR
    else:
        if parsed <= 0:
            errors["amount"] = AMOUNT_ERROR

    # (3) ZERO writes on any validation failure.
    if errors:
        return None, errors

    # (4) Apply the sign SERVER-SIDE — never trust a client sign (T-16-03/D-02a).
    amount_cents = -parsed if is_withdrawal else parsed

    # (5) Mandatory-comment rule (T-16-04/D-04).
    if category in _NOTE_REQUIRED_CATEGORIES and not note.strip():
        return None, {"note": NOTE_REQUIRED_ERROR}

    # (6) Negative-balance warn-but-allow gate (T-16-05/D-05) — withdrawals only;
    # the would-be balance is recomputed LIVE, never trusted from the client.
    if is_withdrawal and confirm != "1" and compute_balance(session) + amount_cents < 0:
        return (
            {"negative_balance": {"balance": compute_balance(session), "amount": -amount_cents}},
            {},
        )

    # (7) Single write path — one row (Pitfall 8), no multi-write machinery.
    try:
        mv = record_cash_movement(
            session,
            category=category,
            amount_cents=amount_cents,
            note=note.strip() or None,
            commit=True,
        )
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}

    return {"movement": mv}, {}


def compute_balance(session: Session) -> int:
    """Recompute the whole-till cash balance from the ledger alone (D-00b).

    Live SUM(amount_cents) — no WHERE clause, no cache. 0 on an empty
    ledger; the signed sum otherwise.
    """
    return session.scalar(select(func.coalesce(func.sum(CashMovement.amount_cents), 0)))
