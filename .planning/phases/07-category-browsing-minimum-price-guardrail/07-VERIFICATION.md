---
phase: 07-category-browsing-minimum-price-guardrail
verified: 2026-07-10T22:15:00Z
status: gaps_found
score: 4/5 must-haves verified
overrides_applied: 0
gaps:
  - truth: "Operators are protected from accidentally underselling (phase goal, broad reading) — including the trivial case of an obviously invalid negative sale price"
    status: failed
    reason: "CR-01 (07-REVIEW.md, Critical, unresolved): app/services/sales.py's per-line sale price parser (register_sale, lines ~99-107) calls to_cents(price_text) with only a ValueError catch — no negative-value guard, unlike parse_optional_cents used everywhere else for money (cost/sale/catalog/min_sale all reject < 0). Independently confirmed: to_cents('-5') returns -500 with no exception. Because min_sale_cents defaults to NULL for every product until an operator explicitly sets a floor (D-06, this phase's own design), the below_minimum check (`line[\"product\"].min_sale_cents is not None and line[\"price_cents\"] < line[\"product\"].min_sale_cents`) is skipped entirely for the default (no-floor) state, so a negative price sails through with ZERO warnings and is written straight into the ledger as a negative sale line. This directly undermines the phase's stated goal of protection from underselling for the majority default case (every newly created product has no floor set), and corrupts profit/report totals with negative 'revenue'. No regression test exists for this case (confirmed: no 'negative' price test in tests/test_sales.py besides the unrelated oversell-allows-negative-STOCK test)."
    artifacts:
      - path: "app/services/sales.py"
        issue: "register_sale's inline price parser (lines ~99-107) accepts negative price_cents with no guard; only parse_optional_cents (app/services/catalog.py) rejects negatives, and register_sale does not reuse it for the sale-line price"
    missing:
      - "A negative-value guard on the sale-line price parse in register_sale, mirroring parse_optional_cents's `if cents < 0: errors[...] = PRICE_ERROR` pattern (per 07-REVIEW.md CR-01's suggested fix)"
      - "A regression test asserting a negative price[] value on POST /sales is rejected with zero writes, independent of whether min_sale_cents is set on the product"
---

# Phase 7: Category Browsing & Minimum-Price Guardrail Verification Report

**Phase Goal:** Operators can browse stock grouped by category and are protected from accidentally underselling a product below a set floor price
**Verified:** 2026-07-10T22:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can open "Товары на складе" page and see all active products grouped under their category/rubric | VERIFIED | `app/routes/categories.py` GET /categories renders `pages/categories.html`; `app/services/catalog.py::products_by_category()` groups active (`deleted_at IS NULL`) products by category, alphabetical, "Без категории" bucket appended last only when present. Nav link wired in `base.html:20`. Router registered in `app/main.py:10,42`. Tests: `test_web_categories_page_lists_groups_with_edit_link`, `test_web_categories_page_hides_deleted_products`, `test_web_categories_page_empty_state`, `test_web_nav_has_categories_link` — all pass. |
| 2 | Operator can set, or leave unset, an optional minimum sale price on a product's card | VERIFIED | Migration `0006_product_min_sale_price.py` adds nullable `min_sale_cents` Integer column (verified: `revision="0006"`, `down_revision="0005"`, plain `op.add_column`/`op.drop_column`). `Product.min_sale_cents: Mapped[int \| None]` in `app/models.py:103`. Form field `name="min_sale"` in `product_form.html:63-65`, positioned between "Цена продажи" and "Цена по каталогу" with "(необязательно)" hint, no default hint (D-07). `create_product`/`update_product` parse via `parse_optional_cents` (empty->NULL, negative rejected). Audited via `_PRICE_FIELDS` + `price_history.html`'s "Минимальная" label. Tests: `test_create_product_min_sale_cents_empty_is_none`, `test_web_create_product_with_min_sale_price_round_trips` — pass. |
| 3 | Selling below a set minimum price shows a warning and requires explicit confirmation before the sale is recorded (same warn-but-allow pattern as oversell) | VERIFIED | `register_sale` (`app/services/sales.py:152-175`) computes `below_minimum` per line, gated by `confirm != "1"`, returns zero writes until `confirm=1`; `sale_create` (`app/routes/sales.py:216`) widened guard `result.get("oversell") or result.get("below_minimum")`; new partial `sale_price_warning.html` mirrors `sale_oversell.html`'s confirm=1 re-POST mechanism exactly. Tests: `test_below_minimum_blocks_without_confirm`, `test_below_minimum_confirm_writes`, `test_web_sale_below_minimum_shows_warning_and_confirm_writes`, `test_oversell_and_below_minimum_both_reported_together`, `test_web_sale_both_warnings_stack_and_single_confirm_resolves_both` — all pass (stacked-warning scenario for D-11 verified). |
| 4 | A product with no minimum price never triggers the warning, and an explicit 0 is respected rather than treated as unset | VERIFIED | `below_minimum` comprehension requires `min_sale_cents is not None` (never a bare `or`), so `None` never warns at any entered price including 0. Explicit `min_sale_cents=0` is stored and compared normally (`0 < entered` etc., strict `<`). Tests: `test_min_sale_unset_never_warns_even_at_zero_entered_price`, `test_create_product_min_sale_cents_explicit_zero_is_stored_as_zero`, `test_web_create_product_min_sale_explicit_zero_round_trips`, `test_below_minimum_boundary_equal_price_passes_silently` (strict less-than at the boundary) — all pass. |
| 5 (goal-level, derived) | Operators are protected from accidentally underselling — including the base case of an obviously invalid (negative) sale price, not just prices below a configured floor | **FAILED** | See Gaps below — CR-01. Independently re-confirmed: `to_cents("-5")` returns `-500` (no exception); `register_sale`'s inline parser at `app/services/sales.py` lines ~99-107 has no negative guard; the `below_minimum` check only fires when `min_sale_cents is not None`, so for the DEFAULT state (every product, until an operator opts in to a floor) a negative price is written to the ledger with zero warnings of any kind. |

