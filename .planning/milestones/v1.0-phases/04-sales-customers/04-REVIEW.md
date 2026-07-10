---
phase: 04-sales-customers
reviewed: 2026-07-09T00:00:00Z
depth: standard
files_reviewed: 26
files_reviewed_list:
  - alembic/versions/0004_sales_customers.py
  - app/main.py
  - app/models.py
  - app/routes/customers.py
  - app/routes/sales.py
  - app/services/customers.py
  - app/services/ledger.py
  - app/services/sales.py
  - app/static/style.css
  - app/templates/base.html
  - app/templates/pages/customer_detail.html
  - app/templates/pages/customer_form.html
  - app/templates/pages/customers_list.html
  - app/templates/pages/sale_form.html
  - app/templates/partials/customer_picker.html
  - app/templates/partials/customer_rows.html
  - app/templates/partials/purchase_history.html
  - app/templates/partials/recent_sales.html
  - app/templates/partials/sale_customer.html
  - app/templates/partials/sale_form.html
  - app/templates/partials/sale_lookup.html
  - app/templates/partials/sale_oversell.html
  - app/templates/partials/sale_row.html
  - tests/conftest.py
  - tests/test_customers.py
  - tests/test_ledger.py
  - tests/test_sales.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-07-09T00:00:00Z
**Depth:** standard
**Files Reviewed:** 26 (full file set across all 6 plans in this phase, including the
04-06 `/sales/lookup` bracketed-key gap closure — this supersedes an earlier
`04-REVIEW.md` written against the pre-gap-closure state of this directory)
**Status:** issues_found

## Summary

Reviewed the full sales + customers slice: the `customers`/`sales` schema migration
(0004), models, routes, services, templates, and tests. All 45 tests in
`test_sales.py` / `test_customers.py` / `test_ledger.py` pass. The bracketed-key
regression in `/sales/lookup` (SAL-01 gap closure, plan 04-06) is correctly fixed —
the route now aliases `code[]`/`name[]`/`price[]`, and the regression tests
(`test_web_sale_lookup_prefills_price`,
`test_web_sale_lookup_bracketed_params_price_prefilled_no_clobber`) exercise the exact
bracketed shape htmx actually sends from `hx-include="closest tr"`.

Note for whoever consumes this report: an earlier `04-REVIEW.md` existed in this
directory (timestamped before the 04-06 gap closure) that flagged a critical reflected-XSS
finding (`row` query param → `hx-on::load` JS sink in `sale_row.html`), an unsafe
`isdigit()`/`int()` precondition, a missing rollback around the basket write loop, and a
missing max-length guard on `Customer` fields. I re-checked all four against the code as
it stands today: **all four are fixed** — `/sales/row`'s `row` param is now validated with
`_ROW_ID_RE` before use, `qty_text.isascii() and qty_text.isdigit()` guards the `int()`
call, the entire per-line write loop plus the final commit are now inside one
`try/except (IntegrityError, ValueError)` with an explicit rollback, and
`app/services/customers.py::_validate_lengths` enforces the declared column lengths. No
regression from that prior review remains.

This pass found no new Critical/Blocker-level issues (no hardcoded secrets, no
`|safe`/`innerHTML`-style XSS, no SQL/command injection, no auth bypass — all templates
rely on Jinja autoescape, and every client-controlled value that flows into a
JS-evaluated attribute is now server-validated). It did find two Warnings worth fixing
before they bite in production:

1. `register_sale`'s write-phase exception handler swallows `IntegrityError`/`ValueError`
   with **no logging**, unlike every other exception boundary in this phase (routes
   always `logger.exception(...)`). A genuine concurrency bug (e.g. a
   `(device_id, seq)` collision) would surface to the operator as a generic "try again"
   message with zero server-side trace to diagnose it.
