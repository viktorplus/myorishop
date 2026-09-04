"""SYNC-10 / SYNC-11: the `POST /api/sync/push` schema-version gate (plan 33-01).

Wave-0 RED scaffold, same idiom as 30-01 / 31-01 / 32-01: the not-yet-existing
symbols (`app.services.sync.push_schema_ok`, `app.routes.sync.SCHEMA_AHEAD_ERROR`)
are imported INSIDE the test bodies so pytest COLLECTION stays green while
EXECUTION is red until Tasks 2 and 3 land.

Why the gate exists: `merge._ledger_row` projects an incoming batch through the
RECEIVER's columns, so a client that self-updates ahead of the server pushes a
column the server does not have, the server silently drops the key, returns 200
and the client stamps `synced_at` — permanent loss behind a success response
(33-RESEARCH.md V2). The gate refuses an AHEAD client with 409 before any DB
touch, which is what keeps those rows unsynced and re-pushable.

D-03: every test here pins the schema versions EXPLICITLY (an injected header
`schema_version` plus a monkeypatched `current_schema_version`). Both
`tests/conftest.py:27` and `:294` build their schema with
`Base.metadata.create_all`, so there is no `alembic_version` table and
`current_schema_version` returns "" on BOTH sides — without the pinning, the
predicate's empty-string escape hatch would make every assertion here vacuous.

Coverage: VA-1 (ahead → 409 naming both versions, behind → 200 and merged) and
VA-2 (a refused push leaves every client row `synced_at IS NULL` and does not
advance `sync_state.last_sync_at`).
"""

import pytest
from sqlalchemy import func, select
from test_merge import build_ndjson

from app.models import Operation
from app.routes import sync as sync_route
from app.services import rate_limit, sync_client

NDJSON = "application/x-ndjson"

# D-03: the three pinned revisions. Fixed-width numeric Alembic ids, so the
# lexicographic comparison in `push_schema_ok` is meaningful (D-04 tripwire:
# tests/test_migrations.py::test_revision_ids_are_fixed_width, plan 33-03).
SERVER_SCHEMA = "0027"
AHEAD_SCHEMA = "0028"
BEHIND_SCHEMA = "0026"


@pytest.fixture(autouse=True)
def _fresh_buckets():
    """Reset the shared rate-limit buckets so limits cannot leak between tests."""
    rate_limit.reset_buckets()
    yield
    rate_limit.reset_buckets()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": NDJSON}


def _op_record(op_id: str, *, product_id: str, batch_id: str | None, seq: int = 1) -> dict:
    """One verbatim `operation` NDJSON record (mirrors the test_sync_api factory)."""
    return {
        "kind": "operation",
        "id": op_id,
        "type": "receipt",
        "product_id": product_id,
        "qty_delta": 5,
        "unit_cost_cents": 1000,
        "unit_price_cents": None,
        "payload": None,
        "sale_id": None,
        "batch_id": batch_id,
        "author_id": None,
        "device_id": "device-A",
        "seq": seq,
        "created_at": "2026-07-19T10:00:00+00:00",
        "created_by": "operator",
        "synced_at": None,
    }


def _body(header_schema: str, records: list[dict]) -> bytes:
    """NDJSON push body whose header carries an EXPLICIT `schema_version` (D-03)."""
    lines = build_ndjson(
        header_overrides={"schema_version": header_schema}, records=records
    )
    return "\n".join(lines).encode("utf-8")


def _pin_server_schema(monkeypatch, revision: str = SERVER_SCHEMA) -> None:
    """Pin the RECEIVER's revision (D-03) — create_all fixtures report "".

    Patched on `app.routes.sync`, the module that owns the gate, so the client
    half (`app.services.sync_client`) is untouched and can be pinned separately.
    """
    monkeypatch.setattr(sync_route, "current_schema_version", lambda session: revision)


# --- SYNC-10: the predicate ---------------------------------------------------


def test_push_schema_ok_accepts_behind_client():
    """D-01: the comparison is ASYMMETRIC — a client BEHIND the receiver merges."""
    from app.services.sync import push_schema_ok

    assert push_schema_ok(BEHIND_SCHEMA, SERVER_SCHEMA) is True


