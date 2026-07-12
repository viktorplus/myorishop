"""Phase 11 Plan 02: /m/search (reuses catalog.search_view unchanged)."""

from app.routes import mobile_search


def test_search_matching_query_returns_row(mobile_client_factory, product):
    client = mobile_client_factory(mobile_search.router)
    response = client.get("/m/search", params={"q": product.code}, headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert product.code in response.text
    assert product.name in response.text


def test_search_no_match_returns_empty_state_string(mobile_client_factory, product):
    client = mobile_client_factory(mobile_search.router)
    response = client.get(
        "/m/search", params={"q": "нет-такого-товара"}, headers={"HX-Request": "true"}
    )

    assert response.status_code == 200
    assert "Ничего не найдено по запросу" in response.text


def test_search_empty_query_shows_no_results_yet(mobile_client_factory, product):
    client = mobile_client_factory(mobile_search.router)
    response = client.get("/m/search")

    assert response.status_code == 200
    assert "Ничего не найдено" not in response.text
    assert "mobile-card" not in response.text


def test_search_product_detail_shows_code_name_and_warehouse_stock(
    mobile_client_factory, stocked_product
):
    client = mobile_client_factory(mobile_search.router)
    response = client.get(f"/m/search/product/{stocked_product.id}")

    assert response.status_code == 200
    body = response.text
    assert stocked_product.code in body
    assert stocked_product.name in body
    assert "8 шт." in body


def test_search_product_detail_unknown_id_returns_404(mobile_client_factory, session):
    client = mobile_client_factory(mobile_search.router)
    response = client.get("/m/search/product/does-not-exist")

    assert response.status_code == 404
