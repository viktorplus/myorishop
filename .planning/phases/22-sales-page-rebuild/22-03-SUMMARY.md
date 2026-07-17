---
phase: 22-sales-page-rebuild
plan: 03
subsystem: ui
tags: [sqlalchemy, outerjoin, jinja2, htmx, sales]

# Dependency graph
requires:
  - phase: 22-01
    provides: "recent_sales() function shape and the xfail-marked test contracts this plan fulfills"
  - phase: 22-05
    provides: "prior wave-2 edits to tests/test_sales.py (serialization only — no code dependency)"
provides:
  - "recent_sales() returns a customer key (Customer|None) per row via a portable double outerjoin"
  - "recent_sales.html Покупатель column with D-06 muted «Розница» walk-in fallback"
affects: [23-dashboard-history-rebuild]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Double outerjoin (Operation -> Sale -> Customer) for optional-customer joins in a sale listing, mirroring export.py's stream_sales_csv shape"

key-files:
  created: []
  modified:
    - app/services/sales.py
    - app/templates/partials/recent_sales.html
    - tests/test_sales.py

key-decisions:
  - "Both outerjoin hops kept as outerjoin (never join) so no walk-in sale is ever dropped from the recent-sales list (D-06)"
  - "Fixed a pre-existing ruff-format violation in sales.py (unrelated SALE_BATCH_FILL_HINT line) because it blocked this task's own format-check acceptance criterion"

patterns-established:
  - "Optional-buyer listing pattern: select(Operation, Product, Customer) with two outerjoins, dict-shape {op, product, customer}, customer is None for walk-in"

requirements-completed: [SALE-07]

# Metrics
duration: 25min
completed: 2026-07-17
---

# Phase 22 Plan 03: Recent-Sales Customer Column Summary

**recent_sales() gains a buyer name via a portable double outerjoin (Operation -> Sale -> Customer); recent_sales.html shows it with a muted «Розница» fallback for walk-ins, and tests/test_sales.py is now marker-free.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-17T15:14:00+02:00 (approx, from first read)
- **Completed:** 2026-07-17T15:25:43+02:00
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments
- `recent_sales()` in `app/services/sales.py` now returns `{"op", "product", "customer"}` per row via a double outerjoin, with `customer` `None` for walk-in sales — mirrors the shipped `export.py:stream_sales_csv` shape
- `recent_sales.html` gained a «Покупатель» `<th>`/`<td>` pair rendering `name surname`, or a muted «Розница» label for walk-ins, on both `/sales/new` and `/returns` (shared partial, 3 include sites)
- `tests/test_sales.py` carries zero xfail markers after this plan — the last three Phase-22 markers (customer column, retail label, walk-in outerjoin) were removed here

## Task Commits

Each task was committed atomically:

1. **Task 1: recent_sales gains the customer outerjoin** - `41fd633` (feat)
2. **Task 2: recent_sales.html gains the Покупатель column** - `b492fe6` (feat)

_No separate plan-metadata commit — this plan runs in worktree mode; the orchestrator commits shared docs after merge._

## Files Created/Modified
- `app/services/sales.py` - `recent_sales()` extended to select `Customer` via a double outerjoin (`Operation -> Sale -> Customer`); docstring documents the SALE-07/D-06 contract and why the join must stay `outerjoin`
- `app/templates/partials/recent_sales.html` - new «Покупатель» `<th>`/`<td>` pair; `<td>` renders `{{ r.customer.name }} {{ r.customer.surname or '' }}` or `<span class="muted">Розница</span>`
- `tests/test_sales.py` - removed the three Phase-22 `xfail` markers this plan owns (`test_recent_sales_includes_walkin`, `test_web_recent_sales_customer_column`, `test_web_recent_sales_retail_label_for_walkin`) and the now-unused `import pytest`

## Decisions Made
- Kept both join hops as `outerjoin` per the plan's explicit anti-pattern warning — an inner join on `Sale` or `Customer` would silently drop walk-in rows from the newest-first listing, inverting D-06.
- `surname or ''` guards the nullable surname so the cell never renders the literal `None`, mirroring the existing `sale_customer.html`/`customer_picker.html` idiom.
- Did not add an `{% if show_customer %}` suppression flag on `/returns` — per 22-UI-SPEC.md Interaction 17, the buyer name is deliberately shown there too.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug/lint] Fixed pre-existing ruff-format violation in `app/services/sales.py`**
- **Found during:** Task 1 (recent_sales outerjoin) — running the task's own `ruff format --check` acceptance criterion
- **Issue:** `SALE_BATCH_FILL_HINT`'s two-line string literal was already non-canonically wrapped before this plan touched the file (confirmed via `git stash`/`stash pop` against the pre-edit file — unrelated to this task's diff), which fails `ruff format --check` on the file this task's acceptance criteria require to pass cleanly.
- **Fix:** Ran `uv run ruff format app/services/sales.py`, collapsing the string onto one line per ruff's canonical style. No behavior change.
- **Files modified:** app/services/sales.py
- **Verification:** `uv run ruff check app/services/sales.py && uv run ruff format --check app/services/sales.py` passes
- **Committed in:** 41fd633 (Task 1 commit)

**2. [Rule 1 - Bug/lint] Removed now-unused `import pytest` in tests/test_sales.py**
- **Found during:** Task 2 (removing the last two xfail markers) — running the plan's repo-wide `ruff check .` verification
- **Issue:** Removing the third-to-last and last `@pytest.mark.xfail` markers (across Tasks 1 and 2) left `import pytest` with zero remaining uses in the file, triggering `F401`.
- **Fix:** Removed the unused `import pytest` line.
- **Files modified:** tests/test_sales.py
- **Verification:** `uv run ruff check tests/test_sales.py` passes; `uv run pytest tests/test_sales.py -q` → 68 passed, 0 failed, 0 xfailed, 0 xpassed
- **Committed in:** b492fe6 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — lint/format fixes directly caused by or blocking this plan's own acceptance criteria)
**Impact on plan:** No scope creep — both fixes were required to satisfy this plan's own stated `ruff` acceptance criteria. No behavior change to sales logic or templates beyond what the plan specified.

## Issues Encountered
None beyond the two lint fixes documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SALE-07 is complete; ROADMAP criterion 4 (recent-sales list shows each sale's customer) is met.
- `/returns` unregressed (10/10 `tests/test_returns.py` pass, unchanged column count assumptions).
- `tests/test_sales.py` is marker-free — future plans touching that file start from a clean baseline.
- Remaining Phase-22 xfail markers (if any) live in `tests/test_mobile_sales.py`, owned by a different plan — untouched here.
- Full suite: 845 passed, 0 failed, 4 xfailed (all outside this plan's scope, in test_mobile_sales.py) — exceeds the ≥808 acceptance bar.

---
*Phase: 22-sales-page-rebuild*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: app/services/sales.py
- FOUND: app/templates/partials/recent_sales.html
- FOUND: .planning/phases/22-sales-page-rebuild/22-03-SUMMARY.md
- FOUND commit: 41fd633
- FOUND commit: b492fe6
- FOUND commit: 0d5a842
