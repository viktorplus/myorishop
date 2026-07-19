---
phase: 28-central-server-hosting-sync-api
verified: 2026-07-19T21:57:49Z
status: human_needed
score: 3/3 must-haves verified (SQLite + code); SC-3 PostgreSQL half awaits CI proof
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
human_verification:
  - test: "Push the phase-28 pg-parity CI branch (e.g. `ci/phase-28-pg-parity`) at the current HEAD and confirm the `PostgreSQL parity` job is GREEN, exercising the four new SC-3 cases (test_pg_synced_at_stamp_allowed, test_pg_payload_tamper_rejected, test_pg_immutable_columns_still_rejected, test_pg_cash_synced_at_stamp_allowed) on postgres:17."
    expected: "The four SC-3 PostgreSQL cases pass — synced_at stamp allowed, json payload tamper rejected via the ::text cast, qty_delta/created_by rejected, cash amount_cents rejected — proving Success Criterion 3 holds on PostgreSQL as well as SQLite."
    why_human: "PostgreSQL cannot be run in this verification environment (no DATABASE_URL / no local postgres). test_pg_parity.py auto-skips locally (9 skipped). The latest CI run on record is for phase 27 (branch ci/phase-27-pg-parity); no CI run has yet executed phase 28's new PG SC-3 cases against postgres:17. SC-3 explicitly requires the guarantee 'on both SQLite and PostgreSQL', so the PG half needs the same CI proof gate used to close phase 27."
---

# Phase 28: Central Server — Hosting & Sync API Verification Report

**Phase Goal:** Bring the central server alive — a VPS PostgreSQL deployment that hosts both online interfaces (browser + mobile) and exposes token-authenticated push/pull sync endpoints wired to the Phase 27 merge engine, plus the column-scoped append-only trigger relaxation that lets the `synced_at` cursor advance without reopening the ledger to tampering.
**Verified:** 2026-07-19T21:57:49Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The central server hosts a browser (desktop) UI and a mobile UI online; the mobile UI is server-only, no offline mobile install. (SRV-04) | ✓ VERIFIED | `app/main.py:105-168` includes both the desktop routers (`/`) and 13 `mobile_*` routers (`/m/`). `mobile_home.py:20` route is `@router.get("/m/")`. `tests/test_sync_api.py:530 test_both_uis_one_app` asserts `/` and `/m/` both return 200 from one app object, distinct templates (`mobile-tabbar` present in `/m/`, absent from `/`) — passed. Mobile is server-only: it is a set of server-rendered routes under `/m/`, no offline/local mobile install path exists. Provider-agnostic runbook in `deploy/DEPLOY.md`. |
| 2 | The server exposes push and pull sync endpoints authenticated with a per-device token; a request without a valid token is rejected. (SYNC-09) | ✓ VERIFIED | `app/routes/sync.py:57 POST /api/sync/push` and `:127 GET /api/sync/pull`, both `Depends(require_device)`. `app/services/security.py:206 require_device` returns 401 (WWW-Authenticate: Bearer) for missing / unknown / revoked tokens. `SYNC_PATH_PREFIX` bypass in `auth_guard` (`security.py:164`) is compensated by the per-route Bearer gate. Cross-auth negatives tested (device token gives no HTML access; session cookie gives no /api/sync access). 78 phase-28 tests pass, incl. push idempotency, poisoned-batch rollback, 413 body cap. CR-01 pull data-loss fixed (`app/services/sync.py:179,205`) + regression test `test_pull_paginates_across_kind_boundary_no_omissions`. |
| 3 | `synced_at` can be stamped, but any change to an immutable ledger column (`qty_delta`, `amount_cents`, author) is still rejected at the DB — on both SQLite and PostgreSQL — enabling the cursor without weakening append-only. | ⚠️ PARTIAL (SQLite proven; PostgreSQL awaits CI) | SQLite: `alembic/versions/0018` + `app/db.py::APPEND_ONLY_TRIGGERS` carry the identical value-based `FOR EACH ROW WHEN` guard (14 ops cols / 10 cash cols, `synced_at` excluded). 9 tests in `tests/test_append_only_cursor.py` pass: stamp allowed, every immutable column rejected, mixed update rejected, DELETE still rejected, schema-derived fail-open guard, and constants↔DDL lockstep. PostgreSQL: `_PG_DDL` present with the `NEW.payload::text IS DISTINCT FROM OLD.payload::text` json cast; 4 SC-3 cases exist in `tests/test_pg_parity.py:224-307`; CI job configured (`.github/workflows/ci.yml:40-43` runs the file on postgres:17). BUT no CI run has executed these new cases (latest run is phase 27) — see Human Verification. |

