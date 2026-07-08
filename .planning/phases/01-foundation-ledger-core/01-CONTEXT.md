# Phase 1: Foundation & Ledger Core - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning
**Mode:** Autonomous (recommended answers auto-accepted per user's full-auto directive)

<domain>
## Phase Boundary

A runnable local FastAPI + HTMX app skeleton with the complete data foundation: append-only operations ledger, sync-ready schema conventions (UUIDs, integer cents, UTC), SQLite configured safely, Alembic migrations, and a run.bat launcher. No business features yet — later phases add catalog, receipts, sales, etc. on top of this foundation.

</domain>

<decisions>
## Implementation Decisions

### Runtime & Startup
- Python 3.13 managed with uv; dependencies in pyproject.toml
- run.bat starts uvicorn with a single worker on 127.0.0.1:8000 and opens the default browser
- htmx 2.0.10 vendored locally in app/static/ (offline requirement — no CDN)
- No PyInstaller/Docker in v1; plain `uv run` via run.bat

### Data Model Conventions
- UUID (uuid4, stdlib) TEXT primary keys on ALL tables — sync-safe, no autoincrement collisions
- Money stored as integer minor units (cents); column names end in `_cents`
- Timestamps stored as UTC ISO-8601 TEXT (`created_at`, `updated_at`); single configurable local timezone for display
- `operations` table is append-only: id, type, product_id, qty_delta, unit_cost_cents, unit_price_cents, payload (JSON for type-specific fields), device_id, seq (per-device counter), created_at (UTC), created_by, synced_at (nullable — future sync cursor)
- Stock quantity is a cached projection on product, always recomputable from the ledger; no direct quantity edits
- Soft deletes (`deleted_at`) on products/customers; no hard deletes

### App Skeleton
- Thin routes / fat services layering: app/routes/, app/services/, app/models.py, app/templates/, app/static/
- Sync SQLAlchemy 2.0 Session with plain `def` endpoints (no async/aiosqlite)
- Alembic from day one with `render_as_batch=True`
- SQLite PRAGMAs set per-connection via SQLAlchemy event listener: WAL, foreign_keys=ON, busy_timeout
- Jinja2 server-rendered pages; HTMX for partial updates; python-multipart for forms
- pytest for tests; Ruff for lint

### Operator Identity
- Single operator name from a local settings/config value; recorded as `created_by` on every operation
- No login/auth in v1 (single user); roles deferred to v2 per REQUIREMENTS.md

### Claude's Discretion
- Exact directory naming, template structure, base layout HTML, and Alembic env details
- UUIDv4 vs UUIDv7 (v4 acceptable; stdlib-trivial)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield; repo contains only planning docs and agent.md

### Established Patterns
- Follow .planning/research/STACK.md and ARCHITECTURE.md (verified versions, project structure, Operation schema sketch)

### Integration Points
- Every later phase writes through services layer to the operations ledger; getting this schema right is the phase's whole point

</code_context>

<specifics>
## Specific Ideas

- UI language: Russian (operator-facing text), code/comments in English
- App must work fully offline at localhost

</specifics>

<deferred>
## Deferred Ideas

- Sync engine, CRDTs, server replay — v2 (schema only stays sync-ready)
- Multi-operator device_id negotiation — v2 (v1 uses one fixed device_id)

</deferred>
