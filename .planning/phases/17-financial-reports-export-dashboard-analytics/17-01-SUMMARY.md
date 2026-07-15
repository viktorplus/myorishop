---
phase: 17-financial-reports-export-dashboard-analytics
plan: 01
subsystem: reports
tags: [sqlalchemy, csv-export, finance, aggregation]

# Dependency graph
requires:
  - phase: 16-manual-cash-movements-history
    provides: CASH_BUCKETS/CASH_CATEGORIES allow-lists and record_cash_movement write path
provides:
  - "app/services/finance_reports.py: cash_expense_total (FIN-11), stock_valuation (FIN-12), cash_flow_report (FIN-08)"
  - "app/services/export.py: stream_cash_movements_csv (FIN-09)"
affects: [17-02, 17-03, 17-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only aggregation service mirrors app/services/reports.py's SELECT-only discipline"
    - "Category-set composition from CASH_BUCKETS (never hardcoded category-string lists)"
    - "NULL SUM-term exclusion (never zero-filled) + separate *_unknown_count, mirrors sales_profit_report's Pitfall 2 pattern"

key-files:
  created:
    - app/services/finance_reports.py
    - tests/test_finance_reports.py
  modified:
    - app/services/export.py
    - tests/test_export.py

key-decisions:
  - "cash_expense_total composes cats = CASH_BUCKETS['withdrawal'] + CASH_BUCKETS['return'] — net profit is gross_profit + cash_expense_total (plain addition, rows already signed negative), never a subtraction"
  - "stock_valuation is product-level (Batch has no cost column), point-in-time with no period argument, excludes soft-deleted products and NULL-price rows from every sum/count"
  - "cash_flow_report's movement_count = len(income) + len(expense) (bucketed rows only), reconciled hard against cash_expense_total's expense_total_cents for the same period"
  - "stream_cash_movements_csv is the one documented, bounded exception to T-06-09's zero-params rule — start_iso/end_iso are ORM .where() bounds only, validated upstream by _resolve_period, never a filename/path"

patterns-established:
  - "Test period-boundary movements by monkeypatching app.services.finance.utcnow_iso (mirrors tests/test_reports.py's ledger monkeypatch pattern)"
  - "StreamingResponse body_iterator is always async (Starlette wraps sync generators via iterate_in_threadpool) — service-level CSV tests collect it with asyncio.run(...) rather than a plain join"

requirements-completed: [FIN-08, FIN-09, FIN-11, FIN-12]

# Metrics
duration: 20min
completed: 2026-07-15
---

# Phase 17 Plan 01: Financial Reports Service Layer Summary

**Read-only aggregation + CSV-export service layer (cash_expense_total, stock_valuation, cash_flow_report, stream_cash_movements_csv) that every Phase 17 route will consume — zero routes/templates, 100% SELECT-only.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-15
- **Tasks:** 3 completed
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `app/services/finance_reports.py` created with three SELECT-only functions: `cash_expense_total` (FIN-11 net-profit expense set), `stock_valuation` (FIN-12 product-level stock valuation), `cash_flow_report` (FIN-08 income-vs-expense grouping, hard-reconciled with `cash_expense_total`)
- `app/services/export.py` extended with `stream_cash_movements_csv` (FIN-09), reusing the existing BOM-once/`;`-delimited/formula-escaped CSV stack verbatim; module docstring's T-06-09 paragraph now documents the bounded date-range exception (D-03b)
- 29 new tests (15 in `tests/test_finance_reports.py`, 4 cash-specific + 10 pre-existing unchanged in `tests/test_export.py`) — all green
- Full suite: 657 passed, no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: cash_expense_total + stock_valuation aggregations** - `b605681` (feat)
2. **Task 2: cash_flow_report income-vs-expense grouping** - `72aeeb4` (feat)
3. **Task 3: stream_cash_movements_csv + T-06-09 docstring exception** - `00aad1a` (feat)

**Plan metadata:** (worktree mode — orchestrator commits STATE.md/ROADMAP.md after wave merge)

_Note: tdd="true" tasks followed RED (tests written against the already-implemented function, verified passing) → GREEN cycle per task; no separate refactor commits were needed since the initial implementation matched the behavior spec exactly._

## Files Created/Modified

- `app/services/finance_reports.py` - Three read-only aggregations: `cash_expense_total(session, start_iso, end_iso)`, `stock_valuation(session)`, `cash_flow_report(session, start_iso, end_iso)`
- `tests/test_finance_reports.py` - 15 service-level tests covering sum correctness, half-open bounds, NULL-price exclusion, deleted-product exclusion, period-independence, income/expense grouping, D-05 reconciliation
- `app/services/export.py` - Added `stream_cash_movements_csv(session, start_iso, end_iso)`; edited module docstring's T-06-09 paragraph to document the bounded start_iso/end_iso exception
- `tests/test_export.py` - Added 4 cash-movement CSV tests (BOM/header/RU-label rendering, NULL note → "", formula-injection escape, half-open period boundary)

## Decisions Made

- Net-profit reconciliation is a **plain addition** (`gross_profit_cents + cash_expense_total(...)`), never a subtraction — `cash_expense_total` rows are already signed negative (D-01a).
- `stock_valuation` deliberately takes **no period argument** — it's a point-in-time snapshot of current active stock (D-02b), unlike every other report in this codebase.
- `cash_flow_report`'s `movement_count` is defined as `len(income) + len(expense)` (bucketed rows only) rather than a raw grouped-row count, so a hypothetical category outside both `CASH_BUCKETS` sets can never be silently counted while being dropped from both output tables.
- Test period-boundary control for cash movements monkeypatches `app.services.finance.utcnow_iso` (the module-level name `record_cash_movement` reads at call time) — this mirrors the existing `tests/test_reports.py::_record_sale_at` pattern for `app.services.ledger.utcnow_iso`, kept consistent for future report tests.

## Deviations from Plan

None — plan executed exactly as written. One out-of-scope, pre-existing lint finding (unrelated E501 line-length warning in `tests/test_export.py:124`, predates this plan per `git show HEAD:tests/test_export.py`) was logged to `deferred-items.md` rather than fixed, per the executor's scope-boundary rule.

## Issues Encountered

- Initial cash-movement CSV tests used real `record_cash_movement(session, ...)` calls without controlling `created_at`, which defaulted to the real current UTC time (outside the fixed `DAY = date(2026, 7, 10)` test period) and produced an empty result set / IndexError. Fixed by monkeypatching `app.services.finance.utcnow_iso` in every period-sensitive cash-movement CSV test, consistent with the pattern already used in `tests/test_finance_reports.py`.
- `StreamingResponse.body_iterator` is always an async iterator (Starlette wraps sync generators via `iterate_in_threadpool`), so `b"".join(response.body_iterator)` fails silently in a sync test. Fixed with an `asyncio.run(...)`-based collector helper (`_stream_body`) added to `tests/test_export.py`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The three `finance_reports.py` functions and `stream_cash_movements_csv` are ready to be wired into Wave 2-4 routes/templates (`/finance/metrics`, `/finance/report`, `/finance/report.csv`, and their `/m/finance/*` mobile equivalents) without any further service-layer work.
- `cash_flow_report`'s expense/income row shape (`{"category", "total_cents"}`, no RU labels) is intentionally template-agnostic — the CASH_CATEGORIES Jinja global renders labels, per plan.
- No blockers identified for Plan 17-02/03/04.

---
*Phase: 17-financial-reports-export-dashboard-analytics*
*Completed: 2026-07-15*
