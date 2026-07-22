---
phase: 32-in-app-secure-self-update
plan: 01
subsystem: testing
tags: [pytest, tdd, red-scaffold, self-update, minisign, ed25519, launcher, htmx]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    provides: "build_release.write_manifest/verify_manifest (manifest schema), launcher.swap.apply_update/parse_pending, launcher.adapters.health_ok/backup_restore, launcher.__main__.run_once"
provides:
  - "tests/test_update.py — executable RED contract for UPD-01..07 (check/verify/anti-downgrade/confirm/manual/server-noop)"
  - "tests/test_launcher.py extension — UPD-04 app-marker->launcher integration + /health version-match contract"
  - "Fixed function/dataclass signatures Waves 02-05 must satisfy (UpdateStatus, check_for_update, apply, stage_pending, is_strictly_newer, get_cached_status; verify_minisign, sha256_matches; health_ok(expected_version=...))"
affects: [32-02, 32-03, 32-04, 32-05, secure-phase-32, verify-work-32]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nyquist Wave-0 RED scaffold: import not-yet-built service INSIDE each test body so collection stays green while execution is RED"
    - "Real-crypto round-trip skip-gated on the minisign binary (throwaway keypair, never app/minisign.pub)"
    - "Environment-restricted socket bind (127.0.0.1:8000) skip-gated so a contract-fixed port never fails spuriously on a locked-down box"

key-files:
  created:
    - tests/test_update.py
  modified:
    - tests/test_launcher.py

key-decisions:
  - "UpdateStatus state vocabulary pinned as the contract: available / offline / noop / up_to_date"
  - "test_apply_rolls_back ties the UPD-04 launcher rollback anchor to the app-side update.stage_pending marker author (RED via in-body import until Wave 03)"
  - "health_ok(expected_version=...) targets the contract-fixed port 8000; skip-gate on bind failure rather than fail spuriously"

patterns-established:
  - "Pattern 1: RED-by-design in-body service import keeps Wave-0 collection green (mirrors tests/test_release_verify.py)"
  - "Pattern 2: synthetic release fixture reproduces build_release.write_manifest schema byte-for-byte so later waves verify the real contract"

requirements-completed: [UPD-01, UPD-02, UPD-03, UPD-04, UPD-05, UPD-06, UPD-07]

# Metrics
duration: 13min
completed: 2026-07-22
---

# Phase 32 Plan 01: Wave-0 RED Self-Update Test Scaffold Summary

**Executable RED test contract for the in-app secure self-update — 7 named UPD tests in tests/test_update.py plus the UPD-04 app-marker->launcher integration and /health version-match contract in tests/test_launcher.py — collection green, execution RED, ready for Waves 02-05 to flip GREEN.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-07-22T19:16Z (post plan-finalize)
- **Completed:** 2026-07-22T19:30Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 extended)

## Accomplishments
- `tests/test_update.py` (new): the 7 named UPD tests (`test_check_detects_newer`, `test_server_noop`, `test_verify_gate`, `test_minisign_pure_python_verify`, `test_anti_downgrade`, `test_confirm_and_defer`, `test_manual_check`) + three fixtures (fake GitHub `/releases/latest` JSON, `synthetic_release` real zip+manifest, throwaway minisign keypair). Collection green (7 collected), execution RED (6 ImportError from the absent `app.services.update`, 1 skipped without the minisign binary).
- `tests/test_launcher.py` (extended, existing tests untouched): `test_apply_rolls_back` (UPD-04 matched-pair rollback anchor tied to `update.stage_pending`), `test_run_once_applies_app_written_marker` (app writes `data/pending.json` -> launcher `run_once` consumes it, one swap, marker deleted), `test_health_ok_requires_version_match` (`health_ok(expected_version=...)` version match, `None` keeps legacy any-status-alive).
- Every UPD-01..07 requirement now has at least one named, executable RED test targeting it, mapped to 32-VALIDATION.md's Per-Task Verification Map.
- Full suite: 1185 passed / 16 skipped; the 12 failures are exactly the new Wave-0 RED update/launcher tests (8) plus the 4 known pre-existing OUT-OF-SCOPE `tests/test_sync_ui.py` failures — no pre-existing test regressed.

## Task Commits

Each task was committed atomically:

