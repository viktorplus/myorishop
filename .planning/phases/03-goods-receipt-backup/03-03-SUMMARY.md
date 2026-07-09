---
phase: 03-goods-receipt-backup
plan: 03
subsystem: infra
tags: [sqlite, vacuum-into, fastapi, lifespan, backup, restore, htmx]

# Dependency graph
requires:
  - phase: 01-foundation-ledger-core
    provides: build_engine (WAL + foreign_keys pragmas), APPEND_ONLY_TRIGGERS, record_operation, compute_stock
  - phase: 03-goods-receipt-backup plan 01
    provides: current app/main.py router set and base.html nav to extend
provides:
  - create_backup (AUTOCOMMIT VACUUM INTO, bound ? parameter, PD-11 collision suffix, partial-file cleanup)
  - prune_backups (mtime ordering, keep newest N) + list_backups (RU size labels, newest first)
  - startup_backup gate (flag / DB exists / DB has data) called from FastAPI lifespan before serving
  - GET /backup page + POST /backup (zero client parameters, V12) with #backup-list htmx swap
  - restore.bat offline restore (copy + mandatory -wal/-shm sidecar deletion)
  - conftest client-fixture gate: backup_on_startup=False before TestClient enters (test-suite safety)
affects: [04-sales, 06-reports, BCK-02 CSV export]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "VACUUM INTO only via exec_driver_sql with bound ? on an isolation_level=AUTOCOMMIT connection"
    - "FastAPI lifespan asynccontextmanager as the startup hook (first lifespan usage; on_event never used)"
    - "Module-qualified service import (backup_service.startup_backup) as the single monkeypatch seam"
    - "POST returns partial at 200 for both success and failure — htmx swaps 2xx, RU error block rides in the partial"

key-files:
  created:
    - app/services/backup.py
    - app/routes/backup.py
    - app/templates/pages/backup.html
    - app/templates/partials/backup_list.html
    - restore.bat
    - tests/test_backup.py
  modified:
    - app/main.py
    - app/config.py
    - tests/conftest.py
    - app/templates/base.html
    - .gitignore

key-decisions:
  - "prune_backups treats keep<=0 as delete-all guard (files[:-keep] slice bug avoided with explicit keep>0 branch)"
  - "list_backups created_iso rendered as UTC isoformat so the existing local_dt Jinja filter handles display timezone"
  - "GET /backup takes no session dependency — list_backups is pure filesystem; only POST needs session.get_bind() (PD-12)"

patterns-established:
  - "Backup filenames myorishop-YYYYMMDD-HHMMSS[-N].db — lexicographic = chronological; mtime is the pruning/listing truth"
  - "restore stays an offline script, never a web endpoint (D-11 / T-3-09)"

requirements-completed: [BCK-01]

# Metrics
duration: 9min
completed: 2026-07-09
---

# Phase 3 Plan 03: Automated Backup & Verified Restore Summary

**VACUUM INTO backups on every app start (gated, pruned to 30) plus a one-click /backup page and restore.bat with -wal/-shm cleanup, proven by an automated backup→restore roundtrip test that also confirms append-only triggers survive**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-09T06:13:02Z
- **Completed:** 2026-07-09T06:21:58Z
- **Tasks:** 3
- **Files modified:** 11

