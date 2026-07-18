---
phase: 26-postgresql-portability-append-only-parity
reviewed: 2026-07-18T23:25:10Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - app/config.py
  - app/db.py
  - alembic/env.py
  - alembic/versions/0001_initial_schema.py
  - alembic/versions/0013_cash_movements.py
  - pyproject.toml
  - .github/workflows/ci.yml
  - tests/test_pg_parity.py
  - tests/test_batches.py
  - tests/test_catalog.py
  - tests/test_dictionary.py
  - tests/test_ledger.py
  - tests/test_warehouses.py
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 26: Code Review Report

**Reviewed:** 2026-07-18T23:25:10Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the SRV-01/SRV-02 PostgreSQL-portability + append-only-parity slice: the
`settings.database_url` single-source-of-truth wiring (`app/config.py`,
`app/db.py`, `alembic/env.py`), the dialect-branched trigger DDL in the two
FROZEN migrations (0001, 0013), the psycopg dependency, the CI parity job, and
the parity/regression tests.

The security posture the task flagged is clean and I verified it directly:

- **No SQL injection surface.** Every migration DDL string and every parity-test
  seed is a static literal — no external/user data is f-stringed into SQL. The
  one dynamic probe uses a bound parameter (`to_regclass(:t)`,
  `tests/test_pg_parity.py:93`).
- **No hardcoded app credentials.** A PostgreSQL URL only ever arrives via
  `DATABASE_URL` env/.env (`app/config.py:30,65`). The only in-repo credential is
  the throwaway ephemeral-CI postgres password, explicitly scoped and documented
  (`.github/workflows/ci.yml:14-18`).
- **Append-only is enforced on both dialects.** SQLite `RAISE(ABORT,…)` triggers
  and the PG PL/pgSQL `RAISE EXCEPTION` triggers both fire on UPDATE/DELETE, and
  the SQLite trigger DDL is byte-for-behavior identical to the pre-phase output.
- **Offline `--sql` generation is NOT broken by the new dialect gate.** I
  verified `op.get_bind().dialect.name` resolves through Alembic's
  `MockConnection` in offline mode (`sqlalchemy/engine/mock.py:40-41`), so the
  added `if op.get_bind().dialect.name == "postgresql"` branch does not raise
  during `alembic upgrade --sql`.

The findings below concern the PostgreSQL **downgrade** path, a source-of-truth
divergence for the DB directory, a latent Alembic URL-interpolation crash for
passwords containing `%`, and non-idempotent parity-test seed data.

## Warnings

### WR-01: PostgreSQL downgrade is broken — `DROP TRIGGER IF EXISTS` omits the mandatory `ON <table>` clause

**File:** `alembic/versions/0001_initial_schema.py:145-146`, `alembic/versions/0013_cash_movements.py:106-107`
**Issue:** Both `downgrade()` bodies run bare
`op.execute("DROP TRIGGER IF EXISTS operations_no_update")` /
`...cash_movements_no_update`. That is valid SQLite, but PostgreSQL syntax is
`DROP TRIGGER [IF EXISTS] name ON table_name` — the `ON <table>` clause is
**required**. On a PostgreSQL target the very first statement of the downgrade
raises a syntax error, so `alembic downgrade` past 0013 or 0001 fails entirely
on the platform this phase exists to support. The subsequent
`DROP FUNCTION IF EXISTS …()` is never reached. This is the plan-acknowledged
deferral, but it is still incorrect behavior on PG; escalate to BLOCKER if
PostgreSQL downgrade support is in scope for this phase's acceptance.
**Fix:** Gate the trigger drops by dialect, mirroring the upgrade branch:
```python
def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS operations_no_update ON operations")
        op.execute("DROP TRIGGER IF EXISTS operations_no_delete ON operations")
        op.execute("DROP FUNCTION IF EXISTS operations_append_only()")
    else:
        op.execute("DROP TRIGGER IF EXISTS operations_no_update")
        op.execute("DROP TRIGGER IF EXISTS operations_no_delete")
    op.drop_index(op.f("ix_operations_product_id"), table_name="operations")
    ...
```
(Keep the SQLite branch byte-identical so deterministic replay is preserved.)

### WR-02: Alembic env derives the SQLite mkdir directory from `db_path`, not from the single-source-of-truth URL

