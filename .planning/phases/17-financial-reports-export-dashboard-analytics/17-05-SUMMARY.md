---
phase: 17-financial-reports-export-dashboard-analytics
plan: 05
subsystem: finance-reports
tags: [jinja2, navigation, ui-gap-closure, finance, mobile]

# Dependency graph
requires:
  - phase: 17-02
    provides: "app/templates/pages/finance.html: «Показатели» tiles section, existing in-page report link"
  - phase: 17-03
    provides: "GET /finance/report (desktop cash-flow report + CSV page), the original unstyled in-page link"
  - phase: 17-04
    provides: "GET /m/finance/report (mobile cash-flow report + CSV page), app/templates/mobile_pages/finance.html"
provides:
  - "app/templates/base.html: top-level nav item linking directly to /finance/report, reachable in one hop from every desktop page including Главная (/)"
  - "app/templates/mobile_pages/home.html: 10th mobile tile linking directly to /m/finance/report, reachable in one hop from /m/"
  - "app/templates/pages/finance.html + mobile_pages/finance.html: .button-styled, CSV-worded in-page report links (were bare unstyled <a> tags)"
  - "app/templates/pages/reports_landing.html: consistent CSV wording on the cash-movements link"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nav-item mutual-exclusion pattern: the existing /finance nav item's active-class condition gained a `and not request.url.path.startswith(\"/finance/report\")` guard so the new /finance/report nav item and the Финансы item are never both marked active simultaneously"
    - "Reused the pre-existing a.button CSS class (app/static/style.css) verbatim for CTA-level in-page report links on both desktop and mobile — no new styles added"

key-files:
  created: []
  modified:
    - app/templates/base.html
    - app/templates/pages/finance.html
    - app/templates/pages/reports_landing.html
    - app/templates/mobile_pages/home.html
    - app/templates/mobile_pages/finance.html
    - tests/test_finance_reports.py

key-decisions:
  - "Task split mirrors the desktop/mobile symmetry of the whole Phase 17 pattern: Task 1 closes the desktop nav-item + finance.html + reports_landing.html gap, Task 2 closes the mobile tile-grid + mobile finance.html gap, each independently committed and tested"
  - "New desktop nav item labeled «Экспорт кассы» (distinct wording from the pre-existing unrelated /export nav item, which is the product/stock export) placed immediately after the existing Финансы item in base.html, inherited by every desktop page via the shared <nav>"
  - "Mobile tile added as the 10th tile (even count, no 2-column grid orphan) immediately after the existing Финансы tile on mobile_pages/home.html, matching desktop wording for consistency"

patterns-established: []

requirements-completed: [FIN-08, FIN-09]

# Metrics
duration: 20min
completed: 2026-07-15
---

# Phase 17 Plan 05: UAT Gap Closure — Navigation Entry Points to /finance/report Summary

**Closed 17-UAT.md Test 2 (nav-discoverability gap) by adding a distinctly-labeled, CSV/export-worded top-nav item (desktop) and mobile home tile pointing directly at `/finance/report` / `/m/finance/report`, plus restyling the pre-existing in-page report links as `.button` CTAs on both platforms — no new routes or services, five Jinja templates only.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-15

## What Was Built

### Task 1: Desktop entry points

- `app/templates/base.html`: added a new nav item `<a href="/finance/report">Экспорт кассы</a>`, immediately after the existing `Финансы` item. Adjusted the `Финансы` item's active-class condition to exclude `/finance/report` paths so the two items are never simultaneously active.
- `app/templates/pages/finance.html`: the bare `<p><a href="/finance/report">Отчёт по кассе за период</a></p>` link is now `<p><a class="button" href="/finance/report">Отчёт и экспорт CSV</a></p>` — reuses the existing `a.button` CSS class.
- `app/templates/pages/reports_landing.html`: relabeled the cash-movements link from `Движения кассы` to `Экспорт кассы (CSV)`.
- Added 4 web tests to `tests/test_finance_reports.py` proving: `GET /` contains the nav link + label; `GET /finance/report` marks the nav item active (and not the sibling); `GET /finance` shows the button-styled CSV link; `GET /reports` shows CSV wording.

### Task 2: Mobile entry points

- `app/templates/mobile_pages/home.html`: added a 10th tile `<a class="mobile-tile" href="/m/finance/report">Экспорт кассы</a>` immediately after the existing `Финансы` tile.
- `app/templates/mobile_pages/finance.html`: the bare `<p><a href="/m/finance/report">Отчёт по кассе за период</a></p>` link is now `<p><a class="button" href="/m/finance/report">Отчёт и экспорт CSV</a></p>`.
- Added 2 web tests proving `GET /m/` contains the new tile + label, and `GET /m/finance` shows the button-styled CSV link. Confirmed no regression in `test_mobile_home.py::test_mobile_home_renders_all_tiles_in_order` and `test_mobile_wiring.py::test_mobile_home_lists_all_eight_tile_hrefs`.

## Verification

- `uv run pytest tests/test_finance_reports.py` — 38 passed (32 pre-existing + 6 new navigation tests).
- `uv run pytest tests/test_finance_reports.py tests/test_mobile_home.py tests/test_mobile_wiring.py` — 44 passed, no regression.
- `uv run pytest` (full suite) — 682 passed, 0 failed.
- `uv run ruff check app` — 4 pre-existing errors in unrelated files (`app/routes/mobile_sales.py`, `app/routes/products.py`, line-length only); zero errors in any file touched by this plan. Out of scope per the deviation-rules scope boundary (not caused by this plan's changes).

## Deviations from Plan

None — plan executed exactly as written. Both tasks' acceptance criteria were met on the first implementation pass with no auto-fixes needed.

## Auth Gates

None encountered — this plan touches only static Jinja templates and tests, no auth-protected surface.

## Known Stubs

None.

## Threat Flags

None — this plan introduces no new routes, query params, or trust boundaries; it only relabels/restyles existing static `<a>` targets on already-threat-modeled GET routes (see plan's `<threat_model>`, T-17-10/T-17-11, both `accept` disposition, unchanged).

## Self-Check: PASSED

- FOUND: app/templates/base.html (new nav item present)
- FOUND: app/templates/pages/finance.html (button-styled link present)
- FOUND: app/templates/pages/reports_landing.html (CSV wording present)
- FOUND: app/templates/mobile_pages/home.html (10th tile present)
- FOUND: app/templates/mobile_pages/finance.html (button-styled link present)
- FOUND: tests/test_finance_reports.py (6 new tests present)
- FOUND commit 5ff71b7: feat(17-05): desktop entry points to /finance/report (UAT gap closure)
- FOUND commit 2308d01: feat(17-05): mobile entry points to /m/finance/report (UAT gap closure)
