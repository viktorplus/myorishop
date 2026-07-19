---
status: testing
phase: 27-shared-idempotent-merge-core
source: [27-VERIFICATION.md]
started: 2026-07-19T00:00:00Z
updated: 2026-07-19T00:00:00Z
---

## Current Test

number: 1
name: GitHub Actions pg-parity job green for the merge portability slice
expected: |
  After pushing the branch, the CI `pg-parity` job's step "PostgreSQL merge
  portability (SYNC-02/04/05)" runs tests/test_merge_pg.py against postgres:17,
  and both test_merge_idempotent_on_pg and test_code_collision_on_pg PASS —
  proving the portable pre-select set-difference and the postgresql_where partial
  unique index behave identically to SQLite. This closes the phase goal's
  "...proven portable on SQLite + PostgreSQL in CI" clause.
awaiting: user response

## Tests

### 1. GitHub Actions pg-parity job green for the merge portability slice
expected: test_merge_idempotent_on_pg and test_code_collision_on_pg both PASS on postgres:17 in the CI pg-parity job (skipif-guarded, skips locally on SQLite — verified 2 skipped locally). Live green run is the deliverable proof of both-dialect portability.
result: [pending]

### 2. Ratify CR-01 intra-batch Product.code deferral (accept as planned scope, or require fix now)
expected: Confirm two NEW products with the same active `code` in ONE batch and no DB incumbent are NOT resolved against each other, so they hit uq_products_code_active → IntegrityError → whole-batch rollback (a LOUD atomic reject, never silent data loss/corruption). Not reachable from a single well-formed device push nor the planned Phase 28/29 online push or Phase 30 offline self-upload. Plan 27-03 explicitly scoped this tie-break OUT. Decision: ACCEPT (record override) or FIX NOW (re-plan with --gaps).
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
