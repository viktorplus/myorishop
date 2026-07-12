---
phase: 9
slug: batch-tracking-ledger-integration
status: draft
nyquist_compliant: true
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
- **After every plan wave:** Run `uv run pytest -q` (mandatory — D-12 has repo-wide blast radius)
- **Before `/gsd-verify-work`:** Full suite must be green + `ruff check .`
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-T1 | 09-01 | 1 | LOT-01, LOT-03 | T-09-01 | Batch model (no deleted_at); open_batches NULLS-LAST order; ru_date | unit | `uv run pytest tests/test_batches.py -k "model or ordering or ru_date" -x -q` | ❌ W0 | ⬜ pending |
| 01-T2 | 09-01 | 1 | LOT-01, criterion 5 | T-09-02, T-09-03 | Migration native add_column; triggers survive; legacy seed from ledger SUM | integration (migration replay) | `uv run pytest tests/test_batches.py -k migration -x -q` | ❌ W0 | ⬜ pending |
| 01-T3 | 09-01 | 1 | LOT-01 | T-09-01 | Dual projection; ownership guard when batch supplied; rebuild invariant | unit + full sweep | `uv run pytest tests/test_batches.py tests/test_ledger.py -x -q && uv run pytest -q` | ❌ W0 | ⬜ pending |
| 02-T1 | 09-02 | 2 | WH-02, LOT-01, LOT-03, LOT-04 | T-09-04, T-09-05 | Resolve-or-create; top-up/warehouse re-validation; expiry validation | unit | `uv run pytest tests/test_receipts.py -x -q` | ✅ extend | ⬜ pending |
| 02-T2 | 09-02 | 2 | WH-02, LOT-01 | T-09-05, T-09-06 | Chooser endpoint; zero-warehouses blocking hint; autoescape | integration | `uv run pytest tests/test_receipts.py -k "chooser or warehouse or zero" -x -q` | ✅ extend | ⬜ pending |
| 03-T1 | 09-03 | 2 | LOT-02, criterion 4 | T-09-07, T-09-08 | Per-line batch required; per-batch oversell aggregation | unit | `uv run pytest tests/test_sales.py -x -q` | ✅ extend | ⬜ pending |
| 03-T2 | 09-03 | 2 | LOT-02, LOT-04, WH-02 | T-09-07, T-09-10, T-09-11 | Picker 4 cols/D-07 order; array-drift; 422 re-echo; auto-select; row-id validation | integration | `uv run pytest tests/test_sales.py -k "picker or batch_pick or drift or echo or autoselect" -x -q` | ✅ extend | ⬜ pending |
| 03-T3 | 09-03 | 2 | criterion 4 | T-09-09 | confirm=1 zero-write re-check on per-batch oversell | integration | `uv run pytest tests/test_sales.py -k oversell -x -q` | ✅ extend | ⬜ pending |
| 04-T1 | 09-04 | 3 | LOT-05, criterion 4 | T-09-12, T-09-14 | Write-off scalar batch required; per-batch over-removal | unit + integration | `uv run pytest tests/test_writeoffs.py -x -q` | ✅ extend | ⬜ pending |
| 04-T2 | 09-04 | 3 | LOT-05, criterion 4 | T-09-13, T-09-14 | Correction count diff vs batch qty; over-removal warn | unit + integration | `uv run pytest tests/test_corrections.py -x -q` | ✅ extend | ⬜ pending |
| 05-T1 | 09-05 | 4 | LOT-05 | T-09-17 | Return batch inheritance + legacy lazy-create (server-resolved) | unit | `uv run pytest tests/test_returns.py -x -q` | ✅ extend | ⬜ pending |
| 05-T2 | 09-05 | 4 | criterion 5 | T-09-18 | /history legacy label at read time (no ledger rewrite) | integration | `uv run pytest tests/test_history.py -x -q` | ✅ extend | ⬜ pending |
| 05-T3 | 09-05 | 4 | LOT-05 | T-09-16 | D-12 mandatory guard flip; full-suite sweep | unit + full sweep | `uv run pytest tests/test_ledger.py -x -q && uv run pytest -q` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_batches.py` (NEW, Plan 09-01) — Batch model (no deleted_at), `open_batches` NULLS-LAST ordering (LOT-01/LOT-03), `compute_batch_stock`/`rebuild_stock` invariant incl. NULL bucket, dual projection + ownership guard, and the migration-replay test (run 0008 against a temp DB seeded with pre-batch ops incl. a ≤0-stock product; assert legacy batches, quantities from ledger SUM, and both `operations_no_%` triggers survive — LOT-05/criterion 5)
- [ ] `tests/conftest.py` (Plan 09-01) — `warehouse` fixture (+ seeded-default-id option), `batch` fixture; `stocked_product` updated to create its batch and pass `batch_id` to `record_operation` so both projections agree
- [ ] Signature-change sweep (distributed across plans, closed by Plan 09-05's guard flip) — every existing test calling `record_operation`/`register_sale`/`register_writeoff`/`register_correction`/`register_return` or POSTing those forms gains batch wiring: test_ledger, test_sales, test_writeoffs, test_corrections, test_returns, test_receipts, test_smoke, test_history. batch_id stays OPTIONAL at the write path through Plans 01-04 (suite green at every wave boundary); Plan 09-05 flips the mandatory D-12 guard once all five services already pass a batch (RESEARCH Pitfall 1: guard never split from callers into a red wave)
- [ ] Array-drift test (Plan 09-03, RESEARCH Pitfall 2) — basket add/delete rows out of order → each op's batch attribution matches its own line

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Batch picker interaction in a real browser (radio select, price oob fill, single-batch auto-select note) | LOT-02 | HTMX swap/oob behavior with typed-value guards needs a real DOM | Open /sales, enter a code with 2+ batches, verify the 4-column table appears in D-07 order, pick a batch, verify the batch price fills the line and the hidden `batch_id[]` posts |
| Receipt "top up vs new batch" chooser + zero-warehouses hint | D-01, D-02 | HTMX chooser + radio show/hide (disabled toggling) needs a real DOM; verify `hx-on:change` single-colon toggle fires (RESEARCH A1) | Open /receipts, enter a code with existing batches in a warehouse → chooser forces an explicit choice; with all warehouses deleted the blocking «Нет активных складов» hint replaces the chooser |
| Correction current-qty hint oob-refresh + over-removal warn | Pitfall 7, criterion 4 | oob swap of `#current-qty-hint` on batch pick needs a real DOM | Open /corrections, pick a batch → hint shows «Остаток в партии: {qty}»; count/remove beyond it → warn-but-allow «В партии не хватает остатка», confirm to save |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
