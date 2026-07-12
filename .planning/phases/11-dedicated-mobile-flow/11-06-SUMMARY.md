---
phase: 11-dedicated-mobile-flow
plan: 06
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile, corrections, ledger]

requires:
  - phase: 11-dedicated-mobile-flow (plan 01)
    provides: mobile_client_factory test fixture, mobile_base.html layout, batch_card_picker.html shared partial, mobile-* CSS classes
provides:
  - Mobile Корректировка (stock correction) wizard, 4 steps (Товар -> Партия -> Режим -> Значение), isolated APIRouter at /m/corrections/*
  - Same-write-path guarantee: mobile_corrections.py calls app.services.corrections.register_correction unchanged, identical to desktop's correction_create
affects: [11-09 (final app.main router registration)]

tech-stack:
  added: []
  patterns:
    - "Single #corrections-step-wrap id target reused across every step's outerHTML swap, keeping the wizard's forward-control enable/disable state in sync with server-rendered selection"
    - "mobile_pages/corrections.html doubles as both wizard step 1 AND the D-05 post-success confirmation screen via a saved-context toggle, avoiding a separate success template"
    - "Over-removal warning renders as a full replacement of the step wrap (not a sibling overlay like desktop) with the step-4 fields re-embedded as hidden inputs, since mobile wizard steps fully replace their target rather than coexisting with a persistent form"

key-files:
  created:
    - app/routes/mobile_corrections.py
    - app/templates/mobile_pages/corrections.html
    - app/templates/mobile_partials/corrections_step_batch.html
    - app/templates/mobile_partials/corrections_step_mode.html
    - app/templates/mobile_partials/corrections_step_value.html
    - app/templates/mobile_partials/corrections_warning.html
    - app/templates/mobile_partials/corrections_name_echo.html
    - tests/test_mobile_corrections.py
  modified: []

key-decisions:
  - "Added app/templates/mobile_partials/corrections_name_echo.html (not in the plan's files_modified list) to implement the explicitly-required debounced code lookup echo — a small, clearly necessary fragment, not a scope expansion"
  - "Batch card tap targets the WHOLE #corrections-step-wrap (via batch_card_picker.html's batch_target override) instead of its own default #batch-wrap, so the step's forward control re-renders in sync with the freshly picked batch"
  - "Назад (back) links are simple returns to /m/corrections (step 1) rather than full per-step state reconstruction — UI-SPEC requires the control's presence but the plan's task/test text does not specify exact backward state restoration, and no test exercises it"

patterns-established:
  - "Success screen reuses the wizard's own step-1 page template with a `saved` context flag, keeping one file per wizard role where practical"

requirements-completed: [UI-01]

duration: ~15min
completed: 2026-07-12
---

# Phase 11 Plan 06: Mobile Correction Wizard Summary

**Mobile Корректировка wizard (Товар -> Партия -> Режим -> Значение) driving the exact same `register_correction()` write as desktop, with byte-identical zero-write-until-confirm over-removal guardrail and zero-net-delta rejection.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-12T23:00Z (approx.)
- **Completed:** 2026-07-12T23:19Z
- **Tasks:** 2
- **Files modified:** 8 (7 created, 1 test file)

## Accomplishments

- Full 4-step mobile wizard for stock corrections: Товар (debounced code lookup) → Партия (shared `batch_card_picker.html`, re-validated ownership) → Режим (count/delta radio rows) → Значение (mode-adapted label + batch-scoped remaining-qty hint)
- Final write calls `register_correction(session, code=, mode=, value_raw=, note=, batch_id=, confirm=)` — identical kwargs to `app/routes/corrections.py::correction_create`
- Over-removal warning is zero-write until `confirm=1`, verified with an explicit zero-Operation-rows assertion before the confirm re-post
- Zero-net-delta value (count == current batch quantity) is rejected gracefully (422, RU error, zero writes)
- A product with zero open batches renders no forward control at the Партия step

## Task Commits

Each task was committed atomically:

1. **Task 1: Route skeleton + steps Товар/Партия** - `d7d12d2` (feat)
2. **Task 2: Steps Режим/Значение + final write + guardrail + success + tests** - `ea4209e` (feat)

## Files Created/Modified

- `app/routes/mobile_corrections.py` - `router`, `GET /m/corrections`, `GET /m/corrections/lookup`, `POST /m/corrections/step/batch`, `GET /m/corrections/step/batch-pick`, `POST /m/corrections/step/mode`, `POST /m/corrections/step/value`, `POST /m/corrections` (final write)
- `app/templates/mobile_pages/corrections.html` - step 1 "Товар" screen; also the post-success confirmation screen (via `saved` context)
- `app/templates/mobile_partials/corrections_step_batch.html` - step 2 "Партия", includes `batch_card_picker.html`
- `app/templates/mobile_partials/corrections_step_mode.html` - step 3 "Режим", two `mobile-card` radio rows
- `app/templates/mobile_partials/corrections_step_value.html` - step 4 "Значение", mode-adapted label + batch-qty hint
- `app/templates/mobile_partials/corrections_warning.html` - over-removal warning, re-posts hidden fields + `confirm=1`
- `app/templates/mobile_partials/corrections_name_echo.html` - debounced lookup echo fragment (new, see Deviations)
- `tests/test_mobile_corrections.py` - 8 scenarios covering both tasks

## Decisions Made

- Reused `mobile_pages/corrections.html` for both the wizard's step-1 screen and the D-05 post-success confirmation screen (toggled by a `saved` context variable), avoiding a ninth template file not named in the plan's file list.
- Batch-card taps target the entire step wrap (`#corrections-step-wrap`) rather than `batch_card_picker.html`'s own default `#batch-wrap`, so the "Далее" forward control's enabled/disabled state always reflects the freshest server-rendered selection in one swap.
- Kept "Назад" navigation as a simple link back to `/m/corrections` on every step rather than reconstructing exact prior-step state — the UI-SPEC requires the control's presence, but neither the plan's task text, acceptance criteria, nor tests specify exact backward-state restoration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `corrections_name_echo.html` partial for the debounced code lookup**
- **Found during:** Task 1
- **Issue:** The plan's action text explicitly requires "debounced `code` lookup importing `lookup_prefill` from `app.services.corrections`" for the Товар step, but the plan's `files_modified` frontmatter did not list a template file for the lookup's echo response. Jinja2Templates (no jinja2-fragments in this project's dependencies) cannot render a sub-block of another template, so a small dedicated fragment was required to correctly implement the explicitly-specified behavior.
- **Fix:** Added `app/templates/mobile_partials/corrections_name_echo.html` (3 lines), included by `mobile_pages/corrections.html` for the initial render and returned directly by `GET /m/corrections/lookup` for the debounced swap.
- **Files modified:** `app/templates/mobile_partials/corrections_name_echo.html` (new), `app/templates/mobile_pages/corrections.html`, `app/routes/mobile_corrections.py`
- **Verification:** `uv run pytest tests/test_mobile_corrections.py -q` passes; manual review confirms the fragment follows the project's Jinja-autoescape-only convention (no `|safe`).
- **Committed in:** `d7d12d2` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary to implement the plan's own explicitly-stated debounced-lookup requirement; no scope creep beyond what the plan's action text already specified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `app/routes/mobile_corrections.py` is fully self-contained and tested in isolation via `mobile_client_factory` (Plan 01); it is NOT yet registered in `app.main` — that happens once, in Plan 09, alongside the other Phase 11 mobile routers.
- No blockers or concerns for Plan 09's registration step.

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*
