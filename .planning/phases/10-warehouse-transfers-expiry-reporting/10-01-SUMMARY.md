---
phase: 10-warehouse-transfers-expiry-reporting
plan: 01
subsystem: inventory
tags: [sqlalchemy, ledger, warehouse-transfer, batches]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration
    provides: Batch model, record_operation batch_id enforcement (STOCK_AFFECTING_TYPES), active_warehouses/open_batches helpers
provides:
  - "transfer" operation type registered across OPERATION_TYPES, OPERATION_TYPE_LABELS, STOCK_AFFECTING_TYPES
  - app/services/transfers.py — register_transfer() + recent_transfers()
  - tests/test_transfers.py — WH-03 service-level unit suite (10 tests)
affects: [10-02 (route/UI wiring), 10-03 (expiry reporting, unaffected but same phase)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["two-row transfer via record_operation(commit=False) x2 + one commit", "destination batch inherits frozen price_cents/expiry/comment/location/name"]

key-files:
  created:
    - app/services/transfers.py
    - tests/test_transfers.py
  modified:
    - app/models.py
    - app/services/ledger.py

key-decisions:
  - "transfer op-type label is «Перемещение» per RESEARCH A2/D-04"
  - "over-qty confirm gate scoped to source BATCH quantity, never product.quantity (transfer nets to zero at product level)"
  - "destination batch price_cents copied via direct assignment (never `or`) so a legitimate 0-cent price survives"

patterns-established:
  - "Pattern: new stock-affecting operation types must be registered in THREE places at once (OPERATION_TYPES, OPERATION_TYPE_LABELS, STOCK_AFFECTING_TYPES) — Pitfall 1 backstop is a dedicated guard test"

requirements-completed: [WH-03]

# Metrics
duration: 25min
completed: 2026-07-12
---

# Phase 10 Plan 01: Transfer Service & Op-Type Registration Summary

**register_transfer() moves stock between warehouses through the existing single ledger write path, writing two paired `transfer` rows and creating a destination batch that inherits the source's frozen price_cents/expiry/comment/location — preserving cost/price history across the move.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-12T17:53:00Z
- **Completed:** 2026-07-12T18:11:00Z
- **Tasks:** 2 completed
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- Registered `"transfer"` in all three runtime collections (`OPERATION_TYPES`, `OPERATION_TYPE_LABELS`, `STOCK_AFFECTING_TYPES`) with a dedicated guard test backstopping the phase's one silent-failure trap (Pitfall 1)
- Implemented `register_transfer()`: validates code/qty/source-batch-ownership/dest-warehouse, gates over-quantity against the source batch (warn-but-allow, `confirm="1"`), creates a fresh destination batch inheriting cost/price history, and writes the paired ledger rows atomically
- Implemented `recent_transfers()` surfacing the outbound (negative qty_delta) row per transfer
- Full WH-03 service-level test suite (10 tests) green; no Alembic migration needed (`operations.type` is unconstrained `String(20)`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Register the "transfer" operation type** - `315700e` (feat)
2. **Task 2: register_transfer() + recent_transfers() service** - `78268b8` (test, RED) → `6f4d3fe` (feat, GREEN)

_TDD task 2 followed RED/GREEN: failing import-error collection confirmed before implementation existed, then full suite went green._

## Files Created/Modified
- `app/models.py` - added `"transfer"` to `OPERATION_TYPES` (after `"correction"`) and `"transfer": "Перемещение"` to `OPERATION_TYPE_LABELS`
- `app/services/ledger.py` - added `"transfer"` to `STOCK_AFFECTING_TYPES` frozenset
- `app/services/transfers.py` (NEW) - `register_transfer(session, *, code, name, qty_raw, batch_id="", dest_warehouse_id="", confirm="")` and `recent_transfers(session, limit=10)`; RU error constants `QTY_ERROR`, `BATCH_REQUIRED_ERROR`, `PRODUCT_NOT_FOUND_TMPL`, `WAREHOUSE_ERROR`, `SAME_WAREHOUSE_ERROR`, `SAVE_FAILED_ERROR`
- `tests/test_transfers.py` (NEW) - `test_transfer_type_registered` + 9 WH-03 service tests (two-row write, projections, dest inheritance incl. 0-cent price, full-empties-source, confirm gate, same-warehouse reject, tampered-id reject x2, rebuild invariant, recent_transfers listing) with inline `_second_warehouse`/`_source_batch` fixtures built on `conftest.py`'s `stocked_product`

## Decisions Made
- Followed PLAN.md and 10-PATTERNS.md exactly for the validation order, error constants, and two-row write shape (mirrors `writeoffs.py` + `receipts.py` precedents)
- `_source_batch` test helper builds a dedicated batch (rather than mutating `stocked_product`'s existing one) whenever a test needs a non-default price/expiry/comment/location, keeping fixture state predictable across tests

## Deviations from Plan

None - plan executed exactly as written. Ran `ruff check --fix` and `ruff format` on the two touched files after implementation to satisfy the plan's `<verification>` clause (`uv run ruff check app/services/transfers.py tests/test_transfers.py` clean) — this was import-sort/formatting only, no logic change.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`app/services/transfers.py` (`register_transfer`, `recent_transfers`) and the `"transfer"` op-type registration are ready for Plan 02 to wire the route (`app/routes/transfers.py`) and UI templates on top, per 10-PATTERNS.md. No blockers.

## TDD Gate Compliance

Verified in git log: `test(10-01): add failing WH-03 unit suite for register_transfer` (78268b8, RED) precedes `feat(10-01): implement register_transfer + recent_transfers (WH-03)` (6f4d3fe, GREEN). Gate sequence satisfied; no refactor commit was needed (implementation was clean on first pass, only ruff formatting applied before commit).

---
*Phase: 10-warehouse-transfers-expiry-reporting*
*Completed: 2026-07-12*
