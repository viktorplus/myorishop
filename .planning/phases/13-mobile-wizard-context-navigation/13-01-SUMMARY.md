---
phase: 13-mobile-wizard-context-navigation
plan: 01
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile-wizard]

# Dependency graph
requires: []
provides:
  - "_wizard_header.html shared partial (code/name + conditional Склад: line) reused verbatim by Plan 13-02 (write-off migration)"
  - "corrections wizard's Партия/Режим/Значение steps showing visible code/name/warehouse context"
  - "corrections wizard's all 4 steps' Назад buttons targeting their own immediate predecessor via hx-get/hx-post + fragment swap"
  - "GET /m/corrections serving both a full page and a bare HX-Request fragment from one route"
affects: [13-02, 13-03, 13-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared _wizard_header.html partial: {code, name, warehouse_name} context contract, name/warehouse_name must be None (not '') to omit their line"
    - "hx-get/hx-post + hx-include=\"closest form\" + hx-target=\"#corrections-step-wrap\" hx-swap=\"outerHTML\" for every wizard step's own Назад button, replacing plain <a> links"
    - "GET route branches on bool(request.headers.get(\"HX-Request\")) to serve either a full page or a bare fragment from the same context dict"

key-files:
  created:
    - app/templates/mobile_partials/_wizard_header.html
    - app/templates/mobile_partials/corrections_step_product.html
  modified:
    - app/routes/mobile_corrections.py
    - app/templates/mobile_pages/corrections.html
    - app/templates/mobile_partials/corrections_step_batch.html
    - app/templates/mobile_partials/corrections_step_mode.html
    - app/templates/mobile_partials/corrections_step_value.html
    - tests/test_mobile_corrections.py

key-decisions:
  - "Extracted a _carried_warehouse_name(session, code, batch_id) helper in mobile_corrections.py reused by step/mode, step/value, and create, instead of duplicating the product-lookup + batch-ownership re-validation three times"
  - "corrections_step_batch.html's own form gained a hidden name input (not explicitly specified in the plan's Task 2 action) so name threads forward into step/mode's Form(name) parameter — required for the header to render on step 3, applied per deviation Rule 2"

patterns-established:
  - "Wizard step back-navigation always targets its own immediate predecessor route, never step 1, via hx-get/hx-post + hx-include=\"closest form\""

requirements-completed: [UI-02, UI-03]

# Metrics
duration: ~20min
completed: 2026-07-14
---

# Phase 13 Plan 01: Corrections Wizard Context & Navigation Summary

**Corrections wizard's Партия/Режим/Значение steps now show visible code/name/warehouse context via a new shared `_wizard_header.html` partial, and all 4 steps' "Назад" buttons target their own immediate predecessor via hx-get/hx-post + fragment swap instead of a plain link that reset to step 1.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3 completed
- **Files modified:** 6 modified, 2 created

## Accomplishments
- `_wizard_header.html` created: a 2-line shared Jinja partial rendering `<strong>{{code}}</strong> — {{name}}` plus a conditional `Склад: {{warehouse_name}}` line, reused by 13-02's write-off migration
- Corrections wizard's Товар step extracted into `corrections_step_product.html` and shared by both the cold full-page GET and a new bare-fragment HX-Request branch on `GET /m/corrections`
- All 4 corrections "Назад" controls (step 2, 3, 4, and step 2's own back-to-step-1) converted from plain `<a class="mobile-back">` links to `hx-get`/`hx-post` buttons targeting their own immediate predecessor route
- `mobile_corrections.py`'s 6 routes thread `name`/`warehouse_name` end-to-end, re-validating the carried `batch_id`'s ownership against the resolved product before trusting its `warehouse_id` for display (T-13-02 mitigation)

## Task Commits

Each task was committed atomically:

1. **Task 1: Thread name/warehouse_name through mobile_corrections.py + serve step 1 as page or fragment** - `4379de5` (feat)
2. **Task 2: Shared header partial + corrections step-1 extraction + step-2 template fix** - `45f7d3c` (feat)
3. **Task 3: corrections_step_mode.html + corrections_step_value.html header/Назад fixes + tests** - `1ce4f55` (feat)

_Plan metadata commit deferred — worktree mode: orchestrator handles the final docs commit after merge._

## Files Created/Modified
- `app/templates/mobile_partials/_wizard_header.html` - New shared partial (code/name + conditional Склад: line)
- `app/templates/mobile_partials/corrections_step_product.html` - Extracted step-1 fragment shared by full-page and HX-Request paths
- `app/routes/mobile_corrections.py` - 6 routes thread name/warehouse_name; GET /m/corrections branches on HX-Request; new `_warehouse_names`/`_carried_warehouse_name` helpers
- `app/templates/mobile_pages/corrections.html` - `{% else %}` branch replaced with a single include of the extracted step-1 fragment
- `app/templates/mobile_partials/corrections_step_batch.html` - Includes header partial; own Назад converted to hx-get fragment swap; carries `name` forward via hidden input
- `app/templates/mobile_partials/corrections_step_mode.html` - Includes header partial; carries `name` forward; Назад now hx-post to `/m/corrections/step/batch`
- `app/templates/mobile_partials/corrections_step_value.html` - Includes header partial; carries `name` forward; Назад now hx-post to `/m/corrections/step/mode`
- `tests/test_mobile_corrections.py` - 3 new tests covering header rendering, own-predecessor Назад targeting, absence of remaining `mobile-back` links, and the HX-Request full-vs-fragment branch

## Decisions Made
- Factored the batch-ownership-revalidated warehouse-name resolution into one `_carried_warehouse_name(session, code, batch_id)` helper reused by `step/mode`, `step/value`, and `create` rather than repeating the same product-lookup + ownership check three times inline (plan described the logic per-route; this consolidates it without changing behavior)
- Added a hidden `name` input to `corrections_step_batch.html`'s own form (not explicitly listed in the plan's Task 2 action) — required so `name` reaches `step/mode`'s new `Form("")` parameter; applied under deviation Rule 2 (missing critical functionality — without it the header would never render past step 2)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added hidden `name` input to corrections_step_batch.html's form**
- **Found during:** Task 2
- **Issue:** Task 1 added a `name: str = Form("")` parameter to `mobile_correction_step_mode`, but the plan's Task 2 action for `corrections_step_batch.html` didn't mention adding a hidden `name` input to carry the value forward — without it, `name` would arrive empty at step 3 and the new header would show only the code, defeating the plan's own D-01/D-03 truth
- **Fix:** Added `<input type="hidden" name="name" value="{{ name }}">` alongside the existing hidden `code`/`batch_qty` inputs
- **Files modified:** `app/templates/mobile_partials/corrections_step_batch.html`
- **Verification:** `test_mobile_correction_step_mode_and_value_show_header_and_own_back_target` asserts the header renders with the product name at step/mode
- **Committed in:** `45f7d3c` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary for the plan's own success criteria (visible name at every step) to actually hold at runtime. No scope creep — same file the plan already listed as modified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `_wizard_header.html` is ready for Plan 13-02 (write-off migration) to include verbatim, as specified in the plan objective
- All 490 tests in the full suite pass; corrections wizard's 11 tests (8 pre-existing + 3 new) are green
- No blockers for 13-02/13-03/13-04, which apply the identical step-2-Назад and header pattern to write-off/receipts/transfers wizards

---
*Phase: 13-mobile-wizard-context-navigation*
*Completed: 2026-07-14*
