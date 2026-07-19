"""Device-token service (SYNC-09): mint / verify / list / revoke.

This is the security-critical tier (V5): every validation rule and the entire
token lifecycle live HERE, never in a route. Returns the established
`(obj | None, errors)` shape with HTML-free RU messages (UI-SPEC Copywriting
Contract). Tokens are never hard-deleted — `revoke_token` is a soft-disable so
a compromised device keeps its audit trail.

CLAUDE.md safety: the token plaintext is generated, returned to the caller
ONCE by `mint_token`, and is NEVER stored, re-derivable, logged, printed, or
echoed into any rendered fragment after that single return. Only its SHA-256
hex digest is persisted.

DELIBERATE hasher divergence — this is intentional, not an oversight. Passwords
go through Argon2id (`auth.hash_password`) because a human-chosen password is
low-entropy and needs a deliberately slow KDF to make guessing expensive. A
device token is `secrets.token_urlsafe(32)` — 256 bits of CSPRNG entropy — so
brute force is infeasible regardless of hash speed, and a slow KDF would buy
nothing while adding ~50-100 ms of CPU to EVERY sync request. SHA-256 is
therefore the correct choice here (see `28-RESEARCH.md`, decision A1).
Constant-time comparison is still mandatory and is reached through
`auth.compare_token`.
"""

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import new_id, utcnow_iso
from app.models import DeviceToken
from app.services.auth import compare_token

# Human-recognisable marker so a leaked string is identifiable as our token.
TOKEN_PLAINTEXT_PREFIX = "myos_"
TOKEN_ENTROPY_BYTES = 32  # 256 bits of CSPRNG entropy
TOKEN_PREFIX_LEN = 12  # width of the NON-SECRET indexed lookup key

# RU validation messages (UI-SPEC Copywriting Contract). HTML-free.
LABEL_REQUIRED_ERROR = "Укажите название устройства."
DEVICE_ID_REQUIRED_ERROR = "Укажите идентификатор устройства."
TOKEN_NOT_FOUND_ERROR = "Токен устройства не найден."

# label is stored in a String(100) column.
_LABEL_MAX = 100


def _digest(plaintext: str) -> str:
    """SHA-256 hex digest of a token plaintext (the only form ever stored)."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def mint_token(
    session: Session, *, device_id: str, label: str, user_id: str | None = None
) -> tuple[tuple[DeviceToken, str] | None, dict[str, str]]:
    """Create a device token; return ((row, plaintext), {}) — plaintext shown ONCE.

    Validates: label required (capped to the column width), device_id required.
    ZERO writes on any validation failure. On success one row is inserted with
    is_active=1, storing only the prefix and the digest. The plaintext appears
    in the return value and nowhere else — never assigned to the row, never
    logged.
    """
    label = (label or "").strip()
    device_id = (device_id or "").strip()
    errors: dict[str, str] = {}

    if not label:
        errors["label"] = LABEL_REQUIRED_ERROR
    if not device_id:
        errors["device_id"] = DEVICE_ID_REQUIRED_ERROR

    if errors:
        return None, errors

    plaintext = TOKEN_PLAINTEXT_PREFIX + secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)
    row = DeviceToken(
        id=new_id(),
        device_id=device_id,
        label=label[:_LABEL_MAX],
        token_prefix=plaintext[:TOKEN_PREFIX_LEN],
        token_hash=_digest(plaintext),
        user_id=user_id,
        is_active=1,
    )
    session.add(row)
    session.commit()
    return (row, plaintext), {}


def lookup_active_token(session: Session, presented: str) -> DeviceToken | None:
    """Resolve a presented plaintext to its active row, or None.

    One indexed SELECT on the non-secret prefix, then one constant-time compare
    of the digests — no table scan, no per-row hashing, never a bare `==` on a
    secret. Wrong, unknown and revoked tokens all resolve to None. This is a
    pure read path (called on every sync request); it never commits.
    """
    if not presented or len(presented) < TOKEN_PREFIX_LEN:
        return None
    row = session.scalar(
        select(DeviceToken).where(
            DeviceToken.token_prefix == presented[:TOKEN_PREFIX_LEN],
            DeviceToken.is_active == 1,
        )
    )
    if row is None:
        return None
    return row if compare_token(_digest(presented), row.token_hash) else None


def touch_last_used(session: Session, token: DeviceToken) -> None:
    """Stamp last_used_at so a stale token is visible to the admin.

    Kept separate from `lookup_active_token` so verification stays a pure read
    and the caller decides when to write.
    """
    token.last_used_at = utcnow_iso()
    session.commit()


def list_device_tokens(session: Session) -> list[DeviceToken]:
    """All tokens ordered by label — active AND revoked (the admin page feed).

    A revoked device must stay visible: it is the audit record.
    """
    return list(session.scalars(select(DeviceToken).order_by(DeviceToken.label)))


def revoke_token(
    session: Session, token_id: str
) -> tuple[DeviceToken | None, dict[str, str]]:
    """Soft-disable a token (is_active=0 + revoked_at), mirroring deactivate_user.

    Unknown id → (None, {"token": ...}) with ZERO writes. Revoking an
    already-revoked token is idempotent (re-stamping is harmless). A
    DeviceToken row is NEVER deleted — the device_id/user_id attribution must
    survive revocation.
    """
    row = session.get(DeviceToken, token_id)
    if row is None:
        return None, {"token": TOKEN_NOT_FOUND_ERROR}
    row.is_active = 0
    row.revoked_at = utcnow_iso()
    session.commit()
    return row, {}
