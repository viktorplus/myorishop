# Feature Research

**Domain:** Small-business warehouse inventory — multi-warehouse, batch/lot tracking, expiry, price guardrails
**Researched:** 2026-07-10
**Confidence:** MEDIUM-HIGH (codebase facts verified directly = HIGH; external practice patterns triangulated across multiple independent web sources = MEDIUM; no primary vendor documentation consulted)

> Supersedes the v1.0 FEATURES.md (2026-07-08, catalog/receipts/sales/customers/reports domain). This file covers only the v1.1 milestone: Multi-Warehouse & Batch Tracking. v1.0 findings remain valid history in git; see PROJECT.md "Validated" section for what already shipped.

## Feature Landscape

Reference products analyzed for this milestone: **Zoho Inventory** (multi-warehouse + batch/lot tracking, full-featured), **Odoo Inventory/POS** (lot/serial tracking, configurable removal strategies, transfer operations), **DealPOS** (minimum-selling-price warning — closest direct analog to PRICE-01), **Finale Inventory / LionO360 / Wasp** (multi-warehouse transfer and reorder-point patterns). Consistent pattern: every reviewed system treats **stock transfer between warehouses** and **batch-level expiry** as core, non-optional features once "multi-warehouse" or "batch tracking" is on the label — both are relevant checks against this milestone's scope below.

### Table Stakes (Users Expect These)

Features any multi-warehouse/batch system is assumed to have. Missing these makes the milestone feel incomplete relative to what "batch tracking" and "multi-warehouse" normally mean.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Stock transfer between warehouses | Every reviewed system (Zoho Inventory, Finale, LionO360, Wasp) treats moving stock from warehouse A to B as core, not optional — it's the most common operation once >1 warehouse exists. **Not in the current v1.1 Active list (WH-01/WH-02/LOT-01..04/PRICE-01/CAT-01/UI-01).** | MEDIUM | Flagged gap — see Dependency Notes. Without it, the only way to "move" stock is write-off + new receipt, which corrupts cost/profit history. |
| Per-warehouse and per-batch stock visibility | Users expect to see not just "10 units" but "6 in Warehouse A / shelf 3, 4 in Warehouse B" — the entire point of the "Товары на складе" (CAT-01) page. | LOW-MEDIUM | Already implied by LOT-02 (batch picker shows qty per batch); needs a stock-overview page grouping by category, then listing batches per product. |
| Batch expiry field, optional | Same SKU commonly has several batches with different expiry dates; expiry must live on the batch, not the product. | LOW | Already scoped as LOT-03. Matches industry practice — batch-level, not product-level. |
| Category/rubric browsing view | Standard secondary navigation once product count grows past ~30-50 items; users don't want to rely on search alone. | LOW | CAT-01. Read view on top of the existing `Product.category` free-text field — no new data model needed. |
| Minimum-price guardrail (warn, not block) | DealPOS and Odoo both implement exactly this pattern: warn when the entered price is below a floor, but allow an override rather than hard-blocking the sale. | LOW | PRICE-01. Matches the already-shipped oversell warn-but-allow pattern (SAL-04, v1.0) almost exactly — reuse that UX. |
| Free-text storage location tag | Small operations without scanner hardware universally use a plain shelf/location label rather than structured bin hierarchies. | LOW | WH-02. Right-sized for this project's scale (see Anti-Features: structured location hierarchy). |
| Mobile-responsive layout | An operator walking a physical warehouse checks stock or records a sale from a phone; desktop-only UI feels broken for this use case. | MEDIUM | UI-01. No data dependency, but touches every template — sequence early/continuously, not as one end-of-milestone pass. |

### Differentiators (Competitive Advantage)

