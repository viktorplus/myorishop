---
phase: 11-dedicated-mobile-flow
plan: 03
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile, receipts, wizard]

# Dependency graph
requires:
  - phase: 11-dedicated-mobile-flow (Plan 01)
    provides: mobile_base.html shell, mobile_client_factory test fixture, mobile CSS classes (.mobile-shell, .mobile-step-indicator, .mobile-card, .mobile-actions)
provides:
  - "GET /m/receipts + POST /m/receipts/step/batch|details|confirm + POST /m/receipts — the mobile Приход (goods receipt) 4-step wizard"
  - "The hidden-field carry-forward wizard pattern (RESEARCH Pattern 1) as a working reference implementation for Plans 04-07 (Sale/Write-off/Correction/Transfer)"
affects: [11-04, 11-05, 11-06, 11-07, 11-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single persistent <form> with hx-target/hx-swap set once on the form (inherited by all descendant hx-post buttons); each step's response is the NEXT step's full replacement content for #wizard-step, re-echoing all prior fields as hidden inputs"
    - "'Назад' buttons re-POST to the endpoint that generated the CURRENT step's precursor, reusing the same forward-step handler for back-navigation instead of adding dedicated back routes"
    - "One template file renders three states (normal / 422-error / post-success) via top-level saved/errors context flags, mirroring desktop's receipt_form.html {% if saved %} convention"

key-files:
  created:
    - app/routes/mobile_receipts.py
    - app/templates/mobile_pages/receipts.html
    - app/templates/mobile_partials/receipts_step_batch.html
    - app/templates/mobile_partials/receipts_step_details.html
    - app/templates/mobile_partials/receipts_step_confirm.html
    - tests/test_mobile_receipts.py
  modified: []

key-decisions:
  - "Plan's 4 wizard steps never mention a product-name field, yet register_receipt() requires a non-empty name — added automatic name resolution via lookup_prefill() at the step1->2 transition (hidden field for known codes), with a visible required Название input on step 2 ONLY when the code resolves to nothing (brand-new product, D-05 auto-create path)"
  - "SAVE_FAILED_ERROR re-declared verbatim in mobile_receipts.py rather than imported from app.routes.receipts — matches the codebase's existing convention (confirmed via grep) that no route file imports from another route file"

patterns-established:
  - "Mobile wizard 'Назад' = re-POST to the prior step's own forward-generating endpoint (no new back-only routes)"

requirements-completed: [UI-01]

# Metrics
duration: 30min
completed: 2026-07-12
---

# Phase 11 Plan 03: Mobile Receipt Wizard Summary

**4-step mobile Приход wizard (Товар → Партия → Количество/Цены → Подтверждение) producing byte-identical register_receipt() writes to the desktop form, for both new-batch and top-up-batch paths.**

## Performance

- **Duration:** ~30 min
- **Completed:** 2026-07-12
- **Tasks:** 2
- **Files modified:** 6 (5 created, 1 test file created+extended)

## Accomplishments
- `GET /m/receipts` renders step 1 (склад + код), blocking with the verbatim desktop RU hint when there are zero active warehouses
- `POST /m/receipts/step/batch` renders step 2's resolve-or-create batch chooser (top-up vs. «Новая партия»), auto-resolving the product name via `lookup_prefill` and only asking the operator to type a name when the code is genuinely unknown
- `POST /m/receipts/step/details` renders step 3 (qty/cost/sale/catalog), server-omitting expiry/location/comment entirely for a top-up (no client-side JS toggling needed, unlike desktop, since the batch choice was already made in a prior step)
- `POST /m/receipts/step/confirm` renders step 4's read-only summary + «Сохранить приход» CTA
- `POST /m/receipts` calls `register_receipt()` with the exact same 11 kwargs as desktop's `receipt_create`, same try/except + `session.rollback()` + `SAVE_FAILED_ERROR` contract, rendering a post-success screen («Приход сохранён: …») with «Добавить ещё» / «На главную» actions
- 11 tests covering: zero-warehouse blocking (steps 1 and 2), new-code vs. existing-product batch chooser rendering, step 3 new-batch-field omission for top-ups, step 4 summary rendering, new-batch and top-up happy-path writes (asserting Operation/Batch rows), and a validation error writing zero rows

## Task Commits

Each task was committed atomically:

1. **Task 1: Route skeleton + steps 1-2 (Товар, Партия chooser)** - `0794f88` (feat)
2. **Task 2: Steps 3-4 (Количество/Цены, Подтверждение) + final write + success + tests** - `6bf306c` (feat)

_This plan has no separate metadata commit — SUMMARY.md is committed via the worktree final commit._

## Files Created/Modified
- `app/routes/mobile_receipts.py` - router with `GET /m/receipts`, `POST /m/receipts/step/batch|details|confirm`, `POST /m/receipts`, helpers `_preselect_warehouse_id`/`_chooser_context`/`_lookup_name`, constants `DEFAULT_WAREHOUSE_ID`/`SAVE_FAILED_ERROR`
- `app/templates/mobile_pages/receipts.html` - step 1 full-page load, wraps the persistent wizard `<form>`
- `app/templates/mobile_partials/receipts_step_batch.html` - step 2 resolve-or-create chooser
- `app/templates/mobile_partials/receipts_step_details.html` - step 3 quantity/prices, conditional new-batch fields
- `app/templates/mobile_partials/receipts_step_confirm.html` - step 4 confirm/error/success (three states, one file)
- `tests/test_mobile_receipts.py` - 11 tests via `mobile_client_factory`

## Decisions Made
- Auto-resolve the product name server-side (Rule 2 — missing critical functionality: `register_receipt` unconditionally requires a non-empty `name`, but none of the plan's 4 described wizard screens included a name field). Implemented as a hidden carry-forward field for known codes (existing product or dictionary entry), falling back to a small required text input on step 2 only for genuinely unknown codes — keeps the common case (existing catalog item) fully in line with the plan's described 4-screen flow while still supporting desktop's D-05 auto-create path.
- Re-declared `SAVE_FAILED_ERROR` locally rather than importing it from `app.routes.receipts`, matching the codebase's established no-route-imports-another-route convention (verified via grep — no existing route file imports from another).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added automatic product-name resolution/entry to the wizard**
- **Found during:** Task 1 (design pass before writing step 1/2)
- **Issue:** The plan's 4 wizard steps (Товар → Партия → Количество/Цены → Подтверждение) never mention a `name` field anywhere, but Task 2's own action text calls `register_receipt(session, code=code, name=name, ...)` and the service unconditionally rejects an empty name (`errors["name"] = "Укажите название."`). Without a name source, every wizard submission would fail validation.
- **Fix:** Added `_lookup_name()` (reusing the existing `lookup_prefill` service function, same one desktop's `/receipts/lookup` uses) at the step1→2 transition. Known codes carry the resolved name forward as a hidden field (ignored by the service for existing products anyway, per PD-9); unknown codes render a small required «Название товара» input on step 2 with an auto-create notice, mirroring desktop's own auto-create messaging.
- **Files modified:** app/routes/mobile_receipts.py, app/templates/mobile_partials/receipts_step_batch.html
- **Verification:** `test_web_step_batch_new_code_shows_new_batch_only_and_name_input`, `test_web_step_batch_existing_product_lists_open_batch_and_carries_name`, `test_web_receipt_create_new_batch_happy_path` all pass
- **Committed in:** 0794f88 (Task 1), extended in 6bf306c (Task 2 final-write kwargs)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary for the wizard to be able to write at all — without it every single submission would 422 on the missing-name validation error, regardless of batch path. No scope creep beyond what `register_receipt`'s existing signature already required.

## Issues Encountered
None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The hidden-field carry-forward pattern (persistent `<form>` + hx-target inheritance + "Назад" re-invoking the prior step's own endpoint) is now a working, tested reference for Plans 04-07 (Sale/Write-off/Correction/Transfer), which reuse the same D-05 wizard-shell contract.
- No blockers. Full test suite green (374 passed) after this plan's changes.

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*

## Self-Check: PASSED

All 7 created/modified files verified present on disk; all 3 commits (0794f88, 6bf306c, 256d6f2) verified in git log.
