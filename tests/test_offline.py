"""Wave-0 RED validation scaffold for Phase 30 (Offline Self-Uploading File).

This module builds on the REAL-guard `anon_client` fixture (NOT the wholesale
`auth_guard`-override `client` fixture): the `/api/offline/` bypass — the single
highest-consequence line of the phase — would be untestable under a blanket
override, exactly the rationale spelled out in `test_sync_api.py:1-19` for the
sync tree. Every ingest test here therefore exercises the genuine guard so the
narrow exact-prefix bypass is really proven.

Contract note (Nyquist Wave 0): the tests below are RED-by-design. Their
module-level imports touch ONLY already-existing symbols; the not-yet-built
modules (`app.routes.offline`, `app.services.offline`, the promoted
`app.services.sync_client.collect_push_records`, `app.services.merge.payload_digest`)
are imported INSIDE the test bodies so collection stays green in Wave 0. Each
RED test's docstring names the wave/plan that turns it green.

CLAUDE.md safety: the offline upload token is minted from `settings.secret_key`
via the same `itsdangerous` contract the Wave-1 `app/services/offline.py` must
honour; it is only ever placed in a form field, never logged.
"""

import hashlib
import json

import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import func, select

from app.config import settings
from app.core import new_id
from app.models import (
    Batch,
    CashMovement,
    Customer,
    Operation,
    Product,
    Sale,
    User,
    Warehouse,
)
from app.services import merge, rate_limit
from app.services.auth import hash_password

# The offline-token salt is the exact contract Wave 1's
# `app/services/offline.mint_offline_token` must honour (RESEARCH Pattern 2).
OFFLINE_TOKEN_SALT = "offline-upload"


@pytest.fixture(autouse=True)
def _fresh_buckets():
    """Reset the shared rate-limit buckets so limits cannot leak between tests."""
    rate_limit.reset_buckets()
    yield
    rate_limit.reset_buckets()


# --- Shared helpers ---------------------------------------------------------


def _offline_ndjson(
    records: list[dict],
    *,
    schema_version: str = "",
    source_device_id: str = "device-offline",
    generated_at: str = "2026-07-20T10:00:00+00:00",
) -> str:
    """Build an offline NDJSON body EXACTLY as `serialize_exchange` will.

    A header line first, then one JSON line per record. `payload_sha256` is
    computed over the RECORD lines only (header excluded, exact emission order),
    LF-joined — the D-08 integrity contract the upload route verifies before any
    DB touch. The route canonicalizes via `splitlines()`, so the returned string
    is LF-joined and CRLF-agnostic.
    """
    record_lines = [json.dumps(rec, ensure_ascii=False) for rec in records]
    payload_sha256 = hashlib.sha256(
        "\n".join(record_lines).encode("utf-8")
    ).hexdigest()
    counts: dict[str, int] = {}
    for rec in records:
        kind = rec.get("kind")
        counts[kind] = counts.get(kind, 0) + 1
    header = {
        "kind": "header",
        "format_version": merge.FORMAT_VERSION,
        "schema_version": schema_version,
        "source_device_id": source_device_id,
        "generated_at": generated_at,
        "counts": counts,
        "payload_sha256": payload_sha256,
    }
    return "\n".join([json.dumps(header, ensure_ascii=False)] + record_lines)


def _mint_offline_token(user_id: str) -> str:
    """Mint an upload-scoped offline token — the Wave-1 service contract (D-03).

    `URLSafeTimedSerializer(settings.secret_key, salt="offline-upload")` packing a
    `{"scope": "offline_upload", "sub": user_id}` claim, exactly what
    `app/services/offline.mint_offline_token` must produce and
    `verify_offline_token` must accept.
    """
    signer = URLSafeTimedSerializer(settings.secret_key, salt=OFFLINE_TOKEN_SALT)
    return signer.dumps({"scope": "offline_upload", "sub": user_id})


def _seed_admin(session, *, login: str = "boss", password: str = "pw") -> User:
    """Seed one active administrator (copy of `test_sync_api.py:_seed_admin`)."""
    user = User(
        id=new_id(),
        login=login,
        display_name="Админ",
        role="administrator",
        password_hash=hash_password(password),
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def _offline_login(anon_client, login: str, password: str):
    """POST `/api/offline/login` with form creds; return the raw response.

    Does not follow redirects so callers can read `.json()["token"]` on success
    or assert on the 401/429 rejection status (OFF-04 / D-05).
    """
    return anon_client.post(
        "/api/offline/login",
        data={"login": login, "password": password},
        follow_redirects=False,
    )


def _op(
    op_id: str,
    *,
    product_id: str,
    batch_id: str | None,
    seq: int,
    qty_delta: int = 5,
) -> dict:
    """One verbatim `operation` NDJSON record (mirrors the sync-test factory)."""
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
        "device_id": "device-offline",
        "seq": seq,
        "created_at": "2026-07-20T10:00:00+00:00",
        "created_by": "operator",
        "synced_at": None,
    }


