---
phase: 1
slug: foundation-ledger-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-08
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — Wave 0 installs (pyproject.toml [tool.pytest.ini_options]) |
| **Quick run command** | `uv run pytest -q -x` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q -x`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

(Filled by planner — one row per task with automated command.)

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-XX | 01 | 1 | FND-01/02/03 | — | N/A | unit | `uv run pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ledger.py` — stubs for FND-01 (append-only ledger, stock recompute)
- [ ] `tests/test_schema.py` — stubs for FND-02 (cents, UTC, UUID) and FND-03 (created_by/created_at)
- [ ] `tests/conftest.py` — shared fixtures (in-memory/temp SQLite session)
- [ ] pytest install via uv dev dependency

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| run.bat starts app and browser opens at localhost offline | FND-01 (skeleton) | Requires real Windows shell + browser | Double-click run.bat; verify page loads at http://127.0.0.1:8000 with network off |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
