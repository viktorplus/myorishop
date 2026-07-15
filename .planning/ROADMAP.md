# Roadmap: MyOriShop

## Milestones

- ✅ **v1.0 MVP** — Phases 1-6 (shipped 2026-07-10)
- ✅ **v1.1 Multi-Warehouse & Batch Tracking** — Phases 7-11 (shipped 2026-07-13)
- ✅ **v1.2 Catalog Pricing UX & List Ergonomics** — Phases 12-14 (shipped 2026-07-14)
- 🚧 **v1.3 Финансы / Касса** — Phases 15-17 (in progress)

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

### 🚧 v1.3 Финансы / Касса (In Progress)

**Milestone Goal:** Ввести кассу как агрегированный учёт денежных средств — автопополнение с каждой продажи, расход с обязательным указанием назначения, история движений и баланс — в виде отдельного модуля «Финансы».

- [x] **Phase 15: Cash Ledger Foundation** - Every sale credits the till and every return debits it symmetrically; the operator sees the resulting balance in a new «Финансы» section (completed 2026-07-14)
- [x] **Phase 16: Manual Cash Movements & History** - Operator can manually withdraw (categorized) or deposit funds, with a warn-but-allow negative-balance check, and browse all movements in a paginated/filterable history (completed 2026-07-15)
- [x] **Phase 17: Financial Reports, Export & Dashboard Analytics** - Operator can view a period cash-flow report, export movements to CSV, and see gross profit, net profit, and stock valuation on the Финансы dashboard (completed 2026-07-15)

## Phase Details

### Phase 15: Cash Ledger Foundation

**Goal**: Every sale credits the till and every return debits it symmetrically, and the operator can see the resulting balance in a new «Финансы» section
**Depends on**: Phase 14 (adds a new sibling `cash_movements` ledger — distinct from the existing `operations` table, per research: cash has no `product_id`/batch invariants — wired into the existing `register_sale`/`register_return` write paths inside their current transactions; no reuse of Phase 14's list infra yet, that lands in Phase 16)
**Requirements**: FIN-01, FIN-02, FIN-06
**Success Criteria** (what must be TRUE):

  1. Operator sees a new «Финансы» nav section showing the current cash balance
  2. Registering a sale immediately increases the displayed cash balance by the sale's total amount
  3. Registering a return against that sale immediately decreases the balance by the same amount, restoring it to the pre-sale value**Plans**: 4 plans

**Wave 1**

- [x] 15-01-PLAN.md — Cash ledger schema: CashMovement model + append-only triggers (db.py + migration 0013)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 15-02-PLAN.md — finance.py single write path + live-SUM compute_balance

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 15-03-PLAN.md — Auto-credit on sale + atomic auto-debit on return

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 15-04-PLAN.md — «Финансы» section: routes, «Баланс кассы» pages, desktop nav + mobile tile

**UI hint**: yes

### Phase 16: Manual Cash Movements & History

**Goal**: Operator can manually adjust the till — withdrawals with a mandatory category, deposits for opening balance/correction — and review every movement, automatic and manual, in one paginated/filterable history
**Depends on**: Phase 15 (extends the `cash_movements` ledger and the Финансы section with a manual-entry write path and a read view over all entries, both auto and manual)
**Requirements**: FIN-03, FIN-04, FIN-05, FIN-07
**Success Criteria** (what must be TRUE):

  1. Operator can withdraw funds from the till by selecting a mandatory category (оплата поставщику / зарплата / аренда / коммунальные / прочее) and entering a comment; the balance decreases accordingly
  2. Operator can manually add funds (opening balance or correction) with a comment; the balance increases accordingly
  3. Withdrawing an amount that would take the balance negative shows a warning but still lets the operator confirm and proceed, matching the existing oversell/min-price warn-but-allow pattern
  4. Operator can browse a paginated, filterable history of every cash movement — sale credits, return debits, and manual entries — on the Финансы page

**Plans**: 4 plans

**Wave 1**

- [x] 16-01-PLAN.md — Extend CASH_CATEGORIES (7 manual keys) + CASH_BUCKETS/CASH_BUCKET_LABELS + Jinja globals

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 16-02-PLAN.md — finance.record_manual_movement (sign/validate/comment/negative-gate) + cash_history_view read service

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 16-03-PLAN.md — Desktop «Финансы»: shared withdraw/deposit forms, POST routes, negative-balance warn, numbered history

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 16-04-PLAN.md — Mobile «Финансы»: reuse shared forms, cards + «Показать ещё» history parity

**UI hint**: yes

### Phase 17: Financial Reports, Export & Dashboard Analytics

**Goal**: Operator can analyze cash flow and overall profitability for any period, export cash movements to CSV, and see the till's business-health metrics (profit, stock value) on the Финансы dashboard
**Depends on**: Phase 16 (net profit needs manual expense movements from Phase 16 to subtract; the period report and CSV export reuse the full movement set plus the existing period-filter/CSV-export conventions from Phase 6. FIN-10/11/12 (profit, stock valuation) are grouped here rather than with Phase 16's manual-movement UI because they are read-only period/point-in-time aggregation queries — reusing `sales_profit_report` and extending the existing stock-report shape — the same nature as FIN-08's cash-flow report and FIN-09's export, not the write-path/form work of Phase 16)
**Requirements**: FIN-08, FIN-09, FIN-10, FIN-11, FIN-12
**Success Criteria** (what must be TRUE):

  1. Operator can view a report of cash movements for a chosen period, broken down by income (sales) vs. expense category
  2. Operator can export a period's cash movements to CSV, opening correctly in Excel via the same BOM/semicolon/formula-escape convention as the existing exports
  3. The Финансы dashboard shows gross profit for the selected period (sale price minus purchase cost across sales, reusing `sales_profit_report`)
  4. The Финансы dashboard shows net profit for the same period (gross profit minus cash expenses recorded in that period)
  5. The Финансы dashboard shows the total value of stock currently on hand, both at purchase cost and at sale price

**Plans**: 5 plans

**Wave 1**

- [x] 17-01-PLAN.md — Read-only aggregation services (cash_expense_total, stock_valuation, cash_flow_report) + period-scoped cash-movements CSV export

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 17-02-PLAN.md — Desktop «Финансы» dashboard tiles (gross/net/stock) + /finance/metrics + light period selector

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 17-03-PLAN.md — Desktop /finance/report cash-flow report page + /finance/report.csv download

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 17-04-PLAN.md — Mobile parity: /m/finance tiles + /m/finance/report + CSV (shared partials via finance_base)

**Wave 5** *(gap closure — UAT Test 2)*

- [ ] 17-05-PLAN.md — Navigation entry points to /finance/report and /m/finance/report (desktop top-nav item + mobile home tile + button-styled dashboard links)

**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15 → 16 → 17

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
| 17. Financial Reports, Export & Dashboard Analytics | v1.3 | 4/4 | Complete   | 2026-07-15 |
