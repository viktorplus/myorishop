# Architecture Research

**Domain:** Local-first inventory & sales tracking (single operator, sync-ready)
**Researched:** 2026-07-08
**Confidence:** MEDIUM-HIGH (patterns are well-established industry practice: ledger-based inventory à la SAP S/4HANA NSDM, operation-log sync à la offline-first mobile apps; verified against multiple independent sources)

## Standard Architecture

### System Overview

The v1 app is a single FastAPI monolith serving server-rendered HTML (Jinja2 + HTMX) at localhost, backed by one SQLite file. The critical architectural move for sync-readiness is: **all stock changes go through an append-only operation log**; current stock is a *derived* value.

```
┌──────────────────────────────────────────────────────────────────┐
│                    Browser (localhost)                            │
│        HTMX: forms, partial swaps, autocomplete search            │
├──────────────────────────────────────────────────────────────────┤
│                    FastAPI (routes layer)                         │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌────────┐ │
│  │ catalog  │ │operations│ │ customers │ │ reports  │ │ search │ │
│  │ routes   │ │ routes   │ │ routes    │ │ routes   │ │ routes │ │
│  └────┬─────┘ └────┬─────┘ └─────┬─────┘ └────┬─────┘ └───┬────┘ │
│       │    returns Jinja2 templates / HTML partials       │      │
├───────┴────────────┴─────────────┴────────────┴───────────┴──────┤
│                    Service layer (business logic)                 │
│  ┌────────────────┐  ┌─────────────────────┐  ┌───────────────┐  │
│  │ CatalogService │  │  OperationService   │  │ ReportService │  │
│  │ (products,     │  │  (receipt, sale,    │  │ (aggregates   │  │
│  │  dictionary)   │  │  write-off, return, │  │  over ledger) │  │
│  └───────┬────────┘  │  correction)        │  └──────┬────────┘  │
│          │           └─────────┬───────────┘         │           │
├──────────┴─────────────────────┴─────────────────────┴───────────┤
│              SQLAlchemy models / repositories                     │
│  ┌──────────┐ ┌───────────────────────────┐ ┌───────────┐        │
│  │ products │ │ operations (APPEND-ONLY   │ │ customers │        │
│  │ (cached  │ │ event log = stock ledger  │ │ product_  │        │
│  │  stock)  │ │ = audit log = sync queue) │ │ dictionary│        │
│  └──────────┘ └───────────────────────────┘ └───────────┘        │
├───────────────────────────────────────────────────────────────────┤
│                    SQLite (single file, WAL mode)                  │
└───────────────────────────────────────────────────────────────────┘

Future (v2+, no rework needed):
  operations WHERE synced_at IS NULL  ──push──▶  Central FastAPI + PostgreSQL
  local DB  ◀──pull── operations from other devices since last cursor
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Routes layer | HTTP handling, form parsing, template rendering, HTMX partials. No business logic. | FastAPI `APIRouter` per domain area; Jinja2Templates; full page vs partial decided by `HX-Request` header |
| CatalogService | Product CRUD, dictionary lookups/auto-fill, price history | Plain Python class/module functions taking a SQLAlchemy session |
| OperationService | **The heart.** Validates and records receipt/sale/write-off/return/correction as immutable operation rows; updates cached stock in the same transaction; raises warnings (oversell) | Single service so every stock mutation goes through one code path |
| CustomerService | Customer profiles, purchase history, frequency/"running low" heuristics, interested-customer matching | Queries over `operations` (sales) joined with customers |
| ReportService | Period reports: sales, profit, stock, write-offs, top products, stale products, low stock | Read-only SQL aggregations over the operations ledger |
| Operations table (event log) | Source of truth for all stock movement + audit trail + future sync queue. INSERT-only. | One table, typed rows, UUID PK, never UPDATE/DELETE |
| Products table | Catalog fields + **cached** `quantity` column (derived from ledger, recomputable) | Mutable table; quantity maintained transactionally alongside ledger insert |
| product_dictionary | Pre-loaded code→name reference | Read-mostly table, seeded once |

## Recommended Project Structure

```
app/
├── main.py              # FastAPI app factory, static files, template config
├── config.py            # settings (DB path, device_id)
├── db.py                # engine, session dependency, SQLite PRAGMAs (WAL, foreign_keys)
├── models/              # SQLAlchemy models, one file per aggregate
│   ├── product.py       # Product, PriceHistory, ProductDictionary
│   ├── operation.py     # Operation (the event log)
│   └── customer.py      # Customer
├── schemas/             # Pydantic form/validation schemas
├── services/            # ALL business logic lives here
│   ├── catalog.py
│   ├── operations.py    # record_receipt(), record_sale(), record_writeoff()...
│   ├── customers.py
│   └── reports.py
├── routes/              # thin HTTP handlers, one router per UI area
│   ├── catalog.py
│   ├── operations.py    # receipt/sale/write-off/return/correction forms
│   ├── customers.py
│   ├── reports.py
│   └── search.py        # autocomplete endpoints (HTMX)
├── templates/
│   ├── base.html
│   ├── partials/        # HTMX fragments (search results, table rows, alerts)
│   └── pages/           # full pages per area
├── static/              # css, htmx.min.js (vendored — app must work offline)
└── alembic/             # migrations from day one
```

### Structure Rationale

- **services/ separated from routes/:** when sync arrives, the central server reuses `services/operations.py` replay logic verbatim; routes are the only web-specific part. Also the single most valuable habit for a learning developer.
- **models/ per aggregate:** keeps the four domains (catalog, ledger, customers, dictionary) visibly separate; mirrors the future sync boundary (operations sync as events; catalog/customers sync as rows).
- **partials/ vs pages/:** standard HTMX convention — every interactive element (search dropdown, operation confirmation, table refresh) is a fragment endpoint; pages compose fragments.
- **htmx vendored in static/:** hard requirement — the app runs without internet, so no CDN.

## Architectural Patterns

### Pattern 1: Append-Only Operation Log as Source of Truth (Event Sourcing "Lite")

**What:** Every stock-affecting action (receipt, sale, write-off, return, correction) is an immutable INSERT into one `operations` table. Current stock is derived: `products.quantity` is a cached projection updated in the same transaction, and can always be recomputed by summing the ledger. Mistakes are fixed by *compensating operations* (e.g., a correction), never by editing history.

**When to use:** Exactly this project — it simultaneously delivers three PROJECT.md requirements (operation history, audit log, sync-readiness) with one table. This is how serious inventory systems work (SAP S/4HANA's NSDM moved to a single INSERT-only material-document table for the same reasons: no lock contention, no redundancy, full history).

**Trade-offs:** Slightly more discipline (never UPDATE operations; corrections are new rows). Reports read the ledger, which stays fast for a single operator for years (tens of thousands of rows is nothing for SQLite). In exchange: perfect audit trail, trivially recomputable stock, and the sync queue already exists.

**Example (core schema — the key design artifact):**
```python
class Operation(Base):
    __tablename__ = "operations"
    id = mapped_column(String, primary_key=True)          # UUID (uuid4 ok; uuid7 nicer for sorting)
    device_id = mapped_column(String, nullable=False)     # constant per install; "main" in v1
    seq = mapped_column(Integer, nullable=False)          # local monotonic counter per device
    op_type = mapped_column(String, nullable=False)       # receipt|sale|writeoff|return|correction
    product_id = mapped_column(String, ForeignKey("products.id"), nullable=False)
    qty_delta = mapped_column(Integer, nullable=False)    # +N receipt, -N sale/writeoff, signed for correction
    unit_cost = mapped_column(Numeric(10, 2))             # cost at receipt
    unit_price = mapped_column(Numeric(10, 2))            # actual sale price
    catalog_price = mapped_column(Numeric(10, 2))
    customer_id = mapped_column(String, ForeignKey("customers.id"))  # optional, sales only
    note = mapped_column(String)
    created_at = mapped_column(DateTime, nullable=False)  # UTC wall clock
    created_by = mapped_column(String, nullable=False)    # operator name; "owner" in v1
    synced_at = mapped_column(DateTime)                   # NULL in v1; used by future sync push
    # UNIQUE(device_id, seq) — gives total order per device; id gives global dedup key