2. I empirically verified (by running `alembic upgrade head` and inspecting the
   resulting schema with SQLAlchemy's `inspect()`) that **production's
   `operations.sale_id` column has no database-level foreign key** — by design, per the
   migration's own "A1 fallback" docstring — while the test suite's
   `Base.metadata.create_all()` schema **does** create that FK. The only safety net this
   phase relies on for `sale_id` integrity therefore does not exist in the deployed
   schema, and no test run against the current fixtures can ever catch a regression that
   writes a bogus `sale_id`.

Neither is a live data-corruption bug in the code as written today (the only caller
passes `sale_id=header.id` from a `Sale` header added in the same transaction), but both
remove a safety net that future changes will likely assume exists.

## Warnings

### WR-01: `register_sale` silently discards genuine write-phase errors (no logging)

**File:** `app/services/sales.py:183-185`
**Issue:** The write loop's exception handler catches `(IntegrityError, ValueError)`,
rolls back, and returns a generic RU message — with no `logger.exception` call:
```python
except (IntegrityError, ValueError):
    session.rollback()
    return None, {"basket": SAVE_ROLLBACK}
```
Contrast this with `app/routes/sales.py:145-148` and `:196-198`, which both explicitly
log via `logger.exception(...)` specifically so "a real bug isn't silently reduced to a
generic user-facing message with no server-side trace" (their own comment). Because
`register_sale` catches these exceptions internally, they never propagate to the route's
`try/except Exception`, so that route-level logging never fires for this class of error.
A real bug (e.g. a `(device_id, seq)` UNIQUE violation from a future concurrency issue)
would be completely invisible in the server logs.
**Fix:**
```python
# app/services/sales.py
import logging
...
logger = logging.getLogger(__name__)
...
    except (IntegrityError, ValueError):
        logger.exception("register_sale write phase failed")
        session.rollback()
        return None, {"basket": SAVE_ROLLBACK}
```

### WR-02: `operations.sale_id` has no FK in production; the test schema silently over-enforces it

**File:** `alembic/versions/0004_sales_customers.py:78-82`, `app/models.py:122-124`,
`tests/conftest.py:22-23`, `app/services/ledger.py:29-90`
**Issue:** Verified by running the actual migration chain and inspecting the resulting
schema:
```
alembic upgrade head        -> operations FKs = [fk_operations_product_id_products]                       (no sale_id FK)
Base.metadata.create_all()  -> operations FKs = [fk_operations_product_id_products, fk_operations_sale_id_sales]
```
Every test in this phase runs against `Base.metadata.create_all()`
(`tests/conftest.py:22-23`), so the suite enforces a `sale_id` FK constraint that
**does not exist in the real, migrated production database** (the migration
deliberately omits it — see the module docstring's "A1 fallback" section on the SQLite
ALTER-with-inline-FK limitation). `record_operation` (`app/services/ledger.py`)
explicitly validates `product_id` (`session.get(Product, product_id)` + a
soft-delete check) but performs **no equivalent existence check for `sale_id`** — the
FK was the only other safety net, and it is absent in production. A future bug that
passes a stale/incorrect `sale_id` into `record_operation` would silently write an
orphaned reference in the field, and no test run against the current fixtures could
ever catch it, because the fixture schema is stricter than production for this exact
column.
**Fix:** Either (a) add an explicit `session.get(Sale, sale_id)` existence check in
`record_operation` mirroring the `product_id` guard when `sale_id is not None`, or (b)
at minimum add a migration-schema-based regression test (in the style of
`test_migration_0004_preserves_append_only_triggers`) that documents/asserts the
current no-FK behavior in production, so a future contributor doesn't accidentally
assume FK enforcement that isn't actually there.

### WR-03: Name-required early return skips length validation on the other fields

**File:** `app/services/customers.py:60-66` (`create_customer`), `:98-104`
(`update_customer`)
**Issue:** Both functions do:
```python
if not name:
    errors["name"] = NAME_REQUIRED_ERROR
    return None, errors

_validate_lengths(name, surname, consultant_number, errors)
if errors:
    return None, errors
```
When `name` is blank *and* `surname`/`consultant_number` exceed their max length, only
`"Укажите имя покупателя."` is ever returned — the length error only surfaces after the
operator fixes the name and resubmits, one avoidable extra round trip later than
necessary, and inconsistent with the "one response, all field errors" pattern the
`errors` dict shape implies elsewhere in this codebase.
**Fix:**
```python
errors: dict[str, str] = {}
name = name.strip()
surname = surname.strip()
consultant_number = consultant_number.strip()

if not name:
    errors["name"] = NAME_REQUIRED_ERROR
_validate_lengths(name, surname, consultant_number, errors)
if errors:
    return None, errors
```

### WR-04: `/sales/lookup`'s `row` param isn't format-validated the way `/sales/row`'s is

**File:** `app/routes/sales.py:71-77`, `app/templates/partials/sale_lookup.html:5-6`
**Issue:** `app/routes/sales.py:24-28` documents, in detail, that a client-controlled
"row" value is attacker-reachable and "must be constrained to the exact shape
`new_id()` produces... before it is ever trusted," and `/sales/row` does exactly that
via `_ROW_ID_RE.fullmatch(row)` (line 107). `/sales/lookup`'s own `row: str = ""` (line
77) is the same kind of client-controlled value from the same style of request, but is
passed straight into `sale_lookup.html` unvalidated (`"name-" + row`,
`"price-" + row`). Today this only ends up inside an `id="..."` HTML attribute, which
Jinja autoescapes, so it is not currently exploitable — but the asymmetry means a
future template change that reuses `row` inside a JS-evaluated attribute (as
`sale_row.html` already does for the validated `row_id`) would silently reintroduce the
exact class of bug `_ROW_ID_RE` exists to prevent.
**Fix:** Apply the same guard for consistency/defense-in-depth:
```python
row = row.strip()
row = row if _ROW_ID_RE.fullmatch(row) else ""
```

