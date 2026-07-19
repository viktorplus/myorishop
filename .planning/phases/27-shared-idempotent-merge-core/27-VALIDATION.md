---
phase: 27
slug: shared-idempotent-merge-core
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-19
---

# Phase 27 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | pyproject.toml / pytest.ini (existing) |
| **Quick run command** | `uv run pytest tests/test_merge.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_merge.py -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 27-01-01 | 01 | 1 | SYNC-04 | — | NDJSON round-trips verbatim (parse∘serialize == identity) preserving origin id/device_id/seq/author | unit | `uv run pytest tests/test_merge.py -q` | ❌ W0 | ⬜ pending |
| 27-02-01 | 02 | 2 | SYNC-02 | — | Merge-twice equals merge-once: no duplicate ledger rows, no double-counted stock/cash | unit | `uv run pytest tests/test_merge.py -q` | ❌ W0 | ⬜ pending |
| 27-02-02 | 02 | 2 | SYNC-03 | — | Derived stock + cash recomputed from ledger after merge match direct SUM | unit | `uv run pytest tests/test_merge.py -q` | ❌ W0 | ⬜ pending |
| 27-03-01 | 03 | 3 | SYNC-05 | T-27-01 | Concurrent reference edits resolve server-authoritatively; duplicate Product.code loser renamed keeping UUID | unit | `uv run pytest tests/test_merge.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are provisional — reconcile against final PLAN.md task numbering during execution.*

---

## Wave 0 Requirements

- [ ] `tests/test_merge.py` — idempotency, conflict-resolution, and derived-state stubs for SYNC-02..05
- [ ] `tests/conftest.py` — shared in-memory session + ledger fixtures (extend if needed)
- [ ] pytest already installed — no framework install required

---

## Manual-Only Verifications

*All phase behaviors have automated verification — the engine is pure functions with no HTTP/file I/O, fully unit-testable in isolation.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
