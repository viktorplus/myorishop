---
phase: 18-two-price-model-consolidation
plan: 05
subsystem: ui
tags: [jinja2, fastapi, htmx, pricing, labelling]

# Dependency graph
requires:
  - phase: 18-02
    provides: "catalog_cents refs already removed from catalog service/export/product-form surfaces; latest_price reference block preserved for relabeling"
  - phase: 18-03
    provides: "catalog price removed from the receipt slice"
provides:
  - "Unified ДЦ/ПЦ price labels on the product card (cost/sale fields + the surviving latest_price reference block) and on catalog_detail.html — same two names everywhere (D-19)"
  - "min_sale regrouped beside the low-stock threshold and reworded as a guardrail, not a price name (D-21) — id/name/value binding and PRICE-01 logic untouched"
  - "D-09 caveat on the latest_price reference block: it is the code's LAST catalog appearance, not today's price"
  - "product_new accepts ?code=: redirects to the existing product's edit page if the code is already live, else prefills the code field on the new-product form (D-18)"
  - "catalog_detail.html per-row «изменить цену» link -> /products/new?code={{ entry.code }}; app/routes/catalogs.py stays read-only"
affects: [18-07, 18-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-18 pattern: a read-only reference view (catalog_detail) never gets an inline edit — it links to the writable entity's own editor route instead, since CatalogPrice is a published historical fact wiped on every re-import"

key-files:
  created: []
  modified:
    - app/templates/pages/product_form.html
    - app/templates/pages/catalog_detail.html
    - app/routes/products.py
    - tests/test_catalogs_feature.py

key-decisions:
  - "Exact ДЦ/ПЦ wording locked for 18-07/18-08 to mirror: cost field label 'ДЦ — закупочная цена', sale field label 'ПЦ — цена продажи'; latest_price reference block prefixes its two numbers with 'ПЦ'/'ДЦ'; catalog_detail's two price column headers are exactly 'ПЦ' and 'ДЦ'."
  - "min_sale's new label reads 'Порог минимальной цены продажи' — kept the word 'Порог' (threshold) to match the low-stock-threshold framing directly above it, without touching the field's id/name/value logic."
  - "product_new's redirect for an existing code uses RedirectResponse's default 307 (no explicit status_code) rather than 303, since this is a GET->GET navigation (no form resubmission concern), unlike the existing POST-redirect-GET 303 pattern used elsewhere in this file."

patterns-established:
  - "D-18 pattern: a read-only reference view never gets an inline edit — it links to the writable entity's own editor route instead."

requirements-completed: [PROD-05, PROD-07]

# Metrics
duration: ~25min
completed: 2026-07-16
---

# Phase 18 Plan 05: Unify ДЦ/ПЦ Labels + Catalog-Detail «изменить цену» Summary

**Relabeled the product card and catalog-detail page to name exactly two prices — ДЦ and ПЦ — identically everywhere, regrouped `min_sale_cents` as a guardrail beside the low-stock threshold with zero logic change, and closed the dictionary/catalog write-back gap by linking catalog-detail's «изменить цену» to the editable product card via a new `?code=` param on `/products/new`.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-16T11:57:30+02:00 (approx, right after wave-2 tracking commit)
- **Completed:** 2026-07-16T12:07:55Z
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments
- `app/templates/pages/product_form.html`: cost/sale labels relabeled to «ДЦ — закупочная цена» / «ПЦ — цена продажи»; `min_sale` moved beside the low-stock threshold and reworded to «Порог минимальной цены продажи» (guardrail framing, D-21) with its `id`/`name`/value-binding/logic completely unchanged and no `data-ref-cents` added; the surviving `latest_price` reference block (Pitfall 6 guard from plan 18-02) relabeled to ПЦ/ДЦ and given the D-09 caveat that it reflects the code's LAST catalog appearance, not today's price.
- `app/templates/pages/catalog_detail.html`: header columns renamed «ПЦ»/«ДЦ» (identical wording to the product card); each product row now has an «изменить цену» link to `/products/new?code={{ entry.code }}` (autoescaped, no `| safe`).
- `app/routes/products.py`: `product_new` accepts an optional `code` query param — redirects (307) to `/products/{id}/edit` when a live product already has that code, otherwise renders the new-product form with the code field prefilled. `app/routes/catalogs.py` was not touched — it stays read-only per D-18.
- `tests/test_catalogs_feature.py`: 4 new tests — catalog-detail shows ПЦ/ДЦ + the «изменить цену» link/href, `/products/new?code=` redirects to the existing product's edit page, prefills the code field when the code is new, and the no-`code` fallback still serves the plain blank form.

## Task Commits

Each task was committed atomically:

1. **Task 1: Unify the product-card price labels to ДЦ/ПЦ, add the D-09 caveat, and regroup min_sale as a guardrail (D-19/D-21)** - `abf41a7` (feat)
2. **Task 2: Catalog-detail ДЦ/ПЦ labels + «изменить цену» → product card (D-18/D-19)** - `3e64791` (feat)

## Files Created/Modified
- `app/templates/pages/product_form.html` - ДЦ/ПЦ relabel on cost/sale, min_sale regrouped as a guardrail beside low-stock threshold, latest_price block relabeled + D-09 caveat added
- `app/templates/pages/catalog_detail.html` - ПЦ/ДЦ header relabel, «изменить цену» link added per row
- `app/routes/products.py` - `product_new` extended to accept `?code=` (redirect-or-prefill, D-18)
- `tests/test_catalogs_feature.py` - 4 new tests covering the D-18 link, redirect, prefill, and no-code fallback

## Decisions Made
- See `key-decisions` in frontmatter — exact ДЦ/ПЦ wording and the min_sale guardrail label are locked for plans 18-07/18-08 to mirror without re-litigating wording.
- `product_new`'s existing-code redirect uses plain `RedirectResponse` (default 307), distinct from the file's existing POST-redirect-GET 303 convention, since it is itself a GET request being redirected — no form-resubmission semantics apply.

## Deviations from Plan

None - plan executed exactly as written. No auto-fixes were required; the two pre-existing `ruff` E501 warnings encountered in `app/routes/products.py:129` and `tests/test_catalogs_feature.py:122` were both confirmed (via `git diff`) to be untouched by this plan's edits, and the `products.py:129` one was already logged to `deferred-items.md` by plan 18-02.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The locked ДЦ/ПЦ wording (`ДЦ — закупочная цена`, `ПЦ — цена продажи`, catalog_detail headers `ПЦ`/`ДЦ`) is ready for plans 18-07/18-08 to reuse verbatim when adding `data-ref-cents`/price-cue wiring — those plans must NOT add `data-ref-cents` to `min_sale` (confirmed absent here).
- `product_new`'s new `?code=` param is a stable integration point: any future page needing "open the product card for this code" can link to `/products/new?code=...` directly.
- Full regression: `uv run pytest -q` — 695 passed, 0 failed. `uv run pytest tests/test_sales.py tests/test_mobile_sales.py -q` (PRICE-01 sample) — 74 passed, confirming min_sale's guardrail behavior is unchanged.
- No blockers.

## Known Stubs

None.

## Threat Flags

None — the `?code=` param is resolved via a bound-parameter ORM query (`Product.code == code_clean`) exactly like every other code-lookup route in this codebase; `entry.code` in the new catalog_detail link renders through Jinja2's default autoescaping (no `| safe`). No new endpoints, auth paths, or schema changes were introduced; the redirect target (`/products/{id}/edit`) is an existing route.

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*
