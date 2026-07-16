---
phase: 19-products-page-rebuild
verified: 2026-07-16T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 19: Products Page Rebuild Verification Report

**Phase Goal:** The products page reads as a stock list the operator can scan by code, not a flat per-batch dump with a redundant add path.
**Verified:** 2026-07-16
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Product list shows one row per product code carrying the total quantity summed across all of that code's batches | ✓ VERIFIED | `Product.code` has a partial unique index among active rows (`app/models.py:135-142`, `uq_products_code_active`), so one `Product` row = one active code. `Product.quantity` is a "cached projection of SUM(operations.qty_delta)" (`app/models.py:168`), rendered in `<td class="num">{{ product.quantity }}</td>` (`product_rows.html:58`). Test `test_web_products_list_shows_quantity_column` asserts `<td class="num">8</td>` for `stocked_product` (quantity=8). |
| 2 | Operator can see each code's individual batches, each with its own expiry date and batch name | ✓ VERIFIED | `batches_for_products()` (`app/services/batches.py:37-53`) groups open batches by `product_id`, wired via `batches_by_id` context key (`app/routes/products.py:54,81`). Template renders a collapsed `<details><summary>Партии (N)</summary>` with a nested table of `Срок годности`/`Партия`/`Остаток` per batch, NULL-guarded to `—` (`product_rows.html:71-98`). Tests: `test_web_products_list_shows_batch_breakdown_when_batches_exist`, `test_web_products_list_no_batch_breakdown_when_no_batches` both pass. |
| 3 | Product list shows each product's category and can be filtered by category (unchanged, regression-guarded) | ✓ VERIFIED | Category column/filter code untouched in `product_rows.html:27,42-45,57`. `uv run pytest tests/test_catalog.py -q -k category` → 5 passed. |
| 4 | The "Добавить товар" button is gone from the product list (page CTA and empty-state), and delete renders as a text link rather than a button | ✓ VERIFIED | `products_list.html` has no `page-actions`/add-button markup (9→6 lines, CTA removed). Empty-state in `product_rows.html:107-111` links to `/receipts/new` instead. Delete control is `<a href="#" class="link-danger" hx-post=...>` (`product_rows.html:63`), no `<button class="danger">` remains. Tests `test_web_products_list_has_no_add_button`, `test_web_products_new_still_reachable_after_button_removal`, `test_web_products_delete_control_is_link_not_button` all pass. |
| 5 | Existing pagination, filtering, and sorting on the product list keep working against the new grouped rows | ✓ VERIFIED | `_products_context()` (`app/routes/products.py:36-82`) preserves every pre-existing return key, adds only `batches_by_id`. Full suite: 720 passed (711 baseline + 9 new), `tests/test_pagination.py` 8/8 passed. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/batches.py` | `batches_for_products(session, product_ids)` — batched, non-N+1, grouped by product_id | ✓ VERIFIED | Present at lines 37-53; single `IN(...)` query, `defaultdict(list)` grouping, same D-07 ordering as `open_batches`. Wired: imported and called in `app/routes/products.py:14,54`. |
| `app/routes/products.py` | `_products_context()` carries `batches_by_id` | ✓ VERIFIED | Line 81, added without disturbing any pre-existing key (verified against plan's interface listing). |
| `app/templates/partials/product_rows.html` | Кол-во column, collapsed batch breakout, text-link delete | ✓ VERIFIED | `<th class="num">Кол-во</th>` (line 28), `<td class="num">{{ product.quantity }}</td>` (line 58), `<details>` breakout (lines 71-98), `a.link-danger` delete link (line 63). |
| `app/templates/pages/products_list.html` | Add-product CTA removed | ✓ VERIFIED | File reduced to 6 lines; no `page-actions`/add-button markup remains. |
| `app/static/style.css` | `.link-danger` destructive text-link rule reusing `#b91c1c` | ✓ VERIFIED | Lines 306-311: `a.link-danger { color: #b91c1c; }` / `:hover { color: #7f1414; }`, matches the existing `button.danger` token, no new color role introduced. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `app/routes/products.py` | `app/services/batches.py` | `batches_for_products(session, product_ids)` call in `_products_context()` | ✓ WIRED | Line 54: `batches_by_id = batches_for_products(session, product_ids)`. |
| `product_rows.html` | `batches_by_id` context key | `batches_by_id.get(product.id, [])` | ✓ WIRED | Line 71. |
| `product_rows.html` | `POST /products/{id}/quick-delete` | `hx-post` on `<a class="link-danger">` | ✓ WIRED | Line 63: `hx-post="/products/{{ product.id }}/quick-delete?page={{ page }}{{ extra_qs }}"`, `href="#"` (never a real URL). Route exists at `app/routes/products.py:104`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| New `batches_for_products` tests pass | `uv run pytest tests/test_batches.py -q -k batches_for_products` | 3 passed (verified via full suite run, function content confirmed at tests/test_batches.py:161-203) | ✓ PASS |
| New product-list tests pass | `uv run pytest tests/test_catalog.py -q -k "quantity_column or batch_breakdown"` | Confirmed via full suite (720 passed total) | ✓ PASS |
| Full regression gate ≥711 baseline + 9 new | `uv run pytest -q` | 720 passed, 3 warnings (pre-existing, unrelated to this phase) in 125.52s | ✓ PASS |
| Category filter regression | `uv run pytest tests/test_catalog.py -q -k category` | 5 passed | ✓ PASS |
| Pagination regression | `uv run pytest tests/test_pagination.py -q` | 8 passed | ✓ PASS |
| Lint clean on touched files | `uv run ruff check` | 9 pre-existing errors, none in files modified by this phase's new code (the 2 hits inside `app/routes/products.py:133` and `tests/test_catalog.py:1175` are pre-existing lines untouched by this plan — confirmed by reading the flagged lines) | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROD-01 | 19-01-PLAN.md | "Добавить товар" button removed from product list | ✓ SATISFIED | CTA removed from `products_list.html` and empty-state in `product_rows.html`; `/products/new` still reachable (regression guard test passes). REQUIREMENTS.md marked `[x]`. |
| PROD-02 | 19-01-PLAN.md | Product-list delete action is a text link, not a button | ✓ SATISFIED | `<a class="link-danger">` replaces `<button class="danger">`; no `<button` with the quick-delete target remains. REQUIREMENTS.md marked `[x]`. |
| PROD-03 | 19-01-PLAN.md | Product list groups rows by code, showing total quantity summed across batches | ✓ SATISFIED | One row per active `Product.code` (unique index), `Кол-во` column renders `product.quantity` (cached SUM of ledger deltas). REQUIREMENTS.md marked `[x]`. |
| PROD-04 | 19-01-PLAN.md | Individual batches remain visible with expiry/name within a grouped code | ✓ SATISFIED | Collapsed `<details>` batch breakout per product, NULL-guarded fields. REQUIREMENTS.md marked `[x]`. |
| PROD-08 | 19-01-PLAN.md | Category display + filter unchanged | ✓ SATISFIED | Category column/filter code untouched; regression tests green. REQUIREMENTS.md marked `[x]`. |

