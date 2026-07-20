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
