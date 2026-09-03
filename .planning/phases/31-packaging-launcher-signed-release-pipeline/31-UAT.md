---
status: testing
phase: 31-packaging-launcher-signed-release-pipeline
source: [31-VERIFICATION.md]
started: 2026-07-22T13:34:37Z
updated: 2026-09-03T11:05:00Z
---

## Current Test

number: 1
name: Bare-Windows install + launch (PKG-01, PKG-02)
expected: |
  A compiled installer (`iscc dist\MyOriShop.iss`) runs on a clean Windows machine
  with no Python/uv/git: SmartScreen cleared via «Подробнее → Выполнить в любом
  случае», Start-Menu shortcut launches the app, login page reachable, per-user
  uninstaller registered under %LOCALAPPDATA%\MyOriShop.
awaiting: user response

## Re-test note (2026-09-03)

All three blockers recorded below were closed by gap-closure plans 31-06, 31-07 and
31-08, and a follow-up code review found and fixed 15 further findings (see
31-REVIEW.md / 31-REVIEW-FIX.md) — including CR-01, a release-archive layout defect
that would have made every self-update stage an unrunnable bundle. Tests 1, 2 and 4
are therefore reset to `pending`: their prior results describe code that no longer
exists. Test 3 stands as passed. The historical `prior_report` blocks are kept
verbatim because they document how each blocker was found.

## Tests

### 1. Bare-Windows install + launch (PKG-01, PKG-02)
expected: On a clean Windows VM with no Python/uv/git, run MyOriShop-Setup-*.exe, clear SmartScreen via «Подробнее → Выполнить в любом случае», launch from the Start-Menu shortcut, reach the login page at http://127.0.0.1:8000 on the distribution's OWN bundled runtime; the uninstaller is registered per-user under %LOCALAPPDATA%\MyOriShop.
result: pending
blocked_on: |
  No installer has ever been compiled: `iscc` is not installed and there is no
  C:\Program Files (x86)\Inno Setup 6. The only setup exe on disk,
  dist/Output/MyOriShop-Setup-1.14.exe (2026-07-22), predates every gap fix and
  still carries the dead launcher.exe shortcut — do not test with it.
  Prerequisite: install Inno Setup 6, rebuild (`uv run python build_release.py
  --version v1.60`), then `iscc dist\MyOriShop.iss`.
prior_result: issue (blocker) — root cause closed by plan 31-06, re-test required
prior_report: |
  Verified 2026-08-09 by building the real distribution locally
  (`uv run python build_release.py --version v1.15` → dist/MyOriShop-1.15.zip,
  27 MB) and booting it on a free port with a clean data dir:
    dist/app/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8056
    MYORISHOP_DATA_DIR=<empty scratch dir>

  WHAT WORKS:
  - The bundled runtime is genuinely self-contained: Python 3.13.1, sys.prefix
    inside dist\app, sys.path carries NO venv and NO system site-packages.
  - PKG-03 holds: data\ was created outside app\ with device_id, secret_key,
    myorishop.db (+ -wal/-shm).
  - GET /health → 200 {"version":"1.15","status":"ok"}.

  WHAT FAILS (blocker): GET / → HTTP 500, and every page is 500. The log shows
  `sqlalchemy.exc.OperationalError: no such table: users`
  (SQL: SELECT count(*) AS count_1 FROM users). The DB file is created but the
  schema never is — a fresh install can NEVER reach the login page.

  ROOT CAUSE: nothing on the first-run path runs `alembic upgrade head`.
  - run.bat (dev) DOES run it before uvicorn and aborts on failure.
  - app/main.py has no create_all and no alembic call.
  - launcher/__main__.py::main() only calls app_process.start(); adapters.migrate
    is invoked ONLY inside apply_update, i.e. exclusively on the update-swap path.
  So the very first launch of an installed copy has no migration step at all.

  SECOND DEFECT (also blocker, found while checking the same item): the generated
  installer script points the Start-Menu shortcut AND UninstallDisplayIcon at
  {app}\launcher\launcher.exe (build_release.py:276 and :286), but no such file
  exists and nothing builds it. dist/launcher/ and the release zip contain only
  __init__.py, __main__.py, adapters.py, swap.py. launcher/__main__.py:3 calls the
  compiled stub optional ("or the compiled launcher.exe stub") — it was never
  implemented. So the Start-Menu entry the operator is told to click targets a
  missing file.

  STILL UNVERIFIED here (needs a real clean VM): SmartScreen «Выполнить в любом
  случае», the actual installer run, per-user uninstaller registration.

