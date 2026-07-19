# Phase 28: Central Server — Hosting & Sync API - Research

**Researched:** 2026-07-19
**Domain:** FastAPI sync API + per-device token auth + portable DB trigger relaxation + VPS deployment
**Confidence:** HIGH (codebase claims verified by reading; trigger SQL verified by execution on SQLite 3.45.1 and postgres:17)

## Summary

Phase 28 is smaller than it looks, because three of its four pillars are already built. The **mobile UI already exists and ships** — 13 `mobile_*` routers serving a `/m/...` route tree, a standalone `mobile_base.html`, 13 `mobile_pages/` and 40 `mobile_partials/` templates. SRV-04 therefore needs **no new UI work**; it needs the existing two-UI app *hosted* on the VPS and a written constraint that the mobile tree is server-only. The **merge engine is done** — `parse_exchange()` / `apply_merge()` / `serialize_exchange()` in `app/services/merge.py` are pure, non-committing, idempotent, and proven on both dialects. And the **`synced_at` column already exists** on both ledger tables (`String(32)`, nullable, migrations `0001` line 97 and `0013` line 80) — no `add_column` is needed.

That leaves the genuinely new work: (1) a **new Alembic migration `0018`** that drops and re-creates the four append-only triggers with a value-based `WHEN` guard, (2) two **NDJSON HTTP endpoints** that are thin callers of the merge engine, (3) a **device-token table + Bearer dependency** that must coexist with the app-level `auth_guard`, and (4) **deployment**. The highest-risk item — the trigger relaxation — I resolved empirically rather than by assumption, and found a trap the roadmap did not anticipate: PostgreSQL's `json` type **has no equality operator**, so a naive `NEW.payload IS DISTINCT FROM OLD.payload` in the trigger `WHEN` clause fails with `operator does not exist: json = json`. `Operation.payload` is a `sa.JSON` column, so the PG trigger must cast: `NEW.payload::text IS DISTINCT FROM OLD.payload::text`.

Also corrected from the phase brief: Phase 25 uses **`argon2-cffi==25.1.*`** (`app/services/auth.py` wraps `argon2.PasswordHasher`), **not `pwdlib[argon2]`**. And contrary to the brief's premise, **SQLite does support both `UPDATE OF <col-list>` and `WHEN` clauses on triggers** — the two dialects are closer than assumed, and one dialect-branched migration handles both cleanly using the existing `op.get_bind().dialect.name` pattern from `26-02`.

**Primary recommendation:** Relax the triggers with a **value-based `WHEN` guard enumerating every immutable column** (not `UPDATE OF`), because it permits a no-op self-assignment and blocks actual tampering; back the enumeration with a schema-derived test that asserts the list equals `model.__mapper__.columns` minus `synced_at`, mirroring Phase 27's schema-derived money-field guard. Add **zero new Python packages** — `secrets` + `hashlib` from stdlib cover device tokens.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Append-only enforcement + `synced_at` relaxation | Database (triggers) | — | The guarantee must survive a compromised app process; it is a DB-level invariant today and must stay one |
| `synced_at` cursor stamping | Client app (Phase 29) | Server app | The *client* stamps its own rows after a successful push; this is why the SQLite relaxation matters most |
| NDJSON parse + validation | API / Backend (`merge.parse_exchange`) | — | Already pure and schema-derived; the route must not re-validate |
| Merge / idempotency / conflict resolution | API / Backend (`merge.apply_merge`) | Database (FK + unique backstops) | Phase 27 owns this; Phase 28 must not reimplement any of it |
| Transaction boundary (all-or-nothing) | API route handler | — | `apply_merge` explicitly never commits — the caller owns the transaction |
| Device-token authentication | API / Backend dependency | Database (token hash table) | Bearer header, server-side lookup by non-secret prefix |
| Browser session authentication | API / Backend (`auth_guard` + SessionMiddleware) | — | Already exists; must not be bypassed by, nor bypass, the token path |
| Desktop UI + Mobile UI rendering | Frontend Server (Jinja2 SSR) | Browser (htmx) | Both already built; Phase 28 only hosts them |
| TLS termination | Reverse proxy (Caddy) | — | Never terminate TLS in uvicorn |
| Process supervision + restart | OS (systemd) | — | Standard, zero-dependency |

## Standard Stack

### Core

**No new Python packages are required for this phase.** Every capability maps to something already in `pyproject.toml` or the standard library.

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | `0.139.*` (installed) | Sync endpoints, `Security()` dependency | Already the app framework [VERIFIED: pyproject.toml] |
| `sqlalchemy` | `2.0.*` (installed) | ORM, portable constructs | Already in use [VERIFIED: pyproject.toml] |
| `alembic` | `1.18.*` (installed) | Migration `0018` for trigger DDL | Already in use; head is `0017` [VERIFIED: alembic/versions/0017_users_and_author_id.py] |
| `psycopg[binary]` | `3.3.*` (installed) | PostgreSQL driver on the server | Added in Phase 26 [VERIFIED: pyproject.toml] |
| `uvicorn[standard]` | `0.51.*` (installed) | ASGI server | Already in use [VERIFIED: pyproject.toml] |
| `secrets` | stdlib | `token_urlsafe(32)` device-token generation | Stdlib CSPRNG; already used for CSRF tokens in `security.issue_csrf` [VERIFIED: app/services/security.py] |
| `hashlib` | stdlib | SHA-256 of the device token for at-rest storage | Correct choice for a high-entropy secret (see Pattern 3 rationale) |
| `hmac` | stdlib | `compare_digest` constant-time compare | Already wrapped as `auth.compare_token()` [VERIFIED: app/services/auth.py] |

### Supporting (deployment, not Python packages)

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| Caddy | 2.x | Reverse proxy + automatic TLS | Recommended default — a two-line Caddyfile obtains and renews certs with no cron, no certbot [CITED: caddyserver.com/docs/caddyfile/patterns] |
| systemd | OS-provided | Process supervision, restart-on-failure, boot start | Standard on any Debian/Ubuntu VPS; zero extra dependency |
| PostgreSQL | 17 | Server database | Matches the CI image already pinned in `.github/workflows/ci.yml` [VERIFIED: ci.yml uses `postgres:17`] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Caddy | nginx + certbot | nginx is more widely known but needs a separate ACME client, a renewal timer, and manual reload wiring. Caddy is one binary and one config block for a single-domain app. Choose nginx only if the VPS already runs it. |
| Value-based `WHEN` trigger | `BEFORE UPDATE OF <col-list>` | Both dialects support `UPDATE OF`. But it fires on columns *mentioned* in the SET clause even when the value is unchanged, and it silently fails open for any column added later without also updating the list. The value-based `WHEN` has the same maintenance need but fails **closed** semantically (it compares actual values) — prefer it. |
| Value-based `WHEN` trigger | Application-level "only update synced_at" discipline | Rejected outright: the entire point of the DB trigger is that it survives an app bug or a compromised process. |
| stdlib token auth | `fastapi-users`, `authlib`, `python-jose` JWT | All are large dependencies solving federated/multi-tenant problems this app does not have. A per-device opaque bearer token in one table is ~40 lines and has no key-rotation or algorithm-confusion failure modes. |
| In-process rate limiter | `slowapi` | `slowapi` is a real option, but a single-reseller app with a handful of devices does not need Redis-backed distributed limits. See Open Question OQ-4. |
| systemd | Docker Compose | CLAUDE.md rejects Docker for the local client; on the server it is defensible but adds a runtime for one process. systemd is proportional. |

**Installation:** none. If a rate limiter is chosen (OQ-4), that is the only candidate new dependency.

### Version verification

No new packages recommended, so no registry lookups were required. Installed versions were read from `pyproject.toml` [VERIFIED: E:\dev\myorishop\pyproject.toml].

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| — | — | — | — | — | — | No new packages proposed |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

This phase adds no external dependency. If Open Question OQ-4 resolves toward a library rate limiter, `slowapi` must be run through the legitimacy gate at plan time before it is added.

## Architecture Patterns

### System Architecture Diagram

