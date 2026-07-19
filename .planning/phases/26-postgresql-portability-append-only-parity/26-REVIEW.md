---
phase: 26-postgresql-portability-append-only-parity
reviewed: 2026-07-19T06:58:31Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - .github/workflows/ci.yml
  - alembic/env.py
  - alembic/versions/0001_initial_schema.py
  - alembic/versions/0013_cash_movements.py
  - app/config.py
  - app/db.py
  - tests/test_pg_parity.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 26: Code Review Report

**Reviewed:** 2026-07-19T06:58:31Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the PostgreSQL-portability / append-only-parity slice: the dialect-branched
trigger DDL in migrations 0001 and 0013, the single-source-of-truth DB-URL wiring in
`app/config.py` + `app/db.py` + `alembic/env.py`, the PG parity CI job, and the parity
proof harness `tests/test_pg_parity.py`.

The upgrade path is sound and is well-guarded by CI. The forward migrations correctly
branch on dialect, and the append-only assertions are matched on a stable message
substring across dialects. However, the review found one BLOCKER on the **downgrade**
path that CI never exercises: the `DROP TRIGGER` statements use SQLite-only syntax and
will raise a hard syntax error on PostgreSQL, so `alembic downgrade` is broken on the
very platform this phase exists to support. Three warnings cover a dir-creation
inconsistency between `env.py` and `app/db.py`, an Alembic percent-interpolation gotcha
for DB passwords, and non-idempotent test seeds that break on re-run against a persistent
PostgreSQL database.

## Critical Issues

### CR-01: PostgreSQL `DROP TRIGGER` in downgrade() omits the required `ON <table>` clause

**File:** `alembic/versions/0001_initial_schema.py:145-146`, `alembic/versions/0013_cash_movements.py:106-107`
**Issue:**
PostgreSQL's grammar is `DROP TRIGGER [IF EXISTS] name ON table_name`. The `ON table_name`
part is **mandatory**. Both migrations issue the SQLite-only form:

```python
op.execute("DROP TRIGGER IF EXISTS operations_no_update")    # 0001
op.execute("DROP TRIGGER IF EXISTS cash_movements_no_update") # 0013
```

On SQLite this is valid, so the upgrade-only CI job (`uv run pytest tests/test_pg_parity.py -x`,
which never calls `command.downgrade`) stays green. But on a PostgreSQL target these
statements raise a syntax error at the very first `DROP TRIGGER` line, aborting the whole
`downgrade()` before it ever reaches `DROP FUNCTION` / `DROP TABLE`. That means
`alembic downgrade` is unusable on PostgreSQL — a correctness defect on the platform this
phase is dedicated to. It is invisible to the current tests and only surfaces by
inspection. The owning table is known at authoring time, so no guesswork is needed.

**Fix:** Branch the DROP exactly like the CREATE side already does, adding `ON <table>` for PG:

```python
# 0001 downgrade()
if op.get_bind().dialect.name == "postgresql":
    op.execute("DROP TRIGGER IF EXISTS operations_no_update ON operations")
    op.execute("DROP TRIGGER IF EXISTS operations_no_delete ON operations")
    op.execute("DROP FUNCTION IF EXISTS operations_append_only()")
else:
    op.execute("DROP TRIGGER IF EXISTS operations_no_update")
    op.execute("DROP TRIGGER IF EXISTS operations_no_delete")
```

Apply the mirror change in `0013_cash_movements.py` (`... ON cash_movements`).

## Warnings

### WR-01: `env.py` creates the SQLite parent dir from `settings.db_path`, not from the resolved URL

**File:** `alembic/env.py:22-23`
**Issue:**
`env.py` sets `sqlalchemy.url = settings.database_url` (line 17) but then mkdirs the parent
of `settings.db_path`:

```python
if settings.database_url.startswith("sqlite"):
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
```

`app/db.py` does the correct thing — it derives the directory from the URL itself
(`Path(engine.url.database).parent`, line 62). If a user overrides
`DATABASE_URL=sqlite:///custom/foo.db` without also changing `db_path` (which stays
`data/myorishop.db`), migrations connect to `custom/foo.db` but only `data/` is created,
so SQLite fails to open the file. In the default flow the two agree (the URL is derived
from `db_path` in `config.py`), so this only bites an explicit divergent override — but it
is an avoidable inconsistency between the two DB-bootstrap paths this phase unified.

**Fix:** Derive the directory from the URL to match `app/db.py`:

```python
from sqlalchemy.engine import make_url
url = settings.database_url
if url.startswith("sqlite"):
    db_file = make_url(url).database
    if db_file:
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
```

### WR-02: A DB password containing `%` breaks online migrations via Alembic config interpolation

**File:** `alembic/env.py:17`
**Issue:**
`config.set_main_option("sqlalchemy.url", settings.database_url)` stores the URL in
Alembic's ConfigParser, which performs pyformat (`%(name)s`) interpolation. A raw `%` in
the value must be escaped as `%%`. Since `DATABASE_URL` arrives from the environment, a
PostgreSQL password containing a literal `%` (common in generated credentials) makes
`engine_from_config` raise an interpolation error at migration time. The CI credential
(`postgres`) has no special chars, so CI never surfaces this. It directly undercuts the
"PostgreSQL by connection string only" portability goal.

**Fix:** Escape the value, or build the engine from `settings.database_url` without routing
it through ConfigParser:

```python
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
```

### WR-03: Parity test seeds are not idempotent and have no teardown — re-runs fail with duplicate-key errors

**File:** `tests/test_pg_parity.py:108-131`, `134-183`
**Issue:**
Every test inserts fixed-PK rows (`pg-cyr-1/2`, `pg-op-upd-p`, `pg-op-upd`, `pg-op-del-p`,
`pg-op-del`, `pg-cash-1`) and never removes them. The module docstring and `_upgrade_head`
claim idempotency "without ordering coupling," but only the *schema* is idempotent — the
*seed data* is not. In CI the DB is a throwaway container so the first run passes, but
running the suite twice against a persistent PostgreSQL (a normal local-dev workflow with
`DATABASE_URL` pointed at a standing server) fails on the second run with unique-violation
errors on the primary keys. Worse, the append-only ledger rows can never be cleaned up
afterward because the very triggers under test block DELETE — leaving the target DB
permanently un-reusable for the harness.

**Fix:** Make the harness self-contained: run each parity test against a uniquely-named
schema (or a freshly created database) via a session-scoped fixture that creates and drops
it, and/or guard the product-parent inserts with `ON CONFLICT DO NOTHING`. At minimum,
document that the harness requires an empty target and enforce that with a fixture.

## Info

### IN-01: CI workflow triggers on both `push` and `pull_request` with no filters — duplicate runs on PRs

**File:** `.github/workflows/ci.yml:3-5`
**Issue:**
`on: push:` and `pull_request:` with no branch filters cause the pg-parity job to run
twice for every PR from a branch in the same repo (once for the push, once for the PR
event), doubling CI minutes and PostgreSQL container spin-ups.
**Fix:** Scope the triggers, e.g. `on: { push: { branches: [main] }, pull_request: {} }`,
so intra-repo branch pushes only run through the PR event.

---

_Reviewed: 2026-07-19T06:58:31Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
