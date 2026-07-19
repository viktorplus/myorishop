"""Endpoint auth + push tests for the sync API (SYNC-09, ROADMAP SC-2).

This module MUST build on `device_client` / `anon_client`: the default `client`
fixture overrides `auth_guard` WHOLESALE, which would make the `/api/sync/`
bypass — the single highest-consequence line in the phase — untestable. Every
test here therefore exercises the REAL guard with a REAL device token.

Coverage:
- valid / missing / unknown / revoked token → 200 / 401 (T-28-02);
- BOTH cross-auth negatives: a device token cannot reach the HTML tree and a
  browser session cannot reach the sync tree (T-28-03, Pitfall 4);
- idempotent replay (SYNC-02), all-or-nothing rollback (T-28-19);
- body cap → 413 (T-28-04), rate limit → 429 (T-28-12), malformed → 400 without
  echoing attacker bytes (T-28-07 / V7);
- a successful push stamps last_used_at.

CLAUDE.md safety: token plaintexts come from the fixture (freshly minted per
test) and are sent only in the Authorization header, never a query string.
"""

import json

import pytest
from sqlalchemy import func, select

from app.core import new_id
from app.models import DeviceToken, Operation, User
from app.routes import sync as sync_route
from app.services import auth, devices, merge, rate_limit

NDJSON = "application/x-ndjson"


@pytest.fixture(autouse=True)
def _fresh_buckets():
    """Reset the shared rate-limit buckets so limits cannot leak between tests."""
    rate_limit.reset_buckets()
    yield
    rate_limit.reset_buckets()


def _header_line() -> dict:
    return {
        "kind": "header",
        "format_version": merge.FORMAT_VERSION,
        "schema_version": "0019",
        "source_device_id": "device-A",
        "generated_at": "2026-07-19T10:00:00+00:00",
        "counts": {},
    }


def _ndjson(records: list[dict]) -> bytes:
    """Build a valid NDJSON body (header first, then one line per record dict)."""
    lines = [json.dumps(_header_line(), ensure_ascii=False)]
    lines.extend(json.dumps(rec, ensure_ascii=False) for rec in records)
    return "\n".join(lines).encode("utf-8")


def _op(op_id: str, *, product_id: str, batch_id: str | None, seq: int, qty_delta: int = 5) -> dict:
    """One verbatim `operation` NDJSON record (mirrors the merge-test factory)."""
    return {
        "kind": "operation",
        "id": op_id,
        "type": "receipt",
        "product_id": product_id,
        "qty_delta": qty_delta,
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


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": NDJSON}


def _ops_count(session) -> int:
    return session.scalar(select(func.count()).select_from(Operation)) or 0


def _seed_admin(session, *, login: str = "boss", password: str = "pw") -> User:
    user = User(
        id=new_id(),
        login=login,
        display_name="Админ",
        role="administrator",
        password_hash=auth.hash_password(password),
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


# --- SYNC-09: token authentication ------------------------------------------


def test_push_with_valid_token(device_client, product, batch):
    body = _ndjson([_op("op-1", product_id=product.id, batch_id=batch.id, seq=1)])
    resp = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )
    assert resp.status_code == 200
    assert resp.json()["operations_inserted"] == 1


def test_push_without_token_rejected(anon_client, session):
    # Pitfall 3 regression: no session-cookie 303→/login on the Bearer tree.
    body = _ndjson([])
    resp = anon_client.post(
        "/api/sync/push", content=body, headers={"Content-Type": NDJSON},
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert resp.status_code != 303
    assert "location" not in {k.lower() for k in resp.headers}


def test_push_with_garbage_token_rejected(device_client):
    body = _ndjson([])
    resp = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer("myos_definitely-not-a-real-token")
    )
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


def test_revoked_token_rejected(device_client, session):
    # Mint a fresh token, prove it works, revoke it, prove it no longer works.
    result, errors = devices.mint_token(session, device_id=new_id(), label="Второе")
    assert errors == {}
    row, plaintext = result
    ok = device_client.client.post(
        "/api/sync/push", content=_ndjson([]), headers=_bearer(plaintext)
    )
    assert ok.status_code == 200

    devices.revoke_token(session, row.id)
    resp = device_client.client.post(
        "/api/sync/push", content=_ndjson([]), headers=_bearer(plaintext)
    )
    assert resp.status_code == 401


# --- T-28-03: neither auth path can reach the other's surface ---------------


def test_device_token_cannot_reach_html(device_client, session):
    # Negative direction A: a Bearer token grants NOTHING on the HTML tree.
    _seed_admin(session)  # so the guard redirects to /login, not /setup
    headers = {"Authorization": f"Bearer {device_client.plaintext}"}
    for path in ("/", "/settings/users", "/settings"):
        resp = device_client.client.get(path, headers=headers, follow_redirects=False)
        assert resp.status_code != 200, path
        assert resp.status_code == 303, path
        assert resp.headers["location"] == "/login", path


def test_session_cookie_cannot_reach_sync(anon_client, session, login):
    # Negative direction B: a real browser session grants NOTHING on the sync tree.
    _seed_admin(session, login="boss", password="pw")
    assert login(anon_client, "boss", "pw").status_code == 303  # real session cookie set
    resp = anon_client.post(
        "/api/sync/push",
        content=_ndjson([]),
        headers={"Content-Type": NDJSON},  # cookie present, NO Bearer header
        follow_redirects=False,
    )
    assert resp.status_code == 401


# --- SYNC-02 / SC-2: idempotency + all-or-nothing ---------------------------


def test_push_idempotent(device_client, product, batch):
    body = _ndjson([_op("op-idem", product_id=product.id, batch_id=batch.id, seq=1)])
    first = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )
    assert first.status_code == 200
    assert first.json()["operations_inserted"] == 1

    second = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )
    assert second.status_code == 200
    payload = second.json()
    assert payload["operations_inserted"] == 0
    assert payload["operations_skipped"] == 1


