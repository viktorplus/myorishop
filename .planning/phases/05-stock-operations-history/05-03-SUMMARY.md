---
phase: 05-stock-operations-history
plan: 03
subsystem: sales
tags: [fastapi, htmx, jinja2, sqlalchemy, sqlite, ru-labels]

# Dependency graph
requires:
  - phase: 05-stock-operations-history (05-01)
    provides: OPERATION_TYPE_LABELS constant, tests/test_returns.py RED contract (link_and_freeze, returnable_cap, entry_point)
  - phase: 04-sales-customers
    provides: Sale header + sale ops + Operation.sale_id link, register_sale frozen-snapshot pattern (D-11/D-12), recent_sales/purchase_history partials (return entry points)
provides:
  - app/services/returns.py - returnable_qty() (D-08 sold-minus-returned aggregation) + sold_qty() + register_return() (frozen-snapshot D-07 write via record_operation)
  - app/routes/returns.py - GET /returns (resolves origin sale op from origin_op_id or sale_id+product_id fallback), POST /returns
  - app/templates/partials/return_form.html - compact return form (context line, returnable hint, frozen-price display, no editable price)
  - Extended recent_sales.html / purchase_history.html with a neutral «Вернуть» entry-point link per sale line + a #return-slot
  - app.include_router(returns.router) wired in app/main.py
  - OPS-02 fully functional: operator can return sold stock from a specific sale line, capped at the returnable remaining, without corrupting frozen profit figures
affects: [05-04-corrections, 05-05-history, 06-reports]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "#return-slot lives OUTSIDE the oob-swapped #recent-sales wrapper (own sibling div, emitted only on the primary non-oob include) - an oob refresh of the recent-sales table must never wipe an in-progress or just-saved return form nested inside it"
    - "GET /returns resolves the origin sale op two ways: explicit origin_op_id (the real entry-point link), or a sale_id+product_id fallback query for the latest matching sale op - covers both the click-through link and a lighter-weight direct-link shape"

key-files:
  created:
    - app/services/returns.py
    - app/routes/returns.py
    - app/templates/partials/return_form.html
  modified:
    - app/main.py
    - app/templates/partials/recent_sales.html
    - app/templates/partials/purchase_history.html

key-decisions:
  - "The return form's price line is display-only (no editable input) but still renders the frozen unit_price_cents via | cents - required by the entry-point web test and by the operator seeing what price the return will use"
  - "sold_qty() is exposed as a public helper alongside returnable_qty()/register_return() (the plan's named exports) so the route can render the returnable hint's denominator ('из {sold}') without duplicating the aggregation query"
  - "recent_sales.html's #return-slot is conditioned on {% if not oob %} - the oob-refresh render (after a sale or return) must not re-emit a second #return-slot into the response body, which would either duplicate the id or (in the oob-only fragment) sit as orphaned leftover content merged into an unrelated main-target swap"

requirements-completed: [OPS-02]

# Metrics
duration: 10min
completed: 2026-07-10
---

# Phase 5 Plan 3: Return Slice Summary

