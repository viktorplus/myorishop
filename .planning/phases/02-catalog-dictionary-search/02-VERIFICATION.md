---
phase: 02-catalog-dictionary-search
verified: 2026-07-08T21:10:00Z
status: human_needed
score: 28/28 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Instant search feel: on /products type a partial Cyrillic name (e.g. «губная») and a partial code in a real browser"
    expected: "Results update in place without page reload, with a ~300ms debounce feel; matched substring highlighted with <mark>"
    why_human: "Debounce timing and no-reload UX are browser behaviors; TestClient only proves the HTML attributes and endpoint responses"
  - test: "Dictionary autofill: add a code→name pair at /dictionary, then on /products/new type that code into «Код» with the name field empty; separately, type your own name first and then the code"
    expected: "After ~300ms the empty name fills with the dictionary name plus hint «Название подставлено из справочника — можно изменить.»; a pre-typed name is NEVER overwritten (nothing changes)"
    why_human: "The 204/fill decision is test-covered server-side, but the live htmx swap into #name-wrap is browser behavior"
  - test: "WR-01 race guard: type a known code, then immediately start typing a name BEFORE the 300ms lookup returns"
    expected: "The in-flight lookup fragment is discarded — the operator's typed name survives"
    why_human: "hx-on::before-swap guard is client-side JS explicitly flagged in 02-REVIEW-FIX.md as 'fixed: requires human verification' — TestClient cannot exercise swap-time events"
---

# Phase 2: Catalog, Dictionary & Search — Verification Report

**Phase Goal:** Operator can maintain the product catalog and find any product in seconds by code or name
**Verified:** 2026-07-08T21:10:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## MVP Mode — User Flow Coverage

Phase mode is `mvp`. The ROADMAP goal line is outcome prose, not canonical User Story format; every PLAN carries the assembled story (flagged to orchestrator, same convention as Phase 1): *"As a shop operator, I want to maintain product cards (code, name, category, three prices) and find any product in seconds by code or name, so that daily receipt and sale entry stays fast and prices are never lost."* The story matches the canonical format; verification proceeds against its outcome clause.

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Open /products from nav | Product list or empty state «Товаров пока нет» | `base.html` nav link; `products_list.html` + `product_rows.html` empty state; `test_web_deleted_product_hidden_and_empty_state` | ✓ |
| Create product card with code/name + optional category/3 prices | Saved with NULL for blanks, integer cents for filled; product_created audit op | `catalog.create_product` + `parse_optional_cents`; `test_create_product_persists_all_fields_and_name_lc`, `test_create_product_records_product_created_op` | ✓ |
| Type a known code on the form | Empty name auto-fills from dictionary with RU hint; non-empty name never overwritten | `GET /dictionary/lookup` 200-fragment/204 pattern in `app/routes/dictionary.py`; `name_input.html`; tests lookup 200/204×3 | ✓ (browser feel → human) |
| Type partial code or name in search | Ranked, capped, highlighted instant results, Cyrillic-safe | `catalog.search_products` (case() rank, LIMIT 20, name_lc); `GET /products/search` partial; 11 tests in `tests/test_search.py` | ✓ (debounce feel → human) |
| Change a price, revisit the card | Old values visible as «История цен» (when, who, field, old → new) | `price_change` ops + `catalog.price_history` + `price_history.html`; `test_web_edit_price_then_history_rendered` | ✓ |

## Goal Achievement

### Observable Truths — ROADMAP Success Criteria

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Operator can create and edit a product card with code, name, category, cost/sale/catalog price, leaving optional fields empty | ✓ VERIFIED | `create_product`/`update_product` in `app/services/catalog.py`; routes GET/POST `/products`, `/products/new`, `/products/{id}/edit`, POST `/products/{id}`; blanks stored as NULL (`parse_optional_cents`); 25 tests in `tests/test_catalog.py` pass |
| 2 | Typing a known product code auto-fills the product name from the reference dictionary | ✓ VERIFIED | Code input in `product_form.html` carries `hx-get="/dictionary/lookup"` + debounce; route returns `name_input.html` fragment (fill) or 204 (guard); tests `test_web_lookup_fills_when_name_empty`, `test_web_lookup_204_when_name_present`, `test_web_lookup_204_when_code_unknown`, `test_web_product_form_wired_for_autofill` |
| 3 | Operator finds a product by partial code or name with instant search/autocomplete results | ✓ VERIFIED | `search_products` (ranked exact>prefix>substring, LIMIT 20, Python-lowered vs `name_lc`, LIKE-escaped); active-search input with all five htmx attrs in `products_list.html`; `GET /products/search` returns rows partial only; 11 tests in `tests/test_search.py` pass |
| 4 | After changing a product's prices, the previous values remain visible as price history | ✓ VERIFIED | One `price_change` op per changed field with `old_cents` snapshotted before mutation; append-only DB triggers protect rows; `price_history.html` renders «Когда/Кто/Поле/Было → Стало»; tests `test_update_price_records_price_change_with_old_and_new`, `test_price_history_returns_only_price_changes_newest_first`, `test_web_edit_price_then_history_rendered` |

