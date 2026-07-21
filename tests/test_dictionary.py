"""CAT-02 executable contract: reference dictionary slice (Plan 02-04).

Covers the dictionary service CRUD (D-22), the /dictionary page with
inline add/edit, the GET /dictionary/lookup autofill endpoint with its
200-fragment vs 204 branches (D-23, Pitfall 5), the helper-only rule
(D-24: dictionary writes never touch products or the ledger) and the
product-form autofill wiring.

Naming convention (used by later -k filters): route/e2e tests are
prefixed test_web_, everything else is service level.
"""

import sqlite3
from contextlib import closing

from alembic.config import Config
from sqlalchemy import select

from alembic import command
from app.config import settings
from app.models import Dictionary, Operation
from app.services.catalog import create_product
from app.services.dictionary import add_entry, list_entries, lookup, update_entry
from app.services.rubrics import RUBRICS

EMPTY_MONEY = {"cost_raw": "", "sale_raw": ""}  # D-01/Pitfall 4 (Phase 18 plan 02)


# --- Service level (D-22 / D-24) ---


def test_add_entry_creates_row_with_uuid_pk(session):
    """PD-1: 36-char UUID surrogate PK; code and name stripped on write."""
    entry, errors = add_entry(session, code=" 1234 ", name=" Губная Помада ")
    assert errors == {}
    assert entry is not None
    assert entry.code == "1234"
    assert entry.name == "Губная Помада"
    assert len(entry.id) == 36
    assert [e.id for e in list_entries(session)["entries"]] == [entry.id]
    # Phase 14 (LIST-02): name_lc kept in sync on create.
    assert entry.name_lc == "губная помада"


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


def test_add_entry_duplicate_race_returns_ru_error_not_500(session, monkeypatch):
    """WR-02: a duplicate landing between check and commit must not raise.

    Simulate the two-tab race by disabling the SELECT-based duplicate check —
    the DB uq_dictionary_code then fires at commit and must be translated
    into the same RU error shape instead of an unhandled IntegrityError.
    """
    from app.services import dictionary as dictionary_service

    entry, errors = add_entry(session, code="1234", name="Губная Помада")
    assert errors == {}

    monkeypatch.setattr(
        dictionary_service,
        "_validate",
        lambda session, code, name, **kw: (code.strip(), name.strip(), {}),
    )
    duplicate, errors = add_entry(session, code="1234", name="Другое Название")
    assert duplicate is None
    assert "Код уже есть в справочнике" in errors["code"]
    # The session is usable again after the rollback.
    assert len(session.scalars(select(Dictionary)).all()) == 1


def test_update_entry_edits_code_and_name(session):
    """Same validation as add; duplicate-code check excludes the row itself."""
    entry, _ = add_entry(session, code="1234", name="Губная Помада")
    other, _ = add_entry(session, code="5678", name="Тушь Для Ресниц")

    # Saving the row with its OWN code is not a duplicate.
    updated, errors = update_entry(session, entry.id, code=" 1234 ", name=" Помада Матовая ")
    assert errors == {}
    assert updated.code == "1234"
    assert updated.name == "Помада Матовая"
    # Phase 14 (LIST-02): name_lc refreshed on update.
    assert updated.name_lc == "помада матовая"

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


# --- Phase 14 (LIST-01/02/03): SQL-side filter/sort/pagination ---


def test_list_entries_filters_by_code_substring(session):
    """code filter is a CONTAINS match, not just a prefix match."""
    add_entry(session, code="1234", name="Помада")
    add_entry(session, code="12345", name="Тушь")
    add_entry(session, code="999", name="Тени")

    result = list_entries(session, code="1234")
    assert result["total"] == 2
    assert {e.code for e in result["entries"]} == {"1234", "12345"}


def test_list_entries_filters_by_name_cyrillic_safe(session):
    """name filter matches name_lc, folding Cyrillic case in Python."""
    add_entry(session, code="1234", name="Губная Помада")
    add_entry(session, code="5678", name="Тушь Для Ресниц")

    for query in ("помада", "ПОМАДА", "Помада"):
        result = list_entries(session, name=query)
        assert result["total"] == 1
        assert result["entries"][0].code == "1234"