### 2. Live launcher swap → migrate → restart + matched-pair rollback (PKG-04)
expected: On a packaged install, hand-place a staged\ dir + data\pending.json and watch the launcher stop the app, rename app→app.prev, rename staged→app, run alembic upgrade head, restart, and drop app.prev on success. Then inject a failing migration and watch the matched-pair rollback restore app.prev→app AND the pre-update DB (with -wal/-shm deleted).
result: pending
retest_scope: |
  Re-run the live swap on a POST-FIX build (v1.60 or later), and extend it to the
  case the unit suite structurally cannot reach: two consecutive ticks with one
  FAILING update, asserting app\ still exists and is runnable afterwards, then a
  SECOND failing update with app.failed\ already present. The original brick was
  found by the live run and missed by the unit suite, so the live re-run is the
  honest close-out even though the two-tick regression now passes in pytest.
prior_result: issue (blocker) — root cause closed by plan 31-07, re-test required
prior_report: |
  Run 2026-08-09 for real: two copies of the built distribution on a scratch
  install root, real launcher adapters (real subprocess, real alembic, real HTTP
  health poll), real os.replace renames. Only adapters._PORT was patched to 8058
  so the operator's own instance on 8000 was never touched.

  HAPPY PATH — PASSES exactly as specified:
    boot app 1.15 → marker {staged_dir, expected_version 1.16, db_backup_path}
    → run_once → stop → app→app.prev → staged→app → alembic upgrade head →
    restart → GET /health returns {"version":"1.16"} → app.prev removed.
    Final state: app=1.16, app.prev gone, staged gone, marker deleted,
    DB size unchanged 245760 → 245760.

  ROLLBACK — PASSES: staged deliberately served 1.15 while the marker demanded
  1.99, so the version-matched health check failed. run_once raised
  RuntimeError("post-update health check failed"); app.failed was created, the
  previous app\ was restored (version back to 1.15), the DB was restored intact.

  BLOCKER FOUND — the failure leaves a STUCK MARKER that destroys the install on
  the next tick. apply_update never clears data\pending.json on the failure path
  (launcher/__main__.py:92 unlinks it only after a successful return), and
  main() calls run_once every 2 seconds. Replaying the real tree the rollback
  left behind (app=1.15, app.failed present, staged consumed, marker still there):
    os.replace(app → app.prev)   -- succeeds; this line sits OUTSIDE the try
    os.replace(staged → app)     -- FileNotFoundError [WinError 2], staged is gone
  The exception escapes apply_update BEFORE the try block that owns the rollback
  (launcher/swap.py:87-89 are outside `try:` at line 89). Observed end state:
    app=False  app.prev=True  app.failed=True  staged=False  marker=True
    app\python.exe present: False
  i.e. the application directory no longer exists, and the marker is STILL there
  so the cycle repeats on every relaunch. One failed update bricks the install.

  Suggested fixes (not applied — verify-work does not change code):
  - delete/quarantine the marker on the failure path too, not just on success;
  - move the two renames inside the guarded region so a missing staged\ cannot
    leave app\ renamed away;
  - refuse to start the cycle when the marker's staged_dir does not exist.

### 3. Offline minisign keygen + vendored public key (PKG-05)
expected: Operator runs `minisign -G` on the OFFLINE machine, stores minisign.key off-repo, commits ONLY app/minisign.pub (base64 line starts 'RW'); confirm the secret key is never committed (.gitignore blocks *.key). Once present, tests/test_release_verify.py::test_vendored_pubkey_present_and_bundled runs green (RW + bundled) instead of skipping.
result: pass
evidence: |
  Satisfied out-of-order during Phase 32 wave 1 (the keygen checkpoint there is the
  same operator action this item describes). Verified 2026-08-09:
  - app/minisign.pub present (115 bytes, committed);
  - the secret key lives outside the repo (C:\Users\Admin\.minisign\minisign.key)
    and `git ls-files | grep '\.key$'` returns nothing tracked;
  - `git check-ignore -v test.key` → .gitignore:52 `*.key`, so a stray secret key
    cannot be staged;
  - tests/test_release_verify.py::test_vendored_pubkey_present_and_bundled PASSED
    (not SKIPPED) — full file 5 passed, which is the exact skip→green flip this
    item asked for.