### Observable Truths — Plan must_haves (24/24)

| Plan | Truth | Status | Evidence |
| ---- | ----- | ------ | -------- |
| 02-01 | /products from nav, list or empty state «Товаров пока нет» | ✓ | nav in `base.html`; empty state in `product_rows.html` |
| 02-01 | Create with optional fields; blanks → NULL, filled → integer cents | ✓ | `parse_optional_cents`; test 1 asserts 10000/15050/None |
| 02-01 | product_created op (qty_delta=0) with operator + UTC stamp | ✓ | `record_operation` stamps `created_by`/`created_at`; test 2 |
| 02-01 | record_operation raises ValueError on soft-deleted product (IN-01) | ✓ | `ledger.py:62-63`; `test_record_operation_rejects_soft_deleted_product` |
| 02-01 | name_lc == Python str.lower() of name incl. Cyrillic | ✓ | unconditional `name.lower()` in create/update; Cyrillic fixtures in tests |
| 02-01 | Migration 0002 fresh-DB + backfill without touching operations triggers | ✓ | Python-side backfill loop in 0002; `test_migration_0002_fresh_db_and_backfill` asserts triggers survive |
| 02-02 | Edit any field at /products/{id}/edit and save | ✓ | `update_product` + POST route; web tests |
| 02-02 | One price_change op per changed field, old captured BEFORE mutation | ✓ | snapshot dict before mutation (`catalog.py:168`); tests 1–2 |
| 02-02 | Price history: when/who/field/old→new newest first; empty state «Цены ещё не менялись.» | ✓ | `price_history.html`; ORDER BY created_at DESC, seq DESC |
| 02-02 | product_edited op with sorted changed fields; name edits refresh name_lc | ✓ | `changed_non_price` sorted; `test_update_non_price_fields_records_product_edited` |
| 02-02 | Soft delete hides from list, card shows «Товар удалён» + «Восстановить», hx-confirm | ✓ | `product_form.html` banner/restore/danger button; `test_web_delete_hides_and_restore_returns` |
| 02-02 | Unchanged resave writes zero operations | ✓ | no-op early return; `test_update_unchanged_values_writes_no_ops` |
| 02-03 | «губная» finds «Губная Помада» — Cyrillic case-insensitive, no reload | ✓ | `name_lc` + Python lower; `test_search_cyrillic_case_insensitive` |
| 02-03 | Ranking exact code > code prefix > name substring | ✓ | `case()` rank in `search_products`; ranking test |
| 02-03 | Cap 20; % and _ literal | ✓ | `.limit(20)`, `_escape_like` + `autoescape=True`; cap + wildcard tests |
| 02-03 | <mark> highlight without \|safe | ✓ | `split_match` segments + literal template `<mark>`; grep gate clean |
| 02-03 | Empty query → first 20 by name; zero results → «Ничего не найдено…» | ✓ | Pitfall-6 branch; empty-state branch in `product_rows.html` |
| 02-03 | Soft-deleted never in results | ✓ | base WHERE `deleted_at IS NULL`; `test_search_excludes_deleted` |
| 02-04 | Add/edit code→name pairs at /dictionary (paste-friendly, no masks) | ✓ | `dictionary.html` inline add + `dictionary_rows.html` inline edit forms |
| 02-04 | Known code auto-fills empty name with hint «Название подставлено из справочника…» | ✓ | `name_input.html` autofilled hint; lookup fragment test |
| 02-04 | Autofill never overwrites non-empty name (204) | ✓ | server 204 guard + WR-01 client swap guard; 204 tests |
| 02-04 | Unknown code → 204, nothing changes | ✓ | `test_web_lookup_204_when_code_unknown` |
| 02-04 | Dictionary edit never changes any product name; zero ledger rows | ✓ | plain CRUD, no `record_operation` import (grep gate); `test_dictionary_edit_does_not_touch_products` |
| 02-04 | Nav shows «Справочник»; /dictionary renders RU with empty-state hint | ✓ | `base.html`; `test_web_dictionary_page_renders`, `test_web_nav_has_dictionary_link` |

