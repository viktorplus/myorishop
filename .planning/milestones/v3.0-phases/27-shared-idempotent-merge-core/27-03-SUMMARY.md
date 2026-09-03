---
phase: 27-shared-idempotent-merge-core
plan: 03
subsystem: services
tags: [merge, sync, conflict-resolution, server-wins, fk-ordering, tombstone, product-code, idempotency, portable-sql]

# Dependency graph
requires:
  - phase: 27-shared-idempotent-merge-core
    provides: "Plan 02 — apply_merge ledger-append core + _insert_new (portable set-difference) + the documented reference-upsert seam before the ledger stage; MergeReport.reference_inserted/reference_server_wins/conflicts declared"
  - phase: 27-shared-idempotent-merge-core
    provides: "Plan 01 — NDJSON format (KIND_TO_MODEL/FIELDS, parse_exchange) + Conflict dataclass + tests/test_merge.py factory (build_ndjson/record_line)"
provides:
  - "app/services/merge.py — _upsert_reference(session, model, rows, *, conflicts=None): insert-if-new, row-level server-wins reference upsert (discards existing UUIDs); runs the Product.code collision pass for Product"
  - "app/services/merge.py — reference-upsert stage inside apply_merge, FK-ordered (warehouses→products→customers→dictionary→batches→sales) BEFORE the ledger append, kind-driven (shuffled file merges identically)"
  - "app/services/merge.py — _resolve_code_collisions(session, product_rows, conflicts): probe active incumbent, rename incoming loser, keep UUID, append Conflict; _suffix_code(code, row_id): deterministic UUID-derived suffix fitting String(20)"
  - "app/services/merge.py — _partition_new(session, model, rows): extracted shared portable set-difference (_insert_new + _upsert_reference both use it); _reference_row: verbatim schema-restricted dict, drops cached quantity to 0"
  - "MergeReport.reference_inserted / reference_server_wins / conflicts now populated by apply_merge"
  - "tests/test_merge.py — SYNC-05 dimensions: server-wins, FK-order/shuffle, missing-parent rollback, inline tombstone, Product.code rename + determinism"
affects: [28-central-server-sync-api, 29-online-client-sync, 30-offline-self-uploading-file]

# Tech tracking
tech-stack:
  added: []  # stdlib + already-installed SQLAlchemy only — no new packages
  patterns:
    - "Reference upsert = insert-if-new + row-level server-wins: an existing UUID is discarded (server authoritative), never field-merged, never deleted_at→NULL, never DELETEd from client input"
    - "FK-dependency insert order driven by KIND (not NDJSON line order): a shuffled file merges identically; a missing parent fails the child FK insert and the caller rolls the whole batch back (all-or-nothing)"
    - "Deterministic collision rename: _suffix_code derives the marker from the losing UUID only (no random, no time) so re-merge renames identically and stays idempotent; the incumbent keeps the clean code, the loser keeps its UUID"
    - "Never trust a synced cache: _reference_row drops the wire quantity to 0; recompute_derived rebuilds Product.quantity/Batch.quantity from the merged ledger"

key-files:
  created: []
  modified:
    - app/services/merge.py
    - tests/test_merge.py

key-decisions:
  - "Extracted _partition_new as the ONE portable set-difference primitive so _insert_new (ledger) and _upsert_reference (reference) share exactly one dedup path (no dialect SQL, no on_conflict)"
  - "_upsert_reference reuses _partition_new then bulk-inserts only new rows; existing UUIDs are counted as server_wins and discarded — insert-only, no UPDATE/DELETE (grep gate == 0)"
  - "_resolve_code_collisions runs on the Product to-insert rows AFTER the set-difference and BEFORE the bulk insert, inside _upsert_reference; the partial unique index uq_products_code_active stays the DB backstop"
  - "_suffix_code = base truncated to fit String(20) + '~' + first 4 hex chars of the losing UUID; deterministic in the UUID only (Pitfall 7), so merge-twice renames identically"
  - "_reference_row forces quantity=0 for product/batch (cached-quantity kinds) — the wire quantity is a stale cache; recompute_derived is the truth after merge"