**File:** `alembic/env.py:22-23`
**Issue:** The parent-dir creation uses `Path(settings.db_path).parent`, while the
migration engine is built from `settings.database_url`
(`config.set_main_option(..., settings.database_url)`). If someone sets an
explicit `DATABASE_URL=sqlite:///custom/dir/app.db` while `db_path` keeps its
`data/myorishop.db` default (both are independent settings fields), env.py
creates `data/` but the migration then tries to open the DB in `custom/dir/`,
which may not exist — SQLite cannot create the file and the migration fails.
`app/db.py` does this correctly by reading `engine.url.database` (line 62); env.py
should be consistent with that single source of truth.
**Fix:** Derive the directory from the resolved URL rather than `db_path`:
```python
from sqlalchemy.engine import make_url

url = make_url(settings.database_url)
if url.get_backend_name() == "sqlite" and url.database:
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)
```

### WR-03: A PostgreSQL password containing `%` crashes Alembic URL configuration

**File:** `alembic/env.py:17`
**Issue:** `config.set_main_option("sqlalchemy.url", settings.database_url)` passes
the raw URL to `ConfigParser.set`, which applies pyformat (`%`) interpolation.
Alembic's own docstring warns: "A raw percent sign not part of an interpolation
symbol must therefore be escaped, e.g. `%%`". A `DATABASE_URL` whose password
contains a literal `%` (common in generated/URL-encoded credentials, e.g. `%25`)
will raise `configparser.InterpolationSyntaxError` at migration time — both
online and offline, since `engine_from_config` reads the same interpolated
section. Since the whole point of the phase is arbitrary env-provided PG URLs,
this is a realistic latent failure.
**Fix:** Escape percent signs before handing the URL to ConfigParser:
```python
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
```

### WR-04: PostgreSQL parity tests seed hardcoded PKs with no cleanup — non-idempotent against a persistent DB

**File:** `tests/test_pg_parity.py:37-67, 134-182`
**Issue:** Each test INSERTs rows with fixed primary keys (`pg-op-upd-p`,
`pg-op-del`, `pg-cash-1`, `pg-cyr-1/2`, …) and never deletes them; the
append-only triggers also make the seeded `operations`/`cash_movements` rows
impossible to remove afterward. The module docstring claims idempotency, but that
only holds for the *schema* (`head` re-apply is a no-op) — the *data* seeds are
not. A second run against the same (non-ephemeral) PostgreSQL target, or a retry
plugin such as pytest-rerunfailures, hits a duplicate-key / unique-constraint
error rather than the asserted append-only failure, producing a false negative.
It passes in CI today only because the `postgres:17` service container is
recreated per run.
**Fix:** Make the seeds unique per run or drop/recreate the schema per module. For
example, generate unique ids (`uuid4()` hex) for the product/op/cash rows, or add
a fixture that runs `command.downgrade(cfg, "base")` + `upgrade(cfg, "head")`
once per module so each run starts from an empty schema regardless of DB
persistence.

## Info

### IN-01: CI PostgreSQL credential is inline in the workflow

**File:** `.github/workflows/ci.yml:18, 42`
**Issue:** `POSTGRES_PASSWORD: postgres` and the matching
`postgresql+psycopg://postgres:postgres@localhost:5432/postgres` are inlined in
the workflow. This is acceptable and correctly documented (ephemeral, non-secret,
never a production value, not referenced from repo code), so it is not a
vulnerability — noted only so the convention stays explicit if this job is ever
copied into a context that talks to a real database.
**Fix:** None required. If reused against a non-ephemeral DB, move the URL to a
GitHub Actions secret.

### IN-02: PG triggers use `CREATE TRIGGER` (not `CREATE OR REPLACE TRIGGER`) while their function uses `CREATE OR REPLACE`

**File:** `alembic/versions/0001_initial_schema.py:57-65`, `alembic/versions/0013_cash_movements.py:57-65`
**Issue:** The trigger functions are `CREATE OR REPLACE FUNCTION` (idempotent) but
the triggers themselves are plain `CREATE TRIGGER`. This is harmless under normal
Alembic version tracking (a migration never re-runs on the same DB), so it is not
a bug today. It is a mild asymmetry: if the DDL is ever re-executed manually
against a DB that already has the triggers, the function replace succeeds while
the trigger create errors with "already exists".
**Fix:** Optional — PostgreSQL 14+ supports `CREATE OR REPLACE TRIGGER`, which
would make the trigger DDL as re-runnable as the function DDL. Leave as-is if
strict frozen-migration byte stability is preferred.

---

_Reviewed: 2026-07-18T23:25:10Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
