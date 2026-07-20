# Phase 30: Offline Self-Uploading File - Pattern Map

**Mapped:** 2026-07-20
**Files analyzed:** 8 (5 NEW, 3 MODIFY)
**Analogs found:** 8 / 8 (all have a strong in-repo analog)

> Every path and analog below was confirmed against the live codebase this session.
> One naming correction from RESEARCH is upheld: the export collector is
> `sync_client._collect_push_records` (`app/services/sync_client.py:256`), **NOT**
> `collect_reference_records` (that symbol, `app/services/sync.py`, is the server-side
> pull pager — verified imported as such in `app/routes/sync.py:37-41`).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| NEW `app/routes/offline.py` | route (server ingest) | request-response / batch | `app/routes/sync.py` (`sync_push` :66-133) | exact (same thin-caller-of-`apply_merge` shape) |
| NEW `app/routes/offline.py` (export handler) | route (client export) | file-I/O / transform | `app/routes/export.py` :18-35 + `sync_client.run_sync_once` :334-360 | role-match |
| NEW `app/services/offline.py` (optional token/digest helpers) | service | transform | `app/services/auth.py` (fat-service crypto) + RESEARCH Pattern 2 | role-match |
| MODIFY `app/services/merge.py` `serialize_exchange` | service | transform | itself :527-560 (additive `payload_sha256` header field) | exact (self) |
| MODIFY `app/services/security.py` `auth_guard` | middleware | request-response | `SYNC_PATH_PREFIX` bypass :52,164 | exact (self, mirror branch) |
| MODIFY `app/services/sync_client.py` `_collect_push_records`→public | service | CRUD/transform | itself :256-331 (promote to public) | exact (self) |
| NEW `app/templates/offline/self_upload.html` | component (standalone) | request-response | `app/templates/auth_base.html` (head/shell) + `pages/login.html` (form idiom) | role-match (inline-replicated CSS — no `<link>`) |
| NEW `app/templates/offline/result.html` | component (server page) | request-response | `app/templates/auth_base.html` (no-session shell) | role-match |
| S3 export CTA in `app/templates/pages/export.html` | component | request-response | `app/templates/pages/export.html` (existing CSV button idiom) | exact (self) |
| NEW `tests/test_offline.py` | test | request-response | `tests/test_sync_api.py` (+ `anon_client` fixture) | exact |

## Pattern Assignments

### `app/routes/offline.py` — ingest route (route, request-response/batch)

**Analog:** `app/routes/sync.py` (`sync_push`, lines 66-133 — read in full)

**Module docstring + RU-constant + size-cap idiom to copy** (`sync.py:1-19, 50-63`):
- Fixed RU error constants, HTML-free, never echo submitted bytes (`sync.py:50-54`).
- `MAX_PUSH_BYTES = 32 * 1024 * 1024` belt-and-braces cap (`sync.py:61`) → clone as `MAX_OFFLINE_BYTES`.
- `router = APIRouter()` (`sync.py:63`); wired in `main.py` with `include_router(...)` and **NO** `dependencies=` (per-route gating).

**The all-or-nothing transaction — copy verbatim** (`sync.py:106-122`):
```python
lines = text.splitlines()          # canonicalizes CRLF -> logical lines (Pitfall 1)
try:
    batch = parse_exchange(lines)  # validates before any DB touch; format_version reject
except ValueError as exc:
    raise HTTPException(status_code=400, detail=MALFORMED_BATCH_ERROR) from exc
# The route owns the ONE transaction: apply_merge never commits.
session.rollback()
with session.begin():
    report = apply_merge(session, batch, server_now=utcnow_iso())
```
> For OFF-07, insert the SHA-256 digest check and the `current_schema_version(session)`
> equality gate (D-09) BETWEEN `splitlines()` and `parse_exchange` — at the route
> layer, never inside `parse_exchange` (keeps its purity + round-trip tests intact).
> D-01 diverges from `sync_push`'s JSON return: render an HTML result page instead
> (see `result.html` below), not a plain dict.

**Imports to reuse verbatim** (`sync.py:28-48`): `from app.core import utcnow_iso`,
`from app.services.merge import apply_merge, parse_exchange, serialize_exchange`,
`from app.services.rate_limit import check_rate_limit`,
`from app.services.sync import current_schema_version`, `from app.routes import templates`.
Do **NOT** import `require_device` (wrong auth model, D-03).

### `app/routes/offline.py` — `POST /api/offline/login` (route, request-response)

**Analog:** `app/routes/auth.py` `login_submit` :51-79 + `sync.py` rate-limit idiom :84-86

**Credential-check idiom to mirror** (`auth.py:58-79`):
```python
login = login.strip()
user = session.scalar(select(User).where(User.login == login))
if user is not None and verify_password(session, user, password):
    if user.is_active != 1:
        ...  # deactivated branch
    ...  # success
# generic BAD_CREDENTIALS_ERROR — same message for unknown login + wrong password
```
- Reuse `BAD_CREDENTIALS_ERROR = "Неверный логин или пароль."` verbatim (`auth.py:31`) —
  no user-enumeration oracle (V2). UI-SPEC appends "Данные не отправлены." in the file's JS.
