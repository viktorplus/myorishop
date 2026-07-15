---
phase: 17-financial-reports-export-dashboard-analytics
plan: 04
subsystem: finance-reports
tags: [fastapi, jinja2, htmx, csv-export, finance, mobile]

# Dependency graph
requires:
  - phase: 17-01
    provides: "app/services/finance_reports.py: cash_expense_total, stock_valuation, cash_flow_report; app/services/export.py: stream_cash_movements_csv"
  - phase: 17-02
    provides: "app/routes/finance.py: FINANCE_BASE/_metrics_context pattern; app/templates/partials/finance_tiles.html"
  - phase: 17-03
    provides: "app/routes/finance.py: finance_report_page/finance_report_csv pattern; app/templates/partials/cash_flow_report.html"
provides:
  - "GET /m/finance/metrics: full page or HX partial (SHARED partials/finance_tiles.html), depending on HX-Request header"
  - "GET /m/finance/report: full page or HX partial (SHARED partials/cash_flow_report.html), depending on HX-Request header"
  - "GET /m/finance/report.csv: period-scoped cash-movement CSV download, delegating to stream_cash_movements_csv"
  - "app/templates/mobile_pages/finance.html: «Показатели» tiles section above the untouched balance/forms/history"
  - "app/templates/mobile_pages/finance_report.html: mobile report page shell reusing the shared results partial"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mobile /m/finance/metrics, /m/finance/report, /m/finance/report.csv are near-verbatim clones of the desktop routes with finance_base=/m/finance, reusing the SAME shared partials/finance_tiles.html and partials/cash_flow_report.html (D-04c) — no mobile-specific tiles/report partial created"
    - "Task 1/Task 2 split ships a minimal wiring-only mobile_pages/finance_report.html placeholder in Task 1 (proves route branching) then Task 2 replaces it with the full UI-SPEC shell (period_filter + CSV link + results div) — mirrors the identical 17-02/17-03 precedent"

key-files:
  created:
    - app/templates/mobile_pages/finance_report.html
  modified:
    - app/routes/mobile_finance.py
    - app/templates/mobile_pages/finance.html
    - tests/test_finance_reports.py

key-decisions:
  - "mobile_finance_metrics/mobile_finance_report/mobile_finance_report_csv are structural clones of the desktop finance.py routes — same _resolve_period -> local_day_bounds_utc -> service -> HX-Request branch shape, only finance_base differs (/m/finance vs /finance)"
  - "_metrics_context in mobile_finance.py duplicates app.routes.finance._metrics_context verbatim (net profit = gross + cash_expense_total, plain addition D-01a; stock_valuation called unconditionally, D-02b) rather than importing the desktop helper, keeping each router self-contained per the existing mobile_finance.py/finance.py duplication pattern (mirrors _history_context's existing split)"
  - "«Показатели» section inserted ABOVE <h1>Баланс кассы</h1> on mobile_pages/finance.html, period_filter OUTSIDE #finance-metrics (only the tiles partial is the HX swap target) — the Phase 15-16 balance/forms/Тип-select/#cash-history-cards/load-more includes are untouched"
  - "mobile_pages/finance_report.html mirrors pages/finance_report.html exactly (period_filter targeting #cashflow-results, plain non-hx-get CSV <a>, #cashflow-results div wrapping the shared partial)"

patterns-established: []

requirements-completed: [FIN-08, FIN-09, FIN-10, FIN-11, FIN-12]

# Metrics
duration: 25min
completed: 2026-07-15
---

# Phase 17 Plan 04: Mobile Финансы Dashboard Tiles + Report + CSV (Mobile Parity) Summary

