---
phase: 14-list-pagination-filtering-sorting-quick-delete
reviewed: 2026-07-14T00:00:00Z
depth: standard
files_reviewed: 32
files_reviewed_list:
  - alembic/versions/0012_dictionary_name_lc.py
  - app/models.py
  - app/routes/catalogs.py
  - app/routes/customers.py
  - app/routes/dictionary.py
  - app/routes/history.py
  - app/routes/mobile_history.py
  - app/routes/products.py
  - app/routes/warehouses.py
  - app/services/catalog.py
  - app/services/catalogs.py
  - app/services/customers.py
  - app/services/dictionary.py
  - app/services/operations.py
  - app/services/pagination.py
  - app/services/warehouses.py
  - app/static/style.css
  - app/templates/pages/catalogs.html
  - app/templates/pages/customers_list.html
  - app/templates/pages/history.html
  - app/templates/pages/products_list.html
  - app/templates/partials/catalog_rows.html
  - app/templates/partials/customer_rows.html
  - app/templates/partials/dictionary_rows.html
  - app/templates/partials/history_rows.html
  - app/templates/partials/pagination.html
  - app/templates/partials/product_rows.html
  - app/templates/partials/warehouse_rows.html
  - tests/test_catalog.py
  - tests/test_catalogs_feature.py
  - tests/test_customers.py
  - tests/test_dictionary.py
  - tests/test_history.py
  - tests/test_pagination.py
  - tests/test_search.py
  - tests/test_warehouses.py
findings:
  critical: 1
  warning: 3
  info: 0
  total: 4
status: issues_found
---

# Phase 14: Code Review Report

**Reviewed:** 2026-07-14T00:00:00Z
**Depth:** standard
**Files Reviewed:** 32 (listed) — reviewed against `git diff 3bc0d1d..HEAD` to focus on Phase 14's actual changes
**Status:** issues_found

## Summary

Phase 14 adds page-number pagination, per-column header-row filters, sort
dropdowns, and quick-delete/quick-warn flows to `/products`, `/dictionary`,
`/warehouses`, `/customers`, `/catalogs` and `/history`. The shared
`app/services/pagination.py` helper (`paginate`, `page_window`,
`LIST_PAGE_SIZE`) is solid and well-tested (edge cases: empty list, exact
page-size boundary, out-of-range page clamping are all covered).

