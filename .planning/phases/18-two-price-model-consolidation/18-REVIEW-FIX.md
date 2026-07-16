---
phase: 18-two-price-model-consolidation
fixed_at: 2026-07-16T00:00:00Z
review_path: .planning/phases/18-two-price-model-consolidation/18-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 18: Code Review Fix Report

**Fixed at:** 2026-07-16
**Source review:** .planning/phases/18-two-price-model-consolidation/18-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (WR-01, WR-02, WR-03 — Critical: 0, Warning: 3)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### WR-01: Zero-cent reference price silently disables the colour cue in 6 of 8 templates

**Files modified:** `app/templates/partials/receipt_price_inputs.html`, `app/templates/mobile_partials/receipts_step_details.html`, `app/templates/partials/sale_batch_pick.html`, `app/templates/partials/sale_lookup.html`, `app/templates/partials/sale_row.html`, `app/templates/mobile_partials/sale_step_qty_price.html`
**Commit:** cd2b7ee
**Applied fix:** Dropped the redundant `and ref_cents`/`and ref_cost_cents`/`and ref_sale_cents`/`and ref_pc_cents` truthy check in all six templates, leaving only `{% if <var> is not none %}`, matching the two call sites (`product_form.html`, `product_price_autofill.html`) that already did this correctly. A catalog reference price of exactly 0 cents now correctly stamps `data-ref-cents="0"` instead of silently omitting the attribute.

### WR-02: The colour cue never attaches to a price field the operator already typed, on the live code-lookup (OOB) path

**Files modified:** `app/routes/receipts.py`, `app/routes/sales.py`, `app/templates/partials/receipt_form.html`, `app/templates/partials/sale_form.html`
**Commit:** 0121c15
**Applied fix:** Investigated both suggested fix options. Option (a) (always render `data-ref-cents` on the OOB fragment even for fields excluded from `fill_fields`/`fill_price`) does not actually solve the gap on its own: the client-side `hx-on::oob-before-swap` guards in `receipt_form.html`/`sale_form.html` block the *entire* OOB fragment (value + `data-ref-cents` together) whenever the target field already has a non-empty value — which is precisely the scenario WR-02 describes. Decoupling value-fill from cue-stamp at the DOM level would require re-running the value-protecting check on every keystroke, widening the exact race window ("an in-flight response never destroys operator input") that guard exists to close, on a live money-input path. Given the cue is purely advisory/cosmetic (confirmed in REVIEW.md's Summary — no data-integrity, security, or money-storage impact) and the affected surface is narrow (only the AJAX live-typing path; full-page loads and every mobile wizard step are unaffected), applied fix option (b): added clear code comments at `receipts.py:141` (both `product`/`catalog` branches share the same `fill_fields` gate), `sales.py` (both `sale_lookup` and `sale_batch_pick`), and the two `oob-before-swap` guard sites in `receipt_form.html`/`sale_form.html`, documenting this as an accepted, narrow limitation and explaining why splitting the guard was rejected. No behavior change; no new race-condition risk introduced.
**Note:** This is a documented/accepted limitation, not a behavioral code change — flagging for human awareness per the reviewer's own two-option framing (code fix vs. documented limitation). No further verification action needed beyond confirming the comments accurately describe the existing (unchanged) behavior.

### WR-03: `style.css`'s stated accessibility design (text badge) for the price cue isn't implemented

**Files modified:** `app/static/style.css`
**Commit:** 5181af1
**Applied fix:** Corrected the comment above `.price-below`/`.price-above` to accurately describe what was actually shipped (border + tint only, no text/icon badge) and explicitly noted the WCAG 1.4.1 (Use of Color) compliance claim is NOT met as currently implemented, rather than leaving the stale claim in place. Did not add a new visually-rendered text/icon badge — that would be a UI feature addition (touching `price-cue.js` and up to 8 templates) beyond the scope of a documentation/implementation-mismatch fix; left as a follow-up if WCAG compliance is actually required for this cue.

## Skipped Issues

None — all in-scope findings (WR-01, WR-02, WR-03) were fixed.

---

_Fixed: 2026-07-16_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
