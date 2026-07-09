# Roadmap: MyOriShop

## Overview

MyOriShop goes from empty repo to a daily-usable local inventory app in six phases. Phase 1 locks in every irreversible decision (append-only operations ledger, UUID keys, integer-cents money, UTC timestamps) inside a runnable FastAPI + HTMX skeleton. Phases 2–5 then build the operator's workflow in dependency order: catalog and instant search, goods receipts (with automated backup shipping before real data entry begins), sales with customer linking and correct profit snapshots, and the remaining stock operations with full history. Phase 6 closes the loop with period reports and CSV export, so the operator always knows stock levels and profit — the core value.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Ledger Core** - Runnable app skeleton with append-only operations ledger and sync-ready schema (completed 2026-07-08)
- [x] **Phase 2: Catalog, Dictionary & Search** - Product cards, code→name dictionary with autofill, instant search (completed 2026-07-08)
- [x] **Phase 3: Goods Receipt & Backup** - Stock intake through the ledger, automated WAL-safe backups before real data entry (completed 2026-07-09)
- [x] **Phase 4: Sales & Customers** - Sales with price override, cost snapshots, oversell warning, and customer profiles with purchase history (completed 2026-07-09)
- [ ] **Phase 5: Stock Operations & History** - Write-off, sale-linked return, stock correction, full operation history browsing
- [ ] **Phase 6: Reports & Data Export** - Period reports (sales, profit, stock, write-offs, top/stale products) and CSV export

## Phase Details

### Phase 1: Foundation & Ledger Core

**Goal**: The app runs locally in the browser on a data foundation where every stock change is an immutable ledger entry and no schema decision blocks future sync
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: FND-01, FND-02, FND-03
**Success Criteria** (what must be TRUE):

  1. Operator can start the app with run.bat and open it in the browser at localhost with no internet connection
  2. Every stock-changing operation is stored as an append-only ledger row, and current stock quantity can be recomputed from the ledger alone
  3. Every recorded operation shows who performed it and when
  4. Database inspection confirms money as integer minor units, timestamps as UTC, and UUID identifiers on all records

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Scaffold uv project + vendored htmx 2.0.10 + FAILING Wave-0 test contract (FND-01/02/03 + e2e)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Data foundation: settings/helpers/engine (PRAGMA listener), models, Alembic migration 0001 with append-only triggers + demo seed

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Vertical slice: ledger service (single write path), HTMX page + POST /ops partial, run.bat launcher, lint gate

### Phase 2: Catalog, Dictionary & Search

**Goal**: Operator can maintain the product catalog and find any product in seconds by code or name
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: CAT-01, CAT-02, CAT-03, CAT-04
**Success Criteria** (what must be TRUE):

  1. Operator can create and edit a product card with code, name, category, cost price, sale price, and catalog price, leaving optional fields empty
  2. Typing a known product code auto-fills the product name from the reference dictionary
  3. Operator finds a product by partial code or name with instant search/autocomplete results
  4. After changing a product's prices, the previous values remain visible as price history

**Plans**: 4 plans
**UI hint**: yes

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Product cards slice: migration 0002 + models + IN-01 guard + create/list at /products (CAT-01)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Edit slice: /products/{id}/edit, price_change/product_edited ops, price history table, soft delete/restore (CAT-01, CAT-04)

**Wave 3** *(blocked on Wave 2 completion; 02-03 and 02-04 run in parallel — zero file overlap)*

- [x] 02-03-PLAN.md — Instant search slice: ranked Cyrillic-safe search on name_lc, HTMX active search, <mark> highlight (CAT-03)
- [x] 02-04-PLAN.md — Dictionary slice: /dictionary CRUD + GET /dictionary/lookup autofill via 204 pattern (CAT-02)

### Phase 3: Goods Receipt & Backup

**Goal**: Operator can put stock on the shelf through the ledger, and the database is protected by automated backups before real daily data entry begins
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: RCP-01, RCP-02, BCK-01
**Success Criteria** (what must be TRUE):

  1. Operator can register a goods receipt by product code with quantity, cost price, catalog price, and sale price, and stock increases accordingly
  2. Product name auto-fills from the dictionary while entering a receipt
  3. A completed receipt appears in the operations ledger with the entered prices captured
  4. Database is backed up automatically using VACUUM INTO, and operator can restore from a backup (restore verified at least once)

**Plans**: 3 plans
**UI hint**: yes

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Receipt entry vertical slice: save-and-next form, one-transaction ledger receipt ops, auto-create, recent list, nav (RCP-01)

**Wave 2** *(blocked on Wave 1 completion; 03-02 and 03-03 run in parallel — zero file overlap)*

- [x] 03-02-PLAN.md — Lookup pre-fill + card price sync: GET /receipts/lookup (204 pattern), name+prices autofill, price_change ops on intake (RCP-02)
- [x] 03-03-PLAN.md — Backup & restore: VACUUM INTO service (AUTOCOMMIT), lifespan startup backup + retention 30, /backup page, restore.bat, restore roundtrip test (BCK-01)

