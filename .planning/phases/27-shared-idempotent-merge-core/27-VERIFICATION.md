---
phase: 27-shared-idempotent-merge-core
verified: 2026-07-19T00:00:00Z
status: human_needed
score: 20/20 must-haves verified (PG-CI live run pending)
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 20/20 (1 caveat, CR-01 decision + PG-CI pending)
  gaps_closed:
    - "CR-01 intra-batch Product.code collision — maintainer chose FIX NOW; _resolve_code_collisions now resolves among new in-batch rows too (commit c921c8b), DD-2-conformant, 7 new tests green. Truth 15 caveat lifted."
    - "WR-01 money validation now strict int (float/str/bool rejected pre-DB)."
    - "WR-02 duplicate origin UUID in one batch now rejected loudly in parse_exchange (ValueError, not opaque IntegrityError)."
    - "WR-03 rename suffix widened 4->8 hex + disambiguation against claimed codes, still within String(20)."
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Push the branch and confirm the GitHub Actions `pg-parity` job is GREEN — specifically the step 'PostgreSQL merge portability (SYNC-02/04/05 one engine, both dialects)' running tests/test_merge_pg.py against postgres:17."
    expected: "test_merge_idempotent_on_pg and test_code_collision_on_pg both PASS on PostgreSQL, proving the portable pre-select set-difference (no dialect on_conflict) and the postgresql_where partial unique index behave identically to SQLite. The phase goal's '...proven portable on SQLite + PostgreSQL in CI' clause is only truly closed once this live run is green."
    why_human: "The PG slice is skipif-guarded and SKIPS on the local Windows/SQLite dev default (verified locally: 2 skipped). Its live execution happens only in CI on push; it cannot be run locally here. Code + CI wiring are verified by inspection; the green run is the deliverable proof."
gaps: []
---

# Phase 27: Shared Idempotent Merge Core Verification Report

**Phase Goal:** The single server-side merge engine and exchange format — UUID-idempotent ledger replay, post-merge recompute, and server-authoritative reference-data conflict policy, proven portable on SQLite + PostgreSQL in CI.
**Verified:** 2026-07-19
**Status:** human_needed
**Re-verification:** Yes — after code-review fix (commit c921c8b closing CR-01/WR-01/WR-02/WR-03)

## Goal Achievement

Re-verification after the maintainer chose **FIX NOW** for code-review finding CR-01 (previous status was `human_needed` with two items). The intra-batch `Product.code` collision is now resolved in `_resolve_code_collisions` (merge.py L361-417); the three robustness warnings (WR-01/02/03) are also fixed. The full merge suite is GREEN on SQLite (`uv run pytest tests/test_merge.py tests/test_merge_pg.py -q` → **33 passed, 2 skipped** — up from 26 passed, the 7 new regression tests included; the 2 skips are the PG slice, correctly skipif-guarded). Portability grep (`dialects|on_conflict|INSERT OR`) = 0, no-commit grep (`.commit(|.rollback(`) = 0, `record_operation(` = 0, debt markers = 0 — every phase-27 invariant preserved through the fix (no regression). One item remains for a human/CI: the live PostgreSQL CI run, which is genuinely un-runnable locally.

### CR-01 fix vs DD-2 — formal conformance assessment (previous human item #2, now RESOLVED)

DD-2 (27-RESEARCH.md Decision 2, L273-289) mandates: **rename the incoming loser with a deterministic UUID-derived suffix, keep its UUID (so its ledger rows stay valid), the incumbent keeps the clean code, and report the rename in `MergeReport.conflicts`.** The rewritten `_resolve_code_collisions` (merge.py L361-417):

- **Resolves against both DB incumbent AND other new in-batch rows** — closing the exact gap CR-01 flagged (two new active products on one code with no DB incumbent).
- **Deterministic order** — `sorted(product_rows, key=lambda r: r["id"])`; first claimant (DB incumbent if present, else smallest-UUID) keeps the clean code; every later claimant is renamed.
- **Keeps the loser's UUID** — only `row["code"]` is mutated; `row["id"]` is untouched, so its operations/batches (which key on `product_id`) stay valid.
- **Reports each rename** — appends a `product_code` `Conflict(original_code, resolved_code, incumbent_id)`.
- **Idempotent replay** — existing UUIDs are dropped by the set-difference before the collision pass, so re-merge renames identically and inserts nothing (`test_intra_batch_code_collision_re_merge_is_noop`).

