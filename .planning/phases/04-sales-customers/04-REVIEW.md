---
phase: 04-sales-customers
reviewed: 2026-07-09T00:00:00Z
depth: standard
files_reviewed: 26
files_reviewed_list:
  - app/models.py
  - app/services/ledger.py
  - app/services/sales.py
  - app/services/customers.py
  - app/routes/sales.py
  - app/routes/customers.py
  - app/main.py
  - alembic/versions/0004_sales_customers.py
  - tests/conftest.py
  - tests/test_ledger.py
  - tests/test_sales.py
  - tests/test_customers.py
  - app/templates/base.html
  - app/templates/pages/sale_form.html
  - app/templates/partials/sale_form.html
  - app/templates/partials/sale_row.html
  - app/templates/partials/sale_lookup.html
  - app/templates/partials/recent_sales.html
  - app/templates/partials/sale_oversell.html
  - app/templates/partials/sale_customer.html
  - app/templates/partials/customer_picker.html
  - app/templates/pages/customers_list.html
  - app/templates/partials/customer_rows.html
  - app/templates/pages/customer_form.html
  - app/templates/pages/customer_detail.html
  - app/templates/partials/purchase_history.html
  - app/static/style.css
findings:
  critical: 1
  warning: 5
  info: 1
  total: 7
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-07-09T00:00:00Z
**Depth:** standard
**Files Reviewed:** 26
**Status:** issues_found

## Summary

Reviewed the sales-basket and customer-CRUD slice: models, the ledger/sales/customers
services, their routes, migration `0004`, tests, and every template touched by this
phase. The append-only ledger contract, the "one transaction / all-or-nothing basket"
design, and the oversell-aggregation logic are all sound and match their docstrings and
tests (verified against the actual SQLAlchemy 2.0.51 flush-ordering behavior used by
this project, and against Python's `str.isdigit()`/`int()` semantics, both confirmed by
running small scripts against the project's own `.venv`).

One genuine, provable XSS vulnerability was found: `GET /sales/row`'s `row` query
parameter is reflected — unsanitized beyond Jinja's default HTML-attribute escaping —
into an `hx-on::load` attribute that htmx evaluates as JavaScript. HTML-entity escaping
of quotes does not neutralize this sink, because the browser HTML-decodes the attribute
value before handing it to the JS engine; a crafted `row` value round-trips back into
syntactically valid JavaScript. Several further robustness/quality issues were found
around exception handling in `app/services/sales.py` / `app/routes/sales.py`.

## Critical Issues

### CR-01: Reflected XSS via `row` query param into an `hx-on::load` JS sink

**File:** `app/routes/sales.py:92-109`, `app/templates/partials/sale_row.html:8-20`

**Issue:** `GET /sales/row` takes `row: str = ""` straight from the query string,
only calls `.strip()`, and uses it as `row_id` whenever non-blank:

```python
@router.get("/sales/row")
def sale_row(request: Request, row: str = ""):
    row_id = row.strip() or new_id()
    context = {"row_id": row_id, ..., "focus_new": True, ...}
    return templates.TemplateResponse(request, "partials/sale_row.html", context)
```

`sale_row.html` then builds `code_id = "code-" + row_id` and embeds it inside a
JS-executing attribute:

```html
{% set code_id = "code" if not row_id else "code-" + row_id %}
<tr id="row-{{ row_id or 'first' }}"{% if focus_new %} hx-on::load="document.getElementById('{{ code_id }}').focus()"{% endif %}>
```

Jinja's autoescaping HTML-entity-encodes `'`/`"` inside the attribute, but the browser
HTML-decodes attribute values *before* htmx reads them with `getAttribute()` and
evaluates them as JS. So a payload such as:

```
GET /sales/row?row=');alert(document.domain);//
```

renders as `hx-on::load="document.getElementById(&#39;code-&#39;);alert(document.domain);//&#39;).focus()"`,
which the browser decodes back to
`document.getElementById('code-');alert(document.domain);//').focus()` — valid
JavaScript that executes `alert(document.domain)` when htmx processes the `load`
hook. Confirmed by manual trace of Jinja's escape set (`&`, `<`, `>`, `'`, `"` only —
`;`, `(`, `)`, `/` pass through untouched) plus standard browser attribute-decoding
behavior for inline event-handler-style attributes.

Under normal app usage the "Добавить строку" button never sends a `row` param (so
`row_id` is always server-generated via `new_id()`), meaning this parameter has no
legitimate non-blank use today — it is pure attacker surface. The same `row` value is
also reflected, unsanitized, into `hx-vals='{"row": "{{ row_id }}"}'` on the same
element (secondary evidence of the same root cause).

**Fix:** Do not let client input choose the DOM id used inside an inline
JS-evaluated attribute. Either ignore the incoming value entirely (always call
`new_id()` server-side for this endpoint), or strictly validate it before use:

```python
import re
_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")

@router.get("/sales/row")
def sale_row(request: Request, row: str = ""):
    row = row.strip()
    row_id = row if _ROW_ID_RE.fullmatch(row) else new_id()
    ...
```

Longer term, prefer the `.dataset`-based pattern already used correctly elsewhere in
this same phase (`app/templates/partials/customer_picker.html`, which explicitly reads
`this.dataset.id` instead of string-interpolating untrusted text into an inline
handler) instead of building `hx-on::load="...('{{ value }}')..."` strings from
request-controlled input.

## Warnings

### WR-01: `qty_text.isdigit()` is not a safe precondition for `int()`

**File:** `app/services/sales.py:76`