- Rate-limit gate (`sync.py:84-86` pattern): `if not check_rate_limit(f"offline-login:{login}"): -> 429`.
- On success mint the `itsdangerous` token; return `JSONResponse` with the single narrow
  CORS header `Access-Control-Allow-Origin: *` (NO `Allow-Credentials`) — scoped to this
  route only (D-05, Pitfall 4). On failure: 401 + same CORS header, **no token, no data**.

### `app/routes/offline.py` — `GET /offline/export` (route, file-I/O)

**Analog:** `app/routes/export.py` :18-35 (session-guarded page/download idiom) +
`sync_client.run_sync_once` :351-360 (the collect→serialize pipeline)

**Collect + serialize pipeline to copy** (`sync_client.py:351-360`):
```python
records, ids = _collect_push_records(session)   # promote to public collect_push_records
body = "\n".join(
    merge.serialize_exchange(
        records,
        schema_version=current_schema_version(session),
        source_device_id=settings.device_id,
        generated_at=utcnow_iso(),
    )
)
```
> Ignore `ids` (D-07 — never stamp `synced_at` on export). Render `self_upload.html`
> with `body` embedded and `Content-Disposition: attachment`. This route is NOT under
> `/api/offline/` — keep it session-guarded (mirror `/sync/run` which stays behind
> `auth_guard`, `sync.py:208-213`). Refuse with an RU `.error-block` when
> `settings.sync_server_url == ""` (Pitfall 5; `config.py:56`).

### `app/services/merge.py` `serialize_exchange` (service, transform) — MODIFY

**Analog:** itself, lines 527-560 (read in full). Minimal additive change:
```python
materialized = list(records)
counts: dict[str, int] = {}
for record in materialized:
    counts[record.kind] = counts.get(record.kind, 0) + 1
record_lines = [json.dumps({"kind": r.kind, **r.data}, ensure_ascii=False) for r in materialized]
payload_sha256 = hashlib.sha256("\n".join(record_lines).encode("utf-8")).hexdigest()  # NEW (D-08)
header = {
    "kind": "header", "format_version": FORMAT_VERSION, "schema_version": schema_version,
    "source_device_id": source_device_id, "generated_at": generated_at,
    "counts": counts, "payload_sha256": payload_sha256,  # NEW
}
yield json.dumps(header, ensure_ascii=False)
yield from record_lines
```
> Digest over **record lines only**, LF-joined (matches the route's `"\n".join(splitlines()[1:])`
> canonicalization — Pitfall 1). Adding a header key is safe: `parse_exchange` ignores
> unknown header keys, round-trip tests assert on `.records` not the header, and the
> online push route ignores it. Add `import hashlib` at module top.

### `app/services/security.py` `auth_guard` (middleware) — MODIFY

**Analog:** the `SYNC_PATH_PREFIX` branch, lines 52 (constant) + 164 (branch)
```python
# beside SYNC_PATH_PREFIX (line 52):
OFFLINE_PATH_PREFIX = "/api/offline/"   # ingest endpoints ONLY; NOT the /offline/export page
# inside auth_guard, right after the SYNC_PATH_PREFIX branch (line 164-165):
if request.url.path.startswith(OFFLINE_PATH_PREFIX):   # in-body auth; no session/CSRF
    return
```
> **Exact-prefix pitfall (Pitfall 3):** the prefix is `/api/offline/`, never a shortened
> `/api/`. The `/offline/export` client page is deliberately NOT under this prefix — it
> stays session-guarded, exactly as `/sync/run` does. CSRF is deliberately skipped for
> these routes (in-body token auth, no cookies — same reasoning as the Bearer sync tree,
> `security.py:150-159`).

### `app/services/sync_client.py` `_collect_push_records` → public (service) — MODIFY

**Analog:** itself, lines 256-331 (read in full). Promote the private
`_collect_push_records` to a public `collect_push_records` (or add a thin public wrapper)
and update its one internal call site (`run_sync_once` :351) so the offline export and
the online push share ONE collector (SYNC-04 — never two divergent implementations).
No behavior change; the FK-closure walk (op→product/batch/sale, cash→sale, sale→customer,
batch→product/warehouse in `merge._REFERENCE_INSERT_ORDER`) is reused verbatim.

### `app/templates/offline/self_upload.html` (standalone component) — NEW

**Analog:** `app/templates/auth_base.html` (head + `mobile-shell` no-nav shell) +
`app/templates/pages/login.html` (login form idiom)

- Copy the `<head>` shape from `auth_base.html:1-16` BUT **inline all CSS** — no
  `<link rel="stylesheet">`, no CDN, no web-font (OFF-03 self-containment). Inline-replicate
  the exact token table from UI-SPEC §S1 (matches `app/static/style.css`).
- Embed NDJSON via `<script type="application/x-ndjson">{{ embedded | safe }}</script>`
  after `embedded = ndjson_text.replace("</script", "<\\/script")` (Pitfall 2/6).
