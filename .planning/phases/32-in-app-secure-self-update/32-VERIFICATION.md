---
phase: 32-in-app-secure-self-update
verified: 2026-07-22T22:30:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Two-release round-trip on a bare Windows box: install release N, publish a signed release N+1, launch the client"
    expected: "The Настройки «Обновление приложения» notice appears with the new version + notes; clicking «Обновить и перезапустить» stages the update, the launcher swaps + migrates + restarts, the header chip then shows v(N+1), and the ledger/data is intact (matched-pair, nothing lost)."
    why_human: "Requires two REAL signed GitHub releases from the Phase-31 pipeline and a packaged launcher parent process; the end-to-end swap/migrate/restart cannot run inside pytest (verified only via fake-callback unit tests + monkeypatched seams)."
  - test: "Reject a downgrade offer and a checksum/signature-tampered asset on real releases"
    expected: "A release whose signed-manifest version is not strictly newer is NOT offered (up_to_date); a release whose archive SHA-256 or Ed25519 signature does not match the vendored app/minisign.pub aborts apply with «Обновление не прошло проверку подлинности…» and NOTHING is installed."
    why_human: "Needs a genuinely tampered/older signed release served from github.com; unit tests prove the gate logic with synthetic fixtures but cannot exercise a real GitHub-hosted tampered asset."
  - test: "Live launcher matched-pair rollback on a forced failure (bad migration or failed post-swap /health version match)"
    expected: "When migrate raises OR the swapped code serves the wrong version at GET /health, the launcher restores the previous app\\ AND the pre-update DB backup together, restarts the old version, and the operator's data is unharmed."
    why_human: "The real os.replace swap + alembic upgrade head + version-match health probe against a live 127.0.0.1:8000 server run only under the packaged launcher; pytest exercises the invariants with injected fakes, not the live machine path."
---

# Phase 32: In-App Secure Self-Update Verification Report

