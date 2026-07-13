---
phase: 12-code-name-autofill
fixed_at: 2026-07-13T20:14:43Z
review_path: .planning/phases/12-code-name-autofill/12-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-07-13T20:14:43Z
**Source review:** .planning/phases/12-code-name-autofill/12-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (fix_scope = critical_warning: CR-01, WR-01, WR-02, WR-03; IN-01 excluded by scope)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: Mobile receipt wizard loses operator-typed prices on a step-3 → step-2 → step-3 round trip

**Files modified:** `app/routes/mobile_receipts.py`
**Commit:** 6e479ba
**Applied fix:** Added `cost`, `sale`, `catalog` as `Form("")` parameters to `mobile_receipt_step_batch`. Applied the same "fresh lookup wins over stale typed value, otherwise keep what the operator already typed" rule already used for `name` in the same function (`resolved_cost/sale/catalog` from `lookup_prefill`, falling back to `cost.strip()`/`sale.strip()`/`catalog.strip()` when the lookup has no value for that field). This is fix option (b) from REVIEW.md. Verified: all 16 existing `tests/test_mobile_receipts.py` tests pass unchanged (they don't post cost/sale/catalog on this route, so the new params default to `""` and behave identically for those cases); the discard bug on the step3→step2→step3 round trip described in the finding no longer occurs.

### WR-01: Receipt lookup claims "название подставлено" even when no name was filled

**Files modified:** `app/templates/partials/receipt_lookup.html`
**Commit:** a9d42aa
**Applied fix:** Changed `{% with autofilled = True %}` to `{% with autofilled = (name != "") %}` around the shared `name_input.html` include, so the "название подставлено" hint and `data-autofilled="true"` marker are only rendered when `result["name"]` actually resolved to a non-empty value (catalog-source matches with a `CatalogPrice` row but no `Dictionary` entry now correctly show no autofill claim for the name field). Verified: full `tests/test_receipts.py` (48 tests) passes, including `test_web_receipt_name_input_has_autofill_markers` which exercises a real product (source="product", name always present) and is unaffected.

### WR-02: Dead `else` branch left over from the "dictionary" → "catalog" source rename

**Files modified:** `app/routes/receipts.py`
**Commit:** 63083f0
**Applied fix:** Removed the unreachable trailing `else` branch (the stale "falls back to the dictionary wording" fallback) and converted the `elif result["source"] == "catalog":` into the terminal `else:` clause, since `lookup_prefill` only ever returns `source == "product"`, `source == "catalog"`, or `None` (the `None` case is already handled earlier in the function). Added a comment explaining why. Verified: full `tests/test_receipts.py` (48 tests) passes.

### WR-03: New `sale_name_field.html` hx-vals is unescaped JSON, and `/sales/lookup`'s `row` isn't validated like its sibling routes

**Files modified:** `app/routes/sales.py`, `app/templates/partials/sale_name_field.html`
**Commit:** 5ee5959
**Applied fix:** Added the same `row = row.strip(); if row and not _ROW_ID_RE.fullmatch(row): row = ""` guard to `sale_lookup` that `sale_search_name`/`sale_batch_pick`/`sale_row` already use. Changed `sale_name_field.html`'s `hx-vals='{"row": "{{ row }}"}'` to `hx-vals="{{ {'row': row} | tojson }}"`, matching the pattern already used in `transfers_step_batch.html` in this same phase. Verified: `row` is always a plain string (never Jinja `Undefined`) in both callers (`sale_row.html` passes `row_id`, `sale_lookup.html` passes the route's `row` param), so `tojson` is safe; full `tests/test_sales.py` + `tests/test_sales_search.py` (54 tests) pass.

## Skipped Issues

None — all in-scope findings were fixed.

**Out of scope (fix_scope = critical_warning):** IN-01 (`_basket_lines`/mobile basket zip silently truncates on array-length mismatch) was not attempted — it is an Info-severity finding excluded by the configured fix scope.

**Full suite verification:** `python -m pytest -q` — 487 passed, 0 failed (run after all four fixes were applied and committed).

---

_Fixed: 2026-07-13T20:14:43Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
