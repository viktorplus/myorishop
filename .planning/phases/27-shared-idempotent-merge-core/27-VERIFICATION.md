---
phase: 27-shared-idempotent-merge-core
verified: 2026-07-19T00:00:00Z
status: human_needed
score: 20/20 must-haves verified (1 with an accepted-scope caveat; PG-CI live run pending)
overrides_applied: 0
human_verification:
  - test: "Push the branch and confirm the GitHub Actions `pg-parity` job is GREEN — specifically the new step 'PostgreSQL merge portability (SYNC-02/04/05)' running tests/test_merge_pg.py against postgres:17."
    expected: "test_merge_idempotent_on_pg and test_code_collision_on_pg both PASS on PostgreSQL, proving the portable pre-select set-difference (no dialect on_conflict) and the postgresql_where partial unique index behave identically to SQLite. The phase goal's '...proven portable on SQLite + PostgreSQL in CI' clause is only truly closed once this live run is green."
    why_human: "The PG slice is skipif-guarded and SKIPS on the local Windows/SQLite dev default (verified locally: 2 skipped). Its live execution happens only in CI on push; it cannot be run locally here. Code + CI wiring are verified by inspection; the green run is the deliverable proof."
  - test: "Decide whether to ACCEPT the intra-batch Product.code deferral (code-review CR-01) as a planned Phase-27 scope boundary, or require it fixed now."
    expected: "Confirm the reviewer's understanding: two NEW products carrying the same active `code` in ONE batch with no DB incumbent are NOT resolved against each other, so they hit the uq_products_code_active partial index → IntegrityError → whole-batch rollback (a LOUD atomic reject, never silent data loss/corruption). This path is not reachable from a single well-formed device push (a device's own partial unique index prevents two active same-code products locally); it only arises from an artificially aggregated multi-device single-batch payload, which neither the Phase 28/29 online push nor the Phase 30 offline self-upload produces. Plan 27-03 explicitly scoped this tie-break OUT ('implement only if naturally covered, else note')."
    why_human: "The code reviewer classified CR-01 as BLOCKER; the plan classified the same case as an out-of-scope, documented deferral with a safe DB backstop. This is a scope/severity judgement the maintainer should ratify, not a mechanical check. If accepted, record an override; if not, re-plan with --gaps."
gaps: []
---

# Phase 27: Shared Idempotent Merge Core Verification Report

**Phase Goal:** The single server-side merge engine and exchange format — UUID-idempotent ledger replay, post-merge recompute, and server-authoritative reference-data conflict policy, proven portable on SQLite + PostgreSQL in CI.
**Verified:** 2026-07-19
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

