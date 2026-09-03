---
phase: 25-authentication-roles-user-attribution
plan: 04
subsystem: auth
tags: [session-middleware, auth-guard, csrf, first-run-setup, login, htmx-redirect, context-processor]

# Dependency graph
requires:
  - phase: 25-01
    provides: settings.secret_key for SessionMiddleware signing
  - phase: 25-03
    provides: auth_guard / NotAuthenticated / session_csrf / require_csrf; verify_password; count_users / create_user
provides:
  - app/main.py — SessionMiddleware + app-level Depends(auth_guard) + NotAuthenticated handler (303 HTML / 401+HX-Redirect HTMX)
  - app/routes/auth.py — public /login /logout /setup routes
  - app/routes/__init__.py — _auth_context context processor (current_user + csrf_token) + ROLES Jinja global
  - templates auth_base.html + pages/login.html + pages/setup.html (standalone auth chrome)
  - tests/conftest.py — authenticated client fixture + anon_client + login helper
affects: [25-05 admin role-gated nav + /settings/users, 25-06 CSRF chrome on base/mobile_base, 25-07 attribution at write paths]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A SINGLE app-level dependency (dependencies=[Depends(auth_guard)]) guards every current + future router — deny-by-default, no per-router guard to forget (ROLE-02)"
    - "NotAuthenticated exception handler branches on HX-Request: 401+HX-Redirect for HTMX (which won't swap 4xx), 303 for plain HTML (Pitfall 3)"
    - "csrf_token + current_user reach every template via a shared-templates context processor — no route re-passes them"
    - "Login verifies the password BEFORE branching on is_active so a deactivated account is not disclosed to someone who doesn't know the password (no enumeration oracle)"
    - "The legacy suite stays green by overriding the whole auth_guard (attach a seeded admin + bypass CSRF), not just current_user"

key-files:
  created:
    - app/routes/auth.py
    - app/templates/auth_base.html
    - app/templates/pages/login.html
    - app/templates/pages/setup.html
  modified:
    - app/main.py
    - app/routes/__init__.py
    - tests/conftest.py
    - tests/test_auth.py

key-decisions:
  - "auth_guard is registered app-level (not per-router) — 33 include_router calls would be 33 chances to forget one; the static mount stays public automatically"
  - "The legacy client fixture overrides auth_guard entirely (seeds an admin, sets request.state.user + _current_user, bypasses CSRF) so ~45 existing test files pass unchanged under the guard"
  - "anon_client (real guard, no override) + a login() helper drive the AUTH integration tests; anon_client deliberately seeds no user so each test controls first-run vs seeded state"
  - "POST /login verifies the password before the is_active branch — a deactivated account only reveals «Учётная запись отключена…» to a correct-password caller; unknown login and wrong password share «Неверный логин или пароль.»"
  - "The login lookup (select(User).where(login==...)) lives inline in the thin route; the security-critical parts (verify_password, create_user) stay in the fat services"

requirements-completed: [AUTH-01, AUTH-03, AUTH-04, AUTH-05, ROLE-02]

# Metrics
duration: ~30min
completed: 2026-07-18
---

# Phase 25 Plan 04: App-Level Auth Boundary (SessionMiddleware + Guard + Login/Setup) Summary

**The security boundary is now ON: a single app-level `auth_guard` + itsdangerous-signed `SessionMiddleware` + a `NotAuthenticated` handler put login in front of every route (incl. /export and /backup), with public `/login` `/logout` `/setup` routes, a standalone auth chrome, a `current_user`/`csrf_token` context processor, and an authenticated conftest fixture that keeps the full pre-existing suite green.**

## Performance

- **Duration:** ~30 min (incl. full 965-test suite run, ~3.5 min)
- **Completed:** 2026-07-18
- **Tasks:** 3
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments
- `app/main.py`: `FastAPI(..., dependencies=[Depends(auth_guard)])` guards every router; `SessionMiddleware(secret_key=settings.secret_key, same_site="lax", https_only=False)`; the `NotAuthenticated` handler returns 401+`HX-Redirect` for HTMX (which does not swap 4xx) and a 303 redirect for plain HTML — AUTH-01, ROLE-02, AUTH-03.
- `app/routes/auth.py`: `GET/POST /login` (password verified before the is_active branch — no enumeration oracle; ZERO session on bad creds; password cleared, login preserved), `POST /logout` (`session.clear()`), `GET/POST /setup` (first-run admin; server-side `count_users==0` re-check closes the double-submit race and self-closes once a user exists) — AUTH-03, AUTH-04.
- `app/routes/__init__.py`: `_auth_context` context processor injects `current_user` + `csrf_token` into every template; `ROLES` registered as a Jinja global for the upcoming role `<select>`/menu-hide — AUTH-05 wiring.
- Templates: `auth_base.html` standalone chrome (htmx-config meta verbatim, `<body hx-headers>` CSRF line, no nav, `.mobile-shell` centering) + `pages/login.html` + `pages/setup.html` with the exact RU copy from the UI-SPEC Copywriting Contract; never `|safe` on login/display_name.
- `tests/conftest.py`: the shared `client` now authenticates (seed one admin + override `auth_guard`), plus a new `anon_client` (real guard) and a `login()` helper; 6 new integration tests in `tests/test_auth.py`.
- Full suite: **965 passed** (959 at Plan 03 + 6 new integration tests), 3 pre-existing warnings unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: SessionMiddleware + app-level guard + handler + context processor + conftest** — `57cb922` (feat)
2. **Task 2: /login /logout /setup routes + auth_base/login/setup templates** — `7723d38` (feat)
3. **Task 3: auth integration tests** — `b1ed39d` (test)

