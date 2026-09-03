---
phase: 28
slug: central-server-hosting-sync-api
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-20
---

# Phase 28 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Phase 28 opens the app's first internet-facing, token-authenticated sync API
> (`/api/sync/push`, `/api/sync/pull`), a per-device Bearer credential store, and
> the VPS deployment surface (Caddy TLS, systemd, PostgreSQL). Every mitigation
> below was VERIFIED present in implemented code — documentation and intent were
> not accepted as evidence.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Internet → Caddy | Public HTTPS listener; TLS terminates at the proxy (automatic ACME cert) | Encrypted HTTP; Bearer tokens, session cookies, ledger NDJSON |
| Caddy → uvicorn | Reverse-proxy hop to `127.0.0.1:8000`; app is plain-HTTP on localhost, never binds a public interface | Proxied HTTP; `X-Forwarded-*` trusted only from 127.0.0.1 |
| Bearer device token → `/api/sync/` tree | Per-device credential (256-bit CSPRNG), gated by `require_device`; NOT the session-cookie tree | SHA-256-verified token; push/pull ledger + reference records |
| Session cookie → HTML tree (`/`, `/m/`) | itsdangerous-signed cookie; `Secure` on the public HTTPS domain (`SESSION_HTTPS_ONLY=true`) | `user_id` + CSRF token only |
| Admin → `/settings/devices` | Device-token mint/revoke surface, gated `require_role("administrator")` | Plaintext token shown ONCE; only SHA-256 digest at rest |
| App → PostgreSQL | Localhost-only DB connection (`127.0.0.1:5432`), never internet-exposed | Connection URL + password from chmod-600 `/etc/myorishop.env` |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation (verified evidence) | Status |
|-----------|----------|-----------|-------------|--------------------------------|--------|
| T-28-01 | Spoofing | device token theft | mitigate | `revoke_token` soft-disable (`is_active=0` + `revoked_at`) + `touch_last_used` staleness — `app/services/devices.py:113,131-147` | closed |
| T-28-02 | Spoofing | sync-endpoint auth | mitigate | `require_device` raises 401 on missing AND unknown/revoked, indistinguishable RU messages + `WWW-Authenticate: Bearer` — `app/services/security.py:206-237` | closed |
| T-28-03 | EoP | auth_guard bypass scope | mitigate | `SYNC_PATH_PREFIX = "/api/sync/"` exact prefix, `PUBLIC_PATHS` exact-set, no bare `/api/` — `app/services/security.py:39,52,164`; router carries no blanket dep — `app/main.py:150-155` | closed |
| T-28-04 | DoS | unbounded push body | mitigate | `MAX_PUSH_BYTES=32MB` checked on Content-Length AND `len(payload)` → 413 — `app/routes/sync.py:52,82-90`; proxy twin `request_body { max_size 32MB }` — `deploy/Caddyfile:25-27`. Residual WR-02 (in-memory buffering) documented below | closed |
| T-28-05 | Info Disclosure | TLS transport | mitigate | Caddy automatic HTTPS terminates at proxy; uvicorn `--host 127.0.0.1` — `deploy/myorishop.service:36`; no `0.0.0.0` anywhere under `deploy/` (grep: 0 matches) | closed |
| T-28-06 | Tampering | CSRF on sync tree | mitigate | `auth_guard` returns at step (3) for the Bearer tree BEFORE the session/CSRF check; HTML tree `require_csrf` untouched (browsers never auto-attach `Authorization`) — `app/services/security.py:164,173-174` | closed |
| T-28-07 | Info Disclosure | token plaintext at rest/logs | mitigate | Only SHA-256 hex persisted (`_digest`), plaintext returned ONCE by `mint_token`, never assigned to row/logged — `app/services/devices.py:49-89`; zero `print`/logging in devices.py (grep: 0); route never echoes body — `app/routes/sync.py:96,105` | closed |
| T-28-08 | Tampering | *_no_update triggers | mitigate | Value-based `FOR EACH ROW WHEN` enumerating 14 op / 10 cash immutable columns (not `UPDATE OF`) — `alembic/versions/0018:74-107`, `app/db.py:35-82` | closed |
| T-28-08b | Tampering | trigger↔schema drift (fail-open) | mitigate | `test_trigger_column_list_matches_schema` asserts column set == model columns − `synced_at` — `tests/test_append_only_cursor.py:244-256` | closed |
| T-28-08c | Tampering | db.py ↔ migration lockstep | mitigate | `APPEND_ONLY_TRIGGERS` SQLite DDL byte-matches `_SQLITE_DDL` in 0018; `test_declared_constants_match_trigger_ddl` guards drift — `app/db.py:35-82`, `tests/test_append_only_cursor.py:259-288` | closed |
| T-28-09 | Repudiation / Spoofing | client-supplied `author_id`/`created_by` | **accept (LOW)** | Documented in Accepted Risks Log; full 6-point rationale in `28-03-PLAN.md:406-445`. Evaluated in place — see log | closed |
| T-28-10 | Spoofing | token-compare timing side-channel | mitigate | Indexed `SELECT` on non-secret `token_prefix`, then `hmac.compare_digest` on digests, never `==` — `app/services/devices.py:92-110`, `app/services/auth.py:55-61` | closed |
| T-28-11 | Info Disclosure | PostgreSQL exposure | mitigate | DEPLOY.md: PG bound to localhost only (§2, `ss -ltnp` check) + ufw firewall opens only 22/80/443 (§8) — `deploy/DEPLOY.md:57-66,180-190` | closed |
| T-28-12 | DoS | request flooding | mitigate | In-process token bucket keyed by `token_prefix` (30 burst / 0.5 rps) → 429 — `app/services/rate_limit.py:19-47`, `app/routes/sync.py:75-77,156-157`; edge control documented (Caddy). Residual WR-01 (limiter after auth) documented below | closed |
| T-28-13 | DoS | VACUUM INTO on PostgreSQL | mitigate | `engine.dialect.name != "sqlite"` early return in `startup_backup` — `app/services/backup.py:110-111`; `BACKUP_ON_STARTUP=false` on server — `deploy/DEPLOY.md:99,107` | closed |
| T-28-14 | Tampering | SQL injection via migration DDL | mitigate | All DDL held in module-level tuples of LITERAL constants, applied via `op.execute(stmt)`; no interpolation — `alembic/versions/0018:68-144,174-189` | closed |
| T-28-15 | DoS | PG `json` column equality | mitigate | `NEW.payload::text IS DISTINCT FROM OLD.payload::text` cast in PG trigger — `alembic/versions/0018:121`; `test_pg_payload_tamper_rejected` — `tests/test_pg_parity.py:251` | closed |
| T-28-16 | EoP | relaxation permits DELETE | mitigate | `*_no_delete` triggers NOT referenced by 0018 (only `*_no_update` dropped/recreated); DELETE stays unconditionally blocked — `alembic/versions/0018:22-24`, `app/db.py:56-60,77-81` | closed |
| T-28-17 | Spoofing | weak token generation | mitigate | `secrets.token_urlsafe(32)` (256-bit CSPRNG), never `random`/`uuid4` — `app/services/devices.py:37,77` | closed |
| T-28-18 | Repudiation | hard-delete of tokens | mitigate | `revoke_token` never calls `session.delete`; `list_device_tokens` returns active+revoked; UI has revoke button only, no delete control — `app/services/devices.py:123-147`, `app/templates/partials/device_rows.html:44-52` | closed |
| T-28-19 | Tampering | route re-implements merge | mitigate | Route calls `parse_exchange`/`apply_merge` unchanged; exactly one `session.begin()`, zero `session.commit()`; poisoned record rolls the whole batch back — `app/routes/sync.py:103,111-113` | closed |
| T-28-20 | Info Disclosure | pull leaks ledger kinds | mitigate | `PULL_KINDS` = six reference kinds only; operations/cash_movements deliberately excluded (derived from `merge.KIND_TO_MODEL`) — `app/services/sync.py:58-65` | closed |
| T-28-21 | Tampering | SQL injection via `since` cursor | mitigate | `datetime.fromisoformat(since)` validation → 400 on garbage; value only ever a bound parameter in `select()` — `app/routes/sync.py:162-166` | closed |
| T-28-22 | Tampering | server stamps/trusts `synced_at` | mitigate | Pull is read-only: no `begin()`/`commit()`, server `synced_at` stays NULL — `app/services/sync.py:16-22`, `app/routes/sync.py:135-139` | closed |
| T-28-23 | Repudiation | divergent wire format | mitigate | Pull serializes through the UNMODIFIED Phase 27 `merge.serialize_exchange` — `app/routes/sync.py:174-179` | closed |
| T-28-24 | EoP | operator can mint tokens | mitigate | `include_router(devices.router, dependencies=[Depends(require_role("administrator"))])` → 403 on all three routes — `app/main.py:147-149`; test coverage `tests/test_devices_ui.py` (403 on every verb) | closed |
| T-28-25 | Info Disclosure | templates render token hash/prefix | mitigate | No `token_hash`/`token_prefix` reference in any template (grep across `app/templates`: 0 matches); rows partial renders only label/device_id/status/last_used — `app/templates/partials/device_rows.html:38-54` | closed |
| T-28-26 | Tampering | XSS via device label | mitigate | Jinja2 autoescape on; zero `|safe` in rows partial; label rendered as escaped text — `app/templates/partials/device_rows.html:1-6,39` | closed |
| T-28-27 | Info Disclosure | session cookie `Secure` flag | mitigate | `session_https_only` (default False, env `SESSION_HTTPS_ONLY`) wired into `SessionMiddleware(https_only=...)` — `app/config.py:36-42`, `app/main.py:81-86`; `SESSION_HTTPS_ONLY=true` on server — `deploy/DEPLOY.md:98,106` | closed |
| T-28-28 | Info Disclosure | secrets at rest / in logs | mitigate | `EnvironmentFile=/etc/myorishop.env` chmod 600, never committed, placeholders only — `deploy/myorishop.service:20-28`, `deploy/DEPLOY.md:102-111`; `pg_dump` reads libpq env, never echoes connection string — `deploy/myorishop-pgbackup.sh:13-25` | closed |
| T-28-29 | DoS | server boots on half-upgraded schema | mitigate | `ExecStartPre=alembic upgrade head` fails start on migration error; `Restart=always` — `deploy/myorishop.service:32,41` | closed |
| T-28-30 | DoS | no server-side backup | mitigate | `pg_dump -Fc` on a systemd `OnCalendar=daily` timer, 30-day `-mtime` retention — `deploy/myorishop-pgbackup.{sh,service,timer}` | closed |
| T-28-31 | Spoofing | forged client source IPs | mitigate | uvicorn default `--forwarded-allow-ips` (127.0.0.1); explicit comment never to widen to `"*"` — `deploy/myorishop.service:37-40` | closed |
| T-28-32 | DoS | non-terminating pagination | mitigate | Composite `(cursor, id)` strictly-greater predicate `or_(col > since, and_(col == since, id > after_id))` guarantees forward progress — `app/services/sync.py:200-204` | closed |
| T-28-SC | Tampering | supply chain (new packages) | **accept** | VERIFIED zero new packages: `git diff c473c4e..HEAD -- pyproject.toml` shows only ruff `extend-immutable-calls` gaining `fastapi.Security`/`fastapi.Body` (linter config); `[project] dependencies`/dev groups unchanged. Rate limiter is ~40 lines of stdlib (`secrets`/`hashlib`/`hmac`), alembic already a dep | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-28-09 | T-28-09 | Client-supplied `author_id`/`created_by` carried verbatim into the ledger. Assessed **LOW** and accepted in place (not re-rated): (1) verbatim carriage is the Phase 27 engine contract DD-6, shared by Phase 29 online + Phase 30 offline — re-attributing in this route would fork the one engine; (2) attacker must already hold an admin-minted, individually-revocable device token (`require_device`, no anonymous path); (3) no self-service enrolment — every token is admin-created at `/settings/devices` and instantly revocable; (4) attribution not fully lost — origin `device_id` + the authenticating `DeviceToken` row (device_id/user_id/last_used_at) still recorded, a forgery leaves a visible mismatch; (5) single-reseller 1-3 device deployment, `author_id` drives display/reporting (RPT-01/USER-06), NOT authz or money; (6) append-only guarantee unaffected — a forged row can be inserted but never altered/deleted. Full text: `28-03-PLAN.md:406-445`. Revisit trigger: multi-tenant, self-service/shared tokens, or `author_id` driving authz. Auditor concurs LOW at block_on:high — the correct escalation, if any, is a Phase 29 design change, not a Phase 28 hotfix. | gsd-security-auditor | 2026-07-20 |
| AR-28-SC | T-28-SC | Supply chain: zero new packages added by any Phase 28 plan. Verified against git — the only `pyproject.toml` change is ruff linter config (`fastapi.Security`/`fastapi.Body` added to `extend-immutable-calls`), no runtime or dev dependency added. Rate limiter, token hashing and compare use only stdlib (`secrets`, `hashlib`, `hmac`); Caddy/PostgreSQL are OS packages installed by the operator. | gsd-security-auditor | 2026-07-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Residual / Advisory Notes (non-blocking)

