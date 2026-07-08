---
phase: 02-catalog-dictionary-search
plan: 04
subsystem: ui
tags: [fastapi, htmx, jinja2, sqlalchemy, dictionary, autofill]

# Dependency graph
requires:
  - phase: 02-catalog-dictionary-search (plan 02-01)
    provides: Dictionary model (UUID PK + UNIQUE(code)), product_form.html with div#name-wrap contract, thin-route/fat-service pattern
  - phase: 02-catalog-dictionary-search (plan 02-02)
    provides: edit-mode product form (delete zone, price history) that the name-field include must not disturb
provides:
  - Dictionary service (add_entry/update_entry/list_entries/lookup) — plain CRUD, zero ledger involvement (D-24)
  - /dictionary page with inline add row and inline row editing via #dictionary-rows partial
  - GET /dictionary/lookup autofill endpoint — 200 name-wrap fragment vs 204 no-op (D-23, Pitfall 5)
  - partials/name_input.html — shared name-field fragment (PD-6), reusable by Phase 3 receipt form
  - «Справочник» nav entry in base.html
affects: [phase-3-receipts (RCP-02 reuses lookup + name_input partial), phase-2-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "204 No Content autofill: server decides fill vs no-op; htmx ignores 204 so the client stays dumb"
    - "form= attribute rows: inline table row editing without nested <form> elements"
    - "Shared field fragment: static form include and HTMX swap render the same partial (PD-6)"

key-files:
  created:
    - app/services/dictionary.py
    - app/routes/dictionary.py
    - app/templates/pages/dictionary.html
    - app/templates/partials/dictionary_rows.html
    - app/templates/partials/name_input.html
    - tests/test_dictionary.py
  modified:
    - app/main.py
    - app/templates/base.html
    - app/templates/pages/product_form.html

key-decisions:
  - "02-04: dictionary row editing uses HTML form= attribute association — inline per-row forms inside the table without illegal nested <form> markup"
  - "02-04: dictionary service docstring avoids the literal string record_operation so the no-ledger grep gate stays clean"

patterns-established:
  - "204 autofill contract: GET lookup returns a fragment only when code is known AND submitted name is empty; 204 otherwise"
  - "PD-6 single-source field fragment: {% with %} + include passes name/autofilled/errors into name_input.html from both the form and the lookup route"

requirements-completed: [CAT-02]

# Metrics
duration: 9min
completed: 2026-07-08
---

# Phase 2 Plan 04: Reference Dictionary + Name Autofill Summary

**Code→name reference dictionary at /dictionary with inline add/edit, plus debounced HTMX autofill that fills an empty product-form name from a known code via the 200-fragment/204 contract**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-08T18:45:47Z
- **Completed:** 2026-07-08T18:54:27Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- CAT-02 complete: operator maintains code→name pairs at /dictionary (paste-friendly plain inputs, no masks) and the product form auto-fills empty names from known codes
- Autofill safety: server answers 204 when the code is unknown OR the operator already typed a name — operator input is never overwritten (Pitfall 5)
- D-24 enforced and test-proven: dictionary writes touch neither Product rows nor the operations ledger (zero Operation rows from dictionary calls)
- name_input.html is the single source for the name-field markup — the static form include and the lookup swap can never drift apart (PD-6)
- Full suite green: 70 tests (13 new dictionary tests + all prior catalog/search/Phase-1 tests); ruff clean; all grep gates hold

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests — dictionary CRUD + lookup 200/204 branches + form wiring (RED)** - `937681f` (test)
2. **Task 2: Dictionary service, routes, pages + product-form autofill wiring (GREEN)** - `1d41675` (feat)

## Files Created/Modified
- `app/services/dictionary.py` - add_entry/update_entry/list_entries/lookup; shared strip+validation helper; plain session.commit(), no ledger
- `app/routes/dictionary.py` - GET /dictionary, GET /dictionary/lookup (204 pattern, PD-5 placement), POST /dictionary, POST /dictionary/{id} (rows-partial responses, 422 on errors)
- `app/templates/pages/dictionary.html` - h1 «Справочник», inline add row (autofocus code input, «Добавить код»), rows include
- `app/templates/partials/dictionary_rows.html` - #dictionary-rows swap target; empty-state hint; per-row inline edit via form= attribute association; «Сохранить код»
- `app/templates/partials/name_input.html` - div#name-wrap fragment: label + name input + autofill hint «Название подставлено из справочника — можно изменить.»
- `app/templates/pages/product_form.html` - name field replaced by the shared include; code input wired: hx-get lookup, delay:300ms, hx-include name, hx-target #name-wrap, hx-sync this:replace
- `app/templates/base.html` - nav gains «Справочник» → /dictionary with active-link styling
- `app/main.py` - dictionary router registered
- `tests/test_dictionary.py` - 13-test CAT-02 contract (6 service + 7 web)

## Decisions Made
- Inline row editing uses the HTML `form="edit-{id}"` attribute so code/name inputs in table cells associate with a per-row form button — avoids illegal nested `<form>` elements while keeping one form per row (htmx collects `form.elements`, which includes form-attribute-associated inputs)
- Update-route 404 detection keys off the service's `"entry"` error slot (unknown entry_id → HTTPException 404), keeping the service's tuple-return contract uniform with add_entry
- Edit-conflict echo: dictionary_rows.html re-fills the offending row from `error_form` when `error_entry_id` matches, so a failed inline edit does not silently revert the operator's typing

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reworded service docstring to keep the no-ledger grep gate clean**
- **Found during:** Task 2 (verification)
- **Issue:** The module docstring mentioned "record_operation" in prose, tripping the plan's gate `! grep -rn "record_operation" app/services/dictionary.py`
- **Fix:** Reworded the docstring to say the same thing without the literal string
- **Files modified:** app/services/dictionary.py
- **Verification:** Gate prints GATE-OK-dictionary-no-ledger; tests and ruff still green
- **Committed in:** 1d41675 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Cosmetic docstring wording only. No scope creep.

## Issues Encountered
None — plan executed as designed; both verification gates and the extra `#name-wrap appears exactly once in both form modes` acceptance check passed on the first full run after the docstring fix.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 2 fully green: all four plans (02-01..02-04) complete; CAT-01/CAT-02/CAT-03 requirements shipped
- Phase 3 receipt form can reuse `lookup()` and `partials/name_input.html` directly for RCP-02 autofill
- End-of-phase human check pending (workflow.human_verify_mode=end-of-phase): type a known code on /products/new → name fills after ~300ms with the hint; pre-typed names are never overwritten
- Standing blocker unchanged: no verified bulk source for the Oriflame dictionary — manual row-by-row entry is the locked v1 scope (Excel import deferred)

## Self-Check: PASSED

- All 6 created files + 3 modified files present on disk
- Task commits 937681f and 1d41675 present in git log
- `uv run pytest -q` → 70 passed; `uv run ruff check .` → clean; all 4 grep gates OK

---
*Phase: 02-catalog-dictionary-search*
*Completed: 2026-07-08*
