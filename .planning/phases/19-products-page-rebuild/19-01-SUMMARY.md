---
phase: 19-products-page-rebuild
plan: 01
subsystem: ui
tags: [fastapi, jinja2, htmx, sqlalchemy, product-catalog, batches]

# Dependency graph
requires:
  - phase: 09-batches-transfers-expiry
    provides: Batch model, open_batches D-07 ordering, ru_date filter
  - phase: 18-two-price-model-consolidation
    provides: final ДЦ/ПЦ product price shape read unchanged by this plan
provides:
  - "batches_for_products(session, product_ids) — batched, non-N+1 open-batch query grouped by product_id"
  - "_products_context() carries batches_by_id for the products list route"
  - "/products list rebuilt: Кол-во column, collapsed per-row batch breakout, no add-button, delete as text link"
affects: [20-warehouses-and-batch-split-transfers]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Batched (non-N+1) per-row child data grouped in Python via defaultdict, one IN(...) query per page load"
    - "Zero-JS expand/collapse via native <details>/<summary>, collapsed by default"

key-files:
  created: []
  modified:
    - app/services/batches.py
    - app/routes/products.py
    - app/templates/partials/product_rows.html
    - app/templates/pages/products_list.html
    - app/static/style.css
    - tests/test_batches.py
    - tests/test_catalog.py

key-decisions:
  - "batches_for_products() mirrors open_batches' D-07 ordering exactly (earliest expiry first, NULL last, oldest created_at) instead of introducing a second ordering convention"
  - "Delete <a class=\"link-danger\"> rendered as one line (href, class, all hx-* attrs) to match the plan's interface spec verbatim, rather than wrapping across lines"

patterns-established:
  - "Pattern 1: Batched (non-N+1) per-row child data, grouped in Python — reusable for any future per-row expandable-detail table on a paginated list"

requirements-completed: [PROD-01, PROD-02, PROD-03, PROD-04, PROD-08]

# Metrics
duration: 8min
completed: 2026-07-16
---

# Phase 19 Plan 01: Products Page Rebuild Summary

**Products list now groups by code with a quantity column and a collapsed per-row batch breakout, drops the redundant "Добавить товар" entry point, and turns delete into an accessible text link — filter/sort/pagination and the category filter untouched.**

## Performance

- **Duration:** 8 min (commit-to-commit)
- **Started:** 2026-07-16T16:27:40+02:00
- **Completed:** 2026-07-16T16:35:20+02:00
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Added `batches_for_products(session, product_ids)` — one `IN (...)` query per page load (non-N+1), grouped by `product_id`, wired into `_products_context()` as a new `batches_by_id` context key with every pre-existing key unchanged
- `/products` now renders a `Кол-во` column (`product.quantity`) and, for each product with open batches, a collapsed `<details><summary>Партии (N)</summary>` block listing expiry/name/quantity with legacy NULL fields rendered as `—`
- Removed the "Добавить товар" CTA from both the page and the empty state (empty state now points to `/receipts/new`); delete control changed from `<button class="danger">` to `<a href="#" class="link-danger">` with identical `hx-*` attributes and confirm text; new `.link-danger` CSS rule reuses the existing `#b91c1c` destructive token

## Task Commits

Each task followed RED (test) → GREEN (feat):

1. **Task 1: Batched batch-grouping service + route wiring** — `371be6d` (test), `118f5fb` (feat)
2. **Task 2: Quantity column + collapsed batch breakout** — `693217a` (test), `b566656` (feat)
3. **Task 3: Remove add-button, delete-as-text-link, CSS** — `b5c6269` (test), `ed3611b` (feat)

_All 6 commits verified RED before GREEN: each new test failed (ImportError/AssertionError) prior to its corresponding implementation commit, confirmed passing after._

## Files Created/Modified
- `app/services/batches.py` - new `batches_for_products(session, product_ids)` function
- `app/routes/products.py` - `_products_context()` gains `batches_by_id` key
- `app/templates/partials/product_rows.html` - new `Кол-во` column, collapsed batch breakout `<tr>`/`<details>`, delete link replaces delete button, new empty-state copy
- `app/templates/pages/products_list.html` - removed the `<p class="page-actions">` add-button CTA
- `app/static/style.css` - new `a.link-danger` / `a.link-danger:hover` rule
- `tests/test_batches.py` - 3 new tests for `batches_for_products`
- `tests/test_catalog.py` - 6 new tests covering the quantity column, batch breakout (present/absent), add-button removal, `/products/new` reachability, delete-as-link

## Decisions Made
- Mirrored `open_batches`' exact D-07 ordering in `batches_for_products` rather than introducing any new ordering rule — keeps the batch-picker and the products-list breakout visually consistent
- Wrote the new `<a class="link-danger">` delete control as a single-line tag (matching the plan's `<interfaces>` spec verbatim) instead of wrapping attributes across lines, avoiding a whitespace mismatch with the plan's exact copy contract

## Deviations from Plan

None — plan executed exactly as written. All three tasks implemented per the `<interfaces>` and `<action>` blocks verbatim; no Rule 1-4 fixes were needed.

## Issues Encountered

Initial attempt at wrapping the delete `<a>` tag's `hx-*` attributes across multiple lines (for readability) didn't match the plan's exact single-line interface spec and my own test's substring assertion. Reformatted to the single-line form given in the plan; re-verified GREEN.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `/products` fully rebuilt per PROD-01/02/03/04/08; category filter/sort/pagination confirmed unregressed (full suite 720 passed = 711 baseline + 9 new; `ruff check` clean on every file this plan touched — two pre-existing E501 warnings in untouched lines of `app/routes/products.py` and `tests/test_catalog.py` are out of scope per the deviation-rules scope boundary)
- Phase 20 (Warehouses & Batch-Split Transfers) can proceed independently; no blockers surfaced

---
*Phase: 19-products-page-rebuild*
*Completed: 2026-07-16*
