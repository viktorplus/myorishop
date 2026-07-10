---
phase: 06-reports-data-export
fixed_at: 2026-07-10T15:42:35Z
review_path: .planning/phases/06-reports-data-export/06-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-07-10T15:42:35Z
**Source review:** .planning/phases/06-reports-data-export/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (1 critical, 4 warning; Info findings excluded by fix_scope)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: `consultant_number` is exported to CSV without formula-injection escaping

**Files modified:** `app/services/export.py`
**Commit:** 0278925
**Applied fix:** `stream_customers_csv` now routes `customer.consultant_number` through
`_csv_safe(customer.consultant_number or "")`, matching the escaping already applied
to `customer.name`/`customer.surname` and restoring the module's documented
"any free-text value" contract.

### WR-01: `products.csv` full dump cannot distinguish active from soft-deleted rows

**Files modified:** `app/services/export.py`, `tests/test_export.py`
**Commit:** 405db93
**Applied fix:** Added a trailing "Удалён" column to `stream_products_csv`'s header
and rows (`"Да" if product.deleted_at else ""`), so a soft-deleted product sharing
a `code` with an active one is now distinguishable in the exported CSV. Updated
`test_products_csv_roundtrip`'s header assertion to the new 8-column shape (existing
test would otherwise fail against the new column).

### WR-02: `/export/sales.csv` and `/export/customers.csv` have no content-level test coverage

**Files modified:** `tests/test_export.py`
**Commit:** 3e539d6
**Applied fix:** Added `test_sales_csv_roundtrip` (creates a `Sale` header + linked
`sale` operation with a formula-injection-prefixed customer name and asserts the
exported row, including the escaped buyer field) and `test_customers_csv_roundtrip`
(creates a customer with a `=cmd|'/C calc'!A0`-style `consultant_number` and asserts
it comes out apostrophe-escaped in `customers.csv`, pinning the CR-01 fix).

### WR-03: No upper-bound validation on `low_stock_threshold` / `stale_days`

**Files modified:** `app/services/catalog.py`, `tests/test_catalog.py`
**Commit:** 7e981cb
**Applied fix:** `parse_optional_int` now rejects any digit string whose integer
value exceeds `2_147_483_647` (int32 max), returning the existing `THRESHOLD_ERROR`
instead of silently accepting an oversized value that would overflow a future
PostgreSQL 4-byte `INTEGER` column. Added
`test_create_product_rejects_threshold_above_int32_bound` (submits `2147483648`,
one past the bound) to pin the new rejection.

### WR-04: Money fields accept negative values with no validation

**Files modified:** `app/services/catalog.py`, `tests/test_catalog.py`
**Commit:** 77fcbdf
**Applied fix:** `parse_optional_cents` now rejects any successfully-parsed value
that is negative, setting the existing `PRICE_ERROR` message instead of storing a
negative `*_cents` value. Scoped to `parse_optional_cents` only (not `to_cents`
itself), preserving the existing `to_cents("-12,505") == -1251` unit test in
`test_core.py` that pins `to_cents`'s own sign-agnostic parsing contract. Added
`test_create_product_rejects_negative_price` (submits `cost_raw="-12,50"`) to pin
the new rejection.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-10T15:42:35Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
