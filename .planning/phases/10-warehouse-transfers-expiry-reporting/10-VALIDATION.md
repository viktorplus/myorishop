---
phase: 10
slug: warehouse-transfers-expiry-reporting
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-12
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `10-RESEARCH.md` → ## Validation Architecture (all rows `[VERIFIED]` against Phase 8/9 code).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* + FastAPI `TestClient` (httpx 0.28.*) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| **Quick run command** | `uv run pytest tests/test_transfers.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds (full suite) |

Shared fixtures in `tests/conftest.py`: `session`, `product`, `warehouse`, `batch`, `stocked_product`, `client` (TestClient with `get_session` overridden, startup backup disabled). A transfer test needs a *stocked source batch in a known warehouse* + a *second active warehouse* — extend `stocked_product`/`batch` or build inline.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_transfers.py -x` (new work) or the touched file's tests
- **After every plan wave:** Run `uv run pytest` (full suite green — transfers touch the shared ledger write path)
- **Before `/gsd-verify-work`:** Full suite must be green + `ruff check .` clean
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

> Requirement → test map from research. Task IDs bind during planning; each `<task>` inherits the matching row's `Automated Command` as its `<automated>` verify.

| Req | Behavior | Test Type | Automated Command | File Exists |
|-----|----------|-----------|-------------------|-------------|
| WH-03 | Transfer writes exactly two `transfer` ops (source −qty, dest +qty) in one transaction | unit | `uv run pytest tests/test_transfers.py::test_transfer_writes_two_rows -x` | ❌ W0 |
| WH-03 | `Product.quantity` unchanged (net-zero); source `Batch.quantity` −qty; dest `Batch.quantity` +qty | unit | `uv run pytest tests/test_transfers.py::test_transfer_projections -x` | ❌ W0 |
| WH-03 | Dest batch inherits `price_cents`/`expiry`/`comment`/`location`, differs only in `warehouse_id`, `is_legacy=0`, new id | unit | `uv run pytest tests/test_transfers.py::test_dest_batch_inherits_history -x` | ❌ W0 |
| WH-03 | Full transfer drives source batch to `quantity=0` (drops out of `open_batches`) | unit | `uv run pytest tests/test_transfers.py::test_full_transfer_empties_source -x` | ❌ W0 |
| WH-03 | Over-quantity: `confirm != "1"` returns oversell payload with ZERO writes; `confirm="1"` writes | unit | `uv run pytest tests/test_transfers.py::test_over_qty_confirm_gate -x` | ❌ W0 |
| WH-03 | Same-warehouse transfer rejected with RU error | unit | `uv run pytest tests/test_transfers.py::test_reject_same_warehouse -x` | ❌ W0 |
| WH-03 | Untrusted `batch_id` (other product) / inactive dest warehouse rejected | unit | `uv run pytest tests/test_transfers.py::test_reject_tampered_ids -x` | ❌ W0 |
| WH-03 | `rebuild_stock()` invariant still holds after a transfer | unit | `uv run pytest tests/test_transfers.py::test_rebuild_invariant_after_transfer -x` | ❌ W0 |
| WH-03 | Transfer appears in `/history` with «Перемещение» label, both directions | integration | `uv run pytest tests/test_transfers.py::test_transfer_in_history -x` | ❌ W0 |
| WH-03 | `GET /transfers`, `/transfers/lookup`, `/transfers/batch-pick`, `POST /transfers` HTTP happy paths | integration | `uv run pytest tests/test_transfers.py -k route -x` | ❌ W0 |
| LOT-06 | `expiring_batches()` returns only `quantity>0` AND non-NULL expiry, earliest first, legacy excluded | unit | `uv run pytest tests/test_batches.py::test_expiring_batches_filter_and_order -x` | ⚠️ extend |
| LOT-06 | `GET /reports/expiry` renders rows; expired (`expiry < today`) carries marker; empty state shown when none | integration | `uv run pytest tests/test_reports.py::test_expiry_report_page -x` | ⚠️ extend |

*Status legend: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_transfers.py` — NEW file covering all WH-03 rows above
- [ ] `tests/test_batches.py` — ADD `expiring_batches()` cases (file exists)
- [ ] `tests/test_reports.py` — ADD `/reports/expiry` route cases (file exists)
- [ ] Fixture: a stocked source batch + a second active warehouse (extend `conftest.py` or build inline in `test_transfers.py`)
- [ ] Framework install: none — pytest/httpx already in the dev group

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual expired-marker styling on `/reports/expiry` (muted/red badge «просрочено») | LOT-06 | CSS/visual rendering not asserted by a route test beyond marker presence | Open `/reports/expiry`, confirm a batch with `expiry < today` shows the marker and stays in the same earliest-first list |
| HTMX partial-swap UX on `/transfers` (code lookup → batch picker → dest select) | WH-03 | Interaction feel across HTMX swaps | Enter a product code, pick a batch, pick a destination warehouse, submit; confirm the oversell warning re-POST flow works |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (`tests/test_transfers.py`, `expiring_batches` + `/reports/expiry` cases)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