patterns-established:
  - "Pattern: FK-ordered, kind-driven reference upsert before the ledger append — the server-authoritative half of the merge (SYNC-05)"
  - "Pattern: deterministic non-interactive duplicate-code resolution (rename the loser, keep UUID, report) — mirrors catalog's probe without its RU UX error"

requirements-completed: [SYNC-05]

# Metrics
duration: ~18min
completed: 2026-07-19
---

# Phase 27 Plan 03: Reference Upsert + Product.code Collision Rename Summary

**The server-authoritative half of the merge engine (SYNC-05): `apply_merge` now upserts reference rows insert-if-new with row-level server-wins in FK order before the ledger, honors inline `deleted_at` tombstones without ever resurrecting/deleting a server row, and renames a cross-device `Product.code` loser deterministically (keeping its UUID so its ledger rows stay valid) while the incumbent keeps the clean code — reported in `MergeReport.conflicts`.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 2
- **Files modified:** 2 (merge.py, test_merge.py)

## Accomplishments

- Extracted `_partition_new(session, model, rows)` — the portable pre-select set-difference — as the single dedup primitive, and refactored `_insert_new` onto it (behavior-preserving). Both the ledger append and the reference upsert now share exactly one chunked, dialect-free `WHERE id IN (...)` path.
- Implemented `_upsert_reference(session, model, rows, *, conflicts=None)` — insert-if-new with **row-level server-wins**: a NEW UUID inserts verbatim (including any inline `deleted_at`); an EXISTING UUID is discarded and counted as `server_wins`. Insert-only — never UPDATE, never `deleted_at`→NULL, never DELETE a server row from client input (DD-1 / DD-1b). For `Product` it runs the code-collision pass on the to-insert rows before the bulk insert.
- Wired the **FK-ordered reference stage** into `apply_merge` BEFORE the ledger appends: buckets records by kind and upserts warehouses → products → customers → dictionary → batches → sales. Ordering is driven by kind, not NDJSON line order, so a shuffled file merges identically; a missing referenced parent makes the child ledger FK insert fail and the caller rolls the whole batch back (all-or-nothing). `_reference_row` restricts each row to schema columns and drops the wire `quantity` to 0 for product/batch (recompute rebuilds it — never trust a synced cache).
- Implemented `_suffix_code(code, row_id)` (deterministic marker = `"~"` + first 4 hex chars of the losing UUID, base truncated to fit `String(20)`) and `_resolve_code_collisions(session, product_rows, conflicts)` (probe an active incumbent with a different UUID, rename the incoming loser keeping its UUID, leave the incumbent's clean code intact, append a `product_code` `Conflict`). Deterministic in the UUID only, so re-merge renames identically (Pitfall 7).
- Populated `MergeReport.reference_inserted` / `reference_server_wins` (per-kind) and `conflicts`.
- Proved the guarantees with 6 new tests (24→26 in the module): server-wins on an existing reference, FK-order/shuffle, missing-parent all-or-nothing rollback, inline tombstone (new soft-deleted inserts; server row never flipped), `Product.code` rename (incumbent keeps code, loser keeps UUID + its op inserts + reported, len ≤ 20), and rename determinism across a re-merge.

## Task Commits

1. **Task 1: Reference upsert stage — server-wins, FK-ordering, inline tombstone (SYNC-05 / DD-1 / DD-1b)** — `66971c6` (feat)
2. **Task 2: Product.code cross-device collision — rename the loser, keep UUID, report (SYNC-05 / DD-2)** — `607b78a` (feat)

## Files Created/Modified

- `app/services/merge.py` — Added `_partition_new` (shared set-difference), refactored `_insert_new` onto it; added `_reference_row`, `_upsert_reference`, `_suffix_code`, `_resolve_code_collisions`; added `_REFERENCE_INSERT_ORDER`, `_CACHED_QUANTITY_KINDS`, and the code-length constants. Wired the FK-ordered reference stage into `apply_merge` before the ledger append and updated its docstring. Populates `MergeReport.reference_inserted/reference_server_wins/conflicts`.
- `tests/test_merge.py` — Added the SYNC-05 suite + `_product_rec`/`_warehouse_rec`/`_batch_rec` reference-record helpers (reusing the Plan 01 `build_ndjson`/`record_line` factory and Plan 02 `_op`/`_apply`). Added `Warehouse` to the model import. 26 tests total, all green.

## Decisions Made

- **One dedup primitive:** `_partition_new` is the sole portable set-difference; `_insert_new` and `_upsert_reference` both call it. No second implementation, no dialect fork.
- **Collision pass placement:** `_resolve_code_collisions` runs inside `_upsert_reference` for `Product`, AFTER the set-difference (so it only touches rows that will actually insert) and BEFORE the bulk insert; the partial unique index `uq_products_code_active` remains the DB backstop.
- **Deterministic rename:** the marker is derived from the losing UUID's hex only (no random/time), base truncated so `base + "~xxxx"` ≤ 20 chars — re-merge is a true no-op on the code.
- **Cache never trusted:** `_reference_row` zeroes the wire `quantity` for product/batch; `recompute_derived` (Plan 02) is the post-merge truth.

## Deviations from Plan

None — plan executed exactly as written. Both tasks landed with their specified functions, tests, and acceptance criteria (ruff clean, per-file and full `pytest` green, insert-only + portability/purity grep gates == 0).

Note (as flagged in the plan, not a deviation): the **same-batch two-new-same-code** tie-break (two NEW products with the same code from different devices in one payload) is not exercised by a dedicated test — neither is an incumbent yet, so the probe finds no clash for either and both head for insert; the partial unique index `uq_products_code_active` then raises `IntegrityError` and the caller rolls back (all-or-nothing). The plan said to implement the earlier-`created_at`-then-smaller-UUID tie-break "only if naturally covered, else note" — it is not naturally covered by the incumbent-probe design, so it is noted here for a future in-payload dedup pass (Phase 28/29 admin reconciliation surface).

## Known Stubs

None — the reference stage is fully wired (real set-difference, real FK-ordered inserts, real collision probe against the DB); no placeholder/empty-data paths introduced.

## Verification

- `uv run ruff check app/services/merge.py tests/test_merge.py` — clean.
- `uv run pytest tests/test_merge.py -q` — 26 passed.
- `uv run pytest -q` (full regression) — 1008 passed, 5 skipped (+6 net new merge tests over the Plan 02 baseline of 1002).
- Insert-only gate on `merge.py` — `grep -v '^#' ... | grep -Ec 'session\.delete|\.delete\('` == `0`.
- Portability/purity gate on `merge.py` — `grep -Ec 'sqlalchemy\.dialects|on_conflict|INSERT OR|\.commit\('` == `0`.

## Next Phase Readiness

- `apply_merge` is now the complete server-side merge engine (reference upsert + idempotent ledger append + recompute), still commit-free — Phases 28 (online sync API) and 30 (offline self-upload) are thin callers wrapping it in one transaction.
- `MergeReport.conflicts` carries the `Product.code` renames for a Phase 28/29 admin "duplicate codes to reconcile" surface.
- Plan 04 (PostgreSQL portability slice + pg-parity CI) closes Phase 27; the merge engine already uses only portable Core/ORM constructs, so it should run unchanged on both dialects.

## Self-Check: PASSED

- FOUND: app/services/merge.py
- FOUND: tests/test_merge.py
- FOUND commit: 66971c6 (Task 1)
- FOUND commit: 607b78a (Task 2)
- Source assertions: `def _upsert_reference`, `def _resolve_code_collisions`, `def _suffix_code` in merge.py; `def test_product_code_collision_renamed` in test_merge.py

---
*Phase: 27-shared-idempotent-merge-core*
*Completed: 2026-07-19*
