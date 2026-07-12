# Roadmap: MyOriShop

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-07-10)
- 🚧 **v1.1 Multi-Warehouse & Batch Tracking** — Phases 7-11 (in progress)

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order. Phase numbering is continuous across milestones (never restarts at 1).

<details>
<summary>✅ v1.0 MVP (Phases 1-6) — SHIPPED 2026-07-10</summary>

- [x] Phase 1: Foundation & Ledger Core (3/3 plans) — completed 2026-07-08
- [x] Phase 2: Catalog, Dictionary & Search (4/4 plans) — completed 2026-07-08
- [x] Phase 3: Goods Receipt & Backup (3/3 plans) — completed 2026-07-09
- [x] Phase 4: Sales & Customers (6/6 plans) — completed 2026-07-09
- [x] Phase 5: Stock Operations & History (9/9 plans) — completed 2026-07-10
- [x] Phase 6: Reports & Data Export (6/6 plans) — completed 2026-07-10

Full phase details archived in `.planning/milestones/v1.0-ROADMAP.md`.

</details>

### 🚧 v1.1 Multi-Warehouse & Batch Tracking (In Progress)

**Milestone Goal:** Support multiple physical warehouses with in-warehouse locations, batch/lot-level stock (distinct expiry dates and prices per batch, chosen manually at sale time), category browsing, minimum-price guardrails, and a dedicated mobile flow.

- [x] **Phase 7: Category Browsing & Minimum Price Guardrail** - Operators browse stock grouped by category and get a warn-but-allow guardrail before underselling a product (completed 2026-07-10)
- [x] **Phase 8: Warehouses** - Operators create and manage multiple physical warehouses (completed 2026-07-11)
- [~] **Phase 9: Batch Tracking & Ledger Integration** - Stock is tracked per batch (warehouse, expiry, price, comment) and every stock-affecting operation requires picking a batch (built 2026-07-12; gap closure in progress from 09-UAT.md)
- [ ] **Phase 10: Warehouse Transfers & Expiry Reporting** - Stock moves between warehouses without losing cost history, and expiring batches are surfaced in a report
- [ ] **Phase 11: Dedicated Mobile Flow** - Operators can perform every core operation — including batch picking, transfers, and expiry checks — through simplified, single-purpose mobile screens, in one self-contained pass covering the complete final v1.1 operation set

## Phase Details

### Phase 7: Category Browsing & Minimum Price Guardrail

**Goal**: Operators can browse stock grouped by category and are protected from accidentally underselling a product below a set floor price
**Depends on**: Phase 6 (builds on the existing v1.0 catalog and sales flow; no new schema dependency)
**Requirements**: CAT-01, PRICE-01
**Success Criteria** (what must be TRUE):

  1. Operator can open a "Товары на складе" page and see all active products grouped under their category/rubric
  2. Operator can set, or leave unset, an optional minimum sale price on a product's card
  3. Selling below a set minimum price shows a warning and requires explicit confirmation before the sale is recorded (same warn-but-allow pattern as the existing oversell warning)
  4. A product with no minimum price configured never triggers the warning, and a minimum price explicitly set to 0 is respected rather than silently treated as "unset"

**Plans**: 4 plans (3 original + 1 gap closure)
Plans:
**Wave 1**

- [x] 07-01-PLAN.md — CAT-01: products_by_category() service query + /categories route, page, and nav link

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 07-02-PLAN.md — PRICE-01 (schema + form): migration 0006, Product.min_sale_cents, product-form field, audit trail

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 07-03-PLAN.md — PRICE-01 (sale guardrail): register_sale() price-floor check, warning partial, route wiring

**Gap closure (wave 1, from 07-VERIFICATION.md CR-01)**

- [x] 07-04-PLAN.md — PRICE-01 (negative-price guard): reject negative sale-line prices in register_sale independent of min_sale_cents

**UI hint**: yes

### Phase 8: Warehouses

