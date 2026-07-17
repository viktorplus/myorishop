---
phase: 22-sales-page-rebuild
plan: 04
subsystem: ui
tags: [htmx, vanilla-js, jinja2, sales, advisory-total]

# Dependency graph
requires:
  - phase: 22-sales-page-rebuild
    provides: "22-02's failing test suite (tests/test_sales_total.py) declaring the markup/wiring contract this plan implements"
provides:
  - "app/static/sale-total.js — advisory client-side running total (SALE-02), mirroring price-cue.js's delegated-listener architecture"
  - "#sale-total markup directly under the desktop basket table (sale_form.html), inside <form id=\"sale-form\">"
  - "Script tag wiring on both base.html and mobile_base.html shells"
  - "window.recalcSaleTotal() hook on the desktop delete button (sale_row.html)"
affects: ["22-07 (mobile sale wizard basket/customer selector — consumes window.recalcSaleTotal and data-rows=\"mobile\" contract)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Delegated document-level input listener for advisory client-side computation (second instance after price-cue.js), with zero float arithmetic where the display value has no server-rendered fallback"

key-files:
  created:
    - app/static/sale-total.js
  modified:
    - app/templates/base.html
    - app/templates/mobile_base.html
    - app/templates/partials/sale_form.html
    - app/templates/partials/sale_row.html
    - tests/test_sales_total.py

key-decisions:
  - "sale-total.js parses money as string->integer-cents with zero float arithmetic (unlike price-cue.js's Math.round(parseFloat(...)), which only compares against a server-authoritative reference); the total has no server-rendered fallback so rounding drift would be visible."
  - "Qty regex written as [0-9] rather than \\d to state the ASCII-only contract on its face next to the server's isascii() guard, even though \\d is byte-identical to [0-9] in JS."
  - "Money regex accepts the strict common subset (comma/dot decimal, no space-thousands, no sign) rather than attempting byte-exact Decimal(str) parity; anything server-accepted-but-JS-rejected (1e3, 1_000, fullwidth digits) falls into the D-09 \"итог неполный\" marker, which is harmless on an advisory display."

patterns-established:
  - "Advisory-only client display elements carry no name= attribute and no form control, so client money math is structurally incapable of reaching the server (T-22-03)."

requirements-completed: [SALE-01, SALE-02]

# Metrics
duration: ~12min
completed: 2026-07-17
---

# Phase 22 Plan 04: Live Running Total Summary

**Advisory client-side running total (amount + unit count) under the sales basket, computed with zero-float string-to-cents parsing that mirrors `core.py`'s `to_cents`/`format_cents`, with three recompute triggers (typing, htmx swap, row delete) and a structural no-`name=` guarantee that the figure can never reach the server.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-17T14:44:00+02:00 (approx.)
- **Completed:** 2026-07-17T14:56:00+02:00 (approx.)
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments
- New `app/static/sale-total.js`: `moneyToCents`, `qtyToInt`, `formatCents`, `recalcSaleTotal`, exposed as `window.recalcSaleTotal`; zero float arithmetic, `.textContent`-only DOM writes, no `classList` touches (that surface stays `price-cue.js`'s alone).
- `#sale-total` (amount + unit count + «итог неполный» marker) renders directly under `table.basket` in `sale_form.html`, above the existing basket hint, inside `<form id="sale-form">`, with no `name=` attribute and no form control.
- Both shells (`base.html`, `mobile_base.html`) load `sale-total.js` via a deferred `<script>` tag, duplicated verbatim per the standing mobile_base-does-not-inherit convention.
- Desktop delete button (`sale_row.html`) now calls `window.recalcSaleTotal()` after removing the row and its batch-wrap sibling, guarded so it degrades gracefully if the script hasn't loaded.
- All six previously-xfail tests in `tests/test_sales_total.py` now pass as strict green (markers removed).

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/static/sale-total.js** - `e5e7352` (feat)
2. **Task 2: Wire the total into both shells and the desktop basket** - `e470aec` (feat)

_No TDD tasks in this plan (tests were red-side coverage from 22-02; this plan turns them green by adding the implementation, not by writing new tests)._

## Files Created/Modified
- `app/static/sale-total.js` - New advisory running-total script (137 lines): parse/format helpers + delegated recompute with 3 triggers
- `app/templates/base.html` - Added `<script src="/static/sale-total.js" defer>` after the price-cue.js tag
- `app/templates/mobile_base.html` - Added the same tag verbatim (standalone shell, does not inherit from base.html)
- `app/templates/partials/sale_form.html` - Inserted `#sale-total` markup between `</table>` and the existing basket hint
- `app/templates/partials/sale_row.html` - Delete button's `hx-on:click` now also calls `window.recalcSaleTotal()` after row/batch-wrap removal
- `tests/test_sales_total.py` - Removed the six `@pytest.mark.xfail` markers (SALE-02 now implemented); dropped the now-unused `import pytest`; updated the module docstring to drop the stale "strict xfail until 22-04" framing

## Decisions Made
- Followed 22-RESEARCH.md Pattern 2's reference implementation and 22-UI-SPEC.md Interaction 11-15 markup/copy verbatim — no deviation from the plan's prescribed regex, rounding rule, or trigger set.
- Kept the module docstring in `tests/test_sales_total.py` accurate (dropped the "strict xfail until 22-04 lands" framing, now that 22-04 has landed) rather than leaving stale documentation — a minor doc-accuracy fix within the file this plan already owns, not a scope expansion.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed now-unused `import pytest` from tests/test_sales_total.py**
- **Found during:** Task 2 (xfail marker removal)
- **Issue:** Removing all six `@pytest.mark.xfail(...)` decorators left `import pytest` unused, which `ruff check` flags as F401 and would fail the plan's own acceptance criterion (`uv run ruff check . && uv run ruff format --check .` passes).
- **Fix:** Removed the unused import line.
- **Files modified:** tests/test_sales_total.py
- **Verification:** `uv run ruff check tests/test_sales_total.py` and `uv run ruff format --check tests/test_sales_total.py` both pass cleanly.
- **Committed in:** e470aec (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug/lint fix)
**Impact on plan:** Necessary for the plan's own ruff acceptance criterion on the one file this plan's Python change touches. No scope creep — no other file was altered for this fix.

## Issues Encountered
- Repo-wide `uv run ruff check .` reports 9 pre-existing errors and `uv run ruff format --check .` reports pre-existing reformatting needs, all in files this plan does not touch (`app/routes/dictionary.py`, `app/routes/products.py`, `scripts/import_master_pricelist.py`, several `tests/test_*.py` files). This is accumulated repo debt already logged under 22-01 and 22-02 in `deferred-items.md`; a matching 22-04 entry was appended. Per the Scope Boundary rule, out-of-scope pre-existing lint/format debt was not fixed. This plan's own touched Python file (`tests/test_sales_total.py`) is individually clean on both `ruff check` and `ruff format --check`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SALE-01 (basket table) regression-guarded and unregressed; SALE-02 (live total) shipped on desktop and wired on both shells.
- `window.recalcSaleTotal` and the `data-rows="mobile"` contract (read by the script but not yet exercised by any markup) are ready for 22-07 to consume when it ships the mobile `#sale-total` markup and mobile delete hook.
- Criterion-5 tripwires (oversell/below-minimum/missing-batch/re-echo), the Phase-18 price-cue regression guard, and the SALE-01 basket-table regression guard all remain green.
- Full suite: `uv run pytest -q` → 834 passed, 15 xfailed, 0 failed.

---
*Phase: 22-sales-page-rebuild*
*Completed: 2026-07-17*

## Self-Check: PASSED

All 7 declared files found on disk; all 3 commits (`e5e7352`, `e470aec`, `7859fa4`) found in git log.
