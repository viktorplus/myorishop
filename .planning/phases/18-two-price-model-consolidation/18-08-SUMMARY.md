---
phase: 18-two-price-model-consolidation
plan: 08
subsystem: ui
tags: [jinja2, fastapi, htmx, javascript, pricing, colour-cue, sales, receipts]

# Dependency graph
requires:
  - phase: 18-01
    provides: "reference_prices_for_code(session, code) -> (ДЦ, ПЦ) tuple contract"
  - phase: 18-03
    provides: "Receipt slice free of the catalog price field"
  - phase: 18-06
    provides: "Sale prefill hint constants + sale-only scope wording"
  - phase: 18-07
    provides: "price-cue.js listener + .price-below/.price-above CSS tokens, loaded on both bases"
provides:
  - "ref_cents optional param on partials/receipt_price_inputs.html (covers static + OOB, Pitfall 2)"
  - "data-ref-cents on all receipt (desktop + mobile) and sale (desktop + mobile) ПЦ/ДЦ inputs"
  - "Reference threading via reference_prices_for_code in every receipt + sale render path (routes.py _form_extras, receipt_lookup, mobile_receipt_step_details, sale_lookup, sale_batch_pick, _build_lines, both mobile_sales.py callers of sale_step_qty_price.html)"
affects: [19-products-page-rebuild]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "receipt_price_inputs.html's optional ref_cents param (guarded by `{% if ref_cents is not none and ref_cents %}`, never `| default`) is the single source for BOTH the static form include and the OOB lookup re-render — one param covers both Pitfall-2-prone paths at once, mirroring 18-07's product_price_autofill.html precedent."
    - "Reference values (ref_cost_cents/ref_sale_cents for receipts, ref_pc_cents for sales) are always resolved and threaded INDEPENDENTLY of the fill/echo values in the same context — the cue compares against the code's CATALOG price, never the card's own price or the picked batch's price, even though they are often numerically identical."

key-files:
  created: []
  modified:
    - app/templates/partials/receipt_price_inputs.html
    - app/templates/partials/receipt_form.html
    - app/templates/partials/receipt_lookup.html
    - app/routes/receipts.py
    - app/routes/mobile_receipts.py
    - app/templates/mobile_partials/receipts_step_details.html
    - app/routes/sales.py
    - app/routes/mobile_sales.py
    - app/templates/partials/sale_row.html
    - app/templates/partials/sale_lookup.html
    - app/templates/partials/sale_batch_pick.html
    - app/templates/mobile_partials/sale_step_qty_price.html
    - app/templates/partials/sale_form.html
    - tests/test_receipts.py
    - tests/test_mobile_receipts.py
    - tests/test_sales.py
    - tests/test_mobile_sales.py
    - .planning/phases/18-two-price-model-consolidation/deferred-items.md

key-decisions:
  - "receipts.py's _form_extras() now resolves reference_prices_for_code for every receipt_form.html render path (fresh /receipts/new, 422 re-render, post-success fresh form) — code=\"\" yields (None, None), a first-class D-07 result, so the fresh form shows no cue until a code is looked up."
  - "sales.py's _build_lines() (the 422/warn basket re-render) resolves the reference per echoed line independently — satisfies the must_haves 'desktop rows' criterion even though the plan's action text named only the lookup/batch-pick handlers explicitly; the read_first note on sale_row.html ('data-ref-cents only when a reference is in context') implied the basket-row path also needed the param wired, just gated by whether a reference happens to be known."
  - "Fixed the 2 pre-existing ruff E501 warnings in app/routes/mobile_sales.py (deferred at 18-06) rather than re-deferring them — Task 2's acceptance criteria explicitly requires a clean ruff check on this exact file, and this plan touches it anyway for the qty-price wiring, which is precisely the 'revisit when next touched' trigger 18-06 named."

patterns-established:
  - "Every receipt/sale route that renders a price-bearing fragment threads its reference cents via reference_prices_for_code, independently of any fill logic already present — the template for any future price-cue wiring in this codebase."

requirements-completed: [PROD-06]

# Metrics
duration: ~45min
completed: 2026-07-16
---

# Phase 18 Plan 08: Reference-Deviation Colour Cue (Receipt + Sale Forms) Summary

**Wired `data-ref-cents` onto every remaining ДЦ/ПЦ price input — the desktop receipt form, the desktop sale basket (rows + lookup + batch-pick), and both mobile wizards (receipt step 3, sale qty-price step) — closing PROD-06's colour-cue requirement across the whole app with zero new JS/CSS (reusing plan 18-07's `price-cue.js` and CSS tokens verbatim).**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-07-16 (approx.)
- **Completed:** 2026-07-16
- **Tasks:** 2/3 automatable tasks complete; Task 3 (checkpoint:human-verify) deferred to end-of-phase per `workflow.human_verify_mode = "end-of-phase"`
- **Files modified:** 18 (17 source/test + 1 shared deferred-items.md)

## Accomplishments

