---
phase: 27-shared-idempotent-merge-core
plan: 02
subsystem: services
tags: [merge, sync, idempotency, recompute, ledger, portable-sql, set-difference]

# Dependency graph
requires:
  - phase: 27-shared-idempotent-merge-core
    provides: "Plan 01 — merge.py format half (ExchangeBatch/MergeReport, KIND_TO_MODEL/FIELDS, parse_exchange) + tests/test_merge.py NDJSON factory (build_ndjson/record_line/record_from_orm)"
  - phase: 26-postgresql-portability-append-only-parity
    provides: "dual-dialect append-only triggers (INSERT permitted, UPDATE/DELETE blocked) + single settings.database_url engine surface"
  - phase: 25-authentication-roles-user-attribution
    provides: "author_id/created_by attribution + per-install device_id carried verbatim on the wire"
provides:
  - "app/services/ledger.py — recompute_derived(session): non-committing Product.quantity + Batch.quantity recompute + invariant assert (rebuild_stock delegates then commits, behavior-preserving)"
  - "app/services/merge.py — apply_merge(session, batch, *, server_now): idempotent verbatim ledger append (operations + cash_movements) + post-merge recompute; NEVER commits (caller owns the transaction)"
  - "app/services/merge.py — _insert_new(session, model, rows): portable pre-select set-difference bulk insert-if-new by UUID PK, chunked at 500"
  - "MergeReport.operations_inserted/operations_skipped/cash_inserted/cash_skipped now populated"
  - "tests/test_merge.py — SYNC-02/03 dimensions: merge-twice==once, verbatim replay, duplicate-UUID skip, stock/cash recompute, two-device union, atomic rollback, non-committing recompute"
affects: [27-03, 28-central-server-sync-api, 29-online-client-sync, 30-offline-self-uploading-file]

# Tech tracking
tech-stack:
  added: []  # stdlib + already-installed SQLAlchemy only — no new packages
  patterns:
    - "Portable idempotent insert-if-new: pre-select existing UUIDs (chunked WHERE id IN), Python set-difference, bulk Core insert(model) — no sqlalchemy.dialects, no on_conflict, no raw SQL"
    - "Verbatim ledger append: build column dicts restricted to schema-derived KIND_TO_FIELDS, preserve origin id/device_id/seq/author_id/created_by/created_at, force synced_at=None — never route through the interactive write path (no identity re-mint)"
    - "Pure engine / caller-owned atomicity: apply_merge never commits; a poisoned mid-batch record rolls back to exactly the prior state (all-or-nothing)"
    - "Non-committing recompute extraction: recompute_derived does the passes + invariant assert; rebuild_stock delegates then commits (behavior-preserving refactor)"

key-files:
  created: []
  modified:
    - app/services/ledger.py
    - app/services/merge.py
    - tests/test_merge.py

key-decisions:
  - "recompute_derived is the extracted non-committing core of rebuild_stock (two passes + invariant assert); rebuild_stock is now a thin delegate-then-commit wrapper so every existing caller sees identical behavior"
  - "_insert_new chunks incoming ids at 500 (well under SQLite's ~999 bound-param cap) so a large upload's WHERE id IN (...) never overflows on SQLite while staying portable to PostgreSQL"
  - "_ledger_row restricts the verbatim dict to the model's own schema-derived columns (KIND_TO_FIELDS) and forces synced_at=None — a stray wire field can't reach the insert and the server-owned sync cursor is never trusted"
  - "apply_merge processes ONLY the two ledger kinds this plan; the FK-ordered reference-upsert stage is a documented empty seam BEFORE the ledger appends for Plan 03 (server_now is threaded through for it)"

patterns-established:
  - "Pattern: portable set-difference bulk insert-if-new (SYNC-02 idempotency core) — the one dedup path across both dialects"
  - "Pattern: verbatim append preserving origin provenance, distinct from record_operation's identity-minting write path"

requirements-completed: [SYNC-02, SYNC-03]

# Metrics
duration: ~20min
completed: 2026-07-19
---

# Phase 27 Plan 02: apply_merge Idempotent Ledger Append + Recompute Summary

**The SYNC-02/03 correctness core: a portable, idempotent verbatim ledger append inside a pure, commit-free `apply_merge`, followed by a ledger-derived stock recompute — so re-syncing the same data twice changes nothing and counts stay correct after every merge.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2
- **Files modified:** 3 (ledger.py, merge.py, test_merge.py)

## Accomplishments

