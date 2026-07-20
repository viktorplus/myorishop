"""Pure state + presentation layer for the online sync client (Phase 29, Plan 02).

Everything here is a plain function over a SQLAlchemy `Session` — NO network, NO
httpx. The Plan-03 network driver consumes these helpers so its own code only has
to wire push/pull:

- `SyncResult` — the value object the driver returns and the formatter renders.
- `get_or_create_sync_state` / `record_sync_result` — the single-row `sync_state`
  (id=1) persistence (D-10). The result is written from ONE exit point after every
  attempt, so a failure is recorded as reliably as a success and survives an app
  restart. Portable SELECT-then-INSERT — no dialect upsert.
- `read_autosync_config` — reads the D-15 auto-sync toggle + interval FRESH from
  the row (so flipping the toggle takes effect on the next tick, D-08) and clamps
  the interval into `MIN_INTERVAL_SECONDS..MAX_INTERVAL_SECONDS`.
- `unsynced_count` — the D-11 badge: `COUNT(*) WHERE synced_at IS NULL` across
  `Operation` + `CashMovement` (the caller hides the badge at 0).
- `format_sync_message` — the LOCKED D-12 Russian result strings, with the
  last-sync line rendered in `settings.display_tz` (Europe/Moscow).

Security (T-29-07): `format_sync_message` renders ONLY the fixed D-12 strings plus
integer counts — never raw server error bytes and never the sync token. Callers
must pass a fixed RU string as `last_result`, never raw exception text.
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import iso_to_local
from app.models import CashMovement, Operation, SyncState

# D-15: the interval is clamped into this range in the service (a single reseller
# needs neither sub-minute sync nor an unbounded gap). 300s (5 min) is the default.
MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 3600
DEFAULT_INTERVAL_SECONDS = 300

# Defensive truncation width for last_result — mirrors SyncState.last_result
# String(300) so an over-long RU string can never overflow the column.
_LAST_RESULT_MAX = 300


@dataclass(frozen=True)
class SyncResult:
    """The outcome of one sync attempt — returned by the Plan-03 driver, rendered
    by `format_sync_message`.

    `status` is one of: ``ok`` | ``partial`` | ``offline`` | ``error`` |
    ``locked`` | ``not_configured``.
    """

    status: str
    pushed: int = 0
    pushed_total: int = 0
    pulled: int = 0


def get_or_create_sync_state(session: Session) -> SyncState:
    """Return the id=1 `sync_state` singleton, inserting it with defaults if absent.

    Portable SELECT-then-INSERT (no `INSERT OR REPLACE`) — this is the D-10
    single-row bookkeeping row. Flushes (not commits) the new row so the caller's
    transaction stays in charge.
    """
    row = session.get(SyncState, 1)
    if row is None:
        row = SyncState(
            id=1,
            auto_enabled=0,
            auto_interval_seconds=DEFAULT_INTERVAL_SECONDS,
        )
        session.add(row)
        session.flush()
    return row


def record_sync_result(
    session: Session,
    *,
    status: str,
    last_result: str,
    last_sync_at: str | None,
) -> None:
    """Upsert the D-10 result columns (last_status / last_result / last_sync_at)
    onto the id=1 row.

    Does NOT commit — the driver (Plan 03) owns the transaction around its single
    exit point (D-10 "written in a finally"), so a failure is recorded as reliably
    as a success. `last_result` MUST already be a fixed RU string (never raw
    exception text, T-29-07); it is defensively truncated to the column width.
    """
    row = get_or_create_sync_state(session)
    row.last_status = status
    row.last_result = last_result[:_LAST_RESULT_MAX]
    row.last_sync_at = last_sync_at


def _clamp_interval(value: int | None) -> int:
    """Force an interval into `MIN_INTERVAL_SECONDS..MAX_INTERVAL_SECONDS` (D-15).

    A None/invalid value falls back to `DEFAULT_INTERVAL_SECONDS`.
    """
    if value is None:
        return DEFAULT_INTERVAL_SECONDS
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL_SECONDS
    return max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, seconds))


def read_autosync_config(session: Session) -> tuple[bool, int]:
    """Return `(enabled, interval_seconds)` read FRESH from the `sync_state` row.

    Read fresh each call (D-08 — flipping the toggle / changing the interval takes
    effect on the next tick) and clamp the interval into 60..3600 (D-15).
    """
    row = get_or_create_sync_state(session)
    return bool(row.auto_enabled), _clamp_interval(row.auto_interval_seconds)


def unsynced_count(session: Session) -> int:
    """The D-11 badge: `COUNT(*) WHERE synced_at IS NULL` across the ledger.

    Sums the unsynced `Operation` + `CashMovement` rows. Backed by the Plan-01
    `ix_operations_unsynced` / `ix_cash_movements_unsynced` partial indexes so the
    count stays cheap as history grows (T-29-09). The caller hides the badge at 0.
    """
    ops = (
        session.scalar(
            select(func.count())
            .select_from(Operation)
            .where(Operation.synced_at.is_(None))
        )
        or 0
    )
    cash = (
        session.scalar(
            select(func.count())
            .select_from(CashMovement)
            .where(CashMovement.synced_at.is_(None))
        )
        or 0
    )
    return ops + cash


def format_sync_message(
    result: SyncResult, sync_state: SyncState | None, tz: str
) -> tuple[str, str]:
    """Render the LOCKED D-12 Russian `(status_message, last_sync_line)` pair.

    `status_message` is chosen from `result.status` + the integer counts, using the
    D-12 strings VERBATIM. `last_sync_line` renders the stored UTC ISO
    `sync_state.last_sync_at` in `tz` (Europe/Moscow), or "Ещё не синхронизировано"
    when it is None.

    T-29-07 / V7: ONLY these fixed strings + integer counts ever cross this
    boundary — raw server error bytes and the sync token can never be interpolated.
    """
    status = result.status
    if status == "ok":
        if result.pushed == 0 and result.pulled == 0:
            message = "Синхронизировано, изменений нет"
        else:
            message = (
                f"Синхронизировано: отправлено {result.pushed}, "
                f"получено {result.pulled}"
            )
    elif status == "partial":
        message = (
            f"Синхронизировано частично: отправлено {result.pushed} "
            f"из {result.pushed_total}"
        )
    elif status == "offline":
        message = "Нет связи с сервером"
    elif status == "locked":
        # D-09: a manual click landed while a tick is already running.
        message = "Синхронизация уже выполняется"
    elif status == "not_configured":
        # SRV-03: blank server URL / token — a fresh install is a no-op.
        message = "Синхронизация не настроена"
    else:
        # `error` and any unexpected status collapse to the generic D-12 error.
        message = "Ошибка сервера, попробуйте позже"

    last_sync_at = sync_state.last_sync_at if sync_state is not None else None
    if last_sync_at:
        last_sync_line = f"Последняя синхронизация: {iso_to_local(last_sync_at, tz)}"
    else:
        last_sync_line = "Ещё не синхронизировано"
    return message, last_sync_line