```
                        ┌──────────────────────── VPS (internet-facing) ─────────────────────────┐
                        │                                                                        │
 Desktop browser ──HTTPS─┤                                                                       │
 (admin/operator)        │   ┌────────┐        ┌──────────────── FastAPI app (app/main.py) ────┐ │
                         │   │ Caddy  │        │                                               │ │
 Mobile browser ──HTTPS──┤──▶│ :443   │──HTTP─▶│  SessionMiddleware (cookie, https_only=True)  │ │
 (server-only, /m/*)     │   │  auto  │  :8000 │                │                              │ │
                         │   │  TLS   │  loop- │                ▼                              │ │
 Desktop client ──HTTPS──┤   └────────┘  back  │      app-level Depends(auth_guard)            │ │
 (Phase 29 sync)         │                     │       │                    │                  │ │
                         │                     │       │ path in            │ else             │ │
 Self-upload file ──HTTPS┤                     │       │ SYNC_PATHS?        │                  │ │
 (Phase 30, OFF-03)      │                     │       ▼                    ▼                  │ │
                         │                     │  ┌──────────┐      ┌──────────────┐           │ │
                         │                     │  │ return   │      │ session +    │           │ │
                         │                     │  │ early    │      │ CSRF + role  │           │ │
                         │                     │  │ (no      │      │ checks       │           │ │
                         │                     │  │ cookie)  │      └──────┬───────┘           │ │
                         │                     │  └────┬─────┘             │                   │ │
                         │                     │       ▼                   ▼                   │ │
                         │                     │  ┌──────────────┐   ┌──────────────────────┐  │ │
                         │                     │  │ require_     │   │ 33 HTML routers      │  │ │
                         │                     │  │ device()     │   │ ├─ desktop  (/...)   │  │ │
                         │                     │  │ Bearer token │   │ └─ mobile   (/m/...) │  │ │
                         │                     │  └──────┬───────┘   └──────────┬───────────┘  │ │
                         │                     │         │                      │              │ │
                         │                     │  ┌──────▼──────────────┐       │              │ │
                         │                     │  │ POST /api/sync/push │       │              │ │
                         │                     │  │  parse_exchange()   │       │              │ │
                         │                     │  │  with session.begin()│      │              │ │
                         │                     │  │    apply_merge()  ───┼──┐   │              │ │
                         │                     │  │  → MergeReport JSON │  │   │              │ │
                         │                     │  ├─────────────────────┤  │   │              │ │
                         │                     │  │ GET /api/sync/pull  │  │   │              │ │
                         │                     │  │  updated_at cursor  │  │   │              │ │
                         │                     │  │  serialize_exchange()│ │   │              │ │
                         │                     │  └─────────────────────┘  │   │              │ │
                         │                     └───────────────────────────┼───┼──────────────┘ │
                         │                                                 ▼   ▼                │
                         │                              ┌──────────────────────────────────┐    │
                         │                              │ PostgreSQL 17 (localhost only)   │    │
                         │                              │  operations / cash_movements     │    │
                         │                              │   └ trigger *_no_update  (WHEN   │    │
                         │                              │       any immutable col differs) │    │
                         │                              │   └ trigger *_no_delete (always) │    │
                         │                              │  reference tables (updated_at)   │    │
                         │                              │  device_tokens                   │    │
                         │                              └──────────────────────────────────┘    │
                         └────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

Additive only — no existing file is restructured.

```
app/
├── routes/
│   └── sync.py             # NEW: POST /api/sync/push, GET /api/sync/pull
├── services/
│   ├── devices.py          # NEW: token mint/hash/lookup/revoke (fat-service convention)
│   ├── sync.py             # NEW: pull-cursor query + record assembly (no HTTP)
│   ├── merge.py            # UNCHANGED — Phase 27, already complete
│   └── security.py         # EDIT: add SYNC_PATHS bypass branch to auth_guard
├── models.py               # EDIT: add DeviceToken model
alembic/versions/
├── 0018_sync_cursor_trigger_relaxation.py   # NEW: drop+recreate 4 triggers, both dialects
└── 0019_device_tokens.py                    # NEW: device_tokens table
deploy/                     # NEW (docs + config, not executed by the app)
├── myorishop.service       # systemd unit
├── Caddyfile               # reverse proxy + auto TLS
└── DEPLOY.md               # runbook
tests/
├── test_sync_api.py        # NEW: push/pull, token auth, idempotency
├── test_devices.py         # NEW: token service unit tests
├── test_append_only_cursor.py  # NEW: SQLite trigger relaxation
└── test_pg_parity.py       # EDIT: add PG trigger-relaxation cases
```

### Pattern 1: Column-scoped append-only relaxation (highest-risk item)

**What:** Replace the four unconditional `BEFORE UPDATE` triggers with `BEFORE UPDATE ... WHEN <any immutable column value differs>`. The `DELETE` triggers are untouched — deletion stays unconditionally blocked.

**Why value-based `WHEN`, not `UPDATE OF`:** Both engines support `UPDATE OF`, but it fires on *mention* in the SET clause. A value-based `WHEN` permits the harmless `SET synced_at=..., qty_delta=qty_delta` and rejects any real change. It expresses the actual invariant.

**Null-safety, per dialect:** SQLite has no `IS DISTINCT FROM` before 3.39; use the universally-supported null-safe `IS NOT`. PostgreSQL uses `IS DISTINCT FROM`. Both were executed and confirmed.

**The PG JSON trap:** `Operation.payload` is `sa.JSON()` [VERIFIED: alembic/versions/0001_initial_schema.py line 94, `sa.Column("payload", sa.JSON(), nullable=True)`]. On PostgreSQL this maps to `json`, which **has no equality operator**. Verified by execution:

```
NOTICE:  JSON compare FAILED: operator does not exist: json = json
```
[VERIFIED: executed against postgres:17 in this session]

The PG trigger must therefore cast `payload` to `text`. `CashMovement` has no JSON column and needs no cast.

**Exact SQLite DDL** (verified executing on SQLite 3.45.1 — stamp allowed, all four tamper attempts blocked):

```sql
CREATE TRIGGER operations_no_update
BEFORE UPDATE ON operations
FOR EACH ROW WHEN
     NEW.id               IS NOT OLD.id
  OR NEW.type             IS NOT OLD.type
  OR NEW.product_id       IS NOT OLD.product_id
  OR NEW.qty_delta        IS NOT OLD.qty_delta
  OR NEW.unit_cost_cents  IS NOT OLD.unit_cost_cents
  OR NEW.unit_price_cents IS NOT OLD.unit_price_cents
  OR NEW.payload          IS NOT OLD.payload
  OR NEW.sale_id          IS NOT OLD.sale_id
  OR NEW.batch_id         IS NOT OLD.batch_id
  OR NEW.author_id        IS NOT OLD.author_id
  OR NEW.device_id        IS NOT OLD.device_id
  OR NEW.seq              IS NOT OLD.seq
  OR NEW.created_at       IS NOT OLD.created_at
  OR NEW.created_by       IS NOT OLD.created_by
BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
```

**Exact PostgreSQL DDL** (verified executing on postgres:17 — stamp allowed, all five tamper attempts blocked). The trigger *function* `operations_append_only()` created by migration `0001` is reused unchanged; only the trigger is dropped and re-created with the `WHEN`:

```sql
DROP TRIGGER IF EXISTS operations_no_update ON operations;

CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
FOR EACH ROW WHEN (
     NEW.id               IS DISTINCT FROM OLD.id
  OR NEW.type             IS DISTINCT FROM OLD.type
  OR NEW.product_id       IS DISTINCT FROM OLD.product_id
  OR NEW.qty_delta        IS DISTINCT FROM OLD.qty_delta
  OR NEW.unit_cost_cents  IS DISTINCT FROM OLD.unit_cost_cents
  OR NEW.unit_price_cents IS DISTINCT FROM OLD.unit_price_cents
  OR NEW.payload::text    IS DISTINCT FROM OLD.payload::text
  OR NEW.sale_id          IS DISTINCT FROM OLD.sale_id
  OR NEW.batch_id         IS DISTINCT FROM OLD.batch_id
  OR NEW.author_id        IS DISTINCT FROM OLD.author_id
  OR NEW.device_id        IS DISTINCT FROM OLD.device_id
  OR NEW.seq              IS DISTINCT FROM OLD.seq
  OR NEW.created_at       IS DISTINCT FROM OLD.created_at
  OR NEW.created_by       IS DISTINCT FROM OLD.created_by
) EXECUTE FUNCTION operations_append_only();
```

`cash_movements` gets the identical treatment over its ten immutable columns (`id, category, amount_cents, note, sale_id, author_id, device_id, seq, created_at, created_by`), reusing `cash_movements_append_only()`, message `'cash ledger is append-only'`.

**How one migration emits both** — reuse the exact `26-02` pattern already frozen in the repo:

```python
def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_RELAXED_DDL:
            op.execute(stmt)
    else:  # sqlite
        for stmt in _SQLITE_RELAXED_DDL:
            op.execute(stmt)
