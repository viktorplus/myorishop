---
phase: 25-authentication-roles-user-attribution
verified: 2026-07-18T07:40:10Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial verification
human_verification:
  - test: "Product decision on WR-02 — confirm the intended visibility of the whole-business cash-flow/profit report at /finance/report and /finance/report.csv."
    expected: "A human/product owner confirms whether this report is operator-visible (as the code + operator-reachable button on /finance imply) or administrator-only. If admin-only is desired, the finance report routes need a server-side require_role gate (currently absent) AND the boundary would be only half-met; if operator-visible, the base.html nav active-state that files /finance/report under the admin «Настройки» highlight should be corrected."
    why_human: "SC4 enumerates exactly four admin-only sections (user management, warehouses, dictionaries, settings) — the finance report is NOT among them, so the code does NOT violate SC4 as written. But the nav design groups the report under the admin menu, hinting at an intent conflict only a product owner can settle. This is a business-sensitivity decision, not a codebase fact."
  - test: "First-run + auth browser flow: launch the app with an empty DB, confirm it lands on /setup, create the initial administrator, then verify login/logout/refresh-persistence and the role-conditioned «Настройки» menu render on both desktop and mobile."
    expected: "Zero-users first run shows the setup screen and no other page is reachable; after creating the admin you are logged straight in; refresh keeps the session; «Выйти» ends it; an operator does not see «Настройки», an admin does; the login/setup screens render correctly."
    why_human: "Visual rendering and the end-to-end browser navigation flow (UI-SPEC line 206 UAT gates) cannot be verified by grep; the underlying behaviors are covered by automated tests but the visual/UX layer is not."
---

# Phase 25: Authentication, Roles & User Attribution Verification Report

**Phase Goal:** Add the app's first security boundary — mandatory login gates every desktop and mobile route (plus export/backup), users have a profile and one of two roles, and every operation and cash movement is attributed to the logged-in user. Fully testable on one SQLite client before any server exists. Also fixes device identity (per-install unique `device_id`) as a pre-flight for all later sync.
**Verified:** 2026-07-18T07:40:10Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ------- | ---------- | -------------- |
| 1 | First run with no users guides creation of an initial administrator (no default credentials); thereafter every desktop + mobile page + export/backup requires login via a server-side guard on every router; unauthenticated visitors are redirected to login. (AUTH-01, AUTH-04, ROLE-02) | ✓ VERIFIED | Single app-level `dependencies=[Depends(auth_guard)]` on the FastAPI app (`app/main.py:73`) covers all 33 routers incl. `export.router` (`:130`) and `backup.router` (`:123`). `auth_guard` (`security.py:123-147`): zero users → `NotAuthenticated("/setup")`, no active session → `NotAuthenticated("/login")`. Exception handler (`main.py:85-96`) returns 303 (plain) / 401+HX-Redirect (HTMX). Setup route creates the first admin with no shipped credentials (`auth.py:98-125`). StaticFiles is a mount, correctly exempt. |
| 2 | Login with login+password (Argon2id hashes only), stays logged in across refresh via a signed cookie, logout ends session; state-changing HTMX POSTs are CSRF-protected. (AUTH-02, AUTH-03, AUTH-05) | ✓ VERIFIED | `auth.py:hash_password`/`verify_password` wrap `argon2.PasswordHasher` (Argon2id defaults), constant-time, never raises, rehash-on-login. `SessionMiddleware` with persisted stable `secret_key` (`main.py:77-82`, `config.py`+`device_id.py`). `logout` → `session.clear()` (`auth.py:82-85`). `auth_guard` step 5 calls `require_csrf` for every unsafe method (`security.py:104-117`, `hmac.compare_digest`); `csrf_token` injected into every template via context processor (`routes/__init__.py:20-29`); `hx-headers` on `base.html:35` + `mobile_base.html:33`. |
| 3 | Admin can create a user (display name/login/role), deactivate (soft) without deleting, reset another's password; a deactivated user cannot log in but past ops stay attributed; exactly two roles exist. (USER-01..04, ROLE-01) | ✓ VERIFIED | `users.py` service: `create_user` (validates ROLES allow-list, unique login, hashes pw), `deactivate_user` (is_active=0, self-deactivate refused, never deleted), `reset_password`, `reactivate_user`. Login rejects `is_active != 1` (`auth.py:64-70`); `get_active_user` bounces deactivated sessions next request. `author_id` FK preserved on soft-disable. `ROLES = {"administrator","operator"}` — exactly two (`models.py:142-145`). Route surface `/settings/users*` behind `require_role` (`users.py`, `main.py:136-138`). |
| 4 | Operator can do receipts/sales/writeoffs/returns/corrections/cash movements, but admin-only sections (user mgmt, warehouses, dictionaries, settings) are BOTH hidden AND server-side-blocked; admin has full access + every operator action. (ROLE-03, ROLE-04) | ✓ VERIFIED | The four enumerated admin routers carry `dependencies=[Depends(require_role("administrator"))]`: warehouses (`main.py:114`), dictionary (`:117`), settings (`:132`), users (`:136`). `require_role` reads `request.state.user` (server-side, not menu) and admin ⊇ operator (`security.py:150-167`). Nav hide is cosmetic (`base.html:48`). Operator routers (receipts/sales/writeoffs/returns/corrections/finance/…) intentionally ungated. See WR-02 adjudication below. |
| 5 | Every operation and cash movement records the logged-in user as author at the single record_operation() write path; History and period Reports show the operating user and filter by user. (USER-05, USER-06, RPT-01) | ✓ VERIFIED | `ledger.record_operation` and `finance.record_cash_movement` both stamp `author_id, created_by = author_fields()` (`ledger.py:109-124`, `finance.py:74-85`), server-derived from the guard's contextvar — never client input. `test_attribution.py` proves contextvars survive the def-endpoint threadpool. History (`operations.history_view`) joins Operation→User and displays author (`history_rows.html:163`), filters via `Operation.author_id` (`history.py:113`). Reports (`sales_profit_report`) filter sales by `Operation.author_id` (`reports.py:106,50-51`); «Пользователь» select in `history_rows.html` + `sales_report_results.html`. |

