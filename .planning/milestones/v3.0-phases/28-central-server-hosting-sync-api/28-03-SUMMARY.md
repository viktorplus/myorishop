---
phase: 28-central-server-hosting-sync-api
plan: 03
subsystem: sync
tags: [sync-api, device-token, bearer-auth, auth-guard-bypass, rate-limit, ndjson, thin-caller]
requires: [SYNC-09, DeviceToken, device-token-service, "0019"]
provides: [sync-push-endpoint, require-device-dependency, sync-path-bypass, rate-limiter]
affects: [app/services/security.py, app/routes, app/services, app/main.py, tests]
tech-stack:
  added: []
  patterns:
    - "narrowly-scoped auth_guard prefix bypass (/api/sync/) — PUBLIC_PATHS stays exact-match"
    - "HTTPBearer(auto_error=False) so the app owns the RU 401 message + WWW-Authenticate header"
    - "thin route: parse_exchange + apply_merge unchanged, route owns the ONE with session.begin()"
    - "stdlib token-bucket rate limiter keyed by non-secret token_prefix (no slowapi/Redis)"
    - "body cap enforced on BOTH Content-Length and len(payload)"
key-files:
  created:
    - app/services/rate_limit.py
    - app/routes/sync.py
    - tests/test_sync_api.py
  modified:
    - app/services/security.py
    - app/main.py
    - tests/conftest.py
    - pyproject.toml
decisions:
  - "require_device lives in app/services/security.py (beside require_role + the bypass it compensates for), NOT in devices.py as 28-RESEARCH sketched — a reviewer reading the bypass finds the gate in the same file, and devices.py stays FastAPI-free (grep-asserted 0 fastapi imports)"
  - "the route rolls back the read-only txn autobegun by the expire_on_commit reload of device.token_prefix before with session.begin() — a real production bug the tests caught, not a test artifact"
  - "ruff flake8-bugbear immutable-calls += fastapi.Security/Body so the FastAPI DI defaults pattern passes lint (mirrors the existing Depends/Form/Query entries)"
  - "both 401 details are indistinguishable unknown-vs-revoked (V7); no message reveals token state"
metrics:
  duration: ~23min
  tasks: 3
  files: 7
  completed: 2026-07-19
---

# Phase 28 Plan 03: Token-Authenticated Sync API (SYNC-09) Summary

The server's first internet-reachable, non-cookie POST surface: a narrowly-scoped `auth_guard` bypass for the `/api/sync/` prefix, a `require_device` Bearer dependency that gates that tree per-route, and `POST /api/sync/push` as a thin caller of the already-complete Phase 27 merge engine — body-capped, rate-limited, and owning exactly one all-or-nothing transaction.

## What Was Built

`auth_guard` now returns early for any path under `SYNC_PATH_PREFIX = "/api/sync/"` (a SEPARATE prefix-matched constant — `PUBLIC_PATHS` stays exact-match so a new sync path can never silently 303 to `/login`, and a bare `/api/` string appears nowhere, grep-asserted 0). The bypass sits immediately after the `PUBLIC_PATHS` check and BEFORE the user-count / session / CSRF checks: CSRF is deliberately inapplicable to a Bearer endpoint because a browser never auto-attaches an `Authorization` header (T-28-06).

`require_device` (in `security.py`, beside `require_role`) resolves a `Bearer` credential via `HTTPBearer(auto_error=False)`, calls `devices.lookup_active_token`, and on success `devices.touch_last_used`. A missing credential or a wrong/unknown/revoked token both raise `401` with `WWW-Authenticate: Bearer` and an RU message that does NOT distinguish unknown from revoked (V7).

`app/routes/sync.py::sync_push` is a plain `def` (threadpool, sync session) that reads the body via a `Body(...)` parameter. In order: rate-limit on the non-secret `token_prefix` (429), size-cap on both `Content-Length` and `len(payload)` (413), strict UTF-8 decode (400), `parse_exchange` outside the transaction (400, never echoing attacker bytes), then `with session.begin(): apply_merge(...)` — the route owns the ONE transaction, never commits, so a poisoned record rolls the whole batch back. `app/services/rate_limit.py` is a ~55-line stdlib token bucket (30 burst / 0.5 rps, thread-safe) — zero new packages.

### Task-by-task