**Mobile `/m/finance/metrics`, `/m/finance/report`, `/m/finance/report.csv` routes bringing the desktop Phase 17 dashboard tiles + cash-flow report + CSV export to mobile parity (D-04c) by reusing the shared `partials/finance_tiles.html` and `partials/cash_flow_report.html` — the Phase 15-16 mobile balance/forms/history stay untouched.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-15
- **Tasks:** 2 completed
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `app/routes/mobile_finance.py` gained `_metrics_context` (finance_base=/m/finance), `mobile_finance_metrics` (`GET /m/finance/metrics`), `mobile_finance_report` (`GET /m/finance/report`), and `mobile_finance_report_csv` (`GET /m/finance/report.csv`) — all near-verbatim clones of the desktop `app/routes/finance.py` shapes, reusing the SAME shared `partials/finance_tiles.html` / `partials/cash_flow_report.html` and the SAME `finance_reports`/`export` services, no mobile-specific service or duplicate partial.
- `mobile_finance_page` (`GET /m/finance`) now merges `**_metrics_context(session, "", "")` so tiles render on first load.
- `app/templates/mobile_pages/finance.html` gained a «Показатели» section (period_filter targeting `#finance-metrics` outside the div, shared tiles partial inside it) above the existing `<h1>Баланс кассы</h1>` — the balance include, withdraw/deposit forms, «Тип» bucket select, `#cash-history-cards`, and load-more control are byte-for-byte unchanged.
- `app/templates/mobile_pages/finance_report.html` created: extends `mobile_base.html`, shared `period_filter.html` (action `/m/finance/report`, target `#cashflow-results`), a plain (never `hx-get`) `<a class="button" href="/m/finance/report.csv?...">Скачать CSV</a>`, and `#cashflow-results` wrapping the shared `cash_flow_report.html` partial.
- 5 new web tests added to `tests/test_finance_reports.py`: metrics HX/plain branching + `/m/finance` still renders, report HX/plain branching, CSV streaming, mobile-vs-desktop subtotal parity, and the net-profit caveat + untouched-surface regression guard.
- Full suite: 674 passed, no regressions (17-03 baseline was 669 + 5 new tests here).
- `gsd-tools query requirements.mark-complete FIN-08 FIN-09 FIN-10 FIN-11 FIN-12` — all 5 phase requirements marked complete in `REQUIREMENTS.md` (this plan is the final wave-4 plan closing out phase 17's mobile-parity scope).

## Task Commits

Each task was committed atomically:

1. **Task 1: /m/finance/metrics + /m/finance/report + /m/finance/report.csv routes** - `97c0d5d` (feat)
2. **Task 2: mobile finance.html Показатели section + mobile finance_report.html page** - `b0d3977` (feat)

**Plan metadata:** (worktree mode — orchestrator commits STATE.md/ROADMAP.md after wave merge)

## Files Created/Modified

- `app/routes/mobile_finance.py` - Added `_metrics_context`, `mobile_finance_metrics`, `mobile_finance_report`, `mobile_finance_report_csv`; extended imports with `Query`, `settings`, `local_day_bounds_utc`, `_resolve_period`, `export_service`, `cash_expense_total`/`cash_flow_report`/`stock_valuation`, `sales_profit_report`; `mobile_finance_page` now merges the metrics context.
- `app/templates/mobile_pages/finance.html` - Added the «Показатели» section (period_filter + `#finance-metrics` wrapping the shared tiles partial) above `<h1>Баланс кассы</h1>`; all other sections unchanged.
- `app/templates/mobile_pages/finance_report.html` - New: mobile report page shell (period filter, CSV link, results div wrapping the shared partial). Shipped as a Task 1 wiring-only placeholder, replaced with the full shell in Task 2.
- `tests/test_finance_reports.py` - 5 new web tests across both tasks (route branching, CSV content, mobile/desktop parity, net caveat + regression guard).

## Decisions Made

- All three mobile routes are structural clones of their desktop counterparts (same `_resolve_period` -> `local_day_bounds_utc` -> service -> `HX-Request` branch shape), differing only in `finance_base` — keeping the codebase's established report/tiles-route pattern consistent for mobile (matches how FIN-03..07 achieved parity via `finance_base`-parameterised shared forms).
- `_metrics_context` is duplicated (not imported) into `mobile_finance.py`, mirroring the existing `_history_context` split between `finance.py` and `mobile_finance.py` — each router stays self-contained, consistent with the codebase's existing desktop/mobile route-file separation.
- No new service, no new write path, no mobile-specific tiles/report partial — all three routes reuse the exact `partials/finance_tiles.html` and `partials/cash_flow_report.html` shipped in 17-02/17-03 (D-04c hard requirement).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Shipped a minimal wiring-only `mobile_pages/finance_report.html` placeholder in Task 1**
- **Found during:** Task 1
- **Issue:** Task 1's own `<verify>` command (`pytest -k "mobile"`) requires `GET /m/finance/report` to render successfully (both HX and full-page branches), but the full period-filter + CSV-link chrome is explicitly Task 2's `files_modified` scope. Without any `mobile_pages/finance_report.html` at all, Task 1's own required test (`test_web_mobile_finance_report_hx`) would fail with `TemplateNotFound`.
- **Fix:** Created a minimal placeholder (title + `#cashflow-results` wrapping the already-existing shared `cash_flow_report.html` partial, no period filter, no CSV link) in Task 1 — just enough to prove the route branches correctly. Task 2 fully replaced it with the UI-SPEC-exact shell (period filter + CSV link).
- **Files modified:** `app/templates/mobile_pages/finance_report.html` (created in Task 1, rewritten in Task 2)
- **Commit:** `97c0d5d` (Task 1 placeholder), `b0d3977` (Task 2 full version)
- Mirrors the identical precedent already established by 17-02's `finance_tiles.html` and 17-03's `cash_flow_report.html` split (see 17-03-SUMMARY.md Deviation 1).

---

**Total deviations:** 1 auto-fixed (test-sequencing, matching established phase precedent).
**Impact on plan:** Mechanical only (identical pattern already used twice earlier in this phase). No scope creep, no behavior change beyond what Task 2 explicitly delivers.

## Known Stubs

None. Both routes are fully wired end-to-end (real service calls, real shared-partial rendering); no hardcoded empty values or placeholder copy.

## Threat Flags

None. All three new routes are GET-only reads reusing the desktop's already-threat-modeled `_resolve_period` clamp, `local_day_bounds_utc` bounds, and the `stream_cash_movements_csv`/`cash_flow_report.html` sanitization already verified in 17-01/17-03 (T-17-01/T-17-02/T-17-05c per this plan's own `<threat_model>`, all disposition `mitigate` and satisfied by reuse — no new surface introduced).

## Issues Encountered

None beyond the expected Task 1/Task 2 template-placeholder sequencing (documented above).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Mobile `/m/finance` shows the gross/net/stock tiles at desktop parity; `/m/finance/report` + `/m/finance/report.csv` work end-to-end (full/HX branch, plain-link CSV); the Phase 15-16 mobile balance/forms/history surface is untouched.
- All 5 Phase 17 requirements (FIN-08, FIN-09, FIN-10, FIN-11, FIN-12) marked complete in `REQUIREMENTS.md`.
- Phase 17 is functionally complete pending the end-of-phase human UAT checklist in this plan's `<verification>` section (phone-width browser check of `/m/finance`, `/m/finance/report`, and the CSV download).
- No blockers identified.

---
*Phase: 17-financial-reports-export-dashboard-analytics*
*Completed: 2026-07-15*

## Self-Check: PASSED

All 5 created/modified files found on disk; both commit hashes (97c0d5d, b0d3977) found in git log.