**Issue:**
```python
qty = int(qty_text) if qty_text.isdigit() else 0
```
Python's `str.isdigit()` returns `True` for non-ASCII "digit" characters that
`int()` cannot parse (e.g. superscript `'²'.isdigit() == True` but
`int('²')` raises `ValueError`). Confirmed by running this exact snippet against the
project's `.venv` Python. If an operator's browser/IME submits such a character in the
quantity field, `register_sale` raises an uncaught `ValueError` instead of producing
the intended `QTY_ERROR` ("Укажите количество…") message; the exception is only
saved from becoming a 500 by the broad `except Exception` in the route (see WR-02),
which then shows a generic, unhelpful "Не удалось сохранить" error instead of the
correct per-field validation message.

**Fix:**
```python
qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
```
(or use a regex `re.fullmatch(r"[0-9]+", qty_text)`). The same pattern exists in
`app/services/receipts.py:58` and should get the same fix for consistency, though that
file is outside this phase's scope.

### WR-02: Broad exception swallowing with no logging in sales routes

**File:** `app/routes/sales.py:130-146` (`sale_customer_create`), `app/routes/sales.py:172-191` (`sale_create`)

**Issue:** Both handlers wrap their service call in `except Exception:  # noqa: BLE001`
and convert *any* unexpected error — including real bugs like WR-01, `AttributeError`,
`KeyError`, or a future regression — into the same generic user-facing message, with
zero logging anywhere. In production this makes any real defect essentially
undiagnosable: there is no trace of what actually failed, only "Не удалось сохранить".

**Fix:** Log the exception before returning the friendly error, e.g.:
```python
except Exception:
    logger.exception("register_sale failed")
    ...
```
so the failure is at least visible in server logs while still shielding the operator
from a raw 500.

### WR-03: Basket write loop has no explicit rollback on non-`IntegrityError` failures

**File:** `app/services/sales.py:143-164`

**Issue:** The per-line write loop (`record_operation(..., commit=False)` for each
resolved line) is not wrapped in a `try`/`except`; only the final `session.commit()`
call catches `IntegrityError`:
```python
for line in resolved:
    ...
    record_operation(session, ..., commit=False)
    ...
try:
    session.commit()
except IntegrityError:
    session.rollback()
    return None, {"basket": SAVE_ROLLBACK}
```
If `record_operation` raises anything other than at commit time (e.g. a `ValueError`
from its own guards, reachable in a TOCTOU race where a product is soft-deleted between
this function's earlier validation and the write loop), the exception propagates out of
`register_sale` with the session left holding uncommitted pending inserts and **no
explicit rollback**. This currently doesn't corrupt data only because the caller's
`get_session()` dependency (`app/db.py:60-63`) happens to close the session via a
context manager, and `Session.close()` implicitly rolls back any open transaction — but
that safety net is incidental, not part of this function's own contract, and the
docstring's claim ("nothing staged or written on any validation error") is not actually
guaranteed by this function in that path.

**Fix:** Wrap the write loop itself and roll back explicitly on any exception, not just
at the final commit:
```python
try:
    for line in resolved:
        ...
        record_operation(session, ..., commit=False)
        total_cents += qty * price_cents
    session.commit()
except (IntegrityError, ValueError):
    session.rollback()
    return None, {"basket": SAVE_ROLLBACK}
```

### WR-04: Basket-line filtering logic duplicated between service and route

**File:** `app/services/sales.py:62-66`, `app/routes/sales.py:21-49`

**Issue:** The "a line counts only if code/qty/price is non-blank" filter is
implemented independently in both `register_sale` (the source of truth for
`f"qty-{i}"`/`f"price-{i}"`/`f"code-{i}"` error keys) and `_build_lines` (used to
re-render the echoed basket on error). The route's docstring even calls this out
("Mirrors register_sale's own non-blank-line filtering"), acknowledging the
duplication. If either filter's rule changes without updating the other, error
messages will silently attach to the wrong row.

**Fix:** Extract the filter into one shared helper (e.g.
`app/services/sales.py::_non_blank_lines(codes, qtys, prices)`) and have both
`register_sale` and `_build_lines` call it.

### WR-05: `search_lc`/name fields have no max-length guard before insert

**File:** `app/services/customers.py:24-50`, `app/services/customers.py:53-80`

**Issue:** `Customer.name`/`surname`/`consultant_number` are declared as
`String(200)`/`String(200)`/`String(50)` and `search_lc` as `String(400)`, but none of
`create_customer`/`update_customer` enforce these lengths before insert. SQLite does
not enforce `VARCHAR` length, so this silently succeeds today; per this project's own
documented PostgreSQL-migration goal (CLAUDE.md: "same models will run on PostgreSQL
later"), an overlong value that works fine now will raise a hard error after that
migration. (Note: the sibling `app/services/catalog.py` has the same gap for
`Product.code`/`name`, so this is a pre-existing project convention, not unique to this
phase — flagged here because it applies directly to the new `Customer` write paths.)

**Fix:** Truncate or validate against the column's declared length in the service
layer, e.g. `errors["name"] = "Слишком длинное имя."` when `len(name) > 200`.

## Info

### IN-01: `row`/`code` GET params echoed into DOM ids without format validation

**File:** `app/routes/sales.py:64-89` (`sale_lookup`), `app/templates/partials/sale_lookup.html:5-6`

**Issue:** `sale_lookup`'s `row` param is likewise used unvalidated to build
`name_wrap_id`/`price_wrap_id` (`"name-" + row`, `"price-" + row`). Unlike CR-01 these
only end up in plain `id="..."` attributes (not a JS-execution sink), so this is not
itself exploitable for script injection, but it shares the same root cause (trusting a
client-supplied "row" identifier) and would benefit from the same validation fix
suggested in CR-01, for consistency and to avoid DOM-id collisions from unexpected
input.

**Fix:** Apply the same `row` format validation described in CR-01's fix to this route
as well.

---

_Reviewed: 2026-07-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
