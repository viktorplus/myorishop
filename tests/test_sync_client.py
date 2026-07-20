"""Unit tests for the pure state + presentation layer of the sync client (Plan 02).

No network here — every helper is a plain function over a `Session`. Covers the
D-10 single-row `sync_state` persistence, the D-15 fresh/clamped auto-sync config
read, the D-11 unsynced badge, and the LOCKED D-12 Russian result strings.
"""

from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import CashMovement, Operation, SyncState
from app.services import sync_client
from app.services.sync_client import (
    DEFAULT_INTERVAL_SECONDS,
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    SyncResult,
)


def _make_operation(session, product, *, synced_at=None):
    """Insert one ledger Operation directly (INSERT is trigger-safe) referencing
    the seeded product; unsynced unless `synced_at` is stamped."""
    op = Operation(
        id=new_id(),
        type="sale",
        product_id=product.id,
        qty_delta=-1,
        device_id=settings.device_id,
        seq=session.query(Operation).count() + 1,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
        synced_at=synced_at,
    )
    session.add(op)
    session.commit()
    return op


def _make_cash_movement(session, *, synced_at=None):
    """Insert one CashMovement directly; unsynced unless `synced_at` is stamped."""
    cash = CashMovement(
        id=new_id(),
        category="sale",
        amount_cents=1000,
        device_id=settings.device_id,
        seq=session.query(CashMovement).count() + 1,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
        synced_at=synced_at,
    )
    session.add(cash)
    session.commit()
    return cash

# --- Task 1: state layer (get_or_create / record_sync_result / read_autosync_config) ---


def test_get_or_create_sync_state_idempotent(session):
    """First call inserts the id=1 singleton with defaults; a second call returns
    the SAME row — never a second one (D-10 single-row invariant)."""
    first = sync_client.get_or_create_sync_state(session)
    assert first.id == 1
    assert first.auto_enabled == 0
    assert first.auto_interval_seconds == DEFAULT_INTERVAL_SECONDS

    second = sync_client.get_or_create_sync_state(session)
    assert second.id == 1
    # Exactly one row exists.
    assert session.query(SyncState).count() == 1


def test_record_sync_result_persists_across_restart(session, engine):
    """record_sync_result writes status/result/last_sync_at onto id=1, and the
    result survives a fresh Session on the same DB (D-10 survives a restart)."""
    stamp = utcnow_iso()
    sync_client.record_sync_result(
        session,
        status="ok",
        last_result="Синхронизировано, изменений нет",
        last_sync_at=stamp,
    )
    # The helper does NOT commit (caller owns the transaction) — commit here.
    session.commit()

    fresh = sessionmaker(bind=engine)
    with fresh() as other:
        row = other.get(SyncState, 1)
        assert row is not None
        assert row.last_status == "ok"
        assert row.last_result == "Синхронизировано, изменений нет"
        assert row.last_sync_at == stamp


def test_record_sync_result_writes_on_error(session):
    """The single exit point records a FAILURE as reliably as a success (D-10):
    status='error' still persists (T-29-08)."""
    sync_client.record_sync_result(
        session,
        status="error",
        last_result="Ошибка сервера, попробуйте позже",
        last_sync_at=None,
    )
    row = sync_client.get_or_create_sync_state(session)
    assert row.last_status == "error"
    assert row.last_result == "Ошибка сервера, попробуйте позже"
    assert row.last_sync_at is None


def test_read_autosync_config_fresh_and_clamped(session):
    """Fresh row → (False, 300). A too-low interval clamps up to 60; a too-high
    one clamps down to 3600 (D-15). Read fresh from the row each call (D-08)."""
    assert sync_client.read_autosync_config(session) == (False, DEFAULT_INTERVAL_SECONDS)

    row = sync_client.get_or_create_sync_state(session)
    row.auto_enabled = 1
    row.auto_interval_seconds = 30
    session.flush()
    assert sync_client.read_autosync_config(session) == (True, MIN_INTERVAL_SECONDS)

    row.auto_interval_seconds = 7200
    session.flush()
    assert sync_client.read_autosync_config(session) == (True, MAX_INTERVAL_SECONDS)


# --- Task 2: unsynced badge (D-11) + D-12 Russian result formatter ---


def test_unsynced_count(session, product):
    """0 on an empty ledger; 2 unsynced ops + 1 unsynced cash → 3; a synced_at-
    stamped row is NOT counted (D-11)."""
    assert sync_client.unsynced_count(session) == 0

    _make_operation(session, product)
    _make_operation(session, product)
    _make_cash_movement(session)
    assert sync_client.unsynced_count(session) == 3

    # A stamped (already-synced) row must be excluded from the badge.
    _make_operation(session, product, synced_at=utcnow_iso())
    assert sync_client.unsynced_count(session) == 3


def test_result_messages(session):
    """Every LOCKED D-12 Russian string renders byte-exact, plus the two secondary
    UI-SPEC states and the never-synced last-sync line."""
    tz = settings.display_tz  # Europe/Moscow

    # No sync_state yet → never-synced line.
    msg, last = sync_client.format_sync_message(
        SyncResult(status="ok", pushed=12, pushed_total=12, pulled=5), None, tz
    )
    assert msg == "Синхронизировано: отправлено 12, получено 5"
    assert last == "Ещё не синхронизировано"

    # ok, no changes.
    msg, _ = sync_client.format_sync_message(
        SyncResult(status="ok", pushed=0, pulled=0), None, tz
    )
    assert msg == "Синхронизировано, изменений нет"

    # partial.
    msg, _ = sync_client.format_sync_message(
        SyncResult(status="partial", pushed=8, pushed_total=12), None, tz
    )
    assert msg == "Синхронизировано частично: отправлено 8 из 12"

    # offline.
    msg, _ = sync_client.format_sync_message(SyncResult(status="offline"), None, tz)
    assert msg == "Нет связи с сервером"

    # error.
    msg, _ = sync_client.format_sync_message(SyncResult(status="error"), None, tz)
    assert msg == "Ошибка сервера, попробуйте позже"

    # Secondary UI-SPEC states.
    msg, _ = sync_client.format_sync_message(SyncResult(status="locked"), None, tz)
    assert msg == "Синхронизация уже выполняется"
    msg, _ = sync_client.format_sync_message(
        SyncResult(status="not_configured"), None, tz
    )
    assert msg == "Синхронизация не настроена"


def test_last_sync_line_in_moscow(session):
    """The last-sync line renders a stored UTC ISO time in Europe/Moscow (D-12).

    11:32 UTC on 2026-07-20 is 14:32 MSK (UTC+3)."""
    row = sync_client.get_or_create_sync_state(session)
    row.last_sync_at = "2026-07-20T11:32:00+00:00"
    session.flush()

    _, last = sync_client.format_sync_message(
        SyncResult(status="ok", pushed=1, pulled=0), row, settings.display_tz
    )
    assert last == "Последняя синхронизация: 20.07.2026 14:32"
