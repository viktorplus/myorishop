---
phase: quick-260721-ebn
plan: fix-dictionary-pull-crashing-on-code-bas
subsystem: sync
tags: [sync, dictionary, sqlalchemy, tdd]

# Dependency graph
requires:
  - phase: 29 (Online Client Sync)
    provides: sync_client.py's _apply_pull_page (D-14 client reference upsert)
provides:
  - "dictionary pull kind partitions/upserts by `code` instead of `id`, avoiding the UNIQUE(code) IntegrityError"
affects: [sync_client, dictionary]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-kind override inside a generic FK-ordered pull loop: special-case one kind's match key while every other kind keeps the shared by-id path"

key-files:
  created: []
  modified:
    - app/services/sync_client.py
    - tests/test_sync_client.py

key-decisions:
  - "Match dictionary rows by `code` (its DB UNIQUE key) instead of `id` for both partition and upsert, since local and server dictionaries are independently seeded and can carry the same code under different ids"
  - "Exclude both `id` and `code` from the update-fields set on a code-conflict row so the local row's identity is never overwritten by the server's differing id"
  - "app/services/merge.py left untouched — this is a client-pull-only fix; merge.py's shared by-id logic backs the server's ingest of every kind and was never the source of the bug"

patterns-established: []

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-07-21
---

# Quick Task 260721-ebn: Fix dictionary pull crashing on code-based UNIQUE collision

**Special-cased the `dictionary` kind in `_apply_pull_page` to partition/upsert by `code` instead of `id`, closing a live IntegrityError that degraded manual sync to `status='partial'` forever**

## Performance

- **Duration:** ~12 min (RED commit to GREEN commit + full suite verification)
- **Started:** 2026-07-21T10:21:20+02:00
- **Completed:** 2026-07-21T10:27:40+02:00
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments
- A pull page carrying a Dictionary record whose `code` already exists locally under a different `id` (independently-imported catalogs on client and server) no longer raises `sqlite3.IntegrityError` / `UniqueViolation` — the sync now completes with `status='ok'`.
- The local dictionary row (matched by `code`) is updated with the server's `name`/`catalogs`/`name_lc`/`rubric`/timestamps (server wins on master data, D-14), while its local `id` and `code` are left untouched.
- A genuinely new dictionary code (absent locally under any id) is still inserted as before, verbatim with the server's id.
- All other reference kinds (warehouse/product/customer/batch/sale) keep their existing by-id partition/upsert behavior unchanged.

## Task Commits

Root-caused and fixed as a single TDD task:

1. **Task 1: Partition/upsert the dictionary pull kind by code instead of id** — RED `9c0981b`, GREEN `c195ad8`

_TDD: RED test commit → GREEN implementation commit, as specified by the plan._

## Files Created/Modified
- `app/services/sync_client.py` - `_apply_pull_page` gained a `kind == "dictionary"` branch: collects incoming codes, queries existing local codes in one chunked `IN (...)` (reusing `merge._IN_CHUNK`), inserts rows for codes with no local match via `merge._reference_row`, and UPDATEs rows for codes that already exist locally (`update(Dictionary).where(Dictionary.code == row["code"])`, excluding both `id` and `code` from the written fields), then `continue`s past the generic by-id block for this kind.
- `tests/test_sync_client.py` - added `test_pull_dictionary_code_conflict_updates_local_row` (RED: proves the collision no longer crashes and the local row updates in place) and `test_pull_dictionary_new_code_still_inserts` (regression guard: a genuinely new code still inserts verbatim).

## Decisions Made
- Match key for `dictionary` pull upsert is `code` (its DB `UNIQUE` column), not `id` — this is the only reference kind independently reseeded on each side by `scripts/import_master_pricelist.py`, so it's the only kind needing this override.
- Both `id` and `code` are excluded from the update-fields set on a conflict row (not just `id`) since `code` is the match key here, not the immutable identity column the generic path excludes.
- `app/services/merge.py` was explicitly left untouched per the plan's scope boundary — it backs the SERVER's ingest of product/batch/sale/etc. via the shared by-id `_partition_new`/`_upsert_reference`, which was never the source of this bug (Dictionary is push-exempt; `collect_push_records` always emits `"dictionary": []`).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The fix is client-pull-only and self-contained; no follow-up work required in `merge.py` or the server side.
- Manual spot check against the real deployed server (per the plan's `<verification>` section) is a follow-up the operator can run by clicking «Синхронизировать» on the s1-deployed client whose local dictionary predates server pairing — not run here (no live server access from this task).
- Full project test suite (`uv run pytest -q`) passes: 1158 passed, 12 skipped, no regressions.

---
*Quick task: 260721-ebn-fix-dictionary-pull-crashing-on-code-bas*
*Completed: 2026-07-21*

## Self-Check: PASSED

All created/modified files and both commit hashes (9c0981b, c195ad8) verified present.
