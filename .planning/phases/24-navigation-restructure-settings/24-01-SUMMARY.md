---
phase: 24-navigation-restructure-settings
plan: 01
subsystem: ui
tags: [jinja2, htmx, navigation, css]

requires: []
provides:
  - "8-item desktop top nav in base.html (NAV-08)"
  - "app/templates/partials/products_toolbar.html — always-visible two-group Товары toolbar (D-01/D-02/D-03/D-04/D-05)"
  - ".toolbar/.toolbar-group CSS classes in app/static/style.css, reused by later plans in this phase"
affects: [24-02-settings-hub, 24-03, 24-04, 24-05, 24-06]

tech-stack:
  added: []
  patterns:
    - "Static <div class=\"toolbar\"> composed of <div class=\"toolbar-group\"> blocks, each reusing existing .form-actions/.button/.muted verbatim — no new interactive component"

key-files:
  created:
    - app/templates/partials/products_toolbar.html
  modified:
    - app/templates/base.html
    - app/templates/pages/products_list.html
    - app/static/style.css
    - tests/test_smoke.py
    - tests/test_dictionary.py
    - tests/test_writeoffs.py
    - tests/test_receipts.py

key-decisions:
  - "Финансы active-state check simplified to plain startswith(\"/finance\") since Экспорт кассы leaves the nav entirely (its old carve-out excluding /finance/report is no longer needed)"
  - "Настройки nav link added with href=\"/settings\" even though the route does not exist yet — plan 24-02 creates it; this task only adds the link text/href per plan instructions"

patterns-established:
  - "Toolbar pattern: <div class=\"toolbar\"> > <div class=\"toolbar-group\"> > <span class=\"muted\">Label</span> + <div class=\"form-actions\">...</div> — reusable for any future always-visible action group"

requirements-completed: [NAV-01, NAV-02, NAV-03, NAV-08]

duration: 25min
completed: 2026-07-17
---

# Phase 24 Plan 01: Nav Reduction + Товары Toolbar Summary

**Desktop top nav cut from 17 items to 8 (NAV-08), with Приход/Списание/Справочник/Категории/Каталоги re-homed into a new always-visible two-group toolbar on the Товары page (D-01..D-05)**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-17T20:08:00Z
- **Completed:** 2026-07-17T20:33:00Z
- **Tasks:** 3
- **Files modified:** 8 (1 created, 7 modified)

## Accomplishments
- `base.html`'s `<nav>` reduced from 17 `<a>` elements to exactly 8 (Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы, Настройки), proven by a new smoke test
- New `partials/products_toolbar.html`: static, always-visible two-group toolbar on `/products` (Действия: Приход/Списание; Справочники: Категории/Справочник/Каталоги) — zero JS, zero click-to-reveal, per D-05
- 3 pre-existing nav-presence tests (dictionary, writeoff, receipts) repointed from `/` to `/products` to match the new IA
- Every route removed from the nav (`/categories`, `/warehouses`, `/dictionary`, `/backup`, `/export`, `/finance/report`) confirmed still reachable by direct URL

## Task Commits

Each task was committed atomically:

1. **Task 1: Reduce desktop top nav to 8 items (NAV-08)** - `b428a42` (feat)
2. **Task 2: Товары toolbar partial + CSS (D-01/D-02/D-03/D-04/D-05)** - `7a2feca` (feat)
3. **Task 3: Update the 3 toolbar-relocated nav-presence tests** - `319f92c` (test)

_No plan-metadata commit yet — this is a worktree-mode execution; the orchestrator handles the final docs commit after merge._

## Files Created/Modified
- `app/templates/base.html` — `<nav>` block reduced to exactly 8 `<a>` items
- `app/templates/partials/products_toolbar.html` (NEW) — static two-group action toolbar
- `app/templates/pages/products_list.html` — includes the new toolbar between `<h1>` and the product rows list
- `app/static/style.css` — 2 new rules: `.toolbar`, `.toolbar-group`
- `tests/test_smoke.py` — new `test_web_top_nav_has_exactly_eight_items`
- `tests/test_dictionary.py` — `test_web_nav_has_dictionary_link` now asserts via `/products`
- `tests/test_writeoffs.py` — `test_web_writeoff_reachable_from_nav` now asserts via `/products`
- `tests/test_receipts.py` — `test_web_nav_has_receipts_link` now asserts via `/products`

## Decisions Made
- Simplified the Финансы active-state Jinja check to plain `startswith("/finance")` — the old carve-out excluding `/finance/report` existed only because that route had its own nav item ("Экспорт кассы"); that item is now gone entirely (moving to the Настройки hub in plan 24-02), so the carve-out is dead logic.
- Left `href="/settings"` pointing at a route that does not exist yet (404 until plan 24-02 lands) — this is the plan's explicit instruction; Task 1 only adds the nav link, not the destination page.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Full-suite run surfaced 5 pre-existing failures** in `tests/test_backup.py::test_web_nav_has_backup_link`, `tests/test_export.py::test_web_nav_has_export_link`, `tests/test_finance_reports.py::test_web_home_nav_links_to_finance_report`, `tests/test_finance_reports.py::test_web_finance_report_nav_item_marks_active`, and `tests/test_warehouses.py::test_web_nav_has_warehouses_link`. These all assert nav-link presence on `GET /`, which now no longer carries Резервные копии/Экспорт/Экспорт кассы/Склады links (removed by Task 1, per plan design — those items move to the Настройки hub / Товары toolbar in later plans of this phase). This is **not a regression introduced outside plan scope**: `.planning/phases/24-navigation-restructure-settings/24-02-PLAN.md` Task 3 explicitly owns updating these exact 5 tests to assert reachability via `/settings` (created by that same plan) instead of `/`. Fixing them here would be premature — `/settings` does not exist until 24-02 lands, so repointing them now would just trade one failure for a 404. Left untouched, to be resolved by 24-02 as already planned.

The plan's own `<verification>` section only requires the **touched-module sweep** (`test_smoke.py`, `test_catalog.py`, `test_dictionary.py`, `test_writeoffs.py`, `test_receipts.py`, `test_mobile_wiring.py` — all 160 tests pass) and success criterion 4 (removed routes still 200 by direct URL — confirmed). The full-suite run was informational per the plan's own verification note ("confirming no other test still depends on the old 17-item nav shape") — it correctly identified the exact 5 tests plan 24-02 is scoped to fix, and no others.

## Next Phase Readiness
- `.toolbar`/`.toolbar-group` CSS and the `products_toolbar.html` pattern are ready for reuse (mirrored on `/m/products` per D-11, referenced in 24-UI-SPEC.md).
- The 8-item nav (including the not-yet-resolving `/settings` link) is the foundation plan 24-02 builds on to create the Настройки hub.
- 5 known-failing tests (documented above) are explicitly in scope for 24-02 Task 3 — no action needed from this plan.

---
*Phase: 24-navigation-restructure-settings*
*Completed: 2026-07-17*
