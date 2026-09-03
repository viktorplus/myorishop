# Phase 30: Offline Self-Uploading File - Research

**Researched:** 2026-07-20
**Domain:** Offline USB data transfer — self-contained HTML uploader, cross-origin form-POST ingest, SHA-256 integrity + schema-version gating, reuse of the Phase 27 idempotent merge engine
**Confidence:** HIGH (reuse surface fully read in-repo; itsdangerous API executed and verified). MEDIUM on browser transport mechanics (CRLF form normalization, CORS simple-request rules) — training knowledge, web search disabled this session, flagged in Assumptions Log.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Exported file is a **single self-contained HTML file** that **uploads itself via a `<form>` POST** (multipart) — chosen over `fetch()` to **avoid CORS entirely** for the bulk data path: a top-level form-submit is a browser navigation the server accepts cross-origin without a preflight, so the online-sync API's CORS posture is never loosened (no `Access-Control-Allow-Origin: null` on `/api/sync/`). Server responds by **rendering an HTML result page**. (Rejected: Option A `fetch()` needing a dedicated `ACAO: null` endpoint; Option C plain `.ndjson` + server-hosted uploader page.)
- **D-02:** Payload = the **existing NDJSON exchange format** (`serialize_exchange` output — one header line with `format_version` + `schema_version`, one record per line), **embedded in the HTML inside a non-executed `<script type="application/x-ndjson">` block** and read back via `textContent` (avoids base64 +33% bloat / JSON-escaping hazards). **Only** escaping: literal `</script>` → `<\/script>`. Bundle = the FK-closure of unsynced ledger rows, exactly as the Phase 29 push body (D-13): `product`, `customer`, `batch`, `sale` in FK order plus the `Operation` + `CashMovement` rows. Over-including reference rows is safe (idempotent insert-if-new).
- **D-03:** New `app/routes/offline.py` with a **dedicated endpoint pair** (NOT a reuse of `POST /api/sync/push` — wrong auth model): `POST /api/offline/login` (login + password → `verify_password` Argon2id → short-lived **upload-scoped** `itsdangerous` signed token) and `POST /api/offline/upload` (token + NDJSON → validate → merge).
- **D-04:** The **two-step handshake** literally satisfies OFF-04's "sends NO data on failure": credentials checked first; business data leaves the untrusted machine only after the server confirms the password. (Rejected: single-shot creds+payload; session cookie via `file://` `Origin: null`.)
- **D-05:** Auth is in the request body → **no CSRF/cookie machinery**. Add `/api/offline/` to the `auth_guard` bypass (mirror the exact-prefix `SYNC_PATH_PREFIX` pattern — beware the exact-prefix pitfall). A **single narrow CORS rule** for the offline routes (POST + form/JSON, **no** `Access-Control-Allow-Credentials`). Rate-limit `/api/offline/login` via `check_rate_limit`. The login token must be **short TTL** and **upload-scoped**.
- **OFF-05 (atomicity + idempotency):** no new logic — ingest through the **same `apply_merge`** (UUID insert-if-new = idempotency), wrapped in the identical **single owned transaction** `sync_push` uses (`session.rollback(); with session.begin(): apply_merge(...)`).
- **D-07:** **Do NOT stamp `synced_at` from the offline path.** The offline client cannot observe upload success; overriding constraint is *never lose data*. Under-marking is cheap (idempotent merge); over-marking loses data-visibility. The offline export **only reads**; `synced_at` is cleared **only by a future online sync**. **Known consequence (flag for planner + UAT):** a permanently-offline client's unsynced badge (SYNC-07) stays inflated indefinitely and re-exports re-include already-uploaded rows (harmless, larger files). Planner MAY add a **read-only UI hint** distinguishing "not yet uploaded" without ever stamping `synced_at`.
- **D-08:** **Integrity = plain SHA-256** of the NDJSON **payload** (stdlib `hashlib`, no new dependency), stored as a **new header field** (suggested `payload_sha256`). Closes the one gap: silent in-string corruption that still parses as valid JSON. Compute over the **record lines only** (header excluded, exact emission order) during serialization; **verify at the upload/route layer BEFORE `apply_merge`**, keeping pure `parse_exchange` + its round-trip tests intact. On mismatch → reject before touching the DB: «Файл повреждён, экспортируйте заново». (Rejected: HMAC — client-generated file, no server secret; no-checksum — silent value corruption merges undetected.)
- **D-09:** **Two version gates, both before merge, distinct messages:** `format_version` exact-match hard reject (already inside `parse_exchange`); `schema_version` exact-match vs `current_schema_version(session)` enforced at the **OFF-07 upload layer, NOT inside `parse_exchange`**. Reject names both versions: «Файл собран для версии данных X, сервер ожидает Y — обновите приложение». **Empty server-side `schema_version` = skip the check** (create_all fixtures have no `alembic_version` table — preserve current behavior).
- **D-10:** **Preview (counts) computed client-side** in the HTML from the embedded NDJSON, **BEFORE** form submit, with an **explicit confirm click** (nothing sent until confirmed).

### Claude's Discretion

- Short-lived login-token TTL value and exact scope claim; the offline-token minter's internal shape (reuse `itsdangerous` signer).
- Exact `<script type="application/x-ndjson">` embedding details and the result-page HTML/wording (success, wrong-password, corrupted-file, incompatible-version).
- The new header field name for the checksum (suggested `payload_sha256`) and where the schema-version gate lives (route vs thin wrapper around `parse_exchange`).
- Whether/how to surface a read-only "offline-exported, not yet confirmed" UI hint (must never stamp `synced_at`).
- Preview counts wording/layout and the export-file naming/location on the USB drive.

### Deferred Ideas (OUT OF SCOPE)

