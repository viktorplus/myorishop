---
phase: 14-list-pagination-filtering-sorting-quick-delete
plan: 05
subsystem: ui
tags: [fastapi, sqlalchemy, jinja2, htmx, pagination, filtering, sorting, soft-delete]

# Dependency graph
requires:
  - phase: 14-01
    provides: "LIST_PAGE_SIZE / page_window() / paginate() in app/services/pagination.py, partials/pagination.html"
provides:
  - "list_warehouses(session, *, name, address, status, sort, page) -> dict — filtered/sorted/paginated warehouse list, hides deleted rows by default (D-14)"
  - "soft_delete_warehouse() D-11 stock guard (SUM of Batch.quantity per warehouse) that runs before the existing D-12 last-active guard, non-overridable by confirm=1"
  - "/warehouses header-row filters (name/address/status) + sort dropdown + numbered pagination, one swappable #warehouse-rows block"
  - "status=deleted / status=all filter as the resolved restore path for quick-deleted warehouses (restore_warehouse/POST /warehouses/{id}/restore reused unchanged)"
affects: [products-list, customers-list, dictionary-list, catalogs-list, history-list]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "list_warehouses() returns a dict {warehouses, total, total_pages, page, name, address, status, sort} instead of a bare list — mirrors the shape other Phase 14 list services use"
    - "_warehouses_context() route helper centralizes the list_warehouses() call + page_window + extra_qs querystring building, shared by all 5 route handlers (GET list, POST add/update/delete/restore)"
    - "Hard, non-overridable guard (D-11 stock check) placed before a soft, warn-then-confirm guard (D-12 last-active) in the same service function — confirm=1 only bypasses the soft guard"

key-files:
  created: []
  modified:
    - app/services/warehouses.py
    - app/routes/warehouses.py
    - app/templates/partials/warehouse_rows.html
    - tests/test_warehouses.py

key-decisions:
  - "Resolved 14-CONTEXT.md's open question: the restore path for quick-deleted warehouses is the status=Удалённые filter (not a separate toggle) — reuses the existing untouched restore_warehouse service and POST /warehouses/{id}/restore route"
  - "Stock guard checked via SUM(Batch.quantity) WHERE warehouse_id=..., not Product.quantity (which is a GLOBAL total across all warehouses and cannot be reused per-warehouse)"
  - "No new route added — POST /warehouses/{id}/delete stays the single quick-delete endpoint; its context now carries both stock_blocked_id/stock_blocked_qty (D-11) and the existing warning_id (D-12) keys"

patterns-established:
  - "Stock-guard hard-block error row (.error, no confirm-override button) rendered as a sibling <tr> immediately after the blocked row, mutually exclusive with the existing last-active warn-then-confirm <tr> since the stock guard runs first"

requirements-completed: [LIST-01, LIST-02, LIST-03, LIST-04]

# Metrics
duration: 8min
completed: 2026-07-14
---

# Phase 14 Plan 05: Warehouse Pagination, Filtering, Sorting & Quick Delete Summary

**`/warehouses` gains header-row name/address/status filters, a sort dropdown, numbered pagination, and a per-warehouse stock quick-delete guard that runs before the existing last-active-warehouse guard — quick-deleted warehouses now disappear from the default view and are reachable only via `status=Удалённые`.**

## Performance

- **Duration:** ~8 min (first commit 05:00:15+02:00, last commit 05:07:57+02:00)
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- `list_warehouses()` now accepts `name`/`address`/`status`/`sort`/`page` and returns a paginated dict; the default view hides soft-deleted rows for the first time (superseding the old "D-09: never filter deleted_at" convention), reachable again via `status=deleted`/`status=all`
- `soft_delete_warehouse()` gained a new, non-overridable D-11 stock guard (`SUM(Batch.quantity)` per warehouse) that runs BEFORE the existing warn-then-confirm last-active-warehouse guard — both guards apply together, neither replaces the other (D-12)
- `GET /warehouses` wired with query params + an `is_hx` dual-response branch (mirrors `app/routes/history.py`); `POST /warehouses/{id}/delete` context now carries both `stock_blocked_id`/`stock_blocked_qty` and the existing `warning_id`
- `partials/warehouse_rows.html` renders one swappable block: sort dropdown, header-row filter cells (name/address text inputs + status select), the D-11 stock-guard inline error, and the shared `partials/pagination.html` include

## Task Commits

Each task was committed atomically (Task 1 followed the RED/GREEN TDD cycle):

1. **Task 1 RED: failing tests for filter/sort/status/page + D-11 stock guard** - `5f1f396` (test)
2. **Task 1 GREEN: list_warehouses filter/sort/status/page + D-11 stock guard** - `7fbbcde` (feat)
3. **Task 2: route wiring — filter/sort/status/page + stock-guard context** - `a209c60` (feat)
4. **Task 3: header-row filters + sort dropdown + pagination + stock-guard error** - `7adb297` (feat)

_Note: Task 1 is `tdd="true"` — RED then GREEN commits, no REFACTOR needed._

## Files Created/Modified
- `app/services/warehouses.py` - `list_warehouses()` signature/return shape changed to a filtered/sorted/paginated dict; `soft_delete_warehouse()` gained the D-11 stock guard ahead of the existing D-12 guard
- `app/routes/warehouses.py` - new `_warehouses_context()` helper; `GET /warehouses` accepts filter/sort/status/page query params and branches on `HX-Request`; `warehouse_delete` context carries the new stock-blocked keys
- `app/templates/partials/warehouse_rows.html` - sort `.filter-bar`, `<tr class="filter-row">` (name/address/status), D-11 stock-guard error row, `{% include "partials/pagination.html" %}`, filtered-to-zero empty state
- `tests/test_warehouses.py` - updated `test_soft_delete_and_restore_roundtrip` for the new default; added 6 new service tests + 4 new/rewritten route tests

## Decisions Made
- The restore path for a quick-deleted warehouse is the `status=Удалённые` filter — no new toggle/route needed, `restore_warehouse`/`POST /warehouses/{id}/restore` reused completely unchanged. This resolves the explicitly-flagged open question in `14-CONTEXT.md` / `14-UI-SPEC.md` Contract E.
- Stock is computed per-warehouse via `SUM(Batch.quantity) WHERE warehouse_id = ...`, not via `Product.quantity` (a global total across all warehouses, confirmed unusable here by the model's own docstring).
- The existing per-row `{% if not w.deleted_at %}Удалить{% else %}Восстановить{% endif %}` template branch needed NO condition change — filtering now happens at the query level (`status` param), so `warehouses` only ever contains rows matching the active filter already.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `list_warehouses()`'s new dict-return shape and `_warehouses_context()` helper pattern are directly reusable as a template for any remaining Phase 14 list plans (customers, dictionary, catalogs) that haven't yet landed pagination/filter/sort.
- Full project test suite (528 tests) passes with these changes; no regressions in dependent modules (transfers, batch pickers, receipts, etc. that reference warehouses).
- No blockers for subsequent Phase 14 plans — this plan's only dependency was 14-01 (pagination helper + partial), which is already merged.

---
*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Completed: 2026-07-14*
