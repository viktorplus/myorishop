---
phase: 26-postgresql-portability-append-only-parity
plan: 02
subsystem: migrations + append-only-parity
tags: [postgresql, portability, append-only, alembic, triggers, plpgsql, wave-1]
requires:
  - "alembic/versions/0001_initial_schema.py (frozen SQLite append-only trigger DDL on operations)"
  - "alembic/versions/0013_cash_movements.py (frozen SQLite append-only trigger DDL on cash_movements)"
  - "op.get_bind().dialect.name (Alembic runtime dialect-branch hook)"
provides:
  - "0001 emits PL/pgSQL operations_append_only() function + operations_no_update/_no_delete triggers on PostgreSQL"
  - "0013 emits PL/pgSQL cash_movements_append_only() function + cash_movements_no_update/_no_delete triggers on PostgreSQL"
  - "alembic upgrade head no longer syntax-errors at revision 0001 on empty PostgreSQL (SRV-01)"
  - "PostgreSQL rejects UPDATE/DELETE on both ledger tables exactly as SQLite does (SRV-02)"
affects:
  - "tests/test_pg_parity.py (Plan 03 proves PG enforcement against postgres:17 CI service)"
tech-stack:
  added: []
  patterns:
    - "Single migration history, dialect-branched trigger DDL via op.get_bind().dialect.name (RESEARCH Pattern 1)"
    - "Two separate PG triggers per table for name parity with SQLite (RESEARCH Pattern 2)"
    - "PL/pgSQL BEFORE UPDATE/DELETE trigger function RAISE EXCEPTION as the PG equivalent of SQLite RAISE(ABORT)"
    - "WR-06 immutability preserved by ADDITIVE-only edit: the SQLite emit path is byte-for-behavior unchanged"
key-files:
  created: []
  modified:
    - "alembic/versions/0001_initial_schema.py"
    - "alembic/versions/0013_cash_movements.py"
decisions:
  - "Fix lives INSIDE 0001.upgrade()/0013.upgrade() (not a new appended migration) because on empty PG the chain dies at revision 0001 before any later revision runs (RESEARCH Pitfall 1)"
  - "Trigger names (operations_no_update/_no_delete, cash_movements_no_update/_no_delete) reused verbatim on PG so tests/test_pragmas.py name assertions and Phase 28's relaxation target the same names (RESEARCH Pattern 2)"
  - "Message substrings preserved exactly ('operations ledger is append-only' / 'cash ledger is append-only') — both contain the 'append-only' substring the PG-parity tests match on"
  - "downgrade() PG branch adds DROP FUNCTION IF EXISTS after the two dialect-neutral DROP TRIGGER IF EXISTS statements"
metrics:
  duration: "~3min"
  completed: "2026-07-18"
  tasks: 2
  files: 2
---

# Phase 26 Plan 02: Append-Only Trigger Dialect Parity Summary

Retrofitted an additive `op.get_bind().dialect.name` branch into the two FROZEN migrations (0001, 0013) so `alembic upgrade head` emits PL/pgSQL append-only trigger functions on PostgreSQL and the unchanged SQLite `RAISE(ABORT)` triggers on SQLite — fixing the Pitfall-1 crash at revision 0001 on empty PG (SRV-01) and giving PostgreSQL the same UPDATE/DELETE rejection on both ledger tables as SQLite (SRV-02).

## What Was Built

- **Task 1 — migration 0001 (operations):** Added module constant `_PG_OPERATIONS_DDL` (a `CREATE OR REPLACE FUNCTION operations_append_only() … LANGUAGE plpgsql` that does `RAISE EXCEPTION 'operations ledger is append-only'`, plus `operations_no_update` BEFORE UPDATE and `operations_no_delete` BEFORE DELETE triggers). Wrapped the trigger emit site in `if op.get_bind().dialect.name == "postgresql": … else: <unchanged SQLite path>`. Added a PG-only `DROP FUNCTION IF EXISTS operations_append_only()` to `downgrade()`.
- **Task 2 — migration 0013 (cash_movements):** Mirrored Task 1 with `_PG_CASH_APPEND_ONLY_DDL` (`cash_movements_append_only()` raising `'cash ledger is append-only'`, plus `cash_movements_no_update`/`_no_delete` triggers), the same dialect branch at the emit site, and a PG-only `DROP FUNCTION IF EXISTS cash_movements_append_only()` in `downgrade()`.

The `_APPEND_ONLY_TRIGGERS` / `_CASH_APPEND_ONLY_TRIGGERS` SQLite tuples and the `create_table`/index/seed code were left untouched.

## Verification

- `uv run pytest tests/test_pragmas.py tests/test_ledger.py -x` → 22 passed (SQLite triggers still created and still ABORT on UPDATE/DELETE).
- `uv run pytest tests/test_pragmas.py -x` → 3 passed.
- `uv run ruff check` clean on both migrations.
- `grep -c "op.get_bind().dialect.name"` = 2 in each migration (upgrade + downgrade branch).
- PG enforcement itself is proven in Plan 03 via `tests/test_pg_parity.py` against the postgres:17 CI service (out of scope here).

## Deviations from Plan

None — plan executed exactly as written.

## WR-06 Compliance

The edit is purely additive: a new PG DDL constant, an `if/else` wrapper whose `else` branch runs the exact statements it ran before, and a PG-only `DROP FUNCTION` line. The SQLite-emitted statements are byte-for-behavior identical, so deterministic SQLite replay of the migration chain is preserved.

## Self-Check: PASSED

- FOUND: alembic/versions/0001_initial_schema.py (modified, commit e3a1010)
- FOUND: alembic/versions/0013_cash_movements.py (modified, commit 8551f72)
- FOUND commit e3a1010 (feat 26-02: operations dialect branch)
- FOUND commit 8551f72 (feat 26-02: cash_movements dialect branch)
