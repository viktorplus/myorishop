---
phase: 24-navigation-restructure-settings
plan: 02
subsystem: ui
tags: [fastapi, jinja2, settings-hub, navigation]

# Dependency graph
requires:
  - phase: 24-navigation-restructure-settings
    provides: "24-01's nav-reduction groundwork (top nav is being trimmed across this phase's plans)"
provides:
  - "GET /settings hub page (D-06) linking to Склады, Резервные копии, Экспорт кассы with live summaries"
  - "settings_summary(session, backup_dir) service function"
  - "/backup page with embedded CSV export links (D-07/NAV-04)"
affects: [24-navigation-restructure-settings (later plans wiring the top nav "Настройки" link, e.g. 24-06)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Settings hub composes existing service functions (list_warehouses, list_backups) rather than adding new queries — thin route + thin service, matching backup_page's established shape"

key-files:
  created:
    - app/services/settings.py
    - app/routes/settings.py
    - app/templates/pages/settings.html
    - tests/test_settings.py
  modified:
    - app/main.py
    - app/routes/__init__.py
    - app/templates/pages/backup.html
    - tests/test_warehouses.py
    - tests/test_backup.py
    - tests/test_export.py
    - tests/test_finance_reports.py

key-decisions:
  - "Registered settings.router in app/main.py after finance.router (near the other admin/report-ish routers), before the mobile_* group — exact position among non-mobile routers is not test-asserted, only single-registration is"
  - "Aliased app/routes/__init__.py's config import from `settings` to `_config_settings` to resolve a package-attribute naming collision with the new app/routes/settings.py submodule (see Deviations)"

requirements-completed: [NAV-04, NAV-05, NAV-06]

# Metrics
duration: 35min
completed: 2026-07-17
---

# Phase 24 Plan 02: Настройки hub + embedded Экспорт Summary

**New `/settings` hub page (Склады/Резервные копии/Экспорт кассы with live warehouse-count and last-backup summaries) plus the 3 CSV export links embedded directly into `/backup`, closing out the nav-reduction admin landing spots from 24-01.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3/3 completed
- **Files modified:** 11 (4 created, 7 modified)

## Accomplishments
- `GET /settings` renders a 3-row hub: Склады (with `{N} складов` summary), Резервные копии (with `Последняя копия: {date}` or `Резервных копий пока нет`), and Экспорт кассы (no summary, per D-06 scope)
- `/backup` now embeds the 3 CSV download links (`/export/products.csv`, `/export/sales.csv`, `/export/customers.csv`) directly, so `/export` is no longer needed as a separate nav destination (D-07/NAV-04)
- All 5 relocated nav-presence regression tests retargeted from `GET /` to `GET /settings` or `GET /backup`, plus 4 new dedicated `/settings` tests
- Full suite: 900 passed, 0 failed

## Task Commits

1. **Task 1: Настройки hub — service, route, template, registration** - `c7a3a92` (feat)
2. **Task 2: Embed Экспорт into /backup** - `45528a6` (feat)
3. **Task 3: Update relocated nav-presence tests + new tests/test_settings.py** - `e3cbcd3` (test)

_Note: SUMMARY.md commit handled separately by the worktree agent per orchestrator instructions (STATE.md/ROADMAP.md updates deferred to orchestrator)._

## Files Created/Modified
- `app/services/settings.py` - `settings_summary(session, backup_dir) -> {warehouse_count, last_backup_iso}`
- `app/routes/settings.py` - `GET /settings` thin route
- `app/templates/pages/settings.html` - Настройки hub markup (3 `.field` rows)
- `app/main.py` - registers `settings.router`
- `app/routes/__init__.py` - aliased config `settings` import to `_config_settings` (collision fix, see Deviations)
- `app/templates/pages/backup.html` - gains an `<h2>Экспорт</h2>` section with 3 CSV links
- `tests/test_warehouses.py`, `tests/test_backup.py`, `tests/test_export.py`, `tests/test_finance_reports.py` - retargeted nav-presence assertions
- `tests/test_settings.py` (new) - 4 tests for the hub page

## Decisions Made
- Placed `app.include_router(settings.router)` after `finance.router` and before the `mobile_*` group in `app/main.py` — the plan's literal instruction ("after sales and before warehouses alphabetically") describes the *import list* ordering (which is alphabetized), not the `include_router` call order (which follows a different logical/historical grouping unrelated to alphabetization); no test asserts registration position, only that it appears exactly once.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed a package-attribute naming collision between the new `app/routes/settings.py` submodule and `app/routes/__init__.py`'s existing `from app.config import settings` import**
- **Found during:** Task 1, first `import app.main` smoke check
- **Issue:** `app/routes/__init__.py` (shared template environment module) already did `from app.config import settings`, which binds an attribute named `settings` on the `app.routes` package. Once `app/routes/settings.py` (the new router submodule) was created, `from app.routes import settings` in `app/main.py` resolved to the pre-existing config `Settings` instance instead of the new submodule (Python resolves `from package import name` via `getattr(package, name)` first, and the package already had that attribute set). This raised `AttributeError: 'Settings' object has no attribute 'router'` at app startup.
- **Fix:** Aliased the import in `app/routes/__init__.py` from `settings` to `_config_settings`, and updated its one usage site (`local_dt` Jinja filter lambda) accordingly. No other file in the codebase referenced `app.routes.settings` as the config instance (verified via grep), so this is a safe, contained rename.
- **Files modified:** `app/routes/__init__.py`
- **Verification:** `uv run python -c "import app.main"` succeeds; full test suite (900 tests) passes, including all `local_dt`-filter-dependent template renders.
- **Committed in:** `c7a3a92` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary for the plan's own required artifact (`app/routes/settings.py`) to load at all — no scope creep, purely a naming-collision fix confined to one import alias.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `/settings` and `/backup` are fully working landing spots for Склады, Резервные копии, Экспорт, and Экспорт кассы
- The top-nav "Настройки" link itself (NAV-08) is out of this plan's scope — later plans in this phase (e.g. 24-06) wire it into the reduced top nav
- No blockers for subsequent 24-xx plans

---
*Phase: 24-navigation-restructure-settings*
*Completed: 2026-07-17*

## Self-Check: PASSED

All created files verified present; all 4 task/summary commit hashes (c7a3a92, 45528a6, e3cbcd3, e22c061) verified in git log.
