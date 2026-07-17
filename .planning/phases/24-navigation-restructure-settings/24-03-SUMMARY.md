---
phase: 24-navigation-restructure-settings
plan: 03
subsystem: ui
tags: [jinja2, htmx, navigation, reports]

# Dependency graph
requires: []
provides:
  - "Back-link (← Назад к отчётам) on all 5 report detail pages, linking to /reports"
  - "5 new automated tests asserting per-page back-link presence"
affects: [24-navigation-restructure-settings]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Report detail pages follow the catalog_detail.html precedent: a static <p><a href=\"...\">← Back label</a></p> line placed immediately above the page's own <h1>, inside {% block content %} but outside any HX-swap partial target."

key-files:
  created: []
  modified:
    - app/templates/pages/reports_sales.html
    - app/templates/pages/reports_writeoffs.html
    - app/templates/pages/reports_stock.html
    - app/templates/pages/reports_expiry.html
    - app/templates/pages/reports_products.html
    - tests/test_reports.py

key-decisions:
  - "Followed catalog_detail.html precedent byte-for-byte (shape), only swapping href/label text per CONTEXT.md mandate"
  - "Left partials/sales_report_results.html, partials/writeoffs_report_rows.html, partials/top_selling_rows.html untouched — they are chrome-less HX-partial fragments; adding a back-link there would duplicate it on every filter swap"

patterns-established:
  - "Report detail page back-link: <p><a href=\"/reports\">← Назад к отчётам</a></p> immediately before <h1>, never inside an HX-swap target"

requirements-completed: [RPT-01]

# Metrics
duration: 12min
completed: 2026-07-17
---

# Phase 24 Plan 03: Report Detail Pages Back-Link Summary

**Added "← Назад к отчётам" back-link to all 5 report detail pages (sales, writeoffs, stock, expiry, products), each linking to /reports, plus 5 new per-page regression tests.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-17T00:00:00Z (approx, worktree agent)
- **Completed:** 2026-07-17
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Every report detail page now has a one-click path back to the `/reports` landing page (RPT-01), closing the same navigation gap UAT found in Phase 17
- `/reports` landing page itself left unmodified (it's the destination, not a detail page)
- HX-partial fragments (`sales_report_results.html`, `writeoffs_report_rows.html`, `top_selling_rows.html`) remain chrome-less — back-link does not leak into filter-swap responses
- 5 new automated tests give explicit, per-page coverage for the back-link

## Task Commits

Each task was committed atomically:

1. **Task 1: Insert the back-link into all 5 report detail templates** - `a78b0de` (feat)
2. **Task 2: Add 5 new back-link assertions to tests/test_reports.py** - `85d460f` (test)

_Note: SUMMARY/plan-metadata commit handled separately per worktree convention._

## Files Created/Modified
- `app/templates/pages/reports_sales.html` - back-link added above `<h1>Продажи и прибыль</h1>`
- `app/templates/pages/reports_writeoffs.html` - back-link added above `<h1>Списания</h1>`
- `app/templates/pages/reports_stock.html` - back-link added above `<h1>Остатки склада</h1>`
- `app/templates/pages/reports_expiry.html` - back-link added above `<h1>Сроки годности</h1>`
- `app/templates/pages/reports_products.html` - back-link added above `<h1>Топ и залежавшиеся товары</h1>`
- `tests/test_reports.py` - added `test_web_reports_sales_has_back_link`, `test_web_reports_writeoffs_has_back_link`, `test_web_reports_stock_has_back_link`, `test_web_reports_expiry_has_back_link`, `test_web_reports_products_has_back_link`, placed near `test_web_nav_has_reports_link`

## Decisions Made
- Matched `catalog_detail.html:3`'s exact shape (`<p><a href="...">← Label</a></p>`) rather than inventing a new markup pattern, per CONTEXT.md's explicit precedent mandate
- Did not modify the 3 HX-partial fragment templates, since they are swapped independently by the period filter and are not full-page renders

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- RPT-01 fully satisfied: all 5 report detail pages have a working back-link to `/reports`
- No blockers for subsequent plans in this wave/phase
- Full test suite (901 tests) passes with no regressions

---
*Phase: 24-navigation-restructure-settings*
*Completed: 2026-07-17*
