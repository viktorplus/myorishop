# Phase 29: Online Client Sync - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-20
**Phase:** 29-online-client-sync
**Areas discussed:** Sync button & status placement, Manual sync execution model, Interval auto-sync mechanism, Sync state storage & result display

Mode: advisor (research-backed comparison tables, calibration tier `standard`).

---

## Sync button & status placement

| Option | Description | Selected |
|--------|-------------|----------|
| A. Header partial in `base.html` | Button + status + last-sync time + badge on every page; OOB refresh via the existing `cash_balance.html` pattern | ✓ |
| B. Header badge/status + dedicated `/sync` page | Lean header, full sync UI on its own page | |
| C. Block inside Settings page only | Smallest change, but fails "always visible" and Settings is admin-gated | |

**User's choice:** A. Партиал в шапке
**Notes:** Reuse the in-repo `partials/cash_balance.html` OOB pattern. Auto-sync toggle/interval detail may go to Settings.

---

## Manual sync execution model

| Option | Description | Selected |
|--------|-------------|----------|
| A. Blocking synchronous request + `httpx` timeout + spinner | Simplest; timeout prevents freeze; sync serialized naturally | ✓ |
| B. Background `threading.Thread` worker + status polling | UI never blocks structurally; unifies manual + auto-sync; needs Lock + per-thread Session | |
| C. FastAPI `BackgroundTasks` + polling | Still occupies a threadpool worker and needs B's shared state; dominated | |

**User's choice:** A. Блокирующий + timeout
**Notes:** Sync is a few short bounded httpx calls; strict timeout already satisfies "failure never blocks local work". B deferred — only worth it if the pull becomes slow/large.

---

## Interval auto-sync mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| A. FastAPI lifespan asyncio background loop | Runs even with the tab closed; 0 new deps; clean cancel; silent offline skip | ✓ |
| B. Browser `hx-trigger="every Ns"` timer | Trivial, but only runs while a tab is open — not "in the background" | |
| C. APScheduler | Purpose-built scheduler, but a new dependency for one tick; 4.0 still alpha | |

**User's choice:** A. asyncio-loop в lifespan
**Notes:** Must offload the sync Session to a thread (fresh Session per tick), broad try/except for silent offline skip, read toggle each iteration, share one sync-driver + "already running" flag with the manual button.

---

## Sync state storage & result display

| Option | Description | Selected |
|--------|-------------|----------|
| B. Persisted single-row `sync_state` table + computed badge | Durable last-result/status across restart; accurate `last_sync_at`; badge stays computed; 1 Alembic migration | ✓ |
| A. Compute-on-the-fly, result in memory | No migration, but result lost on restart and `MAX(synced_at)` misreports pull-only syncs | |
| C. Hybrid (computed badge + computed last-sync, result in memory) | Adds little over A; same blind spots | |

**User's choice:** B. Таблица sync_state + бейдж на лету
**Notes:** Badge = `COUNT(*) WHERE synced_at IS NULL` (Operation + CashMovement) with partial indexes; write `sync_state` in a `finally` so failures are recorded; locked Russian result strings (see CONTEXT.md D-12).

---

## Claude's Discretion

- `httpx.Timeout` values, spinner styling, interval default + allowed range,
  internal sync-driver shape, and `sync_state.last_status` enum values.

## Deferred Ideas

- Sync history / verbose error view + dedicated `/sync` page (Area 1 option B) — revisit only if the header row gets crowded.
- Offline USB self-uploading file — Phase 30 (OFF-*).
- Non-blocking background worker for the manual button (Area 2 option B) — only if the pull becomes slow/large.
