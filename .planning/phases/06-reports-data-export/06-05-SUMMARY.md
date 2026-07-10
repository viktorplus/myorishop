---
phase: 06-reports-data-export
plan: 05
subsystem: reports
tags: [fastapi, sqlalchemy, jinja2, htmx, reporting, writeoffs]

# Dependency graph
requires:
  - phase: 06-reports-data-export
    provides: "06-02: local_day_bounds_utc, _resolve_period, partials/period_filter.html, GET /reports landing page"
  - phase: 05-stock-operations-history
    provides: "WRITEOFF_REASONS reason_code allow-list (damaged/expired/lost/personal/gift/other) and the writeoff operation payload shape {reason_code, note}"
provides:
  - "app.services.reports.writeoff_report(session, start_iso, end_iso) -> dict — write-offs grouped by reason_code in WRITEOFF_REASONS' declared key order"
  - "GET /reports/writeoffs — period-filtered write-off report page"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Group-by-fixed-category report: iterate the allow-list constant's own key order (WRITEOFF_REASONS.items()), including a key only if present in the aggregated data — never sort by the aggregated dict's own insertion order"

key-files:
  created:
    - app/templates/pages/reports_writeoffs.html
    - app/templates/partials/writeoffs_report_rows.html
  modified:
    - app/services/reports.py
    - app/routes/reports.py
    - app/templates/pages/reports_landing.html
    - tests/test_reports.py

key-decisions:
  - "writeoff_report reuses _resolve_period + local_day_bounds_utc verbatim, unmodified, per plan objective — no new period-handling code anywhere in this plan"
  - "h2 «Списания по причинам» lives inside writeoffs_report_rows.html (the swapped partial), matching sales_report_results.html's exact structure (h2 inside the HX swap target) for consistency with Plan 06-02"

patterns-established: []

requirements-completed: [RPT-03]

# Metrics
duration: 15min
completed: 2026-07-10
---

# Phase 6 Plan 05: Write-off Report Summary

**GET /reports/writeoffs groups period write-offs by the exact Phase 5 WRITEOFF_REASONS categories, in their declared key order, reusing Plan 06-02's period filter and local-day boundary math unchanged.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-10 (session start)
- **Completed:** 2026-07-10T14:56:53Z
- **Tasks:** 2 completed
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `writeoff_report(session, start_iso, end_iso)` in `app/services/reports.py`: aggregates period write-offs by `reason_code`, iterating `WRITEOFF_REASONS.items()` in its own declared order (not insertion/discovery order) so the result list is stable across reports; a reason with zero write-offs in the period is omitted entirely.
- No `Product.deleted_at` filter (RESEARCH Pitfall 5, same rule as `sales_profit_report`) — a write-off on a product later soft-deleted still appears in a period report covering the time before deletion.
- `GET /reports/writeoffs` renders the same period-filter UX as `/reports/sales`, calling the exact same `_resolve_period` helper — no second date-parsing implementation.
- `/reports` landing page now links to `/reports/writeoffs`.

## Task Commits

Each task was committed atomically (TDD RED/GREEN for Task 1):

1. **Task 1: writeoff_report — RED** - `6d837ff` (test)
2. **Task 1: writeoff_report — GREEN** - `a9a4108` (feat)
3. **Task 2: GET /reports/writeoffs route, templates, landing-page link** - `fda80f9` (feat)

**Plan metadata:** committed alongside this SUMMARY (see final commit).

## Files Created/Modified
- `app/services/reports.py` - new `writeoff_report` function, imports `WRITEOFF_REASONS` and `defaultdict`
- `app/routes/reports.py` - new `GET /reports/writeoffs` route, reuses `_resolve_period`
- `app/templates/pages/reports_writeoffs.html` - new page: period filter + results div
- `app/templates/partials/writeoffs_report_rows.html` - new partial: error/empty/data three-way branch, Причина/Кол-во,шт. table
- `app/templates/pages/reports_landing.html` - added link to `/reports/writeoffs`
- `tests/test_reports.py` - 4 service-level tests (reason ordering, zero-reason exclusion, deleted-product inclusion, outside-period exclusion) + 4 web-level tests (grouping, empty state, HX partial-only, landing link)

## Decisions Made
- Followed the plan's exact instruction: `by_reason` built via `defaultdict(lambda: {"qty": 0, "lines": []})` keyed by `reason_code`, then the final ordered list iterates `WRITEOFF_REASONS.items()` and includes a reason only if present in `by_reason` — this is what makes ordering deterministic (WRITEOFF_REASONS' key order) instead of dict-insertion order.
- h2 inside the swapped partial (matching `sales_report_results.html`'s structure), per the plan's explicit instruction to prefer this over the alternative (h2 on the full page only) for cross-plan consistency.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Shortened one test function name over ruff's 100-char line-length limit**
- **Found during:** Task 1's `ruff check` verification step
- **Issue:** `test_writeoff_report_excludes_reason_with_zero_writeoffs_in_period` made the `def` line exceed 100 characters, which would fail `uv run ruff check`
- **Fix:** Renamed to `test_writeoff_report_excludes_reason_with_zero_writeoffs` (no behavior change)
- **Files modified:** tests/test_reports.py
- **Verification:** `uv run ruff check tests/test_reports.py` passes; `uv run pytest tests/test_reports.py -x -q -k writeoff` still green
- **Committed in:** `a9a4108` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 lint)
**Impact on plan:** Cosmetic test-name-length fix only; no behavior change. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- RPT-03 fully satisfied: period write-off reporting grouped by the Phase 5 reason categories, reusing Plan 06-02's period filter and boundary math verbatim.
- No blockers for downstream Phase 6 plans (06-06 top/stale products — independent of this plan's write-off service).

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Status |
|------|-----|-------|----------|--------|
| Task 1 (writeoff_report) | ✓ `6d837ff` | ✓ `a9a4108` | n/a | Pass |

Task 2 was `type="auto"` (no `tdd="true"`) — no RED/GREEN gate applies.

---
*Phase: 06-reports-data-export*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/templates/pages/reports_writeoffs.html
- FOUND: app/templates/partials/writeoffs_report_rows.html
- FOUND: app/services/reports.py contains writeoff_report
- FOUND: commit 6d837ff, a9a4108, fda80f9 all present in git log
- uv run pytest tests/test_reports.py -x -q: 25 passed
- uv run pytest (full suite): 209 passed
- uv run ruff check app/services/reports.py app/routes/reports.py app/templates tests/test_reports.py: All checks passed