| Task | What | Commit |
|------|------|--------|
| 1 | `SYNC_PATH_PREFIX` bypass + `require_device` Bearer gate + RU 401 constants; `device_client` fixture on the real guard | `dd5c797` |
| 2 | `rate_limit.py` token bucket + `routes/sync.py` push handler (thin caller, 413/429/400) + `main.py` wiring (no `dependencies=`) | `450549d` |
| 3 | `tests/test_sync_api.py` (12 tests) + Rule 1 transaction-rollback fix in the route | `7648dfc` |

## Key Decisions

- **`require_device` in `security.py`, not `devices.py`.** 28-RESEARCH.md sketched it inside `devices.py`, but placing it beside `require_role` and the `SYNC_PATH_PREFIX` bypass keeps the gate and the bypass it compensates for in one file for review, and keeps `devices.py` FastAPI-free (a pure, unit-testable service — `grep -Ec "^from fastapi|^import fastapi" app/services/devices.py` == 0). Recorded as a deviation.
- **Ruff immutable-calls extended.** Added `fastapi.Security` and `fastapi.Body` to `flake8-bugbear.extend-immutable-calls`, mirroring the existing `Depends`/`Form`/`Query` entries — FastAPI's DI pattern requires these calls in argument defaults.
- **Body cap belt-and-braces.** `MAX_PUSH_BYTES = 32 * 1024 * 1024` is checked against both the declared `Content-Length` (reject early) and the actual `len(payload)` (a missing/lying header cannot defeat it). The Caddy `request_body { max_size 32MB }` twin lands in Plan 06.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Route failed `with session.begin()` — "transaction already begun"**
- **Found during:** Task 3 (first `test_push_with_valid_token` run)
- **Issue:** `require_device` commits the `last_used_at` stamp via `touch_last_used`; with SQLAlchemy's default `expire_on_commit=True` that commit expires the `device` instance, so the handler's first line `check_rate_limit(device.token_prefix)` triggers a lazy reload — a SELECT that autobegins a read-only transaction. `with session.begin()` then raises `InvalidRequestError: A transaction is already begun`. This reproduces with a fresh per-request session too (verified standalone), so it is a genuine production bug, not a test artifact.
- **Fix:** the route captures `rate_key = device.token_prefix` first, then calls `session.rollback()` (a no-op if no txn is open) immediately before `with session.begin()`, so the merge opens the single owned write transaction cleanly.
- **Files modified:** `app/routes/sync.py`
- **Commit:** `7648dfc`

**2. [Rule 3 - Blocking] Pre-existing ruff import-order violation in `app/main.py`**
- **Found during:** Task 2 (acceptance gate `ruff check app/main.py` exit 0)
- **Issue:** `app/main.py` had a pre-existing isort violation (`from app.services.security` before the `from app.routes import (...)` block). Present at HEAD before any 28-03 change.
- **Fix:** applied `ruff check --fix` (safe import reorder, no behaviour change) since the plan required me to edit `main.py` and its acceptance gate demands it clean.
- **Files modified:** `app/main.py`
- **Commit:** `450549d`

### Out of Scope (logged, not fixed)

Three pre-existing `E501` (line-too-long) violations in `app/routes/dictionary.py:73`, `app/routes/products.py:133`, `app/routes/transfers.py:64` — confirmed present at HEAD, in routers untouched by this plan. The plan's verification step `uv run ruff check app` assumed a clean tree; these are logged in `deferred-items.md` rather than fixed (SCOPE BOUNDARY). All files this plan created or modified pass `ruff check` cleanly.

