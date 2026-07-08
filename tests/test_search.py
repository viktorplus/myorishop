"""CAT-03 executable contract: instant product search (Plan 02-03).

Covers Cyrillic case-insensitivity (D-27, Pitfall 1), ranking exact code >
code prefix > name substring (D-26), the 20-row cap, literal LIKE-wildcard
matching (Pattern 3 autoescape), split_match segments (Pattern 5) and the
/products/search HTMX partial endpoint (D-25).

Naming convention: route/e2e tests are prefixed test_web_.
"""

from app.core import utcnow_iso
from app.services.catalog import create_product, search_products, search_view, split_match

EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}


def _make(session, code, name):
    """Create a product through the service so name_lc is maintained (D-27)."""
    product, errors = create_product(session, code=code, name=name, category="", **EMPTY_MONEY)
    assert errors == {}
    return product


def test_search_cyrillic_case_insensitive(session):
    """Pitfall 1: «губная» and «ГУБНАЯ» both find «Губная Помада» (Cyrillic fold)."""
    product = _make(session, "1234", "Губная Помада")

    for query in ("губная", "ГУБНАЯ"):
        results = search_products(session, query)
        assert product in results, f"query {query!r} must match «Губная Помада»"


def test_search_ranking_exact_prefix_substring(session):
    """D-26: exact code match first, code prefix second, name substring last."""
    _make(session, "1234", "Помада")
    _make(session, "12345", "Крем")
    _make(session, "999", "Набор 1234")

    results = search_products(session, "1234")
    assert [p.code for p in results] == ["1234", "12345", "999"]


def test_search_cap_20(session):
    """D-26: never more than 20 rows — 21 matching products yield exactly 20."""
    for code in range(500, 521):  # 21 products
        _make(session, str(code), f"Тестовая Серия {code}")

    results = search_products(session, "тестовая")
    assert len(results) == 20


def test_search_percent_and_underscore_literal(session):
    """Pattern 3: % and _ in the query are literals, never LIKE wildcards."""
    percent = _make(session, "P1", "Скидка 50% Набор")
    _make(session, "P2", "Обычный Крем")

    results = search_products(session, "%")
    assert results == [percent], "bare % must match ONLY the literal-% product"

    results = search_products(session, "50%")
    assert results == [percent]

    results = search_products(session, "_")
    assert results == [], "bare _ must match nothing (no wildcard fallthrough)"


def test_search_empty_query_first_20_by_name(session):
    """Pitfall 6: empty/whitespace query -> first 20 active products by name."""
    _make(session, "3", "Крем")
    _make(session, "1", "Помада")
    _make(session, "2", "Аромат")

    for query in ("", "   "):
        results = search_products(session, query)
        assert [p.name for p in results] == ["Аромат", "Крем", "Помада"]


def test_search_excludes_deleted(session):
    """D-20: soft-deleted products never appear in search results."""
    kept = _make(session, "1111", "Губная Помада")
    gone = _make(session, "2222", "Губная Помада Про")
    gone.deleted_at = utcnow_iso()
    session.commit()

    results = search_products(session, "губная")
    assert kept in results
    assert gone not in results


def test_split_match_segments():
    """Pattern 5: (pre, match, post) segments; match empty when not found/empty q."""
    assert split_match("Губная Помада", "помада") == ("Губная ", "Помада", "")
    assert split_match("Крем", "xyz") == ("Крем", "", "")
    assert split_match("Крем", "") == ("Крем", "", "")


def test_search_view_shape(session):
    """search_view returns q + rows with product and code/name segments."""
    product = _make(session, "1234", "Губная Помада")

    context = search_view(session, "губная")
    assert context["q"] == "губная"
    assert len(context["rows"]) == 1
    row = context["rows"][0]
    assert row["product"] is product
    assert row["name_seg"] == ("", "Губная", " Помада")
    assert row["code_seg"] == ("1234", "", "")


def test_web_search_returns_partial_with_mark(client):
    """D-25: /products/search returns ONLY the rows partial with <mark> highlight."""
    response = client.post(
        "/products",
        data={
            "code": "4321",
            "name": "Губная Помада",
            "category": "",
            "cost": "",
            "sale": "",
            "catalog": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    result = client.get("/products/search", params={"q": "губная"})
    assert result.status_code == 200
    assert "<mark>" in result.text
    assert "Помада" in result.text
    assert "<html" not in result.text  # partial only — Phase 1 rule


def test_web_search_no_results_message(client):
    """UI-SPEC: zero results render the RU empty-search message with the query."""
    result = client.get("/products/search", params={"q": "zzzzz"})
    assert result.status_code == 200
    assert "Ничего не найдено по запросу" in result.text
    assert "zzzzz" in result.text


def test_web_products_page_has_active_search_input(client):
    """Pattern 1: list page carries the debounced active-search input."""
    page = client.get("/products")
    assert page.status_code == 200
    assert 'hx-get="/products/search"' in page.text
    assert "delay:300ms" in page.text
    assert 'hx-sync="this:replace"' in page.text
    assert 'hx-target="#product-rows"' in page.text
    assert "Код или название товара…" in page.text