```

Each branch first drops with the dialect-correct grammar — PG requires `DROP TRIGGER name ON table`, SQLite forbids the `ON` clause (this exact difference was already fixed as CR-01 in Phase 26) [VERIFIED: alembic/versions/0001_initial_schema.py `downgrade()`].

**Three non-obvious obligations:**

1. `app/db.py` `APPEND_ONLY_TRIGGERS` is the **live source for test fixtures** and its docstring already predicts this phase verbatim: *"the v2 sync milestone relaxes the UPDATE trigger with a WHEN clause in a NEW migration — never edit this constant's DDL semantics in place without also adding that migration."* [VERIFIED: app/db.py lines 16-20]. `tests/conftest.py` builds every test DB from this constant, **not** from Alembic [VERIFIED: tests/conftest.py `engine` fixture]. So the constant and migration `0018` must be updated together or the whole suite tests the old triggers.
2. Migration `0018` must be a **new** migration, not an edit to `0001`/`0013` — the frozen-migration rule (WR-06) is stated in `0001`'s module docstring.
3. `synced_at` **already exists** on both tables — `sa.Column("synced_at", sa.String(32), nullable=True)` in `0001` (operations) and `0013` (cash_movements), and `Mapped[str | None] = mapped_column(String(32))` at `app/models.py:374` and `:503` [VERIFIED]. **No `add_column` is needed.**

### Pattern 2: Sync endpoints as thin callers of the Phase 27 engine

The merge engine's real signatures [VERIFIED: app/services/merge.py]:

```python
FORMAT_VERSION: int = 1
def parse_exchange(lines: Iterable[str]) -> ExchangeBatch
def apply_merge(session: Session, batch: ExchangeBatch, *, server_now: str) -> MergeReport
def serialize_exchange(records, *, schema_version, source_device_id, generated_at) -> Iterator[str]
```

`apply_merge` **never commits** — its docstring states the caller wraps the whole call in one transaction so a mid-batch failure rolls back all-or-nothing. The route must therefore own the transaction explicitly.

**Push handler shape:**

```python
# app/routes/sync.py
@router.post("/api/sync/push")
async def sync_push(
    request: Request,
    device: DeviceToken = Depends(require_device),
    session: Session = Depends(get_session),
):
    raw = await request.body()                 # size-capped — see Pitfall 5
    lines = raw.decode("utf-8").splitlines()
    batch = parse_exchange(lines)              # validates BEFORE any DB touch
    with session.begin():                      # caller owns the transaction
        report = apply_merge(session, batch, server_now=utcnow_iso())
    return {
        "operations_inserted": report.operations_inserted,
        "operations_skipped":  report.operations_skipped,
        "cash_inserted":       report.cash_inserted,
        "cash_skipped":        report.cash_skipped,
        "reference_inserted":  report.reference_inserted,
        "conflicts": [dataclasses.asdict(c) for c in report.conflicts],
    }
```

Note the endpoint is `async def` but calls sync SQLAlchemy. **Prefer `def` (not `async def`)** so FastAPI runs it in the threadpool, per CLAUDE.md's locked "sync sessions + `def` endpoints" rule — read the body via a plain `bytes = Body(...)` parameter rather than `await request.body()` to keep the handler synchronous.

**Payload format:** NDJSON, header line first, per-line `kind` — confirmed from the code, not assumed [VERIFIED: `serialize_exchange` yields the header envelope then one `{"kind": ..., **data}` line per record]. Use `Content-Type: application/x-ndjson`.

**Idempotency:** already guaranteed by the engine. `_insert_new` does a portable pre-select set-difference by UUID. A re-push of an already-ingested batch returns **HTTP 200** with `operations_inserted == 0` and `operations_skipped == N`. Do **not** invent a separate batch-id dedupe table — the UUID replay *is* the idempotency mechanism (SYNC-02).

**Pull cursor semantics:** every reference model carries `updated_at` **except `Sale`**, which has only `created_at` [VERIFIED: read from app/models.py]. So:

- `GET /api/sync/pull?since=<iso8601>&limit=<n>` returns NDJSON built by `serialize_exchange`.
- Cursor column: `updated_at` for warehouse/product/customer/dictionary/batch; `created_at` for sale.
- Order by the cursor column, then by `id` as a stable tiebreak (ISO-8601 text sorts lexicographically = chronologically, and duplicate timestamps are likely in a batch write).
- Return `next_since` in the header line's envelope; the client re-requests until fewer than `limit` records come back.
- **Use `>=` on the cursor, not `>`**, and rely on the client's server-wins upsert to absorb the overlap. A strict `>` silently drops any row sharing the boundary timestamp.
- Pull sends **reference data only** — never ledger rows. The offline path is upload-only and SYNC-01 specifies "pulling server-authoritative reference data down."

**`schema_version` in the header:** derive from the live Alembic revision rather than hardcoding, e.g. `MigrationContext.configure(connection).get_current_revision()`. Phase 30's OFF-07 gate depends on this being truthful.

### Pattern 3: Per-device token auth (SYNC-09)

**New table, not a reuse of `User`.** `User` models a *human* with a password, role, and `is_active` [VERIFIED: app/models.py:506-529]. A device token is a different lifetime and a different revocation story. Model it separately:

```python
class DeviceToken(Base):
    __tablename__ = "device_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)   # "Ноутбук Ольги"
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False, index=True, unique=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 hex
    user_id: Mapped[str | None] = mapped_column(String(36))  # FK users.id — attribution
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    last_used_at: Mapped[str | None] = mapped_column(String(32))
    revoked_at: Mapped[str | None] = mapped_column(String(32))
```

**Generation:** `secrets.token_urlsafe(32)` — 256 bits of CSPRNG entropy. The plaintext is shown to the operator **exactly once** at creation and never stored or logged (CLAUDE.md safety rule).

**Which hasher — and this is the one place to deliberately *not* reuse Argon2.** `argon2-cffi` is correct for passwords because passwords are low-entropy and need a deliberately slow KDF. A `token_urlsafe(32)` value has 256 bits of entropy; brute-forcing it is infeasible regardless of hash speed, so the KDF's slowness buys nothing and instead adds ~50-100 ms of CPU to *every single sync request*. Use **`hashlib.sha256`**. This is the same reasoning GitHub and Django apply to API tokens. [ASSUMED — the reasoning is standard practice, but it is a deliberate divergence from the project's Argon2 convention and should be called out in the plan so it reads as intentional, not as an oversight.]

**Constant-time lookup without hashing every row** — the prefix trick:

```
token = "myos_" + secrets.token_urlsafe(32)
token_prefix = token[:12]        # NOT secret — just an index key
token_hash   = hashlib.sha256(token.encode()).hexdigest()
```

Verification is a single indexed `SELECT ... WHERE token_prefix = ? AND is_active = 1`, then `hmac.compare_digest(sha256(presented), row.token_hash)` — one row read, one constant-time compare, no table scan, no per-row hashing. Reuse the existing `auth.compare_token()` wrapper.

**Transport:** `Authorization: Bearer <token>`. Never a query parameter — query strings land in proxy access logs and browser history.

**The dependency:**

```python
# app/services/devices.py
_bearer = HTTPBearer(auto_error=False)

def require_device(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
    session: Session = Depends(get_session),
) -> DeviceToken:
    if credentials is None:
        raise HTTPException(401, "Требуется токен устройства.",
                            headers={"WWW-Authenticate": "Bearer"})
    device = lookup_active_token(session, credentials.credentials)
    if device is None:
        raise HTTPException(401, "Недействительный токен устройства.",
                            headers={"WWW-Authenticate": "Bearer"})
    return device
```

**Coexistence with the browser session guard — the critical wiring detail.** `app/main.py` registers a **single app-level** `dependencies=[Depends(auth_guard)]` that runs on *every* router [VERIFIED: app/main.py]. Left alone it would break the sync endpoints two ways: (a) with no session cookie it raises `NotAuthenticated` → 303 to `/login`; (b) `POST` is not in `("GET","HEAD","OPTIONS")`, so it calls `require_csrf` and returns 403 — a client that has no session cannot possibly hold a CSRF token.

`auth_guard` already has the exact seam for this: `PUBLIC_PATHS = {"/login", "/logout", "/setup"}` checked as `if request.url.path in PUBLIC_PATHS: return` [VERIFIED: app/services/security.py]. Add a **prefix-matched** sibling — an exact-match set is wrong here because `/api/sync/pull` may carry a path or the tree may grow:

```python
SYNC_PATH_PREFIX = "/api/sync/"

# inside auth_guard, immediately after the PUBLIC_PATHS check:
if request.url.path.startswith(SYNC_PATH_PREFIX):
    return   # token-authenticated tree — require_device() guards it per-route
