---
phase: 4
slug: sales-customers
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-09
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `04-RESEARCH.md` § Validation Architecture. The per-task rows
> below are keyed by requirement because plan/task IDs are assigned during
> planning; the executor maps each task to its requirement row.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (installed, dev group) + httpx TestClient |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=.) |
| **Quick run command** | `uv run pytest tests/test_sales.py tests/test_customers.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~10–25 seconds (file-based tmp SQLite; prior phases run in seconds) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_sales.py tests/test_customers.py -x -q` (plus `uv run ruff check .`)
- **After every plan wave:** Run `uv run pytest -q`
- **Before `/gsd-verify-work`:** Full suite green + `ruff check` + `ruff format --check`
- **Max feedback latency:** ~25 seconds

---

## Requirements → Test Map

| Requirement | Behavior (observable signal) | Threat Ref | Test Type | Automated Command | File @ Wave 0 |
|-------------|------------------------------|------------|-----------|-------------------|---------------|
| SAL-01 | Basket writes N `sale` ops (`qty_delta<0`); `Product.quantity` and `compute_stock()` both drop by summed qty | — | unit | `uv run pytest tests/test_sales.py -k stock -x` | ❌ new |
| SAL-01 | Empty basket cannot be finalized (RU error, 0 ledger writes) | T-4-05 (input) | unit | `uv run pytest tests/test_sales.py -k empty_basket -x` | ❌ new |
| SAL-01 | Whole basket commits in ONE transaction (simulated mid-error ⇒ 0 committed ops) | — | unit | `uv run pytest tests/test_sales.py -k one_transaction -x` | ❌ new |
| SAL-02 | Entered price overrides card `sale_cents`; snapshot = entered `unit_price_cents` | T-4-04 (money) | unit | `uv run pytest tests/test_sales.py -k price_override -x` | ❌ new |
| SAL-03 | Sale links `customer_id`; walk-in (`customer=""` ⇒ `customer_id IS NULL`) also valid | — | unit | `uv run pytest tests/test_sales.py -k customer_link -x` | ❌ new |
| SAL-04 | Oversell ⇒ warning partial + «Продать всё равно», **0 writes**; `confirm=1` re-POST writes and allows negative stock | — | web | `uv run pytest tests/test_sales.py -k oversell -x` | ❌ new |
| SAL-05 | `unit_cost_cents` frozen from card at write; later card price change does NOT alter the op | T-4-04 | unit | `uv run pytest tests/test_sales.py -k snapshot -x` | ❌ new |
| SAL-05 (D-12) | NULL card cost ⇒ op cost NULL, sale NOT blocked; empty price ⇒ RU error, 0 writes | T-4-05 | unit | `uv run pytest tests/test_sales.py -k null_cost -x` | ❌ new |
| CST-01 | Create/edit customer; lowercase shadow maintained; RU validation | T-4-01 (XSS) | unit | `uv run pytest tests/test_customers.py -k crud -x` | ❌ new |
| CST-01 | Cyrillic autocomplete via lowercase shadow, capped | T-4-02 (SQLi) | unit | `uv run pytest tests/test_customers.py -k search -x` | ❌ new |
| CST-02 | Purchase history shows product, date, qty, unit price for that customer only | T-4-01 | unit | `uv run pytest tests/test_customers.py -k history -x` | ❌ new |
| CST-02 | History reads frozen `unit_price_cents`, not current card price | — | unit | `uv run pytest tests/test_customers.py -k history_frozen -x` | ❌ new |
| — (invariant) | Ledger still append-only after migration 0004 (`sale_id` add did NOT drop triggers) | T-4-03 (tamper) | unit | `uv run pytest tests/test_ledger.py -k append_only -x` | ⚠️ extend existing |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — the executor stamps status per task commit.*

---

## Wave 0 Requirements

- [ ] `tests/test_sales.py` — RED stubs for SAL-01..05 (service + web slice)
- [ ] `tests/test_customers.py` — RED stubs for CST-01/02 (service + web slice)
- [ ] `tests/conftest.py` — add a `customer` fixture and a `stocked_product` fixture (existing `product` has `quantity=0`; oversell/decrement tests need positive stock — seed via `record_operation(type_="receipt", qty_delta=N)`)
- [ ] Extend `tests/test_ledger.py` — assert `record_operation(..., sale_id=...)` sets the column AND that `operations` remains append-only after migration 0004

*(Framework already installed — no install gap.)*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Focus lands on «Код» after adding a basket line without a click | SAL-01/D-02 | DOM focus not observable via TestClient | add a line → type immediately; characters land in «Код» |
| Lookup never overwrites a price typed during the debounce flight | SAL-02/D-02 | in-flight HTMX swap race needs a real browser | type a price, then a known code fast; typed price survives |
| «Продать всё равно» confirm flow end-to-end in browser | SAL-04/D-08 | full HTMX warn→confirm cycle with live DOM | oversell a line → warning shows → click confirm → sale writes, stock goes negative |

All checks run at end-of-phase UAT (workflow.human_verify_mode = end-of-phase; no in-plan checkpoints).

---

## Validation Sign-Off

- [x] All requirements have an automated verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (per-req map is dense)
- [x] Wave 0 covers all MISSING references (test_sales.py, test_customers.py, conftest fixtures, ledger extend)
- [x] No watch-mode flags
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-09