def test_push_schema_ok_accepts_equal():
    """The ordinary fleet state: client and server on the same revision."""
    from app.services.sync import push_schema_ok

    assert push_schema_ok(SERVER_SCHEMA, SERVER_SCHEMA) is True


def test_push_schema_ok_refuses_ahead_client():
    """D-01: only an AHEAD client is refused — that is the data-loss direction."""
    from app.services.sync import push_schema_ok

    assert push_schema_ok(AHEAD_SCHEMA, SERVER_SCHEMA) is False


def test_push_schema_ok_escape_hatch_both_sides():
    """D-03: the hatch is on BOTH sides, unlike `offline.schema_version_ok`.

    A create_all fixture reports "" on the client half as well as the server
    half, so a server-only hatch would redden the whole shipped sync suite.
    """
    from app.services.sync import push_schema_ok

    assert push_schema_ok("", SERVER_SCHEMA) is True
    assert push_schema_ok(AHEAD_SCHEMA, "") is True
    assert push_schema_ok("", "") is True


# --- VA-1: the route gate -----------------------------------------------------


def test_ahead_client_push_returns_409(device_client, session, product, batch, monkeypatch):
    """VA-1: an AHEAD client is refused with 409 + the RU constant naming BOTH
    versions, and not a single row reaches the ledger."""
    from app.routes.sync import SCHEMA_AHEAD_ERROR

    _pin_server_schema(monkeypatch)
    body = _body(
        AHEAD_SCHEMA,
        [_op_record("op-ahead", product_id=product.id, batch_id=batch.id)],
    )

    resp = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )

    assert resp.status_code == 409
    assert resp.json()["detail"] == SCHEMA_AHEAD_ERROR.format(
        client=AHEAD_SCHEMA, server=SERVER_SCHEMA
    )
    assert session.scalar(select(func.count()).select_from(Operation)) == 0


def test_behind_client_push_merges(device_client, session, product, batch, monkeypatch):
    """VA-1: a BEHIND client still merges (D-01) — its rows land with the new
    column NULL and bucket via the read-time COALESCE (DATE-08)."""
    _pin_server_schema(monkeypatch)
    body = _body(
        BEHIND_SCHEMA,
        [_op_record("op-behind", product_id=product.id, batch_id=batch.id)],
    )

    resp = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )

    assert resp.status_code == 200
    assert resp.json()["operations_inserted"] == 1


# --- VA-2 / SYNC-11: a refused push loses nothing -----------------------------


def test_refused_push_leaves_rows_unsynced(
    sync_driver_pair, session, stocked_product, monkeypatch
):
    """VA-2 / SYNC-11 (D-07 — a TEST, not code): after a 409 every client row is
    still `synced_at IS NULL`, nothing landed on the server, and
    `sync_state.last_sync_at` did not advance.

    Both halves are pinned separately: the receiver at 0027 (route module), the
    driver at 0028 (client module), so the real driver really pushes an AHEAD
    header across the ASGI boundary. `synced_at` is stamped only after
    `raise_for_status()` (`sync_client.py:376,384-393`) and `last_sync_at`
    advances only for `ok`/`partial` (`routes/sync.py:269-273`).
    """
    pair = sync_driver_pair
    _pin_server_schema(monkeypatch)
    monkeypatch.setattr(
        sync_client, "current_schema_version", lambda session: AHEAD_SCHEMA
    )

    last_sync_before = sync_client.get_or_create_sync_state(session).last_sync_at
    unsynced_before = sync_client.unsynced_count(session)
    assert unsynced_before > 0

    result = sync_client.run_sync_once(session, client=pair.client)

    # Plan 33-02 (D-08) gave the 409 its own status: when this test was written
    # a refusal still collapsed into the generic `error`. The SYNC-11 property
    # below — not the status label — is what this case exists to pin.
    assert result.status == "schema_mismatch"
    assert result.pushed == 0
    session.expire_all()
    assert sync_client.unsynced_count(session) == unsynced_before
    stamped = session.scalar(
        select(func.count())
        .select_from(Operation)
        .where(Operation.synced_at.is_not(None))
    )
    assert stamped == 0
    server_ops = pair.server_session.scalar(select(func.count()).select_from(Operation))
    assert server_ops == 0
    assert sync_client.get_or_create_sync_state(session).last_sync_at == last_sync_before
