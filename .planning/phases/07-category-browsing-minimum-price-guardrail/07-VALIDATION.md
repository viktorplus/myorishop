---
phase: 7
slug: category-browsing-minimum-price-guardrail
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-10
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.* [VERIFIED: pyproject.toml `[dependency-groups] dev`] |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| **Quick run command** | `uv run pytest tests/test_catalog.py tests/test_sales.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_catalog.py tests/test_sales.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-xx | TBD | TBD | CAT-01 | — | Active products grouped by category, alphabetical, "Без категории" last, none hidden | unit (service) | `uv run pytest tests/test_catalog.py -k products_by_category -x` | ❌ W0 | ⬜ pending |
| 07-01-xx | TBD | TBD | CAT-01 | — | `/categories` page renders all groups, only active products, edit link works | web/integration | `uv run pytest tests/test_catalog.py -k web_categories -x` | ❌ W0 | ⬜ pending |
| 07-02-xx | TBD | TBD | PRICE-01 | V5 Input Validation | Product form saves/round-trips `min_sale_cents` including explicit `0` | unit (service) | `uv run pytest tests/test_catalog.py -k min_sale -x` | ❌ W0 | ⬜ pending |
| 07-02-xx | TBD | TBD | PRICE-01 | V5 Input Validation | Sale below minimum without confirm -> warning, zero writes; `is not None` guard (NULL and 0 both correctly handled) | unit (service) | `uv run pytest tests/test_sales.py -k below_minimum -x` | ❌ W0 | ⬜ pending |
| 07-02-xx | TBD | TBD | PRICE-01 | — | Boundary: price exactly equal to minimum passes silently (strict `<`) | unit (service) | `uv run pytest tests/test_sales.py -k min_price_boundary -x` | ❌ W0 | ⬜ pending |
| 07-02-xx | TBD | TBD | PRICE-01 | — | Basket tripping BOTH oversell and price-floor shows both warnings in one response (CONTEXT D-11) | unit (service) + web | `uv run pytest tests/test_sales.py -k both_warnings -x` | ❌ W0 | ⬜ pending |
| 07-xx-xx | TBD | TBD | — | Stored XSS via product name on new `/categories` page | Jinja2 autoescape only, never `\|safe` on `product.name` in `categories.html` | manual review | code review during task acceptance | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs, Plan, and Wave columns to be filled by the planner once tasks are assigned.*

---

## Wave 0 Requirements

- [ ] `tests/test_catalog.py` — add test functions for `products_by_category` grouping/ordering and `min_sale_cents` create/update round-trip (including explicit `0`)
- [ ] `tests/test_sales.py` — add test functions for the price-floor check (no-confirm warns, confirm writes, boundary at exact minimum, combined-with-oversell case)
- [ ] `alembic/versions/0006_product_min_sale_price.py` — new migration; `tests/conftest.py`'s `engine` fixture uses `Base.metadata.create_all` (not Alembic), so the new column is automatically picked up by tests once added to `models.py` — no test-fixture change needed, but a manual/CI check that `alembic upgrade head` on a copy of a pre-Phase-7 DB succeeds is still warranted
- No new test framework or fixture infrastructure needed — `tests/conftest.py`'s existing `session`/`client`/`product`/`stocked_product` fixtures cover every scenario this phase needs

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `alembic upgrade head` succeeds on a copy of a pre-Phase-7 DB | CAT-01, PRICE-01 | Alembic migration path is not exercised by the pytest fixture (which uses `Base.metadata.create_all` directly) | Copy `myorishop.db`, run `uv run alembic upgrade head` against the copy, confirm no error and new `min_sale_cents` column exists |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