```
The five sync-enabling fields cost nothing now: `id` (UUID = idempotent replay key on the server), `device_id` + `seq` (per-device total order, replaces fragile wall-clock ordering — the poor-man's logical clock), `created_at` (human timeline), `synced_at` (outbox cursor). This is precisely the "operation with opId + logical position, dedup by opId, replay in per-device order" pattern used by production offline-first sync engines.

### Pattern 2: Transactional Ledger Insert + Projection Update

**What:** One service function per operation type does, inside a single DB transaction: (1) validate (product exists, warn on oversell), (2) INSERT operation row, (3) UPDATE `products.quantity += qty_delta`, (4) append price history if prices changed. A `rebuild_stock()` maintenance function recomputes all quantities from the ledger (consistency check / repair tool).

**When to use:** Always — this is the only write path for stock. UI code never touches `products.quantity` directly.

**Trade-offs:** Cached quantity is denormalized (two places), but the transaction + rebuild function keeps them honest. The alternative (compute stock on every read) is purer but makes every product list a SUM query — unnecessary complexity for v1.

**Example:**
```python
def record_sale(session, *, product_id, qty, unit_price, customer_id=None, allow_oversell=False):
    product = session.get(Product, product_id)
    if product.quantity < qty and not allow_oversell:
        raise OversellWarning(product.quantity)          # UI shows confirm dialog
    op = Operation(id=str(uuid4()), device_id=DEVICE_ID, seq=next_seq(session),
                   op_type="sale", product_id=product_id, qty_delta=-qty,
                   unit_price=unit_price, customer_id=customer_id,
                   created_at=utcnow(), created_by="owner")
    session.add(op)
    product.quantity += op.qty_delta
    session.commit()
    return op
