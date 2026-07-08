# Project Research Summary

**Project:** MyOriShop
**Domain:** Local-first warehouse inventory & sales tracking for a solo direct-sales reseller (Oriflame consultant)
**Researched:** 2026-07-08
**Confidence:** MEDIUM-HIGH

## Executive Summary

MyOriShop is a single-operator, localhost-only inventory and sales app — the same product category as direct-sales consultant tools (Pink Office, Mary Kay myCustomers+) and micro-retail POS, but fully local, free, and Oriflame-code-aware. Research validates the user's chosen stack completely: Python 3.13 + FastAPI + SQLAlchemy 2.0 + SQLite + Jinja2 + HTMX (server-rendered, no build step, htmx vendored locally for offline use). Since all direct-sales analogs are cloud/subscription SaaS, the real competitor is a spreadsheet — which means data-entry speed (code autofill, keyboard-first forms) is the metric that decides adoption.

The load-bearing architectural decision, converging across all four research files, is an **append-only operations ledger as the single source of truth for stock**. Every receipt, sale, write-off, return, and correction is an immutable INSERT; current stock is a cached, recomputable projection. This one table simultaneously delivers three project requirements — operation history, audit log, and future multi-device sync — without building any sync machinery now. Sync-readiness in v1 costs only passive schema hygiene: UUID string primary keys, UTC timezone-aware timestamps, device_id + seq columns, soft deletes. Anything more (CRDTs, sync frameworks, auth) is explicitly an anti-pattern for v1.

Key risks are all schema-level and must be settled in the foundation phase because they're cheap on day one and near-impossible to retrofit: money stored as integer minor units (SQLite has no real DECIMAL — floats corrupt profit math), cost/price snapshotted onto every sale line at sale time (profit computed from current prices silently rewrites history), SQLite PRAGMAs set per-connection (WAL, busy_timeout, foreign_keys=ON), and automated `VACUUM INTO` backups before real data entry begins (no import path exists — data loss is unrecoverable).

## Key Findings

### Recommended Stack

The chosen stack is validated with no changes to core choices; research pins versions and adds guardrails. Use uv for env/package management, Ruff for lint+format, Alembic (batch mode) from day one, and a `run.bat` launcher as the entire Windows "deployment" story — no PyInstaller, no Docker.

**Core technologies:**
- Python 3.13 + FastAPI 0.139 + Uvicorn 0.51: web framework/server — minimal boilerplate, Pydantic v2 validation, sync `def` endpoints (no async SQLAlchemy)
- SQLAlchemy 2.0.51 (2.0 declarative style) + SQLite (WAL) + Alembic 1.18: portable ORM — PostgreSQL later is a connection-string change
- Jinja2 3.1.6 + htmx 2.0.10 (vendored, NOT the 4.0 beta) + python-multipart: server-rendered UI with partial swaps, zero build toolchain
- Optional: jinja2-fragments (HTMX partials), Pico.css (classless styling), pytest + httpx (tests)

**Do not use:** SPA frameworks, async SQLAlchemy/aiosqlite, Float/Numeric for money, SQLite-specific SQL, htmx 4.0 beta or CDN, PyInstaller, Docker, SQLAlchemy 1.x patterns.

### Expected Features

Solo-operator tools win by being simple; Zoho-class breadth kills adoption. The bar is set by spreadsheets, so entry speed is everything.

**Must have (table stakes — all P1, all v1):**
- Product catalog CRUD + fast search (qty derived, never directly edited)
- Goods receipt, multi-line sale (price override, optional customer, cost snapshot, oversell warn-and-allow)
- Write-off, sale-linked return, stock correction — without these stock drifts and trust dies
- Customer profiles + purchase history
- Reports: sales, profit, current stock, write-offs, low-stock, per period
- Append-only operations/audit log (architectural table stake)
- One-click backup + CSV export

**Should have (differentiators):**
- Pre-loaded Oriflame code→name dictionary with autofill — *the* speed feature, cheap, ship in v1
- Keyboard-first minimal-click entry forms (autofocus, Enter-to-advance, stay-on-form)
- v1.x: stale-stock report, top products/active customers, interested-customers-on-receipt, price history UI, repurchase reminders (needs 2–3 months of data)

