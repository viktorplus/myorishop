---
phase: 11-dedicated-mobile-flow
plan: 02
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile]

requires:
  - phase: 11-dedicated-mobile-flow (Plan 01)
    provides: mobile_base.html, mobile_client_factory test fixture, mobile_partials/batch_card_picker.html
provides:
  - "GET /m/ — static 8-tile home grid (D-03), no service call"
  - "GET /m/search — ranked/capped/Cyrillic-safe stock search via unchanged catalog.search_view"
  - "GET /m/search/product/{product_id} — read-only per-warehouse batch-stock summary"
  - "GET /m/reports/expiry — read-only expiring-batches card list via unchanged batches.expiring_batches"
affects: [11-09 (main.py router registration), any future mobile plan touching search or reports]

tech-stack:
  added: []
  patterns:
    - "Mobile read-only screens are thin routes that call existing unmodified service functions (search_view, expiring_batches, open_batches, active_warehouses) — no new SQL/query logic added"
    - "CR-01 HX-Request branching precedent (history.py) reused: only a genuine HX-Request header gets the chrome-less partial; any other request (bookmark/reload) gets full mobile_base chrome"
    - "Search results partial gates on `q` (not `rows`) so the empty-query default-20-rows behavior of search_products stays hidden from mobile until the operator types"

key-files:
  created:
    - app/routes/mobile_home.py
    - app/routes/mobile_search.py
    - app/routes/mobile_reports.py
    - app/templates/mobile_pages/home.html
    - app/templates/mobile_pages/search.html
    - app/templates/mobile_pages/reports_expiry.html
    - app/templates/mobile_partials/search_results.html
    - app/templates/mobile_partials/search_product_detail.html
    - tests/test_mobile_home.py
    - tests/test_mobile_search.py
    - tests/test_mobile_reports.py
  modified: []

key-decisions:
  - "search_product_detail.html lives in mobile_partials/ per the plan's file list but extends mobile_base.html directly, since it is reached by a plain top-level link click (not HTMX) and must render a full HTML document"
  - "Product detail stock rows sorted by warehouse name for deterministic output (plan did not specify an order)"

patterns-established:
  - "Read-only mobile detail screens (no wizard) can extend mobile_base.html even when their template lives under mobile_partials/, when the route is reached by normal navigation rather than an HX swap"

requirements-completed: [UI-01]

duration: 15min
completed: 2026-07-12
---

# Phase 11 Plan 02: Mobile Home, Search & Expiry Report Summary

**Three read-only mobile screens (/m/ tile grid, /m/search stock lookup, /m/reports/expiry card list) built as thin routes over unmodified catalog.search_view and batches.expiring_batches/open_batches/active_warehouses.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-12
- **Tasks:** 3 completed
- **Files created:** 12 (3 routes, 6 templates, 3 test files)

## Accomplishments
- `GET /m/` renders the 8-tile home grid with the exact D-03 hrefs/copy/order, no `<nav>`, no service call
- `GET /m/search` returns ranked, capped, Cyrillic-safe results via the existing `catalog.search_view`, branching on `HX-Request` (CR-01 precedent) between a rows-only fragment and full chrome
- `GET /m/search/product/{product_id}` gives a read-only per-warehouse open-batch stock summary, 404 on unknown/deleted product id (T-11-06)
- `GET /m/reports/expiry` restacks the same `expiring_batches()` data as desktop into one card per row, same local-date "просрочено" marker logic (Pitfall 5)

## Task Commits

Each task was committed atomically:

1. **Task 1: Mobile home — GET /m/ (D-03 8-tile grid)** - `24af59a` (feat)
2. **Task 2: Mobile search — GET /m/search (reuses catalog.search_view)** - `eac3218` (feat)
3. **Task 3: Mobile expiry report — GET /m/reports/expiry (reuses batches.expiring_batches)** - `c5b6aad` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `app/routes/mobile_home.py` - `GET /m/`, static tile grid, no session dependency
- `app/templates/mobile_pages/home.html` - 8 `mobile-tile` links in D-03 order
- `tests/test_mobile_home.py` - asserts tiles, href order, no `<nav>`
- `app/routes/mobile_search.py` - `GET /m/search` (HX-gated) and `GET /m/search/product/{id}` (read-only detail, 404 on unknown id)
- `app/templates/mobile_pages/search.html` - debounced search input + results shell
- `app/templates/mobile_partials/search_results.html` - ranked/highlighted result cards, gated on `q`
- `app/templates/mobile_partials/search_product_detail.html` - read-only detail (code, name, category, min price, per-warehouse qty)
- `tests/test_mobile_search.py` - match/no-match/empty-query/detail/404 cases
- `app/routes/mobile_reports.py` - `GET /m/reports/expiry`, local-date `today`, unchanged `expiring_batches()`
- `app/templates/mobile_pages/reports_expiry.html` - one `mobile-card` per row, same overdue marker as desktop
- `tests/test_mobile_reports.py` - empty state, overdue marker, future no-marker

## Decisions Made
- `search_product_detail.html` is filed under `mobile_partials/` (per the plan's `files_modified` list) but its content `{% extends "mobile_base.html" %}` because it is a normal top-level navigation target (an `<a href>` click, not an HTMX swap) and therefore must be a complete HTML document, not a bare fragment.
- Per-warehouse stock rows on the product detail screen are sorted by warehouse name for deterministic rendering; the plan did not specify an ordering.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three routers (`mobile_home.router`, `mobile_search.router`, `mobile_reports.router`) are self-contained `APIRouter()` instances, tested in isolation via `mobile_client_factory`, and not yet registered in `app/main.py` — registration is Plan 09's job, as designed.
- Full existing test suite (372 tests) stays green; no desktop template, route, or CSS was touched.
- No blockers for the remaining wizard plans (03-08), which build on the same `mobile_base.html` / `mobile_client_factory` / `batch_card_picker.html` foundation proven end-to-end by this plan's three screens.

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*

## Self-Check: PASSED

All 11 created files verified present on disk; all 3 task commit hashes (24af59a, eac3218, c5b6aad) verified in git log.
