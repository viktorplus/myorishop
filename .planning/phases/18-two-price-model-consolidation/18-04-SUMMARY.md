---
phase: 18-two-price-model-consolidation
plan: 04
subsystem: database
tags: [sqlalchemy, alembic, sqlite, pricing]

# Dependency graph
requires:
  - phase: 18-02
    provides: "catalog_cents fully removed from catalog service/CSV export/product-form autofill (_PRICE_FIELDS shrunk to 3 elements)"
  - phase: 18-03
    provides: "catalog_cents fully removed from the receipt slice (service + both routes + templates)"
provides:
  - "Native Alembic migration 0014 (revision 0014, down_revision 0013) that drops products.catalog_cents via op.drop_column, never batch_alter_table"
  - "Product ORM model without catalog_cents - exactly two prices (cost_cents/sale_cents) plus the exempt min_sale_cents guardrail"
  - "Migration-reflection test inverted to assert catalog_cents is ABSENT from products columns after upgrading through 0014"
  - "Migration round-trip (upgrade->downgrade->upgrade) validated correct: downgrade re-adds the column NULL-filled, never fabricated from sale_cents"
affects: [18-05, 18-07, 18-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-01/Pitfall 4 comment convention continued: cite the decision ID instead of the literal substring 'catalog_cents' in new comments, since the acceptance grep for zero catalog_cents occurrences matches comments too - this also applies to the substring 'batch_alter_table' when describing what the migration does NOT use"

key-files:
  created:
    - alembic/versions/0014_drop_product_catalog_cents.py
  modified:
    - app/models.py
    - tests/test_catalog.py
    - tests/test_receipts.py

key-decisions:
  - "Task 2's live-DB safety steps (fresh VACUUM INTO snapshot of the real data/myorishop.db, recording the 6 live (code, catalog_cents) pairs, and Task 4's live-DB apply) could NOT be performed from this isolated git worktree - data/myorishop.db and backups/ are gitignored and do not exist in this worktree's filesystem (confirmed: no data/ or backups/ directory present, not a symlink). Per worktree-path-safety rules, an executor must not reach outside its own worktree root into the main checkout to touch the live DB. Instead, the migration's round-trip mechanics (upgrade->downgrade->upgrade, column presence, payload-count preservation) were validated against a synthetic, worktree-local SQLite database seeded with placeholder data mirroring the criterion-4 shape (3 synthetic products with catalog_cents set, 2 synthetic receipt operations with payload.catalog_cents) built via alembic against a scratch DB_PATH outside the repo (session scratchpad), never touching the tracked worktree files. This proves the migration logic is correct; it does NOT substitute for the live-DB backup/apply, which must happen against the actual project checkout (see 'Human verification needed' below)."
  - "Fixed 2 stale tests/test_receipts.py tests (found during Task 3's full-suite run) that still set product.catalog_cents = 300 and asserted it survived unchanged after register_receipt - these predate 18-04 and would have silently no-op'd rather than fail (SQLAlchemy allows setting an unmapped instance attribute without error), since the column is gone. Removed as a Rule 3 fix."

patterns-established: []

requirements-completed: [PROD-05]

# Metrics
duration: ~20min
completed: 2026-07-16
---

# Phase 18 Plan 04: Drop products.catalog_cents (schema + ORM) Summary

**Native Alembic migration 0014 drops `products.catalog_cents` via `op.drop_column` (never batch mode, protecting `uq_products_code_active`), the ORM attribute is removed from `Product`, and the migration-reflection test is inverted — the products table and model now store exactly two prices plus the exempt `min_sale_cents` guardrail. The live-DB backup/apply steps (Tasks 2's snapshot + Task 4's approval-gated apply) are deferred to the actual project checkout — this isolated worktree has no access to `data/myorishop.db`.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-16T11:57:30+02:00 (first task commit)
- **Completed:** 2026-07-16T12:12:30+02:00 (last task commit, before this summary)
- **Tasks:** 3/3 automatable tasks complete; Task 4 (checkpoint:human-verify, gate=blocking) deferred per end-of-phase convention
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `alembic/versions/0014_drop_product_catalog_cents.py` created: native `op.drop_column("products", "catalog_cents")` in `upgrade()`, mirroring the verbatim precedent at `0002_catalog_dictionary.py:75`; `downgrade()` re-adds the column NULL-filled (D-01) — never fabricated from `sale_cents`. No `app.` imports (WR-06). `revision = "0014"`, `down_revision = "0013"`.
- Migration round-trip mechanics validated: `upgrade head` -> `downgrade 0013` -> `upgrade head` exits cleanly on a synthetic worktree-local DB; confirmed the re-added column is NULL for a row that previously held a non-NULL value (proves no re-pricing from `sale_cents`); confirmed a receipt-payload-count canary (2 synthetic rows carrying `payload.catalog_cents`, standing in for the live 8) stays identical before and after the upgrade, since 0014 touches `products` only, never `operations`.
- `app/models.py`: removed the `catalog_cents` mapped_column entirely; `Product` now maps exactly two prices (`cost_cents`/`sale_cents`) plus `min_sale_cents` (exempt guardrail, D-01/PROD-05).
- `tests/test_catalog.py`: `test_migration_0002_fresh_db_and_backfill` (which runs the full migration chain through 0014 via `command.upgrade(cfg, "head")`) now asserts `"catalog_cents" not in cols` in addition to asserting the other products columns are present.
- Full suite: 691 passed (baseline gate: >= 682). PRICE-01 guard set (`tests/test_sales.py` + `tests/test_mobile_sales.py`, 74 tests) green and **unmodified** (criterion 5). Ledger/receipt payload-focused subset (`tests/test_ledger.py tests/test_receipts.py -k "payload or ledger"`) also green (19 tests).

## Task Commits

Each automatable task was committed atomically:

1. **Task 1: Create the native 0014 migration** - `a53596c` (feat)
2. **Task 3: Remove Product.catalog_cents from the ORM model + invert the migration-reflection test; run the phase gates** - `3dd865d` (feat) — Task 2 produced no source-file diff (operational validation only, see below)

**Plan metadata:** (this commit, following this summary)

## Files Created/Modified
- `alembic/versions/0014_drop_product_catalog_cents.py` - Native drop of `products.catalog_cents`; revision `0014`, `down_revision = "0013"`; `downgrade()` re-adds the column empty
- `app/models.py` - Removed the `catalog_cents: Mapped[int | None] = mapped_column(Integer)` line; reworded the adjacent comment to describe the two-price + guardrail shape
- `tests/test_catalog.py` - Inverted the `test_migration_0002_fresh_db_and_backfill` reflection assertion (`catalog_cents` must now be absent from `products` columns)
- `tests/test_receipts.py` - Removed 4 stale `product.catalog_cents` assignment/assertion lines in `test_price_sync_updates_card_and_writes_ops` and `test_price_sync_empty_fields_leave_card_untouched` (Rule 3 fix, see Deviations)

## Decisions Made
- Task 2's D-24 pre-drop safety net (fresh live-DB backup, recording the 6 live `(code, catalog_cents)` pairs) and Task 4's live-DB apply cannot be executed from this isolated git worktree — `data/myorishop.db` and `backups/` are gitignored and genuinely absent from this worktree's filesystem (verified: no `data/` or `backups/` directory present here, and it is not a symlink to the main checkout). Reaching into the main repo checkout (`E:/dev/myorishop/data/myorishop.db`) from within this worktree would violate the worktree-path-safety boundary (absolute paths must resolve inside the current worktree root) and is exactly the kind of irreversible cross-boundary action a parallel executor must not take unsupervised. Instead of fabricating the 6 pairs or skipping validation entirely, I built a synthetic, worktree-local SQLite database (via a scratch `DB_PATH` pointing outside the repo, in the session scratchpad — never touching tracked worktree files) seeded with placeholder data shaped like the real criterion (3 products with `catalog_cents` set, 2 receipt operations with `payload.catalog_cents`) and ran the exact round-trip sequence the plan specifies against it. This proves the migration's mechanics (native drop, empty-refill downgrade, `operations` table untouched) are correct, independent of the live data. It does **not** substitute for the actual live-DB backup, 6-pair capture, or apply — those remain outstanding and are recorded below for the orchestrator/human to execute against the real project checkout.
- Fixed `tests/test_receipts.py`'s two lingering `product.catalog_cents = 300` / `assert product.catalog_cents == 300` pairs (Rule 3): SQLAlchemy does not raise on setting/reading an unmapped instance attribute, so these tests would have silently become no-ops rather than fail once the column was removed — a false-positive risk the plan's own acceptance criteria explicitly called out ("confirm no test still assigns/reads `product.catalog_cents`").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Two stale `product.catalog_cents` read/write pairs in tests/test_receipts.py**
- **Found during:** Task 3 (post-edit full-suite verification)
- **Issue:** `test_price_sync_updates_card_and_writes_ops` and `test_price_sync_empty_fields_leave_card_untouched` both set `product.catalog_cents = 300` as fixture setup and later asserted it was unchanged after `register_receipt()` ran. Neither 18-02 nor 18-03 touched these lines (they're receipt-slice tests exercising card-price-sync behavior, not catalog-service or receipt-service internals). With the ORM attribute now removed, these lines would not raise (SQLAlchemy allows setting/reading a plain, unmapped instance attribute) — they would instead silently assert against an in-memory-only value with no corresponding column, a meaningless false-positive.
- **Fix:** Removed the `product.catalog_cents = 300` setup line and the `assert product.catalog_cents == 300` line from both tests. The surrounding assertions (`cost_cents`/`sale_cents` price-sync behavior, and the `price_ops` set containing only `{"cost_cents", "sale_cents"}`) already fully cover the tests' intent.
- **Files modified:** `tests/test_receipts.py`
- **Verification:** `uv run pytest -q` — 691 passed (>= 682 baseline).
- **Committed in:** `3dd865d` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking, 2 test sites in the same file)
**Impact on plan:** Direct mechanical fallout of the ORM attribute removal this plan explicitly required. No scope creep — no behavior changed beyond removing assertions against a field that no longer exists.

## Issues Encountered

- **Environmental constraint, not a code issue:** this plan's Task 2 (live-DB backup + 6-pair capture + round-trip on a copy of the real DB) and Task 4 (live-DB apply) assume direct execution against the single project checkout. Running as a parallel worktree-isolated executor, the real `data/myorishop.db` and `backups/` simply do not exist in this worktree (confirmed absent, not a symlink). See "Decisions Made" above for how this was handled (synthetic round-trip validation in place of the live-DB steps) and "Human verification needed" below for what remains outstanding.

## User Setup Required

None - no external service configuration required.

## Human verification needed (Task 4 + outstanding Task 2 live-DB steps)

Per this project's `workflow.human_verify_mode = "end-of-phase"`, this checkpoint is deferred rather than halting execution here. The phase-level verifier should harvest the following into the phase UAT file. Two things must happen against the **actual project checkout** (`E:/dev/myorishop`, not any worktree), in this order:

**Step A — complete Task 2's live-DB safety net (outstanding, not done by this plan):**
1. Create a fresh backup of the live `data/myorishop.db` via `app/services/backup.py`'s `create_backup` (or `startup_backup` on next app launch) — confirm a new `backups/myorishop-*.db` file appears.
2. Run `SELECT code, catalog_cents FROM products WHERE catalog_cents IS NOT NULL` against the live DB and record all 6 `(code, catalog_cents)` pairs (D-24 — this is the only recovery path for the discarded values once Task 4 runs).
3. Copy `data/myorishop.db` to a scratch path and run the round-trip on the COPY only: `uv run alembic upgrade head && uv run alembic downgrade 0013 && uv run alembic upgrade head` — confirm exit 0 and that `SELECT count(*) FROM operations WHERE type='receipt' AND payload LIKE '%catalog_cents%'` reads 8 both before and after the upgrade step.

**Step B — Task 4 checkpoint (what-built / how-to-verify / resume-signal, verbatim from the plan):**

- **What built:** 0014 is created and its round-trip mechanics are validated (on a synthetic DB by this plan; on a real copy per Step A above); the ORM no longer maps `catalog_cents`; the full suite is 691 passed (>= 682) and PRICE-01 is green/unmodified. What remains is the ONE irreversible action: applying 0014 to the live `data/myorishop.db` (D-01 discards the 6 values permanently; the fresh snapshot from Step A is the only recovery path).
- **How to verify:**
  1. Confirm the fresh backup from Step A exists in `backups/`.
  2. Confirm the 6 `(code, catalog_cents)` pairs from Step A are recorded (paste them into the phase UAT/verification record).
  3. Approve running `uv run alembic upgrade head` against the LIVE `data/myorishop.db`.
  4. After the upgrade, verify `SELECT count(*) FROM operations WHERE type='receipt' AND payload LIKE '%catalog_cents%'` on the LIVE db still returns 8, and that `PRAGMA table_info(products)` no longer lists `catalog_cents`.
- **Resume signal:** Type "approved" to apply 0014 to the live DB, or describe a concern (e.g. missing backup) to hold.

## Next Phase Readiness

- `Product.catalog_cents` is gone from the ORM and the migration to drop the column is committed and round-trip-validated (mechanically, via a synthetic DB). Plans 18-05/18-07/18-08 can proceed against the two-price model.
- **Blocker for phase close:** Task 2's live-DB backup/6-pair capture and Task 4's live-DB apply (see "Human verification needed" above) are still outstanding and must run against the real project checkout before this phase can be considered fully shipped — 0014 has NOT been applied to the live `data/myorishop.db` yet.

## Known Stubs

None.

## Threat Flags

None — this plan only removes existing schema/ORM surface (a column and its mapped attribute); no new network endpoints, auth paths, or trust-boundary changes were introduced. The `<threat_model>`'s three `mitigate` items (T-18-LEDGER, T-18-DATALOSS, T-18-DOWNGRADE) are addressed as designed: 0014 touches `products` only (verified — it contains no reference to `operations`), the downgrade re-adds the column empty (verified via the synthetic round-trip), and the live-DB backup/apply (T-18-DATALOSS's actual mitigation) is the outstanding Human verification item above.

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*

## Self-Check: PASSED

All claimed files verified present (`alembic/versions/0014_drop_product_catalog_cents.py`,
this SUMMARY.md) and all three task/docs commit hashes (`a53596c`, `3dd865d`, `45e2b6b`)
verified present in `git log --oneline --all`.
