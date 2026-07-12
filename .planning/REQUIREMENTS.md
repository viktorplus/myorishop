# Requirements: MyOriShop — Oriflame Warehouse Inventory

**Defined:** 2026-07-10
**Core Value:** The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

## v1.1 Requirements

Requirements for the "Multi-Warehouse & Batch Tracking" milestone. Each maps to roadmap phases.

### Warehouses & Locations

- [x] **WH-01**: User can create and manage multiple warehouses
- [x] **WH-02**: Stock item has an optional free-text storage location tag within its warehouse (e.g. "стеллаж А3")
- [ ] **WH-03**: User can transfer stock (a batch or part of it) from one warehouse to another without losing cost/price history

### Categories

- [x] **CAT-01**: "Товары на складе" page groups products by category/rubric

### Batches & Lots

- [x] **LOT-01**: A product code can have multiple batches (lots), each with its own expiry date and price
- [x] **LOT-02**: At sale, operator sees a list of matching batches (price, expiry, remaining quantity, comment) and manually selects one
- [x] **LOT-03**: Optional expiry date field per batch
- [x] **LOT-04**: Optional free-text comment per batch, shown in the sale-time batch picker
- [x] **LOT-05**: Write-off, return, and stock correction also require selecting the specific batch, not just the product
- [ ] **LOT-06**: Report of batches with an approaching or passed expiry date

### Pricing Guardrails

- [x] **PRICE-01**: Optional minimum sale price per product — selling below it shows a warning but allows override (same pattern as the existing oversell warning)

### UI

- [ ] **UI-01**: A dedicated mobile flow — simpler, single-purpose screens/steps for core operations (search, receipts, sales, write-offs/returns/corrections, history) — rather than adapting the same dense desktop pages via CSS alone; the existing desktop layout stays unchanged

## v2 Requirements

Deferred to a future release (v2.0). Tracked but not in the current roadmap.

### Sync & Multi-User

- **SYNC-V2-01**: Multi-operator sync across countries via a central server, with both server-based sync (when online) and USB flash-drive sync (when offline) in the same milestone
- **CUR-V2-01**: Multi-currency support
- **AUTH-V2-01**: User roles: administrator, operator, report viewer

### Customer Intelligence

- **CST-V2-01**: Customer purchase-frequency analysis and "running low" reminders — needs months of sales history
- **CST-V2-02**: On goods receipt, show customers likely interested in the product based on purchase history

### Export

- **EXP-V2-01**: CSV export includes warehouse/batch columns

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Barcodes | No scanner hardware; code entry is fast enough for one operator |
| Oriflame campaign catalog integration | Not needed for core value |
| Automatic FEFO/FIFO batch selection | v1.1 introduces batches (LOT-01..06) but selection stays manual — operator picks the batch |
| Invoicing/payments, notifications | Not needed for core value |
| Excel/CSV import of initial data | No existing data; everything entered manually from scratch (user decision) |
| CSV export with warehouse/batch columns | Existing product/sale/customer-level export stays unchanged this milestone (EXP-V2-01) |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WH-01 | Phase 8 | Complete |
| WH-02 | Phase 9 | Complete |
| WH-03 | Phase 10 | Pending |
| CAT-01 | Phase 7 | Complete |
| LOT-01 | Phase 9 | Complete |
| LOT-02 | Phase 9 | Complete |
| LOT-03 | Phase 9 | Complete |
| LOT-04 | Phase 9 | Complete |
| LOT-05 | Phase 9 | Complete |
| LOT-06 | Phase 10 | Pending |
| PRICE-01 | Phase 7 | Complete |
| UI-01 | Phase 11 | Pending |

**Coverage:**

- v1.1 requirements: 12 total
- Mapped to phases: 12 (roadmap revised 2026-07-10, Phases 7-11)
- Unmapped: 0 ✓

**Revision note (2026-07-10):** UI-01's phase mapping moved from Phase 8 to Phase 11. The mobile flow requirement was reinterpreted as a dedicated single-purpose screen set (not a CSS adaptation of desktop pages) and re-sequenced to the end of the milestone so it is built once, as a self-contained phase, against the complete final v1.1 operation set (including the batch picker, warehouse transfer, and expiry report introduced by Phases 8-10) — see ROADMAP.md Phase 11 for full rationale. Phases 7, 9 (formerly 10), and 10 (formerly 11) are unchanged in scope; only their numbers and cross-references shifted.

---
*Requirements defined: 2026-07-10*
*Last updated: 2026-07-10 after v1.1 roadmap revision (Phases 7-11, Mobile Flow moved to Phase 11)*
