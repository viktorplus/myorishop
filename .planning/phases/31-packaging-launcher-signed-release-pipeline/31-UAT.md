---
status: testing
phase: 31-packaging-launcher-signed-release-pipeline
source: [31-VERIFICATION.md]
started: 2026-07-22T13:34:37Z
updated: 2026-07-22T13:34:37Z
---

## Current Test

number: 1
name: Bare-Windows install + launch (PKG-01, PKG-02)
expected: |
  On a clean Windows VM with no Python/uv/git: run MyOriShop-Setup-*.exe, clear
  SmartScreen via «Подробнее → Выполнить в любом случае», launch from the
  Start-Menu shortcut, reach the login page at http://127.0.0.1:8000 on the
  distribution's OWN bundled runtime; the uninstaller is registered per-user
  under %LOCALAPPDATA%\MyOriShop.
awaiting: user response

## Tests

### 1. Bare-Windows install + launch (PKG-01, PKG-02)
expected: On a clean Windows VM with no Python/uv/git, run MyOriShop-Setup-*.exe, clear SmartScreen via «Подробнее → Выполнить в любом случае», launch from the Start-Menu shortcut, reach the login page at http://127.0.0.1:8000 on the distribution's OWN bundled runtime; the uninstaller is registered per-user under %LOCALAPPDATA%\MyOriShop.
result: issue
severity: blocker
reported: |
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
result: issue
severity: blocker
reported: |
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
result: [pending]

## Summary

total: 4
passed: 1
issues: 2
pending: 1
skipped: 0
blocked: 0

## Gaps

- truth: "A freshly installed copy reaches the login page on its own bundled runtime"
  status: failed
  reason: "Nothing on the first-run path runs `alembic upgrade head`, so the DB file is created without a schema and every page returns HTTP 500 (`no such table: users`). Proven: /health 200 but / 500 on the built distribution with a clean data dir; after running `alembic upgrade head` manually with the bundled python.exe the same build serves / → 303 → /setup (200, «MyOriShop 1.15»)."
  severity: blocker
  test: 1
  artifacts:
    - path: "launcher/__main__.py"
      issue: "main() calls app_process.start() with no migration step; adapters.migrate is only reachable from apply_update (the update path)."
    - path: "run.bat"
      issue: "The dev launcher DOES run `uv run alembic upgrade head` before uvicorn and aborts on failure — the packaged path has no equivalent."
  missing:
    - "Run `alembic upgrade head` before starting the app on every launcher boot (mirroring run.bat), aborting the boot on failure."
    - "A packaging test that boots the assembled dist against an EMPTY data dir and asserts GET / is not 500 — the current suite only unit-tests pieces, so this never surfaced."

- truth: "The Start-Menu shortcut launches the installed application"
  status: failed
  reason: "The generated .iss points [Icons] and UninstallDisplayIcon at {app}\\launcher\\launcher.exe (build_release.py:276, :286) but no launcher.exe exists and nothing builds one; dist/launcher/ and the release zip carry only __init__.py, __main__.py, adapters.py, swap.py."
  severity: blocker
  test: 1
  artifacts:
    - path: "build_release.py"
      issue: "Lines 276 and 286 reference launcher\\launcher.exe; assemble_onedir only copies the launcher .py tree (line 205-207)."
    - path: "launcher/__main__.py"
      issue: "Docstring line 3 treats the compiled launcher.exe as optional ('or the compiled launcher.exe stub') — it was never implemented."
  missing:
    - "Either build the launcher.exe stub the .iss promises, or point the shortcut at a real entry point that exists in the shipped tree (e.g. a .bat/.vbs that runs app\\python.exe -m launcher from the install root)."
    - "A test asserting every path referenced by the generated .iss exists in dist\\ before the installer is compiled."

- truth: "A failed update leaves the install runnable (matched-pair rollback is complete)"
  status: failed
  reason: "The failure path never clears data\\pending.json, and main() re-runs run_once every 2 seconds. On the next tick the marker is still valid, staged\\ is already consumed, and swap.py:87-88 rename app→app.prev BEFORE the try block at line 89 — so os.replace(staged→app) raises FileNotFoundError outside the guarded region. Observed end state: app=False, app.prev=True, app.failed=True, marker=True, app\\python.exe missing. One failed update bricks the installation."
  severity: blocker
  test: 2
  artifacts:
    - path: "launcher/swap.py"
      issue: "Lines 87-88 (the two os.replace calls) sit outside the try: at line 89, so a missing staged\\ escapes the rollback entirely."
    - path: "launcher/__main__.py"
      issue: "Line 92 unlinks the marker only after apply_update returns; an exception leaves it in place for the next 2-second tick."
  missing:
    - "Clear or quarantine the marker on the failure path as well as on success."
    - "Guard the cycle on staged_dir existing before the first rename, and bring both renames inside the rollback-guarded region."
    - "A launcher test that runs two consecutive ticks with one failing update and asserts app\\ still exists afterwards."
