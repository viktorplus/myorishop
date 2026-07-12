"""Phase 11 Plan 09: end-to-end reachability regression test.

Uses the REAL `client` fixture (bound to app.main.app), not
`mobile_client_factory` — the point of this module is proving every
mobile router built in Plans 02-08 is actually registered and reachable
in the real running application, and that every pre-existing desktop
route still works alongside it (ROADMAP criterion 4: purely additive).
"""

MOBILE_TILE_PATHS = [
    "/m/sales",
    "/m/receipts",
    "/m/search",
    "/m/writeoff",
    "/m/corrections",
    "/m/transfers",
    "/m/history",
    "/m/reports/expiry",
]

DESKTOP_NAV_PATHS = [
    "/products",
    "/categories",
    "/warehouses",
    "/receipts/new",
    "/sales/new",
    "/writeoff",
    "/transfers",
    "/customers",
    "/history",
    "/reports",
    "/export",
    "/dictionary",
    "/backup",
]


def test_mobile_home_lists_all_eight_tile_hrefs(client):
    response = client.get("/m/")
    assert response.status_code == 200
    for path in MOBILE_TILE_PATHS:
        assert path in response.text


def test_mobile_home_itself_is_reachable(client):
    response = client.get("/m/")
    assert response.status_code != 404


def test_every_mobile_tile_path_is_reachable(client):
    for path in MOBILE_TILE_PATHS:
        response = client.get(path)
        assert response.status_code != 404, f"{path} returned 404"
        assert response.status_code == 200, f"{path} returned {response.status_code}"


def test_desktop_home_still_renders_with_redirect_script(client, product):
    response = client.get("/")
    assert response.status_code == 200
    # D-02 viewport-width redirect script must still be present — TestClient
    # cannot execute JS, so this only proves the script text is intact
    # (documented limit of automated coverage for D-02 per RESEARCH.md).
    assert 'matchMedia("(max-width: 599px)")' in response.text


def test_every_preexisting_desktop_nav_route_still_returns_200(client, product):
    for path in DESKTOP_NAV_PATHS:
        response = client.get(path)
        assert response.status_code == 200, f"{path} returned {response.status_code}"