- **Receipt-file round-trip** (Option B for OFF-01 marking) — revisit only if UAT shows the inflated unsynced badge confuses the operator.
- **Optimistic mark-on-export** (Option A) — rejected outright (data-loss), not deferred.
- **HMAC-signed files** — rejected (no server secret); recorded so not re-proposed.
- **`fetch()`-based uploader with a dedicated `ACAO: null` endpoint** — revisit only if the rendered result page proves insufficient.
- **Compression** of the export file — out of scope; never adopt it *for* integrity.
- **Any PULL / two-way sync** over the USB path — explicitly out of scope (upload-only).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OFF-01 | Offline client keeps recording + accumulates not-yet-uploaded work | `synced_at IS NULL` is the accumulation marker; `sync_client._collect_push_records` already selects exactly those rows. D-07: export only reads, never stamps. No new logic. |
| OFF-02 | Export all not-yet-uploaded data to a single self-contained USB file, offline | New client route (session-guarded, e.g. `GET /offline/export`) → `_collect_push_records` → `serialize_exchange` → Jinja2 HTML template with embedded NDJSON → `Content-Disposition: attachment` download. All stdlib/existing; works offline. |
| OFF-03 | No install; opens in a browser; uploads itself | Self-contained HTML: embedded `<script type="application/x-ndjson">` payload + login form + preview JS + top-level `<form>` POST to the server's absolute HTTPS URL (embedded at export time from `settings.sync_server_url`). |
| OFF-04 | Login+password auth; wrong credential rejected clearly; NO data sent | Two-step handshake (D-03/D-04): step 1 `POST /api/offline/login` sends creds ONLY, returns a short-lived token; step 2 sends the payload only after step 1 succeeds. `verify_password` (Argon2id) + `check_rate_limit`. |
| OFF-05 | Same idempotent UUID merge; twice = nothing; all-or-nothing | Reuse `apply_merge` verbatim in the `sync_push` transaction idiom. No new merge, no dedup table, no migration. |
| OFF-06 | Preview (counts) + explicit confirm | Client-side JS reads the embedded NDJSON header's `counts` map (already emitted by `serialize_exchange`) BEFORE submit; confirm button gates the form POST. |
| OFF-07 | Integrity checksum + schema-version validation; reject tampered/incompatible clearly | SHA-256 over record lines (D-08, new `payload_sha256` header field) verified at the upload route BEFORE merge; `schema_version` exact-match gate (D-09) vs `current_schema_version(session)`. Distinct RU messages. |
</phase_requirements>

## Summary

This phase adds **one new route module** (`app/routes/offline.py`) and **one new Jinja2 template** (the self-uploading HTML), plus a small **export collector reuse** on the client side and a **new `payload_sha256` header field** in the NDJSON serializer. Every hard part — the merge, idempotency, conflict resolution, FK-closure collection, password verification, rate limiting, the all-or-nothing transaction idiom, the auth-guard bypass pattern — **already exists and is tested** (Phases 27–29). Phase 30 is overwhelmingly *wiring plus one browser-side template*, not new algorithm design. **No new package is added; no new database migration is required** (the checksum lives in the wire header, not a DB column; D-07 writes no `synced_at`).

The genuinely novel work is confined to three places: (1) the **self-contained HTML uploader** and its browser transport mechanics (embedding NDJSON safely, the two-step login→upload handshake, form-POST navigation that lands on a rendered result page); (2) a **thin ingest route** that verifies the SHA-256 digest and the schema-version before calling `apply_merge`; and (3) an **`itsdangerous` short-lived upload-scoped token** minted from the existing `settings.secret_key` (verified: `URLSafeTimedSerializer` with a dedicated salt and `max_age` TTL).

The one design tension the planner must resolve: a **top-level `<form>` navigation cannot carry a JS-held string as raw bytes without CRLF line-ending normalization, and cannot read a cross-origin response** — so the *bulk upload* stays a navigation (D-01, no CORS) while the *login handshake* needs one narrow CORS response header so the file's JS can read back the token (exactly what D-05 provisions). Both the exporter's digest computation and the server's verification must **canonicalize line endings via `splitlines()` + `"\n".join()`** so CRLF normalization never breaks the checksum.

**Primary recommendation:** Build `app/routes/offline.py` as a thin caller mirroring `app/routes/sync.py`; reuse `sync_client._collect_push_records`, `serialize_exchange`, `parse_exchange`, `apply_merge`, `current_schema_version`, `verify_password`, `check_rate_limit` verbatim; mint the upload token with `itsdangerous.URLSafeTimedSerializer(settings.secret_key, salt="offline-upload")` and a 300s TTL; add `payload_sha256` to the serializer header and verify it at the route before merge; keep the online `/api/sync/` CORS posture untouched by scoping the narrow CORS header to `/api/offline/login` only.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Accumulate unsynced work (OFF-01) | Database / Storage (client SQLite) | — | `synced_at IS NULL` is the durable marker; no server involvement offline. |
| Build export bundle (FK-closure) (OFF-02) | API / Backend (client app service) | Database | Pure query over the local ledger; reuses `_collect_push_records`. |
| Render self-contained HTML file (OFF-02/03) | Frontend Server (client, Jinja2) | — | Server-side template render with embedded data; the client app IS the renderer. |
| Preview counts + confirm (OFF-06/10) | Browser / Client (the .html on the internet PC) | — | Pure client-side JS over embedded NDJSON; no network until confirm. |
| Credential handshake (OFF-04) | API / Backend (central server) | — | Password verify + token mint on the server; never client-trusted. |
| Ingest: integrity + schema gate + merge (OFF-05/07) | API / Backend (central server) | Database | Route-layer validation then the shared engine in one owned transaction. |
| Result page (success/rejection) | Frontend Server (central server, Jinja2) | — | Server renders HTML the operator lands on (D-01). |

## Standard Stack

### Core — everything reused, zero new packages

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `hashlib` (stdlib) | — | SHA-256 payload digest (D-08) | Already the exact pattern in `app/services/devices.py:49-51`. No dependency. `[VERIFIED: codebase]` |
| `itsdangerous` | 2.2.0 | Short-lived upload-scoped signed token (D-03) | Already a declared dep (pyproject `itsdangerous==2.2.*`) and already in the runtime via Starlette `SessionMiddleware`. `URLSafeTimedSerializer(secret, salt=...)` + `loads(token, max_age=TTL)` executed and round-tripped successfully this session. `[VERIFIED: uv run]` |
| `argon2-cffi` (`app.services.auth`) | 25.1.* | Password verify for the login step | `verify_password(session, user, raw)` reused verbatim. `[VERIFIED: codebase]` |
| Jinja2 | 3.1.* | Self-uploading HTML template + result pages | The project's standard templating (`app/routes/__init__.py` `templates`). `[VERIFIED: codebase]` |
| FastAPI `Form`/`Body` + `python-multipart` | 0.139.* / 0.0.32 | Multipart form ingest of the payload | `python-multipart` already installed; the app is form-driven. `[VERIFIED: codebase]` |

