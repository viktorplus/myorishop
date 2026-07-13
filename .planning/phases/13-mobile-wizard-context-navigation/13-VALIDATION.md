---
phase: 13
slug: mobile-wizard-context-navigation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-13
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.x (`pyproject.toml` `[dependency-groups] dev`) |
| **Config file** | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`) |
| **Quick run command** | `uv run pytest tests/test_mobile_writeoff.py tests/test_mobile_corrections.py tests/test_mobile_sales.py tests/test_mobile_receipts.py tests/test_mobile_transfers.py tests/test_mobile_search.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~10-20 seconds |

Existing test files already cover each wizard's happy path via `mobile_client_factory` (`tests/conftest.py`) but currently assert only text presence (e.g. `"Далее" in response.text`), not `hx-post`/`hx-include` attribute values or absence of `history.back()` — new assertions of that shape are needed for UI-03's regression coverage.

---

## Sampling Rate

- **After every task commit:** Run the relevant single `test_mobile_*.py` file's quick command above
- **After every plan wave:** Run `uv run pytest tests/test_mobile_*.py`
- **Before `/gsd-verify-work`:** Full suite (`uv run pytest`) must be green
- **Max feedback latency:** ~15 seconds

---

## Per-Task Verification Map

| Task ID | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-xx | UI-02 | Every intermediate wizard step renders `{{ code }}`/`{{ name }}`/`Склад:` as visible `<p>` text (not just hidden inputs) | unit | `uv run pytest tests/test_mobile_writeoff.py -k header -x` | ❌ W0 | ⬜ pending |
| 13-01-xx | UI-03 | Write-off's 3 steps no longer contain `history.back()`; every "Назад" button's `hx-post`/`hx-get` target matches its immediate predecessor's route | unit | `uv run pytest tests/test_mobile_writeoff.py tests/test_mobile_corrections.py -k back -x` | ❌ W0 | ⬜ pending |
| 13-01-xx | UI-04 | `sale_basket.html` contains `<p class="mobile-step-indicator">Корзина</p>` | unit | `uv run pytest tests/test_mobile_sales.py -k basket_step_indicator -x` | ❌ W0 | ⬜ pending |
| 13-01-xx | UI-05 | `search_product_detail.html` renders "Продать"/"Принять" links to `/m/sales?code=`/`/m/receipts?code=`; both `/m/sales` and `/m/receipts` GET accept and echo `?code=` | unit + integration | `uv run pytest tests/test_mobile_search.py tests/test_mobile_sales.py tests/test_mobile_receipts.py -k code_prefill -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — final Task IDs assigned by the planner.*

---

## Wave 0 Requirements

- [ ] New assertions in `tests/test_mobile_corrections.py` — cover per-step back-target fix (REQ UI-03)
- [ ] New assertions in `tests/test_mobile_writeoff.py` — cover shell migration + absence of `history.back()` (REQ UI-03)
- [ ] New assertions in `tests/test_mobile_sales.py` — cover basket step-indicator (REQ UI-04) and `?code=` prefill (REQ UI-05)
- [ ] New assertions in `tests/test_mobile_receipts.py` — cover `?code=` prefill (REQ UI-05) and header format alignment (REQ UI-02)
- [ ] New assertions in `tests/test_mobile_search.py` — cover quick-action link presence, always rendered regardless of stock (REQ UI-05)
- [ ] New assertions in `tests/test_mobile_transfers.py` — cover header format alignment only (REQ UI-02; no back-nav changes here)

*No new test framework/fixtures needed — `mobile_client_factory` (existing, `tests/conftest.py`) already supports every wizard's isolated router testing.*

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification via the existing `mobile_client_factory` test harness.*

---

## Security Notes (ASVS)

| ASVS Category | Applies | Note |
|---------------|---------|------|
| V5 Input Validation | Yes | `name`/`warehouse_name` threaded into new template contexts must stay display-only carry-forward — never re-used to bypass a service's own `code`-based product re-resolution. New warehouse-name lookups must derive from the already-validated batch object, not a raw client-supplied `warehouse_id`. |
| XSS via product/batch name | Yes | New `_wizard_header.html` partial must rely on Jinja2 autoescaping like every other template in this codebase — never apply `\|safe` to `{{ name }}` or `{{ warehouse_name }}`. |

Full threat detail: see `13-RESEARCH.md` → Security Domain section.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
