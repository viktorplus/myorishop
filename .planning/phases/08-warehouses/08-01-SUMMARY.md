---
phase: 08-warehouses
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, sqlite, warehouse, crud]

# Dependency graph
requires:
  - phase: 07-category-browsing-minimum-price-guardrail
    provides: Product/Dictionary/Customer model conventions and the sales.py warn-but-allow confirm-gate pattern this plan reuses
provides:
  - Warehouse SQLAlchemy model (id/name/address/created_at/updated_at/deleted_at)
  - Migration 0007 creating the standalone warehouses table with one frozen seed row (DEFAULT_WAREHOUSE_ID 00000000-0000-4000-8000-000000000010, "Склад по умолчанию")
  - app/services/warehouses.py: list_warehouses, add_warehouse, update_warehouse, restore_warehouse, soft_delete_warehouse
  - Last-active-warehouse warn-but-allow delete guard (confirm=True bypass)
affects: [08-02 (wires this service to /warehouses routes), 09-batch-tracking (Batch.warehouse_id FK, legacy-batch migration points at DEFAULT_WAREHOUSE_ID)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Warn-but-allow single-row delete guard: read-only active-count check before any write, confirm flag bypasses"
    - "list_warehouses never filters deleted_at (D-09) — deleted rows stay visible to callers, unlike every other soft-deletable entity in this app"

key-files:
  created:
    - app/services/warehouses.py
    - alembic/versions/0007_warehouses.py
    - tests/test_warehouses.py
  modified:
    - app/models.py

key-decisions:
  - "DEFAULT_WAREHOUSE_ID frozen as 00000000-0000-4000-8000-000000000010, name \"Склад по умолчанию\" — Phase 9's legacy-batch migration must reference this same literal (D-03)"
  - "No unique constraint on Warehouse.name (D-04) — duplicate names are allowed, unlike Dictionary's uq_dictionary_code"

patterns-established:
  - "Pattern 3 (warn-but-allow single-row delete): soft_delete_warehouse computes active_count before any write, returns (False, {\"warehouse\": w}) with zero writes when confirm is falsy and the target is the last active row"

requirements-completed: [WH-01]

# Metrics
duration: 5min
completed: 2026-07-11
---

# Phase 8 Plan 01: Warehouse Model, Migration, and Service Layer Summary

**Standalone `Warehouse` model + migration 0007 (frozen seed row) and a full CRUD service layer with a warn-but-allow guard blocking deletion of the last active warehouse.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-11T03:42:58+02:00
- **Completed:** 2026-07-11T03:47:25+02:00
- **Tasks:** 2 completed
- **Files modified:** 4 (1 modified, 3 created)

## Accomplishments
- `Warehouse` model added to `app/models.py` as a standalone table (no FK to `Product`/`Operation`, per D-01/D-02) with the same soft-delete/timestamp shape as `Product`/`Customer`
- Migration `0007_warehouses.py` creates the table and seeds exactly one frozen default row that Phase 9's legacy-batch migration can rely on (D-03)
- `app/services/warehouses.py` implements list/add/update/restore plus a warn-but-allow last-active-warehouse delete guard (D-06/D-07) with zero writes on the blocked path
- `list_warehouses` deliberately never filters `deleted_at` (D-09), matching this entity's "always visible, restorable" management-page requirement — verified by a dedicated test and a grep-count acceptance check

## Task Commits

Each task followed RED -> GREEN (TDD):

1. **Task 1: Warehouse model + migration 0007 (schema, frozen seed)**
   - `a01dcdc` (test) - add failing migration test
   - `e4bd602` (feat) - Warehouse model + migration 0007
2. **Task 2: Warehouse service layer (CRUD + warn-but-allow last-warehouse guard)**
   - `f9a958a` (test) - add failing service tests
   - `8170e06` (feat) - implement warehouse service layer

_No refactor commits needed — implementation matched the verified research pattern with no cleanup required._

## Files Created/Modified
- `app/models.py` - added `class Warehouse(Base)` (standalone table, no FK wiring)
- `alembic/versions/0007_warehouses.py` - creates `warehouses` table, seeds `DEFAULT_WAREHOUSE_ID` row; frozen literals only, no app imports (WR-06)
- `app/services/warehouses.py` - `list_warehouses`, `add_warehouse`, `update_warehouse`, `restore_warehouse`, `soft_delete_warehouse`, error constants `NAME_REQUIRED_ERROR`/`WAREHOUSE_NOT_FOUND_ERROR`
- `tests/test_warehouses.py` - migration test + 8 service tests (create/validate/duplicate-names/edit/unknown-id/soft-delete-restore-roundtrip/last-active-guard/idempotent-restore)

## Decisions Made
- Followed the RESEARCH.md-provided code exactly (model, migration, service) — no deviations were needed since the reference implementation was already verified against this codebase's conventions.
- `address` chosen as the optional field name (RESEARCH.md's own recommendation over `note`).

## Deviations from Plan

None - plan executed exactly as written. Only a single ruff auto-formatting fix (import sort order in the test file) was applied, which is not a deviation from planned behavior.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 08-02 can now wire `app/services/warehouses.py` to `/warehouses` routes and templates (D-08/D-09/D-10 UI behavior) — the full backend CRUD + guard contract is in place and tested.
- Phase 9's `Batch` migration can reference `DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"` for its legacy-batch default (D-03) — this value is now frozen and documented in `alembic/versions/0007_warehouses.py`.
- Full test suite (256 tests) green; `uv run ruff check` clean on all modified/created files.

---
*Phase: 08-warehouses*
*Completed: 2026-07-11*

## Self-Check: PASSED

All created files verified present on disk; all task/summary commits verified present in git log.
