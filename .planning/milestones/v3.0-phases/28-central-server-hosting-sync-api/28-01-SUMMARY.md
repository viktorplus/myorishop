---
phase: 28-central-server-hosting-sync-api
plan: 01
subsystem: database
tags: [migration, triggers, append-only, sync-cursor, postgresql, sqlite]
requires: [SRV-02]
provides: [SYNC-01-prereq, SC-3]
affects: [alembic, app/db.py, tests]
tech-stack:
  added: []
  patterns:
    - "dialect-branched DDL via op.get_bind().dialect.name (0001/0013/0018)"
    - "value-based FOR EACH ROW WHEN trigger guard (not UPDATE OF)"
    - "schema-derived fail-open tripwire via model.__mapper__.columns"
key-files:
  created:
    - alembic/versions/0018_sync_cursor_trigger_relaxation.py
    - tests/test_append_only_cursor.py
  modified:
    - app/db.py
    - tests/test_pg_parity.py
    - tests/test_batches.py
decisions:
  - "Value-based WHEN guard, not UPDATE OF: the guard fires on actual change, so a mixed `SET synced_at=..., qty_delta=99` statement is still rejected and the cursor stamp cannot become a smuggling channel"
  - "PG payload guard casts to ::text — PostgreSQL `json` has no equality operator"
  - "The PL/pgSQL append-only functions from 0001/0013 are reused unchanged; migration 0018 replaces only the two triggers and never emits a function drop"
  - "The 0008 trigger probe `SET qty_delta = qty_delta` was retargeted to a real value change — it is now a legitimately permitted no-op under the value-based guard"
metrics:
  duration: ~35min
  tasks: 3
  files: 5
  completed: 2026-07-19
---

# Phase 28 Plan 01: Sync Cursor Trigger Relaxation Summary

Column-scoped append-only UPDATE triggers on both ledgers, so `synced_at` can be stamped on a synced row while every immutable column and all DELETEs stay blocked — proven on SQLite and postgres:17.

## What Was Built

Migration `0018` drops and re-creates `operations_no_update` and `cash_movements_no_update` with a value-based `FOR EACH ROW WHEN` guard enumerating every immutable column (14 on `operations`, 10 on `cash_movements`). Before this, *every* UPDATE was rejected — so a client that pushed successfully could not record that it pushed. This is the database prerequisite for the Phase 29 client cursor (SYNC-01) and ROADMAP Success Criterion 3.

The guarantee is amended, not weakened:

- every immutable column remains immutable;
- a statement setting `synced_at` **and** an immutable column in one go is still rejected (the guard is value-based, not `UPDATE OF`-based, so it cannot be evaded by naming extra columns);
- the two DELETE triggers are never referenced by the migration — deletion stays unconditionally blocked;
- the existing PL/pgSQL functions `operations_append_only()` / `cash_movements_append_only()` are reused unchanged.

### Task-by-task

| Task | What | Commit |
|------|------|--------|
| 1 | Migration `0018` (dialect-branched, with `downgrade()` restoring the v1 unconditional triggers) + the lockstep `app/db.py::APPEND_ONLY_TRIGGERS` edit | `66a355e` |
| 2 | `tests/test_append_only_cursor.py` — 16 SQLite cases incl. two fail-open tripwires | `f9fbce4` |
| 3 | Four new PostgreSQL parity cases appended to `tests/test_pg_parity.py`, zero CI changes | `1f95ce7` |

### Two non-obvious traps handled

**The PostgreSQL `json` trap.** `Operation.payload` is `sa.JSON`, which maps to PG's `json` type — which has **no equality operator**. An uncast `NEW.payload IS DISTINCT FROM OLD.payload` fails with `operator does not exist: json = json`. The PG guard therefore compares `NEW.payload::text IS DISTINCT FROM OLD.payload::text`. `test_pg_payload_tamper_rejected` is the regression: without the cast the UPDATE errors with the json message, which does not match `append-only`, so the test fails loudly rather than silently passing.

**The fixture/migration lockstep.** `tests/conftest.py` builds every test DB from `Base.metadata.create_all` plus `app/db.py::APPEND_ONLY_TRIGGERS` — never via Alembic. If that constant and migration `0018` drift, the entire suite tests the old triggers while production runs the new ones. Both were edited in the same commit, and the lockstep rule is now documented in both files.

## Key Decisions

