---
phase: 27-shared-idempotent-merge-core
plan: 04
subsystem: tests
tags: [merge, sync, postgresql, portability, idempotency, product-code, ci, pg-parity, skipif]

# Dependency graph
requires:
  - phase: 27-shared-idempotent-merge-core
    provides: "Plan 03 — the complete server-side merge engine (reference upsert server-wins + idempotent ledger append + recompute + Product.code collision rename); _suffix_code / apply_merge / parse_exchange"
  - phase: 26-postgresql-portability-append-only-parity
    provides: "settings.database_url single source of truth + tests/test_pg_parity.py skipif harness + pg-parity CI job on postgres:17"
provides:
  - "tests/test_merge_pg.py — PostgreSQL portability slice: merge-twice==once idempotency + Product.code collision rename proven on PG, skipif-guarded on dialect, literal-constant seeds"
  - ".github/workflows/ci.yml — pg-parity job extended with a 'PostgreSQL merge portability' step running tests/test_merge_pg.py against postgres:17 (one engine, both dialects)"
affects: [28-central-server-sync-api, 29-online-client-sync, 30-offline-self-uploading-file]

# Tech tracking
tech-stack:
  added: []  # no new packages — psycopg already added in Phase 26; CI uv sync --dev unchanged
  patterns:
    - "Portability proof by re-running the ONE engine on a real postgres:17 in CI — a dialect-specific construct (accidental on_conflict) would turn the pg-parity job red (SYNC-04 one engine, never two)"
    - "PG test slice mirrors the Phase 26 harness: module-level pytest.mark.skipif on settings.database_url, _engine()/_upgrade_head() helpers, sessionmaker(bind=engine) + try/finally engine.dispose()"
    - "Literal-constant seeds / fixed UUIDs only (no external data f-stringed into SQL, ASVS V5); ledger rows are append-only so a re-run's set-difference finds them present — idempotent assertions on final DB state, not on fresh-vs-rerun insert counts"

key-files:
  created:
    - tests/test_merge_pg.py
  modified:
    - .github/workflows/ci.yml

key-decisions:
  - "New dedicated tests/test_merge_pg.py (the plan's default) keeps the merge slice self-contained rather than extending tests/test_pg_parity.py"
  - "Added a separate CI step 'PostgreSQL merge portability (SYNC-02/04/05)' to the EXISTING pg-parity job (no new job) for a clear per-slice CI signal; same throwaway postgres DATABASE_URL"
  - "Idempotency asserted via a snapshot of derived state (product/batch quantity + cash balance) around a second apply + report2.operations_inserted/cash_inserted==0 & skipped==1 — re-run-safe (no reliance on global row counts or fresh-DB insert counts)"
  - "Collision assert uses _suffix_code(_CODE, _LOSER_ID) for a deterministic, re-run-safe expected rename; incumbent seeded via INSERT ... ON CONFLICT DO NOTHING (literal constants) so the harness re-runs against a standing PG server"

patterns-established:
  - "Pattern: prove a portable engine on both dialects by re-running its idempotency + conflict core on postgres:17 in the existing pg-parity CI job (skipif-guarded so local SQLite runs skip it)"

requirements-completed: [SYNC-02, SYNC-04, SYNC-05]

# Metrics
duration: ~9min
completed: 2026-07-19
---

# Phase 27 Plan 04: PostgreSQL Portability Slice + pg-parity CI Wiring Summary

**The ONE merge engine (`app/services/merge.py`) is now proven portable on both dialects: `tests/test_merge_pg.py` re-runs its idempotency (merge-twice==once via the portable pre-select set-difference) and its `Product.code` collision rename against a real `postgres:17`, skipif-guarded so local SQLite runs skip cleanly — and the existing `pg-parity` CI job runs that slice with `DATABASE_URL` set, making SYNC-04's "one engine, never two divergent implementations" real on SQLite (client) and PostgreSQL (server).**

## Performance

- **Duration:** ~9 min
- **Tasks:** 2
- **Files:** 1 created (test_merge_pg.py), 1 modified (ci.yml)

## Accomplishments

- Created `tests/test_merge_pg.py` — a PostgreSQL portability slice reusing the Phase 26 harness (module-level `pytest.mark.skipif(not settings.database_url.startswith("postgresql"), …)`, `_engine()`, `_upgrade_head()`, `sessionmaker(bind=engine)` + `try/finally: engine.dispose()`). Two focused tests exercise the real `apply_merge`/`parse_exchange` engine on PG:
  - `test_merge_idempotent_on_pg` — merges a reference warehouse/product/batch + an operation + a cash_movement, then re-applies the SAME parsed batch: asserts `report2.operations_inserted == 0`, `cash_inserted == 0`, `operations_skipped == 1`, `cash_skipped == 1`, and that a snapshot of `(product.quantity, batch.quantity, compute_balance)` is unchanged — proving the portable set-difference (not a dialect `on_conflict`) holds on PostgreSQL (SYNC-02/04).
  - `test_code_collision_on_pg` — seeds an active incumbent with a fixed code, merges a NEW product (different UUID) carrying the same code + a referencing operation, and asserts the incumbent keeps the code, the loser is renamed to exactly `_suffix_code(_CODE, _LOSER_ID)` (`~` + 4 UUID-hex chars, ≤ 20 chars) keeping its UUID, and its operation inserted against PG's `postgresql_where` partial unique index `uq_products_code_active` (SYNC-05).
