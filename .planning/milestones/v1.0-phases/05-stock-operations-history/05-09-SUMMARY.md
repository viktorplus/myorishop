---
phase: 05-stock-operations-history
plan: 09
subsystem: ui
tags: [htmx, jinja2, fastapi, pagination, dom-swap]

# Dependency graph
requires:
  - phase: 05-stock-operations-history
    provides: "/history route, history_view()/filter_products() read service, history_rows.html/history_filters.html partials, and the CR-01 (chrome-decision) fix from 05-08"
provides:
  - "Structural fix: #load-more pagination control moved out of <tbody id=\"history-tbody\"> into its own <tfoot>, immune to the tbody's innerHTML (filter change) and beforeend (pagination click) swaps"
  - "New partials/history_load_more.html (standalone control) and partials/history_response.html (combined rows + oob load-more update for HX responses)"
  - "Regression test proving #load-more survives a filter change on a >50-row filtered result set"
affects: [05-stock-operations-history, future phases touching /history or the load-more pagination pattern]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pagination/oob controls that live inside a swap target's innerHTML region are destroyed by that same target's next default swap; isolate persistent oob-swapped controls in a DOM sibling (here: <tfoot>) rather than nesting them inside the swap target's own content"

key-files:
  created:
    - app/templates/partials/history_load_more.html
    - app/templates/partials/history_response.html
  modified:
    - app/templates/partials/history_rows.html
    - app/templates/pages/history.html
    - app/routes/history.py
    - tests/test_history.py

key-decisions:
  - "Root-cause fix per 05-VERIFICATION.md: #load-more moved into <tfoot>, a DOM sibling of #history-tbody, rather than patched with a swap-order workaround"
  - "history_rows.html no longer reads an oob variable at all — that concern moved entirely to history_load_more.html/history_response.html"
  - "Fixed a pre-existing ruff I001 import-order error in tests/test_history.py (blocking this task's own ruff-clean acceptance gate); reordering does not affect the file's intentional RED-by-design collection-failure behavior, which depends on whether app.services.operations.history_view exists, not on import position"

patterns-established:
  - "Combined-response partial (history_response.html) pattern for HX endpoints that need both a main-swap payload and an oob update of a structurally isolated control in the same response"

requirements-completed: [OPS-04]

# Metrics
duration: ~15min
completed: 2026-07-10
---

# Phase 05 Plan 09: Isolate #load-more in tfoot Summary

**Moved the /history "Показать ещё" pagination control out of `<tbody id="history-tbody">` into its own `<tfoot>`, fixing a bug where any filter-select change permanently destroyed the control on a >50-row filtered result set (new CR-01/OPS-04), plus the related button-click reposition defect (WR-01).**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-10T11:09:59Z
- **Tasks:** 1
- **Files modified:** 6 (4 modified, 2 created)

## Accomplishments
- `#load-more` is now a structural sibling of `#history-tbody` (housed in `<tfoot>`), never a descendant — the filter `<select>`s' default innerHTML swap and the "Показать ещё" button's own `beforeend` swap on `#history-tbody` can no longer destroy or reorder it
- Split the old dual-purpose `history_rows.html` into three focused templates: `history_rows.html` (data rows only), `history_load_more.html` (standalone pagination control), and `history_response.html` (combined HX response body)
- Added a regression test (`test_web_history_load_more_survives_filter_change`) proving the control is absent from inside `<tbody id="history-tbody">` and present, live, and reachable in `<tfoot>` for both a plain filtered page load and a genuine HX filter-change request against 51 seeded operations
- Full suite green: 167 passed (up from the 166-passed baseline in `05-VERIFICATION.md`), `ruff check`/`ruff format --check` clean on both `.py` files

## Task Commits

Each task was committed atomically:

1. **Task 1: Move #load-more out of #history-tbody into a standalone tfoot control and add a regression test** - `3970586` (fix)

**Plan metadata:** committed separately by the orchestrator after wave merge (worktree mode — this agent does not touch STATE.md/ROADMAP.md).

## Files Created/Modified
- `app/templates/partials/history_rows.html` - Reduced to data rows + empty-state row only; no longer contains `<tr id="load-more">` or reads `oob`
- `app/templates/partials/history_load_more.html` - NEW. Standalone `<tr id="load-more">` control (conditional `hx-swap-oob`, conditional "Показать ещё" button when `has_next`)
- `app/templates/partials/history_response.html` - NEW. Combines `history_rows.html` (main-swap payload) with an oob-forced include of `history_load_more.html` — rendered for every genuine HX request
- `app/templates/pages/history.html` - `<tbody id="history-tbody">` now includes only `history_rows.html`; a new `<tfoot>` (sibling of `<tbody>`) includes `history_load_more.html` with `oob = False`
- `app/routes/history.py` - HX branch now renders `partials/history_response.html` instead of `partials/history_rows.html`; dropped the now-unused `"oob": is_hx` context key; extended the CR-01 comment block to explain the new fix
- `tests/test_history.py` - New `test_web_history_load_more_survives_filter_change` test; also reordered a pre-existing unsorted import block (ruff I001, unrelated to this plan's behavior change)

## Decisions Made
- Root-cause structural fix (move `#load-more` to `<tfoot>`) chosen over a swap-order workaround, per `05-VERIFICATION.md`'s explicit fix-scope recommendation and `05-REVIEW.md`'s CR-01 finding
- `history_rows.html` no longer has any awareness of `oob` — that concern now lives entirely in `history_load_more.html`/`history_response.html`, keeping each partial single-purpose

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing ruff I001 import-order error in tests/test_history.py**
- **Found during:** Task 1 (running the plan's own `uv run ruff check ... tests/test_history.py` acceptance criterion)
- **Issue:** The file's import block (`from app.services.operations import history_view` separated by a blank line from `app.config`/`app.services.ledger` imports) was already flagged by ruff's `I001` (unsorted import block) before this plan touched the file — confirmed via `git stash` + rerun that the error pre-existed. The plan's acceptance criteria require this check to pass.
- **Fix:** Merged the three imports into one alphabetically-sorted `from app.X import Y` block, matching ruff's suggested fix exactly. The file's "RED by design" collection-failure guarantee (documented in its module docstring) depends on whether `app.services.operations.history_view` exists, not on its position among the other imports, so this reorder does not change that behavior.
- **Files modified:** `tests/test_history.py`
- **Verification:** `uv run ruff check app/routes/history.py tests/test_history.py` exits 0; `uv run pytest tests/test_history.py -q` still 5 passed
- **Committed in:** `3970586` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to satisfy this task's own ruff-clean acceptance gate; no behavior change, no scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- OPS-04 fully satisfied: the operator can browse the complete operation history, including datasets larger than one page, under every filtered and unfiltered interaction path
- No regression in OPS-01..03 or the previously-closed old CR-01 (chrome-decision) fix from 05-08
- Manual sanity check (recommended, non-blocking per `05-VERIFICATION.md`) still open: open `/history`, apply a filter matching >50 operations, confirm "Показать ещё" stays visible and clicking it appends rows after the existing ones — not automated in this plan, left for the operator/next verification pass

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-10*

## Self-Check: PASSED

All created/modified files confirmed on disk; both commits (`3970586` task commit, `ffc426a` SUMMARY commit) confirmed in `git log --oneline --all`.