### Supporting — reused engine functions (exact signatures)

| Symbol | File:line | Signature / idiom | Reuse in Phase 30 |
|--------|-----------|-------------------|-------------------|
| `serialize_exchange` | `app/services/merge.py:527` | `serialize_exchange(records, *, schema_version, source_device_id, generated_at) -> Iterator[str]` — yields header FIRST then one line per record | The export payload. **Add `payload_sha256` to the emitted header** (computed over the record lines it already materializes). |
| `parse_exchange` | `app/services/merge.py:138` | `parse_exchange(lines) -> ExchangeBatch` — validates before any DB touch; `format_version != 1` → `ValueError`; forces `synced_at=None` | Reuse verbatim in the upload route. Do NOT add the schema/checksum gates inside it (D-08/D-09). |
| `apply_merge` | `app/services/merge.py:464` | `apply_merge(session, batch, *, server_now) -> MergeReport` — **never commits** | The ingest engine. Idempotency (OFF-05) is intrinsic. |
| `current_schema_version` | `app/services/sync.py:225` | `current_schema_version(session) -> str` — live Alembic head or `""` | The D-09 schema-version reference. |
| `_collect_push_records` | `app/services/sync_client.py:256` | `_collect_push_records(session) -> (list[ExchangeRecord], dict[str,list[str]])` — unsynced ledger + D-13 FK closure | **The correct export collector.** Use the records; ignore the ids (D-07 never stamps). |
| `verify_password` | `app/services/auth.py:37` | `verify_password(session, user, raw) -> bool` — constant-time, never raises | The login step. |
| `check_rate_limit` | `app/services/rate_limit.py:27` | `check_rate_limit(key) -> bool` | Rate-limit `/api/offline/login` (D-05). |
| `sync_push` txn idiom | `app/routes/sync.py:120-122` | `session.rollback(); with session.begin(): apply_merge(...)` | Copy verbatim for all-or-nothing ingest (OFF-05). |
| `auth_guard` bypass | `app/services/security.py:52,164` | `SYNC_PATH_PREFIX = "/api/sync/"`; `if request.url.path.startswith(SYNC_PATH_PREFIX): return` | Add `OFFLINE_PATH_PREFIX = "/api/offline/"` and a second `startswith` branch. |

> **⚠ Naming correction for the planner:** CONTEXT.md's canonical_refs call the export collector `collect_reference_records`. That symbol (`app/services/sync.py:134`) is the **server-side pull pager** (cursor-based, server→client reference data) — NOT what the export needs. The function that builds "the transitive FK closure of unsynced ledger rows" is **`sync_client._collect_push_records`** (`app/services/sync_client.py:256`). Reuse THAT. It is currently private (leading underscore) — the planner should promote it to a public `collect_push_records` (or add a thin public wrapper) so the offline export and the online push share one collector (SYNC-04: never two divergent implementations).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Payload as a form field (CRLF-normalized) | Payload as a Blob/File part (byte-exact) | You **cannot** programmatically populate an `<input type=file>`, and a Blob upload requires `fetch` (loses the rendered result page). The form-field + line-ending canonicalization path is the only one compatible with D-01's navigation-to-result-page. |
| `URLSafeTimedSerializer` | bare `TimestampSigner` | The serializer packs a JSON claim dict (scope + sub) *and* the timestamp in one urlsafe string; `TimestampSigner` only signs opaque bytes. The serializer is the right shape for an upload-scoped claim. |
| Narrow per-route CORS header on login | App-wide `CORSMiddleware` | Middleware is app-wide and would touch `/api/sync/` and every HTML route — directly violating D-01's "never loosen the online-sync CORS posture." Set the single ACAO header manually in the login response only. |

**Installation:** *None.* No `uv add`. All symbols are stdlib or already-declared dependencies.

**Version verification (this session):**
- `itsdangerous` — `uv run python -c "import itsdangerous"` → **2.2.0**; `URLSafeTimedSerializer(...).dumps(...)` → `loads(..., max_age=300)` round-tripped `{'scope':'offline_upload','sub':'u1'}`. `[VERIFIED: uv run]`
- `itsdangerous` declared `==2.2.*` in `pyproject.toml:10`. `[VERIFIED: codebase]`

## Package Legitimacy Audit

**No external packages are installed in this phase.** Every dependency is either the Python standard library (`hashlib`) or already present and locked in `pyproject.toml` (`itsdangerous`, `argon2-cffi`, `jinja2`, `fastapi`, `python-multipart`). The Package Legitimacy Gate is therefore **not triggered** — there is nothing to verify against a registry.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Architecture Patterns

### System Architecture Diagram

```
OFFLINE DESKTOP CLIENT (local SQLite, no internet)
────────────────────────────────────────────────────
 operator records receipts/sales  ──►  ledger rows with synced_at = NULL   (OFF-01)
                                          │
              GET /offline/export  ◄──────┘  (session-guarded, operator clicks "Экспорт на USB")
                     │
                     ▼
   sync_client._collect_push_records(session)   ── unsynced ledger + D-13 FK closure
                     │  records
                     ▼
   serialize_exchange(records, schema_version=current_schema_version(session), …)
                     │  NDJSON text  (header carries format_version, schema_version, counts, payload_sha256)
                     ▼
   Jinja2 render: self_upload.html  ── embed NDJSON in <script type="application/x-ndjson">
                     │                   (escape </script> → <\/script>); embed server HTTPS URL
                     ▼
   HTTP 200 + Content-Disposition: attachment; filename="myorishop-offline-YYYYMMDD-HHMM.html"
                     │
             operator saves to  ───►  [ USB FLASH DRIVE ]   (OFF-02)


ANY INTERNET COMPUTER (no app install)  ──────────────────────────────────
 operator opens the .html (file:// origin null) in any browser              (OFF-03)
                     │
   client JS: read <script> textContent → unescape <\/script> → NDJSON
              parse header line → show counts preview                        (OFF-06/10)
                     │  operator types login+password, clicks "Проверить"
                     ▼
   fetch POST  {server}/api/offline/login   (application/x-www-form-urlencoded, creds ONLY)
                     │                        ┌───────────────────────────────────────┐
                     ▼                        │ CENTRAL SERVER (PostgreSQL)            │
        /api/offline/login  ─────────────────►  check_rate_limit(login)              │
                                              │  verify_password (Argon2id)           │  (OFF-04)
                                              │  wrong → 401 RU msg, NO token, NO data │
                                              │  right → mint itsdangerous token       │
        token (JSON) + ACAO header  ◄─────────┤  (URLSafeTimedSerializer, TTL 300s)   │
                     │                        └───────────────────────────────────────┘
   JS injects token into hidden field; operator clicks "Отправить" (confirm)
                     ▼
   TOP-LEVEL <form> POST  {server}/api/offline/upload   (multipart nav — NO CORS/preflight)
                     │  token + NDJSON payload           ┌──────────────────────────────┐
                     ▼                                    │ /api/offline/upload           │
                                                          │  verify itsdangerous token    │
                                                          │  (max_age TTL, scope claim)   │
                                                          │  size cap (belt-and-braces)   │
                                                          │  decode → splitlines          │
                                                          │  ① SHA-256(record lines) ==   │  (OFF-07)
                                                          │     header.payload_sha256 ?   │
                                                          │  ② schema_version == server?  │  (OFF-07/D-09)
                                                          │  ③ parse_exchange (format ver)│
                                                          │  ④ rollback; begin():         │  (OFF-05)
                                                          │       apply_merge(...)        │
                                                          └──────────────┬────────────────┘
                                                                         ▼
                     operator LANDS on a rendered RU HTML result page (success / rejection)
```

