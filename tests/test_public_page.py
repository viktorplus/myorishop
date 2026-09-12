"""Публичная страница отчёта о приходах (app/routes/public_pages.py).

Пинит ровно то, ради чего она заведена: аноним получает страницу БЕЗ входа —
и при этом дырка в auth_guard остаётся точечной, а не открывает соседние пути.
Удаляется вместе с самой страницей.
"""

from app.routes.public_pages import RECEIPTS_FILE, RECEIPTS_PATH


def test_page_is_served_to_anonymous_visitor(anon_client):
    response = anon_client.get(RECEIPTS_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Добавление товара с рукописных листов" in response.text


def test_neighbouring_paths_stay_behind_the_login(anon_client):
    """Точечное исключение: соседний путь под тем же префиксом НЕ публичный."""
    for path in (
        "/otchet-prihodov/",
        "/otchet-prihodov/other",
        "/otchet",
        "/products",
    ):
        response = anon_client.get(path, follow_redirects=False)
        assert response.status_code != 200, path


def test_the_five_pages_it_replaced_are_gone(anon_client):
    """12.09.2026 пять отдельных страниц заменены одной сводной.

    Старые адреса должны перестать отдавать 200 — и как удалённые маршруты,
    и как вычеркнутые из PUBLIC_PATHS.
    """
    for path in (
        "/code/artifact/0ac2f0bf-4df3-4de0-864a-b87d09e87305",
        "/code/report/office-import-2026-09-02",
        "/code/report/unknown-codes-2026-09-02",
        "/code/artifact/143c5a2c-d93f-4361-ae44-0059c828962a",
        "/code/report/office-receipt-2026-09-07",
    ):
        response = anon_client.get(path, follow_redirects=False)
        assert response.status_code != 200, path


def test_html_file_is_present_and_self_contained(anon_client):
    html = RECEIPTS_FILE.read_text(encoding="utf-8")

    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    assert html.count("<title>") == 1
    # рантайм-обёртка claude.ai срезана — страница не пытается говорить с parent
    assert "__FRAME" not in html and "frame-runtime" not in html


def test_page_keeps_its_own_light_and_dark_palette(anon_client):
    """Страница сама объявляет обе палитры и сама красит body.

    Светлая обёртка, скопированная сюда с чужой страницы, сломала бы её
    в тёмной теме — этот тест покраснеет раньше, чем это увидит читатель.
    """
    html = RECEIPTS_FILE.read_text(encoding="utf-8")

    assert "@media (prefers-color-scheme: dark)" in html
    assert ':root[data-theme="dark"]' in html
    assert "color-scheme:light" not in html
    assert "background:#faf9f5" not in html


def test_page_carries_a_section_per_batch(anon_client):
    """Ради чего страница заведена: четыре партии и сводка по проверкам."""
    html = RECEIPTS_FILE.read_text(encoding="utf-8")

    for heading in (
        "Четыре партии одной таблицей",
        "Чему можно доверять",
        "Опись 31 августа",
        "Опись 2 сентября",
        "Опись 7 сентября",
        "Опись 12 сентября",
        "Все 58 кодов, требующих проверки",
        "Сроки годности",
        "Как проверялось распознавание",
    ):
        assert heading in html, heading

    # у каждой партии свои три разбора — считаем именно подзаголовки,
    # иначе колонка «Не добавлено» в сводной таблице подмешалась бы в счёт
    assert html.count("<h3>Не добавлено</h3>") == 4
    assert html.count("<h3>Без названия</h3>") == 4
    assert html.count("<h3>Перепроверить</h3>") == 4
