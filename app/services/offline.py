"""Offline self-upload service (OFF-04/OFF-05): pure token + schema helpers.

The offline transport lets a disconnected client build a self-contained bundle
and self-upload it to the server over an untrusted internet PC. Because those
ingest routes bypass the session guard (security.OFFLINE_PATH_PREFIX, D-05), they
gate themselves in-body: a short-lived, upload-scoped token minted here.

This module is PURE — no HTTP, no DB, no file I/O — so it stays unit-testable and
the routes (30-03) stay thin callers. Governing decisions (30-RESEARCH.md):
- D-03: the token is an `itsdangerous` HMAC-timed value derived from
  `settings.secret_key` with the dedicated salt "offline-upload". The salt
  namespaces it away from the Starlette session cookie so a token can never be
  replayed as a cookie, nor a cookie as a token. The secret lives outside the
  synced DB (config.py), so a copied `myorishop.db` never carries the credential.
- D-09: the schema-version gate is exact-match, but SKIPS when the server schema
  is empty (create_all test fixtures have no `alembic_version` table, Pitfall 7).

CLAUDE.md safety: the token and `secret_key` are NEVER logged or printed.
"""

from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import settings

# Short TTL blunts a keylogged/observed token: a captured token is useless within
# minutes (D-03 / A5). Kept module-level so 30-03's expired-token test can
# monkeypatch it to force expiry deterministically.
OFFLINE_TOKEN_TTL = 300  # seconds
# The scope claim the token must carry; a token minted for anything else is
# rejected so it cannot be repurposed across surfaces.
OFFLINE_TOKEN_SCOPE = "offline_upload"

# Dedicated salt (D-03): separate HMAC namespace from the session cookie so the
# two token families can never be cross-replayed.
_signer = URLSafeTimedSerializer(settings.secret_key, salt="offline-upload")


def mint_offline_token(user_id: str) -> str:
    """Mint a short-lived, upload-scoped offline token for `user_id` (D-03).

    Packs a `{"scope": OFFLINE_TOKEN_SCOPE, "sub": user_id}` claim signed with the
    server `secret_key`. Never log the returned value (CLAUDE.md).
    """
    return _signer.dumps({"scope": OFFLINE_TOKEN_SCOPE, "sub": user_id})


def verify_offline_token(token: str) -> dict:
    """Verify an offline token and return its claim dict (D-03).

    Raises `itsdangerous.SignatureExpired` when older than `OFFLINE_TOKEN_TTL`,
    `itsdangerous.BadSignature` on tamper OR when the claim carries the wrong
    scope. Verification is the serializer's own HMAC-timed check — never a bare
    `==` comparison against a stored token.
    """
    claim = _signer.loads(token, max_age=OFFLINE_TOKEN_TTL)
    if claim.get("scope") != OFFLINE_TOKEN_SCOPE:
        raise BadSignature("wrong scope")
    return claim


def schema_version_ok(header_schema: str, server_schema: str) -> bool:
    """Return whether a bundle's schema version is acceptable to ingest (D-09).

    Skips the gate (True) when `server_schema` is empty — create_all fixtures have
    no `alembic_version` table, so `current_schema_version` returns "" (Pitfall 7).
    Otherwise requires an exact match, so a bundle built on a different migration
    head is rejected before any merge.
    """
    if server_schema == "":
        return True
    return header_schema == server_schema