### Recommended Project Structure

```
app/
├── routes/
│   └── offline.py          # NEW: GET /offline/export (client, session-guarded)
│                           #      POST /api/offline/login  (server, bypass + rate-limit + verify_password)
│                           #      POST /api/offline/upload (server, bypass + token + validate + merge)
├── services/
│   ├── offline.py          # OPTIONAL NEW: thin helpers — mint/verify token, compute/verify sha256,
│   │                       #   build the export bundle (or fold into the route if trivial)
│   ├── merge.py            # EDIT: add payload_sha256 to serialize_exchange header
│   ├── sync_client.py      # EDIT: promote _collect_push_records → public collect_push_records
│   └── security.py         # EDIT: add OFFLINE_PATH_PREFIX bypass branch to auth_guard
├── templates/
│   └── offline/
│       ├── self_upload.html    # NEW: the self-contained uploader (embedded NDJSON + form + preview JS)
│       └── result.html         # NEW: server result page (success / wrong-pw / corrupted / incompatible)
└── main.py                 # EDIT: include_router(offline.router) — NO app-level dependencies=
                            #       (per-route gating mirrors the sync tree)
```

### Pattern 1: Thin ingest route mirroring `sync_push`

**What:** The upload route owns exactly four jobs (token gate, validate, own one transaction, render result) and delegates all merge semantics.
**When to use:** `POST /api/offline/upload`.
**Example:**
```python
# Source: adapted from app/routes/sync.py:66-133 (VERIFIED in-repo)
@router.post("/api/offline/upload")
def offline_upload(
    request: Request,
    token: str = Form(...),
    payload: str = Form(...),            # form FIELD — CRLF-normalized on submit (see Pitfall 1)
    session: Session = Depends(get_session),
):
    _require_offline_token(token)        # itsdangerous loads(max_age=TTL) + scope check → 401 RU on failure
    # size cap (belt-and-braces, mirrors sync.py MAX_PUSH_BYTES)
    if len(payload.encode("utf-8")) > MAX_OFFLINE_BYTES:
        return _result(request, "corrupted", status=413)
    lines = payload.splitlines()         # canonicalizes CRLF → logical lines (matches exporter)
    if not lines:
        return _result(request, "corrupted", status=400)
    # ① integrity (D-08): recompute over RECORD lines only, canonical LF join
    header = json.loads(lines[0])
    record_lines = lines[1:]
    digest = hashlib.sha256("\n".join(record_lines).encode("utf-8")).hexdigest()
    if digest != header.get("payload_sha256"):
        return _result(request, "corrupted", status=400)   # «Файл повреждён…»
    # ② schema-version gate (D-09): only when the server reports a real revision
    server_schema = current_schema_version(session)
    if server_schema and header.get("schema_version") != server_schema:
        return _result(request, "incompatible", status=409,
                       file_ver=header.get("schema_version"), server_ver=server_schema)
    # ③ format_version + structural validation (reused; never echo attacker bytes)
    try:
        batch = parse_exchange(lines)
    except ValueError:
        return _result(request, "corrupted", status=400)
    # ④ all-or-nothing (OFF-05): identical to sync_push
    session.rollback()
    with session.begin():
        report = apply_merge(session, batch, server_now=utcnow_iso())
    return _result(request, "success", report=report)
```

### Pattern 2: `itsdangerous` upload-scoped token (D-03)

**What:** A stateless, short-lived, signed token proving "an authenticated operator authorized an upload within TTL." No DB table, no server-side session.
**When to use:** minted in `/api/offline/login`, verified in `/api/offline/upload`.
**Example:**
```python
# Source: itsdangerous 2.2.0 — round-trip EXECUTED and VERIFIED this session (uv run)
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

OFFLINE_TOKEN_TTL = 300          # seconds — discretion; short enough to blunt a keylogger
_signer = URLSafeTimedSerializer(settings.secret_key, salt="offline-upload")  # dedicated salt namespaces it from the session cookie

def mint_offline_token(user_id: str) -> str:
    return _signer.dumps({"scope": "offline_upload", "sub": user_id})

def verify_offline_token(token: str) -> dict:
    data = _signer.loads(token, max_age=OFFLINE_TOKEN_TTL)   # raises SignatureExpired / BadSignature
    if data.get("scope") != "offline_upload":
        raise BadSignature("wrong scope")
    return data
```
> `settings.secret_key` (`app/config.py:35,86-87`) is the per-install session-signing key — already present on every client and server, never logged. The distinct `salt` guarantees an offline token can never be replayed as a session cookie or vice versa.

### Pattern 3: Safe NDJSON embedding + round-trip (D-02/D-08)

