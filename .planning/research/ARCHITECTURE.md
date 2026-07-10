# Architecture Research

**Domain:** Multi-warehouse + batch/lot stock tracking, integrated into MyOriShop's existing single-choke-point ledger architecture (FastAPI + SQLAlchemy 2.0 + SQLite/WAL + HTMX + Jinja2)
**Researched:** 2026-07-10
**Confidence:** HIGH — grounded in direct reading of the current codebase (`app/models.py`, `app/services/ledger.py`, `stock.py`, `sales.py`, `receipts.py`, `writeoffs.py`, `reports.py`, `alembic/versions/0001_initial_schema.py`, `0005_product_thresholds.py`), not external research. This is project-specific integration analysis for the v1.1 milestone; it supersedes the v1.0-era architecture research previously in this file.

## Standard Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Routes (app/routes/*.py) — thin, return HTMX partials                     │
│ sales.py  receipts.py  writeoffs.py  returns.py  corrections.py           │
│ products.py  reports.py  history.py                                       │
│ + NEW: warehouses.py (CRUD)   + NEW: batch-picker partial endpoints       │
│   (likely added to sales.py/receipts.py routes, not a standalone router)  │
├─────────────────────────────────────────────────────────────────────────┤
│ Services (app/services/*.py) — "fat services", routes stay thin           │
│ sales.py  receipts.py  writeoffs.py  returns.py  corrections.py  stock.py │
│ reports.py  catalog.py  dictionary.py                                     │
│ + NEW: warehouses.py (CRUD, soft-delete)                                   │
│ + NEW: batches.py (resolve-or-create, list-for-picker, rebuild helpers)   │
├─────────────────────────────────────────────────────────────────────────┤
│ LEDGER CHOKE POINT — app/services/ledger.py::record_operation()            │
│ record_operation(type_, product_id, qty_delta, batch_id=None, ...)        │
│ — the ONLY writer of `operations` rows AND of BOTH stock cache columns    │
│   (Product.quantity rollup  +  NEW Batch.quantity detail)                 │
├─────────────────────────────────────────────────────────────────────────┤
│ Models (app/models.py)                                                     │
│  Product  (quantity = cross-batch rollup cache, UNCHANGED semantics)      │
│  Operation (append-only; product_id UNCHANGED; + nullable batch_id)       │
│  NEW Warehouse (mutable, soft-delete, mirrors Product's WR-04 pattern)    │
│  NEW Batch (mutable, FK product_id + warehouse_id, its own quantity cache)│
├─────────────────────────────────────────────────────────────────────────┤
│ SQLite (WAL) — DB-level triggers enforce operations append-only           │
│ (operations_no_update / operations_no_delete — unconditional, no WHEN)    │
└───────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `Warehouse` model | Physical location entity (name, soft-delete). No stock lives here directly. | NEW |
| `Batch` model | The actual stock-holding unit: one product × one warehouse × one expiry/price/location/comment combination, with its own cached `quantity`. | NEW |
| `Product.quantity` | Cross-warehouse, cross-batch rollup cache (`SUM(operations.qty_delta)` for that product). Drives catalog list, low-stock report, stale report. | UNCHANGED semantics |
| `Batch.quantity` | Per-lot cache (`SUM(operations.qty_delta)` for that batch). Drives the sale-time batch picker and per-batch oversell. | NEW |
| `record_operation()` | Single ledger write path. Gains an optional `batch_id` param; when present, atomically increments `Batch.quantity` in the SAME transaction it already uses to increment `Product.quantity`. | MODIFIED (additive) |
| `app/services/stock.py` | Low-stock report. Stays product-level (reads `Product.quantity`, unaffected by batches existing underneath it). | UNCHANGED |
| `app/services/reports.py` | Sales/profit/write-off/top-selling/stale reports. All currently join `Operation.product_id → Product`; keep working unmodified. Batch adds an *optional* future drill-down, not a required rewrite. | UNCHANGED (this milestone) |
| `app/services/sales.py` | Oversell check moves from "requested vs `Product.quantity`" to "requested vs `Batch.quantity` for the batch actually picked". | MODIFIED |
| `app/services/receipts.py` | Must resolve-or-create a `Batch` (mirrors today's resolve-or-create `Product` for unknown codes) before calling `record_operation`. | MODIFIED |
| `app/services/writeoffs.py` / `returns.py` / `corrections.py` | Must also target a specific `batch_id` once stock lives at batch granularity. | MODIFIED |
| `app/services/catalog.py` + new category page | Reads the existing `Product.category` field (already in the v1.0 schema) — a pure new read-only route/template, no model change. | NEW route, model unchanged |

## Does stock move from "per product" to "per product+warehouse+batch"?

**Yes, for the operational/detail layer — but keep `Product.quantity` as an honest rollup, do not repurpose or remove it.**

This is a two-tier cache, and both tiers are maintained by the exact same mechanism the app already uses (atomic SQL-side increment inside `record_operation`, always re-derivable from the ledger via `compute_stock`/`rebuild_stock`):

- **`Product.quantity`** (existing column) = total stock of that product across *every* warehouse and batch. Formula unchanged: `SUM(operations.qty_delta) WHERE product_id = X`. Adding batches doesn't change this — a batch-tagged `sale`/`receipt`/`writeoff` operation still carries `product_id` directly (see "Operation.product_id stays" below), so the existing rollup query needs zero changes.
- **`Batch.quantity`** (new column) = stock of one specific lot. Formula: `SUM(operations.qty_delta) WHERE batch_id = Y`. This is what the sale-time picker (LOT-02) and the per-batch oversell check need.

`rebuild_stock()` in `app/services/ledger.py` should be extended to also recompute every `Batch.quantity` alongside every `Product.quantity` — same repair philosophy, no new concept.

### What happens to `Operation`

Add **one** new nullable column: `batch_id: Mapped[str | None] = mapped_column(ForeignKey("batches.id"), index=True)`.

Do **not** also add `warehouse_id` to `Operation`. `Batch` already owns `warehouse_id`; a second FK on `Operation` would be redundant denormalization with no read pattern that needs it (any "stock by warehouse" report groups `Batch.warehouse_id` and joins `Operation.batch_id`, one hop).

`Operation.product_id` **stays exactly as-is** — it is not derived from `batch_id` and is not deprecated. Every existing report (`sales_profit_report`, `writeoff_report`, `top_selling_products`, `stale_products`) already joins on `Operation.product_id → Product` directly; keeping this column means **zero changes to any existing report query**. This mirrors how the ledger already denormalizes `unit_cost_cents`/`unit_price_cents` onto the operation row instead of forcing every read to chase a foreign key — same design principle, applied consistently.

`batch_id` is only meaningful for stock-affecting operation types (`receipt`, `sale`, `writeoff`, `return`, `correction`); it stays `NULL` for the audit-only, `qty_delta=0` types (`product_created`, `product_edited`, `price_change`), which have no batch concept.

### What happens to oversell checks

Today (`app/services/sales.py::register_sale`): aggregate requested qty **per `product_id`** across all basket lines, compare to `Product.quantity`.

After batches: since LOT-02 requires the operator to manually pick a batch per line, the natural (and *more* accurate) check becomes: aggregate requested qty **per `batch_id`** across all basket lines (same double-counting guard as today — Pitfall 6 in the existing code — just re-keyed), compare to `Batch.quantity`. This is a straightforward re-key of existing logic, not a new pattern. The same re-keying applies to the write-off oversell check in `app/services/writeoffs.py`.

### What happens to low-stock and stale-product reports

**Recommendation: leave both at product granularity, unchanged.** `low_stock_products()` (`app/services/stock.py`) keeps reading `Product.quantity` and `Product.low_stock_threshold` exactly as today — "is this product running low across all warehouses/batches combined" is still the useful operator question, and the per-product threshold field already exists. `stale_products()` (`app/services/reports.py`) keeps its `Operation.product_id` join — "has this product sold recently" doesn't care which batch fulfilled the sale.

A **separate, later** "batches nearing expiry" or "stock by warehouse" report is a natural follow-on once `Batch` exists, but it is not one of this milestone's requirements (PROJECT.md lists only WH-01/02, CAT-01, LOT-01..04, PRICE-01, UI-01) — flag it as a gap/future differentiator rather than building it now.

## New vs Modified Components

| Component | New / Modified | Notes |
|-----------|-----------------|-------|
| `Warehouse` model + `warehouses` table | NEW | Mutable entity, soft-delete (mirror `Product`'s `deleted_at` + partial-unique-active pattern on `name`, same as `uq_products_code_active`). |
| `Batch` model + `batches` table | NEW | `id` (UUID PK), `product_id` FK, `warehouse_id` FK, `expiry_date` (nullable), `price_cents` (nullable — the lot's own sale-price pre-fill, see below), `location` (nullable free text, WH-02), `comment` (nullable free text, LOT-04), `quantity` (cached, default 0), `created_at`/`updated_at`. No soft-delete needed (see Anti-Patterns). |
| `Operation.batch_id` | NEW column | Nullable FK to `batches.id`, indexed. Pre-migration rows stay `NULL` (see Anti-Pattern 3). |
| `Product.min_sale_cents` | NEW column | Nullable Integer, for PRICE-01. Fully independent of warehouses/batches. |
| `record_operation()` | MODIFIED (additive) | New optional `batch_id` param; when given, also does `batch.quantity = Batch.quantity + qty_delta` in the same transaction, and validates `batch.product_id == product_id` (mirrors the existing IN-01 deleted-product guard). |
| `rebuild_stock()` | MODIFIED | Also recomputes every `Batch.quantity`. |
| `app/services/sales.py`, `writeoffs.py`, `returns.py`, `corrections.py` | MODIFIED | Oversell/removal checks re-keyed to `batch_id`; each now requires resolving a batch before writing. |
| `app/services/receipts.py` | MODIFIED | Resolve-or-create a `Batch` (new expiry/price/location/comment or top up an existing batch), same transaction as today's resolve-or-create `Product`. |
| Category browsing page (`CAT-01`) | NEW route + template | Reads existing `Product.category`; zero model/ledger changes. |
| Mobile-responsive CSS (`UI-01`) | MODIFIED (styling only) | Touches templates/CSS across the whole app; zero backend/model coupling. |
| Reports (`app/services/reports.py`, `stock.py`) | UNCHANGED (this milestone) | Stay product-level as designed today. |

## Architectural Patterns

### Pattern 1: Two-tier denormalized stock cache

**What:** `Product.quantity` (rollup) and `Batch.quantity` (detail) are both maintained inside the same `record_operation()` transaction via atomic SQL-side increments (`col = col + delta`, no read-modify-write race), and both are fully re-derivable from the ledger (`compute_stock`/`rebuild_stock`).
**When to use:** Any time a new aggregation grain is added on top of an existing single-grain cache that must stay correct.
**Trade-offs:** One extra `UPDATE` per stock-affecting operation (cheap, single row by PK). Keeps the "cache is always a `SUM(ledger)` projection" invariant (`FND-01`) intact at both grains — no drift risk, no reconciliation job needed.

### Pattern 2: Batch as the stock-holding unit; Operation keeps its direct product_id

**What:** `Batch` becomes the true unit that holds quantity/expiry/price/location; `Operation` gets `batch_id` *in addition to* (not instead of) `product_id`.
**When to use:** When a new finer-grained entity is introduced under an existing ledger that many reports already query directly by the coarser key.
**Trade-offs:** One column of "redundant" data (`product_id` is technically derivable via `batch_id → Batch.product_id`), but it avoids rewriting every existing report join and avoids ever leaving `Operation.product_id` unset for historical rows. Consistent with the ledger's existing willingness to denormalize (`unit_cost_cents`, `unit_price_cents` are already snapshots, not FKs to look up elsewhere).

### Pattern 3: Mutable reference entity with soft-delete, reused from `Product`

**What:** `Warehouse` gets `deleted_at` + a partial unique index on `name` (`WHERE deleted_at IS NULL`), exactly mirroring `uq_products_code_active`.
**When to use:** Any reference entity that can be renamed/retired but is permanently FK-referenced by historical ledger rows (via `Batch.warehouse_id`) and must never be hard-deleted.
**Trade-offs:** `Batch` does **not** need this pattern — it has no natural-key uniqueness concern like `Product.code`/`Warehouse.name` do, so a batch simply stops appearing in the picker once `quantity` reaches 0 (a `WHERE quantity > 0` filter), with no soft-delete flag required. Keep it simpler than `Product`/`Warehouse` on purpose.

### Pattern 4: Warn-but-allow guardrail, reused verbatim for the minimum-price check

**What:** PRICE-01's "selling below minimum warns but allows override" is the *exact* existing `confirm != "1"` / `confirm == "1"` pattern already used for sale oversell (`SAL-04`) and write-off oversell.
**When to use:** Any new "soft block" business rule in this codebase — do not invent a second confirmation mechanism.
**Trade-offs:** Needs a product decision (flag for the roadmap, not answered here): should a below-minimum-price line and an oversold-batch line on the *same* basket surface as one combined warning screen, or two sequential ones? Reusing one `confirm` flag for both is simplest for the operator (one "yes, I'm sure" covers everything) and is the recommended default, but should be confirmed during phase planning.

## Data Flow

### Sale-time batch picker (new, LOT-02)

```
Operator types product code
    ↓
HTMX GET → batches.list_for_picker(product_id)
    → SELECT * FROM batches WHERE product_id = ? AND quantity > 0
      ORDER BY expiry_date ASC NULLS LAST  (soonest-to-expire first — an
      operator convenience ordering ONLY; this is not FIFO/FEFO costing,
      which PROJECT.md explicitly puts Out of Scope)
    ↓
Rendered list: price | expiry | remaining qty | comment  (per Batch row)
    ↓
Operator picks one row → basket line stores {product_id, batch_id, qty, price}
    ↓
On submit: register_sale() aggregates requested qty PER batch_id (re-keyed
Pitfall-6 guard), compares to Batch.quantity, warns or writes
    ↓
record_operation(type_="sale", product_id=…, batch_id=…, qty_delta=-qty, …)
    → increments Product.quantity AND Batch.quantity atomically
```

### Receipt flow (modified, resolve-or-create batch)

```
Operator enters code + qty + cost/sale/catalog prices
    ↓ (unchanged) resolve-or-create Product if code unknown
    ↓ NEW: resolve-or-create Batch
      - "add to existing batch" (pick from this product's open batches
        in the chosen warehouse) → just tops up quantity
      - "new batch" → operator enters expiry_date / price / location /
        comment for a NEW batches row (same transaction, mirrors how a
        new Product is created today for an unknown code)
    ↓
record_operation(type_="receipt", product_id=…, batch_id=…, qty_delta=+qty, …)
```

## Scaling Considerations

This is a single-operator, single-machine SQLite app — scale here is about row count over years, not concurrent users. Add:

| Concern | Approach |
|---------|----------|
| Batch-picker query speed | Index `batches(product_id, quantity)` (or a partial index `WHERE quantity > 0`) so "open batches for this product" stays a single index seek even after years of exhausted batches accumulate. |
| Operation table growth | Add `Index("ix_operations_batch_id", "batch_id")`, mirroring the existing `ix_operations_product_id` — same query patterns (recompute/report joins) will hit it. |
| Warehouse/batch counts | Realistically dozens of warehouses and low hundreds of batches per product at worst for a single reseller — no partitioning or archiving strategy is needed at this scale. |

## Anti-Patterns

### Anti-Pattern 1: Duplicating `warehouse_id` onto `Operation`

**What people do:** Add both `warehouse_id` and `batch_id` to `Operation` "to make warehouse reports faster."
**Why it's wrong:** `Batch.warehouse_id` already answers "which warehouse" for any batch-tagged operation; a second FK is redundant state that can drift if a batch is ever reassigned, and there is no read pattern in this milestone's requirements that needs it un-joined.
**Do this instead:** Join `Operation.batch_id → Batch.warehouse_id` when a warehouse-scoped report is needed later.

### Anti-Pattern 2: Repurposing `Product.quantity`

**What people do:** Try to make `Product.quantity` mean "unassigned/legacy stock not yet in a batch" once batches exist.
**Why it's wrong:** Breaks the catalog list, the low-stock report, and every v1.0 screen that reads `Product.quantity` as "total on hand" — a silent semantic change with no migration signal.
**Do this instead:** Keep `Product.quantity` computed exactly as it is today (`SUM` across ALL operations for that product, batch-agnostic). `record_operation()`'s existing line `product.quantity = Product.quantity + qty_delta` does not change at all.

### Anti-Pattern 3: Backfilling `operations.batch_id` for existing rows with a plain `UPDATE`

**What people do:** Write a normal Alembic migration that does `UPDATE operations SET batch_id = ...` to assign historical operations to a synthetic "legacy batch."
**Why it's wrong:** Confirmed by reading `alembic/versions/0001_initial_schema.py`: `operations_no_update` is `BEFORE UPDATE ON operations ... RAISE(ABORT, ...)` with **no `WHEN` clause** — it fires on *any* `UPDATE`, migration or application code alike. That migration's own docstring already warns that any future batch-mode migration touching `operations` must re-create these triggers (because SQLite's move-and-copy `ALTER TABLE` strategy drops them); backfilling existing rows compounds this into "drop trigger → UPDATE → recreate trigger" territory.
**Do this instead:** Add `batch_id` as nullable and leave it `NULL` on every pre-migration row — they simply represent "legacy stock, no batch assigned," which is honest and requires zero trigger surgery. Only require `batch_id` going forward for new writes of stock-affecting operation types. Before finalizing this migration, confirm with the user whether the SQLite file already holds real operator-entered data (v1.0 shipped the same day this milestone starts, and one Phase-1 human-verification item is still deferred per PROJECT.md) — if the DB is still empty/demo-only, this question is moot and a fresh dev DB sidesteps it entirely.

### Anti-Pattern 4: Building the batch-picker UI before the mobile-responsive pass

**What people do:** Build a dense desktop-only multi-column batch picker (price/expiry/qty/comment) first, then try to make it responsive afterward.
**Why it's wrong:** A 4-5 column picker table is one of the harder responsive-retrofit cases in this app (harder than the existing product/customer lists); designing it card-based-on-mobile from the start is much cheaper than reflowing it later.
**Do this instead:** Do the mobile-responsive CSS pass early (before batches), establishing a shared responsive list/table pattern that the batch picker and warehouse-management screens can reuse from day one.

## Integration Points

### External Services

None — this feature stays fully local/offline, consistent with v1.0's constraints. No new integration surface.

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `record_operation()` ↔ `Batch` model | Direct SQL-side increment (`batch.quantity = Batch.quantity + qty_delta`), same transaction as the existing `Product.quantity` increment | Only path that may write `Batch.quantity`; mirrors `IN-02`. |
| `sales.py`/`writeoffs.py`/`returns.py`/`corrections.py` ↔ new `batches.py` service | Resolve/select a `Batch` before calling `record_operation` | Same "resolve before write, whole basket is one transaction" discipline as today (D-03). |
| `receipts.py` ↔ new `batches.py` service | Resolve-or-create a `Batch` in the same transaction as resolve-or-create `Product` | Direct extension of the existing D-05 auto-create pattern. |
| `reports.py`/`stock.py` ↔ `Product` | Unchanged — stays product-level, no new dependency on `Batch` this milestone | Explicit scope boundary to keep the milestone's report surface stable. |
| Category page ↔ `Product.category` | Read-only query, no new FK | `category` already exists on `Product` since v1.0; CAT-01 is additive UI only. |

## Suggested Build Order

Dependency reasoning: `Batch.warehouse_id` is a hard FK dependency on `Warehouse` existing first. `Operation.batch_id` and the whole ledger/report rework depend on `Batch` existing. Category browsing, the minimum-price guardrail, and the mobile-responsive CSS pass have **no** dependency on any of the above or on each other — they are free to sequence wherever is cheapest.

1. **Quick, independent wins first — Category browsing (CAT-01) + minimum sale price guardrail (PRICE-01).** Both are additive, low-risk, and touch nothing that the warehouse/batch work will later change (`Product.category` already exists; `Product.min_sale_cents` is a lone new nullable column reusing the existing warn-but-allow pattern). Shipping these first reduces the size of the later, riskier phase and gives visible progress immediately.
2. **Mobile-responsive CSS pass (UI-01).** Pure styling/template layer, zero schema coupling. Doing this *before* batches means the new batch-picker UI (the most layout-dense screen this milestone adds) gets built mobile-first instead of retrofitted (Anti-Pattern 4).
3. **Warehouses (WH-01, WH-02 minus the per-batch location, i.e. warehouse CRUD itself).** New `warehouses` table + management page + soft-delete. This is a structural prerequisite for batches (`Batch.warehouse_id` FK) but is not independently very useful without batches, since v1.0 has no per-warehouse stock split yet — treat it as a short phase whose main job is to exist before Phase 4, possibly seeding one default warehouse for continuity.
4. **Batches (LOT-01..04, plus the deferred half of WH-02 — the free-text location, which lives on the batch row).** The largest phase: `batches` table, `Operation.batch_id`, `record_operation()` extension, `rebuild_stock()` extension, resolve-or-create batch in receipts, batch-keyed oversell in sales/write-offs/returns/corrections, the sale-time batch picker UI, and the migration decision from Anti-Pattern 3 (nullable `batch_id`, no backfill of historical rows). Do this last because it is the only phase that touches the append-only ledger's schema and every stock-affecting service.

## Sources

- Direct reading of the project codebase (HIGH confidence — verified firsthand, not web research):
  - `E:\dev\myorishop\app\models.py`
  - `E:\dev\myorishop\app\services\ledger.py`
  - `E:\dev\myorishop\app\services\stock.py`
  - `E:\dev\myorishop\app\services\sales.py`
  - `E:\dev\myorishop\app\services\receipts.py`
  - `E:\dev\myorishop\app\services\writeoffs.py`
  - `E:\dev\myorishop\app\services\reports.py`
  - `E:\dev\myorishop\alembic\versions\0001_initial_schema.py`
  - `E:\dev\myorishop\alembic\versions\0005_product_thresholds.py`
  - `E:\dev\myorishop\.planning\PROJECT.md`

---
*Architecture research for: MyOriShop v1.1 (Multi-Warehouse & Batch Tracking)*
*Researched: 2026-07-10*