def _ops_count(session) -> int:
    return session.scalar(select(func.count()).select_from(Operation)) or 0


def _seed_unsynced_op(session, *, product_id: str, batch_id: str | None, seq: int = 1) -> Operation:
    """Insert one unsynced (`synced_at IS NULL`) receipt operation directly.

    A direct INSERT (not `record_operation`) so the ledger row carries a known id
    and stays unsynced — the OFF-01 accumulation marker the export collector reads.
    """
    op = Operation(
        id=new_id(),
        type="receipt",
        product_id=product_id,
        qty_delta=5,
        unit_cost_cents=1000,
        batch_id=batch_id,
        device_id="device-offline",
        seq=seq,
        created_at="2026-07-20T10:00:00+00:00",
        created_by="operator",
    )
    session.add(op)
    session.commit()
    return op


# ===========================================================================
# OFF-04: the two-step credential handshake (login → token, NO data on failure)
# ===========================================================================


def test_login_success_mints_token(anon_client, session):
    """Right creds → 200 with an upload token. (OFF-04, GREEN in 30-03)"""
    _seed_admin(session, login="boss", password="pw")
    resp = _offline_login(anon_client, "boss", "pw")
    assert resp.status_code == 200
    assert resp.json().get("token")


def test_login_wrong_password_no_token(anon_client, session):
    """Wrong password → 401, NO token, NO payload echo. (OFF-04, GREEN in 30-03)"""
    _seed_admin(session, login="boss", password="pw")
    resp = _offline_login(anon_client, "boss", "nope")
    assert resp.status_code == 401
    body = resp.json()
    assert "token" not in body
    # T-30-03 / OFF-04: the failure carries NO business data back to the machine.
    assert "records" not in body
    assert "counts" not in body


def test_login_rate_limited(anon_client, session):
    """Exhausting the login bucket → 429. (T-30-07, GREEN in 30-03)"""
    _seed_admin(session, login="boss", password="pw")
    statuses = []
    for _ in range(rate_limit.SYNC_BUCKET_CAPACITY + 5):
        statuses.append(_offline_login(anon_client, "boss", "nope").status_code)
    assert 429 in statuses


# ===========================================================================
# OFF-05 / OFF-07: the ingest route (token → integrity + schema → merge)
# ===========================================================================


def test_upload_twice_is_noop(anon_client, session, product, batch):
    """Idempotent double-upload inserts nothing the second time. (OFF-05a, GREEN in 30-03)"""
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson([_op("op-idem", product_id=product.id, batch_id=batch.id, seq=1)])

    first = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": body}
    )
    assert first.status_code == 200
    after_first = _ops_count(session)

    second = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": body}
    )
    assert second.status_code == 200
    session.expire_all()
    assert _ops_count(session) == after_first  # the replay inserted nothing


def test_upload_all_or_nothing(anon_client, session, product, batch):
    """A poisoned last record rolls the WHOLE batch back. (OFF-05b, GREEN in 30-03)"""
    from sqlalchemy.exc import IntegrityError

    before = _ops_count(session)
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson(
        [
            _op("op-good", product_id=product.id, batch_id=batch.id, seq=1),
            _op("op-bad", product_id="does-not-exist", batch_id=None, seq=2),
        ]
    )
    # Mirror test_push_all_or_nothing: the FK violation is NOT swallowed — it
    # propagates and the owned transaction rolls the whole batch back.
    with pytest.raises(IntegrityError):
        anon_client.post("/api/offline/upload", data={"token": token, "payload": body})
    session.rollback()
    assert _ops_count(session) == before  # zero rows persisted (all-or-nothing)


def test_upload_corrupted_checksum_rejected(anon_client, session, product, batch):
    """A byte-flip that still parses as JSON → rejected before any DB touch. (OFF-07a, GREEN in 30-03)"""
    before = _ops_count(session)
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson([_op("op-x", product_id=product.id, batch_id=batch.id, seq=1)])
    # Flip a digit inside the RECORD line WITHOUT updating payload_sha256:
    # qty_delta 5 → 6 still parses as valid JSON but breaks the SHA-256 (D-08).
    lines = body.split("\n")
    lines[1] = lines[1].replace('"qty_delta": 5', '"qty_delta": 6')
    tampered = "\n".join(lines)

    resp = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": tampered}
    )
    assert resp.status_code != 200
    assert "Файл повреждён" in resp.text
    session.expire_all()
    assert _ops_count(session) == before  # nothing merged


