---
phase: 20-warehouses-batch-split-transfers
plan: 01
subsystem: database
tags: [sqlalchemy, aggregate-query, outerjoin, warehouses]

# Dependency graph
requires:
  - phase: 14-list-pagination-filter-sort
    provides: list_warehouses() filter/sort/pagination shape (D-07, D-14) this plan appends to
  - phase: 9-batches
    provides: Batch/Operation.batch_id model shape this plan's queries join against
provides:
  - "list_warehouses() rows carry .item_count (distinct-product count, quantity>0) via one grouped query per page"
  - "list_warehouses() rows carry .last_receipt (max receipt-type Operation.created_at) via one grouped outerjoin query per page"
affects: [20-02, 20-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Page-wide grouped aggregate query appended after paginate(), keyed by warehouse_id.in_(page_rows ids) — no per-row query in the existing filter/sort loop"
    - "outerjoin + func.max/group_by for 'latest matching event, else None' aggregates (mirrors app/services/reports.py::stale_products)"

key-files:
  created: []
  modified:
    - app/services/warehouses.py
    - tests/test_warehouses.py

key-decisions:
  - "Both new attributes (item_count, last_receipt) are plain dynamic ORM-instance attributes set after paginate(), never mapped columns — no schema change, no flush risk"
  - "last_receipt query uses outerjoin (not join) so a warehouse whose batches have zero receipt-type Operations — e.g. a transfer-only destination — still returns a row with last_receipt=None instead of being silently dropped"

patterns-established:
  - "Page-wide grouped query for list-page metrics: compute ids from already-paginated page_rows, one session.execute(select(...).where(id.in_(ids)).group_by(...)), dict(rows) lookup, then a plain for-loop attribute assignment"

requirements-completed: [WH-01]

# Metrics
duration: 13min
completed: 2026-07-16
---

# Phase 20 Plan 01: Warehouse List Item-Count and Last-Receipt Aggregates Summary

**`list_warehouses()` now returns `.item_count` and `.last_receipt` per warehouse row via two page-wide grouped queries (distinct-product count and outerjoin max receipt date), with zero per-row queries added to the existing filter/sort/paginate logic.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-16T18:07:22+02:00
- **Completed:** 2026-07-16T18:20:17+02:00
- **Tasks:** 2 (TDD: RED, then GREEN x2)
- **Files modified:** 2

## Accomplishments
- D-03: `list_warehouses()` computes `.item_count` — count of distinct products with `quantity > 0` per warehouse — via one grouped `select(Batch.warehouse_id, func.count(func.distinct(Batch.product_id)))` query for the whole page.
- D-04: `list_warehouses()` computes `.last_receipt` — the latest `created_at` among `type == "receipt"` Operations — via one grouped `outerjoin` query, correctly returning `None` (not dropping the row) for warehouses with zero batches or zero receipt-type operations (including transfer-only destinations).
- Both queries scoped by `Batch.warehouse_id.in_(warehouse_ids)` derived from the already-filtered/paginated `page_rows` — no new query parameter, no new IDOR surface (per threat register T-20-01).

## Task Commits

Each task was committed atomically (TDD RED/GREEN cycle):

1. **RED — failing tests for both D-03 and D-04** - `3903164` (test)
2. **Task 1: D-03 item_count** - `786760f` (feat)
3. **Task 2: D-04 last_receipt** - `779ba6e` (feat)

**Plan metadata:** committed separately after this summary (docs: complete plan)

## Files Created/Modified
- `app/services/warehouses.py` - `list_warehouses()` gained two grouped-query blocks after `paginate()`: item_count (D-03) and last_receipt (D-04, outerjoin); `Operation` added to the `app.models` import (`Batch` was already imported)
- `tests/test_warehouses.py` - 6 new service-level tests (3 item_count, 3 last_receipt) plus `Batch`, `Operation`, `Product`, `new_id`, `next_seq` imports

## Decisions Made
- No deviations from the plan's exact query shapes — action blocks specified the `select(...)`/`outerjoin(...)` statements almost verbatim; implementation matched them directly.
- Test data for Operation rows follows the established direct-insert pattern from `tests/test_batches.py`/`tests/test_history.py` (raw `Operation(...)` + `next_seq()` + `settings.device_id`), not `record_operation()`, since these tests only need read-side ledger rows at specific `created_at` values.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `list_warehouses()`'s `.item_count`/`.last_receipt` attributes are ready for the route/template consumers in plans 20-02/20-03 (per this plan's stated scope: data layer only).
- Full test suite green: `uv run pytest -q` → 726 passed. `tests/test_warehouses.py tests/test_transfers.py -q` → 47 passed. Ruff clean on both modified files.
- No blockers for downstream plans in this phase.

## TDD Gate Compliance

RED (`3903164`, `test(...)`) → GREEN (`786760f`, `779ba6e`, both `feat(...)`) gate sequence confirmed in git log. No REFACTOR commit needed (implementation matched the planned shape with no follow-up cleanup).

---
*Phase: 20-warehouses-batch-split-transfers*
*Completed: 2026-07-16*
