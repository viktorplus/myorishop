---
phase: 24-navigation-restructure-settings
plan: 05
subsystem: ui
tags: [jinja2, htmx, mobile, navigation, css]

requires:
  - phase: 24-navigation-restructure-settings (plan 01)
    provides: "8-item desktop top nav in base.html; .toolbar/.toolbar-group CSS pattern to place new rules after"
provides:
  - "Persistent top-docked 7-tab mobile nav bar (nav.mobile-tabbar) in mobile_base.html, inherited by every /m/* page"
  - "Old 10-tile /m/ home grid removed (D-10); dashboard content unchanged below the new tab bar"
  - "Экспорт кассы unreachable from every /m/* page — no home-grid tile, no /m/finance in-page CTA (D-12)"
affects: [24-06]

tech-stack:
  added: []
  patterns:
    - "Mobile tab bar mirrors base.html's request.url.path.startswith(...)/class=\"active\" idiom, sibling of {% block back %}, never nested inside .mobile-shell"

key-files:
  created: []
  modified:
    - app/templates/mobile_base.html
    - app/static/style.css
    - app/templates/mobile_pages/home.html
    - app/templates/mobile_pages/finance.html
    - tests/test_mobile_home.py
    - tests/test_mobile_wiring.py
    - tests/test_finance_reports.py

key-decisions:
  - "Отчёты tab uses /m/reports/expiry, not the UI-SPEC's literal /m/reports (that route does not exist — only GET /m/reports/expiry is registered); active-state check kept as startswith(\"/m/reports\") since that prefix still covers it"
  - "Plan's <verification> referenced tests/test_mobile_finance.py, which does not exist — the actual file is tests/test_finance.py; ran the correct file instead (plan drift, not a deviation from implemented code)"

patterns-established:
  - "nav.mobile-tabbar / nav.mobile-tabbar a / nav.mobile-tabbar a.active CSS classes — sticky top-docked flex nav, 44px min-height tap targets, active state via font-weight + border-bottom (WCAG 1.4.1, never color alone)"

requirements-completed: [MOB-01]

duration: 13min
completed: 2026-07-17
---

# Phase 24 Plan 05: Mobile Tab Bar + Home Grid/Finance CTA Removal Summary

**Persistent top-docked 7-tab mobile nav bar in mobile_base.html (Главная/Товары/Продажи/Покупатели/История/Отчёты/Финансы), replacing the old 10-tile home grid and closing the last in-page path to Экспорт кассы**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-17T22:44:18+02:00
- **Completed:** 2026-07-17T22:57:21+02:00
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- Every `/m/*` page now renders `<nav class="mobile-tabbar">` with exactly 7 text-only tabs, top-docked (`position: sticky; top: 0`), correct active-state highlighting via `font-weight: 600` + `border-bottom: 3px solid #2563eb` (never color alone)
- Old `.mobile-tile-grid` (10 tiles) fully removed from `/m/`; dashboard content (`<h2>Показатели</h2>` onward) renders unchanged, now directly below the new tab bar
- `/m/finance`'s in-page "Отчёт и экспорт CSV" CTA removed — `/m/finance/report` route stays registered (reachable by direct URL) but has zero remaining discoverable path from any `/m/*` page (D-12)
- All 5 previously-breaking mobile tests renamed and rewired to assert the new tab-bar/no-report-link reality; full 910-test suite passes

## Task Commits

Each task was committed atomically:

1. **Task 1: Persistent top-docked mobile tab bar (D-09, MOB-01)** - `e281a7c` (feat)
2. **Task 2: Remove the old home tile grid (D-10) and the /m/finance report CTA (D-12)** - `7c6e254` (feat)
3. **Task 3: Update the 5 mobile tests broken by the grid/link removal** - `acf5018` (test)

_No plan-metadata commit yet — this is a worktree-mode execution; the orchestrator handles the final docs commit after merge._

## Files Created/Modified
- `app/templates/mobile_base.html` — new `{% block tabbar %}`, sibling of `{% block back %}`, renders `<nav class="mobile-tabbar">` with 7 `<a>` elements
- `app/static/style.css` — 3 new rules: `nav.mobile-tabbar`, `nav.mobile-tabbar a`, `nav.mobile-tabbar a.active`
- `app/templates/mobile_pages/home.html` — `.mobile-tile-grid` block and its anticipatory comment deleted
- `app/templates/mobile_pages/finance.html` — in-page `/m/finance/report` CTA deleted; route itself untouched in `app/routes/mobile_finance.py`
- `tests/test_mobile_home.py` — `EXPECTED_HREFS` → `EXPECTED_TABBAR_HREFS` (7 entries); 2 tests renamed and rewired
- `tests/test_mobile_wiring.py` — new `MOBILE_TABBAR_PATHS` constant; 1 test renamed and rewired (`MOBILE_TILE_PATHS`-based tests untouched)
- `tests/test_finance_reports.py` — 2 tests renamed, assertions inverted to prove the report link is now absent

## Decisions Made
- Used `/m/reports/expiry` for the Отчёты tab href (not the UI-SPEC's literal `/m/reports`, which 404s — confirmed via `app/routes/mobile_reports.py`, the only registered mobile reports route). Active-state check kept as `startswith("/m/reports")` per the plan's own read_first note.
- Plan's `<verification>` section names a nonexistent file `tests/test_mobile_finance.py`; the actual file is `tests/test_finance.py`. Ran the correct file (all tests pass) rather than the nonexistent one — this is plan-text drift, not a code deviation.

## Deviations from Plan

None - plan executed exactly as written. (The verification-file-name correction above is documented as a decision, not a deviation, since no plan-specified code/behavior changed.)

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Mobile navigation now mirrors desktop's 8-item nav (minus Настройки), closing MOB-01.
- `nav.mobile-tabbar` CSS pattern is stable and ready for any future mobile chrome plan (24-06) to build on.
- Full 910-test suite passes; no known regressions or stubs introduced by this plan.

---
*Phase: 24-navigation-restructure-settings*
*Completed: 2026-07-17*

## Self-Check: PASSED
