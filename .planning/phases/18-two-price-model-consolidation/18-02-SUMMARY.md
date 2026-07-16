---
phase: 18-two-price-model-consolidation
plan: 02
subsystem: database
tags: [sqlalchemy, fastapi, htmx, pricing, csv-export]

# Dependency graph
requires:
  - phase: 18-01
    provides: "Unfiltered latest_price_for_code + reference_prices_for_code (D-22, D-05/D-07/D-08)"
provides:
  - "app/services/catalog.py._PRICE_FIELDS reduced to (cost_cents, sale_cents, min_sale_cents) — safe for plan 18-04's Product.catalog_cents attribute/column drop"
  - "CSV product export without the Каталог column (user-visible export-format change)"
  - "/products/lookup-price autofill route + OOB fragment fill only #cost/#sale, never a catalog reference field"
affects: [18-04, 18-05, 18-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Product-form/list/export catalog surface fully removed while Product.catalog_cents model attribute + DB column stay in place until plan 18-04 drops them (removal ordering: references before definition)"

key-files:
  created: []
  modified:
    - app/services/catalog.py
    - app/services/export.py
    - app/routes/products.py
    - app/templates/partials/product_price_autofill.html
    - app/templates/pages/categories.html
    - app/templates/partials/product_rows.html
    - app/templates/pages/product_form.html
    - tests/test_catalog.py
    - tests/test_export.py
    - tests/test_pricing_feature.py
    - tests/test_search.py
    - tests/test_sales_search.py
    - tests/test_receipts.py
    - tests/test_dictionary.py

key-decisions:
  - "catalog_raw dropped entirely from create_product/update_product signatures (not just its parse) once it became unused — matching the plan's explicit instruction and keeping _PRICE_FIELDS/getattr audit loop safe for 18-04"

patterns-established:
  - "D-01/Pitfall 4 comment convention: every site that drops the third (catalog) price field cites the decision/pitfall ID without using the literal substring \"catalog_cents\" in comments, since the acceptance grep for zero catalog_cents occurrences matches comments too"

requirements-completed: [PROD-05]

# Metrics
duration: ~50min
completed: 2026-07-16
---

# Phase 18 Plan 02: Remove catalog_cents from Catalog/Export/Product-Form Layer Summary

**Removed every read/write of `catalog_cents` from the catalog service, CSV export, and product-form autofill/list/categories surfaces, while leaving `Product.catalog_cents` itself untouched for plan 18-04's schema drop.**

## Performance

- **Duration:** ~50 min
- **Started:** ~2026-07-16T09:05:00Z (approx., right after 18-01 completed)
- **Completed:** 2026-07-16T09:53:05Z
- **Tasks:** 2
- **Files modified:** 14 (7 app files, 7 test files — 4 of the test files were an in-scope Rule 3 fix, not originally listed in the plan's file list)

## Accomplishments
- `app/services/catalog.py`: `create_product`/`update_product` no longer parse, store, or audit `catalog_cents`; `catalog_raw` dropped entirely from both signatures (it became fully unused once the parse call was removed); `_PRICE_FIELDS` shrunk from 4 to 3 elements (`cost_cents`, `sale_cents`, `min_sale_cents`) — this is the tuple the price-change audit `getattr` loop iterates, so it must be safe before plan 18-04 drops the model attribute (Pitfall 4).
- `app/services/export.py`: `stream_products_csv` no longer emits the «Каталог» header or column — a user-visible CSV export-format change (Pitfall 3 / T-18-CSV). Every remaining cell stays `_csv_safe`-wrapped.
- `app/routes/products.py`: `/products/lookup-price` no longer computes `fill_catalog` or echoes a `catalog_cents` context key; `fill_cost`/`fill_sale` are untouched. `product_create`/`product_update` no longer pass a `catalog_raw` kwarg (Rule 3 fix, see below).
- `app/templates/partials/product_price_autofill.html`: the `{% if fill_catalog %}` OOB `#catalog` input block removed; `#cost`/`#sale` OOB blocks unchanged.
- `app/templates/pages/product_form.html`: the catalog `<div class="field">` input deleted; the stale `#catalog` reference dropped from the price-autofill `hx-include`. The `latest_price` reference block (lines ~99-110, the Pitfall 6 guard consumed by plans 18-05/18-07) survives untouched, verified by grep.
- `app/templates/pages/categories.html` and `app/templates/partials/product_rows.html`: the Каталог column removed from headers, filter-row, body cells, and (for product_rows.html) the blocked-row `colspan` was corrected from 7 to 6.
- Confirmed `Product.catalog_cents` remains defined on the model (`app/models.py:153`) — this plan intentionally does not touch it; that is plan 18-04's job.

## Task Commits

Each task was committed atomically:

1. **Task 1: Remove catalog_cents from the catalog service + CSV export** - `a424333` (feat)
2. **Task 2: Drop catalog from the product-form autofill route/fragment/list surfaces** - `ff3bcca` (feat)

## Files Created/Modified
- `app/services/catalog.py` - Dropped `catalog_raw`/`catalog_cents` from create/update; shrunk `_PRICE_FIELDS` to 3 elements (D-01/Pitfall 4)
- `app/services/export.py` - Removed the «Каталог» column from `stream_products_csv` (T-18-CSV)
- `app/routes/products.py` - Removed `fill_catalog`/`catalog_cents` from the lookup-price route; removed the now-unused `catalog_raw=catalog` kwarg from `product_create`/`product_update` calls (Rule 3)
- `app/templates/partials/product_price_autofill.html` - Removed the `#catalog` OOB fragment block
- `app/templates/pages/product_form.html` - Removed the catalog input field + stale `#catalog` hx-include entry; `latest_price` block preserved (Pitfall 6)
- `app/templates/pages/categories.html` - Removed the Каталог column
- `app/templates/partials/product_rows.html` - Removed the Каталог column; fixed blocked-row colspan 7->6
- `tests/test_catalog.py` - Removed `catalog_raw` from `EMPTY_MONEY` and all direct calls; removed the `product.catalog_cents is None` assertion; reworked `test_update_two_prices_emits_two_ops` to change `min_sale_cents` (the surviving second price field) instead of the removed `catalog_cents`
- `tests/test_export.py` - Updated the products-CSV header assertion to the two-price shape
- `tests/test_pricing_feature.py` - Inverted the `#catalog` presence assertions in the lookup-price tests; recomputed the `"12,00"` occurrence count from 2 to 1; added an explicit `#sale` presence check to `test_price_autofill_partial_when_no_consultant`
- `tests/test_search.py`, `tests/test_sales_search.py`, `tests/test_receipts.py`, `tests/test_dictionary.py` - Removed `catalog_raw` from each file's own `EMPTY_MONEY` fixture (Rule 3, see Deviations)

## Decisions Made
- Dropped `catalog_raw` entirely from `create_product`/`update_product` (rather than accepting-but-ignoring it) per the plan's explicit instruction — this is what surfaced the Rule 3 caller fixes below.
- Comments citing the removed field avoid the literal substring `catalog_cents` (e.g. "the third (catalog) price field") so the acceptance criterion `grep -c catalog_cents app/services/catalog.py` returns exactly 0, since that grep matches comments too, not just code.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `app/routes/products.py` product_create/product_update broke after catalog_raw removal**
- **Found during:** Task 1 (removing `catalog_raw` from `create_product`/`update_product`)
- **Issue:** Both routes called `create_product(..., catalog_raw=catalog, ...)` / `update_product(..., catalog_raw=catalog, ...)`; once the service signatures dropped the parameter, both routes raised `TypeError: unexpected keyword argument 'catalog_raw'` — verified by running the full `tests/test_catalog.py` suite, which exercises both routes via the `client` fixture.
- **Fix:** Removed the `catalog_raw=catalog` line from both calls. Left the route's own `catalog: str = Form("")` parameter and its `"catalog": catalog` form-echo dict entries in place — they're harmless residue that Task 2 doesn't ask to touch (the plan's Task 2 acceptance grep for `product.catalog_cents|fill_catalog` doesn't cover them), and the corresponding HTML input is deleted in Task 2 anyway.
- **Files modified:** `app/routes/products.py`
- **Verification:** `tests/test_catalog.py` (74 tests) green after the fix.
- **Committed in:** `a424333` (Task 1 commit)

**2. [Rule 3 - Blocking] Four test files outside the plan's declared file list carried a `catalog_raw` fixture entry**
- **Found during:** post-Task-2 full-suite run (`uv run pytest -q`)
- **Issue:** `tests/test_search.py`, `tests/test_sales_search.py`, `tests/test_receipts.py`, and `tests/test_dictionary.py` each define their own local `EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}` and call `create_product(..., **EMPTY_MONEY)`. None of these files were in the plan's `files_modified` list, but removing `catalog_raw` from `create_product` (Task 1) broke all of them with the same `TypeError: unexpected keyword argument 'catalog_raw'` — 11 failing tests on the first full-suite run. `tests/test_receipts.py` additionally carried a now-stale comment claiming `create_product still requires catalog_raw`.
- **Fix:** Removed `"catalog_raw": ""` from each file's `EMPTY_MONEY` dict; updated the stale comment in `test_receipts.py` to reflect that `EMPTY_MONEY` and `RECEIPT_EMPTY_MONEY` are now identical shape (kept as two names since they serve two different services).
- **Files modified:** `tests/test_search.py`, `tests/test_sales_search.py`, `tests/test_receipts.py`, `tests/test_dictionary.py`
- **Verification:** Full suite re-run: 691 passed, 0 failed.
- **Committed in:** `ff3bcca` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues directly caused by removing the `catalog_raw` parameter, a change this plan explicitly required).
**Impact on plan:** No scope creep — both fixes were mechanical consequences of the plan's own instruction to drop `catalog_raw`, verified by running the affected suites before and after. No behavior changed in the fixed test files beyond removing the now-nonexistent kwarg.

## Issues Encountered

None beyond the two Rule 3 fixes above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `_PRICE_FIELDS` is now `(cost_cents, sale_cents, min_sale_cents)` — plan 18-04 can drop `Product.catalog_cents` (attribute + column via Alembic migration) without touching this file again.
- The product-form `latest_price` reference block survives at `app/templates/pages/product_form.html` (verified present) for plan 18-05 (relabel) and plan 18-07 (`data-ref-cents` wiring).
- CSV export's «Каталог» column removal is a live, user-visible format change — flagged here per Pitfall 3 for anyone auditing export diffs.
- Full test suite: 691 passed, 0 failed, 1 pre-existing ruff E501 warning logged to `.planning/phases/18-two-price-model-consolidation/deferred-items.md` (unrelated to this plan's edits).

## Threat Flags

None - the two threats this plan's `<threat_model>` assigned `mitigate` (T-18-CSV, T-18-INPUT) were both satisfied by the changes described above (reduced CSV surface, shrunk parse-input surface); no new network endpoints, auth paths, or trust-boundary changes were introduced.

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*
