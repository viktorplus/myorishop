---
phase: 31-packaging-launcher-signed-release-pipeline
plan: 08
subsystem: infra
tags: [packaging, launcher, installer, inno-setup, embeddable, windows, gap-closure, pkg-01, pkg-02]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    provides: "build_release.assemble_onedir / generate_iss / fetch_embeddable (Plan 04), launcher package + boot() + swap guards (Plans 03/06/07)"
provides:
  - "build_release.assemble_launcher_runtime — a second extraction of the SAME SHA-256-verified embeddable zip into dist\\launcher, with the launcher ._pth and the launcher package"
  - "A Start-Menu shortcut whose target is a file the installer actually ships: {app}\\launcher\\python.exe with Parameters \"-m launcher\""
  - "test_iss_referenced_paths_exist_in_dist — a build-time gate that every path the .iss names resolves in the assembled dist"
  - "test_real_launcher_runtime_resolves_the_sibling_package — skip-gated proof that the shipped runtime imports the sibling launcher package from an unrelated cwd"
affects: [32-in-app-secure-self-update, uat]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "One verified download, two extractions — a second runtime never means a second network fetch (T-31-SC)"
    - "A ._pth `..` entry is the ONLY way an isolated-mode embeddable interpreter can import a sibling package (cwd and PYTHONPATH are ignored)"
    - "Generated-artifact gate: parse the emitted script and assert every path it references exists on disk"

key-files:
  created: []
  modified:
    - build_release.py
    - tests/test_packaging.py
    - launcher/__main__.py
    - .planning/phases/31-packaging-launcher-signed-release-pipeline/31-UAT-STEPS.md
    - app/__init__.py

key-decisions:
  - "The launcher gets its OWN embeddable runtime in launcher\\ (RESEARCH Pattern 4 option (a)) rather than a PyInstaller launcher.exe stub — CLAUDE.md rejects PyInstaller for this project, and the stub the .iss promised was never implemented"
  - "The launcher ._pth is exactly python313.zip / . / .. — Lib\\site-packages and app are omitted so the launcher stays stdlib-only and cannot import the bundle it swaps"
  - "python.exe (console), not pythonw.exe: it mirrors run.bat and is the only place the operator sees the «Migration failed - server not started» abort from Plan 31-06"
  - "The launcher runtime is extracted from the already-verified fetch_embeddable artifact — no second download, no second hash to keep pinned (T-31-SC)"
  - "The [Icons] entry is asserted to be a SINGLE line: Inno reads one entry per line, so a wrapped entry would silently drop Parameters/WorkingDir and the shortcut would open a bare REPL"

patterns-established:
  - "Every generated deployment artifact is parsed back and its referenced paths existence-checked before it can ship"

requirements-completed: [PKG-01, PKG-02]

# Metrics
duration: 33min
completed: 2026-09-03
---

# Phase 31 Plan 08: Start-Menu Shortcut Target Summary

