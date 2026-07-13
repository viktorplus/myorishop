---
phase: 12-code-name-autofill
reviewed: 2026-07-13T00:00:00Z
depth: standard
files_reviewed: 24
files_reviewed_list:
  - app/routes/dictionary.py
  - app/routes/mobile_receipts.py
  - app/routes/mobile_sales.py
  - app/routes/mobile_transfers.py
  - app/routes/products.py
  - app/routes/receipts.py
  - app/routes/sales.py
  - app/services/receipts.py
  - app/static/style.css
  - app/templates/mobile_partials/receipts_step_batch.html
  - app/templates/mobile_partials/receipts_step_details.html
  - app/templates/mobile_partials/sale_step_batch.html
  - app/templates/mobile_partials/sale_step_qty_price.html
  - app/templates/mobile_partials/transfers_step_batch.html
  - app/templates/mobile_partials/transfers_step_dest.html
  - app/templates/partials/receipt_lookup.html
  - app/templates/partials/sale_lookup.html
  - app/templates/partials/sale_name_field.html
  - app/templates/partials/sale_name_search.html
  - app/templates/partials/sale_row.html
  - tests/test_mobile_receipts.py
  - tests/test_mobile_sales.py
  - tests/test_mobile_transfers.py
  - tests/test_receipts.py
  - tests/test_sales_search.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-07-13T00:00:00Z
**Depth:** standard
**Files Reviewed:** 24
**Status:** issues_found

## Summary

This phase formalizes several ad-hoc "code -> name/price autofill" behaviors
(dictionary lookup, catalog-price lookup, sales name->code search, mobile
receipt price carry-forward) into permanent routes/templates, and threads a
resolved product/dictionary `name` through the mobile transfer wizard.

The diff was checked against its actual git history (`a058bac...^..HEAD`) so
findings below are scoped to lines this phase touched, not pre-existing code.
One BLOCKER was found: the mobile receipt wizard silently discards an
operator's step-3 price edits on a "Назад → Далее" round trip through step 2,
because step 2's handler was changed to *recompute* cost/sale/catalog from
the product/catalog lookup on every render instead of honoring whatever the
operator already typed. Three further issues (all WARNING/INFO) affect
correctness of user-facing hint text, a dead code path left over from a
source-value rename, and a missing input-validation guard that the same file
already applies to its sibling routes.

## Critical Issues

### CR-01: Mobile receipt wizard loses operator-typed prices on a step-3 → step-2 → step-3 round trip

**File:** `app/routes/mobile_receipts.py:85-124` (interacting with `app/templates/mobile_partials/receipts_step_batch.html:9-14` and `app/templates/mobile_partials/receipts_step_details.html:16-27`)

**Issue:** `mobile_receipt_step_batch` (step 2, "Партия") was changed in this
phase to always render fresh `cost`/`sale`/`catalog` hidden inputs, computed
by re-running `lookup_prefill(session, code_clean)` and reading the
product's/catalog's own stored prices:

```python
result = lookup_prefill(session, code_clean) if code_clean else None
...
prices = result["prices"] if result and result["prices"] else {}
context = {
    ...
    "cost": format_cents(prices["cost"]) if prices.get("cost") is not None else "",
    "sale": format_cents(prices["sale"]) if prices.get("sale") is not None else "",
    "catalog": (format_cents(prices["catalog"]) if prices.get("catalog") is not None else ""),
    ...
}
```

The route's signature only accepts `code`, `warehouse_id`, `name` as `Form(...)`
— it never reads a posted `cost`/`sale`/`catalog` value, so anything the
operator typed for those fields is discarded, not merely re-validated.

Reachable flow:
1. Step 1 → step 2 for a known product (or an unknown code that partially
   matches a Dictionary/CatalogPrice row) — step 2 renders hidden
   `cost`/`sale`/`catalog` fields pre-filled from the product/catalog data
   (or blank for a fully unknown code).
