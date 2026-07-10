---
phase: 02-catalog-dictionary-search
reviewed: 2026-07-08T19:10:14Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - alembic/versions/0002_catalog_dictionary.py
  - app/main.py
  - app/models.py
  - app/routes/dictionary.py
  - app/routes/products.py
  - app/services/catalog.py
  - app/services/dictionary.py
  - app/services/ledger.py
  - app/static/style.css
  - app/templates/base.html
  - app/templates/pages/dictionary.html
  - app/templates/pages/product_form.html
  - app/templates/pages/products_list.html
  - app/templates/partials/dictionary_rows.html
  - app/templates/partials/name_input.html
  - app/templates/partials/price_history.html
  - app/templates/partials/product_rows.html
  - tests/test_catalog.py
  - tests/test_dictionary.py
  - tests/test_search.py
findings:
  critical: 1
  warning: 4
  info: 6
  total: 11
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-08T19:10:14Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Narrative Findings (AI reviewer)

## Summary

Reviewed the Phase 02 catalog/dictionary/search slice: migration 0002, models, dictionary + products routes, catalog/dictionary/ledger services, templates, CSS, and the three test files. The test suite passes (70 passed). Service-layer logic is solid: Cyrillic-safe `name_lc` handling, snapshot-before-mutate price history, LIKE escaping, soft-delete guards, and the ledger single-write-path contract all check out against traced edge cases (NULL `code`, empty query, `%`/`_` literals).

One Critical defect was found in the HTMX integration: the dictionary add/edit endpoints return their error partial with HTTP 422, but the vendored htmx 2 does **not** swap 4xx responses by default — validation errors are invisible in the browser and the row edit silently appears to do nothing. This exact gap is untested (no web test posts invalid dictionary data), which is why the suite is green. Additional warnings cover a request-time-vs-swap-time race in the name autofill, unhandled `IntegrityError` paths, non-atomic multi-op audit writes, and a double-submit path that can create duplicate active product codes because uniqueness is enforced only in application code.

## Critical Issues

### CR-01: Dictionary validation errors are never shown — htmx does not swap 422 responses

**File:** `app/routes/dictionary.py:60`, `app/routes/dictionary.py:86` (interacts with `app/templates/pages/dictionary.html:6`, `app/templates/partials/dictionary_rows.html:32`, `app/templates/base.html`)
**Issue:** `dictionary_add` and `dictionary_update` respond to `hx-post` requests with the `dictionary_rows.html` error partial and `status_code=422`. The vendored `app/static/htmx.min.js` (htmx 2) ships the default `responseHandling:[{code:"204",swap:false},{code:"[23]..",swap:true},{code:"[45]..",swap:false,error:true}]` — a 422 response is **not swapped**; htmx fires `htmx:responseError` and discards the body. There is no `<meta name="htmx-config">` in `base.html` and no `response-targets` extension. Result: submitting a blank/duplicate code in the dictionary (add or inline edit) does nothing visible — no error message, no feedback, a silent failure of the CAT-02 validation UX. The tests pass because `TestClient` asserts the response body directly; no web test posts invalid dictionary data (see IN-06).
**Fix:** Either opt 422 into swapping globally in `app/templates/base.html`:
```html
<meta name="htmx-config"
      content='{"responseHandling":[{"code":"204","swap":false},{"code":"[23]..","swap":true},{"code":"422","swap":true},{"code":"[45]..","swap":false,"error":true}]}'>
```
or return the error partial with `status_code=200` in both dictionary POST handlers (HTMX-idiomatic: the swap itself carries the error state). If 422 is kept, add a web test asserting the error message is actually swapped (a browser-level or config-level assertion), not just present in the body.

## Warnings

### WR-01: Autofill race can overwrite the operator's in-progress name input

**File:** `app/templates/pages/product_form.html:19-25`, `app/routes/dictionary.py:36-40`
**Issue:** The Pitfall-5 guard ("a non-empty operator name is never overwritten") is evaluated at **request time**: `hx-include="[name='name']"` snapshots the name field when the lookup fires. Sequence: operator types a code → 300 ms debounce elapses → request fires with `name=""` → operator tabs to the name field and starts typing → the 200 response arrives and `hx-swap="outerHTML"` replaces `#name-wrap`, destroying the typed characters and the focus. `hx-sync="this:replace"` only serializes lookups against each other; it does not protect the name field.
**Fix:** Add a swap-time guard on the form so the fragment is discarded if the operator has meanwhile filled the name:
```html
<form method="post" ... class="stacked-form"
      hx-on::htmx:before-swap="if (event.detail.target.id === 'name-wrap'
        && document.getElementById('name').value.trim()) event.detail.shouldSwap = false">
```

### WR-02: Dictionary UNIQUE(code) violation surfaces as an unhandled 500

**File:** `app/services/dictionary.py:44-47`, `app/services/dictionary.py:60-62`
**Issue:** `add_entry`/`update_entry` use check-then-act: a SELECT for duplicates followed by `session.commit()`. If the duplicate appears between check and commit (double-submit from two tabs, or a retried request), SQLite's `uq_dictionary_code` raises `IntegrityError`, which no code catches — the operator gets a raw 500 instead of the RU duplicate message. `hx-disabled-elt` mitigates double-clicks on one button but not two tabs or a stale page.
**Fix:** Catch the constraint violation at the commit and translate it into the existing error shape:
```python
from sqlalchemy.exc import IntegrityError
try:
    session.commit()
except IntegrityError:
    session.rollback()
    return None, {"code": DUPLICATE_ERROR}
```