**What:** Store NDJSON inside a non-executed script block; escape only `</script>`; reverse before submit; digest computed over the ORIGINAL (unescaped) NDJSON on both sides.
**Example:**
```python
# Exporter side (Python, at render time)
embedded = ndjson_text.replace("</script", "<\\/script")   # only escaping needed (D-02)
# render with autoescape OFF for THIS injection: {{ embedded | safe }} inside <script type="application/x-ndjson">
```
```javascript
// Browser side (the .html file)
const raw = document.getElementById("payload").textContent;   // escaped form
const ndjson = raw.replace(/<\\\/script/g, "</script");       // reverse to ORIGINAL
const header = JSON.parse(ndjson.split("\n")[0]);             // header.counts drives the preview (OFF-06)
document.querySelector("input[name=payload]").value = ndjson; // submit the ORIGINAL; digest matches
```

### Anti-Patterns to Avoid

- **App-wide `CORSMiddleware`:** touches `/api/sync/` and every HTML route — violates D-01. Scope one ACAO header to the login response.
- **Submitting the payload via `fetch` to see the merge report:** breaks D-01's "land on a rendered result page" and forces a CORS `ACAO` on the bulk path. Deferred (see CONTEXT).
- **Adding the schema/checksum gates inside `parse_exchange`:** breaks its purity + round-trip tests (D-08/D-09 both say "at the upload layer, NOT inside parse_exchange").
- **Stamping `synced_at` on export:** flat-out forbidden (D-07 — data-loss risk).
- **Bare `==` on the token or digest string:** use `itsdangerous`'s own verify (HMAC-timed) for the token; the SHA-256 digest compare is not a secret-equality (it's integrity, not auth) so a plain `==` is acceptable there — but never compare the *token* with `==`.
- **Embedding the payload in a `<textarea>`:** would require `</textarea>` escaping and re-introduce the very hazard D-02 avoided; keep it in `<script type="application/x-ndjson">`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent UUID merge | A new ingest merge / dedup table | `apply_merge` (`merge.py:464`) | Insert-if-new by UUID IS the idempotency; re-upload = no-op. A second implementation violates SYNC-04. |
| FK-closure of unsynced rows | A fresh closure walker | `sync_client._collect_push_records` (`sync_client.py:256`) | Already walks op→product/batch/sale, cash→sale, sale→customer, batch→product/warehouse in FK order. |
| Short-lived auth token | A custom HMAC + timestamp scheme | `itsdangerous.URLSafeTimedSerializer` | Signing + expiry + tamper-detection in one verified stdlib-of-the-stack call. |
| Password check | Any new comparison | `verify_password` (`auth.py:37`) | Constant-time Argon2id, rehash-on-login, never raises. |
| Rate limiting | A new limiter / package | `check_rate_limit` (`rate_limit.py:27`) | Thread-safe token bucket already used by the sync tree. |
| All-or-nothing ingest | Manual try/except/rollback | `session.rollback(); with session.begin(): …` (`sync.py:120-122`) | The proven transaction-ownership idiom; `apply_merge` never commits by design. |
| Money/timestamp/id handling on the wire | Any parsing in the offline path | The NDJSON format enforces integer-cents + ISO-UTC + UUID already | `parse_exchange` rejects float money and forces `synced_at=None`. |

**Key insight:** Phase 30 has essentially **no domain algorithm of its own**. Its only original code is the browser-side uploader template and a ~40-line ingest route. Every correctness-critical operation is a call into Phase 27–29 code that already runs green on SQLite *and* PostgreSQL. Resist any temptation to "optimize" the offline path with a bespoke merge or a new persistence table.

## Common Pitfalls

### Pitfall 1: CRLF line-ending normalization breaks the SHA-256 digest
**What goes wrong:** A top-level `<form>` submit serializes text field values with **CRLF (`\r\n`) line endings** (HTML form-encoding rule), even when the JS-assigned value used `\n`. If the exporter digests LF-joined lines but the server digests the received bytes verbatim, the checksum never matches and every real upload is rejected as "corrupted."
**Why it happens:** Browsers normalize newlines in submitted text controls; only Blob/File parts are byte-exact, and you cannot programmatically fill a file input.
**How to avoid:** **Both** sides canonicalize: the exporter computes `hashlib.sha256("\n".join(record_lines).encode())`; the server computes over `"\n".join(payload.splitlines()[1:])`. `str.splitlines()` strips `\r\n` and `\n` alike, so re-joining with `\n` yields identical bytes regardless of transport normalization. JSON record lines never contain literal newlines (json.dumps escapes them as `\n` text), so each record is exactly one physical line.
**Warning signs:** All uploads reject as corrupted in a real browser but pass in tests that POST raw `\n` bytes. **Add a CRLF-payload test** (see Validation Architecture).

### Pitfall 2: `</script>` inside product data closes the embed early
**What goes wrong:** A product name literally containing `</script>` terminates the `<script type="application/x-ndjson">` block during HTML parsing, truncating the payload.
**Why it happens:** Script blocks are raw-text; JSON does not escape `/`.
**How to avoid:** Replace `</script` → `<\/script` when embedding (D-02); reverse in JS before parse/submit; **digest the original, unescaped NDJSON** on both sides.
**Warning signs:** A payload that parses in isolation fails to load in the browser; a round-trip test with a `</script>`-bearing name is the guard.

### Pitfall 3: The exact-prefix auth-guard bypass (repeat of the SYNC pitfall)
**What goes wrong:** Bypassing the bare `/api/` prefix (instead of `/api/offline/`) would un-authenticate every current and future API route — the single highest-consequence line.
**Why it happens:** Copy-paste of the sync bypass with a shortened prefix.
**How to avoid:** `OFFLINE_PATH_PREFIX = "/api/offline/"` exactly; the ingest routes stay guarded per-route (token verify on upload, rate-limit + password on login). The client **export** route is NOT under `/api/offline/` — keep it session-guarded (mirror `/sync/run` which stays behind `auth_guard`).
**Warning signs:** A cross-auth negative test — a browser session must NOT reach `/api/offline/*` as a bypass, and the export page MUST require a session — mirrors `test_sync_api.py:165-187`.

