"""User admin service tests (Plan 25-03): create/deactivate/reactivate/reset.

Service-level only (the `session` fixture, no HTTP). Covers USER-01..04 and
ROLE-01 (the ROLES allow-list). Test names are chosen so `-k user_admin`,
`-k roles_allowlist` and `-k deactivate` select the relevant slices per
25-VALIDATION.

CLAUDE.md safety: raw passwords here are local test literals only; no hash
value is asserted on or printed.
"""

from sqlalchemy import select

from app.core import new_id
from app.models import User
from app.services import auth, users


def _seed_user(session, *, login="boss", role="administrator", password="pw") -> User:
    user, errors = users.create_user(
        session,
        display_name="Начальник",
        login=login,
        role=role,
        password=password,
    )
    assert errors == {}
    assert user is not None
    return user


# --- create_user (USER-01/02, ROLE-01) --------------------------------------


def test_user_admin_creates_user_with_role(session):
    user, errors = users.create_user(
        session,
        display_name="Оператор Один",
        login="op1",
        role="operator",
        password="secret",
    )
    assert errors == {}
    assert user is not None
    assert user.role == "operator"
    assert user.is_active == 1
    # Password is stored as an Argon2id hash, never the raw value.
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != "secret"
    assert auth.verify_password(session, user, "secret") is True


def test_user_admin_rejects_duplicate_login(session):
    _seed_user(session, login="dupe")
    user, errors = users.create_user(
        session,
        display_name="Другой",
        login="dupe",
        role="operator",
        password="secret",
    )
    assert user is None
    assert errors == {"login": users.LOGIN_TAKEN_ERROR}
    # ZERO extra writes — still exactly one user with that login.
    assert users.count_users(session) == 1


def test_user_admin_requires_login_display_and_password(session):
    user, errors = users.create_user(
        session, display_name="  ", login="  ", role="operator", password=""
    )
    assert user is None
    assert errors["login"] == users.LOGIN_REQUIRED_ERROR
    assert errors["display_name"] == users.DISPLAY_NAME_REQUIRED_ERROR
    assert errors["password"] == users.PASSWORD_REQUIRED_ERROR
    assert users.count_users(session) == 0


def test_user_admin_caps_display_name_to_snapshot_width(session):
    long_name = "Я" * 250
    user, errors = users.create_user(
        session, display_name=long_name, login="long", role="operator", password="pw"
    )
    assert errors == {}
    # Capped to the created_by (String(100)) snapshot width.
    assert len(user.display_name) == 100


# --- ROLES allow-list (ROLE-01) ---------------------------------------------


def test_roles_allowlist_rejects_unknown_role(session):
    user, errors = users.create_user(
        session, display_name="Хакер", login="x", role="superadmin", password="pw"
    )
    assert user is None
    assert errors == {"role": users.ROLE_INVALID_ERROR}
    assert users.count_users(session) == 0


def test_roles_allowlist_rejects_empty_role(session):
    user, errors = users.create_user(
        session, display_name="Ноль", login="z", role="", password="pw"
    )
    assert user is None
    assert errors == {"role": users.ROLE_INVALID_ERROR}


def test_roles_allowlist_accepts_both_roles(session):
    admin, e1 = users.create_user(
        session, display_name="A", login="a", role="administrator", password="pw"
    )
    operator, e2 = users.create_user(
        session, display_name="O", login="o", role="operator", password="pw"
    )
    assert e1 == {} and e2 == {}
    assert admin.role == "administrator"
    assert operator.role == "operator"


# --- deactivate / reactivate (USER-03) --------------------------------------


def test_deactivate_hides_from_get_active_user_but_keeps_row(session):
    admin = _seed_user(session, login="admin")
    victim = _seed_user(session, login="victim", role="operator")

    ok, errors = users.deactivate_user(session, victim.id, actor_id=admin.id)
    assert ok is True
    assert errors == {}
    # Row still exists...
    assert session.get(User, victim.id) is not None
    assert session.get(User, victim.id).is_active == 0
    # ...but get_active_user rejects it every request (USER-03).
    assert users.get_active_user(session, victim.id) is None


