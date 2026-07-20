"""Security guard module (AUTH-01/04/05, ROLE-02/04, USER-03/05) — greenfield.

No analog in the codebase (25-PATTERNS "NO ANALOG"): this builds the app-level
auth core from RESEARCH Patterns 3/6/7:

- `_current_user` ContextVar + `author_fields()` — the single-write-path
  attribution helper, falling back to `settings.operator_name` when unset so the
  existing ~45 tests + fixtures stay green (the contextvars→threadpool proof is
  deferred to Plan 07).
- `NotAuthenticated` — carries a `.redirect`; the exception handler is registered
  in Plan 04 (HTML 303 / HTMX 401+HX-Redirect).
- CSRF synchronizer-token helpers (issue/session/require) — token in the signed
  session, compared with `hmac.compare_digest` via `auth.compare_token` (AUTH-05).
- `auth_guard` — the one app-level dependency covering every current + future
  router (the "can't forget" guarantee, ROLE-02).
- `require_role` — server-side role gate; an administrator satisfies every
  operator check (ROLE-04).

CLAUDE.md safety: no CSRF token, password or secret is ever logged or printed.
"""

import contextvars
import secrets

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import DeviceToken, User
from app.services import devices
from app.services.auth import compare_token
from app.services.users import count_users, get_active_user

# Only login/logout/first-run are reachable without a session. StaticFiles is a
# mount (not a router), so app-level dependencies never apply to it — /static
# stays public automatically (RESEARCH Pattern 3).
PUBLIC_PATHS = {"/login", "/logout", "/setup"}

# SYNC-09 / threat T-28-03: the token-authenticated sync tree bypass.
# THREE things this constant guarantees, read them before touching it:
#   (1) PUBLIC_PATHS stays EXACT-match — this is a SEPARATE, prefix-matched
#       constant, because the sync tree may grow paths (/api/sync/pull, ...) and
#       an exact set would silently 303-redirect any new one to /login;
#   (2) the prefix is exactly /api/sync/ and NOT the bare /api/ segment — a bare
#       api prefix would un-authenticate every future API route (the single
#       highest-consequence line in the phase, Pitfall 4);
#   (3) this branch is NOT "unguarded": every route under the prefix declares
#       Depends(require_device), a Bearer gate strictly NARROWER than a session
#       cookie (a browser cannot forge an Authorization header).
SYNC_PATH_PREFIX = "/api/sync/"

# OFF-05 / D-05 / threat T-30-06: the token-authenticated offline-ingest bypass.
# Same three guarantees as SYNC_PATH_PREFIX, read them before touching it:
#   (1) prefix is EXACTLY /api/offline/ and NEVER the bare /api/ segment — a bare
#       api prefix would un-authenticate every future API route (Pitfall 3);
#   (2) the client export page /offline/export is DELIBERATELY NOT under this
#       prefix — it stays session-guarded so a browser must log in to build a
#       bundle; only the machine-to-machine ingest tree bypasses the session;
#   (3) this branch is NOT "unguarded": each route under it self-gates in-body
#       (rate-limit + password on /login, offline-token verify on /upload). CSRF
#       is deliberately NOT applied here — the client presents an in-body token,
#       never a session cookie, so the tree is not CSRF-vulnerable (T-30-10).
OFFLINE_PATH_PREFIX = "/api/offline/"

# UI-SPEC Copywriting Contract (line 143): operator hits an admin route.
ACCESS_DENIED_ERROR = "Доступ только для администратора."

# SYNC-09 / threat T-28-02: the two 401 details on the sync tree. Both are
# deliberately indistinguishable in KIND — neither reveals whether a presented
# token is unknown versus revoked (V7); an attacker learns only "not accepted".
DEVICE_TOKEN_REQUIRED_ERROR = "Требуется токен устройства."
DEVICE_TOKEN_INVALID_ERROR = "Недействительный токен устройства."

# Request-scoped current user for attribution at the single write paths (USER-05).
# Default None keeps record_operation/record_cash_movement attribution unchanged
# (settings.operator_name fallback) until Plan 07 wires the guard end-to-end.
_current_user: contextvars.ContextVar = contextvars.ContextVar("current_user", default=None)


class NotAuthenticated(Exception):
    """Raised by the guard when a request must be redirected to log in / set up.

    `redirect` is the target path ("/login" or "/setup"); the exception handler
    (Plan 04) turns it into a 303 for HTML or a 401 + HX-Redirect for HTMX.
    """

    def __init__(self, redirect: str) -> None:
        super().__init__(redirect)
        self.redirect = redirect


def author_fields() -> tuple[str | None, str]:
    """Return (author_id, created_by) for the current request (USER-05).

    When no user is set on the contextvar (tests, fixtures, background tasks),
    fall back to (None, settings.operator_name) so historical attribution and
    the existing suite stay unchanged. Identity is always server-derived, never
    read from client input (repudiation control T-25-03-05).
    """
    user = _current_user.get()
    if user is None:
        return None, settings.operator_name
    return user.id, user.display_name


def current_user(request: Request) -> User | None:
    """FastAPI dependency: the user the guard attached to this request.

    Returns `request.state.user` or None. Overridable in tests via
    `app.dependency_overrides[current_user]` (RESEARCH test pattern).
    """
    return getattr(request.state, "user", None)


# --- CSRF synchronizer token (AUTH-05) --------------------------------------


