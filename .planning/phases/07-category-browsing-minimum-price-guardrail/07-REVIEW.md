---
phase: 07-category-browsing-minimum-price-guardrail
reviewed: 2026-07-10T21:39:36Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - app/routes/categories.py
  - app/templates/pages/categories.html
  - app/services/catalog.py
  - app/templates/base.html
  - app/main.py
  - tests/test_catalog.py
  - alembic/versions/0006_product_min_sale_price.py
  - app/models.py
  - app/services/receipts.py
  - app/templates/partials/price_history.html
  - app/templates/pages/product_form.html
  - app/routes/products.py
  - app/templates/partials/sale_price_warning.html
  - app/services/sales.py
  - app/routes/sales.py
  - app/templates/partials/sale_form.html
  - tests/test_sales.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-07-10T21:39:36Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the category-browsing page (`/categories`, CAT-01) and the minimum-sale-price
guardrail (PRICE-01: schema, capture on the product form, and the sale-time floor check).
The full test suite for these two slices (77 tests in `test_catalog.py` + `test_sales.py`)
passes, and the diff itself is small, well-documented, and internally consistent — the new
`min_sale_cents` column is wired through `create_product`/`update_product`/`_PRICE_FIELDS`,
price history, the product form, and `products_by_category` correctly excludes deleted
products and sorts "Без категории" last, matching the UI spec exactly (no extra "Минимальная"
column — that omission is intentional per `07-UI-SPEC.md`).

The one real defect found is in `app/services/sales.py`: the per-line **sale price** accepted
at checkout is parsed with a bare `to_cents()` call that has no negative-value guard, unlike
every other money field in the codebase (`parse_optional_cents` explicitly rejects `< 0`).
Because the minimum-price guardrail this phase ships is *optional* (unset by default per D-06),
a negative sale price on a product with no floor configured sails through with **zero**
warnings and is written straight into the ledger — directly undermining the stated purpose of
PRICE-01 ("prevent selling too cheap"). This is flagged as the phase's one Critical finding.

A few secondary issues (category-grouping case sensitivity, an unguarded quantity parse in
`receipts.py`, and the shared-confirm design for stacked warnings) are recorded below as
Warnings/Info for completeness.

## Critical Issues

### CR-01: Sale-line price accepts negative values, silently bypassing the price-floor guardrail

**File:** `app/services/sales.py:99-107`
**Issue:** Every other money input in the codebase (`cost`, `sale`, `catalog`, `min_sale` on
the product card) is parsed with `parse_optional_cents`, which explicitly rejects negative
amounts with `PRICE_ERROR` (see `app/services/catalog.py:37-39`, WR-04). The actual
transaction price entered on a sale-basket line, however, is parsed inline in
`register_sale` with a bare `to_cents()` call and only catches `ValueError`:

```python
price_text = price_raw.strip()
price_cents: int | None = None
if not price_text:
    errors[f"price-{i}"] = PRICE_REQUIRED_ERROR
else:
    try:
        price_cents = to_cents(price_text)
    except ValueError:
        errors[f"price-{i}"] = catalog.PRICE_ERROR
```

`to_cents("-5")` parses successfully (`Decimal` accepts a leading `-`) and returns `-500` — no
exception is raised, so nothing rejects it here. The value then flows into the
`below_minimum` check:

```python
if line["product"].min_sale_cents is not None
and line["price_cents"] < line["product"].min_sale_cents
```

D-06 (this phase, by design) means `min_sale_cents` is `None` for every product until an
operator explicitly sets a floor. For the common case of no floor configured, a negative
`price_cents` never trips this check (the whole block is skipped), and the sale proceeds to
write a `sale` operation with a negative `unit_price_cents` and a negative `total_cents`
(`app/routes/sales.py`'s success message even echoes `saved.total_cents`, which can display a
negative total). This is a real data-integrity gap: it lets negative "revenue" be recorded on
a whim (typo or otherwise), silently corrupting profit/report figures, and it means the
guardrail this phase implements cannot protect a product that has no floor set — precisely the
default state for every newly created product. `07-UI-SPEC.md` dismisses this as "moot"
("selling at a negative-impossible price is moot") but the code does not actually enforce that
assumption — there is no client-side `min="0"` (the input is plain `type="text"`) and no
server-side floor of zero.
**Fix:** Reject negative amounts the same way `parse_optional_cents` does, e.g.:
```python
else:
    try:
        price_cents = to_cents(price_text)
    except ValueError:
        errors[f"price-{i}"] = catalog.PRICE_ERROR
    else:
        if price_cents < 0:
            errors[f"price-{i}"] = catalog.PRICE_ERROR
            price_cents = None
```
Add a regression test asserting a negative `price[]` value on `/sales` is rejected with 0
writes, independent of whether `min_sale_cents` is set.

## Warnings

### WR-01: Category grouping is case-sensitive — visually identical labels can silently split into separate groups

