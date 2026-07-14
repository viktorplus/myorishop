---
phase: 14-list-pagination-filtering-sorting-quick-delete
plan: 03
subsystem: ui
tags: [fastapi, sqlalchemy, jinja2, htmx, pagination, filtering, sorting]

requires:
  - phase: 14-01
    provides: LIST_PAGE_SIZE/page_window/paginate helpers, partials/pagination.html, Dictionary.name_lc shadow column
provides:
  - "list_entries() as SQL-side filtered/sorted/paginated query (LIMIT/OFFSET + matching COUNT)"
  - "/dictionary header-row code/name filters, sort dropdown, numbered pagination"
affects: [14-list-pagination-filtering-sorting-quick-delete]

tech-stack:
  added: []
  patterns:
    - "SQL-side list pagination (LIMIT/OFFSET + func.count() with the SAME .where() clauses) for the largest table in the app, mirroring app/services/operations.py's history_view shape"
    - "Fixed sort allow-list dict (_SORT_MAP) resolved via .get(sort, default) — never string-interpolated into order_by()"
    - "Shared route-level _dictionary_context() helper reused by GET and both POST handlers to avoid context-shape drift"

key-files:
  created: []
  modified:
    - app/services/dictionary.py
    - app/routes/dictionary.py
    - app/templates/partials/dictionary_rows.html
    - tests/test_dictionary.py

key-decisions:
  - "list_entries() return type changed from list[Dictionary] to a dict (entries/total/total_pages/page/code/name/sort) — all three call sites in app/routes/dictionary.py updated in the same commit"
  - "Writes (add/update) reset filter/sort/page to defaults on their re-render, matching the existing warehouse/product post-write precedent"

patterns-established:
  - "Dictionary is the only list (besides history) large enough to need SQL-side pagination rather than Python-side paginate() from app/services/pagination.py"

requirements-completed: [LIST-01, LIST-02, LIST-03]

duration: 25min
completed: 2026-07-14
---

# Phase 14 Plan 03: Dictionary Pagination, Filtering & Sorting Summary

**`list_entries()` rewritten as an SQL LIMIT/OFFSET + COUNT query with Cyrillic-safe name filtering and allow-listed sort, plus header-row code/name filters and a sort dropdown wired into `/dictionary` via the shared `pagination.html` partial.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-14T03:11:44Z
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- `list_entries(session, *, code="", name="", sort="", page=0) -> dict` replaces the unbounded `SELECT * ORDER BY code` (6,856 rows) with a filtered/sorted/paginated SQL query and a matching `func.count()` total, clamping out-of-range pages instead of raising.
- `/dictionary` gained an `is_hx` dual-response branch (full page vs. `partials/dictionary_rows.html` fragment) and a shared `_dictionary_context()` helper so GET and both POST handlers build an identical context shape.
- `partials/dictionary_rows.html` now renders a `Сортировать по` dropdown (`Код (по возрастанию) (по умолчанию)` / `Название (А→Я)`), a `.filter-row` with debounced (300ms) code/name inputs, and includes `partials/pagination.html` — plus a distinct "filtered to zero" empty-state message.

## Task Commits

Each task was committed atomically (Task 1 is a TDD task: RED then GREEN):

1. **Task 1: list_entries() SQL-side filter/sort/page + route wiring**
   - `07759a2` (test) - failing tests for filter/name-Cyrillic/sort/paginate-clamp behavior
   - `4790bc8` (feat) - SQL-side `list_entries()` + `_dictionary_context()` route wiring
2. **Task 2: Header-row filters + sort dropdown + pagination partial for /dictionary** - `960c5b2` (feat)

## Files Created/Modified
- `app/services/dictionary.py` - `list_entries()` rewritten to SQL LIMIT/OFFSET + COUNT with `_SORT_MAP` allow-list, code substring filter (`func.lower(Dictionary.code).contains(...)`), Cyrillic-safe name filter (`Dictionary.name_lc.contains(..., autoescape=True)`)
- `app/routes/dictionary.py` - new `_dictionary_context()` helper; `dictionary_page()` gains `code`/`name`/`sort`/`page` query params and an `is_hx` branch; `dictionary_add`/`dictionary_update` reset filter/sort/page on write
- `app/templates/partials/dictionary_rows.html` - `.filter-bar` sort select, `.filter-row` th inputs, `{% include "partials/pagination.html" %}`, filtered-empty vs. true-empty state branching
- `tests/test_dictionary.py` - updated existing `list_entries(session)["entries"]` call; added 4 service tests (code substring, name Cyrillic-safe, sort-by-name, paginate/clamp) and 4 web tests (filter-by-code, sort-by-name, pagination bar, filtered-to-zero empty message)

## Decisions Made
- `list_entries()`'s dict return shape (`entries`/`total`/`total_pages`/`page`/`code`/`name`/`sort`) exactly matches the plan's `must_haves` — no deviation from the specified contract.
- `_dictionary_context()` lives in `app/routes/dictionary.py` (route-local helper), not the service module, per the plan's explicit instruction — it composes `list_entries()` with `page_window()`/`extra_qs` which are route/template concerns, not domain logic.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/dictionary` (6,856 rows) is now bounded to 20 rows/request with server-side filter/sort/page — the largest unbounded-list risk in Phase 14 is resolved.
- Full test suite (526 tests) passes; `tests/test_dictionary.py` (24 tests) covers both the service-level SQL contract and the web-level rendering contract.
- Pattern established here (SQL-side pagination + `_SORT_MAP` allow-list + shared `_context()` route helper) is directly reusable by 14-04 through 14-07 for the remaining lists in this phase.

---
*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Completed: 2026-07-14*