**Score:** 5/5 truths verified

### WR-02 Adjudication (finance report gating) — REQUESTED

**Concern:** `/finance/report` and `/finance/report.csv` (`app/routes/finance.py:299,330`) carry no `require_role`; the `finance.router` is registered without one (`main.py:131`), so any authenticated operator can reach them by URL — while `base.html:49` files `/finance/report` under the admin-only «Настройки» active-state (and `:44` excludes it from the «Финансы» highlight).

**Judgment: this does NOT contradict Success Criterion 4, as written.** SC4 enumerates exactly four administrator-only sections — *user management, warehouses, dictionaries, settings* — and all four are BOTH hidden (`base.html:48` conditional) AND server-side-blocked (`require_role` on their routers). The finance report is **not** one of the four enumerated sections. Three independent design sources confirm finance is intended operator-accessible:
- Plan `25-05-PLAN.md:86,90,100` explicitly instructs "do NOT gate … finance …; ROLE-03 lists ONLY user-management/warehouses/dictionaries/settings as admin-only."
- `main.py:106-113` comment states the same.
- `25-UI-SPEC.md:163` says «Настройки» "holds user management, warehouses, dictionaries" — the finance report is not listed there either.
- The operator-accessible `/finance` page links to the report via a button «Отчёт и экспорт CSV» (`pages/finance.html:10`), giving operators a legitimate UI path.

**The real defect is cosmetic:** `base.html` highlights the admin «Настройки» tab (not «Финансы») when viewing `/finance/report` (`:44,49`). For an operator «Настройки» is hidden, so *neither* tab highlights while they view a report they legitimately reached from «Финансы». This is a nav active-state inconsistency, **not** a security boundary and **not** an SC4 failure.

