---
phase: 23-dashboard-history-rebuild
plan: 04
subsystem: ui
tags: [fastapi, jinja2, htmx, history-ledger]

# Dependency graph
requires:
  - phase: 23-dashboard-history-rebuild
    provides: "Plan 02's extended history_view (customer/category/date-range kwargs, HISTORY_TYPE_COLUMNS, per-row warehouse), plus 23-UI-SPEC.md Interaction 7-13's authoritative desktop layout/column table"
provides:
  - "GET /history: category/customer/from/to query params, local _resolve_history_period helper (blank-means-unfiltered, unlike reports.py's blank-means-today)"
  - "partials/history_rows.html: type-first desktop History UI — top filter-bar (Тип + Сортировать по), universal period_filter.html, per-type narrowed thead/tbody driven by columns"
  - "partials/period_filter.html: additive hx-include on its form + 3 preset links, safe for every existing consumer (Reports/Finance)"
  - "app/services/operations.py: history_view rows now carry a resolved customer object (LEFT OUTER JOIN Sale->Customer), needed for the desktop Покупатель column"
affects: ["23-05 (mobile History UI reuses the same history_view/HISTORY_TYPE_COLUMNS)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local period-resolution helper duplicating reports.py::_resolve_period's parse/validate/preset logic but with a blank-params-means-no-filter default, instead of importing a shared helper whose default would silently break D-04"
    - "Column-driven conditional thead/tbody: a single `columns` tuple (or None) selects between the unchanged generic table and a narrowed per-type table, keeping filter-row cell counts matching their own header row"

key-files:
  created: []
  modified:
    - app/routes/history.py
    - app/templates/partials/history_rows.html
    - app/templates/partials/period_filter.html
    - app/services/operations.py
    - tests/test_history.py

key-decisions:
  - "history_view (Plan 02) extended, in this plan, to always outerjoin Sale then Customer and attach a resolved `customer` object per row — Plan 02's row shape only carried a filterable customer_id path, not a displayable Customer, which the desktop Покупатель column needs"
  - "Категория filter input lives inside the Товар filter-row cell (alongside the product select) rather than a new cell, so filter-row cell counts stay identical to their own header row's cell count in both the generic and every narrowed per-type view — avoids HTML column-count mismatch across <thead> rows"
  - "Покупатель filter input lives inside its own per-type column's filter-row cell (only rendered when that column exists, i.e. sale/return) rather than a separate universal slot — perfect natural alignment since the column and the filter share the same visibility condition"

patterns-established:
  - "Column-driven conditional thead/tbody keyed off a single `columns` value (None vs tuple) — the same shape Plan 03's dashboard feed and Plan 05's mobile History UI should reuse rather than re-deriving their own per-type branching"

requirements-completed: [HIST-01, HIST-02, HIST-03, HIST-04]

# Metrics
duration: 45min
completed: 2026-07-17
---

# Phase 23 Plan 04: Desktop History Type-First Rebuild Summary

**Desktop `/history` now narrows both rows and columns together when a stock-affecting type is selected, with a relocated top filter-bar and new category/customer/date-range filters — the 3 audit types and the untyped default still show the full unchanged 10-column view.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-07-17T16:15:00Z (approx)
- **Completed:** 2026-07-17T16:58:00Z
- **Tasks:** 2 completed
- **Files modified:** 5

## Accomplishments

- `history_page` (`app/routes/history.py`) accepts `category`, `customer`, `from`, `to` query params. A local `_resolve_history_period` helper mirrors `reports.py::_resolve_period`'s malformed/inverted-range fallback-to-today behavior, but — deliberately, unlike the shared helper — returns `from_date=None, to_date=None` (no date filter at all) when both params are blank, so `/history`'s default unfiltered view stays fully unfiltered (D-04).
- `extra_qs` re-serializes every active filter (type/product/sort/category/customer/from/to) onto pagination links, using the RESOLVED dates rather than raw (possibly malformed) input.
- `partials/history_rows.html`: the «Тип» select moved out of the header filter-row into a new top `.filter-bar` alongside «Сортировать по» (Interaction 7); all 9 `OPERATION_TYPE_LABELS` options remain selectable (Pitfall 5/D-06 — audit types are NOT dropped from the dropdown, only from the narrowed-column treatment).
- `period_filter.html` is included immediately below the top filter-bar, universal across every type (D-05); its form and 3 preset links gained an additive `hx-include` so a preset click or от/по submit carries every other active `/history` filter along — a no-op for its other consumers (`/reports/sales`, `/reports/writeoffs`, `/reports/products`, `/finance/report`, mobile equivalents).
- The `<thead>`/`<tbody>` now branch on `columns`: `None` (no type, or one of the 3 audit types) renders the pre-existing unchanged generic 10-column table; a tuple (one of the 6 `STOCK_AFFECTING_TYPES`) renders Когда/Код/Товар + one column per `HISTORY_TYPE_COLUMNS` key, in order, + Действие — with «Кто» dropped from every narrowed view per Interaction 8.
- «Категория» filter input (debounced, `product_rows.html` idiom) is always visible, sharing the Товар filter-row cell with the existing product select. «Покупатель» filter input is visible only for `sale`/`return` (hidden entirely, not disabled — Interaction 11), living in its own column's filter-row cell.

## Task Commits

Each task was committed atomically:

1. **Task 1: history.py route — new filters, local date-range resolution, extra_qs** - `9bab495` (feat) — includes the Plan-02-adjacent `operations.py` deviation described below, since the two are tightly coupled (the route change alone is untestable/incomplete for the customer column without it).
2. **Task 2: history_rows.html — top filter-bar relocation + per-type columns** - `1574219` (feat) — includes the `period_filter.html` additive change and 3 pre-existing test updates required by the intentional structural relocation.

**Plan metadata:** committed separately per worktree protocol (this SUMMARY.md commit).

## Files Created/Modified

- `app/routes/history.py` — `history_page` gains `category`/`customer`/`from`/`to` params; new `_resolve_history_period` local helper; `extra_qs`/context extended with the new filter state plus `columns`
- `app/templates/partials/history_rows.html` — relocated Тип select, top filter-bar, universal period filter include, per-type conditional thead/tbody, new Категория/Покупатель filter inputs
- `app/templates/partials/period_filter.html` — additive `hx-include` on the form and all 3 preset `<a>` tags
- `app/services/operations.py` — `history_view`'s base query now also always outerjoins `Sale` then `Customer`; each row dict gains a `"customer"` key (resolved `Customer` object or `None`)
- `tests/test_history.py` — 3 pre-existing tests updated (see Deviations)

## Decisions Made

- Extended `history_view` (Plan 02's function, not in this plan's declared file list) to attach a resolved `Customer` per row — see Deviations below for the full rationale; this was necessary for the plan's own Task 2 instructions to be implementable.
- Placed the Категория filter inside the Товар filter-row `<th>` (not a new cell) so filter-row cell counts always match their own header row's count, for both the generic view and every narrowed per-type view — avoids any `<thead>` row cell-count mismatch.
- Placed the Покупатель filter inside its own per-type column's filter-row cell (only rendered when `type_filter` is `sale`/`return`, which is exactly when that column exists) rather than a separate always-present slot.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended `history_view` (app/services/operations.py) to attach a resolved Customer per row**
- **Found during:** Task 2 (history_rows.html's Покупатель column)
- **Issue:** The plan's Task 2 instructs the Покупатель column to "reuse `recent_sales.html`'s exact ... rendering" (`r.customer.name`/`r.customer.surname`), but Plan 02's `history_view` row dict only carries `op`/`product`/`batch`/`warehouse` — no `customer` object (only a filterable `Sale.customer_id` reachable via a conditional join, not the row-level object the template needs). Without this, the Покупатель column could not render at all.
- **Fix:** Base query now always `outerjoin`s `Sale` (via `Operation.sale_id`) then `Customer` (via `Sale.customer_id`) — mirroring the existing always-outerjoin `Warehouse` pattern in the same function — and the row dict gains a `"customer"` key (`None` for a walk-in sale or any non-sale op). The pre-existing `customer_q` filter block's own `stmt.outerjoin(Sale, ...)` was removed (now redundant/would duplicate the join) in favor of just `.where(...)`; `count_stmt` keeps its own independent conditional join, unaffected.
- **Files modified:** `app/services/operations.py`
- **Verification:** All 20 pre-existing `tests/test_history.py` tests pass unmodified after this change (no row-shape assertion broke); full suite (866 tests) green.
- **Committed in:** `9bab495` (Task 1 commit)

**2. [Rule 1 - Test maintenance] Updated 3 pre-existing tests broken by the intentional Тип-select relocation and column narrowing**
- **Found during:** Task 2 verification (`uv run pytest tests/test_history.py -x`)
- **Issue:** `test_web_history_table_has_10_columns` asserted exactly 2 `<select>` elements inside `<thead>` (type + product) — the plan explicitly instructs moving the Тип select out of `<thead>` into the top filter-bar, dropping this to 1. `test_web_history_filters` and `test_web_history_filtered_reload_returns_full_chrome` both filtered by `type=writeoff` and asserted on `<td>Списание</td>` (the Тип data cell) — but `writeoff` is a `STOCK_AFFECTING_TYPES` member, so it now renders the narrowed per-type view, which has no «Тип» column at all (per HIST-01/D-06's authoritative column table), making that assertion permanently false.
- **Fix:** `test_web_history_table_has_10_columns` now asserts 1 `<select>` in `<thead>` plus `id="type"` present elsewhere in the page. The two type-filter tests now verify narrowing via a «Код» cell count (`<td>{code}</td>` occurrences drop when filtered) instead of the now-absent Тип label text.
- **Files modified:** `tests/test_history.py`
- **Verification:** `uv run pytest tests/test_history.py -q` — 20/20 pass; full suite — 866/866 pass.
- **Committed in:** `1574219` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking service extension, 1 test maintenance)
**Impact on plan:** Both were direct, necessary consequences of the plan's own explicit instructions (narrow columns per type, relocate the Тип select) — no scope creep, no architectural change, no new tables/schema.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `app/services/operations.py`'s `history_view` now returns a `"customer"` key on every row — available to Plan 05 (mobile History UI) and any future consumer without further service changes.
- The column-driven conditional `<thead>`/`<tbody>` pattern established here (branch on `columns`, one column key per `<td>`) is directly reusable by Plan 05's mobile cards.
- Full test suite: 866 passed, 0 failed.
- No blockers or concerns for downstream plans in this phase.

---
*Phase: 23-dashboard-history-rebuild*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: app/routes/history.py
- FOUND: app/templates/partials/history_rows.html
- FOUND: app/templates/partials/period_filter.html
- FOUND: app/services/operations.py
- FOUND: tests/test_history.py
- FOUND: .planning/phases/23-dashboard-history-rebuild/23-04-SUMMARY.md
- FOUND commits: 9bab495, 1574219