**Goal**: Operators can organize stock across more than one physical warehouse
**Depends on**: Phase 6 (nothing new architecturally; structural prerequisite for Phase 9 — `Batch.warehouse_id` needs `Warehouse` to exist first — so it is sequenced immediately before it)
**Requirements**: WH-01
**Success Criteria** (what must be TRUE):

  1. Operator can create, edit, and soft-delete/restore a warehouse from a warehouse management page
  2. All existing v1.0 stock is automatically attributed to a seeded default warehouse after migration, with no data loss
  3. A soft-deleted warehouse no longer appears as a selectable option elsewhere in the app, but its operation history is preserved

**Plans**: 2 plans
Plans:
**Wave 1**

- [x] 08-01-PLAN.md — WH-01 (schema + service): Warehouse model, migration 0007 (seeded default warehouse, frozen id `00000000-0000-4000-8000-000000000010`), CRUD + warn-but-allow service layer

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 08-02-PLAN.md — WH-01 (web): /warehouses routes, page + rows partial templates, nav link, router registration

**UI hint**: yes

### Phase 9: Batch Tracking & Ledger Integration

**Goal**: Stock is tracked at the batch level (per warehouse, expiry, price, comment) and every stock-affecting operation requires the operator to pick a specific batch
**Depends on**: Phase 8
**Requirements**: WH-02, LOT-01, LOT-02, LOT-03, LOT-04, LOT-05
**Success Criteria** (what must be TRUE):

  1. A product code can have multiple batches, each with its own warehouse, optional free-text storage-location tag, optional expiry date, price, and optional comment
  2. At sale time, the operator sees a list of matching batches (price, expiry, remaining quantity, comment) for the product and must pick one before the line is added to the basket
  3. Write-off, return, and stock-correction forms also require picking the specific batch, not just the product
  4. Selling, writing off, or correcting more than a batch's remaining quantity shows an oversell/over-removal warning scoped to that batch, not the product's total across all its batches
  5. Existing v1.0 stock and sales history remain intact after migration — legacy operations show as belonging to a default legacy batch, with totals and reports still balancing

**Plans**: 9 plans (5 original + 4 gap closure from 09-UAT.md)
Plans:
**Wave 1**

- [x] 09-01-PLAN.md — LOT-01/LOT-03: Batch model, migration 0008 (batches table + operations.batch_id + legacy seed), batches.py read helpers, record_operation dual projection + rebuild invariant, ru_date filter

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 09-02-PLAN.md — WH-02/LOT-01/LOT-03/LOT-04: receipt warehouse select + resolve-or-create batch chooser (batch birth path)
- [x] 09-03-PLAN.md — LOT-02/LOT-04/WH-02: sale batch picker (shared batch_picker.html), server-driven selection, per-batch oversell

**Wave 3** *(blocked on Wave 2 — reuses batch_picker.html)*

- [x] 09-04-PLAN.md — LOT-05: write-off + correction batch pickers, batch-scoped count diff, per-batch over-removal warnings

**Wave 4** *(blocked on Wave 3 — D-12 guard flip needs all services batch-aware)*

- [x] 09-05-PLAN.md — LOT-05: return batch inheritance (+ legacy lazy-create), /history legacy display, D-12 mandatory batch guard flip

**Gap closure (from 09-UAT.md — 4 UAT issues across tests 1/4/5/6)**

**Wave 1** *(three independent fixes, no file overlap — run in parallel)*

- [ ] 09-06-PLAN.md — LOT-02 (blocker, UAT tests 4+5): wrap sale_lookup.html / sale_batch_pick.html OOB table fragments in `<template>` so htmx stops folding the batch-picker `<tr>` into the open sale line (kills the duplicate `batch_id[]` → «Выберите партию.» rejection); regression test for one `batch_id[]` per line + 3-line attribution
- [ ] 09-07-PLAN.md — LOT-05 (UAT test 6): /history dedicated «Код» column + «Действие»/«Вернуть» return link + `#return-slot` (template-only, mirrors recent_sales.html/purchase_history.html)
- [ ] 09-08-PLAN.md — WH-02/LOT-03/LOT-04 (UAT test 1, symptoms 1+2): receipt batch chooser `<fieldset>/<legend>` + state-adaptive helper; name-autofill dirty flag (`autocomplete=off` + `data-autofilled` reset-on-code-edit)

