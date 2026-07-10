---
phase: 06-reports-data-export
plan: 06
subsystem: reports
tags: [fastapi, sqlalchemy, jinja2, htmx, reporting, tdd]

# Dependency graph
requires:
  - phase: 06-reports-data-export
    provides: "06-01: Product.stale_days/Settings.stale_days fields; 06-05: reports_landing.html link pattern, period filter reuse"
provides:
  - "app.services.reports.top_selling_products(session, start_iso, end_iso, limit=10) -> list[dict] — SQL-side rank-by-units-sold"
  - "app.services.reports.stale_products(session) -> list[dict] — LEFT OUTER JOIN never-sold + effective-stale-days filter"
  - "app.services.reports._effective_stale_days(product) -> int — explicit is-not-None fallback, local to reports module"
  - "GET /reports/products — period-ranked top-selling table + always-current stale-products table"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Large-history SQL-side aggregation (func.sum/.group_by()/.order_by()/.limit()) contrasted with writeoff_report's small fixed-cardinality Python grouping — chosen by data-volume risk, not by habit"
    - "LEFT OUTER JOIN + Python-side day-diff filter for a never-sold-or-stale list, independent of any period filter"
    - "Reports-only effective-threshold helper kept local to its own module rather than imported cross-module, even though the fallback pattern is identical to a sibling module's helper"

key-files:
  created:
    - app/templates/pages/reports_products.html
    - app/templates/partials/top_selling_rows.html
  modified:
    - app/services/reports.py
    - app/routes/reports.py
    - app/templates/pages/reports_landing.html
    - tests/test_reports.py

key-decisions:
  - "Implemented stale-days threshold comparison as days_since > threshold (strict), not >= as the plan's action text literally specified — see Deviations"
  - "stale_products result built as two lists (never_sold, stale_with_date sorted by days_since descending) concatenated, per the plan's explicit 'pick whichever reads more clearly' instruction"
  - "_effective_stale_days is a separate local helper, NOT imported from app.services.stock, per plan's explicit reports-only-concern reasoning"

requirements-completed: [RPT-04]

# Metrics
duration: 35min
completed: 2026-07-10
---

# Phase 06 Plan 06: Top-Selling & Stale Products Summary