**Score:** 3/3 truths verified in code and on SQLite; SC-3's PostgreSQL clause is unexecuted and routed to CI/human.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0018_sync_cursor_trigger_relaxation.py` | Dialect-branched drop+recreate of the two `*_no_update` triggers with value-based WHEN | ✓ VERIFIED | `revision="0018"`, `down_revision="0017"`; `_SQLITE_DDL`/`_PG_DDL`; zero `DROP FUNCTION`; no `app` imports; `payload::text` cast present; `*_no_delete` untouched. |
| `app/db.py::APPEND_ONLY_TRIGGERS` | Test-fixture DDL in lockstep with 0018 | ✓ VERIFIED | 4 entries; two `*_no_update` have `FOR EACH ROW WHEN` with identical 14/10 column enumeration; two `*_no_delete` have no WHEN. |
| `tests/test_append_only_cursor.py` | SQLite SC-3 coverage incl. fail-open guard | ✓ VERIFIED | 9 test functions incl. `test_trigger_column_list_matches_schema` and `test_declared_constants_match_trigger_ddl`. Pass. |
| `app/models.py::DeviceToken` | Device-token ORM model | ✓ VERIFIED | `class DeviceToken` (`:532`) with `token_prefix`, `token_hash` (sha256 hex), `is_active`, `revoked_at`, `last_used_at`, `device_id`. |
| `alembic/versions/0019_device_tokens.py` | device_tokens table, `down_revision="0018"` | ✓ VERIFIED | Single head is `0019` (chains 0019→0018→0017). |
| `app/services/devices.py` | mint/lookup/list/revoke/touch token service | ✓ VERIFIED | All 5 exports present; SHA-256 digest only; plaintext returned once; constant-time `compare_token`; single indexed prefix SELECT; soft-revoke. |
| `app/services/security.py` | SYNC_PATH_PREFIX bypass + require_device Bearer gate | ✓ VERIFIED | Prefix `/api/sync/`; per-route `require_device` 401s on missing/invalid/revoked. |
| `app/routes/sync.py` | push (thin merge caller) + pull (NDJSON cursor) | ✓ VERIFIED | Route owns single transaction; 413 body cap; CR-01 pull fix applied; cursor headers emitted. |
| `app/services/sync.py` | Pure pull-cursor query | ✓ VERIFIED | Reference-only PULL_KINDS; composite `(cursor,id)`; CR-01 `is_paging` guard at `:179,205`. |
| `app/services/rate_limit.py` | In-process token bucket | ✓ VERIFIED | `check_rate_limit`, `reset_buckets` exported. |
| `app/routes/devices.py` + templates | Admin device-token surface | ✓ VERIFIED | Router gated `require_role("administrator")` in `main.py:147-149`; settings link `app/templates/pages/settings.html:16` → `/settings/devices`. Tests pass (operator 403, show-once). |
| `app/services/backup.py` | Non-sqlite dialect guard in startup_backup | ✓ VERIFIED | `engine.dialect.name != "sqlite"` → early `return None` (`:110`). |
| `app/config.py::session_https_only` | Env-driven cookie Secure flag, default off | ✓ VERIFIED | `session_https_only: bool = False`; wired `main.py:85 https_only=config_settings.session_https_only`. |
| `deploy/DEPLOY.md` + unit/proxy/backup files | Provider-agnostic VPS runbook | ✓ VERIFIED | All 6 deploy files present; `myorishop.service` has `ExecStartPre` alembic upgrade + `--host 127.0.0.1`; `example.com` is an RFC-2606 placeholder with explicit replace-instructions (not a real domain). |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| migration 0018 | `app/db.py::APPEND_ONLY_TRIGGERS` | identical WHEN column enumeration | ✓ WIRED — verified byte-level, 14/10 columns match |
| `app/routes/sync.py` | `merge.apply_merge` | route owns `session.begin()` | ✓ WIRED (`sync.py:112-113`) |
| `app/routes/sync.py` | `require_device` | per-route Depends | ✓ WIRED (`sync.py:61,132`) |
| `security.py::auth_guard` | `SYNC_PATH_PREFIX` | early return after PUBLIC_PATHS | ✓ WIRED (`security.py:164`) |
| `devices.py` | `auth.compare_token` | constant-time compare | ✓ WIRED (`devices.py:110`) |
| `main.py` | `devices.router` | include_router w/ require_role('administrator') | ✓ WIRED (`main.py:147-149`) |
| `main.py` | `session_https_only` | SessionMiddleware https_only | ✓ WIRED (`main.py:85`) |
| `myorishop.service` | `alembic upgrade head` | ExecStartPre | ✓ WIRED (`myorishop.service:32`) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| SC-3 SQLite trigger relaxation + SYNC-09 auth + device UI + backup guard | `uv run pytest tests/test_append_only_cursor.py tests/test_devices.py tests/test_sync_api.py tests/test_devices_ui.py tests/test_backup.py -q` | 78 passed | ✓ PASS |
| Single alembic head is 0019 | `uv run alembic heads` | `0019 (head)` | ✓ PASS |
| PG parity auto-skips without DATABASE_URL | `uv run pytest tests/test_pg_parity.py -q` | 9 skipped | ✓ PASS (skip is expected locally) |
| CI unchanged since phase base | `git log --oneline 785ccf2..HEAD -- .github/workflows/ci.yml` | empty | ✓ PASS |
| SC-3 on PostgreSQL (postgres:17) | `DATABASE_URL=... uv run pytest tests/test_pg_parity.py` | not run — no local postgres, no CI run for phase 28 HEAD | ? SKIP → human/CI |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SRV-04 | 28-04, 28-06 | Central server hosts desktop + mobile UI; mobile server-only | ✓ SATISFIED | Truth 1 |
| SYNC-09 | 28-02, 28-03, 28-04, 28-05 | Client authenticates to sync endpoints with per-device token | ✓ SATISFIED | Truth 2 |