### Phase 4: Sales & Customers

**Goal**: Operator can sell products — optionally to a known customer — with stock decremented, oversells warned, and profit data frozen correctly at sale time
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: SAL-01, SAL-02, SAL-03, SAL-04, SAL-05, CST-01, CST-02
**Success Criteria** (what must be TRUE):

  1. Operator can register a sale by product code with quantity; stock decreases and the sale is saved to history
  2. Operator can override the sale price on any sale line
  3. Operator can create and edit customer profiles (name, surname, consultant number) and link a sale to a customer
  4. Selling more than is in stock triggers a warning with explicit confirm-to-proceed
  5. Each sale line snapshots unit cost and sale price at sale time, and a customer's purchase history shows what, when, and at what price

**Plans**: 5 plans
**UI hint**: yes

Plans:
**Wave 1**

- [x] 04-01-PLAN.md — Schema + ledger foundation + RED test contract: Customer/Sale models, operations.sale_id, migration 0004 (native ADD COLUMN, triggers preserved), record_operation sale_id kwarg, conftest fixtures, test_sales/test_customers RED (SAL-01, SAL-05)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 04-02-PLAN.md — Sale basket happy path: register_sale (multi-line, one transaction, cost/price snapshot), lookup prefill, recent sales, /sales routes + templates + nav (SAL-01, SAL-02, SAL-05)

**Wave 3** *(blocked on Wave 2 completion; 04-03 and 04-04 run in parallel — zero file overlap)*

- [x] 04-03-PLAN.md — Oversell warn/confirm: aggregate stock check in register_sale, sale_oversell partial, «Продать всё равно» hx-vals confirm, allow-negative (SAL-04)
- [x] 04-04-PLAN.md — Customers CRUD + purchase history: customers service (Cyrillic search, frozen-price history), /customers routes + templates + nav (CST-01, CST-02)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 04-05-PLAN.md — Sale ↔ customer linking: inline picker + quick-create in the sale form, selected-customer chip, /sales/customer-search + POST /sales/customer (SAL-03)

### Phase 5: Stock Operations & History

**Goal**: Operator can handle every non-sale stock movement (write-off, return, correction) and see the complete operation trail
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: OPS-01, OPS-02, OPS-03, OPS-04
**Success Criteria** (what must be TRUE):

  1. Operator can write off stock with a reason, and stock decreases accordingly
  2. Operator can register a return linked to the original sale, and stock increases accordingly
  3. Operator can correct stock quantity, and the adjustment is recorded as an operation rather than a direct edit
  4. Operator can browse the full operation history showing what happened, when, and how much

**Plans**: 5 plans
**UI hint**: yes

Plans:
**Wave 1**

- [x] 05-01-PLAN.md — Shared foundation: WRITEOFF_REASONS + OPERATION_TYPE_LABELS constants (Jinja globals) + Wave-0 RED test contract (OPS-01..04)

**Wave 2** *(blocked on Wave 1)*

- [x] 05-02-PLAN.md — Write-off slice: /writeoff form + service on record_operation, reason allow-list, oversell warn/allow, save-and-next (OPS-01)

**Wave 3** *(blocked on Wave 2 — shares app/main.py)*

- [x] 05-03-PLAN.md — Sale-linked return slice: /returns from a sale line, returnable-qty cap, frozen price/cost copy (OPS-02)

**Wave 4** *(blocked on Wave 3 — shares app/main.py)*

- [ ] 05-04-PLAN.md — Correction slice: /corrections count/delta modes, zero-net reject, retire POST /ops (OPS-03)

**Wave 5** *(blocked on Wave 4 — shares app/main.py)*

- [ ] 05-05-PLAN.md — History slice: /history paginated + type/product filters + nav link, history_rows partial (OPS-04)

### Phase 6: Reports & Data Export

**Goal**: Operator can see sales, profit, and stock health for any period, and get all data out as CSV
**Mode:** mvp
**Depends on**: Phase 5
**Requirements**: RPT-01, RPT-02, RPT-03, RPT-04, BCK-02
**Success Criteria** (what must be TRUE):

  1. Operator can view sales and profit reports for a day, week, month, or custom period, with correct local-day boundaries
  2. Operator can view current stock levels including a low-stock items list
  3. Operator can view write-off reports for a chosen period
  4. Operator can view top-selling products and products with no sales for a long time
  5. Operator can export products, sales, and customers to CSV files

**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Ledger Core | 3/3 | Complete    | 2026-07-08 |
| 2. Catalog, Dictionary & Search | 4/4 | Complete    | 2026-07-08 |
| 3. Goods Receipt & Backup | 3/3 | Complete   | 2026-07-09 |
| 4. Sales & Customers | 6/6 | Complete   | 2026-07-09 |
| 5. Stock Operations & History | 3/5 | In Progress|  |
| 6. Reports & Data Export | 0/TBD | Not started | - |
