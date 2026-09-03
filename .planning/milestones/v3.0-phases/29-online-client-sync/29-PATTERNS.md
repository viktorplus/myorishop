# Phase 29: Online Client Sync - Pattern Map

**Mapped:** 2026-07-20
**Files analyzed:** 9 (4 new, 5 extended)
**Analogs found:** 9 / 9 (all in-repo, verified this session)

All analogs below are confirmed with exact file:line. Follow CLAUDE.md: portable
SQLAlchemy only (no SQLite-specific SQL), sync `Session` + `def` endpoints, money
as integer minor units, secrets in `.env` never in the synced DB.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/sync_client.py` (NEW) | service (outbound driver) | request-response / batch | `app/routes/sync.py` (server txn+merge), `app/services/merge.py`, `app/services/sync.py` | role-match (client mirror of server) |
| `app/templates/partials/sync_status.html` (NEW) | template (OOB partial) | event-driven (HTMX swap) | `app/templates/partials/cash_balance.html` | exact |
| `alembic/versions/0020_*.py` (NEW) | migration | schema | `alembic/versions/0003_products_code_active_unique.py`, `0019_device_tokens.py` | exact |
| `app/routes/sync.py` (EXTEND) | route (def handler) | request-response | `app/routes/finance.py` `_movement_success` | exact |
| `app/config.py` (EXTEND) | config | — | `app/config.py` `secret_key`/`device_id` | exact (same file) |
| `app/main.py` (EXTEND) | provider (lifespan task) | event-driven (loop) | `app/main.py` existing `lifespan` | exact (same file) |
| `app/models.py` (EXTEND) | model + partial index | — | `app/models.py` `Product.__table_args__` (uq_products_code_active) | exact |
| `app/templates/base.html` (EXTEND) | template (nav host) | — | `app/templates/base.html` `<nav>` | exact (same file) |
| `pyproject.toml` (EXTEND) | config (deps) | — | existing `[project].dependencies` | n/a |

## Pattern Assignments

### `app/services/sync_client.py` (service, outbound driver)

This is the one genuinely new module. It has NO single analog; it composes three
existing pieces. Reuse the wire/merge core verbatim — do not re-implement it.

**Merge/wire core to reuse (`app/services/merge.py`):**
- `KIND_TO_FIELDS` (line 79) — per-kind column set; use `KIND_TO_FIELDS["operation"]` / `["cash_movement"]` to project ledger rows into wire `data` dicts.
- `class ExchangeRecord(kind, data)` (line 92) — frozen wire record.
- `serialize_exchange(records, *, schema_version, source_device_id, generated_at)` (line 527) — builds NDJSON push body. Exact call signature is used by the server pull route (see below).
- `parse_exchange(lines)` (line 138) — validates a pulled NDJSON page before any DB touch.
- `apply_merge(session, batch, *, server_now)` (line 464) — applies pulled records; use for NEW rows only (see D-14 note).
- `_REFERENCE_INSERT_ORDER` (line 249): `("warehouse", "product", "customer", "dictionary", "batch", "sale")` — the FK-dependency order the D-13 push closure must follow when including locally-authored reference parents.

**Push envelope call — copy the server pull route's exact `serialize_exchange` usage** (`app/routes/sync.py:174-179`):
```python
lines = serialize_exchange(
    page.records,
    schema_version=current_schema_version(session),   # from app.services.sync
    source_device_id=settings.device_id,
    generated_at=utcnow_iso(),                         # from app.core
)
```

**Pull collection constants (`app/services/sync.py`):** `PULL_KINDS` (line 58),
`DEFAULT_PULL_LIMIT = 500` (line 79), `current_schema_version(session)` (line 225).
The client pulls from `GET /api/sync/pull` and MUST echo BOTH `X-Sync-Next-Since`
and `X-Sync-Next-After-Id` headers back as `since`/`after_id` params — the server
contract documents this cursor requirement (`app/routes/sync.py:142-146, 181-190`).

**Server transaction idiom to mirror for pull-apply** (`app/routes/sync.py:111-113`):
```python
session.rollback()          # discard any autobegun read txn
with session.begin():       # ONE owned write txn per page
    report = apply_merge(session, batch, server_now=utcnow_iso())
