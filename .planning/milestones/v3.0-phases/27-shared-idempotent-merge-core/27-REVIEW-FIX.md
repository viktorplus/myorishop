---
phase: 27-shared-idempotent-merge-core
fixed_at: 2026-07-19T12:20:41Z
review_path: .planning/phases/27-shared-idempotent-merge-core/27-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 27: Code Review Fix Report

**Fixed at:** 2026-07-19T12:20:41Z
**Source review:** .planning/phases/27-shared-idempotent-merge-core/27-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, WR-01, WR-02, WR-03 — Info findings IN-01/IN-02 out of scope)
- Fixed: 4
- Skipped: 0

All four in-scope findings were fixed in `app/services/merge.py` with regression
tests added to `tests/test_merge.py`. Because all four fixes live in the same two
files with interleaved diff hunks — and CR-01's resolver depends directly on
WR-03's widened/disambiguating `_suffix_code` — they were committed as one atomic,
fully-verified commit rather than split into per-finding commits that would leave
a broken intermediate state. This matches the task's "grouped sensibly" allowance.

**Verification (all green, run in an isolated worktree before commit):**
- Portability grep over `merge.py` (`dialects|on_conflict|INSERT OR`): 0 matches — invariant preserved.
- No-commit grep over `merge.py` (`\.commit\(|\.rollback\(`): 0 matches — caller still owns the transaction.
- `uv run ruff check app/services/merge.py tests/test_merge.py`: All checks passed.
- `uv run pytest tests/test_merge.py -q`: 33 passed (7 new regression tests).

## Fixed Issues

### CR-01: Intra-batch `Product.code` collision is never resolved → whole-batch rollback

**Files modified:** `app/services/merge.py`, `tests/test_merge.py`
**Commit:** c921c8b
**Status:** fixed: requires human verification (correctness/logic change — covered by new tests, but confirm the deterministic resolution order matches the intended DD-2 policy)
**Applied fix:** Rewrote `_resolve_code_collisions` to resolve collisions against
BOTH the DB and the other new rows in the same batch. Rows are processed in a
deterministic order (`sorted` by `id`); the first claimant of a clean `code` (the
DB incumbent if present, else the lexicographically smallest in-batch UUID) keeps
it, and every later claimant is renamed via `_suffix_code` (UUID preserved) and
reported as a `product_code` Conflict. A `claimed_by` map tracks every active code
already taken (DB incumbents + in-batch winners + prior renames), and the per-code
DB probe is cached so N same-code rows cost one query. Re-merging the same batch
stays idempotent (existing UUIDs are dropped by the set-difference before the
collision pass, so replay renames identically and inserts nothing).
**Regression tests:** `test_intra_batch_code_collision_two_new`,
`test_intra_batch_code_collision_re_merge_is_noop`,
`test_intra_batch_code_collision_three_new` — prove two/three new active products
on one code (no DB incumbent) all insert with distinct codes, the rename is
reported, `apply_merge` does not raise, and re-merge is a byte-identical no-op.

### WR-01: Money validation only rejects `float`, letting non-int types reach an integer column

**Files modified:** `app/services/merge.py`, `tests/test_merge.py`
**Commit:** c921c8b
**Status:** fixed
**Applied fix:** In `parse_exchange`, the money guard now rejects any present
value that is not a strict `int` — floats, JSON strings (`"500"`), and bools
(`int` subclass, excluded explicitly) all raise `ValueError("money field ... must
be int cents")` before any DB touch, closing the SQLite dynamic-typing hole.
**Regression tests:** `test_string_money_rejected`, `test_bool_money_rejected`
(the existing `test_float_money_rejected` still passes against the new message).

### WR-02: Duplicate origin UUID within one batch is not deduplicated → whole-batch rollback

**Files modified:** `app/services/merge.py`, `tests/test_merge.py`
**Commit:** c921c8b
**Status:** fixed
**Applied fix:** Chose the module's existing strict-reject contract over silent
dedup (parse_exchange already fails loud on all malformed input). Added a
`seen_ids` set of `(kind, id)` pairs in `parse_exchange`; a repeated origin UUID
of the same kind now raises `ValueError("duplicate {kind} record id: ...")`
pre-DB, replacing what would have been an opaque duplicate-PK `IntegrityError`
whole-batch rollback. Keyed by kind because each ORM table owns its own PK space.
**Regression tests:** `test_duplicate_ledger_uuid_rejected`,
`test_duplicate_reference_uuid_rejected`.

### WR-03: `_suffix_code` uses only 4 hex chars of the UUID — collision-prone rename

**Files modified:** `app/services/merge.py`, `tests/test_merge.py`
**Commit:** c921c8b
**Status:** fixed: requires human verification (rename-entropy/logic change — confirm the widened suffix + disambiguation policy is acceptable)
**Applied fix:** Widened `_CODE_SUFFIX_HEX_LEN` from 4 to 8 hex chars (~16→~32
bits) and gave `_suffix_code` an optional `taken` set: when a candidate collides
with an already-claimed code (CR-01's multi-loser case) the hex slice is widened
one char at a time until unique, still fully deterministic in `(code, row_id,
taken)`. The marker is capped at `_CODE_MAX_LEN` so a wide slice never produces a
negative base slice, keeping `resolved_code` within `Product.code` `String(20)`.
**Regression coverage:** `test_intra_batch_code_collision_three_new` asserts three
losers on one base code produce three distinct resolved codes, each `<= 20` chars;
the existing `test_product_code_collision_renamed` still passes (its
`[:4] in code` assertion holds under the 8-char slice).

---

_Fixed: 2026-07-19T12:20:41Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