**Defer (v2+):** sync, auth/roles, multi-currency, barcode scanning, FIFO costing, invoicing/payments, notifications, CSV import, multi-warehouse.

**Anti-features:** directly editable stock quantity, cloud sync in v1, full accounting, real-time charts.

### Architecture Approach

Single FastAPI monolith: thin routes → service layer (all business logic) → SQLAlchemy models → SQLite. OperationService is the only writer of the `operations` table and cached `products.quantity`, updated in one transaction (with a `rebuild_stock()` repair function). HTMX fragment endpoints handle all interactivity (autocomplete, confirmations, table refreshes) via the `HX-Request` header. The service/route split matters doubly here: the future sync server replays operations through the same service code.

**Major components:**
1. `routes/` — HTTP + template rendering per UI area (catalog, operations, customers, reports, search); no business logic
2. `services/operations.py` — the heart: validates and records all five operation types as immutable ledger rows
3. `services/catalog.py`, `customers.py`, `reports.py` — product/dictionary CRUD; read-only queries and aggregates over the ledger
4. `operations` table — UUID PK, device_id + seq, qty_delta, snapshotted cost/prices, UTC created_at, synced_at (NULL in v1)

### Critical Pitfalls

1. **Stock drift from mutable quantity** — ledger is truth from the first migration; cached quantity only with a recompute/verify command
2. **Float money math** — integer cents columns, `Decimal` at edges, one `money.py` helper; never Float/Numeric on SQLite
3. **Profit from current prices** — snapshot unit_price + unit_cost onto every sale line at sale time; profit reads sale lines only
4. **Sync-blocking schema** — UUID PKs, UTC aware timestamps, append-only ops from day one; but zero actual sync code in v1
5. **Backup done wrong or not at all** — `VACUUM INTO` (never file-copy of a live WAL DB), automated + rotated, test one restore
6. **SQLite concurrency defaults** — per-connection PRAGMAs (WAL, busy_timeout=5000, foreign_keys=ON), single uvicorn worker, atomic check-and-decrement, HTMX double-submit guard
7. **Oversell handling** — warn-and-allow with confirmation, negative stock surfaced as "needs correction"; never hard-block, never silent
8. **Timezone report boundaries** — store UTC aware; report periods computed as local-day boundaries converted to UTC, half-open intervals

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Foundation & Schema
**Rationale:** Every irreversible decision lives here — ledger table, UUID PKs, integer-cents money, UTC timestamps, SQLite PRAGMAs, Alembic batch mode. Cheap now, rework-forbidden later.
**Delivers:** Runnable app skeleton (routes/services/models/templates), DB setup, core models, `operations` table, run.bat
**Addresses:** Operations log (architectural table stake)
**Avoids:** Pitfalls 1, 2, 4, 6 (drift, float money, sync-blocking schema, concurrency defaults)

### Phase 2: Catalog, Dictionary & Search
**Rationale:** Products must exist before any operation can reference them; autofill is the core speed differentiator and shapes all later forms.
**Delivers:** Product CRUD, seeded code→name dictionary, HTMX search/autocomplete
**Addresses:** Catalog CRUD, fast search, dictionary autofill
**Implements:** CatalogService, search fragment endpoints

### Phase 3: Goods Receipt
**Rationale:** First operation type; proves the ledger write path, cost/price capture, and price history. Stock must exist before it can be sold.
**Delivers:** Receipt form (keyboard-first), ledger insert + quantity projection, price history
**Avoids:** Pitfall 3 (destructive edits) — append-only pattern established

### Phase 4: Sales
**Rationale:** The core value loop; depends on stock from receipts. Sale-line schema (cost snapshot) must be right here or profit is forever wrong.
**Delivers:** Multi-line sale form, price override, optional customer link (minimal customers table), cost snapshot, oversell warn-and-confirm flow, double-submit guard
**Avoids:** Pitfalls 9, 10 (current-price profit, oversell handling)

### Phase 5: Remaining Operations
**Rationale:** Write-off, sale-linked return, stock correction are small variations on the proven write path; also the compensating "cancel operation" flow.
**Delivers:** All five operation types + cancel-by-compensation UX
**Avoids:** Pitfall 3 (audit trail via compensating operations, never edits)

### Phase 6: Customers & History
**Rationale:** Pure reads over the now-populated ledger; purchase history is a ledger view, not a new table.
**Delivers:** Customer profiles, purchase history views

