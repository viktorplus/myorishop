"""Security-core unit tests (Plan 25-03): Argon2id hashing + timing-safe compare.

These exercise the pure-Python security primitives (no HTTP / app wiring):
password hashing/verification/rehash and the constant-time token compare.
Task 3 extends this file with author_fields / CSRF / require_role tests.

CLAUDE.md safety: never assert on or print a raw password beyond the local
literals under test; never log a hash value.
"""

from argon2 import PasswordHasher

from app.core import new_id
from app.models import User
from app.services import auth


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
