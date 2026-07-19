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
from app.models import (
    CashMovement,
    DeviceToken,
    Operation,
    Product,
    Sale,
    User,
    Warehouse,
)
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


# --- SYNC-09: GET /api/sync/pull (reference-data-down) -----------------------


def _pull(device_client, **params):
    """GET /api/sync/pull with the fixture's Bearer token + optional cursor."""
    return device_client.client.get(
        "/api/sync/pull",
        params={k: v for k, v in params.items() if v is not None} or None,
        headers={"Authorization": f"Bearer {device_client.plaintext}"},
    )


def _pull_lines(resp) -> list[dict]:
    """Parse an NDJSON pull body into a list of JSON objects (blank lines skipped)."""
    return [json.loads(line) for line in resp.text.splitlines() if line.strip()]


def _seed_product(session, *, code, name="Товар", updated_at=None, deleted_at=None):
    product = Product(id=new_id(), code=code, name=name, quantity=0)
    if updated_at is not None:
        product.updated_at = updated_at
    if deleted_at is not None:
        product.deleted_at = deleted_at
    session.add(product)
    session.commit()
    return product


def test_pull_requires_token(anon_client):
    # T-28-02: the pull tree is Bearer-gated exactly like push; no session-cookie
    # 303→/login leak on this surface (Pitfall 4).
    resp = anon_client.get("/api/sync/pull", follow_redirects=False)
    assert resp.status_code == 401
    assert resp.status_code != 303


def test_pull_returns_reference_records(device_client, session):
    product = _seed_product(session, code="PULL-1")
    warehouse = Warehouse(id=new_id(), name="Склад для выгрузки")
    session.add(warehouse)
    session.commit()

    resp = _pull(device_client)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")

    lines = _pull_lines(resp)
    assert lines[0]["kind"] == "header"
    assert lines[0]["format_version"] == 1
    product_ids = {ln["id"] for ln in lines if ln.get("kind") == "product"}
    assert product.id in product_ids


def test_pull_excludes_ledger_kinds(device_client, session, product, batch):
    # T-28-20: pull is reference-only — a seeded operation AND cash movement must
    # never appear in the body.
    op = Operation(
        id=new_id(),
        type="receipt",
        product_id=product.id,
        qty_delta=5,
        batch_id=batch.id,
        device_id="device-A",
        seq=1,
        created_at="2026-07-19T10:00:00+00:00",
        created_by="operator",
    )
    cash = CashMovement(
        id=new_id(),
        category="sale",
        amount_cents=1000,
        device_id="device-A",
        seq=1,
        created_at="2026-07-19T10:00:00+00:00",
        created_by="operator",
    )
    session.add_all([op, cash])
    session.commit()

    lines = _pull_lines(_pull(device_client))
    kinds = {ln.get("kind") for ln in lines}
    assert "operation" not in kinds
    assert "cash_movement" not in kinds


def test_pull_cursor_is_inclusive(device_client, session):
    # Pitfall 7 regression: a row whose cursor == `since` must still be delivered.
    # A strict `>` would return NEITHER of these two identical-timestamp rows.
    ts = "2026-06-01T00:00:00+00:00"
    p1 = _seed_product(session, code="INC-1", updated_at=ts)
    p2 = _seed_product(session, code="INC-2", updated_at=ts)

    lines = _pull_lines(_pull(device_client, since=ts))
    product_ids = {ln["id"] for ln in lines if ln.get("kind") == "product"}
    assert p1.id in product_ids
    assert p2.id in product_ids


def test_pull_sale_uses_created_at(device_client, session):
    # Pitfall 8 regression: Sale has no updated_at, so it is paged by created_at.
    # A uniform updated_at query would raise instead of returning the sale.
    sale = Sale(
        id=new_id(),
        created_at="2026-06-01T00:00:00+00:00",
        created_by="operator",
    )
    session.add(sale)
    session.commit()

    resp = _pull(device_client, since="2026-01-01T00:00:00+00:00")
    assert resp.status_code == 200
    sale_ids = {ln["id"] for ln in _pull_lines(resp) if ln.get("kind") == "sale"}
    assert sale.id in sale_ids


