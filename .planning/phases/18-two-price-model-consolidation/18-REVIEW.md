---
phase: 18-two-price-model-consolidation
reviewed: 2026-07-16T00:00:00Z
depth: standard
files_reviewed: 37
files_reviewed_list:
  - alembic/versions/0014_drop_product_catalog_cents.py
  - app/models.py
  - app/routes/mobile_receipts.py
  - app/routes/mobile_sales.py
  - app/routes/products.py
  - app/routes/receipts.py
  - app/routes/sales.py
  - app/services/catalog.py
  - app/services/export.py
  - app/services/pricing.py
  - app/services/receipts.py
  - app/services/sales.py
  - app/static/price-cue.js
  - app/static/style.css
  - app/templates/base.html
  - app/templates/mobile_base.html
  - app/templates/mobile_partials/receipts_step_batch.html
  - app/templates/mobile_partials/receipts_step_confirm.html
  - app/templates/mobile_partials/receipts_step_details.html
  - app/templates/mobile_partials/sale_step_qty_price.html
  - app/templates/pages/catalog_detail.html
  - app/templates/pages/categories.html
  - app/templates/pages/product_form.html
  - app/templates/partials/product_price_autofill.html
  - app/templates/partials/product_rows.html
  - app/templates/partials/receipt_form.html
  - app/templates/partials/receipt_lookup.html
  - app/templates/partials/receipt_price_inputs.html
  - app/templates/partials/receipt_rows.html
  - app/templates/partials/sale_batch_pick.html
  - app/templates/partials/sale_form.html
  - app/templates/partials/sale_lookup.html
  - app/templates/partials/sale_row.html
  - tests/test_batches.py
  - tests/test_catalog.py
  - tests/test_catalogs_feature.py
  - tests/test_dictionary.py
  - tests/test_export.py
  - tests/test_mobile_receipts.py
  - tests/test_mobile_sales.py
  - tests/test_pricing_feature.py
  - tests/test_receipts.py
  - tests/test_sales.py
  - tests/test_sales_search.py
  - tests/test_search.py
findings:
  critical: 0
  warning: 3
  info: 2
  total: 5
status: issues_found
---

# Phase 18: Code Review Report

**Reviewed:** 2026-07-16
**Depth:** standard
**Files Reviewed:** 37 (per required-reading list; several tests share a module with pre-existing content and were skimmed for phase-18-relevant assertions only)
**Status:** issues_found

## Summary

Phase 18 consolidates product pricing to ДЦ (`cost_cents`)/ПЦ (`sale_cents`), drops `catalog_cents` via migration `0014` (native `DROP COLUMN`, not batch mode — correctly avoids rebuilding the partial unique index `uq_products_code_active`), and adds a client-side, advisory-only reference-price colour cue (`price-cue.js` + `data-ref-cents`).

Money handling stays integer-cents throughout (`Product.cost_cents`/`sale_cents`/`min_sale_cents`, `Operation.unit_cost_cents`/`unit_price_cents`, `CashMovement.amount_cents`) — no floats found in any write path. The migration is deliberately irreversible for the 6 discarded `catalog_cents` values, which is documented and intentional (D-01), not a defect. I found no dangling references to the dropped `catalog_cents` model attribute anywhere in application code (`_PRICE_FIELDS` in `catalog.py` and the `entered` dict in `receipts.py` were both correctly updated) — historical `payload["catalog_cents"]` in old ledger rows and `price_history.html`'s display branch for it are correctly retained as read-only, dict-based (not attribute-based) access, so no `AttributeError` risk. `price-cue.js` is confirmed cosmetic-only: it only toggles CSS classes on `input` events and never reads/writes/blocks form submission.

The issues found are all in the reference-price colour cue itself (a purely additive feature per the plan) — none affect money storage, security, or data integrity. They are UX/consistency gaps in the cue, not correctness bugs in the priced write paths.

## Warnings

### WR-01: Zero-cent reference price silently disables the colour cue in 6 of 8 templates

**File:** `app/templates/partials/receipt_price_inputs.html:13`
Also: `app/templates/mobile_partials/receipts_step_details.html:24,30`, `app/templates/partials/sale_batch_pick.html:28`, `app/templates/partials/sale_lookup.html:27`, `app/templates/partials/sale_row.html:41`, `app/templates/mobile_partials/sale_step_qty_price.html:30`

**Issue:** These six templates gate `data-ref-cents` on:
```jinja
{% if ref_cents is not none and ref_cents %}data-ref-cents="{{ ref_cents }}"{% endif %}
```
The trailing `and ref_cents` truthy-check makes the attribute silently vanish whenever the catalog reference price is exactly `0` cents (Jinja/Python: `0` is falsy) — even though `reference_prices_for_code`/`latest_price_for_code` (`app/services/pricing.py`) never gate on zero and treat `0` as a perfectly valid stored price. A product legitimately priced at 0 (e.g. a promotional/free catalog line) would get no cue at all, contradicting D-08/D-22's stated intent ("ДЦ is never gated on ПЦ's presence — a consultant-only row still yields its ДЦ").

