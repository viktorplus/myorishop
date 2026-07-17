---
phase: 23-dashboard-history-rebuild
plan: 03
subsystem: reporting
tags: [sqlalchemy, dashboard, aggregation, fastapi]

# Dependency graph
requires:
  - phase: 23-dashboard-history-rebuild
    provides: "Plan 01's app/services/active_catalog.py (get_active_catalog, ActiveCatalog model)"
provides:
  - "app.services.dashboard.dashboard_context(session, tz_name) — the single composer call Главная needs"
  - "dashboard_now/catalog_status/period_metrics/dashboard_metrics/stock_summary/recent_operations building blocks"
affects: [23-06-desktop-home-route, 23-07-mobile-home-route]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-09 generalization: single-purpose service shapes (finance.py::_metrics_context, sales.py::recent_sales) generalized to N-period / N-type composition rather than duplicated"
    - "Monkeypatch dashboard.datetime (module attribute) to freeze 'now' in tests, mirroring the utcnow_iso monkeypatch pattern used elsewhere in the suite"

key-files:
  created:
    - app/services/dashboard.py
    - tests/test_dashboard.py
  modified: []

key-decisions:
  - "period_metrics/dashboard_metrics replicate _resolve_period's Monday-start-week/calendar-month boundary formulas locally rather than importing app.routes.reports (services never import routes in this codebase)"
  - "recent_operations widens recent_sales's exact double-outerjoin shape (Sale, Customer both stay outer) to all 6 STOCK_AFFECTING_TYPES instead of writing a new query shape"
  - "stock_summary's product_count is a single SQL count() aggregation (never a Python loop), the one genuinely new aggregation this plan adds"

patterns-established:
  - "Dashboard composer pattern: dashboard_context(session, tz_name) is the one call routes make; every sub-function is independently testable and reusable"

requirements-completed: [DASH-01, DASH-03, DASH-04, DASH-05]

# Metrics
duration: ~45min
completed: 2026-07-17
---

# Phase 23 Plan 03: Dashboard Service Layer Summary

**`app/services/dashboard.py` composing date/weekday/time, catalog countdown, 3-period revenue/net-profit/expense, stock valuation + distinct-code count, and a 10-row 6-type recent-operations feed into one `dashboard_context()` call — zero ledger writes, fully unit-tested in isolation.**

## Performance

- **Duration:** ~45 min
- **Completed:** 2026-07-17
- **Tasks:** 2
- **Files modified:** 2 (both created: app/services/dashboard.py, tests/test_dashboard.py)

## Accomplishments

- `dashboard_now`, `catalog_status`, `period_metrics`, `dashboard_metrics` — DASH-01/02/03, with an explicit regression test proving net profit is `gross + expense` (addition), never a subtraction (D-08), and that week/month boundaries are byte-for-byte identical to `app/routes/reports.py::_resolve_period`'s own formulas (cross-checked directly against the real `_resolve_period` in a test, not just a hand-copied formula).
- `stock_summary`, `recent_operations`, `dashboard_context` — DASH-04 (single SQL `count()` for distinct in-stock product codes) and DASH-05 (6-type feed generalizing `sales.py::recent_sales`'s exact double-outerjoin shape; both Sale and Customer hops stay `.outerjoin()`, verified both by behavior tests — walk-in sale and receipt rows both surface with `customer: None` — and a source-inspection regression test asserting no bare `.join(Sale` / `.join(Customer` sneaks in).
- `dashboard_context(session, tz_name)` composes all of the above into one call; verified it never raises and returns `catalog: None` with every other key still populated when no `ActiveCatalog` row exists (DASH-02's empty-state contract), and that the call makes zero ledger writes (`session.new`/`session.dirty` empty afterward).

## Task Commits

Each task was executed as a literal TDD RED → GREEN pair (verified failing before implementing):

1. **Task 1: dashboard_now, catalog_status, period_metrics, dashboard_metrics**
   - `6195d54` test(23-03): add failing tests — confirmed RED via `ImportError: cannot import name 'dashboard'`
   - `f1735a5` feat(23-03): implement the four functions — GREEN, 8/8 task-1 tests passing
2. **Task 2: stock_summary, recent_operations, dashboard_context composer**
   - `b7696da` test(23-03): add failing tests — confirmed RED via `ImportError: cannot import name 'dashboard_context'`
   - `af914fe` feat(23-03): implement stock_summary/recent_operations/dashboard_context — GREEN, 14/14 tests passing

## Files Created/Modified

- `app/services/dashboard.py` - `WEEKDAY_LABELS`, `dashboard_now`, `catalog_status`, `period_metrics`, `dashboard_metrics`, `stock_summary`, `recent_operations`, `dashboard_context`
- `tests/test_dashboard.py` - 14 tests covering every behavior bullet in the plan, including D-08 sign regression, boundary cross-check against the real `_resolve_period`, Pitfall-4 outerjoin regression, and the no-catalog empty-state contract

## Decisions Made

- Boundary math (Monday-start week, calendar-month) is duplicated locally in `dashboard.py` rather than imported from `app.routes.reports`, per this codebase's convention that services never import routes. A dedicated test (`test_dashboard_metrics_week_and_month_boundaries_match_resolve_period`) freezes both `dashboard.datetime` and `app.routes.reports.datetime` to the same fixed instant and asserts `dashboard_metrics`'s week/month figures equal `period_metrics` called with `_resolve_period`'s own real presets — a genuine cross-module regression guard, not just a hand-copied-formula assertion.
- Test doubles freeze `dashboard.datetime` (module attribute reassignment) rather than adding an injectable `today` parameter to `dashboard_metrics`/`dashboard_context`, because the plan's `artifacts_produced` section fixes those functions' signatures as `(session, tz_name)` only — no `today` param. This mirrors `tests/test_finance_reports.py`'s `utcnow_iso` monkeypatch pattern, applied to a class attribute instead of a function.

## Deviations from Plan

None — plan executed exactly as written. Both tasks' `<behavior>`, `<action>`, and `<acceptance_criteria>` bullets are implemented and tested as specified; no Rule 1-4 fixes were needed.

## Issues Encountered

- First draft of the boundary-matching test unpacked `_resolve_period`'s `presets` dict incorrectly (`week_start, week_end = period["presets"]["week"]` iterated over dict *keys* `"from"`/`"to"` instead of values, since `_resolve_period` returns `{"from": iso, "to": iso}` dicts per preset, not tuples). Caught immediately by the test run (`TypeError: combine() argument 1 must be datetime.date, not str`) before any commit; fixed by explicitly reading `period["presets"]["week"]["from"]`/`["to"]` via `date.fromisoformat`. Not a deviation from the plan — a self-caught test-authoring bug, fixed before the RED commit was made.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `app.services.dashboard.dashboard_context(session, settings.display_tz)` is ready for Plan 06 (desktop home route) and Plan 07 (mobile home route) to call as their single data source — no route-side computation needed.
- Full regression suite (`uv run pytest -q`) passes 880/880 after this plan, confirming zero breakage of prior phases' tests.
- No blockers or concerns carried forward.

---
*Phase: 23-dashboard-history-rebuild*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: app/services/dashboard.py
- FOUND: tests/test_dashboard.py
- FOUND: .planning/phases/23-dashboard-history-rebuild/23-03-SUMMARY.md
- FOUND commit: 6195d54 (test Task 1 RED)
- FOUND commit: f1735a5 (feat Task 1 GREEN)
- FOUND commit: b7696da (test Task 2 RED)
- FOUND commit: af914fe (feat Task 2 GREEN)
- FOUND commit: a1795b4 (docs: SUMMARY)
