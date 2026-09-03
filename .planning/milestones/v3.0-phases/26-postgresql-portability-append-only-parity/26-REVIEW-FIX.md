---
phase: 26-postgresql-portability-append-only-parity
fixed_at: 2026-07-19T00:00:00Z
review_path: .planning/phases/26-postgresql-portability-append-only-parity/26-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 26: Code Review Fix Report

**Fixed at:** 2026-07-19T00:00:00Z
**Source review:** .planning/phases/26-postgresql-portability-append-only-parity/26-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (1 critical, 3 warnings; IN-01 is Info and out of scope for `critical_warning`)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: PostgreSQL `DROP TRIGGER` in downgrade() omits the required `ON <table>` clause

**Files modified:** `alembic/versions/0001_initial_schema.py`, `alembic/versions/0013_cash_movements.py`
**Commit:** 7bba10b
**Applied fix:** Branched `downgrade()` on `op.get_bind().dialect.name == "postgresql"`, mirroring the CREATE side. On PostgreSQL the DROP TRIGGER statements now carry the mandatory `ON operations` / `ON cash_movements` clause and drop the trigger function; SQLite keeps the ON-less form. Syntax-verified with `ast.parse`. The PG downgrade path is not exercised by current CI (`pytest tests/test_pg_parity.py` never calls `command.downgrade`), so full runtime confirmation requires an `alembic downgrade` run against a PostgreSQL target.

### WR-02: A DB password containing `%` breaks online migrations via Alembic config interpolation

**Files modified:** `alembic/env.py`
**Commit:** 233f4ce
**Applied fix:** `config.set_main_option("sqlalchemy.url", ...)` now passes `settings.database_url.replace("%", "%%")` so a literal `%` in a generated PostgreSQL password survives ConfigParser pyformat interpolation. Syntax-verified.

### WR-01: `env.py` creates the SQLite parent dir from `settings.db_path`, not from the resolved URL

**Files modified:** `alembic/env.py`
**Commit:** 5f9e59a
**Applied fix:** Added `from sqlalchemy.engine import make_url` and now derive the SQLite parent directory from `make_url(settings.database_url).database` (guarded against a `None` database), matching `app/db.py`. An explicit `DATABASE_URL=sqlite:///custom/foo.db` override is now honored even when `db_path` is not changed. Syntax-verified.

### WR-03: Parity test seeds are not idempotent and have no teardown

**Files modified:** `tests/test_pg_parity.py`
**Commit:** 363190d
**Applied fix:** Appended `ON CONFLICT DO NOTHING` to the raw-SQL seed inserts (`_SEED_PRODUCT_UPD`, `_SEED_PRODUCT_DEL`, `_SEED_OP_UPD`, `_SEED_OP_DEL`, `_SEED_CASH`) so re-runs no longer raise unique-violation errors — the append-only ledger rows can never be DELETEd once triggers are live, so skip-on-conflict is the only re-runnable option. For the Cyrillic ORM test, added a `DELETE FROM products WHERE id IN ('pg-cyr-1','pg-cyr-2')` before the `add_all` (the products table carries no append-only trigger, so purge-then-insert is safe). Updated the module docstring to document the idempotency guarantee. `ON CONFLICT DO NOTHING` is portable to both SQLite and PostgreSQL, and this module only runs against PostgreSQL (skipif). Syntax-verified. Full runtime confirmation of the re-run behavior requires executing the suite twice against a standing PostgreSQL server.

## Skipped Issues

None — all in-scope findings were fixed.

_(IN-01, the CI duplicate-run trigger scoping, is an Info finding and outside the `critical_warning` fix scope; it was not attempted.)_

---

_Fixed: 2026-07-19T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
