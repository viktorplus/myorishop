"""UI wiring tests for the manual sync surface (Phase 29, Plan 04).

Covers the header nav trigger + status/badge partial rendered on every desktop
page (D-01), the `POST /sync/run` OOB refresh (D-02), the D-11 badge visibility
(hidden at 0, shown when > 0 — SYNC-07), and the SYNC-06 non-blocking failure
contract (an offline / not-configured sync returns 200 with a plain RU partial,
never a 5xx that base.html's htmx-config would refuse to swap).

The `client` fixture authenticates as an admin and overrides `get_session` (so
`/sync/run` and `_render_sync_status` see the test DB). The base.html context
processor opens its OWN `SessionLocal()`, so the `_ctx_session` fixture repoints
that name at the test engine for the first-paint (GET) assertions.
"""

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Operation
from app.services import sync_client
from app.services.sync_client import SyncResult


def _make_operation(session, product, *, synced_at=None):
    """Insert one unsynced ledger Operation (INSERT is trigger-safe)."""
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


class _DummyClient:
    """Stand-in for the httpx.Client the handler builds — only needs close()."""

    def close(self):
        pass


@pytest.fixture()
def _ctx_session(engine, monkeypatch):
    """Point the base.html sync context processor's `SessionLocal` at the TEST
    engine so its first-paint badge/status read reflects the test DB (the handler
    itself uses the get_session-overridden test session, so this only matters for
    GET page renders)."""
    monkeypatch.setattr("app.routes.SessionLocal", sessionmaker(bind=engine))


def _configure_server(monkeypatch):
    """Set a non-blank server URL + token so the handler does NOT short-circuit to
    the not_configured no-op and instead exercises the driver path."""
    monkeypatch.setattr(settings, "sync_server_url", "http://sync")
    monkeypatch.setattr(settings, "sync_token", "test-token")


# --- Header wiring (D-01): trigger + status on every desktop page ------------


def test_header_shows_sync_trigger_and_status(client, _ctx_session, monkeypatch):
    """Every desktop page carries the «Синхронизировать» trigger + #sync-status
    (D-01) — glanceable header chrome, not Settings-only.

    quick-260721-egc: the widget is now conditional on sync_server_url being
    configured (a paired client), so this test must set it explicitly — the
    test-suite default is "" (unconfigured, like the central server)."""
    monkeypatch.setattr(settings, "sync_server_url", "http://sync")
    html = client.get("/history").text
    assert 'hx-post="/sync/run"' in html  # the manual trigger posts to the route
    assert "Синхронизировать" in html  # D-01 CTA copy
    assert 'id="sync-status"' in html  # the status element for the OOB refresh
    assert 'id="sync-badge"' in html  # the badge OOB target is always present


def test_header_hides_sync_trigger_when_not_configured(client, _ctx_session, monkeypatch):
    """quick-260721-egc: on an instance with no sync_server_url (the central
    server, or an unpaired client) the header must not show the sync widget —
    it would otherwise render "Синхронизация не настроена" forever."""
    monkeypatch.setattr(settings, "sync_server_url", "")
    html = client.get("/history").text
    assert "Синхронизировать" not in html
    assert 'id="sync-status"' not in html


def test_badge_hidden_when_zero(client, _ctx_session, monkeypatch):
    """SYNC-07 / D-12: with nothing unsynced the #sync-badge container renders but
    the visible count span is absent (hidden at 0).

    quick-260721-egc: the badge lives inside the now-conditional sync widget, so
    this needs a configured sync_server_url (paired client) to render at all."""
    monkeypatch.setattr(settings, "sync_server_url", "http://sync")
    html = client.get("/history").text
    assert 'id="sync-badge"' in html  # container present so an OOB swap can clear it
    assert "sync-badge-count" not in html  # no visible badge at 0
    assert "padding:4px 8px" not in html  # the badge geometry is not rendered


def test_badge_visible_when_unsynced(client, session, product, _ctx_session, monkeypatch):
    """SYNC-07 / D-11: an unsynced ledger row makes the amber count badge appear
    with the numeric count.

    quick-260721-egc: needs sync_server_url configured, same as above."""
    monkeypatch.setattr(settings, "sync_server_url", "http://sync")
    _make_operation(session, product)  # one unsynced Operation → count == 1
    html = client.get("/history").text
    assert "sync-badge-count" in html  # visible badge span rendered
    assert "padding:4px 8px" in html  # UI-SPEC badge geometry (reused token values)
    assert ">1<" in html  # the integer count


