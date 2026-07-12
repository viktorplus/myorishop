---
phase: 11-dedicated-mobile-flow
plan: 09
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile, integration]

# Dependency graph
requires:
  - phase: 11-dedicated-mobile-flow
    plan: "01"
    provides: mobile_base.html, mobile_client_factory test fixture, mobile CSS classes
  - phase: 11-dedicated-mobile-flow
    plan: "02"
    provides: mobile_home.router, mobile_search.router, mobile_reports.router
  - phase: 11-dedicated-mobile-flow
    plan: "03"
    provides: mobile_receipts.router
  - phase: 11-dedicated-mobile-flow
    plan: "04"
    provides: mobile_sales.router
  - phase: 11-dedicated-mobile-flow
    plan: "05"
    provides: mobile_writeoff.router
  - phase: 11-dedicated-mobile-flow
    plan: "06"
    provides: mobile_corrections.router
  - phase: 11-dedicated-mobile-flow
    plan: "07"
    provides: mobile_transfers.router
  - phase: 11-dedicated-mobile-flow
    plan: "08"
    provides: mobile_history.router, mobile_returns.router
provides:
  - "All 10 mobile routers (mobile_home, mobile_sales, mobile_receipts, mobile_search, mobile_writeoff, mobile_corrections, mobile_transfers, mobile_returns, mobile_history, mobile_reports) registered in app/main.py alongside the 16 pre-existing desktop routers"
  - "tests/test_mobile_wiring.py — end-to-end reachability regression proving the real running app serves the entire /m/... surface plus every pre-existing desktop route, purely additively"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure registration plan (wire-last pattern): no new business logic, no new templates — only app.main.py router wiring plus a full-app reachability regression test using the real `client` fixture instead of the isolated `mobile_client_factory`"

key-files:
  created:
    - tests/test_mobile_wiring.py
  modified:
    - app/main.py

key-decisions:
  - "No deviations needed — every prior-wave router already exported a module-level `router = APIRouter()` and every GET tile landing route already returned 200, so Task 1 was pure mechanical registration exactly as scoped"

requirements-completed: [UI-01]

# Metrics
duration: 12min
completed: 2026-07-12
---

# Phase 11 Plan 09: Mobile Router Wiring & Full-App Reachability Regression Summary

**All 10 mobile routers built in Plans 02-08 registered in `app/main.py`; a new `tests/test_mobile_wiring.py` proves every `/m/...` tile and every pre-existing desktop route are reachable together in the real running app (434 tests, 0 failures).**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-12
- **Tasks:** 2 completed
- **Files modified:** 2 (1 modified, 1 created)

## Accomplishments
- `app/main.py`'s `from app.routes import (...)` block now contains all 26 module names (16 existing + 10 new mobile modules), merged into one alphabetically sorted import statement
- 10 new `app.include_router(mobile_X.router)` calls added after the existing 16, ordered to match the home-tile grid (`mobile_home`, `mobile_sales`, `mobile_receipts`, `mobile_search`, `mobile_writeoff`, `mobile_corrections`, `mobile_transfers`, `mobile_returns`, `mobile_history`, `mobile_reports`)
- `python -c "from app.main import app"` succeeds with no `ImportError`; `len(app.routes)` confirms the mobile routes are registered
- New `tests/test_mobile_wiring.py` (using the real `client` fixture, not `mobile_client_factory`) asserts: `GET /m/` lists all 8 tile hrefs; each of the 8 tile paths plus `/m/` returns 200; desktop `/` still renders with the D-02 `matchMedia("(max-width: 599px)")` redirect script intact; all 13 pre-existing desktop nav routes (`/products`, `/categories`, `/warehouses`, `/receipts/new`, `/sales/new`, `/writeoff`, `/transfers`, `/customers`, `/history`, `/reports`, `/export`, `/dictionary`, `/backup`) still return 200
- Full suite (`uv run pytest -q`): **434 passed, 0 failures** — the final proof that Phase 11 is purely additive

## Task Commits

Each task was committed atomically:

1. **Task 1: Register all 10 mobile routers in app/main.py** - `5904e47` (feat)
2. **Task 2: End-to-end reachability regression test + full suite verification** - `51a62a5` (test)

_Note: no TDD tasks this plan; SUMMARY.md is committed via the worktree final commit._

## Files Created/Modified
- `app/main.py` - merged 10 mobile_* module names into the alphabetized import block; added 10 `include_router` calls after the existing 16, byte-identical elsewhere (lifespan, StaticFiles mount, and the 16 pre-existing include_router calls untouched)
- `tests/test_mobile_wiring.py` - new end-to-end reachability regression test using the real `client` fixture

## Decisions Made
None beyond the plan's own scope — this was a pure mechanical wiring plan. All 10 mobile route modules already exported `router = APIRouter()` (verified before editing) and all 8 GET tile-landing routes already returned 200 (verified via the new test), so no fixes were needed to make registration work.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Every `/m/...` route built across Plans 02-08 is now reachable from the real running `app.main.app`, proven by an automated regression test (not just isolated `mobile_client_factory` tests)
- Every pre-existing desktop route remains functionally unaffected — ROADMAP criterion 4 ("purely additive") is automatically verified for the 13 nav-linked routes plus the redirect-script text proxy for D-02
- Full test suite is green (434 passed, 0 failures)
- The 6 manual UAT gates listed in `11-UI-SPEC.md`'s Interaction Contract (viewport redirect behavior, desktop-width non-redirect, all 8 tiles reachable, no-truncation batch cards, guardrail copy/zero-write parity, pixel-for-pixel desktop unchanged) remain the only manual verification step before `/gsd-verify-work` — this plan's automated coverage does not replace them (TestClient cannot execute JS or render pixels)

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*

## Self-Check: PASSED

`app/main.py` and `tests/test_mobile_wiring.py` verified present on disk; both task commit hashes (`5904e47`, `51a62a5`) verified present in `git log --oneline --all`.
