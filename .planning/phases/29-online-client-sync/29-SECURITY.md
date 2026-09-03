---
phase: 29
slug: online-client-sync
status: verified
threats_open: 0
asvs_level: 1
created: 2026-09-03
---

# Phase 29 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Verification mode: **State B — verify declared mitigations against implemented code.**
> Register authored at plan time (`<threat_model>` blocks in 29-01..29-05-PLAN.md).
> Every row below was proven by reading the cited file:line — no plan/summary claim
> was accepted as evidence.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Local client → central server (`/api/sync/push`, `/api/sync/pull`) | Outbound HTTP driver `sync_client.run_sync_once` over the public internet | Ledger NDJSON (operations, cash movements, FK-closure reference rows) + `Authorization: Bearer <sync_token>` |
| Server response → local DB | Pulled NDJSON pages applied to the local SQLite DB | Untrusted server/attacker-controlled bytes → `merge.parse_exchange` → owned transaction |
| Browser → app (`POST /sync/run`) | Session-authenticated operator trigger | CSRF token + no user payload |
| Browser → app (`POST /settings/sync`) | Admin-only auto-sync config write | `auto_enabled`, `auto_interval_seconds` (clamped) |
| `.env` → process | Secret material resolution | `sync_token` (secret), `sync_server_url` (non-secret) |
| Background loop → threadpool | Lifespan `_auto_sync_loop` → `anyio.to_thread.run_sync(run_sync_tick)` | Own `SessionLocal()` session, shared `_run_lock` |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-29-01 | Information Disclosure | `sync_token` storage | mitigate | `.env`-only pydantic field, default `""`; **not** a DB column; never logged | closed |
| T-29-02 | Tampering | migration 0020 portability | mitigate | `sa.String`/`sa.Integer` only, no server defaults, dual `sqlite_where`+`postgresql_where`; proven on PostgreSQL in CI | closed |
| T-29-03 | Denial of Service | unsynced badge query cost | mitigate | `synced_at IS NULL` partial indexes in both model and migration | closed |
| T-29-04 | Information Disclosure | Bearer token transmission | mitigate | Token only in the `Authorization` header; query params limited to `since`/`after_id`; no logging in the module | closed |
| T-29-05 | Tampering | malicious/garbled pull response | mitigate | `merge.parse_exchange` validates the whole page before any DB touch; page applied in one owned `session.begin()` | closed |
| T-29-06 | Tampering (integrity) | failed push falsely marked synced | mitigate | `synced_at` stamped ONLY after `raise_for_status()`; sole `synced_at` writer in the app | closed |
| T-29-07 | Information Disclosure | rendered status / `/sync/run` HTML / Settings | mitigate | Only locked D-12 RU strings + integer counts reach templates; `sync_token` never in a context dict or template | closed |
| T-29-08 | Tampering (integrity) | `record_sync_result` persistence | mitigate | Single recording point per caller, reached after every network attempt (success or caught failure) | closed |
| T-29-09 | Denial of Service | badge COUNT on large history | mitigate | `unsynced_count` predicates match the two partial indexes | closed |
| T-29-10 | DoS / availability | unreachable server hangs app / loop stalls app | mitigate | Strict `httpx.Timeout`; httpx + non-httpx errors caught (WR-01); handler always 200; `anyio.to_thread.run_sync(..., abandon_on_cancel=False)` (WR-03); tick errors swallowed | closed |
| T-29-11 | Tampering | plain-HTTP push over the internet | mitigate → **accepted residual** | `https://` default URL + server-side TLS termination; **scheme is NOT enforced in code** — see AR-29-01 | closed (residual accepted) |
| T-29-12 | Elevation / concurrency | manual click + tick double-sync | mitigate | Module-level `threading.Lock`, non-blocking acquire in **both** (and only) callers, released in `finally` | closed |
| T-29-13 | Spoofing / Access Control | `/sync/run` and `POST /settings/sync` exposure | mitigate | `/sync/run` is outside `SYNC_PATH_PREFIX` → `auth_guard` session + CSRF applies; settings router mounted with `require_role("administrator")` | closed |
| T-29-14 | Denial of Service | too-frequent interval | mitigate | Server-side `_clamp_interval` (60..3600) inside `save_autosync_config`; unparseable input → 300 s | closed |
| T-29-SC | Tampering (supply chain) | httpx runtime promotion | accept | Verified pure section move; zero new packages — see AR-29-02 | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Evidence

