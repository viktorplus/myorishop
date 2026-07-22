---
phase: 32-in-app-secure-self-update
plan: 04
subsystem: self-update
tags: [security, ed25519, update, zip-slip, rollback, health-check]
requires: [32-03]
provides:
  - "app/services/update.py: apply() verify-before-unpack gate + stage_pending (write half)"
  - "app/routes/health.py: public GET /health -> {version, status}"
  - "launcher/adapters.py: health_ok(expected_version=...) version-match probe"
affects: [32-05]
tech-stack:
  added: []
  patterns: ["verify-before-unpack hard gate", "zip-slip confinement (is_relative_to)", "matched-pair rollback via launcher marker", "version-match health probe"]
key-files:
  created:
    - app/routes/health.py
  modified:
    - app/services/update.py
    - app/main.py
    - app/services/security.py
    - launcher/adapters.py
    - launcher/__main__.py
decisions:
  - "apply() RAISES UpdateVerificationError on a failed gate (per the RED test_verify_gate contract), rather than returning ApplyResult(state='verification_failed') as the plan sketch suggested — an aborting raise is a cleaner never-partial-stage guarantee"
  - "apply(release: dict | None) takes the GitHub release dict (or None => fetch fresh) — matches how test_verify_gate calls it and lets Plan 05 re-verify from scratch at apply time"
  - "verify_release() consolidates the whole gate (manifest download + Ed25519 + version/anti-downgrade + archive download + sha256) as a single monkeypatchable seam, so the gate short-circuits before any real download in tests"
  - "__version__ left at 1.15 (not bumped): test_check_detects_newer pins 1.16 as the newer release; bumping would flip it to up_to_date. app/__init__.py is outside this plan's files_modified"
  - "health_ok(expected_version=None) keeps the legacy any-status 'alive' behaviour for the Phase-31 hand-placed-marker path; a set version polls /health and requires an exact match"
metrics:
  duration: "~25m"
  completed: 2026-07-22
---

# Phase 32 Plan 04: Verify-Before-Unpack Apply + Version-Match Health Summary

Built the WRITE half of the self-update feature: `update.apply` is a verify-before-unpack hard gate that authenticates a release (Ed25519 signature AND archive SHA-256 against the signed manifest, plus an anti-downgrade re-check) BEFORE any extraction, zip-slip-guards the unpack into `install_root/staged`, takes a pre-update VACUUM INTO backup, and writes a launcher-valid `pending.json`. A new public `GET /health` returns the installed version so the launcher's strengthened `health_ok` confirms the swap actually served the new code.

## What Was Built

### Task 1 — `app/services/update.py` apply half (commit 19cac4e)
- `verify_release(release, dest_dir) -> tuple[str, Path] | None`: the HARD GATE in RESEARCH order — (a) Ed25519-verify `manifest.txt` against the vendored `app/minisign.pub`; (b) read the trusted `version=`/`sha256=` from the *verified* manifest; (c) re-assert `^1\.\d+$` shape + `is_strictly_newer` anti-downgrade (UPD-05); (d) only then download the archive and confirm its SHA-256. Re-asserts the V5 asset-host allowlist on every URL. Returns None on ANY failure.
- `_extract_guarded(zip_path, staged_dir)`: resolves every zip member under `staged_dir` and raises `ValueError` on any escape BEFORE `extractall` (T-32-05 zip-slip).
- `stage_pending(install_root, staged_rel, version, backup_rel)`: writes `install_root/data/pending.json` with EXACTLY the 3 keys `{staged_dir, expected_version, db_backup_path}`, relative paths only, so the shipped `launcher.swap.parse_pending` accepts it (T-32-06).
- `apply(release=None, *, engine=None, install_root=None) -> ApplyResult`: dialect gate (non-sqlite → `noop`, no download, UPD-06) → resolve release (None → fetch; still None → `error`) → `verify_release` gate (fail → **raise** `UpdateVerificationError`, nothing staged) → clean prior `staged/` → `_extract_guarded` → reuse shipped `backup.create_backup` VACUUM INTO into the absolute sibling `settings.backup_dir` → `stage_pending`. Returns `ApplyResult(state="staged", staged_version=...)`. The app never self-kills.
- `ApplyResult` frozen dataclass (`state` in `staged|noop|error`) + `UpdateVerificationError`.

