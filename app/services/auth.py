"""Password hashing service (AUTH-02): Argon2id + timing-safe token compare.

All security-critical credential logic lives here, never in a route (the
fat-service V5/V6 convention). `hash_password`/`verify_password` wrap the
canonical `argon2-cffi` `PasswordHasher` (library defaults are Argon2id and
OWASP-reasonable — RESEARCH A5). `verify_password` is constant-time, never
raises, and transparently upgrades a stored hash whose params are weaker than
the current defaults (rehash-on-login). `compare_token` wraps
`hmac.compare_digest` for the CSRF synchronizer-token compare in security.py.

CLAUDE.md safety: no raw password or hash value is ever logged or printed.
"""

import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy.orm import Session

from app.models import User

# Module-level hasher — library defaults select Argon2id with OWASP-reasonable
# parameters (RESEARCH Pattern 2 / A5). Reused across every hash/verify call.
_ph = PasswordHasher()


def hash_password(raw: str) -> str:
    """Return a PHC-encoded Argon2id hash string (store in User.password_hash).

    Each call uses a fresh random salt, so hashing the same input twice yields
    different strings. The full PHC string (algorithm + params + salt + digest)
    is self-contained — no separate salt column.
    """
    return _ph.hash(raw)


def verify_password(session: Session, user: User, raw: str) -> bool:
    """Constant-time verify of `raw` against `user.password_hash`.

    Returns True on match, False on mismatch or a malformed/empty stored hash
    (never raises). On a successful verify, if the stored hash was produced with
    weaker-than-current params, it is re-hashed and committed (rehash-on-login,
    RESEARCH Pattern 2).
    """
    try:
        _ph.verify(user.password_hash, raw)
    except (VerifyMismatchError, InvalidHashError):
        return False
    if _ph.check_needs_rehash(user.password_hash):
        user.password_hash = _ph.hash(raw)
        session.commit()
    return True


def compare_token(a: str, b: str) -> bool:
    """Timing-safe string equality (wraps hmac.compare_digest).

    Used by the CSRF synchronizer-token compare (security.py) to avoid timing
    side-channels — never use a bare `==` on a secret token.
    """
    return hmac.compare_digest(a, b)