def issue_csrf(request: Request) -> str:
    """Ensure the session carries a CSRF token; return it.

    Called FIRST in the guard so every request — including public paths like
    /login — has a token available to render into the page.
    """
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def session_csrf(request: Request) -> str:
    """Return the CSRF token stored in the session (empty string if none)."""
    return request.session.get("csrf", "")


async def require_csrf(request: Request) -> None:
    """Validate the submitted CSRF token against the session token (AUTH-05).

    Accepts the `X-CSRF-Token` header (HTMX) or the `csrf_token` form field
    (plain form). Compares with a constant-time `hmac.compare_digest`; raises
    HTTP 403 on any absence or mismatch (tampering mitigation T-25-03-02).
    """
    submitted = request.headers.get("X-CSRF-Token", "")
    if not submitted:
        form = await request.form()
        submitted = form.get("csrf_token", "")
    expected = session_csrf(request)
    if not expected or not submitted or not compare_token(submitted, expected):
        raise HTTPException(status_code=403, detail="Недействительный CSRF-токен.")


# --- App-level guard + role gate --------------------------------------------


async def auth_guard(request: Request, session: Session = Depends(get_session)) -> None:
    """Deny-by-default auth guard registered once on the whole app (ROLE-02).

    Steps (RESEARCH Pattern 3):
      1. issue a CSRF token FIRST (so public pages can render one);
      2. allow explicit public paths;
      3. allow the /api/sync/ tree (SYNC-09) — a Bearer-authenticated surface
         guarded per-route by require_device, so it returns BEFORE the session
         and CSRF checks. CSRF is deliberately NOT applied here: a browser never
         auto-attaches an Authorization header, so a Bearer endpoint is not
         CSRF-vulnerable, while enforcing CSRF would make it impossible for a
         session-less client to ever call the endpoint (threat T-28-06);
      3b. allow the /api/offline/ tree (OFF-05, D-05) — the token-authenticated
         offline-ingest surface, self-gated per-route (rate-limit + password on
         /login, offline-token verify on /upload); CSRF likewise not applied
         (in-body token, no cookie, T-30-10). The /offline/export page is NOT
         under this prefix and stays session-guarded;
      4. zero users → /setup (first-run, AUTH-04);
      5. no active session user → clear + /login (AUTH-01, USER-03);
      6. unsafe method → validate CSRF (AUTH-05);
      7. attach the user to the contextvar + request.state for attribution.
    """
    issue_csrf(request)  # (1)
    if request.url.path in PUBLIC_PATHS:  # (2)
        return
    if request.url.path.startswith(SYNC_PATH_PREFIX):  # (3) SYNC-09 Bearer tree
        return
    if request.url.path.startswith(OFFLINE_PATH_PREFIX):  # (3b) OFF-05 token tree
        return
    if count_users(session) == 0:  # (4) AUTH-04 first-run
        raise NotAuthenticated(redirect="/setup")
    user_id = request.session.get("user_id")  # (5)
    user = get_active_user(session, user_id) if user_id else None
    if user is None:
        request.session.pop("user_id", None)
        raise NotAuthenticated(redirect="/login")
    if request.method not in ("GET", "HEAD", "OPTIONS"):  # (6) AUTH-05
        await require_csrf(request)
    _current_user.set(user)  # (7)
    request.state.user = user


def require_role(role: str):
    """Return a dependency enforcing `role` server-side (ROLE-03/04).

    An administrator satisfies EVERY role check (admin ⊇ operator hierarchy).
    A user whose role differs (and is not administrator) or a missing user →
    HTTP 403 (defence-in-depth; the app-level guard already blocks anonymous).
    """

    def _role_guard(request: Request) -> None:
        user = getattr(request.state, "user", None)
        if user is None:
            raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)
        if user.role == "administrator":
            return  # admin passes every check (ROLE-04)
        if user.role != role:
            raise HTTPException(status_code=403, detail=ACCESS_DENIED_ERROR)

    return _role_guard


# --- Per-device Bearer gate for the /api/sync/ tree (SYNC-09) ----------------

# auto_error=False so THIS code — not FastAPI's default 403/"Not authenticated"
# — owns the RU message, the 401 status and the WWW-Authenticate header.
_bearer = HTTPBearer(auto_error=False)


def require_device(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    session: Session = Depends(get_session),
) -> DeviceToken:
    """Per-route gate for the /api/sync/ tree: resolve a Bearer device token.

    Placed HERE (beside require_role and the SYNC_PATH_PREFIX bypass it
    compensates for) rather than in app/services/devices.py — a reviewer reading
    the auth_guard bypass finds the compensating gate in the SAME file, and
    devices.py stays FastAPI-free so it remains a pure, unit-testable service
    (deviation from 28-RESEARCH.md, recorded in the SUMMARY).

    A missing credential or a wrong/unknown/revoked token both raise 401 with a
    WWW-Authenticate: Bearer header (T-28-02). The two RU messages do NOT
    distinguish unknown from revoked (V7). On success the token's last_used_at is
    stamped (staleness signal) and the row is returned.
    """
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail=DEVICE_TOKEN_REQUIRED_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = devices.lookup_active_token(session, credentials.credentials)
    if token is None:
        raise HTTPException(
            status_code=401,
            detail=DEVICE_TOKEN_INVALID_ERROR,
            headers={"WWW-Authenticate": "Bearer"},
        )
    devices.touch_last_used(session, token)
    return token
