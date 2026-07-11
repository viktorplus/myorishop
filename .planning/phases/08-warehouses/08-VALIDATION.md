---
phase: 8
slug: warehouses
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-11
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* |
| **Config file** | `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| **Quick run command** | `uv run pytest -q -k warehouse` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~32 seconds (baseline 247 passed) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -q -k warehouse`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 32 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-XX | 01 | 0 | WH-01 | V5 | Required `name` field non-blank after strip; Jinja2 autoescape on `name`/`address` (never `\|safe`) | unit | `pytest tests/test_warehouses.py::test_add_warehouse_creates_row -x` | ❌ W0 | ⬜ pending |
| 08-01-XX | 01 | 1 | WH-01 | V5 | Same as above | unit | `pytest tests/test_warehouses.py::test_update_warehouse_edits_fields -x` | ❌ W0 | ⬜ pending |
| 08-01-XX | 01 | 1 | WH-01 | — | Soft-delete/restore round trip, no hard delete | unit | `pytest tests/test_warehouses.py::test_soft_delete_and_restore_roundtrip -x` | ❌ W0 | ⬜ pending |
| 08-01-XX | 01 | 1 | WH-01 | — | Deleting last active warehouse warns, no write until confirm=1 | unit | `pytest tests/test_warehouses.py::test_delete_last_active_warehouse_warns_then_allows -x` | ❌ W0 | ⬜ pending |
| 08-01-XX | 01 | 1 | WH-01 | — | Deleted warehouse stays visible in list (grayed out + restore), not hidden (D-09) | web | `pytest tests/test_warehouses.py::test_web_deleted_warehouse_stays_visible_with_restore -x` | ❌ W0 | ⬜ pending |
| 08-01-XX | 01 | 1 | WH-01 (SC2) | — | Migration seeds exactly one default warehouse row on upgrade, existing data untouched | migration | `pytest tests/test_warehouses.py::test_migration_0007_creates_and_seeds_default_warehouse -x` | ❌ W0 | ⬜ pending |
| 08-01-XX | 01 | 1 | WH-01 | — | Nav gains a `/warehouses` link | web | `pytest tests/test_warehouses.py::test_web_nav_has_warehouses_link -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_warehouses.py` — new file, stubs for WH-01 (all rows above); no existing test file to extend.
- [ ] No new fixtures needed — `tests/conftest.py`'s `session`/`client`/`engine` fixtures are model-agnostic (schema created via `Base.metadata.create_all`, auto-includes the new `Warehouse` model once added to `app/models.py`).
- [ ] Framework install: none — pytest/httpx already dev dependencies.

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 32s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
