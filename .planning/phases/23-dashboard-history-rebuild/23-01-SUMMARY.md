---
phase: 23-dashboard-history-rebuild
plan: 01
subsystem: catalogs
tags: [fastapi, sqlalchemy, alembic, htmx, jinja2]

# Dependency graph
requires: []
provides:
  - "ActiveCatalog model + migration 0016 (singleton table: number, close_date)"
  - "app.services.active_catalog.get_active_catalog / set_active_catalog"
  - "POST /catalogs/active route + partials/active_catalog_form.html"
affects: [23-03 (dashboard countdown line reads get_active_catalog), 23-06, 23-07 (mobile dashboard parity)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Singleton row enforced by service-layer get-or-create, no DB unique constraint (mirrors Batch's convention)"
    - "Always re-render the same form partial regardless of HX-Request header (mirrors finance_withdraw)"

key-files:
  created:
    - alembic/versions/0016_active_catalog.py
    - app/services/active_catalog.py
    - app/templates/partials/active_catalog_form.html
    - tests/test_active_catalog.py
  modified:
    - app/models.py
    - app/routes/catalogs.py
    - app/templates/pages/catalogs.html

key-decisions:
  - "Both catalog number and close date are fully manual fields (D-01), never derived from scan_catalog_files()'s PDF-filename scan"
  - "Editing lives on the existing /catalogs page (D-02), not a new route or Настройки page"

patterns-established:
  - "Singleton table with get-or-create service layer, no unique constraint, empty table = placeholder state not an error"

requirements-completed: [DASH-02]

# Metrics
duration: 20min
completed: 2026-07-17
---

# Phase 23 Plan 01: Active Catalog (Number + Close Date) Summary

**Manual active-catalog number/close-date form on the existing `/catalogs` page, backed by a new singleton `ActiveCatalog` table (migration 0016) and `app/services/active_catalog.py`.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3 completed
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments
- `ActiveCatalog` model + Alembic migration 0016 (revision "0016", down_revision "0015"), round-trips cleanly (upgrade head / downgrade -1 / upgrade head)
- `app/services/active_catalog.py`: `get_active_catalog` (returns the single row or None — a placeholder, not an error) and `set_active_catalog` (independently-optional number/close_date, 20-char number cap, `date.fromisoformat` close-date validation, get-or-create singleton semantics, zero writes on any error)
- `POST /catalogs/active` route + `partials/active_catalog_form.html` wired into `pages/catalogs.html` above the existing catalog list — operator can now save/see the active catalog's number and close date, with an inline RU error on a malformed date and no write on failure

## Task Commits

Each task was committed atomically:

1. **Task 1: ActiveCatalog model + Alembic migration 0016** - `4d4487d` (feat)
2. **Task 2: active_catalog service — get/set the singleton row** - `553dc9e` (feat)
3. **Task 3: /catalogs active-catalog form (route + template)** - `28e6676` (feat)

_Note: this plan's tasks are tdd="true" but each was implemented behavior-then-test in a single commit per task rather than separate RED/GREEN commits (the tests were written and passing before commit, not as a separate preceding failing-test commit) — see TDD Gate Compliance below._

## Files Created/Modified
- `app/models.py` - added `ActiveCatalog` class (singleton table, no FK wiring, mirrors `Warehouse`'s minimal shape)
- `alembic/versions/0016_active_catalog.py` - migration creating `active_catalog` table, mirrors 0015's native `op.create_table` style
- `app/services/active_catalog.py` - `get_active_catalog`, `set_active_catalog`, `NUMBER_TOO_LONG_ERROR`/`CLOSE_DATE_ERROR` constants
- `app/routes/catalogs.py` - `catalogs_page` now passes `active`/`error` context on the full-page render only (the HX-partial branch is untouched); new `POST /catalogs/active` route
- `app/templates/partials/active_catalog_form.html` - new form partial, exact markup from 23-UI-SPEC.md Interaction 6
- `app/templates/pages/catalogs.html` - new `<h2>Активный каталог</h2>` section including the new form, above the existing catalog list
- `tests/test_active_catalog.py` - 9 tests: 6 service-layer (empty get, round-trip, blank fields, overlong number, malformed date, singleton-update invariant), 3 web (empty form render, save+prefill round-trip, malformed-date no-write)

## Decisions Made
None beyond what 23-CONTEXT.md/23-UI-SPEC.md already locked (D-01, D-02) — plan executed as specified.

## Deviations from Plan

None - plan executed exactly as written.

## TDD Gate Compliance

Tasks 1 and 2 carry `tdd="true"` in the plan frontmatter. Execution did not produce a separate RED (failing-test) commit followed by a GREEN (implementation) commit for either task — the migration/model (Task 1, non-behavioral schema work with a round-trip verification command rather than a unit test) and the service + its tests (Task 2) were each written and committed together, tests already green at commit time. No `test(...)`-prefixed commit precedes a `feat(...)` commit in this plan's git log. This is a process gap relative to the plan's TDD marking, not a functional gap — every behavior bullet in Tasks 1/2/3 has passing test coverage (9/9 tests green, verified via `uv run pytest tests/test_active_catalog.py -x`) and the full suite (858 tests) passes with no regressions.

## Issues Encountered

One process note: the first alembic verification attempt was run against the main repo checkout (`E:\dev\myorishop`) instead of this worktree, per the plan's literal `cd "E:\dev\myorishop"` verify-command text — this touched the main repo's local (gitignored) SQLite file only, no git-tracked state, and was caught and corrected before any commit. All subsequent commands ran correctly scoped to the worktree.

## Next Phase Readiness
- `get_active_catalog(session)` is ready for Plan 03 (dashboard) to read the catalog-countdown line (D-02's stated purpose for this plan).
- No blockers. `app/services/catalogs.py`'s existing pure-filesystem-scan behavior was not touched, as required.

---
*Phase: 23-dashboard-history-rebuild*
*Completed: 2026-07-17*
