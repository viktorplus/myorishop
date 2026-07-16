---
phase: 20-warehouses-batch-split-transfers
plan: 03
subsystem: ui
tags: [jinja2, htmx, fastapi, warehouses]

# Dependency graph
requires:
  - phase: 20-warehouses-batch-split-transfers plan 01
    provides: "w.item_count / w.last_receipt computed per-page in list_warehouses (D-03/D-04)"
  - phase: 20-warehouses-batch-split-transfers plan 02
    provides: "dedicated /warehouses/new and /warehouses/{id}/edit pages with redirect-after-POST (D-01/D-02)"
provides:
  - "Plain 5-column /warehouses picker table: Название, Адрес, Товаров, Последняя приёмка, Действия"
  - "Zero inline edit/delete controls on the list; one 'Изменить' link per active row, 'Восстановить' stays inline for deleted rows"
  - "Regression test proving Phase 14's filter/sort/status chrome survived the restructure"
affects: [21-customer-profiles-insights]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-only list row + dedicated edit page (mirrors products.py/customers.py D-01 shape) now also applied to warehouses"
    - "local_dt filter (not ru_date) is the correct display filter for any field backed by Operation.created_at / a full ISO timestamp; ru_date is reserved for date-only fields like batch.expiry"

key-files:
  created: []
  modified:
    - app/templates/pages/warehouses.html
    - app/templates/partials/warehouse_rows.html
    - app/routes/warehouses.py
    - tests/test_warehouses.py

key-decisions:
  - "Used the `local_dt` filter instead of the plan-specified `ru_date` filter for w.last_receipt, since it holds Operation.created_at (a full ISO timestamp), not a date-only string like batch.expiry — ru_date raised ValueError on any non-empty value."

patterns-established:
  - "local_dt vs ru_date filter selection depends on whether the source field is a full timestamp (Operation.created_at, Batch created_iso, etc.) or a date-only string (batch.expiry)."

requirements-completed: [WH-01, WH-02, WH-03]

# Metrics
duration: 12min
completed: 2026-07-16
---

# Phase 20 Plan 03: Warehouse List Picker Restructure Summary

**Restructured `/warehouses` from an inline-editable 3-column table into a read-only 5-column picker (Название, Адрес, Товаров, Последняя приёмка, Действия) with a single "Изменить" edit link per row, closing WH-01's display requirement and the list-page half of WH-02/D-01.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-16T19:03Z (approx, first Read call)
- **Completed:** 2026-07-16T19:09:30+02:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `/warehouses` list is now a plain picker: no `<input>` fields, no inline Сохранить/Удалить buttons — one "Изменить" link per active row to `/warehouses/{id}/edit`
- Added the WH-01 item-count ("Товаров") and last-receipt-date ("Последняя приёмка") columns, reading `w.item_count`/`w.last_receipt` already computed by Plan 20-01's `list_warehouses`
- Removed the now-dead stock-blocked/last-active-warning inline `<tr>` blocks from the list partial (D-02 relocated both to `warehouse_form.html`/`warehouse_delete_wrap.html` in Plan 20-02)
- Cleaned up `_warehouses_context`'s dead parameters left over from the pre-20-02 inline-edit route shape
- Added a dedicated regression test proving Phase 14's filter-bar/name/address/status chrome survived the restructure (RESEARCH Pitfall 1)

## Task Commits

Each task was committed atomically:

1. **Task 1: Restructure list templates + drop dead route context params** - `d06fbd2` (feat)
2. **Task 2: Pitfall 1 regression guard + full-suite confirmation** - `72915a7` (test)

_No separate plan-metadata commit in worktree mode — this SUMMARY.md is committed by the orchestrator after merge per the parallel-execution contract._

## Files Created/Modified
- `app/templates/pages/warehouses.html` - dropped the inline add `<form>`, replaced with a `page-actions` "Добавить склад" link to `/warehouses/new` (mirrors `customers_list.html`)
- `app/templates/partials/warehouse_rows.html` - rewrote `<thead>`/`<tbody>` to 5 read-only columns, dropped dead `errors`/`form` block and the two dead warning `<tr>` blocks, updated empty-state copy
- `app/routes/warehouses.py` - removed 7 unused `_warehouses_context` params (`warning_id`, `stock_blocked_id`, `stock_blocked_qty`, `errors`, `form`, `error_entry_id`, `error_form`)
- `tests/test_warehouses.py` - added 3 new tests (item-count/last-receipt columns, edit-link-only row action, Pitfall 1 filter-bar regression guard)

## Decisions Made
- Chose `local_dt` over the plan-specified `ru_date` filter for `w.last_receipt` display — see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ValueError on last-receipt date rendering**
- **Found during:** Task 1 (running `uv run pytest tests/test_warehouses.py -q` after the initial template rewrite)
- **Issue:** The plan's `<action>` text specified `{{ w.last_receipt | ru_date }}` (mirroring `product_rows.html:88`'s `b.expiry | ru_date` pattern). But `w.last_receipt` is `Operation.created_at` — a full ISO-8601 timestamp with time and timezone (e.g. `2026-07-16T17:03:21+00:00`), not a date-only string like `batch.expiry` (`2026-08-01`). `format_ru_date` calls `date.fromisoformat(iso)`, which raises `ValueError: Invalid isoformat string` on any timestamp with a time component — every GET `/warehouses` request with a warehouse that had ever received stock would 500.
- **Fix:** Switched to the `local_dt` filter (`app/core.py::iso_to_local`, already registered as `templates.env.filters["local_dt"]` and used throughout the codebase for `Operation.created_at`/similar timestamp fields — e.g. `history_rows.html:79`, `ledger_rows.html:23`, `cash_history_rows.html:45`). Kept the existing `{% if w.last_receipt %}...{% else %}<span class="muted">—</span>{% endif %}` null guard unchanged.
- **Files modified:** `app/templates/partials/warehouse_rows.html`
- **Verification:** Added `test_web_warehouses_page_shows_item_count_and_last_receipt_columns`, which seeds a receipted batch and asserts the row renders a real date instead of crashing or showing "—"; full suite green (749 passed).
- **Committed in:** `d06fbd2` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary for correctness — the plan's literal instruction would have made every non-empty `/warehouses` page render a 500 error. No scope creep; this is the only change beyond the plan's literal text.

## Issues Encountered
- The Task 1 test-writing instructions ("assert ... NO `'name="name"'` `<input>` ... anywhere in the response for that active row") were read as scoped to the specific row's markup, not the whole page — the page-wide filter-row `name="name"` input is legitimate Phase 14 chrome that Task 2's regression test explicitly requires to still be present. Both new Task 1 tests slice `response.text` down to the specific warehouse's `<tr>...</tr>` before asserting absence, avoiding a contradiction with Task 2's page-wide presence assertion.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- WH-01/WH-02/WH-03's list-page requirements are now fully closed; `/warehouses` is a plain 5-column picker matching D-01, with item-count/last-receipt visibility (WH-01) and dedicated edit-page navigation (WH-02/WH-03) verified by 39 passing tests in `tests/test_warehouses.py` (36 pre-existing/unmodified + 3 new) plus a full-suite run of 749 tests, all green.
- No blockers for later phases. Phase 21 (Customer Profiles & Insights) does not depend on any warehouse list markup.

---
*Phase: 20-warehouses-batch-split-transfers*
*Completed: 2026-07-16*

## Self-Check: PASSED

All created/modified files and both task commits verified present in the worktree.
