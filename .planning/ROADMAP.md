# Roadmap: MyOriShop

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-07-10)
- ✅ **v1.1 Multi-Warehouse & Batch Tracking** — Phases 7-11 (shipped 2026-07-13)
- 🚧 **v1.2 Catalog Pricing UX & List Ergonomics** — Phases 12-14 (in progress)

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

### 🚧 v1.2 Catalog Pricing UX & List Ergonomics (In Progress)

**Milestone Goal:** Finish the ad-hoc catalog/pricing feature (extend autofill to goods receipt, add name autofill), close the mobile wizard context gaps found on audit, add code/name cross-autofill and pagination/filter/sort to sales and every list page, and add quick-delete to warehouse/product lists.

- [x] **Phase 12: Code & Name Autofill** - Typing a product code on the product-add, goods-receipt, or sales forms surfaces known catalog price/consultant price/name suggestions (completed 2026-07-13)
- [ ] **Phase 13: Mobile Wizard Context & Navigation** - Mobile wizards keep the operator oriented (visible code/name/warehouse, consistent Назад, step indicator, quick actions)
- [ ] **Phase 14: List Pagination, Filtering, Sorting & Quick Delete** - Every list page supports paging/filtering/sorting, with quick delete for warehouses and products

## Phase Details

### Phase 12: Code & Name Autofill

**Goal**: Wherever the operator types a product code — on the product-add form, goods receipt, or the sales page — the system surfaces known price/name data instead of requiring a manual lookup
**Depends on**: Phase 11 (extends the shipped ad-hoc `feat/catalogs-pricing` pricing-lookup service — `app/services/pricing.py`, `app/services/catalogs.py` — onto the product-add form and goods receipt, and formalizes it as a permanent feature; no new schema)
**Requirements**: PRICE-02, PRICE-03, PRICE-04, SAL-06
**Success Criteria** (what must be TRUE):

  1. On the product-add form, typing a code suggests catalog price and consultant (cost) price from imported catalog data, and the operator can accept the suggestion or override it
  2. On the product-add form, typing a code suggests the product name from the dictionary, and the operator can accept or override it
  3. On goods receipt (desktop and mobile), typing a code not yet in the product catalog suggests catalog price, consultant price, and name from imported catalog/dictionary data, all overridable by the operator
  4. On the sales page, typing a product code shows its name inline, and typing part of a product name shows a dropdown of matching codes to pick from

**Plans**: 4 plans

Plans:
**Wave 1**

- [x] 12-01-PLAN.md — Desktop receipt catalog-source autofill (PRICE-04) + PRICE-02/PRICE-03 formalization
- [x] 12-03-PLAN.md — Sales name-fragment to code dropdown (SAL-06)
- [x] 12-04-PLAN.md — Mobile sales & mobile transfers visible-name fixes (SAL-06 / D-13, D-14)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 12-02-PLAN.md — Mobile receipt price forwarding + visible code/name readout (PRICE-04)

**UI hint**: yes

### Phase 13: Mobile Wizard Context & Navigation

**Goal**: Operators using the mobile sale/receipt/write-off/correction/transfer wizards always know what they're working on, can navigate back reliably, and can jump straight into a wizard from search results
**Depends on**: Phase 11 (fixes context/navigation gaps found on audit of the mobile wizards shipped there — `app/templates/mobile_partials/*.html`, `app/routes/mobile_*.py`)
**Requirements**: UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):

  1. Every intermediate step of the sale, receipt, write-off, correction, and transfer mobile wizards displays the product code, name, and warehouse as visible on-screen text, not only as hidden form fields
  2. Every mobile wizard's "Назад" button uses the same explicit `hx-get`/`hx-post` step navigation pattern; the write-off wizard no longer relies on `history.back()`
  3. The mobile sale basket/review screen shows a step indicator consistent with the rest of the sale wizard
  4. From the mobile search product-detail screen, the operator can tap "Продать" or "Принять" to jump directly into the sale or receipt wizard for that product

**Plans**: 5 plans

Plans:
**Wave 1**

- [x] 13-01-PLAN.md — Corrections wizard visible context + Назад consistency + shared header partial
- [ ] 13-03-PLAN.md — Receipts wizard step-2 Назад fix + /m/receipts code prefill
- [x] 13-04-PLAN.md — Transfers wizard step-2 Назад fix
- [x] 13-05-PLAN.md — Sale basket step indicator + search quick actions + /m/sales code prefill

**Wave 2** *(depends on 13-01 for the shared `_wizard_header.html` partial)*

- [ ] 13-02-PLAN.md — Write-off wizard migration to persistent-shell architecture

**UI hint**: yes

### Phase 14: List Pagination, Filtering, Sorting & Quick Delete

**Goal**: Every list page in the app lets the operator page through, filter, and sort results instead of scrolling one unbounded table, and warehouses/products can be removed straight from their list
**Depends on**: Phase 11 (applies uniformly across every list page shipped through v1.0/v1.1 — products, warehouses, customers, dictionary, history — plus the ad-hoc catalogs list; cross-cutting infrastructure, sequenced last)
**Requirements**: LIST-01, LIST-02, LIST-03, LIST-04, LIST-05
**Success Criteria** (what must be TRUE):

  1. Every list page (products, warehouses, customers, dictionary, catalogs, history) shows results a page at a time instead of one long unbounded list
  2. Every list page lets the operator filter rows by its relevant columns
  3. Every list page lets the operator sort rows by its relevant columns
  4. Operator can delete a warehouse directly from the warehouse list without opening its detail/edit page
  5. Operator can delete a product directly from the product list without opening its detail/edit page

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14

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
| 13. Mobile Wizard Context & Navigation | v1.2 | 3/5 | In Progress|  |
| 14. List Pagination, Filtering, Sorting & Quick Delete | v1.2 | 0/TBD | Not started | - |
