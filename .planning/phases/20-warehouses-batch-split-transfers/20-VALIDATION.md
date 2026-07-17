---
phase: 20
slug: warehouses-batch-split-transfers
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-16
audited: 2026-07-17
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (`pyproject.toml` pinned `pytest==9.1.*`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]` |
| **Quick run command** | `uv run pytest tests/test_warehouses.py tests/test_transfers.py tests/test_mobile_transfers.py tests/test_writeoffs.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Actual runtime (measured)** | Quick: ~19s (98 tests). Full: ~127s (754 tests). |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_warehouses.py tests/test_transfers.py -q`
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|--------|
| 20-01-1/2 | 20-01 | 1 | WH-01 | T-20-01 (20-01) | Item count via page-wide grouped query, not per-row | unit | `uv run pytest tests/test_warehouses.py -k item_count -x` | ✅ green |
| 20-01-2 | 20-01 | 1 | WH-01 | T-20-01 (20-01) | Last receipt date uses outerjoin (warehouse with 0 receipts still shown, not dropped) | unit | `uv run pytest tests/test_warehouses.py -k last_receipt -x` | ✅ green |
| 20-03-1 | 20-03 | 2 | WH-01 | — | `/warehouses` list renders item-count/last-receipt columns | web | `uv run pytest tests/test_warehouses.py -k shows_item_count_and_last_receipt -x` | ✅ green |
| 20-02-1 | 20-02 | 1 | WH-02, D-01 | T-20-02 | `GET /warehouses/new` and `GET/POST /warehouses/{id}/edit` dedicated form pages, redirect-after-success/422-re-render | web | `uv run pytest tests/test_warehouses.py -k warehouse_new or warehouse_edit -x` | ✅ green |
| 20-03-1 | 20-03 | 2 | WH-02 | — | `/warehouses` is a plain picker: no inline edit/delete, one "Изменить" link per row; filter/sort/status preserved (Pitfall 1 regression) | web | `uv run pytest tests/test_warehouses.py -k row_action_is_edit_link or filter_bar -x` | ✅ green |
| 20-02-1 (WR-02 fix) | 20-02 | 1 | WH-02 hardening | T-20-02 | `GET /warehouses/{id}/edit` and `POST /warehouses/{id}` reject a soft-deleted warehouse id (404, no silent update) | web | `uv run pytest tests/test_warehouses.py -k soft_deleted -x` | ✅ green (filled 2026-07-17) |
| 20-02-1 | 20-02 | 1 | WH-03, D-02 | T-20-03 | Delete blocked while stock > 0 (non-overridable); warn-then-confirm for last-active; success redirects at zero stock | unit/web | `uv run pytest tests/test_warehouses.py -k stock_blocked or stock_positive or delete_success -x` | ✅ green |
| 20-04-1 | 20-04 | 1 | XFER-01, D-05/D-06/D-07 | — | Same-warehouse split creates new dest batch with only moved qty (override-or-inherit ternary), source unchanged; blank overrides blocked, zero writes | unit | `uv run pytest tests/test_transfers.py -k same_warehouse -x` | ✅ green |
| 20-05-1 | 20-05 | 2 | XFER-01, D-09 | — | Desktop `/transfers` accepts same-warehouse destination + overrides end-to-end via raw form POST | web | `uv run pytest tests/test_transfers.py -k same_warehouse_success or same_warehouse_blank -x` | ✅ green |
| 20-06-1 | 20-06 | 2 | XFER-01 | — | Mobile `/m/transfers` wizard reaches parity: same-warehouse split + override fields | web | `uv run pytest tests/test_mobile_transfers.py -k same_warehouse -x` | ✅ green |
| 20-07-1 | 20-07 | 3 | XFER-01 | — | Desktop override fields render (unconditional on selected_batch, separate block from dest-select); D-06 error visible; typed values echoed on 422 | web | `uv run pytest tests/test_transfers.py -k override_fields or echoes_typed_override -x` | ✅ green |
| 20-05-1/2 | 20-05 | 2 | D-10 (debt) | T-20-01 (20-05), T-20-07 | Batch-ownership check before echoing `selected_batch` in `transfers_create`/`writeoff_create` | web | `uv run pytest tests/test_transfers.py tests/test_writeoffs.py -k ownership -x` | ✅ green |
| 20-04-2 / 20-05-1 / 20-06-1 | 20-04, 20-05, 20-06 | 1-2 | D-11 (debt) | — | Success echo uses actual transferred qty (int), not raw form string — desktop service, desktop route, mobile route | unit/web | `uv run pytest tests/test_transfers.py tests/test_mobile_transfers.py -k qty_echo -x` | ✅ green |

*Status: ✅ green · ❌ red · ⚠️ flaky*
*98 phase-relevant tests green (`tests/test_warehouses.py tests/test_transfers.py tests/test_mobile_transfers.py tests/test_writeoffs.py`); full suite 754/754 green.*

---

## Manual-Only Verifications

All three items below were executed as UAT on 2026-07-16/17 (see `20-UAT.md`) — **all passed**. Retained here as the permanent record of why they can't be automated.

| Behavior | Requirement | Why Manual | Result |
|----------|-------------|------------|--------|
| Warehouse delete three-state flow (stock-blocked / warn-then-confirm / success redirect) in a live browser, including the HX-Redirect actually navigating | WH-03 | TestClient only asserts the `HX-Redirect` header is present, it does not execute the redirect; client-side `hx-on:click` dismiss handler is JS-only | ✅ pass (20-UAT.md #1) |
| Desktop `/transfers`: destination-`<select>` keeps the operator's original choice pre-selected through an oversell re-render (CR-01 regression) | XFER-01 | CR-01 was a real bug found only by tracing an actual browser round-trip — TestClient's own tests re-supply `dest_warehouse_id` explicitly on the second POST and would not reproduce a dropped-selection bug | ✅ pass (20-UAT.md #2) |
| Mobile wizard (`/m/transfers`): same-warehouse split with expiry override, correct qty on success screen | XFER-01 | End-to-end 3-step HTMX wizard swap UX (back/forward, radio pre-check) not observable via TestClient response bodies alone | ✅ pass (20-UAT.md #3) |

---

## Validation Sign-Off

- [x] All tasks have automated verify or a documented Manual-Only entry
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all previously-MISSING references (all closed during execution, waves 1-3)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (quick run ~19s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** complete — audited 2026-07-17

---

## Validation Audit 2026-07-17

Reconstructed from PLAN/SUMMARY/VERIFICATION/UAT/SECURITY artifacts (execution had completed since this file was last drafted; frontmatter was still `status: draft`/`nyquist_compliant: false` from planning time).

| Metric | Count |
|--------|-------|
| Gaps found | 1 |
| Resolved | 1 |
| Escalated | 0 |

**Gap detail:** WR-02 (code-review fix hardening T-20-02 — soft-deleted warehouse rejected on edit/update) had no dedicated regression test; the fix itself was already confirmed correct by direct code read in `20-VERIFICATION.md`. Filled by `gsd-nyquist-auditor`: added `test_web_warehouse_edit_soft_deleted_id_404s` and `test_web_warehouse_update_soft_deleted_id_rejected` to `tests/test_warehouses.py`. Both pass; full suite 752 → 754 passed, 0 failed, no regressions.
