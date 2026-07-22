---
phase: 32
slug: in-app-secure-self-update
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-22
---

# Phase 32 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from 32-RESEARCH.md § Validation Architecture (security-critical phase: `security_enforcement=true`, ASVS L1, `block_on=high`).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (`pyproject.toml:23`, `[tool.pytest.ini_options]` `testpaths=["tests"]`, `pythonpath=["."]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_update.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30–60 seconds (quick), full suite ~2–4 min (1185 currently green) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_update.py -x`
- **After every plan wave:** Run `uv run pytest` (full suite)
- **Before `/gsd-verify-work`:** Full suite green **AND** CI `release-verify` job green
- **Max feedback latency:** 60 seconds

> **Known baseline noise:** 4 pre-existing `tests/test_sync_ui.py` failures are OUT OF SCOPE for this phase (see MEMORY `preexisting-sync-ui-test-failures`). Do not attribute them to Phase 32.

---

## Per-Task Verification Map

> Task IDs are preliminary (assigned during planning). Wave 0 = RED scaffold. Extend as the planner finalizes plan/task numbering.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 32-01-01 | 01 | 0 | UPD-01..07 | — | RED scaffold imports service inside test bodies (collection stays green) | scaffold | `uv run pytest tests/test_update.py` | ❌ W0 | ⬜ pending |
| 32-xx | — | — | UPD-01 | T-32 (DoS/offline) | Newer release detected; offline = no-op (fetch returns None), never blocks launch | unit (httpx/`respx` mock) | `uv run pytest tests/test_update.py::test_check_detects_newer -x` | ❌ W0 | ⬜ pending |
| 32-xx | — | — | UPD-02 | T-32 (V10 integrity) | SHA-256 mismatch aborts; bad Ed25519 aborts; valid passes; verify BEFORE unpack | unit | `uv run pytest tests/test_update.py::test_verify_gate -x` | ❌ W0 | ⬜ pending |
| 32-xx | — | — | UPD-02 | T-32 (V6 crypto) | Real minisign round-trip (Ed AND ED modes) verifies in pure Python via `cryptography` | integration (skip-gated on `minisign` binary) | `uv run pytest tests/test_update.py::test_minisign_pure_python_verify -x` | ❌ W0 | ⬜ pending |
| 32-xx | — | — | UPD-03 | T-32 (no silent apply) | Confirm applies; «Позже» dismisses; release notes rendered | integration (TestClient) | `uv run pytest tests/test_update.py::test_confirm_and_defer -x` | ❌ W0 | ⬜ pending |
| 32-xx | — | — | UPD-04 | T-32 (data loss) | Pre-update VACUUM INTO backup taken; migrate-fail ⇒ matched-pair (code+DB) rollback | unit (reuse `test_launcher.py` fake-callbacks) | `uv run pytest tests/test_update.py::test_apply_rolls_back -x` | ⚠ extend `tests/test_launcher.py` | ⬜ pending |
| 32-xx | — | — | UPD-05 | T-32 (downgrade) | Integer `"1.<N>"` compare; 9→10 boundary; downgrade refused; version from signed manifest | unit | `uv run pytest tests/test_update.py::test_anti_downgrade -x` | ❌ W0 | ⬜ pending |
| 32-xx | — | — | UPD-06 | T-32 (server no-op) | PostgreSQL dialect ⇒ entire update path is a hard no-op | unit (dialect-gate seam) | `uv run pytest tests/test_update.py::test_server_noop -x` | ❌ W0 | ⬜ pending |
| 32-xx | — | — | UPD-07 | — | Manual «Проверить обновления» route returns banner state | integration (TestClient) | `uv run pytest tests/test_update.py::test_manual_check -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_update.py` — new RED scaffold covering UPD-01..07; import the update service **inside** test bodies to keep collection green (mirror `tests/test_release_verify.py` / `tests/test_packaging.py`)
- [ ] Test fixtures: fake GitHub `/releases/latest` JSON; a throwaway tmp minisign keypair (skip-gated on the `minisign` binary); a synthetic zip + manifest + `.minisig`
- [ ] Extend `tests/test_launcher.py` for the app-writes-marker → launcher-applies integration (the swap half is already covered)
- [ ] Dependency install: `uv add cryptography` — gated behind a `checkpoint:human-verify` (SUS flag on `unknown-downloads` only; canonical PyCA lib)

*Existing infrastructure (pytest, conftest fixtures, TestClient, launcher fake-callback pattern) covers the harness; only the above scaffold/fixtures are new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Bare-Windows end-to-end update between two real signed `v1.<N>` releases | UPD-01..05 | Needs two real signed GitHub releases + a bundled runtime install; cannot be produced in unit tests | Install release N, publish release N+1 signed, launch, confirm «Обновить и перезапустить», verify header shows N+1 and data intact |
| `app/minisign.pub` presence + correct key | UPD-02 | Key is generated offline (`minisign -G`) and vendored; absence is BLOCKING | Confirm `app/minisign.pub` exists, matches the CI signing key, and a tampered asset fails verify |
| Anti-downgrade / tamper rejection against a live release | UPD-02, UPD-05 | Requires a real signed manifest + a deliberately tampered asset | Confirm a downgrade offer and a checksum-tampered asset are both refused with nothing applied |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