### Pitfall 4: Loosening the online-sync CORS posture
**What goes wrong:** Adding `CORSMiddleware` app-wide (or an `ACAO: null`/`*` on `/api/sync/`) to make the login fetch work — exactly what D-01 forbids.
**How to avoid:** Set a single `Access-Control-Allow-Origin` header **only on the `/api/offline/login` response**, with **no** `Access-Control-Allow-Credentials`. Send the login body as `application/x-www-form-urlencoded` so it is a CORS *simple request* (no preflight OPTIONS). The bulk upload stays a form navigation and needs no CORS at all.
**Warning signs:** Any diff touching `app/main.py` middleware or the sync routes' headers.

### Pitfall 5: `settings.sync_server_url` blank on a never-synced client
**What goes wrong:** The exported file must embed the server's absolute HTTPS URL for its `fetch`/`form action`. A client that has never been configured has `sync_server_url == ""`, producing a file that posts to nowhere.
**How to avoid:** The export route should refuse (or clearly warn in RU) when `settings.sync_server_url` is empty, directing the operator to configure it once. Embed `settings.sync_server_url` (`app/config.py:56`) into the template.
**Warning signs:** A generated file whose form action is `/api/offline/upload` with no host.

### Pitfall 6: Jinja2 autoescaping the embedded JSON
**What goes wrong:** Jinja2 HTML-escapes `"` → `&quot;` inside the payload, corrupting the JSON.
**How to avoid:** Inject the payload with `| safe` (after the manual `</script` escape). It is safe: the block is `type="application/x-ndjson"` (non-executable) and the only breakout vector (`</script>`) is already neutralized. Everything else in the template stays autoescaped.

### Pitfall 7: `schema_version` gate rejecting the test fixtures
**What goes wrong:** Enforcing `schema_version` equality unconditionally rejects any batch produced under a `create_all` fixture (no `alembic_version` table → `current_schema_version` returns `""`).
**How to avoid:** D-09 — **skip the gate when `current_schema_version(session)` is empty**; only enforce equality when the server reports a real revision. `parse_exchange` already accepts an empty header `schema_version`.

## Code Examples

### Auth-guard bypass addition (mirror the sync branch)
```python
# Source: app/services/security.py:52,164 (VERIFIED in-repo)
OFFLINE_PATH_PREFIX = "/api/offline/"   # ingest endpoints only; NOT the export page
# inside auth_guard, right after the SYNC_PATH_PREFIX branch:
if request.url.path.startswith(OFFLINE_PATH_PREFIX):   # in-body auth; no session/CSRF
    return
```

### Login route (creds only → token; narrow CORS; no data leaves on failure)
```python
# Source: composed from app/routes/auth.py:51-79 + rate_limit.py:27 (VERIFIED in-repo)
@router.post("/api/offline/login")
def offline_login(
    login: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
):
    if not check_rate_limit(f"offline-login:{login.strip()}"):     # D-05 brute-force blunt
        return JSONResponse({"error": RATE_LIMITED_ERROR}, status_code=429,
                            headers={"Access-Control-Allow-Origin": "*"})
    user = session.scalar(select(User).where(User.login == login.strip()))
    if user is None or not verify_password(session, user, password) or user.is_active != 1:
        # OFF-04: clear rejection, NO token, NO data (payload never left the machine)
        return JSONResponse({"error": BAD_CREDENTIALS_ERROR}, status_code=401,
                            headers={"Access-Control-Allow-Origin": "*"})
    token = mint_offline_token(user.id)
    return JSONResponse({"token": token}, headers={"Access-Control-Allow-Origin": "*"})
```
> `Access-Control-Allow-Origin: *` with **no** `Allow-Credentials` is the minimal rule that lets the `file://` page's JS read the token; the endpoint sends no cookies and returns a token only on correct credentials, so `*` is safe and simpler than reflecting `null`. This header appears on `/api/offline/login` **only**.

### `payload_sha256` in the serializer header (edit `serialize_exchange`)
```python
# Source: app/services/merge.py:527-559 (VERIFIED in-repo) — minimal additive change
materialized = list(records)
record_lines = [json.dumps({"kind": r.kind, **r.data}, ensure_ascii=False) for r in materialized]
payload_sha256 = hashlib.sha256("\n".join(record_lines).encode("utf-8")).hexdigest()
header = {
    "kind": "header", "format_version": FORMAT_VERSION, "schema_version": schema_version,
    "source_device_id": source_device_id, "generated_at": generated_at,
    "counts": counts, "payload_sha256": payload_sha256,   # NEW (D-08)
}
yield json.dumps(header, ensure_ascii=False)
yield from record_lines
```
> Adding a header field is safe for existing callers: `parse_exchange` reads only `format_version`/`schema_version`/`source_device_id` and ignores unknown header keys; the online push route ignores it. Round-trip tests assert on `.records`, not the header, so they stay green. The online push gains a free integrity field it may optionally verify later.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Two divergent transports (online API + offline importer) | One NDJSON format + one `apply_merge` engine, two thin callers | Phase 27 (SYNC-04) | Phase 30 adds zero merge logic. |
| Optimistic "mark exported = synced" | Read-only export; `synced_at` cleared only by a confirmed online 2xx | Phase 30 D-07 | Never loses data; badge stays inflated for permanently-offline clients (UAT flag). |
| No wire integrity check | SHA-256 header field verified before merge | Phase 30 D-08 | Catches silent value corruption that still parses as JSON. |

**Deprecated/outdated:** none introduced. Note `itsdangerous.__version__` is deprecated (use `importlib.metadata.version`) — cosmetic only; do not read `__version__` in code.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A top-level `<form>` submit normalizes text-field newlines to CRLF, and the `splitlines()`+`"\n".join()` canonicalization on both sides makes the digest match regardless. | Pitfall 1 / Pattern 1 | If the browser preserves LF (or the field is sent byte-exact), canonicalization is still correct (idempotent) — low risk. If some browser sends a different separator, the digest breaks. **Mitigate with a real-browser or CRLF-payload test.** Training knowledge; web search disabled this session. |
| A2 | A cross-origin `fetch` with `application/x-www-form-urlencoded` body from a `file://` (Origin `null`) page is a CORS *simple request* (no preflight), and returning `Access-Control-Allow-Origin: *` lets JS read the token. | Pitfall 4 / login example | If a preflight *is* required, `/api/offline/login` also needs an `OPTIONS` handler returning the CORS headers. Low-cost fallback. Training knowledge. |
| A3 | `URLSafeTimedSerializer(secret, salt=...).loads(token, max_age=TTL)` raises `SignatureExpired`/`BadSignature` on expiry/tamper. | Pattern 2 | Verified by execution this session — **low risk**. |
| A4 | Embedding NDJSON in `<script type="application/x-ndjson">` with only `</script>`→`<\/script>` escaping is safe against HTML-parser breakout. | Pattern 3 / Pitfall 2 | Standard technique; the round-trip test is the guard. Training knowledge. |
| A5 | 300s is an appropriate upload-token TTL. | Pattern 2 | Discretion (CONTEXT). Too short → operator re-logins; too long → wider keylogger window. Adjustable constant. |
| A6 | No new Alembic migration is required. | (below) | If a `payload_sha256` DB column or a replay-dedup table were ever demanded, a migration would be needed — but D-07/D-08 place the checksum in the wire header and OFF-05 dedups by existing UUID PK, so none is. Confirmed from codebase. |

