---
phase: 15-cash-ledger-foundation
plan: 02
subsystem: database
tags: [sqlalchemy, sqlite, append-only-ledger, cash]

# Dependency graph
requires:
  - phase: 15-01
    provides: "CashMovement model + cash_movements table, CASH_CATEGORIES allow-list, append-only triggers, migration 0013"
provides:
  - "app/services/finance.py — the single sanctioned write path for cash_movements"
  - "next_seq(session, device_id) — per-device seq, mirrors ledger.next_seq"
  - "record_cash_movement(session, *, category, amount_cents, sale_id=None, note=None, commit=True) — audit-stamped insert with CASH_CATEGORIES allow-list guard"
  - "compute_balance(session) — cacheless live SUM(amount_cents), 0 on empty ledger"
  - "6 unit tests in tests/test_finance.py proving balance correctness + write-path contract"
affects: [15-03, 15-04, 16-manual-cash-movements-history]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "finance.py mirrors ledger.py's shape exactly (next_seq / record_* / compute_*) but drops all stock-specific guards (no Product/Batch lookups) and has no cached projection — compute_balance is always a live SUM, per D-00b"

key-files:
  created:
    - app/services/finance.py
  modified:
    - tests/test_finance.py
    - .planning/phases/15-cash-ledger-foundation/deferred-items.md

key-decisions:
  - "record_cash_movement guards category BEFORE constructing the CashMovement row (raises ValueError, stages nothing) — mirrors ledger.py's type/product guards at the top of record_operation"
  - "compute_balance has NO WHERE clause by design — it is a whole-till balance, not a per-category or per-sale balance (D-00b, Pitfall 4)"

patterns-established:
  - "Cash write path: single service function stamps device_id/seq/created_at/created_by from settings, exactly like the stock ledger — any future manual-movement or report code must go through record_cash_movement/compute_balance, never a raw insert or cached column"

requirements-completed: [FIN-01, FIN-02, FIN-06]

# Metrics
duration: 10min
completed: 2026-07-14
---

# Phase 15 Plan 02: Cash Ledger Write Path Summary

**`app/services/finance.py` created as the single write path for `cash_movements` — audit-stamped inserts, per-device seq, a server-side `CASH_CATEGORIES` allow-list, and a cacheless live-`SUM()` balance — proven by 6 passing unit tests.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `app/services/finance.py` created as a sibling module of `ledger.py`: `next_seq` (per-device max+1, mirrors `ledger.next_seq`), `record_cash_movement` (guards `category` against `CASH_CATEGORIES` before staging, stamps `device_id`/`seq`/`created_at`/`created_by` from `settings`, supports `commit=False` staging), `compute_balance` (`SELECT COALESCE(SUM(amount_cents), 0)`, no WHERE, no cache).
- `tests/test_finance.py` extended with 4 new tests (on top of Plan 01's 2 append-only tests): `test_balance_empty_is_zero`, `test_balance_sums_mixed` (asserts exactly `7500` from `+12500`/`-5000`), `test_contract_stamps_audit_and_seq` (audit stamps + seq 1→2→`next_seq`==3), `test_contract_unknown_category_raises` (ValueError + zero rows persisted after rollback).
- `uv run pytest tests/test_finance.py -x` → 6 passed.
- Full suite: `uv run pytest -q` → 568 passed, 1 pre-existing unrelated flake (see Deviations).

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/services/finance.py (single write path + live-SUM balance)** - `b3a8357` (feat)
2. **Task 2: Extend tests/test_finance.py with balance + contract tests** - `de7c4d5` (test)

**Plan metadata:** committed together with this SUMMARY (worktree mode — orchestrator merges).

## Files Created/Modified
- `app/services/finance.py` - `next_seq`, `record_cash_movement`, `compute_balance` — the sole cash write path
- `tests/test_finance.py` - added balance + write-path contract tests (4 new, 2 existing from Plan 01, 6 total)
- `.planning/phases/15-cash-ledger-foundation/deferred-items.md` - logged one pre-existing, unrelated full-suite test flake (see below)

## Decisions Made
Followed plan exactly for the module shape, guard order, and query pattern. No architectural deviations.

## Deviations from Plan

None - plan executed exactly as written. (One pre-existing, out-of-scope issue was logged, not fixed — see Issues Encountered.)

## Issues Encountered

**Pre-existing test-isolation flake, logged, NOT fixed (out of scope):** `uv run pytest -q` (full suite) reported `1 failed, 568 passed` — `tests/test_mobile_sales.py::test_batch_step_shows_per_card_warehouse_when_batches_span_two_warehouses` failed. Re-ran that single test in isolation (`uv run pytest tests/test_mobile_sales.py::test_batch_step_shows_per_card_warehouse_when_batches_span_two_warehouses -q`) → `1 passed`, confirming a test-order/state-leak flake in an unrelated file, not caused by `finance.py`/`test_finance.py` changes. Logged to `.planning/phases/15-cash-ledger-foundation/deferred-items.md` per the deviation Scope Boundary rule (pre-existing issue in an unrelated file, out of scope for this plan). This plan's own acceptance criterion (`tests/test_finance.py -x` green) is unaffected and passes cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `finance.record_cash_movement`/`compute_balance` are importable and proven correct — Plan 03 (auto-credit on sale / auto-debit on return hooks, per FIN-01/FIN-02) and Plan 04 (balance display, FIN-06) can now build directly on this service.
- No blockers. One unrelated pre-existing test-isolation flake noted above for future investigation (does not block this phase).

## Self-Check: PASSED

All created/modified files verified present on disk; both commit hashes (`b3a8357`, `de7c4d5`) verified present in `git log --oneline --all`.

---
*Phase: 15-cash-ledger-foundation*
*Completed: 2026-07-14*