**Sale-linked return vertical slice (OPS-02): `register_return()` writes one `return` op (qty_delta>0) copying the FROZEN origin sale op's unit_price_cents/unit_cost_cents through `record_operation`, `/returns` routes + a compact return-form template reuse the recent-sales/purchase-history entry points, with a server-enforced returnable cap (sold − already-returned) and no editable price field.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-10T00:57:00+02:00 (approx.)
- **Completed:** 2026-07-10T01:07:00+02:00
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `app/services/returns.py`: `sold_qty(session, sale_id, product_id)` (total sold, positive) and `returnable_qty(session, sale_id, product_id)` (D-08: sold minus already-returned, aggregated per sale_id+product_id via `func.coalesce(func.sum(...))`). `register_return(session, *, origin_op_id, qty_raw)` rejects a missing/non-sale/unlinked origin op (T-05-08), a non-positive or unparsable qty, a fully-returned line, and an over-cap request — all with ZERO writes — then writes exactly one `return` op with `qty_delta=+qty` copying `origin.unit_price_cents`/`origin.unit_cost_cents` (D-07, never `Product.*_cents`) and `payload={"origin_op_id": origin.id}` through the single write path `record_operation`.
- `app/routes/returns.py`: `GET /returns` resolves the origin sale op from `origin_op_id` (preferred) or falls back to the latest `sale` op matching `sale_id`+`product_id` (covers the real entry-point link and the lighter query-only shape the web test exercises), then renders the return form with the frozen price, the sold total, and the returnable remaining. `POST /returns` wraps `register_return` in `try/except Exception: logger.exception(...)` → RU 422 (never a raw 500), re-renders form context on any validation error, and on success rides an oob refresh of `recent_sales.html` so the remaining-returnable count updates there too. Registered in `app/main.py`.
- `app/templates/partials/return_form.html`: compact single-column block (`#return-form-wrap`) — context line («Возврат из продажи от {дата} — {название} ({код}), цена {цена}»), muted returnable hint («Доступно к возврату: {remaining} из {sold}.»), the «Эта позиция уже возвращена полностью.» empty state (no submit) when remaining ≤ 0, and otherwise a form with hidden `origin_op_id`, «Количество к возврату» (defaults to remaining, `max`=remaining), inline `errors.quantity`, and «Оформить возврат». No editable price input anywhere.
- `recent_sales.html` and `purchase_history.html` each gained a neutral «Вернуть» text link per sale line (`hx-get="/returns?sale_id=...&product_id=...&origin_op_id=..."` targeting `#return-slot`) and a `#return-slot` div. In `recent_sales.html` the slot lives OUTSIDE the oob-swapped `#recent-sales` wrapper and is only emitted on the primary (non-oob) render, so an oob refresh after a sale or return never wipes an in-progress/just-saved return form.
- `tests/test_returns.py` (the Wave-0 RED contract from 05-01) is now fully GREEN: 3/3 tests pass (`test_link_and_freeze`, `test_returnable_cap`, `test_web_return_entry_point`). Full suite (excluding the still-RED Wave-4/5 `test_corrections.py`/`test_history.py`) is green: 157 passed.

## Task Commits

Each task was committed atomically:

1. **Task 1: returns service — returnable_qty + register_return** - `8dd6252` (feat)
2. **Task 2: /returns routes + main.py wiring; entry-point test GREEN** - `4297930` (feat)
3. **Task 3: return form template + entry-point links + oob refresh; OPS-02 tests GREEN** - `6425902` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `app/services/returns.py` - `sold_qty()`, `returnable_qty()`, `register_return()`
- `app/routes/returns.py` - `GET /returns`, `POST /returns`
- `app/templates/partials/return_form.html` - the compact return form (swapped whole on GET load and every POST response)
- `app/templates/partials/recent_sales.html` - added a «Действие» column («Вернуть» link) + `#return-slot`
- `app/templates/partials/purchase_history.html` - added a «Действие» column («Вернуть» link) + `#return-slot`
- `app/main.py` - added `returns` import + `app.include_router(returns.router)`

## Decisions Made

- The return form displays the frozen `unit_price_cents` (via `| cents`) as read-only context, not an editable field — required by `test_web_return_entry_point` and by the operator seeing what price the return will record.
- `sold_qty()` was added as a public helper (alongside the plan's named exports `returnable_qty`/`register_return`) so the route can render «из {sold}» without a duplicate aggregation query in the route module.
- Moved `#return-slot` outside `<div id="recent-sales">` and conditioned its emission on `{% if not oob %}` (see Deviations) — the plan's own text ("Add a `<div id="return-slot"></div>` slot below the table") did not specify the oob-safety detail; this is the correct reading given `recent_sales.html`'s existing oob-refresh usage from `sale_form.html`/`writeoff` flows.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - blocking issue] Built `return_form.html` during Task 2, not Task 3**