## Info

### IN-01: Superfluous `noqa: F401` on an import that IS used

**File:** `tests/test_customers.py:23`
**Issue:** `from app.services.sales import register_sale  # noqa: F401 (used to seed linked sales)`
— `register_sale` is genuinely called later in the file (e.g. line 84,
`test_purchase_history_returns_rows_for_customer`), so it is not unused and the `noqa`
suppresses a lint warning that would never fire. Harmless, but reads as if the import
were dead when it isn't.
**Fix:** Drop the `# noqa: F401` (keep the explanatory comment as plain prose if
useful).

### IN-02: `create_customer`/`update_customer` duplicate their validation pipeline

**File:** `app/services/customers.py:47-77` vs `:80-111`
**Issue:** Both functions repeat the identical trim → required-name check →
`_validate_lengths` → build-and-assign sequence almost line for line. Not incorrect,
but the duplication means any future change to validation order/rules (e.g. WR-03
above) has to be applied twice and can drift out of sync.
**Fix:** Extract a shared helper, e.g.
`_normalize_and_validate(name, surname, consultant_number) -> tuple[str, str, str, dict[str, str]]`,
and call it from both functions.

### IN-03: Dead "missing price" branch in the sale history/list partials

**File:** `app/templates/partials/recent_sales.html:28-29`,
`app/templates/partials/purchase_history.html:25-26`
**Issue:** Both partials guard `{% if h.op.unit_price_cents is not none %}` (or
`r.op...`) before rendering price/total, for rows where `Operation.type == "sale"`.
Since `app/services/sales.py::register_sale` rejects any sale line with a blank price
(`PRICE_REQUIRED_ERROR`), a `sale`-type operation can never have `unit_price_cents is
None` in practice — the branch is unreachable given current invariants, and the two
partials aren't even consistent with each other about it (`purchase_history.html`
renders a `—` placeholder for the "missing" case; `recent_sales.html` has no `else`
branch at all, so it would render an empty cell for a case that cannot happen).
**Fix:** Either simplify to `{{ h.op.unit_price_cents | cents }}` unconditionally, or —
if intentionally kept as defensive code against a future operation type reusing this
template — align the two partials to render the same placeholder.

---

_Reviewed: 2026-07-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
