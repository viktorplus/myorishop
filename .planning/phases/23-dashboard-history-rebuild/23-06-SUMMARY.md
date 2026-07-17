---
phase: 23-dashboard-history-rebuild
plan: 06
subsystem: ui
tags: [fastapi, jinja2, htmx, dashboard]

# Dependency graph
requires:
  - phase: 23-dashboard-history-rebuild
    provides: "Plan 03's app/services/dashboard.py::dashboard_context(session, tz_name) — the single composer call this plan renders"
provides:
  - "GET / rebuilt as a thin route delegating entirely to dashboard_context"
  - "app/templates/pages/home.html — the real DASH-01..05 dashboard (date/time, catalog countdown, 4 tiles, 10-column feed)"
  - "app/templates/partials/dashboard_tiles.html — reusable 4-tile .metric-grid (Сегодня/Неделя/Месяц/Склад)"
affects: [23-07-mobile-home-route]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Desktop dashboard feed reuses history_rows.html's per-field Jinja idioms (signed qty, muted-dash cost, inline profit, «Розница» customer fallback) verbatim rather than re-deriving them"
    - "Per-type column population gated on r.op.type (not on value presence) to match 23-UI-SPEC.md's literal per-type column table exactly — e.g. a receipt with a populated unit_price_cents still shows Прибыль as muted-dash, since receipts have no profit concept"

key-files:
  created:
    - app/templates/partials/dashboard_tiles.html
    - tests/test_home.py
  modified:
    - app/routes/home.py
    - app/templates/pages/home.html
    - tests/test_smoke.py

key-decisions:
  - "Task 1 (home.py route rebuild) and Task 2's TDD RED phase were sequenced as: route commit -> RED test commit -> GREEN template commit, since the plan's own Task 1 verify command (`pytest tests/test_home.py -x`) targets a test file Task 2 creates. Task 1 was verified via a manual pytest run showing zero regressions instead, then Task 2's full RED->GREEN cycle covers both tasks together."
  - "dashboard_tiles.html money lines omit the `metrics.<period>.expense_cents` sign convention question entirely — expense_cents is rendered as-is (already-negative, D-07's convention), matching finance_tiles.html's established treatment of the same shape."

patterns-established:
  - "Money is never sign-colored anywhere on Главная — every `| cents` call renders in default text color, including a negative net-profit figure (Color rule 1, WCAG 1.4.1)"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05]

# Metrics
duration: ~15min
completed: 2026-07-17
---

# Phase 23 Plan 06: Desktop Главная Dashboard Summary

**Rebuilt `GET /` from the Phase-1 walking-skeleton (oldest active product + retired correction form) into the real DASH-01..05 dashboard: date/weekday/time, active-catalog countdown with empty/closed states, a 4-tile metric grid, and a 10-column recent-operations feed linking into `/history`.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-17
- **Tasks:** 2
- **Files modified:** 5 (2 created: dashboard_tiles.html, test_home.py; 3 modified: home.py, home.html, test_smoke.py)

## Accomplishments

- `app/routes/home.py` is now a 2-statement thin route: `dashboard_context(session, settings.display_tz)` straight into `pages/home.html` — the `ledger_view` import is gone from this route (the function itself stays in `app/services/ledger.py`, unused by any route but still exercised by tests).
- `pages/home.html` rebuilt per 23-UI-SPEC.md Interaction 1-4 exactly: weekday/date/time line, the catalog countdown line (empty-state link / closed / days-left / number-only branches), the tiles include, and the 10-column feed table with per-type populated cells (receipt: Срок/Кол-во/Себестоимость; sale/return: all data columns + «Розница» fallback; writeoff: Срок/Кол-во/Себестоимость; correction: Кол-во only; transfer: Срок/Кол-во only) and muted dashes everywhere else.
- `partials/dashboard_tiles.html` created: 4-tile `.metric-grid` (Сегодня/Неделя/Месяц each with Выручка/Прибыль/Расход; Склад with product count + cost/sale valuation + the `cost_unknown_count`/`sale_unknown_count` caveat lines copied verbatim from `finance_tiles.html`) — zero new CSS rules, reuses `.metric-grid`/`.metric-tile`/`.tile-label` verbatim.
- `tests/test_home.py` (new, 10 tests): page structure/headings, empty-catalog state (rest of page still renders), empty-feed state, closed-catalog «закрыт» text (never a negative number), open-catalog days-left countdown, and one feed-row test per receipt/sale/writeoff/transfer type asserting `<td>`-scoped type labels (not the nav bar, which reuses the same RU words) plus the «Подробнее» -> `/history?type=...&product=...` link.