All four normative DD-2 clauses are satisfied. The only deviation from research's parenthetical suggestion (intra-batch tie-break on "earlier `created_at`, then smaller UUID") is that the tie-break uses smallest-UUID **only**. Research explicitly framed the `created_at` tie-break as a *future* consideration ("If a future batch could contain two new same-code products…"), and for two genuinely-new rows neither is a true incumbent — the choice of which keeps the clean code is a cosmetic admin-reconciliation detail, not a correctness invariant. Both variants are deterministic, lossless, and reported. **Verdict: conformant.** Covered by `test_intra_batch_code_collision_two_new`, `_three_new`, `_re_merge_is_noop`. Item #2 is **RESOLVED**; Truth 15's prior caveat is **lifted**.

**WR-03** (widened 8-hex suffix + disambiguation, flagged by the fixer as "requires human verification") is likewise conformant with the DD-2 rename scheme (deterministic in the UUID, capped within `String(20)`) and covered by `test_intra_batch_code_collision_three_new` (three distinct resolved codes, each ≤20 chars). It is a robustness improvement over the prior 4-hex slice and needs no separate human decision.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One NDJSON exchange format exists (header line first, per-line `kind`) — the single wire schema (SYNC-04) | ✓ VERIFIED | merge.py FORMAT_VERSION, RECORD_KINDS, KIND_TO_MODEL, 4 dataclasses (L46-130); test_module_imports |
| 2 | parse∘serialize round-trip identity incl. origin id/device_id/seq/author_id/created_by | ✓ VERIFIED | serialize_exchange/parse_exchange (L138-233,527-559); test_round_trip |
| 3 | parse rejects malformed line / bad format_version / unknown kind / duplicate id / non-int money BEFORE any DB touch (V5) | ✓ VERIFIED | ValueError guards L161-217; test_malformed/format_version/unknown_kind/missing_header/duplicate_header/string_money/bool_money/duplicate_*_uuid |
| 4 | Engine module is PURE — no HTTP/file/FastAPI; only stdlib json + dataclasses + SQLAlchemy | ✓ VERIFIED | Imports L25-42; purity grep gate = 0 |
| 5 | synced_at from the wire is never trusted (forced None) | ✓ VERIFIED | parse L219-221, _ledger_row L460; test_synced_at_not_trusted, test_ledger_row_inserted_verbatim |
| 6 | apply_merge inserts each ledger row verbatim by UUID, never re-minting via record_operation (SYNC-02) | ✓ VERIFIED | _ledger_row + _insert_new; grep gate confirms no record_operation( call; test_ledger_row_inserted_verbatim |
| 7 | Merging the same batch twice changes nothing (0 new rows, identical snapshot) (SYNC-02) | ✓ VERIFIED | test_merge_twice_equals_once; test_duplicate_uuid_skipped |
| 8 | Idempotent insert is a PORTABLE pre-select set-difference — no dialects/on_conflict/INSERT OR | ✓ VERIFIED | _partition_new L264-281 (.in_ chunked at 500); purity grep gate = 0 |
| 9 | After merge, Product.quantity==compute_stock, Batch.quantity==compute_batch_stock, cash==signed sum (SYNC-03) | ✓ VERIFIED | recompute_derived call L522; test_stock_recomputed_after_merge, test_cash_balance_after_merge |
| 10 | apply_merge NEVER commits; poisoned mid-batch record leaves DB unchanged (SYNC-02/OFF-05) | ✓ VERIFIED | no .commit( in merge.py (grep gate); test_bad_record_rolls_back |
| 11 | recompute_derived is a non-committing extraction of rebuild_stock; rebuild_stock delegates then commits | ✓ VERIFIED | ledger.py (3 references to recompute_derived); test_recompute_derived_does_not_commit |
| 12 | Reference upsert insert-if-new: new UUID inserts verbatim, existing UUID discarded (server-wins, row-level) (SYNC-05) | ✓ VERIFIED | _upsert_reference L420-447; test_server_wins_on_existing_reference |
| 13 | Reference rows applied in FK-dependency order regardless of NDJSON line order | ✓ VERIFIED | _REFERENCE_INSERT_ORDER L249-256, apply_merge L496-506; test_fk_ordering |
| 14 | A missing referenced parent is rejected all-or-nothing (caller rollback) | ✓ VERIFIED | FK + caller-txn design; test_missing_parent_rejected |
| 15 | Duplicate Product.code renames the incoming loser, keeps UUID, incumbent keeps clean code, reported in conflicts — for BOTH server-incumbent AND intra-batch two-new cases (SYNC-05/DD-2) | ✓ VERIFIED | _resolve_code_collisions L361-417 (now resolves in-batch too); test_product_code_collision_renamed + test_intra_batch_code_collision_two_new/_three_new/_re_merge_is_noop. CR-01 caveat LIFTED (fix c921c8b, DD-2-conformant — see assessment above) |
| 16 | Tombstones inline via deleted_at; existing server row never resurrected/deleted from client input | ✓ VERIFIED | _reference_row carries deleted_at; insert-only (no session.delete/update on DB rows); test_tombstone_inline |
| 17 | Re-merging the same colliding batch renames identically (deterministic) | ✓ VERIFIED | _suffix_code deterministic in (code,row_id,taken) (L332-358); test_collision_rename_is_deterministic + test_intra_batch_code_collision_re_merge_is_noop |
| 18 | Idempotency core (merge-twice==once) passes on PostgreSQL, not just SQLite (SYNC-02/04) | ✓ VERIFIED (code+CI wiring); live run CI-PENDING | tests/test_merge_pg.py test_merge_idempotent_on_pg (L112); skips locally, runs in ci.yml pg-parity |
| 19 | Product.code collision rename passes on PostgreSQL against postgresql_where partial index (SYNC-05) | ✓ VERIFIED (code+CI wiring); live run CI-PENDING | test_code_collision_on_pg (L238) |
| 20 | CI runs the merge PG slice against postgres:17 in the existing pg-parity job (SYNC-04: one engine) | ✓ VERIFIED | .github/workflows/ci.yml L45-48 (DATABASE_URL + tests/test_merge_pg.py -x) |

**Score:** 20/20 truths verified. Truth 15's prior CR-01 caveat is **now lifted** (intra-batch collision fixed and DD-2-conformant). Truths 18-19 are proven by code + CI wiring inspection, with the live green PostgreSQL run pending on CI push (cannot execute locally on Windows/SQLite).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/merge.py` | Pure engine: format consts, dataclasses, parse/serialize, apply_merge + helpers | ✓ VERIFIED | 560 lines (grew from 499 with the fix); all required symbols present, wired, imported by tests + PG slice; purity/no-commit invariants preserved |
| `app/services/ledger.py` | recompute_derived(session) non-committing; rebuild_stock delegates | ✓ VERIFIED | 3 references to recompute_derived (def + rebuild_stock delegate + merge caller) |
| `tests/test_merge.py` | SQLite dimensions (format, idempotency, recompute, server-wins, FK, collision incl. intra-batch, tombstone, money/dup guards) | ✓ VERIFIED | 33 tests (26 + 7 new regressions), all passing |
| `tests/test_merge_pg.py` | PG portability slice, skipif-guarded | ✓ VERIFIED | pytestmark skipif on dialect (L39); test_merge_idempotent_on_pg + test_code_collision_on_pg; skips locally |
| `.github/workflows/ci.yml` | pg-parity job runs test_merge_pg.py against postgres:17 | ✓ VERIFIED | Step L45-48; no new job |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| apply_merge | recompute_derived | post-append recompute in caller txn | ✓ WIRED (L522) |
| _insert_new/_partition_new | operations/cash tables | select(model.id).in_(chunk) set-difference | ✓ WIRED (L279,299) |
| rebuild_stock | recompute_derived | delegates then session.commit() | ✓ WIRED (ledger.py) |
| apply_merge | _upsert_reference | FK-ordered reference stage before ledger | ✓ WIRED (L500) |
| _upsert_reference | _resolve_code_collisions | Product + conflicts → DB-and-in-batch clash → rename loser | ✓ WIRED (L443-444) |
| _resolve_code_collisions | claimed_by / db_incumbent | intra-batch + DB active-code probe (cached) | ✓ WIRED (L386-402) |
| ci.yml pg-parity | tests/test_merge_pg.py | DATABASE_URL=postgresql+psycopg://…@localhost:5432 | ✓ WIRED (L45-48) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Merge suite passes on SQLite (post-fix, +7 tests) | `uv run pytest tests/test_merge.py tests/test_merge_pg.py -q` | 33 passed, 2 skipped | ✓ PASS |
| Purity/portability gate | grep dialects/on_conflict/INSERT OR in merge.py | 0 | ✓ PASS |
| No-commit gate | grep .commit(/.rollback( in merge.py | 0 | ✓ PASS |
| No identity re-minting | grep record_operation(/record_cash_movement( in merge.py | 0 | ✓ PASS |
| No debt markers | grep TBD/FIXME/XXX in merge.py + test_merge.py | 0 | ✓ PASS |
| Live PG parity run | (CI-only, postgres:17) | not runnable locally | ? SKIP → human/CI |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| SYNC-02 | 27-02, 27-04 | Idempotent UUID replay — re-sync/re-upload changes nothing | ✓ SATISFIED | truths 6-8,10,18; REQUIREMENTS.md marked Complete |
| SYNC-03 | 27-02 | Derived stock/cash recomputed after any merge | ✓ SATISFIED | truths 9,11 |
| SYNC-04 | 27-01, 27-04 | One shared exchange format + one merge engine, proven both dialects | ✓ SATISFIED (CI live-run pending) | truths 1-5,18-20 |
| SYNC-05 | 27-03, 27-04 | Server-authoritative reference data + defined Product.code rule (incl. intra-batch, DD-2) | ✓ SATISFIED | truths 12-17,19 — CR-01 fix closes the intra-batch case |

All four declared requirement IDs are accounted for; no orphaned IDs (REQUIREMENTS.md maps exactly SYNC-02..05 to Phase 27).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| test_merge_pg.py | ~65 | PG seed uses ON CONFLICT DO NOTHING (IN-02) | ℹ️ Info | Test seed only (PG-guarded, commented); not an engine leak. Explicitly deferred as out-of-scope in 27-REVIEW-FIX. |

The four previously-noted warnings (CR-01, WR-01, WR-02, WR-03) are all **resolved** in commit c921c8b and no longer present:
- CR-01: intra-batch collision now resolved (L361-417).
- WR-01: money strictly `int`, rejecting float/str/bool pre-DB (L214-217).
- WR-02: duplicate origin UUID rejected loudly in parse_exchange (L195-199).
- WR-03: rename suffix widened to 8 hex + disambiguation, within String(20) (L327-358).

No debt markers (TBD/FIXME/XXX) in any modified file.

### Human Verification Required

**1. GitHub Actions pg-parity job GREEN (SYNC-04 live portability proof) — SOLE remaining item**
- **Test:** Push the branch; confirm the CI step "PostgreSQL merge portability (SYNC-02/04/05 one engine, both dialects)" runs tests/test_merge_pg.py against postgres:17 and passes.
- **Expected:** test_merge_idempotent_on_pg + test_code_collision_on_pg PASS on PostgreSQL — portable set-difference and the postgresql_where partial index behave identically to SQLite.
- **Why human:** The PG slice skipif-skips on the local Windows/SQLite default; the live run is CI-only. Code + wiring verified here (ci.yml L45-48, both tests present, skipif guard confirmed); the green run is the phase-goal's closing proof.

### Gaps Summary

No must-have FAILED. The prior CR-01 human decision was resolved by the maintainer's FIX-NOW choice: `_resolve_code_collisions` now resolves intra-batch `Product.code` collisions in addition to DB-incumbent collisions, conforming to DD-2 (deterministic UUID-derived rename, UUID preserved, incumbent keeps the clean code, reported in `MergeReport.conflicts`), and is covered by three new passing regression tests. WR-01/02/03 robustness gaps are also fixed. All phase-27 invariants (portability, no-commit, verbatim provenance, idempotency, server-wins) survive the fix with no regression (33 passed, 2 skipped locally; all gates 0).

One item remains, routed to human/CI rather than counted as a gap:

1. **PG live CI run (SYNC-04)** — verifiable here only by code + CI-wiring inspection; the green run happens on push. This is expected and by-design (Windows/SQLite dev default skips the slice). The phase goal's "…proven portable on SQLite + PostgreSQL in CI" clause is fully wired and closes on the first green push.

---

_Verified: 2026-07-19 (re-verification after code-review fix c921c8b)_
_Verifier: Claude (gsd-verifier)_
