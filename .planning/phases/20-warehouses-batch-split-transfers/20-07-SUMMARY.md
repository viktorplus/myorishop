---
phase: 20-warehouses-batch-split-transfers
plan: 07
subsystem: ui
tags: [jinja2, htmx, transfers, forms]

# Dependency graph
requires:
  - phase: 20-warehouses-batch-split-transfers
    provides: "Plan 20-05's /transfers POST route already accepting/validating new_expiry and new_comment form fields (D-06/D-07/D-09), plus form_echo carrying them on a 422 re-render"
provides:
  - "Desktop /transfers now shows the same-warehouse-split override fields (expiry, condition/comment) that Plan 20-05 already made functional server-side"
affects: [20-08 (if any further transfer-surface plan exists), navigation phase 24 (NAV-07 nests Перемещение under product context)]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - app/templates/partials/transfer_batch_wrap.html
    - app/templates/partials/transfer_form.html
    - tests/test_transfers.py

key-decisions:
  - "Override fields render in a SEPARATE {% if selected_batch_id %} block from the destination-select block, per UI-SPEC decision 9 / RESEARCH Pitfall 5 (must not be gated on which destination is picked or whether any destination exists)"

patterns-established:
  - "Override field markup and copy are byte-identical between desktop (transfer_batch_wrap.html) and mobile (transfers_step_dest.html) — same label/span text, same input types, same default('') echo convention"

requirements-completed: [XFER-01]

# Metrics
duration: 8min
completed: 2026-07-16
---

# Phase 20 Plan 07: Desktop Transfer Override Fields Summary

**Added the browser-visible expiry/condition override inputs to desktop `/transfers`, rendered unconditionally once a source batch is picked and wired through the existing 422-echo mechanism, closing the last piece of XFER-01's desktop UI surface.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-16T16:58:52Z
- **Completed:** 2026-07-16T17:06:27Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `transfer_batch_wrap.html` now renders "Новый срок годности" and "Новое состояние или комментарий" inputs in their own `{% if selected_batch_id %}` block, independent of the destination-warehouse select's `_wh_list`-gated block
- `transfer_form.html` threads `new_expiry_value`/`new_comment_value` (sourced from `form.new_expiry`/`form.new_comment`, already populated by Plan 20-05's `form_echo`) through the existing `{% with %}` include, so a 422 re-render never loses the operator's typed override values
- Added 3 tests covering field presence + UI-SPEC-locked copy, the D-06 error rendering inside the existing `error-block` container, and override-value echo surviving an unrelated qty-validation 422

## Task Commits

Each task was committed atomically:

1. **Task 1: Override field templates (D-06 copy, Pitfall 5, UI-SPEC decision 9)** - `2bb7e4a` (feat)
2. **Task 2: Web-level tests for the override UI + D-06 error rendering** - `5c64389` (test)

## Files Created/Modified
- `app/templates/partials/transfer_batch_wrap.html` - Added the two override `.field` divs in a separate conditional block after the destination-select block
- `app/templates/partials/transfer_form.html` - Passes `new_expiry_value`/`new_comment_value` into the `transfer_batch_wrap.html` include
- `tests/test_transfers.py` - Added `test_transfer_batch_pick_shows_override_fields`, `test_transfer_post_same_warehouse_blank_overrides_error_visible_in_form`, `test_transfer_post_422_echoes_typed_override_values`

## Decisions Made
None beyond what the plan specified - followed the plan exactly, including the explicit instruction to keep the two `{% if %}` conditions separate rather than combining them.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

This was the final plan touching the transfer surface in Phase 20 (per the plan's own verification note). `uv run pytest tests/test_transfers.py -q` (29 passed) and the full suite `uv run pytest -q` (749 passed) are both green. Manual browser verification (open `/transfers`, pick a batch, confirm both override fields appear, submit a same-warehouse split with an expiry override) is recommended but was not performed by this agent — no interactive browser session available in this execution context.

---
*Phase: 20-warehouses-batch-split-transfers*
*Completed: 2026-07-16*
