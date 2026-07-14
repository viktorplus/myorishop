# Deferred Items — Phase 15

## Pre-existing: `alembic upgrade head --sql` fails on migration 0002 in offline mode

**Found during:** 15-01 Task 2 verification (`uv run alembic upgrade head --sql`).

**Issue:** `alembic/versions/0002_catalog_dictionary.py` (Phase 2, commit `370ba53`)
calls `bind.execute(...)` to backfill `name_lc` in Python. In Alembic's offline
(`--sql`) mode there is no live connection, so `op.get_bind()` returns a bind
whose `.execute()` returns `None` — `rows.fetchall()` then raises
`AttributeError: 'NoneType' object has no attribute 'fetchall'`. This means
the full-chain `alembic upgrade head --sql` has never worked from a fresh DB
across the whole migration history, not just after 0013.

**Scope:** Out of scope for Phase 15 Plan 01 — the bug is in a Phase 2 file,
unrelated to `cash_movements`/migration 0013.

**Verification workaround used for 0013's own acceptance criteria:** ran the
isolated range `uv run alembic upgrade 0012:0013 --sql`, which generates the
`CREATE TABLE cash_movements` + both `CREATE TRIGGER` statements correctly
(4 lines containing "cash_movements"). `uv run alembic heads` confirms `0013`
is the sole head, and `uv run alembic upgrade head` (online, real DB) succeeds
normally — only the offline/`--sql` full-chain replay is affected.

**Recommendation:** revisit `0002_catalog_dictionary.py`'s offline-mode
`bind.execute` if a from-scratch offline SQL dump is ever needed; not
blocking for online `alembic upgrade head`, which is the only path used by
`run.bat` / the app / test fixtures.
