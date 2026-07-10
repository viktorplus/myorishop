---
phase: 02-catalog-dictionary-search
plan: 01
subsystem: catalog
tags: [fastapi, sqlalchemy, alembic, sqlite, jinja2, htmx]

# Dependency graph
requires:
  - phase: 01-foundation-ledger-core
    provides: "append-only ledger (record_operation single write path), conventions helpers (new_id/utcnow_iso/to_cents), thin-route + partial template patterns, migration 0001"
provides:
  - Migration 0002 (products category/cost_cents/sale_cents/catalog_cents/name_lc, Python-side Cyrillic name_lc backfill, dictionary table, ix_products_code + ix_products_name_lc)
  - Extended models (Product CAT-01 columns, Dictionary model PD-1 shape, OPERATION_TYPES + price_change/product_created/product_edited)
  - IN-01 deleted-product guard inside record_operation (covers all op types)
  - app/services/catalog.py (create_product, list_products, category_options, parse_optional_cents)
  - /products + /products/new pages in Russian with nav, #product-rows partial, #name-wrap form interface
  - UI-SPEC-normalized style.css (960px container, accent #2563eb, 4-size type scale)
affects: [02-02 edit/history, 02-03 search, 02-04 dictionary, phase-3 receipts, phase-4 sales]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "stage-then-commit: catalog service stages Product rows, record_operation's commit closes the transaction atomically"
    - "optional money form fields as str = Form('') parsed via to_cents in service (never int | None)"
    - "form error re-render: (entity, errors) tuple from service; route re-renders template with status 422"
    - "name_lc maintained by Python str.lower() (Cyrillic-safe); migration backfills in Python, never SQL lower()"

key-files:
  created:
    - tests/test_catalog.py
    - alembic/versions/0002_catalog_dictionary.py
    - app/services/catalog.py
    - app/routes/products.py
    - app/templates/pages/products_list.html
    - app/templates/pages/product_form.html
    - app/templates/partials/product_rows.html
  modified:
    - app/models.py
    - app/services/ledger.py
    - app/main.py
    - app/templates/base.html
    - app/static/style.css

key-decisions:
  - "PD-1 confirmed in code: dictionary uses UUID String(36) surrogate PK + UNIQUE(code); Phase 1 conventions test stays green and now also validates Dictionary"
  - "Migration 0002 docstring avoids the literal substrings 'import app' and 'operations' so the frozen-rule grep gates (count == 0) hold on prose as well as code"
  - "Unique-index assertion for dictionary.code done via PRAGMA index_list/index_info (SQLite renders named UNIQUE constraints as autoindexes, not named indexes in sqlite_master)"

patterns-established:
  - "test_web_ prefix for route/e2e tests, enabling -k 'not test_web_' service-level filters"
  - "migration tests monkeypatch.setattr the app.config.settings singleton db_path (settings instantiated at import time; setenv would be ignored)"
  - "#product-rows stable swap target (02-03 search) and #name-wrap wrapper (02-04 autofill) shipped as interface contracts"

requirements-completed: [CAT-01]

# Metrics
duration: 16min
completed: 2026-07-08
---

# Phase 2 Plan 01: Catalog Create/List Slice Summary

**Product cards with code/name/category/three-price fields creatable at /products/new and listed at /products, backed by migration 0002, a Cyrillic-safe name_lc shadow column, an atomic product_created ledger op, and the IN-01 deleted-product guard in the single write path**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-07-08T14:18:54Z
- **Completed:** 2026-07-08T14:34:28Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Full CAT-01 data foundation: Product columns (category, cost_cents, sale_cents, catalog_cents, name_lc), Dictionary model/table (PD-1), OPERATION_TYPES + 3 audit types — all landed in one wave so Base.metadata stays in lockstep with migration head
- Migration 0002 proven on a fresh DB by test: plain ADD COLUMN (no batch, append-only triggers verified intact), Python-side backfill folds Cyrillic («ДЕМО-Помада» → «демо-помада»), search indexes created
- create_product commits product row + product_created op (qty_delta=0) atomically through record_operation; duplicate active codes rejected with RU message, soft-deleted codes reusable
- record_operation now raises ValueError for ANY operation on a soft-deleted product (IN-01) — one guard covers all current and future op types, regression-tested
- Operator-facing /products list (empty state «Товаров пока нет») and /products/new RU form with datalist categories, inline 422 error re-render, and interface hooks for Plans 02-03/02-04

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests — CAT-01 create/list contract + migration 0002 + deleted-guard (RED)** - `ae1206c` (test)
2. **Task 2: Schema + write path — models, migration 0002, ledger guard, catalog service (GREEN service scope)** - `370ba53` (feat)
3. **Task 3: Routes + templates — /products list, /products/new form, nav, styles (GREEN e2e)** - `87823e3` (feat)

## Files Created/Modified

- `tests/test_catalog.py` - 11-test CAT-01 executable contract (Cyrillic name_lc, migration fresh-db + backfill, IN-01 regression, 3 web e2e)
- `app/models.py` - Product CAT-01 columns, Dictionary model, OPERATION_TYPES extension, code/name_lc indexes
- `alembic/versions/0002_catalog_dictionary.py` - frozen-style migration: 5 ADD COLUMNs, Python backfill, dictionary table, 2 indexes
- `app/services/ledger.py` - IN-01 guard (product.deleted_at → ValueError "deleted")
- `app/services/catalog.py` - create_product / list_products / category_options / parse_optional_cents (fat service, stage-then-commit)
- `app/routes/products.py` - thin GET /products, GET /products/new, POST /products (303 on success, 422 re-render on errors)
- `app/main.py` - products router registered
- `app/templates/base.html` - nav «Главная»/«Товары» with active-link styling
- `app/templates/pages/products_list.html` - list page with «Добавить товар» CTA
- `app/templates/partials/product_rows.html` - #product-rows swap target, money via | cents, empty state per UI-SPEC
- `app/templates/pages/product_form.html` - RU single-column form, #name-wrap, cat-options datalist, inline errors
- `app/static/style.css` - UI-SPEC normalization (spacing scale, 4-size typography, accent/destructive colors, focus outlines)

## Decisions Made

- Dictionary unique-index test asserts via `PRAGMA index_list/index_info` rather than sqlite_master name lookup — SQLite stores in-table UNIQUE constraints as autoindexes, so this is the only robust check
- Migration docstring wording avoids the substrings the plan's grep gates count (`import app`, `operations`) while keeping the WR-06 and no-batch explanations intact
- Optional-label copy rendered as «Категория <span class="muted">(необязательно)</span>» per UI-SPEC muted-marker rule

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Initial migration grep gates (`grep -c ... == 0`) tripped on docstring prose, not code — reworded the docstring (documented above); no functional change
- Ruff I001 import-sort on the new test file — auto-fixed with `ruff check --fix` before the Task 1 commit

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plans 02-02 (edit/history), 02-03 (search), 02-04 (dictionary) can build on: catalog service shape, #product-rows swap target, #name-wrap wrapper, Dictionary table already migrated
- `alembic upgrade head` applies cleanly on a fresh DB (proven by test); existing DBs get name_lc backfilled
- Full suite 34 passed, ruff clean; all Phase 2 grep gates green

## Self-Check: PASSED

All 7 created files verified on disk; all 3 task commits (ae1206c, 370ba53, 87823e3) verified in git log.

---
*Phase: 02-catalog-dictionary-search*
*Completed: 2026-07-08*
