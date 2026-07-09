---
phase: 04-sales-customers
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, sqlite, pytest, ledger, tdd-red-contract]

# Dependency graph
requires: []
provides:
  - "Customer and Sale models (app/models.py)"
  - "Operation.sale_id nullable column (bare, no DB FK — see decisions)"
  - "record_operation(..., sale_id=None) backward-compatible kwarg"
  - "Migration 0004: customers + sales tables, operations.sale_id"
  - "conftest fixtures: stocked_product (quantity=8), customer"
  - "Phase-wide RED test contract: tests/test_sales.py (22 tests), tests/test_customers.py (12 tests)"
  - "tests/test_ledger.py: sale_id + migration-0004 trigger-preservation tests (green)"
affects: [04-02, 04-03, 04-04, 04-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLite native ADD COLUMN cannot carry an inline FK constraint outside batch mode — bare column + ORM-level ForeignKey is the correct fallback when trigger preservation is required"

key-files:
  created:
    - alembic/versions/0004_sales_customers.py
    - tests/test_sales.py
    - tests/test_customers.py
    - .planning/phases/04-sales-customers/deferred-items.md
  modified:
    - app/models.py
    - app/services/ledger.py
    - tests/conftest.py
    - tests/test_ledger.py

key-decisions:
  - "operations.sale_id has NO database-level FK constraint (Alembic/SQLite cannot ALTER in an inline FK outside batch mode); the ORM ForeignKey on Operation.sale_id in models.py still gives Unit-of-Work insert ordering (Sale header before sale ops) and PostgreSQL portability — verified empirically by running alembic upgrade head against a fresh tmp database"
  - "tests/test_sales.py and tests/test_customers.py assert against the exact function signatures already locked in Plans 04-02/04-03/04-04 (register_sale(session, *, customer_id, codes, qtys, prices, confirm), create_customer/update_customer/search_customers/purchase_history) so later waves have a stable contract to implement against"

patterns-established:
  - "RED-by-design test modules: a whole test file can intentionally fail at collection (ModuleNotFoundError) when the module under test doesn't exist yet — pytest --co / pytest -q both report this as a clean 'red' signal without needing test stubs"

requirements-completed: [SAL-01, SAL-05]

# Metrics
duration: 15min
completed: 2026-07-09
---

# Phase 4 Plan 1: Sales & Customers Schema Foundation Summary

**Customer + Sale models, Operation.sale_id link column, record_operation(sale_id=) kwarg, migration 0004, and the phase-wide RED test contract for the sales/customers vertical slice.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-09T10:45:00Z (approx.)
- **Completed:** 2026-07-09T11:01:14Z
- **Tasks:** 3
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments

- Added `Customer` and `Sale` ORM models plus a nullable `Operation.sale_id` link column, mirroring the existing Product/Dictionary/Operation conventions (UUID PKs, UTC ISO timestamps, Cyrillic-safe `search_lc` shadow maintained in Python).
- Extended `record_operation` with a backward-compatible `sale_id` keyword, set at INSERT time only (the append-only trigger blocks any later UPDATE) — all 5 existing callers keep working untouched.
- Wrote migration `0004_sales_customers.py` creating `customers` + `sales` tables and a native `sale_id` column on `operations`; empirically verified (via a direct `alembic upgrade head` against a fresh tmp SQLite file) that the append-only triggers survive and no `_alembic_tmp_operations` rebuild occurs.
- Added `stocked_product` (ledger-backed quantity=8) and `customer` fixtures to `tests/conftest.py` for use by the rest of the phase.
- Authored the phase-wide RED contract: `tests/test_sales.py` (22 tests covering SAL-01..05, oversell aggregation, and the customer-picker web slice) and `tests/test_customers.py` (12 tests covering CST-01/02 CRUD, Cyrillic search, and frozen-price purchase history) — both intentionally fail at collection since `app.services.sales`/`app.services.customers` don't exist until later waves.
- Extended `tests/test_ledger.py` with `test_record_operation_sets_sale_id` and `test_migration_0004_preserves_append_only_triggers` — both green now.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add Customer + Sale models, Operation.sale_id, and the record_operation sale_id kwarg** - `ecdd275` (feat)
2. **Task 2: Migration 0004 (customers + sales + native operations.sale_id) and conftest fixtures** - `1c4d5af` (feat)
3. **Task 3: RED test contract — test_sales.py, test_customers.py, and extend test_ledger.py** - `0ae039a` (test)

_Note: this is a worktree execution; the plan-metadata commit (SUMMARY.md) is committed separately per the worktree protocol — STATE.md/ROADMAP.md are updated centrally by the orchestrator after merge._

## Files Created/Modified

- `app/models.py` - `Customer`, `Sale` model classes; `Operation.sale_id` nullable FK column
- `app/services/ledger.py` - `record_operation(..., sale_id: str | None = None)` kwarg, threaded into the `Operation(...)` constructor
- `alembic/versions/0004_sales_customers.py` - customers + sales tables, native (bare) `operations.sale_id` column, indexes
- `tests/conftest.py` - `stocked_product` and `customer` fixtures
- `tests/test_sales.py` - 22-test RED contract for SAL-01..05 (service + web slice)
- `tests/test_customers.py` - 12-test RED contract for CST-01/02 (service + web slice)
- `tests/test_ledger.py` - `test_record_operation_sets_sale_id`, `test_migration_0004_preserves_append_only_triggers`
- `.planning/phases/04-sales-customers/deferred-items.md` - log of pre-existing out-of-scope ruff findings

## Decisions Made

- **Bare `sale_id` column, no DB-level FK (RESEARCH A1 fallback applied):** the plan's primary approach (native `op.add_column` with an inline `ForeignKey`) was verified against a real `alembic upgrade head` run and failed with `NotImplementedError: No support for ALTER of constraints in SQLite dialect` — Alembic's SQLite dialect cannot add a column with a constraint outside batch mode. Applied the plan's documented fallback: a bare nullable column with no DB FK, keeping the ORM-level `ForeignKey` on `Operation.sale_id` for Unit-of-Work insert ordering and PostgreSQL portability. Verified append-only triggers survive and no table rebuild occurs.
- **Test contract signatures locked to later-wave plans:** rather than writing generic placeholder tests, `tests/test_sales.py`/`tests/test_customers.py` call the exact function signatures specified in Plans 04-02 (`register_sale(session, *, customer_id, codes, qtys, prices, confirm="")`) and 04-04 (`create_customer`, `update_customer`, `search_customers`, `purchase_history`), so those waves have an unambiguous, already-authored contract to satisfy.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Migration 0004's inline FK on `operations.sale_id` is not supported by Alembic's SQLite dialect outside batch mode**
- **Found during:** Task 2 (Migration 0004 + conftest fixtures)
- **Issue:** The plan's primary approach (`op.add_column("operations", sa.Column("sale_id", ..., sa.ForeignKey(...)))`) raised `NotImplementedError: No support for ALTER of constraints in SQLite dialect` when run against a real tmp SQLite database via `alembic upgrade head`.
- **Fix:** Applied the plan's own documented fallback (RESEARCH A1 / plan `<action>` FALLBACK note): a bare `sale_id` column with no DB-level FK, keeping the ORM `ForeignKey` in `app/models.py` for Unit-of-Work insert ordering + PostgreSQL portability. Re-verified the append-only triggers survive and no `_alembic_tmp_operations` table appears.
- **Files modified:** `alembic/versions/0004_sales_customers.py`
- **Verification:** `alembic upgrade head` against a fresh tmp SQLite file succeeds; `test_migration_0004_preserves_append_only_triggers` (added in Task 3) asserts both the trigger survival and the absence of a table rebuild.
- **Committed in:** `1c4d5af` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in the plan's primary migration approach, with the plan's own documented fallback applied).
**Impact on plan:** No scope creep — this was the anticipated risk (RESEARCH A1) with an explicit fallback already specified in the plan; applying it required no new design decisions.

