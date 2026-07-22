---
phase: 31-packaging-launcher-signed-release-pipeline
plan: 03
subsystem: launcher
tags: [packaging, launcher, self-replace, swap, rollback, path-confinement, pkg-04]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    provides: "Plan 01 tests/test_launcher.py — PKG-04 callback-injected swap/rollback + parse_pending confinement (RED)"
provides:
  - "launcher/swap.py — apply_update matched-pair rollback state machine + Paths/Pending dataclasses + parse_pending ASVS V12 confinement"
  - "launcher/adapters.py — Windows adapters: PID-owning AppProcess (start/stop), migrate, health_ok, backup_restore (WAL-sidecar delete)"
  - "launcher/__main__.py — entry: build_paths + run_once marker-drive hook + main watch loop (python -m launcher)"
affects: [phase-32 self-update]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Callback-injected pure state machine (stop_app/start_app/migrate/health_ok/backup_restore) so swap+rollback sequencing is OS-agnostic unit-testable"
    - "Launcher is stdlib-only and imports NO app.* — importing the app would lock app\\ and break the os.replace rename (RESEARCH Pitfall 3, WinError 32)"
    - "PID ownership over port-scan: AppProcess owns the child and stops by handle (terminate->wait->kill), replacing run.bat's netstat/taskkill anti-pattern"
    - "restore.bat parity in Python: backup_restore copies backup + unlinks -wal/-shm so SQLite cannot replay a stale WAL into the restored DB"

key-files:
  created:
    - launcher/__init__.py
    - launcher/swap.py
    - launcher/adapters.py
    - launcher/__main__.py
  modified:
    - app/__init__.py

key-decisions:
  - "Paths carries the 4 test-pinned fields (app, app_prev, staged, app_failed) as required and adds install_root/data as optional trailing fields, honoring both the Plan-01 test surface and the entry point's need for the sibling data/install-root paths"
  - "parse_pending enforces an EXACT key set {staged_dir, expected_version, db_backup_path} (rejects missing AND extra) and confines via three layers: reject '..' in parts, reject absolute paths, reject resolved paths not is_relative_to(install_root)"
  - "backup_restore signature is (backup_path, db_path) per the test (db_path is the full myorishop.db path), so the entry point wires it into the one-arg apply_update callback via a lambda binding the data-dir DB path"
  - "Marker's staged_dir is validated for confinement but the swap uses the fixed sibling paths.staged (Phase-31 hand-placed proof); reconciling the two is Phase-32 IPC scope"

patterns-established:
  - "Launcher package layout: swap.py (pure) + adapters.py (Windows side effects) + __main__.py (wiring/entry) — Phase 32 self-update drives run_once with real staging"

requirements-completed: [PKG-04]

# Metrics
duration: 18min
completed: 2026-07-22
---

# Phase 31 Plan 03: Stable Launcher — Swap/Rollback State Machine Summary

