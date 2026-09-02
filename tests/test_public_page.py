"""ВРЕМЕННАЯ публичная страница описи (app/routes/public_pages.py).

Пинит ровно то, ради чего она заведена: аноним получает страницу БЕЗ входа —
и при этом дырка в auth_guard остаётся точечной, а не открывает соседние пути.
Удаляется вместе с самой страницей.
"""

from app.routes.public_pages import (
    ARTIFACT_FILE,
    ARTIFACT_PATH,
    REPORT_FILE,
    REPORT_PATH,
)


def test_page_is_served_to_anonymous_visitor(anon_client):
    response = anon_client.get(ARTIFACT_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Опись склада «Офис»" in response.text


def test_html_file_is_present_and_self_contained(anon_client):
    html = ARTIFACT_FILE.read_text(encoding="utf-8")

    assert html.startswith("<!doctype html>")
    # рантайм-обёртка claude.ai срезана — страница не пытается говорить с parent
    assert "__FRAME" not in html and "frame-runtime" not in html


def test_neighbouring_paths_stay_behind_the_login(anon_client):
    """Точечное исключение: соседний путь под тем же префиксом НЕ публичный."""
    for path in (
        "/code/artifact/",
        "/code/artifact/other",
        "/code/report/",
        "/code/report/other",
        "/products",
    ):
        response = anon_client.get(path, follow_redirects=False)
        assert response.status_code != 200, path


def test_import_report_is_served_to_anonymous_visitor(anon_client):
    response = anon_client.get(REPORT_PATH)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Отчёт по описи склада «Офис»" in response.text


def test_import_report_file_is_present_and_self_contained(anon_client):
    html = REPORT_FILE.read_text(encoding="utf-8")

    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    # разделы, ради которых страница заведена
    for heading in (
        "Как лягут 413 партий описи",
        "Товары, которые уже были на складе",
        "Новая партия у существующего товара",
        "Названия, найденные на последнем шаге",
        "Товары без цены",
        "Где перепроверить",
    ):
        assert heading in html, heading