**Score:** 28/28 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `alembic/versions/0002_catalog_dictionary.py` | products columns + Python backfill + dictionary table + indexes; `down_revision = "0001"` | ✓ VERIFIED | 78 lines; no app imports; no batch mode; never touches operations |
| `alembic/versions/0003_products_code_active_unique.py` | WR-04 partial unique index (added by review fix) | ✓ VERIFIED | portable sqlite_where/postgresql_where; mirrored in `Product.__table_args__` |
| `app/services/catalog.py` | create/list/update/delete/restore/history + search_products/split_match/search_view | ✓ VERIFIED | 349 lines; all writes via `record_operation` or explicit service commits; contains `record_operation`, `price_change`, `case(` |
| `app/services/dictionary.py` | add_entry/update_entry/list_entries/lookup, no ledger | ✓ VERIFIED | contains `def lookup`; IntegrityError race guard (WR-02) |
| `app/services/ledger.py` | IN-01 deleted-product guard; `commit` param (WR-03) | ✓ VERIFIED | guard at line 62; `commit: bool = True` |
| `app/routes/products.py` | list/new/create/search/edit/update/delete/restore, thin | ✓ VERIFIED | contains `/products/search`, `/edit`; literal routes before parameterized; zero `session.add` |
| `app/routes/dictionary.py` | page/add/update/lookup with `status_code=204` | ✓ VERIFIED | 204 pattern implemented; lookup declared before `/{entry_id}` |
| `app/templates/pages/product_form.html` | name-wrap include, hx-include autofill wiring, hx-confirm delete, WR-01 guard | ✓ VERIFIED | contains `name-wrap` (via include), `hx-include`, `hx-confirm`, `hx-on::before-swap` |
| `app/templates/partials/product_rows.html` | `#product-rows` swap target, mark highlighting, both empty states | ✓ VERIFIED | id present; segments autoescaped |
| `app/templates/partials/price_history.html` | «История»/Когда/Кто/Поле/Было → Стало | ✓ VERIFIED | cents filter used, no hand-rolled money math |
| `app/templates/partials/name_input.html` | `#name-wrap` fragment + autofill hint | ✓ VERIFIED | single source for name field (PD-6) |
| `app/templates/pages/products_list.html` | active search input with `delay:300ms` | ✓ VERIFIED | all five htmx attrs present |
| `app/templates/base.html` | nav Главная/Товары/Справочник; CR-01 htmx-config 422 swap | ✓ VERIFIED | meta htmx-config present |
| `tests/test_catalog.py` | CAT-01/CAT-04 contract, min 120 lines | ✓ VERIFIED | 639 lines, 25 tests |
| `tests/test_search.py` | CAT-03 contract, min 80 lines | ✓ VERIFIED | 149 lines, 11 tests |
| `tests/test_dictionary.py` | CAT-02 contract, min 70 lines | ✓ VERIFIED | 227 lines, 16 tests |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `app/routes/products.py` | `app/services/catalog.py` | `from app.services.catalog import` | ✓ WIRED | 8 service functions imported; routes write-free |
| `app/services/catalog.py` | `app/services/ledger.py` | `record_operation` (product_created / price_change / product_edited) | ✓ WIRED | single write path intact; WR-03 single-commit staging |
| `app/templates/base.html` | `/products`, `/dictionary` | nav links | ✓ WIRED | `href="/products"`, `href="/dictionary"` present |
| `alembic/versions/0002…` | `app/models.py` | column-set parity (name_lc, category, 3 prices, dictionary) | ✓ WIRED | metadata matches migration head; conventions test green |
| `products_list.html` | `/products/search` | hx-get + delay:300ms + hx-target #product-rows + hx-sync | ✓ WIRED | all attrs present; `test_web_products_page_has_active_search_input` |
| `routes/products.py` | `search_view` | shared by GET /products and GET /products/search | ✓ WIRED | both routes call `search_view` |
| `search_products` | `products.name_lc` | Python-lowered query, never SQL lower on name | ✓ WIRED | grep gate: zero `ilike`/`func.lower(Product.name` under app/ |
| `product_form.html` | `/dictionary/lookup` | hx-get on code input, hx-target #name-wrap | ✓ WIRED | plus hx-include=[name='name'], hx-sync |
| `routes/dictionary.py` | `services/dictionary.py` | `from app.services.dictionary import` | ✓ WIRED | lookup decides fill vs 204 server-side |
| `product_form.html` | `partials/name_input.html` | include (single source for name field) | ✓ WIRED | PD-6 honored in create and edit modes |
| `product_form.html` | `partials/price_history.html` | include on edit page | ✓ WIRED | rendered with history context |
| `product_rows.html` | `/products/{id}/edit` | «Изменить» link in «Действия» column | ✓ WIRED | preserved through 02-03 search rewrite |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `product_rows.html` | `rows` | `search_view` → `search_products` → SELECT products | Yes | ✓ FLOWING |
| `price_history.html` | `history` | `price_history` → SELECT operations WHERE type=price_change | Yes | ✓ FLOWING |
| `dictionary_rows.html` | `entries` | `list_entries` → SELECT dictionary | Yes | ✓ FLOWING |
| `name_input.html` (lookup swap) | `name` | `lookup` → SELECT dictionary by code | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full contract suite (Phase 1 regression + 52 Phase 2 tests) | `uv run pytest -q` (run once) | `74 passed, 1 warning in 7.45s` | ✓ PASS |
| Lint gate | `uv run ruff check .` | All checks passed | ✓ PASS |
| Routes write-free | `grep -rn "session\.add(" app/routes/` | empty | ✓ PASS |
| No `\| safe` in templates | grep over `app/templates/` | empty | ✓ PASS |
| No ilike / SQL-lower on name | grep over `app/` | empty | ✓ PASS |
| `Operation(` constructed only in ledger.py | grep over `app/` | only the class def in models.py | ✓ PASS |
| No quantity form field (D-21) | `grep -rn 'name="quantity"' app/templates/` | empty | ✓ PASS |
| Dictionary ledger-free (D-24) | grep `record_operation` in dictionary.py | empty | ✓ PASS |
| Migrations 0002/0003 free of app imports (WR-06) | grep count | 0 / 0 | ✓ PASS |
| Vendored htmx handles HX-Redirect (PD-4) | `grep -c "HX-Redirect" app/static/htmx.min.js` | 1 | ✓ PASS |
| No CDN URLs in templates | grep `https?://` | empty | ✓ PASS |
| Review-fix commits exist (CR-01, WR-01..WR-04) | `git cat-file -e` c47d83d 73724e1 1309f1d 1873875 440478e | all OK | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes exist or are declared by any Phase 2 plan — SKIPPED (test suite is the executable contract).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| CAT-01 | 02-01, 02-02 | Create and edit product cards (code, name, category, 3 prices, most optional) | ✓ SATISFIED | create/edit routes + service + 25 passing tests; optional fields stored as NULL |
| CAT-02 | 02-04 | Reference dictionary code→name with autofill | ✓ SATISFIED | /dictionary CRUD + lookup 200/204 pattern + form wiring; 16 passing tests |
| CAT-03 | 02-03 | Instant search by code or name | ✓ SATISFIED | ranked Cyrillic-safe search + HTMX active search; 11 passing tests |
| CAT-04 | 02-02 | Price changes kept as history | ✓ SATISFIED | immutable price_change ops (append-only triggers) rendered as «История цен» |

