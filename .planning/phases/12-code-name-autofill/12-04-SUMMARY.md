---
phase: 12-code-name-autofill
plan: 04
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile-wizard]

# Dependency graph
requires:
  - phase: 11-mobile-flow
    provides: mobile sale and transfer wizards (existing lookup_prefill/product-row fetches this plan reuses)
provides:
  - Visible product name (not just code) on every mobile sale wizard step from the batch step onward
  - Visible product name (not just code) on every mobile transfer wizard step from the batch step onward
  - Name carried forward through transfer wizard's hx-vals (step 2, no form) and a hidden form field (step 3)
affects: [13-mobile-wizard-context-navigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Visible код — название readout: <p><strong>{{ code }}</strong>{% if name %} — {{ name }}{% endif %}</p>, placed between the step indicator and the step's <h2> — same convention as D-12 (Plan 12-02)"

key-files:
  created: []
  modified:
    - app/routes/mobile_sales.py
    - app/templates/mobile_partials/sale_step_batch.html
    - app/templates/mobile_partials/sale_step_qty_price.html
    - app/routes/mobile_transfers.py
    - app/templates/mobile_partials/transfers_step_batch.html
    - app/templates/mobile_partials/transfers_step_dest.html
    - tests/test_mobile_sales.py
    - tests/test_mobile_transfers.py

key-decisions:
  - "Zero new database lookups — sales wizard reuses the product row each handler already queries; transfers wizard reuses lookup_prefill's return value, which was previously called and discarded"
  - "Transfers wizard step 2 has no enclosing form, so name is carried via the batch-card's hx-vals (3-key dict); step 3 has its own form, so name is carried via a hidden input"

patterns-established:
  - "Mobile wizard readout line: strong-wrapped code, optional em-dash + name, no label/icon/wrapper — matches D-12/D-13/D-14 UI-SPEC row"

requirements-completed: [SAL-06]

duration: 20min
completed: 2026-07-13
---

# Phase 12 Plan 04: Mobile Sale/Transfer Wizard Name Readout Summary

**Mobile sale and transfer wizards now show the product name alongside its code on every step from the batch step onward, using only data each handler already fetches — zero new SQL lookups.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-13
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Mobile sale wizard (steps 2-3): every response derives `name` from either the already-called `lookup_prefill` result (product step) or the already-queried `product` row (batch/qty-price steps), and shows it in a new `<strong>код</strong> — название` readout line
- Mobile transfer wizard (steps 2-3): `transfers_step_batch` now captures `lookup_prefill`'s return value (previously a bare discarded call) and threads `name` through `_render_batch_step`/`_render_dest_step`, the batch-card `hx-vals` (step 2 has no enclosing form), and a new hidden `name` input in `transfer-dest-form` (step 3, round-trips through `transfers_create`'s existing `name: str = Form("")` parameter)
- 7 new tests (4 sales, 3 transfers) covering all behaviors specified in the plan

## Task Commits

Each task was committed atomically:

1. **Task 1: Mobile sales — surface the already-fetched name on steps 2-3 (D-13)** - `f022c58` (feat)
2. **Task 2: Mobile transfers — surface the already-fetched name on steps 2-3 (D-14)** - `79feccd` (feat, includes a small ruff line-length fix to the Task 1 test file)

_Note: this plan ran in a git worktree as part of a parallel wave; the metadata/docs commit (SUMMARY.md) is a separate commit made by this executor per the worktree protocol._

## Files Created/Modified
- `app/routes/mobile_sales.py` - `mobile_sale_step_product`, `mobile_sale_step_batch`, `mobile_sale_step_qty_price` now add a `name` context key
- `app/templates/mobile_partials/sale_step_batch.html` - new readout line before "Выберите партию"
- `app/templates/mobile_partials/sale_step_qty_price.html` - new readout line before "Количество и цена"
- `app/routes/mobile_transfers.py` - `transfers_step_batch` captures the lookup result; `_render_batch_step`/`_render_dest_step`/`transfers_step_batch_pick`/`transfers_step_dest`/`transfers_create` gained a `name` parameter/pass-through
- `app/templates/mobile_partials/transfers_step_batch.html` - new readout line + `name` added to batch-card `hx-vals`
- `app/templates/mobile_partials/transfers_step_dest.html` - new readout line + hidden `name` input in `transfer-dest-form`
- `tests/test_mobile_sales.py` - 4 new tests (multi-batch name, dictionary-only name, batch-card-tap name, qty-price name)
- `tests/test_mobile_transfers.py` - 3 new tests (batch-step name, batch-pick name carry-forward, oversell-retry name carry-forward)

## Decisions Made
- Zero new lookups for either wizard: sales reuses the `product` row each handler already queries; transfers reuses `lookup_prefill`'s return value instead of discarding it (matches the plan's explicit "no new lookups" boundary and D-14's Tampering disposition — `name` is display-only and never affects `register_transfer`'s write path)
- Test assertions on the transfer batch-card's `hx-vals` check for the `"name":` JSON key rather than the literal Cyrillic name text, since Jinja's `tojson` filter unicode-escapes non-ASCII characters in that attribute

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both wizards now consistently show code+name from the batch step onward, closing D-13/D-14 gaps found by the Phase 11 mobile audit
- Phase 13 (Mobile Wizard Context & Navigation) can build on this without re-litigating the readout pattern — same `<strong>код</strong> — название` convention is now used across receipts (D-12, Plan 12-02), sales (D-13), and transfers (D-14)
- No blockers

---
*Phase: 12-code-name-autofill*
*Completed: 2026-07-13*
