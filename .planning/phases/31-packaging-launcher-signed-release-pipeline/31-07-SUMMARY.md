---
phase: 31-packaging-launcher-signed-release-pipeline
plan: 07
subsystem: infra
tags: [launcher, packaging, swap, rollback, windows, gap-closure, pkg-04]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    provides: "launcher.swap.apply_update / parse_pending (Plan 03), launcher.__main__.run_once + boot (Plans 03/06)"
provides:
  - "apply_update with a staged pre-flight guard: a missing staged\\ is refused BEFORE stop_app and before any rename"
  - "Proportional matched-pair rollback: undoes only the steps that ran; backup_restore only when the migration was attempted"
  - "Repeatable swap+rollback: every directory rename clears its destination first (Windows os.replace cannot replace an existing dir)"
  - "run_once marker quarantine to data\\pending.failed.json — the marker is ALWAYS consumed"
  - "main() watch loop survives a failed tick instead of exiting and stopping the app"
affects: [31-08, 32-secure-self-update, uat]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Track what actually completed with local flags, then let the rollback undo exactly those steps (proportional compensation)"
    - "Every rollback step is best-effort (_best_effort) so no secondary failure masks the original exception"
    - "Clear the destination directory before every os.replace — WinError 5 fires even for an EMPTY destination"

key-files:
  created: []
  modified:
    - launcher/swap.py
    - launcher/__main__.py
    - tests/test_launcher.py
    - app/__init__.py

key-decisions:
  - "A stale app.prev\\ is cleared before the forward swap: it is a leftover, not the rollback anchor (the anchor is created BY that rename), and without clearing it no update could ever apply again"
  - "backup_restore fires only when the migration was attempted — restoring an older DB after a pre-swap failure would itself be data loss (T-31-06b)"
  - "The app.prev -> app restoration sits OUTSIDE the parking step's try, so a failure to park the bad code cannot block the one action that keeps the install runnable"
  - "In the double-fault case (park failed AND rmtree failed) the restoration is SKIPPED and a Russian stderr line points the operator at app.prev\\ — leaving a bad-but-present app\\ beats deleting the only runnable copy"
  - "The marker is quarantined (os.replace to pending.failed.json), not deleted, so a failed update stays available for forensics while being unreplayable"
  - "run_once checks BOTH pending.staged_dir and paths.staged — they are different paths and coincide only when the marker literally names 'staged'"

patterns-established:
  - "Gap-closure regressions are written to fail against the FIXED-BUT-INCOMPLETE implementation, not only against the shipped one (the intermediate RED was run and recorded)"

requirements-completed: [PKG-04]

# Metrics
duration: 38min
completed: 2026-09-03
---

# Phase 31 Plan 07: Failed-Update Brick Fix Summary

**A failed update now leaves the operator running on the previous version indefinitely: both swap renames are inside the rollback-guarded region, every directory rename clears its destination first (Windows `os.replace` refuses an existing directory — even an empty one), and the pending marker is quarantined instead of being replayed every 2 seconds.**

## Performance

- **Duration:** ~38 min
- **Completed:** 2026-09-03
- **Tasks:** 2/2
- **Files modified:** 4

## Accomplishments

