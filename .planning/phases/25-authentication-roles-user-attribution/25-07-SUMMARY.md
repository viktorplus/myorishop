---
phase: 25-authentication-roles-user-attribution
plan: 07
subsystem: auth
tags: [attribution, author-id, contextvars, threadpool, single-write-path, user-05]

# Dependency graph
requires:
  - phase: 25-02
    provides: nullable author_id columns on Operation/CashMovement/Sale
  - phase: 25-03
    provides: author_fields() + _current_user ContextVar (settings.operator_name fallback)
  - phase: 25-04
    provides: auth_guard sets _current_user; anon_client + login() test fixtures
provides:
  - app/services/ledger.py::record_operation — author_id/created_by stamped via author_fields()
  - app/services/finance.py::record_cash_movement — author_id/created_by stamped via author_fields()
  - tests/test_attribution.py — end-to-end contextvars->threadpool propagation proof
affects: [later sync phases consuming author_id for per-operator attribution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "author_id/created_by stamped once, at the single write path, from author_fields() — no new params on the ~7 callers"
    - "The async guard's ContextVar current-user propagates into FastAPI's sync def-endpoint threadpool (AnyIO copies the context); proven end-to-end, not assumed"

key-files:
  created:
    - tests/test_attribution.py
  modified:
    - app/services/ledger.py
    - app/services/finance.py

key-decisions:
  - "Contextvars->threadpool propagation HOLDS end-to-end — the real authenticated POST stamps the logged-in user's id through the sync-def hop, so the documented explicit-parameter fallback (RESEARCH Pitfall 4) was NOT needed"
  - "The two-line change stays inside the single write path; no caller signature changed (single-write-path discipline)"
  - "author_fields() fallback keeps every non-authenticated call site (fixtures, scripts, ~45 legacy tests) stamping settings.operator_name with author_id=None"

requirements-completed: [USER-05]

# Metrics
duration: ~15min
completed: 2026-07-18
---

# Phase 25 Plan 07: Write-Path Author Attribution Summary

**Both single write paths (`record_operation`, `record_cash_movement`) now stamp `author_id` + `created_by` from `author_fields()`, and the phase's riskiest mechanism — the async guard's `ContextVar` current-user surviving FastAPI's sync `def`-endpoint threadpool — is PROVEN end-to-end by a real authenticated receipt/deposit POST that persists `author_id == user.id`.**

## Performance

- **Duration:** ~15 min (incl. full 979-test suite run, ~3.5 min)
- **Completed:** 2026-07-18
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `ledger.py::record_operation`: `author_id, created_by = author_fields()` resolved immediately before the `Operation(...)` insert; the insert gains `author_id=author_id` and uses the resolved `created_by` (was `settings.operator_name`). `device_id`/`seq`/`created_at` untouched — USER-05.
- `finance.py::record_cash_movement`: byte-identical change on the `CashMovement(...)` insert.
- No function signature changed, no caller modified — the single-write-path discipline held (both edits are two lines each inside the one write function).
- `tests/test_attribution.py`: 3 end-to-end tests through the REAL guard (`anon_client` + `login()`): a receipt POST stamps `Operation.author_id == user.id` + `created_by == user.display_name`; a deposit POST stamps `CashMovement.author_id == user.id`; two users produce distinct author_ids (per-request, not a global singleton).
- Full suite: **979 passed** (up from the pre-plan count; +3 new attribution tests plus the phase's Plan 05/06 tests), 3 pre-existing warnings unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: Stamp author_id at both single write paths via author_fields()** — `336185d` (feat)
2. **Task 2: Contextvars threadpool-propagation proof (both write paths)** — `8b6ddbf` (test)

**Plan metadata:** this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md (docs commit follows).

## Files Created/Modified
- `app/services/ledger.py` — `author_fields()` import + `author_id/created_by` stamped on the `Operation(...)` insert (modified).
- `app/services/finance.py` — `author_fields()` import + `author_id/created_by` stamped on the `CashMovement(...)` insert (modified).
- `tests/test_attribution.py` — end-to-end contextvars->threadpool attribution proof at both write paths (created).

## Decisions Made
- **Contextvars propagation holds.** The async `auth_guard` calls `_current_user.set(user)`; FastAPI dispatches the sync `def` endpoint via `run_in_threadpool`, which (through AnyIO) copies the calling context into the worker thread, so `author_fields()` reads the correct user inside `record_operation`/`record_cash_movement`. The proving test asserts the REAL `author_id` (not the fallback) through the HTTP stack — RESEARCH Pitfall 4 / Assumption A1 is closed and the explicit-parameter fallback was not needed.
- **Single write path preserved.** No `author`/`current_user` parameter was added to either function and none of the ~7 callers changed — attribution is a property of the single write path, not of every call site.
- **Fallback intact.** With no user in context (fixtures, scripts, the legacy suite) `author_fields()` still returns `(None, settings.operator_name)`, so `author_id` stays `None` and `created_by` stays the operator name on those rows — the ~45 legacy tests stay green.

## Deviations from Plan

None - plan executed exactly as written. Both two-line write-path edits landed as specified; the contextvars propagation test passed on the first run, so the documented fallback path (explicit-parameter threading) was never triggered.

## Threat Model Coverage
- **T-25-07-01 (Repudiation, authorship):** `author_id` is derived from `author_fields()` (server-set contextvar from the signed session), never from a form field — proven by the attribution test.
- **T-25-07-02 (Tampering, wrong-author silent fallback):** the proving test asserts the REAL `author_id` through the threadpool, so a propagation failure would fail the test rather than silently ship the `settings.operator_name` fallback.
- **T-25-07-03 (Integrity, append-only immutability):** attribution is set at INSERT only inside the single write path; the `operations_no_update`/`cash_movements_no_update` triggers forbid any later rewrite (no historical backfill).

## Known Stubs
None — both write paths are fully wired; no placeholder/empty-data values introduced.

## Issues Encountered
- Git emits the usual LF->CRLF autocrlf warning for the new test file on Windows (cosmetic; commits fine).

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- USER-05 is complete and proven end-to-end: every operation and cash movement records the logged-in user as its author at the single write path.
- Plan 08 (the phase's last plan) can add per-user history filtering (`-k filter_by_user`) on top of the now-populated `author_id`, and the phase-level verifier confirms the full AUTH/USER/ROLE surface end-to-end.

## Self-Check: PASSED

- Files exist: `app/services/ledger.py`, `app/services/finance.py`, `tests/test_attribution.py`, `25-07-SUMMARY.md`.
- Commits exist: `336185d` (Task 1), `8b6ddbf` (Task 2).
- `uv run pytest tests/test_attribution.py -k attribution` → 3 passed; full suite → 979 passed, 3 pre-existing warnings unchanged.

---
*Phase: 25-authentication-roles-user-attribution*
*Completed: 2026-07-18*
