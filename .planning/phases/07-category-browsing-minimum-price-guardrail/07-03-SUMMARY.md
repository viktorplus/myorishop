---
phase: 07-category-browsing-minimum-price-guardrail
plan: 03
subsystem: sales
tags: [fastapi, jinja2, htmx, sales-guardrail, warn-but-allow]

# Dependency graph
requires:
  - phase: 07-02
    provides: "Product.min_sale_cents nullable column, settable through the product form"
provides:
  - "register_sale's below_minimum per-line price-floor check, sharing the confirm=1 gate with the existing oversell check"
  - "app/routes/sales.py's widened (oversell or below_minimum) result guard in sale_create"
  - "app/templates/partials/sale_price_warning.html partial"
  - "sale_form.html's {% if below_minimum %} include, stacking with the oversell block"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Warn-but-allow guardrail #2 built by mirroring an existing one exactly (oversell -> below_minimum): same confirm=1 flag, same zero-writes contract, same partial structure, same route guard shape"
    - "Both independent per-basket checks computed before any early return, then merged into one result dict, so neither check's warning can be silently dropped when both fire in the same request"

key-files:
  created:
    - app/templates/partials/sale_price_warning.html
  modified:
    - app/services/sales.py
    - app/routes/sales.py
    - app/templates/partials/sale_form.html
    - tests/test_sales.py

key-decisions:
  - "below_minimum is per-line (not aggregated like the oversell qty sum) per D-09 — the same product entered at two different prices is checked independently on each line"
  - "oversold and below_minimum are both computed unconditionally before the `if oversold or below_minimum:` gate, so a basket tripping both surfaces both warnings in one response instead of an early oversell-only return silently swallowing the price-floor check (Pitfall 2 / T-07-07)"

requirements-completed: [PRICE-01]

# Metrics
duration: 10min
completed: 2026-07-10
---

# Phase 07 Plan 03: Sale-Time Minimum-Price Guardrail Enforcement Summary

**register_sale gains a per-line below_minimum check that mirrors the existing oversell warn-but-allow pattern exactly (same confirm=1 gate, same zero-writes contract), wired through sale_create and a new sale_price_warning.html partial so both checks can fire and stack in one response.**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2 completed
- **Files modified:** 4 (1 created: `sale_price_warning.html`; 3 modified: `sales.py` service, `sales.py` route, `sale_form.html`, `test_sales.py`)

## Accomplishments

- `register_sale` (app/services/sales.py) computes a `below_minimum` list comprehension alongside the existing `oversold` aggregate check — per-line, `is not None`-guarded (D-06), strict less-than (D-10) — and both checks are evaluated before any return so a basket tripping both surfaces `result["oversell"]` AND `result["below_minimum"]` in the same call (D-11, Pitfall 2 / T-07-07)
- `app/routes/sales.py`'s `sale_create` guard widened from `result.get("oversell")` to `(result.get("oversell") or result.get("below_minimum"))` — closing the gap where a below-minimum-only basket would have fallen through to the success-write branch
- New `app/templates/partials/sale_price_warning.html` mirrors `sale_oversell.html`'s exact structure: `.error-block` wrapper, per-line paragraph, the same `confirm=1` "Продать всё равно" button (form-associated re-POST, no new confirm parameter) and a client-side-only "Вернуться к корзине" dismiss button; product names render autoescaped only (T-07-08)
- `sale_form.html` includes the new partial right after the existing oversell block, so both warning blocks stack in the same response when a basket trips both checks
- 7 new tests added to `tests/test_sales.py`: 5 service-level (`test_below_minimum_blocks_without_confirm`, `test_below_minimum_confirm_writes`, `test_below_minimum_boundary_equal_price_passes_silently`, `test_min_sale_unset_never_warns_even_at_zero_entered_price`, `test_oversell_and_below_minimum_both_reported_together`) and 2 web-level (`test_web_sale_below_minimum_shows_warning_and_confirm_writes`, `test_web_sale_both_warnings_stack_and_single_confirm_resolves_both` — the CONTEXT D-11 manual UAT scenario, now automated)

## Task Commits

1. **Task 1: register_sale() per-line price-floor check**
   - `2e530e3` feat(07-03): per-line minimum-price check in register_sale
2. **Task 2: Route wiring, warning partial, sale_form include**
   - `fecee53` feat(07-03): route wiring, price-floor warning partial, sale_form include

## Files Created/Modified

- `app/services/sales.py` - `below_minimum` list comprehension inside `register_sale`'s `if confirm != "1":` block; `oversold`/`below_minimum` merged into a single `result` dict before returning
- `app/routes/sales.py` - `sale_create`'s result guard widened to `(result.get("oversell") or result.get("below_minimum"))`; context dict passes both keys (falsy/`None` when absent)
- `app/templates/partials/sale_price_warning.html` - new partial, mirrors `sale_oversell.html`
- `app/templates/partials/sale_form.html` - `{% if below_minimum %}{% include "partials/sale_price_warning.html" %}{% endif %}` added after the oversell include
- `tests/test_sales.py` - 7 new tests (5 service-level, 2 web-level)

## Decisions Made

- `below_minimum` is checked strictly per-line (D-09) rather than aggregated like the oversell quantity sum, since price is a per-line attribute with no meaningful basket-wide aggregation.
- Both `oversold` and `below_minimum` are computed unconditionally (not short-circuited) before the combined `if oversold or below_minimum:` gate — the exact fix specified by CONTEXT Pitfall 2 and threat T-07-07, ensuring neither warning can silently swallow the other in a single request.

## Deviations from Plan

One minor deviation, caught by ruff during verification (not a functional bug):

**1. [Rule 1 - Bug] Shortened an over-long test docstring**

- **Found during:** Task 2 verification (`uv run ruff check .`)
- **Issue:** The docstring for `test_web_sale_both_warnings_stack_and_single_confirm_resolves_both` was 101 characters, one over the project's 100-char line-length limit (E501).
- **Fix:** Reworded the docstring to fit within 100 characters, no change to test logic or assertions.
- **Files modified:** `tests/test_sales.py`
- **Commit:** included in `fecee53` (pre-commit fix, not a separate commit)

No other deviations — plan executed as written. Note: `uv run ruff check` on the two new/modified `.html` template files reports parse errors when invoked directly on those paths (ruff attempts to parse `.html` as Python when given an explicit file path, bypassing extension-based file discovery). This is pre-existing behavior — the identical issue reproduces on the untouched `sale_oversell.html` — and is not a regression from this plan. The project's actual lint command (`uv run ruff check .`, which correctly discovers only `.py` files) reports zero errors in any file this plan touched; the one remaining project-wide finding (an import-order warning in `tests/test_sales.py`'s pre-existing header import block, and in a handful of other pre-existing test files) predates this plan and is out of scope.

**Total deviations:** 1 auto-fixed (Rule 1 - lint style, no behavior change)

## Issues Encountered

None beyond the one auto-fixed lint deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PRICE-01 is now delivered in full: `Product.min_sale_cents` (07-02) is enforced at sale time (07-03) with a warn-but-allow guardrail identical in mechanism to the existing oversell check.
- Full test suite green: `uv run pytest -q` — 244 passed.
- `uv run ruff check .` clean on all files this plan touched.
- No further work is scheduled against this phase; Phase 7 (category-browsing-minimum-price-guardrail) is complete pending orchestrator sign-off.

---
*Phase: 07-category-browsing-minimum-price-guardrail*
*Completed: 2026-07-10*

## Self-Check: PASSED

All claimed files verified present; all claimed commit hashes (2e530e3, fecee53, c27ceba) verified present in git log.
