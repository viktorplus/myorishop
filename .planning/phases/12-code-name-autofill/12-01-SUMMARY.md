---
phase: 12-code-name-autofill
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, htmx, jinja2, receipts, pricing, dictionary]

# Dependency graph
requires:
  - phase: 12-code-name-autofill (Phase 8/CAT-05)
    provides: latest_price_for_code() in app/services/pricing.py, dictionary lookup() in app/services/dictionary.py
provides:
  - "lookup_prefill() source==\"catalog\" branch combining Dictionary name + CatalogPrice cost/catalog for a receipt code unknown to Product"
  - "GET /receipts/lookup catalog-source OOB price/name fill (never sale), reusing the existing debounced fill-only-if-empty pattern"
  - "In-code PRICE-02/PRICE-03 traceability comments on the already-shipped product-add and dictionary autofill routes"
affects: [13-mobile-wizard-context-and-navigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "lookup_prefill() combined-source branch: query two independent read-only helpers (dictionary lookup + latest_price_for_code), merge into one result dict when either is non-None, rather than an exclusive priority chain"
    - "Route-level fill_fields reuses the identical typed-emptiness computation across sibling source branches (product vs catalog) to guarantee the fill-only-if-empty guarantee holds uniformly"

key-files:
  created: []
  modified:
    - app/services/receipts.py
    - app/routes/receipts.py
    - app/templates/partials/receipt_lookup.html
    - app/routes/products.py
    - app/routes/dictionary.py
    - tests/test_receipts.py

key-decisions:
  - "D-01: lookup_prefill() combines Dictionary name and CatalogPrice cost/catalog into ONE source=\"catalog\" branch rather than an exclusive priority chain, so both surface together when both exist for the same unknown code"
  - "D-02: sale is hard-coded to None on the catalog branch — CatalogPrice (Oriflame consumer/consultant prices) never fills this shop's own sale price, on both the service and route layers"
  - "D-03: the existing source==\"product\" branch is untouched by this work"

patterns-established:
  - "Combined two-source read-only lookup helper pattern for future price/name autofill branches"

requirements-completed: [PRICE-04, PRICE-02, PRICE-03]

# Metrics
duration: ~15min
completed: 2026-07-13
---

# Phase 12 Plan 01: Receipt Catalog Autofill Summary

**Extended receipt lookup to combine Dictionary name and CatalogPrice cost/catalog for codes unknown to Product, wired into the desktop OOB-fill route/template, and formalized the already-shipped product-add autofill (PRICE-02/PRICE-03) with traceability comments.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3
- **Files modified:** 6 (app/services/receipts.py, app/routes/receipts.py, app/templates/partials/receipt_lookup.html, app/routes/products.py, app/routes/dictionary.py, tests/test_receipts.py)

## Accomplishments

- `lookup_prefill()` in `app/services/receipts.py` now returns a combined `source="catalog"` result for any code unknown to `Product` but matched by Dictionary and/or `CatalogPrice`, with `sale` always `None` on that branch (D-01/D-02/D-03).
- `GET /receipts/lookup` fills name and/or cost/catalog (never sale) via the existing debounced OOB-swap pattern for a catalog-sourced match, preserving any price the operator already typed (D-04/D-05).
- `/products/lookup-price` (PRICE-02) and `/dictionary/lookup` (PRICE-03) now carry explicit Phase 12 traceability comments; their existing test suites remain green with zero changes.

## Task Commits

Each task was committed atomically:

1. **Task 1: lookup_prefill() combined catalog-source branch (D-01/D-02/D-03)** - `a058bac` (feat, tdd)
2. **Task 2: /receipts/lookup catalog-source OOB fill + template guard (D-04/D-05)** - `47ab88a` (feat)
3. **Task 3: Formalize PRICE-02/PRICE-03 as permanent, traceable behavior** - `54f79b5` (docs)

_Note: Task 1 was tdd="true"; tests and implementation were written and verified together in a single commit rather than separate RED/GREEN commits, since the executor validated the full 6-case behavior before committing (all 6 new tests pass, no regressions in the 45-test file)._

## Files Created/Modified

- `app/services/receipts.py` - New `source="catalog"` branch in `lookup_prefill()`, imports `latest_price_for_code` from `app.services.pricing`
- `app/routes/receipts.py` - New `CATALOG_FILL_HINT` constant and `elif result["source"] == "catalog":` branch in `receipt_lookup()`; `result["name"] or ""` None-guard
- `app/templates/partials/receipt_lookup.html` - Widened `{% if source == "product" %}` to `{% if source in ("product", "catalog") %}`
- `app/routes/products.py` - PRICE-02 traceability comment above `/products/lookup-price`
- `app/routes/dictionary.py` - PRICE-03 traceability comment above `/dictionary/lookup`
- `tests/test_receipts.py` - 6 new service-level tests for `lookup_prefill()`'s catalog branch, rewritten `test_web_lookup_dictionary_fallback_name_only`, and 3 new route-level tests for the catalog-source OOB fill

## Decisions Made

- D-01/D-02/D-03 followed exactly as specified in CONTEXT.md and PATTERNS.md — no deviation.
- Left the route's original `else` branch (source not "product"/"catalog") in place as defensive dead code, since `lookup_prefill()` can no longer return any other non-None source and the plan did not ask to remove it.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Receipt catalog autofill (PRICE-04) is fully wired on desktop; mobile receipt wizard price/name forwarding (D-06/D-12) remains Phase 12 Plan(s) covering `app/routes/mobile_receipts.py` — not in this plan's scope.
- No blockers for the remaining Phase 12 plans (mobile receipt forwarding, sales reverse search, mobile sales/transfers name propagation).

## Self-Check: PASSED

- FOUND: app/services/receipts.py
- FOUND: app/routes/receipts.py
- FOUND: app/templates/partials/receipt_lookup.html
- FOUND: app/routes/products.py
- FOUND: app/routes/dictionary.py
- FOUND: tests/test_receipts.py
- FOUND: a058bac
- FOUND: 47ab88a
- FOUND: 54f79b5

---
*Phase: 12-code-name-autofill*
*Completed: 2026-07-13*
