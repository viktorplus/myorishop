---
phase: 32-in-app-secure-self-update
plan: 03
subsystem: self-update
tags: [security, ed25519, minisign, update, offline-safe]
requires: [32-01, 32-02]
provides:
  - "app/services/minisign_verify.py: verify_minisign + sha256_matches"
  - "app/services/update.py: UpdateStatus interface + check_for_update (read half)"
affects: [32-04, 32-05]
tech-stack:
  added: ["cryptography.ed25519 (Ed25519PublicKey.verify)"]
  patterns: ["dialect no-op gate (backup.startup_backup)", "offline-safe httpx (sync_client)", "verify-before-trust", "integer 1.<N> anti-downgrade compare"]
key-files:
  created:
    - app/services/minisign_verify.py
    - app/services/update.py
  modified: []
decisions:
  - "Trusted version read from signature-verified manifest version= field, never git tag_name (T-32-04)"
  - "verified_manifest_version() factored as a monkeypatchable seam so the check tests mock download+verify"
  - "__version__ left at 1.15 (not bumped): the plan's tests pin 1.15 as the compare baseline; bumping to 1.16 would flip test_check_detects_newer to up_to_date"
  - "Any verify/download failure => state 'error' (non-offering); fetch None => 'offline'; both non-raising"
metrics:
  duration: "~20m"
  completed: 2026-07-22
---

# Phase 32 Plan 03: Update Check Service + Ed25519 Verifier Summary

Built the two read-side security primitives of the self-update feature: a pure-Python minisign/Ed25519 verifier (Ed25519 math delegated to `cryptography`) and the `check_for_update` half that offers a release only when its signature-verified manifest carries a strictly-newer integer version — silent no-op offline and on PostgreSQL.

## What Was Built

### Task 1 — `app/services/minisign_verify.py` (commit 3c1d4d1)
- `verify_minisign(manifest_bytes, sig_text, pubkey_text) -> bool`: parses the minisign envelope (`_parse_pubkey` takes the last non-empty pubkey line; `.minisig` line 2 → `alg||key_id[8]||sig[64]`), rejects a key-id mismatch, is algorithm-agnostic (`Ed` raw message vs `ED` BLAKE2b-512 prehashed), and delegates the Ed25519 verify to `cryptography`. Any `InvalidSignature`/parse error returns `False` (never raises).
- `sha256_matches(archive_path, expected_hex) -> bool`: mirrors `build_release.verify_manifest` — re-hash the archive bytes, compare hex.

### Task 2 — `app/services/update.py` (commit 332b5c4)
- `@dataclass(frozen=True) UpdateStatus`: `state` (`available|up_to_date|offline|noop|error`), `current`, `latest`, `notes`, `tag`, `assets` — the interface Waves 04/05 consume.
- `fetch_latest_release() -> dict | None`: GitHub `/releases/latest` with a `User-Agent`; `httpx.HTTPError` → `None` (offline no-op).
- `verified_manifest_version(release) -> tuple[str, str] | None`: locates `manifest.txt` + `.minisig` by asset name, enforces the `_ALLOWED_ASSET_HOSTS` allowlist (V5), downloads both, and reads `version=` **only after** `verify_minisign` returns True (validated against `^1\.\d+$`).
- `check_for_update(engine=None) -> UpdateStatus`: dialect gate FIRST (non-sqlite → `noop`, no fetch), fetch `None` → `offline`, malformed tag → `error`, else trusts the verified manifest version; whole body broad-guarded so it never raises. Caches into `_LAST_CHECK`.
- `is_strictly_newer(remote, local)`: integer counter compare on `"1.<N>"` (9→10 boundary), malformed → `False`.
- `get_cached_status() -> UpdateStatus | None`: returns `_LAST_CHECK` (startup check in Plan 05 populates it).

## Interface for Downstream Waves

- Verifier: `verify_minisign(bytes, str, str) -> bool`, `sha256_matches(path, hex) -> bool`.
- `UpdateStatus(state, current, latest=None, notes=None, tag=None, assets=None)` — `assets` is `{asset_name: browser_download_url}` so Plan 04's apply reuses the archive/manifest/sig URLs.
- `check_for_update`, `get_cached_status`, `verified_manifest_version`, `fetch_latest_release`, `is_strictly_newer`.

## Verification

- `tests/test_update.py::test_minisign_pure_python_verify` GREEN (minisign binary present — real signature verifies, tampered rejected).
- `tests/test_update.py::test_verify_gate` GREEN (sha256_matches True/False across a flipped byte).
- `tests/test_update.py::test_check_detects_newer` / `test_server_noop` / `test_anti_downgrade` GREEN.
- `uv run ruff check` on both files passes.
- Full suite: 1192 passed, 13 skipped, 8 failed — all 8 are expected/out-of-scope (see below). Zero regressions from this plan.

## Deviations from Plan

None — plan executed as written. Note recorded (not a deviation): `__version__` deliberately NOT bumped from 1.15, because the plan's tests pin 1.15 as the anti-downgrade baseline and `app/__init__.py` is outside this plan's `files_modified`.

## Still-RED / Out-of-Scope Failures (not regressions)

- `tests/test_update.py::test_confirm_and_defer`, `::test_manual_check` — Wave 5 routes (`/settings/update/*`), 404 until Plan 05.
- `tests/test_launcher.py::test_apply_rolls_back`, `::test_run_once_applies_app_written_marker` — Wave 4 apply/rollback anchor, RED until Plan 04.
- `tests/test_sync_ui.py` (4 tests) — pre-existing known failures (`sync_client._run_lock` held by lifespan auto-sync thread), unrelated to this plan.

## Known Stubs

None. `_PUBKEY_PATH` (`app/minisign.pub`) is vendored by Plan 02's human-verify checkpoint; its absence during this plan is harmless because the check tests mock `verified_manifest_version` (the only reader of the pubkey).

## Self-Check: PASSED
- FOUND: app/services/minisign_verify.py
- FOUND: app/services/update.py
- FOUND commit: 3c1d4d1 (Task 1)
- FOUND commit: 332b5c4 (Task 2)
