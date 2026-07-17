---
phase: 24-navigation-restructure-settings
plan: 04
subsystem: ui
tags: [fastapi, jinja2, htmx, transfers]

# Dependency graph
requires:
  - phase: 20-warehouses-batch-split-transfers
    provides: "/transfers page, transfer_form.html/transfer_batch_wrap.html partials, register_transfer service"
provides:
  - "«Переместить» per-row action on /products linking to /transfers?code={code}"
  - "_resolve_transfer_lookup(session, code) shared helper in app/routes/transfers.py"
  - "GET /transfers?code= server-side prefill (product name + open batch picker) with silent no-match fallback"
affects: [navigation-restructure-settings]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared resolve-then-prefill helper extracted from an existing HTMX lookup endpoint and reused by a page-level query-param prefill branch (mirrors products.py's product_new pattern)"

key-files:
  created: []
  modified:
    - app/routes/transfers.py
    - app/templates/partials/transfer_form.html
    - app/templates/partials/product_rows.html
    - tests/test_transfers.py
    - tests/test_catalog.py

key-decisions:
  - "_resolve_transfer_lookup returns None on no-match (never raises), letting both callers (transfers_lookup's 204 and transfers_page's silent empty-form fallback) stay simple and consistent with V5 Security Domain guidance"

patterns-established:
  - "prefill_batches/prefill_show_empty as an additive fallback path in a batch-picker {% with %} block, used only when no batch has been explicitly selected yet (selected_batch takes priority)"

requirements-completed: [NAV-07]

# Metrics
duration: ~12min
completed: 2026-07-17
---

# Phase 24 Plan 04: Переместить Row Action + /transfers?code= Prefill Summary

**Product list rows gained a «Переместить» link that opens /transfers?code={code} with the product name and its open-batch picker already resolved server-side, via a new shared `_resolve_transfer_lookup` helper extracted from the existing HTMX lookup endpoint.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-17T20:21:00Z (approx.)
- **Completed:** 2026-07-17T20:33:27Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- `_resolve_transfer_lookup(session, code)` extracted in `app/routes/transfers.py`, shared by `transfers_lookup` (unchanged 204/200 contract) and the new `transfers_page` `?code=` branch
- `GET /transfers?code=X` resolves the product name and open batch picker on first render — zero client-side trigger, no re-selection step
- An unmatched code renders a 200 empty, unprefilled form — code echoed once via the existing autoescaped `value="{{ form.code }}"` attribute, never a 500, never `|safe`
- `/products` row action «Переместить» added next to «Изменить»/«Удалить», linking to `/transfers?code={{ product.code }}`
- 4 new tests added covering prefill, unmatched-code safety, the `/transfers/lookup` regression contract, and row-link presence

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract shared lookup helper + GET /transfers?code= prefill (D-14, V5)** - `e6cf842` (feat)
2. **Task 2: Add the «Переместить» row action to product_rows.html (D-13)** - `02b5d62` (feat)
3. **Task 3: New/updated tests — prefill behavior + row action presence** - `31ffc87` (test)

_Plan metadata commit is created separately by the orchestrator after wave completion (worktree mode)._

## Files Created/Modified
- `app/routes/transfers.py` - Added `_resolve_transfer_lookup` helper; `transfers_lookup` refactored to call it; `transfers_page` gained a `code` query param and prefill branch
- `app/templates/partials/transfer_form.html` - Added `prefill_batches`/`prefill_show_empty` fallback keys to the existing inline `{% with %}` batch-picker block
- `app/templates/partials/product_rows.html` - Added `<a href="/transfers?code={{ product.code }}">Переместить</a>` to the actions cell
- `tests/test_transfers.py` - 3 new web-level tests (prefill, unmatched code, lookup 204 regression)
- `tests/test_catalog.py` - 1 new test asserting the row link's presence

## Decisions Made
None beyond what's captured in `key-decisions` above — plan's design (D-13, D-14) followed as specified.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- NAV-07 fully delivered: reachability path from `/products` into a pre-filled `/transfers` form, replacing the removed top-nav entry (handled in plan 24-01)
- `/transfers/lookup`'s pre-existing 204/200 contract verified byte-identical after the helper extraction (regression-guarded by a new test)
- Full test suite (900 tests) passes; no regressions introduced in shared infrastructure (`transfers.py` is also read by the desktop `/transfers/lookup` and `/transfers/batch-pick` endpoints and the mobile transfer wizard)

---
*Phase: 24-navigation-restructure-settings*
*Completed: 2026-07-17*

## Self-Check: PASSED

All modified files and all 4 task commit hashes (e6cf842, 02b5d62, 31ffc87, 0e8e588) verified present in the worktree and git log.
