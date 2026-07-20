# Phase 30: Offline Self-Uploading File - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the **upload-only USB transfer path** for a desktop client
that has **no internet**. It builds three things:

1. An **offline export** on the desktop client: bundle all not-yet-uploaded work
   (the FK-closure of unsynced `Operation` + `CashMovement` rows — reusing the
   Phase 29 `collect_reference_records` / D-13 collector) into a **single
   self-contained file on a USB drive**, produced entirely offline.
2. A **self-uploading file** that opens in any browser on an internet-connected
   computer **with no app install**, authenticates with **login + password**,
   shows a **preview + explicit confirm**, and uploads its own payload to the
   central server.
3. A **server-side ingest path** that authenticates the operator, validates the
   file (integrity checksum + schema-version), and merges it through the
   **same idempotent UUID merge engine** (`app/services/merge.py apply_merge`) as
   online sync — all-or-nothing, uploading twice changes nothing.

**Requirements:** OFF-01, OFF-02, OFF-03, OFF-04, OFF-05, OFF-06, OFF-07.

**Not in scope:** any PULL in the offline path (upload-only — no
server→client data flow here); mobile UI (server-only, no offline install);
online sync driver (done in Phase 29); the merge engine internals (done in
Phase 27); the central server hosting/token push-pull API (done in Phase 28).
Server-authoritative conflict resolution is already handled inside `apply_merge`
— this phase does not re-decide it.
</domain>

<decisions>
## Implementation Decisions

