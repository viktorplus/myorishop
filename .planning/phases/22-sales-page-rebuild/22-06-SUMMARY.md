---
phase: 22-sales-page-rebuild
plan: 06
subsystem: ui
tags: [fastapi, jinja2, htmx, sqlalchemy, customer-picker, mobile]

# Dependency graph
requires:
  - phase: 22-02
    provides: mobile sale wizard shell (mobile_sales.py, mobile_pages/sales.html, test_mobile_sales.py xfail-pinned scaffolding for D-04)
  - phase: 22-05
    provides: desktop _customer_context builder, _CUSTOMER_MODES allow-list, and the restructured partials/sale_customer.html this plan mirrors
provides:
  - "mobile_partials/customer_picker.html — mobile customer search-result card list, its own m-customer-* ids"
  - "mobile_partials/sale_customer.html — mobile 3-way customer selector at full desktop parity (D-04), root #m-customer-header"
  - "GET /m/sales/customer-mode, GET /m/sales/customer-search, POST /m/sales/customer — mobile customer endpoints mirroring the desktop contracts"
  - "_m_customer_context(session, mode, customer_id, form) in app/routes/mobile_sales.py"
affects: [22-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mobile htmx partial gets its own m- prefixed id namespace instead of reusing/parameterising the desktop partial, to avoid id collisions across the two template trees"
    - "Mobile route module imports a private allow-list tuple from a desktop route module (mobile_finance.py:26 precedent), rather than duplicating it"

key-files:
  created:
    - app/templates/mobile_partials/customer_picker.html
    - app/templates/mobile_partials/sale_customer.html
  modified:
    - app/routes/mobile_sales.py
    - tests/test_mobile_sales.py

key-decisions:
  - "_m_customer_context mirrors app.routes.sales._customer_context's LOGIC only (not imported directly) — the mobile partial's echo-field shape differs from desktop's, and importing the desktop builder would bind mobile to a context shape it doesn't use."
  - "The mode radio's hx-target is #m-customer-header, never #wizard-step — swapping #wizard-step would wipe the accumulated code_acc[]/qty_acc[]/price_acc[]/batch_acc[] basket."
  - "mobile_sale_create is left untouched this plan — the customer_id write-path wiring is explicitly 22-07's task, matching the plan's stated scope boundary."

patterns-established:
  - "Every non-GET-safe htmx control that needs sibling form state carries hx-include explicitly (the fieldset AND the quick-create button both declare it)."

requirements-completed: [SALE-03, SALE-04, SALE-05, SALE-06]

# Metrics
duration: ~20min
completed: 2026-07-17
---

# Phase 22 Plan 06: Mobile Customer Selector Summary

**Mobile sale wizard gets its own 3-way customer selector (Новый/Существующий/Без покупателя) at full desktop parity, via two new m-prefixed partials and three new mobile endpoints — not yet wired into the basket screen (that lands in 22-07).**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-17T13:10:00Z (approx.)
- **Completed:** 2026-07-17T13:31:00Z
- **Tasks:** 3
- **Files modified:** 4 (2 new templates, 1 route module, 1 test file)

## Accomplishments
- New `mobile_partials/customer_picker.html` — the mobile search-result card list, reusing `customer_search_view` unchanged, with its own `m-customer-*` ids so it never collides with the desktop tree
- New `mobile_partials/sale_customer.html` — the mobile 3-way selector at full parity with desktop (D-04): same 3 modes, D-02 `existing` default, D-07's hard 3-field cap on «Новый», D-03 hidden-echo round-trip for inactive modes
- Three new mobile endpoints (`GET /m/sales/customer-mode`, `GET /m/sales/customer-search`, `POST /m/sales/customer`) plus `_m_customer_context`, mirroring the desktop contracts against the mobile templates and ids
- Removed the `acc_survives` xfail marker in `tests/test_mobile_sales.py` — the mode-swap-preserves-basket contract now holds for real

## Task Commits

Each task was committed atomically:

1. **Task 1: New mobile customer picker partial** - `638e16b` (feat)
2. **Task 2: New mobile customer selector partial** - `827ab2f` (feat)
3. **Task 3: Mobile customer endpoints** - `8fef702` (feat)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified
- `app/templates/mobile_partials/customer_picker.html` - mobile customer search-result card list (`.mobile-card`, `.dataset`/`.textContent` contract, `m-` prefixed ids)
- `app/templates/mobile_partials/sale_customer.html` - mobile 3-way customer selector, root `#m-customer-header`
- `app/routes/mobile_sales.py` - `_m_customer_context` builder + 3 new endpoints (`/m/sales/customer-mode`, `/m/sales/customer-search`, `/m/sales/customer`); `mobile_sale_create` untouched
- `tests/test_mobile_sales.py` - removed the `acc_survives` xfail marker only (test body unchanged, per plan's declared scope)

## Decisions Made
- `_m_customer_context` deliberately duplicates `_customer_context`'s logic rather than importing it, because the two partials' echo-field shapes differ (mobile has no `form=` attribute requirement since it lives inside `#sale-wizard-form`, unlike desktop's `#customer-header` which sits outside `<form id="sale-form">`)
- The mode radio's swap root is `#m-customer-header` (never `#wizard-step`) to guarantee the basket survives a mode switch — verified by `test_mobile_selector_swap_acc_survives`, now passing for real instead of xfail
- `_CUSTOMER_MODES` is imported from `app.routes.sales` rather than duplicated, following the `mobile_finance.py:26` precedent (`_resolve_period` import) for cross-module private-helper reuse

## Deviations from Plan

None — plan executed as written. Two header-comment wording adjustments were made purely to satisfy the plan's own literal-substring acceptance-criteria greps (`grep -c 'innerHTML'` / `grep -c "session.add(Customer"` both needed to return 0, including in comments), without changing any documented intent:
- `customer_picker.html`'s header comment describes the "no raw-markup DOM write, never `|safe`" contract without using the literal token `innerHTML`.
- `mobile_sales.py`'s `POST /m/sales/customer` comment describes "never a raw ORM insert built by hand" instead of literally writing `session.add(Customer(...))`.

Both are documentation-only rewordings; the underlying code contract (no `innerHTML`, no direct `Customer` insert bypassing `create_customer`) is unchanged and verified by the acceptance-criteria greps themselves.

## Issues Encountered

None beyond the two comment-wording tweaks above, resolved inline during Task 1/Task 3 verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `mobile_partials/sale_customer.html` and `mobile_partials/customer_picker.html` exist and are endpoint-reachable, but are not yet included anywhere in the rendered wizard — `mobile_sale_create` still hardcodes `customer_id=""` and its stale `# D-04: no mobile customer picker this phase` comment is still present, both intentionally, per this plan's explicit scope boundary.
- 22-07 must: (1) include `mobile_partials/sale_customer.html` into the Корзина screen (`sale_basket.html`) above the basket cards, (2) delete the `customer_id=""` hardcode + stale comment in `mobile_sale_create` and thread the posted `customer_id` through to `register_sale`, (3) remove the remaining `test_mobile_customer_selector_renders_on_basket` and `test_mobile_links_customer` xfail markers, (4) fix the D-11 `hx-include` gap in `mobile_partials/batch_card_picker.html`.
- Pre-existing repo-wide `ruff check`/`ruff format` debt (9 errors / 47 files, unrelated to this plan) logged in `deferred-items.md`, not fixed here — consistent with every prior Phase 22 plan.

---
*Phase: 22-sales-page-rebuild*
*Completed: 2026-07-17*
