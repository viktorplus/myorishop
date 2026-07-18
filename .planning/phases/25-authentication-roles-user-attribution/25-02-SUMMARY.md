---
phase: 25-authentication-roles-user-attribution
plan: 02
subsystem: auth
tags: [users-table, roles, author-id, attribution, migration-0017, append-only]

# Dependency graph
requires:
  - phase: 25-01
    provides: argon2-cffi installed (password_hash column will store its PHC output)
  - phase: (existing schema)
    provides: operations/cash_movements append-only triggers (0001/0013), Base naming convention
provides:
  - User model + users table (login unique, display_name, role, password_hash, is_active, timestamps)
  - ROLES allow-list (exactly two roles: administrator, operator)
  - nullable author_id FK on operations/cash_movements/sales (attribution storage)
  - migration 0017 (users table + native author_id add_column, triggers preserved)
affects: [25-03 user service (ROLES validation, display_name snapshot cap), 25-07 attribution stamping, later sync phases]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "author_id mirrors the bare-nullable batch_id/sale_id FK (ORM ForeignKey, bare DB column)"
    - "ROLES latin-key->RU-label dict mirrors WRITEOFF_REASONS/CASH_CATEGORIES allow-list shape"

key-files:
  created: [alembic/versions/0017_users_and_author_id.py]
  modified: [app/models.py, tests/test_pragmas.py]

key-decisions:
  - "author_id added with NATIVE op.add_column (never batch_alter_table) so the append-only triggers survive"
  - "No historical backfill — pre-auth rows stay NULL (no_update trigger would ABORT it; a fake author is a lie)"
  - "password_hash is String(255) for a full Argon2id PHC string only — hash-only credential storage"
  - "login is case-sensitive ASCII this phase — no login_lc shadow (RESEARCH A7)"

patterns-established:
  - "author_id is a bare nullable column at the DB level, ORM ForeignKey('users.id') for insert ordering + PostgreSQL portability"

requirements-completed: [USER-01, ROLE-01, USER-05]

# Metrics
duration: ~8min
completed: 2026-07-18
---

# Phase 25 Plan 02: Identity & Attribution Schema Summary

**A `users` table, a two-value `ROLES` allow-list, and nullable `author_id` columns on operations/cash_movements/sales — added via migration 0017 with native `op.add_column` so the append-only ledger triggers survive, proven by a new regression test.**

## Performance

- **Duration:** ~8 min (incl. full 921-test suite run, ~3 min)
- **Completed:** 2026-07-18
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `User` model (`users` table): `login` (unique), `display_name`, `role` (a `ROLES` key), `password_hash` (Argon2id PHC, String(255)), `is_active` soft-disable flag, ISO timestamps — mirrors the codebase UUID-PK convention (USER-01).
- `ROLES = {"administrator": "Администратор", "operator": "Оператор"}` — the exact server-side allow-list, exactly two roles, no dynamic/custom roles (ROLE-01).
- Nullable `author_id` FK->`users.id` on `Operation`, `CashMovement`, and `Sale` — the storage half of attribution (USER-05), mirroring the bare-nullable `batch_id`/`sale_id` precedent.
- Migration `0017` (down_revision `0016`): `create_table("users")` + native `op.add_column` for the three `author_id` columns + their indexes; round-trips up/down cleanly.
- New `tests/test_pragmas.py` regressions: (1) all four append-only triggers exist after the author_id/users schema builds; (2) an `UPDATE operations SET author_id=...` still ABORTs — the trigger is live, not merely present.

## Task Commits

1. **Task 1: User model + ROLES + author_id columns** — `c2d78b4` (feat)
2. **Task 2: Migration 0017 — users table + native author_id add_column** — `bb81214` (feat)
3. **Task 3: Trigger-survival regression in test_pragmas.py** — `95b6938` (test)

_Plan metadata commit follows this SUMMARY._

## Files Created/Modified
- `alembic/versions/0017_users_and_author_id.py` — users table + three native `author_id` columns (created). No app-module imports, no `batch_alter_table`.
- `app/models.py` — `ROLES` constant, `User` model, and `author_id` columns on `Operation`/`CashMovement`/`Sale` (modified).
- `tests/test_pragmas.py` — two new trigger-survival regression tests (modified).

## Decisions Made
- `author_id` uses native `op.add_column` (never a batch rebuild) so the `operations_no_update`/`operations_no_delete`/`cash_movements_no_update`/`cash_movements_no_delete` triggers survive — the whole point of the plan's threat register (T-25-02-01).
- No backfill of historical `author_id`: the `operations_no_update` trigger would ABORT any UPDATE, and stamping a fabricated author would be a lie (T-25-02-03). Pre-auth rows stay NULL.
- `password_hash` shaped as String(255) for an Argon2id PHC string only — hash-only storage (T-25-02-02); hashing itself lands in Plan 03.
- `display_name` (200) noted as source for the ledger's `created_by` (100) snapshot — the user service (Plan 03) caps display_name for that snapshot to fit.

## Deviations from Plan

**1. [Rule 1 - Bug] Regression test expected the wrong exception type**
- **Found during:** Task 3
- **Issue:** The trigger's `RAISE(ABORT, 'operations ledger is append-only')` surfaces through SQLAlchemy as `IntegrityError`, not `OperationalError`. The initial test asserted `OperationalError` and failed.
- **Fix:** Changed the import and `pytest.raises` to `sqlalchemy.exc.IntegrityError` (message match `"append-only"` unchanged).
- **Files modified:** `tests/test_pragmas.py`
- **Commit:** `95b6938`

## Issues Encountered
- None beyond the test-exception-type fix above. Git emits an LF->CRLF warning for the new migration/test files on Windows (cosmetic, autocrlf; files commit fine).

## Security Notes
- `users.password_hash` is a hash-only column (String(255), Argon2id PHC); no plaintext/reversible credential storage (T-25-02-02).
- The append-only ledger guarantee is verified to survive the schema change — a regression test proves an UPDATE touching `author_id` still ABORTs (T-25-02-01).

## Verification Evidence
- `uv run alembic upgrade head` / `downgrade -1` / `upgrade head` round-trips cleanly (0016<->0017).
- Post-upgrade PRAGMA check: `author_id` present on operations/cash_movements/sales; `users` table exists with a UNIQUE `login` index; all four append-only triggers present.
- `uv run pytest tests/test_pragmas.py tests/test_core.py tests/test_smoke.py` green.
- `uv run pytest` full suite: **921 passed** (was 919 at Plan 01; +2 new regression tests), 3 pre-existing unrelated SAWarnings.

## Next Phase Readiness
- Ready for 25-03: the user service can now hash Argon2 into `password_hash`, validate `role` against `ROLES`, and rely on the `users` table + unique `login`.
- Attribution stamping (Plan 07) has its `author_id` columns in place on all three write-path tables.

## Self-Check: PASSED

- Files exist: `alembic/versions/0017_users_and_author_id.py`, `app/models.py`, `tests/test_pragmas.py`, `25-02-SUMMARY.md`.
- Commits exist: `c2d78b4` (Task 1), `bb81214` (Task 2), `95b6938` (Task 3).

---
*Phase: 25-authentication-roles-user-attribution*
*Completed: 2026-07-18*