```

**D-14 — client reference UPSERT (server-wins-on-update) is NEW code, NOT `_upsert_reference`.**
`app/services/merge.py:420-447` `_upsert_reference` is explicitly **insert-if-new /
existing-UUID-DISCARDED** (docstring line 427-438: "An EXISTING UUID is DISCARDED …
Insert-only — no UPDATE, no DELETE"). On the client that means the client keeps its
stale row and drops the server's edit. Per D-14 the client pull-apply MUST overwrite
an existing row matched by UUID with the server's version. Keep the existing insert
path for new rows; add a dedicated update-existing branch. Ledger rows stay
insert-only/idempotent (do not overwrite operations/cash_movements).

**Bearer token / offline-safe rules (from `app/routes/sync.py` docstring 15-18 and Security Domain):**
- Send token ONLY via `Authorization: Bearer {settings.sync_token}` header, never a query string, never logged.
- Strict `httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)` (Claude's discretion, research A1).
- Catch `httpx.HTTPError` → return a `SyncResult`, never let it raise out of `/sync/run`.
- Stamp `synced_at` ONLY after `resp.raise_for_status()` passes (Pitfall 3).

**Badge query (D-11) — new helper `unsynced_count(session)`:**
```python
ops = session.scalar(select(func.count()).select_from(Operation).where(Operation.synced_at.is_(None))) or 0
cash = session.scalar(select(func.count()).select_from(CashMovement).where(CashMovement.synced_at.is_(None))) or 0
return ops + cash
```

**Single-run guard (D-09):** module-level `_run_lock = threading.Lock()`; both the
`def` handler and the loop tick (which runs in a thread via `anyio.to_thread.run_sync`)
guard the critical section with `_run_lock.acquire(blocking=False)`. Use
`threading.Lock` NOT `asyncio.Lock` (the body runs in a thread in both paths).

---

### `app/templates/partials/sync_status.html` (template, OOB partial)

**Analog:** `app/templates/partials/cash_balance.html` (whole file, 4 lines).

**Exact idiom to copy** (`cash_balance.html:4`):
```jinja
<p id="cash-balance" class="num"{% if oob %} hx-swap-oob="true"{% endif %}><strong>{{ balance_cents | cents }}</strong></p>
```
The `{% if oob %} hx-swap-oob="true"{% endif %}` on an id'd element is the entire
mechanism: the SAME template renders inline on a full page load (`oob` unset) and
as an out-of-band swap when the handler passes `oob=True`. Make two id'd spans
(`#sync-status`, `#sync-badge`); hide the badge when `unsynced == 0` (D-12).

---

### `app/routes/sync.py` — EXTEND: add `POST /sync/run` (route, def handler)

**Analog:** `app/routes/finance.py:161-174` `_movement_success`.

**Exact OOB-partial return idiom to copy** (`finance.py:165-174`):
```python
balance_html = templates.get_template("partials/cash_balance.html").render(
    oob=True, balance_cents=compute_balance(session)
)
return HTMLResponse(form_html + balance_html + history_html)
```
The new handler renders `partials/sync_status.html` with `oob=True` and returns it
as `HTMLResponse`. It is a plain `def` handler (threadpool), acquires `_run_lock`
non-blocking, calls `run_sync_once`, formats the RU D-12 string, and ALWAYS returns
200 with the partial (never a 5xx on network failure — SYNC-06).

**Wiring note:** the new `POST /sync/run` is a NORMAL app route behind the
app-level `auth_guard` — it must live on a DIFFERENT router or be registered so it
is NOT under the `/api/sync/` bypass prefix. The existing `/api/sync/push` and
`/api/sync/pull` (lines 57, 127) stay untouched and token-gated. `app/main.py:150-155`
documents that the `sync.router` include has NO `dependencies=` because `/api/sync/`
bypasses `auth_guard`; `/sync/run` must be guarded, so verify the prefix boundary
in `app/services/security.py` (SYNC_PATH_PREFIX) — do not accidentally expose
`/sync/run` under the token-bypass.

---

### `app/config.py` — EXTEND: `sync_server_url` + `sync_token`

**Analog:** same file — `secret_key` (line 35) and `device_id` (line 45) secret
handling, resolved via `_resolve_local_identity` (lines 60-78).