### 4. Real signed-release pipeline run (PKG-05)
expected: Pin a verified Python 3.13.x embeddable SHA-256 into EMBEDDABLE_SHA256, push a throwaway tag v1.<N> (with __version__ matching); confirm release.yml builds on the Windows runner and drafts a release with the archive + installer + SHA256SUMS + manifest.txt. Then sign manifest.txt with the OFFLINE key, attach manifest.txt.minisig, and Publish.
result: pending
unblocked: |
  The reason this was skipped ("can't run the pipeline until the blockers are
  fixed") no longer holds — all three blockers are closed and EMBEDDABLE_SHA256 is
  pinned for 3.13.1. Not yet run: `gh release list` and
  `gh run list --workflow=release.yml` are both empty and no .minisig exists
  anywhere in the repo or dist\. The minisign signing step is deliberately an
  offline human action (T-31-02) and cannot be automated here.
  Note: the release-verify minisign round-trip job IS proven green on real CI
  (GitHub Actions run 33699733177) — it is the tag-triggered release.yml build
  that has never run.

## Summary

total: 4
passed: 1
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

- truth: "A freshly installed copy reaches the login page on its own bundled runtime"
  status: resolved
  resolved_by: "31-06-PLAN.md (commits 5499df9 test / afaed58 feat / fd15b43 test)"
  resolved_evidence: "launcher/__main__.py:176 boot() = migrate(paths) then app_process.start(), wired into main() ahead of the watch loop; a failing migration prints to stderr and exits non-zero, so the app is never started on an unmigrated schema. Proven by tests/test_packaging.py::test_assembled_dist_boots_against_empty_data_dir, which starts the REAL dist/app/python.exe on an ephemeral port against an EMPTY data dir and asserts a non-500 response — the executor first reproduced the original 500 / `no such table: users` without the migration, so the assertion is not vacuous."
  original_reason: "Nothing on the first-run path runs `alembic upgrade head`, so the DB file is created without a schema and every page returns HTTP 500 (`no such table: users`). Proven: /health 200 but / 500 on the built distribution with a clean data dir; after running `alembic upgrade head` manually with the bundled python.exe the same build serves / → 303 → /setup (200, «MyOriShop 1.15»)."
  severity: blocker
  test: 1
  root_cause: "launcher/__main__.py:101-113 — main() calls app_process.start() with no migration step. adapters.migrate is reachable ONLY from apply_update (launcher/__main__.py:86), i.e. the update-swap path, so a first launch never migrates."
  verified_at_head: "2026-09-03 — re-read at HEAD 9642261; still true, diagnosis not stale."
  artifacts:
    - path: "launcher/__main__.py"
      issue: "main() calls app_process.start() with no migration step; adapters.migrate is only reachable from apply_update (the update path)."
    - path: "run.bat"
      issue: "The dev launcher DOES run `uv run alembic upgrade head` before uvicorn and aborts on failure — the packaged path has no equivalent."
  missing:
    - "Run `alembic upgrade head` before starting the app on every launcher boot (mirroring run.bat), aborting the boot on failure."
    - "A packaging test that boots the assembled dist against an EMPTY data dir and asserts GET / is not 500 — the current suite only unit-tests pieces, so this never surfaced."

- truth: "The Start-Menu shortcut launches the installed application"
  status: resolved
  resolved_by: "31-08-PLAN.md (commits 3ffc5d2/8fbbd50 launcher runtime, 67ce8b8/cfc2690 shortcut target, 03f3fc3 docs) + WR-07/WR-09 fixes (9392df0, bc848af)"
  resolved_evidence: "build_release.py gained assemble_launcher_runtime(), so dist/launcher/python.exe (105 840 B) is really built with python313._pth = python313.zip / . / .., and the .iss now emits `Name: \"{autoprograms}\\MyOriShop\"; Filename: \"{app}\\launcher\\python.exe\"; Parameters: \"-m launcher\"; WorkingDir: \"{app}\"`. tests/test_packaging.py::test_iss_referenced_paths_exist_in_dist parses the generated .iss and existence-checks every Source:/Filename:/UninstallDisplayIcon path. `launcher.exe` appears nowhere in the tree. Orchestrator confirmed against a real build: ./dist/launcher/python.exe resolved the sibling launcher package and reported has boot: True."
  original_reason: "The generated .iss points [Icons] and UninstallDisplayIcon at {app}\\launcher\\launcher.exe (build_release.py:276, :286) but no launcher.exe exists and nothing builds one; dist/launcher/ and the release zip carry only __init__.py, __main__.py, adapters.py, swap.py."
  severity: blocker
  test: 1
  root_cause: "generate_iss() hardcodes {app}\\launcher\\launcher.exe at build_release.py:276 (UninstallDisplayIcon) and :286 ([Icons] Filename), but assemble_onedir copies only the launcher .py package (build_release.py:205-207) and nothing compiles a stub. The shipped tree has no .exe under launcher\\, so the Start-Menu target does not exist."
  verified_at_head: "2026-09-03 — re-read at HEAD 9642261; grep for 'launcher.exe' shows the two build_release.py lines plus the already-generated dist/MyOriShop.iss:9,19 carrying the same broken target. Still true."
  artifacts:
    - path: "build_release.py"
      issue: "Lines 276 and 286 reference launcher\\launcher.exe; assemble_onedir only copies the launcher .py tree (line 205-207)."
    - path: "launcher/__main__.py"
      issue: "Docstring line 3 treats the compiled launcher.exe as optional ('or the compiled launcher.exe stub') — it was never implemented."
  missing:
    - "Either build the launcher.exe stub the .iss promises, or point the shortcut at a real entry point that exists in the shipped tree (e.g. a .bat/.vbs that runs app\\python.exe -m launcher from the install root)."
    - "A test asserting every path referenced by the generated .iss exists in dist\\ before the installer is compiled."

- truth: "A failed update leaves the install runnable (matched-pair rollback is complete)"
  status: resolved
  resolved_by: "31-07-PLAN.md (commits e0fc7a0/b11ab05 swap guard, 3521401/457a700 marker quarantine) + WR-01/WR-03/WR-04/WR-06 fixes (fa84558, d5745f2, e042549, eb6cebf) + CR-02 fix (75d49b9)"
  resolved_evidence: "apply_update refuses a missing staged\\ BEFORE stop_app and before any rename; stop_app and both os.replace calls now sit inside a BaseException-keyed guarded region; every directory rename clears its destination first (Windows os.replace refuses an existing directory); the pending marker is consumed on every failure path (5 quarantine sites → data\\pending.failed.json) so the 2-second watch loop cannot replay it; the rollback is proportional and its DB restore is gated on migrate_attempted AND a confirmed stop; pending.json is now written atomically (temp + os.replace) so a torn read cannot silently delete a valid in-flight marker. tests/test_launcher.py carries the two-tick regression (one failing update, app\\ still present afterwards) and passes."
  original_reason: "The failure path never clears data\\pending.json, and main() re-runs run_once every 2 seconds. On the next tick the marker is still valid, staged\\ is already consumed, and swap.py:87-88 rename app→app.prev BEFORE the try block at line 89 — so os.replace(staged→app) raises FileNotFoundError outside the guarded region. Observed end state: app=False, app.prev=True, app.failed=True, marker=True, app\\python.exe missing. One failed update bricks the installation."
  severity: blocker
  test: 2
  root_cause: "Two independent defects compound. (a) launcher/swap.py:86-88 — stop_app() and BOTH os.replace calls sit outside the try: that opens at line 89, so once app\\ has been renamed to app.prev\\ a missing staged\\ raises FileNotFoundError with no rollback handler in scope. (b) launcher/__main__.py:92 — marker.unlink() runs only after apply_update returns normally, so a raised exception leaves data\\pending.json in place and main()'s 2-second loop (line 107-109) replays the now-unsatisfiable cycle."
  verified_at_head: "2026-09-03 — re-read at HEAD 9642261; both line ranges unchanged. Still true."
  artifacts:
    - path: "launcher/swap.py"
      issue: "Lines 87-88 (the two os.replace calls) sit outside the try: at line 89, so a missing staged\\ escapes the rollback entirely."
    - path: "launcher/__main__.py"
      issue: "Line 92 unlinks the marker only after apply_update returns; an exception leaves it in place for the next 2-second tick."
  missing:
    - "Clear or quarantine the marker on the failure path as well as on success."
    - "Guard the cycle on staged_dir existing before the first rename, and bring both renames inside the rollback-guarded region."
    - "A launcher test that runs two consecutive ticks with one failing update and asserts app\\ still exists afterwards."