- Plain inline vanilla JS only (no HTMX/JS lib): read `textContent` → reverse escape →
  parse header → render preview counts (OFF-06/D-10) → `fetch` login → reveal confirm →
  top-level `<form method="post" enctype="multipart/form-data" action="{{ server_url }}/api/offline/upload">`.
- `lang="ru"`, charset utf-8, viewport meta (mirror `auth_base.html` head).

### `app/templates/offline/result.html` (server page component) — NEW

**Analog:** `app/templates/auth_base.html` (no-session shell — `mobile-shell`, `/static/style.css`, NO `<nav>`)
- One `h1` + one body block per state (success `.muted` / three rejections `.error-block`),
  RU copy locked in UI-SPEC §S2. Never interpolate raw uploaded bytes except the two
  version strings in the incompatible message (autoescaped, never `| safe`) —
  mirror `sync.py` fixed-constant errors (T-28-07).

### S3 export CTA in `app/templates/pages/export.html` — MODIFY

**Analog:** the existing CSV-export button idiom in `pages/export.html`.
`<a class="button" href="/offline/export">Экспортировать офлайн-файл</a>` + `.muted` helper
(UI-SPEC §S3). Optional read-only hint MUST be plain `.muted` text, never the amber badge,
never reading/writing `synced_at` (D-07).

### `tests/test_offline.py` (test) — NEW

**Analog:** `tests/test_sync_api.py` (read :1-80) + `conftest.py` `anon_client` :191
- Build on `anon_client` (REAL `auth_guard`, so the `/api/offline/` bypass is genuinely
  exercised) — NOT the wholesale-override `client` fixture (`conftest.py:133` overrides the
  guard and would make the bypass untestable — see `test_sync_api.py:1-19` rationale).
- Reuse `_fresh_buckets` autouse fixture (`test_sync_api.py:42-47`) for the rate-limit test.
- Reuse the NDJSON-body factory shape (`test_sync_api.py:50-80`), extended to compute a
  correct `payload_sha256` header. Mirror `test_push_idempotent` (OFF-05a) and
  `test_push_all_or_nothing` (OFF-05b).
- Add a helper to mint an offline token directly via the serializer + `settings.secret_key`
  (skip the login step) plus an expired-token variant.

## Shared Patterns

### All-or-nothing owned transaction
**Source:** `app/routes/sync.py:120-122`
**Apply to:** `POST /api/offline/upload`
```python
session.rollback()
with session.begin():
    report = apply_merge(session, batch, server_now=utcnow_iso())
```

### Fixed RU error constants, never echo attacker bytes (V7 / T-28-07)
**Source:** `app/routes/sync.py:50-54`, `app/routes/auth.py:31`
**Apply to:** every offline route + both result-page rejection states
Reuse `BAD_CREDENTIALS_ERROR` verbatim; locked D-08/D-09 wording for corrupted/incompatible.

### Rate limiting
**Source:** `app/services/rate_limit.py` `check_rate_limit` (used at `sync.py:84-86`)
**Apply to:** `POST /api/offline/login`

### Password verification (Argon2id)
**Source:** `app/services/auth.py` `verify_password` :37-52
**Apply to:** `POST /api/offline/login`

### itsdangerous short-lived upload token (D-03, new — no in-repo analog)
**Source:** `settings.secret_key` (`app/config.py:35,86-87`) + RESEARCH Pattern 2 (executed/verified)
```python
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
_signer = URLSafeTimedSerializer(settings.secret_key, salt="offline-upload")
# mint: _signer.dumps({"scope": "offline_upload", "sub": user_id})
# verify: _signer.loads(token, max_age=OFFLINE_TOKEN_TTL); assert scope
```
Never compare the token with a bare `==` — use the serializer's own HMAC-timed verify.

### Router wiring
**Source:** `app/main.py:219` (`app.include_router(sync.router)`)
**Apply to:** add `app.include_router(offline.router)` with NO app-level `dependencies=`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| itsdangerous upload-token minter | service | transform | No signed-token minter exists yet; `settings.secret_key` + RESEARCH Pattern 2 is the reference (no in-repo code analog — the session cookie is signed by Starlette middleware, not app code). |
| Self-uploading standalone HTML + inline vanilla JS | component | request-response | No standalone (linkless, inline-CSS, embedded-data) template exists; every current template extends `base`/`auth_base`/`mobile_base` and links `/static/style.css`. Use UI-SPEC §S1 inline-token table. |

## Metadata

**Analog search scope:** `app/routes/`, `app/services/`, `app/templates/`, `tests/`, `app/config.py`, `app/main.py`
**Files scanned (read in full or targeted):** `sync.py`, `security.py`, `merge.py` (serialize section), `sync_client.py` (collector+driver), `auth.py`, `routes/auth.py`, `export.py`, `test_sync_api.py`, `conftest.py` (fixtures), `auth_base.html`, `config.py`, `main.py`
**Pattern extraction date:** 2026-07-20
