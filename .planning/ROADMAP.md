# Roadmap: MyOriShop

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-07-10)
- ✅ **v1.1 Multi-Warehouse & Batch Tracking** — Phases 7-11 (shipped 2026-07-13)
- ✅ **v1.2 Catalog Pricing UX & List Ergonomics** — Phases 12-14 (shipped 2026-07-14)
- ✅ **v1.3 Финансы / Касса** — Phases 15-17 (shipped 2026-07-15)
- 🚧 **v2.0 UX Overhaul & Navigation Restructure** — Phases 18-24 (in progress)

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

<details>
<summary>✅ v1.1 Multi-Warehouse & Batch Tracking (Phases 7-11) — SHIPPED 2026-07-13</summary>

- [x] Phase 7: Category Browsing & Minimum Price Guardrail (4/4 plans) — completed 2026-07-10
- [x] Phase 8: Warehouses (2/2 plans) — completed 2026-07-11
- [x] Phase 9: Batch Tracking & Ledger Integration (9/9 plans) — completed 2026-07-12
- [x] Phase 10: Warehouse Transfers & Expiry Reporting (3/3 plans) — completed 2026-07-12
- [x] Phase 11: Dedicated Mobile Flow (10/10 plans) — completed 2026-07-13

Full phase details archived in `.planning/milestones/v1.1-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.2 Catalog Pricing UX & List Ergonomics (Phases 12-14) — SHIPPED 2026-07-14</summary>

- [x] Phase 12: Code & Name Autofill (4/4 plans) — completed 2026-07-13
- [x] Phase 13: Mobile Wizard Context & Navigation (6/6 plans) — completed 2026-07-14
- [x] Phase 14: List Pagination, Filtering, Sorting & Quick Delete (7/7 plans) — completed 2026-07-14

Full phase details archived in `.planning/milestones/v1.2-ROADMAP.md`.

</details>

<details>
<summary>✅ v1.3 Финансы / Касса (Phases 15-17) — SHIPPED 2026-07-15</summary>

- [x] Phase 15: Cash Ledger Foundation (4/4 plans) — completed 2026-07-14
- [x] Phase 16: Manual Cash Movements & History (4/4 plans) — completed 2026-07-15
- [x] Phase 17: Financial Reports, Export & Dashboard Analytics (5/5 plans) — completed 2026-07-15

Full phase details archived in `.planning/milestones/v1.3-ROADMAP.md`.

</details>

### 🚧 v2.0 UX Overhaul & Navigation Restructure (In Progress)

**Milestone Goal:** Rework navigation into nested/secondary menus, add an operational dashboard to the home page, unify the product price model to two fields (ДЦ/ПЦ), and rebuild the Products/Warehouses/Sales/History/Customers pages around the operator's real workflow instead of their original one-feature-at-a-time shape.

- [x] **Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ)** - Collapse every price field in the app to exactly two, editable anywhere, with reference-deviation color cues (completed 2026-07-16)
- [x] **Phase 19: Products Page Rebuild** - Group the product list by code with batch breakout, category filter, and receipt-first entry (completed 2026-07-16)
- [x] **Phase 20: Warehouses & Batch-Split Transfers** - Form-driven warehouse management with stock-guarded delete, plus a correct partial-batch transfer (completed 2026-07-16)
- [x] **Phase 21: Customer Profiles & Purchase Insights** - Multi-contact profiles with last-order date, period spend, and favorite products (completed 2026-07-17)
- [ ] **Phase 22: Sales Page Rebuild** - Table-shaped sale form with a live running total and a new/existing/anonymous customer flow
- [ ] **Phase 23: Dashboard & History Rebuild** - Operational home page plus a type-first history with per-type columns and filters
- [ ] **Phase 24: Navigation Restructure & Settings** - Reduce the top-level nav to first-class pages and nest the rest where they belong

## Phase Details

### Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ)

**Goal**: Every price the operator sees or edits anywhere in the app is one of exactly two — ДЦ (cost/distributor) or ПЦ (sale/catalog) — and can be corrected from wherever it is noticed.
**Depends on**: Nothing in this milestone (builds on shipped v1.3)
**Requirements**: PROD-05, PROD-06, PROD-07
**Scope note (operator decision, 2026-07-15)**: `Product.catalog_cents` collapses into ПЦ (`sale_cents`); `Product.cost_cents` is ДЦ. `Product.min_sale_cents` is **explicitly out of scope for removal** — it is a guardrail threshold, not a displayed price, and the Phase 7 below-minimum sale warning (PRICE-01, shipped v1.1) must keep working unchanged. Do not migrate it away.
**Success Criteria** (what must be TRUE):

  1. Operator sees exactly two price fields — ДЦ and ПЦ — on the product card, the dictionary entry, the goods receipt, and the sale form (desktop and mobile); no third or fourth price field appears anywhere in the app.
  2. Operator can edit ДЦ or ПЦ from any of those four entry points, and the change is saved from where it was made.
  3. Typing a ДЦ or ПЦ below the dictionary's reference price shows the field in yellow; above the reference shows blue; matching the reference shows neither.
  4. Stock, sales, and profit figures recorded before the consolidation still display the prices they were recorded at — no historical money data is lost or re-interpreted.
  5. Selling below a product's configured minimum sale price still shows the existing warn-but-allow warning (PRICE-01 regression guard).

**Plans**: 8 plans (5 waves)

- [x] 18-01-PLAN.md — Reference lookup fix in place (D-22) + reference_prices_for_code contract for the cue
- [x] 18-02-PLAN.md — Service + product-list/export catalog_cents reference removal (model attr stays)
- [x] 18-03-PLAN.md — Receipt catalog-field removal, desktop + mobile wizard (Pitfall 1); stop ledger payload write (D-04)
- [x] 18-04-PLAN.md — Drop the column: 0014 native migration + model removal + D-24 pre-drop backup (irreversible, human-gated)
- [x] 18-05-PLAN.md — Label unification (D-19), min_sale regroup (D-21), catalog-detail «изменить цену» → product card (D-18)
- [x] 18-06-PLAN.md — Sale write-back wording: two hint constants with the sale-only scope clause (D-17/D-23)
- [x] 18-07-PLAN.md — Colour cue foundation (price-cue.js, CSS tokens) + product-card data-ref-cents wiring
- [x] 18-08-PLAN.md — Cue wiring on receipt + sale surfaces (desktop + mobile) + criterion-3 visual sign-off

**UI hint**: yes

### Phase 19: Products Page Rebuild

**Goal**: The products page reads as a stock list the operator can scan by code, not a flat per-batch dump with a redundant add path.
**Depends on**: Phase 18 (rows render the final two-price shape)
**Requirements**: PROD-01, PROD-02, PROD-03, PROD-04, PROD-08
**Success Criteria** (what must be TRUE):

  1. Product list shows one row per product code carrying the total quantity summed across all of that code's batches.
  2. Operator can see each code's individual batches, each with its own expiry date and batch name.
  3. Product list shows each product's category and can be filtered by category.
  4. The "Добавить товар" button is gone from the product list, and delete is a text link rather than a button.
  5. Existing pagination, filtering, and sorting on the product list keep working against the new grouped rows.

**Plans**: 1 plan

- [x] 19-01-PLAN.md — Quantity column + collapsed batch breakout, remove add-button, delete-as-text-link (PROD-01..04, PROD-08 regression)

**UI hint**: yes

### Phase 20: Warehouses & Batch-Split Transfers

**Goal**: Operator manages warehouses through dedicated forms and can move part of a batch out under a different expiry or condition without corrupting the batch it came from.
**Depends on**: Phase 18 (batch price shape). Sequenced after Phase 19 but not blocked by it.
**Requirements**: WH-01, WH-02, WH-03, XFER-01
**Success Criteria** (what must be TRUE):

  1. Warehouse list shows each warehouse's current item count and the date of its last goods receipt.
  2. Operator adds, edits, and deletes a warehouse via links that open a dedicated form rather than inline row controls.
  3. Deleting a warehouse that still holds stock is refused; deleting one holding zero stock succeeds.
  4. Transferring part of a batch under a different expiry date or condition creates a new destination batch holding only the moved portion, leaving the source batch's remaining quantity and attributes unchanged.

**Plans**: 7 plans (3 waves)

Plans:
**Wave 1**

- [x] 20-01-PLAN.md — Warehouse item-count & last-receipt aggregate queries (WH-01, D-03/D-04)
- [x] 20-04-PLAN.md — Transfer service: same-warehouse split + override-or-inherit + qty echo (XFER-01, D-05/D-06/D-07/D-08/D-11)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 20-02-PLAN.md — Warehouse dedicated add/edit/delete routes + templates (WH-02/WH-03, D-01/D-02)
- [x] 20-05-PLAN.md — Desktop transfer routes: dest-filter fix, ownership guard, qty echo, override wiring (XFER-01, D-09/D-10/D-11)
- [x] 20-06-PLAN.md — Mobile transfer parity: dest-filter fix, override wiring, qty echo (XFER-01, D-09 mirrored)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 20-03-PLAN.md — Warehouse list restructure: item-count/last-receipt columns, filter/sort/status preserved (WH-01/02/03)
- [x] 20-07-PLAN.md — Desktop override-field UI + web-level test coverage (XFER-01)

**UI hint**: yes

### Phase 21: Customer Profiles & Purchase Insights

**Goal**: A customer profile holds every way to reach the person and shows what they actually buy, so the operator can act on it.
**Depends on**: Nothing in this milestone (builds on the shipped v1.0 customer/sale ledger)
**Requirements**: CUST-01, CUST-02, CUST-03, CUST-04, CUST-05, CUST-06, CUST-07, CUST-08
**Success Criteria** (what must be TRUE):

  1. Operator can record multiple phone numbers, multiple Telegram handles, multiple email addresses, multiple social-profile links, and a physical address on a single customer profile.
  2. Customer profile shows the date of that customer's most recent order.
  3. Customer profile shows the customer's spend totals for the last month, quarter, and year.
  4. Customer profile shows the customer's favorite products ranked by purchase frequency and quantity.

**Plans**: 5 plans in 5 waves (0-4)

Plans:
**Wave 1**

- [x] 21-01-PLAN.md — Wave 0: CustomerContact + Customer.address schema, migration 0015, past-dated-sale test fixture
- [x] 21-02-PLAN.md — Wave 1: contacts + address service (validation, full-replace, contacts_by_kind)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 21-03-PLAN.md — Wave 2: purchase-insights service (spend windows, favorites ranking, last order date, portability guard)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 21-04-PLAN.md — Wave 3: customer form UI (4 repeatable contact sections, address, /customers/contact-row)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 21-05-PLAN.md — Wave 4: customer detail UI (Контакты, Покупки, Любимые товары) + zero-order and XSS guards

**UI hint**: yes

### Phase 22: Sales Page Rebuild

**Goal**: Operator records a sale as a plain table with the total always visible and settles the customer question in one control at the top.
**Depends on**: Phase 18 (ПЦ on the sale line), Phase 21 (extended profile fields for the inline new-customer form)
**Requirements**: SALE-01, SALE-02, SALE-03, SALE-04, SALE-05, SALE-06, SALE-07
**Success Criteria** (what must be TRUE):

  1. Sale form is a code / name / quantity / sale-price table.
  2. A running total — amount and unit count — sits directly under the table and updates as lines are filled in.
  3. Operator picks new / existing / anonymous customer from a radio at the top of the form: existing offers autocomplete by consultant number, name, or surname and auto-fills the other identifying fields; new shows inline optional profile fields; anonymous shows no extra fields.
  4. Recent-sales list shows each sale's customer name (first + last).
  5. Existing sale guardrails (oversell warning, batch selection, cash credit) still fire on the rebuilt form.

**Plans**: 7 plans

Plans:
**Wave 1**

- [ ] 22-01-PLAN.md — Wave 1: desktop red-side tests (SALE-03/04/05/06/07 + SALE-01 regression guard)
- [ ] 22-02-PLAN.md — Wave 1: live-total, mobile and to_cents parity tests

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 22-04-PLAN.md — Wave 2: live running total, sale-total.js + both shells (SALE-02)
- [ ] 22-05-PLAN.md — Wave 2: desktop 3-way customer header + D-10 guard + D-12 chip fix (SALE-03..06)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 22-03-PLAN.md — Wave 3: recent-sales customer column via portable outerjoin (SALE-07)
- [ ] 22-06-PLAN.md — Wave 3: mobile customer selector partials + endpoints (D-04 parity)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 22-07-PLAN.md — Wave 4: mobile basket wiring, customer_id write path, D-11 batch-card fix

**UI hint**: yes

### Phase 23: Dashboard & History Rebuild

**Goal**: Главная answers "what is the state of the business right now" at a glance, and История answers "what happened" narrowed to the operation type the operator cares about.
**Depends on**: Phase 18 (stock valuation reads ДЦ/ПЦ), Phase 22 (customer column in the operations feed)
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, HIST-01, HIST-02, HIST-03, HIST-04
**Success Criteria** (what must be TRUE):

  1. Home page shows the current date, weekday, and time, plus the active catalog number and the days remaining until it closes.
  2. Home page shows revenue, profit, and expense totals for today, the current week, and the current month, alongside the total distinct product codes in stock and their combined valuation.
  3. Home page shows a recent-operations feed whose columns adapt per operation type (type, code, name, expiry, quantity, cost, profit, customer).
  4. History page lets the operator select an operation type first and then shows only that type's relevant columns.
  5. History results can be filtered by product code, date range, customer, and category, sorted by the relevant columns, and paginated.

**Plans**: TBD
**UI hint**: yes

### Phase 24: Navigation Restructure & Settings

**Goal**: The top-level nav shows only first-class pages, and every secondary action is reachable from the page it belongs to — on desktop and mobile alike.
**Depends on**: Phase 19 (Товары page in final shape), Phase 20 (Склады page in final shape, Перемещение entry point), Phase 23 (Главная in final shape)
**Requirements**: NAV-01, NAV-02, NAV-03, NAV-04, NAV-05, NAV-06, NAV-07, NAV-08, RPT-01, MOB-01
**Success Criteria** (what must be TRUE):

  1. Top-level nav shows only Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы, and Настройки.
  2. Operator reaches Приход, Списание, and Справочник from the Товары page, and Перемещение from the product context.
  3. Operator reaches Склады and Резервные копии from the new Настройки page, and Экспорт from the Резервные копии page.
  4. Every report detail page has a "Назад к отчётам" link that returns to /reports.
  5. Mobile navigation offers the same main tabs as desktop (Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы), excluding Настройки.

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20 → 21 → 22 → 23 → 24

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
| 9. Batch Tracking & Ledger Integration | v1.1 | 9/9 | Complete    | 2026-07-12 |
| 10. Warehouse Transfers & Expiry Reporting | v1.1 | 3/3 | Complete    | 2026-07-12 |
| 11. Dedicated Mobile Flow | v1.1 | 10/10 | Complete   | 2026-07-13 |
| 12. Code & Name Autofill | v1.2 | 4/4 | Complete    | 2026-07-13 |
| 13. Mobile Wizard Context & Navigation | v1.2 | 6/6 | Complete    | 2026-07-13 |
| 14. List Pagination, Filtering, Sorting & Quick Delete | v1.2 | 7/7 | Complete    | 2026-07-14 |
| 15. Cash Ledger Foundation | v1.3 | 4/4 | Complete   | 2026-07-14 |
| 16. Manual Cash Movements & History | v1.3 | 4/4 | Complete    | 2026-07-15 |
| 17. Financial Reports, Export & Dashboard Analytics | v1.3 | 5/5 | Complete   | 2026-07-15 |
| 18. Two-Price Model Consolidation (ДЦ/ПЦ) | v2.0 | 8/8 | Complete   | 2026-07-16 |
| 19. Products Page Rebuild | v2.0 | 1/1 | Complete    | 2026-07-16 |
| 20. Warehouses & Batch-Split Transfers | v2.0 | 7/7 | Complete   | 2026-07-16 |
| 21. Customer Profiles & Purchase Insights | v2.0 | 5/5 | Complete    | 2026-07-17 |
| 22. Sales Page Rebuild | v2.0 | 0/TBD | Not started | - |
| 23. Dashboard & History Rebuild | v2.0 | 0/TBD | Not started | - |
| 24. Navigation Restructure & Settings | v2.0 | 0/TBD | Not started | - |
