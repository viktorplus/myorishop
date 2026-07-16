---
phase: 20-warehouses-batch-split-transfers
plan: 02
subsystem: ui
tags: [fastapi, jinja2, htmx, warehouses]

# Dependency graph
requires:
  - phase: 20-warehouses-batch-split-transfers
    provides: "20-01's schema/service groundwork for warehouse batch-split transfers"
provides:
  - "GET /warehouses/new and GET /warehouses/{id}/edit dedicated pages (WH-02, D-01)"
  - "Redirect-after-POST create/update routes mirroring app/routes/products.py"
  - "partials/warehouse_delete_wrap.html: relocated warn-then-confirm/stock-blocked delete UI (WH-03, D-02)"
affects: [20-03]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Warehouses now follow the same GET /new, GET /{id}/edit, POST redirect-after-success, POST 422-re-render shape as Products"]

key-files:
  created:
    - app/templates/pages/warehouse_form.html
    - app/templates/partials/warehouse_delete_wrap.html
  modified:
    - app/routes/warehouses.py
    - tests/test_warehouses.py

key-decisions:
  - "warehouse_delete_wrap.html's dismiss button uses this.closest('.error-block').remove() rather than the plan's literal '.closest(\"div\")' suggestion, since the warning card is wrapped in a nested .form-actions div — targeting the specific .error-block class (mirroring the original tr-targeting pattern) correctly removes the whole warning card instead of only its button bar."

patterns-established:
  - "Dedicated add/edit page pattern (GET /new, GET /{id}/edit, POST redirect-303-on-success, POST 422-re-render-same-page) now shared verbatim between Products and Warehouses — future entities needing a CRUD form should follow this same shape."

requirements-completed: [WH-02, WH-03]

# Metrics
duration: 35min
completed: 2026-07-16
---

# Phase 20 Plan 02: Dedicated Warehouse Add/Edit/Delete Pages Summary

**Warehouses gained dedicated `/warehouses/new` and `/warehouses/{id}/edit` pages mirroring Products' CRUD shape, with the existing WH-03 warn-then-confirm/stock-blocked delete UI relocated from the list's inline rows onto the new edit page.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-16T16:20:00Z (approx, worktree spawn)
- **Completed:** 2026-07-16
- **Tasks:** 2/2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments

- `GET /warehouses/new` and `GET /warehouses/{id}/edit` render a dedicated `pages/warehouse_form.html`, structurally mirroring `product_form.html` (heading branch, `.field`s, `.form-actions`, destructive zone). Unknown edit id returns 404.
- `POST /warehouses` and `POST /warehouses/{id}` now redirect-after-success (303 to `/warehouses`) instead of re-rendering the list's `warehouse_rows.html` partial; validation errors re-render the SAME form page with a 422 status.
- `POST /warehouses/{id}/delete` now has three response branches: terminal success (200 + `HX-Redirect: /warehouses`, mirrors `product_delete`), stock-blocked (swaps `partials/warehouse_delete_wrap.html` in place with the WH-03 non-overridable guard message), and last-active-warning (swaps the same partial with the warn-then-confirm card, `confirm=1` re-POST completes the delete).
- `soft_delete_warehouse`'s guard logic in `app/services/warehouses.py` is completely untouched — only the rendering location of its warning states moved, per D-02.
- Fixed 5 pre-existing tests that asserted the old inline-row POST response shape (4 removed as fully superseded, 1 rewritten to assert the new terminal-success 200 + HX-Redirect shape while keeping its list-filtering assertions unchanged).

## Task Commits

Each task was committed atomically:

1. **Task 1: Dedicated add/edit routes + templates (D-01, D-02)** - `97db26f` (feat)
2. **Task 2: Fix tests broken by the route response-shape change** - `dc5045b` (test)

**Plan metadata:** committed by this SUMMARY (worktree mode — orchestrator handles the final docs commit centrally)

## Files Created/Modified