Add two `Settings` fields (env `SYNC_SERVER_URL` / `SYNC_TOKEN`):
```python
sync_server_url: str = ""     # e.g. https://sync.example.com
sync_token: str = ""          # per-device Bearer secret; NEVER log (CLAUDE.md)
```
`sync_token` is a secret → resolve from `.env` only (like `secret_key`), NEVER store
in the synced DB (Security Domain: leaks on DB copy). Both empty by default → sync is
a no-op / "not configured" (offline-first, SRV-03). The auto-sync toggle+interval do
NOT go here (they must be runtime-mutable — D-15 puts them in `sync_state`).

---

### `app/main.py` — EXTEND: lifespan auto-sync loop

**Analog:** same file — existing `lifespan` (lines 58-63).

**Existing lifespan to EXTEND (do NOT remove `startup_backup`)** (`main.py:58-63`):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    backup_service.startup_backup()   # EXISTING — keep
    yield
```
Add: `task = asyncio.create_task(_auto_sync_loop())` after `startup_backup()`, then
in a `finally` after `yield` do `task.cancel()` + `with contextlib.suppress(asyncio.CancelledError): await task`
(D-08 clean shutdown). The loop reads the toggle+interval FRESH from `sync_state`
each tick (fresh `Session` per tick — D-07), and offloads the blocking driver via
`anyio.to_thread.run_sync(sync_client.run_sync_tick)`. Wrap each tick body in a broad
`try/except: pass` so offline silently skips (D-08). Test `run_sync_tick` directly,
never the infinite loop.

Note the `settings`-alias precedent: `main.py:12` imports config as
`config_settings` to avoid colliding with the `settings` route submodule — reuse
that alias when reading config in the loop.

---

### `app/models.py` — EXTEND: `SyncState` model + partial indexes

**Analog:** `app/models.py:158-166` `Product.__table_args__` (uq_products_code_active).

**Exact partial-index-in-model idiom to copy** (`models.py:158-166`):
```python
__table_args__ = (
    Index(
        "uq_products_code_active",
        "code",
        unique=True,
        sqlite_where=text("deleted_at IS NULL"),
        postgresql_where=text("deleted_at IS NULL"),
    ),
)
```
**Why declare in the model (Pitfall 5):** `tests/conftest.py` builds schema via
`Base.metadata.create_all`, NOT Alembic. A partial index (or `sync_state` table)
declared only in the migration will be ABSENT in test DBs. Declare BOTH the
`SyncState` model AND the two partial `Index(... sqlite_where + postgresql_where ...)`
on `operations`/`cash_movements.synced_at` in `models.py`, AND write the migration —
keep them in lockstep.

`SyncState` columns (D-10 + D-15, all five): `id` (PK, singleton = 1),
`last_sync_at` `String(32)`, `last_status` `String(16)` (ok|partial|error),
`last_result` `String(300)`, `auto_enabled` `Integer` default 0,
`auto_interval_seconds` `Integer` default 300. Use `String`/`Integer` only (portable).
`synced_at` columns already exist on `Operation` (~line 374) and `CashMovement`
(~line 503) — the indexes attach to those.

---

### `alembic/versions/0020_*.py` — NEW migration

**Analogs:** `alembic/versions/0003_products_code_active_unique.py` (partial index),
`alembic/versions/0019_device_tokens.py` (create_table + portability header).

**Partial index idiom to copy** (`0003:28-36`):
```python
op.create_index(
    "uq_products_code_active", "products", ["code"], unique=True,
    sqlite_where=sa.text("deleted_at IS NULL"),
    postgresql_where=sa.text("deleted_at IS NULL"),
)
```
For 0020: two non-unique partial indexes `ix_operations_unsynced` /
`ix_cash_movements_unsynced` on `["synced_at"]` with `sqlite_where` +
`postgresql_where` = `sa.text("synced_at IS NULL")`.

**create_table idiom to copy** (`0019:42-58`): `sa.String(n)` / `sa.Integer()` columns,
`sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_state"))`. Five columns per D-10+D-15.

**Migration immutability rule (WR-06):** the file must NEVER import application
modules — stdlib + `sqlalchemy as sa` + `from alembic import op` only, with FROZEN
copies of all values (both 0003:13-14 and 0019:26-27 state this). `render_as_batch`
is auto-derived per dialect in `alembic/env.py` — no per-migration handling.
`revision = "0020"`, `down_revision = "0019"`. Must pass PG parity (SRV-01,
`tests/test_pg_parity.py` + `tests/test_merge_pg.py` on postgres:17).

