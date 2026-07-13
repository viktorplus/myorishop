"""SAL-06 executable contract for the sales name->code dropdown (Plan 12-03).

Covers GET /sales/search-name (Task 1: D-08/D-09/D-10) and the shared
sale_name_field.html wiring that survives both the initial row render and
the /sales/lookup OOB swap (Task 2: D-09/D-11).

Naming convention (matches tests/test_sales.py): route/e2e tests are
prefixed test_web_.
"""

from app.services.catalog import create_product

EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}


def _make(session, code, name):
    """Create a product through the service so name_lc is maintained (D-27) —
    the conftest `product` fixture inserts the row directly and never
    populates name_lc, so a name-substring match needs this helper instead
    (mirrors tests/test_search.py's `_make`)."""
    product, errors = create_product(session, code=code, name=name, category="", **EMPTY_MONEY)
    assert errors == {}
    return product


def test_web_search_name_below_threshold_returns_204(client):
    """D-10: fewer than 3 characters after strip -> 204, regardless of padding."""
    response = client.get("/sales/search-name", params={"q": "ab"})
    assert response.status_code == 204
    assert response.text == ""

    response = client.get("/sales/search-name", params={"q": "  ab  "})
    assert response.status_code == 204

    response = client.get("/sales/search-name", params={"q": ""})
    assert response.status_code == 204


def test_web_search_name_matches_render_mark_highlighted_dropdown(client, session):
    """D-08/D-09: 3+ chars matching a product's name -> 200, response
    contains both code and name with <mark> around the matched substring."""
    match = _make(session, "AUTO-1", "Тестовый крем")
    response = client.get("/sales/search-name", params={"q": "Тест"})
    assert response.status_code == 200
    text = response.text
    assert match.code in text
    # D-09: the matched substring is split into pre/<mark>/post segments, so
    # the full name never appears as one contiguous run — check the pieces.
    assert "<mark>Тест</mark>овый крем" in text


def test_web_search_name_no_matches_shows_muted_message(client, product):
    """D-10: 3+ chars with no product match -> exact zero-results copy."""
    response = client.get("/sales/search-name", params={"q": "zzz"})
    assert response.status_code == 200
    assert "Совпадений не найдено." in response.text


def test_web_search_name_malformed_row_is_discarded(client, session):
    """T-12-07: a row value outside _ROW_ID_RE's allow-list collapses to ""
    rather than being echoed into the rendered ids."""
    _make(session, "AUTO-2", "Тестовый крем")
    response = client.get(
        "/sales/search-name", params={"q": "Тест", "row": "not-a-uuid"}
    )
    assert response.status_code == 200
    assert "not-a-uuid" not in response.text


def test_web_sale_new_first_row_wires_debounced_name_search(client):
    """Task 2: the initial /sales/new row includes the name-input id, the
    hx-get trigger, and the persistent name-dropdown target."""
    response = client.get("/sales/new")
    assert response.status_code == 200
    text = response.text
    assert 'id="name-input"' in text
    assert 'hx-get="/sales/search-name"' in text
    assert 'id="name-dropdown"' in text


def test_web_sale_lookup_response_still_wires_debounced_name_search(
    client, session, product
):
    """Task 2 regression guard: a code-triggered /sales/lookup OOB swap must
    NOT drop the debounced name->code dropdown wiring."""
    response = client.get(
        "/sales/lookup", params={"code[]": product.code, "name[]": "", "price[]": ""}
    )
    assert response.status_code == 200
    text = response.text
    assert 'hx-get="/sales/search-name"' in text
    assert 'id="name-dropdown"' in text
