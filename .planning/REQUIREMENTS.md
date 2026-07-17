# Requirements: MyOriShop — UX Overhaul & Navigation Restructure (v2.0)

**Defined:** 2026-07-15
**Core Value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

## v1 Requirements

Requirements for milestone v2.0. Each maps to roadmap phases.

### Navigation Restructure

- [ ] **NAV-01**: Operator reaches goods receipt (Приход) as a nested action from the Товары page, not a top-level nav item
- [ ] **NAV-02**: Operator reaches write-off (Списание) as a nested action from the Товары page, not a top-level nav item
- [ ] **NAV-03**: Operator reaches the reference dictionary (Справочник) from a secondary menu on the Товары page
- [ ] **NAV-04**: Operator reaches CSV export (Экспорт) from the Резервные копии page
- [ ] **NAV-05**: Operator reaches Склады from a secondary menu on a new Настройки page
- [ ] **NAV-06**: Operator reaches Резервные копии from a secondary menu on the Настройки page
- [ ] **NAV-07**: Operator reaches stock transfer (Перемещение) as a nested action from the product context (Товар)
- [ ] **NAV-08**: Top-level nav is reduced to the pages that remain first-class (Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы, Настройки)

### Dashboard

- [ ] **DASH-01**: Home page shows the current date, weekday, and time
- [ ] **DASH-02**: Home page shows the active catalog number and days remaining until it closes
- [ ] **DASH-03**: Home page shows revenue/profit/expense totals for today, the current week, and the current month
- [ ] **DASH-04**: Home page shows the total distinct product codes in stock and their combined valuation
- [ ] **DASH-05**: Home page shows a recent-operations feed with columns adapted per operation type (type, code, name, expiry, quantity, cost, profit, customer)

### Product Pricing & List

- [x] **PROD-01**: The "Добавить товар" button is removed from the product list (goods receipt already creates new products)
- [x] **PROD-02**: Product-list delete action is a text link, not a button
- [x] **PROD-03**: Product list groups rows by product code, showing the total quantity summed across all of that code's batches
- [x] **PROD-04**: Within a grouped code, individual batches remain visible with their own expiry date and batch name
- [ ] **PROD-05**: Product pricing is reduced to exactly two fields — ДЦ (cost/distributor price) and ПЦ (sale/catalog price); every other product price field is removed or consolidated into one of these two. Explicitly exempt: `Product.min_sale_cents` — it is a guardrail threshold (like the low-stock threshold), not a price the operator reads off the card, and the Phase 7 below-minimum sale warning (PRICE-01, shipped v1.1) must keep working unchanged (operator decision, 2026-07-15)
- [x] **PROD-06**: Entering a ДЦ or ПЦ that differs from the dictionary's reference price — at any entry point (product card, dictionary, receipt, sale) — shows a color cue: below reference = yellow, above reference = blue
- [ ] **PROD-07**: ДЦ/ПЦ can be edited at any stage — product card, dictionary, goods receipt, or sale — and the change is saved from wherever it was made
- [x] **PROD-08**: Product list shows each product's category and can be filtered by category

### Warehouses

- [ ] **WH-01**: Warehouse list shows the current item count and the date of the last goods receipt for each warehouse
- [ ] **WH-02**: Add/edit/delete warehouse are reached via links that open a dedicated form (add form, or pick-a-warehouse-then-edit/delete flow)
- [ ] **WH-03**: A warehouse can only be deleted while it holds zero stock

### Transfers

- [x] **XFER-01**: Transferring part of a batch whose moved portion has a different expiry date or condition (e.g. damaged packaging, opened sample) from the remaining source batch creates a new destination batch and moves only that portion into it, leaving the source batch's remaining quantity and attributes unchanged

### Sales

- [ ] **SALE-01**: Sale form is a code / name / quantity / sale-price table
- [ ] **SALE-02**: Sale form shows a live running total (amount and unit count) directly under the table, updating as lines are filled in
- [x] **SALE-03**: Operator selects new / existing / anonymous customer via a radio control at the top of the sale form
- [x] **SALE-04**: Selecting an existing customer offers autocomplete by consultant number, name, or surname; picking a match auto-fills the other identifying fields and hides the rest of the profile
- [x] **SALE-05**: Selecting a new customer shows a form with optional profile fields to fill in inline
- [x] **SALE-06**: Selecting anonymous records the sale against the existing anonymous/walk-in customer profile with no extra fields shown
- [ ] **SALE-07**: Recent-sales list shows the customer's name (first + last) for each sale

### Customers

- [x] **CUST-01**: Customer profile supports multiple phone numbers
- [x] **CUST-02**: Customer profile supports multiple Telegram handles
- [x] **CUST-03**: Customer profile supports multiple email addresses
- [x] **CUST-04**: Customer profile supports other social-network profile links (free-form, multiple)
- [x] **CUST-05**: Customer profile supports a physical address field
- [x] **CUST-06**: Customer profile shows the date of the customer's most recent order
- [x] **CUST-07**: Customer profile shows the customer's spend totals for the last month, quarter, and year
- [x] **CUST-08**: Customer profile shows the customer's favorite products, ranked by purchase frequency and quantity