No architectural changes, no checkpoints, no auth gates, no new packages.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_sync_api.py -q` | **12 passed** |
| `uv run pytest tests/test_auth.py tests/test_roles.py -q` | 30 passed (bypass changed no existing route) |
| `uv run pytest -q` (full SQLite suite) | **1055 passed, 11 skipped** (was 1043 before this plan) |
| `grep -c '"/api/"' app/services/security.py` | 0 (no bare `/api/` string) |
| `grep -n 'startswith(SYNC_PATH_PREFIX)' app/services/security.py` | present, after `PUBLIC_PATHS`, before `count_users` |
| `grep -Ec "^from fastapi\|^import fastapi" app/services/devices.py` | 0 (devices.py stays FastAPI-free) |
| `grep -c "async def" app/routes/sync.py` | 0 |
| `grep -c "session.commit()" app/routes/sync.py` | 0 |
| `grep -c "with session.begin()" app/routes/sync.py` | 1 |
| `grep -Ec "print\(\|logging\|logger" app/routes/sync.py` | 0 (T-28-07) |
| `ruff check app/routes/sync.py app/services/rate_limit.py app/services/security.py app/main.py tests/test_sync_api.py tests/conftest.py` | clean |

## Success Criteria

- [x] ROADMAP SC-2: valid per-device token → `/api/sync/push` 200 + MergeReport; no/invalid/revoked token → 401 (`test_push_with_valid_token`, `test_push_without_token_rejected`, `test_push_with_garbage_token_rejected`, `test_revoked_token_rejected`)
- [x] The bypass is exactly one prefix, `/api/sync/`, proven not to widen in either direction (`test_device_token_cannot_reach_html`, `test_session_cookie_cannot_reach_sync`)
- [x] Thin caller: no merge semantics, one transaction, all-or-nothing rollback (`test_push_idempotent`, `test_push_all_or_nothing`)
- [x] Body size and request rate capped in the app itself (`test_push_rejects_oversized_body` 413, `test_push_rate_limited` 429)

## Threat Model Coverage

| Threat ID | Disposition | How covered |
|-----------|-------------|-------------|
| T-28-02 (missing/invalid token) | mitigate | `require_device` 401 + `WWW-Authenticate: Bearer`, RU message unknown≡revoked (V7); `test_push_without_token_rejected`, `test_push_with_garbage_token_rejected`, `test_revoked_token_rejected` |
| T-28-03 (over-broad bypass) | mitigate | separate `SYNC_PATH_PREFIX`, `PUBLIC_PATHS` stays exact-match, no bare `/api/` (grep 0); `test_device_token_cannot_reach_html`, `test_session_cookie_cannot_reach_sync` |
| T-28-04 (unbounded payload) | mitigate | `MAX_PUSH_BYTES` on Content-Length AND len(payload) → 413; `test_push_rejects_oversized_body` |
| T-28-12 (request flooding) | mitigate | stdlib token bucket on `token_prefix`, 30/0.5rps, thread-safe → 429; `test_push_rate_limited` |
| T-28-06 (CSRF on cookie UI) | mitigate | bypass returns before the session/CSRF checks — removes CSRF only for the Bearer tree; full suite green proves HTML CSRF tests still pass |
| T-28-07 (token/plaintext disclosure) | mitigate | Bearer header only, zero print/logging in sync.py (grep 0), parse errors return a fixed RU constant, never echo bytes; `test_push_rejects_malformed_ndjson` |
| T-28-19 (route weakening merge) | mitigate | `parse_exchange`/`apply_merge` unchanged, one `with session.begin()`, 0 `session.commit()`; `test_push_all_or_nothing` |
| T-28-09 (client author attribution) | accept | Phase 27 engine contract (DD-6), documented in the plan's `<threat_model>`; not owned here |
| T-28-SC (supply chain) | accept | zero new packages — rate limiter is stdlib only |

## Known Stubs

None.

## Threat Flags

None. The one new endpoint (`POST /api/sync/push`) and its trust boundaries are fully enumerated in the plan's `<threat_model>` and covered above. No new network surface, auth path, file access, or schema change beyond what the plan anticipated.

## Notes for Future Plans

- **Plan 05 (admin device UI)** surfaces mint/list/revoke at `/settings/devices` behind `require_role("administrator")`. The service (`devices.mint_token`/`list_device_tokens`/`revoke_token`) is already complete from Plan 02.
- **Plan 06 (Caddy)** must add the `request_body { max_size 32MB }` twin of `MAX_PUSH_BYTES` — the app cap is belt-and-braces, not the only line of defence.
- **A `GET /api/sync/pull`** (reference-data-down) will live under the same `/api/sync/` bypass and MUST also declare `Depends(require_device)` per-route — the bypass leaves the tree open at the guard level by design; the per-route dependency is the gate.
- The `session.rollback()` before `with session.begin()` in the push route is load-bearing: any future sync route that commits during dependency resolution (e.g. `touch_last_used`) and then opens its own transaction needs the same hygiene, because `expire_on_commit` autobegins a read txn on the next attribute access.

## Self-Check: PASSED

- FOUND: `app/services/rate_limit.py`
- FOUND: `app/routes/sync.py`
- FOUND: `tests/test_sync_api.py`
- FOUND: `app/services/security.py` (SYNC_PATH_PREFIX + require_device)
- FOUND: `app/main.py` (include_router(sync.router))
- FOUND: `tests/conftest.py` (device_client fixture)
- FOUND: commit `dd5c797`
- FOUND: commit `450549d`
- FOUND: commit `7648dfc`