- **Found during:** Task 2 (routes + main.py wiring)
- **Issue:** Task 2's own verify command (`pytest tests/test_returns.py -k entry_point`) calls `GET /returns`, which renders `partials/return_form.html` via `TemplateResponse` — but that file is officially assigned to Task 3's `<files>`. Without it, the route would raise `TemplateNotFound` (a 500), and Task 2's verify could not pass in isolation.
- **Fix:** Created a complete `return_form.html` (context line, returnable hint, frozen-price display, no editable price field) during Task 2 so its own verify step is independently green. Task 3 then focused on extending `recent_sales.html`/`purchase_history.html` with the actual «Вернуть» entry-point links and the `#return-slot`, plus wiring the oob refresh into `return_form.html`.
- **Files modified:** `app/templates/partials/return_form.html` (created in the Task 2 commit `4297930`, extended with the oob-refresh include in the Task 3 commit `6425902`).
- **Commit:** `4297930`

**2. [Rule 1 - bug] Kept `#return-slot` outside the oob-swapped `#recent-sales` wrapper**

- **Found during:** Task 3, while wiring the oob refresh of `recent_sales.html` into `return_form.html`'s POST-success response.
- **Issue:** The plan's action text says to add `#return-slot` "below the table" inside `recent_sales.html`. If placed literally inside `<div id="recent-sales" hx-swap-oob="true">`, any oob refresh of that div (triggered by a successful sale OR a successful return) would replace the entire subtree — including whatever the return form had just rendered into `#return-slot` — because htmx applies oob swaps using a full-subtree replace matched by id. This would either silently erase an in-progress return form, or (when `recent_sales.html` is embedded non-oob as leftover content inside another route's main-target swap, e.g. `POST /sales`) leave a stray duplicate `#return-slot` element in the DOM after every sale.
- **Fix:** Moved `#return-slot` to be a sibling of `<div id="recent-sales">` (not nested inside it) and conditioned its emission on `{% if not oob %}` so it is rendered exactly once, on the page's initial (non-oob) include, and never re-emitted by an oob refresh.
- **Files modified:** `app/templates/partials/recent_sales.html`.
- **Commit:** `6425902`

None of the two deviations required an architectural decision (Rule 4) — both are execution-order/markup-nesting corrections needed to make the plan's own verify steps and interaction contract (D-06 oob refresh) actually work as specified.

## Issues Encountered

None beyond the two deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/returns` is reachable and functional end to end from both `recent_sales.html` and `purchase_history.html`; `tests/test_returns.py` is fully GREEN (3/3).
- Full suite green (157 passed) except the two intentionally-RED Wave-0 files (`tests/test_corrections.py`, `tests/test_history.py`) — exactly as designed; those turn GREEN in Waves 4-5 (05-04/05).
- No nav changes were needed or made (no nav link exists for `/returns` — it is reached only via the sale-line entry point, matching D-05's design; this is consistent with 05-02's precedent of leaving nav wiring to Claude's discretion where not blocking).
- No blockers for 05-04 (corrections): this plan did not touch `app/routes/ops.py` or `app/services/corrections.py`.

## TDD Gate Compliance

Task 1 was marked `tdd="true"`, but per the plan's own design the RED test file (`tests/test_returns.py`) was already written and committed in the prior Wave-0 plan (05-01, commit `276d2f9`) — this plan's job was to turn that pre-existing RED contract GREEN, not to author new tests. A single `feat(05-03)` commit (`8dd6252`) implements `returnable_qty`/`register_return` against the already-fixed interface; there is no separate `test(...)` commit within this plan because none was needed (RED already existed). This matches the Wave-0/Wave-N split documented in 05-01-SUMMARY.md and 05-02-SUMMARY.md, and is not a gate violation.

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-10*

## Self-Check: PASSED

All created/modified files verified present on disk; all 3 task commits (`8dd6252`, `4297930`, `6425902`) verified present in git log.
