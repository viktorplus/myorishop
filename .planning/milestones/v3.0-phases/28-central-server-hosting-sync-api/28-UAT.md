---
status: passed
phase: 28-central-server-hosting-sync-api
source: [28-VERIFICATION.md]
started: 2026-07-19T00:00:00Z
updated: 2026-07-19T22:13:00Z
---

## Current Test

number: 1
name: SC-3 PostgreSQL parity — append-only trigger relaxation proven on postgres:17 in CI
expected: |
  Push a branch at HEAD to origin (e.g. `ci/phase-28-pg-parity`). The GitHub Actions
  `pg-parity` job (postgres:17) runs the full SQLite suite, then `test_pg_parity.py -x`
  and `test_merge_pg.py -x` against a live PostgreSQL 17. All three steps must be GREEN,
  confirming: `synced_at` can be stamped on a ledger row, but any attempt to change an
  immutable ledger column (`qty_delta`, `amount_cents`, author) is still rejected at the
  database on PostgreSQL — including the `payload::text` json-cast case. This closes the
  "on both SQLite and PostgreSQL" clause of Success Criterion 3. Same gate that closed
  Phase 27 (run over `ci/phase-27-pg-parity`).
awaiting: none — passed

## Tests

### 1. SC-3 PostgreSQL parity — append-only trigger relaxation proven on postgres:17 in CI
expected: GitHub Actions `pg-parity` job GREEN on a branch at current HEAD — SQLite suite + `test_pg_parity.py` + `test_merge_pg.py` all pass against postgres:17, proving `synced_at` is stampable while every immutable column stays locked on PostgreSQL.
result: passed — CI run 29705703575 (job 88242189180) GREEN in 1m37s over `ci/phase-28-pg-parity` @ becc31f; all three steps (SQLite suite, PostgreSQL parity, PostgreSQL merge portability) passed on postgres:17.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
