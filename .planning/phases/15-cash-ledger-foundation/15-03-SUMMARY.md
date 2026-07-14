---
phase: 15-cash-ledger-foundation
plan: 03
subsystem: database
tags: [sqlalchemy, sqlite, cash-ledger, sales, returns]

# Dependency graph
requires:
  - phase: 15-02
    provides: "app/services/finance.py — record_cash_movement(commit=False support), compute_balance"
provides:
  - "register_sale stages one aggregated +total_cents credit (category=sale, sale_id=header.id) before its trailing commit"
  - "register_return flips record_operation to commit=False, computes an independent debit (qty x frozen unit_price_cents), and closes stock + cash in ONE commit"
  - "tests/test_finance.py integration tests proving credit, rollback-writes-zero, debit, partial-independence, and atomicity"
affects: [15-04, 16-manual-cash-movements-history]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cash write hooks live at the SERVICE layer only (register_sale/register_return), never in routes — both desktop and mobile callers credit/debit for free"
    - "Return debit is always recomputed from the return's own qty x the origin op's frozen unit_price_cents, never reconciled against the prior sale credit row"

key-files:
  created: []
  modified:
    - app/services/sales.py
    - app/services/returns.py
    - tests/test_finance.py

key-decisions:
  - "Used an oversell-without-confirm basket (zero writes, no exception) to exercise the 'rollback path' test rather than forcing an IntegrityError — simpler, deterministic, and still proves zero cash rows on a non-committing sale attempt, matching the plan's own 'oversell without confirm OR a raising line' either/or wording"
  - "Partial-return test uses a distinct entered price (20,00) from the product card's price to prove the debit is computed independently of any cached/current price, not just independently of the credit amount"

patterns-established: []

requirements-completed: [FIN-01, FIN-02]

# Metrics
duration: 6min
completed: 2026-07-14
---

# Phase 15 Plan 03: Cash Ledger Wiring (Sale Credit / Return Debit) Summary

**`register_sale` now stages one aggregated `+total_cents` cash credit and `register_return` stages an independently-computed `-(qty x frozen price)` debit, both closed atomically with their existing stock transaction — proven by 5 new integration tests plus the full 574-test suite green.**

## Performance

- **Duration:** 6 min
- **Tasks:** 3 completed
- **Files modified:** 3 (2 source, 1 test)

## Accomplishments
- `app/services/sales.py::register_sale` stages exactly one `finance.record_cash_movement(category="sale", amount_cents=total_cents, sale_id=header.id, commit=False)` call after the per-line write loop and before the existing trailing `session.commit()`. The existing `except (IntegrityError, ValueError): session.rollback()` arm now rolls back the credit together with the Sale header + Operation rows for free — no new except logic needed.
- `app/services/returns.py::register_return` flips its `record_operation(..., commit=True)` to `commit=False`, computes the debit independently as `qty * (origin.unit_price_cents or 0)` (never read from any prior credit row), stages `finance.record_cash_movement(category="return", amount_cents=-debit, sale_id=origin.sale_id, commit=False)`, then closes both writes with one trailing `session.commit()` inside the existing `try`. Existing `except ValueError`/`except IntegrityError` arms are unchanged and now roll back both writes together.
- `tests/test_finance.py` extended with 5 integration tests: `test_sale_credits_till`, `test_sale_rollback_writes_zero_cash`, `test_full_return_restores_balance`, `test_partial_return_debits_independently`, `test_return_is_atomic`.
- `uv run pytest tests/test_finance.py tests/test_sales.py tests/test_returns.py -q` -> 69 passed.
- Full suite: `uv run pytest -q` -> 574 passed (no regressions; the Plan 02 pre-existing `test_mobile_sales.py` flake did not recur this run).

## Task Commits

Each task was committed atomically:

1. **Task 1: Stage the sale credit inside register_sale** - `b01ed83` (feat)
2. **Task 2: Add the return debit + atomic commit flip in register_return** - `5e38f77` (feat)
3. **Task 3: Integration tests — credit, sale_rollback, debit, partial, atomic** - `e73c47a` (test)

**Plan metadata:** committed together with this SUMMARY (worktree mode — orchestrator merges).

## Files Created/Modified
- `app/services/sales.py` - `from app.services import catalog, finance` import; one staged `record_cash_movement(category="sale", ..., commit=False)` call before `session.commit()`
- `app/services/returns.py` - `from app.services import finance` import; `record_operation(..., commit=False)` flip; independent debit computation + `record_cash_movement(category="return", ..., commit=False)`; one trailing `session.commit()`
- `tests/test_finance.py` - 5 new integration tests (credit/rollback/debit/partial/atomic) plus a `_cash_count` helper and new imports (`func`, `select`, `Operation`, `open_batches`, `register_sale`, `register_return`)

## Decisions Made
- Followed the plan's D-00c/D-00d wiring exactly: service-layer hooks only, `commit=False` staging, independent debit computation. No architectural deviations.
- Chose the oversell-without-confirm mechanism (over forcing an `IntegrityError`) for the rollback test — see key-decisions above.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All three tasks' acceptance criteria passed on first run; no auto-fixes needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FIN-01 (auto-credit on sale) and FIN-02 (auto-debit on return) are now observably correct — a committed sale always credits the till by its exact total, a rolled-back sale credits nothing, and a sale-linked return always debits by qty x frozen price atomically with the return op, restoring the pre-sale balance on a full return.
- No `finance` import exists in any `app/routes/*.py` — confirmed via grep, satisfying the D-00c/Pitfall-3 routing constraint (both desktop and mobile sale/return routes credit/debit through the shared services automatically).
- No blockers. Plan 04 (balance display, FIN-06) can now build on a proven-correct cash ledger with both write paths wired.

## Self-Check: PASSED

All modified files verified present on disk; all 3 commit hashes (`b01ed83`, `5e38f77`, `e73c47a`) verified present in `git log --oneline --all`.

---
*Phase: 15-cash-ledger-foundation*
*Completed: 2026-07-14*
