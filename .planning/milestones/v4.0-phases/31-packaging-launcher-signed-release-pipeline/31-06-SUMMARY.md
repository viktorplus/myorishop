---
phase: 31-packaging-launcher-signed-release-pipeline
plan: 06
subsystem: infra
tags: [launcher, packaging, alembic, migration, first-run, windows, onedir]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    provides: "launcher.adapters.migrate / AppProcess (Plan 03), build_release.assemble_onedir (Plan 04), MYORISHOP_DATA_DIR data seam (Plan 02)"
provides:
  - "launcher.__main__.boot(paths, app_process, *, migrate) — migrate-then-start, wired into main() ahead of the watch loop"
  - "Abort-on-failed-migration boot contract: stderr message + SystemExit(1), the app never serves an unmigrated schema"
  - "First-run integration test that boots the REAL assembled dist against an empty data dir and asserts GET / is not 500"
affects: [31-07, 31-08, 32-secure-self-update, packaging, uat]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Boot sequence mirrors run.bat: migrate, then serve; on migration failure do not serve"
    - "Skip-gated real-artifact integration test (dist/app/python.exe present) on a FREE ephemeral port, never 8000"

key-files:
  created: []
  modified:
    - launcher/__main__.py
    - tests/test_launcher.py
    - tests/test_packaging.py
    - app/__init__.py

key-decisions:
  - "Reuse the already-shipped adapters.migrate instead of writing a second migration mechanism — boot() is a 2-line composition"
  - "boot() carries NO exception handling of its own so a CalledProcessError propagates and start() is unreachable; main() owns the operator-facing message and exit code"
  - "No mkdir in boot(): alembic/env.py already creates the sqlite parent dir, so the migration itself materialises data\\"
  - "The first-run test uses a LOCAL poll helper, not adapters.health_ok, because health_ok treats ANY status (including the 500 under test) as alive"
  - "The first-run test binds an ephemeral port via getsockname() and patches adapters._PORT — port 8000 belongs to the operator's own instance"

patterns-established:
  - "Real-artifact gate: tests that need the ~27 MB assembled onedir are skipif-gated on dist/app/python.exe, mirroring the minisign / vendored-pubkey skip-gates"

requirements-completed: [PKG-01, PKG-04]

# Metrics
duration: 34min
completed: 2026-09-03
---

# Phase 31 Plan 06: First-Run Boot Migration Summary

**The packaged launcher now runs `alembic upgrade head` before starting the app on every boot — closing the GAP-1 blocker where a fresh install created a schema-less DB and served HTTP 500 (`no such table: users`) on every page.**

## Performance

- **Duration:** ~34 min
- **Started:** 2026-09-03T00:00:00Z (approx.)
- **Completed:** 2026-09-03
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- `launcher.__main__.boot(paths, app_process, *, migrate=adapters.migrate)` composes the ALREADY SHIPPED `adapters.migrate` with `AppProcess.start()` in that strict order, and is wired into `main()` ahead of `_open_browser_soon()` and the watch loop. No second migration mechanism was introduced.
- A failing migration now aborts the boot: `main()` prints `Migration failed - server not started: {exc}` to stderr and raises `SystemExit(1)` — byte-for-byte the contract `run.bat:12-17` already gave the dev path (T-31-07). `start()` is never reached, so the app can never serve traffic on an unmigrated or half-migrated schema (T-31-06).
- `tests/test_packaging.py::test_assembled_dist_boots_against_empty_data_dir` automates the 31-UAT reproduction that no unit test could catch: it boots the REAL bundled runtime (`dist/app/python.exe`) through `boot()` against an EMPTY data dir and asserts `GET /` is not 500. It ran (not skipped) on this box and passed.

## Task Commits

1. **Task 1 (RED): failing tests for launcher boot migration** — `5499df9` (test)
2. **Task 1 (GREEN): migrate before starting the app on every launcher boot** — `afaed58` (feat)
3. **Task 2: boot the real assembled dist against an empty data dir + version bump** — `fd15b43` (test)

_TDD: Task 1 followed RED → GREEN (no refactor step was needed — the implementation is a 2-line composition). Task 2's RED was proven empirically rather than by commit ordering, see below._

## Files Created/Modified

- `launcher/__main__.py` — added `boot()` (placed just above `main()`) and rewrote `main()` to boot through it inside a `try/except Exception` guard; added `import sys`. `build_paths`, `run_once` and the `KeyboardInterrupt`/`finally: app_process.stop()` structure are untouched. The module remains stdlib-only — no `app.*` import (WinError 32 / RESEARCH Pitfall 3).
- `tests/test_launcher.py` — 3 new regressions + a shared `_RecordingProc` fake: boot ordering, abort-on-failed-migration, and the `main()` wiring guard (the patched `boot` raises `SystemExit(0)`, a BaseException that the `except Exception` guard cannot swallow, so `main()` stops before any browser is opened).
- `tests/test_packaging.py` — the skip-gated first-run integration test.
- `app/__init__.py` — `__version__` 1.56 → 1.57.

