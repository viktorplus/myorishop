---
phase: 30
plan: 03
subsystem: offline-self-uploading-file
tags: [offline, ingest, routes, wave-2, integrity, schema-gate, cors]
requires:
  - merge.payload_digest / parse_exchange / apply_merge / MergeReport (app/services/merge.py)
  - offline.mint_offline_token / verify_offline_token / schema_version_ok / OFFLINE_TOKEN_TTL (app/services/offline.py)
  - sync.current_schema_version (app/services/sync.py)
  - security.OFFLINE_PATH_PREFIX auth_guard bypass (app/services/security.py)
  - auth.verify_password (app/services/auth.py)
  - rate_limit.check_rate_limit / SYNC_BUCKET_CAPACITY (app/services/rate_limit.py)
provides:
  - "POST /api/offline/login — creds -> short-lived upload token (OFF-04 / D-04)"
  - "POST /api/offline/upload — token + NDJSON -> integrity + schema gate -> all-or-nothing apply_merge (OFF-05 / OFF-07)"
  - app/routes/offline.py — router, MAX_OFFLINE_BYTES, BAD_CREDENTIALS_ERROR, RATE_LIMITED_ERROR, _ACAO, _result, current_schema_version (module attr)
  - app/templates/offline/result.html — S2 five-state no-session result page (D-01)
affects:
  - app/routes/offline.py (30-04 — adds GET /offline/export to the SAME module)
tech-stack:
  added: []
  patterns:
    - "thin ingest route mirrors sync_push; the ONLY additions are the SHA-256 digest check (D-08) + schema-version gate (D-09), both at the route layer BEFORE parse_exchange/apply_merge"
    - "in-body upload token (no cookie) => no CSRF surface (T-30-10); single narrow ACAO header scoped to /api/offline/login only, /api/sync/ CORS untouched (D-05)"
    - "route owns the ONE transaction via `with session.begin(): apply_merge(...)`; IntegrityError propagates so a poisoned record rolls the whole batch back (all-or-nothing, OFF-05)"
    - "CRLF-canonicalize via payload.splitlines() so a form-navigation body still verifies its LF-joined record digest (Pitfall 1)"
key-files:
  created:
    - app/templates/offline/result.html
  modified:
    - app/routes/offline.py
    - app/main.py
decisions:
  - "offline_login declares ONLY login+password (no data field) — literally satisfies OFF-04/D-04 'no data sent on failure'; one generic 401 for unknown login / wrong password / deactivated (no enumeration oracle)"
  - "gate order: token -> size cap -> splitlines -> integrity(D-08) -> schema(D-09) -> parse_exchange -> owned merge; every gate BEFORE any DB touch"
  - "current_schema_version imported as a module attribute so the incompatible-schema test can monkeypatch app.routes.offline.current_schema_version"
  - "total = operations_inserted + cash_inserted + sum(reference_inserted.values()) — reference_inserted is a dict[str,int], summed via .values()"
metrics:
  duration: ~20min
  tasks: 3
  files: 3
  completed: 2026-07-20
---

# Phase 30 Plan 03: Offline Ingest Routes Summary

Wave-2 server ingest: built `app/routes/offline.py` with the two-step handshake — `POST /api/offline/login` (creds → short-lived upload token, D-03/D-04) and `POST /api/offline/upload` (token → SHA-256 integrity + schema-version gate → the SAME Phase-27 `apply_merge` in one owned transaction, D-08/D-09/OFF-05) — plus the S2 five-state RU result page the offline operator lands on (D-01), and wired the router into `app/main.py`. The upload route is a near-verbatim mirror of `sync_push`; the only additions are the digest check and the schema gate, both at the route layer before the pure engine. All additive, zero new packages, no migration.

## What Was Built

**Task 1 — result page + module shell (commit 5926497):**
- `app/templates/offline/result.html`: standalone no-session shell mirroring `auth_base.html` (`<!doctype html>`, `lang="ru"`, charset, viewport, `/static/style.css`, `<main class="mobile-shell">`, NO `<nav>`, no htmx/hx-headers). One `h1` + one body block selected by a `state` variable across the five locked-copy states — `success` (`.muted` counts + idempotency reassurance), `wrong_password`, `corrupted` («Файл повреждён…»), `incompatible` (both `file_ver`/`server_ver` AUTOESCAPED, never `| safe`), `expired`.
- `app/routes/offline.py` shell: module docstring (thin caller of the Phase-27 engine, in-body token auth so no CSRF, never echo bytes), `router = APIRouter()`, `MAX_OFFLINE_BYTES = 32*1024*1024`, RU constants (`BAD_CREDENTIALS_ERROR`, `RATE_LIMITED_ERROR`), `_ACAO = {"Access-Control-Allow-Origin": "*"}`, and the private `_result(request, state, *, status=200, **ctx)` helper rendering `offline/result.html` via `templates.TemplateResponse`.

