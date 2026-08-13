"""Nav-chrome render tests (Plan 25-06 Task 3): AUTH-05 CSRF + ROLE-03 menu-hide.

Drives the REAL app-level guard (`anon_client`, no auth override) plus a real
`POST /login`, then asserts on the RENDERED chrome of `base.html` /
`mobile_base.html`:
  - the `<body hx-headers>` line carries `X-CSRF-Token` on every page (AUTH-05);
  - the admin-only «Настройки» nav link is shown for an administrator and hidden
    for an operator (ROLE-03 — cosmetic menu-hide only; the authoritative 403
    boundary is already proven server-side in test_roles.py);
  - a «Выйти» logout control renders the logged-in user's display name.

These are string/render assertions on purpose: the menu-hide is a UX affordance,
never the security boundary.

CLAUDE.md safety: passwords here are local test literals; no hash is asserted on.
"""

from app.core import new_id
from app.models import Batch, User
from app.routes import nav_section, templates
from app.services import auth


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


def test_desktop_nav_admin_sees_settings_and_logout(anon_client, session, login):
    # An administrator: CSRF header + «Настройки» link + «Выйти» control.
    _seed(session, login="boss", password="pw", role="administrator")
    assert login(anon_client, "boss", "pw").status_code == 303

    html = anon_client.get("/history").text
    assert "X-CSRF-Token" in html  # AUTH-05: body hx-headers carries the token
    assert ">Настройки<" in html  # ROLE-03: admin sees the admin menu
    assert "Пользователь boss · Выйти" in html  # logout control shows the user


def test_desktop_nav_operator_hides_settings_but_has_logout(anon_client, session, login):
    # An operator: CSRF header + «Выйти», but the «Настройки» link is HIDDEN.
    _seed(session, login="op", password="pw", role="operator")
    assert login(anon_client, "op", "pw").status_code == 303

    html = anon_client.get("/history").text
    assert "X-CSRF-Token" in html  # AUTH-05: header renders for every role
    assert ">Настройки<" not in html  # ROLE-03: operator menu-hide (cosmetic)
    assert "Пользователь op · Выйти" in html  # logout control shows the user


def test_finance_report_activates_finance_not_settings(anon_client, session, login):
    # Plan 25-09 (ROLE-03 gap): the operator-visible /finance/report highlights
    # «Финансы» (owns the whole /finance subtree), NOT the admin «Настройки» tab;
    # /settings still highlights «Настройки». Seed an administrator so both
    # admin-visible pages render. Active-state (CSS class) only — no access change.
    _seed(session, login="boss", password="pw", role="administrator")
    assert login(anon_client, "boss", "pw").status_code == 303

    report_html = anon_client.get("/finance/report").text
    assert '<a href="/finance" class="active">Финансы</a>' in report_html
    assert '<a href="/settings" class="active">Настройки</a>' not in report_html

    settings_html = anon_client.get("/settings").text
    assert '<a href="/settings" class="active">Настройки</a>' in settings_html


def test_mobile_nav_carries_csrf_and_logout(anon_client, session, login):
    # Mobile chrome (mobile_base.html) carries the CSRF header + a «Выйти»
    # affordance for the logged-in user.
    _seed(session, login="boss", password="pw", role="administrator")
    assert login(anon_client, "boss", "pw").status_code == 303

    html = anon_client.get("/m/").text
    assert "X-CSRF-Token" in html  # AUTH-05: duplicated body hx-headers on mobile
    assert "hx-post=\"/logout\"" in html  # logout affordance posts to /logout
    assert "Пользователь boss · Выйти" in html  # shows the logged-in user


# --- Task 1 (quick-260813-l0y): shared nav_section() table + breadcrumbs ---


def test_nav_section_maps_every_locked_prefix():
    """nav_section() covers every locked-scope prefix from <behavior> exactly."""
    cases = {
        # "products" group — desktop.
        "/products": "products",
        "/batches/some-id/edit": "products",
        "/receipts/new": "products",
        "/writeoff": "products",
        "/transfers": "products",
        "/corrections": "products",
        "/categories": "products",
        "/dictionary": "products",
        "/catalogs": "products",
        "/warehouses": "products",
        # "products" group — mobile twins.
        "/m/products": "products",
        "/m/batches/some-id/edit": "products",
        "/m/receipts": "products",
        "/m/writeoff": "products",
        "/m/transfers": "products",
        "/m/corrections": "products",
        "/m/search": "products",
        # other sections.
        "/sales/new": "sales",
        "/m/sales": "sales",
        "/customers": "customers",
        "/m/customers": "customers",
        "/returns": "history",
        "/m/returns": "history",
        "/history": "history",
        "/m/history": "history",
        "/reports": "reports",
        "/m/reports/expiry": "reports",
        "/finance": "finance",
        "/m/finance": "finance",
        "/settings": "settings",
        "/settings/users": "settings",
        # home tiles own no section.
        "/": None,
        "/m/": None,
    }
    for path, expected in cases.items():
        assert nav_section(path) == expected, path


def test_breadcrumbs_partial_renders_links_and_final_crumb_as_text():
    html = templates.env.get_template("partials/breadcrumbs.html").render(
        crumbs=[
            {"label": "Главная", "href": "/"},
            {"label": "Товары", "href": "/products"},
            {"label": "Партия", "href": None},
        ]
    )
    assert '<a href="/">Главная</a>' in html
    assert '<a href="/products">Товары</a>' in html
    assert '<span aria-current="page">Партия</span>' in html
    assert "<a" not in html.split('<span aria-current="page">')[1]


def test_desktop_nav_products_active_on_nested_screens(
    anon_client, session, login, product, warehouse
):
    _seed(session, login="boss", password="pw", role="administrator")
    assert login(anon_client, "boss", "pw").status_code == 303
    batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=1)
    session.add(batch)
    session.commit()

    for path in (
        f"/batches/{batch.id}/edit",
        "/receipts/new",
        "/writeoff",
        "/transfers",
        "/corrections",
        "/categories",
        "/dictionary",
        "/catalogs",
        "/warehouses",
    ):
        assert '<a href="/products" class="active">Товары</a>' in anon_client.get(path).text, path


def test_mobile_nav_products_active_on_nested_screens(
    anon_client, session, login, product, warehouse
):
    _seed(session, login="boss", password="pw", role="administrator")
    assert login(anon_client, "boss", "pw").status_code == 303
    batch = Batch(id=new_id(), product_id=product.id, warehouse_id=warehouse.id, quantity=1)
    session.add(batch)
    session.commit()

    for path in (
        f"/m/batches/{batch.id}/edit",
        f"/m/search/product/{product.id}",
        "/m/search",
        "/m/receipts",
        "/m/writeoff",
        "/m/transfers",
        "/m/corrections",
    ):
        assert '<a href="/m/products" class="active">Товары</a>' in anon_client.get(path).text, path
