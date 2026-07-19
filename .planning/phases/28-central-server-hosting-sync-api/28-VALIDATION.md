---
phase: 28
slug: central-server-hosting-sync-api
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-19
updated: 2026-07-19
---

# Phase 28 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (`[dependency-groups] dev` in `pyproject.toml`) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| **Quick run command** | `uv run pytest tests/test_append_only_cursor.py tests/test_devices.py tests/test_sync_api.py tests/test_devices_ui.py -x -q` |
| **Full suite command** | `uv run pytest` |
| **PG-only command** | `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postgres uv run pytest tests/test_pg_parity.py -x` |
| **Estimated runtime** | quick ~5-10 s · full suite ~30 s |

The PostgreSQL half runs in the existing GitHub Actions `pg-parity` job on `postgres:17`.
**No new CI job and no new CI step is added by this phase** — Plan 01's new cases land inside
`tests/test_pg_parity.py`, which the existing `PostgreSQL parity` step already runs.

---

## Sampling Rate

- **After every task commit:** the quick run command above
- **After every plan wave:** `uv run pytest` (the project's established post-merge gate for
  sequential-executor mode)
- **Before `/gsd-verify-work`:** full suite green **plus** a GREEN `pg-parity` Actions run
  including the Plan 01 trigger-relaxation cases
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 28-01-01 | 01 | 1 | SRV-02 / SYNC-01 (SC-3) | T-28-08 / T-28-14 / T-28-15 | Relaxed trigger blocks every immutable column; DDL is literal constants only; no `DROP FUNCTION` | integration | `uv run alembic upgrade head && uv run alembic downgrade 0017 && uv run alembic upgrade head && uv run pytest -x -q` | ✅ (alembic) | ⬜ pending |
| 28-01-02 | 01 | 1 | SRV-02 (SC-3) | T-28-08 / T-28-08b / T-28-16 | `synced_at` stamp allowed; mixed + immutable UPDATE and all DELETE rejected; schema drift fails loudly | unit | `uv run pytest tests/test_append_only_cursor.py -x -q` | ❌ W0 | ⬜ pending |
| 28-01-03 | 01 | 1 | SRV-02 (SC-3) | T-28-15 / T-28-16 | Same behaviour on PostgreSQL incl. the `json` payload cast | integration | `DATABASE_URL=… uv run pytest tests/test_pg_parity.py -q` | ✅ (edit) | ⬜ pending |
| 28-02-01 | 02 | 2 | SYNC-09 | T-28-01 | `device_tokens` table, portable constructs, no expiry column | integration | `uv run alembic upgrade head && uv run alembic downgrade 0018 && uv run alembic upgrade head` | ✅ (alembic) | ⬜ pending |
| 28-02-02 | 02 | 2 | SYNC-09 | T-28-07 / T-28-10 / T-28-17 / T-28-18 | SHA-256 at rest, `hmac.compare_digest` compare, CSPRNG mint, soft revoke, zero logging | unit | `uv run pytest tests/test_devices.py -x -q` | ❌ W0 | ⬜ pending |
| 28-02-03 | 02 | 2 | SYNC-09 | T-28-07 / T-28-10 / T-28-18 | Wrong/unknown/revoked token → None; prefix alone does not authenticate; revoke never deletes | unit | `uv run pytest tests/test_devices.py -x -q` | ❌ W0 | ⬜ pending |
| 28-03-01 | 03 | 3 | SYNC-09 | T-28-02 / T-28-03 / T-28-06 | Bypass prefix is exactly `/api/sync/`; `PUBLIC_PATHS` stays exact-match; 401 + `WWW-Authenticate` | integration | `uv run pytest -q` | ✅ (edit) | ⬜ pending |
| 28-03-02 | 03 | 3 | SYNC-09 | T-28-04 / T-28-12 / T-28-19 / T-28-07 | 413 body cap, 429 rate limit, one `session.begin()`, zero `session.commit()`, no logging | integration | `uv run pytest tests/test_sync_api.py -x -q` | ❌ W0 | ⬜ pending |
| 28-03-03 | 03 | 3 | SYNC-09 (SC-2) | T-28-02 / T-28-03 / T-28-04 / T-28-12 | 401 not 303 without token; **both** cross-auth negatives; idempotent replay; all-or-nothing rollback | integration | `uv run pytest tests/test_sync_api.py -x -q` | ❌ W0 | ⬜ pending |
| 28-04-01 | 04 | 4 | SYNC-09 | T-28-20 / T-28-21 / T-28-22 | Reference kinds only; `>=` cursor; per-kind cursor column; pure module | unit | `uv run pytest tests/test_sync_api.py -x -q` | ❌ W0 | ⬜ pending |
| 28-04-02 | 04 | 4 | SYNC-09 | T-28-02 / T-28-12 / T-28-22 | Token-gated read-only NDJSON; clamped limit; 400 on a bad cursor | integration | `uv run pytest tests/test_sync_api.py -x -q` | ❌ W0 | ⬜ pending |
| 28-04-03 | 04 | 4 | **SRV-04** / SYNC-09 (SC-1, SC-2) | T-28-20 / T-28-23 | `/` and `/m/` both 200 from one app; pull excludes ledger kinds; body round-trips through `parse_exchange` | integration | `uv run pytest tests/test_sync_api.py -x -q` | ❌ W0 | ⬜ pending |
| 28-05-01 | 05 | 5 | SYNC-09 | T-28-24 / T-28-07 | Admin-only on all three verbs; plaintext never touches the session | integration | `uv run pytest tests/test_devices_ui.py -x -q` | ❌ W0 | ⬜ pending |
| 28-05-02 | 05 | 5 | SYNC-09 | T-28-25 / T-28-26 / T-28-06 | No `\|safe`; `token_hash`/`token_prefix` never rendered; CSRF via base chrome | integration | `uv run pytest tests/test_devices_ui.py -x -q` | ❌ W0 | ⬜ pending |
| 28-05-03 | 05 | 5 | SYNC-09 | T-28-01 / T-28-07 / T-28-24 / T-28-18 | Show-once proven by a reload assertion; operator 403 on GET+POST+revoke; revoke ≠ delete | integration | `uv run pytest tests/test_devices_ui.py -x -q` | ❌ W0 | ⬜ pending |
| 28-06-01 | 06 | 6 | SRV-04 | T-28-13 / T-28-27 | Non-sqlite dialect skips `VACUUM INTO` with the file-missing accident removed; `Secure` flag env-driven | unit | `uv run pytest tests/test_backup.py -x -q` | ✅ (edit) | ⬜ pending |
| 28-06-02 | 06 | 6 | SRV-04 | T-28-05 / T-28-11 / T-28-28 / T-28-31 / T-28-04 / T-28-29 / T-28-30 | `127.0.0.1` bind only, no `0.0.0.0`, no secrets in `deploy/`, valid shell, proxy body cap | CLI | `test -f deploy/myorishop.service && ! grep -rq "0\.0\.0\.0" deploy/ && sh -n deploy/myorishop-pgbackup.sh && echo OK` | ❌ W0 | ⬜ pending |
| 28-06-03 | 06 | 6 | **SRV-04** (SC-1) | T-28-05 / T-28-11 / T-28-28 | Runbook enumerates TLS, localhost PG, firewall, secrets handling and the server-only mobile constraint | CLI | `test $(grep -c "" deploy/DEPLOY.md) -ge 120 && grep -q "SESSION_HTTPS_ONLY" deploy/DEPLOY.md && echo OK` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Requirement coverage:** SRV-04 → 28-04-03, 28-06-01/02/03. SYNC-09 → 28-02-*, 28-03-*, 28-04-*, 28-05-*.
Both phase requirement IDs appear in at least one plan's `requirements` frontmatter field.

