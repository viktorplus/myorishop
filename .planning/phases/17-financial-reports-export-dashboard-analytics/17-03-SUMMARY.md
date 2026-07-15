---
phase: 17-financial-reports-export-dashboard-analytics
plan: 03
subsystem: finance-reports
tags: [fastapi, jinja2, htmx, csv-export, finance]

# Dependency graph
requires:
  - phase: 17-01
    provides: "app/services/finance_reports.py: cash_flow_report (FIN-08); app/services/export.py: stream_cash_movements_csv (FIN-09)"
  - phase: 17-02
    provides: "app/routes/finance.py: FINANCE_BASE, _resolve_period import pattern, existing /finance route structure"
provides:
  - "GET /finance/report: full page or HX partial (partials/cash_flow_report.html), depending on HX-Request header"
  - "GET /finance/report.csv: period-scoped cash-movement CSV download, delegating to stream_cash_movements_csv"
  - "app/templates/pages/finance_report.html: report page shell (title + period filter + plain CSV download link + #cashflow-results div)"
  - "app/templates/partials/cash_flow_report.html: Приход/Расход results partial (income/expense tables with CASH_CATEGORIES labels, reconciling with cash_expense_total)"
affects: [17-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Report page HX-vs-full-page branch is a near-verbatim clone of reports_sales_page (app/routes/reports.py) — same _resolve_period -> local_day_bounds_utc -> service -> HX branch shape"
    - "CSV download route stays a bare delegate (no Request/template) mirroring app/routes/export.py's thin-route pattern"
    - "Category labels rendered exclusively via the CASH_CATEGORIES Jinja global — never hardcoded RU strings in a template"

key-files:
  created:
    - app/templates/pages/finance_report.html
    - app/templates/partials/cash_flow_report.html
  modified:
    - app/routes/finance.py
    - tests/test_finance_reports.py

key-decisions:
  - "finance_report_page mirrors reports_sales_page's exact HX-Request branch: HX-Request header -> partials/cash_flow_report.html (results only), plain GET -> pages/finance_report.html (full chrome)"
  - "finance_report_csv is a bare delegate route (no Request/template): resolves the period via _resolve_period (never raises) then hands start_iso/end_iso straight to export_service.stream_cash_movements_csv — the one documented T-06-09 bounded exception from 17-01"
  - "cash_flow_report.html renders two tables (Приход / Расход) with one row per bucketed category plus an Итого за период subtotal row per section; category labels come only from the CASH_CATEGORIES Jinja global (never hardcoded), so the Расход subtotal is structurally guaranteed to equal cash_expense_total for the same period (D-05)"
  - "Task 1 shipped a minimal wiring-only cash_flow_report.html placeholder (three branches, no table markup) to satisfy Task 1's own route-branching tests without pulling Task 2's UI-SPEC work forward; Task 2 replaced it in full — same split pattern 17-02 used for finance_tiles.html"

patterns-established:
  - "Report page shell (pages/*.html) + results partial (partials/*.html) pair, wired through a single _resolve_period -> service -> HX-Request branch, reused verbatim for a third time in this codebase (reports_sales / reports_writeoffs / finance_report)"

requirements-completed: [FIN-08, FIN-09]

# Metrics
duration: 30min
completed: 2026-07-15
---

# Phase 17 Plan 03: Cash-Flow Report Page + CSV Export Summary

**`/finance/report` period cash-flow report (Приход/Расход tables reconciling with the net-profit tile) plus `/finance/report.csv` period-scoped download, both thin routes delegating to the 17-01 service layer.**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-07-15
- **Tasks:** 2 completed
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `app/routes/finance.py` gained `finance_report_page` (`GET /finance/report`: `_resolve_period` -> `local_day_bounds_utc` -> `cash_flow_report`, branching on `HX-Request` between the results partial and the full page) and `finance_report_csv` (`GET /finance/report.csv`: resolves the period then delegates straight to `export_service.stream_cash_movements_csv`).
- `app/templates/pages/finance_report.html` created: `<h1>Движения кассы за период</h1>`, the shared `period_filter.html` targeting `#cashflow-results`, a plain (never `hx-get`) `<a class="button" href="/finance/report.csv?from=...&to=...">Скачать CSV</a>`, and the `#cashflow-results` results div.
- `app/templates/partials/cash_flow_report.html` created with the full three-branch contract: `report is none` -> `.error-block`; `movement_count == 0` -> the empty-state paragraph; else -> Приход/Расход tables, each row's category label sourced only from the `CASH_CATEGORIES` Jinja global, each table closed by an `Итого за период` subtotal row.
- 6 new web tests added to `tests/test_finance_reports.py` covering: HX-partial-only vs full-page branching (Task 1), CSV streaming with period scoping (Task 1), full-page content assertions (CSV link + Приход/Расход + category labels, Task 2), HX-partial content assertions (no page chrome, Task 2), and the empty-state copy (Task 2).
- Full suite: 669 passed, no regressions (17-02 baseline was 663 + 6 new tests here).

## Task Commits

Each task was committed atomically:

1. **Task 1: /finance/report + /finance/report.csv routes** - `ca3552d` (feat)
2. **Task 2: finance_report.html page + cash_flow_report.html results partial** - `1fac0cd` (feat)

**Plan metadata:** (worktree mode — orchestrator commits STATE.md/ROADMAP.md after wave merge)

## Files Created/Modified

- `app/routes/finance.py` - Added `finance_report_page` (`GET /finance/report`) and `finance_report_csv` (`GET /finance/report.csv`); extended the `finance_reports` import with `cash_flow_report` and added the `export_service` import.
- `app/templates/pages/finance_report.html` - New: report page shell (title, period filter, plain CSV download link, results div).
- `app/templates/partials/cash_flow_report.html` - New: three-branch results partial (error / empty / Приход-Расход tables with CASH_CATEGORIES labels and subtotal rows).
- `tests/test_finance_reports.py` - 6 new web tests across both tasks (route branching, CSV content, full-page/HX-partial content, empty state).

## Decisions Made

- `finance_report_page` is a near-verbatim structural clone of `reports_sales_page` (`app/routes/reports.py`) — same `_resolve_period` -> `local_day_bounds_utc` -> service -> `HX-Request` branch shape, keeping the codebase's one report-route pattern consistent for a third instance.
- `finance_report_csv` accepts ONLY `from`/`to` query params (no filename/path), consuming them exclusively as ORM `.where` bounds via `local_day_bounds_utc` — the documented T-06-09 bounded exception from 17-01, never a general "exports may take arbitrary params" precedent.
- Category labels in `cash_flow_report.html` come exclusively from the `CASH_CATEGORIES` Jinja global (already registered in `app/routes/__init__.py`) — never a hardcoded RU string in the template — so the Расход subtotal is structurally guaranteed to match `cash_expense_total` for the same period (D-05 hard reconciliation, verified independently at the service layer in 17-01).
- No pagination added to the report (RESEARCH Open Q2, per plan instruction) — single-operator period counts stay small; revisit only if a real period exceeds `LIST_PAGE_SIZE` movement rows.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Shipped a minimal wiring-only `cash_flow_report.html` placeholder in Task 1**
- **Found during:** Task 1
- **Issue:** Task 1's own `<verify>` command (`pytest -k "report_hx or report_csv or report_page"`) requires `GET /finance/report` to render successfully (both HX and full-page branches), but the full Приход/Расход table markup is explicitly Task 2's `files_modified` scope. Without any `partials/cash_flow_report.html` at all, Task 1's own required tests would fail with `TemplateNotFound`.
- **Fix:** Created a minimal three-branch placeholder (error-block / empty-state / plain income-expense totals, no table markup) in Task 1 — just enough to prove the route branches correctly. Task 2 fully replaced its content with the UI-SPEC-exact Приход/Расход table markup and category labels.
- **Files modified:** `app/templates/partials/cash_flow_report.html` (created in Task 1, rewritten in Task 2)
- **Commit:** `ca3552d` (Task 1 placeholder), `1fac0cd` (Task 2 full version)
- Mirrors the identical precedent already established by 17-02's `finance_tiles.html` split (see 17-02-SUMMARY.md Deviation 1).

**2. [Rule 1 - Lint fix] Reordered an import in `app/routes/finance.py`**
- **Found during:** Task 2 (running `ruff check` before the final commit)
- **Issue:** `ruff check` flagged I001 (unsorted import block) — the Task 1 commit added `from app.services import export as export_service` after the multi-line `from app.services.finance import (...)` block instead of alphabetically before it.
- **Fix:** Ran `ruff check --fix app/routes/finance.py`; the import now sits alphabetically between `app.routes.reports` and `app.services.finance`.
- **Files modified:** `app/routes/finance.py`
- **Verification:** `ruff check app/routes/finance.py` -> "All checks passed!"
- **Committed in:** `1fac0cd` (Task 2 commit, folded in as a minor lint touch-up)

---

**Total deviations:** 2 auto-fixed (1 blocking/test-sequencing, 1 lint)
**Impact on plan:** Both auto-fixes are mechanical (test-sequencing precedent already established in this phase, and an import-order lint fix). No scope creep, no behavior change beyond what Task 2 explicitly delivers.

## Issues Encountered

- An early version of `test_web_finance_report_empty_state` asserted `"Приход" not in response.text`, which false-failed because the app's global nav bar contains an unrelated `<a href="/receipts/new">Приход</a>` link (goods-receipt nav item, not the report's income section). Fixed by narrowing the assertion to `"<h2>Приход</h2>" not in response.text`, which unambiguously targets the report's income-section heading.
- A pre-existing `ruff format` drift was found in `tests/test_finance_reports.py`'s 17-01 test block (`_record_cash_at(...)` call-wrapping style). Confirmed pre-existing by running `ruff format --check` against the file as it stood at `HEAD~1` (before any Plan 17-03 edits) — the drift already existed there. Logged to `deferred-items.md` per the executor's scope-boundary rule rather than reformatted (this plan's own new test block is unaffected and already correctly formatted).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/finance/report` and `/finance/report.csv` are fully wired and tested; the desktop cash-flow report + CSV export surface for FIN-08/FIN-09 is complete.
- `pages/finance_report.html` and `partials/cash_flow_report.html` establish the exact structural pattern (`period_action="/finance/report"`, `period_target="#cashflow-results"`, `finance_base` echoed into context) that Plan 17-04's mobile `/m/finance/report` (D-04c) can mirror the same way 16-04 mirrored 16-03's desktop forms for `/m/finance`.
- No blockers identified for Plan 17-04.

---
*Phase: 17-financial-reports-export-dashboard-analytics*
*Completed: 2026-07-15*

## Self-Check: PASSED

All 5 created/modified files found on disk; all 3 commit hashes (ca3552d, 1fac0cd, e58dee2) found in git log.