Orphan check: REQUIREMENTS.md maps exactly CAT-01..CAT-04 to Phase 2; all four are claimed by plans. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | none (no TBD/FIXME/XXX/TODO/HACK/placeholder markers; no empty-return stubs; no console-log handlers) | — | — |

### Human Verification Required

### 1. Instant search feel in the browser

**Test:** Start the app (`run.bat`), open /products, type «губная» (and a partial code) into the search box.
**Expected:** Results update in place without page reload after a ~300ms pause; matched text highlighted.
**Why human:** Debounce timing and no-reload feel are live-browser behaviors; automated tests only prove attributes and endpoint output. (Deferred end-of-phase check declared in 02-03-PLAN, per workflow.human_verify_mode=end-of-phase.)

### 2. Dictionary autofill on the product form

**Test:** Add a pair (e.g. 1234 → Губная Помада) at /dictionary; on /products/new type 1234 with the name empty; then repeat typing your own name first.
**Expected:** Empty name fills with «Губная Помада» + hint «Название подставлено из справочника — можно изменить.»; a pre-typed name is never overwritten.
**Why human:** Live htmx swap into #name-wrap; server 200/204 branches are test-covered but the browser wiring is not. (Deferred end-of-phase check declared in 02-04-PLAN.)

### 3. WR-01 autofill race guard

**Test:** Type a known code, then immediately start typing a name before the 300ms lookup response arrives.
**Expected:** The typed name survives — the late lookup fragment is discarded.
**Why human:** `hx-on::before-swap` guard is client-side JS; 02-REVIEW-FIX.md explicitly marks it "fixed: requires human verification".

### Gaps Summary

No gaps. All 4 ROADMAP success criteria and all 24 plan must-have truths are verified in the codebase: artifacts exist, are substantive, wired, and render real DB-backed data; the full 74-test suite and lint pass; all five code-review fixes (CR-01, WR-01..WR-04) landed as real commits with regression tests. Status is `human_needed` solely because three browser-only behaviors (search feel, live autofill, WR-01 race guard) cannot be verified programmatically.

---

_Verified: 2026-07-08T21:10:00Z_
_Verifier: Claude (gsd-verifier)_
