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
result: [pending]

### 2. Live launcher swap → migrate → restart + matched-pair rollback (PKG-04)
expected: On a packaged install, hand-place a staged\ dir + data\pending.json and watch the launcher stop the app, rename app→app.prev, rename staged→app, run alembic upgrade head, restart, and drop app.prev on success. Then inject a failing migration and watch the matched-pair rollback restore app.prev→app AND the pre-update DB (with -wal/-shm deleted).
result: [pending]

### 3. Offline minisign keygen + vendored public key (PKG-05)
expected: Operator runs `minisign -G` on the OFFLINE machine, stores minisign.key off-repo, commits ONLY app/minisign.pub (base64 line starts 'RW'); confirm the secret key is never committed (.gitignore blocks *.key). Once present, tests/test_release_verify.py::test_vendored_pubkey_present_and_bundled runs green (RW + bundled) instead of skipping.
result: [pending]

### 4. Real signed-release pipeline run (PKG-05)
expected: Pin a verified Python 3.13.x embeddable SHA-256 into EMBEDDABLE_SHA256, push a throwaway tag v1.<N> (with __version__ matching); confirm release.yml builds on the Windows runner and drafts a release with the archive + installer + SHA256SUMS + manifest.txt. Then sign manifest.txt with the OFFLINE key, attach manifest.txt.minisig, and Publish.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
