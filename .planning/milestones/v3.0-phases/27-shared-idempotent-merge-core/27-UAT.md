---
status: complete
phase: 27-shared-idempotent-merge-core
source: [27-VERIFICATION.md]
started: 2026-07-19T00:00:00Z
updated: 2026-07-19T13:05:50Z
---

## Current Test

[testing complete]

## Tests

### 1. GitHub Actions pg-parity job green for the merge portability slice
expected: test_merge_idempotent_on_pg and test_code_collision_on_pg both PASS on postgres:17 in the CI pg-parity job (skipif-guarded, skips locally on SQLite — verified 2 skipped locally). Live green run is the deliverable proof of both-dialect portability.
result: pass
evidence: |
  Pushed HEAD to origin/ci/phase-27-pg-parity; CI run 29688176513 GREEN (exit 0).
  Step "PostgreSQL merge portability (SYNC-02/04/05 one engine, both dialects)":
  tests/test_merge_pg.py .. → 2 passed on postgres:17. In the plain SQLite suite
  the same slice showed `ss` (2 skipped), confirming the skipif guard. Both
  test_merge_idempotent_on_pg and test_code_collision_on_pg PASS on PostgreSQL —
  portable set-difference + postgresql_where partial unique index behave
  identically to SQLite. Phase goal's "...proven portable on SQLite + PostgreSQL
  in CI" clause is now closed by a live green run.

### 2. Ratify CR-01 intra-batch Product.code deferral (accept as planned scope, or require fix now)
expected: Confirm two NEW products with the same active `code` in ONE batch and no DB incumbent are NOT resolved against each other, so they hit uq_products_code_active → IntegrityError → whole-batch rollback. Decision: ACCEPT (record override) or FIX NOW (re-plan with --gaps).
result: [resolved] Maintainer chose FIX NOW. Fixed in commit c921c8b — _resolve_code_collisions now resolves Product.code collisions among NEW in-batch rows (deterministic order by id; first claimant keeps the clean code; losers renamed via _suffix_code keeping their UUIDs, reported as product_code Conflicts; idempotent on replay). Also fixed WR-01 (strict int money), WR-02 (loud duplicate-origin-UUID reject), WR-03 (widened rename suffix entropy). 7 regression tests added; verifier confirmed DD-2 conformance; full suite 1015 passed / 7 skipped.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
