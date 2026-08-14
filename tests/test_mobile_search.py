"""Phase 11 Plan 02: /m/search (reuses catalog.search_view unchanged)."""

from app.routes import mobile_search
from app.services.dictionary import add_entry


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


def test_search_product_detail_shows_breadcrumbs(mobile_client_factory, stocked_product):
    """Task 3 (quick-260813-l0y): breadcrumb trail replaces the default back link."""
    client = mobile_client_factory(mobile_search.router)
    response = client.get(f"/m/search/product/{stocked_product.id}")

    assert response.status_code == 200
    body = response.text
    assert '<a href="/m/">Главная</a>' in body
    assert '<a href="/m/products">Товары</a>' in body
    assert '<span aria-current="page">Товар</span>' in body
    assert "← Главная" not in body


def test_search_product_detail_unknown_id_returns_404(mobile_client_factory, session):
    client = mobile_client_factory(mobile_search.router)
    response = client.get("/m/search/product/does-not-exist")

    assert response.status_code == 404


def test_search_product_detail_shows_quick_action_links_for_stocked_product(
    mobile_client_factory, stocked_product
):
    client = mobile_client_factory(mobile_search.router)
    response = client.get(f"/m/search/product/{stocked_product.id}")

    assert response.status_code == 200
    assert f'href="/m/sales?code={stocked_product.code}"' in response.text
    assert f'href="/m/receipts?code={stocked_product.code}"' in response.text


def test_search_product_detail_shows_quick_action_links_for_zero_stock_product(
    mobile_client_factory, product
):
    """D-09: the quick actions must render unconditionally, even with zero stock."""
    client = mobile_client_factory(mobile_search.router)
    response = client.get(f"/m/search/product/{product.id}")

    assert response.status_code == 200
    assert f'href="/m/sales?code={product.code}"' in response.text
    assert f'href="/m/receipts?code={product.code}"' in response.text


def test_search_product_detail_shows_dictionary_quick_add_when_missing(
    client, stocked_product
):
    """Quick task 260814-je0: uses `client` (not mobile_client_factory) —
    the CTA POSTs cross-router to dictionary.router and needs a real,
    authenticated current_user for the cosmetic admin gate to evaluate true."""
    response = client.get(f"/m/search/product/{stocked_product.id}")

    assert response.status_code == 200
    assert f'/dictionary/from-product/{stocked_product.id}"' in response.text
    assert "Добавить в справочник" in response.text


def test_search_product_detail_hides_quick_add_when_already_in_dictionary(
    client, session, stocked_product
):
    add_entry(session, code=stocked_product.code, name=stocked_product.name)

    response = client.get(f"/m/search/product/{stocked_product.id}")

    assert response.status_code == 200
    assert "Добавить в справочник" not in response.text
    assert "Есть в справочнике" in response.text


def test_search_product_detail_shows_batch_edit_link_when_batches_exist(
    mobile_client_factory, stocked_product, session
):
    """quick-260813-i28: an open batch renders with an «Изменить» link."""
    from app.services.batches import open_batches

    batch = open_batches(session, stocked_product.id)[0]
    client = mobile_client_factory(mobile_search.router)
    response = client.get(f"/m/search/product/{stocked_product.id}")

    assert response.status_code == 200
    assert f'/m/batches/{batch.id}/edit"' in response.text
