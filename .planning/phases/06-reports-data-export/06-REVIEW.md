---
phase: 06-reports-data-export
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 28
files_reviewed_list:
  - alembic/versions/0005_product_thresholds.py
  - app/config.py
  - app/core.py
  - app/main.py
  - app/models.py
  - app/routes/export.py
  - app/routes/products.py
  - app/routes/reports.py
  - app/services/catalog.py
  - app/services/export.py
  - app/services/reports.py
  - app/services/stock.py
  - app/static/style.css
  - app/templates/base.html
  - app/templates/pages/export.html
  - app/templates/pages/product_form.html
  - app/templates/pages/reports_landing.html
  - app/templates/pages/reports_products.html
  - app/templates/pages/reports_sales.html
  - app/templates/pages/reports_stock.html
  - app/templates/pages/reports_writeoffs.html
  - app/templates/partials/period_filter.html
  - app/templates/partials/sales_report_results.html
  - app/templates/partials/top_selling_rows.html
  - app/templates/partials/writeoffs_report_rows.html
  - tests/test_catalog.py
  - tests/test_core.py
  - tests/test_export.py
  - tests/test_reports.py
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-07-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 28
**Status:** issues_found

## Summary

Reviewed the Phase 6 reports + CSV data-export slice: `app/services/reports.py`
(sales/profit, write-offs, top-selling, stale-products), `app/services/stock.py`
(low-stock), `app/services/export.py` (3 CSV dumps), the new
`low_stock_threshold`/`stale_days` per-product columns and their catalog/form
wiring, and the associated routes/templates/tests.

The period-boundary math (`local_day_bounds_utc`'s half-open `[start, end)`
contract), the `is not None` threshold-fallback discipline (Pitfall 3, applied
consistently in both `stock.py` and `reports.py`), and the null-cost-safe
profit aggregation (Pitfall 2) are all correctly implemented and well covered
by tests — no bugs found in that core logic.

However, the CSV export module has a real formula-injection gap: one
free-text customer field bypasses the module's own `_csv_safe` escaping,
which the module's docstring explicitly promises to apply to "any free-text
value." This is exactly the kind of value an operator could type (or an
external actor could pre-seed via the customer form, since there is no
auth), and it is completely unguarded by tests — `/export/sales.csv` and
`/export/customers.csv` have zero content-level test coverage, unlike
`/export/products.csv`.

## Critical Issues

### CR-01: `consultant_number` is exported to CSV without formula-injection escaping

**File:** `app/services/export.py:134-151`
**Issue:** `stream_customers_csv` escapes `customer.name` and `customer.surname`
through `_csv_safe`, but not `customer.consultant_number`:
```python
rows = [
    [
        _csv_safe(customer.name),
        _csv_safe(customer.surname or ""),
        customer.consultant_number or "",          # <-- not escaped
        iso_to_local(customer.created_at, settings.display_tz),
    ]
    for customer in customers
]
```
`consultant_number` is a free-text `String(50)` field entered directly through
the customer form (`app/routes/customers.py`, `app/services/customers.py`)
with no character restriction beyond a length cap of 50 — easily long enough
for a formula/DDE payload such as `=cmd|'/C calc'!A0` (18 chars). The
module's own docstring states: *"T-06-10: `_csv_safe` prefixes any free-text
value starting with =, +, -, or @ so Excel never interprets it as a formula
on open"* — this field violates that stated contract. When the operator
opens `customers.csv` in Excel, a consultant number starting with `=`, `+`,
`-`, or `@` will be evaluated as a formula/DDE command instead of displayed
as text.

This is precisely the CSV/formula-injection scenario called out in the
review scope, and it slipped through because there is no test that exports
a customer with a consultant number and inspects the CSV bytes (see WR-02).

**Fix:**
```python
customer.consultant_number and _csv_safe(customer.consultant_number) or "",
```
or, more idiomatically:
```python
_csv_safe(customer.consultant_number or ""),
```

## Warnings

### WR-01: `products.csv` full dump cannot distinguish active from soft-deleted rows

**File:** `app/services/export.py:72-92`
**Issue:** `stream_products_csv` intentionally includes soft-deleted products
("BCK-02 full dump"), but the header/row shape has no status or `deleted_at`
column:
```python
header = ["Код", "Название", "Категория", "Закупка", "Продажа", "Каталог", "Остаток"]
```
Per `models.py`'s own documented policy (`uq_products_code_active`), an
active product and a soft-deleted product **can share the same `code`**.
In that scenario, `products.csv` will contain two rows with an identical
code and no way for the operator to tell which one is the live product and
which is deleted — undermining the stated purpose of a "full, unfiltered
table dump" as a usable backup/export artifact.
**Fix:** add a `deleted_at` (or a RU "Статус"/"Удалён" boolean) column, e.g.:
```python
header = [..., "Остаток", "Удалён"]
rows = [[..., product.quantity, "Да" if product.deleted_at else ""] for product in products]
```

### WR-02: `/export/sales.csv` and `/export/customers.csv` have no content-level test coverage

**File:** `tests/test_export.py`
**Issue:** Only `test_products_csv_roundtrip` actually decodes a CSV response
and asserts on its rows. `stream_sales_csv` and `stream_customers_csv` are
never exercised end-to-end with real data — there is no test that creates a
customer/sale and checks the exported bytes. This is the direct reason CR-01
(the unescaped `consultant_number`) was not caught: a roundtrip test mirroring
`test_products_csv_roundtrip` for customers would have needed to assert on
`consultant_number` and likely would have surfaced the gap.
**Fix:** add `test_sales_csv_roundtrip` and `test_customers_csv_roundtrip`
tests analogous to the existing products one, including a case with a
formula-injection-prefixed `consultant_number`/`name` to pin the escaping
contract for every free-text column, not just the ones already covered by
the generic `_csv_safe` unit tests.

