# Architecture Research

**Domain:** Local-first inventory app gaining multi-operator sync (central PostgreSQL server), mandatory auth, and admin/operator roles — integrated onto an existing append-only event ledger
**Researched:** 2026-07-18
**Confidence:** HIGH (grounded in the current codebase; the sync foundation was seeded deliberately since v1.0)

## Executive Orientation

The v1.0–v2.0 architecture was built *for this milestone*. The heavy lifting is already done in the data model, and the job of v3.0 is to **wire up machinery the schema was pre-shaped for**, not to redesign. Concretely, the code already carries:

- `operations` and `cash_movements`: append-only ledgers, UUID4 TEXT PKs, `device_id` + per-device `seq` with `UniqueConstraint(device_id, seq)`, and a **`synced_at` column explicitly commented "v2 sync cursor"** (`app/models.py:355,469`).
- DB triggers `operations_no_update/_no_delete` (and cash equivalents) whose defining comment already says: *"the v2 sync milestone relaxes the UPDATE trigger with a WHEN clause in a NEW migration"* (`app/db.py:16-21`).
- `record_operation()` as the sole stock write path, plus `rebuild_stock()` / `compute_stock()` that recompute every cache from the ledger alone (`app/services/ledger.py`).
- UUID PKs on every business entity, integer-cents money, UTC ISO-8601 text timestamps — all portable to PostgreSQL unchanged.
- `created_by` (String(100)) already stamped on every ledger row — the user-attribution hook, currently fed from static config.
- Partial indexes already carry `postgresql_where=` beside `sqlite_where=` (`app/models.py:150-154`).

This validates the intended approach: **log-shipping + idempotent replay keyed by UUID** for the ledgers, **cache recompute after merge**, and a **single model set / single Alembic history** across SQLite (client) and PostgreSQL (server).

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  CLIENT (per operator install)  — FastAPI + Uvicorn on localhost      │
├──────────────────────────────────────────────────────────────────────┤
│  Browser (HTMX)                                                        │
│      │   desktop routers            mobile_* routers                   │
│      ▼   (auth dependency)          (auth dependency)                  │
│  ┌────────────────────────────────────────────────────────────┐       │
│  │ Auth layer: SessionMiddleware (signed cookie)              │ NEW   │
│  │            + require_user / require_admin dependencies      │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │ Services (register_sale, register_receipt, cash, …)        │ MOD   │
│  │   └─ record_operation()  ← now stamps user_id + device_id  │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │ Sync client: collect unsynced ops → push / pull            │ NEW   │
│  │   ├─ serialize batch (ops+cash+entities)  ── shared core    │       │
│  │   ├─ ingest_batch() verbatim + dedup-by-UUID               │       │
│  │   └─ rebuild_stock() after merge                            │       │
│  ├────────────────────────────────────────────────────────────┤       │
│  │ SQLite (WAL, FK on) — ledgers + caches + users + sync_state│ MOD   │
│  └────────────────────────────────────────────────────────────┘       │
│      │  HTTP  (online)              │  file export/import  (USB) NEW   │
└──────┼─────────────────────────────┼──────────────────────────────────┘
       ▼                             ▼