def test_deactivate_refuses_self(session):
    admin = _seed_user(session, login="admin")
    ok, errors = users.deactivate_user(session, admin.id, actor_id=admin.id)
    assert ok is False
    assert errors == {"user": users.SELF_DEACTIVATE_ERROR}
    # ZERO writes — the admin is still active.
    assert session.get(User, admin.id).is_active == 1


def test_deactivate_unknown_id_is_error(session):
    admin = _seed_user(session, login="admin")
    ok, errors = users.deactivate_user(session, new_id(), actor_id=admin.id)
    assert ok is False
    assert errors == {"user": users.USER_NOT_FOUND_ERROR}


def test_deactivate_preserves_past_author_attribution(session):
    # A deactivated user's id remains a valid attribution target on old rows.
    from app.models import Operation

    admin = _seed_user(session, login="admin")
    victim = _seed_user(session, login="victim", role="operator")

    product_id = new_id()
    from app.models import Product

    session.add(Product(id=product_id, name="Товар", quantity=0))
    session.commit()
    op = Operation(
        id=new_id(),
        type="correction",
        product_id=product_id,
        qty_delta=0,
        author_id=victim.id,
        device_id="test-device",
        seq=1,
        created_at="2026-07-18T00:00:00+00:00",
        created_by=victim.display_name,
    )
    session.add(op)
    session.commit()

    users.deactivate_user(session, victim.id, actor_id=admin.id)

    # The historical row still points at the (now-inactive) user, untouched.
    stored = session.get(Operation, op.id)
    assert stored.author_id == victim.id
    assert stored.created_by == victim.display_name


def test_reactivate_restores_active_flag(session):
    admin = _seed_user(session, login="admin")
    victim = _seed_user(session, login="victim", role="operator")
    users.deactivate_user(session, victim.id, actor_id=admin.id)

    assert users.reactivate_user(session, victim.id) is True
    assert users.get_active_user(session, victim.id) is not None
    # Idempotent no-op when already active or unknown.
    assert users.reactivate_user(session, victim.id) is False
    assert users.reactivate_user(session, new_id()) is False


# --- reset_password (USER-04) -----------------------------------------------


def test_reset_password_changes_hash_and_accepts_new(session):
    user = _seed_user(session, login="reset", role="operator", password="old-pass")
    old_hash = user.password_hash

    updated, errors = users.reset_password(session, user.id, "new-pass")
    assert errors == {}
    assert updated is not None
    assert updated.password_hash != old_hash
    assert auth.verify_password(session, user, "new-pass") is True
    assert auth.verify_password(session, user, "old-pass") is False


def test_reset_password_rejects_blank(session):
    user = _seed_user(session, login="reset", role="operator", password="old-pass")
    updated, errors = users.reset_password(session, user.id, "")
    assert updated is None
    assert errors == {"password": users.PASSWORD_REQUIRED_ERROR}
    # Old password still works — ZERO writes.
    assert auth.verify_password(session, user, "old-pass") is True


def test_reset_password_unknown_id_is_error(session):
    _seed_user(session, login="admin")
    updated, errors = users.reset_password(session, new_id(), "whatever")
    assert updated is None
    assert errors == {"user": users.USER_NOT_FOUND_ERROR}


def test_list_users_ordered_by_display_name(session):
    users.create_user(session, display_name="Яна", login="y", role="operator", password="pw")
    users.create_user(session, display_name="Анна", login="a", role="operator", password="pw")
    names = [u.display_name for u in users.list_users(session)]
    assert names == sorted(names)
    assert names[0] == "Анна"


