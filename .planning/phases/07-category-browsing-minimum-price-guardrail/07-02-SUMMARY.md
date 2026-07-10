---
phase: 07-category-browsing-minimum-price-guardrail
plan: 02
subsystem: database
tags: [sqlalchemy, alembic, fastapi, jinja2, product-form, audit-trail]

# Dependency graph
requires:
  - phase: 07-01
    provides: "/categories page and products_by_category grouping (independent, wave 1)"
provides:
  - "Product.min_sale_cents nullable column (migration 0006)"
  - "create_product/update_product min_sale_raw parsing with empty-vs-zero-vs-negative semantics"
  - "min_sale_cents joined into _PRICE_FIELDS so edits are audited as price_change ops"
  - "Product-form field 'Минимальная цена продажи' wired end-to-end through POST /products and POST /products/{id}"
affects: [07-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Optional price field with NO global-settings fallback (contrast with low_stock_threshold/stale_days): NULL means 'no floor', period"
    - "New price fields join _PRICE_FIELDS generically — audit diffing and old-value snapshot dicts require zero further changes"

key-files:
  created:
    - alembic/versions/0006_product_min_sale_price.py
  modified:
    - app/models.py
    - app/services/catalog.py
    - app/services/receipts.py
    - app/templates/partials/price_history.html
    - app/templates/pages/product_form.html
    - app/routes/products.py
    - tests/test_catalog.py

key-decisions:
  - "min_sale_cents joins _PRICE_FIELDS (treated as a price for audit purposes) per RESEARCH.md Open Question #1"
  - "No global-settings fallback for min_sale_cents (D-06) — unlike low_stock_threshold/stale_days, NULL always means 'no floor set', never 'use a default'"

patterns-established:
  - "Extending _PRICE_FIELDS is not free: any OTHER consumer of that tuple (receipts.py's price-sync loop) must be checked for an assumption that it matches a smaller, hand-built dict"

requirements-completed: [PRICE-01]

# Metrics
duration: 8min
completed: 2026-07-10
---

# Phase 07 Plan 02: Minimum Sale Price — Storage and Capture Summary

**Optional, nullable `Product.min_sale_cents` (migration 0006) with a new product-form field, full create/update parsing (empty-vs-explicit-zero-vs-negative), and price_history.html audit-trail coverage identical to cost/sale/catalog.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-10T21:36:34+02:00
- **Completed:** 2026-07-10T21:44:00+02:00
- **Tasks:** 2 completed
- **Files modified:** 7 (6 planned + `app/services/receipts.py`, an out-of-plan Rule-1 fix)

## Accomplishments
- Migration 0006 adds one nullable `min_sale_cents` Integer column to `products`, applies cleanly from 0005, and downgrades symmetrically
- `create_product`/`update_product` parse `min_sale_raw` via the existing `parse_optional_cents` (empty -> NULL, `"0"` -> `0`, negative -> `PRICE_ERROR`), and `min_sale_cents` joined `_PRICE_FIELDS` so every change is audited as a `price_change` op labeled "Минимальная" in История цен
- Operator-facing "Минимальная цена продажи" field added to `product_form.html`, positioned between "Цена продажи" and "Цена по каталогу", with a "(необязательно)" hint and deliberately no default-value hint (D-07)
- `POST /products` and `POST /products/{id}` both thread `min_sale` through to the service and echo it back on the 422 error re-render path

## Task Commits

Each task followed RED -> GREEN (tdd="true"):

1. **Task 1: Migration 0006 + Product.min_sale_cents + catalog.py parsing/audit wiring**
   - `1f63822` test(07-02): add failing tests for min_sale_cents schema, capture, and audit
   - `26f30f6` feat(07-02): add min_sale_cents column, parsing, and audit wiring
2. **Task 2: Product-form min-price field, end-to-end save round-trip**
   - (tests were included in the single RED commit `1f63822` above, covering both tasks)
   - `286980d` feat(07-02): add min-price field to product form and routes

**Deviation fix commits (see below):**
- `e5a9548` fix(07-02): restore orphaned test assertion split by prior test-file edit
- `52f0a12` fix(07-02): decouple receipts price-sync loop from full _PRICE_FIELDS set

## Files Created/Modified
- `alembic/versions/0006_product_min_sale_price.py` - new migration, nullable `min_sale_cents` column, no backfill
- `app/models.py` - `Product.min_sale_cents: Mapped[int | None]`
- `app/services/catalog.py` - `_PRICE_FIELDS` extended; `min_sale_raw` parsed and persisted in `create_product`/`update_product`
- `app/services/receipts.py` - price-sync loop decoupled from `_PRICE_FIELDS` (see deviations)
- `app/templates/partials/price_history.html` - "Минимальная" label branch for `min_sale_cents` rows
- `app/templates/pages/product_form.html` - new `min_sale` field block
- `app/routes/products.py` - `min_sale: str = Form("")` on both create/update routes, echoed in error-rerender contexts
- `tests/test_catalog.py` - 8 new tests: 1 migration test, 4 service-level (empty/zero/negative/audit), 3 web e2e (round-trip/zero/422)

## Decisions Made
- `min_sale_cents` joins `_PRICE_FIELDS` (per RESEARCH.md Open Question #1) rather than getting its own audit path, since it is money in cents and the existing price_change payload shape already fits.
- No global-settings fallback for `min_sale_cents` — this is the one place in the codebase where an optional per-product numeric field deliberately does NOT mirror the `low_stock_threshold`/`stale_days` "NULL = use default" pattern, because PRICE-01 has no meaningful global default for "how much below list price is acceptable."

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a self-introduced test-file corruption from the RED commit**
- **Found during:** Task 2 GREEN verification (full suite run revealed one still-broken test)
- **Issue:** The RED-commit edit's `old_string` match for the insertion point missed a second assertion line (`assert "Категории" in page.text`) that was part of `test_web_nav_has_categories_link`, silently truncating that test and stranding the orphaned line at the very end of the file, after the newly-added tests, where it referenced an undefined `page` variable.
- **Fix:** Restored the assertion to its original test function and removed the stray trailing line.
- **Files modified:** `tests/test_catalog.py`
- **Verification:** `uv run pytest tests/test_catalog.py -q` — 47/47 pass
- **Commit:** `e5a9548`

**2. [Rule 1 - Bug] Fixed `KeyError` in receipts.py caused by extending `_PRICE_FIELDS`**
- **Found during:** Task 2 GREEN, full-suite run (`uv run pytest -q`) — 5 pre-existing receipt tests failed with `KeyError: 'min_sale_cents'`
- **Issue:** `app/services/receipts.py` imports `_PRICE_FIELDS` from `app.services.catalog` and iterates it in its price-sync loop against a hand-built 3-key `entered` dict (`cost_cents`/`sale_cents`/`catalog_cents`). Extending `_PRICE_FIELDS` to 4 entries (required by this plan's Task 1) broke that assumption, since receipts have no `min_sale` input field.
- **Fix:** Changed the loop to iterate `entered`'s own keys instead of the imported `_PRICE_FIELDS` tuple, and dropped the now-unused `_PRICE_FIELDS` import. This correctly scopes the loop to fields a receipt can actually set, and is resilient to future `_PRICE_FIELDS` growth.
- **Files modified:** `app/services/receipts.py`
- **Verification:** `uv run pytest -q` — 237/237 pass (was 5 failing before the fix)
- **Commit:** `52f0a12`

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes were required for correctness; neither expands scope beyond what Task 1's `_PRICE_FIELDS` extension (explicitly specified in the plan) implied. No new files beyond `app/services/receipts.py`, which was a necessary consequence of the planned change.

## Issues Encountered
None beyond the two auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `Product.min_sale_cents` exists, is settable through the product form, and round-trips correctly (including the explicit-zero case) — Plan 07-03 can now read it at sale time to implement the sale-time guardrail warning.
- Full test suite green (237 passed) and `ruff check` clean on all Python files touched by this plan.

---
*Phase: 07-category-browsing-minimum-price-guardrail*
*Completed: 2026-07-10*

## Self-Check: PASSED

All claimed files verified present; all claimed commit hashes verified present in git log.