┌──────────────────────────────────┐   ┌──────────────────────────┐
│ CENTRAL SERVER (VPS)             │   │  USB flash drive         │
│  FastAPI  /sync/push  /sync/pull │   │  exchange.batch file     │
│    ├─ ingest_batch()  (SAME core)│   │  (SAME serialization)    │
│    ├─ rebuild_stock() after merge│   └──────────────────────────┘
│    └─ auth (user/device token)   │            ▲
│  PostgreSQL (same models,        │            │ same ingest_batch()
│   same Alembic history, triggers │────────────┘
│   in PG dialect)                 │
└──────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status | Implementation |
|-----------|----------------|--------|----------------|
| `record_operation()` | Single local stock write path; append op + bump caches | **MODIFIED** | Add `user_id`; take user from request, not `settings.operator_name` |
| `ingest_batch()` | Replay a batch of foreign ops/entities verbatim, dedup by UUID, preserve `id/device_id/seq/created_by/user_id` | **NEW** | Distinct from `record_operation` — bypasses IN-01 deleted-product guard, does NOT re-stamp seq |
| Batch serializer/deserializer | One JSON (or SQLite-file) format for the exchange payload | **NEW** | Same object for HTTP body and USB file |
| Sync client | Collect `synced_at IS NULL` ops, push; send watermarks, pull; recompute; stamp `synced_at` | **NEW** | Client-side orchestration + `sync_state` cursor table |
| Sync server API | `/sync/push`, `/sync/pull`; ack per-device watermark | **NEW** | FastAPI on VPS; calls the SAME `ingest_batch()` + `rebuild_stock()` |
| Auth layer | Login, password hash, session cookie, role gating | **NEW** | `SessionMiddleware` + `require_user`/`require_admin` deps |
| `users` table | Identity + role (administrator/operator) | **NEW** | UUID PK, `login` unique, `password_hash`, `role`, `device_id` optional |
| `sync_state` table | Per-remote-`device_id` last-ingested `seq` (pull cursor) | **NEW** | Client-side watermark store |
| `rebuild_stock()` | Recompute `Product.quantity` + `Batch.quantity` from ledger; assert invariant | **REUSED** | Call after every merge (client pull, server push, USB import) |
| Append-only triggers | Block UPDATE/DELETE on ledgers | **MODIFIED** | Relax UPDATE to allow the `synced_at` NULL→value stamp; add PG-dialect version |
| Alembic `env.py` | One history, both dialects | **MODIFIED** | `render_as_batch` only for SQLite; trigger DDL branches on dialect |

## Recommended Project Structure

```
app/
├── main.py                 # MOD: add SessionMiddleware; group routers by role dependency
├── config.py               # MOD: device_id becomes per-install UUID; add server_url, secret_key
├── db.py                   # MOD: guard SQLite-only connect-event pragmas by dialect
├── models.py               # MOD: + User; + user_id on operations/cash/sales; + sync_state
├── auth/                   # NEW
│   ├── security.py         #   password hash/verify (passlib[bcrypt] or hashlib.pbkdf2)
│   ├── dependencies.py     #   require_user, require_admin, current_user
│   └── routes.py           #   GET/POST /login, POST /logout, /users admin CRUD
├── sync/                   # NEW  (the whole sync subsystem, transport-agnostic)
│   ├── serialize.py        #   batch <-> dict/JSON  (the ONE exchange format)
│   ├── ingest.py           #   ingest_batch(): verbatim replay + dedup + FK ordering
│   ├── collect.py          #   gather local unsynced ops + referenced entities
│   ├── client.py           #   push()/pull() over HTTP; watermark bookkeeping
│   └── usb.py              #   export_file()/import_file() → reuse serialize+ingest
├── routes/                 # MOD: add role dependency to each router include
└── services/
    └── ledger.py           # MOD: record_operation() gains user attribution

server/                     # NEW  (central server; imports app.models + app.sync)
├── main.py                 #   FastAPI: /sync/push, /sync/pull, /users
├── db.py                   #   PostgreSQL engine (postgresql+psycopg://)
└── .env                    #   DATABASE_URL, SECRET_KEY  (never committed)
```

### Structure Rationale

- **`sync/` is transport-agnostic on purpose.** `serialize.py` + `ingest.py` are pure functions over a session and a batch dict. `client.py` (HTTP) and `usb.py` (file) are two thin callers. This is what makes "USB reuses the online format" true by construction rather than by discipline.
- **`server/` imports `app.models` and `app.sync`,** it does not fork them. One model set, one Alembic history. The server is a different *deployment* of the same schema, not a different codebase.
- **`auth/` is its own package** so the security boundary is auditable in one place (matches how the project already isolates `core.py` as "the only sanctioned conversion points").