---

### `app/templates/base.html` — EXTEND: render partial + button in `<nav>`

**Analog:** same file — existing `<nav>` (lines 37-58), with the logout link
(line 56) as the `hx-post` pattern precedent.

**Existing hx-post nav link to mirror** (`base.html:56`):
```jinja
<a hx-post="/logout" style="margin-left:auto;cursor:pointer">{{ current_user.display_name }} · Выйти</a>
```
Add a `<a hx-post="/sync/run" hx-indicator="#sync-spinner" style="cursor:pointer">Синхронизировать</a>`
plus `{% include "partials/sync_status.html" %}` inside `<nav>` (glanceable on every
page — D-01). The `htmx-config` meta (line 18) marks 4xx as non-swapping; the handler
must return 200 for the OOB swap to land (matches the `_redirect_to_login` note at
`main.py:89-100`).

---

### `pyproject.toml` — EXTEND: promote httpx to runtime

Move `httpx` from `[dependency-groups].dev` into `[project].dependencies` as
`"httpx==0.28.*"` (the driver imports httpx at app runtime; a `uv sync --no-dev`
deploy would `ImportError`). `anyio` needs no add (transitive via starlette). Then
`uv lock && uv sync`. No NEW external package is introduced.

## Shared Patterns

### OOB partial refresh (HTMX)
**Source:** `app/templates/partials/cash_balance.html:4` + `app/routes/finance.py:161-174`
**Apply to:** `sync_status.html` + the `POST /sync/run` handler.
Same-template-serves-both idiom; handler renders with `oob=True` and returns `HTMLResponse`.

### Portable partial index (SQLite + PostgreSQL)
**Source:** `app/models.py:158-166` (model) + `alembic/versions/0003:28-36` (migration)
**Apply to:** the two `synced_at` indexes in both `models.py` and migration 0020.
`sqlite_where` + `postgresql_where` = `text("synced_at IS NULL")`. Declare in BOTH
places (create_all for tests, Alembic for real DBs).

### Secret in `.env`, never in the synced DB
**Source:** `app/config.py:35, 60-78`
**Apply to:** `sync_token` (resolve from `.env` like `secret_key`; never log — CLAUDE.md).

### Sync `def` + owned transaction + reused merge core
**Source:** `app/routes/sync.py:57-124` (push route: `def`, `session.rollback()` →
`with session.begin(): apply_merge(...)`)
**Apply to:** the client driver's push-stamp and pull-apply stages.

### Bearer token only via Authorization header
**Source:** `app/routes/sync.py` docstring (15-18), Security Domain threat table
**Apply to:** every outbound `client.post`/`client.get` in `sync_client.py`.

## No Analog Found

| File | Role | Data Flow | Reason / Guidance |
|------|------|-----------|-------------------|
| (partial) `app/services/sync_client.py` client reference UPSERT (D-14 update-existing branch) | service | transform | No existing code overwrites an existing reference row by UUID — `merge._upsert_reference` (merge.py:420-447) is deliberately insert-only/discard-existing. This ONE branch is genuinely new; model it on the same `_partition_new` split but take the "existing" set and UPDATE instead of discard. |
| `app/services/sync_client.py` lifespan asyncio loop + `threading.Lock` guard | provider | event-driven | No prior background loop in the repo (backup is a blocking startup call, not a loop). Follow research Pattern 2 (main.py:245-278 sketch); `anyio.to_thread.run_sync` off-loop, fresh Session per tick. |

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/`,
`app/`, `alembic/versions/`, `tests/`
**Files read this session:** cash_balance.html, config.py, main.py, sync.py (route),
finance.py (excerpt), models.py (excerpt), merge.py (excerpts), sync.py (service, grep),
0003 + 0019 migrations, conftest.py (device_client), base.html
**Test seam:** `run_sync_once(session, *, client)` — inject `httpx.Client`; tests use
`httpx.ASGITransport(app=main.app)` (real merge, reuse `device_client` mint path,
conftest.py:221-258) or `httpx.MockTransport` (offline/5xx/401). No `respx` needed.
**Pattern extraction date:** 2026-07-20