**A stdlib-only `launcher/` package living outside the swappable `app\` dir: a pure callback-injected `apply_update` state machine (stop → rename app→app.prev → rename staged→app → migrate → health-check → drop app.prev, with matched-pair code+DB rollback on any failure), Windows PID-owning adapters, and a `python -m launcher` entry that watches `data\pending.json` and drives one swap cycle on a valid, path-confined marker.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-07-22
- **Completed:** 2026-07-22
- **Tasks:** 3
- **Files:** 4 created + `app/__init__.py` version bumps (5 total)

## Accomplishments
- `launcher/swap.py` — `apply_update(paths, pending, *, stop_app, start_app, migrate, health_ok, backup_restore)` implementing the RESEARCH skeleton verbatim: migrate runs strictly between the two `os.replace` renames and `start_app`; on migrate-raise OR `health_ok` False it stops, moves staged code aside to `app.failed\`, restores `app.prev\` → `app\`, restores the pre-update DB via `backup_restore`, restarts, and re-raises (matched pair). Frozen `Paths`/`Pending` dataclasses. `parse_pending` strict marker gate with ASVS V12 confinement (`..` / absolute / escape rejection).
- `launcher/adapters.py` — `AppProcess` owns the child PID and stops by handle (`terminate` → `wait(timeout)` → `kill`), never by port; `migrate` runs `app\python.exe -m alembic upgrade head` (CWD=`app\`, `MYORISHOP_DATA_DIR` set); `health_ok` polls `127.0.0.1:8000` and treats any response (incl. 302/303→/login) as alive; `backup_restore(backup, db)` copies the backup then deletes `-wal`/`-shm` (restore.bat parity).
- `launcher/__main__.py` — `build_paths` derives the install-root layout from the launcher's own dir (so the launcher sits outside `app\`); `run_once` is the integration hook that reads `data\pending.json`, parses+confines it, and drives one `apply_update` cycle (refusing invalid/absent markers, T-31-04); `main` starts the app, opens the browser, and watches the marker. Runnable as `python -m launcher`.
- `tests/test_launcher.py` fully GREEN (6/6): happy-path rename ordering, migrate-fail and health-fail matched-pair rollbacks, `backup_restore` WAL-sidecar delete, and both `parse_pending` traversal + malformed-marker rejections.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pure swap state machine + pending-marker path confinement** — `2ad02e3` (feat)
2. **Task 2: Windows adapters — PID-owning start/stop, migrate, health, DB restore** — `a77ec74` (feat)
3. **Task 3: Launcher entry — start, browser, marker watch, drive apply_update** — `218ec9c` (feat)

## Files Created/Modified
- `launcher/__init__.py` — package marker (stdlib-only launcher; no app.* imports)
- `launcher/swap.py` — `apply_update` state machine + `Paths`/`Pending` + `parse_pending` confinement (PKG-04, T-31-04/05/06)
- `launcher/adapters.py` — Windows adapters (AppProcess, migrate, health_ok, backup_restore)
- `launcher/__main__.py` — entry point + `build_paths` + `run_once` hook
- `app/__init__.py` — version bumped 1.5 → 1.8 (per-task-commit convention)

## Decisions Made
- `Paths` keeps the four test-pinned fields required and adds `install_root`/`data` as optional trailing fields, so the Plan-01 `Paths(app, app_prev, staged, app_failed)` contract and the entry point's install-root needs both hold on one frozen dataclass.
- `parse_pending` rejects with a single unambiguous `ValueError` for every case (malformed JSON via `json.JSONDecodeError` subclass, non-object, wrong key set, `..`, absolute, escape) — matching the Plan-01 pinned rejection contract.
- `backup_restore(backup, db)` takes the full DB path (per the test); the one-arg `apply_update` callback is wired in `run_once` via `lambda backup: backup_restore(backup, data/myorishop.db)`.

## Deviations from Plan

None — plan executed exactly as written. (`app/__init__.py` version bumps follow the established project per-task-commit versioning convention, not a plan deviation.)

## Issues Encountered
None affecting this plan. The full suite shows 19 failures, all OUT OF SCOPE and pre-existing:
- **6 RED-by-design** (`tests/test_packaging.py` ×3, `tests/test_release_verify.py` ×3) — Plan-01 scaffold implemented by Plans 02/04/05, not Wave 1 (`ModuleNotFoundError: build_release` / `verify_manifest`).
- **13 full-suite test-isolation failures** (`tests/test_sync_client.py` ×8, `tests/test_sync_ui.py` ×4, `tests/test_warehouses.py::test_migration_0007` ×1) — the documented pre-existing lifespan auto-sync `_run_lock` isolation bug. Verified GREEN in isolation: `uv run pytest tests/test_sync_client.py tests/test_warehouses.py::test_migration_0007... → 24 passed`. Not caused by this plan (the launcher touches no app runtime).

## Known Stubs
None. The `data\pending.json` full IPC / controlled-shutdown contract is intentionally DEFERRED to Phase 32 (RESEARCH Open Question 4 RESOLVED) — Phase 31 implements only the hand-placed-marker drive path, which is complete and tested via `run_once`.

## User Setup Required
None — the launcher is stdlib-only. The packaged `launcher.exe` stub and the embeddable-runtime bundling are Plan-04 (`build_release.py`) / Plan-02 concerns; end-to-end swap-on-a-packaged-install is the deferred end-of-phase UAT.

## Next Phase Readiness
- Plan 02 (`app/config.py` `MYORISHOP_DATA_DIR` seam) and Plan 04 (`build_release.py` onedir + `.iss`) are unblocked — the launcher already reads `MYORISHOP_DATA_DIR` and reproduces the `run.bat` launch command.
- Phase 32 self-update drives `launcher.__main__.run_once` with a real (signature-verified) staged dir; the swap/rollback core and marker gate are proven here.
- No blockers.

## Self-Check: PASSED

- All four launcher files + `31-03-SUMMARY.md` exist on disk.
- All three task commits (2ad02e3, a77ec74, 218ec9c) present in git history.
- `uv run pytest tests/test_launcher.py` → 6 passed (PKG-04 gate green).

---
*Phase: 31-packaging-launcher-signed-release-pipeline*
*Completed: 2026-07-22*
