---
phase: 31-packaging-launcher-signed-release-pipeline
plan: 05
subsystem: release-pipeline
tags: [packaging, github-actions, minisign, offline-signing, inno-setup, smartscreen, draft-release]

# Dependency graph
requires:
  - phase: 31-packaging-launcher-signed-release-pipeline
    plan: 04
    provides: "build_release.py --version (onedir + zip + .iss) and --manifest (SHA256SUMS + manifest.txt); tag<->__version__ contract"
  - phase: 31-packaging-launcher-signed-release-pipeline
    plan: 01
    provides: "tests/test_release_verify.py PKG-05 contract (manifest/tamper/version always-run + skip-gated minisign round-trip + vendored-pubkey)"
provides:
  - ".github/workflows/release.yml — tag-triggered (v1.*) Windows build + DRAFT release (archive + installer + SHA256SUMS + manifest.txt), no repo secrets (Stage A)"
  - "docs/RELEASE.md — offline minisign -G keygen + per-release two-stage sign/attach/publish runbook + RU SmartScreen operator step"
  - ".github/workflows/ci.yml release-verify job — installs minisign so the sign->verify + tamper-fail round-trip runs (not skips) in CI"
  - ".gitignore secret-key guard (*.key / minisign.key) so the offline minisign secret can never be committed"
affects: [phase-32 self-update]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-stage release: CI builds + DRAFTS (no secrets); a human signs manifest.txt offline and publishes — the minisign secret key never enters GitHub Actions (T-31-02)"
    - "workflow_dispatch version input as a dry-run path alongside the v1.* tag trigger, both re-asserting the tag<->__version__ contract via build_release --manifest"
    - "Separate ubuntu-latest release-verify job leaves the pg-parity job untouched; apt-installed minisign flips the skip-gated round-trip test to RUN"

key-files:
  created:
    - .github/workflows/release.yml
    - docs/RELEASE.md
  modified:
    - .github/workflows/ci.yml
    - .gitignore
    - app/__init__.py

key-decisions:
  - "release.yml uses the automatic github.token (permissions: contents: write) for the draft — never a configured repo secret, honoring PKG-05's no-secrets Stage A"
  - "windows-2022 runner (Inno Setup preinstalled) with a Test-Path guard + choco install innosetup fallback for windows-2025 image drift (Pitfall 6)"
  - "release-verify added as a NEW ci.yml job (not a step in pg-parity) so the PostgreSQL service/steps are provably untouched; minisign installed via apt on ubuntu-latest"
  - "This auto plan does NOT generate app/minisign.pub — the operator supplies it offline via minisign -G (T-31-02); the task only guards the secret filename in .gitignore and RW-checks the pubkey if already present"

requirements-completed: [PKG-02, PKG-05]

# Metrics
duration: 16min
completed: 2026-07-22
---

# Phase 31 Plan 05: Signed-Release Pipeline + Offline-Sign Runbook Summary

**A tag-triggered GitHub Actions workflow that builds the MyOriShop distributable on a Windows runner and publishes a DRAFT release (archive + installer + SHA256SUMS + manifest.txt) with NO repo secrets, plus the offline-signing runbook that reconciles "the pipeline publishes a signature" with "the secret key is OFFLINE" via a two-stage build-in-CI / sign-offline-attach flow, the RU SmartScreen operator doc, a `.gitignore` guard so the minisign secret key can never be committed, and a CI `release-verify` job that installs minisign so the sign→verify + tamper-fail round-trip runs green.**

## Performance

- **Duration:** ~16 min
- **Started:** 2026-07-22
- **Completed:** 2026-07-22
- **Tasks:** 3
- **Files:** 2 created (`.github/workflows/release.yml`, `docs/RELEASE.md`) + 3 modified (`.github/workflows/ci.yml`, `.gitignore`, `app/__init__.py`)

## Accomplishments
- **PKG-05 Stage A pipeline** — `.github/workflows/release.yml` triggers on `push: tags: ['v1.*']` (plus a `workflow_dispatch` dry run with a `version` input), runs on `windows-2022`, and mirrors `ci.yml` conventions (`actions/checkout@v4`, `astral-sh/setup-uv@v5`, `uv sync --dev`). It runs `build_release.py --version` (Windows-native wheels — Pitfall 7) to assemble the onedir + zip + `MyOriShop.iss`, guards Inno Setup presence with a `Test-Path` + `choco install innosetup` fallback (Pitfall 6), compiles the installer with `iscc.exe`, runs `--manifest` to write `SHA256SUMS` + `manifest.txt` and re-assert the tag↔`__version__` contract, then publishes a **DRAFT** release via `softprops/action-gh-release@v2` (`draft: true`) uploading the archive, installer, `SHA256SUMS` and `manifest.txt`. A top comment and the `permissions: contents: write` (automatic `github.token`, no configured secret) document that the minisign secret key never enters CI (T-31-02).
- **PKG-05 / PKG-02 runbook** — `docs/RELEASE.md`: Section 1 one-time offline `minisign -G` keygen (HUMAN — secret stored off-repo, only `app/minisign.pub` committed); Section 2 per-release two-stage flow (push tag → CI draft → offline `minisign -S -m manifest.txt` → attach `.minisig` → Publish), explaining WHY the small manifest is signed (binds version + archive SHA-256, fast Phase-32 verify); Section 3 the RU SmartScreen «Подробнее → Выполнить в любом случае» operator step with the cert-deferred note. Threats T-31-01/02/03 cited.
- **PKG-05 secret-key guard** — `.gitignore` now blocks `*.key` / `minisign.key` so the offline minisign secret can never be committed (T-31-02). This plan does NOT generate or fabricate `app/minisign.pub` — it is operator-supplied offline; the automated guard confirms an `RW` base64 line only IF the key is already present.
- **PKG-05 CI verify proof** — a new `release-verify` job in `.github/workflows/ci.yml` (ubuntu-latest) installs minisign via apt and runs `tests/test_release_verify.py -x`, so the sign→verify round-trip and tamper-fail (T-31-03) execute in CI instead of self-skipping. The existing `pg-parity` job is untouched.