**Wave 2** *(blocked on 09-08 — shares receipt_batch_chooser.html)*

- [ ] 09-09-PLAN.md — LOT-01/LOT-04 (UAT test 1, symptom 3): migration 0009 native add-column `batches.name`, auto-generated «{product} — {date}» at creation, surfaced in the chooser top-up label

**UI hint**: yes

### Phase 10: Warehouse Transfers & Expiry Reporting

**Goal**: Operators can move stock between warehouses without losing cost/price history, and can see which batches are nearing or past their expiry date
**Depends on**: Phase 8, Phase 9
**Requirements**: WH-03, LOT-06
**Success Criteria** (what must be TRUE):

  1. Operator can transfer a batch, or part of its quantity, from one warehouse to another, and the destination retains the original cost/price history rather than resetting it
  2. A transfer is recorded in the operation history like any other stock-affecting operation
  3. Operator can open a report page listing batches with an approaching or already-passed expiry date

**Plans**: TBD
**UI hint**: yes

### Phase 11: Dedicated Mobile Flow

**Goal**: Operators can perform every core day-to-day operation through a dedicated, single-purpose mobile flow — not the desktop pages reflowed via CSS — covering the complete final v1.1 operation set (including batch picking, transfers, and expiry checks) in one self-contained pass
**Depends on**: Phase 7, Phase 8, Phase 9, Phase 10 — deliberately sequenced last so this single phase builds the mobile flow once, against the finished feature set, instead of building it early and having to extend it piecemeal every time a later phase adds an operation (batch picker, transfer, expiry report)
**Requirements**: UI-01
**Success Criteria** (what must be TRUE):

  1. From a smartphone-width viewport, the app offers a distinct mobile entry flow with simplified, single-purpose screens/steps for: searching stock, recording a receipt, recording a sale, recording a write-off/return/correction, and browsing history — separate screens from the existing desktop templates, not a CSS reflow of them
  2. The mobile sale, write-off, return, and correction flows include a simplified batch-selection step (price, expiry, remaining quantity, comment) whenever a product has more than one batch, and surface the same min-price/oversell warn-but-allow guardrails as the desktop flow
  3. Operator can perform a warehouse transfer and view the expiring-batches report through dedicated mobile screens, not only via the desktop pages
  4. The existing desktop pages — including the category page, batch picker, transfer form, and expiry report built earlier in this milestone — remain visually and functionally unchanged at desktop widths; the mobile flow is purely additive
  5. Landing on the app from a phone-width viewport routes the operator into the mobile flow (or offers an unmistakable entry point to it) rather than silently rendering the dense desktop templates

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|-----------------|--------|-----------|
| 1. Foundation & Ledger Core | v1.0 | 3/3 | Complete | 2026-07-08 |
| 2. Catalog, Dictionary & Search | v1.0 | 4/4 | Complete | 2026-07-08 |
| 3. Goods Receipt & Backup | v1.0 | 3/3 | Complete | 2026-07-09 |
| 4. Sales & Customers | v1.0 | 6/6 | Complete | 2026-07-09 |
| 5. Stock Operations & History | v1.0 | 9/9 | Complete | 2026-07-10 |
| 6. Reports & Data Export | v1.0 | 6/6 | Complete | 2026-07-10 |
| 7. Category Browsing & Minimum Price Guardrail | v1.1 | 4/4 | Complete    | 2026-07-10 |
| 8. Warehouses | v1.1 | 2/2 | Complete   | 2026-07-11 |
| 9. Batch Tracking & Ledger Integration | v1.1 | 5/9 | Gap closure | - |
| 10. Warehouse Transfers & Expiry Reporting | v1.1 | 0/TBD | Not started | - |
| 11. Dedicated Mobile Flow | v1.1 | 0/TBD | Not started | - |