The most significant defect is a **BLOCKER**: on `products.py`,
`dictionary.py`, and `warehouses.py`, every write-response route rebuilds
its shared template context by calling `_products_context()` /
`_dictionary_context()` / `_warehouses_context()` **with no filter/sort/page
arguments**, resetting the response to the unfiltered page-0 view. Before
this phase that reset was harmless (lists were small and unpaginated); now
that these lists support filtering/pagination, a row-specific error or
warning (failed edit validation, "blocked: stock on hand", "last active
warehouse") can silently fail to render anywhere in the response whenever
the affected row is not on the reset default page — the user just sees an
unrelated set of rows with zero explanation of what happened to their
action.

Three further **WARNING**-level issues were found: a LIKE-wildcard
autoescape inconsistency in the new `dictionary.list_entries` code filter,
an unconditional pagination bar shown even in the empty-catalogs state
(inconsistent with every other Phase 14 list partial), and a new line that
violates the project's own configured `ruff` line-length limit.

## Critical Issues

### CR-01: Row-specific error/warning feedback can vanish after a write, because the shared context builders discard the current filter/sort/page state

**File:** `app/routes/products.py:98-110`, `app/routes/dictionary.py:111-134`, `app/routes/warehouses.py:132-175`

**Issue:**
Three write-response routes rebuild their list context by calling the
shared `_..._context()` helper with **no** `code`/`name`/`category`/
`sort`/`page` (or `status`) arguments, which unconditionally resets the
rendered list to page 0 with all filters cleared:

```python
# app/routes/products.py — product_quick_delete
deleted, blocked = quick_delete_product(session, product_id)
context = _products_context(
    session,
    blocked_id=product_id if not deleted and blocked else None,
    blocked_qty=blocked.get("blocked_qty"),
)
```

```python
# app/routes/dictionary.py — dictionary_update
entry, errors = update_entry(session, entry_id, code=code, name=name)
...
context = {
    **_dictionary_context(session),   # no code/name/sort/page passed
    "errors": errors,
    "error_entry_id": entry_id if errors else None,
    "error_form": {"code": code, "name": name} if errors else None,
}
```

```python
# app/routes/warehouses.py — warehouse_update / warehouse_delete
context = _warehouses_context(
    session,
    errors=errors,
    error_entry_id=warehouse_id if errors else None,
    error_form={"name": name, "address": address} if errors else None,
)
# and:
context = _warehouses_context(
    session,
    warning_id=warehouse_id if warning.get("warehouse") else None,
    stock_blocked_id=warehouse_id if warning.get("stock") else None,
    stock_blocked_qty=warning.get("stock"),
)
```

The corresponding templates only render the per-row error/blocked/warning
markup when the affected row is present in the (now reset) `entries` /
`rows` / `warehouses` list for the current render
(`{% if error_entry_id == e.id %}`, `{% if blocked_id == product.id %}`,
`{% if stock_blocked_id == w.id %}`, `{% if warning_id == w.id %}`). If the
row the operator was looking at is **not** on the default page-0/no-filter
view — which is exactly the scenario filtering/pagination exist to solve
(the dictionary alone has ~6,856 rows, i.e. 343 pages) — the response
silently swaps in a completely different, unrelated page of rows with no
error/warning anywhere in the HTML. Concretely:

- An operator filters `/dictionary` by `name`, opens row #200, submits an
  invalid edit (e.g. a duplicate code) → 422 response re-renders page 0
  unfiltered; the edited row (and its error message) is very likely not on
  that page at all, so **no error is visible**, and the general error
  banner is also suppressed because it only renders `{% if errors and not
  error_entry_id %}` (`error_entry_id` is set here).
- An operator filters `/products` by category, clicks "Удалить" on a
  product with stock > 0 → the quick-delete-blocked message
  ("Нельзя удалить: на остатке N шт.") only renders next to that product's
  row; after the reset, that product is very likely off the (unfiltered,
  page-0) view, so the "blocked" feedback is lost — the operator sees an
  unrelated product list and no indication the delete failed.
- Same failure mode for `warehouse_update` validation errors and for
  `warehouse_delete`'s stock-blocked / last-active-warehouse warnings when
  `status`/`name`/`address`/`sort`/`page` are non-default.

This is untested: every existing test for these flows (`test_dictionary.py`,
`test_warehouses.py`, `test_catalog.py`) exercises the error/blocked/warning
path only from the default unfiltered page-0 view, where the bug is
invisible.

**Fix:** Thread the request's current `code`/`name`/`category`/`status`/
`sort`/`page` through to the context builder on every write response
instead of dropping them, e.g.:

```python
@router.post("/dictionary/{entry_id}")
def dictionary_update(
    request: Request,
    entry_id: str,
    code: str = Form(""),
    name: str = Form(""),
    # echo back the list state the operator was viewing:
    list_code: str = Form(""),
    list_name: str = Form(""),
    list_sort: str = Form(""),
    list_page: int = Form(0),
    session: Session = Depends(get_session),
):
    entry, errors = update_entry(session, entry_id, code=code, name=name)
    if "entry" in errors:
        raise HTTPException(status_code=404, detail="unknown dictionary entry")
    context = {
        **_dictionary_context(session, code=list_code, name=list_name, sort=list_sort, page=list_page),
        "errors": errors,
        "error_entry_id": entry_id if errors else None,
        "error_form": {"code": code, "name": name} if errors else None,
    }
    ...
```

(populate `list_code`/`list_name`/`list_sort`/`list_page` as hidden fields
in each row's edit `<form>`/quick-delete button, e.g. via `hx-vals` or
hidden `<input>`s, mirroring how `hx-vals='{"confirm": "1"}'` already
carries extra state on the warehouse delete-confirm button). At minimum,
when the affected row falls outside the reset view, fall back to always
showing the general error banner (drop the `not error_entry_id` guard) so
validation failures are never silently swallowed.

## Warnings

### WR-01: `dictionary.list_entries`'s code filter is missing `autoescape=True`, unlike its name filter — LIKE wildcards leak through

**File:** `app/services/dictionary.py:108`
**Issue:** The new SQL-side filters in `list_entries` are inconsistent:

```python
if code:
    filters.append(func.lower(Dictionary.code).contains(code.lower()))
if name:
    filters.append(Dictionary.name_lc.contains(name.lower(), autoescape=True))
```

`Column.contains(...)` defaults to `autoescape=False` (verified against the
pinned SQLAlchemy 2.0.51: `code.contains('a_b')` compiles to
`code LIKE '%' || 'a_b' || '%'` — no `ESCAPE` clause — while
`code.contains('a_b', autoescape=True)` compiles to
`code LIKE '%' || 'a/_b' || '%' ESCAPE '/'`). The `code` filter therefore
treats a literal `%` or `_` typed by the operator as a SQL `LIKE` wildcard
(match-anything / match-any-single-char) instead of a literal character —
the exact class of bug `catalog.py`'s `_escape_like()` and this same
function's `name` filter were written to avoid. This is inconsistent with
the project's own established pattern (`catalog.search_products` escapes
`%`/`_`/`\` explicitly; `name_lc.contains(..., autoescape=True)` two lines
below it does the right thing).

**Fix:**
```python
if code:
    filters.append(func.lower(Dictionary.code).contains(code.lower(), autoescape=True))
```

### WR-02: `catalog_rows.html` renders the pagination bar unconditionally, even when the catalog list is empty

**File:** `app/templates/partials/catalog_rows.html:38-82`
**Issue:** Every other Phase 14 list partial (`product_rows.html`,
`customer_rows.html`, `dictionary_rows.html`, `warehouse_rows.html`) places
`{% include "partials/pagination.html" %}` **inside** the truthy branch of
its `{% if rows %}`/`{% if entries %}`/`{% if warehouses %}` guard, so the
pagination bar is hidden together with the table in the empty-state. In
`catalog_rows.html`, the include sits **after** (outside) the
`{% if not catalogs %} ... {% else %} ... {% endif %}` block:

```jinja
{% if not catalogs %}
  <div class="empty-state">...</div>
{% else %}
  ... table(s) ...
{% endif %}

{% include "partials/pagination.html" %}
```

With zero catalogs, `page_window(0, 1)` still returns `[0]`
(`total_pages` is clamped to a minimum of 1 by `paginate`/`list_catalogs`),
so the empty "Каталогов пока нет" / "Ничего не найдено по заданным
фильтрам." message is followed by a spurious "Страница 1 из 1" pagination
bar with a highlighted "1" button — inconsistent with the UX of every
other list page in this phase and untested (no test asserts pagination is
absent for the empty-catalogs case).

**Fix:** move the `{% include "partials/pagination.html" %}` line inside
the `{% else %}` branch, right after the closing `{% endif %}` of the
per-page year-grouping loop, mirroring `product_rows.html`'s placement.

### WR-03: New line in `operations.py` exceeds the project's configured `ruff` line-length limit

**File:** `app/services/operations.py:52`
**Issue:** `ruff check` (configured `line-length = 100`, `select = ["E", ...]` in `pyproject.toml`) fails on this Phase 14-added line:

```
E501 Line too long (110 > 100)
  --> app/services/operations.py:52:101
   |
52 |     count_stmt = select(func.count()).select_from(Operation).join(Product, Operation.product_id == Product.id)
```

This breaks the project's own lint gate for a file that was otherwise
carefully kept clean in this phase.

**Fix:** wrap the statement, e.g.:
```python
count_stmt = (
    select(func.count())
    .select_from(Operation)
    .join(Product, Operation.product_id == Product.id)
)
```

---

_Reviewed: 2026-07-14T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
