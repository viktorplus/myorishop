---
phase: 04-sales-customers
plan: 06
subsystem: sales
tags: [fastapi, htmx, jinja2, query-params, gap-closure]

# Dependency graph
requires:
  - phase: 04-sales-customers
    provides: "04-02 basket transaction slice (GET /sales/lookup route, sale_row.html basket row template)"
provides:
  - "GET /sales/lookup binds bracketed code[]/name[]/price[] query keys via FastAPI Query(alias=...), matching what sale_row.html's hx-include=\"closest tr\" actually sends"
  - "Regression coverage for both the fill-when-empty (oob price fill) and no-clobber-when-typed (SAL-01 UAT gap) lookup paths, using the real bracketed request shape"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "GET routes with array-form basket inputs must alias bare query params to their bracketed DOM name (Query(\"\", alias=\"code[]\")), mirroring the sibling POST route's existing Form(alias=...) pattern — bare/aliased mismatch is a silent 204 no-op, not a visible error"

key-files:
  created: []
  modified:
    - app/routes/sales.py
    - tests/test_sales.py

key-decisions:
  - "Left row: str = \"\" unaliased — hx-vals sends a bare \"row\" key via a separate JS object literal, not through hx-include's array-form serialization, so it was never affected by the bug"

patterns-established: []

requirements-completed: [SAL-01]

# Metrics
duration: 8min
completed: 2026-07-09
---

# Phase 4 Plan 6: Fix /sales/lookup Bracketed Query-Param Binding Summary

**GET /sales/lookup now binds `code[]`/`name[]`/`price[]` via FastAPI `Query(alias=...)`, closing the Phase 4 UAT gap where the basket's per-line code lookup never autofilled «Название» because the route only declared bare, unaliased query param names.**

## Performance

- **Duration:** 8 min
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- `sale_lookup()` in `app/routes/sales.py` now declares `code`, `name`, `price` as `Query("", alias="code[]")` / `Query("", alias="name[]")` / `Query("", alias="price[]")`, mirroring the sibling `POST /sales` route's existing `Form(alias="code[]")` pattern. This is the exact request shape `sale_row.html`'s `hx-include="closest tr"` produces from the real basket row DOM (array-form inputs `code[]`/`name[]`/`price[]`), which the route previously never bound — `code` always arrived as `""`, so every lookup silently returned 204 and «Название» never filled, in every case (not just when a price was typed first).
- `tests/test_sales.py::test_web_sale_lookup_prefills_price` updated to send bracketed params (matching the real DOM) and now asserts the `hx-swap-oob="true"` price-fill block is present.
- Added `test_web_sale_lookup_bracketed_params_price_prefilled_no_clobber`, the exact Phase 4 UAT Test 2 reproduction: bracketed params with `price[]` already non-empty (`"15,00"`) still autofill «Название» while asserting `hx-swap-oob="true"` is absent (the already-typed price is not clobbered).

## Task Commits

Each task was committed atomically:

1. **Task 1: Alias /sales/lookup query params to the bracketed keys hx-include actually sends** - `94391b8` (fix)

## Files Created/Modified

- `app/routes/sales.py` - `sale_lookup()`'s `code`/`name`/`price` params changed from bare `str = ""` to `Query("", alias="code[]"/"name[]"/"price[]")`; `Query` added to the `fastapi` import line
- `tests/test_sales.py` - `test_web_sale_lookup_prefills_price` sends bracketed params + asserts oob price fill; new `test_web_sale_lookup_bracketed_params_price_prefilled_no_clobber` reproduces the UAT gap (price typed first, no clobber)

## Decisions Made

- `row: str = ""` was left unaliased — confirmed via `sale_row.html`'s `hx-vals='{"row": "{{ row_id }}"}'` that `row` is sent as a bare key through a separate JS object literal, not through `hx-include`'s array-form serialization, so it was never part of the bug and needed no change.

## Deviations from Plan

None - plan executed exactly as written. The root cause was already fully diagnosed in `.planning/debug/sale-lookup-name-not-filling.md`; this plan applied the documented fix and test updates verbatim.

## Issues Encountered

None. Pre-existing `ruff check tests/test_sales.py` `I001` (unsorted import block, lines 20-24) is unrelated to this plan's changes — confirmed via `git stash`/re-check that it exists on the pre-plan commit too, and it was already logged in `deferred-items.md` under "From Plan 04-02". No new deferred items added.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `uv run pytest tests/test_sales.py -k lookup -x -q` — 2 passed (both lookup tests green).
- `uv run pytest tests/test_sales.py -q` — 23 passed, no regressions in the SAL-01/02/03/04/05 suite.
- `uv run ruff check app/routes/sales.py tests/test_sales.py` and `uv run ruff format --check app/routes/sales.py tests/test_sales.py` — both exit 0 for the files this plan touched.
- SAL-01's code-lookup autofill gap is closed. This was the last plan in Phase 4 (gap closure, wave 1); no blockers for milestone completion.

---
*Phase: 04-sales-customers*
*Completed: 2026-07-09*
