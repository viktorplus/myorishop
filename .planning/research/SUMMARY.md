# Project Research Summary

**Project:** MyOriShop — v1.1 "Multi-Warehouse & Batch Tracking" milestone
**Domain:** Warehouse inventory web app (small-business, single operator) — schema/architecture evolution of an already-shipped FastAPI/SQLAlchemy/SQLite/HTMX app
**Researched:** 2026-07-10
**Confidence:** HIGH

## Executive Summary

This milestone extends a shipped, single-warehouse inventory app (FastAPI + SQLAlchemy 2.0 + SQLite + HTMX/Jinja2) to support multiple warehouses, batch/lot tracking with expiry and per-lot pricing, a category browsing page, a minimum-sale-price guardrail, and a mobile-responsive layout. All four research streams agree: no new runtime dependency is needed. Everything is a schema addition (`warehouses`, `batches` tables, nullable `Operation.batch_id`, nullable `Product.min_price_cents`) plus service-layer logic that reuses patterns already proven in v1.0 — the single-choke-point ledger (`record_operation()`), atomic SQL-side quantity increments, warn-but-allow guardrails (already used for oversell), soft-delete for mutable reference entities, and CSS-only responsive patterns.

The recommended approach is a two-tier stock cache: keep `Product.quantity` as an unchanged, ledger-derived rollup across all batches/warehouses (so every existing v1.0 report keeps working untouched), and add a new `Batch.quantity` cache maintained by the same atomic-increment mechanism inside the same `record_operation()` transaction. `Operation` gains one nullable `batch_id` FK (never a second `warehouse_id` FK — reachable via `batch.warehouse_id`), added as a bare, non-batch-mode `ALTER TABLE` to avoid dropping the append-only enforcement triggers (a documented, previously-hit pitfall). Historical rows stay `batch_id = NULL` ("legacy, no batch"); no destructive backfill UPDATE is attempted against the trigger-protected `operations` table.

The dominant risk is retrofitting granularity onto code that assumes one stock number per product: oversell checks (sales, write-offs), stock corrections' "counted" mode, and price/cost freezing at sale time are all currently keyed to `product_id` only and must be re-keyed to `(product_id, batch_id)` in the same phase the schema changes — deferring this creates a live oversell hole and silently corrupts stock or profit numbers the first time a product has more than one batch. Feature research also flags one gap not in the current Active list — stock transfer between warehouses — which every competitor product treats as core; recommend flagging it for explicit user sign-off rather than silently omitting it.

## Key Findings

### Recommended Stack

No new dependency. Reuses SQLAlchemy 2.0 (new FK-related tables/columns), Alembic (migrations 0006+, `render_as_batch=True` already configured), SQLite, and FastAPI/Jinja2/HTMX 2.0.10 (batch picker = same "type code -> hx-get filtered partial" pattern as existing product/customer autocomplete). Mobile responsiveness is pure CSS (media queries + a CSS-only details/checkbox nav disclosure) — explicitly rejecting Alpine.js, Pico.css, Bootstrap, or Tailwind as unnecessary for this scope.

**Core technologies (unchanged from v1.0, reused not added):**
- SQLAlchemy 2.0.51 — new `warehouses`/`batches` tables, `Operation.batch_id`, `Product.min_price_cents` — ordinary FK-related mapped classes, nothing exotic
- Alembic 1.18.5 — migrations 0006+; must use native `op.add_column` (not batch_alter_table) on `operations` to avoid dropping append-only triggers
- FastAPI + Jinja2 + HTMX 2.0.10 (vendored) — batch picker partial, warehouse/category pages, mobile nav — same partial-rendering pattern already established

**Explicitly rejected as unnecessary:** a date/calendar library (stdlib date.fromisoformat/isoformat suffices), any CSS framework, Alpine.js/JS framework for nav toggle, a generic inventory/FEFO package (batch selection here is manual, not automatic).

### Expected Features

**Must have (table stakes):**
- Multi-warehouse CRUD + free-text storage location per batch (WH-01/WH-02)
- Batch/lot entity with optional expiry, per-lot price, comment (LOT-01, LOT-03, LOT-04)
- Sale-time batch picker (LOT-02) — the milestone's core value
- Per-warehouse/per-batch stock visibility
- Category/rubric browsing page (CAT-01)
- Minimum-sale-price guardrail, warn-but-allow (PRICE-01)
- Mobile-responsive layout (UI-01)

