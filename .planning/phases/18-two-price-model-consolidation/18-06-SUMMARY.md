---
phase: 18-two-price-model-consolidation
plan: 06
subsystem: sales
tags: [fastapi, sqlalchemy, htmx, sales, price-model, prod-07]

# Dependency graph
requires:
  - phase: 18-two-price-model-consolidation
    provides: none (this plan has no depends_on; wave 1, standalone wording+test task)
provides:
  - "SALE_CARD_FILL_HINT and SALE_BATCH_FILL_HINT named constants in app/services/sales.py, each ending with the D-17/D-23 sale-only scope clause"
  - "All 6 inline sale-price-prefill-hint literals (desktop sales.py x4, mobile mobile_sales.py x2) collapsed to the two constants"
  - "Test-locked no-write-back guarantee: register_sale never mutates Product.sale_cents or Batch.price_cents (D-15/D-16)"
affects: [19-products-page-rebuild]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Public-constant cross-import from a service module into multiple route trees (desktop + mobile), mirroring receipts.py's CARD_FILL_HINT precedent"

key-files:
  created: []
  modified:
    - app/services/sales.py
    - app/routes/sales.py
    - app/routes/mobile_sales.py
    - tests/test_sales.py
    - tests/test_mobile_sales.py

key-decisions:
  - "Both sale prefill-hint families (card-sourced and batch-sourced) now carry the same scope clause, appended after the existing wording with a semicolon, so existing substring assertions ('Цена подставлена из карточки товара' / 'Цена подставлена из партии') kept passing unmodified"

patterns-established:
  - "Sale-only scope clause wording: '...можно изменить; изменение сохранится только в этой продаже.' — reusable if a future hint needs the same sale-scoped disclaimer"

requirements-completed: [PROD-07]

# Metrics
duration: ~20min
completed: 2026-07-16
---

# Phase 18 Plan 06: Sale Price Hint Scope Clause Summary

**Extracted two named sale-hint constants (card + batch) carrying a "saved only to this sale" scope clause, collapsing 6 inline Russian-string duplicates across desktop and mobile sale routes, and test-locked both the wording and the pre-existing no-write-back guarantee.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-16
- **Tasks:** 2/2 completed
- **Files modified:** 5

## Accomplishments

- `SALE_CARD_FILL_HINT` and `SALE_BATCH_FILL_HINT` declared in `app/services/sales.py`, each ending with "изменение сохранится только в этой продаже" (D-17/D-23), documenting the sale-only rationale and citing D-15/D-16 for why no write-back logic accompanies the wording change
- All 6 inline hint literals replaced: 4 in `app/routes/sales.py` (`sale_lookup` + `sale_batch_pick`), 2 in `app/routes/mobile_sales.py` (`mobile_sale_step_qty_price`) — imports extended in both route modules
- 5 new tests added: 2 desktop (card + batch hint scope clause via `/sales/lookup` and `/sales/batch-pick`), 2 mobile (card + batch hint scope clause via `/m/sales/step/qty-price`), 1 service-level no-write-back guarantee test (`test_sale_does_not_write_back_to_product_or_batch`)
- Confirmed via `git diff` that zero existing lines in `tests/test_sales.py`/`tests/test_mobile_sales.py` were removed or altered — all 9+ PRICE-01 guard tests (`min_sale`/`below_minimum`/`negative_price`/`oversell` filter: 18 tests) remain green and byte-for-byte unmodified

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract two sale-hint constants with the sale-only scope clause; replace all 6 inline literals (desktop + mobile)** - `393c955` (feat)
2. **Task 2: Lock the wording and the no-write-back guarantee (D-17/D-23 + D-15/D-16)** - `cc937a1` (test)

**Plan metadata:** committed separately (docs) — see final commit in this plan's execution.

## Files Created/Modified

- `app/services/sales.py` - Declares `SALE_CARD_FILL_HINT` + `SALE_BATCH_FILL_HINT` beside `PRODUCT_NOT_FOUND_TMPL`, mirroring `receipts.py`'s `CARD_FILL_HINT` comment style
- `app/routes/sales.py` - Imports both constants; 4 inline literal call sites (`sale_lookup` card fill x1, batch-autoselect fill x1, `sale_batch_pick` x2) now reference the constants
- `app/routes/mobile_sales.py` - Extends the existing `from app.services.sales import PRODUCT_NOT_FOUND_TMPL, ...` to bring in both constants; 2 inline literal call sites in `mobile_sale_step_qty_price` now reference them
- `tests/test_sales.py` - Adds `test_web_sale_card_hint_states_sale_only_scope`, `test_web_sale_batch_hint_states_sale_only_scope`, `test_sale_does_not_write_back_to_product_or_batch`
- `tests/test_mobile_sales.py` - Adds `test_qty_price_step_batch_hint_states_sale_only_scope`, `test_qty_price_step_card_hint_states_sale_only_scope`

## Decisions Made

- The scope clause was appended after the existing hint text with a semicolon separator (not replacing existing wording), so all pre-existing substring assertions ("Цена подставлена из карточки товара" / "Цена подставлена из партии") in the untouched test suite kept passing without modification — no test churn beyond the 5 new additions.

## Deviations from Plan

None - plan executed exactly as written. One out-of-scope discovery was logged (not fixed, per scope boundary rule):

- **[Out of scope] 2 pre-existing `ruff` E501 warnings in `app/routes/mobile_sales.py`** (lines 218 and 284, both predating this plan's edits) — logged to `.planning/phases/18-two-price-model-consolidation/deferred-items.md` for a future pass that touches `mobile_sales.py` for an unrelated reason. Not fixed here because they are unrelated to the 6 hint-literal call sites this plan touches.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PROD-07 is now fully satisfied: every sale prefill hint (card + batch, desktop + mobile) states the sale-only scope, and the no-write-back guarantee (D-15/D-16, protecting PRICE-01's criterion 5) is test-locked.
- No blockers for the remaining Phase 18 plans (18-07/18-08 price-cue UI work) or Phase 19 (Products Page Rebuild).

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*