1. **Task 1: RED scaffold tests/test_update.py for UPD-01/02/03/05/06/07** - `69e75d0` (test)
2. **Task 2: Extend tests/test_launcher.py — app-marker->launcher integration, UPD-04 rollback, /health version-match** - `1024914` (test)

**Plan metadata:** (this SUMMARY + STATE + ROADMAP commit)

## Files Created/Modified
- `tests/test_update.py` - RED Nyquist scaffold: 7 UPD tests + fake-GitHub-JSON / synthetic-release / throwaway-keypair fixtures; `app.services.update` and `app.services.minisign_verify` imported in-body.
- `tests/test_launcher.py` - Added `import os` + three RED tests (UPD-04 rollback anchor, app-marker->launcher integration, `/health` version-match); existing 6 launcher tests unchanged; no top-level `app` import.

## Decisions Made
- **UpdateStatus state vocabulary** pinned as the RED contract: `available` (newer signed release), `offline` (fetch returned None, silent no-op), `noop` (PostgreSQL server, UPD-06), `up_to_date` (not strictly newer). Waves 02/05 must satisfy these exact strings.
- **test_apply_rolls_back is a genuine UPD-04 anchor, not a duplicate** of `test_apply_update_rolls_back_on_migrate_failure`: it in-body imports `app.services.update` and asserts `update.stage_pending` exists before asserting the shipped launcher rollback invariants — so it is RED now (module absent) and flips fully GREEN in Wave 03, tying the app marker-author to the launcher consumer.
- **health_ok version-match uses the contract-fixed port 8000** (`launcher.adapters._PORT`); it cannot use an ephemeral port because the shipped adapter hardcodes 8000. Bind is skip-gated on `OSError`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Skip-gate test_health_ok_requires_version_match on a restricted socket bind**
- **Found during:** Task 2 (launcher extension)
- **Issue:** The stub HTTP server binds `127.0.0.1:8000` per the launcher's fixed-port contract, but this Windows box raises `PermissionError` (WinError 10013) binding 8000 — producing a spurious environment failure that is NOT the intended RED reason (missing `expected_version` param) and would also fail after implementation on this box.
- **Fix:** Wrapped the `HTTPServer(("127.0.0.1", 8000), ...)` construction in `try/except OSError -> pytest.skip`, mirroring the project's minisign binary skip-gate. On CI/operator boxes where 8000 binds, the test runs RED now (unexpected `expected_version` kwarg) and GREEN after Wave 04.
- **Files modified:** tests/test_launcher.py
- **Verification:** `uv run pytest tests/test_launcher.py -q` -> 2 failed (RED), 6 passed, 1 skipped (the health test) with no PermissionError leaking to the suite.
- **Committed in:** `1024914` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test hygiene)
**Impact on plan:** Keeps the local full-suite RED set clean (only genuine Wave-0 RED + the known sync_ui baseline); no scope creep, contract unchanged (port 8000 still asserted).

## Issues Encountered
- The full suite takes ~5 min; ran it in the background to confirm the RED set. Result matched the plan's verification expectation exactly (8 new RED + 4 known sync_ui OUT-OF-SCOPE, 1185 passed).

## User Setup Required
None - no external service configuration required in this plan. (The `uv add cryptography` supply-chain checkpoint and the `app/minisign.pub` vendor step are gated in Plan 32-02, not here.)

## Next Phase Readiness
- The executable contract for Waves 02-05 is fixed: `app.services.update` (`check_for_update`, `apply`, `stage_pending`, `is_strictly_newer`, `get_cached_status`, `UpdateStatus`, `fetch_latest_release`, `verified_manifest_version`/`verify_release` seams), `app.services.minisign_verify` (`verify_minisign`, `sha256_matches`), and `launcher.adapters.health_ok(expected_version=...)`.
- Wave 02 (32-02) still PAUSES for its two blocking-human checkpoints: `uv add cryptography` supply-chain approval and vendoring the ABSENT `app/minisign.pub` (`minisign -G` offline + confirm the repo is public). Until `app/minisign.pub` exists, `test_minisign_pure_python_verify` remains skip-gated.
- No blockers introduced by this plan.

---
*Phase: 32-in-app-secure-self-update*
*Completed: 2026-07-22*