- Seeds use only literal-constant strings / fixed UUIDs (no external data f-stringed into SQL, ASVS V5 / T-27-05); fixed UUIDs + `INSERT … ON CONFLICT DO NOTHING` for the incumbent keep the module re-runnable against a standing PG server (ledger rows can never be DELETEd, so a re-run's set-difference simply finds them present).
- Extended the EXISTING `pg-parity` job in `.github/workflows/ci.yml` (no new job) with a step **"PostgreSQL merge portability (SYNC-02/04/05 one engine, both dialects)"** that sets the same throwaway `DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/postgres` and runs `uv run pytest tests/test_merge_pg.py -x`. The SQLite suite step (no `DATABASE_URL`) still covers `tests/test_merge.py` and auto-skips the PG slice.

## Task Commits

1. **Task 1: PostgreSQL portability slice — idempotency + code collision on PG (SYNC-02/04/05)** — `ff099e4` (test)
2. **Task 2: Wire the merge PG slice into the pg-parity CI job (SYNC-04 both-dialects proof)** — `8b22038` (ci)

## Files Created/Modified

- `tests/test_merge_pg.py` (created) — skipif-guarded PG portability slice; `_engine`/`_upgrade_head` helpers + local literal-constant NDJSON builders (`_rec`/`_ndjson`/`_apply`); `test_merge_idempotent_on_pg`, `test_code_collision_on_pg`. Imports the real engine (`apply_merge`, `parse_exchange`, `_suffix_code`, `FORMAT_VERSION`) — no engine code changed.
- `.github/workflows/ci.yml` (modified) — added one step to the existing `pg-parity` job invoking `tests/test_merge_pg.py` against `postgres:17` with `DATABASE_URL` set. No new job; no real/production secret.

## Deviations from Plan

None — plan executed exactly as written. No changes to `app/services/merge.py` or `app/services/ledger.py` (scope fence respected); no new CI job (existing `pg-parity` extended); no Alembic migration.

## Known Stubs

None — the slice exercises the real engine end-to-end; the assertions are on real DB state, not placeholders. (PG execution runs in CI; locally on Windows/SQLite the module correctly skips.)

## Verification

- `uv run ruff check tests/test_merge_pg.py` — clean.
- `uv run pytest tests/test_merge_pg.py -q` — `2 skipped` on SQLite (skips cleanly, no collection error), as designed.
- Security V5: `grep -i 'f"…(INSERT|SELECT|UPDATE|DELETE)'` on the file — 0 matches (no dynamic data f-stringed into SQL).
- `.github/workflows/ci.yml` — `grep -q 'test_merge_pg'` and `grep -q 'postgresql+psycopg://postgres:postgres@localhost:5432'` both pass; YAML parses with a SINGLE `pg-parity` job (no new job added).
- Full local regression `uv run pytest -q` — **1008 passed, 7 skipped** (the 2 new PG merge tests + the 5 Phase 26 pg-parity tests skip on SQLite); post-wave gate green.
- **Human-check / phase gate (pending CI):** push and confirm the GitHub Actions `pg-parity` job is GREEN including the new merge PG step — idempotency + `Product.code` collision both hold on `postgres:17`, proving the portable pre-select set-difference and the `postgresql_where` partial index behave identically to SQLite. Local Windows runs skip the PG slice; CI is the deliverable proof.

## Next Phase Readiness

- Phase 27 is COMPLETE (4/4 plans). `app/services/merge.py` is the one shared, portability-proven server-side merge engine (reference upsert server-wins + idempotent ledger append + recompute + `Product.code` collision rename), still commit-free.
- Phase 28 (Central Server — Hosting & Sync API) and Phase 30 (Offline Self-Uploading File) are thin callers that wrap `apply_merge` in one transaction; both inherit an engine proven on both dialects.
- The PG portability slice is the template for any future dialect-sensitive merge behavior — add a skipif-guarded test to `tests/test_merge_pg.py` and it runs automatically in the `pg-parity` job.

## Self-Check: PASSED

- FOUND: tests/test_merge_pg.py
- FOUND: .github/workflows/ci.yml (extended)
- FOUND commit: ff099e4 (Task 1)
- FOUND commit: 8b22038 (Task 2)
- Source assertions: `pytestmark = pytest.mark.skipif` + `def test_merge_idempotent_on_pg` + `def test_code_collision_on_pg` in test_merge_pg.py; `test_merge_pg` invocation under the postgres DATABASE_URL step in ci.yml

---
*Phase: 27-shared-idempotent-merge-core*
*Completed: 2026-07-19*