```

### Pattern 3: Sync-Ready Row Conventions (applied everywhere, exercised later)

**What:** Conventions on *all* tables so future merge with a central PostgreSQL is a data-shipping problem, not a remodeling problem:
- **UUID string primary keys** on products, customers, operations (never autoincrement ints — two offline devices would mint colliding ids).
- **`created_at`/`updated_at` (UTC)** on mutable tables (products, customers) → enables last-write-wins merge for catalog-type data.
- **Soft delete** (`deleted_at` tombstone) instead of `DELETE` on products/customers → deletions can propagate.
- **Store money as `Numeric`/integer cents, times as UTC** — merging currencies/timezones later is much worse.

**When to use:** From the first migration. Retrofitting UUID PKs later means rewriting every FK — that is the "rework" PROJECT.md forbids.

**Trade-offs:** UUIDs are uglier in URLs and debugging than `1, 2, 3`; negligible cost otherwise at this scale. Future conflict strategy stays simple because the ledger side has *no conflicts by construction* (append-only sets merge as unions; stock = sum of all operations from all devices), and only catalog/customer field edits need LWW-by-`updated_at` — an acceptable policy for one team.

### Pattern 4: HTMX Fragment Endpoints

**What:** Routes return full pages normally and HTML fragments for HTMX requests (`HX-Request` header). Autocomplete = `GET /search/products?q=...` returning a `<ul>` partial; posting a sale returns an updated stock row + toast partial.

**When to use:** All interactive elements (search-as-you-type by code/name, inline warnings, table refreshes) — this delivers the "fast, minimal clicks" requirement with zero JavaScript build step.

**Trade-offs:** Some duplication between page and partial templates (solved with Jinja2 includes); state lives on the server, which is exactly right for a localhost single-user app.

## Data Flow

### Request Flow (write path — e.g., recording a sale)

```
Operator types product code → HTMX GET /search/products?q=134
    ↓ (fragment: matching products from dictionary+catalog, auto-fill name/prices)
Operator submits sale form → POST /operations/sale
    ↓
routes/operations.py (parse form, no logic)
    ↓
