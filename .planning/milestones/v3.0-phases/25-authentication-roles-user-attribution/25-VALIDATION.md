---
phase: 25
slug: authentication-roles-user-attribution
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-18
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `25-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* + httpx 0.28.* (`fastapi.testclient.TestClient`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_auth.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30–60 seconds (full suite; ~45 existing files + new) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_auth.py -x` (or the plan's target new test file)
- **After every plan wave:** Run `uv run pytest` — the ~45 existing test files MUST stay green after the app-level guard + attribution retrofit
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| AUTH-01 / ROLE-02 | Unauthenticated GET of a protected route → 303 redirect to `/login` (HTML) or 401 + `HX-Redirect` (HTMX) | integration | `uv run pytest tests/test_auth.py -k guard_redirects` | ❌ W0 | ⬜ pending |
| AUTH-01 | `export` / `backup` endpoints require login | integration | `... -k gated_export_backup` | ❌ W0 | ⬜ pending |
| AUTH-02 | Password stored only as Argon2id PHC hash; verify accepts correct, rejects wrong | unit | `... -k password_hash` | ❌ W0 | ⬜ pending |
| AUTH-03 | Login sets session; survives a second request; logout clears it | integration | `... -k session_persist_logout` | ❌ W0 | ⬜ pending |
| AUTH-04 | Zero users → `/setup`; POST creates admin; `/setup` self-closes once a user exists | integration | `... -k first_run_setup` | ❌ W0 | ⬜ pending |
| AUTH-05 | POST without CSRF token → 403; with valid token → OK | integration | `... -k csrf` | ❌ W0 | ⬜ pending |
| USER-01 / 02 / 04 | Admin creates user, assigns role, resets another user's password | integration | `... -k user_admin` | ❌ W0 | ⬜ pending |
| USER-03 | Deactivated user cannot log in; existing session rejected next request; past ops keep author | integration | `... -k deactivate` | ❌ W0 | ⬜ pending |
| USER-05 | Sale/receipt/cash op via TestClient persists `author_id == logged-in user` (contextvars propagation proof) | integration | `... -k attribution` | ❌ W0 | ⬜ pending |
| USER-06 / RPT-01 | History + period Reports show author and filter by `author_id`; NULL-author (pre-auth) rows tolerated | integration | `... -k filter_by_user` | ❌ W0 | ⬜ pending |
| ROLE-01 | Exactly two roles; unknown role rejected by the service allow-list | unit | `... -k roles_allowlist` | ❌ W0 | ⬜ pending |
| ROLE-03 | Operator blocked (403) from admin routers server-side; menu item hidden | integration | `... -k operator_blocked` | ❌ W0 | ⬜ pending |
| ROLE-04 | Admin reaches every admin + operator action | integration | `... -k admin_full_access` | ❌ W0 | ⬜ pending |
| (pre-flight) | Append-only triggers still present after the new users/device_id/author_id migration (regression) | integration | `uv run pytest tests/test_pragmas.py` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth.py` — login / guard / csrf / first-run / session (AUTH-01..05)
- [ ] `tests/test_users.py` — user CRUD / deactivate / reset + roles allow-list (USER-01..04, ROLE-01)
- [ ] `tests/test_roles.py` — operator-blocked / admin-full server-side (ROLE-03/04)
- [ ] `tests/test_attribution.py` — `author_id` stamped at both write paths; history / report filter (USER-05/06, RPT-01)
- [ ] **Update `tests/conftest.py`** — the existing `client` fixture must now log in (or override `current_user`), or **every one of the ~45 existing test files breaks** once the app-level guard lands. Highest-effort Wave-0 item.
- [ ] Extend `tests/test_pragmas.py` — assert append-only triggers survive the new migration (Pitfall 1 regression guard).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| First-run admin setup UX on a fresh empty DB in a real browser | AUTH-04 | Full guided flow + redirect chain best confirmed visually | Delete/rename `.db`, launch `run.bat`, confirm `/setup` appears, create admin, confirm subsequent login gate |
| Admin-only menu items visually hidden for an operator | ROLE-03 | Template-hide is cosmetic; server-side block is the automated boundary | Log in as operator, confirm user-management/warehouses/dictionaries/settings nav items are absent |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (plan-checker Dim 8a: every impl task has an inline automated command)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (Dim 8c pass)
- [x] Wave 0 covers all MISSING references — each plan creates its own tests alongside implementation; no separate Wave-0-only gap (Dim 8d pass)
- [x] No watch-mode flags (Dim 8b pass)
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

> `wave_0_complete` stays `false` until execution: tests are authored but not yet run green.

**Approval:** approved 2026-07-18 (design-time; per gsd-plan-checker verification of Phase 25 plans)
