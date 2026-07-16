---
phase: 20-warehouses-batch-split-transfers
plan: 05
subsystem: api
tags: [fastapi, sqlalchemy, transfers, writeoffs, security-hardening]

# Dependency graph
requires:
  - phase: 20-warehouses-batch-split-transfers (plan 04)
    provides: register_transfer's new_expiry/new_comment Form contract and result["qty"] return shape
provides:
  - "/transfers accepts a same-warehouse destination end-to-end via raw form POST (new_expiry/new_comment fields wired to register_transfer)"
  - "transfers_create and writeoff_create both re-validate batch_id ownership before echoing selected_batch, closing the WR-01 debt in both files"
  - "/transfers success message reports the real transferred integer quantity"
affects: [20-07 (transfer_form.html template UI for the new override fields)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Route-level batch-ownership re-validation: resolve product by code, then only accept a client-submitted batch_id as selected_batch if candidate.product_id == product.id — now applied uniformly in transfers_batch_pick/transfers_create and writeoff_batch_pick/writeoff_create"

key-files:
  created: []
  modified:
    - app/routes/transfers.py
    - app/routes/writeoffs.py
    - tests/test_transfers.py
    - tests/test_writeoffs.py

key-decisions:
  - "D-09 dest-warehouse comment cleanup: updated stale docstring/comment in transfers.py (_dest_warehouses and transfers_batch_pick) that described the old source-exclusion behavior, since D-09 makes that description false"

patterns-established:
  - "Ownership-guard port: the 4-line ownership-check pattern first proven in each file's own GET batch-pick endpoint is now reused verbatim in the POST create endpoint's selected_batch resolution"

requirements-completed: [XFER-01]

# Metrics
duration: 9min
completed: 2026-07-16
---

# Phase 20 Plan 05: Wire /transfers and /writeoff to D-09/D-10/D-11 fixes Summary

**Desktop /transfers now accepts a same-warehouse destination plus expiry/comment overrides end-to-end via raw form POST, and both /transfers and /writeoff never echo a foreign batch into the picker on an error re-render.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-16T18:40:27+02:00
- **Completed:** 2026-07-16T18:49:33+02:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `_dest_warehouses` no longer excludes the source batch's own warehouse (D-09) — the destination `<select>` on `/transfers` now includes it
- `transfers_create` accepts `new_expiry`/`new_comment` Form fields and forwards them to `register_transfer`, making a same-warehouse batch split reachable end-to-end via a raw form POST (D-05), ahead of the template UI (Plan 20-07)
- `transfers_create` and `writeoff_create` both port the proven batch-ownership guard from their sibling GET batch-pick endpoints — a client-submitted `batch_id` naming another product's batch is never echoed back (D-10), closing both halves of the pre-flagged WR-01 debt (STATE.md, 2026-07-13)
- `/transfers` success message now shows `result["qty"]` (the parsed integer) instead of the raw form string (D-11)

## Task Commits

Each task was committed atomically:

1. **Task 1: transfers.py — D-09/D-10/D-11 + override Form params** - `ff3fb72` (feat)
2. **Task 2: writeoffs.py — D-10 ownership guard port** - `b2f5d2b` (fix)

**Plan metadata:** SUMMARY commit (this file)

## Files Created/Modified
- `app/routes/transfers.py` - `_dest_warehouses` no longer filters by source warehouse; `transfers_create` gained `new_expiry`/`new_comment` Form params forwarded to `register_transfer`, an ownership-validated `selected_batch` resolution, and a fixed qty echo in the success context
- `app/routes/writeoffs.py` - `writeoff_create`'s `selected_batch` resolution now re-validates ownership the same way `writeoff_batch_pick` does
- `tests/test_transfers.py` - renamed/rewrote the dest-exclusion test to assert inclusion (D-09); added ownership-guard, qty-echo regression, same-warehouse-success, and same-warehouse-blank-error route-level tests
- `tests/test_writeoffs.py` - added a route-level ownership-guard test mirroring the transfers.py one

## Decisions Made
- Updated two stale in-code comments describing the pre-D-09 "minus the source warehouse" behavior (the `_dest_warehouses` docstring and a comment in `transfers_batch_pick`) so the code no longer documents a lie — same-file cleanup directly required by the D-09 change, not a separate architectural decision.

## Deviations from Plan

None - plan executed exactly as written. The two comment-text updates above were already explicitly called for in the plan's Task 1 action (docstring correction) or are the same class of same-line cleanup, not new scope.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 20-07 can now build the `<input>` elements for `new_expiry`/`new_comment` and the widened destination-warehouse `<select>` directly against this route contract — the route-level TestClient tests in this plan already prove the fields work via raw form-encoded field names, independent of the rendered markup.
- Full test suite (`uv run pytest -q`) passes: 737 passed, 0 failed.
- No blockers.

---
*Phase: 20-warehouses-batch-split-transfers*
*Completed: 2026-07-16*

## Self-Check: PASSED

All files (app/routes/transfers.py, app/routes/writeoffs.py, tests/test_transfers.py,
tests/test_writeoffs.py, this SUMMARY.md) confirmed present on disk. All task commits
(ff3fb72, b2f5d2b) and this summary's commit (f23f97b) confirmed present in git log.