**Residual question routed to a human (not a codebase gap):** the nav grouping hints someone may have *intended* the whole-business profit/cash-flow report to be admin-only. Whether that business sensitivity is real is a product decision, surfaced in `human_verification[0]`. If admin-only is later chosen, the report routes would need a server-side `require_role` (they lack one today) and only then would the boundary be half-met.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | ----------- | ------ | ------- |
| `app/services/security.py` | auth_guard, require_role, CSRF, author_fields | ✓ VERIFIED | Deny-by-default guard, role gate, synchronizer-token CSRF, contextvar attribution helper — all present and wired app-level |
| `app/services/auth.py` | Argon2id hash/verify + timing-safe compare | ✓ VERIFIED | `PasswordHasher` (Argon2id), rehash-on-login, `hmac.compare_digest` |
| `app/services/users.py` | user CRUD + ROLES allow-list | ✓ VERIFIED | create/deactivate/reactivate/reset, unique-login, soft-disable |
| `app/routes/auth.py` | login/logout/setup | ✓ VERIFIED | First-run self-close, deactivated rejection, session write/clear |
| `app/routes/users.py` | /settings/users admin surface | ✓ VERIFIED | Behind require_role; create/deactivate/reactivate/reset routes |
| `app/main.py` | app-level guard + admin router gating | ✓ VERIFIED | Single `Depends(auth_guard)`; require_role on 4 admin routers; SessionMiddleware |
| `app/models.py` | User model + author_id columns + ROLES | ✓ VERIFIED | User table, nullable author_id FK on operations/sales/cash_movements, 2-role dict |
| `alembic/versions/0017_*` | users table + author_id (native add_column) | ✓ VERIFIED | create_table users + native add_column (append-only ledger preserved) |
| `app/config.py` + `app/device_id.py` | persisted secret_key + per-install device_id | ✓ VERIFIED | File-persisted identity/signing key outside the DB |
| `app/templates/base.html` / `mobile_base.html` | CSRF hx-headers + logout + role menu-hide | ✓ VERIFIED | hx-headers, «Выйти», admin-only «Настройки» conditional |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| app (all routers) | auth_guard | `dependencies=[Depends(auth_guard)]` | ✓ WIRED | `main.py:73` — single app-level guard |
| auth_guard | user attribution | `_current_user.set(user)` + `request.state.user` | ✓ WIRED | `security.py:146-147` |
| record_operation / record_cash_movement | logged-in user | `author_fields()` | ✓ WIRED | `ledger.py:109`, `finance.py:74` |
| admin routers | role gate | `require_role("administrator")` | ✓ WIRED | `main.py:114,117,132,136` |
| templates | csrf_token / current_user | context_processor | ✓ WIRED | `routes/__init__.py:20-34` |
| history/reports | author filter | `Operation.author_id` | ✓ WIRED | `history.py:113`, `reports.py:51` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| history_rows.html | `r.author.display_name` / `users` | `history_view` join Operation→User; `list_users` | ✓ real join, not static | ✓ FLOWING |
| sales_report_results.html | `report` / `users` | `sales_profit_report` Operation query; `list_users` | ✓ real DB query | ✓ FLOWING |
| Operation.author_id | current user | `author_fields()` ← contextvar ← guard | ✓ server-derived, proven by test_attribution | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full test suite green | `uv run pytest -q` | 981 passed, 3 warnings in 214.99s | ✓ PASS |
| argon2/itsdangerous importable | (covered by suite import + PasswordHasher use) | suite green | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| AUTH-01 | 04 | Login required before any page | ✓ SATISFIED | app-level auth_guard |
| AUTH-02 | 01,03 | Argon2id password hashes only | ✓ SATISFIED | auth.py PasswordHasher |
| AUTH-03 | 01,04 | Signed cookie session + logout | ✓ SATISFIED | SessionMiddleware + persisted secret_key + logout |
| AUTH-04 | 04 | First-run admin setup, no default creds | ✓ SATISFIED | /setup flow, create_user |
| AUTH-05 | 03,04,06 | CSRF on HTMX POST | ✓ SATISFIED | require_csrf + hx-headers |
| USER-01 | 02,03,05 | User profile (name/login/role) | ✓ SATISFIED | User model + create_user |
| USER-02 | 03,05 | Admin creates user + role | ✓ SATISFIED | users route + create_user |
| USER-03 | 03,05 | Soft-disable without deleting | ✓ SATISFIED | deactivate_user is_active=0 |
| USER-04 | 03,05 | Reset another user's password | ✓ SATISFIED | reset_password |
| USER-05 | 02,07 | Author stamped at record_operation() | ✓ SATISFIED | author_fields() both write paths |
| USER-06 | 08 | History shows + filters by user | ✓ SATISFIED | history_view join + author filter |
| ROLE-01 | 02,03 | Exactly two roles | ✓ SATISFIED | ROLES dict |
| ROLE-02 | 04,05 | Server-side guard every route incl export/backup | ✓ SATISFIED | app-level guard covers all routers |
| ROLE-03 | 05,06 | Admin sections hidden + blocked; operator ops allowed | ✓ SATISFIED | require_role on 4 routers + nav hide (see WR-02) |
| ROLE-04 | 03,05 | Admin full access + every operator action | ✓ SATISFIED | require_role admin passes every check |
| RPT-01 | 08 | Reports filterable by operator | ✓ SATISFIED | sales_report_results «Пользователь» select |

