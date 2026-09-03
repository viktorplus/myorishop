---
status: complete
phase: 26-postgresql-portability-append-only-parity
source: [26-VERIFICATION.md]
started: 2026-07-18T23:34:59Z
updated: 2026-07-19T07:16:00Z
---

## Current Test

[testing complete]

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
result: pass
notes: |
  Verified live via GitHub Actions against the real postgres:17 CI service.
  Pushed HEAD (main @ 8b61df8) to branch ci/phase-26-pg-parity to trigger the
  `on: push` CI workflow without advancing origin/main.
  Run: https://github.com/viktorplus/myorishop/actions/runs/29677761455
  conclusion: success (job "PostgreSQL portability & append-only parity
  (SRV-01/SRV-02)" GREEN in 1m37s).
  Evidence from CI logs:
  - SQLite suite step: 982 passed, 5 skipped (the 5 PG-parity tests skip without
    DATABASE_URL, as designed).
  - PG parity step (DATABASE_URL=postgresql+psycopg://...): "5 passed in 0.24s" —
    full migration history applied to the empty postgres:17 (SRV-01), Cyrillic
    case-insensitive search parity held, and UPDATE/DELETE on both `operations`
    and `cash_movements` were rejected at the DB layer (SRV-02): logs show
    `ERROR: operations ledger is append-only` (operations_append_only()) and
    `ERROR: cash ledger is append-only` (cash_movements_append_only()) for the
    UPDATE and DELETE statements the tests issue.

## Summary

total: 1
passed: 1
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