- `app/routes/warehouses.py` - Added `GET /warehouses/new`, `GET /warehouses/{id}/edit`; rewrote `warehouse_add`/`warehouse_update` to redirect-after-success/422-re-render; rewrote `warehouse_delete` with a 404 guard, terminal-success `HX-Redirect`, and a swap of the new delete-wrap partial for warn states. `_warehouses_context` left untouched (still used by `warehouses_page`/`warehouse_restore`) — its now-partially-unused warning/stock-blocked/error params are 20-03's cleanup scope.
- `app/templates/pages/warehouse_form.html` (new) - Add/edit form page, mirrors `product_form.html`'s structure (heading branch, name/address fields, `.form-actions`, destructive zone including the delete-wrap include).
- `app/templates/partials/warehouse_delete_wrap.html` (new) - Three mutually-exclusive branches (stock-blocked / last-active-warning / default delete button), all `hx-post`ing to `/warehouses/{id}/delete` and targeting `#warehouse-delete-wrap` with `hx-swap="outerHTML"`. Warn-state copy ported verbatim from the old `warehouse_rows.html` inline rows.
- `tests/test_warehouses.py` - Added 9 new web-slice tests for the dedicated pages; removed 4 tests superseded by them; rewrote 1 test to assert the new terminal-success delete response shape; dropped the now-unused `import re`.

## Decisions Made

- The plan's suggested `this.closest('div').remove()` for the last-active-warning card's "Отмена" (dismiss) button would only remove the nested `.form-actions` button bar (leaving the warning text stranded), because the warning card wraps its buttons in a nested `.form-actions` div — the same structural issue the ORIGINAL `warehouse_rows.html` implementation avoided by targeting `tr` specifically (a selector that skips past the nested div). I used the equivalent specific-selector approach here: `this.closest('.error-block').remove()`, which correctly removes the entire warning card in one action, matching the original's intent ("or equivalent" per plan text).

## Deviations from Plan

None - plan executed exactly as written, aside from the one implementation-detail decision documented above (Rule 1 — the plan's literal suggested selector would not have worked correctly, `.error-block` is the correct equivalent).

## Issues Encountered

The full test suite (`uv run pytest -q`) had 4 pre-existing failures after Task 1 landed, caused by the exact response-shape change Task 2 is scoped to fix. Confirmed all 4 failures matched Task 2's named target tests before proceeding — no surprises, Task 2 resolved them all and the full suite (737 tests) passed green afterward.

## Known Transitional State (not a stub, deferred to 20-03 by plan design)

`app/templates/pages/warehouses.html` still contains the OLD inline add-form (`hx-post="/warehouses" hx-target="#warehouse-rows" hx-swap="outerHTML"`), which this plan's route changes make functionally stale: submitting it now triggers a 303 redirect rather than returning the `warehouse_rows.html` partial the form's `hx-target`/`hx-swap` expect. This is **intentional and explicitly out of scope** — the plan's objective states this file is untouched in THIS plan, with its cosmetic restructure (replacing the inline form with a `Добавить склад` CTA link to `/warehouses/new`, per D-01 and the UI-SPEC Copywriting Contract) deferred to 20-03. No automated test exercises the inline form's real htmx round-trip (TestClient doesn't execute JS), so the suite stays green per the plan's explicit design; a manual user visiting `/warehouses` and using the OLD inline add form before 20-03 lands would see broken behavior. This is flagged here for visibility, not treated as a plan defect.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- WH-02 (dedicated add/edit page) and WH-03 (relocated delete guard UI) are both shipped and covered by passing tests.
- 20-03 can now safely restructure `warehouses.html`/`warehouse_rows.html` (new item_count/last_receipt columns, single "Изменить" link, CTA link replacing the inline add form) — the routes it will point at (`/warehouses/new`, `/warehouses/{id}/edit`) already exist and are stable.
- `_warehouses_context`'s now-partially-dead `warning_id`/`stock_blocked_id`/`stock_blocked_qty`/`errors`/`form`/`error_entry_id`/`error_form` params are explicitly left for 20-03 to remove once `warehouse_rows.html` stops reading them (noted in the route file's docstring/comments).

---
*Phase: 20-warehouses-batch-split-transfers*
*Completed: 2026-07-16*

## Self-Check: PASSED

All created files exist on disk; all task/summary commits (97db26f, dc5045b, 6f48cb3) confirmed in git log.
