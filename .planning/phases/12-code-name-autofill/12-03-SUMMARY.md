---
phase: 12-code-name-autofill
plan: 03
subsystem: ui
tags: [fastapi, jinja2, htmx, sqlalchemy, sales]

# Dependency graph
requires:
  - phase: 02-catalog-search
    provides: search_products()/split_match()/search_view() (app/services/catalog.py) reused verbatim (D-08)
  - phase: 04-sales-basket
    provides: sale_row.html/sale_lookup.html basket-line rendering and the /sales/lookup OOB-swap convention this plan extends
provides:
  - GET /sales/search-name route (debounced name-fragment product search for the sales page)
  - app/templates/partials/sale_name_search.html (click-to-select, mark-highlighted dropdown response fragment)
  - app/templates/partials/sale_name_field.html (shared name-input + dropdown-target fragment, PD-6 pattern)
  - .name-search-list CSS rules
affects: [phase-13-mobile-wizard]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PD-6 shared-partial pattern extended to the sales name field: one source (sale_name_field.html) rendered by both the initial row render and every OOB swap, so debounced hx-get wiring can never be silently dropped by an outerHTML replace"
    - "tojson-embedded JS values inside hx-on:click (matches mobile_partials/batch_card_picker.html's WR-02-fixed convention) used for the dropdown's click-to-select fill"

key-files:
  created:
    - app/templates/partials/sale_name_search.html
    - app/templates/partials/sale_name_field.html
    - tests/test_sales_search.py
  modified:
    - app/routes/sales.py
    - app/templates/partials/sale_row.html
    - app/templates/partials/sale_lookup.html
    - app/static/style.css

key-decisions:
  - "3-character trigger threshold enforced in the new route, not inside search_products() (RESEARCH Pitfall 5) — search_products()'s own empty-query fallback stays intact for /products/search"
  - "row query param sanitized with the existing _ROW_ID_RE allow-list guard (mirrors sale_batch_pick's T-09-10 precedent) before being used to build any rendered id"
  - "Dropdown selection fills both code and name fields directly from the clicked row's own data (D-11) — no re-trigger of /sales/lookup"

patterns-established:
  - "Pattern: any future OOB-swap fragment that replaces a wrapper containing a debounced hx-get input must include the SAME shared partial the initial render uses, not re-declare the input inline"

requirements-completed: [SAL-06]

# Metrics
duration: ~20min
completed: 2026-07-13
---

# Phase 12 Plan 03: Sales Name->Code Dropdown Summary

**Debounced name-fragment search on the sales page rendering a click-to-select, mark-highlighted dropdown of matching code+name rows, wired as a shared partial so it survives both the initial basket-row render and every subsequent code-triggered /sales/lookup OOB swap.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-13T19:44:35Z
- **Tasks:** 2
- **Files modified:** 7 (3 created, 4 modified)

## Accomplishments
- New `GET /sales/search-name` route reuses `search_products()`/`split_match()` verbatim (D-08), enforcing the 3-character trigger threshold itself (D-10) rather than modifying the shared catalog search function
- New `sale_name_search.html` renders a click-to-select, `<mark>`-highlighted dropdown (or a "no matches" message), with row data embedded into `hx-on:click` via `tojson` (mirrors the established `batch_card_picker.html` convention)
- New shared `sale_name_field.html` (PD-6 pattern) is included by both `sale_row.html` (first render) and `sale_lookup.html` (the code-triggered OOB swap), so the debounced dropdown wiring can never be dropped by a plain `outerHTML` replace — this was the specific regression the plan targeted
- Selecting a dropdown row fills both code and name fields directly from the clicked row's own data (D-11), with no redundant `/sales/lookup` round trip

## Task Commits

Each task was committed atomically:

1. **Task 1: GET /sales/search-name route + response partial (D-08/D-10)** - `6094ae9` (feat)
2. **Task 2: Wire the debounced trigger + dropdown target via a shared partial (D-09/D-11)** - `52b8f70` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `app/routes/sales.py` - new `GET /sales/search-name` route; imports `search_products`/`split_match`
- `app/templates/partials/sale_name_search.html` - new dropdown response fragment (click-to-select, mark-highlighted, zero-results copy)
- `app/templates/partials/sale_name_field.html` - new shared name-input + dropdown-target fragment (parameters `row`, `name`, `source`)
- `app/templates/partials/sale_row.html` - name `<td>` now includes the shared partial instead of a bare input
- `app/templates/partials/sale_lookup.html` - name `<td>`'s OOB-swap content now includes the same shared partial (the regression fix)
- `app/static/style.css` - new `.name-search-list` rules
- `tests/test_sales_search.py` - 6 tests covering the route's 4 behaviors plus 2 wiring-survival assertions

## Decisions Made
- 3-character guard lives in the new route (D-10/RESEARCH Pitfall 5), never inside `search_products()`, since that function is shared with `/products/search` and must keep its own empty-query "first 20" fallback.
- `row` is sanitized with the exact same two-line pattern `sale_batch_pick` already uses (T-12-07), so a malformed value collapses to `""` instead of being echoed into rendered ids.
- Product code/name/id values embedded into `hx-on:click` use `tojson` (T-12-08), matching the WR-02-fixed convention in `mobile_partials/batch_card_picker.html` rather than manual string concatenation.

## Deviations from Plan

None - plan executed exactly as written. Two adjustments were needed only in the test suite (not the shipped code) to make Task 1's own acceptance tests pass against the actual seed data:
- The `product` conftest fixture inserts a `Product` row directly and never populates `name_lc` (the shadow column `search_products()` matches Cyrillic name substrings against), so the "name-substring match" test needed a product created via `app.services.catalog.create_product()` instead — this mirrors the exact `_make()` helper already established in `tests/test_search.py` for the same reason. No production code was affected.
- The `<mark>`-highlighted match assertion checks for the specific `<mark>...</mark>` substring rather than the full un-split product name, since D-09 highlighting breaks the matched name into pre/`<mark>`/post segments (confirmed correct behavior, not a bug).

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SAL-06 fully delivered: sales-page code→name (already shipped) and name→code (this plan) autocomplete are both live.
- No blockers for Phase 13 (Mobile Wizard Context & Navigation) — this plan touched only desktop `/sales/new` templates and routes; mobile sale wizard templates (`app/templates/mobile_partials/`) were not modified.

---
*Phase: 12-code-name-autofill*
*Completed: 2026-07-13*

## Self-Check: PASSED

All created/modified files found on disk; both task commits (`6094ae9`, `52b8f70`) verified present in git log.
