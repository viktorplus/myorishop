---
phase: 23-dashboard-history-rebuild
plan: 05
subsystem: ui
tags: [fastapi, jinja2, htmx, history-ledger, mobile, pagination]

# Dependency graph
requires:
  - phase: 23-dashboard-history-rebuild
    provides: "23-02's extended history_view (customer/category/start_iso/end_iso kwargs, HISTORY_TYPE_COLUMNS, per-row warehouse key, 'columns' return key)"
provides:
  - "GET /m/history with type/product/category/customer/from/to filters, numbered page_window/paginate pagination (parity with desktop /history, D-10)"
  - "mobile_partials/history_pagination.html — OOB-swappable pagination sibling, retires history_load_more.html"
  - "mobile_partials/history_cards.html — self-wrapping #history-cards, per-type field narrowing driven by HISTORY_TYPE_COLUMNS"
affects: ["23-03 (dashboard feed deep-links into this route)", "23-06/23-07 (any later mobile nav/parity work touching /m/history)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Local _resolve_history_period date-range resolver, duplicated (not imported) from app/routes/history.py per this codebase's established route-helper duplication convention (_metrics_context precedent)"
    - "Dual-fragment HX-Request response (main + OOB sibling), mirroring mobile_finance.py's _movement_success concat pattern"

key-files:
  created:
    - app/templates/mobile_partials/history_pagination.html
  modified:
    - app/routes/mobile_history.py
    - app/templates/mobile_pages/history.html
    - app/templates/mobile_partials/history_cards.html
    - tests/test_mobile_history.py
  deleted:
    - app/templates/mobile_partials/history_load_more.html

key-decisions:
  - "product param reinstated on mobile_history_page per D-10 (supersedes the Phase-11 CONTEXT decision to drop it) — deep-link only, no visible Товар control on mobile"
  - "Local _resolve_history_period omits presets/active_preset entirely (unlike history.py's fuller version) since mobile has no preset bar (D-10's 'own simpler layout') — only from_date/to_date/error are needed"
  - "Empty-state message condition extended to fire on every new filter dimension (product/category/customer/date), not just type, matching the parity intent behind D-10"

patterns-established:
  - "mobile_partials/history_pagination.html as the canonical OOB-swappable pagination sibling for any future mobile list migrating off a load-more control"

requirements-completed: [HIST-01, HIST-02, HIST-03, HIST-04]

# Metrics
duration: ~25min
completed: 2026-07-17
---

# Phase 23 Plan 05: Mobile History Rebuild Summary

**Mobile `/m/history` now matches desktop's type-first column narrowing, all 4 filter dimensions, and numbered `page_window`/`paginate` pagination — rendered as cards, retiring the legacy `history_load_more.html` load-more control.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-17T18:25:00Z (approx)
- **Completed:** 2026-07-17T18:52:00Z
- **Tasks:** 2 completed
- **Files modified:** 5 (1 created, 3 modified route/templates, 1 deleted, plus tests)

## Accomplishments

- `mobile_history_page` gains `product` (reinstated, D-10), `category`, `customer`, `from`/`to` query params, all passed into Plan 02's extended `history_view` unchanged.
- New local `_resolve_history_period` date-range resolver (duplicated from `app/routes/history.py`, not imported — matches this codebase's `_metrics_context` route-helper duplication convention): blank/blank means no date filter at all (D-04 regression guard), malformed/inverted input falls back to today with an inline RU error, never a raw 500.
- `has_next` sentinel replaced entirely by `page_window`/`extra_qs` re-serialization mirroring desktop's `history.py` shape — every active filter dimension survives a pagination click, and every pagination state survives a filter change.
- HX-Request responses now always render two sibling fragments — `history_cards.html` (main) + `history_pagination.html` (OOB) — mirroring `mobile_finance.py::_movement_success`'s concat pattern.
- `mobile_pages/history.html` gained a new `#history-filters` wrapper with stacked Тип/Категория/Покупатель(conditional, sale/return-only)/с/по fields, all wired with the shared `hx-include`/`hx-target="#history-cards"` contract.
- `history_cards.html` self-wraps in `#history-cards` (with `hx-swap-oob` support), and narrows each card's field lines per `HISTORY_TYPE_COLUMNS` when a stock-affecting type is selected; the unfiltered/audit-type view renders today's card markup completely unchanged.
- New `history_pagination.html` wraps the shared `partials/pagination.html`, a DOM sibling of `#history-cards`, never nested — a filter swap can never destroy the pagination control (CR-01 precedent).
- `mobile_partials/history_load_more.html` deleted (verified no remaining references); `mobile_partials/cash_history_load_more.html` (a different, unrelated file) is untouched.

## Task Commits

1. **Task 1: mobile_history.py — full filter set + numbered pagination** — `5a8cf82` (feat)
2. **Task 2: mobile templates — stacked filters, self-wrapping cards, OOB pagination sibling** — `6475c30` (feat)

**Plan metadata:** committed separately per worktree protocol (this SUMMARY.md commit).

## Files Created/Modified

- `app/routes/mobile_history.py` — full filter set (product/category/customer/from/to), local `_resolve_history_period`, `page_window`/`extra_qs` pagination, dual-fragment HX-Request response
- `app/templates/mobile_pages/history.html` — new `#history-filters` wrapper, stacked filter fields, pagination include replaces load-more include
- `app/templates/mobile_partials/history_cards.html` — self-wrapping `#history-cards`, per-type field narrowing via `columns`
- `app/templates/mobile_partials/history_pagination.html` — new, OOB-swappable pagination sibling
- `app/templates/mobile_partials/history_load_more.html` — deleted (superseded)
- `tests/test_mobile_history.py` — updated the product-signature test (now asserts presence, not absence) and the paging test (numbered-pagination-bar assertion replaces the old load-more-link substring); added a product-filter-narrowing test and a filtered-total pagination-bar test mirroring desktop's `test_web_history_pagination_bar_reflects_filtered_total`

## Decisions Made

- Kept the local date-range resolver minimal (no `presets`/`active_preset` computation) since mobile's UI-SPEC explicitly rules out a preset bar for this screen (D-10's "own simpler layout") — only `from_date`/`to_date`/`error` are consumed by the route and template.
- Extended the empty-state condition (`Нет операций по выбранным фильтрам.` vs `Операций пока нет.`) to check every new filter dimension (product/category/customer/date), not just `type_filter` as the pre-existing code did — a direct, minimal consequence of adding the new filters that keeps the empty-state message accurate under every new filter combination.

## Deviations from Plan

None — plan executed exactly as written. Both tasks matched their `must_haves`/`acceptance_criteria` without requiring any Rule 1-4 auto-fixes to plan scope.

## Known Stubs / Gaps

- **`Покупатель` column always shows «Розница» on mobile History, even for sales linked to a real customer.** `history_view` (Plan 02, `app/services/operations.py`) selects only `Operation, Product, Batch, Warehouse` into each row — it does not outerjoin `Sale`/`Customer` for row display (it only outerjoins `Sale` transiently when the `customer` filter itself is active, and doesn't select `Customer` into the returned tuple even then). This plan's card template renders `r.customer` per the plan's literal spec (mirroring `recent_sales.html`'s exact idiom, matching desktop Plan 04's identical instruction), but since `history_view`'s row dicts never carry a `customer` key, the `{% if r.customer %}` branch is always falsy and the muted «Розница» fallback always renders — never a raw error, never `None`, so page-load / filtering / pagination all continue to work correctly, but the customer name is not yet actually plumbed through for either History surface.
  - This gap is NOT specific to mobile: desktop Plan 04 (running in the same wave, in a separate worktree) faces the identical situation, since neither plan's `files_modified` list includes `app/services/operations.py` and neither plan's task text specifies extending `history_view`'s query with a `Sale`→`Customer` outerjoin.
  - Not auto-fixed here (Rule-scope boundary): fixing it requires modifying `app/services/operations.py`, a shared file this plan does not own and that Plan 04 may be editing concurrently in a sibling worktree in the same wave — touching it risked a merge conflict with no coordination channel between parallel executors.
  - Suggested follow-up: extend `history_view`'s base query with an unconditional `outerjoin(Sale, Operation.sale_id == Sale.id).outerjoin(Customer, Sale.customer_id == Customer.id)` (cheap, mirrors the existing "Warehouse always outerjoined" precedent from Plan 02) and add a `"customer"` key to each row dict — this single change would make both the desktop and mobile `Покупатель` columns display correctly with no template changes needed on either surface.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Mobile `/m/history` is ready for the dashboard feed's deep link (`/m/history?type=X&product=Y`, DASH-05/Plan 03) — the reinstated `product` param resolves it correctly even with no visible Товар control.
- `mobile_partials/history_pagination.html` establishes a reusable OOB-pagination-sibling pattern for any future mobile list still on a load-more control.
- The `Покупатель`-column customer-name gap documented above (shared with desktop Plan 04) should be closed in a small follow-up touching `app/services/operations.py::history_view` once both Plan 04 and Plan 05 have landed, to avoid the two parallel worktrees colliding on the same file.
- Full test suite: 868 passed, 0 failed (`uv run pytest`, full run) — no regressions in `tests/test_history.py` (desktop, cross-checked per the plan's verification section) or anywhere else in the suite.

---
*Phase: 23-dashboard-history-rebuild*
*Completed: 2026-07-17*