### History

- [ ] **HIST-01**: History page has a nested menu to select an operation type first, then shows that type's relevant columns only
- [ ] **HIST-02**: History supports filtering by product code, date range, customer, and category
- [ ] **HIST-03**: History supports sorting by its relevant columns
- [ ] **HIST-04**: History results are paginated

### Reports

- [ ] **RPT-01**: Every report detail page has a "Назад к отчётам" link back to /reports

### Mobile

- [ ] **MOB-01**: Mobile navigation includes the same main tabs as desktop (Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы), excluding Настройки

## v2 Requirements

Deferred to future release. Not in current roadmap.

- **DASH-V2-01**: Configurable/dismissible dashboard tiles (choose which metrics show)
- **CUST-V2-01**: Automated "running low" purchase-frequency reminders (already tracked in PROJECT.md Future section, unrelated to this milestone's profile/stats work)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| New backend data model for social/contact fields beyond free-text lists | A structured multi-provider contacts schema (validated phone/email formats, provider-specific fields) is unnecessary complexity for a single-operator local tool — plain repeatable text fields suffice |
| Real-time/automatic catalog-close date source | No external Oriflame API exists; catalog number and close date stay operator-entered/configured, same as the existing `Catalog` mechanism |
| Configurable dashboard layout | Fixed dashboard layout ships in v2.0; customization deferred to v2 backlog (DASH-V2-01) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROD-05 | Phase 18 | Pending |
| PROD-06 | Phase 18 | Complete |
| PROD-07 | Phase 18 | Pending |
| PROD-01 | Phase 19 | Complete |
| PROD-02 | Phase 19 | Complete |
| PROD-03 | Phase 19 | Complete |
| PROD-04 | Phase 19 | Complete |
| PROD-08 | Phase 19 | Complete |
| WH-01 | Phase 20 | Pending |
| WH-02 | Phase 20 | Pending |
| WH-03 | Phase 20 | Pending |
| XFER-01 | Phase 20 | Complete |
| CUST-01 | Phase 21 | Complete |
| CUST-02 | Phase 21 | Complete |
| CUST-03 | Phase 21 | Complete |
| CUST-04 | Phase 21 | Complete |
| CUST-05 | Phase 21 | Complete |
| CUST-06 | Phase 21 | Complete |
| CUST-07 | Phase 21 | Complete |
| CUST-08 | Phase 21 | Complete |
| SALE-01 | Phase 22 | Pending |
| SALE-02 | Phase 22 | Pending |
| SALE-03 | Phase 22 | Complete |
| SALE-04 | Phase 22 | Complete |
| SALE-05 | Phase 22 | Complete |
| SALE-06 | Phase 22 | Complete |
| SALE-07 | Phase 22 | Pending |
| DASH-01 | Phase 23 | Pending |
| DASH-02 | Phase 23 | Pending |
| DASH-03 | Phase 23 | Pending |
| DASH-04 | Phase 23 | Pending |
| DASH-05 | Phase 23 | Pending |
| HIST-01 | Phase 23 | Pending |
| HIST-02 | Phase 23 | Pending |
| HIST-03 | Phase 23 | Pending |
| HIST-04 | Phase 23 | Pending |
| NAV-01 | Phase 24 | Pending |
| NAV-02 | Phase 24 | Pending |
| NAV-03 | Phase 24 | Pending |
| NAV-04 | Phase 24 | Pending |
| NAV-05 | Phase 24 | Pending |
| NAV-06 | Phase 24 | Pending |
| NAV-07 | Phase 24 | Pending |
| NAV-08 | Phase 24 | Pending |
| RPT-01 | Phase 24 | Pending |
| MOB-01 | Phase 24 | Pending |

**Coverage:**
- v1 requirements: 46 total (count corrected from 45 during roadmap creation — the original tally under-counted by one; all requirement IDs are unchanged)
- Mapped to phases: 46 ✓
- Unmapped: 0 ✓
- Duplicated across phases: 0 ✓

**By phase:**

| Phase | Requirements | Count |
|-------|--------------|-------|
| 18. Two-Price Model Consolidation (ДЦ/ПЦ) | PROD-05, PROD-06, PROD-07 | 3 |
| 19. Products Page Rebuild | PROD-01..04, PROD-08 | 5 |
| 20. Warehouses & Batch-Split Transfers | WH-01..03, XFER-01 | 4 |
| 21. Customer Profiles & Purchase Insights | CUST-01..08 | 8 |
| 22. Sales Page Rebuild | SALE-01..07 | 7 |
| 23. Dashboard & History Rebuild | DASH-01..05, HIST-01..04 | 9 |
| 24. Navigation Restructure & Settings | NAV-01..08, RPT-01, MOB-01 | 10 |

---
*Requirements defined: 2026-07-15*
*Last updated: 2026-07-15 — traceability mapped to Phases 18-24 during roadmap creation; total count corrected 45 → 46*