No orphaned requirements — REQUIREMENTS.md's Phase 19 mapping (line 167: `PROD-01..04, PROD-08`) matches exactly the 5 IDs declared in the plan's frontmatter.

### Anti-Patterns Found

None. Scanned all 5 modified source files (`app/services/batches.py`, `app/routes/products.py`, `app/templates/partials/product_rows.html`, `app/templates/pages/products_list.html`, `app/static/style.css`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub-copy phrases — zero matches. The only `placeholder` hits are legitimate HTML `placeholder="Фильтр…"` attributes on pre-existing filter inputs, not stub markers.

### Human Verification Required

None. All truths are verifiable via code inspection and automated tests; no visual/UX judgment calls are outstanding for this phase (UI-SPEC's copywriting and interaction decisions were followed verbatim and are test-covered).

### Gaps Summary

No gaps. All 5 observable truths verified, all 5 artifacts present/substantive/wired, all 3 key links wired, full regression suite green at 720 passed (711 baseline + 9 new, zero failures), `ruff check` clean on every line this phase touched, all 5 requirement IDs (PROD-01, PROD-02, PROD-03, PROD-04, PROD-08) satisfied and correctly marked complete in REQUIREMENTS.md with no orphaned IDs for this phase.

---

_Verified: 2026-07-16_
_Verifier: Claude (gsd-verifier)_
