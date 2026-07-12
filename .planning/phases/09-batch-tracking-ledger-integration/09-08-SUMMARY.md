---
phase: 09-batch-tracking-ledger-integration
plan: 08
subsystem: ui
tags: [htmx, jinja2, fastapi, receipts, batch-chooser, autofill, gap-closure]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration
    provides: resolve-or-create batch chooser (D-01/D-02), /receipts/lookup name+price prefill (D-03/PD-10)
provides:
  - Self-explanatory batch chooser (fieldset/legend + state-adaptive helper text)
  - code_entered render flag distinguishing bare-load from resolved-no-batches
  - Client-side autofilled-vs-typed dirty flag restoring name autofill on repeat code lookups
affects: [09-verify-work, receipts-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Client-side data-autofilled dirty flag: server still authoritatively decides fill vs 204; the flag only lets the client clear a stale autofilled value before re-lookup"
    - "State-adaptive Jinja helper text driven by a route-supplied boolean flag (code_entered) instead of proxy inference in the template"

key-files:
  created: []
  modified:
    - app/routes/receipts.py
    - app/templates/partials/receipt_batch_chooser.html
    - app/templates/partials/name_input.html
    - app/templates/partials/receipt_form.html
    - tests/test_receipts.py

key-decisions:
  - "Kept the auto-select-new default for the empty-batches state (removed AMBIGUITY, not the pre-check) — unknown codes return 204 and never re-render the chooser, so removing the default would break the dominant new-product receipt flow. Deliberate, plan-sanctioned deviation from the gap's 'no pre-check on bare load' sub-bullet."
  - "Implemented the typed-vs-autofilled distinction entirely client-side to leave the Phase 2 D-23 server 204 contract and its test untouched."

patterns-established:
  - "Pattern: labelled <fieldset><legend> for radio groups instead of a bare <label> sibling"
  - "Pattern: data-autofilled marker + oninput dirty-clear to protect operator-typed values while allowing refresh of machine-filled ones"

requirements-completed: [WH-02, LOT-03, LOT-04]

# Metrics
duration: ~15min
completed: 2026-07-12
---

# Phase 9 Plan 08: Batch chooser clarity + name autofill fix Summary

**Receipt batch chooser is now a labelled fieldset with state-adaptive helper text, and «Название» autofill is restored via a client-side autofilled-vs-typed dirty flag — without touching the server 204 contract.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Batch chooser radio group wrapped in `<fieldset><legend>Партия</legend>` with a muted helper line that adapts to three states (no code yet / no open batches / choose top-up), removing the "непонятно к чему относится и уже выбрана" confusion (UAT test 1, symptom 1).
- Restored name autofill on repeat existing-code lookups: `name_input.html` now carries `autocomplete="off"`, a `data-autofilled="true"` marker on autofill responses, and an `oninput` dirty-clear; the code input clears a stale autofilled name before the next debounced lookup so the server refills it (UAT test 1, symptom 2).
- Preserved the new-product receipt flow (empty-batches still defaults to «Новая партия» so expiry/location/comment stay reachable) and the D-23 server 204 contract (its `test_web_lookup_204_when_name_typed` test unchanged).

## Task Commits

Each task was committed atomically:

1. **Task 1: Disambiguate the batch chooser (fieldset/legend + state-adaptive helper)** - `83658fe` (fix)
2. **Task 2: Restore name autofill via an autofilled-vs-typed dirty flag** - `c27bc4a` (fix)
3. **Task 3: Regression tests for chooser clarity and autofill markers** - `606dacb` (test)

## Files Created/Modified
- `app/routes/receipts.py` - `_chooser_context` now returns a `code_entered` flag on every render path (zero-warehouses early return, normal return, and the lookup unknown-code branch).
- `app/templates/partials/receipt_batch_chooser.html` - radio group is a `<fieldset><legend>` with a state-adaptive `.muted` helper line; `new_selected` default unchanged.
- `app/templates/partials/name_input.html` - `autocomplete="off"`, conditional `data-autofilled="true"` marker, `oninput` dirty-clear.
- `app/templates/partials/receipt_form.html` - code input `hx-on:input` clears an autofilled name before re-lookup.
- `tests/test_receipts.py` - 4 new regression tests locking in the fieldset/legend, the bare-load vs top-up hints (no radio pre-checked with open batches), and the name-input autofill markers.

## Decisions Made
- Kept the auto-select-new default for empty batches (fixed ambiguity, not the pre-check) — sanctioned by the plan's scope note because unknown codes never re-render the chooser.
- Distinguished typed vs autofilled names entirely client-side to keep the server 204 contract and its test intact.

## Deviations from Plan

None - plan executed exactly as written. (The kept auto-select-new default is an explicit, pre-approved design decision documented in the plan's objective scope note, not an unplanned deviation.)

## Issues Encountered
- Initial draft of the two chooser-rendering tests omitted the `warehouse` fixture, so `GET /receipts/new` rendered the zero-active-warehouses branch (no fieldset), and the `BARE_LOAD_HINT` substring `"Введите код товара"` false-matched the recent-receipts empty-state text. Resolved by adding the `warehouse` fixture to both tests and tightening the hint constant to `"Введите код товара и выберите склад"`. All 39 receipts tests pass; `ruff check` clean.

## Next Phase Readiness
- UAT test 1 symptoms 1 & 2 addressed; remaining browser UAT (live JS dirty-flag behavior) is verified manually per the plan.
- Symptom 3 (batches need a name — schema change) remains scoped to plan 09-09.

## Self-Check: PASSED

All modified files present on disk; all task + docs commits (83658fe, c27bc4a, 606dacb, f6a4f58) verified in git history.

---
*Phase: 09-batch-tracking-ledger-integration*
*Completed: 2026-07-12*
