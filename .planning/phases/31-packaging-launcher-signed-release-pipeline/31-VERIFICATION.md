---
phase: 31-packaging-launcher-signed-release-pipeline
verified: 2026-09-03T09:02:24Z
status: human_needed
score: 5/5 must-haves code-verified (3 require machine/offline confirmation)
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 5/5 code contracts verified (4 require machine/offline UAT confirmation)
  gaps_closed:
    - "GAP-1 (blocker): a fresh install never ran `alembic upgrade head`, so every page returned 500 (`no such table: users`)"
    - "GAP-2 (blocker): the Start-Menu shortcut and UninstallDisplayIcon targeted {app}\\launcher\\launcher.exe, a file nothing ever built"
    - "GAP-3 (blocker): a failed update left a stuck pending.json; the next 2-second tick renamed app\\ away and bricked the install"
    - "Prior human item 3 (offline minisign keygen + vendored pubkey): app/minisign.pub is now present and committed, no *.key is tracked, and test_vendored_pubkey_present_and_bundled RUNS green instead of skipping"
    - "Prior anti-pattern: EMBEDDABLE_SHA256 was empty; 3.13.1 is now pinned with a stated provenance note, so a real build no longer raises"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Compile the installer and run it on a bare Windows machine (PKG-01, PKG-02)"
    expected: "Run `iscc dist\\MyOriShop.iss` to produce MyOriShop-Setup-1.60.exe. On a clean Windows VM with no Python/uv/git: run it, clear SmartScreen via «Подробнее → Выполнить в любом случае», confirm the per-user install lands under %LOCALAPPDATA%\\MyOriShop with an uninstall entry, click the Start-Menu «MyOriShop» shortcut, and reach the login/setup page at http://127.0.0.1:8000 on the distribution's own bundled runtime."
    why_human: "`iscc` is NOT installed in this environment (no `C:\\Program Files (x86)\\Inno Setup 6`), so the .iss has been generated and parsed but never COMPILED — no installer exe exists for the current code. The only setup exe on disk, dist/Output/MyOriShop-Setup-1.14.exe, is from 2026-07-22 and predates every gap fix (it still carries the dead launcher.exe shortcut). SmartScreen, the Start-Menu click, per-user uninstaller registration and the bare-machine condition have never been observed. The runtime half IS proven here: tests/test_packaging.py::test_assembled_dist_boots_against_empty_data_dir boots the real 27 MB dist through launcher.boot() against an empty data dir and asserts GET / is not 500 — it PASSED."
  - test: "Live packaged failed-update, two consecutive ticks (PKG-04)"
    expected: "On a packaged install, hand-place staged\\ + data\\pending.json, force the migration to fail, and watch tick 1 roll back (app\\ = previous code, app.failed\\ created, DB restored, marker moved to data\\pending.failed.json) and tick 2 be a no-op that leaves app\\ intact and runnable."
    why_human: "The state machine is fully unit-proven with real os.replace on real directories (test_two_ticks_with_one_failing_update_keep_app_dir, test_run_once_refuses_marker_whose_staged_dir_is_gone, test_ctrl_c_mid_swap_rolls_back_and_quarantines_the_marker — all PASS), and the live happy-path + single-rollback was already run for real in the 31-UAT. But the ORIGINAL two-tick brick was found by the live run and missed by the unit suite, so the post-fix live confirmation against real subprocess/alembic/HTTP is the honest close-out. Fold it into the bare-Windows VM session above."
  - test: "Real signed-release pipeline run + offline signature (PKG-05)"
    expected: "Push tag v1.60 (matching __version__). Confirm release.yml builds on windows-2022 and drafts a release carrying MyOriShop-1.60.zip, MyOriShop-Setup-1.60.exe, SHA256SUMS and manifest.txt. Then on the OFFLINE machine `minisign -S -m manifest.txt -t \"MyOriShop 1.60\"`, attach manifest.txt.minisig to the draft, publish, and verify with `minisign -Vm manifest.txt -p app/minisign.pub`."
    why_human: "`gh release list` and `gh run list --workflow=release.yml` both return EMPTY — the release pipeline has never been triggered and no release has ever been published. No .minisig artifact exists anywhere in the repo or dist/. The signing step is deliberately a human offline action (T-31-02: the secret key must never be a CI secret), so this end-to-end can only be closed by the operator."
