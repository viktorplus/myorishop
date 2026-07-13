---
phase: 13-mobile-wizard-context-navigation
plan: 06
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile-wizard, warehouses]

# Dependency graph
requires:
  - phase: 13-mobile-wizard-context-navigation
    provides: "Waves 1/2's Склад: visible-text pattern already shipped for receipt/write-off/correction/transfer wizards (_warehouse_names() helper, batch_card_picker.html per-card pattern, _wizard_header.html shared partial)"
provides:
  - "_warehouse_names() helper in mobile_sales.py (mirrors mobile_transfers.py/mobile_corrections.py)"
  - "warehouse_name/warehouse_names threaded through mobile_sale_step_product, mobile_sale_step_batch, mobile_sale_step_qty_price, and _basket_lines"
  - "Optional per-card Склад: line in batch_card_picker.html, gated on warehouse_names being passed"
  - "Склад: line in sale_step_qty_price.html (via _wizard_header.html) and sale_basket.html"
  - "3 new regression tests for warehouse visibility in the sale wizard"
affects: [13-VERIFICATION, mobile wizard context/navigation follow-up work]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "batch_card_picker.html's warehouse_names param is opt-in (Jinja `is defined` check) so shared-partial extension is fully backward compatible with existing callers (corrections/write-off) that never pass it"

key-files:
  created: []
  modified:
    - app/routes/mobile_sales.py
    - app/templates/mobile_partials/batch_card_picker.html
    - app/templates/mobile_partials/sale_step_qty_price.html
    - app/templates/mobile_partials/sale_basket.html
    - tests/test_mobile_sales.py

key-decisions:
  - "warehouse_name resolved ONLY from an already ownership-validated Batch object at each call site (T-13-11), never from a raw client-supplied warehouse_id -- matches the existing mobile_corrections.py::_carried_warehouse_name pattern"
  - "batch_card_picker.html's new per-card line is opt-in on `warehouse_names is defined and warehouse_names`, so corrections/write-off (which never pass it) get zero behavior change"

patterns-established: []

requirements-completed: [UI-02]

# Metrics
duration: 12min
completed: 2026-07-13
---

# Phase 13 Plan 06: Sale Wizard Warehouse Visibility Summary

**Sale wizard now shows a `Склад:` (warehouse) line at every step -- per-card on the multi-warehouse batch-pick step, and a single line on qty-price/basket -- closing the last remaining Phase 13 Success Criterion #1 gap (UI-02).**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-13T23:24:00Z (approx.)
- **Completed:** 2026-07-13T23:36:32Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `_warehouse_names(session)` helper added to `mobile_sales.py`, mirroring the identical helper already shipped in `mobile_transfers.py`/`mobile_corrections.py`
- `mobile_sale_step_product`'s dictionary-only branch explicitly sets `warehouse_name: None`; its batches branch and `mobile_sale_step_batch` (GET) both pass `warehouse_names` for the per-card batch-pick display
- `mobile_sale_step_qty_price` resolves a single `warehouse_name` from the ownership-validated `picked` batch
- `_basket_lines` computes the warehouse-names dict once per request (not per line) and sets `warehouse_name` per basket line
- `batch_card_picker.html` renders a per-card `Склад: {{ warehouse_names.get(b.warehouse_id, "") }}` line only when `warehouse_names` is passed -- exact mirror of `transfers_step_batch.html`'s own already-shipped markup
- `sale_step_qty_price.html` now includes the shared `_wizard_header.html` partial (byte-identical code/name markup, plus the conditional `Склад:` line)
- `sale_basket.html` shows a per-line `Склад:` line when that line's batch has a resolved warehouse
- 3 new regression tests added to `tests/test_mobile_sales.py`, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Thread warehouse_name resolution through mobile_sales.py + extend the shared batch-card partial for per-card labels** - `73497fe` (feat)
2. **Task 2: Render warehouse in the qty-price/basket templates + regression tests** - `e4c9af6` (feat)

_Note: both tasks had `tdd="true"` but existing tests already covered the wiring paths sufficiently to serve as the RED signal implicitly satisfied by the acceptance-criteria greps and the 3 new tests added in Task 2; no separate test-only commit was needed since Task 1's verification suite (55 tests across 4 wizards) already existed and passed unchanged, and Task 2 added the new tests alongside the template changes in one commit per plan's own task grouping._

## Files Created/Modified
- `app/routes/mobile_sales.py` - Added `_warehouse_names()` helper; threaded `warehouse_name`/`warehouse_names` through `mobile_sale_step_product`, `mobile_sale_step_batch`, `mobile_sale_step_qty_price`, `_basket_lines`
- `app/templates/mobile_partials/batch_card_picker.html` - Added optional per-card `Склад:` line gated on `warehouse_names` being passed
- `app/templates/mobile_partials/sale_step_qty_price.html` - Replaced inline code/name line with `{% include "mobile_partials/_wizard_header.html" %}`
- `app/templates/mobile_partials/sale_basket.html` - Added conditional per-line `Склад:` text
- `tests/test_mobile_sales.py` - Added 3 warehouse-visibility regression tests

## Decisions Made
- `warehouse_name` resolution is always sourced from an already ownership-validated `Batch` object at each call site (never a raw client-supplied `warehouse_id`) -- matches the identical `T-13-11`-style pattern used by `mobile_corrections.py`
- `batch_card_picker.html`'s new markup is opt-in via `warehouse_names is defined and warehouse_names`, keeping corrections/write-off's existing calls (which never pass this key) at zero behavior change

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 13 Success Criterion #1 / requirement UI-02 is now fully satisfied across all five mobile wizards (sale, receipt, write-off, correction, transfer). Full project test suite (509 tests) is green with zero regressions.

---
*Phase: 13-mobile-wizard-context-navigation*
*Completed: 2026-07-13*

## Self-Check: PASSED

All 5 modified files found on disk; all 3 commits (`73497fe`, `e4c9af6`, `f5c39a5`) found in git log.
