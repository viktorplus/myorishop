---
phase: 25-authentication-roles-user-attribution
plan: 03
subsystem: auth
tags: [argon2id, password-hash, csrf, contextvars, rbac, require-role, user-service, fat-service]

# Dependency graph
requires:
  - phase: 25-01
    provides: argon2-cffi installed; settings.secret_key / device_id
  - phase: 25-02
    provides: User model, ROLES allow-list, author_id columns, users table
provides:
  - app/services/auth.py — Argon2id hash_password/verify_password (rehash-on-login) + compare_token
  - app/services/users.py — user CRUD (create/deactivate/reactivate/reset) + count_users/get_active_user/list_users, ROLES validation
  - app/services/security.py — _current_user ContextVar, author_fields(), NotAuthenticated, PUBLIC_PATHS, CSRF helpers, auth_guard, require_role
affects: [25-04 app wiring (SessionMiddleware + guard + login/setup), 25-05 admin role gating + user page, 25-06 CSRF chrome, 25-07 attribution at write paths]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Security-critical credential logic lives in a fat service (auth.py), never in a route (V5/V6)"
    - "contextvars _current_user set by the guard; author_fields() reads it with a settings.operator_name fallback so existing tests stay green"
    - "CSRF synchronizer token in the signed session, constant-time compared via hmac.compare_digest"
    - "require_role dependency: administrator satisfies every operator check (admin ⊇ operator hierarchy)"

key-files:
  created:
    - app/services/auth.py
    - app/services/users.py
    - app/services/security.py
    - tests/test_users.py
  modified:
    - tests/test_auth.py

key-decisions:
  - "author_fields() defaults to (None, settings.operator_name) when the contextvar is unset — keeps the ~45 existing tests + fixtures green until Plan 07 wires the guard"
  - "display_name is capped to 100 chars on store so the append-only ledger created_by (String(100)) snapshot always fits"
  - "verify_password never raises: VerifyMismatchError/InvalidHashError both map to False; a malformed/empty stored hash returns False"
  - "require_csrf accepts the X-CSRF-Token header (HTMX) or the csrf_token form field (plain form); auth_guard issues a token BEFORE the public-path early-return"

patterns-established:
  - "Fat-service auth core unit-tested with the plain session fixture (no HTTP) before any app wiring exists"
  - "require_role returns a per-role FastAPI dependency reading request.state.user; admin passes every check (ROLE-04)"

requirements-completed: [AUTH-02, AUTH-05, USER-01, USER-02, USER-03, USER-04, ROLE-01, ROLE-04]

# Metrics
duration: ~18min
completed: 2026-07-18
---

# Phase 25 Plan 03: Security Core (Argon2id, User Service, Guard) Summary

**Pure-Python security core — Argon2id hash/verify/rehash, the admin user service (create/deactivate/reactivate/reset with ROLES validation), and the security.py guard module (contextvars author_fields, auth_guard, require_role, NotAuthenticated, CSRF synchronizer helpers) — all unit-tested with the plain `session` fixture before any app wiring.**

## Performance

- **Duration:** ~18 min (incl. full 959-test suite run, ~3 min)
- **Completed:** 2026-07-18
- **Tasks:** 3
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments
- `auth.py`: `hash_password` (PHC-encoded Argon2id, random salt per call), `verify_password` (constant-time, false on malformed hash, rehash-on-login via `check_needs_rehash`), `compare_token` (hmac.compare_digest) — AUTH-02.
- `users.py`: `create_user`/`deactivate_user`/`reactivate_user`/`reset_password` + `count_users`/`get_active_user`/`list_users`, all mirroring the warehouses `(obj|None, errors)` contract with HTML-free RU messages from the UI-SPEC copywriting contract; validates `role` against `ROLES`, unique login, required fields; caps display_name to the 100-char snapshot width — USER-01/02/03/04, ROLE-01.
- `security.py`: `_current_user` ContextVar + `author_fields()` (settings.operator_name fallback), `NotAuthenticated(redirect)`, `PUBLIC_PATHS`, CSRF helpers (`issue_csrf`/`session_csrf`/`require_csrf`), the app-level `auth_guard`, and `require_role` (admin ⊇ operator) — AUTH-05, ROLE-02/04, USER-03/05 helper.
- 38 new tests (22 in `tests/test_auth.py`, 16 in `tests/test_users.py`); full suite 959 passed (was 921 at Plan 02).