- `receipt_price_inputs.html` gained an optional `ref_cents` param (guarded by `{% if ref_cents is not none and ref_cents %}`, never `| default`) — being the single source for BOTH the static form include and the OOB lookup fragment, this one change covers both Pitfall-2-prone render paths at once.
- `receipts.py`'s `_form_extras()` (used by every `receipt_form.html` render) and `receipt_lookup()` (the OOB fragment) both resolve `reference_prices_for_code` independently of source/fill — a ДЦ-only code still cues its ДЦ (D-08/D-22).
- `mobile_receipts.py`'s `mobile_receipt_step_details` (step 3 — the wizard's only visible price surface, D-20) gained a `session` dependency and the same reference resolution; `receipts_step_details.html`'s `#receipt-cost`/`#receipt-sale` inputs now carry `data-ref-cents`.
- Every sale ПЦ `price[]` input across the desktop basket (`sale_row.html`, the lookup OOB fragment `sale_lookup.html`, the batch-pick OOB fragment `sale_batch_pick.html`) and the mobile sale wizard's qty-price step now carries `data-ref-cents = consumer_cents`, threaded independently of the batch/card fill value in `sales.py` (`_build_lines`, `sale_lookup`, `sale_batch_pick`) and `mobile_sales.py` (both callers of `sale_step_qty_price.html`: the batch-step-forward path and the dictionary-only skip-ahead path).
- Fixed 2 pre-existing `ruff` E501 warnings in `mobile_sales.py` (deferred at plan 18-06) since Task 2's acceptance criteria requires a clean `ruff check` on this file and this plan touches it anyway.
- 15 new tests added across 4 test files, asserting the cue on both render paths (static + OOB) for receipts, on lookup/batch-pick/422-basket-re-render/dictionary-skip for sales, the ДЦ-only-row independence case, and the D-07 no-reference silent case.
- Full regression: `uv run pytest -q` — **711 passed, 0 failed** (≥ 682 phase gate satisfied). PRICE-01's guard tests remain green and byte-for-byte unmodified.

## Task Commits

Each task was committed atomically:

1. **Task 1: Receipt cue wiring — ref_cents param + data-ref-cents on desktop + mobile receipt ДЦ/ПЦ inputs (static + OOB)** - `ee4cd37` (feat)
2. **Task 2: Sale cue wiring — data-ref-cents (ПЦ reference) on all sale price[] inputs, desktop + mobile** - `894c723` (feat)

**Plan metadata:** (this commit, following this summary)

## Files Created/Modified

- `app/templates/partials/receipt_price_inputs.html` - Optional `ref_cents` param, guarded `{% if %}`, on both the static and OOB render paths
- `app/templates/partials/receipt_form.html` - Passes `ref_cents = ref_cost_cents`/`ref_sale_cents` into the cost/sale includes
- `app/templates/partials/receipt_lookup.html` - `refs` dict passes `ref_cents = refs[f]` into the OOB fill loop
- `app/routes/receipts.py` - `_form_extras()` and `receipt_lookup()` resolve `reference_prices_for_code` and thread `ref_cost_cents`/`ref_sale_cents`
- `app/routes/mobile_receipts.py` - `mobile_receipt_step_details` gains a `session` dependency + the same reference resolution
- `app/templates/mobile_partials/receipts_step_details.html` - `data-ref-cents` on `#receipt-cost`/`#receipt-sale`
- `app/routes/sales.py` - `_build_lines`, `sale_lookup`, `sale_batch_pick` each resolve `reference_prices_for_code` and thread `ref_pc_cents`/`ref_cost_cents`/`ref_sale_cents` per line/lookup
- `app/routes/mobile_sales.py` - Both `sale_step_qty_price.html` callers thread `ref_pc_cents`; 2 pre-existing E501 warnings fixed
- `app/templates/partials/sale_row.html` - `data-ref-cents` on the `price[]` input (basket rows)
- `app/templates/partials/sale_lookup.html` - `data-ref-cents` on the OOB price fragment
- `app/templates/partials/sale_batch_pick.html` - `data-ref-cents` on the OOB price fragment
- `app/templates/mobile_partials/sale_step_qty_price.html` - `data-ref-cents` on the mobile wizard's only price input
- `app/templates/partials/sale_form.html` - Threads `ref_pc_cents = line.ref_pc_cents` per basket row
- `tests/test_receipts.py` - 4 new tests (OOB cue, ДЦ-only-row, static-path cue via 422, no-code no-cue)
- `tests/test_mobile_receipts.py` - 2 new tests (step 3 cue, no-catalog-row no-cue)
- `tests/test_sales.py` - 4 new tests (lookup cue, no-catalog no-cue, batch-pick cue, 422 basket-row cue)
- `tests/test_mobile_sales.py` - 3 new tests (qty-price cue, no-catalog no-cue, dictionary-skip cue)
- `.planning/phases/18-two-price-model-consolidation/deferred-items.md` - Marked the 18-06 mobile_sales.py E501 items RESOLVED

## Decisions Made