**Score:** 4/5 truths verified (the 4 literal ROADMAP-listed success criteria all pass; one goal-level truth derived from the broader phase-goal wording fails per the code-review's Critical finding)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/catalog.py::products_by_category` | Groups active products by category, alphabetical, uncategorized last | VERIFIED | Function present, matches plan spec exactly (lines 416-435) |
| `app/routes/categories.py` | `GET /categories` thin route | VERIFIED | Present, calls `products_by_category(session)`, renders template |
| `app/templates/pages/categories.html` | Category-grouped listing page | VERIFIED | "Товары на складе" h1, per-group h2/table, empty-state, "Изменить" edit link |
| `app/templates/base.html` nav link | `/categories` link from every page | VERIFIED | `href="/categories"` with active-class logic at line 20 |
| `app/main.py` router registration | `categories.router` included | VERIFIED | Import + `include_router` present |
| `alembic/versions/0006_product_min_sale_price.py` | Nullable `min_sale_cents` column migration | VERIFIED | `revision="0006"`, `down_revision="0005"`, plain add/drop column, no backfill |
| `app/models.py` `Product.min_sale_cents` | Nullable int column | VERIFIED | Line 103, `Mapped[int \| None]` |
| `app/templates/pages/product_form.html` `min_sale` field | Positioned between sale and catalog fields | VERIFIED | Lines 63-65, correct position and hint copy |
| `app/services/sales.py` `below_minimum` check | Per-line price-floor check inside `register_sale` | VERIFIED | Lines 152-175, per-line (not aggregated), `is not None` guard, strict `<` |
| `app/templates/partials/sale_price_warning.html` | Price-floor warning partial | VERIFIED | Mirrors `sale_oversell.html` structure, `confirm=1` re-POST |
| `app/services/sales.py` price parser (adjacent) | Sale-line price rejects invalid amounts | **STUB-LIKE GAP** | Rejects unparsable text (`ValueError`) but NOT negative amounts — see CR-01 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/routes/categories.py` | `app/services/catalog.py` | `products_by_category(session)` call | WIRED | Confirmed in route body |
| `app/templates/base.html` | `app/routes/categories.py` | `href="/categories"` | WIRED | Confirmed, active-class logic present |
| `app/main.py` | `app/routes/categories.py` | `app.include_router(categories.router)` | WIRED | Confirmed |
| `app/templates/pages/product_form.html` | `app/routes/products.py` | `name="min_sale"` form field | WIRED | Both `product_create`/`product_update` accept `min_sale: str = Form("")`, pass `min_sale_raw` to service |
| `app/routes/products.py` | `app/services/catalog.py` | `min_sale_raw` kwarg | WIRED | Confirmed in both create/update routes |
| `app/services/catalog.py` | `app/templates/partials/price_history.html` | `field == "min_sale_cents"` label branch | WIRED | Confirmed |
| `app/templates/partials/sale_form.html` | `app/templates/partials/sale_price_warning.html` | `{% if below_minimum %}` include | WIRED | Confirmed, positioned after oversell include |
| `app/routes/sales.py` | `app/services/sales.py` | `result.get("below_minimum")` | WIRED | Guard widened correctly; both keys always present in context dict |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CAT-01 + PRICE-01 targeted tests | `uv run pytest tests/test_catalog.py -k "migration_0006 or products_by_category or web_categories or web_nav_has_categories_link"` | 8 passed | PASS |
| PRICE-01 sale-time guardrail tests | `uv run pytest tests/test_sales.py -k "below_minimum or both_reported or web_sale_below_minimum or web_sale_both_warnings"` | 6 passed | PASS |
| Full workspace suite (single run) | `uv run pytest -q` | 244 passed, 0 failed | PASS |
| Negative price parses silently (CR-01 re-check) | `python -c "from app.core import to_cents; print(to_cents('-5'))"` | `-500`, no exception raised | CONFIRMS GAP |
| Regression test exists for negative sale price | `grep -n "negative" tests/test_sales.py` | Only `test_oversell_confirm_writes_negative_stock` (unrelated — negative STOCK after oversell confirm, not negative PRICE) | CONFIRMS GAP — no coverage |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CAT-01 | 07-01-PLAN.md | "Товары на складе" page groups products by category/rubric | SATISFIED | /categories route + template + service function, all verified above |
| PRICE-01 | 07-02-PLAN.md, 07-03-PLAN.md | Optional minimum sale price per product; selling below it warns but allows override | SATISFIED (for its literal scope) | min_sale_cents column, form field, audit trail (07-02) + sale-time warn-but-allow check (07-03), all verified above. Note: the adjacent CR-01 negative-price gap does not fall within PRICE-01's literal text (which only speaks to prices below an explicitly configured minimum) but affects the broader phase-goal framing — see gap above. |

No orphaned requirements: both CAT-01 and PRICE-01 are declared in plan frontmatter and both appear in `.planning/REQUIREMENTS.md`'s traceability table mapped to Phase 7.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/services/sales.py` | ~99-107 | Sale-line price parser has no negative-value guard (unlike `parse_optional_cents` used for every other money field) | 🛑 Blocker (data integrity, see CR-01 / gap above) | Negative "revenue" can be recorded on any product with no minimum price configured (the default state) |
| `app/services/catalog.py` | 416-435 (`products_by_category`) | Category grouping key is case-sensitive raw string (`p.category or ""`) — no normalization | ⚠️ Warning (07-REVIEW.md WR-01) | Visually-identical category names differing only in case render as separate `<h2>` groups; does not block CAT-01's stated success criteria but is a real UX quirk newly surfaced by this phase's structural grouping |
| `app/services/sales.py` | 129-175 | Oversell and price-floor warnings share a single `confirm=1` flag | ℹ️ Info (07-REVIEW.md WR-03) | Documented as intentional design (tested via `test_web_sale_both_warnings_stack_and_single_confirm_resolves_both`), not a defect against this phase's own success criteria |
| `app/services/receipts.py` | 57-58 | Quantity parsing lacks `isascii()` guard used elsewhere (WR-02) | ℹ️ Info | Pre-existing, out of this phase's file-modification scope per the plan, noted by reviewer for completeness only |

No `TBD`/`FIXME`/`XXX` unresolved debt markers found in any file this phase modified.

### Human Verification Required

None. All observable truths and artifacts are programmatically verifiable via grep/tests; no visual, real-time, or external-service behavior in this phase's scope requires human judgment beyond what automated tests already cover.

### Gaps Summary

Both literal ROADMAP success criteria sets — CAT-01 (category browsing) and PRICE-01 (minimum-price capture + sale-time warn-but-allow guardrail) — are fully and correctly implemented, tested (244/244 suite green), and wired end-to-end. No stubs, no orphaned artifacts, no broken key links were found in either slice.

However, the phase's own stated goal text is broader than the four enumerated success criteria: "...are protected from accidentally underselling a product below a set floor price." The already-documented code-review Critical finding (CR-01 in `07-REVIEW.md`) — independently re-confirmed in this verification — shows that `register_sale`'s sale-line price parser accepts negative values with zero validation, and because `min_sale_cents` is `NULL` by design for every product until an operator opts in (the default state this phase ships every product into), a negative price on ANY such product is written straight into the ledger with **no warning of any kind** — not the oversell warning, not the new price-floor warning, nothing. This is a real, unresolved, and verified data-integrity gap that undercuts the "protected from accidentally underselling" framing of the phase goal for the majority-default case, even though it does not violate any of the four specific enumerated success criteria (which only speak to behavior relative to an explicitly-configured minimum).

This is flagged as a gap rather than silently passed, per the explicit adversarial-verification instruction to weigh CR-01 against the phase's stated goal. It is distinct from, and does not diminish, the fact that CAT-01 and PRICE-01's literal scope is fully delivered.

---

_Verified: 2026-07-10T22:15:00Z_
_Verifier: Claude (gsd-verifier)_
