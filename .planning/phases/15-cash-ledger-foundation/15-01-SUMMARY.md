---
phase: 15-cash-ledger-foundation
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, sqlite, append-only-ledger]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "Operation append-only ledger pattern (APPEND_ONLY_TRIGGERS, NAMING_CONVENTION, UUID/cents/UTC conventions) this plan mirrors for cash"
provides:
  - "CashMovement model + cash_movements table (UUID PK, signed amount_cents, device_id/seq, sale_id FK)"
  - "CASH_CATEGORIES allow-list dict (sale, return)"
  - "cash_movements_no_update / cash_movements_no_delete triggers in app/db.py APPEND_ONLY_TRIGGERS and migration 0013"
  - "Migration 0013_cash_movements.py, single alembic head"
  - "tests/test_finance.py append-only executable contract"
affects: [15-02-manual-cash-movements, 15-03, 15-04, 16-manual-cash-movements-history]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cash ledger mirrors Operation's sync-ready shape (UUID PK, device_id/seq, created_at/created_by, nullable sale_id FK) but drops all stock-specific columns and has no cached projection (balance = live SUM)"

key-files:
  created:
    - alembic/versions/0013_cash_movements.py
    - tests/test_finance.py
    - .planning/phases/15-cash-ledger-foundation/deferred-items.md
  modified:
    - app/models.py
    - app/db.py

key-decisions:
  - "CASH_CATEGORIES keeps a distinct 'return' key (not reusing 'sale') so Phase 16/17 history/report views can separate system-generated movements from operator-entered ones"
  - "No relationship()/cached balance column on CashMovement — balance is always a live SUM(amount_cents), per D-00b"

patterns-established:
  - "Append-only cash ledger: DB-level BEFORE UPDATE/DELETE triggers installed in BOTH app/db.py (conftest's live source for test fixtures) AND the migration (frozen copy) — same dual-location pattern as the operations ledger"

requirements-completed: [FIN-01, FIN-02, FIN-06]

# Metrics
duration: 24min
completed: 2026-07-14
---

# Phase 15 Plan 01: Cash Ledger Foundation Summary

**Append-only `cash_movements` table (CashMovement model + CASH_CATEGORIES, migration 0013, DB-level triggers in both app/db.py and the migration) proven immutable by executable tests.**

## Performance

- **Duration:** 24 min
- **Tasks:** 3 completed
- **Files modified:** 5 (2 created source, 1 created test, 1 created migration, 2 modified)

## Accomplishments
- `CashMovement` SQLAlchemy model added, mirroring `Operation`'s sync-ready shape (UUID4 String(36) PK, signed `amount_cents` Integer, `device_id`/`seq` unique pair, `created_at`/`created_by`, nullable `sale_id` FK to `sales.id`) but without any stock-specific column (no `product_id`, `qty_delta`, `unit_cost_cents`, `unit_price_cents`, `payload`, `batch_id`) and no cached balance column.
- `CASH_CATEGORIES = {"sale": "Продажа", "return": "Возврат"}` added beside `WRITEOFF_REASONS`.
- `cash_movements_no_update` / `cash_movements_no_delete` triggers added to `app/db.py`'s `APPEND_ONLY_TRIGGERS` (now `tuple[str, ...]`, widened from `tuple[str, str]`) so the `conftest.py` fixture engine installs them automatically.
- `alembic/versions/0013_cash_movements.py` created: fresh `CREATE TABLE cash_movements` (PK, FK to `sales.id`, unique `(device_id, seq)`, index on `sale_id`) plus a frozen local copy of the two trigger statements, chained onto `down_revision = "0012"`. `alembic heads` reports a single head, `0013`.
- `tests/test_finance.py` created with `test_cash_movement_append_only_update_is_rejected` and `test_cash_movement_append_only_delete_is_rejected`, mirroring `test_ledger.py`'s pattern; imports only `app.models`/`app.core`/`app.config` (no `app.services.finance`, which lands in Plan 02).

## Task Commits

Each task was committed atomically:

1. **Task 1: Add CASH_CATEGORIES + CashMovement to app/models.py** - `fb60988` (feat)
2. **Task 2: Add cash append-only triggers to app/db.py and create migration 0013** - `ef5b57a` (feat)
3. **Task 3: Create tests/test_finance.py with append-only rejection tests** - `b79929b` (test)

**Plan metadata:** committed together with this SUMMARY (worktree mode — orchestrator merges).

