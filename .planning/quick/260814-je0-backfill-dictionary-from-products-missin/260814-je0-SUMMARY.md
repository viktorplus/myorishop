---
phase: quick-260814-je0
plan: backfill-dictionary-from-products-missin
subsystem: catalog
tags: [fastapi, jinja2, htmx, sqlalchemy, dictionary]

# Dependency graph
requires:
  - phase: quick-260721-f39
    provides: app.services.dictionary CRUD (add_entry, list_entries, lookup) and app.services.rubrics RUBRICS
provides:
  - list_missing_products / add_entry_from_product service functions (app/services/dictionary.py)
  - GET /dictionary/missing, POST /dictionary/missing/{id}/add, POST /dictionary/from-product/{id} routes
  - dedicated missing-products page + rows partial + shared dictionary_quick_add.html CTA
affects: [dictionary, products, mobile-search]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Portable Core outerjoin(Dictionary, Product.code == Dictionary.code) LEFT JOIN for a 'products missing from a helper table' list, mirroring list_entries's SQL-side pagination shape"
    - "Shared quick-add CTA partial (dictionary_quick_add.html) included by two different templates AND returned verbatim by its own POST route, swapped outerHTML into the same #dictionary-quick-add id"

key-files:
  created:
    - app/templates/pages/dictionary_missing.html
    - app/templates/partials/dictionary_missing_rows.html
    - app/templates/partials/dictionary_quick_add.html
  modified:
    - app/services/dictionary.py
    - app/routes/dictionary.py
    - app/routes/products.py
    - app/routes/mobile_search.py
    - app/templates/pages/product_form.html
    - app/templates/mobile_partials/search_product_detail.html
    - app/templates/partials/products_toolbar.html
    - app/templates/mobile_partials/products_toolbar.html
    - app/__init__.py
    - tests/test_dictionary.py
    - tests/test_catalog.py
    - tests/test_mobile_search.py
    - tests/test_mobile_products.py

key-decisions:
  - "No new router file — all three new routes live on the existing dictionary.router (already admin-gated via require_role in app/main.py), continuing its 'all dictionary reads/writes' ownership"
  - "Whole-list re-render on POST /dictionary/missing/{id}/add (not per-row DOM removal) — the added product simply stops matching the LEFT JOIN query"
  - "Cosmetic admin gate on the quick-add CTA mirrors the existing ROLE-03 «Настройки» precedent — real boundary stays server-side require_role"

patterns-established:
  - "Backfill-from-existing-row services (add_entry_from_product) as thin passthroughs to the existing write path, no validation duplicated"

requirements-completed: []

# Metrics
duration: ~25min
completed: 2026-08-14
---

# Quick Task 260814-je0: Backfill Dictionary From Products Missing Summary

**One-click backfill of missing dictionary rows from a dedicated list page and from both product detail cards, reusing the existing `add_entry` write path (D-24: dictionary stays a helper, zero Product/ledger writes).**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2 completed
- **Files modified:** 16 (3 created, 13 modified)

## Accomplishments
- `GET /dictionary/missing` lists every active product whose non-empty code has no matching dictionary row (portable SQL-side LEFT JOIN + pagination), reachable from the «Справочники» toolbar group on both `/products` and `/m/products`.
- A one-click «Добавить в справочник» action on that list's rows re-renders the same partial — the row disappears because the underlying query no longer matches it.
- The same one-click CTA is wired into the desktop product edit card (`/products/{id}/edit`) and the mobile product detail card (`/m/search/product/{id}`), flipping to an «Есть в справочнике» done-state once the entry exists, admin-gated cosmetically to avoid showing an operator a button that would only 403.
- `__version__` bumped to `1.33`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Missing-products page + one-click add from its rows + toolbar entry points** - `37256ef` (feat)
2. **Task 2: One-click add on the product detail cards (desktop + mobile) + version bump** - `0ca3581` (feat)

