---
phase: 01-foundation-ledger-core
plan: 02
subsystem: database
tags: [sqlalchemy, alembic, sqlite, pydantic-settings, wal, append-only-ledger]

# Dependency graph
requires:
  - phase: 01-01
    provides: uv project scaffold, pinned deps, RED test contract (tests/conftest.py imports app.db/app.models/app.core)
provides:
  - app.config.settings (db_path, operator_name, device_id, display_tz via pydantic-settings)
  - app.core helpers (new_id, utcnow_iso, to_cents, format_cents, iso_to_local)
  - app.db (build_engine with PRAGMA listener, engine, SessionLocal, get_session, APPEND_ONLY_TRIGGERS)
  - app.models (Base with naming convention, Product, Operation, OPERATION_TYPES)
  - Alembic migration 0001 applied — data/myorishop.db with append-only triggers and demo product
affects: [01-03, foundation-ledger-core]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - per-connection PRAGMA event listener with autocommit save/restore (WAL, foreign_keys, busy_timeout)
    - single-source trigger DDL (app.db.APPEND_ONLY_TRIGGERS shared by migration and test fixtures)
    - hand-written Alembic migrations as schema source of truth (no autogenerate, no create_all outside tests)
    - naming convention on MetaData from day one (batch-migration safety)

key-files:
  created:
    - app/config.py
    - app/core.py
    - app/db.py
    - app/models.py
    - alembic.ini
    - alembic/env.py
    - alembic/script.py.mako
    - alembic/versions/0001_initial_schema.py
  modified: []

key-decisions:
  - "raw sqlite3 surfaces RAISE(ABORT) as IntegrityError (not OperationalError); tests already catch both"
  - "datetime.UTC alias used instead of timezone.utc (ruff UP017, py313 target)"
  - "alembic/README committed alongside scaffold (no untracked generated files)"

patterns-established:
  - "All money/time/id conversions go through app.core helpers only"
  - "Any future batch migration recreating operations MUST re-execute APPEND_ONLY_TRIGGERS (documented in migration docstring)"
  - "v1 triggers block ALL updates incl. synced_at; v2 sync relaxes with WHEN clause in a new migration"

requirements-completed: [FND-01, FND-02, FND-03]

# Metrics
duration: 5min
completed: 2026-07-08
---

# Phase 01 Plan 02: Data Foundation Summary

**Sync-ready SQLite schema live: SQLAlchemy 2.0 models with UUID4 TEXT PKs / integer cents / UTC ISO text, per-connection WAL+FK PRAGMAs, and Alembic migration 0001 installing DB-level append-only triggers plus a seeded demo product**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-08T12:49:32Z
- **Completed:** 2026-07-08T12:54:35Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- Four app core modules implemented against the 01-01 RED contract: `app.config` (pydantic-settings, .env override), `app.core` (Decimal-based `to_cents` rejecting garbage, comma-separator `format_cents`, `utcnow_iso` with tz-aware offset, `iso_to_local` display), `app.db` (engine factory with the official autocommit-safe PRAGMA listener), `app.models` (2.0-style `DeclarativeBase`/`Mapped`, naming convention, `UNIQUE(device_id, seq)`)
- Alembic operational with `render_as_batch=True` in both offline and online paths; URL forced from `settings.db_path`
- Migration 0001 (hand-written, revision "0001") created `products` + `operations`, executed both `APPEND_ONLY_TRIGGERS` from the single DDL source in `app.db`, and seeded demo product "Демо-товар" (DEMO-001, id `00000000-0000-4000-8000-000000000001`)
- `data/myorishop.db` at head; re-running `alembic upgrade head` is a no-op
- Verified in a throwaway DB copy: `UPDATE`/`DELETE` on `operations` abort with "operations ledger is append-only" while `products` stays mutable
- `tests/test_pragmas.py` GREEN (WAL / foreign_keys=1 / busy_timeout=5000 on a live pooled connection); ruff clean

## Task Commits

Each task was committed atomically:

1. **Task 1: App core — config, helpers, engine with PRAGMA listener, models** - `93c910e` (feat)
2. **Task 2: Alembic setup + migration 0001 (schema, triggers, demo seed)** - `d2c021a` (feat)

## Files Created/Modified

- `app/config.py` - `Settings(BaseSettings)` with db_path/operator_name/device_id/display_tz + module singleton `settings`
- `app/core.py` - `new_id`, `utcnow_iso`, `to_cents`, `format_cents`, `iso_to_local` (Decimal only, never float)
- `app/db.py` - `build_engine` (mkdir + PRAGMA listener with autocommit dance), module `engine`, `SessionLocal`, `get_session`, `APPEND_ONLY_TRIGGERS`
- `app/models.py` - `NAMING_CONVENTION`, `Base`, `OPERATION_TYPES`, `Product` (soft delete, cached quantity), `Operation` (D-08 column set, indexed FK, unique device_id+seq)
- `alembic.ini` - default scaffold; sqlalchemy.url placeholder (env.py overrides)
- `alembic/env.py` - target_metadata = Base.metadata, settings-driven URL, render_as_batch=True (x2)
- `alembic/script.py.mako` + `alembic/README` - alembic init scaffold
- `alembic/versions/0001_initial_schema.py` - tables + triggers + demo seed + batch-caveat docstring; downgrade drops triggers then tables

## Decisions Made

- **RAISE(ABORT) error class:** raw sqlite3 raises `IntegrityError` for trigger aborts (SQLAlchemy wraps it); the test contract already catches `(OperationalError, IntegrityError)` so no test change was needed — acceptance probe adjusted to catch both
- **`datetime.UTC` over `timezone.utc`:** ruff UP017 (py313 target) enforced the alias; semantics identical
- **alembic/README committed:** generated by `alembic init`; committing avoids untracked generated files

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Ruff UP017 failure on `timezone.utc`**

- **Found during:** Task 1 verification (`uv run ruff check app/`)
- **Issue:** `datetime.now(timezone.utc)` fails the project's UP lint rule on py313
- **Fix:** Switched to `datetime.now(UTC)` alias; UTC-offset acceptance check re-verified
- **Files modified:** app/core.py
- **Commit:** 93c910e

**2. [Deviation - minor] Migration file authored directly instead of `alembic revision` + rename**

- **Found during:** Task 2
- **Issue:** Plan suggested generating a revision then renaming; writing `0001_initial_schema.py` by hand with `revision = "0001"` is equivalent and avoids a stray auto-named file
- **Fix:** Hand-authored file matching the script.py.mako structure; `alembic upgrade head` applies it cleanly and is idempotent at head
- **Files modified:** alembic/versions/0001_initial_schema.py
- **Commit:** d2c021a

---

**Total deviations:** 2 minor (1 lint auto-fix, 1 equivalent-path simplification). No scope creep, no architectural changes.

## Issues Encountered

- Raw sqlite3 driver reports trigger `RAISE(ABORT)` as `IntegrityError`, not `OperationalError` — only affected the standalone acceptance probe; SQLAlchemy-side tests were already written to accept both exception types.

## Known Stubs

None. `tests/test_ledger.py` and `tests/test_smoke.py` remain RED by contract (`app.services.ledger` and `app.main` arrive in Plan 01-03) — this is the planned wave state, not a stub.

## User Setup Required

None — migration already applied locally; no external services.

## Next Phase Readiness

- Plan 01-03 can now implement `app/services/ledger.py` (record_operation, next_seq, compute_stock, rebuild_stock) and `app/main.py` against a live schema
- Demo product `00000000-0000-4000-8000-000000000001` exists for the walking-skeleton correction flow
- Reminder for any future migration touching `operations` in batch mode: re-execute `APPEND_ONLY_TRIGGERS` (documented in 0001 docstring)

---

*Phase: 01-foundation-ledger-core*
*Completed: 2026-07-08*

## Self-Check: PASSED

All 8 created files plus data/myorishop.db exist on disk; commits 93c910e and d2c021a verified in git log.
