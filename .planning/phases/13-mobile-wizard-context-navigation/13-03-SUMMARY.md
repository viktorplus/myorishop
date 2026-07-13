---
phase: 13-mobile-wizard-context-navigation
plan: 03
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile-wizard, receipts]

# Dependency graph
requires: ["13-01"]
provides:
  - "Receipts wizard step 2's own hx-get Назад button (last plain-link exception closed)"
  - "GET /m/receipts serving both a full page and a bare HX-Request fragment, with an optional ?code= pre-fill (D-08/UI-05 route-side prerequisite for 13-05's search quick-action link)"
  - "Receipts wizard step 2 (Партия) showing visible code/name/warehouse context via the shared _wizard_header.html partial (UI-02)"
affects: [13-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Receipts' warehouse is chosen in step 1, before any batch is picked — unlike corrections/write-off, warehouse_name is available on every render of step 2, no batch-pick dependency"

key-files:
  created:
    - app/templates/mobile_partials/receipts_step_product.html
  modified:
    - app/routes/mobile_receipts.py
    - app/templates/mobile_pages/receipts.html
    - app/templates/mobile_partials/receipts_step_batch.html
    - tests/test_mobile_receipts.py

key-decisions:
  - "Task 1's tdd=\"true\" flag was satisfied structurally rather than with a dedicated RED/GREEN cycle: the plan itself bundles Task 1's own acceptance-criteria tests into Task 2's test additions (Task 2's tests 3/4 are exactly Task 1's ?code=/HX-Request acceptance criteria) — followed the plan's literal task boundaries rather than duplicating tests across two tasks."

requirements-completed: [UI-02, UI-03, UI-05]

# Metrics
duration: ~7min
completed: 2026-07-14
---

# Phase 13 Plan 03: Receipts Wizard Context & Navigation Summary

**Receipts wizard's step 2 "Назад" converted from a plain full-page link to the same hx-get + fragment pattern used everywhere else in the phase, GET /m/receipts now accepts a ?code= pre-fill and serves both a full page and a bare fragment, and step 2 now shows the same visible code/name/warehouse header as every other fixed wizard's Партия step.**

## Performance

- **Duration:** ~7 min
- **Tasks:** 3 completed
- **Files modified:** 3 modified, 1 created

## Accomplishments
- `GET /m/receipts` accepts an optional `?code=` query param (echoed into the code field) and branches on `HX-Request` to serve either the full page or a bare fragment from the same context
- Receipts' step 1 (Товар) markup extracted into `receipts_step_product.html`, shared by the full-page route and the new HX-Request fragment branch — `mobile_pages/receipts.html` now just includes it
- Receipts step 2's own "Назад" button converted from `<a class="button secondary" href="/m/receipts">` to `hx-get="/m/receipts"` + `hx-include="closest form"` + `hx-target="#wizard-step"` + `hx-swap="innerHTML"` — the typed code now survives the round trip, closing the last plain-link exception in the phase's audit
- Added a `_warehouse_names` helper (copied verbatim from `mobile_transfers.py`) to `mobile_receipts.py`, threading `warehouse_name` into step/batch's context; `receipts_step_batch.html` now includes the shared `_wizard_header.html` partial showing `<strong>code</strong> — name` plus a conditional `Склад:` line
- 8 new tests added to `tests/test_mobile_receipts.py` (22 total in the file); full suite (504 tests) green with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: mobile_receipt_new — code query param + HX-Request branch** - `675b807` (feat)
2. **Task 2: Extract receipts_step_product.html + fix receipts_step_batch.html's Назад + tests** - `3694b76` (feat)
3. **Task 3: Visible code/name/warehouse header on receipts_step_batch.html (UI-02)** - `409cb93` (feat)

_Plan metadata commit deferred — worktree mode: orchestrator handles the final docs commit after merge._

## Files Created/Modified
- `app/templates/mobile_partials/receipts_step_product.html` - New extracted step-1 (Товар) fragment shared by the full-page GET and the HX-Request bare-fragment branch
- `app/routes/mobile_receipts.py` - `mobile_receipt_new` accepts/echoes `?code=` and branches on `HX-Request`; new `_warehouse_names` helper; `mobile_receipt_step_batch` threads `warehouse_name`
- `app/templates/mobile_pages/receipts.html` - `{% block content %}` rewritten around the extracted step-1 partial, `zero_warehouses` conditional now lives inside the partial
- `app/templates/mobile_partials/receipts_step_batch.html` - Own "Назад" converted to `hx-get`; includes `_wizard_header.html` for the visible code/name/warehouse line
- `tests/test_mobile_receipts.py` - 8 new tests: plain-link removal, hx-get target, `?code=` pre-fill on both response shapes, and the header rendering on known/unknown codes

## Decisions Made
- Task 1 carries `tdd="true"` but its own `<files>` list excludes the test file, and its acceptance criteria are literally re-tested by Task 2's own test additions (tests 3 and 4 in Task 2's action list). Rather than write a duplicate RED test in Task 1 and another in Task 2, followed the plan's literal task boundaries: Task 1's route change was verified against the existing (unaffected) test suite, and its behavior-specific tests were added once, in Task 2, exactly as the plan specifies.

## Deviations from Plan

None - plan executed exactly as written. All three tasks' actions, tests, and acceptance criteria matched their literal specifications; the `receipts_step_product.html` extraction preserved the original `zero_warehouses` conditional and Далее button verbatim, just relocated per the plan's explicit instruction.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `GET /m/receipts` now consumes `?code=` exactly as Plan 13-05's search quick-action link requires (D-08/UI-05 route-side prerequisite satisfied)
- Receipts wizard has zero remaining plain-link "Назад" exceptions; every step now uses the uniform hx-get/hx-post + fragment-swap pattern
- No blockers for 13-04 (transfers) or 13-05 (search quick actions)

---
*Phase: 13-mobile-wizard-context-navigation*
*Completed: 2026-07-14*