### Phase 7: Reports
**Rationale:** Last core phase — needs all operation types populated. Sales/profit/stock/write-offs/low-stock per period.
**Delivers:** Report screens with period filters, negative-stock visibility
**Avoids:** Pitfall 7 (local-day boundaries, half-open UTC intervals; test the 23:30 sale)

### Phase 8: Backup, Polish & Daily-Use Hardening
**Rationale:** Backup must ship before (or with) real daily entry; polish pays off the speed promise.
**Delivers:** Automated `VACUUM INTO` backup + rotation + tested restore, CSV export, operation-log browsing, keyboard-flow refinement
**Avoids:** Pitfall 5 (data loss)

*Note:* Backup could reasonably move earlier (into Phase 3–4) since real data entry starts as soon as receipts work — flag for roadmapper judgment. v1.x differentiators (stale-stock, top products, interested-customers, repurchase reminders) and v2 sync are post-roadmap milestones.

### Phase Ordering Rationale

- Dependencies point one way: schema → catalog → receipts → sales → other ops → customer/report reads. Reports last because they aggregate everything.
- Grouping mirrors the service boundaries (Catalog / Operation / Customer / Report services), so each phase completes one component.
- Front-loading the foundation phase neutralizes all four "impossible to retrofit" pitfalls before any real data exists.

### Research Flags

Phases likely needing deeper research during planning:
- **None strictly require it.** All phases use well-documented FastAPI/SQLAlchemy/HTMX patterns already detailed in ARCHITECTURE.md and PITFALLS.md.
- **Phase 2 (Dictionary):** minor open question — sourcing/format of the Oriflame code→name list (data acquisition, not technical research).
- **Future sync milestone (v2, out of scope now):** will need dedicated research when it arrives (conflict policy, transport, auth).

Phases with standard patterns (skip research-phase):
- **Phases 1–8:** established patterns; STACK.md pins exact versions, ARCHITECTURE.md provides the schema and write-path code shape, PITFALLS.md provides per-phase verification checks.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI/GitHub/unpkg on 2026-07-08 |
| Features | MEDIUM | Vendor marketing + comparison articles, cross-verified 3+ sources; no curated docs exist for this niche |
| Architecture | MEDIUM-HIGH | Ledger/op-log patterns are established industry practice (SAP NSDM, offline-first sync engines), multiple independent sources |
| Pitfalls | MEDIUM-HIGH | SQLite behavior from official docs (HIGH); design pitfalls community-cross-verified (MEDIUM) |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Oriflame code dictionary data source:** no verified source for the code→name list; plan for manual/CSV seeding and confirm format with the user during Phase 2 planning.
- **jinja2-fragments necessity:** version verified but adoption optional; decide when HTMX partials multiply (Phase 2–4).
- **Repurchase-reminder heuristic quality:** median-interval approach is an educated guess; validate against real data in v1.x, not before.
- **Backup timing in roadmap:** research says "before real daily data entry" — roadmapper should decide whether it lands in Phase 1/3 or Phase 8.

## Sources

### Primary (HIGH confidence)
- PyPI JSON metadata (fastapi, sqlalchemy, alembic, uvicorn, jinja2, pydantic, python-multipart, pytest, httpx, ruff, uv, jinja2-fragments) — versions verified 2026-07-08
- unpkg / GitHub releases — htmx 2.0.10 stable; 4.0.0-beta5 confirmed not stable
- SQLite official docs — WAL, temp files, busy_timeout, single-writer semantics

### Secondary (MEDIUM confidence)
- Direct-sales tools (Pink Office, Direct Sidekick, myCustomers+, QT Office) — feature baseline for the niche
- POS feature guides (Shopify, retailcloud, Microsoft Dynamics) — sale/return/override/adjustment semantics
- SAP S/4HANA NSDM blog, system-design guides, offline-first sync writeups — ledger + op-log architecture
- Modern Treasury / LearnPython — integer-cents money consensus; Vaultwarden discussions — SQLite backup practice

### Tertiary (LOW confidence)
- Repurchase-frequency inference approach — inferred from myCustomers+ marketing; needs validation with real data

---
*Research completed: 2026-07-08*
*Ready for roadmap: yes*