### WR-03: No upper-bound validation on `low_stock_threshold` / `stale_days`

**File:** `app/services/catalog.py:34-47`
**Issue:** `parse_optional_int` only rejects non-ASCII-digit input; any
string of digits is accepted and passed straight to `int()`, with no range
check:
```python
if raw.isascii() and raw.isdigit():
    return int(raw)
```
An operator (or a malformed/duplicated form submit) can submit an
arbitrarily large digit string (e.g. 20 digits), which SQLite's dynamically
typed `INTEGER` column will happily store, but which would overflow a
4-byte PostgreSQL `INTEGER` column on the project's stated future migration
(`app/models.py` documents `low_stock_threshold`/`stale_days` as plain
`Integer` columns, and CLAUDE.md's sync-readiness goal is a PostgreSQL
connection-string swap with no schema rework).
**Fix:** clamp/reject values above a sane bound, e.g.:
```python
if raw.isascii() and raw.isdigit() and int(raw) <= 2_147_483_647:
    return int(raw)
errors[field] = THRESHOLD_ERROR
return None
```

### WR-04: Money fields accept negative values with no validation

**File:** `app/services/catalog.py:22-31` (`parse_optional_cents` / `app/core.py:to_cents`)
**Issue:** `parse_optional_cents` calls `to_cents` with no sign check, so
`cost_raw="-12.50"` is accepted and stored as `cost_cents=-1250`. A negative
purchase/sale/catalog price has no domain meaning for this app. It also
interacts with the CSV export: `format_cents(-1250)` produces the string
`"-12,50"`, which begins with `-` — one of the exact characters
`app/services/export.py`'s own `_INJECTION_PREFIXES` treats as a
formula-injection trigger — yet `stream_products_csv`/`stream_sales_csv`
never pass the formatted money strings through `_csv_safe`. In practice a
plain `-12,50` cell is unlikely to be evaluated by Excel as a formula, so
this is not itself exploitable, but it is a real gap in input validation
that the money-formatting/export code silently tolerates.
**Fix:** reject negative amounts in `parse_optional_cents` (or in
`to_cents` for this call site) with the existing `PRICE_ERROR` message.

## Info

### IN-01: Unescaped `product.code` renders literal "(None)" if code is ever NULL

**File:** `app/templates/partials/sales_report_results.html:39`, `app/templates/partials/top_selling_rows.html:25`
**Issue:** Both partials render `{{ row.product.name }} ({{ row.product.code }})`
with no `or ""` guard. `Product.code` is a nullable column
(`Mapped[str | None]`), and Jinja2 renders a `None` value as the literal text
`"None"` (verified: `env.from_string('{{ code }}').render(code=None)` →
`'None'`). The sibling report templates added in this same phase,
`reports_stock.html` and `reports_products.html`, correctly guard with
`{{ row.product.code or "" }}`. Currently unreachable in practice because
`create_product` requires a non-empty code, but it is an inconsistency
against the pattern this same phase establishes elsewhere, and the model
itself allows NULL.
**Fix:** `{{ row.product.name }} ({{ row.product.code or "" }})`.

### IN-02: `top_selling_products` has no documented/tested soft-delete policy

**File:** `app/services/reports.py:144-167`
**Issue:** `sales_profit_report` and `writeoff_report` both carry an explicit
docstring note (and a dedicated test) pinning the "historical reports never
filter `deleted_at`" contract (RESEARCH Pitfall 5). `top_selling_products`,
which is period-based like those two, has no such note and no test covering
a soft-deleted product inside its period — leaving its behavior with
deleted products undocumented and unverified, even though it will in fact
include them (no `deleted_at` filter present).
**Fix:** add a docstring note plus a test mirroring
`test_sales_report_includes_deleted_product_for_past_period`.

### IN-03: `writeoff_report`'s per-line detail is computed but never displayed

**File:** `app/services/reports.py:108-124`, `app/templates/partials/writeoffs_report_rows.html`
**Issue:** `writeoff_report` builds a `"lines"` list of `{"op", "product"}`
per reason group, but `writeoffs_report_rows.html` only renders the
aggregated `reason_code`/`label`/`qty` — `entry.lines` is never iterated in
any template. It is exercised only by unit tests
(`report["by_reason"][0]["lines"][0]["product"]`), not by any UI consumer.
**Fix:** either drop the unused `"lines"` payload from the return value (it
still fully loads each `Operation`/`Product` row into memory for nothing), or
document that it is intentionally reserved for a future drill-down view.

### IN-04: No HTTP-level test exercises the new threshold form fields end-to-end

**File:** `tests/test_catalog.py`
**Issue:** `test_create_product_threshold_fields_empty_means_none`,
`..._zero_is_stored_as_zero_not_none`, and `..._rejects_invalid_threshold`
all call `create_product`/`update_product` directly. No `test_web_*` test
posts `low_stock_threshold`/`stale_days` through `POST /products` or
`POST /products/{id}` and asserts the stored value, so a mismatch between
the `Form(...)` parameter names in `app/routes/products.py` and the service's
keyword arguments (`low_stock_threshold_raw=`, `stale_days_raw=`) would not
be caught by the test suite.
**Fix:** add a `test_web_*` test posting both fields and asserting the
persisted `Product.low_stock_threshold`/`stale_days`.

---

_Reviewed: 2026-07-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
