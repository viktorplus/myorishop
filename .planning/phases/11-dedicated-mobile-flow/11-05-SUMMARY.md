---
phase: 11-dedicated-mobile-flow
plan: 05
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile, write-off, batches]

# Dependency graph
requires:
  - phase: 11-dedicated-mobile-flow (Plan 01)
    provides: mobile_base.html layout, mobile_client_factory test fixture, batch_card_picker.html shared partial, .mobile-* CSS classes
provides:
  - Mobile Списание (write-off) wizard: 4 screens (Товар -> Партия -> Количество -> Причина) ending in the same register_writeoff() write as desktop
  - Reusable pattern (proven here first) for the other "single scalar batch_id" Phase 11 wizards: full-page POST-per-step navigation, htmx used only for the debounced code lookup and the batch-card tap echo
affects: [11-06, 11-07, 11-08, 11-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mobile wizard step navigation via plain (non-htmx) POST forms returning full pages — htmx reserved for small in-step partial swaps only (debounced lookup, batch-card tap echo)"
    - "Reason/mode selectors on mobile: visually-hidden native radio input inside a `.mobile-card` label, keeping the field keyboard-accessible while the card is the ≥44px tap target"
    - "Zero-write oversell warning re-post via native `form=\"...\"` attribute + a dedicated submit button `name=\"confirm\" value=\"1\"` — no htmx/JS required to add confirm=1 on top of the existing form fields"

key-files:
  created:
    - app/routes/mobile_writeoff.py
    - app/templates/mobile_pages/writeoff.html
    - app/templates/mobile_partials/writeoff_step_batch.html
    - app/templates/mobile_partials/writeoff_step_qty.html
    - app/templates/mobile_partials/writeoff_step_reason.html
    - app/templates/mobile_partials/writeoff_warning.html
    - app/templates/mobile_partials/writeoff_batch_wrap.html
    - app/templates/mobile_partials/writeoff_name_fill.html
    - tests/test_mobile_writeoff.py
  modified:
    - app/static/style.css

key-decisions:
  - "Reused mobile_pages/writeoff.html for BOTH step-1 form AND the post-success screen (differentiated by `saved` in context), avoiding a separate success template not listed in the plan's file scope"
  - "Added two small supporting fragment files (writeoff_batch_wrap.html, writeoff_name_fill.html) mirroring the desktop convention (writeoff_batch_pick.html/writeoff_lookup.html) so the htmx partial-swap targets have a single markup source, at the cost of one small duplicated 3-line block between writeoff_step_batch.html and writeoff_batch_wrap.html"
  - "Step-to-step wizard navigation uses plain browser POST forms (not htmx), keeping each step a real full-page navigation consistent with D-03/D-04's single-purpose-screen goal; htmx is scoped to the two documented in-step partial swaps only"

patterns-established:
  - "Every mobile wizard's 'Назад' button uses `onclick=\"history.back()\"` (native browser history, no new JS framework) since each step is a real page in the browser history stack"

requirements-completed: [UI-01]

# Metrics
duration: ~25min
completed: 2026-07-12
---

# Phase 11 Plan 05: Mobile Write-off Wizard Summary

**4-screen mobile Списание wizard (Товар → Партия → Количество → Причина) that calls the exact same `register_writeoff()` as desktop, with the reason picker rendered as accessible tappable cards instead of a native `<select>`.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-12T21:18:54Z
- **Tasks:** 2
- **Files modified:** 10 (8 created, 1 modified route file spans both tasks, 1 modified CSS)

## Accomplishments
- Full 4-step write-off wizard: code lookup (debounced, display-only) → batch pick (re-validated ownership, zero-batch block) → quantity → reason (tappable cards) → save
- Byte-identical write to desktop: same `register_writeoff()` call, same rollback/oversell/error branching
- Zero-write-until-confirmed oversell guardrail preserved exactly (T-11-15)
- 8 passing tests covering the full flow, including the batch-ownership re-validation and the reason-row rendering from the `WRITEOFF_REASONS` Jinja global

## Task Commits

Each task was committed atomically:

1. **Task 1: Route skeleton + steps Товар/Партия/Количество** - `9c12432` (feat)
2. **Task 2: Step Причина + final write + guardrail + success + tests** - `101b756` (feat)

_Note: the route file (app/routes/mobile_writeoff.py) was written once with all 7 endpoints and committed in Task 1; Task 2's commit adds the two templates (writeoff_step_reason.html, writeoff_warning.html) those already-committed handlers depend on, plus the CSS utility and the full test suite that exercises both tasks' code together._

## Files Created/Modified
- `app/routes/mobile_writeoff.py` - 7 endpoints: GET /m/writeoff, GET /m/writeoff/lookup, POST /m/writeoff/step/batch, GET /m/writeoff/step/batch-pick, POST /m/writeoff/step/qty, POST /m/writeoff/step/reason, POST /m/writeoff
- `app/templates/mobile_pages/writeoff.html` - step 1 form + post-success screen (shared file)
- `app/templates/mobile_partials/writeoff_step_batch.html` - step 2, includes batch_card_picker.html, blocks forward progress on zero batches
- `app/templates/mobile_partials/writeoff_batch_wrap.html` - standalone `#batch-wrap` fragment returned by the batch-pick tap echo
- `app/templates/mobile_partials/writeoff_step_qty.html` - step 3, single qty input
- `app/templates/mobile_partials/writeoff_step_reason.html` - step 4, tappable reason cards + note field
- `app/templates/mobile_partials/writeoff_warning.html` - oversell warning, verbatim desktop copy
- `app/templates/mobile_partials/writeoff_name_fill.html` - debounced name-display fragment for step 1
- `app/static/style.css` - `.visually-hidden` utility class (accessibility, not a new design token)
- `tests/test_mobile_writeoff.py` - 8 tests: batch listing, empty-batch block, unknown-code error, batch ownership re-validation, happy path, missing reason 422, oversell zero-write-then-confirm, reason row rendering

## Decisions Made
- Write-off wizard step transitions are plain (non-htmx) `<form method="post">` submissions returning full pages, not htmx partial swaps — matches the phase's "single-purpose screen" philosophy and keeps the browser back button (`history.back()`) meaningful for the "Назад" control. htmx is used only for the two documented small partial swaps (debounced code→name lookup, batch-card tap echo).
- `mobile_pages/writeoff.html` doubles as both the step-1 screen and the post-success screen (toggled by `saved` in context) rather than adding a separate success template, since the plan's `files_modified` listed this file only once.
- Two small supporting fragment files were added beyond the plan's exact file list (`writeoff_batch_wrap.html`, `writeoff_name_fill.html`) — necessary so the htmx partial-swap responses have their own single-purpose template, mirroring the existing desktop pattern (`writeoff_batch_wrap.html`/`writeoff_lookup.html`). Documented under Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added two small supporting template files not in the plan's `files_modified` list**
- **Found during:** Task 1
- **Issue:** The plan's `files_modified` lists only `writeoff_step_batch.html` for step 2, but the batch-card tap echo (`GET /m/writeoff/step/batch-pick`) needs to return ONLY the `#batch-wrap` div (for an htmx `outerHTML` swap), not the whole step-2 page — and the debounced code lookup similarly needs its own small fragment target. Without these, either the htmx swap would break (wrong root element) or markup would need to be duplicated inline via ad-hoc string templates.
- **Fix:** Added `mobile_partials/writeoff_batch_wrap.html` and `mobile_partials/writeoff_name_fill.html`, mirroring the desktop convention (`partials/writeoff_batch_wrap.html`, `partials/writeoff_lookup.html`) where a small dedicated fragment file backs an htmx partial-swap endpoint. `writeoff_step_batch.html` still directly includes `batch_card_picker.html` itself (satisfying the plan's literal `writeoff_step_batch.html includes batch_card_picker.html` acceptance criterion) — the wrap file duplicates the 3-line `<div id="batch-wrap">...</div>` shell only, used solely by the pick-echo endpoint.
- **Files modified:** app/templates/mobile_partials/writeoff_batch_wrap.html, app/templates/mobile_partials/writeoff_name_fill.html
- **Verification:** `test_batch_pick_revalidates_ownership_against_another_product` and `test_batch_step_lists_open_batches_and_includes_picker` both pass
- **Committed in:** 9c12432 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added `.visually-hidden` CSS utility class**
- **Found during:** Task 2
- **Issue:** The plan requires the reason radio input to be "visually-hidden" while remaining keyboard-accessible (per the Interaction Contract's accessibility bullet), but no such utility class existed in `style.css`.
- **Fix:** Added the standard clip-rect `.visually-hidden` technique — reuses no new color/spacing tokens, purely an accessibility utility.
- **Files modified:** app/static/style.css
- **Verification:** `test_reason_step_renders_one_row_per_writeoff_reason` asserts `class="visually-hidden"` is present
- **Committed in:** 101b756 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 2 — missing critical supporting artifacts, not scope creep)
**Impact on plan:** Both additions are small, single-purpose files/utilities required for the htmx partial-swap and accessibility requirements the plan itself specifies. No architectural change, no new dependency.

## Issues Encountered
- Initial test for the happy-path write asserted `product.quantity == 7` after a write-off of 3 from a batch seeded directly at quantity 10 — this ignored that the `product` fixture starts at quantity 0 (unrelated to the batch's directly-set quantity, since the batch wasn't created through the ledger). Fixed the assertion to check the batch's post-write quantity (7) and the product's ledger-cache delta (-3) separately — this is a test-only correction, not a code bug (register_writeoff's dual-projection behavior is correct and unchanged).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The full-page-POST-per-step wizard pattern, the tappable-card reason/mode selector pattern, and the native `form="..."` + dedicated `name`/`value` confirm-button pattern (for zero-JS oversell re-post) are all now proven and available for the remaining Phase 11 wizards (Correction, Transfer, Sale) to reuse.
- `app/routes/mobile_writeoff.py`'s router is NOT yet registered in `app/main.py` — that happens in Plan 09 alongside every other Phase 11 router, per the plan's stated scope.

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*
