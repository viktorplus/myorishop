# Phase 29: Online Client Sync - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers the **desktop CLIENT side** of online sync. The server-side
push/pull endpoints (`POST /api/sync/push`, `GET /api/sync/pull`) and the
idempotent UUID merge engine already exist from phases 27–28. Phase 29 builds
what the local client is still missing:

1. The outbound **sync driver** (an httpx caller) that pushes local unsynced
   ledger rows to the server and pulls server-authoritative reference data down
   — the client half of SYNC-01.
2. A manual **«Синхронизировать»** button.
3. **Sync status + last-sync time + plain-language result** (SYNC-06).
4. An **unsynced-count badge** (SYNC-07).
5. **Optional interval auto-sync** that runs in the background and silently
   stops attempting while offline; when disabled only the manual button syncs
   (SYNC-08).
6. **Offline-safe failure** — a sync failure never blocks local work.

**Not in scope:** the offline USB self-uploading file (Phase 30, OFF-*), any
server-side merge/endpoint changes (done in 27–28), mobile UI (server-only).
</domain>

<decisions>
## Implementation Decisions

### Sync button & status placement (Area 1)
- **D-01:** Put the «Синхронизировать» button, sync status, last-sync time, and
  the unsynced-count badge in a **header partial rendered in `base.html`**, so
  they are glanceable on every desktop page (satisfies SYNC-06/07 "always
  visible"). Settings-only placement is rejected — Settings is behind the
  admin-role nav gate, so a plain operator would never see sync status.
- **D-02:** Refresh the header status/badge in place using the **existing
  out-of-band (OOB) swap pattern already proven in
  `app/templates/partials/cash_balance.html`**
  (`{% if oob %}hx-swap-oob="true"{% endif %}` on an id'd element). The sync
  action returns the sync-status partial with `hx-swap-oob="true"` — no full
  page reload.
- **D-03:** Secondary sync config (the auto-sync on/off toggle and interval
  value from SYNC-08) may live in the Settings page; only the glanceable
  indicator + button belong in the header.

### Manual sync execution model (Area 2)
- **D-04:** The manual button runs sync **synchronously inside the HTMX
  request** (a `def` handler in the FastAPI threadpool), with a spinner via
  `hx-indicator`, then swaps in the result partial. Chosen for simplicity —
  sync is a few short bounded httpx calls.
- **D-05:** The outbound httpx client MUST use a strict **`httpx.Timeout`** so a
  bad/absent network can only stall for the timeout window, never freeze the
  app. On timeout/transport error the handler catches the exception and returns
  an "offline/failed" partial — it never returns a 5xx that would block the
  page (honors SYNC-06 "failure never blocks local work").

### Interval auto-sync mechanism (Area 3)
- **D-06:** Run the optional interval auto-sync as an **asyncio background loop
  started in the FastAPI `lifespan`** — the only zero-dependency option that
  keeps syncing even with the browser tab closed ("runs in the background").
  APScheduler/Celery/Redis rejected (project bans background-job infra; adds a
  dependency for one fixed tick).
- **D-07:** The loop must NOT run the sync SQLAlchemy `Session` on the event
  loop — call the shared sync-driver function via
  `anyio.to_thread.run_sync`, opening a **fresh `Session` per tick**.
- **D-08:** Wrap each tick in a broad `try/except` that swallows
  connection/httpx errors so being offline just **silently skips a tick** (no
  log spam, loop never dies). Read the on/off toggle from settings **at the top
  of each iteration** (not captured once at startup) so flipping it takes effect
  next tick. Cancel the task cleanly on lifespan shutdown (`task.cancel()`).
- **D-09:** Manual sync (D-04) and the auto-sync loop (D-06) call **one shared
  sync-driver function** guarded by a single **"already running" flag/lock** so
  a manual click and a timed tick can never overlap or double-sync.

### Sync state storage & result display (Area 4)
- **D-10:** Persist a **single-row `sync_state` table**
  (`last_sync_at`, `last_status`, `last_result` text) written after **every**
  sync attempt inside a `finally`/single exit point, so the failure path is
  recorded as reliably as success and the result survives an app restart.
  Requires **one Alembic migration** (`render_as_batch=True`) that must also run
  on PostgreSQL under the shared migration history (SRV-01) — plain single-row
  table, no SQLite-specific SQL.
- **D-11:** The **badge is always computed**, never stored:
  `COUNT(*) WHERE synced_at IS NULL` across `Operation` + `CashMovement`. Add a
  **partial index** (`... WHERE synced_at IS NULL`) on each so the count stays
  cheap as history grows. `last_sync_at` comes from `sync_state` (NOT
  `MAX(synced_at)`, which never advances on a pull-only/no-op sync).
- **D-12:** Plain-language Russian result strings, times formatted in
  `settings.display_tz` (Europe/Moscow):
  - Success (both directions): `Синхронизировано: отправлено 12, получено 5`
  - Success, no changes: `Синхронизировано, изменений нет`
  - Partial: `Синхронизировано частично: отправлено 8 из 12`
  - No connection: `Нет связи с сервером`
  - Server/other error: `Ошибка сервера, попробуйте позже`
  - Last-sync line: `Последняя синхронизация: 20.07.2026 14:32`
  - Never synced: `Ещё не синхронизировано`
  - Badge: show only when `> 0`; hide at zero.

### Sync topology — resolved open questions (Area 5, resolved 2026-07-20)
_Resolved with the user after research surfaced two correctness gaps in the
"ops+cash only" framing (verified against `app/services/merge.py`,
`app/services/sync.py`, and the local creation routes `POST /sales`,
`/receipts`, `/products`, `/customers`)._
- **D-13:** The push body MUST include the locally-authored **reference rows**
  that unsynced ledger rows transitively reference (`product`, `customer`,
  `batch`, `sale` — collected in FK-dependency order), not just operations +
  cash movements. This **supersedes the "ops + cash only" framing** in
  D-01/SYNC-01: an operator who sells or receives goods offline creates local
  `Sale`/`Batch` rows, so pushing operations without their FK parents fails the
  server's all-or-nothing merge (`test_push_all_or_nothing`). The server's
  `merge.apply_merge` reference upsert is idempotent (insert-if-new,
  server-wins), so over-including reference rows is safe. The exact collection
  mechanism is planner's discretion; the recommended minimal set is the
  transitive closure of the FK parents of the unsynced `Operation` +
  `CashMovement` rows. (Reference tables have no `synced_at` marker, so this
  closure — not a `synced_at IS NULL` query — is how "unsynced" reference rows
  are identified.)
- **D-14:** The client pull-apply MUST apply server **UPDATES** to existing
  reference rows — "server-authoritative reference data down" means the server
  wins on the client. The server-side `merge.apply_merge` reference stage is
  insert-if-new / keep-existing (which on the client means client-wins-on-update
  and silently drops server edits like a changed product price), so it **MUST
  NOT be reused as-is for the pull**. A small dedicated client-side reference
  upsert that overwrites an existing row (matched by UUID) with the server's
  version is required. New-row inserts keep the existing insert behavior; only
  the update-existing path is new. Ledger rows are still insert-only/idempotent.
- **D-15:** The auto-sync **toggle + interval** are stored as two columns on the
  single-row `sync_state` table (`auto_enabled` INTEGER default `0`,
  `auto_interval_seconds` INTEGER default `300`), **extending D-10's** three
  result columns — one migration covers all five columns. They are read **fresh
  at the top of each loop tick** (D-08) so flipping the toggle / changing the
  interval takes effect on the next tick. `.env` is unsuitable (static, cannot
  flip at runtime). Interval range clamped in the service (recommend 60–3600 s).

### Claude's Discretion
- Exact `httpx.Timeout` values, spinner styling, the interval default (N
  seconds/minutes) and its allowed range, and the internal shape of the
  sync-driver function are left to research/planning.
- Status enum values for `sync_state.last_status` (suggested `ok` / `partial` /
  `error`) may be finalized by the planner.

### Open implementation gap (flag for researcher/planner)
- **The client has no server-address config and no outbound driver yet.**
  There is no `server_url` field in `app/config.py`, and no httpx caller exists.
  Planning MUST add: (a) client config for the **server base URL** and the
  **per-device sync token** (SYNC-09 device token already exists —
  `app/services/devices.py`, `settings.device_id`), and (b) the outbound driver
  itself. Decide where the server URL is configured (`.env`/settings row/
  Settings page field).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` §Synchronization (SYNC) — **SYNC-06** (status +
  last-sync + plain result, failure never blocks), **SYNC-07** (unsynced badge),
  **SYNC-08** (optional interval auto-sync, silent offline stop), plus SYNC-01
  (manual push/pull) and SYNC-09 (per-device token) already delivered.
- `.planning/ROADMAP.md` — Phase 29 line ("«Синхронизировать» push/pull, sync
  status + last-sync time, unsynced-count badge, optional interval sync,
  offline-safe failure").

### Server-side sync (already built — the client calls these)
- `app/routes/sync.py` — `POST /api/sync/push`, `GET /api/sync/pull` (token-auth
  transport the new client driver must call).
- `app/services/sync.py` — pull collection of server-authoritative REFERENCE
  data; documents the `synced_at` semantics ("server never writes synced_at";
  NULL = "never pushed from here").
- `app/services/merge.py` — idempotent UUID merge; `synced_at` is server-owned
  and forced to None on the wire (DD-6). The client push must respect this.
- `app/services/devices.py`, `app/routes/devices.py` — per-device sync token
  (SYNC-09) the client authenticates with.

### Client patterns & config to reuse/extend
- `app/templates/partials/cash_balance.html` — the OOB-refresh pattern to copy
  for the header sync-status partial (D-02).
- `app/templates/base.html` — nav/header that hosts the new sync partial (D-01);
  existing htmx 2.0.10 config lives here.
- `app/templates/pages/settings.html` — home for the auto-sync toggle/interval
  (D-03) and candidate for the server-URL field.
- `app/config.py` — `Settings` (device_id, display_tz); add server URL + sync
  token config here.
- `app/models.py` — `synced_at` columns on `Operation` (~line 374) and
  `CashMovement` (~line 503); the badge counts these NULLs (D-11).
- `alembic/` (env.py with `render_as_batch=True`) — where the `sync_state`
  migration + partial indexes go (D-10/D-11); must run on SQLite AND PostgreSQL.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **OOB partial refresh** — `partials/cash_balance.html` already does exactly the
  "update an always-present element after a POST without reload" that the header
  sync status needs. Copy the `hx-swap-oob` idiom.
- **Device token / device_id** — `services/devices.py` + `settings.device_id`
  give the client its per-device identity and token for the sync endpoints
  (SYNC-09 done); the driver just needs to send it.
- **`synced_at IS NULL` marker** — already on `Operation` and `CashMovement`;
  the unsynced badge is a pure query, no new bookkeeping.

### Established Patterns
- Sync `def` endpoints + sync SQLAlchemy `Session` in FastAPI threadpool (no
  async DB). The lifespan auto-sync loop must therefore offload to a thread and
  use its own Session (D-07).
- Single shared Alembic history runs on SQLite + PostgreSQL (SRV-01); any new
  table (`sync_state`) and partial index must be portable — no SQLite-only SQL.
- Money as integer minor units; append-only ledger; caches recomputed after
  merge (server-side, already handled).

### Integration Points
- New outbound httpx driver → existing server `POST /api/sync/push` &
  `GET /api/sync/pull`.
- New header partial → `base.html` nav, OOB-refreshed by the sync action.
- New `sync_state` table + partial indexes → Alembic migration.
- New lifespan background task → `app/main.py` lifespan.
- New server-URL + sync-token config → `app/config.py` (+ maybe Settings page).

</code_context>

<specifics>
## Specific Ideas

- Reuse the in-repo `cash_balance.html` OOB pattern verbatim rather than
  inventing a new refresh mechanism.
- Concrete Russian result strings are locked in D-12.

</specifics>

<deferred>
## Deferred Ideas

- **Sync history / verbose error log** and a dedicated `/sync` page — considered
  (Area 1 option B) but not chosen; revisit only if the header row gets crowded
  or a sync-history view is later requested. Not in Phase 29 scope.
- **Offline USB self-uploading file** — Phase 30 (OFF-*), explicitly separate;
  upload-only path, no pull.
- **Non-blocking background worker for the manual button** (Area 2 option B) —
  deferred; only worth it if the reference pull becomes slow/large.

None beyond the above — discussion stayed within phase scope.

</deferred>

---

*Phase: 29-online-client-sync*
*Context gathered: 2026-07-20*
