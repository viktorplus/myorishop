"""Unit tests for the pure state + presentation layer of the sync client (Plan 02).

No network here — every helper is a plain function over a `Session`. Covers the
D-10 single-row `sync_state` persistence, the D-15 fresh/clamped auto-sync config
read, the D-11 unsynced badge, and the LOCKED D-12 Russian result strings.
"""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import Batch, CashMovement, Operation, Product, Sale, SyncState
from app.services import rate_limit
from app.services.ledger import next_seq, record_operation
from app.services import sync_client
from app.services.sync_client import (
    DEFAULT_INTERVAL_SECONDS,
    MAX_INTERVAL_SECONDS,
    MIN_INTERVAL_SECONDS,
    SyncResult,
)


@pytest.fixture(autouse=True)
def _reset_rate_limit_buckets():
    """Keep the shared sync rate-limit buckets from leaking across driver tests
    (the ASGITransport driver hits the real rate-limited /api/sync/ routes)."""
    rate_limit.reset_buckets()
    yield
    rate_limit.reset_buckets()


def _mock_client(handler):
    """A sync httpx.Client over a MockTransport (offline / 5xx / scripted)."""
    return httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://sync"
    )


_MERGE_REPORT_JSON = {
    "operations_inserted": 0,
    "operations_skipped": 0,
    "cash_inserted": 0,
    "cash_skipped": 0,
    "reference_inserted": {},
    "reference_server_wins": {},
    "conflicts": [],
}


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


# --- Plan-03 Task 1: push driver + D-13 closure + stamp-after-200 + lock ------


def _author_offline_sale(session, product, batch, customer):
    """Author a fully local (offline) sale: receipt stock, a Sale header, a `sale`
    operation linked to it, and a CashMovement — so the unsynced ledger rows
    reference a locally-created Sale/Batch/Customer (the D-13 FK closure)."""
    record_operation(
        session,
        type_="receipt",
        product_id=product.id,
        qty_delta=5,
        unit_cost_cents=1000,
        unit_price_cents=1500,
        batch_id=batch.id,
    )
    sale = Sale(
        id=new_id(),
        customer_id=customer.id,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
        device_id=settings.device_id,
    )
    session.add(sale)
    session.flush()
    record_operation(
        session,
        type_="sale",
        product_id=product.id,
        qty_delta=-1,
        unit_price_cents=1500,
        sale_id=sale.id,
        batch_id=batch.id,
    )
    cash = CashMovement(
        id=new_id(),
        category="sale",
        amount_cents=1500,
        sale_id=sale.id,
        device_id=settings.device_id,
        seq=session.query(CashMovement).count() + 1,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
    session.add(cash)
    session.commit()
    return sale


def test_push_marks_synced_and_pulls(sync_driver_pair, session, stocked_product):
    """After run_sync_once every unsynced ledger row is synced_at-stamped and the
    pushed operations are present on the SERVER DB (SYNC-01)."""
    pair = sync_driver_pair
    assert sync_client.unsynced_count(session) > 0

    result = sync_client.run_sync_once(session, client=pair.client)

    assert result.status == "ok"
    assert result.pushed >= 1
    assert sync_client.unsynced_count(session) == 0  # every row stamped
    server_ops = pair.server_session.scalars(select(Operation)).all()
    assert len(server_ops) >= 1  # present on the server (crossed the boundary)


def test_push_includes_referenced_reference_rows(
    sync_driver_pair, session, product, batch, customer
):
    """D-13: an offline-authored sale (local Sale+Batch+Customer) pushes with NO FK
    failure because the body carried the FK parents in FK-dependency order."""
    pair = sync_driver_pair
    sale = _author_offline_sale(session, product, batch, customer)

    result = sync_client.run_sync_once(session, client=pair.client)

    assert result.status == "ok"  # no IntegrityError / 4xx from the server merge
    # The FK parents really landed on the (previously empty) server.
    assert pair.server_session.get(Sale, sale.id) is not None
    assert pair.server_session.get(Product, product.id) is not None
    assert pair.server_session.get(Batch, batch.id) is not None


def test_second_sync_is_noop(sync_driver_pair, session, stocked_product):
    """Idempotency: a second run with nothing newly unsynced pushes 0 and the
    server replay skips the already-merged rows (no duplicate operations)."""
    pair = sync_driver_pair
    sync_client.run_sync_once(session, client=pair.client)
    server_ops_after_first = pair.server_session.scalars(select(Operation)).all()

    second = sync_client.run_sync_once(session, client=pair.client)

    assert second.pushed == 0  # nothing left unsynced
    server_ops_after_second = pair.server_session.scalars(select(Operation)).all()
    assert len(server_ops_after_second) == len(server_ops_after_first)  # no dupes


def test_push_failure_does_not_stamp(session, stocked_product, monkeypatch):
    """Pitfall 3: a non-2xx push leaves synced_at NULL — the rows re-push next time."""
    monkeypatch.setattr(settings, "sync_server_url", "http://sync")
    monkeypatch.setattr(settings, "sync_token", "tok")
    before = sync_client.unsynced_count(session)
    assert before > 0

    def handler(request):
        return httpx.Response(500, text="boom")

    result = sync_client.run_sync_once(session, client=_mock_client(handler))

    assert result.status == "error"
    assert sync_client.unsynced_count(session) == before  # NOT stamped


def test_single_run_lock_refuses_overlap(sync_driver_pair, monkeypatch):
    """D-09: while _run_lock is held, run_sync_tick does not execute a second run —
    build_sync_client (its first side effect) is never reached."""
    def _boom():
        raise AssertionError("run_sync_tick must not execute while the lock is held")

    monkeypatch.setattr(sync_client, "build_sync_client", _boom)

    acquired = sync_client._run_lock.acquire(blocking=False)
    assert acquired
    try:
        # Must return immediately without raising (the lock is already held).
        sync_client.run_sync_tick()
    finally:
        sync_client._run_lock.release()


def test_run_sync_once_not_configured(session, monkeypatch):
    """SRV-03: a blank server URL / token short-circuits to not_configured and never
    touches the network."""
    monkeypatch.setattr(settings, "sync_server_url", "")
    monkeypatch.setattr(settings, "sync_token", "")

    def handler(request):
        raise AssertionError("the network must not be touched when unconfigured")

    result = sync_client.run_sync_once(session, client=_mock_client(handler))

    assert result.status == "not_configured"