Features that set this app apart from generic enterprise WMS/ERP tools, deliberately aligned with "single operator, simple, offline" Core Value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Manual batch selection (not automatic FEFO) | Enterprise systems force First-Expired-First-Out auto-deduction; a solo reseller often knows their physical stock better than the system (an already-open box, a customer wanting the near-expiry one at a discount). Manual pick with full visibility (price/expiry/qty/comment) is simpler AND more honest about who's actually in control. | LOW (already the plan, LOT-02) | Genuine, defensible design choice — worth stating explicitly so it isn't "fixed" later by someone assuming FEFO is the industry-mandatory default. |
| Free-text comment per batch | Enterprise batch tracking rarely offers a plain comment field — a cheap, human touch ("dented cap", "customer's favorite scent", "from supplier X's June delivery") that fits a small, personal reseller far better than rigid structured fields. | LOW | LOT-04. Cheap to build, meaningfully improves the sale-time picker's usefulness. |
| "Товары на складе" as an operational (not report) view | Most competitors bury stock-by-category inside a heavier "inventory report" module. A dedicated, fast, always-current browsing page is lighter-weight and more approachable for a non-technical single operator. | LOW-MEDIUM | Reuses existing catalog + stock query patterns (`all_active_products`, `Product.category`). |
| Mobile-first for a warehouse operator (not just admin-desk software) | Most small-business inventory tools reviewed assume a back-office desktop user; this app is meant to be used standing in the warehouse. | MEDIUM | Genuine differentiator vs. the desktop-only competitor products surveyed. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that look good on a "batch tracking" checklist but would be scope creep or actively wrong for this project's scale.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Automatic FEFO enforcement (system auto-picks the batch to sell from) | "Real" WMS software treats this as the definition of batch tracking. | Removes operator judgment for a single-person business where the person IS the expert on their own shelf; contradicts the already-decided Out-of-Scope item "Batch FIFO costing." | Keep the manual picker (LOT-02) as designed; optionally sort the picker list by soonest-expiry-first as a *default sort order only*, not an enforced rule. |
| Structured location hierarchy (zone → aisle → rack → bin, each a separate entity) | Feels "more professional," matches enterprise WMS vocabulary. | Overkill for "free-text storage location" as specified; adds a whole entity + relations + UI for zero benefit at this scale, with no barcode/scanner hardware to justify it. | Single free-text field per stock item (batch row), exactly as scoped in WH-02. |
| Push/email/SMS expiry alerts | Feels essential once you have expiry dates — "the system should warn me automatically." | No-internet-required is a hard constraint (runs offline); no auth/notification infra exists; a notification pipeline (scheduler, delivery channel, dedup) is a much larger feature than this milestone scopes. | A simple "batches expiring within N days" list/report, viewed on demand — same pattern as the existing low-stock report, no push mechanism. |
| Per-warehouse low-stock thresholds | Sounds like a natural extension of "multi-warehouse." | Doubles the settings surface (per-product AND per-warehouse fallback logic) for a business that almost certainly cares about *total* stock of a product when deciding to reorder, not which building it sits in. | Keep the existing single per-product threshold (`effective_low_stock_threshold`) checked against total quantity across all warehouses/batches; batch/warehouse breakdown stays a display-only concern. |
| Automatic multi-batch splitting on a single sale line (system silently draws from batch 1 then batch 2 when batch 1 runs short) | Looks like a nice convenience once oversell against a single batch is possible. | Hides which physical batch actually left the shelf — breaks the "operator manually selects" design intent (LOT-02) and complicates the frozen cost/price snapshot per sale line (which batch's cost applies?). | Apply the existing oversell warn-but-allow pattern (SAL-04) per selected batch: operator can oversell one chosen batch into negative remaining qty; to split across two batches, add two sale lines. |
| Warehouse-scoped user permissions / roles | Feels natural once "multiple warehouses" exist ("warehouse manager only sees their warehouse"). | Explicitly out of scope — v1 constraint is 1 operator, no auth complexity; user roles are already deferred to v2.0 per PROJECT.md. | Nothing in v1.1; revisit only alongside v2.0's planned multi-operator roles. |

## Feature Dependencies

```
WH-01 (create/manage warehouses)
    └──requires──> new Warehouse entity (id, name, soft-delete flag)

LOT-01 (batches per product code)
    └──requires──> new Batch entity, scoped to (product_id, warehouse_id)
                       └──requires──> WH-01 (a batch must live in a warehouse)

WH-02 (free-text storage location per stock item)
    └──best modeled as──> a field ON Batch (batch = "the physical stock item"), not a separate entity

LOT-02 (sale-time batch picker: price/expiry/qty/comment)
    └──requires──> LOT-01, LOT-03, LOT-04
    └──requires──> record_operation() gains an optional batch_id parameter
                       └──requires──> Batch.quantity cached column, updated the same
                                       atomic way Product.quantity is today

CAT-01 ("Товары на складе" grouped by category)
    └──requires──> existing Product.category field (already shipped, v1.0)
    └──enhances──> stock visibility once batches/warehouses exist (shows breakdown)

PRICE-01 (per-product minimum sale price, warn-but-allow)
    └──reuses pattern from──> SAL-04 oversell warn-but-allow (already shipped, v1.0)
    └──does NOT depend on──> LOT-01 (minimum stays product-level even though price varies per batch)

UI-01 (mobile-responsive layout)
    └──touches──> every existing template, independent of the data-model features above

[Stock transfer between warehouses] (NOT in current Active list — recommended addition)
    └──requires──> WH-01, LOT-01 (a transfer moves quantity out of one batch/warehouse
                     and into a batch/warehouse elsewhere)
    └──conflicts with──> using write-off + receipt as a workaround (loses cost/price
                          continuity, pollutes write-off reports with fake reasons)

[Expiring-soon report] (NOT in current Active list — recommended low-cost addition)
    └──requires──> LOT-03 (expiry date must exist to alert on it)
    └──reuses──> existing period-report date-window helpers (Phase 6 reports service)
```

### Dependency Notes — how this milestone interacts with the shipped v1.0 architecture

- **Stock cache granularity changes.** Today `Product.quantity` (D-09) is a single cached column, always `SUM(Operation.qty_delta)` for that product, maintained atomically inside `record_operation()` — the sole write path per the "one choke point" Key Decision already validated in v1.0. Introducing batches means stock must exist at (product, batch) granularity at minimum. **Recommended approach:** keep `Product.quantity` as-is (a total rollup, so every Phase 6 report — low-stock, stale-products, top-products, sales/profit — keeps working unchanged), and add a new `Batch.quantity` cached column maintained the same way (`Batch.quantity = Batch.quantity + qty_delta`, atomic SQL-side increment, same transaction). This is the minimal-change path: no existing report needs rewriting.
- **`record_operation()` needs a new optional `batch_id` parameter.** It is the single sanctioned write path — do not create a second path for batch stock. When `batch_id` is supplied, it must update `Batch.quantity` in addition to `Product.quantity`, in the same transaction, using the identical atomic-increment pattern already used for products. Receipts create/select a batch; sales, write-offs, returns, and corrections must specify which existing batch they affect once a product has batches.
- **Low-stock threshold logic (`effective_low_stock_threshold`, D-04/D-05) should NOT change.** Keep checking the product-level total (`Product.quantity`), not a per-warehouse or per-batch figure — avoids a second settings surface and matches what a single operator actually needs (a total reorder signal), per the Anti-Features table above.
- **Reports (`sales_profit_report` and siblings) join `Operation` → `Product` only today** — adding a nullable `batch_id` to `Operation` is backward-compatible and requires no changes to keep the existing reports working. Batch/warehouse-broken-down reports are a natural v2 extension, not required for this milestone.
- **Batch lifecycle should mirror the existing product soft-delete pattern.** Once a batch's `quantity` reaches 0 it should disappear from the sale-time picker but remain visible in `/history` and any batch-management view (never hard-deleted) — same append-only philosophy already applied to products (`deleted_at`, never a real DELETE).
- **Warehouse deletion needs a guard**, same shape as the existing product-deletion guard: reject (or require confirmation) if a warehouse still has batches with nonzero quantity.
- **Data migration / backfill gap:** existing v1.0 stock has no warehouse or batch. Recommend a one-time migration that creates a single "default warehouse" and one "legacy" batch per product (no expiry, current cached quantity, current cost/sale price) so v1.0 data is never orphaned by the schema change. This is as much a pitfall as a dependency — flag for the roadmap's first v1.1 phase.
- **Minimum sale price (PRICE-01) stays product-level**, not per-batch, even though batches can carry different sale prices — one number is simpler to reason about and matches the milestone's plain-language scope ("per-product minimum sale price").
- **Mobile-responsive layout (UI-01) has no data dependency** on any of the above — it can be sequenced independently, and doing it early/continuously (shared base template + CSS) avoids one giant end-of-milestone phase touching every existing template at once.

## MVP Definition

### Launch With (this milestone, v1.1)

- [ ] Warehouse entity + CRUD (WH-01) — nothing else in this milestone works without it
- [ ] Batch entity scoped to (product, warehouse), with location, expiry, price, comment, cached quantity (LOT-01, WH-02, LOT-03, LOT-04)
- [ ] Sale-time batch picker (LOT-02) — this is the milestone's core value; everything else supports it
- [ ] Per-product minimum sale price, warn-but-allow (PRICE-01) — reuses existing oversell UX, low cost
- [ ] "Товары на складе" category view (CAT-01) — low cost, high visible payoff
- [ ] Mobile-responsive layout (UI-01) — stated hard requirement, sequence early to avoid a late scramble
- [ ] Legacy-data migration: default warehouse + backfill batch per existing product (implicit prerequisite, not user-visible, but required so v1.0 data isn't orphaned)

### Add After Validation (v1.x, same milestone or immediate follow-up — recommend for user sign-off)

- [ ] Stock transfer between warehouses — flagged gap; without it, physical stock moves have no honest representation in the ledger. Recommend adding within v1.1 if any real cross-warehouse movement is expected; otherwise explicitly document as deferred with a stated workaround.
- [ ] "Batches expiring within N days" list/report — cheap given existing report infrastructure, high perceived value for anyone actually tracking expiry dates (the whole point of LOT-03).

### Future Consideration (v2+)

- [ ] Automatic FEFO/FIFO batch suggestion — deliberately rejected for this project's scale; revisit only if the operator explicitly asks for it after using manual selection for a while.
- [ ] Per-warehouse low-stock thresholds — only worth it if the business grows into genuinely independent warehouses with separate reorder cycles.
- [ ] Structured multi-level storage locations (zone/aisle/rack/bin) — only worth it alongside barcode scanning, which is already out of scope.
- [ ] Push/email expiry notifications — needs a scheduler + delivery channel; contradicts current offline/no-auth constraints.
- [ ] Warehouse-scoped user roles — bundled with the already-deferred v2.0 multi-operator/roles milestone.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Warehouse entity + CRUD (WH-01) | HIGH | LOW | P1 |
| Batch entity + storage location (LOT-01, WH-02) | HIGH | MEDIUM | P1 |
| Sale-time batch picker (LOT-02) | HIGH | MEDIUM | P1 |
| Optional expiry per batch (LOT-03) | HIGH | LOW | P1 |
| Optional comment per batch (LOT-04) | MEDIUM | LOW | P1 |
| Minimum sale price guardrail (PRICE-01) | MEDIUM | LOW | P1 |
| "Товары на складе" category page (CAT-01) | MEDIUM | LOW | P1 |
| Mobile-responsive layout (UI-01) | HIGH | MEDIUM | P1 |
| Legacy-data migration (default warehouse + backfill batch) | HIGH (prevents data loss) | LOW-MEDIUM | P1 (implicit prerequisite, not user-visible) |
| Stock transfer between warehouses | HIGH | MEDIUM | P2 (recommend promoting to P1 pending user confirmation) |
| Expiring-soon report | MEDIUM | LOW | P2 |
| Automatic FEFO suggestion | LOW (for this project) | HIGH | P3 / rejected |
| Per-warehouse thresholds | LOW | MEDIUM | P3 |

## Competitor Feature Analysis

| Feature | Zoho Inventory | Odoo (Inventory/POS) | DealPOS | MyOriShop v1.1 Approach |
|---------|-----------------|------------------------|---------|--------------------------|
| Multi-warehouse | Full warehouse hierarchy, per-warehouse reorder points, warehouse-specific reports | Multi-location + multi-warehouse with routes/rules (pull/push) | Location-based stock, simpler than Odoo | Flat list of warehouses, single free-text location tag per batch — no routing/rules engine |
| Batch/lot tracking | Batch numbers with expiry, supports FEFO picking during transfers/sales | Lot/serial tracking, FEFO/FIFO removal strategies configurable per location | Basic batch/expiry support | Batch = (warehouse, location, expiry, price, comment, qty); operator manually picks, no auto-removal strategy |
| Stock transfer | Dedicated transfer orders between warehouses, can select batch/serial during transfer | Internal transfer operations; stock moves are first-class ledger entries | Simpler stock adjustment between locations | **Gap in current scope** — recommended addition (see MVP Definition) |
| Minimum/floor price | Not a headline feature; pricing rules are more about tiered/customer pricing | Configurable price list rules; "no sale below cost" achievable via config/customizations | Explicit "minimum selling price" with warning popup — closest match to this project's need | PRICE-01 reuses existing oversell warn-but-allow UX exactly, per-product only |
| Expiry alerts | Configurable alert thresholds in advanced plans | Activity/automated action rules can flag near-expiry lots | Not a headline feature | Not currently scoped; recommend a simple on-demand "expiring soon" list reusing existing report infra, no push notifications |

## Sources

Confidence: MEDIUM-HIGH overall — direct codebase inspection is HIGH; vendor pages and forum posts are MEDIUM, cross-checked across 3+ independent sources per claim. (Note: gsd-tools `research-plan` / `classify-confidence` / `research-store` seams were not available as registered commands in this installation — `research-plan`, `classify-confidence` fell back through the generic CLI without producing plan/tier output; built-in WebSearch used directly per the tool_strategy fallback rules, confidence self-assessed using the source-hierarchy guidance.)

- [Expiration Date Management for Inventory: FIFO, FEFO, and Batch Tracking](https://stockpilot.co/blog/inventory-expiry-date-tracking-guide) — MEDIUM confidence (vendor blog, practitioner consensus)
- [First Expired, First Out: What Is FEFO and How Do You Manage It?](https://www.mrpeasy.com/blog/fefo-first-expired-first-out/) — MEDIUM
- [Batch & Expiry Tracking in Inventory: 7-Step Guide](https://eloerp.net/blog/batch-and-expiry-tracking-in-inventory/) — MEDIUM
- [Multi Warehouse Management & Inventory Software — LionO360](https://www.lionobytes.com/products/erp/features/multi-warehouse-management) — MEDIUM
- [Online Warehouse Management System — Zoho Inventory](https://www.zoho.com/us/inventory/warehouse-inventory-management/) — MEDIUM (vendor docs, describes a real shipped product's feature set)
- [Multi-Warehouse Inventory Management — Finale Inventory](https://www.finaleinventory.com/multi-warehouse-inventory-management) — MEDIUM
- [Inventory Management Software for Your Warehouse: Basic-to-Advanced Feature Checklist — HandiFox](https://www.handifox.com/handifox-blog/inventory-management-software-for-warehouse) — MEDIUM
- [Using and Configuring the Minimum Selling Price — DealPOS](https://support.dealpos.com/en/articles/4773830-using-and-configuring-the-minimum-selling-price) — MEDIUM-HIGH (vendor documentation of a real, directly analogous feature)
- [How to add warning to POS when user input price below standard price? — Odoo forum](https://www.odoo.com/forum/help-1/how-to-add-warning-to-pos-when-user-input-price-below-standard-price-139285) — MEDIUM (community forum, cross-checked against DealPOS's official docs)
- Direct codebase inspection: `app/models.py`, `app/services/ledger.py`, `app/services/stock.py`, `app/services/reports.py` (v1.0 shipped code) — HIGH confidence, verified firsthand
- Project context: `E:\dev\myorishop\.planning\PROJECT.md`

---
*Feature research for: MyOriShop v1.1 — Multi-Warehouse & Batch Tracking*
*Researched: 2026-07-10*