2. Operator taps "Далее" → step 3 ("Количество и цены"), where those values
   populate the *visible*, editable `cost`/`sale`/`catalog` inputs
   (`receipts_step_details.html:16-27`). The operator edits, say, `sale`
   from `10,00` to `20,00`.
3. Operator taps "Назад" (`receipts_step_details.html:43`:
   `hx-post="/m/receipts/step/batch" hx-include="closest form"`) — this
   re-POSTs the *entire* persistent form, including `sale=20,00`, to
   `/m/receipts/step/batch`.
4. That handler ignores the posted `sale` value entirely (it isn't declared
   as a parameter) and recomputes step 2's hidden `sale` field from the
   product's stored `sale_cents` (`10,00`) — or blank, for an
   unknown/catalog-only code, since `lookup_prefill` returns no `sale` there.
5. Operator taps "Далее" again → step 3 now shows `10,00` (or blank), and the
   operator's `20,00` edit is gone with no warning.

This is a real data-loss risk for user input (the exact scenario an operator
performs when double-checking the batch before confirming a receipt), and it
is new to this phase — before this diff, step 2 rendered no
`cost`/`sale`/`catalog` hidden fields at all (see
`git diff a058bac...^ HEAD -- app/templates/mobile_partials/receipts_step_batch.html`).
No test in `tests/test_mobile_receipts.py` exercises the step3→step2→step3
round trip, so this regression is untested.

**Fix:** Either (a) stop step 2 from carrying `cost`/`sale`/`catalog` at all
(let step 3 own those fields exclusively, the way it did before this phase),
or (b) accept them as `Form("")` inputs on `mobile_receipt_step_batch` and
apply the same "fresh lookup wins over a stale typed value, otherwise keep
what the operator already has" rule already used for `name` in the same
function:

```python
cost: str = Form(""),
sale: str = Form(""),
catalog: str = Form(""),
...
resolved_cost = format_cents(prices["cost"]) if prices.get("cost") is not None else ""
final_cost = resolved_cost or cost.strip()
# ...repeat for sale/catalog, mirroring final_name = resolved_name or name.strip()
```

## Warnings

### WR-01: Receipt lookup claims "название подставлено" even when no name was filled

**File:** `app/routes/receipts.py:134-145`, `app/services/receipts.py:288-299`, `app/templates/partials/name_input.html:11`

**Issue:** This phase merged the old "dictionary" source into a new
"catalog" source that can match on a `CatalogPrice` row alone, with no
`Dictionary` entry:

```python
entry = dictionary_lookup(session, code)
latest = latest_price_for_code(session, code)
if entry is not None or latest is not None:
    return {"source": "catalog", "name": entry.name if entry is not None else None, ...}
```

When `entry` is `None` (a CatalogPrice-only match), `receipt_lookup` sets
`context["name"] = result["name"] or ""` (blank) but still sets
`hint = CATALOG_FILL_HINT = "Цена и название подставлены из каталога — можно изменить."`
and always renders `name_input.html` with `autofilled = True` (hardcoded at
`receipt_lookup.html:7`, unconditional regardless of whether a name was
actually available). The operator sees the name field swapped in with
`data-autofilled="true"` and a hint claiming the name was filled, while the
field is actually empty — misleading, and specifically not covered by
`test_web_lookup_catalog_source_price_only_fills_cost_and_catalog`, which
only asserts on the price fields.

**Fix:** Only claim the name was autofilled when it actually was, e.g. pass
`autofilled = bool(result["name"])` for the name fragment (independent of
whether price fields fill), or split the hint so the "название" clause is
omitted when `result["name"]` is `None`.

### WR-02: Dead `else` branch left over from the "dictionary" → "catalog" source rename

**File:** `app/routes/receipts.py:146-150`

**Issue:** `lookup_prefill` (services/receipts.py) now only ever returns
`source == "product"`, `source == "catalog"`, or `None` — the old
`"dictionary"` source was removed by this phase's diff. The route's
`if/elif/else` still carries the old fallback:

```python
elif result["source"] == "catalog":
    ...
else:
    fill_fields = []
    hint = ""  # name_input.html falls back to the dictionary wording
    chooser = {"zero_warehouses": False, "batches": [], "code_entered": False}
    include_chooser = False
```

Since `result` is never `None` at this point (checked earlier) and no third
source value is ever produced, this `else` is unreachable dead code, and its
comment ("falls back to the dictionary wording") refers to a source value
that no longer exists — likely to confuse a future maintainer into thinking
a `"dictionary"`-only path still exists.

**Fix:** Remove the dead `else` branch (or replace with an explicit
assertion/log if defensive code is desired), and drop the stale comment.

### WR-03: New `sale_name_field.html` hx-vals is unescaped JSON, and `/sales/lookup`'s `row` isn't validated like its sibling routes

**File:** `app/templates/partials/sale_name_field.html:15`, `app/routes/sales.py:94-165` (`sale_lookup`)

**Issue:** This phase adds a new shared partial that is now included both by
`sale_row.html` (`row_id` always server-validated: either `_ROW_ID_RE`-matched
or freshly generated by `new_id()`) **and** by `sale_lookup.html`
(`sale_lookup.html:14`, wired in this same phase — previously the name cell
had no `hx-vals` at all). The partial builds its `hx-vals` by raw string
interpolation instead of `| tojson`:

```jinja
hx-vals='{"row": "{{ row }}"}'
```

Every other route in `app/routes/sales.py` that echoes a client-supplied
`row` value into rendered markup validates it first:

```python
row = row.strip()
if row and not _ROW_ID_RE.fullmatch(row):
    row = ""
```

(`sale_search_name`, `sale_batch_pick`, `sale_row` all do this — the
`sale_search_name` comment even says "T-12-07: mirrors sale_batch_pick's row
guard".) `sale_lookup` (the route whose response now flows `row` into this
new hx-vals attribute) has **no such guard** — `row: str = ""` is passed to
the template unchanged. A crafted `row` value (e.g. containing `"`)
reaching `/sales/lookup?row=...` produces malformed JSON inside `hx-vals`
once the browser HTML-entity-decodes the attribute, breaking the
name-search widget for that row and — because `hx-vals` values are honored
as extra key/value pairs sent with the next htmx request — allows
injecting extra keys into that request. Jinja's autoescaping prevents this
from becoming a classic markup-breakout/script-injection issue, but it is
still an inconsistency with the file's own established defensive pattern
and an untested gap (no test exercises `/sales/lookup` with a malformed
`row`).

**Fix:** Add the same `row = row.strip(); if row and not _ROW_ID_RE.fullmatch(row): row = ""`
guard to `sale_lookup`, and change `sale_name_field.html` to build `hx-vals`
via `{{ {"row": row} | tojson }}`, matching the pattern already used in
`sale_name_search.html` and `transfers_step_batch.html` in this same phase.

## Info

### IN-01: `_basket_lines`/mobile basket zip silently truncates on array-length mismatch

**File:** `app/routes/mobile_sales.py:246` (and the analogous desktop
`_build_lines`, `app/routes/sales.py:59-79`, already using the shared
`non_blank_lines` helper)

**Issue:** `_basket_lines` zips `code_acc`, `qty_acc`, `price_acc`,
`batch_acc` with `strict=False`, so if the four accumulated arrays ever
drift out of alignment (e.g. a future UI change adds a line without
appending to all four hidden-input groups), the display silently drops the
tail instead of surfacing an error. This is display-only (register_sale is
the actual trust boundary and does its own validation), so it's low risk,
but it diverges from the desktop basket's explicit "index-aligned" comment
convention (`sale_row.html:39-41`, "Pitfall 2") without a similar safeguard
or comment here.

**Fix:** Consider `zip(..., strict=True)` (or an assertion on equal
lengths) so an alignment bug fails loudly during development instead of
silently rendering a truncated basket.

---

_Reviewed: 2026-07-13T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