def test_upload_incompatible_schema_rejected(anon_client, session, monkeypatch, product, batch):
    """File schema_version != a REAL server revision → 409 naming both. (OFF-07b, GREEN in 30-03)"""
    import app.routes.offline as offline_route

    # Force the server to report a concrete revision that differs from the file's.
    monkeypatch.setattr(offline_route, "current_schema_version", lambda _session: "0099")
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson(
        [_op("op-s", product_id=product.id, batch_id=batch.id, seq=1)],
        schema_version="0042",
    )
    resp = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": body}
    )
    assert resp.status_code == 409
    # D-09: both versions named, distinct message.
    assert "0042" in resp.text
    assert "0099" in resp.text
    assert "Файл собран для версии данных" in resp.text


def test_upload_empty_server_schema_skips_gate(anon_client, session, product, batch):
    """Empty server schema (create_all fixture) → gate skipped, upload proceeds. (OFF-07b, GREEN in 30-03)"""
    # The test DB is built via Base.metadata.create_all → no alembic_version table
    # → current_schema_version(session) == "" → the schema gate is skipped (D-09).
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson(
        [_op("op-e", product_id=product.id, batch_id=batch.id, seq=1)],
        schema_version="0042",  # non-empty file version, but server reports none
    )
    resp = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": body}
    )
    assert resp.status_code == 200


def test_upload_bad_format_version_rejected(anon_client, session, product, batch):
    """header format_version != FORMAT_VERSION → rejected via parse_exchange. (OFF-07c, GREEN in 30-03)"""
    before = _ops_count(session)
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson([_op("op-f", product_id=product.id, batch_id=batch.id, seq=1)])
    # Corrupt ONLY the header's format_version. The digest is over the record
    # lines only, so it still matches — the rejection comes from parse_exchange.
    lines = body.split("\n")
    header = json.loads(lines[0])
    header["format_version"] = 999
    lines[0] = json.dumps(header, ensure_ascii=False)
    resp = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": "\n".join(lines)}
    )
    assert resp.status_code != 200
    assert "Файл повреждён" in resp.text
    session.expire_all()
    assert _ops_count(session) == before


def test_upload_expired_token_rejected(anon_client, session, monkeypatch, product, batch):
    """An expired upload token → 401 / «Время на загрузку истекло». (T-30-04, GREEN in 30-03)"""
    import app.services.offline as offline_service

    # Push the TTL into the past so a freshly-minted token verifies as expired.
    monkeypatch.setattr(offline_service, "OFFLINE_TOKEN_TTL", -1)
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson([_op("op-t", product_id=product.id, batch_id=batch.id, seq=1)])
    resp = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": body}
    )
    assert resp.status_code == 401
    assert "Время на загрузку истекло" in resp.text


def test_upload_oversized_body_rejected(anon_client, session, monkeypatch, product, batch):
    """Belt-and-braces body cap → rejected before merge. (T-30-09, GREEN in 30-03)"""
    import app.routes.offline as offline_route

    before = _ops_count(session)
    monkeypatch.setattr(offline_route, "MAX_OFFLINE_BYTES", 10)  # tiny cap
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson([_op("op-big", product_id=product.id, batch_id=batch.id, seq=1)])
    resp = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": body}
    )
    assert resp.status_code != 200
    session.expire_all()
    assert _ops_count(session) == before


def test_crlf_payload_digest_matches(anon_client, session, product, batch):
    """A CRLF-normalized payload still verifies its digest. (Pitfall 1, GREEN in 30-03)"""
    # A top-level <form> submit normalizes newlines to CRLF; the route
    # canonicalizes via splitlines()+"\n".join() on both sides, so the SHA-256
    # still matches and the upload succeeds rather than false-rejecting.
    token = _mint_offline_token("some-user-id")
    body = _offline_ndjson([_op("op-crlf", product_id=product.id, batch_id=batch.id, seq=1)])
    crlf_body = body.replace("\n", "\r\n")
    resp = anon_client.post(
        "/api/offline/upload", data={"token": token, "payload": crlf_body}
    )
    assert resp.status_code == 200


# ===========================================================================
# T-30-06: the auth-guard bypass is narrow (exact-prefix + session-guarded export)
# ===========================================================================


def test_offline_bypass_is_narrow(anon_client, session, login):
    """A browser session is NOT an ingest bypass; export needs a session. (T-30-06, GREEN spans 30-02/03/04)"""
    _seed_admin(session, login="boss", password="pw")  # so the guard 303s to /login, not /setup

    # (a) The client export page is session-guarded — anonymous → 303 /login.
    export = anon_client.get("/offline/export", follow_redirects=False)
    assert export.status_code == 303
    assert export.headers["location"].startswith("/login")

    # (b) A real browser session grants NOTHING on the ingest tree: the in-body
    # token gate still applies, so a session cookie without a valid token cannot
    # upload (mirror test_session_cookie_cannot_reach_sync).
    assert login(anon_client, "boss", "pw").status_code == 303  # real session cookie set
    resp = anon_client.post(
        "/api/offline/upload",
        data={"token": "not-a-valid-token", "payload": "x"},
        follow_redirects=False,
    )
    assert resp.status_code != 200


