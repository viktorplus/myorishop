---
phase: 11-dedicated-mobile-flow
plan: 04
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile, sales, wizard]

# Dependency graph
requires:
  - phase: 11-dedicated-mobile-flow
    plan: "01"
    provides: "mobile_base.html, batch_card_picker.html, mobile CSS classes, mobile_client_factory test fixture"
provides:
  - "app/routes/mobile_sales.py — full mobile Продажа wizard: product lookup, batch pick, qty/price, basket assembly, final register_sale() write"
  - "5 mobile sale templates (mobile_pages/sales.html + 4 mobile_partials)"
  - "Precedent for a mobile wizard's hidden-field basket accumulation, reused by later Phase 11 write-wizards (05-07)"
affects: [11-05, 11-06, 11-07, 11-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single persistent <form> per wizard wraps every step; each step response is a partial swapped into #wizard-step (innerHTML) or, for the batch-pick card tap, #batch-wrap (outerHTML, per batch_card_picker.html's fixed contract) — htmx's closest-form default inclusion carries the accumulated arrays forward with zero manual hx-include"
    - "Each basket line in the Корзина review owns its own 4 hidden accumulated-array inputs inside its .mobile-card — client-side «Удалить» (hx-on:click removing the card) drops that line from the form with no server round trip, mirroring desktop sale_row.html's Pitfall 2 precedent"
    - "The warning screen (sale_warning.html) {% include %}s the basket screen (sale_basket.html) below it, so the danger button's confirm=1 re-POST and the dismiss button's client-side removal both operate on the SAME still-intact basket DOM"
    - "The success screen reuses sale_step_product.html (a `saved` context flag toggles between the step-1 form and the confirmation banner) since 'Добавить ещё' restarts the wizard exactly there — no separate success template needed"

key-files:
  created:
    - app/routes/mobile_sales.py
    - app/templates/mobile_pages/sales.html
    - app/templates/mobile_partials/sale_step_product.html
    - app/templates/mobile_partials/sale_step_batch.html
    - app/templates/mobile_partials/sale_step_qty_price.html
    - app/templates/mobile_partials/sale_basket.html
    - app/templates/mobile_partials/sale_warning.html
  modified:
    - tests/test_mobile_sales.py
    - pyproject.toml

key-decisions:
  - "POST (not GET) for /m/sales/step/product, despite the plan's action text mentioning hx-get — Form()-based accumulated-array carry-forward requires POST; the endpoint's own header declaration ('POST /m/sales/step/product') and Form-field description are authoritative. Documented as a deviation."
  - "No dedicated basket-remove server route — per-line removal is client-side only (hx-on:click removing the .mobile-card), matching desktop sale_row.html's existing precedent and keeping the file list unchanged from the plan"
  - "Success screen renders via sale_step_product.html with a `saved` flag rather than a new template, since files_modified for this plan lists no separate success partial and 'Добавить ещё' naturally restarts at step 1"

requirements-completed: [UI-01]

# Metrics
duration: 20min
completed: 2026-07-12
---

# Phase 11 Plan 04: Mobile Sale Wizard Summary

Mobile Продажа wizard (Товар → Партия → Количество и цена → Корзина → Оформить продажу) built via hidden-field basket accumulation, ending in the exact same array-shaped `register_sale()` write as desktop — including zero-write-until-confirmed price-floor and oversell guardrails.

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-12
- **Tasks:** 2 completed
- **Files modified:** 10 (8 created, 2 modified)

## Accomplishments
- `app/routes/mobile_sales.py`: `GET /m/sales`, `POST /m/sales/step/product`, `GET /m/sales/step/batch`, `POST /m/sales/step/qty-price`, `POST /m/sales/step/basket-add`, `POST /m/sales` — six endpoints, zero new SQL queries (reuses `lookup_prefill`, `open_batches`, `register_sale` unchanged)
- A product with zero open batches blocks forward wizard progress (Pitfall 6/D-12); a sole open batch auto-selects (D-06) but the step still shows with its forward control enabled
- Batch ownership re-validated (`candidate.product_id == product.id`, T-09-08/T-11-10) before any client-supplied `batch_id` is trusted, both at the batch-pick step and the qty-price price-fill step
- Price pre-fill at the qty/price step mirrors desktop's exact rule: picked batch's `price_cents` first, card `sale_cents` fallback (D-14) when the batch has none
- The final write calls `register_sale(session, customer_id="", codes=, qtys=, prices=, batch_ids=, confirm=)` — byte-identical keyword shape to desktop's `sale_create`, same try/except → oversell-or-below_minimum → errors → success branching order (Pitfall 5)
- Price-floor and oversell warnings combine both bodies verbatim from `sale_price_warning.html`/`sale_oversell.html` into one `sale_warning.html`, rendered above the still-intact basket; zero Operation rows written until the danger button re-POSTs with `confirm=1`
- 11 tests covering both product/batch step navigation and the full basket-to-write flow, including two scenarios that assert zero `Operation` rows exist before the `confirm=1` re-post

## Task Commits

Each task was committed atomically:

1. **Task 1: Route skeleton + steps Товар/Партия** - `86ca753` (feat)
2. **Task 2: Step Количество/цена + basket assembly + final write + guardrails + tests** - `e286b8d` (feat)

_Note: no TDD tasks this plan._

## Files Created/Modified
- `app/routes/mobile_sales.py` - the full 6-endpoint sale wizard router
- `app/templates/mobile_pages/sales.html` - wizard page shell, one persistent `<form>` wrapping `#wizard-step`
- `app/templates/mobile_partials/sale_step_product.html` - step 1 "Товар" + doubles as the post-success confirmation screen
- `app/templates/mobile_partials/sale_step_batch.html` - step 2 "Партия", wraps `batch_card_picker.html` (Plan 01), self-replacing `#batch-wrap` root
- `app/templates/mobile_partials/sale_step_qty_price.html` - step 3 "Количество и цена", batch-rule price pre-fill
- `app/templates/mobile_partials/sale_basket.html` - "Корзина" review, per-line client-side removal
- `app/templates/mobile_partials/sale_warning.html` - combined price-floor + oversell warning, includes the intact basket below it
- `tests/test_mobile_sales.py` - 11 tests (route skeleton + full write/guardrail scenarios)
- `pyproject.toml` - added `fastapi.Query` to ruff's bugbear `extend-immutable-calls` (same rationale as the existing `Depends`/`Form` entries; needed for the GET batch-pick step's accumulated-array query params)