- See `key-decisions` in frontmatter — `_form_extras`/`_build_lines` resolve the reference for every render path rather than only the explicitly-named lookup/batch-pick handlers, satisfying the plan's `must_haves` truths in full; the 2 deferred E501 warnings were fixed rather than re-deferred since this plan's own acceptance criteria demanded a clean `ruff check` on the file it was already touching.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical / acceptance-criteria compliance] Fixed 2 pre-existing ruff E501 warnings in app/routes/mobile_sales.py**
- **Found during:** Task 2 verification (`ruff check app/routes/mobile_sales.py`)
- **Issue:** Two E501 (line too long) warnings deferred at plan 18-06 (lines 218/284, shifted to 224/297 by this plan's insertions) were still present, but Task 2's acceptance criteria explicitly requires `ruff check app/routes/sales.py app/routes/mobile_sales.py` to be clean.
- **Fix:** Wrapped both long lines (`warehouse_name = (...)` assignment and the `"warehouse_name": (...)` dict entry) across multiple lines, no logic change.
- **Files modified:** `app/routes/mobile_sales.py`
- **Verification:** `uv run ruff check app/routes/sales.py app/routes/mobile_sales.py` — all checks passed; `uv run pytest tests/test_sales.py tests/test_mobile_sales.py -q` — 81 passed.
- **Committed in:** `894c723` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (acceptance-criteria compliance, no logic change)
**Impact on plan:** Zero scope creep — the fix was a direct requirement of this plan's own stated acceptance criteria, on a file this plan was already editing for its primary purpose.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Human verification needed (Task 3, deferred to end-of-phase)

Per `workflow.human_verify_mode = "end-of-phase"`, this plan's `checkpoint:human-verify` (Task 3) was NOT halted on — it is recorded here for the phase-level verifier to harvest into the phase UAT file.

**What was built:** The full reference-deviation cue is now wired server-side across every price surface: the product card (plan 18-07), the desktop + mobile receipt forms, and the desktop + mobile sale forms (this plan). `price-cue.js` toggles `.price-below` (amber `#b45309`/`#fef9e7`) and `.price-above` (blue `#2563eb`/`#eff6ff`) as the operator types. `TestClient` does not execute JavaScript, so the colours themselves are verified by eye; server-side, `data-ref-cents` presence/absence and the CSS classes are already asserted by the automated test suite.

**How to verify:**
1. Start the app (`run.bat`) and open a product card for a code WITH a CatalogPrice row. Type a ДЦ below `consultant_cents` -> amber border `#b45309` on `#fef9e7` + «ниже справочной» badge. Type above -> blue border `#2563eb` on `#eff6ff` + «выше справочной». Type exactly equal -> no cue. Repeat on ПЦ against `consumer_cents`.
2. Repeat in the desktop RECEIPT form and the desktop SALE basket (add a line for a priced code).
3. Repeat in the MOBILE receipt wizard and the MOBILE sale wizard (the only two mobile price surfaces — D-20; there is no mobile product card, and none should exist).
4. Confirm the blue is `#eff6ff` and NOT `#e8effd` (the existing search-match/selection tint at 6 sites).
5. Confirm NO cue appears on «Минимальная цена продажи» (Pitfall 8), and that a code with no CatalogPrice row shows the muted «нет справочной цены» hint with no colour (D-07).
6. After a code lookup that OOB-swaps `#cost`/`#sale` (receipt) or the basket's price cell (sale), type again — the cue must still fire (Pitfall 2).

**Resume signal:** Type "approved" if all surfaces cue correctly, or describe what is off (wrong colour, missing cue, cue on min_sale, blue == `#e8effd`).

## Next Phase Readiness

- PROD-06 is now fully wired server-side across every price surface in the app (product card, receipt desktop+mobile, sale desktop+mobile). The only remaining step is the visual (by-eye) sign-off above, deferred to end-of-phase per project config.
- The D-20 interpretation holds throughout: mobile's two price surfaces (receipt wizard step 3, sale wizard qty-price step) are cued; no mobile product card was built (none exists, none was asked for).
- Full regression: `uv run pytest -q` — 711 passed, 0 failed. `uv run pytest tests/test_receipts.py tests/test_mobile_receipts.py tests/test_sales.py tests/test_mobile_sales.py -q` — 157 passed. PRICE-01's 9 guard tests remain green and unmodified.
- No blockers for Phase 19 (Products Page Rebuild).

## Known Stubs

None.

## Threat Flags

None — every `data-ref-cents` attribute renders an `int` (or omits entirely) from `CatalogPrice` via `reference_prices_for_code`, through Jinja2's default autoescaping, never `| safe`. No new endpoints, auth paths, or schema changes were introduced; the two mobile route handlers that gained a `session` dependency (`mobile_receipt_step_details`, already-present in others) only add a read-only lookup, no new write path.

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*

## Self-Check: PASSED

All 17 claimed source/test files and this SUMMARY.md verified present on disk; both task commits (`ee4cd37`, `894c723`) verified present in `git log --oneline`. Full suite: 711 passed, 0 failed.
