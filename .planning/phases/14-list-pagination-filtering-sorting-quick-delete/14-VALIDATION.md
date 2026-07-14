---
phase: 14
slug: list-pagination-filtering-sorting-quick-delete
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-14
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (`pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_warehouses.py tests/test_catalog.py tests/test_history.py tests/test_customers.py tests/test_dictionary.py tests/test_catalogs_feature.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run the relevant single test file (`uv run pytest tests/test_<entity>.py -x`)
- **After every plan wave:** Run `uv run pytest tests/test_warehouses.py tests/test_catalog.py tests/test_history.py tests/test_customers.py tests/test_dictionary.py tests/test_catalogs_feature.py`
- **Before `/gsd-verify-work`:** Full suite (`uv run pytest`) must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-XX-XX | TBD | 0 | LIST-01 | V5 | `page` clamped to `[0, total_pages-1]` | integration | `uv run pytest tests/test_history.py::test_history_pagination -x` (existing pattern, extend/copy per list) | ✅ partial (history only) — ❌ W0 for products/warehouses/customers/dictionary/catalogs | ⬜ pending |
| 14-XX-XX | TBD | 0 | LIST-02 | V5 | filter values only via parameterized ORM `.where()`/`.contains()` | integration | `uv run pytest tests/test_history.py -k filter -x` (existing pattern, extend/copy per list) | ✅ partial (history only) — ❌ W0 for other five | ⬜ pending |
| 14-XX-XX | TBD | 0 | LIST-03 | V5 | `sort` resolved through fixed allow-list dict, never string-interpolated | integration | e.g. `uv run pytest tests/test_catalog.py -k sort -x` | ❌ W0 for all six lists | ⬜ pending |
| 14-XX-XX | TBD | 0 | LIST-04 | Tampering (confused deputy) | stock guard (hard block, non-overridable) checked before last-active guard (soft warn, `confirm=1`) | unit + integration | `uv run pytest tests/test_warehouses.py -k delete -x` | ⚠️ W0 — existing test covers old guard only; new stock-guard test + replacement for `test_web_deleted_warehouse_stays_visible_with_restore` (`tests/test_warehouses.py:194`) needed | ⬜ pending |
| 14-XX-XX | TBD | 0 | LIST-05 | Tampering / Info Disclosure | stock guard blocks delete-with-stock; error strings autoescaped, never `\|safe` | unit + integration | `uv run pytest tests/test_catalog.py -k delete -x` | ❌ W0 — no existing quick-delete test; `soft_delete_product` has no stock guard test | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs are placeholders — the planner assigns final Plan/Task IDs; this map's Req↔Test mapping stays authoritative regardless of ID renumbering.*

---

## Wave 0 Requirements

- [ ] Pagination test coverage for products, warehouses, customers, dictionary, catalogs (only history has one today — `tests/test_history.py:67`)
- [ ] Filter test coverage for products, warehouses, customers, dictionary, catalogs (only history has one today — `tests/test_history.py:107`)
- [ ] Sort test coverage for all six lists (none exist today)
- [ ] `tests/test_catalog.py` — new tests for `quick_delete_product` (blocked-with-stock case, success case, idempotent-on-already-deleted case)
- [ ] `tests/test_warehouses.py` — new test for the D-11 stock guard on `soft_delete_warehouse`, plus a replacement for `test_web_deleted_warehouse_stays_visible_with_restore` (`tests/test_warehouses.py:194`) which currently asserts the OLD grayed-out-with-restore behavior that D-14 changes
- [ ] `tests/test_catalogs_feature.py` — check existing `list_catalogs`/`catalog_detail` coverage; likely needs new pagination/filter/sort tests

*(Framework and fixtures already exist — `tests/conftest.py` provides `session`, `client`, `product`, `stocked_product`, `batch` fixtures used throughout the existing list tests; no new fixture infrastructure is anticipated.)*

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification via pytest integration tests against the FastAPI TestClient.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