# ===========================================================================
# OFF-01 / OFF-02 / OFF-06: the export collector + serializer (unit, no network)
# ===========================================================================


def test_export_header_counts_present(session, product, batch):
    """The serialized header carries a `counts` map AND a `payload_sha256`. (OFF-06, GREEN in 30-02/30-04)"""
    from app.services.sync_client import collect_push_records

    _seed_unsynced_op(session, product_id=product.id, batch_id=batch.id)
    records, _ids = collect_push_records(session)
    lines = list(
        merge.serialize_exchange(
            records,
            schema_version="",
            source_device_id="device-offline",
            generated_at="2026-07-20T10:00:00+00:00",
        )
    )
    header = json.loads(lines[0])
    assert "counts" in header
    assert header["counts"].get("operation") == 1
    assert "payload_sha256" in header  # D-08 integrity field emitted by the serializer


def test_export_does_not_stamp_synced_at(session, product, batch):
    """Building the export bundle writes NO `synced_at` (read-only). (OFF-01/D-07, GREEN in 30-02/30-04)"""
    from app.services.sync_client import collect_push_records

    op = _seed_unsynced_op(session, product_id=product.id, batch_id=batch.id)
    records, _ids = collect_push_records(session)
    list(
        merge.serialize_exchange(
            records,
            schema_version="",
            source_device_id="device-offline",
            generated_at="2026-07-20T10:00:00+00:00",
        )
    )
    session.expire_all()
    refreshed = session.get(Operation, op.id)
    assert refreshed.synced_at is None  # D-07: export never marks rows synced


def test_export_bundle_fk_closure_complete(session, product, warehouse, customer):
    """The bundle carries the FK parents of the unsynced ledger rows. (OFF-02, GREEN in 30-04)"""
    from app.services.sync_client import collect_push_records

    # Build an unsynced sale + operation so the closure must pull sale→customer,
    # batch→product/warehouse, operation→product/batch.
    batch = Batch(
        id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=0
    )
    session.add(batch)
    sale = Sale(
        id=new_id(),
        customer_id=customer.id,
        created_at="2026-07-20T10:00:00+00:00",
        created_by="operator",
    )
    session.add(sale)
    session.commit()
    op = Operation(
        id=new_id(),
        type="sale",
        product_id=product.id,
        qty_delta=-1,
        unit_price_cents=1500,
        sale_id=sale.id,
        batch_id=batch.id,
        device_id="device-offline",
        seq=1,
        created_at="2026-07-20T10:00:00+00:00",
        created_by="operator",
    )
    session.add(op)
    session.commit()

    records, _ids = collect_push_records(session)
    kinds = {rec.kind for rec in records}
    for parent_kind in ("product", "batch", "sale", "customer", "warehouse"):
        assert parent_kind in kinds, parent_kind


def test_export_html_contains_embedded_payload_and_form(client, monkeypatch):
    """GET /offline/export embeds NDJSON in a script block + a form to /api/offline/upload. (OFF-03, GREEN in 30-04)"""
    # Pitfall 5: the export refuses/embeds the server URL — give it a real one.
    monkeypatch.setattr(settings, "sync_server_url", "https://sync.example.com")
    resp = client.get("/offline/export")
    assert resp.status_code == 200
    assert 'type="application/x-ndjson"' in resp.text
    assert "/api/offline/upload" in resp.text
    assert "<form" in resp.text.lower()


def test_script_tag_escaping_round_trip(client, session, product, batch, monkeypatch):
    """A `</script>`-bearing product name survives export→embed→unescape→parse. (T-30-08, GREEN in 30-04/30-03)"""
    monkeypatch.setattr(settings, "sync_server_url", "https://sync.example.com")
    product.name = "Крем</script>Ночной"
    session.add(product)
    _seed_unsynced_op(session, product_id=product.id, batch_id=batch.id)
    session.commit()

    resp = client.get("/offline/export")
    assert resp.status_code == 200
    # The raw closing tag must be escaped inside the embed so it cannot break out.
    assert "<\\/script" in resp.text

    # Extract the embedded NDJSON, reverse the escape, and re-parse: the product
    # name must round-trip byte-for-byte (T-30-08).
    marker = 'type="application/x-ndjson">'
    start = resp.text.index(marker) + len(marker)
    end = resp.text.index("</script>", start)
    embedded = resp.text[start:end]
    ndjson = embedded.replace("<\\/script", "</script")
    batch_parsed = merge.parse_exchange(ndjson.strip().splitlines())
    product_names = [
        rec.data.get("name") for rec in batch_parsed.records if rec.kind == "product"
    ]
    assert "Крем</script>Ночной" in product_names