services/operations.record_sale()
    ├─ validate stock → OversellWarning? → return confirm partial, re-submit with allow_oversell
    ├─ INSERT operations row  ──────────────┐ one
    ├─ UPDATE products.quantity            ─┤ transaction
    └─ (link customer if provided)  ────────┘
    ↓
route renders partial: updated stock badge + "sale recorded" toast → HTMX swaps into page
```

### Read path (reports)

```
GET /reports?period=month
    ↓
services/reports.py → SQL aggregates over operations
   (profit = Σ sales.unit_price·qty − Σ matched cost;  v1: average cost, FIFO deferred)
    ↓
full page render (reports don't need HTMX interactivity beyond period picker)
```

### Key Data Flows

1. **Stock truth flow:** UI → OperationService → `operations` INSERT (+ cached quantity). All reads of "current stock" hit the cache; all *history* reads (reports, audit, customer purchase history, price history) hit the ledger. One direction, one write path.
2. **Dictionary auto-fill flow:** product code entry → dictionary lookup → pre-filled form; on first receipt of unknown-to-catalog code, a product row is created from the dictionary entry.
3. **Future sync flow (designed now, built later):** background task pushes `operations WHERE synced_at IS NULL` ordered by `seq` to central server; server dedups by `id`, appends to global log, replays through the *same* service code against PostgreSQL; client pulls foreign devices' operations since a cursor and applies them locally. No schema change required — only new code.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| v1: 1 operator, localhost | Exactly as above. SQLite in WAL mode; single process uvicorn. Nothing else. |
| v2: 2–5 operators, occasional internet | Add sync service (push/pull of operations), central FastAPI + PostgreSQL with identical `operations` schema, `device_id` becomes meaningful, add auth + `created_by` becomes real users. Local app unchanged otherwise. |
| Beyond | Only if ledger reads slow down (≫100k operations): add monthly stock snapshots table so reports sum from last snapshot instead of from zero. |

### Scaling Priorities

1. **First bottleneck (v2):** conflict policy for concurrent *catalog edits* (not stock — stock merges automatically as ledger union). Mitigated now by `updated_at` on products/customers → LWW.
2. **Second bottleneck:** report queries summing a large ledger → snapshot/rollup table. Purely additive change.

## Anti-Patterns

### Anti-Pattern 1: Mutable `quantity` column as the only record

**What people do:** `UPDATE products SET quantity = quantity - 3` with a separate, optional "history" table written as an afterthought (or not at all).
**Why it's wrong:** No audit trail, no way to answer "why is stock wrong?", and — fatally for this project — nothing to sync. Two offline devices both setting `quantity = 7` cannot be merged; two devices each appending "-3 sold" merge trivially.
**Do this instead:** Ledger is truth (Pattern 1); quantity is a cache.

### Anti-Pattern 2: Autoincrement integer primary keys

**What people do:** Default SQLAlchemy `id = Column(Integer, primary_key=True, autoincrement=True)`.
**Why it's wrong:** Two offline devices generate the same ids; merging requires renumbering every row and rewriting every foreign key — the definition of the rework we must avoid.
**Do this instead:** UUID string PKs from migration #1 (Pattern 3).

### Anti-Pattern 3: Editing or deleting operation history

**What people do:** "Fix" a mistyped sale by UPDATE-ing or DELETE-ing the operation row.
**Why it's wrong:** Breaks the audit requirement, silently desyncs cached stock, and makes replay non-idempotent (a device that already synced the original row diverges forever).
**Do this instead:** Compensating operations — a `correction` row (and UI affordance "cancel/fix last operation" that *generates* the compensating row).

### Anti-Pattern 4: Building sync/CRDT machinery in v1

**What people do:** Add Lamport/HLC libraries, vector clocks, CRDT columns, or a sync framework before there is a second device.
**Why it's wrong:** Massive complexity for a learning solo developer, zero v1 value, and half of it will be wrong until real sync requirements exist. The research consensus for local-first SQLite apps is: append-only op log + stable ids + per-device sequence is *sufficient groundwork*; the merge engine can come later.
**Do this instead:** Pattern 3's five cheap fields. Defer everything else to the sync milestone.

### Anti-Pattern 5: Business logic in route handlers

**What people do:** Stock math and validation inline in the FastAPI endpoint.
**Why it's wrong:** The future sync server must replay operations through the same logic without HTTP; also untestable.
**Do this instead:** Thin routes, fat `services/` (standard FastAPI layering).

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| None in v1 | — | Fully offline; vendor htmx.js locally |
| Future central server | HTTPS push/pull of operation batches (JSON), dedup by operation `id` | Same FastAPI codebase can host it; PostgreSQL mirror of `operations` schema |
| Backups | File copy of the SQLite DB (app is single-file DB by design) | Offer "Backup now" button + auto-copy on startup; use `VACUUM INTO` for a consistent snapshot |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| routes ↔ services | Direct function calls, session passed in | Routes never import models for writes |
| services ↔ models | SQLAlchemy session | OperationService is the *only* writer of `operations` and `products.quantity` |
| CustomerService ↔ ledger | Read-only queries on `operations` (op_type='sale') | Purchase history is a ledger view, not a separate table |
| ReportService ↔ ledger | Read-only SQL aggregates | Never writes |

## Build Order Implications (for roadmap)

Dependencies point one way, suggesting this phase order:

1. **Foundation:** project skeleton, DB setup (WAL, Alembic), core models with sync-ready conventions (UUID PKs, timestamps), `operations` table — *everything else depends on the schema being right first*.
2. **Catalog + dictionary:** products, code→name dictionary seed, search/autocomplete — needed before any operation can reference a product.
3. **Receipts:** first real operation type; proves the ledger write path + price history.
4. **Sales:** second operation type + optional customer link (customers table can start minimal here).
5. **Remaining operations:** write-off, return, correction — small variations on the proven path.
6. **Customers:** profiles, purchase history views, frequency/reminders, interested-customers — pure reads over the now-populated ledger.
7. **Reports:** aggregates over ledger — last because they need all operation types to exist.
8. **Polish:** oversell warnings flow, backups, operation-log browsing UI.

Sync itself is a separate future milestone; phases 1–5 above are what make it possible without rework.

## Sources

- [SAP S/4HANA Inventory Management NSDM — INSERT-only material document table rationale](https://community.sap.com/t5/enterprise-resource-planning-blog-posts-by-sap/sap-s-4hana-inventory-management-tables-new-simplified-data-model-nsdm/ba-p/13497469) — MEDIUM-HIGH (vendor engineering blog)
- [System Design Handbook — Inventory Management System design (immutable transaction ledger)](https://www.systemdesignhandbook.com/guides/design-inventory-management-system/) — MEDIUM
- [Local-First Architecture Series V: Bidirectional Sync & Conflict Resolution](https://www.welcomedeveloper.com/posts/local-first-architecture-5-bidirectional-sync/) — MEDIUM
- [sqlite-sync (CRDT-based offline-first sync for SQLite → PostgreSQL)](https://github.com/sqliteai/sqlite-sync) — MEDIUM (existence proof that op-log SQLite→Postgres sync is the standard shape)
- [Building Offline-First Apps with SQLite: Sync Strategies](https://www.sqliteforum.com/p/building-offline-first-applications) — MEDIUM
- [Offline sync without race conditions — opId dedup, per-entity ordering, outbox loop](https://medium.com/@connect.hashblock/7-js-pwas-at-scale-offline-sync-without-race-conditions-069a4bc41b10) — MEDIUM
- [Hybrid Logical Clock in Distributed Systems](https://singhajit.com/distributed-systems/hybrid-clock/) — MEDIUM (background; deliberately deferred past v1)
- [TestDriven.io — Using HTMX with FastAPI](https://testdriven.io/blog/fastapi-htmx/) — MEDIUM-HIGH (established tutorial site)
- [FastAPI + HTMX layered structure guides](https://medium.com/@sylvesterranjithfrancis/complete-guide-building-production-ready-web-apps-with-fastapi-and-htmx-from-setup-to-deployment-3010b1c8ff5c) — MEDIUM

---
*Architecture research for: local-first inventory & sales tracking (MyOriShop)*
*Researched: 2026-07-08*
