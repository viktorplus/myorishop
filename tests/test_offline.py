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