## Decisions Made
- Used POST for `/m/sales/step/product` (see Deviations) since the accumulated arrays are carried as `Form()` fields.
- Client-side-only basket-line removal (no new server route), matching desktop's `sale_row.html` precedent exactly.
- Success confirmation reuses `sale_step_product.html` rather than a new template, keeping this plan's file list unchanged from what was planned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Resolved plan's hx-get/POST inconsistency for the product-lookup step**
- **Found during:** Task 1
- **Issue:** The plan's `<action>` prose for `GET /m/sales` describes the code input as `hx-get="/m/sales/step/product"`, but the very next paragraph declares the endpoint as `POST /m/sales/step/product` accepting the 4 accumulated arrays as `Form` fields — a GET request cannot carry `Form()`-typed body data the way the endpoint description requires.
- **Fix:** Implemented `/m/sales/step/product` as `POST` (matching the endpoint's own header declaration and its `Form`-field description) and used `hx-post` on the code input's debounced lookup trigger.
- **Files modified:** app/routes/mobile_sales.py, app/templates/mobile_partials/sale_step_product.html
- **Verification:** `test_product_step_unknown_code_shows_error_no_forward` and all other product-step tests pass against the POST endpoint.
- **Commit:** 86ca753

**2. [Rule 3 - Blocking] Added `fastapi.Query` to ruff's immutable-calls allowlist**
- **Found during:** Task 1
- **Issue:** `GET /m/sales/step/batch` needs `Query([], alias="...[]")` defaults for the 4 accumulated arrays (a GET request serializes closest-form values into the query string); ruff's `flake8-bugbear` B008 flagged these as "function call in argument defaults" since only `fastapi.Depends`/`fastapi.Form` were previously allowlisted.
- **Fix:** Added `"fastapi.Query"` to `[tool.ruff.lint.flake8-bugbear].extend-immutable-calls` in pyproject.toml, alongside the existing `Depends`/`Form` entries (same rationale comment already in place).
- **Files modified:** pyproject.toml
- **Verification:** `uv run ruff check` passes clean on `app/routes/mobile_sales.py`.
- **Commit:** 86ca753

**3. [Rule 2 - Missing Critical] Added a step-back ("Назад") control not spelled out per-endpoint in the task text**
- **Found during:** Task 1/2
- **Issue:** The plan's task `<action>` text doesn't specify the exact wiring for the wizard shell's shared "Назад" control (UI-SPEC: "every step except the first"), but UI-SPEC's Wizard Shell table requires it.
- **Fix:** Batch and qty-price steps' "Назад" button re-posts to `/m/sales/step/product` with a `back=1` flag, which short-circuits the lookup and re-renders step 1 as-is (no forced re-navigation).
- **Files modified:** app/routes/mobile_sales.py, sale_step_batch.html, sale_step_qty_price.html
- **Verification:** Manual template/route review; not separately unit-tested (not required by this plan's acceptance criteria).
- **Commit:** 86ca753 / e286b8d

---

**Total deviations:** 3 auto-fixed (1 bug-fix for plan self-inconsistency, 1 blocking lint-config fix, 1 missing-critical wizard-shell control)
**Impact on plan:** All three necessary for the wizard to function/lint cleanly. No scope creep — deviation 3 implements an already-mandated UI-SPEC element the task text simply didn't spell out mechanically.

## Issues Encountered
- `Batch.price_cents` is a receipt-creation-time snapshot, not something `record_operation` sets from `unit_price_cents` — one test initially assumed otherwise and was corrected to set `batch.price_cents` directly, matching what the real receipt route does.
- Jinja's default `Undefined` raises on chained attribute access (`errors.form` when `errors` itself is undefined) rather than silently evaluating falsy — `sale_basket.html` now defaults `errors` via `{% set errors = errors | default({}) %}` so it can be safely included from contexts that don't pass an `errors` key (e.g. the basket-add success path).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
The full mobile sale wizard is implemented and tested in isolation via `mobile_client_factory` (no `app.main` registration yet — that's Plan 09's job). `uv run pytest tests/test_mobile_sales.py -x -q` (11 tests) and the full suite (`uv run pytest -q`, 374 tests) both pass. The hidden-field carry-forward pattern and the client-side per-line basket removal are now established precedent for the remaining write-wizards (Списание/Корректировка/Перемещение, Plans 05-07).

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*

## Self-Check: PASSED

All 8 created/modified files verified present on disk; both task commit hashes (86ca753, e286b8d) verified present in `git log --oneline --all`.
