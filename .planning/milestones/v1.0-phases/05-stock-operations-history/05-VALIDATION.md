---
phase: 5
slug: stock-operations-history
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `05-RESEARCH.md` § Validation Architecture. The per-requirement
> rows below are keyed by requirement because plan/task IDs are assigned during
> planning; the executor maps each task to its requirement row.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (installed, dev group) + FastAPI `TestClient` via httpx |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=.) |
| **Quick run command** | `uv run pytest tests/test_writeoffs.py tests/test_returns.py tests/test_corrections.py tests/test_history.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10–25 seconds (file-based tmp SQLite; prior phases run in seconds) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q` (plus `uv run ruff check .`)
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite green + `ruff check` + `ruff format --check`
- **Max feedback latency:** ~25 seconds

---

## Requirements → Test Map

| Requirement | Behavior (observable signal) | Threat Ref | Test Type | Automated Command | File @ Wave 0 |
|-------------|------------------------------|------------|-----------|-------------------|---------------|
| OPS-01 | Write-off writes a `writeoff` op (`qty_delta<0`); `Product.quantity` and `compute_stock()` both drop by qty; reason persisted in `payload` `{reason_code,note}` | output-encoding (note XSS) | unit (service) | `uv run pytest tests/test_writeoffs.py -k stock_and_reason -x` | ❌ new |
| OPS-01 | Invalid/absent `reason_code` rejected server-side against the allow-list (not just the `<select>`) | input allow-list | unit | `uv run pytest tests/test_writeoffs.py -k reason_allowlist -x` | ❌ new |
| OPS-01 | Write-off form renders + submits: code→name autofill (204), RU 422 on bad input, 0 writes on error | input validation | web | `uv run pytest tests/test_writeoffs.py -k form -x` | ❌ new |
| OPS-01 | Oversell on write-off warns-but-allows (reuse Phase 4 pattern): warning partial + confirm, 0 writes until confirm; stock may go to/through zero | business-logic | web | `uv run pytest tests/test_writeoffs.py -k oversell -x` | ❌ new |
| OPS-02 | Return writes a `return` op (`qty_delta>0`); stock increases; `sale_id` + frozen `unit_price_cents`/`unit_cost_cents` copied from the origin sale line | frozen-snapshot (SAL-05) | unit | `uv run pytest tests/test_returns.py -k link_and_freeze -x` | ❌ new |
| OPS-02 | Over-return rejected; partial return respects remaining returnable = sold − already-returned per sale_id+product_id | business-logic over-return | unit | `uv run pytest tests/test_returns.py -k returnable_cap -x` | ❌ new |
| OPS-02 | Return entry from a recent-sales / purchase-history line wires the origin op (sale_id, product, frozen price) into the return | input validation | web | `uv run pytest tests/test_returns.py -k entry_point -x` | ❌ new |
| OPS-03 | Counted mode writes `qty_delta = counted − current_quantity`; delta mode writes the entered delta as-is | input validation | unit | `uv run pytest tests/test_corrections.py -k count_vs_delta -x` | ❌ new |
| OPS-03 | Zero-net correction is a no-op — no row written, graceful RU rejection | input validation | unit | `uv run pytest tests/test_corrections.py -k zero_net_noop -x` | ❌ new |
| OPS-03 | Correction is always a `correction` op via `record_operation`; `products.quantity` never edited directly (ledger==cache) | append-only tamper | unit | `uv run pytest tests/test_corrections.py -k ledger_equals_cache -x` | ❌ new |
| OPS-03 (D-12) | Old walking-skeleton `POST /ops` correction removed/migrated — exactly one correction path, no duplicate | — | web | `uv run pytest tests/test_corrections.py -k ops_replaced -x` | ❌ new |
| OPS-04 | `/history` returns all ops newest-first with product + reason + signed qty + who + when | output-encoding (XSS) | web | `uv run pytest tests/test_history.py -k rows -x` | ❌ new |
| OPS-04 | Type filter and product filter each narrow results (portable ORM, no raw SQL) | input validation | web | `uv run pytest tests/test_history.py -k filters -x` | ❌ new |
| OPS-04 | Pagination returns a bounded page (LIMIT/OFFSET or "load more"), never the whole ledger unbounded | resource abuse | web | `uv run pytest tests/test_history.py -k pagination -x` | ❌ new |
| — (invariant) | Append-only preserved: `return`/`correction` are NEW rows; UPDATE/DELETE on `operations` still ABORT; no migration drops triggers | ledger falsification | unit | `uv run pytest tests/test_ledger.py -k append_only -x` | ⚠️ extend existing |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — the executor stamps status per task commit.*

---

## Wave 0 Requirements

- [ ] `tests/test_writeoffs.py` — RED stubs for OPS-01 (stock delta, reason payload, allow-list, form + autofill, oversell warn/confirm)
- [ ] `tests/test_returns.py` — RED stubs for OPS-02 (stock delta, sale_id link, frozen price/cost, returnable cap, entry point)
- [ ] `tests/test_corrections.py` — RED stubs for OPS-03 (count/delta arithmetic, zero-net no-op, ledger==cache, `POST /ops` replacement)
- [ ] `tests/test_history.py` — RED stubs for OPS-04 (ordering, type + product filters, pagination bound, RU labels + reason column, XSS-safe render)
- [ ] Extend `tests/test_ledger.py` — assert append-only holds after any Phase 5 change (returns/corrections are new rows; triggers intact)

*(Framework already installed — no install gap. Existing `session`, `product`, `stocked_product`, `customer`, `client` fixtures in `tests/conftest.py` cover it; a return test builds a sale inline via `register_sale`/`record_operation(type_="sale", ...)`.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Focus lands on «Код» after opening the write-off form / adding a line without a click | OPS-01 | DOM focus not observable via TestClient | open write-off form → type immediately; characters land in «Код» |
| Lookup never overwrites a value typed during the debounce flight | OPS-01 | in-flight HTMX swap race needs a real browser | type in a field, then a known code fast; typed value survives the 204 autofill |
| Write-off oversell warn→«Списать всё равно» confirm cycle end-to-end | OPS-01 | full HTMX warn→confirm cycle with live DOM | write off more than in stock → warning shows → confirm → op writes, stock goes to/through zero |
| «Показать ещё» appends the next page without reloading the table | OPS-04 | beforeend HTMX append + scroll position needs a real browser | scroll `/history` → click «Показать ещё» → next 50 rows append in place |

All checks run at end-of-phase UAT (workflow.human_verify_mode = end-of-phase; no in-plan checkpoints).

---

## Validation Sign-Off

- [x] All requirements have an automated verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (per-req map is dense)
- [x] Wave 0 covers all MISSING references (test_writeoffs.py, test_returns.py, test_corrections.py, test_history.py, ledger extend)
- [x] No watch-mode flags
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-09
