# Phase 29: Online Client Sync - Research

**Researched:** 2026-07-20
**Domain:** Client-side sync driver (outbound httpx), FastAPI lifespan background task, portable Alembic migration, HTMX OOB header partial
**Confidence:** HIGH (everything is in-repo verified; the two correctness risks in Open Questions are flagged for the planner, not guessed)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** «Синхронизировать» button, sync status, last-sync time, unsynced-count badge live in a **header partial rendered in `base.html`** (glanceable on every desktop page). Settings-only placement rejected (Settings is admin-gated).
- **D-02:** Refresh the header status/badge in place with the **existing OOB swap pattern from `app/templates/partials/cash_balance.html`** (`{% if oob %}hx-swap-oob="true"{% endif %}` on an id'd element). The sync action returns the sync-status partial OOB — no full page reload.
- **D-03:** Secondary sync config (auto-sync on/off toggle + interval value) may live in the Settings page; only the glanceable indicator + button belong in the header.
- **D-04:** The manual button runs sync **synchronously inside the HTMX request** (a `def` handler in the FastAPI threadpool), spinner via `hx-indicator`, then swaps the result partial.
- **D-05:** The outbound httpx client MUST use a strict **`httpx.Timeout`**; on timeout/transport error the handler catches the exception and returns an "offline/failed" partial — never a 5xx that would block the page.
- **D-06:** Optional interval auto-sync runs as an **asyncio background loop started in the FastAPI `lifespan`** (zero-dependency; keeps syncing with the tab closed). APScheduler/Celery/Redis rejected.
- **D-07:** The loop must NOT run the SQLAlchemy `Session` on the event loop — call the shared sync-driver via `anyio.to_thread.run_sync`, **fresh `Session` per tick**.
- **D-08:** Wrap each tick in a broad `try/except` that swallows connection/httpx errors (offline = silently skip a tick, no log spam, loop never dies). Read the on/off toggle **at the top of each iteration**. Cancel the task cleanly on shutdown (`task.cancel()`).
- **D-09:** Manual sync (D-04) and the loop (D-06) call **one shared sync-driver function** guarded by a single **"already running" flag/lock** so a click and a tick never overlap or double-sync.
- **D-10:** Persist a **single-row `sync_state` table** (`last_sync_at`, `last_status`, `last_result` text) written after **every** attempt in a `finally`/single exit point. One Alembic migration (`render_as_batch=True`) that also runs on PostgreSQL under the shared history (SRV-01). Plain single-row table, no SQLite-specific SQL.
- **D-11:** Badge is **always computed**, never stored: `COUNT(*) WHERE synced_at IS NULL` across `Operation` + `CashMovement`. Add a **partial index** (`... WHERE synced_at IS NULL`) on each. `last_sync_at` comes from `sync_state` (NOT `MAX(synced_at)`).
- **D-12:** Plain-language Russian result strings, times in `settings.display_tz` (Europe/Moscow):
  - Success (both): `Синхронизировано: отправлено 12, получено 5`
  - Success, no changes: `Синхронизировано, изменений нет`
  - Partial: `Синхронизировано частично: отправлено 8 из 12`
  - No connection: `Нет связи с сервером`
  - Server/other error: `Ошибка сервера, попробуйте позже`
  - Last-sync line: `Последняя синхронизация: 20.07.2026 14:32`
  - Never synced: `Ещё не синхронизировано`
  - Badge: show only when `> 0`; hide at zero.

### Claude's Discretion
- Exact `httpx.Timeout` values, spinner styling, the interval default and allowed range, and the internal shape of the sync-driver function.
- Status enum values for `sync_state.last_status` (suggested `ok` / `partial` / `error`).

### Deferred Ideas (OUT OF SCOPE)
- Sync history / verbose error log and a dedicated `/sync` page.
- Offline USB self-uploading file (Phase 30, OFF-*).
- Non-blocking background worker for the manual button.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYNC-01 | Manual push (ops + cash) + pull (reference data down); stock/figures stay correct | §Push Contract, §Pull Contract, §Pattern 1 (driver). Reuse `merge.serialize_exchange` / `merge.parse_exchange` / `merge.apply_merge`; recompute is inside `apply_merge`. **See Open Question 1 & 2 — two correctness gaps in the locked ledger-only push + insert-only pull-apply.** |
| SYNC-06 | Status + last-sync time + plain RU result; failure never blocks local work | §httpx Timeout & Offline-Safe Failure, §Pattern 4 (OOB partial), D-12 strings, `sync_state` (D-10). Handler catches `httpx.HTTPError`, returns partial, never 5xx. |
| SYNC-07 | Badge of unsynced local operations | §Badge Query + §Partial Index (D-11). `COUNT(*) WHERE synced_at IS NULL` on Operation + CashMovement. |
| SYNC-08 | Optional interval auto-sync; silent offline stop; disabled = manual only | §Pattern 2 (lifespan asyncio loop), D-06/07/08. Toggle read fresh per tick from DB. |
| SRV-03 | Desktop keeps working fully offline on local SQLite; server only needed for sync | Offline-safe failure (D-05/D-08); nothing in the local write path calls the network. Sync is additive. |
</phase_requirements>

## Summary

Phase 29 is a **client-side integration** phase. Every server contract already exists and is exercised by `tests/test_sync_api.py`: `POST /api/sync/push` (NDJSON body, Bearer device token, returns a JSON `MergeReport` projection) and `GET /api/sync/pull` (streams reference records as NDJSON with `X-Sync-Next-Since` / `X-Sync-Next-After-Id` cursor headers). The shared merge engine (`app/services/merge.py`) is PURE and reusable on the client for BOTH directions: `serialize_exchange` builds the push body, `parse_exchange` + `apply_merge` apply the pulled data. The migration-0018 trigger relaxation already permits the client's `UPDATE ... SET synced_at = ...` stamp.

The genuine build work is: (1) an **outbound httpx driver** that collects unsynced `Operation` + `CashMovement` rows, serializes them, POSTs them, stamps `synced_at` on success, then paginates the pull and applies it; (2) **client config** for the server base URL and per-device Bearer token; (3) a strict **`httpx.Timeout` + broad exception catch** so offline can only stall for the timeout window; (4) a **lifespan asyncio loop** offloading the sync-driver via `anyio.to_thread.run_sync` with a fresh Session per tick; (5) a **`threading.Lock`** single-run guard shared by the manual `def` handler and the loop tick (both execute the driver in a thread); (6) a **`sync_state` single-row table** + **partial indexes** via one portable Alembic migration; (7) a **header OOB partial** copied verbatim from `cash_balance.html`.

**Primary recommendation:** Build ONE pure-ish `run_sync_once(session, *, client)` driver reused by the manual handler and the loop, injecting the `httpx.Client` so tests can swap in `httpx.ASGITransport(app=...)` (real server, real merge) or `httpx.MockTransport` (offline/5xx). Promote `httpx` from a dev-only to a **runtime** dependency. **Escalate Open Questions 1 and 2 to the user before locking the plan** — the locked "push ops+cash only" and "reuse `apply_merge` for pull" decisions have real correctness gaps around locally-authored reference parents and server-wins-on-update semantics.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Collect unsynced rows, build push body | API/Backend (service) | Database | Reads local ledger, reuses `merge.serialize_exchange` — pure service logic |
| Outbound HTTP push/pull | API/Backend (new sync driver) | — | The single new network egress point; must stay off the event loop (threadpool/anyio thread) |
| Stamp `synced_at` after push | Database (write) | API/Backend | Local UPDATE; allowed by the 0018 column-scoped trigger |
| Apply pulled reference data | API/Backend (merge engine) | Database | Dedicated client-side **server-wins** upsert in one owned transaction (per **D-14** — NOT `merge.apply_merge`, whose insert-only/server-wins-by-discard semantics would drop server updates on rows the client already has) |
| Manual sync request handling | Frontend Server (FastAPI `def` route) | API/Backend | Threadpool `def` handler, returns OOB partial |
| Interval auto-sync scheduling | Frontend Server (lifespan asyncio task) | API/Backend | In-process background loop; offloads blocking work to a thread |
| Sync status / badge display | Browser/Client (HTMX OOB swap) | Frontend Server | Header partial, `hx-swap-oob="true"` |
| Server URL + token config | API/Backend (`app/config.py` Settings) | — | Token is a secret → resolved from `.env`, never the synced DB |
| Auto-sync toggle + interval persistence | Database (runtime-mutable single row) | Frontend Server | MUST be DB-backed (D-08: flip takes effect next tick) — `.env` cannot flip at runtime |

## Standard Stack

### Core (all already in-repo — no new external library except a promotion)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 | Outbound sync HTTP client | Already the repo's TestClient transport; `httpx.Client` (sync) matches the sync-Session rule; supports `Timeout`, `ASGITransport`, `MockTransport`. `[VERIFIED: pyproject.toml + uv venv import — httpx 0.28.1 present]` |
| anyio | (bundled via starlette/fastapi) | `anyio.to_thread.run_sync` to offload the blocking driver off the event loop (D-07) | Already a transitive runtime dependency of Starlette; FastAPI itself uses it for threadpool offload. `[VERIFIED: importable in uv venv]` |
| asyncio | stdlib | `create_task` / `sleep` / `task.cancel()` for the lifespan loop (D-06/D-08) | stdlib; the only zero-dependency option (D-06) `[VERIFIED: stdlib]` |
| threading | stdlib | `threading.Lock` single-run guard (D-09) | Both the manual `def` handler AND the loop tick execute the driver body **in a thread** (the loop offloads via `anyio.to_thread`), so a `threading.Lock` — not an `asyncio.Lock` — is the correct shared primitive `[VERIFIED: stdlib + code paths inspected]` |
| SQLAlchemy | 2.0.x | Unsynced-row query, `synced_at` UPDATE, `sync_state` upsert | Existing ORM; portable constructs only (CLAUDE.md) `[VERIFIED: pyproject.toml]` |
| Alembic | 1.18.x | `sync_state` table + partial indexes migration | Shared history runs on SQLite + PostgreSQL (SRV-01) `[VERIFIED: pyproject.toml + alembic/env.py]` |
| `app.services.merge` | in-repo | `serialize_exchange`, `parse_exchange`, `apply_merge`, `KIND_TO_FIELDS` | The single wire/merge core reused verbatim (SYNC-04) `[VERIFIED: read app/services/merge.py]` |
| `app.services.sync.current_schema_version` | in-repo | Header `schema_version` for the push envelope | Already used by the pull route `[VERIFIED: read app/services/sync.py]` |

### Supporting
| Component | Purpose | When to Use |
|-----------|---------|-------------|
| `httpx.ASGITransport(app=app)` | Point the driver's `httpx.Client` at the real in-process server app | Integration tests of the driver against the real merge engine (no live server) |
| `httpx.MockTransport(handler)` | Simulate offline (`raise httpx.ConnectError`), timeout, 401, 5xx | Offline-safe-failure + status-mapping tests |
| `zoneinfo.ZoneInfo` via `app.core` helpers | Format `last_sync_at` in `settings.display_tz` (D-12) | The last-sync line + result rendering — reuse existing `app/core.py` tz helpers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `httpx.Client` (sync) | `httpx.AsyncClient` | Async client would force async handling and contradict the locked sync-Session rule (CLAUDE.md) and D-04's threadpool `def` handler. Reject. |
| `threading.Lock` | `asyncio.Lock` | The driver body runs in a thread in BOTH paths (`anyio.to_thread` for the loop, threadpool for the `def` handler), so an asyncio lock cannot guard the actual critical section. Reject. |
| Reuse `merge.apply_merge` for pull-apply | Custom client-side upsert | `apply_merge` is insert-only/server-wins — correct for NEW rows but drops UPDATES to rows the client already has (see Open Question 2). Flag to user; do not silently invent a new merge. |
| httpx runtime dep | keep httpx dev-only | The driver imports httpx at APP runtime; a `run.bat` `uv sync --no-dev` deploy would `ImportError`. Must promote. |

**Installation / dependency change (the only packaging change this phase needs):**
```toml
# pyproject.toml — MOVE httpx from [dependency-groups].dev into [project].dependencies:
#   "httpx==0.28.*",
# anyio needs NO explicit add — it is already a transitive runtime dep of starlette/fastapi.
```
Then `uv sync` (or `uv lock && uv sync`).

**Version verification:**
```bash
uv run python -c "import httpx; print(httpx.__version__)"   # -> 0.28.1 (verified 2026-07-20)
```

## Package Legitimacy Audit

> No NEW external package is introduced. `httpx` is promoted from dev-only to runtime; it is already vetted and pinned in this repo (CLAUDE.md Technology Stack, verified 2026-07-08).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| httpx | PyPI | mature (8+ yrs line) | very high | github.com/encode/httpx | OK | Approved — promote to runtime dep |
| anyio | PyPI (transitive) | mature | very high | github.com/agronholm/anyio | OK | Already installed transitively via starlette; no add |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
                    ┌─────────────────────── DESKTOP CLIENT (this FastAPI app) ───────────────────────┐
                    │                                                                                  │
 [Operator clicks   │   POST /sync/run (def, threadpool)                                               │
  «Синхронизировать»]│           │                                                                     │
        │           │           ▼                                                                      │
        └──HTMX──────┼──►  try acquire threading.Lock (non-blocking) ──not acquired──► "уже идёт" partial
                    │           │ acquired                                                             │
 [lifespan asyncio   │          ▼                                                                      │
  loop tick (every N)│   run_sync_once(session, client)  ◄── anyio.to_thread.run_sync (loop path)     │
        │            │          │                                                                      │
        └──read toggle┼─►(if on)│                                                                      │
                    │           ├─(1) collect Operation/CashMovement WHERE synced_at IS NULL           │
                    │           ├─(2) serialize_exchange(records) ──► NDJSON body                      │
                    │           ├─(3) httpx.Client.post(server_url + /api/sync/push, Bearer token) ────┼──► SERVER
                    │           │        (strict httpx.Timeout)                                        │    /api/sync/push
                    │           ├─(4) on 200: UPDATE synced_at = utcnow_iso() on pushed row ids        │◄── MergeReport JSON
                    │           ├─(5) paginate GET /api/sync/pull (echo X-Sync-Next-* headers) ────────┼──► /api/sync/pull
                    │           │        each page: parse_exchange + apply_merge (one txn)             │◄── NDJSON pages
                    │           └─(6) finally: write sync_state(last_sync_at,last_status,last_result)  │
                    │                      │                                                            │
                    │                      ▼                                                            │
                    │   return SyncResult ─► format RU (D-12) ─► header OOB partial (hx-swap-oob)      │
                    │                                              #sync-status + #sync-badge          │
                    └──────────────────────────────────────────────────────────────────────────────────┘
   Offline: any httpx.HTTPError at (3) or (5) is caught → SyncResult(status="offline") → "Нет связи с сервером"
            local work (receipts/sales) never touches this path (SRV-03).
```

### Recommended Project Structure
```
app/
├── services/
│   └── sync_client.py     # NEW: run_sync_once() driver + collect/serialize/stamp/apply + result dataclass + RU formatter
├── routes/
│   └── sync.py            # EXTEND: add POST /sync/run (def handler, OOB partial) — keep the existing /api/sync/* server routes untouched
├── config.py             # EXTEND: sync_server_url + sync_token (from .env)
├── main.py               # EXTEND: lifespan starts/cancels the auto-sync asyncio task
├── models.py             # EXTEND: SyncState model + partial Index() on Operation/CashMovement.synced_at
├── db.py                 # unchanged (0018 triggers already permit synced_at UPDATE)
└── templates/
    ├── base.html         # EXTEND: render the sync-status header partial in <nav>
    └── partials/
        └── sync_status.html   # NEW: OOB partial (mirror cash_balance.html idiom)
alembic/versions/
└── 0020_sync_state_and_unsynced_indexes.py   # NEW migration (portable, render_as_batch auto)
```

### Pattern 1: The shared sync driver (D-09) — injectable client for testability

```python
# app/services/sync_client.py   (design sketch — planner refines)
import threading
from dataclasses import dataclass
import httpx
from sqlalchemy import select, update, func
from app.core import utcnow_iso
from app.models import Operation, CashMovement
from app.services import merge
from app.services.sync import current_schema_version
from app.config import settings

_run_lock = threading.Lock()   # D-09 single-run guard (shared by manual + loop)

@dataclass
class SyncResult:
    status: str          # "ok" | "partial" | "error" | "offline"
    pushed: int
    pushed_total: int
    pulled: int

_LEDGER = (("operation", Operation), ("cash_movement", CashMovement))

def run_sync_once(session, *, client: httpx.Client) -> SyncResult:
    """One full sync. Reused by the manual handler and the loop tick.
    `client` is injected so tests pass ASGITransport(real app) or MockTransport."""
    # (1) collect unsynced ledger rows
    push_rows, ids = [], {"operation": [], "cash_movement": []}
    for kind, model in _LEDGER:
        for row in session.scalars(select(model).where(model.synced_at.is_(None))):
            data = {f: getattr(row, f) for f in merge.KIND_TO_FIELDS[kind]}
            push_rows.append(merge.ExchangeRecord(kind=kind, data=data))
            ids[kind].append(row.id)
    pushed_total = len(push_rows)

    # (2)+(3) serialize + POST (strict timeout upstream on the client)
    body = "\n".join(merge.serialize_exchange(
        push_rows, schema_version=current_schema_version(session),
        source_device_id=settings.device_id, generated_at=utcnow_iso(),
    )).encode("utf-8")
    resp = client.post("/api/sync/push", content=body,
                       headers={"Content-Type": "application/x-ndjson",
                                "Authorization": f"Bearer {settings.sync_token}"})
    resp.raise_for_status()            # 4xx/5xx -> HTTPStatusError (caught by caller)

    # (4) stamp synced_at on the rows we pushed (0018 permits SET synced_at)
    stamp = utcnow_iso()
    pushed = 0
    for kind, model in _LEDGER:
        if ids[kind]:
            session.execute(update(model).where(model.id.in_(ids[kind]))
                            .values(synced_at=stamp))
            pushed += len(ids[kind])
    session.commit()

    # (5) paginate pull + apply (see Pattern 3)
    pulled = _pull_all(session, client)
    return SyncResult(status="ok", pushed=pushed, pushed_total=pushed_total, pulled=pulled)
```
**When to use:** the ONE entry point. The manual handler wraps it in the lock + `httpx.Client(...)` context; the loop wraps it in `anyio.to_thread.run_sync` + a fresh Session. Both share `_run_lock` via `_run_lock.acquire(blocking=False)`.

### Pattern 2: Lifespan asyncio auto-sync loop (D-06/D-07/D-08)

```python
# app/main.py lifespan (extend the existing one — DO NOT remove startup_backup)
import asyncio, contextlib
import anyio
from app.db import SessionLocal
from app.services import sync_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    backup_service.startup_backup()          # EXISTING — keep
    task = asyncio.create_task(_auto_sync_loop())
    try:
        yield
    finally:
        task.cancel()                        # D-08 clean shutdown
        with contextlib.suppress(asyncio.CancelledError):
            await task

async def _auto_sync_loop():
    while True:
        interval = _read_interval_default()  # fallback if DB read fails
        try:
            with SessionLocal() as s:         # D-07 fresh Session per tick
                cfg = sync_client.read_autosync_config(s)   # toggle+interval, read FRESH (D-08)
            interval = cfg.interval_seconds
            if cfg.enabled:
                await anyio.to_thread.run_sync(sync_client.run_sync_tick)  # opens its OWN Session
        except Exception:
            pass                              # D-08 offline = silent skip, loop never dies
        await asyncio.sleep(interval)
```
`run_sync_tick()` = acquire `_run_lock` non-blocking → open a fresh Session → build an `httpx.Client` → `run_sync_once` → write `sync_state` in `finally`. **Test the tick, never the infinite loop** (call `run_sync_tick()` directly).

**Discretion (interval):** recommend default **300 s (5 min)**, allowed range **60 s – 3600 s**, clamped in the service. Rationale: a single reseller does not need sub-minute sync; 5 min bounds server load and battery/CPU.

### Pattern 3: Pull-all with the composite cursor (echo BOTH headers)

```python
def _pull_all(session, client) -> int:
    since = after_id = None
    pulled = 0
    while True:
        params = {k: v for k, v in (("since", since), ("after_id", after_id)) if v}
        resp = client.get("/api/sync/pull", params=params or None,
                          headers={"Authorization": f"Bearer {settings.sync_token}"})
        resp.raise_for_status()
        batch = merge.parse_exchange(resp.text.splitlines())
        if batch.records:
            session.rollback()                       # discard any autobegun read txn
            with session.begin():                    # ONE owned txn per page (mirrors push route)
                merge.apply_merge(session, batch, server_now=utcnow_iso())
            pulled += len(batch.records)
        nxt_since = resp.headers.get("x-sync-next-since")
        nxt_after = resp.headers.get("x-sync-next-after-id")
        if len(batch.records) < DEFAULT_PULL_LIMIT or not nxt_since:
            break
        since, after_id = nxt_since, nxt_after        # MUST echo BOTH (else infinite loop on identical timestamps)
    return pulled
```
`DEFAULT_PULL_LIMIT` is 500 (`app/services/sync.py`). A full pull each sync is simple and idempotent for a single reseller's small reference set; persisting the cursor across syncs is a future optimization (see Open Questions).

### Pattern 4: The OOB header partial (D-01/D-02) — copy `cash_balance.html` idiom

```jinja
{# app/templates/partials/sync_status.html #}
<span id="sync-status"{% if oob %} hx-swap-oob="true"{% endif %}>{{ sync_message }}</span>
<span id="sync-badge"{% if oob %} hx-swap-oob="true"{% endif %}>{% if unsynced > 0 %}{{ unsynced }}{% endif %}</span>
```
```jinja
{# base.html <nav>: the button + the two id'd spans #}
<a hx-post="/sync/run" hx-indicator="#sync-spinner" style="cursor:pointer">Синхронизировать</a>
{% include "partials/sync_status.html" %}
```
The `POST /sync/run` handler returns the partial rendered with `oob=True` (mirrors `finance._movement_success`: `templates.get_template("partials/sync_status.html").render(oob=True, ...)` wrapped in `HTMLResponse`). Because `base.html` renders it with `oob` unset on full page loads and the handler renders it with `oob=True`, the SAME template serves both first paint and the OOB refresh — exactly the `cash_balance.html` pattern.

### Anti-Patterns to Avoid
- **`httpx.AsyncClient` / async handler** — contradicts the sync-Session rule and D-04. Use sync `httpx.Client`.
- **Running the driver Session on the event loop** — D-07 forbids it; always `anyio.to_thread.run_sync` for the loop path.
- **`asyncio.Lock` for the single-run guard** — the critical section runs in threads; use `threading.Lock`.
- **Sending only `since` on pull continuations** — loops forever across identical timestamps (documented in `app/services/sync.py`). Echo BOTH cursor headers.
- **Returning a 5xx from `/sync/run` on network failure** — violates SYNC-06. Catch `httpx.HTTPError`, return the offline partial with 200.
- **Stamping `synced_at` before the push 200** — a failed push would falsely mark rows synced. Stamp only after `raise_for_status()` passes.
- **Storing the sync token in the synced DB** — copying `myorishop.db` would leak the credential. Store it in `.env` like `secret_key` (see §Config).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| NDJSON serialization/parsing | A second wire encoder | `merge.serialize_exchange` / `merge.parse_exchange` | SYNC-04: one wire implementation, round-trip proven by `test_pull_round_trips_through_parse_exchange` |
| Reference upsert + stock recompute on pull-apply | Custom client merge | `merge.apply_merge` (in one owned txn) | Idempotent, FK-ordered, recomputes derived stock. (But read Open Question 2 re: update semantics) |
| Off-loop blocking call | Manual thread management | `anyio.to_thread.run_sync` | Already how FastAPI offloads `def` routes; integrates with the running loop |
| Cursor pagination | Reinvent paging | Echo `X-Sync-Next-Since` + `X-Sync-Next-After-Id` | Composite cursor already guarantees termination server-side |
| Money handling in payload | Any float conversion | Verbatim integer `*_cents` from the row | `parse_exchange` rejects non-int cents; keep ints end-to-end |
| Background scheduler | APScheduler/Celery/Redis | `asyncio.create_task` in lifespan | D-06 bans background-job infra |

**Key insight:** The correctness core (wire format + merge + trigger relaxation + cursor) was fully built and tested in phases 27–28. Phase 29 is plumbing — the risk is not in the algorithms but in the two **topology assumptions** in Open Questions 1 & 2.

## Runtime State Inventory

> Phase 29 adds new state; it does not rename/migrate existing state. Only the new-state notes matter here.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | New `sync_state` single row; `synced_at` gets stamped on existing Operation/CashMovement rows | Migration creates the table; driver stamps `synced_at` (0018 trigger already permits it — verified `app/db.py` + migration 0018) |
| Live service config | Auto-sync toggle + interval MUST be runtime-mutable and DB-persisted (D-08 flip-takes-effect-next-tick) | Store in DB (extend `sync_state` or a small config row), NOT `.env`. See Open Question 3 |
| OS-registered state | None — the loop is an in-process asyncio task, not an OS scheduler task (D-06) | None (verified: no Task Scheduler / pm2 in scope) |
| Secrets/env vars | New `SYNC_TOKEN` (per-device Bearer secret) + `SYNC_SERVER_URL` in `.env` | Add to `app/config.py` Settings; token resolved like `secret_key` (never logged) |
| Build artifacts | None | `httpx` promoted to runtime dep → run `uv sync` after the pyproject edit |

## Common Pitfalls

### Pitfall 1: Pushed operation references a reference parent the server lacks → whole batch 4xx/rollback
**What goes wrong:** `apply_merge` inserts operations after reference upsert; an `operation.sale_id`/`batch_id`/`product_id` with no server-side parent fails the FK and rolls the ENTIRE push back (proven by `test_push_all_or_nothing`, which raises `IntegrityError`). The locked scope pushes **ops + cash only**, so locally-authored sales/batches/customers are NOT in the body.
**Why it happens:** A local sale creates a `Sale` header + operations offline; the `Sale` never reaches the server, so the operation's `sale_id` FK is dangling on the server.
**How to avoid:** See Open Question 1 — the planner/user must decide whether the client push includes the reference rows its ledger transitively references. Do NOT assume server-first reference creation covers this.
**Warning signs:** A push returning 400/500 (server raises before the plain-dict projection), or an `IntegrityError` in server logs, whenever the operator sold or received goods offline.

### Pitfall 2: Server updates to existing reference rows never reach the client
**What goes wrong:** `apply_merge`'s reference upsert is **insert-if-new, server-wins-by-discard**. On the CLIENT, "existing UUID is discarded" means the client keeps its OWN old copy and drops the server's newer version — so a product price edited on the server never propagates to a client that already has the product.
**Why it happens:** The engine's server-wins semantics are written from the server's viewpoint; reused unchanged on the client they become client-wins-on-update.
**How to avoid:** See Open Question 2. For NEW reference rows the behavior is correct; only UPDATES are dropped. Decide with the user whether phase 29's "server-authoritative reference data down" must include updates.
**Warning signs:** A reference row edited on the server; the client's copy stays stale after a successful sync.

### Pitfall 3: Stamping `synced_at` on a failed push
**What goes wrong:** If `synced_at` is set before confirming the 200, a network drop after the request is sent but before the response would falsely mark rows synced → they never re-push → silent data divergence.
**How to avoid:** Stamp only after `resp.raise_for_status()` succeeds; the merge is idempotent (`operations_skipped` on replay), so re-pushing an already-merged row on a later sync is harmless.

### Pitfall 4: `httpx.Timeout` too generous → app appears frozen offline
**What goes wrong:** Default httpx timeout is 5 s per operation but connect on an unreachable host can hang the OS-level connect for longer on some networks; a manual click with a long total timeout blocks the HTMX request and the spinner spins.
**How to avoid:** Set an explicit `httpx.Timeout(connect=3.0, read=10.0, write=10.0, pool=3.0)` (values are Claude's discretion — recommend these). Short connect fails fast when offline; longer read tolerates a larger pull page. The whole sync is bounded by (connect + read) × pages.
**Warning signs:** Spinner running for tens of seconds when the server is down.

### Pitfall 5: Test DB built by `create_all`, not Alembic → partial index absent unless declared in the model
**What goes wrong:** `tests/conftest.py` builds schema via `Base.metadata.create_all` + `APPEND_ONLY_TRIGGERS`, never Alembic. A partial index declared ONLY in the migration won't exist in test DBs (and a `sync_state` table declared only in the migration won't either).
**How to avoid:** Declare BOTH the `SyncState` model and the partial `Index(...)` in `app/models.py` `__table_args__` (with `sqlite_where` + `postgresql_where`) — exactly the `uq_products_code_active` precedent (models.py:158) — AND write the migration. `create_all` then builds them for tests; Alembic builds them for real DBs. Keep the two in lockstep.

### Pitfall 6: Loop tick and manual click double-sync
**What goes wrong:** A timed tick fires while the operator clicks the button → two concurrent pushes, duplicate work, possible interleaved `sync_state` writes.
**How to avoid:** `_run_lock.acquire(blocking=False)`; if not acquired, the manual handler returns a "sync already running" result and the loop tick silently skips. The lock lives at module scope in `sync_client.py`.

## Code Examples

### Config additions (server URL + token) — smallest consistent extension of the existing Settings
```python
# app/config.py — add two fields (mirrors secret_key / device_id secret handling)
sync_server_url: str = ""     # env SYNC_SERVER_URL, e.g. https://sync.example.com
sync_token: str = ""          # env SYNC_TOKEN — per-device Bearer secret; NEVER log/print (CLAUDE.md)
```
`sync_token` is a secret → resolve from `.env` only (like `secret_key`), never store in the synced DB. `sync_server_url` is non-secret; `.env` is simplest, or a Settings-page field (Claude's discretion). Both empty by default → sync is a no-op/"not configured" until the operator sets them (offline-first, SRV-03).

### `sync_state` model (single row) — declare in models.py for create_all parity
```python
class SyncState(Base):
    __tablename__ = "sync_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)   # always 1 (singleton)
    last_sync_at: Mapped[str | None] = mapped_column(String(32))
    last_status: Mapped[str | None] = mapped_column(String(16))  # ok | partial | error (D-12)
    last_result: Mapped[str | None] = mapped_column(String(300)) # the RU message
    # If storing auto-sync config here (Open Question 3):
    # auto_enabled: Mapped[int] = mapped_column(Integer, default=0)
    # auto_interval_seconds: Mapped[int] = mapped_column(Integer, default=300)
```
Service `get_or_create` upserts the id=1 row (portable: SELECT then INSERT if missing — no `INSERT OR REPLACE`).

### Partial index migration (mirror migration 0003 exactly)
```python
# alembic/versions/0020_sync_state_and_unsynced_indexes.py
def upgrade() -> None:
    op.create_table(
        "sync_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("last_sync_at", sa.String(32), nullable=True),
        sa.Column("last_status", sa.String(16), nullable=True),
        sa.Column("last_result", sa.String(300), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_state")),
    )
    op.create_index("ix_operations_unsynced", "operations", ["synced_at"],
        sqlite_where=sa.text("synced_at IS NULL"),
        postgresql_where=sa.text("synced_at IS NULL"))
    op.create_index("ix_cash_movements_unsynced", "cash_movements", ["synced_at"],
        sqlite_where=sa.text("synced_at IS NULL"),
        postgresql_where=sa.text("synced_at IS NULL"))
```
`render_as_batch` is auto-derived per dialect in `alembic/env.py` (verified) — no per-migration handling needed. `String`/`Integer` only, no dialect SQL → portable (SRV-01). Immutability rule WR-06: this file must NOT import app modules (mirror 0019/0003).

### Badge query (D-11)
```python
def unsynced_count(session) -> int:
    ops = session.scalar(select(func.count()).select_from(Operation)
                         .where(Operation.synced_at.is_(None))) or 0
    cash = session.scalar(select(func.count()).select_from(CashMovement)
                          .where(CashMovement.synced_at.is_(None))) or 0
    return ops + cash
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Unconditional append-only UPDATE triggers | Column-scoped `WHEN` triggers permitting `SET synced_at` | Phase 28, migration 0018 | The client CAN stamp `synced_at` without tripping the immutability guard — no new trigger work in phase 29 |
| No client transport | Server push/pull endpoints live + tested | Phases 27–28 | Phase 29 only writes the caller |
| httpx as test-only dep | Needed at app runtime | This phase | Promote to `[project].dependencies` |

**Deprecated/outdated:** none relevant.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommended `httpx.Timeout(connect=3, read=10, write=10, pool=3)` | Pitfall 4 | Too tight → spurious "offline" on a slow link; too loose → longer freeze. Tunable, low risk (Claude's discretion). |
| A2 | Interval default 300 s, range 60–3600 s | Pattern 2 | Wrong default → over/under-frequent sync. Tunable (Claude's discretion). |
| A3 | Full-pull-every-sync (no persisted pull cursor) is acceptable for a single reseller's small reference set | Pattern 3 | If reference data grows large, each sync re-transfers everything. Optimization deferrable. |
| A4 | Store `sync_token` in `.env` (like `secret_key`), server_url in `.env`/Settings | §Config | If user wants a Settings-page token field writing to a `data/` file instead, the storage location changes (still not the synced DB). |
| A5 | Auto-sync toggle+interval stored in DB (extend `sync_state` or a config row) | Open Question 3 | Placement affects the migration column set (slightly extends D-10's locked three columns). |

## Open Questions (RESOLVED)

> **RESOLVED 2026-07-20 in 29-CONTEXT.md Area 5.** OQ1 → **D-13** (the client push includes the transitive FK reference closure — product/customer/batch/sale/warehouse in FK order). OQ2 → **D-14** (pull-apply MUST apply server updates via a dedicated client-side server-wins upsert — NOT a reuse of `apply_merge`'s insert-only reference stage). OQ3 (pull cursor persistence) → **D-15** (full pull each sync for now; cursor persistence deferred). The recommendations below are the original pre-resolution analysis, kept for traceability.

1. **Does the client push include the reference rows its ledger transitively references?** (HIGHEST PRIORITY — correctness)
   - What we know: The locked scope (D-01/SYNC-01) says "push ops + cash movements." The server's `apply_merge` inserts operations AFTER reference upsert and FK-fails (whole-batch rollback) if `sale_id`/`batch_id`/`product_id` has no server-side parent (`test_push_all_or_nothing`). Reference tables have NO `synced_at` marker, so "unsynced reference rows" cannot be queried the way ledger rows can.
   - What's unclear: In the deployed topology, are sales/batches/customers created ONLY on the server (so they always pre-exist before a client operation references them)? Or does the operator create them offline (making the dangling-FK failure real)?
   - Recommendation: **Escalate to the user before planning.** If offline authoring of sales/batches/customers is possible, the driver must include those reference rows in the push body (`apply_merge` reference upsert is idempotent, so over-including is safe) — which extends the locked "ops+cash only" push. Decide explicitly; do not let the plan ship a push that 500s after any offline sale.

2. **Must "server-authoritative reference data down" apply UPDATES, or only new inserts?** (correctness)
   - What we know: `apply_merge` reference upsert is insert-only/server-wins-by-discard. Reused on the client, it applies NEW reference rows but DROPS updates to rows the client already has (Pitfall 2). The pull cursor DOES send updated rows (ordered by `updated_at`), so the server offers updates the client then discards.
   - What's unclear: Whether phase 29 requires reference UPDATES to reach the client, or whether insert-only (new rows only) satisfies the requirement for now.
   - Recommendation: Confirm with the user. If updates must apply, the client needs a pull-apply path that lets the SERVER win on existing UUIDs (the opposite of `apply_merge`'s server-side semantics) — a small dedicated client upsert, NOT a reuse of `apply_merge`'s reference stage. Flag before locking "reuse apply_merge" for pull.

3. **Where do the auto-sync toggle + interval live?** (implementation detail)
   - What we know: D-08 requires the toggle to be runtime-mutable (flip takes effect next tick), so `.env` (static) is unsuitable. D-10 locks `sync_state`'s three result columns.
   - Recommendation: Add two columns to `sync_state` (`auto_enabled`, `auto_interval_seconds`) — one single-row table, one migration. This slightly extends D-10's column list; confirm it's acceptable, or use a tiny separate single-row config table.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| httpx | Outbound sync driver | ✓ (dev group; must promote to runtime) | 0.28.1 | none — required |
| anyio | `to_thread.run_sync` off-loop | ✓ (transitive via starlette) | present | none needed |
| A running server with `/api/sync/*` | Live push/pull | server built in phase 28 (PG deploy 28-06) | — | Offline-safe: driver returns "Нет связи с сервером"; local work unaffected (SRV-03) |

**Missing dependencies with no fallback:** none (httpx present; promotion is a pyproject edit, not an install of something new).
**Missing dependencies with fallback:** a reachable server — handled by design (offline-safe failure).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x + FastAPI `TestClient` (httpx-backed) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_sync_client.py -x` (new file) |
| Full suite command | `uv run pytest` |
| PG parity | `tests/test_pg_parity.py` + `tests/test_merge_pg.py` run the shared migration/merge on `postgres:17` in CI (run 29705703575 GREEN). The new migration + `sync_state`/indexes must pass PG parity. |

### Key test seam — inject the httpx client into the driver
`run_sync_once(session, *, client)` takes the client as a parameter. Tests supply:
- **Real contract (integration):** `httpx.Client(transport=httpx.ASGITransport(app=main.app), base_url="http://sync")` + a minted device token (reuse the `device_client` fixture's `mint_token`). The driver then hits the REAL `/api/sync/push` + `/api/sync/pull` + merge engine in-process — no live server, full round-trip. Assert `synced_at` flips, server rows appear, `sync_state` row written.
- **Offline/timeout/error:** `httpx.Client(transport=httpx.MockTransport(handler))` where `handler` raises `httpx.ConnectError` (offline), returns 500 (server error), or 401 (bad token). Assert the driver/handler maps to the right D-12 string and NEVER raises out of `/sync/run`.

No `respx` needed (repo has none; `MockTransport` + `ASGITransport` are built into httpx 0.28).

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SYNC-01 | Push flips `synced_at`; server merges ops+cash; pull applies reference; stock stays correct | integration (ASGITransport) | `pytest tests/test_sync_client.py::test_push_marks_synced_and_pulls -x` | ❌ Wave 0 |
| SYNC-01 | Idempotent re-sync (already-synced rows not re-pushed; replay skipped) | integration | `pytest tests/test_sync_client.py::test_second_sync_is_noop -x` | ❌ Wave 0 |
| SYNC-06 | Offline (`ConnectError`) → status "offline", `Нет связи с сервером`, handler returns 200 partial not 5xx | unit (MockTransport) | `pytest tests/test_sync_client.py::test_offline_returns_partial_not_5xx -x` | ❌ Wave 0 |
| SYNC-06 | `sync_state` row written on BOTH success and failure (finally path) | unit | `pytest tests/test_sync_client.py::test_sync_state_written_on_failure -x` | ❌ Wave 0 |
| SYNC-06 | D-12 RU strings for ok / no-change / partial / offline / server-error | unit | `pytest tests/test_sync_client.py::test_result_messages -x` | ❌ Wave 0 |
| SYNC-07 | `unsynced_count` = ops+cash where `synced_at IS NULL`; badge hidden at 0 | unit | `pytest tests/test_sync_client.py::test_unsynced_count -x` | ❌ Wave 0 |
| SYNC-07 | Header partial renders badge OOB after `/sync/run` | integration (client fixture) | `pytest tests/test_sync_ui.py::test_sync_run_returns_oob_partial -x` | ❌ Wave 0 |
| SYNC-08 | One tick with toggle OFF does nothing; toggle ON runs the driver; offline tick swallowed | unit (call `run_sync_tick` directly) | `pytest tests/test_sync_client.py::test_tick_respects_toggle -x` | ❌ Wave 0 |
| SYNC-08 | `_run_lock` prevents overlap (manual + tick) | unit | `pytest tests/test_sync_client.py::test_single_run_lock -x` | ❌ Wave 0 |
| SRV-03 | Local receipt/sale succeeds with `sync_server_url` empty / server down | integration | `pytest tests/test_sync_client.py::test_local_work_unaffected_offline -x` | ❌ Wave 0 (partly covered by existing receipt/sale tests) |
| SRV-01 | New migration + `sync_state` + indexes apply on PostgreSQL | PG parity | `pytest tests/test_pg_parity.py -x` (extend) | ⚠️ extend |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_sync_client.py tests/test_sync_ui.py -x`
- **Per wave merge:** `uv run pytest` (full suite; the repo runs the full ~1079-test suite as the post-merge gate per project convention)
- **Phase gate:** Full suite green + PG parity green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_sync_client.py` — driver push/pull/stamp/offline/lock/tick/messages (SYNC-01/06/07/08, SRV-03)
- [ ] `tests/test_sync_ui.py` — `POST /sync/run` returns OOB header partial; badge visibility (SYNC-06/07)
- [ ] Extend `tests/test_pg_parity.py` — assert `sync_state` + unsynced partial indexes build on PG (SRV-01)
- [ ] Fixture: an `httpx.Client(ASGITransport(app), base_url=...)` + device token helper (can build on the existing `device_client` mint path)
- [ ] Framework install: none — httpx/pytest already present; just promote httpx to runtime dep

## Security Domain

> `security_enforcement` is enabled (project default). The sync SERVER surface was fully threat-modeled and SECURED in phase 28 (35/35 threats closed). Phase 29 adds a CLIENT egress; the relevant new surface is small.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Bearer device token in `Authorization` header only (never query string / never logged) — mirrors the server contract and `app/services/sync.py` docstring |
| V3 Session Management | no (client egress uses a device token, not a session) | — |
| V4 Access Control | yes | `POST /sync/run` is a normal authenticated app route (behind the app-level `auth_guard`); it is an operator action, not admin-only |
| V5 Input Validation | yes | Pulled NDJSON is validated by `parse_exchange` before any DB touch (rejects bad money/ids/format) — reused unchanged |
| V6 Cryptography | no new crypto | Token compare is server-side (constant-time, already built); the client only presents the plaintext |
| V7 Error Handling / Logging | yes | Never log `sync_token`; never surface raw server error bytes in the RU partial (D-12 uses fixed strings) |

### Known Threat Patterns for the client egress
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Sync token stored in the synced DB → leaks on DB copy | Information Disclosure | Store token in `.env` (like `secret_key`), outside the synced `myorishop.db` |
| Token in a URL query string → proxy/browser logs | Information Disclosure | Send ONLY via `Authorization: Bearer` header (matches server contract) |
| Token or server error echoed into the UI | Information Disclosure | Fixed RU D-12 strings; never render exception text; never log the token (CLAUDE.md) |
| Push over plain HTTP on the internet | Tampering / Disclosure | `sync_server_url` should be `https://…` for internet deployment (Caddy TLS from phase 28); document as an operational requirement |
| Failed push falsely marked synced → silent data loss | Tampering (integrity) | Stamp `synced_at` only after `raise_for_status()` (Pitfall 3) |

## Sources

### Primary (HIGH confidence — in-repo, read this session)
- `app/routes/sync.py` — push/pull server contract, Bearer auth, NDJSON media type, cursor headers `[VERIFIED]`
- `app/services/sync.py` — pull-cursor semantics, `PULL_KINDS`, `DEFAULT_PULL_LIMIT`, `current_schema_version` `[VERIFIED]`
- `app/services/merge.py` — `serialize_exchange` / `parse_exchange` / `apply_merge`, `KIND_TO_FIELDS`, insert-only/server-wins semantics, DD-6 synced_at forced None `[VERIFIED]`
- `app/services/security.py` + `app/services/devices.py` — `require_device` Bearer gate, token lookup, SYNC_PATH_PREFIX bypass `[VERIFIED]`
- `app/config.py` — Settings pattern; `secret_key`/`device_id` persisted outside the synced DB `[VERIFIED]`
- `app/main.py` — existing lifespan (`startup_backup`), router wiring `[VERIFIED]`
- `app/models.py` — `Operation.synced_at` (~374), `CashMovement.synced_at` (~503), `uq_products_code_active` partial-index-in-model precedent (158) `[VERIFIED]`
- `app/db.py` + `alembic/versions/0018_*.py` — column-scoped triggers permit `SET synced_at` `[VERIFIED]`
- `alembic/env.py` + `0003_*.py` + `0019_*.py` — portable migration + partial-index + `render_as_batch` per-dialect pattern `[VERIFIED]`
- `app/templates/partials/cash_balance.html` + `base.html` + `app/routes/finance.py` (`_movement_success`) — OOB partial idiom `[VERIFIED]`
- `tests/conftest.py` + `tests/test_sync_api.py` — `device_client` fixture, create_all vs Alembic, NDJSON test helpers, cursor pagination tests `[VERIFIED]`
- `pyproject.toml` — httpx dev-only (needs promotion), anyio transitive `[VERIFIED]`

### Secondary (MEDIUM confidence)
- Recommended timeout/interval values — practitioner defaults, tunable (A1/A2).

### Tertiary (LOW confidence)
- none.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — everything is in-repo and import-verified; only httpx promotion is a change.
- Architecture: HIGH — all four patterns derive from existing, tested code paths (push route txn, OOB partial, lifespan, cursor).
- Pitfalls: HIGH — Pitfalls 1 & 2 are grounded in read code (`test_push_all_or_nothing`, `_upsert_reference` semantics); they are the phase's real risk and are escalated as Open Questions, not guessed away.

**Research date:** 2026-07-20
**Valid until:** 2026-08-19 (stable domain; in-repo contracts change only with new phases)
