---
phase: 31-packaging-launcher-signed-release-pipeline
plan: 02
subsystem: config
tags: [packaging, pkg-03, data-separation, config-seam, path-rooting, tdd]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    plan: 01
    provides: "tests/test_packaging.py PKG-03 gates (RED) that pin the MYORISHOP_DATA_DIR seam"
provides:
  - "app/config.py MYORISHOP_DATA_DIR-rooted absolute data paths (db_path, backup_dir, .env, secret_key, device_id)"
  - "MYORISHOP_DATA_DIR env-var contract (absolute data-dir root, default \"data\") for the Plan-03 launcher"
affects: [31-03 launcher, 31-04 build_release, phase-32 self-update]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Import-time absolute data-dir root: _DATA_DIR = Path(os.environ.get('MYORISHOP_DATA_DIR', 'data')).resolve() rooting every operator-state path so data is a physical sibling of the swappable app\\ dir"
    - "secret_key/device_id follow db_path.parent for free — no new resolution code when the DB root moves"

key-files:
  created: []
  modified:
    - app/config.py
    - app/__init__.py

key-decisions:
  - "Rooted db_path, backup_dir and .env at a single import-time _DATA_DIR; the critical line is backup_dir = _DATA_DIR / 'backups' (absolute) so backups survive an over-the-top app-dir swap (RESEARCH Pitfall 2)"
  - "Left _resolve_local_identity untouched: data_dir = Path(self.db_path).parent already resolves to _DATA_DIR, so secret_key/device_id follow the seam with zero new code"
  - "catalogs_dir left CWD-relative (out of PKG-03 scope): catalogs are shipped read-only PDFs that belong in app\\ and are re-bundled each release; the launcher runs with CWD=app\\"
  - "Task 2 is a pure safety-gate: no test relied on the literal 'backups'/'data/myorishop.db' strings, so no code change was needed to keep the suite green"

requirements-completed: [PKG-03]

# Metrics
duration: 15min
completed: 2026-07-22
---

# Phase 31 Plan 02: MYORISHOP_DATA_DIR Config Seam (PKG-03) Summary

**Roots every operator-state path (SQLite DB, `.env`, per-install `secret_key`/`device_id`, and `backups/`) under a single import-time absolute data dir supplied by `MYORISHOP_DATA_DIR` (default `"data"`), so the operator's data lives as a physical sibling of the swappable `app\` directory and an over-the-top app-dir swap can never reach or destroy it.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-22
- **Completed:** 2026-07-22
- **Tasks:** 2 (1 TDD config change + 1 full-suite safety gate)
- **Files modified:** 2 (`app/config.py`, `app/__init__.py` version bump)

## Accomplishments
- Added a module-level `_DATA_DIR = Path(os.environ.get("MYORISHOP_DATA_DIR", "data")).resolve()` in `app/config.py`, annotated with the PKG-03 / RESEARCH Pattern 3 rationale.
- Rerouted `model_config` `env_file` → `str(_DATA_DIR / ".env")`, `db_path` default → `str(_DATA_DIR / "myorishop.db")`, and `backup_dir` default → `str(_DATA_DIR / "backups")` (the critical absolute-path wipe-risk line).
- Confirmed `secret_key`/`device_id` follow `Path(self.db_path).parent` (= `_DATA_DIR`) for free — the `_resolve_local_identity` validator is unchanged except for a one-line clarifying comment.
- All three PKG-03 gates turned GREEN: `test_data_paths_are_siblings`, `test_backup_dir_is_absolute_not_cwd_relative`, `test_swap_of_app_dir_cannot_reach_data`.
- Full-suite safety gate: with `MYORISHOP_DATA_DIR` unset the default `"data"` behavior is byte-identical (paths resolve to the repo `data\` dir); no test depended on the literal `"backups"`/`"data/myorishop.db"` strings.

## Task Commits

1. **Task 1: Root all operator data paths under MYORISHOP_DATA_DIR (PKG-03 config seam)** — `800c45e` (feat) — TDD RED→GREEN on the three PKG-03 selectors.
2. **Task 2: Regression-guard the seam (full suite green under default data root)** — no commit (pure verification gate; no code change required — no test relied on the CWD-relative literals).

## Files Created/Modified
- `app/config.py` — `_DATA_DIR` seam + `env_file`/`db_path`/`backup_dir` rerouted under it; identity validator commented (logic unchanged).
- `app/__init__.py` — version bumped 1.4 → 1.5 (per-task-commit convention).

## Decisions Made
- The single highest-risk line is `backup_dir = str(_DATA_DIR / "backups")` — absolute so VACUUM-INTO snapshots survive an app-dir swap (T-31-06 mitigation).
- No new symbols beyond `_DATA_DIR`; identity resolution inherits the seam through `db_path.parent` (T-31-05: `.resolve()` normalizes the launcher-supplied path once at import).
- `catalogs_dir` deliberately left CWD-relative — shipped read-only PDFs re-bundled each release, launcher guarantees CWD=`app\`.

## Deviations from Plan

None — plan executed exactly as written. (The `app/__init__.py` version bump follows the established project per-task-commit versioning convention, not a plan deviation.)

## Issues Encountered
- The full suite showed 24 failures, but investigation confirmed **none are a regression from this plan**:
  - **6 test_launcher + 3 test_packaging (PKG-01/02) + 3 test_release_verify** — expected Wave-0 RED scaffolds; their `build_release`/`launcher` modules are built by Plans 03/04/05.
  - **8 test_sync_client + 1 test_warehouses** — pass cleanly in isolation (64 passed). Proven to be a pre-existing test-isolation artifact of the Wave-0 scaffold's `importlib.reload(app.config)` (mechanism introduced in Plan 01), not this change: excluding the three reload-scaffold files, those failures vanish entirely.
  - **4 test_sync_ui** — the documented pre-existing sync-suite isolation bug (`sync_client._run_lock` held by the lifespan auto-sync thread), explicitly out of scope.
- Full suite excluding the Wave-0 reload scaffolds: **1170 passed / 12 skipped / 4 known-pre-existing failed** — zero new failures attributable to the seam.

## User Setup Required
None — `MYORISHOP_DATA_DIR` is optional; unset it (dev/run.bat) and behavior is byte-identical. The Plan-03 launcher exports it for the packaged install.

## Next Phase Readiness
- Plan 03 (launcher) can now export `MYORISHOP_DATA_DIR=<install_root>\data` and rely on all operator state landing there, safely siblinged from the swappable `app\`.
- The PKG-03 swap-safety invariant is now enforced by absolute rooting, not careful per-call code.

## Self-Check: PASSED

- `app/config.py` and `app/__init__.py` exist on disk with the `_DATA_DIR` seam (verified: `settings.backup_dir` = `E:\dev\myorishop\data\backups`, `settings.db_path` = `E:\dev\myorishop\data\myorishop.db`, `env_file` = `E:\dev\myorishop\data\.env`).
- Task 1 commit `800c45e` present in git history.
- Three PKG-03 gates GREEN (`3 passed, 3 deselected`).

---
*Phase: 31-packaging-launcher-signed-release-pipeline*
*Completed: 2026-07-22*
