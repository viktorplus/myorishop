"""End-to-end walking-skeleton happy path (D-15): GET /.

app.main (Plan 01-03) is imported lazily inside the `client` fixture,
so this module stays collectable while only app.config exists.

The original POST /ops correction round-trip (D-15) was retired in Phase 5
Plan 4 (D-12): /corrections is now the single correction path, and
tests/test_corrections.py::test_web_ops_replaced is the authoritative
contract asserting POST /ops is gone (404/405).
"""


def test_home_page_renders(client, product):
    response = client.get("/")
    assert response.status_code == 200
    # D-03: vendored htmx, never a CDN script tag
    assert "/static/htmx.min.js" in response.text
    assert "Тестовый товар" in response.text
