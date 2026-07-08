"""End-to-end walking-skeleton happy path (D-15): GET / and POST /ops.

app.main (Plan 01-03) is imported lazily inside the `client` fixture,
so this module stays collectable while only app.config exists.
"""

from app.config import settings


def test_home_page_renders(client, product):
    response = client.get("/")
    assert response.status_code == 200
    # D-03: vendored htmx, never a CDN script tag
    assert "/static/htmx.min.js" in response.text
    assert "Тестовый товар" in response.text


def test_post_ops_records_correction(client, session, product):
    response = client.post(
        "/ops",
        data={"product_id": product.id, "qty_delta": "3"},
    )
    assert response.status_code == 200
    # FND-03: the partial shows who recorded the operation
    assert settings.operator_name in response.text
    # updated stock is rendered (IN-03: no vacuous `or "3"` fallback —
    # the partial renders the quantity as <strong>3</strong> / <td>3</td>)
    assert ">3<" in response.text

    session.expire_all()
    assert product.quantity == 3


def test_post_ops_unknown_product_returns_404(client, session):
    """WR-04: stale/tampered product_id yields a 4xx, not an unhandled 500."""
    response = client.post(
        "/ops",
        data={"product_id": "no-such-id", "qty_delta": "1"},
    )
    assert response.status_code == 404