## Issues Encountered

- Pre-existing ruff findings unrelated to this plan (2 `I001` in `tests/test_backup.py`, and 7 files that `ruff format --check .` would reformat, including lines in `app/models.py`/`app/services/ledger.py` outside anything this plan touched) were confirmed pre-existing via isolated `ruff` runs and `ruff format --diff`, then logged to `.planning/phases/04-sales-customers/deferred-items.md` per the SCOPE BOUNDARY rule rather than fixed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 2 (Plan 04-02) can implement `app/services/sales.py` and `app/routes/sales.py` directly against the RED contract in `tests/test_sales.py` — `register_sale`, `lookup_prefill`, `recent_sales` signatures are already exercised by 22 tests.
- Wave 3 (Plans 04-03/04-04) can implement the oversell aggregate check and `app/services/customers.py`/`app/routes/customers.py` against `tests/test_customers.py`'s 12-test contract.
- No blockers. One note for 04-02: `register_sale`'s oversell branch and any FK-dependent query on `operations.sale_id` must join through the ORM relationship rather than assume a DB-level foreign key exists (there is none after the A1 fallback) — referential integrity for `sale_id` is enforced only at the application layer (Unit-of-Work ordering), not by SQLite.

---
*Phase: 04-sales-customers*
*Completed: 2026-07-09*