def test_push_all_or_nothing(device_client, session, product, batch):
    # The last record references a non-existent product_id: it passes
    # parse_exchange and fails the FK at insert, rolling the WHOLE batch back.
    from sqlalchemy.exc import IntegrityError

    before = _ops_count(session)
    body = _ndjson(
        [
            _op("op-good", product_id=product.id, batch_id=batch.id, seq=1),
            _op("op-bad", product_id="does-not-exist", batch_id=None, seq=2),
        ]
    )
    with pytest.raises(IntegrityError):
        device_client.client.post(
            "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
        )
    session.rollback()
    assert _ops_count(session) == before  # zero rows persisted (all-or-nothing)


# --- T-28-04 / T-28-12 / V7: body cap, rate limit, malformed ----------------


def test_push_rejects_oversized_body(device_client, session, monkeypatch):
    monkeypatch.setattr(sync_route, "MAX_PUSH_BYTES", 10)  # tiny cap, no 32MB body
    before = _ops_count(session)
    body = _ndjson([])  # comfortably larger than 10 bytes
    resp = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )
    assert resp.status_code == 413
    assert _ops_count(session) == before


def test_push_rejects_malformed_ndjson(device_client):
    body = b"totally not json and not a header line"
    resp = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )
    assert resp.status_code == 400
    # V7: the fixed RU constant, never the attacker-submitted bytes reflected back.
    assert resp.json()["detail"] == sync_route.MALFORMED_BATCH_ERROR
    assert b"totally not json" not in resp.content


def test_push_rate_limited(device_client):
    body = _ndjson([])  # header-only valid batch → 200 until the bucket empties
    statuses = []
    for _ in range(rate_limit.SYNC_BUCKET_CAPACITY + 5):
        resp = device_client.client.post(
            "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
        )
        statuses.append(resp.status_code)
        if resp.status_code == 429:
            assert resp.json()["detail"] == sync_route.RATE_LIMITED_ERROR
    assert 429 in statuses


def test_successful_push_stamps_last_used_at(device_client, session):
    resp = device_client.client.post(
        "/api/sync/push", content=_ndjson([]), headers=_bearer(device_client.plaintext)
    )
    assert resp.status_code == 200
    session.expire_all()
    row = session.scalar(
        select(DeviceToken).where(DeviceToken.token_prefix == device_client.prefix)
    )
    assert row is not None
    assert row.last_used_at  # a non-empty ISO timestamp
