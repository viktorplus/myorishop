# Requirements — MyOriShop v1

## v1 Requirements

### Foundation

- [x] **FND-01**: All stock changes are recorded in an append-only operations ledger (receipt, sale, write-off, return, correction); stock quantity is derived from it
- [x] **FND-02**: All money values are stored as integer minor units (cents); all timestamps in UTC; all records use UUID identifiers
- [x] **FND-03**: Every operation records who performed it and when (audit trail)

### Catalog

- [ ] **CAT-01**: User can create and edit product cards: code, name, category, cost price, sale price, current catalog price (most fields optional)
- [ ] **CAT-02**: User can maintain a reference dictionary (product code → name) that auto-fills the name when entering a code
- [ ] **CAT-03**: User can find a product by code or name with instant search/autocomplete
- [ ] **CAT-04**: Price changes on a product are kept as history (previous values not lost)

### Receipt

- [ ] **RCP-01**: User can register a goods receipt by product code with quantity, cost price, catalog price, and sale price; stock increases accordingly
- [ ] **RCP-02**: Product name auto-fills from the dictionary during receipt entry

### Sales

- [ ] **SAL-01**: User can register a sale by product code with quantity; stock decreases and the sale is saved to history
- [ ] **SAL-02**: Sale price can differ from the standard price per sale line
- [ ] **SAL-03**: A sale can optionally be linked to a customer (name, surname, consultant number)
- [ ] **SAL-04**: User is warned when selling more than is in stock
- [ ] **SAL-05**: Each sale line snapshots unit cost and sale price at the moment of sale (profit reports stay correct after price changes)

### Operations

- [ ] **OPS-01**: User can write off stock with a reason
- [ ] **OPS-02**: User can register a return linked to the original sale; stock increases accordingly
- [ ] **OPS-03**: User can correct stock quantity (adjustment recorded as an operation, not a direct edit)
- [ ] **OPS-04**: User can view the full operation history (what, when, how much)

### Customers

- [ ] **CST-01**: User can create and edit customer profiles (name, surname, consultant number)
- [ ] **CST-02**: User can view a customer's purchase history: what, when, at what price

### Reports

- [ ] **RPT-01**: User can view sales and profit reports for a day, week, month, or custom period
- [ ] **RPT-02**: User can view current stock levels and low-stock items
- [ ] **RPT-03**: User can view write-off reports for a period
- [ ] **RPT-04**: User can view top-selling products and products with no sales for a long time

### Backup

- [ ] **BCK-01**: Database is backed up automatically using a WAL-safe method (VACUUM INTO); user can restore from a backup
- [ ] **BCK-02**: User can export data (products, sales, customers) to CSV

## v2 Requirements

- **CST-V2-01**: Purchase-frequency analysis and "customer may be running low" reminders (needs months of sales history)
- **CST-V2-02**: On goods receipt, show customers likely interested in the product based on purchase history
- **SYNC-V2-01**: Multi-operator sync via central server (PostgreSQL) with conflict resolution over the operations ledger
- **AUTH-V2-01**: User roles (administrator, operator, report viewer)
- **CUR-V2-01**: Multi-currency support

## Out of Scope

- Barcodes — no scanner hardware; code entry is fast enough for one operator
- FIFO batch costing — average/snapshot cost is sufficient for v1 profit reports
- Excel import of initial data — user starts from scratch (user decision)
- Invoicing/payments, notifications, Oriflame campaign catalog integration — not needed for core value
- Direct editing of stock quantity — breaks the ledger; corrections go through OPS-03
- CRDT/sync frameworks in v1 — sync-readiness is achieved via ledger + UUIDs + UTC only

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FND-01 | Phase 1 | Complete |
| FND-02 | Phase 1 | Complete |
| FND-03 | Phase 1 | Complete |
| CAT-01 | Phase 2 | Pending |
| CAT-02 | Phase 2 | Pending |
| CAT-03 | Phase 2 | Pending |
| CAT-04 | Phase 2 | Pending |
| RCP-01 | Phase 3 | Pending |
| RCP-02 | Phase 3 | Pending |
| BCK-01 | Phase 3 | Pending |
| SAL-01 | Phase 4 | Pending |
| SAL-02 | Phase 4 | Pending |
| SAL-03 | Phase 4 | Pending |
| SAL-04 | Phase 4 | Pending |
| SAL-05 | Phase 4 | Pending |
| CST-01 | Phase 4 | Pending |
| CST-02 | Phase 4 | Pending |
| OPS-01 | Phase 5 | Pending |
| OPS-02 | Phase 5 | Pending |
| OPS-03 | Phase 5 | Pending |
| OPS-04 | Phase 5 | Pending |
| RPT-01 | Phase 6 | Pending |
| RPT-02 | Phase 6 | Pending |
| RPT-03 | Phase 6 | Pending |
| RPT-04 | Phase 6 | Pending |
| BCK-02 | Phase 6 | Pending |

**Coverage: 26/26 v1 requirements mapped — no orphans, no duplicates.**