**Should have (differentiators, already aligned with project's "simple, offline, single operator" identity):**
- Manual (not automatic FEFO) batch selection — deliberate, defensible design choice
- Free-text comment per batch
- "Товары на складе" as a lightweight operational view, not a buried report
- Mobile-first design for an operator standing in the warehouse, not a back-office desktop tool

**Flagged gap — recommend explicit user sign-off, not silent omission:**
- Stock transfer between warehouses — every competitor reviewed (Zoho, Odoo, Finale, LionO360) treats this as core once multi-warehouse exists; without it, moving stock requires write-off + receipt, which corrupts cost/profit history
- "Batches expiring within N days" list — cheap given existing report infra, closes the "expiry date stored but never surfaced" UX gap

**Defer (v2+):** automatic FEFO/FIFO allocation, per-warehouse low-stock thresholds, structured location hierarchy (zone/aisle/rack/bin), push/email expiry notifications, warehouse-scoped user roles (bundled with the already-deferred v2.0 multi-operator milestone).

### Architecture Approach

Two-tier denormalized stock cache maintained entirely inside the existing `record_operation()` choke point: `Product.quantity` stays an unchanged cross-batch rollup; a new `Batch.quantity` is incremented atomically in the same transaction whenever a `batch_id` is supplied. `Operation` gains one nullable, indexed `batch_id` FK (not a second `warehouse_id` FK — derivable via `batch.warehouse_id`); `Operation.product_id` is kept as-is so every existing report query needs zero changes. `Warehouse` is a mutable, soft-deleted reference entity mirroring `Product`'s pattern; `Batch` needs no soft-delete (it simply disappears from the picker once its quantity reaches 0).

**Major components:**
1. `Warehouse` model + CRUD service — physical location entity, soft-delete, no stock lives here directly
2. `Batch` model + batches.py service — the actual stock-holding unit (product x warehouse x expiry/price/location/comment), own cached quantity, resolve-or-create in receipts
3. `record_operation()` (modified, additive) — gains optional batch_id, atomically increments both Product.quantity and Batch.quantity in one transaction
4. sales.py/writeoffs.py/returns.py/corrections.py (modified) — oversell/removal checks re-keyed from product_id to (product_id, batch_id)
5. Category page + mobile CSS — pure additive read/UI layers, zero backend coupling to the batch/warehouse work

**Suggested build order** (dependency-driven): quick independent wins (CAT-01 + PRICE-01) first -> mobile-responsive CSS pass (before the batch picker exists, so it's built mobile-first, not retrofitted) -> warehouses (structural prerequisite) -> batches (largest, riskiest phase, touches the ledger schema and every stock-affecting service) last.

### Critical Pitfalls

1. **Two independently-drifting stock caches** — Product.quantity must stay a genuine ledger-derived rollup, updated in the same record_operation() call that updates Batch.quantity, never wired up as a separate later step. Avoid by making this an explicit Phase 1 decision before any migration is written.
2. **Oversell checks keyed by product_id only** — a basket with the same product split across two batches (one nearly empty) must be validated per-(product_id, batch_id), not per-product-total, or a real oversell hole opens the moment batches ship. Must land in the same phase as the batch picker, not deferred.
3. **Stock correction's "counted" mode diffs against the wrong baseline** — once stock is split, the existing qty_delta = counted - product.quantity corrupts every batch/warehouse except the one actually counted. Must be scoped to a specific batch or explicitly blocked/hidden once a product has >1 batch.
4. **batch_id/warehouse_id must be real indexed FK columns, not JSON payload fields** — payload was designed for descriptive, non-aggregated data; anything the system needs to SUM()/GROUP BY (oversell, remaining-qty display) needs a real column, exactly like product_id.
5. **Sale/receipt cost-freeze must snapshot the batch's price/cost, not the product card's** — otherwise profit reports silently use a stale or wrong cost the moment two batches of the same product have different costs, breaking the existing "historical profit reports never change" guarantee.

Additional notable pitfalls: no repair/rebuild path initially for the new batch-level cache (extend rebuild_stock); NOT NULL FK migration against non-empty tables (must be nullable + backfill-free, since operations' append-only triggers forbid a backfill UPDATE); sale basket's parallel array pattern (code[]/qty[]/price[]) needs a 4th strictly index-aligned batch_id[] array, tested against out-of-order row add/remove; minimum-price field must use the same is not None guard as effective_low_stock_threshold (a bare or would treat an explicit 0 minimum as "unset" — a bug already hit once in this codebase for a structurally identical feature).

## Implications for Roadmap

Based on combined research, suggested phase structure (5 phases):

### Phase 1: Quick wins — Category page + Minimum sale price
**Rationale:** Both are additive, zero dependency on warehouses/batches, and reduce the size of later, riskier phases while delivering visible value immediately.
**Delivers:** "Товары на складе" category browsing page (CAT-01); per-product min_price_cents with warn-but-allow sale guardrail (PRICE-01).
**Addresses:** CAT-01, PRICE-01 from FEATURES.md.
**Avoids:** Pitfall 8 (bare-or fallback bug) — implement with the identical is not None guard pattern already used for effective_low_stock_threshold.

### Phase 2: Mobile-responsive layout
**Rationale:** Pure CSS/template layer with zero schema coupling; doing this before batches means the most layout-dense new screen (the batch picker) is built mobile-first instead of retrofitted (a documented anti-pattern).
**Delivers:** @media breakpoints in style.css, CSS-only collapsible nav, horizontal-scroll wrappers for wide tables.
**Uses:** Vendored HTMX/Jinja2 stack, no new dependency.
**Implements:** Shared responsive list/table CSS pattern reused by later warehouse/batch screens.

### Phase 3: Warehouses (CRUD)
**Rationale:** Structural prerequisite for batches (Batch.warehouse_id FK) but not independently very useful yet; keep this phase short.
**Delivers:** warehouses table (soft-delete, mirroring Product's pattern), management page, possibly a seeded default warehouse for continuity.
**Uses:** SQLAlchemy 2.0 declarative style, Alembic migration with render_as_batch=True.

### Phase 4: Batches, ledger integration, and legacy-data migration
**Rationale:** The largest and riskiest phase — the only one touching the append-only ledger's schema and every stock-affecting service. Do it last, after warehouses exist and mobile CSS/category/price work is already shipped.
**Delivers:** batches table; nullable Operation.batch_id (native op.add_column, never batch_alter_table, to preserve the operations_no_update/operations_no_delete triggers); record_operation() extended with optional batch_id; rebuild_stock()/compute_stock() extended to repair batch-level caches; resolve-or-create batch in receipts; oversell checks in sales/write-offs re-keyed to (product_id, batch_id); correction "counted" mode scoped to a batch or blocked when a product has >1 batch; sale-time cost/price freeze sourced from the selected batch; sale basket's parallel arrays extended with a strictly index-aligned batch_id[]; a default "legacy warehouse + legacy batch" backfill for existing v1.0 data so nothing is orphaned.
**Implements:** Two-tier stock cache pattern; Batch-as-stock-holding-unit pattern; server-side re-validation that a submitted batch_id belongs to the submitted product (mirrors existing register_return origin re-validation).

### Phase 5 (flag for user decision, not yet committed): Stock transfer between warehouses
**Rationale:** Feature research identifies this as a near-universal table-stakes feature once multi-warehouse exists, but it is not in the current Active scope list.
**Delivers:** A transfer operation moving quantity from one batch/warehouse to another without corrupting cost/profit history (unlike the write-off + receipt workaround).
**Addresses:** The one significant gap flagged in FEATURES.md's competitor analysis.

### Phase Ordering Rationale

- Dependency chain: Batch.warehouse_id requires Warehouse to exist first; Operation.batch_id and all ledger/report rework require Batch to exist. Category browsing, minimum price, and mobile CSS have no dependency on any of the above or each other, so they're sequenced first to reduce the size and risk of the later, coupled phases.
- Doing the mobile-responsive CSS pass before batches avoids retrofitting the most layout-dense new screen (the batch picker) after the fact — a documented anti-pattern.
- Batches are sequenced last specifically because they are the only phase touching the append-only ledger schema and every stock-affecting service (sales, receipts, write-offs, returns, corrections) — isolating this risk to one phase, after the lower-risk work has already shipped, limits blast radius.

### Research Flags

Needs deeper research during planning:
- **Phase 4 (Batches/ledger integration):** Highest complexity — schema migration on a trigger-protected table, re-keying multiple oversell checks, cost-freeze rewiring, basket array alignment. Recommend `/gsd-plan-phase --research-phase 4` to work through migration sequencing and test design before implementation.
- **Phase 5 (Stock transfer, if approved):** Not yet scoped in PROJECT.md; needs its own feature/architecture pass once the user confirms it's in scope.

Phases with standard, well-documented patterns (skip research-phase):
- **Phase 1 (Category + min price):** Directly reuses existing catalog query patterns and the existing warn-but-allow oversell UX; no new pattern needed.
- **Phase 2 (Mobile CSS):** Standard CSS media-query technique, no framework decision remaining.
- **Phase 3 (Warehouses CRUD):** Directly mirrors Product's existing soft-delete + partial-unique-index pattern.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Zero new dependencies; conclusion grounded in direct inspection of the existing codebase rather than external version research, which was unnecessary since nothing new is being added |
| Features | MEDIUM-HIGH | Codebase facts (what's already scoped in PROJECT.md) are HIGH; competitive feature-landscape claims (Zoho, Odoo, DealPOS, etc.) are triangulated across 3+ independent web sources per claim but are vendor/forum sources, not primary documentation |
| Architecture | HIGH | Grounded entirely in direct reading of the current codebase's models, services, and migrations — not external research; this is project-specific integration analysis |
| Pitfalls | HIGH (architecture-fit findings) / MEDIUM (generic domain color) | Pitfalls tied to this codebase's specific patterns (ledger triggers, array-based basket, threshold fallback bug) are HIGH, verified firsthand; generic multi-location-inventory UX/performance color is MEDIUM (marketing-oriented sources) |

**Overall confidence:** HIGH

### Gaps to Address

- **Stock transfer between warehouses** is not in the current Active feature list but is flagged as a near-universal expectation once multi-warehouse exists. Needs explicit user decision before roadmap finalization: promote to this milestone (P1) or defer with a documented workaround (write-off + receipt, understood to lose cost/profit continuity).
- **Whether the combined-warning UX for oversold-batch + below-minimum-price on the same basket** should be one shared "confirm" flag or two sequential warnings — this is unresolved, recommendation is one shared flag as simplest default, but should be confirmed during phase planning.
- **Whether the SQLite DB already holds real operator-entered data** (vs. still being empty/demo) affects how cautiously the legacy-data backfill migration (default warehouse + legacy batch) must be tested — confirm with the user before writing that migration.
- **CSV export / backup** (app/services/export.py) is not required to include batch/warehouse columns this milestone per current scope, but is flagged as technical debt if left silently unaddressed — decide explicitly whether to extend it now or log it as a documented gap in PROJECT.md.
- **Whether reports (sales_profit_report, low-stock, stale-products) get a warehouse/batch breakdown this milestone** — current recommendation is to leave them product-level, unchanged, but this should be confirmed as an intentional scope boundary during roadmap creation, not an oversight.

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: app/models.py, app/services/ledger.py, app/services/sales.py, app/services/stock.py, app/services/reports.py, app/services/writeoffs.py, app/services/returns.py, app/services/corrections.py, app/services/receipts.py, app/services/catalog.py, app/services/export.py, app/templates/base.html, app/templates/partials/sale_row.html, app/static/style.css, alembic/versions/0001_initial_schema.py through 0005_product_thresholds.py, pyproject.toml
- .planning/PROJECT.md — v1.1 milestone scope, Active feature list, explicit Out of Scope items

### Secondary (MEDIUM confidence)
- Zoho Inventory, Odoo Inventory/POS, DealPOS, Finale Inventory, LionO360, Wasp, HandiFox — vendor documentation and product pages on multi-warehouse/batch tracking and minimum-selling-price patterns
- Odoo community forum — minimum-price warning implementation pattern, cross-checked against DealPOS's official docs

### Tertiary (LOW-MEDIUM confidence, needs validation)
- General multi-location-inventory blog/marketing content (Stockpilot, MRPeasy, EloERP, Sortly, Digit Software, Kladana, Inflow Inventory) — used only for generic UX/performance domain color, not as primary evidence for any architecture-specific claim

---
*Research completed: 2026-07-10*
*Ready for roadmap: yes*