## Architectural Patterns

### Pattern 1: Two-tier replication — append-only log-shipping vs. reference LWW

**What:** Split tables into two replication tiers instead of one uniform strategy.

- **Tier A — Append-only logs (the money-critical data):** `operations`, `cash_movements`, and the effectively-immutable `sales` headers and `batches`-at-creation. These have UUID PKs and are never updated. Replicate by **log-shipping + idempotent replay**: ship the rows; on receipt, `INSERT` each row verbatim, skipping any whose UUID PK already exists. `UniqueConstraint(device_id, seq)` is the second dedup guard. **No last-write-wins, no CRDT, no merge of row contents** — an append-only row's content never changes, so there is nothing to reconcile. This is the validated core the schema was built for.
- **Tier B — Mutable reference rows:** `products` (editable name/prices/thresholds), `warehouses`, `customers`, `customer_contacts`, `dictionary`, `catalog_prices`, `active_catalog`. These are edited in place. Replicate by **last-write-wins keyed by UUID + `updated_at`** (already present on all of them). Contention is low: reference data is predominantly administrator-owned, and two operators editing the *same* product row concurrently is rare.

**When to use:** This is the recommended v3.0 split. It concentrates the strong guarantee (no loss, no double-count) exactly where money lives (the ledgers), and accepts a pragmatic LWW where the domain tolerates it.

**Trade-offs:** LWW on Tier B can silently drop one of two concurrent edits to the same reference row. Acceptable for v3.0 given the operator model; if it ever bites, the *upgrade path* is already latent — `product_edited` / `price_change` audit ops exist in the ledger, so edits could later be event-sourced into Tier A. Do **not** build that now (YAGNI); note it.

**Critical detail — never ship the caches:** `Product.quantity` and `Batch.quantity` are derived caches. Exclude them from the Tier-B LWW payload, otherwise a metadata sync would clobber locally-correct stock. Stock is *only* ever set by replaying Tier-A ops and then `rebuild_stock()`.

```python
# ingest.py — idempotent replay, portable dedup (no SQLite-only INSERT OR IGNORE)
def ingest_operation(session, row: dict) -> bool:
    if session.get(Operation, row["id"]) is not None:
        return False                      # already have it — dedup by UUID PK
    session.add(Operation(**row))         # verbatim: keep id/device_id/seq/created_by/user_id
    return True                           # NOTE: bypasses record_operation() guards on purpose
```

### Pattern 2: Verbatim ingest is a *separate* write path from `record_operation()`

**What:** Replay must NOT go through `record_operation()`.

**Why:** `record_operation()` (a) re-stamps `seq = next_seq(device_id)` and `device_id = settings.device_id`, which would corrupt provenance; (b) rejects ops on soft-deleted products via the IN-01 guard (`ledger.py:85`) — but a legitimate historical op on a since-deleted product *must* replay; (c) increments caches incrementally, whereas after a bulk merge you want one authoritative `rebuild_stock()`.

**When to use:** All three merge entry points (server push-ingest, client pull-ingest, USB import) call `ingest_batch()`, never `record_operation()`.

**Trade-offs:** Two write paths to maintain. Mitigated by keeping `ingest_batch()` tiny and letting `rebuild_stock()` (which already *asserts* the stock invariant, `ledger.py:196`) be the correctness backstop after every merge.

### Pattern 3: FK-ordered batch, then one recompute

**What:** With `PRAGMA foreign_keys=ON` (SQLite) and native FKs (PostgreSQL), rows must be inserted parents-first. The exchange batch is an *ordered* structure and `ingest_batch()` inserts in dependency order:

```
users → warehouses → products → customers → customer_contacts
      → batches → sales → operations → cash_movements
```

Then call `rebuild_stock(session)` once at the end.

**When to use:** Every ingest, both transports.

