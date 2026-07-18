---
phase: 25-authentication-roles-user-attribution
plan: 06
subsystem: auth
tags: [csrf, hx-headers, logout, role-conditioned-nav, menu-hide, chrome, htmx]

# Dependency graph
requires:
  - phase: 25-04
    provides: current_user + csrf_token context processor injected into every template; NotAuthenticated 401+HX-Redirect handling
  - phase: 25-05
    provides: server-side require_role admin boundary; /settings/users; «Настройки» classified admin-only
provides:
  - app/templates/base.html — <body hx-headers> CSRF line + right-aligned logout control + role-gated «Настройки»
  - app/templates/mobile_base.html — duplicated <body hx-headers> CSRF line + 44px logout affordance in the back row
  - tests/test_nav.py — CSRF-header + role-conditioned menu-hide + logout render tests
affects: [25-07 write-path attribution (chrome now fully authenticated across desktop + mobile)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One <body hx-headers='{\"X-CSRF-Token\": \"{{ csrf_token }}\"}'> line on each shared layout covers every hx-post/hx-put/hx-delete descendant on the page — no per-form header (AUTH-05)"
    - "mobile_base.html duplicates the hx-headers line because it is a standalone template that does NOT inherit from base.html (same reasoning as its duplicated htmx-config meta)"
    - "Role-conditioned nav is cosmetic ONLY: {% if current_user.role == 'administrator' %} hides «Настройки»; the authoritative boundary is the require_role dependency from Plan 05 (proven in test_roles.py)"
    - "The logout control is a hrefless <a hx-post='/logout'> chrome affordance, right-aligned with margin-left:auto (no new CSS token); display_name is autoescaped, never |safe (T-25-06-03)"

key-files:
  created:
    - tests/test_nav.py
  modified:
    - app/templates/base.html
    - app/templates/mobile_base.html
    - tests/test_smoke.py

key-decisions:
  - "The logout control has NO href (it is an hx-post affordance, not a navigation destination); NAV-08's «exactly 8» smoke assertion was retargeted to count href-bearing links only, preserving its intent while accommodating the new chrome"
  - "Both layouts guard the logout control in {% if current_user %} so any anonymous render (auth pages use auth_base, not base) never shows it"
  - "The nested same-token hx-headers left on users.html (Plan 05's scoped wrapper) is intentionally NOT removed — it is now redundant but harmless under the base-level line"

requirements-completed: [AUTH-05, ROLE-03]

# Metrics
duration: ~12min
completed: 2026-07-18
---

# Phase 25 Plan 06: Authenticated Chrome (CSRF hx-headers + Logout + Role-Gated Nav) Summary

**Both shared layouts now carry the authenticated chrome: a single `<body hx-headers>` line puts the session CSRF token on every desktop and mobile page (covering logout and every existing state-changing form — AUTH-05), a right-aligned «{display_name} · Выйти» logout control posts to `/logout`, and the admin-only «Настройки» nav item is hidden for operators / shown for administrators (cosmetic ROLE-03 layer over the Plan-05 server-side guard) — full suite 976 green.**

## Performance

- **Duration:** ~12 min (incl. two full 976-test suite runs, ~3.5 min each)
- **Completed:** 2026-07-18
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `app/templates/base.html`: `<body hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'>` (one line covers every `hx-post`/`hx-put`/`hx-delete` on the page — AUTH-05); the existing «Настройки» link wrapped in `{% if current_user and current_user.role == "administrator" %}` (ROLE-03 menu-hide, cosmetic); a right-aligned logout control `<a hx-post="/logout" style="margin-left:auto;cursor:pointer">{{ current_user.display_name }} · Выйти</a>` guarded by `{% if current_user %}`. Operator nav order unchanged.
- `app/templates/mobile_base.html`: the same `<body hx-headers>` CSRF line (duplicated because mobile_base is standalone — mirrors its duplicated `htmx-config` meta); a logout affordance in the `{% block back %}` row, guarded by `{% if current_user %}`, reusing `.mobile-back` (min-height 44px touch target) + `margin-left:auto`, `hx-post="/logout"`. No admin menu-hide needed (mobile has no «Настройки» tab today).
- `tests/test_nav.py` (new): three render tests over the REAL guard (`anon_client` + real `POST /login`) — admin sees CSRF header + «Настройки» + «Выйти»; operator sees CSRF header + «Выйти» but the «Настройки» link is absent (menu-hide); mobile `/m/` carries the CSRF header + an `hx-post="/logout"` affordance with the user's name.
- Full suite: **976 passed** (973 at Plan 05 + 3 new nav tests), 3 pre-existing warnings unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: base.html — CSRF hx-headers + logout control + role-gated «Настройки»** — `efc9975` (feat)
2. **Task 2: mobile_base.html — CSRF hx-headers + logout affordance** — `1afc640` (feat)
3. **Task 3: nav render tests + NAV-08 smoke-count fix** — `821f3e4` (test)

**Plan metadata:** this SUMMARY + STATE.md + ROADMAP.md + REQUIREMENTS.md (docs commit follows).

## Files Created/Modified
- `tests/test_nav.py` — CSRF-header + role-conditioned menu-hide + logout render tests (created).
- `app/templates/base.html` — `<body hx-headers>` CSRF, role-gated «Настройки», right-aligned logout control (modified).
- `app/templates/mobile_base.html` — duplicated `<body hx-headers>` CSRF, 44px logout affordance in the back row (modified).
- `tests/test_smoke.py` — NAV-08 assertion retargeted to count href-bearing nav links (excludes the new hrefless logout chrome) (modified).

## Decisions Made
- The logout control is a **hrefless** `<a hx-post="/logout">` — an affordance, not a navigation destination. NAV-08's `count("<a ") == 8` smoke assertion therefore became `count("<a href=") == 8`, preserving its «exactly 8 navigation items» intent while accommodating the new chrome (the `client` fixture is an administrator, so «Настройки» is present in that count).
- Both layouts guard the logout control in `{% if current_user %}` so any anonymous render never shows it (login/setup use `auth_base`, not these layouts).
- The nested same-token `hx-headers` on `users.html` (Plan 05's scoped wrapper) is intentionally left in place — now redundant under the base-level line but harmless (a nested identical-token header changes nothing).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] NAV-08 smoke test broke on the new logout chrome**
- **Found during:** Task 3 full-suite run
- **Issue:** `tests/test_smoke.py::test_web_top_nav_has_exactly_eight_items` asserts the desktop nav has `count("<a ") == 8`. Adding the logout control (`<a hx-post="/logout">`) made the admin-rendered nav carry 9 `<a ` tags, failing the assertion — a direct consequence of Task 1's chrome change.
- **Fix:** Retargeted the count to `count("<a href=") == 8` (the 8 navigation links all carry `href=`; the logout control is hrefless), and documented the Phase-25 chrome change in the test docstring. NAV-08's intent (exactly 8 navigation destinations) is preserved.
- **Files modified:** `tests/test_smoke.py`
- **Commit:** `821f3e4`

**Total deviations:** 1 auto-fixed test (Rule 1, in scope — directly caused by the nav chrome change). No architectural changes; the other 8 nav-link href/label assertions in that test still pass unchanged.

## Threat Model Coverage
- **T-25-06-01 (Tampering, CSRF coverage):** one `<body hx-headers>` line on `base.html` + `mobile_base.html` carries `X-CSRF-Token` to every hx-post site; `test_desktop_nav_*` + `test_mobile_nav_carries_csrf_and_logout` assert the header renders for every role on both layouts (AUTH-05).
- **T-25-06-02 (EoP, menu-hide mistaken for control):** the `{% if current_user.role == "administrator" %}` guard is explicitly cosmetic — `test_desktop_nav_operator_hides_settings_but_has_logout` proves the operator does not see «Настройки», while the authoritative 403 boundary stays proven server-side in Plan 05's `test_roles.py::test_operator_blocked_from_admin_routes` (direct URL/POST, no nav involved).
- **T-25-06-03 (Info disclosure, display_name in nav):** `current_user.display_name` is rendered with Jinja autoescape, never `|safe`, in both the desktop and mobile logout controls.

## Issues Encountered
- One pre-existing NAV-08 smoke test needed updating for the new logout chrome (see Deviations); no other test touched. Git emits the usual LF→CRLF autocrlf warning for the new `test_nav.py` on Windows (cosmetic; commits fine).

## Requirements Note
AUTH-05 (CSRF on every state-changing surface) and ROLE-03 (admin-only nav, cosmetic over the server-side guard) are now user-reachable on both desktop and mobile chrome and covered by `tests/test_nav.py`. Per-user write-path attribution (author_id at `record_operation` / `record_cash_movement`) lands in Plan 07. Marked complete following this phase's per-plan slice convention; the phase-level verifier confirms end-to-end.

## Known Stubs
None — no placeholder/empty-data stubs introduced. The chrome is fully wired: `csrf_token`/`current_user` arrive via the Plan-04 context processor.

## Threat Flags
None — no new network endpoint, auth path, or trust-boundary surface introduced. The logout `hx-post="/logout"` targets the existing public `/logout` route (Plan 04); this plan only adds the control that invokes it.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Ready for 25-07: every desktop and mobile page now carries the CSRF token and a logged-in identity affordance; the authenticated chrome is complete, so attribution work can proceed on the operator routers with the session's `current_user` reachable in every template.

## Self-Check: PASSED

- Files exist: `app/templates/base.html`, `app/templates/mobile_base.html`, `tests/test_nav.py`, `tests/test_smoke.py`, `25-06-SUMMARY.md`.
- Commits exist: `efc9975` (Task 1), `1afc640` (Task 2), `821f3e4` (Task 3).
- Full suite: **976 passed** (973 at Plan 05 + 3 new nav tests), 3 pre-existing warnings unchanged.

---
*Phase: 25-authentication-roles-user-attribution*
*Completed: 2026-07-18*
