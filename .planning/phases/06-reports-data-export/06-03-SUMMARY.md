---
phase: 06-reports-data-export
plan: 03
subsystem: reports
tags: [fastapi, sqlalchemy, jinja2, reporting, stock]

# Dependency graph
requires:
  - phase: 06-reports-data-export
    provides: "06-01: Product.low_stock_threshold/Settings.low_stock_threshold fields; 06-02: shared reports router/templates scaffold, GET /reports landing page"
provides:
  - "app.services.stock.effective_low_stock_threshold(product) -> int — explicit is-not-None fallback (Pitfall 3 safe)"
  - "app.services.stock.low_stock_products(session) -> list[Product] — active products at/below effective threshold, sorted by quantity ascending"
  - "app.services.stock.all_active_products(session) -> list[Product] — active products ordered by name_lc"
  - "GET /reports/stock — current-stock view with distinct low-stock action list, no period filter"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Explicit 'is not None' fallback check for nullable per-entity override + global default (never bare 'or', which would treat 0 as falsy)"
    - "No-period-filter report pages render the full page only (no HX-Request branching) since there is no filter to re-apply in place"

key-files:
  created:
    - app/services/stock.py
    - app/templates/pages/reports_stock.html
  modified:
    - app/routes/reports.py
    - app/templates/pages/reports_landing.html
    - tests/test_reports.py

key-decisions:
  - "Followed plan's exact instruction: low_stock_products fetches active products via select+where(deleted_at IS NULL), filters in Python (no ORDER BY in the query), then Python-sorts by quantity ascending"
  - "low_stock_rows built as list of {product, threshold} dicts in the route so the low-stock table can show the effective threshold if ever needed; full-stock table stays a plain Product list per UI-SPEC's column list (no threshold column there)"
  - "low_stock_ids (a set of product ids) threaded into the template context so the full-stock table's Статус cell can show 'Мало' without re-deriving threshold logic in Jinja"

requirements-completed: [RPT-02]

# Metrics
duration: 15min
completed: 2026-07-10
---

# Phase 06 Plan 03: Stock & Low-Stock Report Summary

**GET /reports/stock with a Pitfall-3-safe effective-threshold low-stock action list (explicit 0 never falls back to global default) plus the full active-product stock table.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-10T14:20:00Z (approx)
- **Completed:** 2026-07-10T14:36:13Z
- **Tasks:** 2 completed
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `app/services/stock.py`: `effective_low_stock_threshold`, `low_stock_products`, `all_active_products` — the effective-threshold fallback uses an explicit `is not None` check, never a bare `or`, so a product with `low_stock_threshold=0` is correctly included in the low-stock list only at exactly zero stock.
- `GET /reports/stock` renders the low-stock action list first (Код/Название/Остаток/Статус, `Статус` shown as plain "Мало" text with no color coding, per UI-SPEC) and the full active-product stock table below it, with an empty-state message when nothing is low.
- `/reports` landing page now links to `/reports/stock` from the same `<p>` as the sales-report link.

## Task Commits

Each task was committed atomically (TDD RED/GREEN for Task 1):

1. **Task 1: stock.py — RED** - `9d0b97c` (test)
2. **Task 1: stock.py — GREEN** - `e98e767` (feat)
3. **Task 2: GET /reports/stock route, template, landing-page link** - `67c935c` (feat)

**Plan metadata:** committed alongside this SUMMARY (see final commit).

## Files Created/Modified
- `app/services/stock.py` - `effective_low_stock_threshold`, `low_stock_products`, `all_active_products`
- `app/routes/reports.py` - new `GET /reports/stock` route, imports from `app.services.stock`
- `app/templates/pages/reports_stock.html` - new template: low-stock action list + full stock table
- `app/templates/pages/reports_landing.html` - added link to `/reports/stock`
- `tests/test_reports.py` - 5 service-level tests (Pitfall 3 zero-threshold, global fallback, deleted exclusion x2, sort order) + 3 web-level tests

## Decisions Made
- No new CSS needed — reused `table`/`th`/`td`/`.num`/`.empty-state`/`.muted` verbatim, per UI-SPEC's "reuse before adding" convention.
- "Все товары" chosen as the full-table section heading (UI-SPEC left this heading to Claude's discretion since only "Мало на складе" has a mandated exact string).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `uv run ruff check app/templates/pages/reports_stock.html` reports ~174 "invalid-syntax" errors when the `.html` file is passed directly on the command line — confirmed via the same pre-existing behavior documented in 06-01-SUMMARY.md (ruff attempts to parse Jinja templates as Python when given an explicit path). Not a regression: all `.py` files (`app/services/stock.py`, `app/routes/reports.py`) pass `ruff check` cleanly, and the full test suite (193 tests) passes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- RPT-02 fully satisfied: current-stock view plus a correctly-filtered, correctly-sorted low-stock action list honoring per-product overrides down to an explicit 0.
- No blockers for downstream Phase 6 plans (06-05 write-offs report, 06-06 stale products — neither depends on this plan's stock service).

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Status |
|------|-----|-------|----------|--------|
| Task 1 (stock.py effective threshold + reads) | ✓ `9d0b97c` | ✓ `e98e767` | n/a | Pass |

Task 2 was `type="auto"` (no `tdd="true"`) — no RED/GREEN gate applies.

---
*Phase: 06-reports-data-export*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/services/stock.py
- FOUND: app/templates/pages/reports_stock.html
- FOUND: commit 9d0b97c, e98e767, 67c935c all present in git log
- uv run pytest tests/test_reports.py -x -q: 17 passed
- uv run pytest (full suite): 193 passed
- uv run ruff check app/services/stock.py app/routes/reports.py: All checks passed