## Task Commits

Each task was committed atomically:

1. **Task 1: Tag-triggered build + draft release workflow (PKG-05 Stage A, PKG-02)** — `63fbadf` (feat)
2. **Task 2: Offline-sign runbook + SmartScreen doc + secret-key .gitignore guard (PKG-05, PKG-02)** — `41a4e7d` (docs)
3. **Task 3: Prove minisign verify in CI — sign→verify round-trip + tamper-fail (PKG-05)** — `60ca2a6` (ci)

## Files Created/Modified
- `.github/workflows/release.yml` — tag-triggered Windows build + DRAFT release, no repo secrets (new)
- `docs/RELEASE.md` — offline keygen + two-stage sign/attach/publish runbook + RU SmartScreen doc (new)
- `.github/workflows/ci.yml` — added `release-verify` job (minisign install + release-verify test); pg-parity untouched
- `.gitignore` — blocks `*.key` / `minisign.key` (minisign secret-key guard, T-31-02)
- `app/__init__.py` — version bumped 1.11 → 1.14 (per-task-commit convention)

## Decisions Made
- **Automatic `github.token`, not a repo secret** — `release.yml` sets `permissions: contents: write` and lets `softprops/action-gh-release@v2` use the built-in token; nothing under `secrets.` is referenced, honoring PKG-05's "no repo secrets for Stage A".
- **`windows-2022` + choco guard** — the runner has Inno Setup preinstalled (Pitfall 6); a `Test-Path` check installs `innosetup` via Chocolatey only if `iscc.exe` is missing, so a windows-2025 image drift does not break the build.
- **`release-verify` as a separate job** — added a new ubuntu-latest job rather than a step inside pg-parity, so the PostgreSQL service/steps are provably untouched; minisign installed via `apt-get` (available in Ubuntu universe on the runner).
- **No fabricated public key** — the plan's `auto` scope explicitly excludes generating `app/minisign.pub`; the secret key must never leave the operator's offline machine (T-31-02), so this plan only documents the HUMAN keygen and guards the secret filename.

## Deviations from Plan

None — plan executed exactly as written. (The `app/__init__.py` version bumps follow the established project per-task-commit versioning convention, not a plan deviation.)

## Issues Encountered
- Full suite: **1185 passed / 14 skipped / 4 failed** in ~317s. The 4 failures are exclusively the documented pre-existing `tests/test_sync_ui.py` isolation failures (`sync_client._run_lock` held by the lifespan auto-sync thread) called out as OUT OF SCOPE in the plan brief — not a regression from this plan. Zero regressions attributable to Plan 05. The 2 skips inside `tests/test_release_verify.py` are the intentional minisign-binary-absent and `app/minisign.pub`-absent skip gates on the dev box.

## Known Stubs
- None introduced by this plan. `app/minisign.pub` is intentionally absent on dev/CI — it is an OFFLINE operator deliverable (`minisign -G`, T-31-02), not a stub; its absence keeps `test_vendored_pubkey_present_and_bundled` skip-gated by design, and `release.yml`/`ci.yml` install/consume minisign only where the real pipeline runs.

## User Setup Required
Per the plan's `user_setup` block (HUMAN, offline — deferred to end-of-phase `<human-check>`):
- One-time: run `minisign -G` on the offline machine, store `minisign.key` OFF-repo (never committed, never a CI secret), commit ONLY `app/minisign.pub`. Once present, `tests/test_release_verify.py::test_vendored_pubkey_present_and_bundled` runs green (RW + bundled) instead of skipping.
- Per release: download `manifest.txt` from the draft, run `minisign -S -m manifest.txt -t "MyOriShop 1.<N>"`, attach `manifest.txt.minisig` to the draft, then Publish.
- For a real Windows CI build: pin the verified Python 3.13.x embeddable SHA-256 into `EMBEDDABLE_SHA256` (Plan 04 gate, T-31-SC).

## Next Phase Readiness
- Phase 32 (self-update) verifies against the `manifest.txt` `release.yml` publishes and the `app/minisign.pub` `build_release` bundles (once the operator vendors it) using the same minisign `-Vm` primitive the CI `release-verify` job now exercises.
- No blockers.

## Self-Check: PASSED

- `.github/workflows/release.yml`, `docs/RELEASE.md`, and `31-05-SUMMARY.md` exist on disk.
- All three task commits (`63fbadf`, `41a4e7d`, `60ca2a6`) present in git history.
- PKG-05 verify contract green: `tests/test_release_verify.py` → 3 passed, 2 skipped (skip-gated by design).

---
*Phase: 31-packaging-launcher-signed-release-pipeline*
*Completed: 2026-07-22*