# --- POST /sync/run: OOB refresh + non-blocking failure (D-02, SYNC-06) ------


def test_sync_run_returns_oob_partial(client, monkeypatch):
    """D-02: a successful manual sync returns 200 with an hx-swap-oob partial —
    an in-place refresh, no full page reload."""
    _configure_server(monkeypatch)
    monkeypatch.setattr(sync_client, "build_sync_client", lambda: _DummyClient())
    monkeypatch.setattr(
        sync_client,
        "run_sync_once",
        lambda session, *, client: SyncResult(status="ok", pushed=2, pulled=3),
    )
    resp = client.post("/sync/run")
    assert resp.status_code == 200
    assert 'hx-swap-oob="true"' in resp.text  # OOB refresh (D-02)
    assert 'id="sync-status"' in resp.text
    assert "Синхронизировано: отправлено 2, получено 3" in resp.text  # D-12


def test_offline_run_returns_200_ru(client, monkeypatch):
    """SYNC-06: an offline sync returns 200 with the plain RU «Нет связи с
    сервером», never a 5xx that would break the page."""
    _configure_server(monkeypatch)
    monkeypatch.setattr(sync_client, "build_sync_client", lambda: _DummyClient())
    monkeypatch.setattr(
        sync_client,
        "run_sync_once",
        lambda session, *, client: SyncResult(status="offline"),
    )
    resp = client.post("/sync/run")
    assert resp.status_code == 200  # non-blocking (never 5xx)
    assert "Нет связи с сервером" in resp.text  # D-12 offline string
    assert 'hx-swap-oob="true"' in resp.text


def test_not_configured_run_is_a_noop(client, monkeypatch):
    """SRV-03: a blank server URL/token yields the not-configured partial at 200
    and never touches the network (build_sync_client is not called)."""
    monkeypatch.setattr(settings, "sync_server_url", "")
    monkeypatch.setattr(settings, "sync_token", "")

    def _boom():
        raise AssertionError("build_sync_client must not run when not configured")

    monkeypatch.setattr(sync_client, "build_sync_client", _boom)
    resp = client.post("/sync/run")
    assert resp.status_code == 200
    assert "Синхронизация не настроена" in resp.text  # SRV-03 no-op copy


def test_lock_hit_returns_locked_partial(client, monkeypatch):
    """D-09: a manual click while the shared _run_lock is held returns the
    «Синхронизация уже выполняется» partial (no second run)."""
    _configure_server(monkeypatch)

    def _boom():
        raise AssertionError("no sync must run while the lock is held")

    monkeypatch.setattr(sync_client, "build_sync_client", _boom)
    assert sync_client._run_lock.acquire(blocking=False)  # hold the lock
    try:
        resp = client.post("/sync/run")
    finally:
        sync_client._run_lock.release()
    assert resp.status_code == 200
    assert "Синхронизация уже выполняется" in resp.text  # D-09 lock-hit copy


def test_context_processor_never_breaks_page(client, monkeypatch):
    """SRV-03: a sync-state hiccup (SessionLocal raises) must not break page
    rendering — the page still returns 200 with the neutral never-synced line.

    quick-260721-egc: needs sync_server_url configured so the (now-conditional)
    widget is even rendered — otherwise this assertion couldn't distinguish the
    exception path from the "not a sync client" path."""
    monkeypatch.setattr(settings, "sync_server_url", "http://sync")

    def _boom():
        raise RuntimeError("sync_state unavailable")

    monkeypatch.setattr("app.routes.SessionLocal", _boom)
    resp = client.get("/history")
    assert resp.status_code == 200  # page still renders
    assert "Ещё не синхронизировано" in resp.text  # neutral default line


# --- Nav server-mode indicator (SRV-01/02) ------------------------------------


def test_nav_server_mode_on_postgres_db_url(client, _ctx_session, monkeypatch):
    """quick-260721-egc: a PostgreSQL-backed database_url (the deployed central
    server) renders the nav with the server-mode class so it can't be mistaken
    for a local SQLite client."""
    monkeypatch.setattr(settings, "database_url", "postgresql+psycopg://u:p@host/db")
    html = client.get("/history").text
    assert 'class="server-mode"' in html


def test_nav_default_mode_on_sqlite_db_url(client, _ctx_session):
    """quick-260721-egc: the normal test-suite condition (sqlite database_url,
    unchanged) renders the nav with no server-mode class — every local client
    stays pixel-identical to before this change."""
    html = client.get("/history").text
    assert 'class="server-mode"' not in html
