"""Tests for the Plan-05 interval auto-sync loop + Settings config control.

Two surfaces:
- `app.main._auto_sync_iteration` / `_auto_sync_loop` + the lifespan wiring —
  the D-06/D-07/D-08 background loop (reads config fresh, offloads off the event
  loop, swallows offline errors, cancels cleanly on shutdown).
- `POST /settings/sync` + `save_autosync_config` — the D-03/D-15 admin control
  that persists the clamped toggle + interval to the single `sync_state` row.
"""

import asyncio

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.services import sync_client

# ---------------------------------------------------------------------------
# Task 1: the lifespan interval auto-sync loop (D-06/D-07/D-08)
# ---------------------------------------------------------------------------


@pytest.fixture()
def _loop_session(engine, monkeypatch):
    """Repoint `app.main.SessionLocal` at the TEST engine so the background
    iteration reads config from the test DB, never the developer's real DB."""
    monkeypatch.setattr("app.main.SessionLocal", sessionmaker(bind=engine))


def test_iteration_auto_off_does_not_call_run_sync_tick(
    _loop_session, session, monkeypatch
):
    """Auto-sync disabled (default) → `run_sync_tick` is never called (D-15)."""
    import app.main as main

    called = []
    monkeypatch.setattr(sync_client, "run_sync_tick", lambda: called.append(True))

    interval = asyncio.run(main._auto_sync_iteration())

    assert called == []
    assert interval == 300  # DEFAULT_INTERVAL_SECONDS (fresh row)


def test_iteration_auto_on_calls_run_sync_tick(_loop_session, session, monkeypatch):
    """Auto-sync enabled → `run_sync_tick` is offloaded and called (D-07)."""
    import app.main as main
    from app.services.sync_client import get_or_create_sync_state

    row = get_or_create_sync_state(session)
    row.auto_enabled = 1
    row.auto_interval_seconds = 120
    session.commit()

    called = []
    monkeypatch.setattr(sync_client, "run_sync_tick", lambda: called.append(True))

    interval = asyncio.run(main._auto_sync_iteration())

    assert called == [True]
    assert interval == 120


def test_iteration_swallows_tick_exception(_loop_session, session, monkeypatch):
    """An exception raised by `run_sync_tick` (offline) is swallowed — the
    iteration returns the interval instead of raising (D-08, loop never dies)."""
    import app.main as main
    from app.services.sync_client import get_or_create_sync_state

    row = get_or_create_sync_state(session)
    row.auto_enabled = 1
    row.auto_interval_seconds = 300
    session.commit()

    def _boom():
        raise RuntimeError("offline")

    monkeypatch.setattr(sync_client, "run_sync_tick", _boom)

    # Must NOT raise.
    interval = asyncio.run(main._auto_sync_iteration())

    assert interval == 300


def test_lifespan_starts_and_cancels_loop_cleanly(engine, session, monkeypatch):
    """`with TestClient(app)` runs the real lifespan: the auto-sync task starts
    after the startup backup and is cancelled cleanly on exit — no hang, no
    raise (D-06/D-08). `run_sync_tick` is neutralised so no network is touched."""
    from fastapi.testclient import TestClient

    from app.db import get_session
    from app.main import app
    from app.services.security import auth_guard

    monkeypatch.setattr(settings, "backup_on_startup", False)
    # Keep the background loop from touching the network or the real DB: the
    # config read always reports disabled, so the tick is a no-op that just
    # sleeps until the lifespan cancels it.
    monkeypatch.setattr(sync_client, "read_autosync_config", lambda _s: (False, 3600))
    monkeypatch.setattr("app.main.SessionLocal", sessionmaker(bind=engine))

    def override_get_session():
        yield session

    def override_auth_guard(request):
        return None

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[auth_guard] = override_auth_guard
    try:
        # Entering runs startup (create_task); exiting runs shutdown
        # (task.cancel() + suppressed CancelledError). Neither may hang/raise.
        with TestClient(app):
            pass
    finally:
        app.dependency_overrides.clear()
