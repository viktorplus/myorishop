---
phase: 13-mobile-wizard-context-navigation
plan: 02
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile-wizard]

# Dependency graph
requires: ["13-01"]
provides:
  - "Write-off wizard migrated from full-page-per-step to persistent-shell + fragment-swap architecture, mirroring receipts.html"
  - "Write-off wizard's Партия/Количество/Причина steps show visible code/name/warehouse context via _wizard_header.html"
  - "Zero history.back() remaining anywhere in write-off templates — all 4 steps' Назад buttons target their own immediate predecessor via hx-get/hx-post"
affects: [13-03, 13-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reused _wizard_header.html and the hx-get/hx-post + hx-include=\"closest form\" Назад pattern from 13-01 verbatim for a second wizard"
    - "Ambient persistent form id renamed (writeoff-reason-form -> writeoff-form) to match the single-shell-form convention; danger/oversell button re-posts via form=\"writeoff-form\" + hx-post + hx-vals (mirrors corrections_warning.html)"

key-files:
  created:
    - app/templates/mobile_partials/writeoff_step_product.html
  modified:
    - app/routes/mobile_writeoff.py
    - app/templates/mobile_pages/writeoff.html
    - app/templates/mobile_partials/writeoff_step_batch.html
    - app/templates/mobile_partials/writeoff_step_qty.html
    - app/templates/mobile_partials/writeoff_step_reason.html
    - app/templates/mobile_partials/writeoff_warning.html
    - tests/test_mobile_writeoff.py

key-decisions:
  - "Added a _carried_warehouse_name(session, code_clean, batch_id_clean) helper in mobile_writeoff.py, mirroring 13-01's mobile_corrections.py precedent, instead of duplicating the product-lookup + batch-ownership re-validation across step/qty, step/reason, and submit"
  - "Added explicit hx-post=\"/m/writeoff/step/qty\" to writeoff_step_batch.html's own 'Далее' button (plan's Task 2 action described it as 'already correctly type=submit inside the ambient form', but removing the old <form action=...> wrapper left the button with no navigation target — a plain submit would have triggered a native GET to the current page)"

patterns-established: []

requirements-completed: [UI-02, UI-03]

# Metrics
duration: ~25min
completed: 2026-07-14
---

# Phase 13 Plan 02: Write-off Wizard Context & Navigation Summary

**Write-off wizard migrated from its old full-page-per-step architecture (per-step `{% extends %}` templates, `history.back()` for "Назад") to the persistent-shell + htmx-fragment-swap architecture every other mobile wizard uses, gaining visible code/name/warehouse context on all 3 intermediate steps along the way.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 3 completed
- **Files modified:** 6 modified, 1 created (route + 5 templates + tests)

## Accomplishments
- `app/routes/mobile_writeoff.py`'s 6 routes thread `name`/`warehouse_name` end-to-end; `GET /m/writeoff` branches on `HX-Request` to serve either the full page or a bare `writeoff_step_product.html` fragment; `register_writeoff` is now called with the real carried `name` instead of a hardcoded `""`
- `mobile_pages/writeoff.html` restructured as a persistent shell (one ambient `<form id="writeoff-form">` wrapping `#wizard-step`), mirroring `mobile_pages/receipts.html` verbatim; the old `{% block step_indicator %}` override removed
- All 3 intermediate write-off steps (`writeoff_step_batch.html`, `writeoff_step_qty.html`, `writeoff_step_reason.html`) converted from full-page templates to bare fragments, each including `_wizard_header.html` (created in 13-01) to show `<strong>{{code}}</strong> — {{name}}` plus a conditional `Склад:` line
- Every write-off "Назад" button now targets its own immediate predecessor route via `hx-post`/`hx-get` + `hx-include="closest form"` — zero `onclick="history.back()"` remains anywhere in `app/templates/mobile_partials/writeoff_*.html`
- `writeoff_warning.html`'s oversell danger button re-posts the renamed ambient `#writeoff-form` via `hx-post`/`hx-vals` (mirrors `corrections_warning.html`'s exact shape) instead of a native `name="confirm" value="1"` submit-button pair
- Full pytest suite (500 tests) is green — zero regressions across the whole app

## Task Commits

Each task was committed atomically:

1. **Task 1: Route migration — HX-Request branch + name/warehouse_name threading in mobile_writeoff.py** - `6fbc1ee` (feat)
2. **Task 2: Shell migration — mobile_pages/writeoff.html, writeoff_step_product.html, writeoff_step_batch.html** - `6c387f8` (feat)
3. **Task 3: writeoff_step_qty.html + writeoff_step_reason.html + writeoff_warning.html + tests** - `c5cb6bc` (feat)

_Plan metadata commit deferred — worktree mode: orchestrator handles the final docs commit after merge._

