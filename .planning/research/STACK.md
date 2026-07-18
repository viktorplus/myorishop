# Stack Research

**Domain:** Local-first inventory app gaining a central PostgreSQL server, online + offline-USB sync of an append-only ledger, and mandatory auth with roles (v3.0)
**Researched:** 2026-07-18
**Confidence:** HIGH (all versions verified against PyPI JSON on 2026-07-18; architecture recommendations MEDIUM-HIGH)

> Scope note: the v1/v2 stack (Python 3.13, FastAPI 0.139, SQLAlchemy 2.0 sync, SQLite+WAL, HTMX 2.0.10 vendored, Jinja2, Alembic, uv, Ruff) is **settled and unchanged**. This file only covers the **NEW** additions v3.0 needs. Nothing here replaces an existing choice.

---

## Recommended Stack

### Core Technologies (new for v3.0)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **psycopg** (psycopg 3) | 3.3.4 | PostgreSQL driver for the **server** SQLAlchemy engine | The modern, actively-maintained Postgres adapter; SQLAlchemy 2.0 ships a first-class dialect for it (`postgresql+psycopg://`). Server-only: clients keep SQLite, so this installs on the VPS, not on operator machines. Install `psycopg[binary]` to avoid a local C/libpq build on the server. **Confidence: HIGH** (PyPI 3.3.4, requires-python >=3.10, released 2026-05-01) |
| **pwdlib** (with argon2 extra) | 0.3.0 | Password hashing for login | The FastAPI-recommended successor to passlib. Defaults to **Argon2id** (current OWASP first choice), tiny surface, sync API that fits `def` endpoints. `pwdlib[argon2]` pulls `argon2-cffi`. Passlib is unmaintained (last release 2020) and leans on the stdlib `crypt` module, **removed in Python 3.13 (PEP 594)** — a hard reason not to use it here. **Confidence: HIGH** (version), **HIGH** (passlib-vs-pwdlib rationale) |
| **argon2-cffi** | 25.1.0 | Argon2 backend used by pwdlib | Pulled automatically by `pwdlib[argon2]` (declared range `>=23.1.0,<26`, so 25.1.0 fits). The actual hashing implementation. **Confidence: HIGH** |
| **Starlette `SessionMiddleware`** | bundled (Starlette 1.3.1 via FastAPI 0.139) | Signed-cookie login session | Already in the tree — no new framework. Stores a small signed session (`user_id`, `role`) in an itsdangerous-signed cookie. Stateless (no session table, works across uvicorn workers), which is the simplest safe fit for a server-rendered HTMX app. **Confidence: HIGH** |
| **itsdangerous** | 2.2.0 | Cookie signing backend for SessionMiddleware | `SessionMiddleware` **requires** it (raises `AssertionError` at startup if missing) — declare it explicitly rather than relying on it being transitively present. Also the right tool if you later sign a USB-export file or a device sync token. **Confidence: HIGH** |
| **httpx** | 0.28.1 | Client -> server sync HTTP transport | Already a **dev** dependency (TestClient) — promote it to a runtime dependency. Use the **sync** `httpx.Client` to match the all-sync codebase (`def` endpoints, sync Session). Timeouts, retries, TLS, and streaming uploads for large ledger batches, all in one lib. **Confidence: HIGH** |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **stdlib `json`** | (Python 3.13) | Serialize the ledger exchange (NDJSON) for BOTH online HTTP and offline USB | No new dependency. Every ledger/entity column is already JSON-native (TEXT UUIDs, int cents, ISO-text timestamps, `payload` is already a `JSON` column). One serializer feeds both transports — see "Sync exchange format" below. **Confidence: HIGH** |
| **pydantic** | 2.13.x (already present) | Type/validate the sync envelope + the login form | Already in the tree via pydantic-settings/FastAPI. Define one small `SyncEnvelope`/`OperationRow` model reused by push, pull, and USB import — no separate serialization lib (no marshmallow). **Confidence: HIGH** |
| **pydantic-settings** | 2.14.x (already present) | Hold the new secrets: `secret_key`, `database_url`, `sync_server_url`, per-device `sync_token` | Extend the existing `Settings` class. Keeps the session secret and the Postgres URL in `.env`, never in code (CLAUDE.md safety rule). **Confidence: HIGH** |
| **psycopg[binary]** | 3.3.4 | Server-only optional dependency group | Put Postgres behind an optional `[project.optional-dependencies] server` group so operator clients (`uv sync`) never install it. **Confidence: HIGH** |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| uv | Env/dep manager (unchanged) | Add the runtime deps with `uv add`; add server-only Postgres as an optional group (`uv add --optional server "psycopg[binary]"`). |
| Alembic (unchanged) | One migration history for BOTH dialects | Make batch mode conditional on the SQLite dialect and gate dialect-specific trigger DDL — see "Alembic: one history, two databases". |
| A local Postgres for dev | Test the same migrations against Postgres before the VPS | Docker Postgres or a native install is fine **for the server/dev box only**; do NOT introduce Docker into the client run story (still `run.bat`). |