def test_list_entries_sort_by_name(session):
    """sort='name' orders by name_lc asc; default stays code asc (D-07)."""
    add_entry(session, code="2", name="Яблоко")
    add_entry(session, code="1", name="Апельсин")

    by_name = list_entries(session, sort="name")
    assert [e.code for e in by_name["entries"]] == ["1", "2"]

    by_default = list_entries(session)
    assert [e.code for e in by_default["entries"]] == ["1", "2"]


def test_list_entries_paginates_and_clamps_page(session):
    """20/page, total/total_pages reflect the filtered set; page clamps."""
    for i in range(45):
        add_entry(session, code=f"{i:02d}", name=f"Товар {i:02d}")

    first = list_entries(session, page=0)
    assert len(first["entries"]) == 20
    assert first["total"] == 45
    assert first["total_pages"] == 3

    clamped = list_entries(session, page=99)
    assert clamped["page"] == 2
    assert len(clamped["entries"]) == 5


def test_migration_0012_adds_name_lc_and_backfills_cyrillic(tmp_path, monkeypatch):
    """Migration 0012 (LIST-02): adds dictionary.name_lc, backfills existing
    rows in PYTHON (SQLite lower() is ASCII-only and cannot fold Cyrillic —
    mirrors migration 0002's frozen products.name_lc precedent)."""
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file.as_posix()}")
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0011")

    now = "2026-07-14T00:00:00+00:00"
    with closing(sqlite3.connect(db_file)) as conn:
        conn.execute(
            "INSERT INTO dictionary (id, code, name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("00000000-0000-4000-8000-000000000012", "1234", "Губная Помада", now, now),
        )
        conn.commit()

    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(dictionary)")}
        assert "name_lc" in cols

        (name_lc,) = conn.execute(
            "SELECT name_lc FROM dictionary WHERE code = ?", ("1234",)
        ).fetchone()
        assert name_lc == "губная помада"

        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
        }
        assert "ix_dictionary_name_lc" in indexes


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


def test_web_add_invalid_returns_swappable_422_partial(client, session):
    """CR-01 contract: errors come back as 422 AND htmx is configured to swap 422.

    htmx 2 default responseHandling discards 4xx bodies; base.html must opt
    422 into swapping, otherwise the RU validation message never renders.
    """
    # Blank code -> 422 with the RU field error in the rows partial.
    response = client.post("/dictionary", data={"code": "  ", "name": "Помада"})
    assert response.status_code == 422
    assert 'id="dictionary-rows"' in response.text
    assert "Укажите код." in response.text

    # Duplicate code on inline edit -> 422 with the RU duplicate message.
    add_entry(session, code="1234", name="Губная Помада")
    entry, _ = add_entry(session, code="5678", name="Тушь Для Ресниц")
    response = client.post(f"/dictionary/{entry.id}", data={"code": "1234", "name": "Тушь"})
    assert response.status_code == 422
    assert "Код уже есть в справочнике" in response.text

    # Config-level assertion: any full page carries the htmx-config meta
    # that opts 422 into swapping (this is what makes the 422 body visible).
    page = client.get("/dictionary")
    assert 'name="htmx-config"' in page.text
    assert '{"code":"422","swap":true}' in page.text


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
    assert "hx-include=\"[name='name'], [name='category']\"" in response.text
    assert 'hx-target="#name-wrap"' in response.text
    assert "delay:300ms" in response.text


def test_web_lookup_fills_category_when_empty(client, session):
    """CAT-06: known code with a rubric + both name/category empty -> category OOB fill."""
    entry, _ = add_entry(session, code="1234", name="Губная Помада")
    entry.rubric = "Макияж"
    session.commit()

    response = client.get(
        "/dictionary/lookup", params={"code": "1234", "name": "", "category": ""}
    )
    assert response.status_code == 200
    assert 'id="category"' in response.text
    assert 'hx-swap-oob="true"' in response.text
    assert "Макияж" in response.text


def test_web_lookup_fills_category_only_when_name_already_present(client, session):
    """Category fills independently of name already being set (no name autofill hint)."""
    entry, _ = add_entry(session, code="1234", name="Губная Помада")
    entry.rubric = "Макияж"
    session.commit()

    response = client.get(
        "/dictionary/lookup",
        params={"code": "1234", "name": "Уже заполнено", "category": ""},
    )
    assert response.status_code == 200
    assert 'id="category"' in response.text
    assert "Макияж" in response.text
    assert "Название подставлено из справочника" not in response.text


