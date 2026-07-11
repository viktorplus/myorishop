---
phase: 9
slug: batch-tracking-ledger-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-11
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x (installed, 262 tests green) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/test_batches.py tests/test_ledger.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~30 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run the quick run command scoped to the touched service's test file(s)
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD (filled by planner) | — | — | WH-02, LOT-01..05 | — | — | unit/integration | `uv run pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_batches.py` — stubs for LOT-01 (model/service), WH-02 (location tag)
- [ ] Existing `tests/conftest.py` fixtures extended for the mandatory `batch_id` in `record_operation()` (D-12 test-fixture sweep — the full 262-test suite must stay green)
- [ ] Migration 0008 upgrade test against a seeded pre-batch DB (legacy-batch seed balances, LOT-05/criterion 5)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Batch picker interaction in a real browser (radio select, price oob fill, single-batch auto-select note) | LOT-02 | HTMX swap/oob behavior with typed-value guards needs a real DOM | Open /sales, enter a code with 2+ batches, verify table appears, pick a batch, verify price fills and hidden batch_id posts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
