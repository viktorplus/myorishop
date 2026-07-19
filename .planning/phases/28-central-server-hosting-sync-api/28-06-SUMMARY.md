---
phase: 28-central-server-hosting-sync-api
plan: 06
subsystem: deployment
tags: [deployment, postgresql, systemd, reverse-proxy, tls, session-cookie, backup, pg_dump, runbook, SRV-04]
requires: [SRV-04, "28-01", "28-03", "28-04", "28-05"]
provides: [deploy-artifacts, dialect-guarded-startup-backup, session_https_only, DEPLOY-runbook]
affects:
  - app/services/backup.py
  - app/config.py
  - app/main.py
  - deploy/
tech-stack:
  added: []
  patterns:
    - "dialect gate idiom (app/db.py precedent): resolve the engine, then `if engine.dialect.name != \"sqlite\": return` before any SQLite-only work"
    - "environment-driven security flag with a safe default (session_https_only: bool = False; env SESSION_HTTPS_ONLY, true only on the server)"
    - "operator artifacts under deploy/ — never imported or executed by the app; every host-specific value is a placeholder"
    - "systemd ExecStartPre mirrors run.bat's `alembic upgrade head` so migration-on-deploy is identical on both targets"
key-files:
  created:
    - deploy/myorishop.service
    - deploy/Caddyfile
    - deploy/myorishop-pgbackup.sh
    - deploy/myorishop-pgbackup.service
    - deploy/myorishop-pgbackup.timer
    - deploy/DEPLOY.md
  modified:
    - app/services/backup.py
    - app/config.py
    - app/main.py
    - tests/test_backup.py
decisions:
  - "startup_backup() gains an explicit `engine.dialect.name != \"sqlite\"` early return (OQ-6): a PostgreSQL boot can no longer reach `VACUUM INTO`; the regression test forces settings.db_path to an EXISTING file so the file-missing accident cannot mask the guard"
  - "session_https_only defaults False so localhost/run.bat and the whole suite (plain HTTP) keep working; set true only in /etc/myorishop.env for the public HTTPS domain (T-28-27)"
  - "SessionMiddleware reads https_only at registration time, so the test asserts the WIRING (constructed middleware option == settings.session_https_only) rather than a live flip — documented limitation in the test docstring"
  - "deploy/ is provider-agnostic: no VPS vendor, tier/plan name, real domain or public IP; only 127.0.0.1 and the placeholder shop.example.com appear"
metrics:
  duration: ~22min
  tasks: 3
  files: 10
  completed: 2026-07-19
---

# Phase 28 Plan 06: Server Hosting & PostgreSQL-Safety Guards Summary

Makes MyOriShop deployable and safe on an internet-facing PostgreSQL server without choosing the operator's VPS provider, plan size or domain. Two code-level landmines that only fire on a PostgreSQL deployment are closed — the SQLite `VACUUM INTO` startup backup is now guarded by an explicit dialect gate, and the session cookie's `Secure` flag is environment-driven — and a provider-agnostic `deploy/` directory ships a systemd unit, a Caddy reverse-proxy config, a nightly `pg_dump` timer and a full Ubuntu 24.04 runbook.

## What Was Built

**Task 1 — PostgreSQL-safety guards.** `app/services/backup.py::startup_backup()` gains an explicit `engine.dialect.name != "sqlite"` early return (mirroring the `app/db.py` idiom), placed after engine resolution and before any SQLite-specific work. Its comment names OQ-6 and explains the failure mode: `create_backup` issues `VACUUM INTO` (SQLite-only), and a PostgreSQL server currently survives boot only by accident (`settings.db_path` names an absent file); if that file ever exists the accident evaporates and `VACUUM INTO` would raise inside `lifespan`, crashing the server on boot. The three pre-existing skip conditions (flag off / file missing / DB empty) are untouched — this is an addition, not a rewrite. `app/config.py` declares `session_https_only: bool = False` (env `SESSION_HTTPS_ONLY`), and `app/main.py` replaces the hardcoded `https_only=False` on `SessionMiddleware` with `https_only=config_settings.session_https_only`. Two tests were appended to `tests/test_backup.py`.

**Task 2 — deploy/ artifacts.** A new top-level `deploy/` directory, none of it imported or executed by the app. `myorishop.service` runs as a non-root `User=myorishop`, loads `/etc/myorishop.env`, runs `ExecStartPre=… alembic upgrade head` (mirroring `run.bat`), binds uvicorn to `127.0.0.1:8000`, `Restart=always`, with comments forbidding a public/all-interfaces bind and a widened `--forwarded-allow-ips`. `Caddyfile` terminates TLS at the proxy, `reverse_proxy 127.0.0.1:8000`, `request_body { max_size 32MB }` as the twin of `app/routes/sync.py::MAX_PUSH_BYTES`, with the placeholder domain `shop.example.com` and nginx+certbot noted as the alternative. `myorishop-pgbackup.sh` (`set -euo pipefail`) runs `pg_dump -Fc` with 30-day retention, reading credentials from the libpq environment and never echoing them. `myorishop-pgbackup.service` (`Type=oneshot`) + `myorishop-pgbackup.timer` (`OnCalendar=daily`, `Persistent=true`).

**Task 3 — DEPLOY.md.** A 269-line provider-agnostic runbook (Russian prose, Latin commands) with all 13 sections in order: what-to-decide block, prerequisites, PostgreSQL 17 (localhost-only), app user + code, `/etc/myorishop.env` (the four env vars), migrations via `ExecStartPre`, systemd, reverse proxy + TLS, firewall 22/80/443, `pg_dump` backups, post-deploy checklist (including 401-without-token and 200-with-token sync verifications), the «Мобильный интерфейс — только на сервере» (SRV-04) section referencing `tests/test_sync_api.py::test_both_uis_one_app`, updating a running server (with the `0018` trigger-rewrite downgrade warning), and troubleshooting.

