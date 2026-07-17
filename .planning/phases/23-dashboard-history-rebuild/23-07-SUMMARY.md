---
phase: 23-dashboard-history-rebuild
plan: 07
subsystem: mobile-ui
tags: [fastapi, jinja2, mobile, dashboard]

# Dependency graph
requires:
  - phase: 23-dashboard-history-rebuild
    provides: "Plan 03's app/services/dashboard.py::dashboard_context(session, tz_name)"
provides:
  - "GET /m/ — mobile Главная: 10-tile nav grid (unchanged) + DASH-01..05 dashboard content below it"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "FEED_FIELDS Jinja dict: per-type feed-card field presence (mirrors history_cards.html's per-type `columns` narrowing), inlined in the template since the feed itself is not type-filtered server-side"

key-files:
  created: []
  modified:
    - app/routes/mobile_home.py
    - app/templates/mobile_pages/home.html
    - tests/test_mobile_home.py

key-decisions:
  - "Feed cards OMIT a field's entire line for types it does not apply to (not a muted-dash placeholder) — required so a sale card visibly differs from a receipt card (Прибыль/Покупатель present vs absent), matching the plan's acceptance criteria literally"
  - "4-tile metric grid and catalog line are inlined directly in mobile_pages/home.html (not {% include %}'d from a shared partial) — D-10's 'own layout' framing, consistent with 23-06's dashboard_tiles.html being desktop-only markup"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05]

# Metrics
duration: ~35min
completed: 2026-07-17
---

# Phase 23 Plan 07: Mobile Dashboard Rebuild Summary

**`/m/` rebuilt from a static 13-line stub into the same DASH-01..05 dashboard as desktop (same `dashboard_context()` call), with the existing 10-tile nav grid kept first and byte-for-byte unchanged, and a `FEED_FIELDS`-driven per-type card layout for the recent-operations feed.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-07-17
- **Tasks:** 2
- **Files modified:** 3 (app/routes/mobile_home.py, app/templates/mobile_pages/home.html, tests/test_mobile_home.py)

## Accomplishments

- `app/routes/mobile_home.py` — `GET /m/` now calls `dashboard_context(session, settings.display_tz)`, identical to `app/routes/home.py`'s call shape; adds a `Depends(get_session)` dependency the route never had before.
- `app/templates/mobile_pages/home.html` — the existing 10-tile `.mobile-tile-grid` stays first and untouched; below it: `<h2>Показатели</h2>`, the date/weekday/time line, the same 4-branch catalog-line Jinja as desktop (empty-state link / closed / countdown / number-only), a `.metric-grid` with the same 4 tiles as desktop (Сегодня/Неделя/Месяц/Склад, inlined per D-10's "own layout"), `<h2>Последние операции</h2>`, and one `.mobile-card` per feed entry with per-type field narrowing (`FEED_FIELDS` map) and a «Подробнее» link into `/m/history?type=...&product=...`.
- `tests/test_mobile_home.py` — extended from 1 to 5 tests: the original tile-order test unmodified; a structural Pitfall-1 regression guard (nav grid's last tile textually precedes «Показатели»); an empty-catalog-state test (link renders, tiles still render); and two feed-card narrowing tests (receipt omits Прибыль/Покупатель, sale shows both).

## Task Commits

Each task committed individually; Task 2 executed as a literal TDD RED -> GREEN pair:

1. **Task 1: mobile_home.py route rebuild**
   - `fee8a6f` feat(23-07): mobile_home.py route rebuild calls dashboard_context
2. **Task 2: mobile_pages/home.html — dashboard content below the untouched nav grid**
   - `1b94d8f` test(23-07): add failing tests for mobile dashboard content — confirmed RED (4/5 new tests failed against the unmodified nav-grid-only template; the pre-existing tile-order test still passed)
   - `46d831b` feat(23-07): mobile Главная dashboard content below the untouched nav grid — GREEN, 5/5 tests passing

## Files Created/Modified

- `app/routes/mobile_home.py` - rebuilt to call `dashboard_context`, gained a session dependency
- `app/templates/mobile_pages/home.html` - nav grid preserved verbatim + dashboard content (date/time, catalog line, 4-tile metric grid, per-type feed cards) appended below it
- `tests/test_mobile_home.py` - extended with 4 new tests (structural regression guard, empty-catalog state, receipt/sale feed-card narrowing)

## Decisions Made

- Per-type feed-card field narrowing OMITS an inapplicable field's whole line (via a `FEED_FIELDS` dict of applicable field-name tuples per `op.type`), rather than rendering every line with a muted-dash placeholder as the desktop 10-column table does. This diverges slightly from a literal reading of "muted dash otherwise" in the plan's `<action>` text, but is required by the plan's own acceptance criteria ("a feed card for a receipt does not [show Прибыль]") — a dash-value line would still contain the literal word "Прибыль". This mirrors `history_cards.html`'s existing per-type `columns`-narrowing convention (Plan 05), computed inline in the template since `dashboard_context()`'s feed is not itself type-filtered.
- The 4-tile metric grid and catalog-line Jinja are duplicated inline in `mobile_pages/home.html` rather than shared via `{% include %}` with desktop's `dashboard_tiles.html` (Plan 06) — per the plan's explicit instruction and D-10 ("mobile's own layout, not a shared partial").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertions for feed-card field narrowing initially checked the whole response body**
- **Found during:** Task 2 GREEN verification
- **Issue:** `test_mobile_home_receipt_feed_card_omits_profit_and_customer` and `test_mobile_home_sale_feed_card_shows_profit_and_customer` originally asserted `"Прибыль" not in body` / `"Прибыль" in body` against the full page body. The 4-tile metric grid (Сегодня/Неделя/Месяц) legitimately renders the label "Прибыль" on every page load regardless of feed content, making the receipt-card assertion fail even with correct template behavior (false negative on GREEN run).
- **Fix:** Scoped both assertions to `response.text.split("<h2>Последние операции</h2>", 1)[1]` — the feed section only — before checking for "Прибыль"/"Покупатель" presence.
- **Files modified:** tests/test_mobile_home.py
- **Commit:** 46d831b (folded into the GREEN commit; caught before that commit was made, not a separate fix-up)

None else — plan executed as written otherwise.

## Issues Encountered

None beyond the self-caught test-scoping bug above (caught during the GREEN verification run, fixed before commit, full suite confirmed 886/886 passing afterward).

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Both desktop (`/`, Plan 06, executed in a parallel wave-3 worktree) and mobile (`/m/`, this plan) now read from the same `dashboard_context()` composer — DASH-01..05 fully satisfied on both surfaces once both plans merge.
- `/m/history?type=...&product=...` deep links from feed cards are consumed by Plan 05's mobile history rebuild (already shipped).
- No blockers or concerns carried forward.

---
*Phase: 23-dashboard-history-rebuild*
*Completed: 2026-07-17*