### File format & self-contained mechanism (Area 1 → OFF-02/OFF-03)
- **D-01:** The exported file is a **single self-contained HTML file** that
  **uploads itself via a `<form>` POST** (multipart) to the server — chosen over
  `fetch()` specifically to **avoid CORS entirely**: a top-level form-submit is a
  browser navigation the server accepts cross-origin without a preflight, so the
  online-sync API's CORS posture is never loosened (no `Access-Control-Allow-Origin: null`).
  The server responds by **rendering an HTML result page** the operator lands on
  (success/rejection). (Rejected: Option A `fetch()` → would require a dedicated
  `ACAO: null` endpoint; Option C plain `.ndjson` + server-hosted uploader page →
  not "self-uploading", spurns OFF-03's self-contained intent.)
- **D-02:** The payload is the **existing NDJSON exchange format**
  (`app/services/merge.py serialize_exchange` output — one header line carrying
  `format_version` + `schema_version`, one record per line), **embedded in the
  HTML inside a non-executed `<script type="application/x-ndjson">` block** and
  read back via `textContent` (avoids base64's +33% bloat and JSON-escaping
  hazards). The **only** escaping needed is a literal `</script>` → `<\/script>`.
  The offline export bundle = the FK-closure of unsynced ledger rows, exactly as
  the Phase 29 push body (D-13): `product`, `customer`, `batch`, `sale` in
  FK-dependency order, plus the `Operation` + `CashMovement` rows. Over-including
  reference rows is safe (server reference upsert is idempotent insert-if-new).

### Ingest endpoint & authentication (Area 2 → OFF-04/OFF-05)
- **D-03:** A **new dedicated endpoint pair** under a new `app/routes/offline.py`,
  NOT a reuse of `POST /api/sync/push` (which uses the per-device Bearer token —
  the wrong auth model for OFF-04, and a long-lived secret would have to be typed
  into a file on an untrusted computer):
  - `POST /api/offline/login` — takes **login + password**, verifies with the
    existing `app/services/auth.py verify_password` (Argon2id), and on success
    mints a **short-lived, upload-scoped signed token** (reuse the `itsdangerous`
    signer already in the stack). Wrong credentials → clear rejection message,
    **no data sent** (the payload is only transmitted in the second step).
  - `POST /api/offline/upload` — takes the short-lived token + the NDJSON payload,
    validates (D-06), then merges.
- **D-04:** This **two-step handshake is what satisfies OFF-04's "sends NO data
  on failure"** literally: credentials are checked first; the business data leaves
  the untrusted machine only after the server confirms the password. (Rejected:
  Option 2 single-shot creds+payload → transmits data regardless and discards
  server-side, violating "no data on failure"; Option 3 session cookie → `file://`
  `Origin: null` + `SameSite` break cross-origin cookies and widen attack surface.)
- **D-05:** **Auth is in the request body, so no CSRF/cookie machinery** — same
  reasoning already codified for the Bearer sync tree in `app/services/security.py`
  `auth_guard`. Add `/api/offline/` to the `auth_guard` bypass list (mirror the
  exact-prefix `SYNC_PATH_PREFIX` pattern — beware the same exact-prefix pitfall).
  A **single narrow CORS rule** for the offline routes (POST + form/JSON, **no**
  `Access-Control-Allow-Credentials`). Rate-limit `/api/offline/login` via the
  existing `check_rate_limit` to blunt brute force / limit a keylogger's window.
  The login token must be **short TTL** and **upload-scoped**.
- **OFF-05 (atomicity + idempotency) is NOT a differentiator and needs no new
  logic:** ingest through the **same `apply_merge`** (UUID insert-if-new = the
  idempotency mechanism; re-uploading inserts nothing), wrapped in the identical
  **single owned transaction** `sync_push` already uses
  (`session.rollback(); with session.begin(): apply_merge(...)`) so an interrupted
  upload rolls the whole batch back (all-or-nothing).

### Marking work as uploaded — no return channel (Area 3 → OFF-01)
- **D-07:** **Do NOT stamp `synced_at` from the offline path** (Option C, base).
  The offline client cannot observe upload success (the file is uploaded on a
  different computer), and the overriding project constraint is *never lose data*.
  Because the UUID merge is idempotent, **under-marking is cheap** (a bigger file
  + an inflated unsynced badge) while **over-marking loses data-visibility**
  (an optimistic stamp on a file that is lost/never uploaded silently drops those
  rows from the next export). The offline export therefore **only reads**; the
  `synced_at` marker is cleared **only by a future online sync**
  (`app/services/sync_client.py` already stamps `synced_at` **only after a 2xx**,
  UPDATE permitted by migration 0018). (Rejected here-and-now: Option A optimistic
  mark-on-export → data-loss risk; Option B receipt round-trip → correct but needs
  a second USB trip + import UI, and a single operator is likely to skip it.)
- **Known consequence (flag for planner + UAT):** for a **permanently** offline
  client, the unsynced-count badge (Phase 29 SYNC-07) stays **inflated
  indefinitely**, and re-exports keep re-including already-uploaded rows
  (harmless, just larger files). If UAT shows this genuinely confuses/discourages
  the operator, escalate to **Option B (receipt-import)** — noted in Deferred.
  The planner MAY add a **read-only UI hint** distinguishing "not yet uploaded
  (offline export)" without ever stamping `synced_at` on faith.

### File integrity & schema-version validation (Area 4 → OFF-07)
- **D-08:** **Integrity = plain SHA-256** of the NDJSON **payload** (stdlib
  `hashlib`, no new dependency), stored as a **new header field** (e.g.
  `payload_sha256`). It closes the one gap the existing pipeline misses — **silent
  in-string corruption that still parses as valid JSON** (a byte-flip inside a
  name/`code`/timestamp). Compute the digest over the **record lines only**
  (header excluded, in exact emission order) during serialization; **verify at the
  upload/route layer (or a thin wrapper) BEFORE `apply_merge`**, keeping pure
  `parse_exchange` and its round-trip tests intact. On mismatch → reject before
  touching the DB with a clear Russian message (e.g. «Файл повреждён, экспортируйте
  заново»). (Rejected: Option 3 HMAC → the file is **client-generated**, so there
  is no server-secret the client could sign with; HMAC buys a false sense of
  security + key-management cost for zero net gain against an authenticated
  operator. Option 1 no-checksum → silent value corruption merges undetected.)
- **D-09:** **Two distinct version gates, both checked before merge, distinct
  messages:**
  - `format_version` — **exact match, hard reject** (already enforced inside
    `parse_exchange`: `version != FORMAT_VERSION` → `ValueError`). Engine/wire
    compatibility; never loosen.
  - `schema_version` — **exact match** against
    `app/services/merge.py current_schema_version(session)` (the live Alembic
    head), enforced at the **OFF-07 upload layer, NOT inside pure `parse_exchange`**
    (`apply_merge` derives column sets from the live ORM models, so a `>= min`
    rule can't know which columns changed). Reject message names **both** versions
    (e.g. «Файл собран для версии данных X, сервер ожидает Y — обновите
    приложение»). **Empty server-side `schema_version` = skip the check** (test
    fixtures built via `create_all` have no `alembic_version` table — preserve
    current behavior; only enforce equality when the server reports a real revision).

### Preview & confirm (OFF-06)
- **D-10:** The **preview (counts of operations/records to be sent) is computed
  client-side in the self-uploading HTML file from the embedded NDJSON, BEFORE**
  the form is submitted, and requires an **explicit confirm click** (nothing is
  sent until confirmed). This is a natural fit for D-01/D-02 (the payload is
  already in the page). Exact wording/layout is planner discretion.

### Claude's Discretion
- Short-lived login-token TTL value and exact scope claim; the offline-token
  minter's internal shape (reuse `itsdangerous` signer).
- Exact `<script type="application/x-ndjson">` embedding details and the result-page
  HTML/wording (success, wrong-password, corrupted-file, incompatible-version).
- The new header field name for the checksum (suggested `payload_sha256`) and
  where the schema-version gate lives (route vs thin wrapper around `parse_exchange`).
- Whether/how to surface a read-only "offline-exported, not yet confirmed" UI hint
  (must never stamp `synced_at`).
- Preview counts wording/layout and the export-file naming/location on the USB drive.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` §Offline (OFF) — **OFF-01** (offline client keeps
  accumulating unsynced work), **OFF-02** (export to a single self-contained USB
  file, offline), **OFF-03** (no install; opens in a browser; uploads itself),
  **OFF-04** (login+password auth, wrong cred rejected clearly, no data sent),
  **OFF-05** (same idempotent UUID merge, twice = nothing, all-or-nothing),
  **OFF-06** (preview counts + explicit confirm), **OFF-07** (integrity checksum +
  schema-version validation, reject tampered/incompatible clearly).
- `.planning/ROADMAP.md` — Phase 30 line ("Upload-only USB path: export
  not-yet-uploaded work to a self-contained file that authenticates, previews,
  and uploads itself through the same merge engine").

### Merge engine & exchange format (reuse verbatim — the ingest is a thin caller)
- `app/services/merge.py` — `serialize_exchange` (NDJSON header + records; the
  export payload), `parse_exchange` (strict validation, `format_version` exact-match
  reject), `apply_merge(session, batch, *, server_now)` (pure, idempotent UUID
  insert-if-new + server-wins reference upsert), `current_schema_version(session)`
  (the schema-version gate reference for D-09).
- `app/routes/sync.py:66-133` — `sync_push`: the **transaction-ownership /
  all-or-nothing pattern to copy** (`session.rollback(); with session.begin(): ...`)
  and the rate-limit idiom.

### Client export payload (reuse the Phase 29 FK-closure collector)
- `app/services/sync_client.py` — the outbound driver: `synced_at IS NULL`
  selection of unsynced `Operation` + `CashMovement`, and the `synced_at`
  stamping **only after 2xx** (line ~377) that D-07 relies on for self-healing.
- `app/services/sync.py` — `collect_reference_records` (the FK-closure collector,
  D-13) and the locked `synced_at` semantics ("server never writes `synced_at`";
  NULL = "never pushed from here").
- `.planning/phases/29-online-client-sync/29-CONTEXT.md` — **D-13** (FK-closure
  push body) and **D-11** (unsynced badge = `COUNT(*) WHERE synced_at IS NULL`),
  which Phase 30's export mirrors and whose badge D-07 leaves inflated.

### Auth & security stack (reuse; add the offline bypass)
- `app/services/auth.py` — `verify_password` (Argon2id), used by `/api/offline/login`.
- `app/routes/auth.py:51` — `login_submit` credential-check idiom to mirror.
- `app/services/security.py` — `auth_guard`, the `SYNC_PATH_PREFIX` bypass pattern
  to mirror for `/api/offline/` (exact-prefix pitfall), `require_csrf` (NOT needed
  for the in-body-auth offline routes, D-05).
- `app/services/devices.py` — per-device identity (context only; the offline path
  uses login+password, not the device token).

### Migrations
- `alembic/` (`env.py` with `render_as_batch=True`) — if any schema change is
  needed it must run on **SQLite AND PostgreSQL** under the single shared history
  (SRV-01). Note: migration **0018** already permits `SET synced_at`; the offline
  path adds NO new `synced_at` writes (D-07), so likely **no new migration** is
  required — confirm during planning.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Merge engine (`apply_merge`) + NDJSON (`serialize_exchange`/`parse_exchange`)**
  — pure, idempotent, already the single wire schema. The offline export writes
  `serialize_exchange` output; the server ingest is a thin caller of `apply_merge`,
  exactly like `sync_push`. No second merge implementation.
- **FK-closure collector (`collect_reference_records`, Phase 29 D-13)** — builds
  the transitive FK closure of unsynced ledger rows; the offline export bundle
  reuses it verbatim.
- **Argon2id login (`verify_password`) + `itsdangerous` signer** — the offline
  login endpoint reuses both; no new auth crypto.
- **`sync_push` transaction pattern** — copy for all-or-nothing ingest.
- **Rate limiter (`check_rate_limit`)** — apply to `/api/offline/login`.

### Established Patterns
- Sync `def` endpoints + sync SQLAlchemy `Session` in the FastAPI threadpool
  (no async DB).
- Single shared Alembic history runs on SQLite + PostgreSQL (SRV-01); any new
  column/table must be portable.
- `synced_at` is a **client-local** marker the server never writes; the client
  stamps it only after a confirmed 2xx push.
- In-body-auth routes bypass CSRF (Bearer sync tree precedent in `auth_guard`).
- Money as integer minor units; append-only ledger; caches recomputed inside
  `apply_merge` server-side.

### Integration Points
- New `app/routes/offline.py` (`POST /api/offline/login`, `POST /api/offline/upload`)
  → `auth_guard` bypass list + narrow CORS rule.
- Offline export (new service/route on the desktop client) → `serialize_exchange`
  + `collect_reference_records` → writes the self-contained HTML file to USB.
- Self-uploading HTML template (embedded NDJSON + login form + client-side preview
  + form-POST) → `/api/offline/login` then `/api/offline/upload`.
- Server ingest → SHA-256 verify + schema-version gate → `apply_merge` in one
  owned transaction → rendered HTML result page.

</code_context>

<specifics>
## Specific Ideas

- Reuse the existing NDJSON exchange verbatim as the payload — do not invent a new
  format.
- Avoid CORS entirely via form-POST navigation rather than `fetch()` (D-01) — the
  online-sync API's CORS posture must stay untouched.
- Embed NDJSON in `<script type="application/x-ndjson">` (not base64) — only escape
  a literal `</script>`.
- Concrete Russian rejection messages: corrupted file «Файл повреждён,
  экспортируйте заново»; incompatible version «Файл собран для версии данных X,
  сервер ожидает Y — обновите приложение».

</specifics>

<deferred>
## Deferred Ideas

- **Receipt-file round-trip (Option B for OFF-01 marking)** — the server emits a
  receipt of acknowledged UUIDs; the operator carries it back on the USB and
  imports it to stamp `synced_at`. Considered and NOT chosen for Phase 30 (needs a
  second USB trip + an import UI; a single operator is likely to skip it). Revisit
  **only if UAT shows the permanently-inflated unsynced badge genuinely confuses or
  discourages the operator.**
- **Optimistic mark-on-export (Option A)** — rejected outright (data-loss risk),
  not deferred; recorded so it is not re-proposed.
- **HMAC-signed files** — rejected (client-generated file has no server secret to
  sign with); recorded so it is not re-proposed.
- **`fetch()`-based uploader with a dedicated `ACAO: null` endpoint (Option A,
  Area 1)** — viable only if the UI must read the server's structured merge report
  in-page; not chosen. Revisit only if the rendered-result-page UX proves
  insufficient.
- **Compression of the export file** — out of scope; only consider if file size
  becomes a real problem, and never adopt it *for* integrity.
- **Any PULL / two-way sync over the USB path** — explicitly out of scope
  (offline path is upload-only).

None beyond the above — discussion stayed within phase scope.

</deferred>

---

*Phase: 30-offline-self-uploading-file*
*Context gathered: 2026-07-20*