def test_web_lookup_does_not_overwrite_existing_category(client, session):
    """Pitfall 5 mirrored for category: an operator-entered value is never overwritten."""
    entry, _ = add_entry(session, code="1234", name="Губная Помада")
    entry.rubric = "Макияж"
    session.commit()

    response = client.get(
        "/dictionary/lookup",
        params={"code": "1234", "name": "", "category": "Уже заполнено"},
    )
    assert response.status_code == 200
    assert 'id="category"' not in response.text


def test_web_dictionary_shows_rubric_column(client, session):
    """CAT-06: the list renders a read-only Категория column (rubric or —)."""
    with_rubric, _ = add_entry(session, code="1234", name="Помада")
    with_rubric.rubric = "Макияж"
    session.commit()
    add_entry(session, code="5678", name="Тушь")

    response = client.get("/dictionary")
    assert response.status_code == 200
    assert "Категория" in response.text
    assert "Макияж" in response.text
    assert "—" in response.text


def test_web_nav_has_dictionary_link(client):
    """Phase 24: Справочник -> /dictionary moved from the top nav into the
    Товары page toolbar (D-01/D-04); verify reachability there instead."""
    response = client.get("/products")
    assert response.status_code == 200
    assert 'href="/dictionary"' in response.text
    assert "Справочник" in response.text


# --- Phase 14 (LIST-01/02/03): header-row filters, sort, pagination ---


def test_web_dictionary_filters_by_code(client, session):
    """Header-row code filter narrows the rendered rows (D-04/D-05)."""
    add_entry(session, code="1234", name="Помада")
    add_entry(session, code="5678", name="Тушь")

    response = client.get("/dictionary", params={"code": "1234"})
    assert response.status_code == 200
    assert "Помада" in response.text
    assert "Тушь" not in response.text


def test_web_dictionary_sort_by_name(client, session):
    """sort=name selects the Название option and reorders rows (D-06/D-07)."""
    add_entry(session, code="2", name="Яблоко")
    add_entry(session, code="1", name="Апельсин")

    response = client.get("/dictionary", params={"sort": "name"})
    assert response.status_code == 200
    assert response.text.index("Апельсин") < response.text.index("Яблоко")
    assert 'value="name" selected' in response.text


def test_web_dictionary_pagination_shows_page_bar(client, session):
    """25+ rows renders the shared pagination partial (D-01/D-02/D-03)."""
    for i in range(25):
        add_entry(session, code=f"{i:02d}", name=f"Товар {i:02d}")

    response = client.get("/dictionary")
    assert response.status_code == 200
    assert 'class="pagination"' in response.text
    assert "Страница 1 из" in response.text


def test_web_dictionary_filtered_to_zero_shows_empty_filter_message(client, session):
    """A filter matching nothing shows the shared filtered-empty copy."""
    add_entry(session, code="1234", name="Помада")

    response = client.get("/dictionary", params={"code": "0000"})
    assert response.status_code == 200
    assert "Ничего не найдено по заданным фильтрам." in response.text


# --- Quick task 260721-f39: category (rubric) filter ---


def test_web_dictionary_category_filter_exact_match(client, session):
    """category filters to entries whose rubric exactly matches (closed vocabulary)."""
    matching, _ = add_entry(session, code="1234", name="Помада")
    matching.rubric = "Макияж"
    other, _ = add_entry(session, code="5678", name="Крем Для Рук")
    other.rubric = "Уход за руками и ногами"
    session.commit()

    response = client.get("/dictionary", params={"category": "Макияж"})
    assert response.status_code == 200
    assert "Помада" in response.text
    assert "Крем Для Рук" not in response.text


def test_web_dictionary_category_filter_no_matches_shows_empty_state(client, session):
    """A rubric with zero matching entries shows the shared filtered-empty copy."""
    entry, _ = add_entry(session, code="1234", name="Помада")
    entry.rubric = "Макияж"
    session.commit()

    other_rubric = next(r for r in RUBRICS if r != "Макияж")
    response = client.get("/dictionary", params={"category": other_rubric})
    assert response.status_code == 200
    assert "Ничего не найдено по заданным фильтрам." in response.text


def test_web_dictionary_renders_category_select(client, session):
    """The list renders a <select name="category"> sourced from RUBRICS."""
    response = client.get("/dictionary")
    assert response.status_code == 200
    assert '<select name="category"' in response.text
    assert "Макияж" in response.text
    assert "Уход за лицом" in response.text