## Open Questions (RESOLVED)

> All three resolved during planning (Phase 30 plans 30-02..30-04): Q1 → 30-03 (urlencoded login + narrow ACAO on `/api/offline/login` only, OPTIONS added only if a preflight appears); Q2 → 30-02 (promote `_collect_push_records` → public `collect_push_records`); Q3 → 30-04 (optional read-only hint, never stamps `synced_at`, deferable to UAT).

1. **[RESOLVED → 30-03] Login transport: `fetch` + narrow CORS vs. a pure-navigation alternative?**
   - What we know: the bulk upload must be a form navigation (D-01); the login must be a separate round-trip whose response the file reads (D-04), which implies `fetch` + one CORS header (D-05 provisions exactly this).
   - What's unclear: whether a preflight fires for the login fetch (A2).
   - Recommendation: send login as `application/x-www-form-urlencoded` (simple request); if a preflight appears in testing, add a minimal `OPTIONS /api/offline/login` returning the same ACAO header. Keep the header off `/api/sync/`.

2. **Promote `_collect_push_records` to public, or add a wrapper?**
   - What we know: reuse is mandatory (SYNC-04); the symbol is currently private.
   - Recommendation: rename to `collect_push_records` (public) and update the two call sites, so the export and online push share one collector — the cleanest guard against divergence.

3. **Read-only "offline-exported, not yet confirmed" UI hint (D-07 discretion).**
   - Recommendation: optional; if added, derive it purely from data already present (e.g. a per-session flag or a timestamp file) and **never** write `synced_at`. Safe to defer to UAT feedback (the deferred Option B path).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python + FastAPI stack | Export route + ingest routes | ✓ | 3.13 / 0.139.* | — |
| `itsdangerous` | Upload token | ✓ | 2.2.0 (verified) | — |
| `hashlib` (stdlib) | Integrity digest | ✓ | — | — |
| A modern browser on the internet PC | OFF-03 self-upload | ✗ (external, out of our control) | — | None — but the file targets baseline `fetch` + form POST + `textContent`, supported by every browser since ~2017. No polyfill needed. |
| HTTPS-served central server URL | The file's form action / fetch target | ✓ (Phase 28 deploy behind Caddy TLS) | — | `settings.sync_server_url` must be non-empty on the exporting client (Pitfall 5). |

