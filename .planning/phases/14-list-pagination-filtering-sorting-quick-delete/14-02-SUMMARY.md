---
phase: 14-list-pagination-filtering-sorting-quick-delete
plan: 02
subsystem: ui
tags: [fastapi, sqlalchemy, htmx, jinja2, pagination, filtering, sorting]

# Dependency graph
requires:
  - phase: 14-01
    provides: "app/services/pagination.py (LIST_PAGE_SIZE=20, page_window()) and partials/pagination.html shared bar"
provides:
  - "history_view() total-count-based pagination (total/total_pages, no has_next) with a sort allow-list (_SORT_MAP)"
  - "/history migrated onto the shared #history-rows single-swappable-block shape: sort dropdown + header-row filters + shared pagination partial"
  - "history_load_more.html/history_response.html/history_filters.html retired (deleted)"
affects: [14-03, 14-04, 14-05, 14-06, 14-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "history_view() total-count query mirrors the row query's .where() clauses exactly, run separately (no .order_by/.limit/.offset) via func.count().select_from(Operation).join(Product, ...)"
    - "page clamped server-side into [0, total_pages - 1] before .offset() (T-14-04 confused-deputy mitigation)"
    - "sort resolved via a fixed _SORT_MAP.get(sort, default) allow-list dict, never string-interpolated into order_by() (T-14-03)"
    - "single swappable #history-rows div (sort .filter-bar + table with a filter-row <thead> <tr> + shared partials/pagination.html include) — same shape Contract A/B/C prescribe for every other list"

key-files:
  created: []
  modified:
    - app/services/operations.py
    - app/routes/history.py
    - app/templates/partials/history_rows.html
    - app/templates/pages/history.html
    - app/routes/mobile_history.py
    - tests/test_history.py

key-decisions:
  - "mobile_history.py (out of this plan's files_modified list) read history_view()'s has_next key removed by Task 1 — fixed by deriving has_next locally from total_pages rather than redesigning the mobile route, since mobile list revamp is out of this phase's desktop-only scope (Rule 1 auto-fix)"

patterns-established:
  - "Total-count sibling query pattern for list services: build the row-fetch stmt and a count_stmt together, apply identical .where() filters to both, compute total_pages before slicing/limiting the row stmt"

requirements-completed: [LIST-01, LIST-02, LIST-03]

# Metrics
duration: 19min
completed: 2026-07-14
---

# Phase 14 Plan 02: History List Pagination/Filtering/Sorting Migration Summary

**Migrated `/history`'s offset+has_next "Показать ещё" pagination onto the shared total-count page-number pagination bar, moved its type/product filters from a standalone `.filter-bar` into a header-row filter shape, and added a "Сортировать по" newest/oldest sort dropdown — all inside one swappable `#history-rows` block.**

## Performance

- **Duration:** 19 min
- **Started:** 2026-07-14T04:53Z (base commit d5dd77e)
- **Completed:** 2026-07-14T05:12Z
- **Tasks:** 2
- **Files modified:** 7 (3 deleted, 4 modified/rewritten)

## Accomplishments
- `history_view()` now returns `total`/`total_pages` (never `has_next`); page is always clamped server-side into `[0, total_pages - 1]`
- Added a fixed `_SORT_MAP` sort allow-list (`sort="oldest"` reverses to `created_at asc, seq asc`; default stays `created_at desc, seq desc`)
- `/history` renders one swappable `#history-rows` block: sort dropdown + a second `<tr class="filter-row">` header row carrying the type/product `<select>`s + the unchanged 10-column data table + the shared `partials/pagination.html` bar
- Retired `history_load_more.html`, `history_response.html`, and `history_filters.html` entirely — their content folded into the rewritten `history_rows.html`
- Default `page_size` moved from a hardcoded 50 to the shared `LIST_PAGE_SIZE` (20) constant from Plan 14-01

## Task Commits

Each task was committed atomically:

1. **Task 1: history_view() total-count + sort allow-list; route wiring** - `8a1ae6a` (feat)
2. **Task 2: Retire load-more/tfoot markup; header-row filters + sort dropdown + pagination partial** - `2301f45` (feat)

_No plan-metadata commit — worktree mode; orchestrator handles the final metadata commit after merge._

## Files Created/Modified
- `app/services/operations.py` - `history_view()` gains `sort` param, `_SORT_MAP` allow-list, and a total-count sibling query; returns `total`/`total_pages` instead of `has_next`; default `page_size` now `LIST_PAGE_SIZE`
- `app/routes/history.py` - `history_page()` gains a `sort` query param, computes `page_window`/`extra_qs`, and renders `partials/history_rows.html` for both the `is_hx` and full-page branches (full page wraps it via `pages/history.html`)
- `app/templates/partials/history_rows.html` - rewritten as `<div id="history-rows">` wrapping the sort `.filter-bar`, the `<table>` with a new `.filter-row` `<thead>` `<tr>`, the unchanged row-rendering loop, and an include of `partials/pagination.html`
- `app/templates/pages/history.html` - now just `{% include "partials/history_rows.html" %}` + `#return-slot`, dropped its own `<table>`/`<thead>`/`<tfoot>`/filter-bar include
- `app/templates/partials/history_load_more.html` - deleted (tfoot/oob load-more mechanism retired)
- `app/templates/partials/history_response.html` - deleted (combined-response oob wrapper retired)
- `app/templates/partials/history_filters.html` - deleted (type/product selects moved into the new filter-row)
- `app/routes/mobile_history.py` - Rule 1 fix: derives `has_next` locally from `total_pages` instead of reading the now-removed `has_next` key (mobile history page is out of this phase's scope)
- `tests/test_history.py` - `test_history_pagination` asserts `total`/`total_pages` (no `has_next`); new `test_history_view_sort_oldest_first`; replaced the retired tfoot-survival regression test with `test_web_history_pagination_bar_reflects_filtered_total`; updated `test_web_history_table_has_10_columns` for the new 2-row `<thead>` (20 `<th>`, 2 `<select>`)

## Decisions Made
- Kept the row-rendering markup and empty-state RU copy completely unchanged per the plan's explicit "unchanged" instruction, even though `14-UI-SPEC.md`'s generic copywriting contract proposes a different filtered-to-zero-rows string — the plan's Task 2 action text is authoritative for this migration ("the EXACT existing row-rendering Jinja logic ... unchanged").
- `count_stmt` mirrors the row stmt's `.join(Product, ...)` even though neither active filter (`type`/`product_id`) touches a `Product` column, per the plan's explicit instruction — keeps the two queries structurally identical so a future filter added to either stays trivially in sync.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] mobile_history.py broke on history_view()'s has_next removal**
- **Found during:** Task 1 verification (full test suite run before Task 2 commit)
- **Issue:** `app/routes/mobile_history.py` (not in this plan's `files_modified` list) reads `result["has_next"]` from `history_view()`'s return dict; Task 1 removed that key entirely, causing a `KeyError` on every `/m/history` request and cascading test failures in `tests/test_mobile_history.py` (5 tests) and `tests/test_mobile_wiring.py` (1 test).
- **Fix:** Derive the equivalent `has_next` locally in the route (`result["page"] < result["total_pages"] - 1`) rather than redesigning the mobile history page's load-more UI — mobile list pagination/filtering is out of this phase's scope (desktop-only per `14-CONTEXT.md`).
- **Files modified:** `app/routes/mobile_history.py`
- **Verification:** `uv run pytest tests/test_mobile_history.py tests/test_mobile_wiring.py tests/test_history.py -x` — 23 passed; full suite subsequently green (519 passed)
- **Committed in:** `2301f45` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug/regression fix)
**Impact on plan:** Necessary to avoid shipping a regression in an out-of-scope but directly-affected consumer of `history_view()`. No scope creep — mobile history's UI/behavior is unchanged, only its internal has_next computation moved.

## Issues Encountered
None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `/history` fully migrated onto the shared pagination/filter-row/sort-dropdown shape established by Plan 14-01; a working end-to-end reference implementation now exists for the remaining list pages (products, warehouses, customers, dictionary, catalogs) in later plans of this phase.
- Full test suite green (519 passed) after this plan, including the previously-unlisted `mobile_history.py`/`test_mobile_history.py`/`test_mobile_wiring.py` fix.
- No blockers for subsequent plans in Phase 14.

---
*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Completed: 2026-07-14*