**GET /reports/products with SQL-side top-selling ranking (func.sum/.group_by()/.order_by()/.limit()) and an always-current, LEFT-OUTER-JOIN-based stale/never-sold products list honoring per-product zero-day overrides — the phase's final plan.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-10T14:57:00Z (approx, continuing from 06-05 session)
- **Completed:** 2026-07-10T15:32:00Z (approx)
- **Tasks:** 2 completed
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `top_selling_products(session, start_iso, end_iso, limit=10)`: ranks products by units sold descending within a UTC period using SQL-side `func.sum`/`.group_by()`/`.order_by()`/`.limit()` — not a Python accumulator, since sales history can be large (unlike write-off grouping's small fixed category count).
- `stale_products(session)`: LEFT OUTER JOIN so an active product with zero sale operations still appears (with `days_since=None`, "Никогда"); excludes soft-deleted products; honors an explicit per-product `stale_days=0` without silently falling back to `settings.stale_days` (Pitfall 3, mirrored from the low-stock threshold's discipline but kept in a local helper, not imported cross-module).
- `GET /reports/products` renders two independent halves on one page: a period-filtered top-selling table (HX-swappable) and an always-rendered stale-products table with no period dependency — the stale half stays correct even when the period query params are garbage.
- `/reports` landing page now links to all four reports (sales, stock, write-offs, products), closing out the phase's landing-page contract.

## Task Commits

Each task was committed atomically (TDD RED/GREEN for Task 1):

1. **Task 1: top_selling_products/stale_products — RED** - `1d15777` (test)
2. **Task 1: top_selling_products/stale_products — GREEN** - `08b4a19` (feat)
3. **Task 2: GET /reports/products route, templates, final landing-page link** - `87ba22f` (feat)
4. **Deferred-items log (out-of-scope ruff findings)** - `b4173a4` (docs)

**Plan metadata:** committed alongside this SUMMARY (see final commit).

## Files Created/Modified
- `app/services/reports.py` - new `top_selling_products`, `stale_products`, `_effective_stale_days`
- `app/routes/reports.py` - new `GET /reports/products` route, imports from `app.services.reports`
- `app/templates/pages/reports_products.html` - new page: period-based top-selling section + always-rendered stale section
- `app/templates/partials/top_selling_rows.html` - new partial: error/empty/data three-way branch, Товар/Продано columns
- `app/templates/pages/reports_landing.html` - added the fourth and final report link
- `tests/test_reports.py` - 5 service-level tests (rank order, limit, never-sold, zero-threshold Pitfall 3, soft-delete exclusion) + 4 web-level tests (ranked rendering, "Никогда" for never-sold, stale section independent of a bad period, all-four-links landing page)

## Decisions Made
- **Strict `>` for the stale threshold comparison, not `>=`** — see Deviations below; this is the one place execution diverged from the plan's literal action text.
- Two-list concatenation (`never_sold + stale_with_date`) for `stale_products`' sort order, per the plan's explicit either-is-acceptable instruction — chosen over a single combined sort key for readability.
- `_iso_days_ago(n)` test helper computes timestamps relative to the REAL current local date (`datetime.now(ZoneInfo(TZ))`), unlike every other report test in this file which fixes a synthetic `DAY` constant — required because `stale_products` reads the real clock (`datetime.now`), not a caller-supplied period.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] stale-days threshold comparison: `>` instead of `>=`**
- **Found during:** Task 1, writing `test_stale_threshold_zero_not_fallback`
- **Issue:** The plan's `<action>` text instructed `days_since >= _effective_stale_days(product)`. But the SAME task's acceptance test description explicitly requires: a product with `stale_days=0` and a sale from **yesterday** IS included, while a product with `stale_days=0` and a sale from **TODAY** is EXCLUDED. With `>=`, a same-day sale (`days_since=0`) against a `threshold=0` evaluates `0 >= 0 = True` — included, contradicting the excluded expectation. Only strict `>` (`0 > 0 = False` → excluded; `1 > 0 = True` → included) satisfies both stated behaviors. This is an internal inconsistency between the plan's literal formula and its own authoritative test description.
- **Fix:** Implemented `days_since > _effective_stale_days(product)` (strict greater-than) instead of `>=`.
- **Files modified:** app/services/reports.py
- **Verification:** `test_stale_threshold_zero_not_fallback` passes exactly as the plan's acceptance criteria describe (yesterday included, today excluded); full test suite green.
- **Committed in:** `08b4a19` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary correctness fix — the plan's own test description is the authoritative behavior spec; the literal formula in the action text was the error. No scope creep.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

RPT-04 is fully satisfied: period-ranked top-selling products via SQL aggregation, plus an always-current stale/never-sold list honoring per-product zero-threshold overrides and excluding soft-deleted products.

**All five Phase 6 requirements are now complete** (confirmed by scanning `requirements-completed` across every plan's SUMMARY in this phase):
- RPT-01 — 06-02
- RPT-02 — 06-01 (threshold fields) + 06-03 (stock/low-stock report)
- RPT-03 — 06-05
- RPT-04 — 06-01 (threshold fields) + 06-06 (this plan)
- BCK-02 — 06-04

`/reports` links to all four report pages (sales, stock, write-offs, products). No blockers for milestone completion.

## TDD Gate Compliance

| Task | RED | GREEN | REFACTOR | Status |
|------|-----|-------|----------|--------|
| Task 1 (top_selling_products/stale_products) | ✓ `1d15777` | ✓ `08b4a19` | n/a | Pass |

Task 2 was `type="auto"` (no `tdd="true"`) — no RED/GREEN gate applies.

---
*Phase: 06-reports-data-export*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/services/reports.py contains `def stale_products`, `def top_selling_products`, `def _effective_stale_days`
- FOUND: app/templates/pages/reports_products.html
- FOUND: app/templates/partials/top_selling_rows.html
- FOUND: commit 1d15777, 08b4a19, 87ba22f, b4173a4 all present in git log
- `uv run pytest tests/test_reports.py -x -q`: 34 passed
- `uv run pytest -q` (full suite): 218 passed
- `uv run ruff check app/services/reports.py app/routes/reports.py tests/test_reports.py`: All checks passed
- `grep -n 'stale_products(' app/routes/reports.py`: match found (unconditional call)
- `grep -n 'href="/reports/products"' app/templates/pages/reports_landing.html`: match found