```

This returns *before* the session check and *before* `require_csrf`, which is correct: CSRF protection is meaningless for a Bearer-authenticated endpoint (the browser never attaches a Bearer header automatically — that is precisely why bearer tokens are not CSRF-vulnerable), and harmful here because it would block every legitimate client.

**Neither path can bypass the other.** A browser cookie grants nothing on `/api/sync/*` because `require_device` reads only the `Authorization` header and ignores session state. A device token grants nothing on the HTML tree because `auth_guard` returns early only for the `/api/sync/` prefix and otherwise still demands `request.session["user_id"]`. **The plan must include an explicit negative test for each direction** — this early-return is the single highest-consequence line of code in the phase, and a mistyped prefix (e.g. `/api/` instead of `/api/sync/`) would silently open a hole.

**Revocation:** set `is_active = 0` and stamp `revoked_at`. Never hard-delete — this mirrors the `User` soft-disable convention. Surface mint/list/revoke on the existing admin-only `/settings` tree via `require_role("administrator")`.

### Pattern 4: Two UIs on one server (SRV-04)

**This is already built.** Verified in the repo:

- 13 mobile routers registered in `app/main.py` (`mobile_home`, `mobile_sales`, `mobile_receipts`, `mobile_search`, `mobile_writeoff`, `mobile_corrections`, `mobile_products`, `mobile_customers`, `mobile_transfers`, `mobile_returns`, `mobile_history`, `mobile_reports`, `mobile_finance`)
- Routes are declared with a literal `/m/` prefix on each decorator, e.g. `@router.get("/m/")`, `@router.get("/m/sales")` — the routers themselves are bare `APIRouter()` with no `prefix=` [VERIFIED: app/routes/mobile_home.py:20, app/routes/mobile_sales.py]
- A standalone `mobile_base.html` that deliberately does **not** inherit from `base.html` (its comments document three tags duplicated verbatim for that reason)
- Template counts: `pages/` 32, `partials/` 67, `mobile_pages/` 13, `mobile_partials/` 40

**Recommendation: keep the separate `/m` route tree. Do not refactor toward responsive-single-template or server-side device detection.** The comparison, in terms of this codebase specifically:

| Option | Cost here | Verdict |
|--------|-----------|---------|
| Separate `/m` tree (status quo) | Already shipped and tested across 14 `test_mobile_*.py` files. Duplication is real (53 mobile templates alongside 99 desktop) but it is *paid-for, working* duplication. | **Recommended** |
| Responsive single template set + CSS breakpoints | Would require merging 152 templates into one set and rewriting 14 mobile test modules. The two UIs are not merely restyled — the mobile sale flow is a multi-step wizard (`/m/sales/step/product`, `/step/batch`, `/step/qty-price`, `/step/basket-add`) with no desktop equivalent. CSS cannot express a different interaction model. | Rejected — a rewrite disguised as a refactor |
| Server-side device detection (User-Agent → serve mobile) | Adds UA-sniffing fragility and makes URLs non-shareable/non-bookmarkable; the operator loses the ability to force either UI. | Rejected |

**What "mobile UI is server-only" actually constrains in code** — it is a *deployment and packaging* constraint, not a runtime one. Concretely:

1. `run.bat` (the local desktop launcher) must not be presented as a mobile entry point; it binds `127.0.0.1` [VERIFIED: run.bat `uvicorn app.main:app --host 127.0.0.1 --port 8000`], so the mobile tree is unreachable from a phone on the same LAN by construction. **Leave this binding alone** — do not "helpfully" change it to `0.0.0.0`.
2. There is no mobile installer, no service worker, no offline cache, no local mobile DB. Phase 30's offline path is explicitly desktop-only (OFF-01 says "the local desktop client").
3. The same `app/main.py` serves both trees on the VPS; no second process, no second app object. Hosting the app *is* the SRV-04 deliverable.
4. The plan should assert this with a **documentation + test artifact**, not new UI code: a smoke test that `/m/` and `/` both render 200 for an authenticated user against the same app, plus a line in `DEPLOY.md`.

### Anti-Patterns to Avoid

- **Reimplementing any merge logic in the route.** `parse_exchange` already rejects malformed lines, bad `format_version`, unknown kinds, a missing header, and float money *before any DB touch*, and forces `synced_at → None`. A route that re-validates will drift from the engine and violate SYNC-04's "never two divergent implementations."
- **Calling `session.commit()` inside the push handler body.** `apply_merge` deliberately does not commit. Use `with session.begin():` so a poisoned record rolls the whole batch back.
- **Trusting `synced_at` from the wire.** Already defended in `_ledger_row` (`row["synced_at"] = None`) — do not add a route-level path that re-introduces it.
- **Editing migrations `0001` or `0013` in place.** WR-06. New migration only.
- **Updating `db.APPEND_ONLY_TRIGGERS` without migration `0018`, or vice versa.** The fixtures and the real schema would test different things.
- **Adding the sync router before the `auth_guard` bypass.** Every sync test will 303-redirect to `/login` and the cause is non-obvious.
- **`0.0.0.0` binding on the VPS uvicorn.** Bind `127.0.0.1:8000` and let Caddy be the only internet-facing listener.
- **Terminating TLS in uvicorn.** Use the proxy.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Idempotent UUID merge | A batch-id dedupe table or "already seen" cache | `merge.apply_merge` | Already portable, proven on both dialects, and re-merge is byte-identical (27-02/27-04) |
| NDJSON validation | Per-route Pydantic models for 8 record kinds | `merge.parse_exchange` | Schema-derived from `model.__mapper__.columns` — cannot drift from the schema |
| Stock/cash recompute after merge | A route-level recalculation | `ledger.recompute_derived` (called inside `apply_merge`) | Asserts the invariant and raises on inconsistency |
| Constant-time secret compare | `==` on token strings | `auth.compare_token` (`hmac.compare_digest`) | Timing side-channel; the wrapper already exists |
| Token generation | `uuid4()`, `random`, or a hand-rolled alphabet | `secrets.token_urlsafe(32)` | `random` is not a CSPRNG; uuid4 has 122 bits and encodes structure |
| TLS certificates | certbot cron + renewal scripting | Caddy automatic HTTPS | Obtains and renews transparently from one config line |
| Process restart / boot start | A `while true` shell loop or `screen`/`nohup` | systemd unit with `Restart=always` | Survives reboot, logs to journald, no orphan processes |
| Append-only enforcement | Application-level "don't UPDATE" discipline | DB triggers | Must survive an app bug or a compromised process |

**Key insight:** Phase 27 deliberately built the merge engine as pure functions with no HTTP and no file I/O so that Phases 28 and 30 would be *thin*. If any plan task in this phase starts describing merge semantics, conflict rules, or idempotency, that task is in the wrong phase.

## Runtime State Inventory

Not a rename/refactor/migration-of-existing-data phase — this is additive (new tables, new routes, re-created triggers). Included for the trigger DDL specifically, which *is* a form of live-state change:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None. `synced_at` already exists on `operations` and `cash_movements`, currently all-NULL; the relaxation changes no row values | None — code/DDL only |
| Live service config | Existing SQLite triggers on every already-deployed client DB must be dropped and re-created by migration `0018` at next `alembic upgrade head` (`run.bat` runs this on every launch — verified) | Migration handles it automatically |
| OS-registered state | None today. Phase 28 *creates* new OS state on the VPS (systemd unit, Caddy site) — greenfield, nothing to migrate | New registration in `DEPLOY.md` |
| Secrets/env vars | `SECRET_KEY` and `DATABASE_URL` must be set in the server environment; `settings.database_url` already honours `DATABASE_URL` and `secret_key` already honours `SECRET_KEY` (verified in `app/config.py`). No key is renamed | Set on the VPS only; never committed |
| Build artifacts | `app/db.py::APPEND_ONLY_TRIGGERS` is a *live* constant consumed by `tests/conftest.py` to build every test DB — it is effectively a build artifact of the trigger design and **will not** auto-update from the migration | Must be edited in the same plan as migration `0018` |

## Common Pitfalls

### Pitfall 1: PostgreSQL `json` has no equality operator
**What goes wrong:** The PG trigger `WHEN` clause containing `NEW.payload IS DISTINCT FROM OLD.payload` fails with `operator does not exist: json = json`. Depending on where it surfaces, either `CREATE TRIGGER` fails at migration time or every `UPDATE` on `operations` errors at runtime.
**Why it happens:** `Operation.payload` is `sa.JSON()`, which maps to PG's `json` (not `jsonb`); `json` intentionally has no `=` operator because JSON documents have no canonical byte form.
**How to avoid:** Cast both sides to `text`: `NEW.payload::text IS DISTINCT FROM OLD.payload::text`. SQLite needs no cast (it stores JSON as TEXT).
**Warning signs:** The pg-parity job fails on migration `0018` with an `operator does not exist` error, or passes migration but every push fails.
**Confidence:** HIGH — reproduced by execution in this session.

### Pitfall 2: `APPEND_ONLY_TRIGGERS` and migration `0018` drift apart
**What goes wrong:** The test suite keeps passing against the *old* unconditional triggers while production runs the relaxed ones (or the reverse), so the relaxation is never actually tested.
**Why it happens:** `tests/conftest.py` builds every test DB via `Base.metadata.create_all()` + `APPEND_ONLY_TRIGGERS` — it never runs Alembic. Two independent sources of the same DDL.
**How to avoid:** Edit `app/db.py::APPEND_ONLY_TRIGGERS` and add migration `0018` in the **same plan task**. Add a test that stamps `synced_at` on a fixture row and asserts it succeeds — it will fail loudly if the constant was missed.
**Warning signs:** All SQLite tests green but the first real client push fails on the trigger.

### Pitfall 3: The app-level `auth_guard` silently blocks the sync tree
**What goes wrong:** Every sync request 303-redirects to `/login`, or `POST` returns 403 «Недействительный CSRF-токен.»
**Why it happens:** `app/main.py` applies `dependencies=[Depends(auth_guard)]` to the whole app; the guard demands a session user and enforces CSRF on all non-GET methods.
**How to avoid:** Add the `/api/sync/` prefix early-return to `auth_guard` before mounting the router.
**Warning signs:** A 303 with a `location: /login` header on a request that carried a valid Bearer token.

### Pitfall 4: A too-broad guard bypass opens the HTML tree
**What goes wrong:** A bypass written as `startswith("/api/")` or added to `PUBLIC_PATHS` too loosely un-authenticates more than intended.
**Why it happens:** `PUBLIC_PATHS` is exact-match today; switching to prefix matching changes the matching semantics for everything.
**How to avoid:** Keep `PUBLIC_PATHS` exact-match and add a *separate* narrowly-scoped prefix constant. Add a negative test asserting a device token cannot fetch `/` or `/settings/users`, and that an unauthenticated request to `/api/sync/push` is 401 (not 303).
**Warning signs:** A test that expected 303/401 gets 200.

### Pitfall 5: Unbounded push payload
**What goes wrong:** `await request.body()` on a multi-GB upload OOMs the VPS — a trivial DoS on a small box.
**Why it happens:** Neither Starlette nor uvicorn imposes a default body-size limit.
**How to avoid:** Cap at the proxy (`request_body { max_size 32MB }` in Caddy) **and** in the handler (check `Content-Length`, reject with 413). Belt and braces — the app must be safe even if the proxy config is wrong. Consider streaming line-by-line into `parse_exchange`, which already accepts any `Iterable[str]`.
**Warning signs:** Server memory spikes during sync; OOM-killer entries in journald.

### Pitfall 6: `https_only=False` on the session cookie in production
**What goes wrong:** The session cookie is sent over plaintext HTTP and can be intercepted.
**Why it happens:** `app/main.py` hardcodes `https_only=False` with the comment "for localhost" [VERIFIED].
**How to avoid:** Make it a setting (`settings.session_https_only`, default `False` so localhost keeps working) and set it `True` in the server environment. Do **not** hardcode `True` — that would break every local client and the whole test suite.
**Warning signs:** Browser devtools shows the session cookie without the `Secure` flag on the production domain.

### Pitfall 7: Pull cursor with strict `>` drops boundary rows
**What goes wrong:** Reference rows sharing the exact `updated_at` of the last page are never delivered — a silent, permanent data gap.
**Why it happens:** `updated_at` is second- or microsecond-granularity ISO text; a bulk edit writes many rows with an identical stamp.
**How to avoid:** Use `>=` and let the client's server-wins upsert absorb the re-delivery. `apply_merge`'s reference upsert is idempotent, so the overlap is free.
**Warning signs:** A product edited in the same second as another never appears on the client.

### Pitfall 8: `Sale` has no `updated_at`
**What goes wrong:** A generic pull query written as "select where `updated_at` >= since" over all reference kinds raises an `AttributeError`/`UndefinedColumn` for `sale`.
**Why it happens:** `Sale` carries only `created_at` [VERIFIED: app/models.py].
**How to avoid:** Map the cursor column per kind explicitly rather than assuming a uniform column.
**Warning signs:** Pull works for products and fails for sales.

### Pitfall 9: uvicorn behind a proxy without `--proxy-headers`
**What goes wrong:** Client IPs all log as `127.0.0.1`, and any IP-based rate limiting or logging is useless.
**Why it happens:** `--proxy-headers` is enabled by default but only trusts IPs listed in `--forwarded-allow-ips`, which defaults to `127.0.0.1`.
**How to avoid:** Since Caddy connects from `127.0.0.1` on the same host, the default is actually correct here — but verify rather than assume, and never set `--forwarded-allow-ips="*"` on an internet-facing box.
**Confidence:** MEDIUM [CITED: uvicorn.dev/settings/ via search; the canonical uvicorn.org page was unreachable from this environment — `needs verification` against uvicorn.dev/settings/ at plan time].

## Code Examples

### Migration 0018 skeleton (dialect-branched, mirroring the frozen 26-02 pattern)

```python
"""relax append-only UPDATE triggers to allow the synced_at cursor

Revision ID: 0018
Revises: 0017
"""
revision = "0018"
down_revision = "0017"

_SQLITE_DDL = (
    "DROP TRIGGER IF EXISTS operations_no_update",
    _SQLITE_OPERATIONS_NO_UPDATE,       # the WHEN-guarded CREATE TRIGGER above
    "DROP TRIGGER IF EXISTS cash_movements_no_update",
    _SQLITE_CASH_NO_UPDATE,
)

_PG_DDL = (
    "DROP TRIGGER IF EXISTS operations_no_update ON operations",
    _PG_OPERATIONS_NO_UPDATE,           # reuses operations_append_only()
    "DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements",
    _PG_CASH_NO_UPDATE,                 # reuses cash_movements_append_only()
)

def upgrade() -> None:
    statements = _PG_DDL if op.get_bind().dialect.name == "postgresql" else _SQLITE_DDL
    for stmt in statements:
        op.execute(stmt)
```

The `*_no_delete` triggers and both PL/pgSQL functions are **not** touched — deletion stays unconditionally blocked and the functions are reused as-is.

### Schema-derived guard test (mirrors Phase 27's money-field guard)

```python
# tests/test_append_only_cursor.py
IMMUTABLE_OPERATION_COLUMNS = { ...the 14 names hardcoded in the trigger... }

def test_trigger_column_list_matches_schema():
    """A column added to Operation without updating trigger 0018 fails here."""
    actual = {c.key for c in Operation.__mapper__.columns} - {"synced_at"}
    assert actual == IMMUTABLE_OPERATION_COLUMNS, (
        "Operation gained/lost a column — update migration 0018's WHEN clause "
        "and app/db.py APPEND_ONLY_TRIGGERS together."
    )
```

This is the single most valuable test in the phase: it converts a silent fail-open (a future column not covered by the trigger) into a loud red test.

### Bearer token verification service

```python
# app/services/devices.py
import hashlib, secrets
from app.services.auth import compare_token

TOKEN_PREFIX_LEN = 12

def mint_token(session, *, device_id, label, user_id=None) -> tuple[DeviceToken, str]:
    """Create a device token. Returns (row, plaintext) — plaintext shown ONCE."""
    plaintext = "myos_" + secrets.token_urlsafe(32)
    row = DeviceToken(
        device_id=device_id, label=label, user_id=user_id,
        token_prefix=plaintext[:TOKEN_PREFIX_LEN],
        token_hash=hashlib.sha256(plaintext.encode()).hexdigest(),
    )
    session.add(row); session.commit()
    return row, plaintext          # never logged, never stored in plaintext

def lookup_active_token(session, presented: str) -> DeviceToken | None:
    row = session.scalar(
        select(DeviceToken).where(
            DeviceToken.token_prefix == presented[:TOKEN_PREFIX_LEN],
            DeviceToken.is_active == 1,
        )
    )
    if row is None:
        return None
    digest = hashlib.sha256(presented.encode()).hexdigest()
    return row if compare_token(digest, row.token_hash) else None
```

### systemd unit + Caddyfile

```ini
# /etc/systemd/system/myorishop.service
[Unit]
Description=MyOriShop
After=network.target postgresql.service

[Service]
User=myorishop
WorkingDirectory=/srv/myorishop
EnvironmentFile=/etc/myorishop.env        # chmod 600 — DATABASE_URL, SECRET_KEY
ExecStartPre=/usr/local/bin/uv run alembic upgrade head
ExecStart=/usr/local/bin/uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```
# /etc/caddy/Caddyfile
shop.example.com {
    reverse_proxy 127.0.0.1:8000
    request_body { max_size 32MB }
}
```
[CITED: caddyserver.com/docs/caddyfile/patterns — the two-line reverse-proxy form and automatic certificate issuance/renewal]

`ExecStartPre` running `alembic upgrade head` mirrors what `run.bat` already does on the client [VERIFIED: run.bat line `uv run alembic upgrade head`], so migration-on-deploy is consistent across both targets.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Unconditional `BEFORE UPDATE` append-only trigger | `WHEN`-guarded, column-scoped trigger | This phase | Enables the `synced_at` cursor without weakening immutability |
| certbot + cron renewal | Caddy automatic HTTPS | ~2019 onward | One config line replaces an ACME client and a renewal timer |
| JWT for every API | Opaque bearer tokens with server-side lookup for small single-tenant apps | Ongoing pushback against JWT-by-default | Instant revocation, no key rotation, no `alg=none` class of bug |
| Argon2 for all secrets | Argon2 for passwords, SHA-256 for high-entropy tokens | Long-standing practice | Avoids ~100 ms KDF cost on every authenticated request |

**Deprecated/outdated:**
- `www.uvicorn.org` appears to have moved to `uvicorn.dev` (the old host was unreachable from this environment; search results cite `uvicorn.dev/settings/`). `needs verification`.

## Project Constraints (from CLAUDE.md)

Directives the planner must honour:

- **Sync SQLAlchemy `Session` + `def` endpoints** — no `async def` on DB-touching sync routes, no `aiosqlite`/`async_sessionmaker`.
- **Portable ORM constructs only** — no `sqlalchemy.dialects`, no `on_conflict`, no SQLite- or PG-specific SQL in application code. (Dialect-branched *trigger DDL inside a migration* is the established, sanctioned exception — precedent set by `26-02`.)
- **Money as integer minor units** — never `FLOAT`/`REAL`. `parse_exchange` already rejects float money.
- **Alembic from day one**, `render_as_batch=True` **SQLite-only** (already dialect-gated in `alembic/env.py`).
- **htmx 2.0.10 vendored**, no CDN, no SPA framework.
- **No Docker for the local client.** (The server is a separate question — see OQ-2.)
- **Never hardcode secrets**; use environment variables. `secret_key`/`database_url` already resolve from env with `.env` precedence.
- **Never log or print** `secret_key`, `device_id`, passwords, hashes, or CSRF tokens — extend this to device-token plaintext.
- **Russian for user-facing strings**, English for code/comments/commits.
- **Smallest safe change**; patch rather than replace; do not remove existing logic, comments, tests, or config without a clear reason.
- **GSD workflow enforcement** — file edits go through a GSD command.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Everything | ✓ | 3.13 (`requires-python = ">=3.13"`) | — |
| Docker | Local PG testing during development | ✓ | verified in this session (pulled and ran `postgres:17`) | GitHub Actions pg-parity job |
| PostgreSQL 17 | Server DB + parity tests | ✓ (via Docker / CI service container) | 17 | — |
| `psql` CLI | Convenience only | ✗ | — | `docker exec ... psql` (used successfully in this session) |
| GitHub Actions runner | pg-parity CI proof | ✓ | `ci.yml` present with `postgres:17` service | — |
| VPS host | Production deployment | ✗ — not yet provisioned | — | **Blocking for live deploy; see OQ-1** |
| Domain name | TLS certificate issuance | ✗ — not yet chosen | — | **Blocking for TLS; see OQ-1** |

**Missing dependencies with no fallback:**
- VPS host and domain name. Caddy cannot obtain a certificate without a domain resolving to the server. This does not block *building or testing* the phase — all three success criteria are verifiable locally and in CI — but it blocks the live-deployment step.

**Missing dependencies with fallback:**
- `psql` CLI — `docker exec pg... psql` works and was used for this research.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (`[dependency-groups] dev` in pyproject.toml) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]`, `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `uv run pytest tests/test_sync_api.py tests/test_devices.py tests/test_append_only_cursor.py -x` |
| Full suite command | `uv run pytest` |
| PG-only command | `DATABASE_URL=postgresql+psycopg://… uv run pytest tests/test_pg_parity.py -x` |

The established PG pattern to reuse [VERIFIED: tests/test_pg_parity.py, tests/test_merge_pg.py]:
- module-level `pytestmark = pytest.mark.skipif(not settings.database_url.startswith("postgresql"), ...)` so the module auto-skips on the SQLite default
- `_engine()` from `settings.database_url`, `_upgrade_head()` via `alembic.command`
- literal-constant seeds only, every NOT NULL column named, `ON CONFLICT DO NOTHING` for ledger rows so the harness re-runs against a standing server
- assert append-only rejection on the **message substring** `append-only` with `pytest.raises(Exception, match="append-only")` — PG raises a driver exception, not SQLite's `IntegrityError`

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRV-04 | `/` renders the desktop UI 200 for an authenticated user | smoke | `uv run pytest tests/test_smoke.py -x` | ✅ exists |
| SRV-04 | `/m/` renders the mobile UI 200 from the same app | smoke | `uv run pytest tests/test_mobile_foundation.py tests/test_mobile_wiring.py -x` | ✅ exists |
| SRV-04 | Both trees are served by one app object (no second process) | integration | `uv run pytest tests/test_sync_api.py::test_both_uis_one_app -x` | ❌ Wave 0 |
| SYNC-09 | Push with a valid Bearer token → 200 + MergeReport | integration | `uv run pytest tests/test_sync_api.py::test_push_with_valid_token -x` | ❌ Wave 0 |
| SYNC-09 | Push with **no** token → 401 (not a 303 to /login) | integration | `uv run pytest tests/test_sync_api.py::test_push_without_token_rejected -x` | ❌ Wave 0 |
| SYNC-09 | Push with an invalid/revoked token → 401 | integration | `uv run pytest tests/test_sync_api.py::test_revoked_token_rejected -x` | ❌ Wave 0 |
| SYNC-09 | A device token does **not** grant access to `/` or `/settings/users` | integration | `uv run pytest tests/test_sync_api.py::test_device_token_cannot_reach_html -x` | ❌ Wave 0 |
| SYNC-09 | A browser session does **not** grant access to `/api/sync/push` | integration | `uv run pytest tests/test_sync_api.py::test_session_cookie_cannot_reach_sync -x` | ❌ Wave 0 |
| SYNC-09 | Token stored only as a SHA-256 hash; plaintext never persisted | unit | `uv run pytest tests/test_devices.py -x` | ❌ Wave 0 |
| SC-2 | Pushing the same NDJSON batch twice → second returns inserted=0 | integration | `uv run pytest tests/test_sync_api.py::test_push_idempotent -x` | ❌ Wave 0 |
| SC-2 | A poisoned record rolls the whole batch back (0 rows) | integration | `uv run pytest tests/test_sync_api.py::test_push_all_or_nothing -x` | ❌ Wave 0 |
| SC-2 | Pull returns NDJSON reference rows after the cursor | integration | `uv run pytest tests/test_sync_api.py::test_pull_cursor -x` | ❌ Wave 0 |
| SC-3 | **SQLite:** stamping `synced_at` alone succeeds | unit | `uv run pytest tests/test_append_only_cursor.py::test_synced_at_stamp_allowed -x` | ❌ Wave 0 |
| SC-3 | **SQLite:** UPDATE of `qty_delta` / `amount_cents` / `author_id` / `created_by` rejected | unit | `uv run pytest tests/test_append_only_cursor.py::test_immutable_columns_rejected -x` | ❌ Wave 0 |
| SC-3 | **SQLite:** UPDATE mixing `synced_at` + an immutable column rejected | unit | `uv run pytest tests/test_append_only_cursor.py::test_mixed_update_rejected -x` | ❌ Wave 0 |
| SC-3 | **SQLite:** DELETE still unconditionally rejected | unit | `uv run pytest tests/test_append_only_cursor.py::test_delete_still_rejected -x` | ❌ Wave 0 |
| SC-3 | Trigger column list == schema columns minus `synced_at` (fail-open guard) | unit | `uv run pytest tests/test_append_only_cursor.py::test_trigger_column_list_matches_schema -x` | ❌ Wave 0 |
| SC-3 | **PostgreSQL:** identical stamp-allowed / tamper-rejected behavior, incl. `payload` | integration | `DATABASE_URL=… uv run pytest tests/test_pg_parity.py -x` | ✅ file exists, ❌ new cases |
| SRV-01 | Full Alembic history still applies clean on empty PG **through 0018/0019** | integration | `DATABASE_URL=… uv run pytest tests/test_pg_parity.py::test_full_history_applies -x` | ✅ exists (re-run) |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_sync_api.py tests/test_devices.py tests/test_append_only_cursor.py -x`
- **Per wave merge:** `uv run pytest` (full SQLite suite — this is the project's established post-merge gate)
- **Phase gate:** full suite green **plus** a GREEN GitHub Actions `pg-parity` run including the new trigger-relaxation cases, before `/gsd-verify-work`

### PostgreSQL-only trigger testing — reuse, do not rebuild

The existing `pg-parity` job already runs three steps [VERIFIED: .github/workflows/ci.yml]. **Add the new PG trigger-relaxation assertions as cases inside `tests/test_pg_parity.py`, not as a new file or a new job** — that file already carries `test_operations_update_rejected`, `test_operations_delete_rejected`, and `test_cash_movements_immutable`, and the new "stamp allowed" case is their natural sibling. It is then picked up by the existing `PostgreSQL parity` step with **zero CI changes**. This mirrors the `27-04` precedent, which added one step rather than one job; here even that is unnecessary.

One caveat for the PG seeds: the existing harness inserts ledger rows with `ON CONFLICT DO NOTHING` because they can never be deleted. A "stamp `synced_at`" test **mutates** a row it may share with a previous run, so it must either use its own dedicated fixed-UUID row or assert idempotently (stamping an already-stamped row to the same value is still a permitted no-op under the value-based `WHEN`).

### Wave 0 Gaps

- [ ] `tests/test_append_only_cursor.py` — covers SC-3 on SQLite, incl. the schema-derived fail-open guard
- [ ] `tests/test_devices.py` — covers SYNC-09 token service (mint/hash/lookup/revoke)
- [ ] `tests/test_sync_api.py` — covers SYNC-09 endpoint auth + SC-2 push/pull/idempotency/rollback + the two negative cross-auth cases
- [ ] New cases appended to `tests/test_pg_parity.py` — covers SC-3 on PostgreSQL
- [ ] A `device_token`/authenticated-sync-client fixture in `tests/conftest.py` (the existing authenticated-client fixture overrides the whole `auth_guard`, which is the *wrong* seam for token tests — a token test must exercise the real guard)
- No framework install needed — pytest, httpx, and the PG harness all exist.

## Security Domain

**ASVS L1** (`security_asvs_level: 1`, `security_enforcement: true`). This phase is the app's **first internet-exposed surface**, so several categories become live that were dormant while the app was localhost-only.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Argon2id for humans (existing); `secrets.token_urlsafe(32)` + SHA-256 at rest for device tokens; `hmac.compare_digest` compare |
| V3 Session Management | yes | Existing itsdangerous-signed cookie; **must set `https_only=True` in production** (currently hardcoded `False`) and keep `same_site="lax"` |
| V4 Access Control | yes | Existing app-level `auth_guard` + `require_role("administrator")`; new `require_device` for the sync tree; the `/api/sync/` bypass must be narrow and negatively tested both directions |
| V5 Input Validation | yes | `merge.parse_exchange` (schema-derived, rejects malformed/bad-version/unknown-kind/float-money before any DB touch); request body size cap |
| V6 Cryptography | yes | Stdlib only — `secrets`, `hashlib`, `hmac`. No hand-rolled crypto, no JWT signing |
| V7 Error Handling & Logging | yes | Never log token plaintext, `secret_key`, or password hashes; return generic 401 text that does not distinguish "unknown token" from "revoked token" |
| V9 Communication | yes | TLS everywhere via Caddy automatic HTTPS; uvicorn bound to `127.0.0.1` only; HSTS via Caddy default |
| V12 Files & Resources | yes | Push body size limit at proxy **and** handler (413) |
| V13 API & Web Service | yes | Bearer token in the `Authorization` header (never a query param); explicit `WWW-Authenticate: Bearer` on 401 |

### Known Threat Patterns for FastAPI + PostgreSQL + internet-exposed sync

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Device-token theft from disk on a lost laptop | Spoofing | Admin revocation (`is_active = 0`); `last_used_at` for anomaly spotting; short-lived tokens rejected as over-engineering at this scale (see OQ-3) |
| Token replay over plaintext HTTP | Spoofing | TLS-only; HSTS; never accept the token over a non-TLS listener |
| Token leakage via logs/history | Information Disclosure | Bearer **header** only, never query string; never log the plaintext; store only the SHA-256 |
| Timing attack on token compare | Spoofing | Indexed lookup by non-secret prefix, then `hmac.compare_digest` on the digest |
| Brute-force / credential stuffing on the sync endpoint | Spoofing | Rate limiting (see OQ-4); 256-bit tokens make guessing infeasible regardless |
| Push-payload DoS (huge body) | Denial of Service | Caddy `max_size` + handler `Content-Length` check → 413 |
| Ledger tampering via the relaxed trigger | Tampering / Repudiation | Value-based `WHEN` enumerating **every** immutable column + the schema-derived fail-open guard test; DELETE stays unconditionally blocked |
| Client-supplied `synced_at` used to fake sync state | Tampering | Already defended — `_ledger_row` forces `synced_at = None`; `parse_exchange` nulls it on the wire |
| Client-supplied author to forge attribution | Repudiation | `author_id`/`created_by` are carried verbatim from the origin device by design (DD-6). **This is an accepted trust boundary**: a device token holder can assert any author. Note it explicitly rather than pretending otherwise; tightening it is a Phase 29/30 discussion |
| CSRF on the cookie-authenticated UI now that it is internet-facing | Tampering | Existing synchronizer-token CSRF (`require_csrf`, `X-CSRF-Token`) + `same_site="lax"`. **Bearer endpoints are not CSRF-vulnerable** (browsers never auto-attach an `Authorization` header) — which is exactly why skipping CSRF on `/api/sync/` is correct, not a weakening |
| SQL injection | Tampering | ORM/parameterized throughout; the trigger DDL contains **only literal constants** — no value is ever f-stringed into SQL |
| Postgres exposed to the internet | Information Disclosure | Bind PG to `localhost` only; no `0.0.0.0` listen; firewall to 22/80/443 |
| Secrets in the repo | Information Disclosure | `EnvironmentFile=/etc/myorishop.env` (chmod 600), never committed; `settings` already reads from env |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SHA-256 (not Argon2) is the right hasher for a 256-bit device token | Pattern 3 | If a reviewer disagrees on convention grounds, switching to Argon2 costs ~50-100 ms per sync request but is not insecure. Low risk; flag as an intentional divergence in the plan. |
| A2 | Pull should carry reference data only, never ledger rows | Pattern 2 | SYNC-01 says "pulling server-authoritative reference data down" and the offline path is upload-only — but multi-device desktop clients might later want each other's ledger rows. If wrong, pull gains a second record class in Phase 29. Medium risk; confirm at Phase 29 planning. |
| A3 | `>=` cursor semantics with client-side idempotent absorption | Pattern 2 | If the client upsert were not idempotent this would duplicate; it *is* idempotent (27-03). Low risk. |
| A4 | Device tokens are minted by an administrator in the UI, not self-registered | Pattern 3 | If the operator expects a self-service device enrolment flow, the admin surface is wasted work. Low risk at 1-2 devices; raised as OQ-3. |
| A5 | uvicorn's default `--forwarded-allow-ips=127.0.0.1` suffices with a same-host Caddy | Pitfall 9 | Wrong client IPs in logs only; no security impact given no IP-based auth. Low risk. `needs verification` against uvicorn.dev/settings/. |
| A6 | The existing `pg-parity` job needs no workflow change (new cases land in an existing file) | Validation Architecture | If the cases go in a new file instead, one CI step must be added. Trivial to fix. |

## Open Questions (RESOLVED)

> Resolved at Phase 28 planning, 2026-07-19. OQ-2..OQ-6 adopted their researcher-recommended
> defaults and each names the plan that implements it. OQ-1 remains open **by decision** and does
> not gate the phase.

1. **VPS provider, plan size, OS, and domain name** *(genuine user/business decision — cost and account ownership)*
   - **OPEN BY DECISION** — user decision on VPS provider/tier/domain; does not gate this phase, all
     three success criteria are provable locally and in CI. Plan 28-06 ships provider-agnostic
     artifacts (systemd unit, Caddyfile, `pg_dump` timer, `DEPLOY.md`) with placeholders only; no task
     performs a live deploy and no acceptance criterion depends on a live host existing.
   - What we know: the app is single-tenant with 1-3 devices; PostgreSQL 17; Python 3.13; the whole workload fits in the smallest tier available anywhere.
   - What's unclear: budget, preferred provider, existing domain, data-residency preference.
   - **Recommended default:** the cheapest 1 vCPU / 2 GB tier on any mainstream provider (Hetzner CX22, DigitalOcean, Vultr all qualify), Ubuntu 24.04 LTS, with PostgreSQL installed on the same box (not a managed DB — a managed instance often costs more than the VPS itself at this scale). A subdomain of a domain the operator already owns avoids a new registration.
   - **This blocks the live-deploy step only** — all three success criteria are testable locally and in CI without it.

2. **Managed PostgreSQL vs. same-box PostgreSQL, and Docker on the server**
   - **RESOLVED (2026-07-19):** recommended default adopted — PostgreSQL installed directly on the VPS
     from distro/PGDG packages, bound to `localhost`, no Docker on the server. Implemented by **Plan
     28-06** (`deploy/DEPLOY.md` sections 2 and 8, threat T-28-11).
   - What we know: CLAUDE.md rejects Docker for the *local client*; it is silent on the server. CI already uses `postgres:17`.
   - **Recommended default:** PostgreSQL installed directly on the VPS via the distro package, bound to `localhost`, no Docker. One fewer runtime, and `pg_dump` backups are simpler. Revisit only if the operator wants managed backups they do not have to think about.

3. **Device-token lifecycle: who mints, and do tokens expire?**
   - **RESOLVED (2026-07-19):** recommended default adopted — admin-minted from a new
     `/settings/devices` page, plaintext shown exactly once, **no expiry — revocation only**, plus a
     `last_used_at` column so a stale token is visible. Implemented by **Plan 28-02** (model + service,
     no `expires_at` column by acceptance criterion) and **Plan 28-05** (admin surface, show-once,
     revoke, operator 403).
   - What we know: `User` already has an admin CRUD surface at `/settings/users` with `require_role("administrator")`.
   - **Recommended default:** admin-minted from a new `/settings/devices` page, plaintext shown exactly once, **no expiry** — revocation only. Expiry on a 1-3 device single-reseller app creates a failure mode (sync silently stops working on a Tuesday) with negligible security gain. Add `last_used_at` so a stale token is visible.

4. **Rate limiting: in-process, library, or proxy-level?**
   - **RESOLVED (2026-07-19):** proportional-only default adopted — a ~40-line in-process token bucket
     keyed by the non-secret `token_prefix`, plus optional proxy-level limiting. **No `slowapi`, no
     Redis, no new package.** Implemented by **Plan 28-03** (`app/services/rate_limit.py`, threat
     T-28-12) with the proxy-side note in **Plan 28-06**.
   - What we know: no rate limiting exists anywhere in the app today; the sync endpoint is the first internet-exposed POST.
   - **Recommended default:** Caddy-level rate limiting or a ~20-line in-process token bucket keyed by `token_prefix`. Do **not** add `slowapi` + Redis for 1-3 devices. Given 256-bit tokens, rate limiting here is DoS protection, not brute-force protection — sizing it accordingly keeps it proportional. If a library is chosen, run it through the package legitimacy gate first.

5. **Should `synced_at` be stamped on the server as well as the client?**
   - **RESOLVED (2026-07-19):** recommended default adopted — implement the trigger relaxation on BOTH
     engines (SC-3 requires it regardless), but only the **client** writes the cursor, in Phase 29. On
     the server `synced_at` stays NULL, meaning "this row has never been pushed FROM here".
     Implemented by **Plan 28-01** (both-dialect relaxation) and written into **Plan 28-04**'s objective,
     its `app/services/sync.py` docstring instruction and threat T-28-22 so Phase 29 does not
     rediscover it.
   - What we know: success criterion 3 requires the relaxation on **both** engines. The client (SQLite) genuinely needs it for the SYNC-07 unsynced badge (`COUNT WHERE synced_at IS NULL`). The server's need is less obvious.
   - **Recommended default:** implement the relaxation on both (required by SC-3 regardless) but only the **client** actually writes the cursor in Phase 29. On the server, `synced_at` stays NULL — meaning "this row has never been pushed *from here*". Keeping the server's semantics identical rather than inventing a second meaning avoids a subtle divergence. Worth one explicit line in the plan so it is not accidentally rediscovered in Phase 29.

6. **Backup strategy on the server**
   - **RESOLVED (2026-07-19):** recommended default adopted, and the `needs verification` item was
     checked — `28-PATTERNS.md` traced `app/services/backup.py:89-105` and found `startup_backup()`
     avoids crashing on PostgreSQL only **by accident** (it early-returns because `settings.db_path`
     names an absent SQLite file). **Plan 28-06** adds an explicit `engine.dialect.name != "sqlite"`
     guard with a regression test that removes the accidental skip, plus the nightly `pg_dump` systemd
     timer with 30-day retention (threats T-28-13, T-28-30).
   - What we know: the client already has `VACUUM INTO` startup backups (`app/services/backup.py`, `backup_keep: 30`). That code is SQLite-specific and will not work against PostgreSQL.
   - **Recommended default:** a nightly `pg_dump` to a local directory with 30-day retention via a systemd timer, plus an off-box copy. **Check at plan time whether `startup_backup()` errors or silently no-ops when `database_url` is PostgreSQL** — it runs unconditionally in the app lifespan [VERIFIED: app/main.py `lifespan` calls `backup_service.startup_backup()`], so a PG deployment could crash on boot. `needs verification` — this was not traced into `app/services/backup.py` during this research and is a plausible deploy-day blocker.

## Sources

### Primary (HIGH confidence)
- Direct execution against SQLite 3.45.1 in this session — WHEN-clause trigger: `synced_at` stamp allowed; `qty_delta`, `created_by`, `author_id`, and mixed-column updates all rejected with `operations ledger is append-only`
- Direct execution against `postgres:17` in Docker in this session — `IS DISTINCT FROM` trigger with `payload::text` cast: stamp allowed, five tamper variants rejected; and confirmation that `json = json` does not exist
- Repository files read directly: `app/main.py`, `app/db.py`, `app/config.py`, `app/models.py`, `app/services/merge.py`, `app/services/security.py`, `app/services/auth.py`, `app/services/ledger.py`, `app/routes/mobile_home.py`, `app/routes/mobile_sales.py`, `alembic/versions/0001_initial_schema.py`, `alembic/versions/0013_cash_movements.py`, `alembic/versions/0017_users_and_author_id.py`, `alembic/env.py`, `tests/conftest.py`, `tests/test_pg_parity.py`, `.github/workflows/ci.yml`, `pyproject.toml`, `run.bat`, `.planning/config.json`, `.planning/ROADMAP.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `CLAUDE.md`

### Secondary (MEDIUM confidence)
- caddyserver.com/docs/caddyfile/patterns — minimal reverse-proxy Caddyfile and automatic HTTPS
- uvicorn.dev/settings/ (via web search; canonical host unreachable from this environment) — `--proxy-headers` default-enabled, `--forwarded-allow-ips` default `127.0.0.1`

### Tertiary (LOW confidence)
- Ecosystem judgment on SHA-256-vs-Argon2 for high-entropy API tokens (A1) and opaque-token-vs-JWT for single-tenant apps — practitioner consensus, not cited to a specific standard

## Metadata

**Confidence breakdown:**
- Trigger relaxation (SC-3): **HIGH** — both dialects verified by execution, including the non-obvious PG JSON trap
- Sync API surface: **HIGH** — function signatures, transaction contract, and NDJSON format read from `app/services/merge.py`, not assumed
- Device-token auth: **HIGH** on mechanism and the `auth_guard` interaction (read from source); **MEDIUM** on the hasher choice (deliberate convention divergence, A1)
- Two UIs (SRV-04): **HIGH** — the mobile tree is already shipped and was enumerated file-by-file
- VPS deployment: **MEDIUM** — shape is standard and Caddy behavior is cited, but no target host exists yet (OQ-1) and the PG-vs-SQLite backup interaction is unverified (OQ-6)
- Security: **HIGH** on the threat list; **MEDIUM** on rate-limiting sizing (OQ-4)
- Validation: **HIGH** — reuses the established, currently-GREEN pg-parity harness

**Research date:** 2026-07-19
**Valid until:** 2026-08-18 (30 days — stack is stable; the codebase claims are pinned to the current HEAD `c473c4e` and should be re-checked if Phase 28 planning slips past a Phase 27 follow-up commit)
