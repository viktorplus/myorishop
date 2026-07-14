---
phase: 14-list-pagination-filtering-sorting-quick-delete
plan: 06
subsystem: ui
tags: [fastapi, sqlalchemy, htmx, jinja2, pagination, filtering, sorting]

requires:
  - phase: 14-01
    provides: "app/services/pagination.py (LIST_PAGE_SIZE=20, page_window, paginate) and partials/pagination.html"
provides:
  - "app/services/customers.py: list_customers_view() — independent name/surname/consultant_number filters, allow-listed sort, pagination"
  - "GET /customers gains name/surname/consultant_number/sort/page query params and an is_hx dual response (mirrors history.py)"
  - "GET /customers/search route retired (Pitfall 6) — search_customers()/customer_search_view() stay byte-for-byte unchanged for the sale-form customer picker"
affects: [products-list, warehouses-list, dictionary-list, catalogs-list, history-list]

tech-stack:
  added: []
  patterns:
    - "list_customers_view() is a NEW, separate function from search_customers/customer_search_view — never overload the combined search_lc query with independent per-column filter semantics"
    - "_customers_context() route helper mirrors the plan's pattern for list routes: call the service, compute page_window + extra_qs, return one context dict shared by full-page and is_hx-partial responses"

key-files:
  created: []
  modified:
    - app/services/customers.py
    - app/routes/customers.py
    - app/templates/partials/customer_rows.html
    - app/templates/pages/customers_list.html
    - tests/test_customers.py

key-decisions:
  - "list_customers_view's returned page field is the raw input page param (not paginate()'s internally-clamped index) — matches the exact contract specified in the plan and mirrors the sibling 14-04 (products) plan's identical convention; paginate() still guarantees the ROWS never raise/empty-out on an out-of-range page (T-14-19)."
  - "Sort/filter controls live inside the same {% if rows %} block as the table (filter-row inputs disappear on a zero-result filter) — matches the established phase-wide convention (verified against 14-04-PLAN.md's identical products list structure), not a customers-specific choice."

patterns-established:
  - "New list_*_view() service functions are added ADDITIVELY below existing search functions, never replacing them, when another route (sales.py's customer picker) depends on the original search shape."

requirements-completed: [LIST-01, LIST-02, LIST-03]

duration: 15min
completed: 2026-07-14
---

# Phase 14 Plan 06: Customers List Filter/Sort/Pagination Summary

**New `list_customers_view()` gives `/customers` independent per-column filters (name/surname/consultant number), an allow-listed sort dropdown, and page-number pagination — while `search_customers`/`customer_search_view` stay byte-for-byte unchanged for the sale-form customer picker, and the now-redundant `/customers/search` route is retired.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-14T02:53:00Z (approx, per STATE.md session timestamp)
- **Completed:** 2026-07-14T03:07:53Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `list_customers_view(session, *, name="", surname="", consultant_number="", sort="", page=0)` filters each column independently via Python `.lower()` substring match, sorts via an allow-list (`_SORT_MAP`), and paginates via the shared `pagination.paginate()` helper (20 rows/page, D-03).
- `GET /customers` now accepts `name`/`surname`/`consultant_number`/`sort`/`page` query params and returns a chrome-less `partials/customer_rows.html` for HTMX requests (mirroring `app/routes/history.py`'s `is_hx` pattern) or the full `pages/customers_list.html` otherwise.
- `GET /customers/search` (route only) is deleted — `search_customers`/`customer_search_view`/`_search_lc` in `app/services/customers.py` remain untouched (verified via `git diff` showing zero removed/modified lines in that file), and `app/routes/sales.py`'s customer picker (`customer_picker.html`) still imports and uses `customer_search_view` unaffected.
- `partials/customer_rows.html` is now a single swappable `#customer-rows` block: a `.filter-bar` sort `<select>` (default "Имя (А→Я) (по умолчанию)", plus "Фамилия (А→Я)" / "Номер консультанта"), a `<tr class="filter-row">` with debounced (300ms) name/surname/consultant_number text inputs, plain (unhighlighted) rows, and `partials/pagination.html`.
- `pages/customers_list.html`'s standalone `q` search `<input>` is removed (Pitfall 6) — filtering now lives entirely in the header row.

## Task Commits

Each task was committed atomically (Task 1 used TDD's RED → GREEN cycle):

1. **Task 1 RED: failing tests for `list_customers_view` + retired `/customers/search`** - `bdeaf75` (test)
2. **Task 1 GREEN: `list_customers_view()` service function + route wiring** - `ae112b5` (feat)
3. **Task 2: Header-row filters + sort dropdown + pagination partial** - `7cad533` (feat)

## Files Created/Modified
- `app/services/customers.py` - added `_SORT_MAP` allow-list + `list_customers_view()`; `search_customers`/`customer_search_view`/`_search_lc` untouched
- `app/routes/customers.py` - `customers_list()` gains query params + `_customers_context()` helper + `is_hx` branch; `/customers/search` route deleted
- `app/templates/partials/customer_rows.html` - rewritten: sort `.filter-bar`, `filter-row` header cells, plain rows, `pagination.html` include, updated empty-state (no-data vs. filtered-to-zero)
- `app/templates/pages/customers_list.html` - standalone search `<input>` removed
- `tests/test_customers.py` - 3 service-level tests (filter independence, sort allow-list + default, pagination/clamp), 4 web-level tests (retired route 404, filter-row narrows results, pagination bar total, no standalone search input)

## Decisions Made
- Kept `list_customers_view`'s returned `page` field as the raw (unclamped) input, per the plan's literal `Return` spec and matching sibling plan 14-04's identical convention for products — `pagination.paginate()` already guarantees the returned ROWS never raise or come back empty for an out-of-range page (T-14-19 mitigation is about safety, not display-perfect page numbering on a hand-crafted out-of-range URL).
- Filter-row inputs and the sort dropdown live inside the same conditional block as the results table (not always-visible independent of row count) — this exactly matches the parallel 14-04-PLAN.md (products) structure, confirmed by reading that plan before implementing, so the two lists stay visually/structurally consistent per the phase's cross-cutting intent.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/customers` list now matches the phase's shared filter/sort/pagination shape (Contracts A/B/C from `14-UI-SPEC.md`), ready for the phase-wide verification pass alongside products/warehouses/dictionary/catalogs/history.
- No quick-delete added for customers — out of scope per plan (LIST-04/LIST-05 apply only to warehouses/products).
- `app/routes/sales.py`'s customer-picker autocomplete (`GET /sales/customer-search`) is a separate, untouched route/function pair — confirmed no regression via `tests/test_sales.py` (67/67 passed alongside `tests/test_customers.py`).

---
*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Completed: 2026-07-14*

## Self-Check: PASSED
