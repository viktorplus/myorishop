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

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import User
from app.services.auth import compare_token
from app.services.users import count_users, get_active_user

# Only login/logout/first-run are reachable without a session. StaticFiles is a
# mount (not a router), so app-level dependencies never apply to it — /static
# stays public automatically (RESEARCH Pattern 3).
PUBLIC_PATHS = {"/login", "/logout", "/setup"}

# UI-SPEC Copywriting Contract (line 143): operator hits an admin route.
ACCESS_DENIED_ERROR = "Доступ только для администратора."

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
      3. zero users → /setup (first-run, AUTH-04);
      4. no active session user → clear + /login (AUTH-01, USER-03);
      5. unsafe method → validate CSRF (AUTH-05);
      6. attach the user to the contextvar + request.state for attribution.
    """
    issue_csrf(request)  # (1)
    if request.url.path in PUBLIC_PATHS:  # (2)
        return
    if count_users(session) == 0:  # (3) AUTH-04 first-run
        raise NotAuthenticated(redirect="/setup")
    user_id = request.session.get("user_id")  # (4)
    user = get_active_user(session, user_id) if user_id else None
    if user is None:
        request.session.pop("user_id", None)
        raise NotAuthenticated(redirect="/login")
    if request.method not in ("GET", "HEAD", "OPTIONS"):  # (5) AUTH-05
        await require_csrf(request)
    _current_user.set(user)  # (6)
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