**The Start-Menu shortcut now targets a file the installer actually ships — `{app}\launcher\python.exe -m launcher`, running on a second extraction of the same SHA-256-verified embeddable runtime that lives OUTSIDE the swappable `app\`, with a test that fails the build if any path the generated `.iss` names is missing.**

## Performance

- **Duration:** ~33 min
- **Completed:** 2026-09-03
- **Tasks:** 3/3

## What Was Built

### Task 1 — `assemble_launcher_runtime` (RED `3ffc5d2` → GREEN `8fbbd50`)

`build_release.assemble_launcher_runtime(*, embeddable_zip, dest, repo_root)` owns the whole `launcher\` output dir: it wipes it, extracts the **same** embeddable zip `assemble_onedir` unpacks (one verified download, two extractions — no second `fetch_embeddable` call, so `EMBEDDABLE_SHA256` remains the single supply-chain pin, T-31-SC), overwrites `python313._pth` with the launcher variant and copies the launcher package in. It reuses `assemble_onedir`'s delete-partial-on-failure wrapper, so a half-written launcher dir can never pass for a valid one.

`_LAUNCHER_PTH_LINES = ("python313.zip", ".", "..")` is a new module constant beside `_PTH_LINES`, carrying the verified rationale in a comment: a `._pth` forces isolated mode (`sys.flags.isolated == 1`, `safe_path True` — measured on the real `dist/app` runtime), so the cwd and `PYTHONPATH` are NOT on `sys.path`; only the `..` entry, resolving to the install root, makes the sibling `launcher` package importable. `Lib\site-packages` and `app` are deliberately omitted — the launcher is stdlib-only and must not be able to reach into the bundle it swaps.

Step 5 of `assemble_onedir` (previously `if launcher_src.exists(): _copy(...)`, which shipped only the `.py` tree) now calls the new function, inside the existing `try`. `_write_pth` gained a `lines` parameter so both runtimes share one writer instead of a second mechanism. The install-root layout comment now states that `launcher\` holds its own runtime. `_zip_onedir` and the `.iss` `[Files] Source: "launcher\*"` line already ship the tree recursively and were not touched.

Two tests:

- `test_launcher_runtime_is_bundled_outside_app` — `dist/launcher/python.exe` exists; its `._pth` is exactly `python313.zip` / `.` / `..` (and contains neither `Lib\site-packages` nor `app`); `__main__.py`, `swap.py`, `adapters.py` are present; `dist/app/launcher` does **not** exist.
- `test_real_launcher_runtime_resolves_the_sibling_package` — skip-gated on the real `dist/launcher/python.exe`, whose absence names `uv run python build_release.py --version v1.<N>` in the skip reason. It runs the shipped runtime with `-c "import launcher; print(launcher.__file__)"` from an unrelated cwd and asserts the printed path is `dist/launcher/__init__.py`. It imports the package rather than running `-m launcher`, which would start the app and open a browser.

### Task 2 — the shortcut points at something real (RED `67ce8b8` → GREEN `cfc2690`)

`generate_iss` now emits `UninstallDisplayIcon={app}\launcher\python.exe` and
`Name: "{autoprograms}\MyOriShop"; Filename: "{app}\launcher\python.exe"; Parameters: "-m launcher"; WorkingDir: "{app}"`.
Every other locked directive (`PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\MyOriShop`, `AppVersion`, `OutputBaseFilename`, both `[Files]` Source lines, the "data\ is NOT shipped" note) is byte-identical. The docstring records the invariant, why `python.exe` and not `pythonw.exe`, and that `WorkingDir` is cosmetic because the isolated-mode search path — not the cwd — resolves `-m launcher`.

`test_iss_referenced_paths_exist_in_dist` assembles a fake dist, generates the `.iss` into it, and resolves every path the script names: each `[Files] Source` pattern (relative to the script dir, glob-expanded, at least one match required), every `[Icons] Filename` and `UninstallDisplayIcon` (the `{app}\` prefix mapped onto the dist dir). All must exist. It also asserts the literal `launcher.exe` is gone from the script and that the shortcut carries `Parameters: "-m launcher"` — without it the target is a bare interpreter and the shortcut would open a REPL. The parser is ~15 lines of `str.startswith`/`partition` local to the test; no `.iss` parsing dependency was added.

### Task 3 — no artifact promises a stub that is never built (`03f3fc3`)

`launcher/__main__.py`'s docstring now opens with the real invocation (`launcher\python.exe -m launcher`, the Start-Menu shortcut's target) on the runtime shipped inside `launcher\`, states that there is no compiled `.exe` stub and none is planned, and explains why it must not run on `app\python.exe`: a running interpreter image cannot be deleted, so the post-swap `shutil.rmtree(app.prev)` silently fails and leaks a full copy of the previous bundle on every successful update. The install-root layout, the never-import-`app.*` rule and the Phase-32 deferral note are unchanged; no code changed in this task.

`31-UAT-STEPS.md`'s Test-2 preamble now tells the operator the launcher is `R\launcher\python.exe -m launcher` instead of a file that never existed. `app/__init__.py` `__version__` 1.58 → 1.59.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_packaging.py -x` | 9 passed, 1 skipped (the real-runtime import gate — no local build) |
| `uv run pytest tests/test_launcher.py tests/test_packaging.py -x` | 28 passed, 1 skipped |
| `uv run pytest -q` (full suite) | **4 failed, 1465 passed, 14 skipped** — the 4 are the known pre-existing `tests/test_sync_ui.py` set (`sync_client._run_lock` held by the lifespan auto-sync thread), unrelated to this plan |
| `uv run ruff check build_release.py launcher tests/test_packaging.py` | All checks passed |
| `grep -rn "launcher\.exe" launcher build_release.py --include='*.py'` | no matches |