**Trade-offs:** The serializer must include every entity an op references (its product, batch, warehouse, sale, customer, user). `collect.py` walks the unsynced ops and gathers their referenced entities so a fresh server can satisfy FKs. Simpler alternative if this proves fiddly: full-entity snapshots for Tier B on every sync (cheap at this data scale — thousands of rows).

### Pattern 4: Watermark/cursor tracking (push high-water + pull-per-device)

**What:** Two directions, two cursors.

- **Push:** client selects ledger rows `WHERE synced_at IS NULL`, sends them, server acks the max `seq` accepted per device, client stamps `synced_at = utcnow_iso()` on those rows. Stamping `synced_at` is the *only* UPDATE ever allowed on a ledger row — hence the pre-planned trigger relaxation.
- **Pull:** client keeps a `sync_state(device_id, last_seq)` row per *remote* device. It sends these watermarks; the server returns ops from *other* devices with `seq > last_seq`; client ingests idempotently and advances each watermark to the max `seq` ingested. Because `seq` is gapless per device, a watermark is sufficient and self-healing (a missed pull just resends next time).

**When to use:** Online sync. USB uses the same watermarks exchanged inside the file.

**Trade-offs:** Requires the server to preserve the client's original `device_id`/`seq` verbatim (Pattern 2). The default `device_id="device-01"` in `config.py:16` is a **fleet-wide collision hazard** — see Anti-Patterns.

### Pattern 5: Auth as a router-level dependency, session as thin middleware

**What:** Split the two concerns of "is this request authenticated?" and "may this user do this?".

- **Authentication / session:** Starlette `SessionMiddleware` (signed cookie via `SECRET_KEY`) stores `user_id` after login. A tiny `current_user` dependency loads the user from the session each request. Passwords hashed with `passlib[bcrypt]` (or stdlib `hashlib.pbkdf2_hmac` to avoid a dependency for a beginner).
- **Authorization / roles:** `require_user` and `require_admin` FastAPI **dependencies**, attached at the **router** level via `APIRouter(dependencies=[Depends(require_admin)])` or on the `include_router(..., dependencies=[...])` call in `main.py`.

Why dependencies over bespoke middleware for role-gating: they compose with the existing `get_session` DI, are unit-testable per route, give per-router granularity, and return proper redirects/403s. Middleware is used *only* for the cross-cutting "no session → redirect to `/login`" behavior so unauthenticated browser hits land on the login page instead of a raw 401.

**Desktop AND mobile trees:** both are plain `APIRouter`s included in `main.py`. Apply the same role dependency to each. Role→router map (from the milestone scope):

| Role | Desktop routers | Mobile routers |
|------|-----------------|----------------|
| **operator** (`require_user`) | receipts, sales, writeoffs, returns, corrections, transfers, finance, history, home, products(read), search | mobile_receipts, mobile_sales, mobile_writeoff, mobile_returns, mobile_corrections, mobile_transfers, mobile_finance, mobile_history, mobile_home, mobile_products, mobile_search |
| **administrator** (`require_admin`) | warehouses, dictionary, catalogs, categories, settings, reports, customers(CRUD), export, backup, **users** | mobile_reports, mobile_customers |
| **public** (no auth) | `auth/login`, `/static`, `/sync/*` (own token auth) | — |

```python
# main.py
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.include_router(sales.router,      dependencies=[Depends(require_user)])
app.include_router(warehouses.router, dependencies=[Depends(require_admin)])
app.include_router(auth.router)  # login/logout — no guard
```

**Trade-offs:** Router-level deps mean each `include_router` must be classified once. That is a one-time, explicit, reviewable table (above) — appropriate for the app's first security boundary.

## Data Flow

### Write flow (today → v3.0)

```
TODAY:  route → service → record_operation(device_id=settings, created_by=settings.operator_name)
                                              → append op + bump cache

v3.0:   authenticated route (request.session.user_id)
          → service(user)
          → record_operation(device_id=settings.device_id, user=current_user)
                                              → append op with user_id + created_by snapshot
                                              → bump cache   (unchanged)
```

