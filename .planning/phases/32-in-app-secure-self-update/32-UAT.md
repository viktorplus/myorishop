---
status: testing
phase: 32-in-app-secure-self-update
source: [32-VERIFICATION.md]
started: 2026-07-22T22:40:00Z
updated: 2026-07-22T22:40:00Z
---

## Current Test

number: 1
name: Two-release round-trip on a bare Windows box (install N, publish signed N+1, update)
expected: |
  The Настройки «Обновление приложения» notice appears with the new version + notes;
  clicking «Обновить и перезапустить» stages the update, the launcher swaps + migrates +
  restarts, the header chip then shows v(N+1), and the ledger/data is intact (matched-pair,
  nothing lost).
awaiting: user response

## Tests

### 1. Two-release round-trip on a bare Windows box
expected: Install release N, publish a signed release N+1 from the Phase-31 pipeline, launch the client. The Настройки «Обновление приложения» notice shows the new version + release notes; «Обновить и перезапустить» stages the update, the launcher swaps + migrates + restarts, the header chip then reads v(N+1), and all ledger/data is intact (matched-pair swap, nothing lost).
result: [pending]

### 2. Reject a downgrade offer and a tampered asset on real releases
expected: A release whose signed-manifest version is not strictly newer is NOT offered (up_to_date). A release whose archive SHA-256 or Ed25519 signature does not match the vendored app/minisign.pub aborts apply with «Обновление не прошло проверку подлинности…» and NOTHING is installed.
result: [pending]

### 3. Live launcher matched-pair rollback on a forced failure
expected: When migrate raises OR the swapped code serves the wrong version at GET /health, the launcher restores the previous app\ AND the pre-update DB backup together, restarts the old version, and the operator's data is unharmed.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