These do NOT reopen any threat — the declared mitigations for T-28-04 and T-28-12
are present in code AND include the proxy as the authoritative edge control, and
that proxy config ships in `deploy/Caddyfile`. Recorded for Phase 29 hardening.

| Ref | Note | Disposition |
|-----|------|-------------|
| WR-01 | The in-process rate limiter runs INSIDE the handler, after `require_device`. Unauthenticated garbage-token floods are rejected by the Bearer gate first and never reach `check_rate_limit`; authenticated-but-throttled requests still incur `touch_last_used`'s `UPDATE ... COMMIT`. App-layer limiter is effective only for authenticated volume; unauthenticated flood protection relies on the upstream Caddy proxy. Deferred as proxy-mitigated. | advisory |
| WR-02 | `payload: bytes = Body(...)` buffers the whole body before the `len()` cap fires, so the 32MB check bounds acceptance, not peak memory. Real memory bound is Caddy `request_body { max_size 32MB }`; app must not be exposed without the proxy. Deferred as proxy-mitigated. | advisory |
| IN-01 | `session_https_only` defaults False (required for localhost/tests); it is an easily-missed deploy step. DEPLOY.md §4 and the post-deploy checklist §10.3 require setting `SESSION_HTTPS_ONLY=true` and verifying the `Secure` flag. Documented, not enforced at startup. | advisory |

**Auditor judgment at block_on: high** — T-28-04 and T-28-12 are DoS threats whose
declared mitigation is a two-layer control (in-process app cap/limiter + Caddy edge
twin). Both layers are present in code and config. WR-01/WR-02 show the app-layer
portion is partial, but the register's own mitigation plan names the proxy as the
authoritative edge control, and `deploy/Caddyfile` (Plan 06) is shipped. The
declared mitigation is therefore present, not absent and not weaker than declared,
so these remain CLOSED. No BLOCKER.

---

## Unregistered Flags

None. The `## Threat Flags` section of 28-01..05 SUMMARY.md each reads "None — all
STRIDE surface enumerated in the plan's `<threat_model>`"; 28-06-SUMMARY.md uses a
`## Threat Mitigations Applied` table (T-28-05/11/13/27/28/29/30/31) that maps to
already-registered IDs. No new attack surface appeared during implementation
without a mapped threat ID.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-20 | 35 | 35 | 0 | gsd-security-auditor |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (AR-28-09, AR-28-SC)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-20