## Files Created/Modified
- `app/services/dictionary.py` - `list_missing_products` (LEFT JOIN + pagination), `add_entry_from_product` (passthrough to `add_entry`)
- `app/routes/dictionary.py` - `_dictionary_missing_context` helper + 3 new routes (`GET /dictionary/missing`, `POST /dictionary/missing/{id}/add`, `POST /dictionary/from-product/{id}`)
- `app/routes/products.py` - `product_edit` now resolves `dictionary_entry` via `lookup`
- `app/routes/mobile_search.py` - `mobile_search_product_detail` now resolves `dictionary_entry` via `lookup`
- `app/templates/pages/dictionary_missing.html` - full-page listing (new)
- `app/templates/partials/dictionary_missing_rows.html` - htmx swap target + pagination (new)
- `app/templates/partials/dictionary_quick_add.html` - shared CTA, admin-gated (new)
- `app/templates/pages/product_form.html` - includes the quick-add CTA in edit mode
- `app/templates/mobile_partials/search_product_detail.html` - includes the quick-add CTA
- `app/templates/partials/products_toolbar.html` / `mobile_partials/products_toolbar.html` - new «Нет в справочнике» toolbar link
- `app/__init__.py` - `__version__` "1.32" -> "1.33"
- `tests/test_dictionary.py`, `tests/test_catalog.py`, `tests/test_mobile_search.py`, `tests/test_mobile_products.py` - new coverage (24 new tests total)

## Decisions Made
None beyond what the plan locked (route ownership, whole-list re-render shape, cosmetic admin gate) — plan executed as written.

## Deviations from Plan

None - plan executed exactly as written. All service/route/template code matches the plan's action blocks verbatim; all specified tests were added and pass.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification

**Automated (per task):**
- `uv run pytest tests/test_dictionary.py tests/test_mobile_products.py -q` -> 47 passed
- `uv run pytest tests/test_catalog.py tests/test_mobile_search.py -q` -> 87 passed

**Full suite (post-task gate):**
```
uv run pytest -q --junitxml=reports/quick-260814-je0.xml
...
1296 passed, 13 skipped, 3 failed in 446.09s
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru
FAILED tests/test_sync_ui.py::test_not_configured_run_is_a_noop
```
All 3 failures are in `tests/test_sync_ui.py`, none of which this plan touches. Confirmed pre-existing/non-deterministic: running `tests/test_sync_ui.py` alone immediately afterward failed **3 different tests** in that same file (`test_offline_run_returns_200_ru`, `test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`) — consistent with the documented root cause (`sync_client._run_lock` held by the lifespan auto-sync thread, see MEMORY.md `preexisting-sync-ui-test-failures`), not a regression from this task.

**Real-path check (CLAUDE.md — exercised via FastAPI TestClient against a fresh SQLite DB with an authenticated admin session):**
```
GET /dictionary/missing -> 200
  contains product name: OK (non-empty render)
POST /dictionary/missing/{id}/add -> 200
  product row disappeared from re-render: OK
  dictionary entry created: True VJE0
GET /products/{id}/edit -> 200
  edit card shows 'Есть в справочнике': OK
POST /dictionary/from-product/{id2} -> 200
  quick-add flipped to done-state: OK
  entry survives save -> reload -> read on /dictionary: OK
ALL REAL-PATH CHECKS PASSED
```
Confirms: the missing-products list renders non-empty when a genuine gap exists; the row disappears after add (query-driven, no manual DOM trick); the desktop edit card CTA flips to done-state; the product-detail-card CTA creates the entry and it survives save -> reload -> read on `/dictionary`.

**Not run (needs a live browser, per plan's manual/real-path check):** mobile-viewport visual check at `/m/search/product/{id}`, and the operator-role visual absence check (covered instead by the automated `test_web_edit_page_quick_add_hidden_for_operator` test, which proves the server-rendered gate).

## Next Phase Readiness

This quick task is self-contained; no downstream phase depends on it. The dictionary stays a helper table (D-24 unaffected) — no Product or ledger writes were introduced by any code path in this plan.

## Self-Check: PASSED

All created files verified present on disk (3 templates + this SUMMARY + 3 report artifacts); both task commits (`37256ef`, `0ca3581`) verified present in `git log`.

---
*Quick task: 260814-je0*
*Completed: 2026-08-14*