Both phase requirements (REQUIREMENTS.md:162) are accounted for. No orphaned requirements. Plan 01 additionally amends SRV-02/SYNC-01 (owned by phases 26/29) via the trigger relaxation — Truth 3.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | No TODO/FIXME/XXX/TBD/HACK/PLACEHOLDER in any phase-28 modified source | ℹ️ Info | None |

### Human Verification Required

**1. Confirm PostgreSQL SC-3 in CI**

**Test:** Push a `ci/phase-28-pg-parity` branch at the current HEAD and confirm the `PostgreSQL parity` CI job is GREEN, running the four new SC-3 cases (`test_pg_synced_at_stamp_allowed`, `test_pg_payload_tamper_rejected`, `test_pg_immutable_columns_still_rejected`, `test_pg_cash_synced_at_stamp_allowed`) against postgres:17.
**Expected:** All four pass — `synced_at` stamp allowed; `payload` tamper rejected through the `::text` json cast; `qty_delta`/`created_by`/`amount_cents` rejected.
**Why human:** PostgreSQL cannot run in this verification environment; the tests auto-skip locally (9 skipped). The latest CI run on record is phase 27; phase 28's new PG cases have not been executed. SC-3 explicitly requires the guarantee on both engines, so the PG half needs the same CI gate that closed phase 27.

### Gaps Summary

No functional gaps. All three success criteria are implemented, wired, and — for SC-1, SC-2, and the SQLite half of SC-3 — proven green (78 phase tests, single alembic head 0019, CI workflow untouched). The CR-01 pull data-loss BLOCKER is fixed with a dedicated cross-kind regression test. The only unresolved item is execution proof of SC-3 on PostgreSQL, which cannot run in this environment and has no CI run yet for phase 28 — routed to human/CI verification rather than treated as a code gap, because the PG DDL and test cases are present and correct-looking (the `payload::text` cast that guards the documented `json = json` trap is in place).

---

_Verified: 2026-07-19T21:57:49Z_
_Verifier: Claude (gsd-verifier)_
