---
phase: 10-warehouse-transfers-expiry-reporting
plan: 03
subsystem: reports
tags: [fastapi, sqlalchemy, jinja2, htmx, reports]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration
    provides: Batch model (expiry, quantity, price_cents, comment, location), open_batches() query idiom, ru_date/cents Jinja filters
provides:
  - "expiring_batches(session) read helper in app/services/batches.py"
  - "GET /reports/expiry read-only report page"
  - "Сроки годности link on the reports landing page"
affects: [phase-11-mobile-flow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only report route mirrors reports_stock_page (no period/warehouse filter, full-page GET only)"
    - "Local-date (settings.display_tz) computed at the route, never UTC, for date-vs-today comparisons"

key-files:
  created:
    - app/templates/pages/reports_expiry.html
  modified:
    - app/services/batches.py
    - app/routes/reports.py
    - app/templates/pages/reports_landing.html
    - tests/test_batches.py
    - tests/test_reports.py

key-decisions:
  - "expiring_batches() lives beside open_batches() in the existing read-only batches.py module rather than a new file, per 10-PATTERNS.md discretion note"
  - "No nullslast needed for expiring_batches — is_not(None) already excludes NULL-expiry legacy batches, unlike open_batches which must still show them"

patterns-established:
  - "Expiry report is a pure read feature: one query helper, one route, one template, one landing link — no inline actions, no filters (D-07/D-08)"

requirements-completed: [LOT-06]

# Metrics
duration: ~15min
completed: 2026-07-12
---

# Phase 10 Plan 03: Expiry Report Summary

**Read-only `/reports/expiry` page listing open batches with a set expiry, earliest first, with a local-date «просрочено» marker for already-expired batches**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-12T18:11:13Z
- **Tasks:** 2 completed
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `expiring_batches(session)` read helper: open batches (quantity > 0) with a non-NULL expiry, joined to Product + Warehouse, earliest expiry first — legacy/NULL-expiry batches excluded automatically by `is_not(None)`.
- `GET /reports/expiry` renders the full report page mirroring `/reports/stock` (no period/warehouse filter), computing `today` from `settings.display_tz` (operator's local date, not UTC) so the expired marker is never mis-flagged near midnight.
- Reports landing page links to the new report under the existing «Отчёты» nav.

## Task Commits

Each task followed the RED → GREEN TDD gate:

1. **Task 1: expiring_batches() read helper + tests**
   - `0a28ec6` test(10-03): add failing test for expiring_batches
   - `91da2a7` feat(10-03): add expiring_batches read helper
2. **Task 2: /reports/expiry route + page template + landing link + route test**
   - `795c3d0` test(10-03): add failing test for GET /reports/expiry
   - `7d24e2b` feat(10-03): add GET /reports/expiry read-only page

_Plan metadata commit made separately per worktree protocol (SUMMARY.md only; STATE.md/ROADMAP.md owned by the orchestrator)._

## TDD Gate Compliance

Both tasks confirmed RED (import error / 404 respectively) before GREEN (passing). No skipped gates.

## Files Created/Modified
- `app/services/batches.py` - added `expiring_batches(session)` beside `open_batches()`; imports `Product`
- `app/routes/reports.py` - added `reports_expiry_page` GET handler + `expiring_batches` import
- `app/templates/pages/reports_expiry.html` (NEW) - read-only table: Код/Название/Склад/Срок годности/Остаток/Цена/Комментарий, «просрочено» marker, muted empty state
- `app/templates/pages/reports_landing.html` - added «Сроки годности» link
- `tests/test_batches.py` - `test_expiring_batches_filter_and_order`
- `tests/test_reports.py` - `test_expiry_report_page`, `test_expiry_report_page_empty_state`

## Decisions Made
- Followed 10-PATTERNS.md exactly: `expiring_batches()` in the existing `batches.py` module (not a new file), route/template mirror `reports_stock_page`/`reports_stock.html` verbatim in structure.
- No Alembic migration needed (no schema change this plan).

## Deviations from Plan

None - plan executed exactly as written. One extra test (`test_expiry_report_page_empty_state`) was added beyond the plan's single named test, to explicitly cover the empty-state acceptance criterion mentioned in the plan's `must_haves.truths` — this is additional test coverage for an already-specified behavior, not a scope change.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- LOT-06 delivered; ROADMAP criterion 3 (expiry report) satisfied.
- Full test suite green (341 passed) and `ruff check` clean on both touched service/route files.
- Human verification (human_verify_mode=end-of-phase, per plan's `<verification>` section) still pending: open `/reports`, follow «Сроки годности», confirm earliest-first ordering, «просрочено» marker on a past-expiry batch, and legacy batches absent. Deferred to end-of-phase per project config, not a blocker for this plan.
- No blockers for Plan 10-01 (transfers) — this plan touched no shared files with the transfer plan (parallel wave, no conflicts).

---
*Phase: 10-warehouse-transfers-expiry-reporting*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created/modified files verified present on disk; all 5 task/metadata commit hashes (0a28ec6, 91da2a7, 795c3d0, 7d24e2b, 7d7d4db) verified in git log.
