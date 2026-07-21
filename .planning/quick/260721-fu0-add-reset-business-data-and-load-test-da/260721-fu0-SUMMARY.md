---
phase: quick-260721-fu0
plan: add-reset-business-data-and-load-test-data
subsystem: database
tags: [sqlalchemy, sqlite, postgresql, alembic-adjacent, ledger]

# Dependency graph
requires:
  - phase: quick-scripts-baseline
    provides: "scripts/reset_demo_data.py + scripts/seed_demo_data.py precedent (file-delete wipe / small demo dataset), app.db.APPEND_ONLY_TRIGGERS, app/services/ledger.record_operation single-write-path"
provides:
  - "scripts/reset_business_data.py: dialect-aware wipe of ONLY business/transactional tables (products, batches, customers, customer_contacts, sales, operations, cash_movements), interactive typed-confirmation gate (no --force/--yes bypass), append-only triggers bypassed only for the wipe's duration and always restored"
  - "scripts/load_test_data.py: 10 customers + exactly 10 operations of each of the 9 OPERATION_TYPES values (90 rows total), via service-layer calls only, refuses on a non-empty database"
affects: [deploy, operations, qa]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dialect-branched DDL (engine.dialect.name == sqlite|postgresql) for trigger bypass, mirroring app/db.py's build_engine_from_url and migration 0001/0013/0018's existing dialect-gated trigger DDL"
    - "Interactive-only confirmation gate with zero scriptable bypass (no --yes/--force flag anywhere), non-tty stdin aborts before any DB query"
    - "Test-data generator composes ONLY existing service-layer functions, never raw Operation()/CashMovement() ORM construction — verified by both behavioral assertions and a source-grep test"

key-files:
  created:
    - scripts/reset_business_data.py
    - scripts/load_test_data.py
    - tests/test_reset_business_data.py
    - tests/test_load_test_data.py
  modified: []

key-decisions:
  - "main()'s tty check runs BEFORE any database query (not after the pre-flight row-count summary, as the plan's draft ordering suggested) — safer and simpler: a non-interactive invocation (CI, piped input) never issues a single query against whatever database DATABASE_URL happens to resolve to before aborting"
  - "load_test_data reuses the first active warehouse if one already exists (real just-reset installs always have the migration-seeded default warehouse, since reset_business_data.py never touches warehouses) and only creates a new one when none exists (e.g. a bare create_all test DB) — avoids hardcoding the frozen DEFAULT_WAREHOUSE_ID literal from app.services.returns, which is a migration-only seed contract, not a general-purpose constant"

patterns-established: []

requirements-completed: []

# Metrics
duration: ~35min
completed: 2026-07-21
---

# Quick Task 260721-fu0: Reset Business Data + Load Test Data Summary

**Dialect-aware business-data wipe script (SQLite + PostgreSQL, typed-confirmation gated, append-only-trigger-safe) paired with a service-layer test-data generator producing exactly 90 operation rows across all 9 ledger types.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-07-21
- **Tasks:** 2 (both TDD: RED + GREEN)
- **Files created:** 4

## Accomplishments
- `scripts/reset_business_data.py` wipes ONLY products/batches/customers/customer_contacts/sales/operations/cash_movements — in FK-safe child-before-parent order (`CashMovement, Operation, CustomerContact, Sale, Batch, Customer, Product`) — leaving `warehouses`, `users`, `device_tokens`, `dictionary`, `catalog_prices`, `active_catalog`, and `sync_state` byte-for-byte untouched. Works unmodified on both SQLite (dialect-detected via `engine.dialect.name`) and PostgreSQL.
- The append-only triggers on `operations`/`cash_movements` are bypassed ONLY for the duration of the wipe call (SQLite: `DROP TRIGGER IF EXISTS` then recreate verbatim from `app.db.APPEND_ONLY_TRIGGERS`; PostgreSQL: `ALTER TABLE ... DISABLE/ENABLE TRIGGER ALL`), inside a `try/finally` so restoration happens even on a mid-wipe exception. Proven, not assumed: a test inserts a fresh row after the wipe and confirms both `UPDATE` and `DELETE` on `operations` still raise `"append-only"`.
- No `--yes`/`--force` flag exists anywhere in the script. `main()` checks `sys.stdin.isatty()` BEFORE issuing any database query — a non-interactive invocation (piped input, CI) aborts immediately with a nonzero exit and never hangs or touches the target database. Interactive confirmation requires typing the exact phrase `УДАЛИТЬ`.
- `scripts/load_test_data.py` creates 10 products, 10 customers, and exactly 10 operations of EACH of the 9 `OPERATION_TYPES` values (90 rows total) — entirely through the existing service layer (`create_product`, `register_receipt`, `register_sale`, `register_return`, `register_writeoff`, `register_correction`, `register_transfer`, `update_product`). `register_transfer` is called exactly 5 times (it writes 2 rows/call) to land on exactly 10 `transfer` rows; `update_product` changes a price field AND a non-price field in the same call, so each of the 10 calls emits one `price_change` row AND one `product_edited` row (10 + 10, not collapsed or doubled).
- `load_test_data` refuses with zero writes if any `Product` already exists (the "not freshly reset" guard) — no partial writes on refusal.
- Full test suite (1174 passed, 12 skipped) confirms zero regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1: scripts/reset_business_data.py — dialect-aware business-data wipe**
   - RED - `f7e4435` (test)
   - GREEN - `a3b5b0f` (feat)
