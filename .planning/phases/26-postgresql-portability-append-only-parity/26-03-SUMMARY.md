---
phase: 26-postgresql-portability-append-only-parity
plan: 03
subsystem: db-portability
tags: [postgresql, sqlite, alembic, ci, append-only, dialect-gating]
requires: [26-01, 26-02]
provides:
  - "build_engine_from_url(url) — dialect-gated engine builder (sqlite side effects only)"
  - "alembic/env.py reads settings.database_url; render_as_batch + mkdir dialect-gated"
  - ".github/workflows/ci.yml — pg-parity job on postgres:17 proving SRV-01/SRV-02"
affects: [app/db.py, alembic/env.py, .github/workflows/ci.yml]
tech-stack:
  added: []
  patterns:
    - "Dialect-gated side effects: PRAGMA listener + parent-dir mkdir + render_as_batch run only when dialect == sqlite"
    - "Single DB-URL source of truth: both app engine and Alembic read settings.database_url"
    - "CI proof via GitHub Actions services: postgres:17 container with pg_isready health gate"
key-files:
  created:
    - .github/workflows/ci.yml
  modified:
    - app/db.py
    - alembic/env.py
decisions:
  - "build_engine(db_path) signature preserved and delegates to build_engine_from_url(f'sqlite:///{db_path}') — conftest.py and the 982-test SQLite suite untouched (lowest blast radius)"
  - "render_as_batch derived from URL scheme offline (no connection) and connection.dialect.name online"
  - "CI Postgres password is a throwaway non-secret 'postgres' on an ephemeral container (T-26-02) — no repo secret, no production credential committed"
metrics:
  duration: ~6min
  completed: 2026-07-18
---

# Phase 26 Plan 03: PostgreSQL Portability Wiring & CI Proof Summary

Wired `settings.database_url` through the engine builder and Alembic env, gated every SQLite-only side effect (PRAGMA connect-listener, parent-dir mkdir, `render_as_batch`) by dialect, and stood up a GitHub Actions `pg-parity` job on a real `postgres:17` service that proves SRV-01 (full migration history applies to empty PG + Cyrillic search parity) and SRV-02 (UPDATE/DELETE rejection on the operations and cash_movements ledgers).

## What Was Built

### Task 1 — Dialect-gated engine builder (app/db.py)
- Added `build_engine_from_url(url: str) -> Engine`: calls `create_engine(url)` and, only when `engine.dialect.name == "sqlite"`, performs the parent-dir `mkdir` and registers the `connect`-event PRAGMA listener (WAL / foreign_keys / busy_timeout with the autocommit dance). On PostgreSQL no listener and no mkdir run (PRAGMAs are a PG syntax error; PG enforces FKs natively).
- `build_engine(db_path)` kept with its exact signature, now delegating to `build_engine_from_url(f"sqlite:///{db_path}")` — `tests/conftest.py` and the full SQLite suite are byte-unchanged.
- Module engine now reads the single source of truth: `engine = build_engine_from_url(settings.database_url)`.
- Commit: `2ddec8a`

### Task 2 — Dialect-gated Alembic env (alembic/env.py)
- Replaced the hardcoded `sqlite:///{settings.db_path}` URL with `settings.database_url`.
- Gated the top-level parent-dir `mkdir` behind `settings.database_url.startswith("sqlite")`.
- Gated both `render_as_batch` occurrences: offline derives it from the URL scheme (no connection available), online derives it from `connection.dialect.name`.
- Verified: full Alembic chain (0001→0017) applies cleanly on a throwaway sqlite DB via a `DATABASE_URL` override; grep confirms 3 `settings.database_url` refs and 0 non-comment `sqlite:///` literals.
- Commit: `98202d7`

### Task 3 — GitHub Actions CI (.github/workflows/ci.yml)
- New workflow triggered on `push` and `pull_request`, one job `pg-parity` on `ubuntu-latest`.
- `services: postgres` → image `postgres:17`, `POSTGRES_PASSWORD: postgres`, ports `5432:5432`, `pg_isready` health check (interval 10s / timeout 5s / retries 5).
- Steps: checkout → `astral-sh/setup-uv` → `uv sync --dev` → SQLite suite (`uv run pytest`, no `DATABASE_URL`, so `tests/test_pg_parity.py` auto-skips) → PostgreSQL parity (`DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postgres uv run pytest tests/test_pg_parity.py -x`).
- Commit: `465b682`

## Verification

- **Task 1:** `uv run pytest -x` → 982 passed, 5 skipped (PG parity tests skip on SQLite), 0 failed; `uv run ruff check app/db.py` clean; `tests/conftest.py` not in diff.
- **Task 2:** `uv run ruff check alembic/env.py` clean; `grep -c settings.database_url` = 3; non-comment `sqlite:///` literals = 0; `alembic upgrade head` on a throwaway sqlite DB completes 0001→0017.
- **Task 3:** structural greps pass — `image: postgres:17`, `pg_isready`, `test_pg_parity`, `postgresql+psycopg://postgres:postgres@localhost:5432` all present; SQLite step has no `DATABASE_URL`, parity step sets it to the local service.

## Deferred Verification (end-of-phase human check)

The plan's Task 3 `<human-check>` — confirming the GitHub Actions `pg-parity` job runs GREEN (real `alembic upgrade head` on empty postgres:17 for SRV-01, and all 5 `tests/test_pg_parity.py` assertions for SRV-01/SRV-02) — requires pushing the branch to GitHub. Per project config `human_verify_mode: end-of-phase`, this is carried to the end-of-phase verification gate. A local run is not possible on this Windows host without a docker PG on port 5432; CI is the deliverable proof.

## Deviations from Plan

None — plan executed exactly as written. No auth gates, no deviation rules triggered.

## Threat Model

The plan's threat register (T-26-01 tampering on PG ledgers, T-26-02 credential disclosure, T-26-03 URL/CI SQL tampering) is satisfied as designed: the CI job asserts append-only rejection (T-26-01), uses only the throwaway non-secret `postgres` password on an ephemeral container with no repo secret (T-26-02), and flows the URL through SQLAlchemy config with literal-seed parity SQL only (T-26-03). No new security surface introduced beyond the plan's model.

## Self-Check: PASSED
- FOUND: app/db.py (build_engine_from_url present)
- FOUND: alembic/env.py (settings.database_url present)
- FOUND: .github/workflows/ci.yml
- FOUND commit: 2ddec8a (Task 1)
- FOUND commit: 98202d7 (Task 2)
- FOUND commit: 465b682 (Task 3)
