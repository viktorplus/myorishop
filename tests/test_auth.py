"""Security-core unit tests (Plan 25-03): Argon2id hashing + timing-safe compare.

These exercise the pure-Python security primitives (no HTTP / app wiring):
password hashing/verification/rehash and the constant-time token compare.
Task 3 extends this file with author_fields / CSRF / require_role tests.

CLAUDE.md safety: never assert on or print a raw password beyond the local
literals under test; never log a hash value.
"""

import asyncio
from types import SimpleNamespace

import pytest
from argon2 import PasswordHasher
from fastapi import HTTPException

from app.config import settings
from app.core import new_id
from app.models import User
from app.services import auth, security


_UNSET = object()


def _make_user(session, *, raw_password: str, password_hash=_UNSET) -> User:
    """Persist a minimal admin User carrying the given (or freshly hashed) hash.

    `password_hash` defaults to a fresh Argon2id hash of `raw_password`; pass an
    explicit value (including "") to store a malformed/empty hash under test.
    """
    stored = auth.hash_password(raw_password) if password_hash is _UNSET else password_hash
    user = User(
        id=new_id(),
        login=f"login-{new_id()[:8]}",
        display_name="Тест Пользователь",
        role="administrator",
        password_hash=stored,
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def test_password_hash_is_argon2id_phc():
    hashed = auth.hash_password("secret")
    assert hashed.startswith("$argon2id$")


def test_password_hash_is_salted_per_call():
    # Same input hashed twice must differ (random salt).
    assert auth.hash_password("secret") != auth.hash_password("secret")


def test_verify_password_accepts_correct(session):
    user = _make_user(session, raw_password="correct horse")
    assert auth.verify_password(session, user, "correct horse") is True


def test_verify_password_rejects_wrong(session):
    user = _make_user(session, raw_password="correct horse")
    assert auth.verify_password(session, user, "wrong password") is False


def test_verify_password_returns_false_on_malformed_hash(session):
    # A corrupt / empty stored hash must return False, never raise.
    user = _make_user(session, raw_password="x", password_hash="not-a-real-hash")
    assert auth.verify_password(session, user, "x") is False
    empty = _make_user(session, raw_password="x", password_hash="")
    assert auth.verify_password(session, empty, "x") is False


def test_verify_password_rehashes_weaker_params(session):
    # A hash produced with weaker-than-default params must be transparently
    # upgraded on a successful verify (check_needs_rehash → re-hash + commit).
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    weak_hash = weak.hash("upgrade me")
    user = _make_user(session, raw_password="upgrade me", password_hash=weak_hash)

    assert auth.verify_password(session, user, "upgrade me") is True
    # Stored hash was rehashed to the current (stronger) default params.
    assert user.password_hash != weak_hash
    assert user.password_hash.startswith("$argon2id$")
    # The freshly persisted hash still verifies the same password.
    assert auth.verify_password(session, user, "upgrade me") is True


def test_compare_token_equal_is_true():
    assert auth.compare_token("x", "x") is True


def test_compare_token_differ_is_false():
    assert auth.compare_token("x", "y") is False
    assert auth.compare_token("", "y") is False


# --- security.py: fake request helpers ---------------------------------------


class _FakeHeaders:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class _FakeRequest:
    """Minimal Request stand-in for the pure-function security tests.

    Provides `.session` (dict), `.headers`, `.state`, and an async `.form()`.
    """

    def __init__(self, *, session=None, headers=None, form=None, state=None):
        self.session = session if session is not None else {}
        self.headers = _FakeHeaders(headers or {})
        self._form = form or {}
        self.state = state if state is not None else SimpleNamespace()

    async def form(self):
        return self._form


# --- author_fields contextvar fallback (USER-05) -----------------------------


def test_author_fields_falls_back_to_operator_name_when_unset():
    # No user on the contextvar → (None, settings.operator_name).
    token = security._current_user.set(None)
    try:
        author_id, created_by = security.author_fields()
    finally:
        security._current_user.reset(token)
    assert author_id is None
    assert created_by == settings.operator_name


def test_author_fields_returns_user_identity_when_set():
    user = User(
        id=new_id(),
        login="attr",
        display_name="Автор Операции",
        role="operator",
        password_hash="x",
        is_active=1,
    )
    token = security._current_user.set(user)
    try:
        author_id, created_by = security.author_fields()
    finally:
        security._current_user.reset(token)
    assert author_id == user.id
    assert created_by == "Автор Операции"


# --- CSRF synchronizer token (AUTH-05) ---------------------------------------


def test_issue_csrf_stores_and_returns_a_token():
    request = _FakeRequest()
    token = security.issue_csrf(request)
    assert token
    assert request.session["csrf"] == token
    # Idempotent — a second call keeps the same token.
    assert security.issue_csrf(request) == token


def test_require_csrf_passes_on_matching_header_token():
    request = _FakeRequest(session={"csrf": "good-token"}, headers={"X-CSRF-Token": "good-token"})
    # No exception raised.
    asyncio.run(security.require_csrf(request))


def test_require_csrf_passes_on_matching_form_token():
    request = _FakeRequest(session={"csrf": "good-token"}, form={"csrf_token": "good-token"})
    asyncio.run(security.require_csrf(request))


def test_require_csrf_rejects_missing_token():
    request = _FakeRequest(session={"csrf": "good-token"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.require_csrf(request))
    assert exc.value.status_code == 403


def test_require_csrf_rejects_wrong_token():
    request = _FakeRequest(session={"csrf": "good-token"}, headers={"X-CSRF-Token": "bad-token"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.require_csrf(request))
    assert exc.value.status_code == 403


def test_require_csrf_rejects_when_session_has_no_token():
    request = _FakeRequest(session={}, headers={"X-CSRF-Token": "anything"})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(security.require_csrf(request))
    assert exc.value.status_code == 403


# --- require_role hierarchy (ROLE-03/04) -------------------------------------


def _request_for_role(role):
    user = User(
        id=new_id(),
        login=f"r-{new_id()[:8]}",
        display_name="Роль",
        role=role,
        password_hash="x",
        is_active=1,
    )
    return _FakeRequest(state=SimpleNamespace(user=user))


def test_require_role_admin_passes_admin_requirement():
    guard = security.require_role("administrator")
    # No exception.
    guard(_request_for_role("administrator"))


def test_require_role_admin_satisfies_operator_requirement():
    guard = security.require_role("operator")
    guard(_request_for_role("administrator"))  # admin ⊇ operator (ROLE-04)


def test_require_role_operator_rejected_for_admin_requirement():
    guard = security.require_role("administrator")
    with pytest.raises(HTTPException) as exc:
        guard(_request_for_role("operator"))
    assert exc.value.status_code == 403
    assert exc.value.detail == security.ACCESS_DENIED_ERROR


def test_require_role_operator_passes_operator_requirement():
    guard = security.require_role("operator")
    guard(_request_for_role("operator"))


def test_require_role_missing_user_is_403():
    guard = security.require_role("operator")
    request = _FakeRequest(state=SimpleNamespace())
    with pytest.raises(HTTPException) as exc:
        guard(request)
    assert exc.value.status_code == 403


# --- auth_guard issues CSRF before the public early-return -------------------


def test_auth_guard_issues_csrf_before_public_return():
    # A public path returns early, but a CSRF token must already be issued so
    # /login can render one (RESEARCH Pattern 3 step 1).
    request = _FakeRequest(session={})
    request.url = SimpleNamespace(path="/login")
    request.method = "GET"
    asyncio.run(security.auth_guard(request, session=None))
    assert request.session.get("csrf")


# --- Integration tests (Plan 04 Task 3): the real app-level guard ------------
#
# These use the `anon_client` fixture (real guard active, no auth override) plus
# the `login` helper from conftest. They prove the end-to-end AUTH-01/03/04/05 +
# ROLE-02 behaviours through the HTTP stack, not just the unit primitives above.

import re


def _seed_admin(session, *, login="admin", password="pw", is_active=1):
    """Persist one administrator with a real Argon2id hash for login round-trips."""
    user = User(
        id=new_id(),
        login=login,
        display_name="Админ",
        role="administrator",
        password_hash=auth.hash_password(password),
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    return user


def _csrf_from_login_page(anon_client) -> str:
    """Scrape the session CSRF token from the rendered login page hidden field."""
    html = anon_client.get("/login").text
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "login page must render a csrf_token hidden field"
    return match.group(1)


def test_guard_redirects_html_and_htmx(anon_client, session):
    _seed_admin(session)
    # Plain (HTML) GET of a protected route → 303 to /login.
    resp = anon_client.get("/products", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"
    # The same GET as an HTMX request → 401 + HX-Redirect (Pitfall 3): HTMX does
    # not swap 4xx, so the browser must be told to navigate via the header.
    hx = anon_client.get(
        "/history", headers={"HX-Request": "true"}, follow_redirects=False
    )
    assert hx.status_code == 401
    assert hx.headers["hx-redirect"] == "/login"


def test_guard_gated_export_backup(anon_client, session):
    # AUTH-01 must cover export + backup, not just the ordinary pages.
    _seed_admin(session)
    for path in ("/export", "/export/products.csv", "/backup"):
        resp = anon_client.get(path, follow_redirects=False)
        assert resp.status_code == 303, path
        assert resp.headers["location"] == "/login", path


def test_session_persist_logout(anon_client, session, login):
    # AUTH-03: login sets a signed-cookie session that survives a SECOND request;
    # logout ends it.
    _seed_admin(session, login="anna", password="s3cret")
    resp = login(anon_client, "anna", "s3cret")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/"
    # Second request (cookie persists via TestClient) reaches a protected page.
    page = anon_client.get("/products", follow_redirects=False)
    assert page.status_code == 200
    # Logout clears the session (a public path — no CSRF needed).
    out = anon_client.post("/logout", follow_redirects=False)
    assert out.status_code == 303
    assert out.headers["location"] == "/login"
    # After logout the protected page redirects to /login again.
    after = anon_client.get("/products", follow_redirects=False)
    assert after.status_code == 303
    assert after.headers["location"] == "/login"


def test_login_bad_credentials_writes_no_session(anon_client, session):
    _seed_admin(session, login="anna", password="s3cret")
    resp = anon_client.post(
        "/login",
        data={"login": "anna", "password": "wrong"},
        follow_redirects=False,
    )
    assert resp.status_code == 422
    assert "Неверный логин или пароль." in resp.text
    # No session was written → the next protected request still redirects.
    assert anon_client.get("/products", follow_redirects=False).status_code == 303


def test_first_run_setup(anon_client, session):
    # AUTH-04: zero users → every protected route redirects to /setup.
    from app.services.users import count_users

    assert count_users(session) == 0
    guarded = anon_client.get("/products", follow_redirects=False)
    assert guarded.status_code == 303
    assert guarded.headers["location"] == "/setup"
    # POST /setup creates the first administrator and logs them in.
    created = anon_client.post(
        "/setup",
        data={"display_name": "Первый", "login": "root", "password": "pw"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == "/"
    assert count_users(session) == 1
    # Now logged in: a protected page renders.
    assert anon_client.get("/products", follow_redirects=False).status_code == 200
    # Self-close: a SECOND POST /setup does NOT create another user.
    second = anon_client.post(
        "/setup",
        data={"display_name": "Второй", "login": "root2", "password": "pw"},
        follow_redirects=False,
    )
    assert second.status_code == 303
    assert second.headers["location"] == "/login"
    assert count_users(session) == 1


def test_csrf_enforced_on_protected_post(anon_client, session, login):
    # AUTH-05: an authenticated but token-less unsafe POST is rejected (403);
    # the same POST carrying the session token succeeds.
    _seed_admin(session, login="anna", password="s3cret")
    login(anon_client, "anna", "s3cret")
    no_token = anon_client.post(
        "/warehouses", data={"name": "Без токена"}, follow_redirects=False
    )
    assert no_token.status_code == 403
    token = _csrf_from_login_page(anon_client)
    with_token = anon_client.post(
        "/warehouses",
        data={"name": "С токеном"},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert with_token.status_code != 403
    assert with_token.status_code == 303
