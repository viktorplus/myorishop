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
