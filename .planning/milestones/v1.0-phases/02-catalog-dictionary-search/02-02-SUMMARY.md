---
phase: 02-catalog-dictionary-search
plan: 02
subsystem: catalog
tags: [fastapi, sqlalchemy, sqlite, jinja2, htmx]

# Dependency graph
requires:
  - phase: 02-catalog-dictionary-search
    provides: "Plan 02-01: create_product/list_products service, migration 0002 columns, product_form.html create mode, #product-rows partial, IN-01 guard in record_operation"
provides:
  - update_product with snapshot-before-mutate audit (per-field price_change ops, product_edited op, self-excluding code uniqueness, soft-deleted rejection, no-op saves write zero ops)
  - soft_delete_product / restore_product (plain row writes, no ledger op, idempotent) + get_product + price_history query
  - /products/{id}/edit, POST /products/{id}, POST /products/{id}/delete, POST /products/{id}/restore routes (delete/restore answer 200 + HX-Redirect)
  - product_form.html edit mode (pre-filled inputs via cents filter, «История цен» section, hx-confirm delete, deleted banner + «Восстановить»)
  - partials/price_history.html (Когда/Кто/Поле/Было → Стало, RU field labels, empty state)
  - «Действия»/«Изменить» column in partials/product_rows.html
affects: [02-03 search, 02-04 dictionary, phase-3 receipts, phase-4 sales]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "snapshot-before-mutate audit: old field values captured into dicts BEFORE applying form values; per-field price_change payloads compare snapshot vs new"
    - "HX-Redirect responses (200 + header) for htmx POSTs that must navigate after hx-confirm (PD-4)"
    - "dual-mode form template: form dict wins on error re-render, product row pre-fills on GET, create mode falls back to empty"

key-files:
  created:
    - app/templates/partials/price_history.html
  modified:
    - tests/test_catalog.py
    - app/services/catalog.py
    - app/routes/products.py
    - app/templates/pages/product_form.html
    - app/templates/partials/product_rows.html

key-decisions:
  - "PD-3 honored as written: multi-field price saves emit one record_operation call per field; first call's commit persists all staged row mutations"
  - "PD-4 verified: vendored htmx 2.0.10 contains HX-Redirect (grep count 1) — delete/restore use 200 + HX-Redirect, no fallback needed"
  - "catalog.py module docstring reworded so the .quantity grep gate holds on prose (same precedent as 02-01 migration docstrings)"

patterns-established:
  - "destructive zone reuses .form-actions (margin-top 24px) — UI-SPEC lg separation with zero CSS additions"
  - "price_history.html maps column names to RU labels inside the template (chained conditionals, no Python-side HTML)"

requirements-completed: [CAT-01, CAT-04]

# Metrics
duration: 17min
completed: 2026-07-08
---

# Phase 2 Plan 02: Edit, Price History & Soft Delete Summary

**Product cards editable at /products/{id}/edit with every price change preserved as an immutable price_change ledger op rendered as «История цен» (when/who/field/old → new), plus hx-confirm soft delete and one-click restore via HX-Redirect**

## Performance

- **Duration:** ~17 min
- **Started:** 2026-07-08T14:44:18Z
- **Completed:** 2026-07-08T15:00:57Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- CAT-04 delivered end-to-end: update_product snapshots old cents BEFORE mutation and emits exactly one price_change op per changed field (payload {field, old_cents, new_cents}); None → value initial fills keep old_cents = None; history renders newest-first with seq tie-break
- CAT-01 edit path complete: same validation as create with self-excluding code uniqueness (D-19) and up-front rejection of soft-deleted products; name edits refresh name_lc unconditionally (D-27); non-price edits write one product_edited op with sorted changed fields (D-30)
- No-op saves proven to write zero operations (resubmit-identical test asserts op count unchanged, no commit path taken)
- Soft delete/restore (D-20): deleted products vanish from lists, edit page shows «Товар удалён» banner + «Восстановить», delete gated by hx-confirm with the exact UI-SPEC sentence; both actions answer 200 + HX-Redirect (PD-4, header verified present in vendored htmx 2.0.10)
- Single write path intact: catalog.py constructs no Operation rows, never touches quantity, and update_product has no commit between staged mutations and the first record_operation call

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests — edit, price history, soft delete/restore (RED)** - `f5fd642` (test)
2. **Task 2: Catalog service — update with audit ops, soft delete/restore, price history (service GREEN)** - `5df9d50` (feat)
3. **Task 3: Edit routes + templates — edit page, history table, delete/restore UI (GREEN e2e)** - `301c17c` (feat)

## Files Created/Modified

- `tests/test_catalog.py` - 12 new tests: price_change payload semantics, two-field saves, no-op saves, product_edited, duplicate-code-excluding-self, deleted rejection, delete/restore roundtrip, history ordering, 4 web e2e
- `app/services/catalog.py` - get_product, update_product (snapshot-before-mutate), soft_delete_product, restore_product, price_history
- `app/routes/products.py` - 4 new thin endpoints; literal routes kept declared before parameterized /products/{product_id}
- `app/templates/pages/product_form.html` - dual create/edit mode, pre-fill via cents filter, «История цен» include, destructive zone, deleted banner/restore
- `app/templates/partials/price_history.html` - NEW: Когда/Кто/Поле/Было → Стало table, RU field label mapping, «Цены ещё не менялись.» empty state
- `app/templates/partials/product_rows.html` - «Действия» column with «Изменить» link per row

## Decisions Made

- Destructive/restore zone reuses the existing `.form-actions` class for its 24px top margin — UI-SPEC lg separation without touching style.css (kept files_modified scope exact)
- The h2 «История цен» lives INSIDE partials/price_history.html so the plan's artifact gate (partial contains «История») holds while product_form.html still just includes the partial
- Edit-mode input values: `form` dict wins when present (422 re-render), otherwise product row values via cents filter — create mode unaffected because empty form dict is falsy

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reworded catalog.py module docstring for the .quantity grep gate**
- **Found during:** Task 2 (acceptance criteria gate `! grep -n "\.quantity" app/services/catalog.py`)
- **Issue:** The pre-existing (02-01) module docstring contained the literal "products.quantity", tripping the gate on prose, not code
- **Fix:** Reworded to "the cached stock projection" — same precedent as 02-01 migration docstrings
- **Files modified:** app/services/catalog.py
- **Commit:** 5df9d50

No other deviations — plan executed as written.

## Issues Encountered

- Ruff E501/I001 on the new test block — reformatted long create_product/update_product calls to multi-line and let `ruff check --fix` sort imports before the Task 1 commit; no functional change

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-03 (search) can extend app/routes/products.py — literal /products/search must be declared before the parameterized routes (comment left in the router marking the spot); «Действия» column must be preserved when adding match highlight to product_rows.html
- Plan 02-04 (dictionary autofill) keeps its #name-wrap contract — wrapper untouched in edit mode
- Full suite 46 passed, ruff clean; all Phase 2 grep gates green (routes write-free, no | safe, Operation construction only in ledger.py, no hand-rolled money math in templates)

## Known Stubs

None — no placeholder values or unwired components introduced.

## Self-Check: PASSED

All files verified on disk; all 3 task commits (f5fd642, 5df9d50, 301c17c) verified in git log.

---
*Phase: 02-catalog-dictionary-search*
*Completed: 2026-07-08*