**File:** `app/services/catalog.py:416-435`
**Issue:** `products_by_category` groups products by the raw `p.category or ""` string:
```python
by_category: dict[str, list[Product]] = {}
for p in products:
    by_category.setdefault(p.category or "", []).append(p)
named = sorted(k for k in by_category if k)
```
Because `category` is free text (no normalization beyond `.strip()` at write time in
`create_product`/`update_product`), two products saved with `category="Уход"` and
`category="уход"` (a plausible typo, since the datalist suggestion from `category_options()`
is also exact-match) will now render as **two separate `<h2>` groups** on `/categories` that
look identical to the operator except for case — one of the exact "silently split" failure
modes the phase's own D-04 note (uncategorized bucket "never split") warns against for the
NULL/empty case, but does not address for case variants of a real category name. This is a
new, more visible surface for a pre-existing free-text quirk, since `/categories` is the first
screen that renders categories as structural headings rather than an inline column value.
**Fix:** Normalize the grouping key (e.g. `p.category.strip().lower()` for the dict key while
keeping the first-seen original casing for display), or normalize `category` at write time in
`create_product`/`update_product` (e.g. title-case or lower-case canonicalization) so the
free-text field can't produce visually-duplicate groups.

### WR-02: Receipt quantity parsing lacks the `isascii()` guard used elsewhere, can raise an uncaught `ValueError`

**File:** `app/services/receipts.py:57-58`
**Issue:**
```python
qty_text = qty_raw.strip()
qty = int(qty_text) if qty_text.isdigit() else 0
```
`str.isdigit()` returns `True` for non-ASCII "digit" characters (e.g. superscript `²`,
`U+00B2`) that `int()` cannot parse, raising an uncaught `ValueError`. `app/services/sales.py`
explicitly guards against exactly this class of input (see the `WR-01` comment at
`app/services/sales.py:88-93`: "isdigit() alone accepts non-ASCII 'digit' characters ... guard
with isascii() first"), but the equivalent line in `receipts.py` was never updated with the
same guard. The route (`app/routes/receipts.py:86-96`) wraps `register_receipt` in a broad
`except Exception`, so this does not surface as a raw 500 — but it does turn what should be
the specific `QTY_ERROR` ("Укажите количество...") into the generic
`SAVE_FAILED_ERROR` ("Не удалось сохранить...") and silently discards the operator's other
correctly-typed field values from the echoed form in that exceptional path since `form_echo`
is fine but the specific field error is lost. This is pre-existing (not touched by this
phase's diff) but lives in a file explicitly in this review's scope and is directly analogous
to a bug this same phase's sibling function (`register_sale`) already fixed.
**Fix:** Mirror the sales.py guard:
```python
qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
```

### WR-03: Oversell and price-floor warnings share a single `confirm=1` flag — one click silently overrides both guardrails at once

**File:** `app/services/sales.py:129-175`, `app/templates/partials/sale_price_warning.html:15-18`
**Issue:** When a basket trips both the oversell check and the price-floor check, both
warnings render in the same response (correct — Pitfall 2), but both the oversell "Продать
всё равно" button and the price-floor "Продать всё равно" button re-POST the identical
`confirm=1` flag, and `register_sale` skips *both* checks together once `confirm == "1"`
(`app/services/sales.py:129`, `if confirm != "1":` wraps both the oversell and the
below-minimum computation). An operator who only intends to acknowledge an oversell (e.g.
"yes, I know stock is low") has no way to confirm only that and still be re-warned about a
price that is below the configured floor on the same basket — the single click silently
authorizes selling below cost too. This is tested and documented as the intended behavior
(`test_web_sale_both_warnings_stack_and_single_confirm_resolves_both`), so it is a deliberate
design choice rather than an implementation slip, but it weakens the practical protection the
price-floor guardrail is meant to provide in the (Pitfall-2-documented) case where both
warnings co-occur.
**Fix:** Consider a distinct confirmation flag per guardrail (e.g.
`confirm_oversell=1`/`confirm_price=1`) so acknowledging one does not silently waive the
other, or at minimum make the combined-warning copy explicit that confirming overrides *both*
checks simultaneously.

## Info

### IN-01: `/categories` has no row cap, unlike every other catalog listing

**File:** `app/services/catalog.py:416-435`, `app/routes/categories.py:13-17`
**Issue:** `list_products`/`search_products` cap results at 20 rows; `products_by_category`
has no `.limit()` and renders every active product across every category group on one page.
This matches the explicit UI-SPEC intent ("no filter/search this phase... a static page load
already satisfies the requirement"), so it is not a defect against the current spec, but it is
worth flagging for awareness as the catalog grows — a large catalog will produce one very long
page with no way to jump to a category.
**Fix:** No action required for this phase; note for a future phase if catalog size grows
(anchor links per category heading, or pagination).

---

_Reviewed: 2026-07-10T21:39:36Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
