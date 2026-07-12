---
phase: 10-warehouse-transfers-expiry-reporting
plan: 02
subsystem: ui
tags: [fastapi, jinja2, htmx, warehouse-transfer, batches]

# Dependency graph
requires:
  - phase: 10-warehouse-transfers-expiry-reporting (Plan 01)
    provides: app/services/transfers.py (register_transfer/recent_transfers), "transfer" op-type registration
provides:
  - GET /transfers, GET /transfers/lookup, GET /transfers/batch-pick, POST /transfers routes
  - Six transfer templates mirroring the write-off UI, with a destination-warehouse select replacing reason/note
  - "Перемещение" nav link in base.html
  - tests/test_transfers.py — 6 appended route/integration tests (16 total in file, all green)
affects: [10-03 (expiry reporting, already merged, unaffected)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["destination-warehouse <select> rendered inside the shared batch-wrap partial, gated on selected_batch_id + a server-filtered warehouses list — same wrapper serves inline/oob/main-swap contexts from one markup source"]

key-files:
  created:
    - app/templates/pages/transfer_form.html
    - app/templates/partials/transfer_form.html
    - app/templates/partials/transfer_lookup.html
    - app/templates/partials/transfer_batch_wrap.html
    - app/templates/partials/transfer_oversell.html
    - app/templates/partials/transfer_rows.html
    - app/routes/transfers.py
  modified:
    - app/main.py
    - app/templates/base.html
    - tests/test_transfers.py

key-decisions:
  - "Destination-warehouse <select> lives inside transfer_batch_wrap.html (not transfer_form.html) so one swap both fills the source-batch picker and reveals the filtered dest select — avoids a second round trip"
  - "Dest select visibility gated on `selected_batch_id and warehouses` (both truthy) rather than 'warehouses is defined' — degenerates safely to no-select if a source is picked but no other active warehouse exists"

requirements-completed: [WH-03]

# Metrics
duration: 24min
completed: 2026-07-12
---

# Phase 10 Plan 02: Transfer Route & UI Wiring Summary

**The `/transfers` page, lookup, batch-pick, and POST routes are live, mirroring the write-off form 1:1 with a server-filtered destination-warehouse `<select>` (active warehouses minus source) replacing the reason/note fields; a completed transfer shows in `/history` as «Перемещение» with both directions.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-12T18:03:00Z
- **Completed:** 2026-07-12T18:27:00Z
- **Tasks:** 2 completed
- **Files modified:** 10 (7 created, 3 modified)

## Accomplishments
- Created the six transfer templates (page + 5 partials) by mirroring the write-off analogs file-by-file per 10-PATTERNS.md, renaming every `writeoff`→`transfer` token on ids/urls/targets, and replacing the reason/note fields with the destination-warehouse `<select>`
- Added the «Перемещение» nav link to `base.html` next to «Списание»
- Implemented `app/routes/transfers.py` (`GET /transfers`, `GET /transfers/lookup`, `GET /transfers/batch-pick`, `POST /transfers`) as a 1:1 mirror of `writeoffs.py`, with literal routes declared before any parameterized route, defensive rollback on POST failure, the oversell warn-but-allow branch, and 422 re-echo of the selected batch + filtered dest select
- Registered the router in `app/main.py` (after `writeoffs.router`)
- TDD RED→GREEN: appended 6 failing route/integration tests confirming `/transfers` 404s pre-route, then implemented the route to green; full 16-test file and full 358-test suite pass
- Verified end-to-end: transfer moves stock (source Batch.quantity down, dest Batch.quantity up), oversell warns with zero writes until `confirm=1`, and `/history` shows «Перемещение» with both a `-3` and `+3` row for the same product

## Task Commits

Each task was committed atomically:

1. **Task 1: Transfer templates (6) + «Перемещение» nav link** - `6f7587f` (feat)
2. **Task 2: Transfer routes + router registration + route integration tests** - `f5b7f64` (test, RED) → `07a18f9` (feat, GREEN)

_TDD task 2 followed RED/GREEN: `/transfers` returning 404 confirmed as RED before the route module existed, then the full suite went green after implementation — no refactor commit was needed._

## Files Created/Modified
- `app/templates/pages/transfer_form.html` (NEW) - page wrapper, heading «Перемещение», includes the form + recent-rows partials
- `app/templates/partials/transfer_form.html` (NEW) - whole-swapped form: code lookup, name field, qty, batch picker include, success line, oversell include, oob recent-rows include
- `app/templates/partials/transfer_batch_wrap.html` (NEW) - scalar batch_id wrapper reusing `batch_picker.html`, PLUS the destination-warehouse `<select name="dest_warehouse_id">` shown only once a source batch is picked and a `warehouses` list is supplied
- `app/templates/partials/transfer_lookup.html` (NEW) - `/transfers/lookup` oob response fragment (name fill + oob batch-wrap)
- `app/templates/partials/transfer_oversell.html` (NEW) - warn-but-allow block, re-POSTs with `confirm=1`
- `app/templates/partials/transfer_rows.html` (NEW) - recent-transfers table, `|abs` on `qty_delta` since `recent_transfers()` returns the outbound (negative) row
- `app/routes/transfers.py` (NEW) - the four routes; `_dest_warehouses()` helper computes active warehouses minus the picked source's warehouse, reused across batch-pick and all three POST response branches
- `app/main.py` - added `transfers` import + `app.include_router(transfers.router)`
- `app/templates/base.html` - added «Перемещение» nav link after «Списание»
- `tests/test_transfers.py` - appended 6 route/integration tests (page render, lookup fill, batch-pick dest-exclusion, POST move, oversell→confirm, transfer-in-history)

## Decisions Made
- Followed 10-PATTERNS.md exactly for template renames and route structure (writeoffs.py 1:1 mirror)
- Success context's `saved.qty` uses the raw form `qty` string (not a recomputed int from the operation), matching the plan's explicit instruction — consistent with how the operator's own input is echoed back
- Dest-select visibility condition combines "source picked" AND "warehouses non-empty" (both truthy) rather than "warehouses is defined" — functionally identical in practice (route always passes `[]` before a pick) but also degrades safely if a source is picked and no other active warehouse exists

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria and verification commands passed on first implementation (after the deliberate RED step for Task 2).

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

WH-03 is now delivered end-to-end (service from Plan 01 + route/UI from this plan). The transfer feature is fully wired: `/transfers` page, lookup, batch-pick with source-excluding dest select, POST with defensive rollback + confirm=1 warn, and `/history` correctly labels both directions as «Перемещение». No blockers for the remaining phase work (10-03, expiry reporting, was already merged independently in the same wave and is unaffected by this plan).

## TDD Gate Compliance

Verified in git log: `test(10-02): add failing route/integration tests for transfer wiring` (f5b7f64, RED) precedes `feat(10-02): implement transfer routes + router registration (WH-03)` (07a18f9, GREEN). Gate sequence satisfied; no refactor commit was needed (ruff clean on first pass, no reformatting required).

## Self-Check: PASSED

All created files verified on disk (six templates under `app/templates/pages/` and `app/templates/partials/`, `app/routes/transfers.py`, this SUMMARY.md); all task/plan commits (6f7587f, f5b7f64, 07a18f9) verified present in git log via `git log --oneline`.

---
*Phase: 10-warehouse-transfers-expiry-reporting*
*Completed: 2026-07-12*