All 16 declared requirement IDs are present in REQUIREMENTS.md and covered by at least one plan. No orphaned requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| app/services/sales.py | 255 | `created_by=settings.operator_name` on the Sale HEADER (not via author_fields) | ℹ️ Info | NOT a gap: History and Reports attribution both read Operation rows (properly stamped via author_fields); the Sale header's created_by/author_id is legacy and unused for USER-05/06/RPT-01 display or filtering. Plan 07 deliberately scoped attribution to the two write paths. |
| app/templates/base.html | 44,49 | `/finance/report` filed under admin «Настройки» active-state | ℹ️ Info | Cosmetic nav-highlight inconsistency (see WR-02); not a security boundary |

No `TBD`/`FIXME`/`XXX` debt markers in any phase source file. No stubs, no orphaned artifacts.

### Code Review Findings Status (from 25-REVIEW.md)

| ID | Finding | Verifier disposition |
| -- | ------- | -------------------- |
| WR-01 | Login timing side-channel (Argon2 verify skipped for unknown login) | Confirmed present (`auth.py:59-63`). Message oracle IS closed; only the timing oracle is open. Hardening nit on a localhost single-operator app — does NOT fail AUTH-02/03/05. Not a phase gap. |
| WR-02 | Finance report operator-accessible while nav-filed under admin menu | Adjudicated above — not an SC4 failure; residual product question routed to human. |
| WR-03 | create_user SELECT-then-INSERT, no IntegrityError catch | Confirmed (`users.py:76,94-95`); DB `uq_users_login` is the real backstop so integrity is safe; worst case is a 500 on a rare double-submit race. Robustness nit, not a goal failure. |
| IN-01/02/03 | logout CSRF-exempt / reactivate always-200 / rehash-before-active-check | Minor, non-blocking; consistent with review. |

### Human Verification Required

1. **WR-02 product decision** — Confirm whether the whole-business cash-flow/profit report (`/finance/report`, `/finance/report.csv`) is intentionally operator-visible (as code + the operator `/finance` button imply) or should be administrator-only. If admin-only: the routes need a server-side `require_role` (currently absent). If operator-visible: fix the `base.html` nav active-state so it does not file the report under the admin «Настройки» menu.
2. **First-run + auth browser flow (visual UAT)** — Empty DB → `/setup` → create admin → login/logout/refresh persistence → role-conditioned «Настройки» render on desktop + mobile. Behaviors are automated-tested; the visual/UX layer (UI-SPEC line 206 gates) is not.

### Gaps Summary

No blocking gaps. All 5 success criteria are observably true in the codebase and backed by a green 981-test suite (test_auth, test_roles, test_attribution, test_nav, test_users). The two items above require human judgment — one is a product/business decision (WR-02 report visibility), the other is visual/UX UAT that cannot be verified programmatically. The security-critical mechanisms (Argon2id hashing, app-level deny-by-default guard, server-side role gates on the four enumerated admin sections, CSRF synchronizer token, and server-derived attribution surviving the threadpool hop) are all present, substantive, wired, and data-flowing.

---

_Verified: 2026-07-18T07:40:10Z_
_Verifier: Claude (gsd-verifier)_
