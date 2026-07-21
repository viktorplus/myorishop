---
phase: quick/260720-wqc-rubric
plan: 01
subsystem: ui
tags: [fastapi, jinja2, htmx, dictionary, catalog]

# Dependency graph
requires:
  - phase: 260714-2w6-update-dictionary-pricelist
    provides: Dictionary.rubric column populated by CAT-06 import/classification
provides:
  - Read-only Категория column on /dictionary showing Dictionary.rubric
  - Product.category autofill from Dictionary.rubric on the product form's code lookup
affects: [dictionary, product_form, catalog]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Independent per-field autofill: each field's 'fill only if empty' decision (Pitfall 5) is computed separately, not gated on a single field"
    - "OOB fragment composition: a route can render a wrapper partial that includes an existing swap-target fragment (name-wrap) plus an additional hx-swap-oob fragment, without touching the shared included partial"

key-files:
  created:
    - app/templates/partials/dictionary_lookup.html
  modified:
    - app/templates/partials/dictionary_rows.html
    - app/routes/dictionary.py
    - app/templates/pages/product_form.html
    - tests/test_dictionary.py

key-decisions:
  - "fill_name and fill_category computed independently in dictionary_lookup route — category can autofill even when name is already set, and vice versa"
  - "204 no-op contract preserved: response is empty only when neither field would fill (unknown code, or both name and category already non-empty)"
  - "name_input.html left untouched — dictionary_lookup.html only wraps it, keeping the /receipts/lookup route's reuse of the same fragment unaffected (PD-6)"

patterns-established:
  - "Pitfall 5 (never overwrite operator input) applied per-field, not per-request, when a lookup response can fill multiple independent fields"

requirements-completed: []

# Metrics
duration: ~15min
completed: 2026-07-21
---

# Quick Task 260720-wqc-rubric Summary

**Dictionary rubric (CAT-06) surfaced as a read-only /dictionary column and wired into the product form's code-lookup as an independent Категория autofill, mirroring the existing Название autofill's never-overwrite rule.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 2 completed
- **Files modified:** 4 modified, 1 created

## Accomplishments
- /dictionary list now renders a 4th "Категория" column (Dictionary.rubric or em dash "—"), display-only — no filter, no sort.
- The product form's debounced code lookup now also autofills Категория from the matched entry's rubric, independently of the existing Название autofill, and never overwrites an operator-entered category.

## Task Commits

Each task was committed atomically:

1. **Task 1: Show read-only Категория column on the /dictionary list** - `b14fbaf` (feat)
2. **Task 2: Autofill Product.category from Dictionary.rubric on the product form** - `3c0afc1` (test, RED) then `5faf403` (feat, GREEN)

_TDD task 2 followed RED -> GREEN: 3c0afc1 added the three new failing tests plus the updated hx-include assertion; 5faf403 made them pass. No REFACTOR commit was needed._

## Files Created/Modified
- `app/templates/partials/dictionary_rows.html` - adds the read-only Категория `<td>`/header cell, no filter/sort control
- `app/routes/dictionary.py` - `dictionary_lookup` gains a `category` query param, computes `fill_name`/`fill_category` independently, renders the new combined partial
- `app/templates/partials/dictionary_lookup.html` (new) - thin wrapper: includes `name_input.html` unchanged, adds an OOB `#category` input only when `fill_category` is true
- `app/templates/pages/product_form.html` - `#code`'s `hx-include` widened from `[name='name']` to `[name='name'], [name='category']`
- `tests/test_dictionary.py` - `test_web_dictionary_shows_rubric_column` (Task 1); `test_web_lookup_fills_category_when_empty`, `test_web_lookup_fills_category_only_when_name_already_present`, `test_web_lookup_does_not_overwrite_existing_category` (Task 2); updated `test_web_product_form_wired_for_autofill` for the new hx-include value

## Decisions Made
- Category fill decision (`fill_category = bool(entry.rubric) and not category.strip()`) is fully independent of the name fill decision — matches the plan's explicit requirement that the two fields autofill independently.
- When neither field would fill, the route still returns `204` (contract preserved byte-for-byte for the two existing "no-op" tests).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- No blockers. The change is additive and purely UI-level; no schema/migration changes were needed since Dictionary.rubric already existed (CAT-06, populated by the earlier 260714-2w6 import).
- Full project test suite run twice after implementation: 1156 passed, 12 skipped, 0 failures both times.

## TDD Gate Compliance

Task 2 (tdd="true") gate sequence verified in git log:
- RED: `3c0afc1` `test(quick-260720-wqc): add failing tests for category autofill from rubric` — confirmed failing before implementation (3 failures: the widened hx-include assertion + 2 new category-fill tests; a 3rd new test happened to pass trivially since the OOB fragment did not yet exist).
- GREEN: `5faf403` `feat(quick-260720-wqc): autofill Product.category from Dictionary.rubric` — all 28 tests in tests/test_dictionary.py pass.
- REFACTOR: not needed, no commit.

---
*Quick task: 260720-wqc-rubric*
*Completed: 2026-07-21*

## Self-Check: PASSED

All created/modified files present on disk; all 3 task commits (b14fbaf, 3c0afc1, 5faf403) found in git log.