## Task Commits

Each task was committed atomically:

1. **Task 1: Argon2id auth service (TDD)** — `123d226` (test, RED) → `30641c6` (feat, GREEN)
2. **Task 2: Admin user service** — `0e9e2fc` (feat)
3. **Task 3: security.py guard module** — `ee59e70` (feat)

**Plan metadata:** this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md (docs commit follows).

## Files Created/Modified
- `app/services/auth.py` — Argon2id hashing/verification/rehash + timing-safe token compare (created).
- `app/services/users.py` — admin user service + lookups + RU error constants (created).
- `app/services/security.py` — contextvars, author_fields, NotAuthenticated, CSRF helpers, auth_guard, require_role (created).
- `tests/test_users.py` — 16 service-level user CRUD/deactivate/reset/roles tests (created).
- `tests/test_auth.py` — 22 unit tests: password hash/verify/rehash, token compare, author_fields fallback, CSRF, require_role (modified — grew across Tasks 1 and 3).

## Decisions Made
- `author_fields()` returns `(None, settings.operator_name)` when `_current_user` is unset so the ~45 existing tests and fixtures keep their current attribution; real per-user attribution is threaded when the guard is wired (Plan 07).
- `display_name` is truncated to 100 chars on store (not rejected) so the append-only `created_by` snapshot always fits — matches the Plan 02 note that the service caps it.
- `verify_password` is total (never raises): mismatch and malformed/empty hashes both return False.
- `require_csrf` is async (reads header then form); `auth_guard` is async and issues the CSRF token before the public-path early-return so `/login` can render one.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test helper overwrote the empty-hash case under test**
- **Found during:** Task 1 (Argon2id auth service)
- **Issue:** `_make_user(..., password_hash="")` used `password_hash or hash_password(raw)`; the empty string is falsy, so a real hash was computed instead of storing `""`, making `test_verify_password_returns_false_on_malformed_hash` assert True.
- **Fix:** Introduced an `_UNSET` sentinel so an explicit `""` (or any malformed value) is stored verbatim while the default still hashes `raw_password`.
- **Files modified:** `tests/test_auth.py`
- **Verification:** `uv run pytest tests/test_auth.py` — 22 passed.
- **Committed in:** `30641c6` (Task 1 GREEN commit).

---

**Total deviations:** 1 auto-fixed (1 bug, in test-only code).
**Impact on plan:** The fix corrected a test-helper bug that masked a real behavior assertion; no production code affected, no scope creep.

## Issues Encountered
- Git emits the usual LF→CRLF autocrlf warnings for the new files on Windows (cosmetic; files commit fine).

## Requirements Note
The service tier for AUTH-05, USER-02/03/04 and ROLE-04 is complete and unit-tested here, but these become user-reachable only once the app wiring lands: SessionMiddleware + the app-level `auth_guard` (Plan 04), admin routes + `/settings/users` page (Plan 05), and the CSRF `hx-headers` chrome (Plan 06). Marked complete following this phase's per-plan slice convention (Plans 01/02); the phase-level verifier confirms end-to-end.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ready for 25-04: `auth_guard`, `NotAuthenticated`, `issue_csrf`/`require_csrf`, `count_users`/`get_active_user` are in place for the app-level dependency + SessionMiddleware + login/logout/setup routes and the authenticated conftest fixture.
- `author_fields()` is ready for Plan 07 to replace the `settings` reads inside `record_operation`/`record_cash_movement` (with the contextvars→threadpool proof deferred there).

## Self-Check: PASSED

- Files exist: `app/services/auth.py`, `app/services/users.py`, `app/services/security.py`, `tests/test_auth.py`, `tests/test_users.py`, `25-03-SUMMARY.md`.
- Commits exist: `123d226`, `30641c6` (Task 1), `0e9e2fc` (Task 2), `ee59e70` (Task 3).
- Full suite: 959 passed (921 + 38 new), 3 pre-existing warnings unchanged.

---
*Phase: 25-authentication-roles-user-attribution*
*Completed: 2026-07-18*