**Plan metadata:** this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md (docs commit follows).

## Files Created/Modified
- `app/routes/auth.py` — public login/logout/first-run-setup routes; thin over `verify_password` / `create_user` (created).
- `app/templates/auth_base.html` — standalone auth chrome, htmx-config verbatim, CSRF hx-headers, no nav (created).
- `app/templates/pages/login.html` — «Вход» form with error-block + hidden csrf (created).
- `app/templates/pages/setup.html` — «Первый запуск» admin-creation form (created).
- `app/main.py` — SessionMiddleware, app-level `dependencies=[Depends(auth_guard)]`, `NotAuthenticated` handler, public auth router registration (modified).
- `app/routes/__init__.py` — `_auth_context` context processor + `ROLES` Jinja global (modified).
- `tests/conftest.py` — authenticated `client` fixture (seed admin + guard override), `anon_client`, `login()` helper (modified).
- `tests/test_auth.py` — 6 new integration tests (guard_redirects, gated_export_backup, session_persist_logout, bad-credentials, first_run_setup, csrf) (modified).

## Decisions Made
- The guard is registered **once, app-level** — the ROLE-02 "every route" guarantee. `/static` is a mount, not a router, so app-level dependencies never apply and it stays public.
- The legacy `client` fixture overrides the **whole** `auth_guard` (seeds an admin, sets `request.state.user` + `_current_user`, bypasses CSRF) rather than only `current_user`, so existing POST tests need neither a login round-trip nor a CSRF token.
- `POST /login` verifies the password **before** branching on `is_active` so a deactivated account is disclosed only to a correct-password caller; unknown-login and wrong-password share one generic message (login-oracle mitigation T-25-04-05).
- The login-by-`login` lookup is an inline `select` in the thin route; all credential/creation logic stays in the fat services (`verify_password`, `create_user`).

## Deviations from Plan

None - plan executed exactly as written. All three tasks landed with their planned files; the login-oracle ordering (verify password before the is_active branch) is the plan's own «if found + active + verify_password» expressed to also satisfy threat T-25-04-05.

## Threat Model Coverage
- **T-25-04-01 (EoP, forgotten router):** single app-level `Depends(auth_guard)`; `gated_export_backup` proves /export + /backup are gated.
- **T-25-04-02 (Spoofing, first-run backdoor):** no creds seeded; `/setup` POST re-checks `count_users==0` and self-closes; `first_run_setup` proves it.
- **T-25-04-03 (Tampering, session cookie):** itsdangerous-signed `SessionMiddleware`, `same_site=lax`, only `user_id`+`csrf` stored.
- **T-25-04-04 (Tampering, CSRF):** guard calls `require_csrf` on unsafe methods; `csrf` test proves 403 without a token and success with the session token.
- **T-25-04-05 (Info disclosure, login oracle):** shared «Неверный логин или пароль.» for unknown login vs wrong password; password verified before the deactivated branch; password cleared on re-render.
- **T-25-04-06 (HTMX 4xx swallowed):** 401+`HX-Redirect` for HX requests; `guard_redirects` proves both the 303 (HTML) and 401+HX-Redirect (HTMX) paths.

## Issues Encountered
- Git emits the usual LF→CRLF autocrlf warnings for the new files on Windows (cosmetic; files commit fine).

## Requirements Note
AUTH-01/03/04/05 and ROLE-02 are now user-reachable and covered by integration tests. The role-conditioned nav menu-hide, the `/settings/users` admin page, and the CSRF `hx-headers` on `base.html`/`mobile_base.html` land in Plans 05-06; per-user write-path attribution lands in Plan 07. Marked complete following this phase's per-plan slice convention; the phase-level verifier confirms end-to-end.

## Known Stubs
None — no placeholder/empty-data stubs introduced. Login/setup forms are fully wired to the services.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Ready for 25-05: `current_user` + `ROLES` are in every template context for the role-gated nav and the `/settings/users` admin page; `require_role("administrator")` (from Plan 03) is ready to gate the admin routers.
- Ready for 25-06: `auth_base.html` already carries the CSRF `hx-headers`; `base.html`/`mobile_base.html` still need the same line + the logout control + the role `{% if %}` guards.
- Ready for 25-07: the guard sets `_current_user`; `author_fields()` will resolve to the logged-in user at `record_operation`/`record_cash_movement` (contextvars→threadpool proof deferred there).

## Self-Check: PASSED

- Files exist: `app/routes/auth.py`, `app/templates/auth_base.html`, `app/templates/pages/login.html`, `app/templates/pages/setup.html`, `app/main.py`, `app/routes/__init__.py`, `tests/conftest.py`, `tests/test_auth.py`, `25-04-SUMMARY.md`.
- Commits exist: `57cb922` (Task 1), `7723d38` (Task 2), `b1ed39d` (Task 3).
- Full suite: **965 passed** (959 at Plan 03 + 6 new integration tests), 3 pre-existing warnings unchanged — the authenticated `client` fixture keeps the whole legacy suite green under the new app-level guard (critical wave-merge gate).

---
*Phase: 25-authentication-roles-user-attribution*
*Completed: 2026-07-18*
