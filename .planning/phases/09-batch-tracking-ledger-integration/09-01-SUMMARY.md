---
phase: 09-batch-tracking-ledger-integration
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, sqlite, batch-tracking, ledger, migration, tdd]

# Dependency graph
requires:
  - phase: 08-warehouses
    provides: "warehouses table + frozen DEFAULT_WAREHOUSE_ID seed (legacy-batch target)"
  - phase: 01-foundation
    provides: "append-only operations ledger, record_operation single write path, append-only triggers"
provides:
  - "Batch model (batches table): product x warehouse x lot stock-holding unit, cached quantity, is_legacy marker, no soft-delete (D-03)"
  - "Operation.batch_id nullable ORM FK (fk_operations_batch_id_batches) — the ledger→lot link (D-10)"
  - "Alembic migration 0008: batches table, native operations.batch_id, per-product legacy-batch seed from the ledger SUM (D-13/D-14)"
  - "app/services/batches.py read helpers: open_batches (D-07 order), legacy_batch, active_warehouses"
  - "record_operation batch_id param: dual quantity projection + ownership guard (D-11/D-12 backstop)"
  - "compute_batch_stock + rebuild_stock per-batch invariant with NULL-bucket legacy absorption"
  - "format_ru_date + ru_date Jinja filter (ISO -> dd.mm.yyyy) for every batch surface"
  - "conftest warehouse/batch fixtures + batch-consistent stocked_product"
affects: [receipts, sales, writeoffs, corrections, returns, history, batch-picker-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual cached projection in the single write path (Product.quantity + Batch.quantity, SQL-side increment, same transaction)"
    - "Native op.add_column for operations schema changes (never batch/move-and-copy — preserves append-only triggers)"
    - "Plain-SQL ledger-derived migration seed (never the products.quantity cache)"
    - "Ledger-derivable per-batch quantity with is_legacy NULL-bucket absorption"

key-files:
  created:
    - "app/services/batches.py"
    - "alembic/versions/0008_batches.py"
    - "tests/test_batches.py"
  modified:
    - "app/models.py"
    - "app/core.py"
    - "app/services/ledger.py"
    - "app/routes/__init__.py"
    - "tests/conftest.py"

key-decisions:
  - "batch_id kept OPTIONAL this plan (default None) — the mandatory D-12 guard is deferred to Plan 05 so the suite stays green at every wave boundary (RESEARCH Pitfall 1)"
  - "Legacy-batch seed reads SUM(operations.qty_delta) in plain SQL, never products.quantity (D-13, criterion-5 safe against a stale cache)"
  - "uuid5(_LEGACY_NS, product_id) for replay-deterministic legacy-batch ids"
  - "nullslast(Batch.expiry.asc()) for portable NULLS-LAST ordering (D-07)"

patterns-established:
  - "Dual projection: record_operation increments both product and batch caches in one transaction"
  - "rebuild_stock per-product invariant: Product.quantity == SUM(batch quantities) + uncaptured NULL bucket (only for products with no legacy batch)"

requirements-completed: [LOT-01, LOT-03]

# Metrics
duration: ~35 min
completed: 2026-07-12
---

# Phase 9 Plan 01: Batch Write-Path Foundation Summary

**Batch model + Alembic 0008 (batches table, native operations.batch_id, ledger-seeded legacy batches) with a batch-aware record_operation dual projection and a rebuild_stock per-batch invariant — full 278-test suite green.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-07-12
- **Tasks:** 3 (all TDD: RED → GREEN)
- **Files modified:** 8 (3 created, 5 modified)

## Accomplishments
- `Batch` stock-holding model (no `deleted_at`, D-03) plus nullable `Operation.batch_id` ORM FK — the ledger→lot link.
- Migration `0008` creates the `batches` table and adds `operations.batch_id` via native `op.add_column` (append-only triggers preserved), then seeds one legacy batch per SUM>0 product from the ledger, never the cache (D-13/D-14). Reversible downgrade verified.
- `record_operation` now threads an optional `batch_id`: dual quantity projection (D-11) with the T-09 ownership guard, while staying optional so every existing call site keeps working.
- `rebuild_stock` gained a per-batch pass + per-product invariant with NULL-bucket legacy absorption; `open_batches`/`legacy_batch`/`active_warehouses` read helpers and the `ru_date` display filter shipped.

## Task Commits

Each task was executed TDD (RED test commit → GREEN implementation commit):

1. **Task 1: Batch model, Operation.batch_id, batches.py helpers, ru_date**
   - `12ab79b` (test) → `0d8e029` (feat)
2. **Task 2: Migration 0008 (batches, operations.batch_id, legacy seed) + replay test**
   - `5e13354` (test) → `5f320c0` (feat)
3. **Task 3: record_operation dual projection + rebuild_stock invariant + conftest sweep**
   - `e984b3a` (test) → `bd7ca4c` (feat)

## Files Created/Modified
- `app/models.py` — `Batch` model (no `deleted_at`); `Operation.batch_id` nullable FK `fk_operations_batch_id_batches`.
- `app/core.py` — `format_ru_date(iso)` ISO→dd.mm.yyyy helper.
- `app/routes/__init__.py` — registered the `ru_date` Jinja filter.
- `app/services/batches.py` (new) — `open_batches` (D-07 order), `legacy_batch`, `active_warehouses`.
- `app/services/ledger.py` — `record_operation` `batch_id` param + dual projection + ownership guard; `compute_batch_stock`; `rebuild_stock` per-batch invariant.
- `alembic/versions/0008_batches.py` (new) — batches table, native `operations.batch_id`, ledger-derived legacy seed; reversible downgrade.
- `tests/conftest.py` — `warehouse`/`batch` fixtures; batch-consistent `stocked_product`.
- `tests/test_batches.py` (new) — model, ordering, ru_date, migration replay/downgrade, dual projection, ownership guard, rebuild invariant.

## Decisions Made
- **batch_id stays optional this plan.** Per RESEARCH Pitfall 1, splitting the mandatory D-12 guard from its callers would turn the whole suite red for a wave. The ownership guard (unknown/foreign batch → `ValueError`) is active whenever a `batch_id` is supplied; the mandatory-when-missing + audit-type rejection is Plan 05's flip.
- **Legacy seed from the ledger, not the cache** (D-13) — `SUM(qty_delta) GROUP BY product_id HAVING SUM > 0`, guaranteeing criterion-5 balance even against a stale `products.quantity`.
- **`uuid5` deterministic legacy ids** keyed on `product_id` for replay reproducibility.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the trigger-abort exception type in the migration-replay test**
- **Found during:** Task 2 (migration replay test)
- **Issue:** The test expected `sqlite3.OperationalError` from the append-only `UPDATE` trigger, but `RAISE(ABORT, ...)` surfaces as `sqlite3.IntegrityError` through the raw sqlite3 driver.
- **Fix:** Changed the `pytest.raises(...)` expectation to `sqlite3.IntegrityError` (message assertion `"append-only"` unchanged).
- **Files modified:** tests/test_batches.py
- **Verification:** `uv run pytest tests/test_batches.py -k migration -q` → 2 passed.
- **Committed in:** `5f320c0` (Task 2 GREEN commit)

**2. [Rule 3 - Blocking] Reworded migration docstring to satisfy the `batch_alter_table`-count acceptance gate**
- **Found during:** Task 2 (acceptance criterion `grep -c "batch_alter_table" == 0`)
- **Issue:** The docstring's cautionary phrase literally contained `batch_alter_table("operations")`, making the grep return 1.
- **Fix:** Reworded to "NEVER an Alembic batch/move-and-copy rebuild of the operations table" — same warning, no literal token.
- **Files modified:** alembic/versions/0008_batches.py
- **Verification:** `grep -c "batch_alter_table"` now returns 0; migration still uses native `op.add_column`.
- **Committed in:** `5f320c0` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 test bug, 1 blocking acceptance-gate wording).
**Impact on plan:** Both fixes were test/doc-level corrections needed for the acceptance gates to pass; production behaviour matches the plan exactly. No scope creep.