## Installation

```bash
# Client + shared runtime deps (all machines)
uv add "pwdlib[argon2]==0.3.*" "itsdangerous==2.2.*" "httpx==0.28.*"

# Server-only (the VPS running Postgres) — optional group, clients skip it
uv add --optional server "psycopg[binary]==3.3.*"

# Server connection string (SQLAlchemy 2.0 + psycopg 3 dialect):
#   postgresql+psycopg://USER:PASSWORD@HOST:5432/myorishop
# Client connection string stays:
#   sqlite:///data/myorishop.db
#
# New .env keys (never commit real values):
#   SECRET_KEY=<64+ random hex chars>       # SessionMiddleware cookie signing
#   DATABASE_URL=postgresql+psycopg://...    # server only; clients keep db_path
#   SYNC_SERVER_URL=https://your-vps/...     # client only
#   SYNC_TOKEN=<per-device shared secret>    # client<->server auth for /sync
```

## Integration Points (into the existing codebase)

**(a) One SQLAlchemy 2.0 model set on both SQLite (client) and PostgreSQL (server)**
- The models are **already portable** — `app/models.py` uses only dialect-neutral types (`String`, `Integer`, `JSON`, `ForeignKey`) and already writes partial indexes with *both* `sqlite_where=` and `postgresql_where=` (e.g. `uq_products_code_active`). No model rewrite needed.
- `app/db.py` `build_engine()` is SQLite-specific (the PRAGMA `connect` listener). Add a sibling **server engine** built from `DATABASE_URL` with `postgresql+psycopg`; the PRAGMA listener must NOT be attached to it (guard on `engine.dialect.name == "sqlite"`).
- Keep the generic `JSON` column type (works on both). Optionally map to `JSONB` on Postgres later via a type variant, but it is not required for correctness.
- Money stays integer cents (already the rule); ISO-text UTC timestamps stay TEXT (portable to Postgres `text`; can migrate to `timestamptz` later without touching model code).

