---
phase: 11-dedicated-mobile-flow
plan: 10
subsystem: ui
tags: [css, htmx, jinja2, fastapi, mobile-wizard]

# Dependency graph
requires:
  - phase: 11-dedicated-mobile-flow
    provides: mobile Sale wizard (Plan 04), shared batch_card_picker.html partial, .mobile-card CSS token
provides:
  - "button.mobile-card CSS color fix closing the white-on-white batch-card text bug (11-UAT.md Test 4 Bug A)"
  - "from_batch_step-gated Назад wiring in the mobile Sale wizard's qty-price step, closing the lost-batch-step back-navigation bug (11-UAT.md Test 4 Bug B)"
affects: [11-UAT, 11-VALIDATION]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scoped CSS override on the concrete rendered element (button.mobile-card) rather than a blanket class-level color change, to avoid touching unrelated div/label/a .mobile-card usages"
    - "Server-side from_batch_step boolean flag passed to a shared partial to disambiguate which previous step a Назад control must target, instead of inferring it client-side"

key-files:
  created: []
  modified:
    - app/static/style.css
    - app/routes/mobile_sales.py
    - app/templates/mobile_partials/sale_step_qty_price.html
    - tests/test_mobile_sales.py

key-decisions:
  - "CSS fix scoped to button.mobile-card only (not a blanket .mobile-card color rule), per plan instruction — every other .mobile-card usage (div/label/a) already renders correctly and must not be touched."
  - "Назад now performs a GET /m/sales/step/batch (no explicit hx-vals) relying on htmx's default closest-form field inclusion to carry code/batch_id/*_acc[] — mirrors the existing pattern already used by batch card taps."

patterns-established:
  - "from_batch_step context flag: any future wizard step that can be reached via two different prior steps should pass an explicit boolean flag distinguishing origin, rather than trying to infer it from other context fields."

requirements-completed: [UI-01]

# Metrics
duration: 25min
completed: 2026-07-13
---

# Phase 11 Plan 10: Gap Closure — Batch-Card Legibility + Sale Wizard Back-Navigation Summary

**Fixed white-on-white batch-selection card text (button.mobile-card color scoping) and the mobile Sale wizard's Назад control skipping past the batch step, per 11-UAT.md Test 4's two root-caused gaps.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-12T23:37:00Z
- **Completed:** 2026-07-13T00:02:06Z
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- Batch-selection cards (Sale/Write-off/Correction/Transfer wizards) now render price/expiry/quantity/comment in legible dark text at rest, on hover, and when selected — no longer readable only via the generic `button:hover` darken-then-lighten coincidence.
- The mobile Sale wizard's qty-price step's Назад control now returns to a freshly re-rendered batch-selection step (code and any prior pick intact) whenever a batch step was actually shown for the line, while still returning straight to the product step for a dictionary-only match that never had a batch step.
- Both gaps closed with automated regression coverage (2 new tests), full suite green (436 tests), ruff clean.

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix invisible batch-card text (button.mobile-card color)** - `e7e00ce` (fix)
2. **Task 2: Fix Sale wizard Назад skipping the batch step** - `2d7114a` (fix)

**Plan metadata:** commit pending (this SUMMARY + REQUIREMENTS)

_Note: worktree mode — STATE.md/ROADMAP.md updates deferred to the orchestrator after merge._

## Files Created/Modified
- `app/static/style.css` - Added `button.mobile-card { color: #222; }` plus matching `:hover` and `.selected:hover` overrides, scoped to the button element only.
- `app/routes/mobile_sales.py` - Added `from_batch_step` boolean to both context dicts that render `sale_step_qty_price.html` (dictionary-only branch: `False`; batch-step-origin `/step/qty-price` handler: `True`).
- `app/templates/mobile_partials/sale_step_qty_price.html` - Назад button now conditionally wired: `hx-get="/m/sales/step/batch"` when `from_batch_step` is true, otherwise the original `hx-post="/m/sales/step/product" hx-vals='{"back": "1"}'`.
- `tests/test_mobile_sales.py` - Added `test_qty_price_step_back_returns_to_batch_step_when_batch_step_was_shown` and `test_qty_price_step_back_returns_to_product_step_for_dictionary_match`.

## Decisions Made
- Kept the CSS fix scoped to `button.mobile-card` per the plan's explicit rationale — a blanket `.mobile-card { color }` would have silently altered unrelated already-working surfaces (history cards, receipts batch chooser, corrections mode picker, write-off reason rows, search results).
- Used `hx-get` with no explicit `hx-vals` for the new Назад wiring, relying on htmx's default closest-form field inclusion (the button lives inside `#sale-wizard-form`) to carry `code`/`batch_id`/`code_acc[]`/`qty_acc[]`/`price_acc[]`/`batch_acc[]` — matches the parameter shape `GET /m/sales/step/batch` already expects via `Query(...)`, verified by the new regression test's direct GET call.

## Deviations from Plan

None - plan executed exactly as written. The plan's automated verify command for Task 1 (`grep -A1 "^button.mobile-card {$" ...`) assumed a multi-line CSS format; the actual file uses this section's existing single-line rule convention (e.g. `.mobile-tile-grid { display: grid; ... }`), so the rule was written as `button.mobile-card { color: #222; }` on one line — functionally identical to the `<done>` criteria's exact required string, verified with an equivalent single-line grep instead.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both 11-UAT.md Test 4 gaps are closed with automated regression coverage; ready for the next UAT re-run pass covering the remaining phase items.
- No blockers or concerns.

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-13*
