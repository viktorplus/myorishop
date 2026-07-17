---
phase: 22
slug: sales-page-rebuild
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-17
bound: 2026-07-17
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `22-RESEARCH.md` § Validation Architecture (commands measured, not estimated).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* (`pyproject.toml:20`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| **Quick run command** | `uv run pytest tests/test_sales.py tests/test_mobile_sales.py tests/test_sales_search.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~24 seconds quick (87 tests) · ~169 seconds full (808 tests) — both measured this session |

> **Every command must be prefixed `uv run`.** Bare `python -m pytest` fails with
> `ModuleNotFoundError: No module named 'sqlalchemy'` — deps live in the uv-managed `.venv`.

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_sales.py tests/test_mobile_sales.py tests/test_sales_search.py -q`
- **After every plan wave:** Run `uv run pytest -q` **plus** `uv run ruff check . && uv run ruff format --check .`
- **Before `/gsd-verify-work`:** Full suite must be green (≥808 baseline + new tests)
- **Max feedback latency:** 24 seconds (quick) — comfortably under the 30s budget

**Baseline captured 2026-07-17:** `uv run pytest -q` → `808 passed, 3 warnings in 169.23s`.
The 3 warnings are pre-existing `SAWarning`s in `test_returns.py:316` — not a gate.

---

## Wave Structure

| Wave | Plans | Test files written |
|------|-------|--------------------|
| 1 | 22-01, 22-02 | `test_sales.py` (22-01) · `test_sales_total.py`, `test_mobile_sales.py`, `test_core.py` (22-02) |
| 2 | 22-04, 22-05 | `test_sales_total.py` (22-04, markers) · `test_sales.py` (22-05, markers) |
| 3 | 22-03, 22-06 | `test_sales.py` (22-03, final markers) · `test_mobile_sales.py` (22-06, markers) |
| 4 | 22-07 | `test_mobile_sales.py` (22-07, final markers) |

**File-ownership invariant:** no two plans in the same wave write the same file. `test_sales.py` is
serialized 22-01 → 22-05 → 22-03; `test_mobile_sales.py` is serialized 22-02 → 22-06 → 22-07.

**xfail retirement ledger** (strict xfail — an unremoved marker XPASSes and FAILS the suite):

| File | Markers | Removed by |
|------|---------|-----------|
| `test_sales.py` | 13 | 10 by 22-05 (wave 2) · 3 by 22-03 (wave 3) |
| `test_sales_total.py` | 6 | 6 by 22-04 (wave 2) |
| `test_mobile_sales.py` | 5 | 1 by 22-06 (wave 3) · 4 by 22-07 (wave 4) |

Zero xfail / zero xpass across the suite is the phase gate, asserted in **22-07-T3**.

---

## Per-Task Verification Map

> Columns bound by the planner 2026-07-17. **Task ID** is the task that makes the row GREEN (the
> implementing task), not the task that authors the test — Wave-0 authorship is recorded in the
> **File Exists** column.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 22-04-T2 | 22-04 | 2 | SALE-01 | — | N/A (regression guard — already shipped) | web | `uv run pytest tests/test_sales.py::test_web_sale_page_renders_form -x` | ✅ (:570) extended by 22-01-T3 | ⬜ pending |
| 22-04-T2 | 22-04 | 2 | SALE-02 | — | N/A | web | `uv run pytest tests/test_sales_total.py -x` | ❌ W0 → 22-02-T1 | ⬜ pending |
| 22-04-T2 | 22-04 | 2 | SALE-02 | — | N/A | web | `uv run pytest tests/test_sales_total.py -k script -x` | ❌ W0 → 22-02-T1 | ⬜ pending |
| 22-04-T2 | 22-04 | 2 | SALE-02 | — | 422 re-render still carries `#sale-total` | web | `uv run pytest tests/test_sales_total.py -k rerender -x` | ❌ W0 → 22-02-T1 | ⬜ pending |
| 22-04-T2 | 22-04 | 2 | SALE-02 | — | Delete button carries `recalcSaleTotal` hook (desktop row partial) | web | `uv run pytest tests/test_sales_total.py -k delete_hook -x` | ❌ W0 → 22-02-T1 | ⬜ pending |
| 22-02-T3 | 22-02 | 1 | SALE-02 / D-09 | — | Parse parity: JS accept-set vs `to_cents` | unit | `uv run pytest tests/test_core.py -k to_cents -x` | ✅ extended by 22-02-T3 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-03 | — | 3 radios render, «Существующий» checked (D-02) | web | `uv run pytest tests/test_sales.py -k customer_mode_default -x` | ❌ W0 → 22-01-T1 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-03 | — | `customer_mode=new` renders the 3-field block | web | `uv run pytest tests/test_sales.py -k customer_mode_new -x` | ❌ W0 → 22-01-T1 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-03 / D-03 | — | Round-trip preserves both modes' values | web | `uv run pytest tests/test_sales.py -k customer_mode_roundtrip -x` | ❌ W0 → 22-01-T1 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-03 | T-22-01 | Unknown `customer_mode` → allow-list fallback, never echoed raw (allow-list lands in 22-05-T1) | web | `uv run pytest tests/test_sales.py -k customer_mode_allowlist -x` | ❌ W0 → 22-01-T1 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-04 | — | Autocomplete matches name, surname, consultant number | web | `uv run pytest tests/test_sales.py::test_web_customer_search_returns_rows -x` | ✅ (:749) extended by 22-01-T2 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-04 | — | Picking a match fills chip, hides search | web | `uv run pytest tests/test_sales.py -k picker_data_attrs -x` | ❌ W0 → 22-01-T2 | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | SALE-04 | T-22-10 | **422 re-render keeps the chip visible** (verified live defect) | web | `uv run pytest tests/test_sales.py -k chip_survives_422 -x` | ❌ W0 → 22-01-T2 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-05 | — | Exactly 3 fields, no Phase-21 profile fields (D-07) | web | `uv run pytest tests/test_sales.py -k new_customer_field_set -x` | ❌ W0 → 22-01-T2 | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | SALE-05 / D-10 | T-22-11 | «Новый» + blank `customer_id` + filled fields → 422, never a silent walk-in | web | `uv run pytest tests/test_sales.py -k new_customer_requires_button -x` | ❌ W0 → 22-01-T2 | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-05 | — | Quick-create returns a chip carrying the new id | web | `uv run pytest tests/test_sales.py::test_web_customer_quick_create_returns_chip -x` | ✅ (:756) | ⬜ pending |
| 22-05-T2 | 22-05 | 2 | SALE-06 | — | Anonymous mode renders no extra fields | web | `uv run pytest tests/test_sales.py -k customer_mode_anon -x` | ❌ W0 → 22-01-T1 | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | SALE-06 | — | Anonymous submit writes `Sale.customer_id IS NULL` | unit | `uv run pytest tests/test_sales.py::test_customer_link_walkin_customer_id_null -x` | ✅ (:255) | ⬜ pending |
| 22-03-T2 | 22-03 | 3 | SALE-07 | — | Recent sales renders buyer first+last name | web | `uv run pytest tests/test_sales.py -k recent_sales_customer_column -x` | ❌ W0 → 22-01-T3 | ⬜ pending |
| 22-03-T2 | 22-03 | 3 | SALE-07 / D-06 | — | Walk-in renders muted «Розница», not blank | web | `uv run pytest tests/test_sales.py -k recent_sales_retail_label -x` | ❌ W0 → 22-01-T3 | ⬜ pending |
| 22-03-T1 | 22-03 | 3 | SALE-07 | — | `recent_sales` outerjoin does not drop walk-in rows | unit | `uv run pytest tests/test_sales.py -k recent_sales_includes_walkin -x` | ❌ W0 → 22-01-T3 | ⬜ pending |
| 22-03-T2 | 22-03 | 3 | SALE-07 | — | `/returns` recent-sales include still renders | web | `uv run pytest tests/test_returns.py -q` | ✅ existing | ⬜ pending |
| 22-07-T2 | 22-07 | 4 | D-04 | — | Mobile Корзина renders the 3-way selector | web | `uv run pytest tests/test_mobile_sales.py -k customer_selector -x` | ❌ W0 → 22-02-T2 | ⬜ pending |
| 22-07-T1 | 22-07 | 4 | D-04 | T-22-04 | `POST /m/sales` with `customer_id` links the sale | web | `uv run pytest tests/test_mobile_sales.py -k mobile_links_customer -x` | ❌ W0 → 22-02-T2 | ⬜ pending |
| 22-07-T1 | 22-07 | 4 | D-04 | — | `POST /m/sales` without `customer_id` still writes a walk-in | web | `uv run pytest tests/test_mobile_sales.py -k mobile_walkin -x` | ❌ W0 → 22-02-T2 | ⬜ pending |
| 22-06-T3 | 22-06 | 3 | D-04 | T-22-14 | Mobile selector swap does not wipe `code_acc[]` | web | `uv run pytest tests/test_mobile_sales.py -k acc_survives -x` | ❌ W0 → 22-02-T2 | ⬜ pending |
| 22-07-T3 | 22-07 | 4 | D-11 | T-22-14 | Batch-card tap preserves the accumulated basket (`hx-include`) | web | `uv run pytest tests/test_mobile_sales.py -k batch_card_preserves_basket -x` | ❌ W0 → 22-02-T2 | ⬜ pending |
| 22-07-T3 | 22-07 | 4 | D-11 | T-22-16 | Sibling wizards unregressed by the shared-partial change | web | `uv run pytest tests/test_mobile_writeoffs.py tests/test_mobile_receipts.py tests/test_mobile_corrections.py -q` | ✅ existing | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | Criterion 5 | — | Oversell warning still fires, confirm still writes | web | `uv run pytest tests/test_sales.py::test_web_sale_oversell_shows_warning_and_confirm_writes -x` | ✅ (:615) | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | Criterion 5 | — | Below-minimum still fires, confirm still writes | web | `uv run pytest tests/test_sales.py::test_web_sale_below_minimum_shows_warning_and_confirm_writes -x` | ✅ (:648) | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | Criterion 5 | — | Both warnings stack; one confirm resolves both | web | `uv run pytest tests/test_sales.py::test_web_sale_both_warnings_stack_and_single_confirm_resolves_both -x` | ✅ (:684) | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | Criterion 5 | — | Batch selection required; missing pick → 422 | web | `uv run pytest tests/test_sales.py::test_web_sale_missing_batch_pick_returns_422 -x` | ✅ (:1081) | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | Criterion 5 | — | Batch pick survives the 422 re-echo | web | `uv run pytest tests/test_sales.py::test_web_sale_422_re_echoes_picked_batch -x` | ✅ (:1041) | ⬜ pending |
| 22-05-T3 | 22-05 | 2 | Criterion 5 | — | Cash credit written for the basket | unit | `uv run pytest tests/test_finance.py -q` | ✅ existing | ⬜ pending |
| 22-04-T2 | 22-04 | 2 | Regression | — | Colour cue still stamped on the rebuilt form (Phase 18) | web | `uv run pytest tests/test_sales.py -k data_ref_cents -q` | ✅ (:899, :933, :956) | ⬜ pending |
| 22-04-T2 | 22-04 | 2 | Regression | — | Name→code search dropdown still wired | web | `uv run pytest tests/test_sales_search.py -q` | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

> Criterion-5 and Regression rows are asserted by **more than one** task (22-04-T2 and 22-05-T3 both
> run the criterion-5 tripwires; 22-05-T3 also re-runs `test_sales_search.py`). The **Task ID** column
> names the primary owner — the task whose code change could plausibly break the row.

---

## Wave 0 Requirements

- [ ] `tests/test_sales_total.py` — **new file** (22-02-T1); SALE-02 markup/wiring stubs (`#sale-total` present, script tag on both shells, 422 re-render carries it, delete hook present)
- [ ] `tests/test_sales.py` — extend (22-01-T1/T2/T3), **13 strict-xfail tests total** (matches the retirement ledger above): SALE-03 (5 tests incl. the D-03 round-trip), SALE-04 (2 — chip-survives-422 + picker attrs), SALE-05 (3 — field-set + both sides of the D-10 422 guard), SALE-07 (3 tests). Plus one **non-xfail** extension of the shipped `test_web_sale_page_renders_form` (:570) as the SALE-01 regression guard — an extension, not a new test, and never marked xfail.
- [ ] `tests/test_mobile_sales.py` — extend (22-02-T2): D-04 (4 tests) + D-11 (batch-card basket preservation)
- [ ] `tests/test_core.py` — extend `to_cents` coverage (22-02-T3) to pin the accept-set boundaries the JS mirrors (`'1 000'` and `'12abc'` → ValueError; `'12.505'` → 1251)
- [ ] Framework install: **none needed** — pytest/httpx/TestClient already present and green
- [ ] Shared fixtures: **none needed** — `client`, `session`, `customer`, `stocked_product`, `mobile_client_factory` in `tests/conftest.py` already cover every case (`customer` seeds «Анна Иванова» / consultant `12345` with `search_lc` set — exactly what SALE-04's three-way autocomplete test needs)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live total sums correctly as lines are filled in | SALE-02 | No JS runtime in the suite — no jsdom/Playwright, and CLAUDE.md forbids an npm toolchain. Server-side tests assert *markup + wiring presence*; the arithmetic itself has no automated harness. Mitigation: the parser is pure and could be ported to a Python mirror test if drift is ever suspected. | Open `/sales/new`, add 2+ lines, type qty/price into each; confirm the amount and unit count under the basket update on every keystroke and match a hand calculation. Enter `12,50` (RU comma) and confirm it parses. |
| «итог неполный» marker appears for an invalid/incomplete row | SALE-02 / D-09 | Same — client-side rendering with no JS test runtime. | With one valid line, type `abc` into another line's price; confirm the «итог неполный» marker shows and the partial sum is not presented as final. |
| Radio switch preserves already-typed data, felt end-to-end | SALE-03 / D-03 | Server tests cover the round-trip contract, but the *perceived* no-data-loss behavior (focus, in-flight typing, swap guards interacting) needs a real browser. | Type into «Новый» fields → switch to «Существующий» → pick a customer → switch back to «Новый»; confirm the typed values are still there and nothing was silently reset. |

> These three rows have **no automated coverage and no plan claims otherwise.** They are the phase's
> known sampling blind spot, accepted deliberately (an npm/jsdom toolchain is forbidden by CLAUDE.md
> §What NOT to Use). Do not "close" them by weakening a server-side test into a proxy assertion.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — all 19 tasks across 22-01..22-07 carry an `<automated>` command; every ❌ W0 reference is authored by 22-01/22-02 in wave 1
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — no task lacks one, so the gap is structurally zero
- [x] Wave 0 covers all MISSING references — every ❌ W0 row maps to a named 22-01/22-02 task above
- [x] No watch-mode flags — every command is a single-shot `uv run pytest`; no `--looponfail`, no `-f`
- [x] Feedback latency < 30s — 24s measured for the quick run (87 tests), under the 30s budget
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] Wave 0 executed (`wave_0_complete`) — **not yet true**; 22-01/22-02 have not run. Flips on wave-1 completion, not at planning time.

**Approval:** Planner-bound 2026-07-17 — task/plan/wave columns resolved, Nyquist gate green.
Awaiting execution; `status` flips to `verified` once the phase gate in 22-07-T3 reports 0 failed,
0 xfailed, 0 xpassed.