def test_pull_limit_and_next_since(device_client, session):
    for i in range(4):
        _seed_product(session, code=f"LIM-{i}")

    resp = _pull(device_client, limit=2)
    records = [ln for ln in _pull_lines(resp) if ln.get("kind") != "header"]
    assert len(records) == 2
    # BOTH cursor halves present and non-empty — a lone `since` cannot advance.
    assert resp.headers.get("x-sync-next-since")
    assert resp.headers.get("x-sync-next-after-id")


def test_pull_paginates_past_identical_timestamps(device_client, session):
    # W-1 termination regression: the documented bulk-edit case — more rows share
    # one identical updated_at than `limit`. A single-column cursor loops forever;
    # the composite (cursor, id) cursor advances by id and terminates.
    ts = "2026-06-01T00:00:00+00:00"
    limit = 2
    seeded = {
        _seed_product(session, code=f"BULK-{i}", updated_at=ts).id
        for i in range(limit + 1)
    }

    collected: list[str] = []
    since: str | None = None
    after_id: str | None = None
    first_page: set[str] = set()
    terminated = False
    for iteration in range(10):  # hard cap: a non-terminating cursor blows past it
        resp = _pull(device_client, since=since, after_id=after_id, limit=limit)
        assert resp.status_code == 200
        page_ids = [ln["id"] for ln in _pull_lines(resp) if ln.get("kind") == "product"]
        if iteration == 0:
            first_page = set(page_ids)
        elif iteration == 1:
            # Page 2 must ADVANCE, never repeat page 1.
            assert set(page_ids).isdisjoint(first_page)
        collected.extend(page_ids)
        if len(page_ids) < limit:
            terminated = True
            break
        since = resp.headers["x-sync-next-since"]
        after_id = resp.headers["x-sync-next-after-id"]

    assert terminated, "pull pagination did not terminate within the iteration cap"
    assert set(collected) == seeded  # no omissions
    assert len(collected) == len(seeded)  # and no duplicates


def test_pull_round_trips_through_parse_exchange(device_client, session):
    # SYNC-04: the server emits EXACTLY the format the Phase 29 client parses —
    # one wire implementation, proven by feeding the raw body back through the
    # Phase 27 parser.
    product = _seed_product(session, code="RT-1")

    resp = _pull(device_client)
    batch = merge.parse_exchange(resp.text.splitlines())
    assert batch.format_version == 1
    assert len(batch.records) == 1
    assert batch.records[0].kind == "product"
    assert batch.records[0].data["id"] == product.id


def test_pull_rejects_bad_cursor(device_client):
    resp = _pull(device_client, since="not-a-date")
    assert resp.status_code == 400
    assert resp.json()["detail"] == sync_route.INVALID_CURSOR_ERROR


def test_pull_lone_after_id_accepted(device_client, session):
    # A lone after_id with no `since` is meaningless and is IGNORED, not an error.
    _seed_product(session, code="LONE-1")
    resp = _pull(device_client, after_id="abc")
    assert resp.status_code == 200


# --- SRV-04 (ROADMAP Success Criterion 1): one app object, two UIs -----------


def test_both_uis_one_app(client):
    # Locks in that the mobile UI is SERVER-ONLY: one app object, one process, no
    # second deployment, no local/offline mobile install (SRV-04; REQUIREMENTS
    # "Explicitly out of scope": a local/offline mobile install). The default
    # authenticated `client` fixture is correct here — this test is about hosting,
    # not the device-token bypass.
    desktop = client.get("/")
    mobile = client.get("/m/")
    assert desktop.status_code == 200
    assert mobile.status_code == 200
    # The two responses render DIFFERENT templates from the SAME app: the mobile
    # tab-bar chrome is unique to mobile_base.html and absent from desktop.
    assert "mobile-tabbar" in mobile.text
    assert "mobile-tabbar" not in desktop.text
    assert desktop.text != mobile.text
