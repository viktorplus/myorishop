"""End-to-end walking-skeleton happy path (D-15): GET /.

app.main (Plan 01-03) is imported lazily inside the `client` fixture,
so this module stays collectable while only app.config exists.

The original POST /ops correction round-trip (D-15) was retired in Phase 5
Plan 4 (D-12): /corrections is now the single correction path, and
tests/test_corrections.py::test_web_ops_replaced is the authoritative
contract asserting POST /ops is gone (404/405).

Phase 23 Plan 06 (D-11/D-12 walking-skeleton retirement): GET / no longer
renders the oldest active product / correction form — it renders the
Главная dashboard (DASH-01..05, dashboard_context). The authoritative
dashboard content contract lives in tests/test_home.py; this smoke test
only proves the route boots end-to-end and htmx is vendored, not a CDN.
"""


def test_home_page_renders(client, product):
    response = client.get("/")
    assert response.status_code == 200
    # D-03: vendored htmx, never a CDN script tag
    assert "/static/htmx.min.js" in response.text
    assert "Главная" in response.text


def test_web_top_nav_has_exactly_eight_items(client):
    """NAV-08: desktop top-level nav is reduced from 17 items to exactly 8.

    Phase 24 Plan 01: Приход/Списание/Справочник/Категории/Каталоги moved
    into the Товары page toolbar; Склады/Резервные копии/Экспорт move under
    Настройки (later plans); Экспорт кассы leaves the nav entirely.
    """
    response = client.get("/")
    assert response.status_code == 200
    start = response.text.index("<nav>")
    end = response.text.index("</nav>", start)
    nav_html = response.text[start:end]
    assert nav_html.count("<a ") == 8

    expected_hrefs = [
        "/",
        "/products",
        "/sales/new",
        "/customers",
        "/history",
        "/reports",
        "/finance",
        "/settings",
    ]
    for href in expected_hrefs:
        assert f'href="{href}"' in nav_html

    expected_labels = [
        "Главная",
        "Товары",
        "Продажи",
        "Покупатели",
        "История",
        "Отчёты",
        "Финансы",
        "Настройки",
    ]
    for label in expected_labels:
        assert label in nav_html