### Task 2 — public /health + launcher version-match (commit ace31b1)
- `app/routes/health.py`: `router` with public `GET /health -> {"version": APP_VERSION, "status": "ok"}` (imports `app.__version__`, no auth/session/DB).
- `app/main.py`: `app.include_router(health.router)` with no `dependencies=`.
- `app/services/security.py`: `/health` added to `PUBLIC_PATHS` (anonymous launcher probe gets 200, not a 303 to /login).
- `launcher/adapters.py`: `health_ok(timeout, interval, expected_version=None)` — `None` keeps legacy any-status-on-`/` alive; a set version polls `GET /health`, returns True only on 200 AND `body["version"] == expected_version`; False on refused/non-200/parse-error/mismatch. Stdlib-only (`http.client` + `json`), no `app.*` import.
- `launcher/__main__.py`: `run_once` binds `health_ok=lambda: health_ok(expected_version=pending.expected_version)` so a stale/wrong swap fails the check and fires the shipped matched-pair rollback.

## Interface for Plan 05 (UI wave)
- `update.apply(release: dict | None = None, *, engine=None, install_root=None) -> ApplyResult` — raises `UpdateVerificationError` on a failed gate; returns `ApplyResult(state="staged"|"noop"|"error", staged_version, message)`.
- `update.stage_pending(install_root, staged_rel, version, backup_rel) -> None`.
- `update.ApplyResult`, `update.UpdateVerificationError`, `update.verify_release`.
- `GET /health -> {"version": <__version__>, "status": "ok"}` (public).

## Verification
- `tests/test_update.py::test_verify_gate` GREEN — a failed gate aborts `apply` with nothing in `staged/`.
- `tests/test_launcher.py::test_run_once_applies_app_written_marker`, `::test_apply_rolls_back`, `::test_health_ok_requires_version_match` GREEN; all pre-existing swap/rollback/parse_pending tests stay GREEN.
- Anonymous `GET /health` returns 200 `{"version":"1.15","status":"ok"}` (proves PUBLIC_PATHS).
- `uv run ruff check` on all five touched files passes; `grep "import app"` in the launcher returns nothing.
- Full suite: **1194 passed, 13 skipped, 6 failed** — all 6 expected/out-of-scope (below). Zero regressions.

## Deviations from Plan
- **[Contract alignment] `apply` raises instead of returning `ApplyResult(state="verification_failed")`.** The RED `test_verify_gate` asserts `pytest.raises(Exception)` on a failed gate, so the aborting `UpdateVerificationError` raise is the authoritative behaviour. The plan's `"verification_failed"` return state is therefore not produced; `ApplyResult` carries `staged|noop|error`. No user impact — an aborting raise is a stronger never-partial-stage guarantee.
- **[Signature] `apply(release: dict | None)` not `apply(status: UpdateStatus)`.** The test passes a raw GitHub release dict; `apply` re-verifies from scratch (re-download + re-verify) which is the more secure apply-time posture the RESEARCH mandates.

## Still-RED / Out-of-Scope Failures (not regressions)
- `tests/test_update.py::test_confirm_and_defer`, `::test_manual_check` — Wave 5 `/settings/update/*` routes, 404 until Plan 05.
- `tests/test_sync_ui.py` (4 tests) — pre-existing known failures (`sync_client._run_lock` held by the lifespan auto-sync thread), unrelated to this plan.

## Known Stubs
None. `app/minisign.pub` is vendored by Plan 02's human-verify checkpoint; its absence during this plan is harmless because `test_verify_gate` monkeypatches `verify_release` (the only reader of the pubkey in the apply path).

## Threat Flags
None — the new surface (`GET /health`) is a version/liveness probe carrying no secret and is covered by the plan's threat model.

## Self-Check: PASSED
- FOUND: app/services/update.py
- FOUND: app/routes/health.py
- FOUND commit: 19cac4e (Task 1)
- FOUND commit: ace31b1 (Task 2)