## Accomplishments
- `app/services/backup.py`: `create_backup` executes `VACUUM INTO ?` as a bound parameter on an AUTOCOMMIT connection (T-3-08; Windows-path safe), appends a `-2`/`-3` suffix on same-second collisions (PD-11), and unlinks the partial target on any failure (Pitfall 4); `prune_backups`/`list_backups` order by mtime; `startup_backup` holds all three D-09 skip conditions (flag off, DB file missing, DB empty via `_db_has_data` that treats SQLAlchemy errors as "no data")
- `app/main.py` lifespan calls `backup_service.startup_backup()` before serving — first lifespan usage in the project, module-qualified so tests monkeypatch one seam (PD-13)
- `/backup` page: server-enumerated list (Файл / Создана / Размер with RU size labels «1,2 МБ»), one-click «Создать резервную копию» (htmx `#backup-list` outerHTML swap, button disabled during VACUUM), RU restore instructions; POST takes ZERO client parameters (V12, grep-gated) and renders the RU error block at 200 with the list unchanged on failure
- `restore.bat`: usage help with backup listing, copy over `data/myorishop.db`, mandatory deletion of `-wal`/`-shm` sidecars (sqlite.org corruption guard, T-3-10)
- D-11 closed by `test_backup_and_restore_roundtrip_preserves_data_and_triggers`: backup → copy (restore.bat's copy step) → reopen with production `build_engine` → quantity and `compute_stock` both read 5 AND an UPDATE on `operations` still raises "append-only" (Assumption A2 closed)
- Test-suite safety (Pitfall 1): the `client` fixture monkeypatches `settings.backup_on_startup = False` before `TestClient(app)` enters — `uv run pytest` leaves no real `backups/` directory (verified after every task)

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests + settings + conftest startup-backup gate (RED)** - `bb5d8f3` (test)
2. **Task 2: Backup service (VACUUM INTO) + lifespan startup hook (GREEN service)** - `3db08fc` (feat)
3. **Task 3: /backup page + restore.bat + nav + gitignore (GREEN web + restore path)** - `0f66681` (feat)

## Files Created/Modified
- `app/services/backup.py` - create_backup / prune_backups / list_backups / startup_backup / _db_has_data
- `app/routes/backup.py` - GET /backup page, POST /backup (parameter-free, PD-12 engine via session.get_bind())
- `app/templates/pages/backup.html` - h1, 30-copy note, backup button, list include, restore instructions
- `app/templates/partials/backup_list.html` - #backup-list swap target: message/error, table, RU empty state
- `restore.bat` - offline restore with stale-WAL sidecar deletion
- `tests/test_backup.py` - 14-test BCK-01 contract incl. restore roundtrip + V12 client-params test
- `app/main.py` - lifespan + backup router registered
- `app/config.py` - backup_dir / backup_on_startup / backup_keep settings
- `tests/conftest.py` - client fixture disables backup_on_startup (Pitfall 1 gate)
- `app/templates/base.html` - nav «Резервные копии» last (UI-SPEC order)
- `.gitignore` - explicit `backups/` entry

## Decisions Made
- `prune_backups` guards `keep > 0` explicitly — the naive `files[:-keep]` slice would keep everything at keep=0
- `created_iso` stored as UTC isoformat string so the shared `local_dt` Jinja filter (display_tz) renders backup timestamps like every other timestamp in the app
- GET /backup omits the session dependency (pure filesystem read); only POST needs the session for `get_bind()` (PD-12)

## Deviations from Plan

None - plan executed exactly as written. (Ruff auto-fix reordered imports in the RED test file within Task 1 before commit — cosmetic, no behavior change.)

## Issues Encountered
None

## Known Stubs
None — all backup UI is wired to the live service; retention, error, and empty states all render from real data.

## Threat Flags
None — new surface (POST /backup, VACUUM INTO path, restore.bat file replacement) is exactly the plan's threat model; T-3-08/T-3-09/T-3-10/T-3-11/T-3-12 mitigations verified by tests and grep gates (bound-parameter VACUUM only, no Form/Query on backup routes, sidecar deletion in restore.bat, backups/ gitignored, partial-target cleanup).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 plans 1–3 all complete — phase ready for `/gsd-verify-work 3`
- Human verify (end-of-phase): start run.bat → new myorishop-*.db appears in backups/; run restore.bat with that file (app stopped) → app starts with the same data — one end-to-end pass on real Windows
- Phase 6 BCK-02 (CSV export) can reuse create_backup/list_backups as-is

## TDD Gate Compliance
Task 1 (tdd="true"): RED commit `bb5d8f3` (test) confirmed failing (ModuleNotFoundError on app.services.backup) before GREEN commits `3db08fc`/`0f66681` (feat). Gate sequence satisfied.

## Self-Check: PASSED

- All 6 created files exist on disk; all 5 modified files contain the required content
- All 3 task commits found in git log (bb5d8f3, 3db08fc, 0f66681)
- tests/test_backup.py is 245 lines (min_lines 90 satisfied)
- Full suite: 112 passed; ruff clean
- Grep gates: bound-parameter VACUUM, no f-string SQL, lifespan in main.py, no Form/Query in backup routes, -wal/-shm cleanup in restore.bat, ^backups/ in .gitignore, routes write-free
- No real backups/ directory after the full pytest run (conftest gate effective)

---
*Phase: 03-goods-receipt-backup*
*Completed: 2026-07-09*