# --- HTTP surface (Plan 25-05 Task 2): /settings/users create/deactivate/reset --
#
# These drive the routes + templates through the authenticated `client` fixture
# (a seeded administrator with the guard/CSRF overridden), proving the HTTP
# behaviours in the UI-SPEC (the service-level rules above are re-used, not
# re-tested). The `session` fixture is the SAME session the route sees, so a row
# created/mutated over HTTP is visible to the assertions.


def _admin(session) -> User:
    """The administrator seeded by the `client` fixture (login 'test-admin')."""
    return session.scalar(select(User).where(User.login == "test-admin"))


def test_user_admin_http_create_shows_row_and_notice(client, session):
    resp = client.post(
        "/settings/users",
        data={
            "display_name": "Оператор HTTP",
            "login": "op-http",
            "role": "operator",
            "password": "pw",
        },
    )
    assert resp.status_code == 200
    assert "Пользователь создан." in resp.text
    assert "op-http" in resp.text
    created = session.scalar(select(User).where(User.login == "op-http"))
    assert created is not None
    assert created.role == "operator"
    assert created.is_active == 1
    # The raw password never appears in the response.
    assert "pw" not in resp.text


def test_user_admin_http_duplicate_login_is_422(client, session):
    client.post(
        "/settings/users",
        data={"display_name": "Первый", "login": "dup", "role": "operator", "password": "pw"},
    )
    resp = client.post(
        "/settings/users",
        data={"display_name": "Второй", "login": "dup", "role": "operator", "password": "pw"},
    )
    assert resp.status_code == 422
    assert users.LOGIN_TAKEN_ERROR in resp.text
    # ZERO extra writes — still exactly one 'dup' (plus the seeded admin).
    assert len(list(session.scalars(select(User).where(User.login == "dup")))) == 1


def test_http_deactivate_sets_inactive_and_shows_status(client, session):
    client.post(
        "/settings/users",
        data={"display_name": "Жертва", "login": "victim", "role": "operator", "password": "pw"},
    )
    victim = session.scalar(select(User).where(User.login == "victim"))
    resp = client.post(f"/settings/users/{victim.id}/deactivate")
    assert resp.status_code == 200
    assert "Отключён" in resp.text
    assert session.get(User, victim.id).is_active == 0


def test_http_deactivate_refuses_self(client, session):
    admin = _admin(session)
    resp = client.post(f"/settings/users/{admin.id}/deactivate")
    assert resp.status_code == 422
    assert users.SELF_DEACTIVATE_ERROR in resp.text
    # ZERO writes — the acting admin stays active (no self-lockout, T-25-05-03).
    assert session.get(User, admin.id).is_active == 1


def test_http_reactivate_restores_active(client, session):
    client.post(
        "/settings/users",
        data={"display_name": "Назад", "login": "back", "role": "operator", "password": "pw"},
    )
    user = session.scalar(select(User).where(User.login == "back"))
    client.post(f"/settings/users/{user.id}/deactivate")
    resp = client.post(f"/settings/users/{user.id}/reactivate")
    assert resp.status_code == 200
    assert "Активен" in resp.text
    assert session.get(User, user.id).is_active == 1


def test_http_reset_password_updates_hash_and_never_echoes(client, session):
    client.post(
        "/settings/users",
        data={
            "display_name": "Сброс",
            "login": "resetme",
            "role": "operator",
            "password": "old-pass",
        },
    )
    user = session.scalar(select(User).where(User.login == "resetme"))
    old_hash = user.password_hash
    resp = client.post(
        f"/settings/users/{user.id}/reset-password",
        data={"new_password": "brand-new-pass"},
    )
    assert resp.status_code == 200
    assert "Пароль сброшен." in resp.text
    # The new password is written server-side and NEVER echoed back (T-25-05-05).
    assert "brand-new-pass" not in resp.text
    session.refresh(user)
    assert user.password_hash != old_hash
    assert auth.verify_password(session, user, "brand-new-pass") is True
