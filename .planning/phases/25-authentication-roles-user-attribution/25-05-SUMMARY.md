---
phase: 25-authentication-roles-user-attribution
plan: 05
subsystem: auth
tags: [rbac, require-role, admin-gating, user-management, htmx-swap, csrf, role-boundary]

# Dependency graph
requires:
  - phase: 25-03
    provides: require_role dependency + user service (create/deactivate/reactivate/reset/list)
  - phase: 25-04
    provides: app-level auth_guard + SessionMiddleware + current_user/csrf_token context processor + anon_client/login fixtures
provides:
  - app/main.py — warehouses/dictionary/settings/users routers gated with Depends(require_role("administrator")) (ROLE-02/03)
  - app/routes/users.py — GET/POST /settings/users (+ /{id}/deactivate|reactivate|reset-password), thin over app/services/users.py
  - templates pages/users.html + partials/user_rows.html + partials/user_reset.html (create/list/deactivate/reactivate/reset, scoped CSRF hx-headers)
  - tests/test_roles.py — operator_blocked (ROLE-03) + admin_full_access (ROLE-04); HTTP user tests in tests/test_users.py
affects: [25-06 role-conditioned nav + CSRF chrome on base.html/mobile_base.html, 25-07 write-path attribution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Admin boundary = a per-router include_router dependency (require_role) that reads request.state.user set by the app-level guard which runs first — an operator gets 403 BEFORE the route body; menu-hide (Plan 06) is cosmetic only (ROLE-02/03)"
    - "ONLY user-management/warehouses/dictionaries/settings are admin-gated; every operator router (products, sales, receipts, history, reports, finance, mobile_*) stays open so an operator keeps product + warehouse pickers during receipts/sales"
    - "The users page scopes CSRF hx-headers onto its own content wrapper (base.html gets the line in Plan 06) so every descendant hx-post inherits the token now — the page is self-contained before the base-chrome change"
    - "The create form lives OUTSIDE #users-table and is never swapped, so an operator's typed values survive a 422 naturally; the inline error renders at the top of the refreshed table region"
    - "Reset password uses a native <details> reveal (no client JS, no extra GET route) wrapping an in-place swap fragment; the new password is never pre-filled or echoed back"

key-files:
  created:
    - app/routes/users.py
    - app/templates/pages/users.html
    - app/templates/partials/user_rows.html
    - app/templates/partials/user_reset.html
    - tests/test_roles.py
  modified:
    - app/main.py
    - tests/test_users.py

key-decisions:
  - "require_role is applied at include_router (never re-checked inside the thin routes) — the dependency is the single boundary; app-level auth_guard runs first and attaches request.state.user, so require_role can read it"
  - "deactivate/reactivate/create all swap the whole #users-table (outerHTML) rather than a single <tr>, keeping the partial set to the three planned templates while still flipping the affected row's status and action; reset swaps its own in-row fragment"
  - "the deactivate actor_id is taken from request.state.user server-side (never a form field); deactivate_user refuses the acting admin's own id and the own-row deactivate control is omitted in the template (self-lockout guard, T-25-05-03)"
  - "create-form validation errors render as an error block at the top of the swapped table region (the form is not swapped, so typed values persist) rather than strictly under each field — the field-level service errors are all surfaced, and the UI-SPEC copy is preserved"

requirements-completed: [USER-01, USER-02, USER-03, USER-04, ROLE-02, ROLE-03, ROLE-04]

# Metrics
duration: ~25min
completed: 2026-07-18
---

# Phase 25 Plan 05: Admin Role-Gating + User-Management Page Summary

**The administrator boundary is now enforced SERVER-SIDE: the warehouses / dictionaries / settings / new users routers are gated with `Depends(require_role("administrator"))` (an operator gets 403 before the route body, menu-hide is cosmetic), and `/settings/users` ships a create / list / deactivate / reactivate / reset-password page over the fat user service, proven by `operator_blocked` + `admin_full_access` role tests and HTTP user tests — full suite 973 green.**

## Performance

- **Duration:** ~25 min (incl. full 973-test suite run, ~3.5 min)
- **Completed:** 2026-07-18
- **Tasks:** 3
- **Files modified:** 7 (5 created, 2 modified)

## Accomplishments
- `app/main.py`: `warehouses`, `dictionary`, `settings`, and the NEW `users` router each carry `dependencies=[Depends(require_role("administrator"))]` (ROLE-02/03). Every OTHER router stays operator-accessible — products, sales, receipts, history, reports, finance, and all `mobile_*` remain 200 for an operator (ROLE-03 lists only the four admin sections).
- `app/routes/users.py`: thin routes over `app/services/users.py` — `GET /settings/users` (page / HX rows), `POST /settings/users` (create, 200 + «Пользователь создан.» / 422 with the service errors), `POST /settings/users/{id}/deactivate` (server-side self-refusal via `request.state.user`), `.../reactivate`, `.../reset-password` (in-row fragment swap, password never echoed) — USER-01/02/03/04.
- Templates: `pages/users.html` (create-user `.stacked-form` with the RU labels + a two-option `ROLES` select, scoped CSRF `hx-headers`), `partials/user_rows.html` (swappable `#users-table`: Имя/Логин/Роль/Статус/Действия; own-row omits Деактивировать; disabled row offers Активировать), `partials/user_reset.html` (native `<details>` reveal + in-place reset fragment). Autoescape only — never `|safe` on display_name/login.
- `tests/test_roles.py`: `operator_blocked` (403 on all four admin surfaces + a valid-CSRF admin POST, 200 on operator routes) and `admin_full_access` (200 everywhere + create-user), driving the real guard via `anon_client` + `login`. `tests/test_users.py`: 6 HTTP tests (create/duplicate/deactivate/self-refusal/reactivate/reset).
- Full suite: **973 passed** (965 at Plan 04 + 8 new), 3 pre-existing warnings unchanged — the admin-gated warehouses/dictionary/settings routers keep their existing tests green because the shared `client` fixture authenticates as an administrator.

## Task Commits

Each task was committed atomically:

1. **Task 1: Gate admin routers with require_role + register the users router** — `f6ba9cc` (feat)
2. **Task 2: User-management page + partials + HTTP user tests** — `b698fcb` (feat)
3. **Task 3: Role-boundary tests (operator blocked, admin full access)** — `8d6bf00` (test)

**Plan metadata:** this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md (docs commit follows).

## Files Created/Modified
- `app/routes/users.py` — thin admin user-management routes over the fat user service (created).
- `app/templates/pages/users.html` — create-user form + users table, scoped CSRF hx-headers (created).
- `app/templates/partials/user_rows.html` — swappable users table, own-row deactivate omission (created).
- `app/templates/partials/user_reset.html` — in-row reset-password fragment, password never echoed (created).
- `tests/test_roles.py` — operator_blocked / admin_full_access server-side role tests (created).
- `app/main.py` — require_role on warehouses/dictionary/settings + registered the gated users router (modified).
- `tests/test_users.py` — 6 HTTP create/deactivate/reset route tests (modified).

## Decisions Made
- The admin boundary is a per-router `include_router` dependency (`require_role("administrator")`); the app-level `auth_guard` runs first and attaches `request.state.user`, so `require_role` reads it and 403s an operator before the route body ever runs — the menu-hide in Plan 06 is cosmetic only (ROLE-02/03).
- deactivate/reactivate/create swap the whole `#users-table` (outerHTML), keeping the template set to the three planned partials; reset swaps its own in-row `<details>` fragment. The create form sits outside `#users-table` and is never swapped, so a 422 preserves the operator's typed values naturally.
- The deactivate `actor_id` is server-derived from `request.state.user` (never a form field); `deactivate_user` refuses the acting admin's own id and the own-row control is omitted (self-lockout guard).

## Deviations from Plan

### Auto-fixed / implementation choices

**1. [Rule 3 - Blocking] Reset-password reveal uses native `<details>` (no GET route)**
- **Found during:** Task 2
- **Issue:** The UI-SPEC describes the reset input being "revealed", but the plan's route set has no GET endpoint to fetch a reveal fragment, and the "no client JS beyond HTMX" rule forbids a scripted toggle.
- **Fix:** Wrapped the in-row reset fragment in a native HTML `<details>`/`<summary>` disclosure — zero JS, zero extra route, still a click-to-reveal. The POST swaps the fragment in place.
- **Files:** `app/templates/partials/user_rows.html`, `partials/user_reset.html`
- **Committed in:** `b698fcb`.

**2. [Rule 2 - Missing critical] Scoped CSRF `hx-headers` on the users page wrapper**
- **Found during:** Task 2
- **Issue:** `base.html` does not carry the `<body hx-headers>` CSRF line until Plan 06, so every `hx-post` on this admin page (create/deactivate/reactivate/reset) would be rejected 403 by the guard's CSRF check in a real browser.
- **Fix:** Added `hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'` on the page's content wrapper (inherited by all descendant hx-posts) plus a hidden `csrf_token` on the two `<form>`s. The page is self-contained now and unaffected when Plan 06 adds the base-level line.
- **Files:** `app/templates/pages/users.html`, `partials/user_reset.html`
- **Committed in:** `b698fcb`.

**3. HTTP user tests placed in `tests/test_users.py`**
- Per the plan's artifacts ("extended tests/test_users.py (HTTP create/deactivate/reset)") and the frontmatter `files_modified`, the 6 HTTP route tests live in `tests/test_users.py` alongside the existing service tests. `tests/test_roles.py` holds only the role-boundary tests. Not a behavioural deviation.

**Total deviations:** 2 implementation choices (both within Rules 2/3, no scope creep) + 1 test placement note. No architectural changes.

## Threat Model Coverage
- **T-25-05-01 (EoP, admin routers):** `require_role("administrator")` on warehouses/dictionary/settings/users; `operator_blocked` proves 403 (ROLE-02/03).
- **T-25-05-02 (EoP, menu-hide mistaken for control):** the dependency is the boundary; nav-hide is Plan 06 cosmetic — `operator_blocked` blocks direct URL/POST access with no nav involved.
- **T-25-05-03 (EoP, self-lockout):** `deactivate_user` refuses the acting admin's own id (server-side), the own-row control is omitted; `test_http_deactivate_refuses_self` proves 422 + still-active.
- **T-25-05-04 (Tampering, create/reset input):** all validation stays in `app/services/users.py` (role allow-list, duplicate login, required fields); routes stay thin; every POST is CSRF-protected by the guard.
- **T-25-05-05 (Info disclosure, reset echo):** the new password is written server-side and never rendered back into the reset fragment; `test_http_reset_password_updates_hash_and_never_echoes` asserts the raw value is absent from the response.

## Issues Encountered
- Git emits the usual LF→CRLF autocrlf warnings for the new files on Windows (cosmetic; files commit fine).

## Requirements Note
USER-01/02/03/04 are now user-reachable over HTTP and ROLE-02/03/04 are proven server-side. The role-conditioned nav menu-hide + the CSRF `hx-headers` on `base.html`/`mobile_base.html` land in Plan 06 (this page carries its own scoped hx-headers meanwhile); per-user write-path attribution lands in Plan 07. Marked complete following this phase's per-plan slice convention; the phase-level verifier confirms end-to-end.

## Known Stubs
None — the users page is fully wired to `app/services/users.py`; no placeholder/empty-data stubs introduced.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Ready for 25-06: `current_user.role` is in every template context for the `{% if %}` menu-hide; when `base.html`/`mobile_base.html` gain the `<body hx-headers>` CSRF line, the users page's own scoped wrapper becomes redundant but harmless.
- Ready for 25-07: the admin boundary and user service are in place; write-path attribution can proceed on the operator routers that stayed open here.

## Self-Check: PASSED

- Files exist: `app/routes/users.py`, `app/templates/pages/users.html`, `app/templates/partials/user_rows.html`, `app/templates/partials/user_reset.html`, `tests/test_roles.py`, `app/main.py`, `tests/test_users.py`, `25-05-SUMMARY.md`.
- Commits exist: `f6ba9cc` (Task 1), `b698fcb` (Task 2), `8d6bf00` (Task 3).
- Full suite: **973 passed** (965 at Plan 04 + 8 new), 3 pre-existing warnings unchanged — admin-gated warehouses/dictionary/settings routers stay green under the authenticated `client` fixture.

---
*Phase: 25-authentication-roles-user-attribution*
*Completed: 2026-07-18*
