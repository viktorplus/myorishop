---
phase: 14-list-pagination-filtering-sorting-quick-delete
plan: 01
subsystem: infra
tags: [pagination, jinja2, htmx, alembic, sqlite, cyrillic]

# Dependency graph
requires: []
provides:
  - "app/services/pagination.py: LIST_PAGE_SIZE (20), page_window(), paginate() — the shared page-number pagination foundation for all six list pages"
  - "app/templates/partials/pagination.html: copy-paste-ready pagination bar partial (Contract A)"
  - "Structural CSS: .pagination, .pagination .current-page, .filter-row th, .filter-row input/select"
  - "Dictionary.name_lc: Cyrillic-safe lowercase shadow column, live in schema and maintained by add_entry/update_entry"
affects: ["14-02", "14-03", "14-04", "14-05", "14-06", "14-07"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single page-size constant + page-window ellipsis algorithm imported by every list route, never re-implemented per list"
    - "Python-side _lc shadow-column backfill in Alembic migrations (never SQL lower()) — now established twice (products.name_lc in 0002, dictionary.name_lc in 0012)"

key-files:
  created:
    - app/services/pagination.py
    - tests/test_pagination.py
    - app/templates/partials/pagination.html
    - alembic/versions/0012_dictionary_name_lc.py
  modified:
    - app/static/style.css
    - app/models.py
    - app/services/dictionary.py
    - tests/test_dictionary.py

key-decisions:
  - "Followed the plan's TDD sequencing exactly: test commit then feat commit per task, mirroring migration 0002's frozen Python-side Cyrillic backfill pattern for migration 0012"

patterns-established:
  - "Every Wave 2 list plan (14-02..14-07) must import LIST_PAGE_SIZE/page_window/paginate from app.services.pagination and include partials/pagination.html unchanged — never hand-roll a second implementation"

requirements-completed: [LIST-01, LIST-02]

# Metrics
duration: 15min
completed: 2026-07-14
---

# Phase 14 Plan 01: Shared Pagination Foundation & Dictionary Cyrillic Shadow Column Summary

**Shared `app/services/pagination.py` (LIST_PAGE_SIZE=20, ellipsis-aware `page_window()`, clamping `paginate()`), a copy-paste-ready `partials/pagination.html` bar with 4 new structural CSS rules, and `Dictionary.name_lc` (migration 0012, Python-backfilled Cyrillic-safe) for Wave 2's six list pages to build on.**

## Performance

- **Duration:** 15 min
- **Completed:** 2026-07-14T02:46:51Z
- **Tasks:** 3 completed
- **Files modified:** 8

## Accomplishments
- `app/services/pagination.py` gives every future list route one constant (`LIST_PAGE_SIZE=20`) and one page-window/ellipsis algorithm — no list can drift into its own off-by-one pagination math
- `partials/pagination.html` + 4 new CSS rules (`.pagination`, `.pagination .current-page`, `.filter-row th`, `.filter-row input, .filter-row select`) implement UI-SPEC Contract A verbatim, reusing only existing color/spacing tokens
- `Dictionary.name_lc` shadow column (migration 0012) is live in the schema, backfilled in Python for existing rows, and kept in sync by `add_entry`/`update_entry` — unblocks Plan 14-03's dictionary name filter

## Task Commits

Each task was committed atomically (TDD: test then feat per task):

1. **Task 1: Shared pagination helper module** - `9be5196` (test) / `df0d732` (feat)
2. **Task 2: Shared pagination partial + structural CSS** - `05ff170` (feat, extends test_pagination.py in the same commit)
3. **Task 3: Dictionary.name_lc shadow column** - `379aaae` (test) / `424b747` (feat)

**Plan metadata:** commit pending (this SUMMARY + STATE/ROADMAP update)

_Note: TDD tasks have separate test → feat commits; Task 2 is `type="auto"` (no tdd flag) so its partial-render test and template landed in one commit._

## Files Created/Modified
- `app/services/pagination.py` - `LIST_PAGE_SIZE`, `page_window()`, `paginate()`
- `tests/test_pagination.py` - 8 tests covering all behavior-block cases + partial render
- `app/templates/partials/pagination.html` - shared pagination bar partial (Contract A)
- `app/static/style.css` - 4 new structural rules, no existing rule altered
- `app/models.py` - `Dictionary.name_lc: Mapped[str | None]` column
- `alembic/versions/0012_dictionary_name_lc.py` - adds + Python-backfills `dictionary.name_lc`, `down_revision = "0011"`
- `app/services/dictionary.py` - `add_entry`/`update_entry` now set `name_lc`
- `tests/test_dictionary.py` - migration 0012 test + `name_lc` assertions on create/update

## Decisions Made
None beyond the plan — executed as written, mirroring the frozen migration 0002 Python-backfill precedent exactly for migration 0012.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- One unrelated full-suite flake (`tests/test_reports.py::test_web_reports_writeoffs_hx_request_returns_partial_only` — `OSError: [WinError 10055]`, a Windows socket resource-exhaustion error from an unrelated live-server fixture, not touched by this plan). Confirmed pre-existing and environment-only: passes cleanly when re-run in isolation. No code change made (out of scope per Scope Boundary — `test_reports.py` is not among this plan's `files_modified`).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `app/services/pagination.py`, `partials/pagination.html`, and `Dictionary.name_lc` are ready for Wave 2 plans 14-02 through 14-07 to import/include/query directly — no re-implementation needed
- Full test suite: 517 passed (plus the one confirmed-flaky, confirmed-unrelated test above), zero regressions from this plan's changes
- `uv run alembic upgrade head` on a fresh temp DB confirmed to add `dictionary.name_lc` cleanly

---
*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Completed: 2026-07-14*

## Self-Check: PASSED

All 8 created/modified files found on disk; all 5 task commit hashes found in git log.
