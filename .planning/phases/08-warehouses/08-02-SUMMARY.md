---
phase: 08-warehouses
plan: 02
subsystem: ui
tags: [fastapi, htmx, jinja2, warehouse, crud]

# Dependency graph
requires:
  - phase: 08-warehouses (Plan 08-01)
    provides: Warehouse model, migration 0007 (frozen seed row), and app/services/warehouses.py CRUD + warn-but-allow delete guard
provides:
  - "/warehouses" management page: inline add, per-row inline edit, delete (with warn-but-allow last-active guard), restore
  - Router registration (app.include_router(warehouses.router)) and "Склады" nav link reachable from every page
affects: [09-batch-tracking (Batch.warehouse_id FK will reference this page's data), 10-warehouse-transfers-expiry-reporting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-08 settings-style single-page CRUD: every POST (add/edit/delete/restore) re-renders partials/warehouse_rows.html in place, no HX-Redirect, no separate /new or /{id}/edit page"
    - "D-09 always-visible soft-delete: list_warehouses never filters deleted_at, deleted rows render muted with a Восстановить action instead of disappearing"
    - "warning_id context flag renders an inline warn-but-allow block directly under the affected row (mirrors sale_price_warning.html's confirm=1 + client-side-only Отмена dismiss pattern)"

key-files:
  created:
    - app/routes/warehouses.py
    - app/templates/pages/warehouses.html
    - app/templates/partials/warehouse_rows.html
  modified:
    - app/main.py
    - app/templates/base.html
    - tests/test_warehouses.py

key-decisions:
  - "Router registration (app.main.py) was moved into Task 1 instead of Task 2 as planned — Task 1's own acceptance criteria requires `pytest tests/test_warehouses.py -k web -x` to pass, which is unreachable via TestClient without the router being included in the app. Task 2 then only needed to add the nav link."
  - "tests/conftest.py's engine fixture builds schema via Base.metadata.create_all (per 08-VALIDATION.md Wave 0: 'No new fixtures needed'), which does NOT run the Alembic seed migration — so the client fixture starts with ZERO warehouses, unlike a real post-migration DB. Web tests create their own warehouses via the session fixture (mirroring test_dictionary.py) instead of asserting the migration-seeded 'Склад по умолчанию' row."

patterns-established:
  - "Empty-state fallback ('Складов пока нет') only reachable in tests (pre-migration state); production DBs always have at least the frozen seed row per D-03"

requirements-completed: [WH-01]

# Metrics
duration: 6min
completed: 2026-07-11
---

# Phase 8 Plan 02: Warehouse Management Page (Routes, Templates, Nav) Summary

**`/warehouses` settings-style page with inline add/edit/delete/restore wired to the Plan 08-01 service layer — every write re-renders the rows partial in place, deleted warehouses stay visible with a restore action, and deleting the last active warehouse is warn-but-allow with zero writes until confirmed.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-11T09:36:32+02:00
- **Completed:** 2026-07-11T09:41:36+02:00
- **Tasks:** 2 completed
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments
- `GET /warehouses`, `POST /warehouses`, `POST /warehouses/{id}`, `POST /warehouses/{id}/delete`, `POST /warehouses/{id}/restore` — all wired to `app/services/warehouses.py`, every response re-renders `partials/warehouse_rows.html` (D-08), zero `HX-Redirect` usage in the module
- Deleting a non-last-active warehouse soft-deletes immediately; the row stays visible, muted, with a "Восстановить" button (D-09)
- Deleting the LAST active warehouse performs zero writes and renders an inline "Это последний активный склад" warning with a "Удалить всё равно" (`confirm=1`) button and a client-side-only "Отмена" dismiss (mirrors `sale_price_warning.html`)
- "Склады" nav link added to `base.html`, positioned after "Категории" and before "Приход", active-state matches path prefix
- Full suite green: 262 passed (247 pre-existing + 15 warehouse tests across Plans 08-01 and 08-02)

## Task Commits

Each task followed RED -> GREEN (TDD) for Task 1; Task 2 was a small additive change:

1. **Task 1: /warehouses routes + page + rows partial**
   - `189ad55` (test) - add failing web-layer tests for /warehouses routes
   - `c64f4a5` (feat) - implement /warehouses routes, page, and rows partial (includes router registration, moved up from Task 2 — see Decisions)
2. **Task 2: Nav link + router registration + full-phase verification**
   - `1ad6851` (feat) - add Склады nav link
3. **Post-task fix (acceptance-criteria compliance):**
   - `c09b0f5` (fix) - drop literal "HX-Redirect" string from a code comment so the Pitfall-1 grep-count acceptance check (`grep -c "HX-Redirect" app/routes/warehouses.py` == 0) passes literally, not just in spirit

_No refactor commits needed._

## Files Created/Modified
- `app/routes/warehouses.py` - new router: page + add/update/delete/restore routes, all rows-partial-only responses
- `app/templates/pages/warehouses.html` - page shell: extends base.html, inline add form, includes rows partial
- `app/templates/partials/warehouse_rows.html` - swap target `#warehouse-rows`, row-level edit/delete/restore, `warning_id`-driven inline warn-but-allow block, empty-state fallback
- `app/main.py` - imports `warehouses`, registers `app.include_router(warehouses.router)` after `categories.router`
- `app/templates/base.html` - "Склады" nav `<a href="/warehouses">` after "Категории", before "Приход"
- `tests/test_warehouses.py` - added 6 web-layer tests (page render, add/edit rows, 422 validation partial, deleted-stays-visible-with-restore, last-active warn-then-confirm, nav link)

## Decisions Made
- Moved router registration from Task 2 into Task 1's commit, since Task 1's own `<verify>` command (`pytest tests/test_warehouses.py -k web -x`) requires the app's `TestClient` to actually reach `/warehouses`, which is impossible without `app.include_router(warehouses.router)` already present. Task 2 then only added the nav link, per its remaining scope.
- Web tests build their own warehouse rows via the `session` fixture (`add_warehouse(session, ...)`) rather than relying on the migration-seeded "Склад по умолчанию" row, because `tests/conftest.py`'s `engine` fixture creates schema via `Base.metadata.create_all` (confirmed by 08-VALIDATION.md's own Wave 0 note: "No new fixtures needed"), which does not run the Alembic seed migration. This is a pre-existing test-infra fact, not a plan deviation in behavior — `soft_delete_warehouse`/`list_warehouses` behave identically either way.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Router registration moved from Task 2 into Task 1**
- **Found during:** Task 1 (writing the GREEN implementation)
- **Issue:** Task 1's acceptance criteria requires `uv run pytest tests/test_warehouses.py -k web -x` to pass, but the plan assigned `app.include_router(warehouses.router)` to Task 2. Without registration, every web test would 404 regardless of route/template correctness.
- **Fix:** Added the `warehouses` import and `app.include_router(warehouses.router)` call to `app/main.py` as part of Task 1's commit; Task 2 then only added the nav link (its router-registration action step was already satisfied).
- **Files modified:** app/main.py
- **Verification:** `uv run pytest tests/test_warehouses.py -k web -x` — 5/5 passed after Task 1's commit
- **Committed in:** c64f4a5 (Task 1 commit)

**2. [Rule 1 - Bug] Literal "HX-Redirect" string left in a code comment**
- **Found during:** Post-Task-1 acceptance-criteria verification
- **Issue:** Task 1's acceptance criteria requires `grep -c "HX-Redirect" app/routes/warehouses.py` to return 0 (Pitfall 1: this module must never use HX-Redirect). A comment explaining the delete route's response shape referenced "HX-Redirect" by name, tripping the literal grep check even though the code never constructs that header.
- **Fix:** Reworded the comment to describe the same behavior without the literal string.
- **Files modified:** app/routes/warehouses.py
- **Verification:** `grep -c "HX-Redirect" app/routes/warehouses.py` returns 0; full test suite still green (262 passed)
- **Committed in:** c09b0f5

---

**Total deviations:** 2 auto-fixed (1 blocking-fix task reordering, 1 bug/acceptance-criteria fix)
**Impact on plan:** Both fixes were necessary to satisfy the plan's own stated acceptance criteria; no scope creep, no behavior changes beyond what the plan specified.

## Issues Encountered
- `uv run ruff check` on `.html` files (as the plan's `<verification>` section literally lists `app/templates/base.html`) produces hundreds of Jinja2-syntax-as-Python parse errors. Verified this is a pre-existing, unrelated artifact by running the same command against the already-shipped `app/templates/pages/dictionary.html` — identical failure. Ruff has no Jinja2/HTML file type in this project's config (`[tool.ruff]` has no `include`/file-extension override), so `.html` paths were excluded from the ruff check actually run; only `app/routes/warehouses.py` and `app/main.py` (real Python files) were linted, both clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WH-01 and ROADMAP Phase 8 success criteria 1-3 are complete end-to-end: operator can create/edit/soft-delete/restore warehouses from `/warehouses`, deleted warehouses stay visible with restore, deleting the last active warehouse is warn-but-allow, and the nav exposes the page from every screen.
- Full test suite green (262 passed) — ready for Phase 9 (Batch Tracking), whose `Batch.warehouse_id` FK and legacy-batch migration will point at the same `DEFAULT_WAREHOUSE_ID` frozen in `alembic/versions/0007_warehouses.py`.
- Manual UAT (Task 2's human-check: start `uvicorn`, click through add/delete/restore/last-active-warning flows in a browser) was NOT run by this automated executor — recommend running it before considering Phase 8 fully closed, per the plan's own `<verify><human-check>` step.

---
*Phase: 08-warehouses*
*Completed: 2026-07-11*

## Self-Check: PASSED
