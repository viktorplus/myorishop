---
phase: 24-navigation-restructure-settings
plan: 07
subsystem: ui
tags: [jinja2, htmx, mobile-nav, fastapi]

# Dependency graph
requires:
  - phase: 24-navigation-restructure-settings
    provides: "24-01 (desktop nav 8-item reduction), 24-06 (mobile Товары page + toolbar mirror)"
provides:
  - "Mobile Товары toolbar links to /m/transfers, /m/corrections, /m/search (closes CR-01)"
  - "Desktop nav active-state correctly highlights Настройки for /finance/report (closes WR-03)"
  - "Two regression tests proving rendered-link presence, not just direct-URL 200"
affects: [24-VERIFICATION, 24-REVIEW]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Rendered-link regression tests (assert href string in response.text) as the standard proof of UI reachability, distinct from route-registration 200 checks"

key-files:
  created: []
  modified:
    - app/templates/mobile_partials/products_toolbar.html
    - tests/test_mobile_products.py
    - app/templates/base.html
    - tests/test_finance_reports.py

key-decisions:
  - "Поиск and Корректировка placed on the same mobile Товары toolbar as Перемещение (not on mobile_pages/home.html) — D-11's language establishes one catch-all landing zone; re-adding links to Главная would partially reverse D-10's removal of the tile-hub role. Корректировка fits the existing Действия group semantically (stock-quantity action like Приход/Списание); Поиск fits Справочники (lookup tool like Категории/Справочник/Каталоги). No third toolbar-group invented."

requirements-completed: [NAV-07, MOB-01]

# Metrics
duration: 25min
completed: 2026-07-17
---

# Phase 24 Plan 07: Gap Closure (CR-01 mobile reachability + WR-03 nav highlight) Summary

**Extended the mobile Товары toolbar with 3 new rendered links (Перемещение, Корректировка, Поиск) and fixed the desktop nav active-state so /finance/report highlights Настройки instead of Финансы — both gaps closed with regression tests proving rendered-link/highlight behavior, not just route-registration or direct-URL checks.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-17T21:40:00Z (approx)
- **Completed:** 2026-07-17T22:05:37Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Mobile `/m/products` toolbar now renders working `<a href>` links to `/m/transfers`, `/m/corrections`, and `/m/search` — closing CR-01 (24-REVIEW.md) and the corresponding 24-VERIFICATION.md gap (D-11 named Перемещение explicitly; Поиск/Корректировка had no removal authorization)
- `/finance/report` now highlights Настройки as the active top-nav tab (matching D-08, which moved Экспорт кассы reachability under Настройки); `/finance` still correctly highlights Финансы — closing WR-03 (24-REVIEW.md)
- Added `test_mobile_products_toolbar_reaches_transfers_corrections_search` — asserts rendered `href` presence, a class of regression that `test_mobile_wiring.py`'s direct-URL 200 checks cannot catch
- Added `test_web_finance_report_highlights_settings_not_finance` and `test_web_finance_page_still_highlights_finance` — proves the fix and guards against over-broad regression on the unaffected `/finance` page

## Task Commits

Each task was committed atomically:

1. **Task 1: Close CR-01 — add Перемещение/Корректировка/Поиск to the mobile Товары toolbar + regression test** - `728289e` (feat)
2. **Task 2: Close WR-03 — desktop nav active-state fix for /finance/report + regression test** - `df4b6f1` (fix)

**Plan metadata:** (pending — this SUMMARY commit)

## Files Created/Modified
- `app/templates/mobile_partials/products_toolbar.html` - Действия group gained `<a href="/m/transfers">Перемещение</a>` and `<a href="/m/corrections">Корректировка</a>`; Справочники group gained `<a href="/m/search">Поиск</a>` — 8 total `.button` entries, up from 5, still 2 `.toolbar-group` blocks
- `tests/test_mobile_products.py` - New test `test_mobile_products_toolbar_reaches_transfers_corrections_search` asserting all three hrefs render in `/m/products` response
- `app/templates/base.html` - Финансы active-state condition now excludes `/finance/report`; Настройки active-state condition now includes `/finance/report`
- `tests/test_finance_reports.py` - New tests `test_web_finance_report_highlights_settings_not_finance` and `test_web_finance_page_still_highlights_finance`

## Decisions Made
- Поиск and Корректировка placed on the mobile Товары toolbar (same as Перемещение), not on `mobile_pages/home.html` — see `key-decisions` in frontmatter for full rationale (already documented in the plan's own placement-decision block, executed as specified).
- Desktop's own lack of any `/corrections` or `/search` link is a pre-existing, out-of-scope condition confirmed via `git log -p -- app/templates/base.html` (no commit ever added such a link) — not touched by this plan, per the plan's explicit scope note.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's `<action>` blocks precisely; no auto-fixes, no blocking issues, no architectural questions arose.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Verification

- `uv run pytest tests/test_mobile_products.py -q` — 4/4 passed (3 existing + 1 new)
- `uv run pytest tests/test_mobile_wiring.py -q` — 5/5 passed, unchanged (route registration untouched)
- `uv run pytest tests/test_finance_reports.py tests/test_smoke.py::test_web_top_nav_has_exactly_eight_items tests/test_settings.py -q` — 45/45 passed
- `uv run pytest tests/test_mobile_products.py tests/test_mobile_wiring.py tests/test_finance_reports.py tests/test_smoke.py tests/test_settings.py -q` — 55/55 passed (full touched-module sweep)
- `uv run pytest -q` (full suite) — 919 passed, 3 warnings (pre-existing SAWarning/StarletteDeprecationWarning noise, unrelated to this plan), no regressions
- `grep -c 'href="/m/' app/templates/mobile_partials/products_toolbar.html` — 5 (not the plan's estimated 3: the toolbar already had 2 pre-existing `/m/` links — `/m/receipts`, `/m/writeoff` — before this task added 3 more: `/m/transfers`, `/m/corrections`, `/m/search`. Total is correctly 5, matching 2 existing + 3 new; the plan's verification note's arithmetic undercounted the pre-existing `/m/receipts`/`/m/writeoff` links when estimating "3". Functionally correct — all three new hrefs present and asserted by the regression test.)

## Next Phase Readiness

24-VERIFICATION.md's gap (5/6 → 6/6 truths) and 24-REVIEW.md's CR-01 (critical) and WR-03 (warning) findings are both closed. A re-verification of Phase 24 would find the phase Goal statement — "every secondary action is reachable from the page it belongs to — on desktop and mobile alike" — fully true. No blockers for closing out Phase 24.

---
*Phase: 24-navigation-restructure-settings*
*Completed: 2026-07-17*