- **Pre-flight guard (GAP-3 defect a).** `apply_update` raises `FileNotFoundError` when `staged\` is missing — before `stop_app()` and before the first rename. The 31-UAT end state (`app=False, app.prev=True, marker=True`) is now unreachable: nothing is touched when the cycle is refused.
- **Both renames inside the guarded region.** `os.replace(app → app.prev)` and `os.replace(staged → app)` moved into the `try:`, tracked by `prev_renamed` / `staged_swapped` / `migrate_attempted`.
- **Proportional rollback (defect b, T-31-06b).** The rollback undoes only what ran. `backup_restore` fires **only** when the migration was attempted — a failure at the first rename no longer reverts the operator's DB to an older backup and discards every write made since.
- **Repeatable swap AND rollback (defect c, T-31-06c).** Measured on this box: `os.replace(<dir>, <existing dir>)` raises `PermissionError [WinError 5]` even for an empty destination. So `app.prev\` is cleared before the forward swap and `app.failed\` before parking the bad code. The `app.prev → app` restoration sits outside the parking step's own `try`, so the SECOND failed update rolls back exactly like the first. Every rollback step is best-effort (`_best_effort`), so the ORIGINAL exception always propagates — the failing-migrate test now asserts `RuntimeError`, never a `PermissionError` from the rollback's own rename.
- **Marker always consumed (T-31-04).** `run_once` quarantines `data\pending.json` → `data\pending.failed.json` on every failure path, and refuses a marker whose staged dir is gone *before* entering `apply_update`. `main()` catches a failed tick, prints «Обновление не применено, приложение работает на прежней версии: …» to stderr and keeps watching — the rollback already restarted the app, so exiting would stop the operator's install.
- **The UAT-mandated two-tick regression exists and passes:** `test_two_ticks_with_one_failing_update_keep_app_dir` drives real `os.replace` renames on tmp dirs, fails tick 1, and proves tick 2 is a no-op with `app\` intact.

## Task Commits

1. **Task 1 (RED): failing tests for the GAP-3 apply_update guard** — `e0fc7a0` (test)
2. **Task 1 (GREEN): guard both swap renames and make the rollback proportional** — `b11ab05` (fix)
3. **Task 2 (RED): failing tests for pending-marker quarantine** — `3521401` (test)
4. **Task 2 (GREEN): always consume the pending marker and survive a failed tick** — `457a700` (fix, incl. version bump)

## Files Created/Modified

- `launcher/swap.py` — `apply_update` reworked: pre-flight guard, both renames inside the `try:`, destination-clearing before every rename, proportional best-effort rollback, new module-private `_best_effort`, `import sys` for the double-fault stderr line. Docstrings updated (module T-31-06 line + the `apply_update` contract). **`parse_pending` / `_confine` are byte-identical** — `git diff` shows zero lines touching them, so the T-31-05 confinement is exactly as shipped.
- `launcher/__main__.py` — `_FAILED_MARKER_NAME` + `_quarantine_marker()`; `run_once` refuses an unsatisfiable marker and wraps `apply_update` in `try/except` → quarantine + re-raise; `main()`'s loop guards `run_once`. Added `import os`. Stdlib-only, still no `app.*` import.
- `tests/test_launcher.py` — 7 new tests (+ `_swap_fixture`, `_write_marker`, `_NoopProc`, `_tick` helpers) and `import shutil` at the top. 12 → 19 tests.
- `app/__init__.py` — `__version__` 1.57 → 1.58.

## Verification Evidence

**Task 1 RED (against the shipped code):**
```
FAILED tests/test_launcher.py::test_apply_update_refuses_when_staged_dir_is_missing
FAILED tests/test_launcher.py::test_rollback_leaves_db_untouched_when_no_swap_happened
FAILED tests/test_launcher.py::test_rollback_succeeds_when_app_failed_already_exists
FAILED tests/test_launcher.py::test_apply_update_rotates_a_stale_app_prev - P...
4 failed, 4 passed, 8 deselected in 0.98s
```
`test_apply_update_rotates_a_stale_app_prev` failed with the measured
`PermissionError: [WinError 5] Отказано в доступе: '…\app' -> '…\app.prev'` — the empty-vs-non-empty
directory claim in the plan is confirmed empirically on this machine.

**Intermediate RED (the plan-checker's third defect, proven explicitly).** With ONLY steps 1–2 applied
(pre-flight guard + both forward renames inside the `try:`, rollback untouched):
```
>           os.replace(paths.app, paths.app_failed)
E           PermissionError: [WinError 5] … '\app' -> '\app.failed'
launcher\swap.py:106: PermissionError
FAILED tests/test_launcher.py::test_rollback_leaves_db_untouched_when_no_swap_happened
FAILED tests/test_launcher.py::test_rollback_succeeds_when_app_failed_already_exists
2 failed, 14 deselected
```
This is the plan's explicit requirement: the two rollback tests are RED against the
plan-as-first-written, not merely against today's code, so the step-3 regression is genuinely proven.

**Task 1 GREEN:** `uv run pytest tests/test_launcher.py -k "apply_update or apply_rolls_back or rollback"` → `8 passed, 8 deselected` (the four new tests plus the three shipped rollback/happy-path tests and the Phase-32 `test_apply_rolls_back` anchor, all unchanged).

**Task 2 RED:**
```
FAILED tests/test_launcher.py::test_two_ticks_with_one_failing_update_keep_app_dir
FAILED tests/test_launcher.py::test_run_once_refuses_marker_whose_staged_dir_is_gone
FAILED tests/test_launcher.py::test_run_once_quarantines_marker_after_failed_apply
3 failed, 16 deselected in 0.50s
```

**Task 2 GREEN:** `uv run pytest tests/test_launcher.py` → `19 passed in 6.72s`.

**Lint:** `uv run ruff check launcher` → `All checks passed!`.
`uv run ruff check tests/test_launcher.py` → `Found 3 errors` — byte-for-byte the 3 PRE-EXISTING 31-01 scaffold findings (`B017` blind `pytest.raises(Exception)`, `E501`, `UP031`), already logged in `deferred-items.md`. No new finding on any line this plan added.

**Full suite:** `uv run pytest -q` → `4 failed, 1463 passed, 13 skipped, 3 warnings in 416.20s`. All 4 failures are `tests/test_sync_ui.py` (`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`, `test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`) — the documented PRE-EXISTING `sync_client._run_lock` isolation failures (the lifespan auto-sync thread holds the lock; the exact subset varies with thread timing). Nothing in this plan touches the sync path. Passing count rose 1456 → 1463, i.e. exactly the 7 tests added here.

## Decisions Made

- **Clear a stale `app.prev\` before the forward swap.** It is a leftover from a cycle whose cleanup `rmtree` partially failed, not the current rollback anchor (the anchor is created by the very rename that follows). Without it, one bad cleanup would make every future update fail with WinError 5 — no brick, but no updates either. The accepted tradeoff is stated in the code comment: if that `app.prev\` was the recovery copy an incomplete rollback deliberately retained, the operator's recovery window is the failed cycle itself, not the next one.
- **Restore the DB only when the migration was attempted.** A failure before the swap cannot have changed the schema; rolling the DB back there would silently destroy operator work written since the backup. This is a data-loss fix in its own right (T-31-06b), not just a tidiness change.
- **Skip the restoration in the double-fault case rather than force it.** If parking the bad code fails AND the fallback `rmtree` of `app\` also fails, `app\` still holds the new code; deleting it would remove the operator's only present copy. The plan's judgement is followed: keep it, revert the DB, print «Откат неполный: app\ не восстановлен, предыдущая версия сохранена в app.prev\» to stderr, and say plainly in the docstring that this is the ONE branch where "code and DB revert together" does not hold.
- **Quarantine, not delete.** `pending.failed.json` keeps the failed marker for forensics; `os.replace` makes the overwrite atomic and idempotent across repeated failures.
- **`_quarantine_marker` swallows its own failure.** A quarantine error must never mask the real update exception; the worst case is a marker the next tick refuses again (its staged dir is gone by then), which is a no-op, not a brick.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The three pre-existing `tests/test_launcher.py` ruff findings from the 31-01 scaffold were left untouched per the executor scope boundary (already in `deferred-items.md`). Their reported line numbers shifted (`:196 → :196`, `:251 → :402`, `:432 → :690`) because tests were inserted above them; the findings themselves are unchanged.

## Known Stubs

None — no stubbed values, placeholders or TODO markers were introduced.

## Threat Flags

None — no new network endpoint, auth path, file-access pattern or schema change. This plan removes data-integrity hazards (T-31-06/06b/06c) and closes a replay hazard (T-31-04). `parse_pending`'s ASVS V12 confinement (T-31-05) is byte-identical.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **GAP-3 (blocker) is closed at the code level** and is covered by the two-tick regression the UAT asked for.
- Still deferred to a real UAT re-run on a packaged install (unchanged from the plan's `<verification>`): inject a failing migration on the assembled distribution, watch the matched-pair rollback, leave the launcher running for at least two more ticks, then repeat the SAME failing update a second time with `app.failed\` from the first run still present.
- Phase 32's `app/services/update.py` drives exactly this state machine; the `apply_update` / `run_once` signatures and the `test_apply_rolls_back` UPD-04 anchor are unchanged, so nothing downstream needs adjusting.
- The remaining Phase-31 gap (missing `launcher\launcher.exe` Start-Menu target) is owned by Plan 31-08.

## Self-Check: PASSED

All 4 modified files exist on disk; all 4 task commits (`e0fc7a0`, `b11ab05`, `3521401`, `457a700`) are present in `git log`; `def test_two_ticks_with_one_failing_update_keep_app_dir` is present in `tests/test_launcher.py`, `_quarantine_marker` / `pending.failed.json` in `launcher/__main__.py`, and the pre-flight `FileNotFoundError` + `rmtree(paths.app_failed` in `launcher/swap.py`.

---
*Phase: 31-packaging-launcher-signed-release-pipeline*
*Completed: 2026-09-03*
