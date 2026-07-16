---
phase: 20
slug: warehouses-batch-split-transfers
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (`pyproject.toml` pinned `pytest==9.1.*`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `uv run pytest tests/test_warehouses.py tests/test_transfers.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10 seconds (baseline 41/41 relevant tests; full suite runs in low single-digit seconds per prior phases) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_warehouses.py tests/test_transfers.py -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 20-xx-xx | TBD | TBD | WH-01 | — | Item count / last-receipt via page-wide grouped query, not per-row | unit | `uv run pytest tests/test_warehouses.py -k item_count -x` | ❌ W0 | ⬜ pending |
| 20-xx-xx | TBD | TBD | WH-01 | — | Last receipt date uses outerjoin (warehouse with 0 receipts still shown) | unit | `uv run pytest tests/test_warehouses.py -k last_receipt -x` | ❌ W0 | ⬜ pending |
| 20-xx-xx | TBD | TBD | WH-02 | — | `/warehouses` is a plain picker, no inline edit/delete, filter/sort/status preserved | web | `uv run pytest tests/test_warehouses.py -k web_warehouses_page -x` | ✅ (needs rewrite) | ⬜ pending |
| 20-xx-xx | TBD | TBD | WH-02 | — | `/warehouses/new` renders add form; `POST /warehouses` creates | web | `uv run pytest tests/test_warehouses.py -k warehouse_new -x` | ❌ W0 | ⬜ pending |
| 20-xx-xx | TBD | TBD | WH-02 | — | `/warehouses/{id}/edit` renders edit+delete form | web | `uv run pytest tests/test_warehouses.py -k warehouse_edit -x` | ❌ W0 | ⬜ pending |
| 20-xx-xx | TBD | TBD | WH-03 | — | Delete blocked while stock > 0; succeeds at zero stock (logic unchanged, rendering moved) | unit | `uv run pytest tests/test_warehouses.py -k stock_positive -x` | ✅ exists | ⬜ pending |
| 20-xx-xx | TBD | TBD | XFER-01 | — | Same-warehouse split creates new dest batch with only moved qty, source unchanged | unit | `uv run pytest tests/test_transfers.py -k same_warehouse -x` | ❌ W0 (rewrite of `test_reject_same_warehouse`, D-08) | ⬜ pending |
| 20-xx-xx | TBD | TBD | XFER-01 | — | Cross-warehouse transfer with expiry/comment override | unit | `uv run pytest tests/test_transfers.py -k override -x` | ❌ W0 | ⬜ pending |
| 20-xx-xx | TBD | TBD | XFER-01 | — | Blank overrides + same warehouse → validation error, zero writes | unit | `uv run pytest tests/test_transfers.py -k requires_override -x` | ❌ W0 | ⬜ pending |
| 20-xx-xx | TBD | TBD | D-10 (debt) | T-20-01 | Batch-ownership check before echoing `selected_batch` in `transfers.py`/`writeoffs.py` create handlers | unit/web | `uv run pytest tests/test_transfers.py tests/test_writeoffs.py -k ownership -x` | ❌ W0 | ⬜ pending |
| 20-xx-xx | TBD | TBD | D-11 (debt) | — | Success echo uses actual transferred qty, not raw form string | web | `uv run pytest tests/test_transfers.py -k qty_echo -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs and Plan/Wave columns will be filled by the planner when PLAN.md files are created.*

---

## Wave 0 Requirements

- [ ] New service-level tests for `list_warehouses`' item-count/last-receipt grouped queries (WH-01)
- [ ] New route tests for `GET /warehouses/new` and `GET/POST /warehouses/{id}/edit` (WH-02)
- [ ] Rewrite of `tests/test_warehouses.py`'s `test_web_*` section (lines ~235-369) to match the new picker+dedicated-form page shape
- [ ] New/renamed tests in `tests/test_transfers.py` for D-05/D-06/D-07 (same-warehouse split, override fields, blank-override validation), replacing `test_reject_same_warehouse`'s old assertion (D-08)
- [ ] Confirm whether `tests/test_mobile_transfers.py` exists and needs the same parity additions as desktop's transfer tests (verify during planning)
- [ ] New tests for D-10 (ownership guard in `transfers_create`/`writeoff_create`) and D-11 (accurate qty echo)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Warehouse edit-page delete warn/stock-blocked states render legibly (HTMX-in-place vs full-page redirect, per CONTEXT.md's Claude's Discretion) | WH-03 | Visual/interaction confirmation of relocated warning UI can't be asserted via TestClient response body alone with full confidence | Open `/warehouses/{id}/edit` for a warehouse with stock, click delete, confirm stock-blocked message renders; repeat for a warehouse with 0 stock and confirm the warn-then-confirm two-step works |
| Same-warehouse split override fields appear/behave correctly in the browser (HTMX partial swaps, field visibility once a source batch is picked) | XFER-01 | HTMX DOM-merge/OOB-swap behavior is browser-only per this project's established gotcha pattern (Phase 9 UAT); TestClient can't reproduce browser-side fragment merging | Open `/transfers`, pick a batch, select the source warehouse as destination, confirm override fields are visible and the form blocks submission with both blank |
| Mobile transfer wizard override fields and same-warehouse destination option | XFER-01 | Mobile wizard step-by-step flow relies on the same HTMX/browser rendering concerns as desktop | Open `/m/transfers` on a mobile viewport, verify destination list includes source warehouse and override fields are reachable |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