**Missing dependencies with no fallback:** none. The only "external" runtime is the browser on the internet-connected PC, which is inherent to OFF-03 and needs no install.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (+ `fastapi.testclient`, `httpx` 0.28.*) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_offline.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OFF-01 | Unsynced rows accumulate; export reads them; export writes NO `synced_at` | unit | `uv run pytest tests/test_offline.py::test_export_does_not_stamp_synced_at -x` | ❌ Wave 0 |
| OFF-02 | Export bundle = FK-closure of unsynced ledger; self-contained HTML download | unit/integration | `... ::test_export_bundle_fk_closure_complete` | ❌ Wave 0 |
| OFF-03 | Exported HTML embeds NDJSON in `<script type=application/x-ndjson>` + server URL + form | integration | `... ::test_export_html_contains_embedded_payload_and_form` | ❌ Wave 0 |
| OFF-04 | Wrong password → 401, NO token; right password → token; **no data field accepted by login** | integration | `... ::test_login_wrong_password_no_token` / `::test_login_success_mints_token` | ❌ Wave 0 |
| OFF-05a | Idempotent double-upload changes nothing | integration | `... ::test_upload_twice_is_noop` (mirror `test_sync_api.py::test_push_idempotent`) | ❌ Wave 0 |
| OFF-05b | Interrupted/poisoned batch rolls back whole (all-or-nothing) | integration | `... ::test_upload_all_or_nothing` (mirror `test_sync_api.py::test_push_all_or_nothing:209`) | ❌ Wave 0 |
| OFF-06 | Preview counts derivable from embedded header `counts`; (JS confirm gate is manual) | unit | `... ::test_export_header_counts_present` | ❌ Wave 0 |
| OFF-07a | SHA-256 mismatch (byte-flip that still parses) → rejected before DB touch, RU message | integration | `... ::test_upload_corrupted_checksum_rejected` | ❌ Wave 0 |
| OFF-07b | `schema_version` mismatch → 409, both versions named; empty server schema → skip | integration | `... ::test_upload_incompatible_schema_rejected` / `::test_upload_empty_server_schema_skips_gate` | ❌ Wave 0 |
| OFF-07c | `format_version` mismatch → rejected (via `parse_exchange`) | integration | `... ::test_upload_bad_format_version_rejected` | ❌ Wave 0 |
| — | Expired / tampered / wrong-scope upload token → 401 | integration | `... ::test_upload_expired_token_rejected` | ❌ Wave 0 |
| — | Auth-guard bypass is exact-prefix; browser session cannot use `/api/offline/*` as a bypass; export page needs a session | integration | `... ::test_offline_bypass_is_narrow` | ❌ Wave 0 |
| — | `</script>`-bearing product name survives export→embed→unescape→upload→parse (round-trip) | unit | `... ::test_script_tag_escaping_round_trip` | ❌ Wave 0 |
| — | CRLF-normalized payload still verifies its digest (Pitfall 1) | unit | `... ::test_crlf_payload_digest_matches` | ❌ Wave 0 |
| — | Rate limit on `/api/offline/login` → 429 | integration | `... ::test_login_rate_limited` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_offline.py tests/test_merge.py -x` (offline surface + engine round-trip).
- **Per wave merge:** `uv run pytest` (full suite — ~1122 passing baseline per project memory).
- **Phase gate:** full suite green before `/gsd-verify-work`; PG-parity CI must stay green because `apply_merge` runs on PostgreSQL too (SYNC-04 proof).

### Wave 0 Gaps
- [ ] `tests/test_offline.py` — covers OFF-01..07 + token/bypass/escaping/CRLF/rate-limit rows above.
- [ ] A fixture/helper to (a) build a valid offline NDJSON body **with a correct `payload_sha256` header** and (b) POST `/api/offline/login` to obtain a token — build on the existing `anon_client` (REAL guard, so the `/api/offline/` bypass is genuinely exercised, mirroring `device_client`).
- [ ] A helper to mint an offline token directly (via the serializer + `settings.secret_key`) for upload tests that skip the login step, plus an **expired-token** variant (`max_age`-in-the-past or a monkeypatched TTL).
- [ ] No new framework install — pytest/httpx/TestClient already present.

## Security Domain

### Applicable ASVS Categories (L1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `verify_password` (Argon2id) on `/api/offline/login`; generic RU failure (no user-enumeration oracle, mirror `auth.py:31` `BAD_CREDENTIALS_ERROR`); `check_rate_limit` blunts brute force. |
| V3 Session Management | yes | Stateless upload token via `itsdangerous` (HMAC-signed, `max_age` TTL, dedicated salt, scope claim). No cookies on the offline path (D-04/D-05) → no session-fixation surface. |
| V4 Access Control | yes | `auth_guard` exact-prefix bypass for `/api/offline/` only; export page stays session-guarded; login/upload guarded per-route (mirror the sync tree). |
| V5 Input Validation | yes | `parse_exchange` (float-money reject, unknown-kind reject, duplicate-id reject) + SHA-256 integrity + schema-version gate + body size cap, all before `apply_merge`. |
| V6 Cryptography | yes | SHA-256 (integrity, stdlib) + HMAC via `itsdangerous` (token). **No hand-rolled crypto**; D-08 deliberately rejects HMAC-signing of the file (no server secret exists client-side). |
| V7 Error Handling & Logging | yes | Never echo submitted bytes in errors (fixed RU constants, mirror `sync.py:53` / `T-28-07`); never log the token, password, or `secret_key` (CLAUDE.md). |
| V13 API / Web Service | yes | Narrow CORS: one `Access-Control-Allow-Origin` header on `/api/offline/login` only, **no** `Allow-Credentials`; `/api/sync/` posture untouched; bulk upload is a navigation (no CORS). |

### Known Threat Patterns for {self-uploading file on an untrusted internet PC}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Tampered/corrupted file uploaded | Tampering | SHA-256 header verify before merge (D-08) → «Файл повреждён…»; `parse_exchange` structural validation. |
| Incompatible-schema file merged | Tampering / Integrity | `schema_version` exact-match gate (D-09) → 409 naming both versions. |
| Replay (upload same file twice) | — (idempotent by design) | `apply_merge` UUID insert-if-new = no-op; **accepted risk**, no dedup table. |
| Payload sent before auth (data leak on wrong password) | Information Disclosure | Two-step handshake (D-04): creds first, data only after a confirmed password. |
| Stolen token on the untrusted PC | Spoofing / Elevation | Short TTL (300s) + upload-scope claim; token is single-purpose (cannot reach `/api/sync/` or the HTML app). |
| Keylogged password | Spoofing | `check_rate_limit` on login; short exposure window; out-of-scope items (2FA/lockout) explicitly excluded by REQUIREMENTS. |
| CORS widening of the sync API | Elevation of Privilege | Bulk upload is a form navigation (no CORS); the one ACAO header is scoped to `/api/offline/login`. |
| HTML-injection / breakout via embedded data | Tampering | Non-executable `<script type=application/x-ndjson>` + `</script>` escape; `| safe` used only after that escape. |
| CSRF on the ingest endpoints | Spoofing | In-body token auth, no cookies → not CSRF-vulnerable (same reasoning as the Bearer sync tree, `security.py:150-159`). |
| Oversized-body DoS | Denial of Service | Belt-and-braces size cap in the upload route (mirror `sync.py:61` `MAX_PUSH_BYTES`), independent of any proxy config. |

## Sources

### Primary (HIGH confidence)
- Codebase (read in full this session): `app/services/merge.py`, `app/routes/sync.py`, `app/services/sync.py`, `app/services/sync_client.py`, `app/services/security.py`, `app/services/auth.py`, `app/routes/auth.py`, `app/services/rate_limit.py`, `app/services/devices.py`, `app/config.py`, `app/core.py`, `app/routes/__init__.py`, `app/routes/export.py`, `app/main.py`, `tests/conftest.py`, `tests/test_sync_api.py`, `pyproject.toml`, `alembic/versions/0018_*.py`, `.planning/config.json`.
- `itsdangerous` 2.2.0 API — executed and round-tripped via `uv run` this session (`URLSafeTimedSerializer.dumps`/`loads(max_age=...)`).

### Secondary (MEDIUM confidence)
- CONTEXT.md D-01..D-10 (the authoritative decision record) and REQUIREMENTS.md §Offline.

### Tertiary (LOW confidence — flagged in Assumptions Log)
- Browser transport mechanics (CRLF form normalization A1; CORS simple-request rules A2; script-block escaping A4) — training knowledge; WebSearch/ref/perplexity all disabled in `.planning/config.json`, so these are marked `[ASSUMED]` and each has a corresponding Wave-0 test to confirm behavior at runtime.

## Metadata

**Confidence breakdown:**
- Reuse surface / stack: HIGH — every symbol read in-repo with exact signatures and line numbers; itsdangerous executed.
- Architecture / ingest route: HIGH — a near-verbatim mirror of the tested `sync_push`.
- Browser uploader mechanics: MEDIUM — correct by construction and by standard technique, but CRLF/CORS specifics are `[ASSUMED]` pending the Wave-0 tests.
- Pitfalls: HIGH for the codebase-derived ones (exact-prefix bypass, schema gate, CORS scope); MEDIUM for the browser ones.

**Research date:** 2026-07-20
**Valid until:** 2026-08-19 (stable stack; re-verify only if the merge/exchange format or the auth-guard bypass pattern changes).
