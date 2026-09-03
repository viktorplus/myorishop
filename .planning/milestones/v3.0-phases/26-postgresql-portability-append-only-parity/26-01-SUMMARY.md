---
phase: 26-postgresql-portability-append-only-parity
plan: 01
subsystem: config + db-portability
tags: [postgresql, portability, append-only, config, test-scaffold, wave-0]
requires:
  - "app.config.Settings (existing _resolve_local_identity idiom)"
  - "app/models.py Operation / CashMovement / Product schema"
  - "app/services/catalog.search_products (Python-folded Cyrillic search)"
provides:
  - "settings.database_url — single DB-URL source of truth (env var DATABASE_URL)"
  - "psycopg[binary]==3.3.* dependency (uv.lock synced, 3.3.4)"
  - "tests/test_pg_parity.py — 5 SRV-01/SRV-02 PG-parity tests (RED in CI, skipped on SQLite)"
affects:
  - "alembic/env.py (Plan 03 will read settings.database_url)"
  - "app/db.py (Plan 03 will read settings.database_url + gate PRAGMA listener)"
tech-stack:
  added:
    - "psycopg[binary]==3.3.* (psycopg v3, postgresql+psycopg:// driver)"
  patterns:
    - "Single DB-URL source of truth: settings.database_url, sqlite default filled in _resolve_local_identity, env DATABASE_URL wins"
    - "PG-only integration tests: module-level pytestmark skipif on settings.database_url prefix"
key-files:
  created:
    - "tests/test_pg_parity.py"
  modified:
    - "app/config.py"
    - "pyproject.toml"
    - "uv.lock"
decisions:
  - "database_url default derived from db_path (sqlite:///{db_path}); a PG URL only ever arrives via env/.env — no credential hardcoded (RESEARCH Open Q2, T-26-02)"
  - "PG-parity tests match on message SUBSTRING 'append-only' (PG raises a driver exception, not SQLite IntegrityError)"
  - "Each PG test calls idempotent _upgrade_head() + uses unique seed ids, so the 5 tests are order-independent"
metrics:
  duration: "~12min"
  completed: "2026-07-18"
  tasks: 2
  files: 4
---

# Phase 26 Plan 01: PostgreSQL Portability Config + Append-Only Parity Scaffold Summary

Added the psycopg v3 driver, established `settings.database_url` as the single DB-URL source of truth (sqlite default, `DATABASE_URL` env override), and laid down the RED-in-CI `tests/test_pg_parity.py` scaffold (5 SRV-01/SRV-02 tests that skip on SQLite) that Plans 02-03 will turn green on PostgreSQL.

## What Was Built

### Task 1 — psycopg driver + `settings.database_url` single source of truth
- `pyproject.toml`: added `"psycopg[binary]==3.3.*"` (alphabetical placement after `jinja2`, existing minor-pin style preserved). `uv add "psycopg[binary]"` synced `uv.lock` (installed 3.3.4; the `[binary]` extra ships prebuilt libpq wheels — no C toolchain needed).
- `app/config.py`: new `database_url: str = ""` field on `Settings`. Empty default lets an explicit `DATABASE_URL` env/.env value win (pydantic-settings field→env mapping). Inside the existing `_resolve_local_identity` `@model_validator(mode="after")`, the empty default is filled with `f"sqlite:///{self.db_path}"` — mirroring the `secret_key`/`device_id` "env untouched, only empty default replaced" idiom. No host/user/password literal added.
- Commit: `e092ffd`

### Task 2 — PG-parity test scaffold (Wave 0, RED in CI)
- `tests/test_pg_parity.py`: module-level `pytestmark = pytest.mark.skipif(not settings.database_url.startswith("postgresql"), …)` so the file SKIPS on SQLite and RUNS only against a `postgresql+psycopg://` target. Five functions per the RESEARCH test map:
  - `test_full_history_applies` (SRV-01) — `command.upgrade(Config("alembic.ini"), "head")` then assert `products`/`operations`/`cash_movements` exist via `to_regclass`.
  - `test_cyrillic_search_parity` (SRV-01) — ORM-insert Cyrillic products (with Python-folded `name_lc`), call `search_products(session, "крем")`, assert the returned id set.
  - `test_operations_update_rejected` / `test_operations_delete_rejected` (SRV-02) — seed product + operation, assert UPDATE / DELETE raise `Exception` matching `append-only`.
  - `test_cash_movements_immutable` (SRV-02) — seed a cash row, assert both UPDATE and DELETE raise `append-only`.
- Every seed INSERT names all NOT NULL columns of its target table (`operations`, `cash_movements`, `products`); `author_id` (nullable, Phase 25 migration 0017) omitted. Only literal constant seeds — no external data f-stringed into SQL (the single bound param is `to_regclass(:t)`). Each test calls idempotent `_upgrade_head()` and uses unique seed ids → order-independent.
- Commit: `84a29f7`

## Verification

- `uv run pytest tests/test_pg_parity.py --collect-only -q` → 5 tests, 0 errors.
- `uv run pytest tests/test_pg_parity.py -q` → 5 skipped locally (no `DATABASE_URL`).
- `uv run python -c "from app.config import settings; print(settings.database_url)"` → `sqlite:///data/myorishop.db`.
- `DATABASE_URL=postgresql+psycopg://u:p@h/db …` → env override wins (exit 0).
- `uv run ruff check app/config.py pyproject.toml tests/test_pg_parity.py` → clean.
- Full suite: `uv run pytest` → **982 passed, 5 skipped, 3 warnings** (SQLite regression untouched; the 3 warnings are pre-existing SAWarnings in `test_returns.py`, out of scope).

## Deviations from Plan

None — plan executed exactly as written.

(One tooling nit auto-resolved: `ruff --fix` re-sorted the import block — first-party `alembic`/`app` after third-party `pytest`/`sqlalchemy`. Cosmetic, no behavior change.)

## Threat Surface

No new security-relevant surface beyond the plan's `<threat_model>`. `settings.database_url` holds only the non-secret `sqlite:///` default in-repo; any PG credential arrives solely via env/.env (T-26-02 mitigated). psycopg is the official PostgreSQL adapter (T-26-SC accepted, no install failure).

## Notes for Plan 02/03

- `settings.database_url` is the ONE value `alembic/env.py` and `app/db.py` must read (both currently hardcode `sqlite:///`).
- `tests/test_pg_parity.py` stays RED on PG until 0001/0013 emit dialect-branched trigger DDL and `env.py`/`build_engine` read `settings.database_url`.
- `_upgrade_head()` builds `Config("alembic.ini")` with no explicit URL — it relies on Plan 03 making `env.py` read `settings.database_url`.

## Self-Check: PASSED

- Files: tests/test_pg_parity.py, app/config.py, pyproject.toml, 26-01-SUMMARY.md — all FOUND.
- Commits: e092ffd (Task 1), 84a29f7 (Task 2) — all FOUND.
