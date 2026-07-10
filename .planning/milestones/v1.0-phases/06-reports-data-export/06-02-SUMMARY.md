---
phase: 06-reports-data-export
plan: 02
subsystem: reports
tags: [fastapi, sqlalchemy, jinja2, htmx, zoneinfo, reporting]

# Dependency graph
requires:
  - phase: 01-foundation-ledger-core
    provides: append-only Operation ledger, utcnow_iso/iso_to_local UTC-ISO conventions
  - phase: 04-sales-customers
    provides: frozen unit_cost_cents/unit_price_cents snapshot per sale line (SAL-05)
provides:
  - "app.core.local_day_bounds_utc(start_day, end_day, tz_name) -> (start_iso, end_iso) — the sole sanctioned period-math helper for Phase 6"
  - "app.services.reports.sales_profit_report(session, start_iso, end_iso) -> dict — NULL-cost-safe sales/profit aggregation"
  - "GET /reports landing page + GET /reports/sales report page"
  - "app.routes.reports._resolve_period(from_raw, to_raw, tz_name) -> dict — shared preset/date-parsing logic"
  - "partials/period_filter.html — shared preset-bar + от/по date filter, reused unchanged by Plans 06-05/06-06"
affects: [06-05-writeoffs-report, 06-06-top-stale-products]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "local_day_bounds_utc: local-midnight-to-UTC half-open range via ZoneInfo, mirrors iso_to_local's tz handling in the opposite direction"
    - "NULL-cost-safe profit aggregation: cost-unknown sale lines count toward revenue but are excluded from cost/profit sums, surfaced via cost_unknown_count instead of silently treated as zero-cost"
    - "one code path for period selection (D-01): preset buttons and hand-edited от/по dates both resolve through the same _resolve_period + local_day_bounds_utc pair"

key-files:
  created:
    - app/services/reports.py
    - app/routes/reports.py
    - app/templates/pages/reports_landing.html
    - app/templates/pages/reports_sales.html
    - app/templates/partials/period_filter.html
    - app/templates/partials/sales_report_results.html
  modified:
    - app/core.py
    - app/templates/base.html
    - app/main.py
    - app/static/style.css
    - tests/test_core.py
    - tests/test_reports.py

key-decisions:
  - "local_day_bounds_utc is the ONLY period-math helper any report in Phase 6 uses — never slice the UTC created_at string by date directly"
  - "sales_profit_report excludes cost-unknown lines from cost/profit but still counts their revenue and units, per RESEARCH Pitfall 2 — shown as a visible caveat, not hidden"
  - "sales/write-off reports never filter Product.deleted_at (RESEARCH Pitfall 5) — they are historical views over what happened, not catalog views of what currently exists"

patterns-established:
  - "Period filter partial contract (period_action, period_target, from_date, to_date, active_preset, presets, error) — Plans 06-05/06-06 include partials/period_filter.html unchanged with only period_action/period_target varying"

requirements-completed: [RPT-01]

# Metrics
duration: 25min
completed: 2026-07-10
---

# Phase 6 Plan 02: Sales & Profit Report + Shared Reporting Infrastructure Summary

**local_day_bounds_utc half-open UTC boundary helper, NULL-cost-safe sales_profit_report aggregation, and /reports + /reports/sales with a shared one-code-path period filter (preset buttons + от/по dates)**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-10 (session start)
- **Completed:** 2026-07-10T14:25:05Z
- **Tasks:** 3
- **Files modified:** 12 (6 created, 6 modified)

## Accomplishments
- `local_day_bounds_utc(start_day, end_day, tz_name)` in `app/core.py` — converts a local calendar day/range into a half-open `[start_iso, end_iso)` UTC ISO string range, pinned by tests covering the exact evening-sale-near-midnight scenario D-02 exists to get right
- `sales_profit_report(session, start_iso, end_iso)` in `app/services/reports.py` — totals + per-product breakdown, cost-unknown lines never silently inflate profit (RESEARCH Pitfall 2), soft-deleted products still appear in past-period reports (RESEARCH Pitfall 5)
- `GET /reports` landing page linking to the sales report; `GET /reports/sales` rendering period totals and a per-product breakdown table for today/week/month/custom ranges, with a RU inline error for invalid/inverted dates (never a 500)
- Shared `partials/period_filter.html` — the exact preset-bar + от/по contract Plans 06-05 and 06-06 will include unchanged
- Nav gains an «Отчёты» entry; `app/main.py` registers the new router

