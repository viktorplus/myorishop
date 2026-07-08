"""CAT-02 executable contract: reference dictionary slice (Plan 02-04).

Covers the dictionary service CRUD (D-22), the /dictionary page with
inline add/edit, the GET /dictionary/lookup autofill endpoint with its
200-fragment vs 204 branches (D-23, Pitfall 5), the helper-only rule
(D-24: dictionary writes never touch products or the ledger) and the
product-form autofill wiring.

Naming convention (used by later -k filters): route/e2e tests are
prefixed test_web_, everything else is service level.
"""

from sqlalchemy import select

from app.models import Dictionary, Operation
from app.services.catalog import create_product
from app.services.dictionary import add_entry, list_entries, lookup, update_entry

EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}


# --- Service level (D-22 / D-24) ---


def test_add_entry_creates_row_with_uuid_pk(session):
    """PD-1: 36-char UUID surrogate PK; code and name stripped on write."""
    entry, errors = add_entry(session, code=" 1234 ", name=" Губная Помада ")
    assert errors == {}
    assert entry is not None
    assert entry.code == "1234"
    assert entry.name == "Губная Помада"
    assert len(entry.id) == 36
    assert [e.id for e in list_entries(session)] == [entry.id]


def test_add_entry_rejects_duplicate_code(session):
    """UNIQUE(code): second add with the same code fails with a RU message."""
    first, errors = add_entry(session, code="1234", name="Губная Помада")
    assert errors == {}
    duplicate, errors = add_entry(session, code="1234", name="Другое Название")
    assert duplicate is None
    assert "code" in errors
    assert "Код уже есть в справочнике" in errors["code"]
    assert len(session.scalars(select(Dictionary)).all()) == 1


def test_add_entry_requires_code_and_name(session):
    """Blank code or blank name -> RU field errors, nothing written."""
    entry, errors = add_entry(session, code="   ", name="Губная Помада")
    assert entry is None
    assert errors["code"] == "Укажите код."

    entry, errors = add_entry(session, code="1234", name="   ")
    assert entry is None
    assert errors["name"] == "Укажите название."

    assert session.scalars(select(Dictionary)).all() == []


def test_update_entry_edits_code_and_name(session):
    """Same validation as add; duplicate-code check excludes the row itself."""
    entry, _ = add_entry(session, code="1234", name="Губная Помада")
    other, _ = add_entry(session, code="5678", name="Тушь Для Ресниц")

    # Saving the row with its OWN code is not a duplicate.
    updated, errors = update_entry(session, entry.id, code=" 1234 ", name=" Помада Матовая ")
    assert errors == {}
    assert updated.code == "1234"
    assert updated.name == "Помада Матовая"

    # Taking another row's code IS a duplicate.
    updated, errors = update_entry(session, entry.id, code="5678", name="Помада Матовая")
    assert updated is None
    assert "Код уже есть в справочнике" in errors["code"]

    # Blank fields rejected with the same RU messages.
    updated, errors = update_entry(session, other.id, code="", name="Тушь")
    assert updated is None
    assert errors["code"] == "Укажите код."


def test_lookup_exact_code_after_strip(session):
    """D-23: exact match on the stripped code; unknown code -> None."""
    entry, _ = add_entry(session, code="1234", name="Губная Помада")
    assert lookup(session, "1234").id == entry.id
    assert lookup(session, " 1234 ").id == entry.id
    assert lookup(session, "9999") is None


def test_dictionary_edit_does_not_touch_products(session):
    """D-24: dictionary is a helper — products and the ledger stay untouched."""
    product, errors = create_product(
        session, code="1234", name="Своё Название", category="", **EMPTY_MONEY
    )
    assert errors == {}
    ops_before = len(session.scalars(select(Operation)).all())

    entry, _ = add_entry(session, code="1234", name="Словарное Название")
    update_entry(session, entry.id, code="1234", name="Новое Словарное")

    session.refresh(product)
    assert product.name == "Своё Название"
    # Dictionary calls wrote ZERO ledger rows.
    assert len(session.scalars(select(Operation)).all()) == ops_before


# --- Web slice (routes + templates) ---


def test_web_dictionary_page_renders(client):
    """/dictionary page: RU title, add CTA, empty-state hint when no rows."""
    response = client.get("/dictionary")
    assert response.status_code == 200
    assert "Справочник" in response.text
    assert "Добавить код" in response.text
    assert "Справочник пуст" in response.text


def test_web_add_and_edit_rows(client, session):
    """POST endpoints answer with the rows partial only (never a full page)."""
    response = client.post("/dictionary", data={"code": "1234", "name": "Губная Помада"})
    assert response.status_code == 200
    assert 'id="dictionary-rows"' in response.text
    assert "Губная Помада" in response.text
    assert "<html" not in response.text

    entry = session.scalars(select(Dictionary).where(Dictionary.code == "1234")).one()
    response = client.post(
        f"/dictionary/{entry.id}", data={"code": "1234", "name": "Помада Матовая"}
    )
    assert response.status_code == 200
    assert 'id="dictionary-rows"' in response.text
    assert "Помада Матовая" in response.text
    assert "<html" not in response.text


def test_web_lookup_fills_when_name_empty(client, session):
    """Known code + empty name -> 200 name-wrap fragment with the autofill hint."""
    add_entry(session, code="1234", name="Губная Помада")
    response = client.get("/dictionary/lookup", params={"code": "1234", "name": ""})
    assert response.status_code == 200
    assert 'id="name-wrap"' in response.text
    assert "Губная Помада" in response.text
    assert "Название подставлено из справочника" in response.text


def test_web_lookup_204_when_name_present(client, session):
    """Pitfall 5: operator input is NEVER overwritten -> 204, htmx does nothing."""
    add_entry(session, code="1234", name="Губная Помада")
    response = client.get("/dictionary/lookup", params={"code": "1234", "name": "Что-то"})
    assert response.status_code == 204
    assert response.text == ""


def test_web_lookup_204_when_code_unknown(client):
    """Unknown code -> 204, the form stays as-is."""
    response = client.get("/dictionary/lookup", params={"code": "0000", "name": ""})
    assert response.status_code == 204
    assert response.text == ""


def test_web_product_form_wired_for_autofill(client):
    """D-23: code input triggers the debounced lookup targeting #name-wrap."""
    response = client.get("/products/new")
    assert response.status_code == 200
    assert 'hx-get="/dictionary/lookup"' in response.text
    assert "hx-include=\"[name='name']\"" in response.text
    assert 'hx-target="#name-wrap"' in response.text
    assert "delay:300ms" in response.text


def test_web_nav_has_dictionary_link(client):
    """Nav gains the third entry: Справочник -> /dictionary."""
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/dictionary"' in response.text
    assert "Справочник" in response.text