## Deferred Issues
Pre-existing ruff lint errors in files this plan did NOT touch (out of scope per the scope boundary): `I001` import-sort in `tests/test_backup.py`, `tests/test_corrections.py`, `tests/test_customers.py`, `tests/test_sales.py`, `tests/test_writeoffs.py`, and `E501` line-length in `tests/test_export.py`. All files this plan created/modified pass `ruff check` clean. The plan-level `ruff check .` gate is therefore red only for pre-existing debt unrelated to batch tracking — recommend a separate lint-cleanup task.

## Known Stubs
None — every artifact is wired and exercised by tests. `Batch.price_cents`/`location`/`comment` are intentionally nullable (populated by the receipt flow in Plan 02, per D-02); the write path and helpers are fully functional.

## Threat Flags
None — no new network endpoints or trust boundaries introduced. The T-09-01 tampering mitigation (batch↔product ownership guard) is implemented; T-09-02 (native add_column, trigger survival) is asserted by the replay test.

## Issues Encountered
None beyond the two auto-fixed deviations above. The live dev DB (`data/myorishop.db`) is not present in the worktree, so the "scratch copy of a seeded DB" reversibility check was satisfied via the temp-DB replay/downgrade tests plus a fresh upgrade→downgrade→upgrade cycle (both green).

## Next Phase Readiness
- Schema is at Alembic head `0008`; `record_operation` is batch-aware; batch quantities are ledger-derivable. Ready for Plan 02 (receipt batch birth path).
- Plan 05 must flip the mandatory D-12 guard (batch_id required for stock-affecting types + audit-type rejection) once every operation service passes a batch.

## Self-Check: PASSED
- All 8 key files present on disk (verified with `[ -f ]`).
- All 6 task commits present in `git log` (3 RED test + 3 GREEN feat).
- `uv run pytest -q` → 278 passed. Migration reversibility verified. `ruff check` clean on all plan files.

---
*Phase: 09-batch-tracking-ledger-integration*
*Completed: 2026-07-12*
