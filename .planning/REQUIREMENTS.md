# Requirements: MyOriShop — v1.2 Catalog Pricing UX & List Ergonomics

**Defined:** 2026-07-13
**Core Value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

## v1 Requirements

Requirements for milestone v1.2. Each maps to roadmap phases.

### Pricing Autofill

- [ ] **PRICE-02**: On the product-add form, typing a code suggests catalog price and consultant (cost) price from imported catalog data; operator can accept or override (formalize existing ad-hoc `feat/catalogs-pricing` behavior)
- [ ] **PRICE-03**: On the product-add form, typing a code suggests the product name from the dictionary; operator can accept or override
- [ ] **PRICE-04**: On goods receipt (desktop and mobile), typing a code not yet in the product catalog suggests catalog price, consultant price, and name from imported catalog/dictionary data; operator can accept or override

### Mobile Wizard UX

- [ ] **UI-02**: Every intermediate step of the sale, receipt, write-off, correction, and transfer mobile wizards displays the product code, name, and warehouse in visible text (not just hidden inputs)
- [ ] **UI-03**: All mobile wizards use the same explicit `hx-get`/`hx-post` "Назад" navigation pattern; the write-off wizard's `history.back()` steps are fixed to match
- [ ] **UI-04**: The mobile sale basket/review screen shows a step indicator consistent with the rest of the sale wizard
- [ ] **UI-05**: Mobile search product-detail screen offers quick "Продать" / "Принять" actions that jump directly into the sale/receipt wizard for that product

### Sales Autocomplete

- [ ] **SAL-06**: On the sales page, typing a product code shows its name inline; typing part of a product name shows a dropdown of matching codes to pick from

### List Ergonomics

- [ ] **LIST-01**: Every list page (products, warehouses, customers, dictionary, catalogs, history, and any others) supports pagination
- [ ] **LIST-02**: Every list page supports filtering on its relevant columns
- [ ] **LIST-03**: Every list page supports sorting on its relevant columns
- [ ] **LIST-04**: Operator can delete a warehouse directly from the warehouse list without opening its detail/edit page
- [ ] **LIST-05**: Operator can delete a product directly from the product list without opening its detail/edit page

## v2 Requirements

Deferred to v2.0. Tracked but not in current roadmap.

### Sync & Multi-Currency

- **SYNC-V2-01**: Multi-operator sync across countries via a central server, server-based (online) + USB flash-drive (offline)
- **CUR-V2-01**: Multi-currency support
- **AUTH-V2-01**: User roles: administrator, operator, report viewer

### Customer Intelligence

- **CST-V2-01**: Customer purchase-frequency analysis and "running low" reminders
- **CST-V2-02**: On goods receipt, show customers likely interested in the product based on purchase history

### Export & Mobile Parity

- **EXP-V2-01**: CSV export includes warehouse/batch columns
- **UI-V2-02**: Mobile CRUD parity for warehouses, products/catalog, customers, dictionary, and full reports (deferred from v1.2 mobile audit)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Full mobile CRUD for warehouses/products/customers/dictionary/reports | Large separate build (a CRUD screen set per section); v1.2 only fixes context/navigation gaps in existing mobile wizards — see UI-V2-02 |
| Barcodes | No scanner hardware; code entry is fast enough for one operator |
| Automatic FEFO/FIFO batch selection | v1.1 introduced batches but selection stays manual (operator picks the batch) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PRICE-02 | TBD | Pending |
| PRICE-03 | TBD | Pending |
| PRICE-04 | TBD | Pending |
| UI-02 | TBD | Pending |
| UI-03 | TBD | Pending |
| UI-04 | TBD | Pending |
| UI-05 | TBD | Pending |
| SAL-06 | TBD | Pending |
| LIST-01 | TBD | Pending |
| LIST-02 | TBD | Pending |
| LIST-03 | TBD | Pending |
| LIST-04 | TBD | Pending |
| LIST-05 | TBD | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 0 (roadmap not yet created)
- Unmapped: 13 ⚠️ (resolved by roadmapper)

---
*Requirements defined: 2026-07-13*
*Last updated: 2026-07-13 after milestone v1.2 definition*
