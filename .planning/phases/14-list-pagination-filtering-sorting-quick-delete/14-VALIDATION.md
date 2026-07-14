---
phase: 14
slug: list-pagination-filtering-sorting-quick-delete
status: draft
nyquist_compliant: true
wave_0_complete: true
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

Wave 0 gaps identified during research are resolved: every plan (14-01 through 14-07) carries `tdd="true"` tasks that write the missing pagination/filter/sort/quick-delete test coverage inline as part of the same task, rather than in a separate Wave 0 plan. All `<verify>` blocks use `<automated>` pytest commands with no watch-mode flags.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01/02/03 | 14-01 | 1 | LIST-01, LIST-02 | V5 | `page_window`/`paginate` clamp + `name_lc` Cyrillic-safe backfill | integration | `uv run pytest tests/test_pagination.py tests/test_dictionary.py -x` | ✅ delivered by plan | ⬜ pending |
| 14-02-01/02 | 14-02 | 2 | LIST-01, LIST-02, LIST-03 | V5 | `page`/`sort`/filter params validated server-side | integration | `uv run pytest tests/test_catalog.py -x` | ✅ delivered by plan | ⬜ pending |
| 14-03-01/02 | 14-03 | 2 | LIST-01, LIST-02, LIST-03 | V5 | `sort` resolved through fixed allow-list dict; `code`/`name` filters parameterized | integration | `uv run pytest tests/test_dictionary.py -x` | ✅ delivered by plan | ⬜ pending |
| 14-04-01/02/03 | 14-04 | 2 | LIST-01, LIST-02, LIST-03, LIST-05 | V5 / Tampering (confused deputy) | `page` clamped to `[0, total_pages-1]`; product quick-delete stock guard (hard block, non-overridable) | integration | `uv run pytest tests/test_catalog.py -x` | ✅ delivered by plan | ⬜ pending |
| 14-05-01/02/03 | 14-05 | 2 | LIST-01, LIST-02, LIST-03, LIST-04 | V5 / Tampering (confused deputy) | filter values only via parameterized Python comparisons; warehouse stock guard (hard block, non-overridable) checked before last-active guard (soft warn, `confirm=1`) | unit + integration | `uv run pytest tests/test_warehouses.py -x` | ✅ delivered by plan | ⬜ pending |
| 14-06-01/02 | 14-06 | 2 | LIST-01, LIST-02, LIST-03 | V5 | filter values only via parameterized Python comparisons; retires `/customers/search` route | integration | `uv run pytest tests/test_customers.py -x` | ✅ delivered by plan | ⬜ pending |
| 14-07-01/02 | 14-07 | 2 | LIST-01, LIST-02, LIST-03 | V5 | `year`/`sort`/`page` defensively parsed; year filter rendered in `.filter-row` header-row (D-04/Contract B), not `.filter-bar` | integration | `uv run pytest tests/test_catalogs_feature.py -x` | ✅ delivered by plan | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs reflect the planner's final Plan/Task numbering (14-01 through 14-07); this map's Req↔Test mapping stays authoritative regardless of any future renumbering.*

---

## Wave 0 Requirements

All Wave 0 gaps identified in RESEARCH.md are closed inline within their owning plan's `tdd="true"` tasks — no standalone Wave 0 plan was needed:

- [x] Pagination test coverage for products, warehouses, customers, dictionary, catalogs — delivered by 14-02/14-03/14-04/14-05/14-07 Task 1 (`paginate()`/`total_pages` behavior-block tests)
- [x] Filter test coverage for products, warehouses, customers, dictionary, catalogs — delivered by 14-02/14-03/14-04/14-05/14-07 Task 1/2
- [x] Sort test coverage for all six lists — delivered by 14-02/14-03/14-04/14-05/14-06/14-07 Task 1 (allow-listed `sort` param tests)
- [x] `tests/test_catalog.py` — new tests for `quick_delete_product` (blocked-with-stock case, success case, idempotent-on-already-deleted case) — delivered by 14-06
- [x] `tests/test_warehouses.py` — new test for the D-11 stock guard on `soft_delete_warehouse`, plus a replacement for `test_web_deleted_warehouse_stays_visible_with_restore` (`tests/test_warehouses.py:194`) — delivered by 14-06
- [x] `tests/test_catalogs_feature.py` — new pagination/filter/sort tests — delivered by 14-07 Task 1/2

*(Framework and fixtures already exist — `tests/conftest.py` provides `session`, `client`, `product`, `stocked_product`, `batch` fixtures used throughout the existing list tests; no new fixture infrastructure is anticipated.)*

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification via pytest integration tests against the FastAPI TestClient.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