- Extracted `recompute_derived(session)` from `rebuild_stock` — the two ledger→cache passes + per-product invariant assert, WITHOUT committing. `rebuild_stock` now delegates to it then commits, a behavior-preserving refactor: every existing caller (rebuild scripts, the whole `test_ledger.py` suite) sees the identical recompute + commit + raise-on-mismatch.
- Implemented `_insert_new` — the portable idempotent insert-if-new: pre-select the already-present UUIDs (chunked at 500 for SQLite's bound-param cap), filter them out as a Python set-difference, and bulk-insert the remainder with a generic Core `insert(model)`. No `sqlalchemy.dialects`, no `on_conflict`, no raw SQL. Replaying the same rows finds every id present → `inserted == 0` → a true no-op.
- Implemented `apply_merge(session, batch, *, server_now)` for the ledger stage: buckets `operation` + `cash_movement` records, builds verbatim column dicts (origin `id`/`device_id`/`seq`/`author_id`/`created_by`/`created_at` preserved, `synced_at` forced None), inserts each ledger via `_insert_new`, populates the `MergeReport` counters, then calls `recompute_derived`. It NEVER commits — the caller owns the single all-or-nothing transaction, and the recompute's invariant `ValueError` propagates to reject an internally inconsistent batch.
- Left a documented empty seam for Plan 03's FK-ordered reference-upsert stage, ordered BEFORE the ledger appends.
- Proved the guarantees with 8 new tests (7 SYNC-02/03/04 + the non-committing recompute check): merge-twice==once (byte-identical snapshot, 0 second-apply inserts), verbatim replay, duplicate-UUID skip, stock + cash recompute cross-checked against the ledger, order-independent two-device stock union, and atomic rollback (a poisoned record leaves 0 rows).

## Task Commits

1. **Task 1: Extract non-committing recompute_derived from rebuild_stock** — `1a85fe2` (refactor)
2. **Task 2: apply_merge ledger-append core — portable idempotent insert + recompute** — `0a025c7` (feat)

## Files Created/Modified

- `app/services/ledger.py` — Added `recompute_derived(session)` (non-committing recompute + invariant assert); `rebuild_stock` reduced to `recompute_derived(session)` + `session.commit()`. `compute_stock`/`compute_batch_stock`/`record_operation` untouched.
- `app/services/merge.py` — Added `_insert_new` (portable set-difference bulk insert), `_ledger_row` (verbatim schema-restricted dict + synced_at→None), `apply_merge` (ledger stage + recompute, no commit), the `_IN_CHUNK`/`_LEDGER_INSERT_ORDER` constants, and the `insert`/`select`/`Session`/`recompute_derived` imports. Populates the `MergeReport` counters.
- `tests/test_merge.py` — Added the SYNC-02/03 dimension suite + `test_recompute_derived_does_not_commit`, plus the `_op`/`_cash`/`_apply`/`_seed_user`/`_snapshot` helpers (reusing the Plan 01 `build_ndjson`/`record_line` factory). 20 tests total in the module, all green.

## Decisions Made

- **Behavior-preserving extraction:** `recompute_derived` holds the entire recompute + invariant logic; `rebuild_stock` is now a two-line wrapper. This keeps the merge one caller-owned transaction while guaranteeing zero change for interactive callers.
- **Chunk size 500:** comfortably under SQLite's ~999 bound-param cap for `WHERE id IN (...)`, and harmless on PostgreSQL — one portable code path (RESEARCH Pitfall 3).
- **Schema-restricted verbatim dict:** `_ledger_row` builds `{col: data.get(col) for col in KIND_TO_FIELDS[kind]}` so the bulk insert has uniform keys and no stray wire field can slip in; `synced_at` is always forced None (server-owned).
- **Ledger-only scope with a documented seam:** `apply_merge` ignores reference kinds this plan (tests seed them via fixtures); the reference-upsert stage is a clearly marked empty block BEFORE the ledger appends for Plan 03.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed with their specified functions, tests, and acceptance criteria (ruff clean, per-file and full `pytest` green, portability/purity grep gate == 0).

## Verification

- `uv run ruff check app/services/ledger.py app/services/merge.py tests/test_merge.py` — clean.
- `uv run pytest tests/test_merge.py -q` — 20 passed.
- `uv run pytest -q` (full regression) — 1002 passed, 5 skipped (recompute extraction confirmed behavior-preserving; +7 net new merge tests over the pre-plan baseline).
- Portability/purity grep gate on `merge.py` — `0` (no `sqlalchemy.dialects`, no `on_conflict`, no `INSERT OR`, no write-path re-mint, no internal `.commit(`).

## Next Phase Readiness

- `apply_merge` and `_insert_new` are ready for Plan 03 to slot the FK-ordered reference-upsert stage (warehouses→products→…→sales) + `Product.code` collision rename into the documented seam BEFORE the ledger appends; `MergeReport.reference_inserted`/`reference_server_wins`/`conflicts` are declared and waiting.
- `recompute_derived` gives Plan 03 (and Phases 28/30 callers) the non-committing recompute for the same one-transaction contract.
- No Alembic migration (engine runs on the existing 0001→0017 schema — RESEARCH A8), unchanged and correct.

## Self-Check: PASSED

- FOUND: app/services/merge.py
- FOUND: app/services/ledger.py
- FOUND: tests/test_merge.py
- FOUND commit: 1a85fe2 (Task 1)
- FOUND commit: 0a025c7 (Task 2)
- Source assertions: `def recompute_derived` in ledger.py; `def apply_merge` + `def _insert_new` in merge.py

---
*Phase: 27-shared-idempotent-merge-core*
*Completed: 2026-07-19*