2. **Task 2: scripts/load_test_data.py — 10 customers + 10 operations of every type**
   - RED - `6e0cc3e` (test)
   - GREEN - `8061a99` (feat)

_Note: no plan-metadata commit — SUMMARY.md/STATE.md updates are handled by the orchestrator separately, per this quick task's constraints._

## Files Created/Modified
- `scripts/reset_business_data.py` - `wipe_business_data(session, engine)` core (dialect-branched trigger bypass, FK-safe wipe order) + `main()` (target-identity print with redacted URL, pre-flight per-table row counts, tty-gated `УДАЛИТЬ` confirmation, no bypass flag)
- `scripts/load_test_data.py` - `load_test_data(session)` core (10-step data plan through the service layer, non-empty-DB guard) + thin `main()` printing the RU summary
- `tests/test_reset_business_data.py` - `test_wipe_empties_only_business_tables_preserves_the_rest`, `test_wipe_is_idempotent_on_an_already_empty_database`, `test_wipe_restores_append_only_enforcement_afterward`, `test_main_aborts_without_a_tty_and_never_wipes` (subprocess against a throwaway scratch SQLite file, never the real `data/myorishop.db`)
- `tests/test_load_test_data.py` - `test_guard_refuses_when_a_product_already_exists`, `test_load_test_data_creates_ten_customers_and_ten_ops_per_type`, `test_transfer_rows_total_exactly_ten_not_twenty`, `test_update_product_emits_price_change_and_product_edited_separately`, `test_load_test_data_never_constructs_ledger_rows_directly`

## Decisions Made
- `main()`'s non-tty check runs before any database query (see key-decisions above) — a safer ordering than the plan's illustrative draft, still satisfying every behavioral requirement (abort before `wipe_business_data`, nonzero exit, no hang).
- `load_test_data` resolves the receipt warehouse via `active_warehouses(session)` (first active row, or create one if none exists) rather than importing the frozen `DEFAULT_WAREHOUSE_ID` literal from `app.services.returns` — that literal is a migration-0007-specific seed contract, not a general "the default warehouse" constant, and this approach works correctly against both a real just-reset install (which always has the seeded warehouse) and a bare test database (which has none).

## Deviations from Plan

None - plan executed exactly as written, with the two decisions noted above (both within the plan's own "adjust as needed for correctness" and "whichever error-handling shape reads more naturally" latitude, not scope changes).

## Issues Encountered
None.

## TDD Gate Compliance

Both tasks followed the mandatory RED -> GREEN sequence:
- Task 1: RED commit `f7e4435` (`test(260721-fu0): add failing test for reset_business_data.wipe_business_data`) confirmed failing via `ModuleNotFoundError` (module did not exist) before any implementation. GREEN commit `a3b5b0f` (`feat(260721-fu0): add reset_business_data.py dialect-aware wipe script`) — all 4 tests pass.
- Task 2: RED commit `6e0cc3e` (`test(260721-fu0): add failing test for load_test_data core generator`) confirmed failing via `ModuleNotFoundError` before any implementation. GREEN commit `8061a99` (`feat(260721-fu0): add load_test_data.py service-layer test-data generator`) — all 5 tests pass.
- No REFACTOR commit needed for either task — implementation was clean on first pass (one lint fix — an unused import and a docstring wording adjustment — folded into the GREEN commits before they were made, not a separate cycle).

## User Setup Required

None - no external service configuration required.

## Manual Verification (NOT run by the executor)

Per the plan's `<verification>` section, the operator should manually spot-check locally:
1. Run `uv run python scripts/reset_business_data.py` against a DB with `scripts/seed_demo_data.py` data loaded — confirm it prompts, confirm typing anything other than `УДАЛИТЬ` aborts safely, confirm typing `УДАЛИТЬ` wipes only the intended tables (`/products`, `/customers`, `/history` empty; `/dictionary`, `/settings/users`, `/settings/devices`, `/warehouses` unchanged).
2. Then run `uv run python scripts/load_test_data.py` and confirm 10 products/customers appear and `/history` shows 10 rows of each operation type.
This was flagged in PLAN.md as explicitly out of scope for the executor (requires live interactive input); the automated tests cover the same guarantees against the isolated test DB.

## Next Phase Readiness

Both scripts are CLI-only utilities, not wired into the web UI — no route changes, no blockers. Ready for the operator's manual spot-check above before relying on them against a real database (local or the deployed PostgreSQL server).

---
*Quick task: 260721-fu0-add-reset-business-data-and-load-test-da*
*Completed: 2026-07-21*

## Self-Check: PASSED

All 4 created files exist on disk (scripts/reset_business_data.py, scripts/load_test_data.py,
tests/test_reset_business_data.py, tests/test_load_test_data.py); all 4 commit hashes
(f7e4435, a3b5b0f, 6e0cc3e, 8061a99) found in git log. Full suite: 1174 passed, 12 skipped,
zero regressions.