**(b) Auth for the FastAPI + HTMX server-rendered app**
- New `User` model: `id` UUID TEXT PK (matches the house convention), `login` unique, `name`, `password_hash` (String), `role` (String), `created_at`. Follow the project's existing **service-layer allow-list** pattern for `role` (like `WRITEOFF_REASONS`/`CONTACT_KINDS`) — no DB CHECK on role; validate `role in {"admin", "operator"}` in the service.
- Hash with `pwdlib.PasswordHash.recommended()` (Argon2id) at user-create and password-change; verify at login; use its `verify_and_update` to transparently re-hash on parameter changes.
- Add `SessionMiddleware(secret_key=settings.secret_key, https_only=True, same_site="lax")` in `app/main.py`. On login success set `request.session["user_id"]` and `["role"]`; logout clears it.
- Add two FastAPI dependencies — `require_login` and `require_admin` — that read the session and 303-redirect to `/login` (or 403) otherwise. Apply `require_admin` to admin-only routers (users, warehouses, dictionaries, settings, reports) and `require_login` everywhere else. This replaces the v1 "single local user, no auth" assumption.
- `settings.operator_name` (currently a static config default stamped into `record_operation`'s `created_by`) should become **the logged-in user's name** — a small, contained change at the single ledger choke point.

**(c) Append-only ledger sync — one format for online + USB**
- The ledger is **already sync-ready**: `Operation`/`CashMovement` have UUID4 TEXT PKs, `device_id`+`seq` with `UNIQUE(device_id, seq)`, an unused `synced_at` cursor column, and DB triggers blocking UPDATE/DELETE. `record_operation()` is the single write path.
- **Format: NDJSON** (one JSON object per line) of ledger rows — same bytes whether it is an HTTP request/response body (online) or a file on a USB stick (offline). No custom binary format, no shipping a second SQLite file.
- **Merge = set union by UUID PK.** Because rows are immutable and globally unique, importing is an idempotent "insert if the `id` is not already present" — no conflict resolution, no last-writer-wins, no CRDT. `synced_at` marks which local rows have been pushed so the next push sends only the delta.
- **The SQLite append-only triggers do NOT block importing remote rows** — they block UPDATE/DELETE only, so inserting synced rows is allowed. But the server (Postgres) needs **equivalent triggers**: `app/db.py:APPEND_ONLY_TRIGGERS` and migration `0001` carry a *frozen SQLite* `CREATE TRIGGER ... RAISE(ABORT ...)`. A new migration must add the **PostgreSQL** equivalent (`CREATE FUNCTION ... RAISE EXCEPTION` + `BEFORE UPDATE/DELETE` trigger), gated on dialect — see the flag below. The `db.py` comment already anticipates a "v2 sync milestone relaxes the UPDATE trigger" — treat that DDL constant as append-only itself.

**(d) HTTP client for push/pull**
- New FastAPI routes on the **server**: `POST /sync/push` (accept NDJSON ledger delta) and `GET /sync/pull?since_seq=&device_id=` (return rows the client lacks). No new server framework — same FastAPI/Starlette.
- New **client** module using sync `httpx.Client`: read un-synced rows (`synced_at IS NULL`), POST them, GET peers' rows, insert locally, stamp `synced_at`. Authenticate `/sync/*` with the per-device `SYNC_TOKEN` header (simplest device auth; not a user login).

## Alembic: one history, two databases

| Concern | Do this |
|---------|---------|
| `render_as_batch` | Make it **conditional**: `render_as_batch = connection.dialect.name == "sqlite"` in `env.py`. Batch mode is a SQLite-only workaround; forcing it on Postgres is wrong. |
| Dialect-specific DDL (append-only triggers) | Inside migrations, branch on `op.get_bind().dialect.name` — emit `RAISE(ABORT ...)` SQLite triggers vs a plpgsql `RAISE EXCEPTION` function+trigger for Postgres. |
| Connection string | Same migration files, both databases: `alembic upgrade head` runs against SQLite locally and Postgres on the server; only `sqlalchemy.url` differs (read from `DATABASE_URL`). |
| Multidb template | **Not needed** — that template is for one process migrating several DBs at once. Here each machine migrates its own single DB. |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| psycopg 3 (`postgresql+psycopg`) | psycopg2 (`postgresql+psycopg2`) | Only if a dependency forces psycopg2. It is in maintenance-only mode; psycopg3 has better typing, native async (unused here) and is the forward path. No reason to pick it for a greenfield server. |
| pwdlib[argon2] | bcrypt (5.0.0) used directly | Perfectly fine and slightly fewer layers if you prefer bcrypt; call `bcrypt.hashpw`/`checkpw` yourself. pwdlib is recommended because it defaults to Argon2id and gives a stable verify/needs-update API for free. |
| Argon2id | bcrypt | bcrypt is acceptable and battle-tested; choose it if you want the smallest possible dependency. Argon2id is the current OWASP first recommendation, hence the default. |
| Starlette SessionMiddleware (signed cookie) | Server-side session store (DB/Redis) | Only if you must invalidate sessions server-side instantly or store large session state. For a handful of operators with `user_id`+`role` in the cookie, stateless signed cookies are simpler and sufficient. |
| NDJSON over HTTP + USB file | Ship a whole SQLite `.db` file for USB sync | Copying a `.db` file is easy for full backup, but it conflates "backup" with "merge" and can't be reused by the online transport. NDJSON is one format for both paths and merges row-by-row. |
| Per-device shared-secret token for `/sync` | OAuth2 / JWT for sync | Overkill for a closed set of trusted operator devices talking to one owner-run server. A signed token header is enough; revisit only if untrusted third-party clients appear. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **passlib** | Unmaintained since 2020; relies on the stdlib `crypt` module, **removed in Python 3.13 (PEP 594)** — the project runs 3.13 | `pwdlib[argon2]` (or `bcrypt` directly) |
| **fastapi-users** | Heavy, async-first, brings its own DB models/registration/OAuth flows — triples the auth surface for a 2-role, server-rendered app | A tiny `User` model + pwdlib + SessionMiddleware + two `Depends` guards |
| **python-jose / JWT for user login** | Hand-rolled JWT in a server-rendered app is more code and more footguns than a signed session cookie; no SPA/API consumer needs a bearer token | Starlette `SessionMiddleware` signed cookie |
| **Celery / RQ / APScheduler + Redis/RabbitMQ** | No background job infrastructure is justified; sync is a request/response the operator triggers (button or simple timer). Adds a broker, a worker process, ops burden | A `def` sync function called from a route (online) or a menu action (USB) |
| **Kafka / Debezium / logical replication / CDC** | Enterprise streaming/CDC for 1–handful of operators is absurd overkill | NDJSON delta over `httpx` / USB, merged by UUID |
| **CRDT libraries (automerge, y-py, pycrdt)** | The ledger is append-only, immutable, UUID-keyed — merge is a set union with zero conflicts, so a CRDT solves a problem you don't have | Insert-if-absent by `id` |
| **psycopg2** on the server | Maintenance-only; weaker typing than psycopg3 | psycopg 3 |
| **asyncpg / async SQLAlchemy / `async_sessionmaker`** | Would fork the entire sync codebase (sync Session + `def` endpoints) for no throughput need at this scale | Sync `psycopg` + sync `Session` |
| **Alembic multidb template** | For migrating several DBs in one run; here each node migrates its own single DB | One history + `DATABASE_URL` + dialect-conditional batch/DDL |
| **SQLModel** | Already rejected in v1 (lags SQLAlchemy, thin docs); no reason to revisit | SQLAlchemy 2.0 declarative (unchanged) |
| **A second serialization lib (marshmallow, custom binary)** | pydantic + stdlib `json` already cover the sync envelope | pydantic `SyncEnvelope` + `json` |
| **Docker/pgbouncer on the client** | Clients stay SQLite + `run.bat`; no Postgres, no pooler there | Client engine unchanged |

## Stack Patterns by Variant

**If deploying the central server (VPS):**
- Install the `[server]` optional group (`psycopg[binary]`), set `DATABASE_URL=postgresql+psycopg://...`, run `alembic upgrade head` against Postgres, and add the plpgsql append-only trigger via the dialect-gated migration.
- Do NOT attach the SQLite PRAGMA `connect` listener to the Postgres engine.

**If running an operator client (Windows, offline-capable):**
- Nothing changes about the DB layer — still `sqlite:///data/myorishop.db`, WAL, PRAGMAs, `run.bat`. It gains only the login screen, the `httpx` push/pull module, and a USB export/import action. `psycopg` is never installed here.

**If online sync is available:** `httpx.Client` push/pull against `/sync/*` with the `SYNC_TOKEN` header.

**If offline (USB) only:** the same NDJSON serializer writes to / reads from a file on the flash drive; import runs the identical insert-if-absent merge. No transport-specific code beyond "bytes from HTTP body" vs "bytes from file".

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| sqlalchemy 2.0.x | psycopg 3.3.4 | Dialect `postgresql+psycopg` is native to SQLAlchemy 2.0. Verified requires-python >=3.10. **HIGH** |
| fastapi 0.139.0 | starlette 1.3.1 | Installed in the venv; `SessionMiddleware` ships in Starlette. **HIGH** |
| starlette SessionMiddleware | itsdangerous 2.2.0 | Middleware asserts itsdangerous is importable at startup. **HIGH** |
| pwdlib 0.3.0 | argon2-cffi 25.1.0 | `pwdlib[argon2]` requires `argon2-cffi >=23.1.0,<26` — 25.1.0 fits. **HIGH** |
| pwdlib 0.3.0 (bcrypt extra) | bcrypt 5.0.0 | `pwdlib[bcrypt]` requires `bcrypt >=4.1.2,<6` — 5.0.0 fits (only if you pick bcrypt over argon2). **HIGH** |
| httpx 0.28.1 | Python 3.13 | Already used as the TestClient backend; promote to runtime. **HIGH** |
| psycopg 3.3.4 | Python 3.13 | requires-python >=3.10. `[binary]` avoids a libpq build on the server. **HIGH** |
| passlib 1.7.4 | Python 3.13 | **INCOMPATIBLE in spirit** — relies on stdlib `crypt`, removed in 3.13 (PEP 594); unmaintained since 2020. Do not add. **HIGH** |

## Sources

- https://pypi.org/pypi/psycopg/json — 3.3.4, requires-python >=3.10, released 2026-05-01 (verified 2026-07-18, HIGH)
- https://pypi.org/pypi/pwdlib/json — 0.3.0; extras `argon2` (argon2-cffi >=23.1.0,<26), `bcrypt` (bcrypt >=4.1.2,<6) (verified 2026-07-18, HIGH)
- https://pypi.org/pypi/argon2-cffi/json — 25.1.0 (verified 2026-07-18, HIGH)
- https://pypi.org/pypi/itsdangerous/json — 2.2.0 (verified 2026-07-18, HIGH)
- https://pypi.org/pypi/httpx/json — 0.28.1 (verified 2026-07-18, HIGH)
- https://pypi.org/pypi/bcrypt/json — 5.0.0 (verified 2026-07-18, HIGH)
- https://pypi.org/pypi/passlib/json — 1.7.4, last release 2020; unmaintained (verified 2026-07-18, HIGH)
- Installed venv introspection — starlette 1.3.1 / fastapi 0.139.0 (verified 2026-07-18, HIGH)
- Codebase read — `app/models.py` (UUID PK, device_id/seq, synced_at, portable partial indexes), `app/db.py` (SQLite PRAGMA listener, `APPEND_ONLY_TRIGGERS`, frozen migration-0001 copy), `app/services/ledger.py` (`record_operation` single write path, `created_by` from settings), `app/config.py` (pydantic-settings) (verified 2026-07-18, HIGH)
- PEP 594 (removal of `crypt`/`spwd` in Python 3.13) and OWASP Password Storage guidance (Argon2id first choice) — general/standards knowledge (MEDIUM-HIGH)

---
*Stack research for: v3.0 central server + sync + auth additions to a mature FastAPI/SQLAlchemy/SQLite local-first app*
*Researched: 2026-07-18*