## Task Commits

Each task was committed atomically:

1. **Task 1: local_day_bounds_utc — RED** - `4c5bfcb` (test)
2. **Task 1: local_day_bounds_utc — GREEN** - `0c203f7` (feat)
3. **Task 2: sales_profit_report — RED** - `be458ab` (test)
4. **Task 2: sales_profit_report — GREEN** - `6e03c4f` (feat)
5. **Task 3: /reports landing + /reports/sales route, templates, nav, period filter** - `52c8556` (feat)

**Plan metadata:** committed alongside this SUMMARY (see final commit).

## Files Created/Modified
- `app/core.py` - Added `local_day_bounds_utc` (D-02 mandatory correctness helper)
- `app/services/reports.py` - New `sales_profit_report` NULL-cost-safe aggregation service
- `app/routes/reports.py` - New router: `_resolve_period`, `GET /reports`, `GET /reports/sales`
- `app/templates/pages/reports_landing.html` - New `/reports` landing page
- `app/templates/pages/reports_sales.html` - New `/reports/sales` page
- `app/templates/partials/period_filter.html` - New shared preset-bar + от/по partial (D-01)
- `app/templates/partials/sales_report_results.html` - New summary + breakdown table partial
- `app/templates/base.html` - Added «Отчёты» nav entry between «История» and «Справочник»
- `app/main.py` - Registered `reports` router (alphabetical import + append to include_router block)
- `app/static/style.css` - Added `.preset-bar` rule below `.filter-bar`
- `tests/test_core.py` - 4 new tests for `local_day_bounds_utc`; 2 docstrings shortened for ruff line-length
- `tests/test_reports.py` - New file: 4 service-level tests + 5 web-level tests

## Decisions Made
- Followed the plan's exact implementation guidance for `_resolve_period`: blank from/to defaults to today; unparsable dates and inverted ranges both fall back to today with a RU error, never reaching the query layer (Security V5)
- `sales_report_results.html` has no wrapping id — the page template supplies `div#sales-results`, and the same partial is the HX innerHTML swap payload (matches `/history`'s existing pattern)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Shortened two test_core.py docstrings over ruff's 100-char line limit**
- **Found during:** Task 3's plan-level `ruff check` verification step
- **Issue:** Two docstrings added in Task 1 (RED commit `4c5bfcb`) exceeded the 100-character line-length limit enforced by this project's ruff config, which would fail `uv run ruff check`
- **Fix:** Shortened the docstring wording without changing test behavior or assertions
- **Files modified:** tests/test_core.py
- **Verification:** `uv run ruff check` passes with no errors; `uv run pytest tests/test_core.py -x -q` still green
- **Committed in:** `52c8556` (bundled with Task 3's commit since it was caught during Task 3's verification pass)

---

**Total deviations:** 1 auto-fixed (1 bug/lint)
**Impact on plan:** Cosmetic docstring-length fix only; no behavior change. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `local_day_bounds_utc` and `partials/period_filter.html` exist as the shared contract Plans 06-05 (write-offs report) and 06-06 (top-selling/stale products) build on without redefining period math
- RPT-01 fully satisfied: today/week/month/custom period sales & profit reporting with correct local-day boundaries and NULL-cost-safe profit math
- No blockers for downstream Phase 6 plans

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Status |
|------|-----|-------|----------|--------|
| Task 1 (local_day_bounds_utc) | ✓ `4c5bfcb` | ✓ `0c203f7` | n/a | Pass |
| Task 2 (sales_profit_report) | ✓ `be458ab` | ✓ `6e03c4f` | n/a | Pass |

Task 3 was `type="auto"` (no `tdd="true"`) — no RED/GREEN gate applies.

---
*Phase: 06-reports-data-export*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/core.py contains local_day_bounds_utc
- FOUND: app/services/reports.py
- FOUND: app/routes/reports.py
- FOUND: app/templates/pages/reports_landing.html
- FOUND: app/templates/pages/reports_sales.html
- FOUND: app/templates/partials/period_filter.html
- FOUND: app/templates/partials/sales_report_results.html
- FOUND: commit 4c5bfcb, 0c203f7, be458ab, 6e03c4f, 52c8556 all present in git log
- uv run pytest tests/test_core.py tests/test_reports.py -x -q: 24 passed
- uv run pytest (full suite): 180 passed
- uv run ruff check app/core.py app/services/reports.py app/routes/reports.py app/main.py: All checks passed