Deferred to UAT (needs a real build + a bare Windows VM, blocked on the operator pinning `EMBEDDABLE_SHA256` and running `uv run python build_release.py --version v1.<N>`): install from the compiled setup, click the Start-Menu shortcut, confirm the app reaches the login page on its own runtime with `data\` created beside `app\`. Running that build also flips `test_real_launcher_runtime_resolves_the_sibling_package` from skip to run.

No server was started and no port was taken during this plan.

## Deviations from Plan

### 1. [Documentation-only] Task 3's grep acceptance criterion is literally unsatisfiable over `tests/`

- **Found during:** Task 3 verification
- **Issue:** the criterion `grep -rn "launcher\.exe" launcher build_release.py tests` must return nothing, but Task 2 of the same plan mandates a regression asserting `"launcher.exe" not in text`. That assertion — and the docstring naming the closed gap — necessarily contain the literal.
- **Resolution:** the criterion was applied to its intent ("no artifact *promises* a stub"). `launcher/` and `build_release.py` are clean; the only remaining occurrences in `tests/test_packaging.py:310,328,329` are the negative assertion and its explanation, i.e. the opposite of a promise. Obfuscating the literal to satisfy a literal grep was rejected as making the test unreadable.
- **Files:** none changed for this.

### 2. [Rule 3 - Blocking] `_write_pth` gained a `lines` parameter

- **Found during:** Task 1
- **Issue:** `_write_pth` hardcoded `_PTH_LINES`, so the launcher runtime would have needed either the app's search path (wrong — it would put `Lib\site-packages` and `app` on the launcher's `sys.path`) or a second `._pth` writer.
- **Fix:** one writer, `_write_pth(dest_dir, lines=_PTH_LINES)`, called with `_LAUNCHER_PTH_LINES` for the launcher. Its docstring now also records that the `python313._pth` filename is matched against `python313.dll` and therefore governs `pythonw.exe` too. No call site changed.
- **Files:** `build_release.py` · **Commit:** `8fbbd50`

### 3. [Rule 2 - Missing critical check] `[Icons]` single-line assertion

- **Found during:** Task 2
- **Issue:** the `[Icons]` line exceeds ruff's 100-char limit, so the source uses a backslash line-continuation inside the f-string. If that continuation were ever lost, Inno — which reads one entry per line — would silently drop `Parameters`/`WorkingDir`, and the shortcut would launch a bare Python REPL. Nothing would have caught it: the path-existence parser would simply stop matching the `Name:` line.
- **Fix:** the test asserts there is exactly one `Name: ` line and that it ends with `WorkingDir: "{app}"`.
- **Files:** `tests/test_packaging.py` · **Commit:** `cfc2690`

No architectural (Rule 4) decisions were needed; no checkpoint was hit.

## Out of Scope / Deferred

- The 3 pre-existing ruff findings in `tests/test_launcher.py` (B017/E501/UP031 from the 31-01 scaffold) are untouched and remain logged in `deferred-items.md`. A repo-wide `ruff check tests` reports 25 findings in total, all pre-existing in files this plan did not touch (`test_offline.py`, `test_auth.py`, `test_update.py`, and others); none are in `build_release.py`, `launcher/` or `tests/test_packaging.py`.
- The Start-Menu icon is the stock Python one until a real `.ico` is added — cosmetic, explicitly out of scope per the plan.
- The second runtime costs roughly 15 MB on disk (~10 MB in the release zip). Accepted by the plan: it is the price of the launcher living outside the swap target.

## Threat Model Outcome

| Threat ID | Disposition | Outcome |
|-----------|-------------|---------|
| T-31-08 (dead/plantable shortcut target) | mitigate | **Closed.** The target is a shipped file, and `test_iss_referenced_paths_exist_in_dist` fails the build if any referenced path is missing. |
| T-31-SC (second runtime supply chain) | mitigate | **Closed.** `assemble_launcher_runtime` takes the already-verified zip as a parameter; `fetch_embeddable` is still called exactly once in `_build_cli`. |
| T-31-06 (stale `app.prev` after a good update) | mitigate | **Closed at the layout level.** The launcher runs from `launcher\`, outside the swap target, so `rmtree(app.prev)` is not blocked by its own running image. |
| T-31-09 (`..` puts the install root on the launcher's `sys.path`) | accept | Accepted by design — it IS the mechanism. `python313.zip` precedes `..` so the stdlib cannot be shadowed, the launcher imports only stdlib + `launcher.*`, `import site` is omitted, and anyone able to plant a module in the install root can already overwrite `launcher\swap.py` outright. |
| T-31-01 (unsigned installer / SmartScreen) | accept | Unchanged. |

No new security surface was introduced beyond the accepted T-31-09 residual: no new network path, no new endpoint, no schema change.

## Known Stubs

None. `assemble_launcher_runtime` is fully wired into `assemble_onedir`, and the `.iss` it feeds is generated by the shipped CLI path.

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `3ffc5d2` | test | RED: launcher-runtime layout gate + skip-gated real-runtime import gate |
| `8fbbd50` | feat | GREEN: `assemble_launcher_runtime` + `_LAUNCHER_PTH_LINES`, wired into `assemble_onedir` |
| `67ce8b8` | test | RED: every `.iss` referenced path must exist in dist |
| `cfc2690` | feat | GREEN: shortcut + uninstall icon target `{app}\launcher\python.exe -m launcher` |
| `03f3fc3` | docs | launcher docstring, UAT runbook, `__version__` 1.58 → 1.59 |

## Self-Check: PASSED

All 5 modified/created files exist on disk; all 5 commit hashes resolve in `git log`.
