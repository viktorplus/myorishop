---
phase: 13-mobile-wizard-context-navigation
plan: 05
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile]

requires:
  - phase: 11-mobile-flow
    provides: mobile sale wizard (basket/step partials), mobile search product-detail screen
provides:
  - "Корзина" step-indicator line on the mobile sale wizard's basket/review screen (D-07, UI-04)
  - Optional `?code=` GET query-param pre-fill on GET /m/sales, echoed unchanged into step 1 (D-08)
  - Unconditional "Продать"/"Принять" quick-action links on the mobile search product-detail screen, jumping to /m/sales?code= and /m/receipts?code= (D-08/D-09, UI-05)
affects: [13-mobile-wizard-context-navigation]

tech-stack:
  added: []
  patterns:
    - "mobile-step-indicator class reused verbatim for unnumbered wizard screens (literal 'Корзина' text instead of computed 'Шаг N из 3')"
    - "GET wizard entry routes accept an optional code query param and pass it through unchanged to pre-fill step 1's code input — no step-skip, no new entry point"

key-files:
  created: []
  modified:
    - app/templates/mobile_partials/sale_basket.html
    - app/routes/mobile_sales.py
    - tests/test_mobile_sales.py
    - app/templates/mobile_partials/search_product_detail.html
    - tests/test_mobile_search.py

key-decisions:
  - "sale_basket.html's step-indicator uses a literal 'Корзина' string (not a step_label variable) since this screen has no numeric step, matching the plan's explicit instruction not to compute one"
  - "Both quick-action links render unconditionally regardless of stock_rows content per D-09 (zero-stock products stay reachable via the existing oversell-warning pattern)"

patterns-established: []

requirements-completed: [UI-04, UI-05]

duration: 13min
completed: 2026-07-14
---

# Phase 13 Plan 05: Basket step indicator + search quick actions Summary

**Adds a "Корзина" step-indicator to the mobile sale wizard's basket screen and unconditional Продать/Принять quick-action links (with `?code=` pre-fill) from the mobile search product-detail screen**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-13T22:15:31Z
- **Completed:** 2026-07-13T22:28:08Z
- **Tasks:** 2 completed
- **Files modified:** 5

## Accomplishments
- `sale_basket.html`'s Корзина screen now shows a `mobile-step-indicator` line consistent with the rest of the wizard (D-07)
- `GET /m/sales` accepts an optional `code` query param, echoing it into the pre-filled code input on step 1 (D-08, sale-side half — receipt-side half lands via Plan 13-03 in the same wave)
- `search_product_detail.html` always renders both "Продать" and "Принять" quick-action links, regardless of stock level (D-08/D-09)

## Task Commits

Each task was committed atomically:

1. **Task 1: Sale basket step indicator + /m/sales code query param** - `e39dba3` (feat)
2. **Task 2: Search product-detail quick actions (Продать/Принять)** - `253a57a` (feat)

_Note: no TDD tasks in this plan; each task's tests were added alongside its implementation change and verified together._

## Files Created/Modified
- `app/templates/mobile_partials/sale_basket.html` - added `<p class="mobile-step-indicator">Корзина</p>` before the `<h2>Корзина</h2>` heading
- `app/routes/mobile_sales.py` - `mobile_sales_page` now accepts `code: str = ""` and passes it through as `"code": code` instead of a hardcoded empty string
- `tests/test_mobile_sales.py` - added tests for the step-indicator markup and the `?code=` round trip
- `app/templates/mobile_partials/search_product_detail.html` - added a `.mobile-actions` block with unconditional "Продать"/"Принять" links to `/m/sales?code=` and `/m/receipts?code=`
- `tests/test_mobile_search.py` - added tests asserting both links render for a stocked product and (unconditionally) for a zero-stock product

## Decisions Made
- Followed the plan's literal-string approach for the Корзина step-indicator (no numeric step computed for this screen)
- Followed 13-UI-SPEC.md Contract D markup verbatim for the quick-action links (plain `.button` styling, not `.secondary`)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both of this plan's `must_haves.artifacts` (Корзина step-indicator, quick-action links) are in place and test-verified.
- Cross-plan note from the plan objective: the "Принять" link's target (`GET /m/receipts?code=`) is wired up by Plan 13-03 (same wave, no file overlap with this plan) — that plan's own tests verify the `/m/receipts?code=` round trip.
- No blockers for the rest of Phase 13's wave.

---
*Phase: 13-mobile-wizard-context-navigation*
*Completed: 2026-07-14*
