---
phase: 07-category-browsing-minimum-price-guardrail
verified: 2026-07-11T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "Operators are protected from accidentally underselling (phase goal, broad reading) — including the trivial case of an obviously invalid negative sale price"
  gaps_remaining: []
  regressions: []
---

# Phase 7: Category Browsing & Minimum-Price Guardrail Verification Report

**Phase Goal:** Operators can browse stock grouped by category and are protected from accidentally underselling a product below a set floor price
**Verified:** 2026-07-11T00:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (07-04-PLAN.md / 07-04-SUMMARY.md, gap_closure: true)

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can open "Товары на складе" page and see all active products grouped under their category/rubric | VERIFIED (regression) | `app/routes/categories.py` GET /categories renders `pages/categories.html`; `products_by_category()` groups active products by category. Quick regression: `uv run pytest tests/test_catalog.py -k "migration_0006 or products_by_category or web_categories or web_nav_has_categories_link"` → 8 passed. No changes to this code path since prior verification. |
| 2 | Operator can set, or leave unset, an optional minimum sale price on a product's card | VERIFIED (regression) | `min_sale_cents` column, form field, `parse_optional_cents` wiring unchanged since prior verification. No regression expected or found. |
| 3 | Selling below a set minimum price shows a warning and requires explicit confirmation before the sale is recorded (same warn-but-allow pattern as oversell) | VERIFIED (regression) | `register_sale`'s `below_minimum` computation (lines 152-175, unmoved by this gap-closure edit) still gated by `confirm != "1"`. Quick regression: `uv run pytest tests/test_sales.py -k "below_minimum or both_reported or web_sale_below_minimum or web_sale_both_warnings"` → 6 passed. |
| 4 | A product with no minimum price never triggers the warning, and an explicit 0 is respected rather than treated as unset | VERIFIED (regression) | `below_minimum` comprehension still requires `min_sale_cents is not None`; unaffected by this plan's edit (which lives earlier in the same function, on the price-parse block, not the below_minimum block). Same regression run as #3 covers boundary/zero-entered tests. |
| 5 (goal-level, derived) | Operators are protected from accidentally underselling — including the base case of an obviously invalid (negative) sale price, not just prices below a configured floor | **VERIFIED — gap closed** | `app/services/sales.py` lines 99-115: the per-line price `try/except` around `to_cents(price_text)` now has an `else` clause: `if price_cents < 0: errors[f"price-{i}"] = catalog.PRICE_ERROR; price_cents = None`. Confirmed present at the exact call site (not inside `to_cents`, which still returns `-500` for `"-5"` unmodified — verified via `python -c "from app.core import to_cents; print(to_cents('-5'))"` → `-500`, proving the guard is a call-site addition, not a change to the shared low-level parser). Three new regression tests independently run and pass: `test_negative_price_rejected_without_min_sale_configured` (product's `min_sale_cents is None`, negative price rejected, zero writes), `test_negative_price_rejected_with_min_sale_configured` (same guard fires even when a floor IS set, proving independence from `below_minimum`), `test_web_sale_negative_price_rejected` (`POST /sales` with negative `price[]` → HTTP 422, `catalog.PRICE_ERROR` in body, zero `Operation` rows written). All 3 pass: `uv run pytest tests/test_sales.py -k "negative_price"` → 3 passed. |

**Score:** 5/5 truths verified. The gap from the initial verification (CR-01: negative sale price silently written to the ledger with zero warnings when no minimum-price floor is configured — the default state for every product) is closed.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/catalog.py::products_by_category` | Groups active products by category, alphabetical, uncategorized last | VERIFIED (regression) | Unchanged since prior verification |
| `app/routes/categories.py` | `GET /categories` thin route | VERIFIED (regression) | Unchanged |
| `app/templates/pages/categories.html` | Category-grouped listing page | VERIFIED (regression) | Unchanged |
| `app/templates/base.html` nav link | `/categories` link from every page | VERIFIED (regression) | Unchanged |
| `app/main.py` router registration | `categories.router` included | VERIFIED (regression) | Unchanged |
| `alembic/versions/0006_product_min_sale_price.py` | Nullable `min_sale_cents` column migration | VERIFIED (regression) | Unchanged |
| `app/models.py` `Product.min_sale_cents` | Nullable int column | VERIFIED (regression) | Unchanged |
| `app/templates/pages/product_form.html` `min_sale` field | Positioned between sale and catalog fields | VERIFIED (regression) | Unchanged |
| `app/services/sales.py` `below_minimum` check | Per-line price-floor check inside `register_sale` | VERIFIED (regression) | Lines shifted (152→ same relative position after the new 9-line guard block), logic unchanged, `is not None` guard, strict `<` |
| `app/templates/partials/sale_price_warning.html` | Price-floor warning partial | VERIFIED (regression) | Unchanged |
| `app/services/sales.py` price parser negative-value guard | Sale-line price rejects negative amounts, reusing `catalog.PRICE_ERROR` | **VERIFIED — new** | Lines 99-115: `else` clause added to existing `try/except`, contains `price_cents < 0` check exactly per plan's `must_haves.artifacts.contains` spec. `grep -c "price_cents < 0" app/services/sales.py` → 1 match, at the correct call site. |
| `tests/test_sales.py` 3 new regression tests | Cover unset-floor, set-floor, and web-level 422 cases | **VERIFIED — new** | All 3 present, all 3 pass individually and as part of the full 247-test suite |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/routes/categories.py` | `app/services/catalog.py` | `products_by_category(session)` call | WIRED (regression) | Unchanged |
| `app/templates/base.html` | `app/routes/categories.py` | `href="/categories"` | WIRED (regression) | Unchanged |
| `app/main.py` | `app/routes/categories.py` | `app.include_router(categories.router)` | WIRED (regression) | Unchanged |
| `app/templates/pages/product_form.html` | `app/routes/products.py` | `name="min_sale"` form field | WIRED (regression) | Unchanged |
| `app/routes/products.py` | `app/services/catalog.py` | `min_sale_raw` kwarg | WIRED (regression) | Unchanged |
| `app/services/catalog.py` | `app/templates/partials/price_history.html` | `field == "min_sale_cents"` label branch | WIRED (regression) | Unchanged |
| `app/templates/partials/sale_form.html` | `app/templates/partials/sale_price_warning.html` | `{% if below_minimum %}` include | WIRED (regression) | Unchanged |
| `app/routes/sales.py` | `app/services/sales.py` | `result.get("below_minimum")` | WIRED (regression) | Unchanged |
| `app/services/sales.py` (register_sale) | `app/services/catalog.py` | `catalog.PRICE_ERROR` reused for the new negative-price guard | **WIRED — new** | Confirmed at `app/services/sales.py:114`: `errors[f"price-{i}"] = catalog.PRICE_ERROR` — same constant already imported via `from app.services import catalog`, no new error path introduced |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| New negative-price regression tests (gap closure) | `uv run pytest tests/test_sales.py -k "negative_price" -v` | 3 passed (`test_negative_price_rejected_without_min_sale_configured`, `test_negative_price_rejected_with_min_sale_configured`, `test_web_sale_negative_price_rejected`) | PASS |
| CAT-01 + PRICE-01 targeted tests (regression) | `uv run pytest tests/test_catalog.py -k "migration_0006 or products_by_category or web_categories or web_nav_has_categories_link"` | 8 passed | PASS |
| PRICE-01 sale-time guardrail tests (regression) | `uv run pytest tests/test_sales.py -k "below_minimum or both_reported or web_sale_below_minimum or web_sale_both_warnings"` | 6 passed | PASS |
| Full workspace suite (single run) | `uv run pytest -q` | 247 passed, 0 failed | PASS |
| `to_cents` itself unchanged (guard is call-site, not shared-parser) | `python -c "from app.core import to_cents; print(to_cents('-5'))"` | `-500` (still negative, no exception) — confirms the fix does not alter the shared low-level parser's contract, per plan's explicit acceptance criterion | PASS |
| No debt markers introduced | `grep -n -E "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER" app/services/sales.py tests/test_sales.py` | No matches | PASS |
| Lint on modified files | `uv run ruff check app/services/sales.py tests/test_sales.py` | 1 pre-existing `I001` (import order) in `tests/test_sales.py:20`, confirmed pre-existing via `deferred-items.md` (present before this plan's edits); `app/services/sales.py` clean | PASS (no new lint issues) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CAT-01 | 07-01-PLAN.md | "Товары на складе" page groups products by category/rubric | SATISFIED | /categories route + template + service function, regression-verified above. **Note:** `.planning/REQUIREMENTS.md` line 18/78 still shows the checkbox unchecked (`[ ]`) and status "Pending" for CAT-01 — this is a documentation-bookkeeping staleness (the requirements tracker was not updated when Phase 7's CAT-01 slice completed), not a code/functionality gap. Flagged as an informational anti-pattern below; does not affect this phase's pass/fail determination since the underlying implementation and tests are independently verified. |
| PRICE-01 | 07-02-PLAN.md, 07-03-PLAN.md, 07-04-PLAN.md | Optional minimum sale price per product; selling below it warns but allows override | SATISFIED — fully, including the gap-closure edge case | min_sale_cents column, form field, audit trail (07-02) + sale-time warn-but-allow check (07-03) + negative-price guard closing the CR-01 gap (07-04), all verified above. `.planning/REQUIREMENTS.md` line 31/85 correctly shows PRICE-01 checked and "Complete". |

No orphaned requirements: both CAT-01 and PRICE-01 are declared in plan frontmatter (07-01 through 07-04) and both appear in `.planning/REQUIREMENTS.md`'s traceability table mapped to Phase 7.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `.planning/REQUIREMENTS.md` | 18, 78 | CAT-01 checkbox/status not updated to complete despite the requirement being fully implemented and test-covered since 07-01 | ℹ️ Info | Documentation staleness only; does not affect code behavior. Recommend a follow-up doc update to check `[x]` and mark "Complete" for CAT-01, consistent with PRICE-01's entry. |
| `tests/test_sales.py` | 20 | Pre-existing `ruff check` I001 (import block unsorted) | ℹ️ Info | Documented in `deferred-items.md` as pre-existing, confirmed via prior-commit diff; not introduced by this or the gap-closure plan; out of scope per executor's stated boundary. |
| `app/services/catalog.py` | 416-435 (`products_by_category`) | Category grouping key is case-sensitive raw string | ⚠️ Warning (carried forward from prior verification, WR-01) | Unchanged by this gap-closure plan; does not block any of the 4 literal success criteria. |
| `app/services/sales.py` | 129-175 (unmoved logic, shifted line numbers) | Oversell and price-floor warnings share a single `confirm=1` flag | ℹ️ Info (carried forward, WR-03) | Documented as intentional design, unaffected by this plan. |

No `TBD`/`FIXME`/`XXX` unresolved debt markers found in either file this gap-closure plan modified (`app/services/sales.py`, `tests/test_sales.py`).

### Human Verification Required

None. All observable truths and artifacts are programmatically verifiable via grep/tests; no visual, real-time, or external-service behavior in this phase's scope requires human judgment beyond what automated tests already cover.

### Gaps Summary

The one gap from the initial verification (07-VERIFICATION.md, `gaps_found`, 4/5) is closed. `07-04-PLAN.md` added an `else` clause to `register_sale`'s existing per-line price `try/except` in `app/services/sales.py` (lines 99-115): after a successful `to_cents` parse, `price_cents < 0` now sets `errors[f"price-{i}"] = catalog.PRICE_ERROR` and resets `price_cents = None` — mirroring `catalog.parse_optional_cents`'s existing negative-amount convention verbatim, reusing the same error constant, introducing no new error path.

Independently re-verified (not just trusting 07-04-SUMMARY.md's claims):
- Read the actual diff in `app/services/sales.py` — the guard is present at exactly the described location, gated correctly (does not touch the `PRICE_REQUIRED_ERROR` or `ValueError` branches).
- Ran the 3 new regression tests directly (`uv run pytest tests/test_sales.py -k "negative_price"`) — all 3 pass, independent of this verifier's own process (not just re-reading the SUMMARY's reported pass count).
- Ran the full workspace suite once (`uv run pytest -q`) — 247 passed, 0 failed, matching the SUMMARY's claim, confirming no regressions were introduced anywhere else in the codebase.
- Confirmed the guard fires **independent of `min_sale_cents`** — both the unset-floor and explicitly-set-floor test cases reject the negative price with the identical `catalog.PRICE_ERROR`, closing the exact scenario CR-01 flagged (the default no-floor state, which is every product until an operator opts in per D-06).
- Confirmed `to_cents` itself is unmodified (still returns `-500` for `"-5"`) — the fix is a call-site addition in `register_sale`, not a change to the shared low-level parser, per the plan's explicit acceptance criterion (avoids any risk of an unintended behavior change elsewhere `to_cents` is used).
- Ran quick regression checks on the previously-passing CAT-01 and PRICE-01 test groups — no regressions found.

One informational (non-blocking) documentation item was newly surfaced during this re-verification: `.planning/REQUIREMENTS.md`'s CAT-01 entry (lines 18, 78) still shows an unchecked checkbox and "Pending" status despite CAT-01 being fully implemented and test-verified since the initial verification. This is a requirements-tracker bookkeeping gap, not a code-functionality gap — it does not affect the phase's status determination but is worth a quick follow-up doc fix.

Phase 7's goal — "Operators can browse stock grouped by category and are protected from accidentally underselling a product below a set floor price" — is now fully achieved, including the broader "protected from accidentally underselling" framing that the initial verification correctly flagged as incompletely covered by the four literal success criteria alone.

---

_Verified: 2026-07-11T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
