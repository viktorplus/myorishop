---
phase: 14-list-pagination-filtering-sorting-quick-delete
plan: 04
subsystem: api
tags: [fastapi, jinja2, htmx, sqlalchemy, product-catalog]

# Dependency graph
requires:
  - phase: 14-01
    provides: "app/services/pagination.py (LIST_PAGE_SIZE, paginate, page_window) and partials/pagination.html"
provides:
  - "catalog.list_products_view() — Python-side filter (code/name/category substring)/sort (name_desc, code, default name-asc)/page for /products"
  - "catalog.quick_delete_product() — D-08 hard stock guard, zero-writes-on-block, mirrors soft_delete_warehouse's (deleted, info) shape"
  - "GET /products with code/name/category/sort/page query params + is_hx dual response (partial vs full page)"
  - "POST /products/{id}/quick-delete route, re-renders partials/product_rows.html in place"
  - "/products/search route retired (search_products/search_view/split_match functions kept byte-for-byte for mobile_search.py and sales.py)"
affects: [14-05, 14-06, 14-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Python-side filter/sort/page over one fetch (small cardinality) instead of SQL WHERE/ORDER BY — matches the existing search_products precedent"
    - "_products_context() route helper mirrors search_view's D-18 shared-context-for-page-and-partial pattern for the new filter/sort/page shape"

key-files:
  created: []
  modified:
    - app/services/catalog.py
    - app/routes/products.py
    - app/templates/partials/product_rows.html
    - app/templates/pages/products_list.html
    - tests/test_catalog.py
    - tests/test_search.py

key-decisions:
  - "list_products/search_products/search_view/split_match/soft_delete_product left completely untouched — mobile_search.py and sales.py autocomplete keep working on the old functions, verified by the full 529-test suite passing"
  - "quick_delete_product has NO confirm=1 override (unlike soft_delete_warehouse's last-active guard) — D-08 stock guard is a hard, non-overridable block per the threat model (T-14-11)"
  - "test_web_products_search_route_retired asserts 405, not 404 — the bare path /products/search still path-matches the parameterized POST /products/{product_id} route, so Starlette reports Method Not Allowed rather than a bare 404; this is correct routing behavior, not a leftover endpoint"

patterns-established:
  - "_SORT_MAP module-level allow-list dict of Python key= callables (never string-interpolated into SQL) for T-14-09 tampering mitigation"

requirements-completed: [LIST-01, LIST-02, LIST-03, LIST-05]

# Metrics
duration: 12min
completed: 2026-07-14
---

# Phase 14 Plan 04: Product List Filter/Sort/Page + Quick-Delete Summary

**New `list_products_view()`/`quick_delete_product()` catalog service functions power a filterable, sortable, paginated `/products` list with a one-click stock-guarded quick-delete, while the existing search/mobile/sales code paths stay byte-for-byte unchanged.**

## Performance

- **Duration:** ~12 min (commit span 04:59–05:09 UTC+2, plus context-reading time)
- **Started:** 2026-07-14T04:5x (approx, not explicitly timestamped)
- **Completed:** 2026-07-14T05:09:25+02:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- `list_products_view()`: Python-side code/name/category substring filters, `_SORT_MAP`-driven sort (name_desc, code, default name-ascending), pagination via the shared `paginate()` helper from Plan 14-01
- `quick_delete_product()`: D-08 hard stock guard (`quantity > 0` blocks with `(False, {"blocked_qty": N})`, zero writes staged), idempotent no-op on unknown/already-deleted ids
- `GET /products` now accepts `code`/`name`/`category`/`sort`/`page` query params and returns either the rows partial (HX-Request) or the full page
- `POST /products/{id}/quick-delete` re-renders `#product-rows` in place — matches D-10 (row disappears entirely on success)
- `/products/search` route retired; the underlying `search_products`/`search_view`/`split_match` service functions are untouched and still serve `mobile_search.py`/`sales.py`

## Task Commits

Each task was committed atomically:

1. **Task 1: list_products_view() + quick_delete_product() service functions** - `ec7584c` (feat)
2. **Task 2: Route wiring — filter/sort/page on GET /products, new quick-delete route, retire /products/search** - `d7258b3` (feat)
3. **Task 3: Header-row filters + sort dropdown + pagination + quick-delete button in templates** - `992861e` (feat)

_Note: Task 2's route/test changes and Task 3's template changes were implemented together (routes reference the new template context shape) but committed separately per the plan's file ownership — both commits were verified against the full green test suite at time of commit._

## Files Created/Modified
- `app/services/catalog.py` - `list_products_view()`, `quick_delete_product()`, `_SORT_MAP` added; all pre-existing functions unchanged (verified via `git diff --stat`: pure additions, zero deletions)
- `app/routes/products.py` - `products_list()` rewritten with query params + is_hx branch; new `product_quick_delete()` route; `products_search()`/`GET /products/search` deleted; `product_delete`/`product_restore` untouched
- `app/templates/partials/product_rows.html` - sort `<select>`, filter-row `<th>` inputs, plain product rendering (drops `<mark>` highlighting), quick-delete button, inline blocked-error row, pagination include, three-way empty-state branch
- `app/templates/pages/products_list.html` - standalone search `<input>` removed (Pitfall 6)
- `tests/test_catalog.py` - 8 service-level tests (Task 1) + 2 route-level quick-delete tests (Task 2) + 3 route-level filter/pagination/search-input tests (Task 3)
- `tests/test_search.py` - two now-obsolete `/products/search` tests deleted; one replaced with a route-retirement check (405)

## Decisions Made
- Kept `list_products`/`search_products`/`search_view`/`split_match`/`soft_delete_product` completely untouched, confirmed by `git diff` showing zero deletions in `catalog.py` and by the full 529-test suite (including `test_mobile_search.py`, `test_sales_search.py`) passing unmodified.
- No `confirm=1` override on the D-08 stock guard, unlike the warehouse last-active guard — matches the threat model's T-14-11 disposition (hard block, no bypass path).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected the retired-route test's expected status code**
- **Found during:** Task 2 (Route wiring)
- **Issue:** The plan specified `assert client.get("/products/search").status_code == 404`, but the bare path `/products/search` still path-matches the parameterized `POST /products/{product_id}` route (`product_id="search"`), so Starlette's router returns 405 Method Not Allowed for a GET request instead of a bare 404 — this is correct HTTP routing semantics, not a leftover endpoint.
- **Fix:** Changed the assertion to `status_code == 405` with a docstring explaining why, in `tests/test_search.py::test_web_products_search_route_retired`.
- **Files modified:** tests/test_search.py
- **Verification:** `uv run pytest tests/test_catalog.py tests/test_search.py -x` — 66/66 pass; full suite — 529/529 pass.
- **Committed in:** d7258b3 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — incorrect expected HTTP status in the plan's test spec)
**Impact on plan:** Cosmetic test-assertion correction only; no application-code behavior change. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `/products` list ergonomics (filter/sort/page/quick-delete) fully shipped; the same `pagination.py`/`pagination.html` foundation from Plan 14-01 is proven out end-to-end and ready to be reused by the remaining list pages (warehouses, customers, dictionary, catalogs, history) in later Phase 14 plans.
- `_products_context()` in `app/routes/products.py` is a reusable shape (list_url/rows_target_id/extra_qs/page_window) that later plans' route helpers can mirror.
- No blockers or concerns for subsequent Phase 14 plans.

## Self-Check: PASSED

All claimed files exist on disk (verified via `[ -f ... ]`) and all three task commit hashes (`ec7584c`, `d7258b3`, `992861e`) are present in `git log --oneline --all`.

---
*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Completed: 2026-07-14*