| Threat ID | Evidence (file:line) |
|-----------|----------------------|
| T-29-01 | `app/config.py:58-75` — `sync_token: str = ""` on `Settings` whose `model_config` env_file is `_DATA_DIR/.env` (`app/config.py:30-32`). `app/models.py:640-653` — `SyncState` columns are `id/last_sync_at/last_status/last_result/auto_enabled/auto_interval_seconds`; **no token column** (rationale `app/models.py:634-637`). Repo-wide grep for `sync_token`/`SYNC_TOKEN` returns only `app/config.py`, `app/services/sync_client.py:355,368,544`, `app/routes/sync.py:255`, docstrings and tests — never a template, never a log call. `app/services/sync_client.py` contains **no** `print(`/`logging`/`logger`/`traceback` (grep: no matches). Regression: `tests/test_autosync.py:250-258` (`test_web_settings_never_renders_token`) — PASSED locally. |
| T-29-02 | `alembic/versions/0020_sync_state_and_unsynced_indexes.py:43-66` — `sa.Integer()`/`sa.String(n)` only, no `server_default`, no dialect SQL; partial predicate given via BOTH `sqlite_where` and `postgresql_where` (lines 57-58, 64-65). Proof test `tests/test_pg_parity.py:342-375` (`to_regclass('sync_state')` + `pg_indexes` for both index names, bound params only). **Executed evidence:** CI run `29906722138` (commit `0c0a27dc`, 2026-07-22) job "PostgreSQL portability & append-only parity (SRV-01/SRV-02)" = **success**, and `git merge-base --is-ancestor 9335b6b 0c0a27dc` confirms migration 0020 was present in that commit; the job's `DATABASE_URL` step runs `pytest tests/test_pg_parity.py -x` against `postgres:17` (`.github/workflows/ci.yml:16,42-43`). |
| T-29-03 | `app/models.py:360-365` (`ix_operations_unsynced`) and `app/models.py:510-515` (`ix_cash_movements_unsynced`) — declared in the model so `create_all` builds them too; `alembic/versions/0020_...py:53-66` for migrated DBs. |
| T-29-04 | `app/services/sync_client.py:242-248` — `build_sync_client()` builds the client with base_url+timeout and deliberately does NOT bake the token in. Token appears only as `{"Authorization": f"Bearer {settings.sync_token}"}` at `:368` (push) and `:544` (pull). Pull query params are restricted to `since`/`after_id` at `:546-551` — the token can never reach a query string. No logging in the module. |
| T-29-05 | `app/services/sync_client.py:553` — `merge.parse_exchange(response.text.splitlines())` runs BEFORE `:556` `with session.begin(): _apply_pull_page(...)`. `app/services/merge.py:139-214` — `parse_exchange` is pure (no DB/file/network) and raises `ValueError` on malformed NDJSON, non-object line, missing/duplicate header, unsupported `format_version`, unknown kind, missing/empty id, intra-batch duplicate origin id, missing ledger provenance, non-int `seq`, and non-int money (bool excluded explicitly). A page failure rolls back via the owned `session.begin()` and is downgraded to `partial` at `:401-410`. |
| T-29-06 | `app/services/sync_client.py:376` `response.raise_for_status()` → `:384-393` the `update(...).values(synced_at=stamp)`. Non-2xx returns before the stamp (`:377-379`), transport error likewise (`:380-382`). Repo-wide grep `synced_at=` in `app/` yields exactly ONE writer: `app/services/sync_client.py:390`. Regression `tests/test_sync_client.py:329` (`test_push_failure_does_not_stamp`) — PASSED locally. |
| T-29-07 | `app/services/sync_client.py:172-216` — `format_sync_message` selects from six hardcoded RU strings, interpolating only `int` counts and `iso_to_local(...)`. `app/routes/sync.py:217-233` — `_render_sync_status` passes only `sync_message`/`last_sync_line`/`unsynced` into the template. `app/templates/partials/sync_status.html:15-16` — renders only those three (Jinja autoescape on). `app/routes/__init__.py:150-181` — context processor renders `row.last_result`, which is only ever written by `record_sync_result` from a `format_sync_message` output (`app/routes/sync.py:274-280`, `app/services/sync_client.py:600-606`); any error collapses to a neutral default (`:174-181`), never exception text. `app/services/settings.py:35-47` — `settings_summary` returns `sync_server_url` but no token. `app/templates/pages/settings.html:37-40` — read-only `sync_server_url` input; grep for `sync` in that template shows no token field. Regression `tests/test_autosync.py:250-258` — PASSED. |
| T-29-08 | `app/routes/sync.py:275-281` and `app/services/sync_client.py:601-606` — both callers record the result and commit after every network attempt; both wrap the driver in `except Exception` first (`app/routes/sync.py:263-264`, `app/services/sync_client.py:586-593`), so no exception path can bypass the write. Regression `tests/test_sync_client.py:129-142` (`test_record_sync_result_writes_on_error`) and `:107` (persists across restart) — PASSED. **Honest note:** the write is not literally inside a `finally` as D-10 phrased it; the equivalent guarantee holds because every driver exception is caught before the recording line. `locked` and `not_configured` deliberately do not write (no attempt occurred; writing on `locked` would clobber the in-flight run's state). |
| T-29-09 | `app/services/sync_client.py:146-169` — `unsynced_count` issues `COUNT(*) ... WHERE synced_at IS NULL` on `Operation` and `CashMovement`, matching the partial-index predicates cited in T-29-03 exactly. |
| T-29-10 | `app/services/sync_client.py:233` `SYNC_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)` applied at `:248`. Push errors caught at `:377-382`; pull `httpx.HTTPError` at `:399-400`; **WR-01 fix present** at `:401-410` (`except Exception` → rollback → `partial`, so a poisoned page's `ValueError`/`IntegrityError` never escapes). `app/routes/sync.py:236-284` always returns an `HTMLResponse` (no raise; broad guard at `:263-264`). `app/main.py:97-99` — **WR-03 fix present**: `anyio.to_thread.run_sync(sync_client.run_sync_tick, abandon_on_cancel=False)`; `app/main.py:100-102` swallows any iteration error so the loop never dies; `app/main.py:156-161` cancels the task cleanly on shutdown; `app/services/sync_client.py:607-618` guards the tick's final commit against engine teardown. Regressions `tests/test_sync_client.py:491` (offline not raised), `:505` (push-ok/pull-fail = partial), `:586` (tick swallows offline), `tests/test_autosync.py:71` (iteration swallows tick exception), `:93` (lifespan starts/cancels cleanly) — all PASSED. |
| T-29-11 | `app/config.py:74` — `sync_server_url: str = "https://ori.viktorplus.com"` (https by default; comment at `:59-60` states the https form). Server-side TLS: `deploy/Caddyfile:1-28` (automatic HTTPS, TLS terminates at the proxy) and `deploy/DEPLOY.md:155-169`. **No scheme validation exists anywhere** — grep of `app/config.py` / `app/services/sync_client.py` finds no `startswith("https")` / URL-scheme check, so an operator-supplied `SYNC_SERVER_URL=http://…` in `.env` would send the Bearer token in cleartext. Additionally `.env.example` (whole file read) documents neither `SYNC_SERVER_URL` nor `SYNC_TOKEN`, and `docs/INSTALL-RU.md` contains no `sync`/`https` guidance. Classified as an accepted residual: **AR-29-01**. |
| T-29-12 | `app/services/sync_client.py:228` `_run_lock = threading.Lock()`. Repo-wide grep for `run_sync_once` callers in `app/` returns exactly two: `app/routes/sync.py:262` (guarded by `:250` `acquire(blocking=False)`, released `:284` in `finally`) and `app/services/sync_client.py:585` (guarded by `:576`, released `:620` in `finally`). No third entry point exists. `locked` renders the fixed RU partial (`app/routes/sync.py:251`, string at `app/services/sync_client.py:203`). Regression `tests/test_sync_client.py:345` (`test_single_run_lock_refuses_overlap`) — PASSED. |
| T-29-13 | `app/services/security.py:63` `SYNC_PATH_PREFIX = "/api/sync/"`; `app/services/security.py:191-206` — `auth_guard` returns early only for exact `PUBLIC_PATHS` (`:41-50`, does not contain `/sync/run`), the `/api/sync/` prefix and the `/api/offline/` prefix. `"/sync/run"` matches none of them, so it falls through to the first-run check, the session check (`:199-203`) and the CSRF check for non-safe methods (`:204-205`). CSRF token is carried by `app/templates/base.html:35` (`hx-headers='{"X-CSRF-Token": "..."}'`) and the trigger at `:76` is an `hx-post`. `app/main.py:172` mounts `auth_guard` as an app-level dependency. `POST /settings/sync` is declared at `app/routes/settings.py:43-44` on the settings router, which `app/main.py:240-242` includes with `dependencies=[Depends(require_role("administrator"))]` (`app/services/security.py:210-227`). |
| T-29-14 | `app/services/settings.py:63` — `row.auto_interval_seconds = _clamp_interval(interval_seconds)` inside `save_autosync_config`, i.e. **server-side**, not an HTML attribute. `app/services/sync_client.py:122-133` — `_clamp_interval` = `max(60, min(3600, int(value)))` with `DEFAULT_INTERVAL_SECONDS` (300) on `None`/unparseable. `app/routes/settings.py:59-63` additionally falls back to 300 on a non-int form value. `app/services/sync_client.py:136-143` re-clamps on read. Regressions `tests/test_autosync.py:144` (clamps low), `:155` (clamps high), `:205` (web POST clamps out-of-range), `:219` (unparseable → default) — all PASSED. |
| T-29-SC | `git show 54ff30c -- pyproject.toml` — `httpx==0.28.*` moved from `[dependency-groups].dev` into `[project].dependencies`, a pure section move; `uv.lock` diff in the same commit is `1 file changed, 2 insertions(+), 2 deletions(-)` with **zero** added/removed `name = ` entries (no package added or removed). `pyproject.toml:5-19` current state. `git log --name-only 54ff30c~1..bcc640b` shows `pyproject.toml`/`uv.lock` touched by that one commit only in the whole phase. Recorded as **AR-29-02**. |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-29-01 | T-29-11 | **Plain-HTTP sync URL is not code-enforced.** The only controls are the `https://…` default in `app/config.py:74` and server-side TLS termination (`deploy/Caddyfile`, `deploy/DEPLOY.md:155-169`). No scheme validation exists, so an operator who edits `.env` to `SYNC_SERVER_URL=http://…` transmits the Bearer `sync_token` and the full ledger in cleartext. Accepted for ASVS L1 / a 1-3 device single-reseller deployment where the URL ships pre-baked and is not normally edited. **Documentation gap noted:** `.env.example` documents neither `SYNC_SERVER_URL` nor `SYNC_TOKEN`, and `docs/INSTALL-RU.md` has no sync/HTTPS guidance — the "documented operational requirement" claimed by the plan exists only in source comments and planning artifacts. Recommended (doc-only, non-blocking): add both keys to `.env.example` with an explicit "must be `https://`" note; optional hardening: reject a non-https `sync_server_url` unless the host is localhost. | gsd-security-auditor (phase 29 audit) | 2026-09-03 |
| AR-29-02 | T-29-SC | **httpx runtime promotion accepted.** Verified as a pure `pyproject.toml` section move with a 2-line `uv.lock` diff and no added package names; `httpx==0.28.*` was already vetted and pinned in this repo. No new runtime dependency entered the tree during phase 29. | gsd-security-auditor (phase 29 audit) | 2026-09-03 |

---

## Unregistered Flags

| Flag | Source | Assessment |
|------|--------|------------|
| none | `## Threat Flags` in 29-03/04/05-SUMMARY.md all read "None" | Independently checked: the phase's new externally reachable surface is exactly `POST /sync/run` (T-29-13) and `POST /settings/sync` (T-29-13/14) plus the outbound driver (T-29-04/05/06/10/11) — all registered. |
| *process note* | 29-01-SUMMARY.md has **no** `## Threat Flags` section (29-02 uses `## Threat Model Compliance` instead) | Informational only, not new attack surface. 29-01's actual surface (two `Settings` fields, one migration, one model) is fully covered by T-29-01/02/03/SC, each verified above. |

---

## Non-Blocking Observations

| ID | Observation |
|----|-------------|
| IN-29-A | `.env.example` lacks `SYNC_SERVER_URL` / `SYNC_TOKEN` entries entirely, so an operator has no guided place to set the sync credential and no stated HTTPS requirement. Doc-only; tracked under AR-29-01. |
| IN-29-B | 4 `tests/test_sync_ui.py` tests (`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`, `test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`) fail deterministically in a local combined run because `sync_client._run_lock` is still held by a lifespan-started auto-sync tick from an earlier test. Known pre-existing test-isolation race (see memory note "pre-existing sync_ui test failures"), **not** a production defect: both lock holders release in a `finally` (`app/routes/sync.py:284`, `app/services/sync_client.py:620`). It does not weaken T-29-12 — if anything it demonstrates the guard engaging. |
| IN-29-C | Current `main` CI is red, but the failure is `tests/test_launcher.py::test_parse_pending_rejects_path_traversal` (a Phase-31 packaging test on Linux path semantics) in the SQLite step, which aborts the job **before** the PostgreSQL steps run. The T-29-02 PG evidence therefore comes from the last fully green run `29906722138`, which post-dates migration 0020. Out of phase-29 scope; flagged so the PG parity proof is not silently assumed to be re-running today. |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-09-03 | 15 | 15 | 0 | gsd-security-auditor (State B — verify mitigations) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log (AR-29-01, AR-29-02)
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03
