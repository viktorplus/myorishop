---
status: testing
phase: 26-postgresql-portability-append-only-parity
source: [26-VERIFICATION.md]
started: 2026-07-18T23:34:59Z
updated: 2026-07-18T23:34:59Z
---

## Current Test

number: 1
name: Push the phase branch to GitHub and confirm the Actions `pg-parity` job is GREEN
expected: |
  `alembic upgrade head` completes on the empty postgres:17 service (SRV-01) and
  all 5 tests/test_pg_parity.py assertions pass — full history applies
  (products/operations/cash_movements exist), Cyrillic search parity holds, and
  UPDATE/DELETE on operations + cash_movements are rejected with an `append-only`
  error (SRV-02).
awaiting: user response

## Tests

### 1. GitHub Actions `pg-parity` job is GREEN against real PostgreSQL
expected: |
  Push the branch to GitHub; the `pg-parity` job runs against the `postgres:17`
  service. `alembic upgrade head` applies the full migration history to the empty
  PG database (SRV-01), and all 5 `tests/test_pg_parity.py` assertions pass:
  the products/operations/cash_movements tables exist, Cyrillic case-insensitive
  search returns identical results to SQLite (SRV-01), and UPDATE/DELETE on both
  `operations` and `cash_movements` are rejected at the database with an
  `append-only` error (SRV-02).
why_human: |
  The 5 PG-parity tests SKIP locally by design (no DATABASE_URL / no PostgreSQL on
  this Windows host). The actual proof executes only against the real postgres:17
  CI service, which requires pushing the branch to GitHub. Config
  human_verify_mode: end-of-phase deferred this to end-of-phase verification.
result: [pending]

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
