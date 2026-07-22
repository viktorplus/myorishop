---
phase: 31-packaging-launcher-signed-release-pipeline
plan: 04
subsystem: build-tooling
tags: [packaging, embeddable-python, onedir, inno-setup, manifest, sha256, tag-version-contract]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    plan: 01
    provides: "tests/test_packaging.py PKG-01/02 + tests/test_release_verify.py PKG-05 (RED) — the acceptance contract this plan turns green"
  - phase: 31-packaging-launcher-signed-release-pipeline
    plan: 02
    provides: "MYORISHOP_DATA_DIR seam — the bundle ships NO data\\ (created on first run beside app\\)"
  - phase: 31-packaging-launcher-signed-release-pipeline
    plan: 03
    provides: "launcher/ package copied verbatim into <root>\\launcher (OUTSIDE the swappable app\\)"
provides:
  - "build_release.py — onedir assembler (embeddable + _pth + vendored wheels + app/alembic/launcher), manifest/SHA-256 writer, tag<->version assertion, per-user .iss generator"
  - "build CLI: `python build_release.py --version v1.<N>` (build) and `--manifest` (SHA256SUMS + manifest.txt)"
affects: [31-05 release pipeline, phase-32 self-update]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Injectable pure filesystem assembler: assemble_onedir(embeddable_zip, wheel_dir, dest, repo_root) so a synthetic zip + fake wheels unit-test the layout, while the network-bound fetch_embeddable stays separate"
    - "Parse app/__init__.py __version__ via ast without importing the app (no FastAPI/SQLAlchemy graph pulled) — the tag<->version single source of truth"
    - "Delete-partial-on-failure mirrored from backup.py for the onedir bundle, the zip, and the embeddable download"

key-files:
  created:
    - build_release.py
  modified:
    - .gitignore
    - app/__init__.py

key-decisions:
  - "assemble_onedir asserts bundled alembic migration count == repo count (dynamic), not a hardcoded 22 — the meaningful Pitfall-5 invariant (nothing dropped) survives a future 0023 migration without a build-script edit"
  - "fetch_embeddable refuses any Python version whose SHA-256 is not pinned in EMBEDDABLE_SHA256 (or passed explicitly) — no invented/unverified digest; the map is intentionally empty until an operator verifies against python.org (T-31-SC honest gate)"
  - "MyOriShop.iss [Files] Source paths are RELATIVE (launcher\\*, app\\*) because Inno's SourceDir defaults to the script dir (dist\\); the RESEARCH template's dist\\app\\* would double-resolve to dist\\dist\\app under `iscc dist\\MyOriShop.iss`"
  - "CLI vendors wheels into a staging dir (dist\\.wheels) BEFORE assemble_onedir, since assemble_onedir wipes dest\\ first — vendoring straight into dest\\Lib\\site-packages would be deleted"

patterns-established:
  - "Build SUT: build_release exports assemble_onedir / fetch_embeddable / vendor_wheels / write_manifest / verify_manifest / assert_tag_matches_version / generate_iss / VENDORED_APP_ASSETS — the single build entry point for Plan 05 CI + the installer"

requirements-completed: [PKG-01, PKG-02, PKG-05]

# Metrics
duration: 22min
completed: 2026-07-22
---

# Phase 31 Plan 04: build_release.py — Onedir Assembler + Signed Manifest + Installer Script Summary

**`build_release.py`, the single repeatable build SUT that turns the git+uv checkout into a self-contained Windows onedir (Python 3.13 embeddable runtime + a site-packages-enabled `python313._pth` + vendored wheels + app source + all 22 alembic migrations + the stable launcher), computes the release SHA-256 into a signable `manifest.txt`, enforces the `v1.<N>` tag ↔ `__version__` contract by parsing `app/__init__.py` without importing the app, and generates the per-user Inno Setup `MyOriShop.iss` — never a self-locking single-file exe.**

## Performance

- **Duration:** ~22 min
- **Started:** 2026-07-22
- **Completed:** 2026-07-22
- **Tasks:** 3
- **Files:** 1 created (`build_release.py`) + 2 modified (`.gitignore`, `app/__init__.py` version bumps)