### Task-by-task

| Task | What | Commit |
|------|------|--------|
| 1 | Dialect gate in `startup_backup` + `session_https_only` setting + `SessionMiddleware` wiring + 2 tests | `6e23424` |
| 2 | Five `deploy/` operator artifacts (systemd unit, Caddyfile, pg_dump script + service + timer) | `cd0358f` |
| 3 | `deploy/DEPLOY.md` provider-agnostic runbook | `4f45c3d` |

## Key Decisions

- **The dialect is the real condition; the missing file is an accident.** The guard makes the PostgreSQL skip explicit and unconditional. `test_startup_backup_skips_non_sqlite_dialect` monkeypatches `settings.db_path` to an EXISTING file and passes a `postgresql+psycopg` engine (SQLAlchemy resolves the dialect without connecting, so no PG server is needed) — proving the guard, not the file-missing accident, returns None.
- **`session_https_only` defaults False.** A `Secure` cookie is not sent over plain HTTP, so a hardcoded `True` would break every local `run.bat` client and the entire test suite. It is set true only in the server's `/etc/myorishop.env`.
- **The cookie test asserts wiring, not a live flip.** `SessionMiddleware` reads `https_only` at registration time, so `test_session_cookie_secure_flag_follows_setting` asserts the constructed middleware option equals `settings.session_https_only` (and pins the default to False). This fails if `main.py` ever hardcodes a literal again. Limitation stated in the docstring.
- **`deploy/` chooses nothing for the operator.** No VPS provider, tier/plan name, real domain or public IP — only `127.0.0.1` and the placeholder `shop.example.com`. The "1 vCPU / 2 GB" resource shape is stated as sufficient without recommending a vendor (per plan action).

## Threat Mitigations Applied

| Threat ID | Mitigation | Where |
|-----------|-----------|-------|
| T-28-13 | `engine.dialect.name != "sqlite"` early return + `BACKUP_ON_STARTUP=false` on the server | `app/services/backup.py`, unit |
| T-28-27 | `session_https_only` wired into `SessionMiddleware`, true in `/etc/myorishop.env`, default False | `app/config.py`, `app/main.py` |
| T-28-05 | Caddy automatic HTTPS terminates TLS at the proxy; uvicorn binds `127.0.0.1`; no `0.0.0.0` anywhere under `deploy/` | `deploy/Caddyfile`, `deploy/myorishop.service` |
| T-28-11 | PostgreSQL bound to localhost + firewall 22/80/443 only, with a verification step | `deploy/DEPLOY.md` §2, §8 |
| T-28-28 | `EnvironmentFile` (chmod 600, never committed); placeholders only; pg_dump never echoes its connection string | `deploy/*` |
| T-28-04 | Proxy-side `max_size 32MB`, the twin of `MAX_PUSH_BYTES`, comment to move both together | `deploy/Caddyfile` |
| T-28-29 | `ExecStartPre=alembic upgrade head` makes a failed migration prevent service start | `deploy/myorishop.service` |
| T-28-30 | Daily `pg_dump` timer, `Persistent=true`, 30-day retention; off-box copy stated as operator's job | `deploy/myorishop-pgbackup.*` |
| T-28-31 | Unit keeps uvicorn's default `--forwarded-allow-ips`, comment never to widen it | `deploy/myorishop.service` |
| T-28-SC | Zero new Python packages; Caddy/PostgreSQL are OS packages installed by the operator | — |

## Deviations from Plan

None — plan executed as written. No Rule 1-4 deviations were required.

## Deferred Issues

Three pre-existing `ruff E501` (line-too-long) violations remain in files this plan did NOT touch (`app/routes/dictionary.py:73`, `app/routes/products.py:133`, `app/routes/transfers.py:64`). They pre-date this plan (already logged in `deferred-items.md` during Plan 28-03) and are out of scope per the SCOPE BOUNDARY rule. All files modified by this plan pass `uv run ruff check`.

## Verification

- `uv run pytest tests/test_backup.py -x -q` — 16 passed (includes the two new tests), green with no PostgreSQL server running.
- `uv run pytest -q` — full suite: 1078 passed, 11 skipped.
- `grep -c "https_only=False" app/main.py` → 0; `grep -c "https_only=config_settings.session_https_only" app/main.py` → 1.
- `grep -rc "0\.0\.0\.0" deploy/` → 0 for every file.
- `sh -n deploy/myorishop-pgbackup.sh` → exit 0.
- `uv run ruff check` on the four modified app/test files → all checks passed.
- `deploy/DEPLOY.md` → 269 lines (≥120), all 13 sections, four env vars, SRV-04 + `test_both_uis_one_app` reference, no provider/tier/real-domain/public-IP.

## Note for the Phase Gate

ROADMAP Success Criterion 1's hosting story is now written down and its server-only mobile constraint recorded, backed by the standing `test_both_uis_one_app` assertion from Plan 04. The phase-level `pg-parity` CI gate (migrations 0018/0019 on postgres:17) is independent of this plan — nothing here touches migrations or the engine.

## Self-Check: PASSED

All six `deploy/` + `28-06-SUMMARY.md` artifacts exist on disk, and all three task commits (`6e23424`, `cd0358f`, `4f45c3d`) are present in git history.