**Task 2 — POST /api/offline/login + router wiring (commit e4376d4):**
- `offline_login(login, password, session)` plain `def` declaring ONLY the two credential fields (no data field → OFF-04/D-04). Flow: strip login → `check_rate_limit(f"offline-login:{login}")` → 429 `_ACAO` on empty bucket (D-05/T-30-07) → look up `User` by login → generic 401 `_ACAO` (no token, no data) when user is None OR `verify_password` false OR `is_active != 1` (no enumeration oracle) → on success `mint_offline_token(user.id)` returned as `{"token": ...}` with the single `_ACAO` header (no Allow-Credentials).
- `app/main.py`: added `offline` to the route imports (alphabetical, before `products`) and `app.include_router(offline.router)` beside the sync router with NO `dependencies=` (the app-level guard already bypasses `/api/offline/`).

**Task 3 — POST /api/offline/upload (commit 68dfd45):**
- `offline_upload(request, token, payload, session)` plain `def`, gates strictly in order, ALL before any DB write: (1) `verify_offline_token` → `expired` 401 on `SignatureExpired`/`BadSignature`; (2) `len(payload.encode("utf-8")) > MAX_OFFLINE_BYTES` → `corrupted` 413; (3) `payload.splitlines()` canonicalize, empty → `corrupted` 400; (4) `json.loads(lines[0])` (JSONDecodeError or non-dict → `corrupted` 400), `payload_digest(lines[1:]) != header["payload_sha256"]` → `corrupted` 400 (D-08); (5) `current_schema_version(session)` + `schema_version_ok` → `incompatible` 409 naming both versions, empty-server skip (D-09); (6) `parse_exchange(lines)` → `corrupted` 400 on ValueError (enforces `format_version`); (7) `session.rollback(); with session.begin(): apply_merge(...)` — IntegrityError deliberately NOT swallowed (all-or-nothing), success renders `total = operations_inserted + cash_inserted + sum(reference_inserted.values())`.

## Verification

- `uv run pytest tests/test_offline.py::test_login_success_mints_token ...login... -x -q` → **3 passed** (Task 2 gate).
- `uv run pytest tests/test_offline.py tests/test_merge.py -q` → **50 passed, 3 failed** — the 3 failures are the `/offline/export`-dependent rows owned by 30-04 (`test_offline_bypass_is_narrow`, `test_export_html_contains_embedded_payload_and_form`, `test_script_tag_escaping_round_trip`), exactly as the plan's `<verification>` states ("export/self-upload rows still RED pending 30-04"). All login + upload rows are GREEN.
- `uv run pytest -q` (full suite) → **1139 passed, 12 skipped, 3 failed** — the same 3 pending-30-04 export rows; **zero regressions** in existing sync/auth/merge tests (the /api/sync/ CORS + guard are provably unchanged).
- Manual scope confirmation: the narrow `Access-Control-Allow-Origin` header lives only on `app/routes/offline.py` login responses; no `CORSMiddleware` was added to `app/main.py`, so the online-sync CORS posture is untouched (D-05).

## Deviations from Plan

### Auto-added functionality

**1. [Rule 2 - Missing validation] Non-dict header guard**
- **Found during:** Task 3
- **Issue:** The plan wraps `json.loads(lines[0])` in try/except → `corrupted`, but a syntactically-valid non-object header (e.g. a JSON list/number) would pass `json.loads` and then raise `AttributeError` on `header.get(...)`, surfacing as a 500 that echoes internal state — violating the "never echo bytes / fixed RU result" contract (T-28-07).
- **Fix:** Added `if not isinstance(header, dict): return _result(request, "corrupted", status=400)` immediately after the successful `json.loads`, so any malformed header shape lands on the same «Файл повреждён» page before any DB touch.
- **Files modified:** app/routes/offline.py
- **Commit:** 68dfd45

## Notes for Downstream Waves

- **30-04** adds `GET /offline/export` (session-guarded, NOT under `/api/offline/`) to the SAME `app/routes/offline.py` module — that route is what turns the last 3 RED tests green (the export page + the `test_offline_bypass_is_narrow` 303-vs-404 assertion). It consumes `sync_client.collect_push_records` + `merge.serialize_exchange` and embeds the NDJSON in a `<script type="application/x-ndjson">` block with `</script>` → `<\/script>` escaping, posting to `/api/offline/upload`.
- The result page expects `total`/`ops`/`cash` on `success` and `file_ver`/`server_ver` on `incompatible`; the export form's success navigation lands there via the upload route above.

## Self-Check: PASSED
