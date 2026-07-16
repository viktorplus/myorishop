---
phase: 19
slug: products-page-rebuild
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-16
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (verified via `pyproject.toml` `[tool.pytest.ini_options]`) |
| **Config file** | `pyproject.toml` → `testpaths = ["tests"]`, `pythonpath = ["."]` |
| **Quick run command** | `uv run pytest tests/test_catalog.py -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~12s quick / ~126s full |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_catalog.py -q` (~12s) + `uv run ruff check`
- **After every plan wave:** Run `uv run pytest tests/test_catalog.py tests/test_batches.py tests/test_pagination.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green — **≥ 711 passed** (pre-phase-19 baseline, 2026-07-16); any drop below 711 is a regression
- **Max feedback latency:** ~12 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 0 | PROD-03 | V5 | N/A | unit | `uv run pytest tests/test_batches.py -q -k batches_for_products` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | PROD-03 | V5 | N/A | unit | `uv run pytest tests/test_catalog.py -q -k web_products` | ❌ W0 | ⬜ pending |
| 19-01-03 | 01 | 1 | PROD-04 | V5 (batch text fields — Jinja autoescape only, never `\|safe`) | Rendered batch name/comment/location fields must remain autoescaped | integration | `uv run pytest tests/test_catalog.py tests/test_batches.py -q` | ✅ (`open_batches` covered) / ❌ W0 (grouping+template) | ⬜ pending |
| 19-01-04 | 01 | 1 | PROD-01 | — | N/A | unit | `uv run pytest tests/test_catalog.py -q -k web_products` | ❌ W0 | ⬜ pending |
| 19-01-05 | 01 | 1 | PROD-02 | Tampering (delete-link must stay POST-only, no real `href` to the delete URL) | `<a>` triggers `hx-post`, never a bare `href` GET to the delete endpoint | integration | `uv run pytest tests/test_catalog.py -q -k quick_delete` | ✅ (existing quick-delete tests) / ❌ W0 (element-type assertion) | ⬜ pending |
| 19-01-06 | 01 | 1 | PROD-08 | V5 | N/A (no behavior change expected) | unit | `uv run pytest tests/test_catalog.py -q -k category` | ✅ already green | ⬜ pending |
| 19-01-07 | 01 | 2 | (regression) | — | N/A | integration | `uv run pytest tests/test_catalog.py tests/test_pagination.py -q` | ✅ existing suite | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs above are placeholders — the planner assigns final task IDs/waves; this table's requirement→test mapping is the binding contract.*

---

## Wave 0 Requirements

- [ ] `tests/test_batches.py` — new `batches_for_products(session, product_ids)` grouping function: empty-list input, multiple products, quantity-0 batches excluded, ordering matches `open_batches`
- [ ] `tests/test_catalog.py` — `/products` list renders `product.quantity` per row
- [ ] `tests/test_catalog.py` — `/products` list renders a batch's `expiry`/`name` when the product has open batches, and renders nothing extra when it has none
- [ ] `tests/test_catalog.py` — "Добавить товар" absent from `/products` response text; `/products/new` (GET) still returns 200 (regression guard for the retained entry point)
- [ ] `tests/test_catalog.py` — delete control is an `<a ... hx-post=".../quick-delete"...>`, not a `<button>`, on the `/products` list

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification per the Wave 0 gaps above.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
