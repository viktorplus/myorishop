---
status: complete
phase: 32-in-app-secure-self-update
source: [32-VERIFICATION.md]
started: 2026-07-22T22:40:00Z
updated: 2026-09-03T20:20:00Z
---

## Current Test

[testing complete]

## Test Rig

All three items were executed live on 2026-09-03 against a scratch install
assembled from the SHIPPED release artifacts, driven by the SHIPPED
`launcher\python.exe` and the SHIPPED `app\python.exe`.

| Piece | What was actually used |
|-------|------------------------|
| Install N | `dist/MyOriShop-1.60.zip` extracted to `<scratch>/install/app`, real `dist/launcher` alongside, empty `data\` — first boot ran the real `alembic upgrade head` (26 migrations) |
| Release N+1 | `dist/MyOriShop-1.61.zip` (27 376 048 B, `sha256=20f53a03e31177caa8fb2a20024ab54acac8efa465da77ff5d2c796abe91fa2e`), built by the real `build_release.py --version v1.61`; `manifest.txt` written by the real `write_manifest` |
| Signature | `manifest.txt.minisig` produced by the OPERATOR with the real `~/.minisign/minisign.key`; both manifests independently re-verified with `minisign -V -p app/minisign.pub` → "Signature and comment signature verified" |
| Trust anchor | the production vendored `app/minisign.pub` (`RWToyp3x…`), unmodified |
| Ports | app on **8061**; the operator's own instance on 8000 (PID 39100) was never touched |
| Scripts | `<scratch>/p32/{live_rig.py, stage6b.py, apply_driver.py}` |

Two transport-level substitutions, both outside the code under test:
1. the release JSON is handed to `update.apply()` directly instead of coming
   back from `api.github.com` (`apply(release=...)` is the shipped public seam);
2. `update._ALLOWED_ASSET_HOSTS` was widened at runtime to include `127.0.0.1`
   so the assets could be served from a local `http.server`.

Everything the phase is verified on ran untouched: Ed25519 manifest
verification against the vendored key, the trusted-version read, the integer
anti-downgrade compare, the SHA-256 archive check, the zip-slip-guarded unpack,
the `VACUUM INTO` backup, `pending.json`, the real `os.replace` swap, the real
`alembic upgrade head`, the real HTTP `/health` version-match probe and the real
matched-pair rollback.

**Totals: 63 live checks, 63 passed** (50 in `live_rig.py`, 13 in the
`stage6b.py` redo — see test 3 for why the redo exists).

## Tests

### 1. Two-release round-trip on a bare Windows box
expected: Install release N, publish a signed release N+1 from the Phase-31 pipeline, launch the client. The Настройки «Обновление приложения» notice shows the new version + release notes; «Обновить и перезапустить» stages the update, the launcher swaps + migrates + restarts, the header chip then reads v(N+1), and all ledger/data is intact (matched-pair swap, nothing lost).
result: pass
evidence: |
  Stage 1 — the 1.60 install booted: `boot()` ran 26 migrations, uvicorn came up
  on 8061, `GET /health` → `{"version": "1.60"}`, `GET /` → 303 → `/setup` 200.
  An operator ledger row was written before the update.
  Stage 2 — `check_for_update()` returned `state="available"`, `latest="1.61"`
  read from the SIGNED manifest, with the release notes carried through
  («Исправления и улучшения UAT-32.»).
  Stage 3 — `apply()` returned `state="staged"`, `staged_version="1.61"`;
  `staged\python.exe` present (real archive layout); `pending.json` carried
  exactly the 3 launcher keys with relative paths
  (`{"staged_dir": "staged", "expected_version": "1.61", "db_backup_path": "data/backups/myorishop-20260903-205421.db"}`);
  the pre-update VACUUM backup existed on disk.
  Stage 4 — `run_once()` drove the real swap: `GET /health` → `{"version": "1.61"}`,
  `app\app\__init__.py` on disk reads 1.61, `app.prev\` cleaned up,
  `pending.json` consumed, no quarantine marker, row counts identical before and
  after (`customers/products/operations/users` = 1/0/0/0), the pre-update ledger
  row still present, `GET /` still serves.
partial: |
  Two sub-conditions of the original wording were NOT reproduced and are
  recorded as acknowledged gaps, not as passes:
  (a) a bare Windows box — the run used a scratch install root on the dev
      machine, not a clean VM;
  (b) the release was served from a local HTTP server, not from a published
      GitHub release (the repo still has zero releases: `api.github.com/repos/
      viktorplus/myorishop/releases/latest` → 404). The Настройки panel itself
      was not clicked in a browser; the apply path was driven through the same
      service call the route makes.

### 2. Reject a downgrade offer and a tampered asset on real releases
expected: A release whose signed-manifest version is not strictly newer is NOT offered (up_to_date). A release whose archive SHA-256 or Ed25519 signature does not match the vendored app/minisign.pub aborts apply with «Обновление не прошло проверку подлинности…» and NOTHING is installed.
result: pass
evidence: |
  Against the installed 1.61, with releases signed by the REAL key:
  - a genuinely signed 1.59 release → `check_for_update()` = `up_to_date`
    (`latest=1.59`, not offered); `apply()` → `UpdateVerificationError`;
  - the 1.61 archive with ONE flipped byte (manifest sha256 no longer matches)
    → `apply()` → `UpdateVerificationError`;
  - the 1.61 manifest signature with ONE flipped base64 character
    → `apply()` → `UpdateVerificationError`.
  After every one of the three refusals: `staged\` was NOT created, no
  `pending.json` was written, and the app kept serving 1.61.
  Independently: `minisign -V -p app/minisign.pub` verified both untampered
  manifests, which also proves the vendored public key really is the
  counterpart of the operator's private key (previously unverified).
partial: |
  The tampered/older assets were served from `127.0.0.1`, not from
  `objects.githubusercontent.com`. The host allow-list itself was therefore
  relaxed for the run and is covered only by its unit test.

### 3. Live launcher matched-pair rollback on a forced failure
expected: When migrate raises OR the swapped code serves the wrong version at GET /health, the launcher restores the previous app\ AND the pre-update DB backup together, restarts the old version, and the operator's data is unharmed.
result: pass
evidence: |
  Both failure modes were forced on the live install, each with a real
  `VACUUM INTO` backup taken first and a real operator row written AFTER the
  backup so the DB half of the rollback is observable.

  (a) FAILED MIGRATION — a `9999_uat32_fail.py` revision was dropped into the
  staged `alembic\versions\`; `alembic upgrade head` exited non-zero
  (`CalledProcessError`), `app\` was restored to 1.61, the post-backup row was
  gone (DB reverted with the code), the original ledger row survived, and the
  app was serving again.

  (b) /health VERSION MISMATCH — the real 1.60 bundle was staged under a marker
  declaring `expected_version: "1.61"`. The swapped code STARTED and answered
  `/health` with `1.60`; `health_ok` polled for 43.2 s and returned False, so
  `apply_update` raised `RuntimeError: post-update health check failed`. The
  rollback then restored `app\` to 1.61, parked the wrong-version code in
  `app.failed\`, reverted the DB to the pre-update backup (post-backup row
  gone, original ledger row intact), quarantined the marker to
  `pending.failed.json`, restarted on 1.61, and the next tick was a no-op.
note: |
  The first attempt at (b) staged `MyOriShop-1.59.zip` and appeared to pass, but
  the failure was `FileNotFoundError [WinError 2]` from `start_app`, not the
  version match: that archive predates the layout fix and has `app/` + `launcher/`
  at its root instead of `python.exe`, so the swapped app never started. The
  check was disqualified and re-run as `stage6b.py` with the correctly-laid-out
  1.60 bundle, which is where the 43.2 s `/health` evidence above comes from.
  This is a stale build artifact in `dist\`, not a defect in the current code —
  1.60 and 1.61 both have the correct single-root layout.

## Summary

total: 3
passed: 3
issues: 0
pending: 0
skipped: 0
blocked: 0

## Acknowledged Gaps

Accepted rather than closed — recorded so nothing is silently claimed:

1. **Bare-Windows-VM install run.** The round trip used a scratch install root
   on the dev box, not a clean machine via `MyOriShop-Setup-1.61.exe`. Carried
   over from the identical Phase-31 gap.
2. **No published GitHub release.** The repo has zero releases, so
   `fetch_latest_release()` against the live `api.github.com` and the asset-host
   allow-list against `objects.githubusercontent.com` were not exercised
   end-to-end. Closing this needs a real tag push + the offline signing stage.
3. **The Настройки panel was not driven in a browser.** «Обновить и
   перезапустить» / «Позже» rendering and the HTMX swap are covered by
   `test_confirm_and_defer` and by the UI-SPEC review, not by a live click.

## Gaps

[none — no failures]
