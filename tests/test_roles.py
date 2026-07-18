"""Role-boundary HTTP tests (Plan 25-05 Task 3): ROLE-03 + ROLE-04.

Drives the REAL app-level guard (the `anon_client` fixture, no auth override)
plus a real `POST /login`, proving the SERVER-SIDE role boundary — not a
menu-hide. `-k operator_blocked` covers ROLE-03 (an operator gets 403 on every
admin surface but still reaches the operator routes); `-k admin_full_access`
covers ROLE-04 (an administrator, admin ⊇ operator, reaches everything and can
create a user).

CLAUDE.md safety: passwords here are local test literals; no hash is asserted on.
"""

import re

from sqlalchemy import select

from app.core import new_id
from app.models import User
from app.services import auth

# The four admin-only sections gated by require_role("administrator") in
# app/main.py (ROLE-03). Every OTHER router stays operator-accessible.
ADMIN_ROUTES = ("/settings/users", "/warehouses", "/dictionary", "/settings")
# A representative slice of the operator-accessible routers.
OPERATOR_ROUTES = ("/products", "/history", "/sales/new", "/finance")


def _seed(session, *, login, password, role):
    """Persist one user with a real Argon2id hash for login round-trips."""
    user = User(
        id=new_id(),
        login=login,
        display_name=f"Пользователь {login}",
        role=role,
        password_hash=auth.hash_password(password),
        is_active=1,
    )
    session.add(user)
    session.commit()
    return user


def _csrf(anon_client) -> str:
    """Scrape the session CSRF token from the rendered login page hidden field."""
    html = anon_client.get("/login").text
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "login page must render a csrf_token hidden field"
    return match.group(1)


def test_operator_blocked_from_admin_routes(anon_client, session, login):
    # ROLE-02/03: an operator is blocked SERVER-SIDE from every admin section.
    _seed(session, login="op", password="pw", role="operator")
    assert login(anon_client, "op", "pw").status_code == 303

    for path in ADMIN_ROUTES:
        resp = anon_client.get(path, follow_redirects=False)
        assert resp.status_code == 403, path

    # A state-changing admin POST is blocked too (with a VALID CSRF token, so the
    # 403 is the ROLE gate, not the CSRF gate — proving the server-side boundary).
    token = _csrf(anon_client)
    created = anon_client.post(
        "/settings/users",
        data={"display_name": "X", "login": "y", "role": "operator", "password": "pw"},
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert created.status_code == 403

    # ...but the operator still reaches every operator route.
    for path in OPERATOR_ROUTES:
        resp = anon_client.get(path, follow_redirects=False)
        assert resp.status_code == 200, path


def test_admin_full_access(anon_client, session, login):
    # ROLE-04: an administrator (admin ⊇ operator) reaches every admin AND
    # operator route, and can create a user.
    _seed(session, login="boss", password="pw", role="administrator")
    assert login(anon_client, "boss", "pw").status_code == 303

    for path in ADMIN_ROUTES + OPERATOR_ROUTES:
        resp = anon_client.get(path, follow_redirects=False)
        assert resp.status_code == 200, path

    token = _csrf(anon_client)
    created = anon_client.post(
        "/settings/users",
        data={
            "display_name": "Новый оператор",
            "login": "new-op",
            "role": "operator",
            "password": "pw",
        },
        headers={"X-CSRF-Token": token},
        follow_redirects=False,
    )
    assert created.status_code == 200
    assert "Пользователь создан." in created.text
    assert session.scalar(select(User).where(User.login == "new-op")) is not None
