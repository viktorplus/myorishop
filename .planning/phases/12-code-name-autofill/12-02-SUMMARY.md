---
phase: 12-code-name-autofill
plan: 02
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile, receipts, pricing]

# Dependency graph
requires:
  - phase: 12-code-name-autofill (Plan 01)
    provides: lookup_prefill() source=="catalog" branch combining Dictionary name + CatalogPrice cost/catalog
provides:
  - "mobile_receipt_step_batch forwarding cost/sale/catalog (product or catalog source) as hidden fields into step 3"
  - "Visible bolded code + optional name readout on mobile receipt step 3 (D-12)"
affects: [13-mobile-wizard-context-and-navigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mobile wizard step-2 handler resolves price/name once via a single lookup_prefill() call, formats via format_cents(), and forwards as hidden fields — no new debounced/live-lookup surface added"

key-files:
  created: []
  modified:
    - app/routes/mobile_receipts.py
    - app/templates/mobile_partials/receipts_step_batch.html
    - app/templates/mobile_partials/receipts_step_details.html
    - tests/test_mobile_receipts.py

key-decisions:
  - "D-06 applied as a superset: prices are forwarded for BOTH source==\"product\" and source==\"catalog\" lookup_prefill matches, keeping mobile symmetric with desktop's existing /receipts/lookup behavior"
  - "sale is never filled from CatalogPrice data at the mobile layer either (D-02 boundary carried from Plan 01)"
  - "D-12 readout is a narrowly-scoped exception to D-07 (no other navigation/step-indicator/back-button changes) — one paragraph line added to step 3 only"

patterns-established:
  - "format_cents()-before-template pattern (RESEARCH Pitfall 4) applied at the mobile step-2 handler, mirroring the desktop route"

requirements-completed: [PRICE-04]

# Metrics
duration: ~10min
completed: 2026-07-13
---

# Phase 12 Plan 02: Mobile Receipt Price/Name Forwarding Summary

**Mobile goods-receipt step 2 now resolves cost/sale/catalog via a single `lookup_prefill()` call and forwards them as hidden fields that pre-fill step 3, plus step 3 always shows a visible bolded product code (and name when known).**

## Performance

- **Duration:** ~10 min
- **Tasks:** 2
- **Files modified:** 4 (app/routes/mobile_receipts.py, app/templates/mobile_partials/receipts_step_batch.html, app/templates/mobile_partials/receipts_step_details.html, tests/test_mobile_receipts.py)

## Accomplishments

- `mobile_receipt_step_batch` in `app/routes/mobile_receipts.py` now makes ONE `lookup_prefill()` call (covering both `source=="product"` and `source=="catalog"` matches), formats cost/sale/catalog via `format_cents()`, and forwards them as hidden fields on step 2's response — reaching step 3's already-existing price inputs automatically via `hx-include="closest form"`.
- CatalogPrice data never reaches the `sale` hidden field, matching the D-02 boundary established on desktop in Plan 01.
- Removed the now-redundant `_lookup_name` helper, inlining its logic into the single `lookup_prefill` call site.
- Mobile receipt step 3 (`receipts_step_details.html`) always shows a visible `<strong>код</strong> — название` readout line above the price fields (D-12), with no other wizard changes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Thread resolved cost/sale/catalog from step 2 into step 3 (D-06)** — tdd="true", two commits:
   - `0e59811` (test) — 3 failing tests for cost/sale/catalog forwarding across product-source, catalog-source, and unknown-code cases
   - `efedae7` (feat) — implementation: single `lookup_prefill()` call, `format_cents()` formatting, 3 hidden inputs in `receipts_step_batch.html`, `_lookup_name` removed
2. **Task 2: Visible code/name readout on step 3 (D-12)** — `322d2a2` (feat) — one paragraph line in `receipts_step_details.html` plus 2 new tests

**Plan metadata:** (this commit)

## Files Created/Modified

- `app/routes/mobile_receipts.py` — `mobile_receipt_step_batch` rewritten to call `lookup_prefill` once, format prices via `format_cents`, forward `cost`/`sale`/`catalog` in context; `_lookup_name` removed
- `app/templates/mobile_partials/receipts_step_batch.html` — 3 new hidden inputs (`cost`, `sale`, `catalog`) placed after the existing `warehouse_id` hidden field, outside the `zero_warehouses` guard
- `app/templates/mobile_partials/receipts_step_details.html` — 1 new visible readout paragraph (bolded code, optional em-dash + name) inserted after the last hidden input, before the qty field
- `tests/test_mobile_receipts.py` — 5 new tests: 3 for price forwarding (existing-product cost-only, catalog-source cost+catalog-never-sale, unknown-code all-empty), 2 for the visible readout (name known / name empty, no trailing dash)

## Decisions Made

- Followed the plan's D-06 superset framing exactly: prices forward for both `source=="product"` and `source=="catalog"` matches, not just the literal catalog-source wording, to stay symmetric with desktop.
- `mobile_receipt_step_details` (step-3 POST handler) required NO changes — it already declares `cost`/`sale`/`catalog` as `Form("")` and echoes them unchanged, so the new hidden fields flow through automatically.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- PRICE-04 is now fully wired on both desktop (Plan 01) and mobile (this plan).
- Phase 13 (Mobile Wizard Context & Navigation) can proceed independently — this plan deliberately did not touch step-indicator/back-button/navigation, per D-07's boundary, leaving that surface untouched for Phase 13's dedicated rework.
- No blockers for remaining Phase 12 plans.

## Self-Check: PASSED

- FOUND: app/routes/mobile_receipts.py
- FOUND: app/templates/mobile_partials/receipts_step_batch.html
- FOUND: app/templates/mobile_partials/receipts_step_details.html
- FOUND: tests/test_mobile_receipts.py
- FOUND: 0e59811
- FOUND: efedae7
- FOUND: 322d2a2

---
*Phase: 12-code-name-autofill*
*Completed: 2026-07-13*