## Files Created/Modified
- `app/routes/mobile_writeoff.py` - Added `_warehouse_names`/`_carried_warehouse_name` helpers; all 6 routes thread `name`/`warehouse_name`; `GET /m/writeoff` branches on `HX-Request`; `register_writeoff` called with `name=name`
- `app/templates/mobile_pages/writeoff.html` - `{% else %}` branch replaced with a single ambient `#writeoff-form` wrapping `#wizard-step`, including the extracted step-1 fragment; `saved` branch unchanged
- `app/templates/mobile_partials/writeoff_step_product.html` - New: extracted step-1 fragment shared by full-page and HX-Request paths
- `app/templates/mobile_partials/writeoff_step_batch.html` - Bare fragment: includes header partial; hidden `name` input added; own Назад now `hx-get="/m/writeoff"`; own Далее now explicit `hx-post="/m/writeoff/step/qty"` (Rule 1 fix, see Decisions)
- `app/templates/mobile_partials/writeoff_step_qty.html` - Bare fragment: includes header partial; hidden `name` input added; Назад now `hx-post="/m/writeoff/step/batch"`; Далее now `hx-post="/m/writeoff/step/reason"`
- `app/templates/mobile_partials/writeoff_step_reason.html` - Bare fragment: includes header partial; hidden `name` input added; `id="writeoff-reason-form"` removed (folds into ambient `#writeoff-form`); Назад now `hx-post="/m/writeoff/step/qty"`; submit now `hx-post="/m/writeoff"`
- `app/templates/mobile_partials/writeoff_warning.html` - Danger button `form` attribute renamed to `writeoff-form`; added `hx-post`/`hx-vals`/`hx-target`/`hx-swap`/`hx-disabled-elt` (mirrors `corrections_warning.html`)
- `tests/test_mobile_writeoff.py` - 2 new tests: header + own-predecessor-Назад-target on qty/reason steps, and the `HX-Request` full-vs-fragment branch on `GET /m/writeoff`

## Decisions Made
- Factored the batch-ownership-revalidated warehouse-name resolution into one `_carried_warehouse_name(session, code_clean, batch_id_clean)` helper reused by `step/qty`, `step/reason`, and `mobile_writeoff_submit`, mirroring the precedent `_carried_warehouse_name` helper 13-01 established in `mobile_corrections.py`, rather than repeating the product-lookup + ownership check three times inline
- Added explicit `hx-post="/m/writeoff/step/qty"` to `writeoff_step_batch.html`'s own "Далее" button under deviation Rule 1 (bug fix): the plan's Task 2 action described this button as "already correctly `type="submit"` inside the ambient form," but removing the old `<form method="post" action="/m/writeoff/step/qty">` wrapper (Task 2's own instruction) left the button with no submission target — a bare `type="submit"` inside the new ambient `#writeoff-form` (which has no `hx-post`/`action`) would have triggered a native browser GET to the current URL instead of advancing the wizard. Fixed inline, verified by the existing `test_batch_step_lists_open_batches_and_includes_picker` still passing (asserts "Далее" is present) and the new header/back-target test suite.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added missing hx-post to writeoff_step_batch.html's "Далее" button**
- **Found during:** Task 2
- **Issue:** Plan's Task 2 action said to keep the "Далее" button unchanged (plain `type="submit"`) since it was "already correctly... inside the ambient form" — but the same task instructed removing the old `<form action="/m/writeoff/step/qty">` wrapper. Without an `hx-post` on the button itself, submitting would fall back to a native browser form submission (GET, no target URL), breaking navigation from step 2 to step 3.
- **Fix:** Added `hx-post="/m/writeoff/step/qty" hx-include="closest form"` to the button, matching the pattern used by every other "Далее" button in this same migration (step 1, qty, reason) and in `receipts_step_details.html`.
- **Files modified:** `app/templates/mobile_partials/writeoff_step_batch.html`
- **Verification:** Full `test_mobile_writeoff.py` suite (10 tests) green; manual trace of the ambient form's attributes confirms no other implicit submission path exists.
- **Committed in:** `6c387f8` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for the wizard to actually advance past step 2 — without it, tapping "Далее" on the Партия step would silently reload the page instead of posting to `/m/writeoff/step/qty`. No scope creep — same file the plan already listed as modified in Task 2.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Threat Model Verification
- T-13-04 (Tampering/Information Disclosure — `_wizard_header.html` rendering `{{ name }}`/`{{ warehouse_name }}`): mitigated — Jinja2 autoescaping only, no `|safe` applied anywhere in the modified templates.
- T-13-05 (Tampering — `warehouse_name` resolved from client-carried `batch_id`): mitigated — `_carried_warehouse_name` re-validates `candidate.product_id == product.id` before trusting `warehouse_id`, applied uniformly in `step/qty`, `step/reason`, and `mobile_writeoff_submit`.
- T-13-06 (Repudiation/Tampering — removing the per-step `<form>` boundary): mitigated — `register_writeoff` is unchanged and still re-validates every field (qty, reason_code allow-list, batch ownership) server-side regardless of which HTML element carried the POST; this migration is presentation-layer only.

## Next Phase Readiness
- Write-off wizard now matches the same persistent-shell + `_wizard_header.html` + own-predecessor-Назад pattern established by 13-01's corrections wizard migration
- All 500 tests in the full suite pass; write-off wizard's 10 tests (8 pre-existing + 2 new) are green
- No blockers for 13-03/13-04, which apply the identical pattern to the remaining wizards (sale/receipt basket, transfers)

---
*Phase: 13-mobile-wizard-context-navigation*
*Completed: 2026-07-14*

## Self-Check: PASSED

All 8 created/modified files verified on disk; all 3 task commits (6fbc1ee, 6c387f8, c5cb6bc) verified in `git log`.