## Verification Evidence

**Task 1 RED (before `boot` existed):**
```
FAILED tests/test_launcher.py::test_boot_migrates_before_starting_the_app - A...
FAILED tests/test_launcher.py::test_boot_aborts_when_migration_fails - Attrib...
FAILED tests/test_launcher.py::test_main_boots_through_migration_before_the_watch_loop
E       AttributeError: <module 'launcher.__main__' ...> has no attribute 'boot'
3 failed, 9 deselected in 0.49s
```

**Task 1 GREEN:** `uv run pytest tests/test_launcher.py` → `12 passed in 8.09s`

**Task 2 RED (empirical, not commit-ordered):** the plan notes `boot` and this test land in the same plan, so the RED was proven directly instead. A scratch script started the SAME assembled dist WITHOUT the migration (the pre-fix `main()` behaviour) on ephemeral port 59300 against an empty data dir:
```
started child pid=13692 on port 59300, data=...\redproof-rnjqwpk4\data
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: users
[SQL: SELECT count(*) AS count_1 FROM users]
GET / status (no migration): 500
db exists: True
child stopped
```
This reproduces the 31-UAT blocker exactly and proves the new assertion is not vacuous — the DB file is created, the schema is not. The child process was stopped by the script's `finally`.

**Task 2 GREEN:** `uv run pytest tests/test_packaging.py` → `7 passed in 9.17s` (0 skipped — the gate found `dist/app/python.exe`, so the first-run test genuinely RAN against the real 27 MB onedir).

**Lint:** `uv run ruff check launcher tests/test_packaging.py app/__init__.py` → `All checks passed!`

**Full suite:** `uv run pytest -q` → `3 failed, 1457 passed, 13 skipped in 428.96s`. The 3 failures are all in `tests/test_sync_ui.py` and are the documented PRE-EXISTING `sync_client._run_lock` isolation failures (the lifespan auto-sync thread holds the lock). Confirmed pre-existing and unrelated: they also fail when `tests/test_sync_ui.py` is run in isolation (`3 failed, 8 passed`), and the exact subset varies with thread timing. Nothing in this plan touches the sync path.

## Decisions Made

- **Reuse, do not re-implement.** `boot()` is a composition of `adapters.migrate` and `AppProcess.start` — the CLAUDE.md additive-change rule ("rg for an existing mechanism before writing a new one") and the plan's explicit success criterion.
- **Error handling lives in `main()`, not `boot()`.** `boot()` stays exception-free so it is trivially testable and so `apply_update`-style callers can impose their own policy; `main()` owns the operator-facing stderr message and exit code.
- **`except Exception`, not `except CalledProcessError`.** A missing `app\python.exe` raises `FileNotFoundError`, not `CalledProcessError` — both must abort the boot rather than start an unmigrated app.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Pre-existing ruff findings in `tests/test_launcher.py` (out of scope, NOT fixed).** `uv run ruff check tests/test_launcher.py` reports 3 errors on lines authored by Plan 31-01: `B017` blind `pytest.raises(Exception)` at :196, `E501` long line at :251, `UP031` percent-format at :432. All predate this plan; the lines this plan added are clean. Logged to `deferred-items.md` per the executor scope boundary rather than fixed here.

## Known Stubs

None — no stubbed values, placeholders or TODO markers were introduced.

## Threat Flags

None — this plan introduces no new network endpoint, auth path, file-access pattern or schema change. It removes a data-integrity hazard (T-31-06) and adds a fail-closed availability behaviour (T-31-07).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- GAP-1 (blocker) from `31-VERIFICATION.md` / `31-UAT.md` test 1 is CLOSED at the code level and is now covered by an automated test against the real distribution.
- The remaining two 31-UAT blockers are NOT addressed here and are owned by the sibling gap-closure plans: the missing `launcher\launcher.exe` Start-Menu target (Plan 31-08) and the stuck-`pending.json` / renames-outside-the-try bricking path (Plan 31-07).
- Re-running the Phase 31 UAT item 1 end-to-end still needs a real bare-Windows install (SmartScreen, per-user uninstaller) — unchanged from the original verification report.

## Self-Check: PASSED

All 4 modified files and the SUMMARY exist on disk; all 3 task commits (`5499df9`, `afaed58`, `fd15b43`) are present in `git log`; `def boot(` is present in `launcher/__main__.py` and `def test_assembled_dist_boots_against_empty_data_dir` in `tests/test_packaging.py`.

---
*Phase: 31-packaging-launcher-signed-release-pipeline*
*Completed: 2026-09-03*