## Files Created/Modified
- `app/models.py` - `CASH_CATEGORIES` dict + `CashMovement` model/table
- `app/db.py` - `APPEND_ONLY_TRIGGERS` widened to `tuple[str, ...]`, two new cash triggers appended
- `alembic/versions/0013_cash_movements.py` - `cash_movements` table + frozen trigger DDL, revises 0012
- `tests/test_finance.py` - append-only UPDATE/DELETE rejection tests for `cash_movements`
- `.planning/phases/15-cash-ledger-foundation/deferred-items.md` - pre-existing (Phase 2) offline-migration bug logged, out of scope

## Decisions Made
- Followed plan exactly for schema/trigger shape. No architectural deviations.
- Test names renamed to `test_cash_movement_append_only_update_is_rejected` / `_delete_is_rejected` (plan's action text used shorter names, but the plan's own acceptance criteria requires `-k append_only` to select exactly 2 tests — the `append_only` substring had to be in the test name itself).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, out-of-scope] Renamed test_finance.py test functions to satisfy the plan's own `-k append_only` verification filter**
- **Found during:** Task 3
- **Issue:** The plan's `<action>` text named the tests `test_cash_movement_update_is_rejected` / `test_cash_movement_delete_is_rejected`, but its own `<acceptance_criteria>` requires `uv run pytest tests/test_finance.py -k append_only -x` to select exactly 2 tests — neither name contains the substring "append_only".
- **Fix:** Renamed to `test_cash_movement_append_only_update_is_rejected` / `test_cash_movement_append_only_delete_is_rejected`.
- **Files modified:** tests/test_finance.py
- **Verification:** `uv run pytest tests/test_finance.py -k append_only -x` → 2 passed.
- **Committed in:** b79929b (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking/naming), plus 1 logged-and-deferred pre-existing issue (see below).
**Impact on plan:** Cosmetic rename only, required to satisfy the plan's own literal acceptance criteria. No scope creep.

## Issues Encountered

**Pre-existing bug found, logged, NOT fixed (out of scope):** `uv run alembic upgrade head --sql` (full chain from a fresh DB) fails inside migration `0002_catalog_dictionary.py` (Phase 2, commit `370ba53`) — its Python backfill loop calls `bind.execute(...)` which returns `None` in Alembic's offline mode, so `.fetchall()` raises `AttributeError`. This is unrelated to Phase 15/migration 0013 and predates this plan. Verified migration 0013's own DDL is correct via the isolated range `uv run alembic upgrade 0012:0013 --sql` (generates `CREATE TABLE cash_movements` + both `CREATE TRIGGER` statements correctly), and via `uv run alembic heads` (single head `0013`) plus the full online `uv run pytest` suite (565 passed, includes `test_migration_0004_preserves_append_only_triggers`-style migration exercises against a real online DB). Logged to `.planning/phases/15-cash-ledger-foundation/deferred-items.md` per the deviation Scope Boundary rule (pre-existing issue in an unrelated file, out of scope for this plan).

**Operator note (accidental `git stash -u`):** during Task 2 verification I mistakenly ran `git stash -u`, which is prohibited in worktree mode. I did not run `stash pop`/`apply`/`drop` to recover — instead used the sanctioned read-only `git show stash@{0}:<path>` / `git show stash@{0}^3:<path>` to extract both the modified `app/db.py` and the new untracked `alembic/versions/0013_cash_movements.py` byte-for-byte, restored them via the Write tool, and diff-verified an exact match before proceeding. The stash entry (`stash@{0}`) was intentionally left untouched rather than removed via any `git stash` subcommand — it is a single, unambiguously self-created entry (matches this worktree's branch/HEAD in its message) and poses no risk to other worktrees, but its cleanup is left to the user/orchestrator per the destructive-git-operation prohibition.

## Next Phase Readiness
- `CashMovement`/`CASH_CATEGORIES` are importable and the append-only guarantee is proven — Plan 02 (auto-credit on sale / auto-debit on return, per FIN-01/FIN-02) can now build `app/services/finance.py` against this table.
- No blockers. One stray `git stash` entry remains in this worktree (see above) — harmless but worth a `git stash list` / cleanup glance before the next agent runs here.

## Self-Check: PASSED

All created/modified files verified present on disk; all 4 commit hashes (`fb60988`, `ef5b57a`, `b79929b`, `391d055`) verified present in `git log --oneline --all`.