**Sampling continuity:** no three consecutive tasks lack an automated verify — every task in
every plan carries an `<automated>` command.

---

## Wave 0 Requirements

Test files that do not yet exist and are created by the task that first needs them:

- [ ] `tests/test_append_only_cursor.py` — SC-3 on SQLite incl. the schema-derived fail-open guard (created by 28-01-02)
- [ ] `tests/test_devices.py` — SYNC-09 token service unit coverage (created by 28-02-03)
- [ ] `tests/test_sync_api.py` — SYNC-09 endpoint auth, both cross-auth negatives, SC-2 push/pull/idempotency/rollback, SRV-04 both-UIs (created by 28-03-03, extended by 28-04-03)
- [ ] `device_client` fixture in `tests/conftest.py` — the ONLY correct base for token tests; the default `client` fixture overrides `auth_guard` wholesale and cannot exercise the bypass (created by 28-03-01)
- [ ] `tests/test_devices_ui.py` — SYNC-09 admin surface (created by 28-05-03)
- [ ] New cases appended to `tests/test_pg_parity.py` — SC-3 on PostgreSQL (created by 28-01-03)
- [ ] `deploy/` artifacts — verified by CLI existence/grep gates, not pytest (created by 28-06-02/03)

No framework install is needed: pytest, httpx, TestClient and the PostgreSQL harness all exist.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| A live VPS deployment reachable over HTTPS with a real certificate | SRV-04 | No VPS host or domain exists yet (OQ-1 is an open user decision). Certificate issuance requires a real DNS record. **This does not gate the phase** — all three ROADMAP success criteria are provable locally and in CI | Follow `deploy/DEPLOY.md` end to end once a host and domain are chosen, then run its section-10 post-deploy checklist |
| The «Устройства» page rendering correctly in a real browser (layout, htmx swap, `hx-confirm` dialog) | SYNC-09 | Server-side responses are asserted in `tests/test_devices_ui.py`; only the felt client-side htmx behaviour is unconfirmed | Launch `run.bat`, log in as an administrator, visit `/settings/devices`, mint a token, confirm the plaintext shows once with the copy warning, reload and confirm it is gone, then revoke and confirm the row shows «Отозван» |

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify or a declared Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-19