---

# Phase 31: Packaging, Launcher & Signed-Release Pipeline Verification Report

**Phase Goal:** Turn the git+uv dev checkout into a self-contained, installable Windows distribution — a bundled Python runtime + app source (onedir), an unsigned Inno Setup installer, operator data physically separated from the swappable code, a stable launcher that can stop/swap/migrate/restart the app, and a repeatable GitHub Actions pipeline that publishes a signed release.
**Verified:** 2026-09-03T09:02:24Z
**Status:** human_needed
**Re-verification:** Yes — after gap closure (plans 31-06/07/08) plus a full code-review fix pass (15 findings). HEAD `8195e50`, `__version__` 1.60.

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 (PKG-01) | Bare Windows, no Python/uv/git: installer → launch → working localhost UI on the distribution's own bundled onedir runtime | ✓ VERIFIED (runtime half, proven against the real artifact) · ? HUMAN (installer + bare machine) | `launcher/__main__.py:176-201` `boot()` = `migrate(paths)` then `app_process.start()`, wired at `main():227` BEFORE the watch loop — the GAP-1 fix. Proven end-to-end, not by unit stub: `tests/test_packaging.py::test_assembled_dist_boots_against_empty_data_dir` starts the REAL `dist/app/python.exe` through `boot()` on an ephemeral port with an EMPTY `MYORISHOP_DATA_DIR`, polls `GET /` with its own helper (NOT `health_ok`, which would treat the 500 as alive), asserts status ∉ {500} and that `data/myorishop.db` was created. Re-run by this verifier: **PASSED**. `dist/app/python313._pth` = `python313.zip / . / app / Lib\site-packages / import site` (isolated, Pitfall-1 fixed). Archive `dist/MyOriShop-1.60.zip`: 2586 members, `python.exe` at ROOT, no `app/python.exe`, no `launcher/` member, 26 alembic versions, `minisign.pub` bundled. Installer compile + clean-VM run → human. |
| 2 (PKG-02) | Per-user %LOCALAPPDATA% install, Start-Menu shortcut + uninstaller, documented SmartScreen step | ✓ VERIFIED (script contract) · ? HUMAN (compile + install) | GAP-2 CLOSED at the artifact level. Generated `dist/MyOriShop.iss` (read verbatim): `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\MyOriShop`, `AppId={{1BF2D689-…}`, `AppVersion=1.60`, `UninstallDisplayIcon={app}\launcher\python.exe`, `[Icons] Name: "{autoprograms}\MyOriShop"; Filename: "{app}\launcher\python.exe"; Parameters: "-m launcher"; WorkingDir: "{app}"` on ONE line, `[Files]` ships `launcher\*` + `app\*` with `ignoreversion` but NOT `data\`, `[UninstallDelete]` sweeps `app.prev`/`app.failed`/`staged`. The target now EXISTS: `dist/launcher/python.exe` (105 840 bytes) + `dist/launcher/python313._pth` = `python313.zip / . / ..`. `test_iss_referenced_paths_exist_in_dist` parses the emitted script and existence-checks every `Source:`/`Filename:`/`UninstallDisplayIcon` path — PASSED; `test_real_launcher_runtime_resolves_the_sibling_package` PASSED (the shipped runtime imports the sibling `launcher` package). `docs/RELEASE.md` §3 carries the RU «Подробнее → Выполнить в любом случае». `iscc` absent here → human. |
| 3 (PKG-03) | Operator DB, .env, secret_key/device_id and backups/ are a SIBLING of the swappable app dir | ✓ VERIFIED | Fully code-verifiable, no machine dependency. `app/config.py:24` `_DATA_DIR = Path(os.environ.get("MYORISHOP_DATA_DIR", "data")).resolve()` roots `env_file` (:31), `db_path` (:34) and — the wipe-risk line — `backup_dir` (:86, ABSOLUTE); `secret_key`/`device_id` follow via `Path(self.db_path).parent` (:105-116). `launcher/adapters.py:43-46,90-92` set `MYORISHOP_DATA_DIR` to `install_root\data` for BOTH the uvicorn child and the alembic subprocess. `test_data_paths_are_siblings`, `test_backup_dir_is_absolute_not_cwd_relative`, `test_swap_of_app_dir_cannot_reach_data` PASS, and the real-boot test above independently created `data/` outside `app/`. |
| 4 (PKG-04) | Stable launcher OUTSIDE the swappable dir: stop → swap staged → `alembic upgrade head` → restart; a failed apply rolls back code + pre-update DB as a matched pair | ✓ VERIFIED · ? HUMAN (live post-fix re-run, see item 2) | The launcher now runs on its OWN embeddable runtime in `launcher\` (`build_release.assemble_launcher_runtime:262`), so it cannot lock the rename target. `launcher/swap.py apply_update`: pre-flight `if not Path(paths.staged).exists(): raise` BEFORE `stop_app` and before any rename (:122); `stop_app()` and BOTH `os.replace` calls now INSIDE the `try` (:142-155); `migrate()` strictly between the swap and `start_app` (:158-159); `except BaseException` rollback (:162) parks bad code at `app.failed`, restores `app.prev → app`, restores the DB only when `migrate_attempted AND stopped` (:206) with a RU stderr line otherwise, restarts, re-raises. Every directory rename clears its destination first (WinError 5). `launcher/__main__.py run_once` reads the marker INSIDE the guard, requires `pending.staged_dir == paths.staged`, and ALWAYS consumes the marker — `pending.failed.json` quarantine on every failure path (:128/139/144/165) — the GAP-3 fix. 29 launcher tests PASS on real `os.replace` over real dirs, incl. `test_two_ticks_with_one_failing_update_keep_app_dir`, `test_ctrl_c_mid_swap_rolls_back_and_quarantines_the_marker`, `test_rollback_skips_the_db_restore_when_the_app_could_not_be_stopped`, `test_apply_update_rotates_a_stale_app_prev`. The live happy-path + single rollback already PASSED in 31-UAT test 2. |
| 5 (PKG-05) | Tag → CI builds the distributable and publishes archive + SHA-256 + Ed25519 minisign signature over the signed manifest, from an OFFLINE key, verifying against the vendored pubkey | ✓ VERIFIED (every mechanism) · ? HUMAN (never run end-to-end) | Mechanisms proven on real artifacts: `dist/manifest.txt` = `version=1.60 / archive=MyOriShop-1.60.zip / sha256=72161b66…abc408e`, matching `dist/SHA256SUMS` and the real zip — `verify_manifest(1.60) → True`, `verify_manifest(wrong archive) → False` (run by this verifier). `assert_tag_matches_version('v1.60') → ok`, `'v1.59'` and `'1.60'` both rejected. `app/minisign.pub` PRESENT (115 B, `RWToyp3x…`), tracked by git; `git ls-files | grep '\.key$'` → empty; `.gitignore:52-53` blocks `*.key`. Both previously skip-gated tests now RUN green (`test_vendored_pubkey_present_and_bundled`, `test_minisign_roundtrip_verifies_and_tamper_fails`). `.github/workflows/ci.yml` `release-verify` job is GREEN in REAL CI (run 33699733177, job "minisign sign->verify round-trip + tamper-fail" ✓ 26s). `release.yml` = `on: push tags v1.*`, windows-2022, iscc + choco fallback, DRAFT-only, `github.token` and no repo secret. **But `gh release list` and `gh run list --workflow=release.yml` are both EMPTY and no `.minisig` exists** → the end-to-end has never happened. |

**Score:** 5/5 must-haves code-verified. Criteria 3 and 4 are fully achieved in the codebase; criteria 1, 2 and 5 have every code contract proven (several against real build artifacts) but retain a machine-level / offline-operator step that cannot be executed in this environment.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `launcher/__main__.py` | `boot()` migrate-then-start; `run_once` marker quarantine; console-holding abort | ✓ VERIFIED | 260 lines. `boot` :176, `_quarantine_marker` :59, `_hold_console` :204, `main` :223. Substantive, wired into `main()`. |
| `launcher/swap.py` | `apply_update` with staged pre-flight, guarded renames, proportional matched-pair rollback; `parse_pending` confinement | ✓ VERIFIED | 278 lines. Pure stdlib, imports no `app.*`. ASVS V12 `_confine` :264 rejects `..`, absolute, and escapes. |
| `launcher/adapters.py` | PID-owning start/stop, migrate subprocess, `health_ok(expected_version)`, `backup_restore` | ✓ VERIFIED | `AppProcess` owns the child (terminate → wait → kill); both subprocesses carry `MYORISHOP_DATA_DIR`. |
| `launcher/__init__.py` | package docstring incl. the not-field-updatable constraint (WR-11) | ✓ VERIFIED | Explicit: a launcher bug is permanent until a re-install; explains why `_zip_onedir` excludes `launcher\`. |
| `build_release.py` | onedir + launcher runtime + manifest/SHA-256 + tag↔version + .iss | ✓ VERIFIED | 600 lines. `assemble_launcher_runtime` :262 (second extraction of the SAME verified zip), `_zip_onedir` :514 roots the archive at `dist/app` (CR-01 fix), `generate_iss` :338 raises when `dest.parent != dist_dir` (WR-07). `EMBEDDABLE_SHA256` now PINS 3.13.1 with a stated, honest provenance note (WR-10) — no longer an empty gate. |
| `app/config.py` | `MYORISHOP_DATA_DIR`-rooted absolute data paths | ✓ VERIFIED | `_DATA_DIR` seam; `backup_dir` absolute; identity files follow `db_path.parent`. |
| `app/minisign.pub` | vendored Ed25519 public key | ✓ VERIFIED (was ABSENT at the prior verification) | Present, committed, `RW`-prefixed; bundled into the archive root by `VENDORED_APP_ASSETS`. |
| `.github/workflows/release.yml` | tag-triggered Windows build + DRAFT release, no secrets | ✓ VERIFIED (never executed) | Committed `63fbadf`. Referenced only `github.token`. |
| `.github/workflows/ci.yml` (`release-verify`) | installs minisign, runs the sign→verify→tamper round-trip | ✓ VERIFIED + PROVEN IN CI | Job green on run 33699733177. |
| `docs/RELEASE.md` | offline keygen + two-stage sign/publish runbook + RU SmartScreen | ✓ VERIFIED | 3 sections + threat table; §1 keygen, §2a/2b/2c build→sign→publish, §3 RU SmartScreen; WR-11 re-install callout added. |
| `.gitignore` | secret-key guard | ✓ VERIFIED | `*.key` + `minisign.key`; no `.key` file is tracked. |
| `tests/test_packaging.py` | PKG-01/02/03 gates + real-artifact first-boot + .iss path gate | ✓ VERIFIED | 14 substantive tests, all pass, 0 skipped (both real-artifact gates RAN). |
| `tests/test_launcher.py` | PKG-04 swap/rollback/quarantine/boot/console | ✓ VERIFIED | 29 substantive tests, all pass. |
| `tests/test_release_verify.py` | PKG-05 manifest/tamper/version + minisign + pubkey | ✓ VERIFIED | 5 tests, all pass, 0 skipped (minisign installed locally). |
| `31-UAT-STEPS.md` | operator re-run script for the UAT items | ✓ VERIFIED | Present (11 KB), produced by 31-08. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `launcher/__main__.main()` | `launcher.adapters.migrate` | `boot(paths, app_process)` before the watch loop | ✓ WIRED | `main():227`; a `CalledProcessError` propagates → RU stderr + `SystemExit(1)`, `start()` unreachable. |
| `launcher/__main__.run_once` | `data/pending.failed.json` | `os.replace` on every failure path | ✓ WIRED | 5 quarantine call sites (invalid marker, wrong staged_dir, missing staged, `BaseException`). |
| `launcher/swap.apply_update` | `paths.staged` | pre-flight existence check before `stop_app` | ✓ WIRED | `swap.py:122`, raises `FileNotFoundError` before any side effect. |
| `launcher/adapters.AppProcess` | `app\python.exe -m uvicorn` | `subprocess.Popen` with `cwd=app`, `MYORISHOP_DATA_DIR=install_root\data` | ✓ WIRED | Verified live by the real-boot test. |
| `build_release.generate_iss` | `dist/launcher/python.exe` | `[Icons] Filename` + `UninstallDisplayIcon` | ✓ WIRED | The file exists in `dist/`; a build-time test asserts every referenced path resolves. |
| `build_release.assemble_launcher_runtime` | the SHA-256-verified embeddable zip | second `zipfile.extractall` of the same artifact | ✓ WIRED | One verified download, two extractions; `_LAUNCHER_PTH_LINES` `..` makes the sibling package importable. |
| `build_release._zip_onedir` | `staged\` → `app\` swap contract | archive root == `dist/app` | ✓ WIRED | Verified on the real 1.60 zip: `python.exe` at root, no `app/` prefix, `launcher/` excluded. |
| `build_release.write_manifest` | `manifest.txt` + `SHA256SUMS` | `hashlib.sha256` over the real archive | ✓ WIRED | Round-trip re-verified by this verifier on the actual artifacts. |
| `release.yml` | `build_release.py` | `--version` then `--manifest` | ⚠️ WIRED BUT NEVER EXECUTED | No workflow run and no release exist. |
| `app/minisign.pub` | onedir bundle root | `VENDORED_APP_ASSETS` copy | ✓ WIRED | `minisign.pub` present at the archive root of `MyOriShop-1.60.zip`. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `dist/manifest.txt` | `sha256` | `hashlib.sha256(archive.read_bytes())` in `write_manifest` | Yes — `72161b66…abc408e` re-verified against the on-disk 27 MB zip | ✓ FLOWING |
| `dist/MyOriShop.iss` | `[Icons] Filename`, `[Files] Source` | `generate_iss(dist_dir, version)` | Yes — every referenced path resolves to a real file in `dist/` | ✓ FLOWING |
| `data/myorishop.db` on first run | schema | `boot()` → `adapters.migrate` → real `alembic upgrade head` subprocess | Yes — the real-boot test created a migrated DB from an empty dir and served a non-500 page | ✓ FLOWING |
| `dist/launcher/` | `python.exe` + launcher package + `._pth` | `assemble_launcher_runtime` | Yes — the shipped runtime resolved and imported the sibling package (`has boot: True`) | ✓ FLOWING |
| Published release assets | archive / SHA256SUMS / manifest.txt / .minisig | `release.yml` + offline Stage B | **No — nothing published; no `.minisig` exists** | ✗ DISCONNECTED (human step) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All Phase-31 tests green, nothing skipped | `uv run pytest tests/test_packaging.py tests/test_launcher.py tests/test_release_verify.py` | `48 passed in 20.64s` (0 skipped) | ✓ PASS |
| Real dist boots on an empty data dir (GAP-1) | `pytest ::test_assembled_dist_boots_against_empty_data_dir -v` | PASSED | ✓ PASS |
| Every .iss path ships (GAP-2) | `pytest ::test_iss_referenced_paths_exist_in_dist -v` | PASSED | ✓ PASS |
| Shipped launcher runtime imports the sibling package (GAP-2) | `pytest ::test_real_launcher_runtime_resolves_the_sibling_package -v` | PASSED | ✓ PASS |
| Two ticks, one failing update, app\ survives (GAP-3) | `pytest ::test_two_ticks_with_one_failing_update_keep_app_dir -v` | PASSED | ✓ PASS |
| Vendored pubkey + minisign round-trip | `pytest ::test_vendored_pubkey_present_and_bundled ::test_minisign_roundtrip_verifies_and_tamper_fails -v` | 2 PASSED (no skip) | ✓ PASS |
| Archive layout matches the swap contract (CR-01) | `zipfile` inspection of `dist/MyOriShop-1.60.zip` | root `python.exe` True; `app/python.exe` False; any `launcher/` False; 26 alembic versions; `minisign.pub` True | ✓ PASS |
| Manifest binds the real archive; tamper detected | `verify_manifest` on the real zip / a different zip | `True` / `False` | ✓ PASS |
| Tag↔version contract | `assert_tag_matches_version` v1.60 / v1.59 / 1.60 | ok / rejected / rejected | ✓ PASS |
| No secret key tracked | `git ls-files \| grep '\.key$'` | empty | ✓ PASS |
| CI release-verify job in real GitHub Actions | `gh run view 33699733177` | job ✓ green (26s) | ✓ PASS |
| Release pipeline ever run | `gh run list --workflow=release.yml`, `gh release list` | both EMPTY | ✗ NOT RUN → human item 3 |
| Installer ever compiled | `which iscc`, `ls "C:\Program Files (x86)\Inno Setup 6"` | not found; only a stale `dist/Output/MyOriShop-Setup-1.14.exe` from 2026-07-22 | ? SKIP → human item 1 |

### Probe Execution

No `scripts/*/tests/probe-*.sh` exist in this repository and no PLAN declares a probe. **Step 7c: SKIPPED (no probes defined for this project).** The equivalent runnable evidence is the behavioral spot-check table above, all of which this verifier executed directly.

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| PKG-01 | 31-01, 31-04, 31-06, 31-08 | Onedir bundled runtime + app source, no host Python | ✓ SATISFIED (code + real-artifact boot) / HUMAN (bare machine) | `assemble_onedir` + real-dist first-boot test PASSED |
| PKG-02 | 31-01, 31-04, 31-05, 31-08 | Per-user installer, shortcut, uninstaller, SmartScreen doc | ✓ SATISFIED (script + shipped target) / HUMAN (compile + install) | `generate_iss` + `test_iss_referenced_paths_exist_in_dist` + `docs/RELEASE.md` §3 |
| PKG-03 | 31-01, 31-02 | Operator data sibling of the swappable app dir | ✓ SATISFIED | `app/config.py` `_DATA_DIR` seam + 3 gates + live proof from the boot test |
| PKG-04 | 31-01, 31-03, 31-06, 31-07 | Stable launcher swap/migrate/restart + matched-pair rollback | ✓ SATISFIED | `swap.py` + `adapters.py` + 29 passing launcher tests + prior live UAT happy/rollback pass |
| PKG-05 | 31-01, 31-04, 31-05 | Tag pipeline builds + publishes archive + SHA-256 + minisign signature | ✓ SATISFIED (mechanism, CI-proven) / HUMAN (real run + offline sign) | manifest/SHA256/tag gates + green CI `release-verify` + vendored pubkey |

All five requirement IDs declared across the eight PLAN frontmatters (`31-01`..`31-08`) map to Phase 31 in `.planning/REQUIREMENTS.md` (lines 55-59), all marked `[x]`. **No orphaned requirements** — REQUIREMENTS.md maps exactly PKG-01..05 to Phase 31 and every one is claimed by at least one plan. No duplicates, no unclaimed IDs.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `launcher/*.py`, `build_release.py`, `app/config.py`, `docs/RELEASE.md`, `.github/workflows/release.yml` | — | No `TBD` / `FIXME` / `XXX` / `TODO` / `HACK` / `PLACEHOLDER` anywhere | ℹ️ Info | Debt-marker gate CLEAN — no unresolved markers in any file this phase touched |
| `build_release.py` | 71-80 | `EMBEDDABLE_SHA256` pins 3.13.1 with an explicit "this is a download-integrity pin, not a publisher attestation" note | ℹ️ Info | The prior verification flagged this as an empty gate that made every real build raise. It is now populated and the comment honestly states the residual weakness (self-computed SHA-256 seeded from python.org's MD5). Upgrade path documented. |
| `dist/launcher/__pycache__/` | — | Build residue that `[Files] Source: "launcher\*"; recursesubdirs` would package | ℹ️ Info | Cosmetic only. `assemble_launcher_runtime` copies with `ignore_patterns("__pycache__")`; the `.pyc` appears afterwards because the verifier/tests execute the shipped runtime in place. Shipping a stale `.pyc` is harmless (CPython revalidates by source mtime/size). Worth a `del /s` before `iscc` on a release build. |
| `tests/test_launcher.py` | 196, 251, 432 | Pre-existing ruff `B017` / `E501` / `UP031` from the 31-01 scaffold | ℹ️ Info | Logged in `deferred-items.md`; untouched by the gap plans on purpose. `ruff check launcher build_release.py tests/test_packaging.py` → All checks passed. |
| `launcher/` (whole package) | — | The launcher is not field-updatable (WR-11) | ⚠️ Warning (documented, deferred) | The swap replaces `app\` only and the `.iss` is the only writer of `launcher\`, so a launcher bug is permanent for every installed copy until a re-install. Documented in `launcher/__init__.py` and `docs/RELEASE.md`; the design change (two-subdir staged shape) is deliberately left as a milestone decision in `deferred-items.md`. Not a Phase-31 gap — the phase never promised a self-updating launcher. |
| `tests/test_sync_ui.py` | — | 3 failures in the full suite | ℹ️ Info — OUT OF SCOPE | Independently reproduced by this verifier in ISOLATION (`3 failed, 8 passed`). The response body is `Синхронизация уже выполняется` — `sync_client._run_lock` held by the lifespan auto-sync thread, the documented pre-existing failure set. Nothing in Phase 31 touches `sync_client`, the sync routes, or the lifespan. NOT counted against this phase. |

### Human Verification Required

Three items remain, all inherently machine-level or offline-operator. See the `human_verification` frontmatter for the full expected/why-human text.

1. **Compile the installer and run it on a bare Windows machine (PKG-01, PKG-02)** — `iscc` is not installed here, so no setup exe has ever been produced from the fixed `.iss`; SmartScreen, the Start-Menu click, the per-user uninstaller and the bare-machine condition are unobserved. The runtime half is already proven against the real 27 MB build.
2. **Live packaged failed-update, two consecutive ticks (PKG-04)** — the fix is unit-proven with real `os.replace`, but the original brick was found by a live run, so the post-fix live confirmation is the honest close-out. Fold into the VM session from item 1.
3. **Real signed-release pipeline run + offline signature (PKG-05)** — `gh release list` and `gh run list --workflow=release.yml` are both empty; no `.minisig` exists anywhere. The signing step is deliberately a human offline action (T-31-02).

**Closed since the prior verification:** the offline minisign keygen item — `app/minisign.pub` is present and committed, no `*.key` is tracked, `.gitignore` blocks them, and `test_vendored_pubkey_present_and_bundled` now RUNS green instead of skipping.

### Gaps Summary

**No blocking gaps.** All three UAT blockers the gap-closure plans targeted are closed in the codebase, and each is closed with a regression that would fail against the pre-fix code:

- **GAP-1** — `boot()` migrates before starting, wired into `main()`; proven not by a stub but by booting the REAL assembled distribution against an empty data dir and asserting `GET /` is not 500. This is the strongest single piece of evidence in the phase, because it reproduces the exact operator condition that failed.
- **GAP-2** — the Start-Menu shortcut and `UninstallDisplayIcon` now target `{app}\launcher\python.exe`, a file `assemble_launcher_runtime` actually ships, invoked with `-m launcher` on a `._pth` whose `..` entry makes the sibling package importable in isolated mode. A build-time test parses the emitted `.iss` and existence-checks every path it names, so the dead-target class of defect cannot recur silently.
- **GAP-3** — the marker is always consumed (quarantined to `pending.failed.json`), a missing `staged\` is refused before any side effect, both renames live inside the `BaseException`-keyed guarded region, every rename clears its destination first, and the DB restore is gated on `migrate_attempted AND stopped`. The two-tick regression passes.

The subsequent code review found three further blockers, of which **CR-01 was the most consequential and was verified here on a real artifact**: `MyOriShop-1.60.zip` now roots at the future `app\` (`python.exe` at the archive root, no `launcher/` member), so a Phase-32 self-update stages a runnable bundle instead of `app\app\python.exe`. All 15 review findings are fixed.

What remains is exactly what this environment cannot execute: `iscc` is not installed so the installer has never been compiled, no bare Windows machine is available, and the release pipeline has never been triggered against a real tag (zero workflow runs, zero releases, zero signature artifacts). These are operator/machine deliverables, not code defects — hence **human_needed**, not **gaps_found**.

---

_Verified: 2026-09-03T09:02:24Z_
_Verifier: Claude (gsd-verifier)_