## Accomplishments
- **PKG-01 onedir assembler** — `assemble_onedir(embeddable_zip, wheel_dir, dest, repo_root)` extracts the embeddable, overwrites `python313._pth` with the five-line site-packages-enabled search path (Pattern 1 / Pitfall 1), vendors the wheel dir into `Lib\site-packages`, copies `app/`, `alembic/` (incl. `versions/`), `alembic.ini` and optional `minisign.pub` verbatim into the bundle, and drops `launcher/` next to the bundle (OUTSIDE the swappable `app\`, Pitfall 3). Asserts every repo migration is bundled (Pitfall 5) and deletes a partial bundle on failure (backup.py idiom). `fetch_embeddable` (pinned download + SHA-256 verify, T-31-SC) and `vendor_wheels` (`uv export` + `pip install --target`, Pitfall 7) stay separate so the unit tests inject synthetic inputs.
- **PKG-05 manifest + contract** — `write_manifest` binds `version` + `archive` + the archive's real `hashlib.sha256` into `manifest.txt` (plus a `SHA256SUMS` sibling); `verify_manifest` re-hashes and returns False on a one-byte tamper (T-31-03); `assert_tag_matches_version` parses `__version__` via `ast` (no app import), validates the tag against `^v1\.\d+$` (V5) and rejects any drift (T-31-05). Wired into a `--version` / `--manifest` CLI that fails fast on drift.
- **PKG-02 installer script** — `generate_iss` emits the per-user `MyOriShop.iss`: `PrivilegesRequired=lowest`, `DefaultDirName={localappdata}\MyOriShop`, an `{autoprograms}` Start-Menu shortcut at the launcher, `UninstallDisplayIcon`, `AppVersion` synced to `__version__`, shipping `launcher\` + `app\` but never `data\` (PKG-03).
- **All PKG gates green** — `tests/test_packaging.py` + `tests/test_release_verify.py`: 9 passed, 2 skipped (minisign binary + `app/minisign.pub` absent on dev, both skip-gated by design).

## Task Commits

Each task was committed atomically:

1. **Task 1: Onedir assembler — embeddable + _pth + vendored wheels + app/alembic/launcher (PKG-01)** — `fd4772c` (feat)
2. **Task 2: Manifest + SHA-256 + tag<->version contract (PKG-05 build side)** — `a228287` (feat)
3. **Task 3: Generate per-user Inno Setup script MyOriShop.iss (PKG-02)** — `f7b49b1` (feat)

## Files Created/Modified
- `build_release.py` — the onedir assembler + manifest/SHA-256 writer + tag↔version assertion + `.iss` generator + build CLI (new)
- `.gitignore` — ignore `/dist/`, `requirements-locked.txt`, `.build-cache/` (regenerable build artifacts)
- `app/__init__.py` — version bumped 1.8 → 1.11 (per-task-commit convention)

## Decisions Made
- **Dynamic migration-count assertion** (bundled == repo count) instead of a literal `== 22`, so adding `0023_*.py` later does not silently break the build; the real Pitfall-5 invariant is "nothing dropped from the repo", which the dynamic check enforces.
- **No invented embeddable SHA-256** — `EMBEDDABLE_SHA256` is intentionally empty and `fetch_embeddable` raises a clear "verify against python.org and pin the digest" error rather than download an unpinned runtime (honest T-31-SC gate; the digest is filled in by whoever runs the real Windows build).
- **Relative `.iss` Source paths** (`launcher\*`, `app\*`) because Inno's `SourceDir` defaults to the script directory (`dist\`) — the RESEARCH template's `dist\app\*` would double-resolve when compiled with `iscc dist\MyOriShop.iss`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CLI vendored wheels into a dir that assemble_onedir then wiped**
- **Found during:** Task 2 (wiring the build CLI)
- **Issue:** The first draft vendored wheels straight into `dist/app/Lib/site-packages`, but `assemble_onedir` starts by `shutil.rmtree(dest)` — so the freshly vendored wheels would be deleted before assembly, producing an empty `site-packages`.
- **Fix:** Vendor into a staging dir (`dist/.wheels`) first, then pass it as `wheel_dir` to `assemble_onedir`.
- **Files modified:** `build_release.py`
- **Commit:** `a228287`

**2. [Rule 1 - Bug] RESEARCH .iss Source paths would double-resolve under iscc**
- **Found during:** Task 3
- **Issue:** The RESEARCH Pattern 2 template uses `Source: "dist\app\*"`, but the generated `.iss` lives in `dist\` and Inno's `SourceDir` defaults to the script dir, so `dist\app\*` resolves to `dist\dist\app` at compile time.
- **Fix:** Emit relative Source paths (`launcher\*`, `app\*`) with a comment documenting the `SourceDir` default.
- **Files modified:** `build_release.py`
- **Commit:** `f7b49b1`

(The `app/__init__.py` version bumps follow the established project per-task-commit versioning convention, not a plan deviation.)

## Issues Encountered
- Full suite (excluding the 4 documented pre-existing `tests/test_sync_ui.py` isolation failures, which are OUT OF SCOPE per the plan brief): **1178 passed / 14 skipped / 0 failed** in ~377s. Zero regressions attributable to this plan. The 2 skips inside the PKG files are the intentional minisign-binary / `app/minisign.pub`-absent skip gates.

## Known Stubs
- `fetch_embeddable` / `vendor_wheels` are the network- and Windows-native halves that are exercised only by the real CI build (Plan 05), not by unit tests — by design (Nyquist: the pure `assemble_onedir` is unit-tested with injected inputs). `EMBEDDABLE_SHA256` is intentionally unpinned until an operator verifies a specific Python 3.13.x embeddable digest against python.org; the build raises rather than proceed unpinned. This is a documented supply-chain gate (T-31-SC), not an accidental stub.

## User Setup Required
None for the tests. For a real release build (Plan 05, on a Windows runner): pin the verified Python 3.13.x embeddable SHA-256 into `EMBEDDABLE_SHA256` (or pass `expected_sha256=`), and have Inno Setup (`iscc.exe`) available (`choco install innosetup` on windows-2025). The offline `app/minisign.pub` is supplied by the operator (`minisign -G`) — still absent on dev, keeping the vendored-pubkey test skip-gated.

## Next Phase Readiness
- Plan 05 (release pipeline) has its single build SUT: `python build_release.py --version v1.<N>` (build → onedir + zip + `.iss`) and `--manifest` (SHA256SUMS + `manifest.txt`); the offline human signs `manifest.txt` and attaches the `.minisig`.
- Phase 32 self-update verifies against the `manifest.txt` this plan writes and the `minisign.pub` `build_release` bundles (once vendored).
- No blockers.

## Self-Check: PASSED

- `build_release.py` and `31-04-SUMMARY.md` exist on disk.
- All three task commits (`fd4772c`, `a228287`, `f7b49b1`) present in git history.
- PKG-01/02/05 gates green: `tests/test_packaging.py` + `tests/test_release_verify.py` → 9 passed, 2 skipped (skip-gated by design).

---
*Phase: 31-packaging-launcher-signed-release-pipeline*
*Completed: 2026-07-22*