- **Value-based `WHEN` over `UPDATE OF`** — `UPDATE OF col` fires on the *mention* of a column in the SET clause. It would reject the harmless no-op `SET synced_at=..., qty_delta=qty_delta`, and, more importantly, expresses "was named" rather than "was changed". The value-based guard expresses the actual invariant and closes the mixed-statement smuggling path.
- **A no-op self-assignment is permitted.** Re-stamping `synced_at` to the value it already holds succeeds. The PG harness depends on this to stay re-runnable against a standing server, since ledger rows can never be deleted.
- **No new migration for `synced_at`** — the column already exists on both tables (migrations `0001` and `0013`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `test_migration_0008_seeds_legacy_batches_and_preserves_triggers` failed after the relaxation**

- **Found during:** Task 1 (full-suite gate)
- **Issue:** The test probed trigger liveness with `UPDATE operations SET qty_delta = qty_delta` — a *self-assignment*. Under the new value-based guard this changes nothing and is legitimately permitted, so the expected `IntegrityError` no longer raised. This is the intended semantic change surfacing, not a defect in the migration.
- **Fix:** Retargeted the probe to `SET qty_delta = qty_delta + 1` (a genuinely different value). The invariant under test — an immutable ledger column cannot be changed — is unchanged; only the probe's chosen value moved. Added a comment explaining why, pointing at the new module for full coverage.
- **Files modified:** `tests/test_batches.py`
- **Commit:** `66a355e`

**2. [Rule 2 - Missing critical coverage] Extra cases beyond the plan's enumeration**

- **Found during:** Tasks 2 and 3
- **Issue:** The plan named the mixed-update case only for `operations`, and the PG immutable case only for `qty_delta`/`created_by`. The cash ledger's mixed-statement path and PG's DELETE path were unproven.
- **Fix:** Added `test_mixed_cash_update_rejected` (SQLite), extended the SQLite tamper parametrisation to 8 cases (adding `type`, `created_at`, `category`), added a leak-through assertion after each mixed-update rejection (`synced_at IS NULL` — proving the rejection rolled back rather than partially applying), added `test_declared_constants_match_trigger_ddl` as the second tripwire direction, and folded a DELETE case into `test_pg_immutable_columns_still_rejected`.
- **Files modified:** `tests/test_append_only_cursor.py`, `tests/test_pg_parity.py`
- **Commits:** `f9fbce4`, `1f95ce7`

No architectural changes, no checkpoints, no auth gates, no new packages.

## Verification

| Check | Result |
|-------|--------|
| `alembic upgrade head` → `downgrade 0017` → `upgrade head` | all exit 0 |
| `alembic heads` | `0018 (head)` — single head |
| `uv run pytest -q` (full SQLite suite) | **1031 passed, 7 skipped** |
| `uv run pytest tests/test_append_only_cursor.py -q` | 16 passed |
| `uv run pytest tests/test_pg_parity.py -q` (no `DATABASE_URL`) | 9 skipped (guard intact) |
| `pytest tests/test_pg_parity.py` on **postgres:17** | **9 passed**, idempotent on immediate re-run |
| `pytest tests/test_merge_pg.py` on postgres:17 | 2 passed (Phase 27 slice unaffected) |
| `grep -c "DROP FUNCTION" …/0018_….py` | 0 |
| `grep -cE "^(import app\|from app)" …/0018_….py` | 0 (WR-06) |
| `git log --oneline 785ccf2..HEAD -- .github/workflows/ci.yml` | empty — no CI change |
| `ruff check` on all touched files | clean |

The PostgreSQL run was executed locally against a real `postgres:17` container, not merely reasoned about. The live schema was inspected as an independent confirmation that the tests were not false-greening:

```
cash_movements_no_delete|f
cash_movements_no_update|t
operations_no_delete|f
operations_no_update|t
```

(`t` = the trigger definition carries a `WHEN` clause.) Exactly the two UPDATE triggers are column-scoped; both DELETE triggers remain unconditional.

## Success Criteria

- [x] SC-3 true and automated on both engines: `synced_at` stampable; `qty_delta`, `amount_cents`, `author_id`, `created_by`, `payload`, `type`, `category`, `created_at` all rejected; DELETE blocked
- [x] Migration `0018` is the single head, applies and reverses cleanly, reuses the existing PL/pgSQL functions
- [x] `app/db.py::APPEND_ONLY_TRIGGERS` and migration `0018` carry the identical SQLite guard
- [x] A future column added to either ledger model fails a test rather than silently escaping the trigger

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, file access, or trust-boundary schema changes — this plan only tightens an existing DB-level control. All DDL is module-level literal constants with no interpolation (T-28-14); test SQL uses bound parameters for all values, with table/column names coming only from in-module literal constants.

## Notes for Future Plans

- **Phase 29 (SYNC-01)** can now write the client cursor: `UPDATE operations SET synced_at = ... WHERE id = ...` is permitted on both dialects. Stamp `synced_at` **alone** — a statement that also touches any other column is rejected wholesale.
- **Any future ledger column** must be added to *three* places in the same commit: migration (a new one, never editing `0018`), `app/db.py::APPEND_ONLY_TRIGGERS`, and the constants in `tests/test_append_only_cursor.py`. `test_trigger_column_list_matches_schema` fails loudly if you forget — that is deliberate.
- The `0008` probe change is a small precedent: any *other* test that asserts append-only by self-assignment would now false-green. A sweep found no others.

## Self-Check: PASSED

- FOUND: `alembic/versions/0018_sync_cursor_trigger_relaxation.py`
- FOUND: `tests/test_append_only_cursor.py` (288 lines, min 90 required)
- FOUND: `app/db.py`
- FOUND: commit `66a355e`
- FOUND: commit `f9fbce4`
- FOUND: commit `1f95ce7`
