---
phase: 32
slug: in-app-secure-self-update
status: verified
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-22
audited: 2026-09-03
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 32-RESEARCH.md § Validation Architecture (security-critical phase: `security_enforcement=true`, ASVS L1, `block_on=high`).
> **Audited 2026-09-03** (`/gsd-validate-phase 32`) — the pre-execution draft below was reconciled against the shipped code and five security-control coverage gaps were closed.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (`pyproject.toml`, `[tool.pytest.ini_options]` `testpaths=["tests"]`, `pythonpath=["."]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_update.py -x` |
| **Phase-scoped command** | `uv run pytest tests/test_update.py tests/test_launcher.py -q` |
| **Full suite command** | `uv run pytest` |
| **Observed runtime** | phase-scoped ~5 s warm / ~11 s cold; full suite ~4–5 min |
| **Observed result (2026-09-03)** | **40 passed, 1 skipped** (skip = `test_health_ok_requires_version_match`, cannot bind `127.0.0.1:8000`) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_update.py -x`
- **After every plan wave:** Run `uv run pytest` (full suite)
- **Before `/gsd-verify-work`:** Full suite green **AND** CI `release-verify` job green
- **Max feedback latency:** 60 seconds — met (phase-scoped run is ~5 s)

> **Known baseline noise:** 4 pre-existing `tests/test_sync_ui.py` failures are OUT OF SCOPE for this phase (see MEMORY `preexisting-sync-ui-test-failures`). Do not attribute them to Phase 32.

---

## Per-Task Verification Map

| Requirement | Threat Ref | Secure Behavior | Test | Automated Command | Status |
|-------------|------------|-----------------|------|-------------------|--------|
| UPD-01 | T-32-10 | Newer signed release detected; offline (fetch → None) is a silent no-op that never raises | `tests/test_update.py::test_check_detects_newer` | `uv run pytest tests/test_update.py::test_check_detects_newer -x` | ✅ green |
| UPD-02 | T-32-01 (V10 integrity) | SHA-256 mismatch aborts; a failed gate stages nothing | `tests/test_update.py::test_verify_gate` | `uv run pytest tests/test_update.py::test_verify_gate -x` | ✅ green |
| UPD-02 | T-32-01 (V6 crypto) | Real minisign round-trip verifies in pure Python via `cryptography`; tampered payload rejected | `tests/test_update.py::test_minisign_pure_python_verify` | `uv run pytest tests/test_update.py::test_minisign_pure_python_verify -x` | ✅ green (skip-gated on the `minisign` binary — present here) |
| UPD-02 | T-32-03 / ASVS V5 | An asset URL off the host allowlist is refused **before any byte is fetched**; a suffix look-alike host is refused too | `tests/test_update.py::test_offhost_asset_url_is_refused_before_any_download` | `uv run pytest tests/test_update.py::test_offhost_asset_url_is_refused_before_any_download -x` | ✅ green *(added 2026-09-03 — closes SEC-A3)* |
| UPD-02 | T-32-05 / ASVS V12 | An archive carrying a `../` (or drive-absolute) member raises `ValueError`; the whole namelist is pre-scanned, so **no** member is extracted | `tests/test_update.py::test_extract_guarded_rejects_zip_slip_member` | `uv run pytest tests/test_update.py::test_extract_guarded_rejects_zip_slip_member -x` | ✅ green *(added 2026-09-03 — closes SEC-A4)* |
| UPD-02, UPD-05 | T-32-01/03/04 | The **real** `verify_release` gate: bad signature ⇒ the multi-MB archive is never downloaded; tampered archive ⇒ refused; clean gate ⇒ version read from the SIGNED manifest, not the lying git tag | `tests/test_update.py::test_verify_release_gate_ordering_is_real` | `uv run pytest tests/test_update.py::test_verify_release_gate_ordering_is_real -x` | ✅ green *(added 2026-09-03 — closes SEC-A1/SEC-A9 ordering evidence)* |
| UPD-03 | T-32-01 (no silent apply) | Confirm applies; «Позже» dismisses; release notes rendered AUTOESCAPED (never `\|safe`) | `tests/test_update.py::test_confirm_and_defer` | `uv run pytest tests/test_update.py::test_confirm_and_defer -x` | ✅ green |
| UPD-04 | T-32-08, T-32-06 | A clean gate unpacks into `staged/`, takes a real pre-update `VACUUM INTO` backup, and writes `data/pending.json` with EXACTLY 3 keys and relative paths, no `.partial` left | `tests/test_update.py::test_apply_stages_backup_and_marker` | `uv run pytest tests/test_update.py::test_apply_stages_backup_and_marker -x` | ✅ green *(added 2026-09-03)* |
| UPD-04 | T-32-08 | Matched-pair rollback: migrate-fail ⇒ code restored + DB reverted; app-written marker consumed by the launcher | `tests/test_launcher.py::test_apply_rolls_back`, `::test_run_once_applies_app_written_marker` | `uv run pytest tests/test_launcher.py -q` | ✅ green |
| UPD-04 | T-32-06 | `stage_pending` is atomic (temp + `os.replace`); traversal payloads refused by `parse_pending` | `tests/test_launcher.py::test_stage_pending_writes_the_marker_atomically`, `::test_parse_pending_rejects_path_traversal` | `uv run pytest tests/test_launcher.py -q` | ✅ green |
| UPD-05 | T-32-02 | Integer `"1.<N>"` compare incl. the 9→10 boundary; a verified-but-older manifest ⇒ `up_to_date` | `tests/test_update.py::test_anti_downgrade` | `uv run pytest tests/test_update.py::test_anti_downgrade -x` | ✅ green |
| UPD-06 | T-32-09 | `check_for_update` on a PostgreSQL dialect ⇒ `noop`, no network fetch | `tests/test_update.py::test_server_noop` | `uv run pytest tests/test_update.py::test_server_noop -x` | ✅ green |
| UPD-06 | T-32-09 | `apply` on a PostgreSQL dialect ⇒ `noop` **before** resolving or verifying anything | `tests/test_update.py::test_apply_is_noop_on_postgresql` | `uv run pytest tests/test_update.py::test_apply_is_noop_on_postgresql -x` | ✅ green *(added 2026-09-03)* |
| UPD-07 | T-32-03 | Manual «Проверить обновления» returns 200 with the `#update-panel` partial — never a 5xx, even offline | `tests/test_update.py::test_manual_check` | `uv run pytest tests/test_update.py::test_manual_check -x` | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Non-vacuity note (why the new tests can actually fail):** both trust entry points end in `except Exception: return None`, so a tripwire that *raises* would be swallowed and the assertion would pass even with the control deleted. The allowlist test therefore **records** requested URLs and asserts `fetched == []`; the ordering test asserts positively that the manifest+signature **were** fetched while the archive was **not**. Delete the allowlist or reorder the gate and both tests go red.

---

## Wave 0 Requirements — all met

- [x] `tests/test_update.py` — RED scaffold covering UPD-01..07, flipped GREEN by Waves 03–05
- [x] Test fixtures: fake GitHub `/releases/latest` JSON; a throwaway tmp minisign keypair (skip-gated on the `minisign` binary); a synthetic zip + manifest + `.minisig`
- [x] `tests/test_launcher.py` extended for the app-writes-marker → launcher-applies integration
- [x] `uv add cryptography` — human-approved supply-chain checkpoint (32-02, commit `07a2186`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Status |
|----------|-------------|------------|--------|
| Bare-Windows end-to-end update between two real signed `v1.<N>` releases, via the installer on a clean VM | UPD-01..05 | Needs two real published GitHub releases + a bundled-runtime install; the repo currently has **zero** published releases (`releases/latest` → 404) | ⏳ open — `32-UAT.md` ran the round trip on a scratch install root with a local HTTP server instead (63 live checks, 63 passed) |
| `app/minisign.pub` presence + correct key | UPD-02 | Key generated offline (`minisign -G`) and vendored | ✅ closed — `32-UAT.md` test 2 verified real manifests signed with the offline key against the vendored anchor |
| Anti-downgrade / tamper rejection against a live release | UPD-02, UPD-05 | Requires a real signed manifest + a deliberately tampered asset | ✅ closed live — a genuinely signed 1.59 vs installed 1.61 → `up_to_date`; flipped archive byte and flipped signature char → `UpdateVerificationError` |
| Browser click of «Обновить и перезапустить» / «Позже» (HTMX swap of `#update-panel`) | UPD-03, UPD-07 | No browser driver in this project's test stack | ⏳ open — covered server-side by `test_confirm_and_defer` / `test_manual_check` and by the UI-SPEC review only |
| Real `api.github.com` fetch from a published release | UPD-01 | No GitHub release exists yet; this is also the root cause of SEC-A3 having had no live evidence | ⏳ open — the allowlist is now covered by a unit test instead |
| `health_ok(expected_version=...)` version match | UPD-04 | `launcher/adapters._PORT` is fixed at 8000 by contract and the operator's own instance owns that port on this box (`WinError 10013`) — the test self-skips | ✅ control proven live instead — `32-UAT.md` test 3(b): a 43.2 s poll, version mismatch, full matched-pair rollback |

---

## Escalated to Implementation (NOT a coverage gap)

| Ref | Defect | Why not tested here |
|-----|--------|---------------------|
| SEC-A5 / WR-02 | `backup_path.relative_to(root)` (`app/services/update.py:423`) raises `ValueError` when `settings.backup_dir` is not under the derived install root (reachable via a `BACKUP_DIR` override). It fires **after** `_extract_guarded` already wrote `staged/`, and `settings_update_apply`'s broad `except` then shows «Восстановлена предыдущая версия, ваши данные в безопасности» — a rollback that never happened. No data loss, no half-swap; the operator is simply told something untrue. | A test for this would be RED against shipped code. The Nyquist auditor is forbidden to modify implementation files, so this is escalated rather than papered over. Fix = guard the `relative_to`, or compute it before extracting. `test_apply_stages_backup_and_marker` deliberately places `backup_dir` **under** the install root so it does not trip the defect. |
| SEC-A6 / IN-01 | `assert raw[:2] == b"Ed"` (`app/services/minisign_verify.py:36`) — a security-relevant format check that vanishes under `python -O`. Impact nil (fail-closed downstream), but it should be an explicit `raise ValueError`. | Implementation change, out of scope for a validation audit. |
| ruff `B017` | `tests/test_update.py:218` (`pytest.raises(Exception)` inside the pre-existing `test_verify_gate`). Pre-existing — confirmed identical against a stashed clean tree; the five new tests add zero ruff findings. | Left untouched per the do-not-touch-unrelated-code rule. One-line fix: `pytest.raises(update.UpdateVerificationError)`. |

---

## Validation Audit 2026-09-03

| Metric | Count |
|--------|-------|
| Gaps found | 5 |
| Resolved (new automated tests) | 5 |
| Escalated to implementation | 1 (SEC-A5) |
| Escalated to manual-only | 0 |
| Phase-scoped suite before | 35 passed, 1 skipped |
| Phase-scoped suite after | **40 passed, 1 skipped** |

Gaps came from `32-SECURITY.md`'s advisory register, not from guesswork: SEC-A3 (host allowlist with zero execution evidence), SEC-A4 (zip-slip guard verified by inspection only), SEC-A1/A9 (the trust gate is duplicated and only the stubbed copy ran), plus two entry points the map had never claimed — the apply-side dialect gate and the apply happy path.

---

## Validation Sign-Off

- [x] All requirements have an automated verify command
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covered all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s (~5 s phase-scoped)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** verified 2026-09-03
