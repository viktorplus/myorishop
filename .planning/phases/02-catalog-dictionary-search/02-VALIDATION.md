---
phase: 2
slug: catalog-dictionary-search
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-08
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (+ httpx TestClient) — already installed (Phase 1) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest -q -x` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q -x`
- **After every plan wave:** Run `uv run pytest -q` + `uv run ruff check .`
- **Before `/gsd-verify-work`:** Full suite green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

(Filled by planner — one row per task with automated command.)

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 2-XX-XX | — | — | CAT-01..04 | — | N/A | unit/integration | `uv run pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_catalog.py` — CAT-01 (CRUD, optional fields, soft-delete reject), CAT-04 (price history ops)
- [ ] `tests/test_search.py` — CAT-03 (Cyrillic case-insensitive partial search, ranking, cap 20)
- [ ] `tests/test_dictionary.py` — CAT-02 (dictionary CRUD, code→name lookup autofill endpoint)
- [ ] Existing fixtures from tests/conftest.py reused (no new framework install)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Debounced autocomplete feel (300ms) in real browser | CAT-03 | Perceived latency/UX not testable in-process | Type in search box on /products; results update without page reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