The engine (`app/services/merge.py`, 499 lines) and the `recompute_derived` extraction (`app/services/ledger.py`) are real, substantive, and wired. All 26 SQLite merge tests pass locally (`uv run pytest tests/test_merge.py tests/test_merge_pg.py -q` → 26 passed, 2 skipped — the 2 skips are the PG slice, correctly guarded). Every observable truth from the four plans' `must_haves` is backed by a substantive, passing test. Two items require a human/CI decision (see below): the live PostgreSQL CI run (cannot run locally) and ratification of the CR-01 intra-batch collision deferral.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | One NDJSON exchange format exists (header line first, per-line `kind`) — the single wire schema (SYNC-04) | ✓ VERIFIED | merge.py FORMAT_VERSION, RECORD_KINDS, KIND_TO_MODEL, 4 dataclasses (L46-130); test_module_imports |
| 2 | parse∘serialize round-trip identity incl. origin id/device_id/seq/author_id/created_by | ✓ VERIFIED | serialize_exchange/parse_exchange (L138-214,466-498); test_round_trip |
| 3 | parse rejects malformed line / bad format_version / unknown kind BEFORE any DB touch (V5) | ✓ VERIFIED | ValueError guards L155-198; test_malformed/format_version/unknown_kind/missing_header/duplicate_header |
| 4 | Engine module is PURE — no HTTP/file/FastAPI; only stdlib json + dataclasses + SQLAlchemy | ✓ VERIFIED | Imports L25-42; purity grep gate = 0 |
| 5 | synced_at from the wire is never trusted (forced None) | ✓ VERIFIED | parse L200-202, _ledger_row L399; test_synced_at_not_trusted, test_ledger_row_inserted_verbatim |
| 6 | apply_merge inserts each ledger row verbatim by UUID, never re-minting via record_operation (SYNC-02) | ✓ VERIFIED | _ledger_row + _insert_new; grep gate confirms no record_operation( call; test_ledger_row_inserted_verbatim |
| 7 | Merging the same batch twice changes nothing (0 new rows, identical snapshot) (SYNC-02) | ✓ VERIFIED | test_merge_twice_equals_once (byte-identical snapshot); test_duplicate_uuid_skipped |
| 8 | Idempotent insert is a PORTABLE pre-select set-difference — no dialects/on_conflict/INSERT OR | ✓ VERIFIED | _partition_new L245-262 (.in_ chunked at 500); purity grep gate = 0 |
| 9 | After merge, Product.quantity==compute_stock, Batch.quantity==compute_batch_stock, cash==signed sum (SYNC-03) | ✓ VERIFIED | recompute_derived call L461; test_stock_recomputed_after_merge, test_cash_balance_after_merge |
| 10 | apply_merge NEVER commits; poisoned mid-batch record leaves DB unchanged (SYNC-02/OFF-05) | ✓ VERIFIED | no .commit( in merge.py (grep gate); test_bad_record_rolls_back |
| 11 | recompute_derived is a non-committing extraction of rebuild_stock; rebuild_stock delegates then commits | ✓ VERIFIED | ledger.py L171-222; test_recompute_derived_does_not_commit |
| 12 | Reference upsert insert-if-new: new UUID inserts verbatim, existing UUID discarded (server-wins, row-level) (SYNC-05) | ✓ VERIFIED | _upsert_reference L359-386; test_server_wins_on_existing_reference |
| 13 | Reference rows applied in FK-dependency order regardless of NDJSON line order | ✓ VERIFIED | _REFERENCE_INSERT_ORDER L230-237, apply_merge L435-445; test_fk_ordering |
| 14 | A missing referenced parent is rejected all-or-nothing (caller rollback) | ✓ VERIFIED | FK + caller-txn design; test_missing_parent_rejected |
| 15 | Duplicate Product.code (incoming vs server incumbent) renames the incoming loser, keeps UUID, incumbent keeps clean code, reported in conflicts (SYNC-05) | ✓ VERIFIED (caveat) | _resolve_code_collisions L321-356; test_product_code_collision_renamed. Caveat: intra-batch two-NEW-same-code case not covered (CR-01) — see Warnings |
| 16 | Tombstones inline via deleted_at; existing server row never resurrected/deleted from client input | ✓ VERIFIED | _reference_row carries deleted_at; insert-only (no session.delete/update on DB rows); test_tombstone_inline |
| 17 | Re-merging the same colliding batch renames identically (deterministic) | ✓ VERIFIED | _suffix_code deterministic in UUID only (L307-318); test_collision_rename_is_deterministic |
| 18 | Idempotency core (merge-twice==once) passes on PostgreSQL, not just SQLite (SYNC-02/04) | ✓ VERIFIED (code+CI wiring); live run CI-PENDING | tests/test_merge_pg.py test_merge_idempotent_on_pg; skips locally, runs in ci.yml pg-parity |
| 19 | Product.code collision rename passes on PostgreSQL against postgresql_where partial index (SYNC-05) | ✓ VERIFIED (code+CI wiring); live run CI-PENDING | test_code_collision_on_pg |
| 20 | CI runs the merge PG slice against postgres:17 in the existing pg-parity job (SYNC-04: one engine) | ✓ VERIFIED | .github/workflows/ci.yml L45-48 (DATABASE_URL + tests/test_merge_pg.py) |

**Score:** 20/20 truths verified. Truth 15 carries an accepted-scope caveat (CR-01); truths 18-19 are proven by code + CI wiring inspection, with the live green PostgreSQL run pending on CI push (cannot execute locally on Windows/SQLite).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/merge.py` | Pure engine: format consts, dataclasses, parse/serialize, apply_merge + helpers | ✓ VERIFIED | 499 lines; all required symbols present, wired, imported by tests + PG slice |
| `app/services/ledger.py` | recompute_derived(session) non-committing; rebuild_stock delegates | ✓ VERIFIED | L171-222; 2 references to recompute_derived(session) |
| `tests/test_merge.py` | SQLite dimensions (format, idempotency, recompute, server-wins, FK, collision, tombstone) | ✓ VERIFIED | 26 tests, all named must-have tests present and passing |
| `tests/test_merge_pg.py` | PG portability slice, skipif-guarded | ✓ VERIFIED | pytestmark skipif on dialect; skips locally |
| `.github/workflows/ci.yml` | pg-parity job runs test_merge_pg.py against postgres:17 | ✓ VERIFIED | Step added L45-48; no new job |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| apply_merge | recompute_derived | post-append recompute in caller txn | ✓ WIRED (L461) |
| _insert_new/_partition_new | operations/cash tables | select(model.id).in_(chunk) set-difference | ✓ WIRED (L260,278) |
| rebuild_stock | recompute_derived | delegates then session.commit() | ✓ WIRED (ledger.py L221-222) |
| apply_merge | _upsert_reference | FK-ordered reference stage before ledger | ✓ WIRED (L439) |
| _resolve_code_collisions | Product.deleted_at.is_(None) probe | active-code clash → rename loser | ✓ WIRED (L341-347) |
| ci.yml pg-parity | tests/test_merge_pg.py | DATABASE_URL=postgresql+psycopg://…@localhost:5432 | ✓ WIRED (L45-48) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Merge suite passes on SQLite | `uv run pytest tests/test_merge.py tests/test_merge_pg.py -q` | 26 passed, 2 skipped | ✓ PASS |
| Purity/portability gate | grep dialects/on_conflict/INSERT OR/record_operation/.commit in merge.py | 0 | ✓ PASS |
| No SQL UPDATE/DELETE of reference rows | grep session.delete/.delete(/update( | 1 match = Python set `.update()` (false positive) | ✓ PASS |
| recompute_derived wiring | grep -c recompute_derived(session) in ledger.py | 2 (def + call) | ✓ PASS |
| Live PG parity run | (CI-only, postgres:17) | not runnable locally | ? SKIP → human/CI |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| SYNC-02 | 27-02, 27-04 | Idempotent UUID replay — re-sync/re-upload changes nothing | ✓ SATISFIED | truths 6-8,10,18; REQUIREMENTS.md marked Complete |
| SYNC-03 | 27-02 | Derived stock/cash recomputed after any merge | ✓ SATISFIED | truths 9,11 |
| SYNC-04 | 27-01, 27-04 | One shared exchange format + one merge engine, proven both dialects | ✓ SATISFIED (CI live-run pending) | truths 1-5,18-20 |
| SYNC-05 | 27-03, 27-04 | Server-authoritative reference data + defined Product.code rule | ✓ SATISFIED (CR-01 caveat) | truths 12-17,19 |

All four declared requirement IDs are accounted for; no orphaned IDs (REQUIREMENTS.md maps exactly SYNC-02..05 to Phase 27). REQUIREMENTS.md already marks all four Complete/Done.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| merge.py | 321-356 | Intra-batch Product.code collision not resolved (CR-01) | ⚠️ Warning | Two NEW same-code products in one batch, no DB incumbent → IntegrityError → whole-batch rollback. LOUD (never silent corruption). Not reachable from a single well-formed device push. Plan-deferred. |
| merge.py | 195-198 | Money guard rejects `float` only, not str/bool (WR-01) | ⚠️ Warning | Non-int money could reach an Integer column on SQLite. Stated must-have was specifically "reject float" — that IS done/tested. Robustness gap. |
| merge.py | 245-281 | Intra-batch duplicate origin UUID not deduped (WR-02) | ⚠️ Warning | Duplicated NDJSON line → duplicate-PK IntegrityError → whole-batch rollback. Loud, not silent. |
| merge.py | 302-318 | _suffix_code uses 4 hex chars (~16 bits) of UUID (WR-03) | ⚠️ Warning | Rename-collision-prone at scale; determinism must-have still holds (same UUID → same suffix). |
| test_merge_pg.py | 65-70 | PG seed uses ON CONFLICT DO NOTHING (IN-02) | ℹ️ Info | Test seed only (PG-guarded, commented); not an engine leak. |

No debt markers (TBD/FIXME/XXX/HACK) in any modified file (the one "HACKED" hit is test-data product name).

### Human Verification Required

**1. GitHub Actions pg-parity job GREEN (SYNC-04 live portability proof)**
- **Test:** Push the branch; confirm the new CI step "PostgreSQL merge portability (SYNC-02/04/05)" runs tests/test_merge_pg.py against postgres:17 and passes.
- **Expected:** test_merge_idempotent_on_pg + test_code_collision_on_pg PASS on PostgreSQL — portable set-difference and the postgresql_where partial index behave identically to SQLite.
- **Why human:** The PG slice skipif-skips on the local Windows/SQLite default; the live run is CI-only. Code + wiring verified here; the green run is the phase-goal's closing proof.

**2. Ratify the CR-01 intra-batch Product.code deferral**
- **Test:** Decide accept-as-planned-scope vs fix-now for the intra-batch two-NEW-same-code case.
- **Expected:** Confirm it is a loud atomic DB-backstop rollback (never silent loss), unreachable from a single-device push, and explicitly scoped out by Plan 27-03.
- **Why human:** Reviewer classified it BLOCKER; plan classified it a documented deferral. Severity/scope call for the maintainer. If accepted, add an `overrides:` entry to this file's frontmatter; if not, re-plan with `--gaps`.

### Gaps Summary

No must-have (as worded) FAILED. The engine, format, idempotency, recompute, and server-wins/rename conflict policy are all implemented, wired, and covered by substantive passing tests on SQLite. Two items are routed to a human/CI decision rather than counted as gaps:

1. **PG live CI run (SYNC-04)** — verifiable here only by code + CI-wiring inspection; the green run happens on push. This is expected and by-design (Windows/SQLite dev default skips the slice).

2. **CR-01 intra-batch Product.code (SYNC-05 edge)** — the code reviewer's BLOCKER. Assessed as an acceptable planned scope boundary for Phase 27: the DB partial-unique index makes it a LOUD, atomic, whole-batch rollback (never silent data loss or corruption); the case is not reachable from a single well-formed device push (a device's own uq_products_code_active prevents two active same-code products locally) and neither the Phase 28/29 online push nor the Phase 30 offline self-upload produces an aggregated multi-device single-batch payload; and Plan 27-03 explicitly scoped the same-batch tie-break out. It is NOT deferred on roadmap evidence (phases 28-30 success criteria do not schedule it), so it is surfaced for an explicit maintainer accept/override decision rather than silently deferred.

The three warnings (WR-01/02/03) are robustness hardening opportunities; none falsifies a stated must-have, and all fail loud (validation error or atomic rollback) rather than corrupting data.

---

_Verified: 2026-07-19_
_Verifier: Claude (gsd-verifier)_