`settings.operator_name` stops being the identity source; `settings.device_id` remains the per-install identity. `user_id` (FK) is added to `operations`, `cash_movements`, and `sales`; `created_by` is kept as a denormalized display snapshot (name at time of action) so history renders without a join and old rows stay valid.

### Sync push (online)

```
[Sync button/timer] → collect ops WHERE synced_at IS NULL (+ referenced entities)
   → serialize batch → POST /sync/push (user/device token)
   → server: ingest_batch() verbatim + dedup → rebuild_stock() → ack max seq/device
   → client: stamp synced_at on acked rows   (the ONLY allowed ledger UPDATE)
```

### Sync pull (online)

```
[Sync] → send sync_state watermarks (per remote device_id)
   → server: return ops WHERE device_id != me AND seq > watermark
   → client: ingest_batch() verbatim + dedup → rebuild_stock()
   → advance each watermark to max ingested seq
```

### USB (offline) — identical core

```
Export:  collect (same as push) → serialize → write exchange.batch to USB
Import:  read exchange.batch → ingest_batch() (same) → rebuild_stock() (same)
         → advance watermarks / stamp synced_at from the file's ack section
```

The *only* difference between online and USB is the transport of an identical batch object. No second merge implementation exists.

## SQLite (client) ↔ PostgreSQL (server): one model, one history

| Concern | Approach | Status |
|---------|----------|--------|
| Models | Already portable: `String(36)` UUIDs, `Integer` cents, `JSON`, `String` timestamps, partial indexes carry `postgresql_where` | **REUSED** |
| Alembic history | One linear history (`0001`..`00NN`) runs on both; server does `alembic upgrade head` against the PG URL | **REUSED** + MOD |
| `render_as_batch` | Currently hardcoded `True` (`env.py:48,72`). Make it `connection.dialect.name == "sqlite"` — batch mode is a SQLite move-and-copy hack, unwanted on PG | **MODIFIED** |
| Append-only triggers | `0001` ships SQLite `CREATE TRIGGER ... RAISE(ABORT)`. Migrations that touch triggers must branch on `op.get_bind().dialect.name`: PG uses a `BEFORE UPDATE/DELETE` trigger **function** raising an exception | **MODIFIED / NEW** |
| Connect-event pragmas | `PRAGMA journal_mode=WAL / foreign_keys=ON / busy_timeout` are SQLite-only (`db.py:51-61`); guard by dialect. PG enforces FKs natively, no WAL pragma | **MODIFIED** |
| Engine builder | `build_engine()` is SQLite-only; add a PG engine (`postgresql+psycopg://`) in `server/db.py`; no pragma listener | **NEW** |
| Config | Client `.env` keeps `db_path` + unique `device_id` + `server_url` + `secret_key`; server `.env` holds `DATABASE_URL` + `secret_key` | **MODIFIED** |
| Driver dep | Add `psycopg[binary]` (server only) | **NEW** |

The trigger-relaxation migration (allowing the `synced_at` NULL→value stamp) is the one the code already anticipates (`db.py:16-21`). Express it dialect-aware so it applies on both client SQLite and server PostgreSQL.

## Scaling Considerations