## Task Commits

Task 2 followed a literal TDD RED -> GREEN cycle (verified failing before implementing):

1. **Task 1: home.py route rebuild** - `00d985d` (feat)
2. **Task 2 RED: failing tests/test_home.py** - `3ce1ba2` (test) - confirmed 10/10 failing against the still-unmodified home.html
3. **Task 2 GREEN: pages/home.html + dashboard_tiles.html** - `36bc656` (feat) - 10/10 passing; also fixed `tests/test_smoke.py`'s stale walking-skeleton assertion (see Deviations)

## Files Created/Modified

- `app/routes/home.py` - thin route, calls `dashboard_context`
- `app/templates/pages/home.html` - rebuilt Главная (date/time, catalog line, tiles include, 10-column feed)
- `app/templates/partials/dashboard_tiles.html` - new, 4-tile `.metric-grid`
- `tests/test_home.py` - new, 10 tests covering every behavior bullet in the plan
- `tests/test_smoke.py` - `test_home_page_renders` updated (see Deviations)

## Decisions Made

- Task 1's own verify command (`pytest tests/test_home.py -x`) targets a file that Task 2 creates — executed Task 1 first (route change, verified via a full-suite pytest run showing zero regressions), then ran Task 2's complete RED->GREEN cycle, which exercises Task 1's route wiring as well. No functional gap: the final `tests/test_home.py -x` run (post Task 2) covers both tasks' acceptance criteria together.
- Feed-row tests assert `<td>{{ label }}</td>` rather than a bare substring match, because the RU operation-type labels (Приход/Списание/Перемещение) also appear verbatim as nav-bar link text in `base.html` — a bare substring check would pass vacuously regardless of feed content. Caught during the RED run (2 of 10 tests passed unexpectedly before this fix) and corrected before the RED commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a stale test asserting retired walking-skeleton behavior**
- **Found during:** Task 2 (full-suite regression run after GREEN)
- **Issue:** `tests/test_smoke.py::test_home_page_renders` asserted `"Тестовый товар" in response.text` — the Phase-1 walking-skeleton behavior of showing the oldest active product's name on `/`. This plan's own objective explicitly retires that concept, so the assertion was testing behavior this plan intentionally removes, not a regression this plan introduced.
- **Fix:** Updated the assertion to `"Главная" in response.text` (the new dashboard's `<h1>`), keeping the test's original intent (prove `GET /` boots end-to-end with vendored htmx) while dropping the obsolete content check. The authoritative dashboard-content contract lives in the new `tests/test_home.py`.
- **Files modified:** tests/test_smoke.py
- **Verification:** `uv run pytest tests/test_smoke.py tests/test_home.py -q` — 11/11 passing; full suite `uv run pytest -q` — 892/892 passing.
- **Committed in:** 36bc656 (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, in-scope collateral from the plan's own stated objective)
**Impact on plan:** Necessary to keep the full suite green; no scope creep — the change only updates an assertion that tested behavior this plan explicitly retires.

## Issues Encountered

None beyond the two items already covered under Decisions Made / Deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Desktop Главная fully satisfies DASH-01..05: date/time, catalog countdown/empty-state, 4-tile metrics, 10-column feed linking into History.
- `dashboard_context` proved reusable end-to-end through the real route/template stack (Plan 03's service layer needed zero changes).
- Ready for Plan 07 (mobile home route) to build the mobile equivalent against the same `dashboard_context` call, per 23-UI-SPEC.md Interaction 5's "supplement, never replace the nav tile grid" contract.
- Full regression suite (`uv run pytest -q`) passes 892/892 after this plan.
- No blockers or concerns carried forward.

---
*Phase: 23-dashboard-history-rebuild*
*Completed: 2026-07-17*
