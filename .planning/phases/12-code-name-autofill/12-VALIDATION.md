---
phase: 12
slug: code-name-autofill
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-13
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x [VERIFIED: codebase — `pyproject.toml` dev dependency-group] |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| **Quick run command** | `uv run pytest tests/test_pricing_feature.py tests/test_receipts.py tests/test_sales.py tests/test_dictionary.py tests/test_mobile_receipts.py tests/test_mobile_sales.py tests/test_mobile_transfers.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~15 seconds (quick), full suite similar order of magnitude — single-file SQLite, no network |

---

## Sampling Rate

- **After every task commit:** Run the relevant single test file from the quick run command above
- **After every plan wave:** Run `uv run pytest tests/test_pricing_feature.py tests/test_receipts.py tests/test_sales.py tests/test_dictionary.py tests/test_mobile_receipts.py tests/test_mobile_sales.py tests/test_mobile_transfers.py`
- **Before `/gsd-verify-work`:** Full suite (`uv run pytest`) must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | TBD | 0 | PRICE-04 | V5 | `lookup_prefill()` `source=="catalog"` branch never fills `sale` from CatalogPrice (D-02) | unit/integration | `uv run pytest tests/test_receipts.py -k lookup -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | TBD | 1 | SAL-06 | V5 | `/sales/search-name` reuses `search_products()` (parameterized query, no raw SQL) | integration | `uv run pytest tests/test_sales.py -k lookup -x` (+ new dropdown test) | ❌ W0 | ⬜ pending |
| 12-03-01 | TBD | 1 | PRICE-04 | — | Mobile receipt wizard surfaces fetched name/price (D-06/D-12) | integration | `uv run pytest tests/test_mobile_receipts.py -x` | ✅ | ⬜ pending |
| 12-04-01 | TBD | 1 | SAL-06 | — | Mobile sales wizard surfaces fetched name (D-13) | integration | `uv run pytest tests/test_mobile_sales.py -x` | ✅ | ⬜ pending |
| 12-05-01 | TBD | 1 | — | — | Mobile transfers wizard surfaces fetched name (D-14) | integration | `uv run pytest tests/test_mobile_transfers.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_receipts.py` — add cases for `lookup_prefill()`'s new `source=="catalog"` branch (D-01/D-02/D-03): CatalogPrice-only match, Dictionary-only match, both-present match, neither-present (still None), and the `sale` field NEVER filling from CatalogPrice (D-02 regression guard)
- [ ] `tests/test_mobile_receipts.py` — add case for D-06 price forwarding from step 2 into step 3's rendered value attributes, and D-12's visible code/name readout on step 3
- [ ] `tests/test_sales.py` (or a new `tests/test_sales_search.py`) — new `/sales/search-name` route: 3-char threshold (D-10), ranked results via `search_products`, click-fills both code+name (D-11)
- [ ] `tests/test_mobile_sales.py` — add case asserting the fetched `name` (already returned by `lookup_prefill`) now renders as visible text on `sale_step_batch.html`/`sale_step_qty_price.html` (D-13)
- [ ] `tests/test_mobile_transfers.py` — add case asserting the fetched `name` (already returned by `lookup_prefill`) now renders as visible text starting at the batch step through `transfers_step_dest.html` (D-14)

No new test framework or fixture infrastructure needed — all gaps are new test FUNCTIONS in existing, already-passing test files.

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification via the pytest suite above.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