| Scale | Architecture adjustments |
|-------|--------------------------|
| 1–5 operators (year one target) | Manual/button-triggered sync is fine. Full-entity Tier-B snapshots per sync are cheap (thousands of rows). Single VPS PostgreSQL, no replication. |
| 5–50 operators / multi-country | Move to delta Tier-B (LWW by `updated_at` filter) to cut payload; background sync timer; add per-device auth tokens; index `operations(device_id, seq)` and `operations(synced_at)` (the latter for the client's push scan). |
| 50+ / high op volume | Paginate pull (`seq` ranges); consider server-side incremental cache maintenance instead of full `rebuild_stock()`; partition ledgers by device/period. Not remotely needed for this domain. |

### Scaling priorities

1. **First bottleneck:** the client's `WHERE synced_at IS NULL` push scan and the pull `seq > watermark` — both fixed by indexing `operations.synced_at` and relying on the existing `UniqueConstraint(device_id, seq)` index.
2. **Second bottleneck:** `rebuild_stock()` walks all products/batches on every merge. Fine for this scale; if data grows, recompute only the products touched by the just-ingested batch.

## Anti-Patterns

### Anti-Pattern 1: Reusing `record_operation()` to replay foreign ops

**What people do:** Loop incoming ops through `record_operation()` "to reuse the logic."
**Why it's wrong:** It re-stamps `device_id`/`seq`, destroying provenance and breaking watermark dedup; it rejects ops on soft-deleted products (IN-01); it double-counts caches. It fundamentally cannot replay another device's history.
**Do this instead:** `ingest_batch()` inserts rows verbatim, dedups by UUID, then one `rebuild_stock()`.

### Anti-Pattern 2: Shipping the derived caches

**What people do:** Include `Product.quantity` / `Batch.quantity` in the sync payload and write them on the receiver.
**Why it's wrong:** Two devices' caches are partial views; writing a remote cache over a local one corrupts stock. Caches are *projections*, not source of truth.
**Do this instead:** Never sync caches. Ship only ledger ops + reference metadata (minus quantity); recompute via `rebuild_stock()`.

### Anti-Pattern 3: The default `device_id="device-01"` on every install

**What people do:** Ship the config default (`config.py:16`) unchanged to every operator.
**Why it's wrong:** Two installs sharing a `device_id` produce colliding `(device_id, seq)` pairs → `IntegrityError` on the server, or silent op loss. This breaks the entire replication model.
**Do this instead:** Generate a unique `device_id` (a UUID) at first run / install and persist it. Treat a duplicate `device_id` as a fatal setup error. Add this as a first-run check.

### Anti-Pattern 4: Last-write-wins on the ledger, or CRDTs anywhere

**What people do:** Reach for LWW row-merging or a CRDT library "because it's sync."
**Why it's wrong:** The ledgers are append-only and immutable — there is no write to lose and nothing to converge; LWW/CRDT add complexity and risk *reducing* correctness. CRDTs solve concurrent mutation of shared state; this domain has none in Tier A.
**Do this instead:** Log-shipping + UUID dedup for Tier A; simple `updated_at` LWW only for low-contention Tier-B reference rows.

### Anti-Pattern 5: Editing the append-only trigger DDL in place

**What people do:** Change the `APPEND_ONLY_TRIGGERS` constant to allow the `synced_at` update.
**Why it's wrong:** Migration `0001` carries a *frozen* copy; the constant is for test fixtures. Editing it in place desyncs fixtures from migrated DBs (the code comment at `db.py:16-21` warns of exactly this).
**Do this instead:** Add a new dialect-aware migration that `DROP`s and re-creates the UPDATE trigger with a `WHEN` clause permitting only `NEW.synced_at IS NOT NULL AND OLD.synced_at IS NULL` (and no other column change).

## Integration Points

### Existing code touched

| Boundary | Change | Notes |
|----------|--------|-------|
| `record_operation()` ↔ all service callers | Thread `user` through; add `user_id` | Broad but mechanical; `device_id` still from settings |
| `rebuild_stock()` | Call site added after every merge | No change to the function itself — reused as the invariant backstop |
| `main.py` router includes | Add role `dependencies=` per router | One classification table; covers desktop + mobile |
| `db.py` connect-event | Guard SQLite pragmas by dialect | So the same module can back a PG server if ever co-located |
| `env.py` | Dialect-conditional `render_as_batch` + triggers | Enables one history on both engines |
| Append-only triggers | New migration relaxing UPDATE for `synced_at` | Pre-planned; dialect-aware |

### New surfaces

| Surface | Communication | Notes |
|---------|---------------|-------|
| Client ↔ Server | HTTPS JSON `/sync/push`, `/sync/pull` | Auth via user/device token; TLS on the VPS |
| Client ↔ USB | File `exchange.batch` (same JSON) | No network; same `ingest_batch()` |
| Login/session | Signed cookie (`SessionMiddleware`) | `SECRET_KEY` from env, never committed |
| `users` CRUD | Admin-only router | Seeds the first administrator at setup |

## Suggested Build Order (dependencies first)

1. **Auth + users + roles (client-local).** Add `users` table, password hashing, `/login` + `SessionMiddleware`, `require_user`/`require_admin`, classify every desktop + mobile router. Add `user_id` to `operations`/`cash_movements`/`sales`; thread `user` through `record_operation()`. *Rationale:* establishes identity — everything downstream attributes ops to a user; fully testable on one SQLite client before any server exists. *Also do here:* replace the `device_id` default with a first-run unique UUID.
2. **PostgreSQL portability.** Dialect-conditional `render_as_batch` + triggers + connect-event; PG engine builder; add `psycopg`; run `alembic upgrade head` against an empty PostgreSQL to prove the schema builds. *No sync logic yet.* *Rationale:* the server can't exist until the one model set provably runs on PG.
3. **Shared merge core (`sync/serialize.py` + `sync/ingest.py` + `sync/collect.py`).** Define the batch format; `ingest_batch()` verbatim replay + UUID dedup + FK ordering; `rebuild_stock()` after. Test by exporting a batch from one DB and importing into a fresh one — pure functions, no HTTP. *Rationale:* this is the single implementation both transports depend on; build and harden it in isolation.
4. **Server sync API + trigger relaxation.** `/sync/push` (ingest + ack watermark), `/sync/pull` (return other-device ops since watermark), endpoint auth. Ship the migration relaxing the append-only UPDATE trigger to permit the `synced_at` stamp; add client `sync_state` cursor table. *Rationale:* needs the core (3) and the identity/token (1) in place.
5. **Online client sync.** `sync/client.py`: collect→push→stamp `synced_at`; watermark→pull→ingest→recompute; a «Синхронизация» button + status UI. *Rationale:* wires the client to the API from (4).
6. **Offline USB sync.** `sync/usb.py`: export the same batch to a file; import through the same `ingest_batch()`; exchange watermarks/acks inside the file. UI for export/import. *Rationale:* pure reuse of (3); smallest increment, built last because it depends on the format and watermark semantics being final.

## Sources

- `app/models.py` — `operations`/`cash_movements` (UUID PK, `device_id`/`seq`, `UniqueConstraint`, `synced_at` "v2 sync cursor"), `created_by`, portable partial indexes (HIGH, direct source)
- `app/db.py:16-21` — append-only trigger DDL with explicit "v2 sync milestone relaxes the UPDATE trigger" note (HIGH)
- `app/services/ledger.py` — `record_operation()` single write path, IN-01 deleted-product guard, `next_seq()`, `compute_stock()`, `rebuild_stock()` invariant assertion (HIGH)
- `app/main.py`, `app/routes/__init__.py`, `app/routes/sales.py` — router structure (desktop + `mobile_*`), `get_session` DI, no existing auth (HIGH)
- `alembic/env.py` — single history, `render_as_batch=True` (hardcoded), URL from settings (HIGH)
- `app/config.py` — `device_id`/`operator_name` from `.env`; default `device_id="device-01"` collision hazard (HIGH)
- `.planning/PROJECT.md` — Key Decisions (event log from day one, `record_operation` choke point, local-first→PostgreSQL intent), v3.0 milestone scope (HIGH)
- `CLAUDE.md` "Stack Patterns by Variant" — UUID-for-sync, append-only-never-UPDATE/DELETE, portable-ORM-only, `postgresql+psycopg://` connection-string migration (HIGH)

---
*Architecture research for: multi-operator sync + central server + auth/roles over an existing append-only ledger*
*Researched: 2026-07-18*
