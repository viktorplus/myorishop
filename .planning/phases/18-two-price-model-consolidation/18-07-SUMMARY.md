---
phase: 18-two-price-model-consolidation
plan: 07
subsystem: ui
tags: [jinja2, fastapi, htmx, javascript, pricing, colour-cue]

# Dependency graph
requires:
  - phase: 18-01
    provides: "latest_price_for_code unfiltered (D-22) + reference_prices_for_code contract"
  - phase: 18-05
    provides: "ДЦ/ПЦ label wording locked on product_form.html; min_sale regrouped as a guardrail (no data-ref-cents)"
provides:
  - "app/static/price-cue.js: delegated document input listener toggling .price-below/.price-above from data-ref-cents (D-10/D-12/D-13)"
  - ".price-below/.price-above CSS tokens (D-14): amber #b45309/#fef9e7 below, blue #2563eb/#eff6ff above — blue deliberately distinct from the #e8effd search-match token"
  - "data-ref-cents wired on the product card's cost/sale inputs (never min_sale) and on the OOB autofill fragment (Pitfall 2), plus the D-07 muted 'нет справочной цены' hint"
affects: [18-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "First hand-written first-party static JS file in the repo (app/static/price-cue.js) — a single delegated document-level input listener, no client-side state, loaded via <script defer> duplicated in both standalone base templates"
    - "latest_price is defined and latest_price guard convention extended to gate data-ref-cents rendering safely across routes that do/don't resolve a reference (product_new, product_edit, create/update 422 re-renders)"

key-files:
  created:
    - app/static/price-cue.js
  modified:
    - app/static/style.css
    - app/templates/base.html
    - app/templates/mobile_base.html
    - app/routes/products.py
    - app/templates/pages/product_form.html
    - app/templates/partials/product_price_autofill.html
    - tests/test_pricing_feature.py
    - tests/test_catalog.py

key-decisions:
  - "ref_cost_cents/ref_sale_cents are separate context keys from cost_cents/sale_cents in product_price_lookup's OOB fragment, even though they are numerically identical today (the fill value IS the reference value in the autofill path) — keeps the cue's reference semantics decoupled from the fill-value semantics per the plan's D-08/D-22 instruction, so a future change to one doesn't silently break the other."
  - "The D-07 'нет справочной цены' hint only renders when latest_price is defined AND falsy (not when the key is simply absent from context) — this correctly targets the product_edit GET path and product_new's ?code= path (both always define latest_price, even as None) while staying silent on product_create/product_update's 422 re-render paths, which don't fetch a reference at all and would otherwise show a false hint."

patterns-established:
  - "price-cue.js: one document-level delegated 'input' listener reads data-ref-cents off event.target, covering desktop, mobile, and HTMX-added rows with zero re-initialisation — the template for any future stateless client-side hint in this codebase."

requirements-completed: [PROD-06]

# Metrics
duration: ~20min
completed: 2026-07-16
---

# Phase 18 Plan 07: Reference-Deviation Colour Cue (Product Card) Summary

**Added `price-cue.js` (a single delegated input listener) plus `.price-below`/`.price-above` CSS tokens, wired both base templates to load it, and stamped `data-ref-cents` on the product card's cost/sale inputs and the OOB autofill fragment — never on `min_sale` — closing PROD-06's colour-cue requirement for the product card surface.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-16T12:40:00Z (approx.)
- **Completed:** 2026-07-16T12:58:16Z
- **Tasks:** 2/2
- **Files modified:** 8 (1 created, 7 modified)

## Accomplishments
- `app/static/price-cue.js` created verbatim from research's D-10/D-12/D-13 source: one `document.addEventListener('input', ...)` that reads `data-ref-cents`, computes cents with the same strip+comma→dot parity as `core.py:28`'s `to_cents`, and toggles `.price-below`/`.price-above` — advisory only, never parses for submission.
- `.price-below`/`.price-above` tokens added to `app/static/style.css` near the existing selection-tint block (D-14): amber border `#b45309` on `#fef9e7` below reference, accent-blue border `#2563eb` on `#eff6ff` above — the blue fill is deliberately **not** `#e8effd` (the pre-existing search-match/selection token used at 6 sites, count unchanged by this plan). Extended the file header to name `#b45309` as the phase's 4th global colour role.
- `<script src="/static/price-cue.js" defer></script>` added to both `base.html` and `mobile_base.html` (duplicated verbatim — `mobile_base.html` does not inherit from `base.html`).
- `product_form.html`'s cost (ДЦ) and sale (ПЦ) inputs carry `data-ref-cents` from `latest_price.consultant_cents`/`consumer_cents` respectively, guarded by `latest_price is defined and latest_price`; `min_sale` carries none (Pitfall 8). Added a muted "нет справочной цены" hint for the case where `latest_price` is defined but absent (D-07 — the MAIN path, 6 of 7 live products have no catalog row).
- `product_price_autofill.html`'s OOB `#cost`/`#sale` fragments now also stamp `data-ref-cents`, so the cue survives the `hx-swap-oob` element replacement (Pitfall 2) — verified with a dedicated test.
- `app/routes/products.py`: `product_price_lookup` threads `ref_cost_cents`/`ref_sale_cents` into the OOB context independently of the fill flags; `product_new` resolves `latest_price` for a prefilled `?code=` so the new-product form's cost/sale inputs also get `data-ref-cents` on first render.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create price-cue.js, the cue CSS tokens, and the standalone script tags in both bases** - `8c6f1e5` (feat)
2. **Task 2: Wire data-ref-cents on the product card's ДЦ/ПЦ inputs (never min_sale), OOB-safe; add the D-07 muted hint** - `a3ebbf2` (feat)

## Files Created/Modified
- `app/static/price-cue.js` - New delegated input listener (D-10/D-12/D-13)
- `app/static/style.css` - `.price-below`/`.price-above` tokens (D-14); header extended to name `#b45309`
- `app/templates/base.html` - `<script src="/static/price-cue.js" defer>` added
- `app/templates/mobile_base.html` - same script tag duplicated (standalone template)
- `app/routes/products.py` - `product_price_lookup` threads `ref_cost_cents`/`ref_sale_cents`; `product_new` resolves `latest_price` for `?code=`
- `app/templates/pages/product_form.html` - `data-ref-cents` on cost/sale inputs; D-07 muted hint
- `app/templates/partials/product_price_autofill.html` - OOB `#cost`/`#sale` carry `data-ref-cents`
- `tests/test_pricing_feature.py` - OOB `data-ref-cents` preservation test; `test_product_form_cues_only_dc_and_pc`
- `tests/test_catalog.py` - D-07 no-CatalogPrice-row hint test

## Decisions Made
- See `key-decisions` in frontmatter — `ref_cost_cents`/`ref_sale_cents` kept as distinct context keys from `cost_cents`/`sale_cents`, and the D-07 hint gated on `is defined` (not just falsy) to avoid a false hint on validation-error re-renders.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's acceptance criteria verbatim (research's D-10/D-12/D-13/D-14 code examples landed as specified; 18-PATTERNS.md's Q4 test shape reused directly).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `price-cue.js`, its CSS tokens, and the script tags are live on every page (both desktop and mobile bases) — plan 18-08 (receipt/sale wiring) can attach `data-ref-cents` to its own inputs and the cue will work with zero additional JS/CSS changes.
- The `ref_cost_cents`/`ref_sale_cents` naming convention in OOB fragments and the `latest_price is defined and latest_price` guard pattern are available for 18-08 to reuse on the receipt/sale surfaces.
- Full regression: `uv run pytest -q` — 698 passed, 0 failed (baseline 682 + prior-plan additions + this plan's 3 new tests). `uv run pytest tests/test_sales.py tests/test_mobile_sales.py -q` — 74 passed, confirming PRICE-01's 9 guards are unmodified. `ruff check app/routes/products.py` shows only the pre-existing `products.py:129` E501 (already logged in `deferred-items.md` by plan 18-02) — no new lint issues.
- Manual browser verification of the visual cue (yellow below / blue above / neither at equality) is still outstanding per 18-RESEARCH.md's Wave 0 gaps — `TestClient` does not execute JS. Recommend a `checkpoint:human-verify` pass once 18-08 completes and both surfaces are wired.
- No blockers.

## Known Stubs

None.

## Threat Flags

None — `data-ref-cents` renders an `int` from `CatalogPrice` through Jinja2's default autoescaping (never `| safe`); the cue badge classes are static CSS class names, never interpolated operator text (T-18-XSS mitigated). `price-cue.js` is hand-written first-party code, not a vendored dependency (T-18-SC not applicable). No new endpoints, auth paths, or schema changes were introduced.

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*
