"""User admin service (USER-01..04, ROLE-01): create/deactivate/reactivate/reset.

Mirrors the warehouses service: validate → gate → single commit, returning the
established `(obj | None, errors)` shape with HTML-free RU messages (UI-SPEC
Copywriting Contract). This is the security-critical tier (V5): the `ROLES`
allow-list, the unique-login check and every required-field rule are enforced
HERE, never in a route. Users are never hard-deleted — `is_active` is a
soft-disable flag so past ledger rows keep their `author_id` (USER-03).

CLAUDE.md safety: a raw password is hashed via `auth.hash_password` before
store and is never echoed back or logged.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import ROLES, User
from app.services.auth import hash_password

# RU validation messages (UI-SPEC Copywriting Contract, lines 138-142). HTML-free.
LOGIN_REQUIRED_ERROR = "Введите логин."
DISPLAY_NAME_REQUIRED_ERROR = "Укажите отображаемое имя."
LOGIN_TAKEN_ERROR = "Такой логин уже занят."
ROLE_INVALID_ERROR = "Выберите роль из списка."
PASSWORD_REQUIRED_ERROR = "Задайте пароль."
USER_NOT_FOUND_ERROR = "Пользователь не найден."
SELF_DEACTIVATE_ERROR = "Нельзя отключить самого себя."

# display_name (String(200)) is snapshotted into the append-only ledger's
# created_by (String(100)) at write time, so it is capped to that width here.
_DISPLAY_NAME_MAX = 100


def count_users(session: Session) -> int:
    """Total number of user rows (0 = first-run, triggers /setup — AUTH-04)."""
    return session.scalar(select(func.count()).select_from(User)) or 0


def get_active_user(session, user_id: str) -> User | None:
    """Return the user only if it exists AND is active (USER-03).

    The guard calls this every request, so a deactivated user's still-valid
    session cookie is rejected on the next request.
    """
    user = session.get(User, user_id)
    if user is None or user.is_active != 1:
        return None
    return user


def list_users(session: Session) -> list[User]:
    """All users ordered by display_name (user-mgmt page + history/report filter)."""
    return list(session.scalars(select(User).order_by(User.display_name)))


def create_user(
    session: Session, *, display_name: str, login: str, role: str, password: str
) -> tuple[User | None, dict[str, str]]:
    """Create a user with a hashed password; validate against the ROLES allow-list.

    Validates: display_name required (capped to the created_by snapshot width),
    login required + not already taken, role in `ROLES`, password non-empty.
    On success the password is hashed and one row is inserted with is_active=1.
    ZERO writes on any validation failure.
    """
    display_name = display_name.strip()
    login = login.strip()
    role = (role or "").strip()
    errors: dict[str, str] = {}

    if not display_name:
        errors["display_name"] = DISPLAY_NAME_REQUIRED_ERROR
    if not login:
        errors["login"] = LOGIN_REQUIRED_ERROR
    elif session.scalar(select(User).where(User.login == login)) is not None:
        errors["login"] = LOGIN_TAKEN_ERROR
    if role not in ROLES:
        errors["role"] = ROLE_INVALID_ERROR
    if not password:
        errors["password"] = PASSWORD_REQUIRED_ERROR

    if errors:
        return None, errors

    user = User(
        id=new_id(),
        login=login,
        display_name=display_name[:_DISPLAY_NAME_MAX],
        role=role,
        password_hash=hash_password(password),
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user, {}


def deactivate_user(
    session: Session, user_id: str, *, actor_id: str
) -> tuple[bool, dict[str, str]]:
    """Soft-disable a user (is_active=0); an admin cannot disable themselves.

    Returns (True, {}) on success; (False, errors) on unknown id or a
    self-deactivation attempt (distinct error, ZERO writes). Past operations
    keep their author_id — the row is never deleted (USER-03).
    """
    if user_id == actor_id:
        return False, {"user": SELF_DEACTIVATE_ERROR}
    user = session.get(User, user_id)
    if user is None:
        return False, {"user": USER_NOT_FOUND_ERROR}
    user.is_active = 0
    session.commit()
    return True, {}


def reactivate_user(session: Session, user_id: str) -> bool:
    """Re-enable a user (is_active=1); idempotent no-op on unknown/already-active."""
    user = session.get(User, user_id)
    if user is None or user.is_active == 1:
        return False
    user.is_active = 1
    session.commit()
    return True


def reset_password(
    session: Session, user_id: str, new_password: str
) -> tuple[User | None, dict[str, str]]:
    """Re-hash and store a new password for a user (USER-04).

    Validates the password is non-empty; unknown id is a distinct error. The
    raw password is never echoed back. ZERO writes on failure.
    """
    if not new_password:
        return None, {"password": PASSWORD_REQUIRED_ERROR}
    user = session.get(User, user_id)
    if user is None:
        return None, {"user": USER_NOT_FOUND_ERROR}
    user.password_hash = hash_password(new_password)
    session.commit()
    return user, {}
