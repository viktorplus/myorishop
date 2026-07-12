---
phase: 11-dedicated-mobile-flow
plan: 07
subsystem: ui
tags: [fastapi, htmx, jinja2, mobile, transfers]

# Dependency graph
requires: ["11-01"]
provides:
  - "app/routes/mobile_transfers.py — mobile Перемещение wizard: GET /m/transfers, POST /m/transfers/step/batch, GET /m/transfers/step/batch-pick, POST /m/transfers/step/dest, POST /m/transfers, all calling app.services.transfers.register_transfer unchanged"
  - "mobile_pages/transfers.html, mobile_partials/transfers_step_batch.html, mobile_partials/transfers_step_dest.html, mobile_partials/transfers_warning.html"
affects: ["11-09"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared #wizard-step root id on every step-2/step-3 partial so hx-swap=\"outerHTML\" can move the wizard forward AND backward without touching the surrounding mobile_base.html chrome"
    - "Batch-selection card tap (GET .../step/batch-pick) auto-advances straight into the NEXT step's full content (D-07 — no separate confirm sub-step), rather than re-echoing the same step like desktop's transfers_batch_pick"
    - "One partial (transfers_step_dest.html) triples as the normal step-3 form, the D-06 oversell warning host, and the D-05 post-success confirmation screen, branched by which of errors/oversell/saved is set in context"

key-files:
  created:
    - app/routes/mobile_transfers.py
    - app/templates/mobile_pages/transfers.html
    - app/templates/mobile_partials/transfers_step_batch.html
    - app/templates/mobile_partials/transfers_step_dest.html
    - app/templates/mobile_partials/transfers_warning.html
    - tests/test_mobile_transfers.py
  modified: []

key-decisions:
  - "GET /m/transfers/step/batch-pick renders the FULL step-3 «Куда и количество» content directly (not just an echo of the batch-step selection state) — required to make D-07's 'tapping a batch card advances automatically, no separate confirm sub-step' literal, and makes the destination-exclusion behavior testable from Task 1 alone before Task 2 adds the POST variant"
  - "POST /m/transfers/step/dest is a POST-reachable equivalent of the same step-3 render (used by step 3's own «Назад» button, which hx-posts back to POST /m/transfers/step/batch, and available as a direct entry point) — both routes share the private _render_dest_step/_pick_batch helpers so their validation and output can never drift apart"
  - "«Назад» from step 2 to step 1 is a PLAIN <a href=\"/m/transfers\"> (full page reload), not an htmx swap — GET /m/transfers returns a full HTML document, which cannot cleanly outerHTML-swap into a #wizard-step partial target; «Назад» from step 3 to step 2 IS an htmx hx-post (POST /m/transfers/step/batch returns a #wizard-step partial, safe to swap)"
  - "transfers_step_batch.html renders its own 5-line card markup (4 LOT-02 fields identical wording/filters to batch_card_picker.html, plus a 5th «Склад:» line) rather than reusing the shared partial verbatim, per the plan's explicit instruction — batch_card_picker.html has no warehouse-name slot"

requirements-completed: [UI-01]

# Metrics
duration: 45min
completed: 2026-07-12
---

# Phase 11 Plan 07: Mobile Transfer Wizard Summary

Mobile Перемещение (warehouse transfer) wizard — 3 steps (Товар → Партия with source warehouse shown → Куда и количество) ending in the exact same `register_transfer()` write as the desktop form, with identical destination-exclusion and zero-write-until-confirmed oversell guardrail semantics.

## Performance

- **Duration:** 45 min
- **Started:** 2026-07-12T20:XX:XXZ
- **Completed:** 2026-07-12
- **Tasks:** 2 completed
- **Files modified:** 6 (all created)

## Accomplishments

- `app/routes/mobile_transfers.py` implements all 5 wizard endpoints (`GET /m/transfers`, `POST /m/transfers/step/batch`, `GET /m/transfers/step/batch-pick`, `POST /m/transfers/step/dest`, `POST /m/transfers`), plus the `_dest_warehouses` helper mirroring desktop's D-02 exclusion rule (`[w for w in active_warehouses(session) if w.id != source.warehouse_id]`) and a shared `_pick_batch` helper enforcing the T-11-19/T-09-08 batch-ownership re-validation (`candidate.product_id == product.id`) on every batch-pick entry point
- Step 2 "Партия" (`transfers_step_batch.html`) shows each open batch as its own 5-line card: the four LOT-02 fields identical to `batch_card_picker.html`'s wording/filters, plus a `Склад:` line resolved via a `{warehouse_id: name}` map (never a `Batch.warehouse` ORM relationship, which doesn't exist)
- Step 3 "Куда и количество" (`transfers_step_dest.html`) shows destination-warehouse radio cards (excluding the source's own warehouse) and the quantity field on one screen, per D-05's "one combined decision" rule; the same partial also hosts the D-06 oversell warning (`transfers_warning.html`, verbatim copy of desktop's `transfer_oversell.html` body/buttons) and the D-05 post-success confirmation screen with "Добавить ещё"/"На главную" actions
- `POST /m/transfers` calls `register_transfer(session, code=..., batch_id=..., dest_warehouse_id=..., confirm=...)` with the identical `try/except` → scalar-oversell → errors → success branching as desktop's `transfers_create`
- 9 new tests in `tests/test_mobile_transfers.py`, isolated via `mobile_client_factory`, cover: the happy path (two `transfer` Operation rows, dest batch inherits price/expiry/comment/location), destination-warehouse exclusion (both via the tap-forward GET and the POST variant), the zero-write-until-`confirm=1` oversell guardrail, rejection of a batch belonging to a different product, and the empty-open-batches block

## Task Commits

Each task was committed atomically:

1. **Task 1: Route skeleton + steps Товар/Партия (source warehouse shown)** - `6928bc8` (feat)
2. **Task 2: Step Куда и количество + final write + guardrail + success + tests** - `ada5c03` (feat)

_Note: no TDD tasks this plan._

## Files Created/Modified

- `app/routes/mobile_transfers.py` - new: 5-route wizard router, `_dest_warehouses`/`_pick_batch`/`_render_batch_step`/`_render_dest_step` helpers
- `app/templates/mobile_pages/transfers.html` - new: step 1 "Товар", debounced code input
- `app/templates/mobile_partials/transfers_step_batch.html` - new: step 2 "Партия", own 5-line card markup
- `app/templates/mobile_partials/transfers_step_dest.html` - new: step 3 "Куда и количество" / oversell host / post-success screen
- `app/templates/mobile_partials/transfers_warning.html` - new: mobile oversell warning, verbatim desktop copy
- `tests/test_mobile_transfers.py` - new: 9 tests

## Decisions Made

See `key-decisions` in frontmatter. The most consequential one: `GET /m/transfers/step/batch-pick` renders the full step-3 content directly rather than re-echoing step 2, matching the UI-SPEC's literal "tapping a batch card advances the wizard automatically, no separate confirm sub-step" wording for the batch-selection step.

## Deviations from Plan

### Auto-fixed / process notes

**1. [Process note, not a Rule 1-4 deviation] Both wizard endpoints for step 3 were implemented together in the Task 1 commit's route file**

- **Found during:** Task 1 implementation
- **Detail:** `app/routes/mobile_transfers.py` was authored as one complete file (all 5 routes) before either task's commit boundary was drawn, since the routes share private helpers (`_pick_batch`, `_render_dest_step`) that made a clean partial-file split impractical without duplicating logic mid-plan. The Task 1 commit therefore includes `POST /m/transfers/step/dest` and `POST /m/transfers` route bodies, but the templates they render (`transfers_step_dest.html`, `transfers_warning.html`) are not committed until Task 2 — meaning a checkout of the Task 1 commit alone would 500 on those two routes (TemplateNotFound). This does not affect the final plan state (both tasks are committed, full suite green) but is noted for bisectability awareness.
- **Files affected:** `app/routes/mobile_transfers.py` (committed whole in Task 1)
- **Commit:** `6928bc8`

None of Rules 1-4 were triggered — no bugs found in existing code, no missing critical functionality beyond what the plan specified, no blocking issues, no architectural changes.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`app/routes/mobile_transfers.py` and its 4 templates are complete and covered by 9 passing tests, isolated from the rest of the app via `mobile_client_factory` (no changes to `app/main.py` — real router registration happens in Plan 09 per the phase's artifact map). Full suite (`uv run pytest -q`) is green: 372 passed. Plan 09 (final mobile router wiring + home tile) can include `mobile_transfers.router` directly.

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created files verified present on disk; both task commit hashes (`6928bc8`, `ada5c03`) verified present in `git log --oneline --all`.
