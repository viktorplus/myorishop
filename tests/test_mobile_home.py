"""Phase 11 Plan 02: /m/ home tile grid (D-03)."""

from app.routes import mobile_home

EXPECTED_HREFS = [
    "/m/sales",
    "/m/receipts",
    "/m/search",
    "/m/writeoff",
    "/m/corrections",
    "/m/transfers",
    "/m/history",
    "/m/reports/expiry",
]


def test_mobile_home_renders_all_tiles_in_order(mobile_client_factory):
    client = mobile_client_factory(mobile_home.router)
    response = client.get("/m/")

    assert response.status_code == 200
    body = response.text
    assert "<h1>MyOriShop</h1>" in body
    assert "<nav>" not in body

    positions = [body.index(f'href="{href}"') for href in EXPECTED_HREFS]
    assert positions == sorted(positions)