### WR-03: Multi-field product update is not atomic despite the docstring's atomicity claim

**File:** `app/services/catalog.py:186-202`, `app/services/ledger.py:76`
**Issue:** `update_product` calls `record_operation` once per changed price field plus once for non-price fields, and **each call commits its own transaction** (`ledger.py:76`). Only the first commit is atomic with the product-row mutation; the remaining audit ops are separate transactions. A crash (power loss — a stated risk for this app) between commits leaves the product updated but the price history missing one or more `price_change` rows, silently corrupting the CAT-04 audit trail. The docstring's "audit every change through the single write path" and the create-path "atomically" wording overstate the guarantee.
**Fix:** Stage all `Operation` rows first and commit once. Minimal change: add a `commit: bool = True` parameter to `record_operation`, pass `commit=False` for all ops in `update_product`, then `session.commit()` once at the end (`next_seq` still works — autoflush flushes pending ops before the `max(seq)` query).

### WR-04: Duplicate active product codes possible — uniqueness enforced only in Python

**File:** `app/services/catalog.py:57-62`, `app/templates/pages/product_form.html:14`, `alembic/versions/0002_catalog_dictionary.py:65`
**Issue:** Product-code uniqueness among active products exists only as a SELECT-then-INSERT check; there is no DB constraint (`ix_products_code` is non-unique, deliberately, since deleted products may share codes). The create form is a plain `method="post"` form with no double-submit protection — a double-click on «Сохранить товар» sends two POSTs, both can pass the duplicate check, and two active products with the same code are created. This silently breaks the D-26 "exact code match" ranking assumption and the operator's mental model of one code = one product.
**Fix:** Add a partial unique index in a follow-up migration (portable to PostgreSQL):
```python
op.create_index(
    "uq_products_code_active", "products", ["code"], unique=True,
    sqlite_where=sa.text("deleted_at IS NULL"),
    postgresql_where=sa.text("deleted_at IS NULL"),
)
```
and catch `IntegrityError` in `create_product`/`update_product` (same pattern as WR-02). Optionally disable the submit button on submit.

## Info

### IN-01: Empty-query listing and ranked search sort by different columns

**File:** `app/services/catalog.py:269`, `app/services/catalog.py:280`
**Issue:** Empty query orders by `Product.name` (mixed-case BINARY collation: all uppercase before lowercase), ranked search orders by `Product.name_lc`. The same catalog can appear in two different orders depending on whether the search box is empty.
**Fix:** Order the empty-query branch by `Product.name_lc` too (fall back to `Product.name` for NULL `name_lc` rows if any predate the service).

### IN-02: Non-ASCII product codes silently lose case-insensitive code matching

**File:** `app/services/catalog.py:270-275`, `app/services/catalog.py:57-62`
**Issue:** Code matching relies on SQL `lower()` (ASCII-only fold) under assumption A1 "codes are ASCII digits", but `create_product` never enforces that assumption — an operator can save a Cyrillic code, and case-insensitive code search for it will quietly fail (only name-substring matching would find the product).
**Fix:** Either validate codes as ASCII at write time (`code.isascii()` → RU error) or add a `code_lc` shadow column mirroring the `name_lc` pattern.

### IN-03: split_match indexes can misalign for length-changing lowercase

**File:** `app/services/catalog.py:291-294`
**Issue:** `split_match` computes the match index on `text.lower()` but slices the original `text`. For characters whose lowercase changes string length (e.g. `İ` → `i̇`), the indices shift and the `<mark>` highlight lands on the wrong characters. Cyrillic and ASCII are unaffected (1:1), so this is cosmetic for the target locale.
**Fix:** Compute segments on the lowered string's index only when `len(text.lower()) == len(text)`; otherwise return `(text, "", "")` (no highlight).

### IN-04: dictionary_rows.html depends on undefined context variables

**File:** `app/templates/partials/dictionary_rows.html:3,24`, `app/routes/dictionary.py:23,51-55`
**Issue:** The GET page and the add handler never pass `error_entry_id`/`error_form`, so the partial relies on Jinja's silent `Undefined` being falsy. It works today, but switching the environment to `StrictUndefined` (a common hardening step) would break both render paths.
**Fix:** Add `"error_entry_id": None, "error_form": None` to the contexts in `dictionary_page` and `dictionary_add`.

### IN-05: dictionary_lookup queries the DB even when the result is discarded

**File:** `app/routes/dictionary.py:36-38`
**Issue:** `lookup(session, code)` runs before the `name.strip()` guard, so every keystroke-debounced request with a filled name still hits the DB only to return 204.
**Fix:** Check `if name.strip(): return Response(status_code=204)` first, then perform the lookup.

### IN-06: No web test covers the dictionary validation-error response path

**File:** `tests/test_dictionary.py:119-134`
**Issue:** Web tests only post valid dictionary data; the 422 error-partial branch of `dictionary_add`/`dictionary_update` is exercised solely at service level. This gap is exactly why CR-01 (invisible errors in the browser) went undetected while the suite stayed green.
**Fix:** Add web tests posting a blank and a duplicate code to `/dictionary` and `/dictionary/{id}`, asserting both the status code contract chosen for CR-01 and the presence of the RU error message in the swapped partial.

---

_Reviewed: 2026-07-08T19:10:14Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