**Phase Goal:** Build the security-critical in-app self-update on top of Phase 31 — check GitHub Releases, verify signature AND checksum before unpacking, notify-and-confirm apply, pre-update backup + migrate with matched-pair rollback, header version tied to the installed release with integer-scheme anti-downgrade, hard no-op on the PostgreSQL server. Verification is a hard gate.
**Verified:** 2026-07-22T22:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (roadmap Success Criterion) | Status | Evidence |
|---|-----------------------------------|--------|----------|
| 1 | Startup + manual check detect a newer release; offline is a silent no-op; PostgreSQL server is a hard dialect-gated no-op (UPD-01/06/07) | ✓ VERIFIED | `update.check_for_update` dialect-gates FIRST (`engine.dialect.name != "sqlite"` → `noop`, no fetch — update.py:188), fetch `None` → `offline`, whole body broad-guarded (never raises). `main.py:113-156` one-shot `_startup_update_check` via `asyncio.create_task`, NOT awaited before `yield`. `POST /settings/update/check` (settings.py:70). Tests `test_server_noop`, `test_check_detects_newer`, `test_manual_check` GREEN. |
| 2 | Signature AND SHA-256 verified over the SIGNED manifest (not the git tag) before any unpack; failure aborts, nothing applied (UPD-02) | ✓ VERIFIED | `verify_release` (update.py:282) runs `verify_minisign` against vendored `app/minisign.pub` BEFORE reading any field, re-asserts version shape + anti-downgrade, THEN downloads archive and `sha256_matches`; `apply` raises `UpdateVerificationError` on any failure with nothing staged (extract only after gate passes, update.py:401-410). `minisign_verify.py` delegates Ed25519 to `cryptography`, key-id checked, fail-closed. `app/minisign.pub` vendored (RW key line), `cryptography>=49.0.0` in pyproject. Test `test_verify_gate` GREEN. |
| 3 | Operator shown new version + notes; applied ONLY on explicit «Обновить и перезапустить»; «Позже» defers — never silent (UPD-03) | ✓ VERIFIED | `update_panel.html` renders version line + autoescaped `{{ update_status.notes }}` (never `|safe`), «Обновить и перезапустить» → `hx-post /settings/update/apply`, «Позже» → dismiss. Routes are thin, always 200. Test `test_confirm_and_defer` GREEN (notes with `<b>` escaped). |
| 4 | Apply takes pre-update VACUUM backup, runs `alembic upgrade head`, matched-pair rollback (code + DB) on verify/migration/health failure (UPD-04) | ✓ VERIFIED | `apply` calls shipped `backup.create_backup` VACUUM INTO then `stage_pending` writes 3-key `pending.json` (update.py:413-415). Launcher `run_once` drives `apply_update` with `migrate` (`alembic upgrade head`, adapters.py:86-101), `health_ok(expected_version=pending.expected_version)`, and `backup_restore` (matched pair). Tests `test_apply_rolls_back`, `test_run_once_applies_app_written_marker`, `test_health_ok_requires_version_match` GREEN. Live machine round-trip → human. |
| 5 | Header version reflects installed release; integer `"1.<N>"` compare, strictly-newer only (UPD-05) | ✓ VERIFIED | `is_strictly_newer` uses `_counter` int compare (9→10 boundary), malformed → False (update.py:79-88); re-asserted at apply time. Header chip `MyOriShop v{{ APP_VERSION }}` (base.html:40), APP_VERSION from `app.__version__`. Test `test_anti_downgrade` GREEN. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/minisign_verify.py` | Ed25519/minisign verify + sha256_matches | ✓ VERIFIED | `verify_minisign` (algorithm-agnostic Ed/ED, key-id check, fail-closed) + `sha256_matches`; Ed25519 delegated to `cryptography`. |
| `app/services/update.py` | check half + apply verify-before-unpack gate + stage_pending | ✓ VERIFIED | `check_for_update`, `verify_release`, `apply` (raises on gate fail), `_extract_guarded` (zip-slip), `stage_pending` (3-key marker), `is_strictly_newer`. Substantive (417 lines), wired to routes + launcher. |
| `app/routes/health.py` | public GET /health → {version, status} | ✓ VERIFIED | Returns `{"version": APP_VERSION, "status": "ok"}`; in PUBLIC_PATHS; included in main.py. |
| `app/minisign.pub` | vendored RW public key trust anchor | ✓ VERIFIED | Last line starts `RWTo…` (minisign marker). |
| `app/templates/partials/update_panel.html` | all states, autoescaped notes, locked RU copy | ✓ VERIFIED | «Обновить и перзапустить»/«Позже», amber notice, error-block states; no `|safe`. |
| `app/routes/settings.py` | 3 thin /settings/update/* routes, always 200 | ✓ VERIFIED | check/apply/dismiss; apply maps `UpdateVerificationError` → verification-failed caption. |
| `launcher/adapters.py` | health_ok(expected_version=…) version-match | ✓ VERIFIED | Version-match probe on /health; None keeps legacy any-status-alive. |
| `app/main.py` | one-shot non-blocking startup check | ✓ VERIFIED | `_startup_update_check` via `anyio.to_thread.run_sync`, create_task, not awaited before yield, cancelled on shutdown. |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| settings.py routes | update.check_for_update / apply | thin route → service → #update-panel | ✓ WIRED |
| update.apply | backup.create_backup | pre-update VACUUM INTO into settings.backup_dir | ✓ WIRED |
| update.stage_pending | launcher.swap.parse_pending | 3-key pending.json, relative paths | ✓ WIRED |
| launcher.run_once | adapters.health_ok | `health_ok(expected_version=pending.expected_version)` | ✓ WIRED |
| launcher.run_once | adapters.migrate | `alembic upgrade head` on swapped layout | ✓ WIRED |
| minisign_verify | cryptography Ed25519PublicKey | from_public_bytes(pk).verify(sig, msg) | ✓ WIRED |
| update.py | app/minisign.pub | `_PUBKEY_PATH.read_text()` before trusting version | ✓ WIRED |
| main.py lifespan | update.check_for_update | asyncio.create_task, not awaited before yield | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Phase update + launcher tests pass | `uv run pytest tests/test_update.py tests/test_launcher.py -q` | 15 passed, 1 skipped | ✓ PASS |

The single skip is the environment-gated real-crypto / socket-bind test (skip-gated by design on a box without the minisign binary or with port 8000 restricted), never a failure.

### Requirements Coverage

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| UPD-01 | 32-01/03/05 | ✓ SATISFIED | Startup + manual check, offline silent no-op (truth 1) |
| UPD-02 | 32-01/02/03/04 | ✓ SATISFIED | Verify-before-unpack gate, vendored key, cryptography (truth 2) |
| UPD-03 | 32-01/05 | ✓ SATISFIED | Notify-and-confirm notice, apply/defer (truth 3) |
| UPD-04 | 32-01/04 | ✓ SATISFIED (code); live machine → human | Backup + migrate + matched-pair rollback wiring (truth 4) |
| UPD-05 | 32-01/03/05 | ✓ SATISFIED | Integer anti-downgrade + header chip (truth 5) |
| UPD-06 | 32-01/03/04/05 | ✓ SATISFIED | Dialect no-op gate in check + apply, sqlite-only section (truths 1,4) |
| UPD-07 | 32-01/05 | ✓ SATISFIED | Manual «Проверить обновления» route (truth 1) |

All 7 requirement IDs from PLAN frontmatter cross-referenced against REQUIREMENTS.md (lines 22-28, 60-66). No orphans — REQUIREMENTS.md maps exactly UPD-01..07 to Phase 32, every one claimed by at least one plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| app/services/update.py | 169 (notes), rendered update_panel.html:27 | Release notes sourced from UNSIGNED GitHub body (WR-01) | ℹ️ Info | Autoescaped (no XSS); notes are unsigned by design per SC3. Social-engineering surface only; route to /gsd-secure-phase 32. |
| app/services/update.py | 413-415 | `relative_to(root)` can raise post-extraction on a BACKUP_DIR override outside install root (WR-02) | ⚠️ Warning | Non-default config only; fails closed (nothing installed) but shows a misleading "rolled back" message and leaves staged/. Advisory. |
| app/services/update.py | 137-171 & 282-329 | Trust-gate scaffolding duplicated across two functions (WR-03) | ⚠️ Warning | Maintenance hazard; both copies currently agree. Advisory refactor. |
| app/services/minisign_verify.py | 36 | `assert` for pubkey-algorithm marker (IN-01) | ℹ️ Info | Stripped under `python -O`; input is the trusted vendored key, downstream fail-closed. |

No debt markers (TBD/FIXME/XXX/HACK/placeholder) in any phase-modified file. Zero BLOCKERs. The three warnings are robustness/quality advisories from 32-REVIEW.md (critical: 0), none of which break the update trust model — the code reviewer independently traced the full apply path and found no signature-bypass, downgrade, path-escape, or XSS hole.

### Human Verification Required

The security-critical apply path is fully code-verified with GREEN tests, but three behaviors genuinely cannot be exercised in pytest — they need two REAL signed GitHub releases from the Phase-31 pipeline and the packaged launcher parent process:

1. **Two-release round-trip (UPD-01/03/04/05).** Install release N on a bare Windows box, publish a signed N+1, launch → the notice appears; click «Обновить и перезапустить» → app restarts, header chip shows v(N+1), ledger intact.
2. **Tamper/downgrade rejection on real releases (UPD-02).** A checksum/signature-tampered asset and an older-version offer are both refused with nothing installed.
3. **Live launcher matched-pair rollback (UPD-04).** A forced migration failure or a failed post-swap /health version match restores the previous code + DB together, data unharmed.

These match the post-phase UAT items recorded in 32-05-SUMMARY.md — routed to `/gsd-verify-work 32`.

### Gaps Summary

No gaps. All 5 roadmap Success Criteria are observably true in the codebase, all 8 required artifacts exist, are substantive, and are wired end-to-end, all key links verified, and the phase's 15 behavioral tests pass (1 environment-gated skip). All 7 UPD requirements accounted for. Status is `human_needed` (not `passed`) solely because the real-signed-release round-trip, tamper/downgrade rejection on live releases, and the live-machine launcher rollback require two genuine signed releases and the packaged launcher — none of which can be verified programmatically.

**Note:** `/gsd-secure-phase 32` remains pending (plans carry threat models T-32-01..10 + T-32-SC); the WR-01 unsigned-notes surface is best resolved there.

---

_Verified: 2026-07-22T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
