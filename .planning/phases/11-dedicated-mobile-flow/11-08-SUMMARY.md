---
phase: 11-dedicated-mobile-flow
plan: 08
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile]

# Dependency graph
requires:
  - phase: 11-dedicated-mobile-flow (plan 01)
    provides: mobile_client_factory test fixture, mobile_base.html layout, mobile-only CSS classes (.mobile-card, .mobile-actions, etc.)
provides:
  - "GET /m/history — mobile history card list, single Тип операции filter, load-more pagination"
  - "GET/POST /m/returns — mobile return flow reached from a history card's Вернуть action"
affects: [11-09 (main.py mobile router registration)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mobile HX combined-response pattern: two structural-sibling partials (cards + oob-swapped load-more) concatenated via HTMLResponse, mirroring desktop's CR-01 history_response.html precedent without adding an extra template file"
    - "Mobile routes replicate desktop's module-private helpers (_resolve_origin/_origin_context/_empty_context) inline rather than importing them, keeping app.routes.returns' private surface untouched"

key-files:
  created:
    - app/routes/mobile_history.py
    - app/routes/mobile_returns.py
    - app/templates/mobile_pages/history.html
    - app/templates/mobile_partials/history_cards.html
    - app/templates/mobile_partials/history_load_more.html
    - app/templates/mobile_partials/return_confirm.html
    - tests/test_mobile_history.py
    - tests/test_mobile_returns.py
  modified: []

key-decisions:
  - "History and returns built in one plan (as scoped) because desktop couples them via the Вернуть link inside history_rows.html — avoids a cross-plan dependency on the card markup"
  - "Line 4 of a history card shows the reason/note (write-off/correction) when present, else falls back to created_by — combines desktop's two separate Причина/Кто columns into one muted line, matching UI-SPEC's 'reason/note ... or created_by' composition"
  - "Mobile return success screen adds an explicit Готово link back to /m/history — desktop has no equivalent since its return form stays inline in the table"

requirements-completed: [UI-01]

# Metrics
duration: 35min
completed: 2026-07-12
---

# Phase 11 Plan 08: Mobile History & Return Flow Summary

**Mobile /m/history card list with a single Тип операции filter, plus a /m/returns confirm flow reached only from a history card's Вернуть action — both reusing history_view/register_return unchanged from desktop.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-12T20:36:00Z
- **Completed:** 2026-07-12T21:11:03Z
- **Tasks:** 2
- **Files modified:** 8 (all new)

## Accomplishments
- `GET /m/history` renders a paginated, single-filter card list identical in underlying data to desktop's 10-column history table, via `app.services.operations.history_view` unchanged
- History cards expose a `Вернуть` entry point on `sale`-type rows only, targeting `#return-slot`
- `GET/POST /m/returns` resolves the origin sale (identical `_resolve_origin` guard as desktop: only a `sale`-typed Operation with a non-null `sale_id`), enforces the same returnable cap, and writes through `app.services.returns.register_return` unchanged
- Mobile-only "Готово" exit link added to the return success screen

## Task Commits

Each task was committed atomically:

1. **Task 1: Mobile history — GET /m/history (single filter, card list, load more)** - `758bc7b` (feat)
2. **Task 2: Mobile return flow — entry from a history card, no standalone tile** - `f1f4f6c` (feat)

**Plan metadata:** pending (this SUMMARY commit)

## Files Created/Modified
- `app/routes/mobile_history.py` - `GET /m/history`, CR-01-precedent HX/full-chrome branching, no `product` filter param
- `app/routes/mobile_returns.py` - `GET/POST /m/returns`, `_resolve_origin` replicated inline (not imported from `app.routes.returns`)
- `app/templates/mobile_pages/history.html` - mobile history screen chrome, single filter `<select>`, `#return-slot` outside `#history-cards`
- `app/templates/mobile_partials/history_cards.html` - one `.mobile-card` per operation, both empty states, `Вернуть` gated on `r.op.type == "sale"`
- `app/templates/mobile_partials/history_load_more.html` - "Показать ещё" control, oob-swappable
- `app/templates/mobile_partials/return_confirm.html` - origin summary, batch/legacy label, `Доступно к возврату`, fully-returned message, success + Готово
- `tests/test_mobile_history.py` - 6 tests (empty state, receipt card, type filter + filtered-empty, sale row Вернуть link, route signature guard, paging)
- `tests/test_mobile_returns.py` - 4 tests (origin resolution + returnable count, valid return write, over-cap 422 zero-write, unresolvable origin)

## Decisions Made
- Combined-response HX pattern implemented via `HTMLResponse(cards_html + load_more_html)` in the route rather than a separate `mobile_partials/history_response.html` file, since the plan's `files_modified` list did not enumerate an extra combined-response template
- Test assertions for the type filter scope to the card's own `· <label></p>` line rather than a bare substring check, since the always-populated filter `<select>` lists every RU type label as an `<option>` (same precedent noted in desktop's `test_web_history_filters` docstring)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `mobile_history.router` and `mobile_returns.router` are ready for registration in `app/main.py` (Plan 09)
- Full test suite (373 tests) passes with these additions; no regressions to desktop `/history` or `/returns`

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*

## Self-Check: PASSED

All created files found on disk; both task commits (`758bc7b`, `f1f4f6c`) verified present in git log.