Two other templates touched by the same phase get this right — `app/templates/pages/product_form.html:71,79` and `app/templates/partials/product_price_autofill.html:13,19` use only `{% if ref_cost_cents is not none %}`, with no truthy check. This is an inconsistency introduced within the same phase, not a pre-existing pattern; no test exercises a `consumer_cents`/`consultant_cents` value of `0` to catch it (`tests/test_pricing_feature.py`'s `priced` fixture never seeds a zero price).

**Fix:** Drop the redundant truthy check everywhere, matching the two correct call sites:
```jinja
{% if ref_cents is not none %}data-ref-cents="{{ ref_cents }}"{% endif %}
```

### WR-02: The colour cue never attaches to a price field the operator already typed, on the live code-lookup (OOB) path

**File:** `app/routes/receipts.py:141-146` (desktop `/receipts/lookup`), similarly `app/routes/sales.py` (`sale_lookup`/`sale_batch_pick`)
**File:** `app/templates/partials/receipt_form.html:18-21` (client swap guard)

**Issue:** On the desktop `/receipts/lookup` and `/sales/lookup` / `/sales/batch-pick` live-typing flows, a price field's `data-ref-cents` is only (re-)stamped when the server includes it as an out-of-band fragment — which only happens when that field was empty at request time (`fill_fields = [f for f in ("cost", "sale") if not typed[f].strip()]`), and even then the client-side `hx-on::oob-before-swap` guard blocks the swap if the field has since gained a value. Consequently, if the operator types a price into `cost`/`sale`/`price` *before* the code lookup resolves (a plausible real sequence: paste a known price first, then type/change the code), that field's DOM node never receives `data-ref-cents`, and the colour cue never activates for it — even though the value may genuinely deviate from the catalog reference. This does not affect the full-page/static render path (`receipt_form.html`'s non-OOB `{% with field=... ref_cents=ref_cost_cents %}` block, and every mobile wizard step, which always re-render `ref_cost_cents`/`ref_sale_cents` unconditionally) — only the AJAX partial-fill path is affected. Since the cue is purely advisory this is not a data-integrity bug, but it is a real gap relative to the feature's stated purpose (flag any reference-price deviation).

**Fix:** Either (a) always include `data-ref-cents` on the OOB fragment even when the corresponding price field is excluded from `fill_fields` (the cue-stamp and the value-fill are logically independent per PROD-06/D-08's own design note — the fragment is currently skipped entirely for a non-empty field, killing both at once), or (b) document this as an accepted, narrow limitation of the live-typing path only.

### WR-03: `style.css`'s stated accessibility design (text badge) for the price cue isn't implemented

**File:** `app/static/style.css:289-297`
**Issue:** The comment above `.price-below`/`.price-above` states: *"Border + tint + text badge — colour alone fails WCAG 1.4.1 (Use of Color)..."* but no text badge exists anywhere in the codebase — `price-cue.js:20-22` only toggles `classList` (`price-below`/`price-above`), and no template renders any accompanying text/icon when the class is applied. The actual implementation differentiates the two states purely via `border-color` + `background` (both colour properties), which is exactly the WCAG 1.4.1 failure mode the comment says was avoided. This is a documentation/implementation mismatch, not solely a style nit — the code's own stated compliance rationale is unmet.

**Fix:** Either add a visually-rendered text/icon cue (e.g. a small "выше/ниже справочной" label near the field, shown/hidden by the same class toggle) or correct the comment to accurately describe what was actually shipped (border + tint only) and drop the WCAG 1.4.1 compliance claim if it isn't actually met.

## Info

### IN-01: Dead `"catalog"` label entry in `receipt_lookup.html`

**File:** `app/templates/partials/receipt_lookup.html:15`
**Issue:** `{% set labels = {"cost": ..., "sale": ..., "catalog": "Цена по каталогу"} %}` still defines a `"catalog"` label, but `fill_fields` (computed in `app/routes/receipts.py:145`) is permanently restricted to `("cost", "sale")` since PROD-05 removed the catalog price field from the receipt form — `labels["catalog"]` can never be looked up. Leftover from the two-price consolidation.
**Fix:** Remove the `"catalog"` key from the `labels` dict.

### IN-02: `lookup_prefill` still returns an unused `"catalog"` price key

**File:** `app/services/receipts.py:295`
**Issue:** The `"catalog"` source branch of `lookup_prefill` still builds `"prices": {"cost": ..., "catalog": latest.consumer_cents ..., "sale": ...}`. No caller (`app/routes/receipts.py`, `app/routes/mobile_receipts.py`) ever reads `prices["catalog"]` — only `cost`/`sale` are consumed. It's exercised by name in `tests/test_receipts.py` (e.g. `test_lookup_prefill_catalog_source_price_only`), so removing it requires updating those assertions too. Currently it's harmless but confusing residue from the field removal (PROD-05/Pitfall 1 already explicitly reasons about removing the *field*, but the dict key that mirrors it was left behind).
**Fix:** Drop the `"catalog"` key from the returned dict (and the corresponding assertions in `tests/test_receipts.py`), or add a one-line comment noting it's intentionally kept for parity/back-compat if there's a reason not covered by the read files.

---

_Reviewed: 2026-07-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
