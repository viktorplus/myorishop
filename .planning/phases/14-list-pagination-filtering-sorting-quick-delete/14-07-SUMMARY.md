---
phase: 14-list-pagination-filtering-sorting-quick-delete
plan: 07
subsystem: ui
tags: [jinja2, htmx, pagination, filtering, sorting, catalogs]

# Dependency graph
requires:
  - phase: 14-01
    provides: "app/services/pagination.py (LIST_PAGE_SIZE, page_window, paginate), partials/pagination.html, .filter-row CSS"
provides:
  - "list_catalogs(session, *, year, sort, page) -> dict with catalogs/total/total_pages/page/year/sort"
  - "catalog_year_options(session) -> list[int], distinct years on disk sorted descending"
  - "partials/catalog_rows.html: extracted, swappable #catalog-rows block with header-row filter/sort bar + paginated year-grouping + pagination"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pagination-before-grouping: list_catalogs() slices the flat sorted list BEFORE the caller's per-year <table> grouping loop runs, so loop.first/loop.last open/close correctly per PAGE instead of per full list (Pitfall 5)"
    - "Synthetic single-row <table><thead><tr class=\"filter-row\"> hosts non-per-column filter/sort controls when a list has no single shared <thead> across the page (catalogs groups rows into one <table> per year) — self-balanced, does not perturb <table>/</table> tag-count checks"

key-files:
  created:
    - app/templates/partials/catalog_rows.html
  modified:
    - app/services/catalogs.py
    - app/routes/catalogs.py
    - app/templates/pages/catalogs.html
    - tests/test_catalogs_feature.py

key-decisions:
  - "Followed the plan exactly: year filter defensively parsed via .isdigit() (never raises on garbage input), sort='oldest' as the only allow-listed non-default value, pagination happens inside the service before any template grouping."

patterns-established:
  - "Pagination-before-grouping for any list that visually groups rows across multiple <table> elements"

requirements-completed: [LIST-01, LIST-02, LIST-03]

# Metrics
duration: 18min
completed: 2026-07-14
---

# Phase 14 Plan 07: Catalogs Pagination, Year Filter & Sort Summary

**`/catalogs` gained year filtering, newest/oldest sorting, and page-number pagination by pre-slicing the flat catalog list inside `list_catalogs()` before the existing per-year `<table>` grouping loop (now extracted into `partials/catalog_rows.html`) ever sees it — so a 20-row page boundary falling mid-year never leaves an unclosed `</table>`.**

## Performance

- **Duration:** 18 min
- **Completed:** 2026-07-14T (session)
- **Tasks:** 2 completed
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `list_catalogs()` now filters by year (defensive `.isdigit()` parse, never raises), sorts oldest/newest via a fixed allow-list, and paginates the FLAT sorted list before any year-grouping happens — the SAME 20/5 split regardless of how years distribute across the page boundary
- New `catalog_year_options()` always reflects every year on disk, independent of the active filter
- `/catalogs` now serves both a full-page response and an HTMX-partial response (`partials/catalog_rows.html`) via an `is_hx` branch, matching the established `history_page` pattern
- New `partials/catalog_rows.html` wraps a synthetic single-row `<thead><tr class="filter-row">` bar (year select + sort select) — D-04/Contract B compliant, NOT a `.filter-bar` div — above the year-grouped tables (moved verbatim from `pages/catalogs.html`) and the shared pagination bar
- `pages/catalogs.html` reduced to a single `{% extends %}` + `{% include %}` of the new partial

## Task Commits

Each task was committed atomically:

1. **Task 1: list_catalogs() year filter + sort + pre-grouping pagination; route wiring** - `b566025` (feat)
2. **Task 2: Extract catalog_rows.html partial** - `f8b83bf` (feat)

**Plan metadata:** this SUMMARY commit (worktree mode — orchestrator applies STATE.md/ROADMAP.md updates after merge)

## Files Created/Modified
- `app/services/catalogs.py` - `list_catalogs()` signature changed to accept `year`/`sort`/`page` and return a dict (`catalogs`, `total`, `total_pages`, `page`, `year`, `sort`); new `catalog_year_options()`
- `app/routes/catalogs.py` - `catalogs_page()` gains `year`/`sort`/`page` query params, an `is_hx` branch, and a shared `_catalogs_context()` helper (`page_window`, `extra_qs` from non-empty filter/sort state)
- `app/templates/partials/catalog_rows.html` (NEW) - synthetic filter/sort header-row bar + paginated year-grouping table loop (moved verbatim from the page template) + `{% include "partials/pagination.html" %}`, all wrapped in `#catalog-rows`
- `app/templates/pages/catalogs.html` - reduced to `{% extends %}` + `{% include "partials/catalog_rows.html" %}`
- `tests/test_catalogs_feature.py` - 8 new tests: 4 service-level (year filter, oldest sort, flat-list pagination before grouping, year-options completeness) + 4 route-level (pagination total shown, year filter narrows results, filter lives in `.filter-row` not `.filter-bar`, `<table>`/`</table>` tags balanced on a paginated page with a mid-year page boundary)

## Decisions Made
None beyond the plan — executed as written, matching the shared `_catalogs_context()` helper shape and pagination-before-grouping approach specified in the plan action text.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `/catalogs` now matches the established filter/sort/pagination shape used by other Wave 2 list plans (14-02..14-06), all consuming the same `app/services/pagination.py` foundation from 14-01
- Full test suite: 526 passed, 0 failures, 0 regressions from this plan's changes
- `LIST-01`/`LIST-02`/`LIST-03` requirement IDs marked complete via `gsd-tools query requirements.mark-complete` (LIST-01/LIST-02 were already complete from earlier Wave 2 plans; LIST-03 newly completed by this plan)

---
*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Completed: 2026-07-14*

## Self-Check: PASSED

All 5 created/modified files found on disk; both task commit hashes (`b566025`, `f8b83bf`) found in git log.
