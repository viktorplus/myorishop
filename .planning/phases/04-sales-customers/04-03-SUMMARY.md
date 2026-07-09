---
phase: 04-sales-customers
plan: 03
subsystem: sales
tags: [fastapi, sqlalchemy, htmx, jinja2, ledger, oversell]

# Dependency graph
requires:
  - phase: 04-sales-customers
    provides: "04-01 Sale/Customer models + record_operation(sale_id=); 04-02 register_sale/route/basket templates with the commented 04-03 insertion points"
provides:
  - "Aggregate oversell check inside register_sale: sums requested qty per product_id across the whole basket (Pitfall 6) before comparing to cached Product.quantity"
  - "partials/sale_oversell.html: error-block warning + button.danger confirm + neutral cancel"
  - "POST /sales oversell branch: renders the warning in-place above the intact basket, zero writes, until confirm=1"
affects: ["04-05"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Oversell two-step confirm reuses form= association (not basket re-serialization): the confirm button lives outside <form id=\"sale-form\"> but submits it via form=\"sale-form\" + hx-vals confirm=1, so the warning partial never needs to carry the basket's own field values"

key-files:
  created:
    - app/templates/partials/sale_oversell.html
  modified:
    - app/services/sales.py
    - app/routes/sales.py
    - app/templates/partials/sale_form.html

key-decisions:
  - "Oversell dismiss (\"Вернуться к корзине\") is a pure client-side DOM removal (hx-on:click removing #sale-oversell-warning) — no server round-trip, matching D-08's zero-writes-until-confirmed contract and the UI-SPEC's 'no write' requirement for the cancel action"
  - "The confirm button's form=\"sale-form\" association was chosen over re-POSTing a serialized copy of the basket, per RESEARCH Pattern 3 and the plan's explicit code example — this guarantees the exact same basket (including any operator edits made before the oversell response arrived) is what gets confirmed"

requirements-completed: [SAL-04]

# Metrics
duration: 20min
completed: 2026-07-09
---

# Phase 4 Plan 3: Oversell Safety Flow Summary

**Aggregate oversell check in register_sale (sums duplicate lines before comparing to stock) with a warn-then-confirm HTMX flow that writes zero sale ops until the operator explicitly confirms.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-09T13:05:00Z (approx.)
- **Completed:** 2026-07-09T13:26:00Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `register_sale` now aggregates requested quantity per `product_id` across every resolved basket line (before any write) and compares the sum to the cached, authoritative `Product.quantity` — two lines of the same product each individually within stock but oversold in total are correctly caught (Pitfall 6).
- When any product oversells and `confirm != "1"`, `register_sale` returns `{"oversell": [{"product", "available", "requested"}, ...]}` sorted by product name, with the header never staged and zero `sale` operations written.
- `confirm == "1"` skips the check entirely — the sale writes and `Product.quantity` may go negative (D-09, allow-negative is an explicit operator decision, not an accident).
- New `partials/sale_oversell.html`: a destructive `.error-block` (existing color role, no new CSS) listing each oversold product's name/available/requested, a `button.danger` «Продать всё равно» that re-POSTs the exact same basket via `form="sale-form"` + `hx-vals='{"confirm": "1"}'`, and a neutral «Вернуться к корзине» that dismisses the warning client-side with no server call.
- `POST /sales` renders the oversell partial in-place above the still-intact basket (the form itself is never swapped away, so entered lines survive); `partials/sale_form.html` gained a stable `id="sale-form"` so the confirm button's `form=` association resolves.

## Task Commits

Each task was committed atomically:

1. **Task 1: aggregate oversell check in register_sale** - `ef09f9b` (feat)
2. **Task 2: oversell partial + route branch + confirm/cancel wiring** - `cface6e` (feat)

_Note: this is a worktree execution; STATE.md/ROADMAP.md are updated centrally by the orchestrator after all wave-3 worktree agents complete._

## Files Created/Modified

- `app/services/sales.py` - aggregate oversell check inserted at the documented `register_sale` insertion point (between line validation and header staging); module docstring updated to describe the finished behavior instead of the placeholder
- `app/routes/sales.py` - `POST /sales` oversell branch now passes `result["oversell"]` into the `sale_form.html` context instead of the no-op stub
- `app/templates/partials/sale_form.html` - added `id="sale-form"` to the `<form>`; wired the 04-03 insertion point to `{% include "partials/sale_oversell.html" %}` when `oversell` is present
- `app/templates/partials/sale_oversell.html` (new) - the warning block: heading, one line per oversold product, confirm/cancel actions

## Decisions Made

- See `key-decisions` in frontmatter: client-side-only dismiss for the cancel action; `form=` association (not re-serialization) for the confirm re-POST.
- A small ruff-format-only tweak was applied to the Task 1 oversell-check code (one long line wrapped) and folded into the Task 2 commit rather than amending Task 1's commit, per the "never amend, always new commit" rule.

## Deviations from Plan

None - plan executed exactly as written. The one formatting tweak (ruff format wrapping a long dict-comprehension line) is not a behavior deviation and was folded into the Task 2 commit as noted above rather than tracked as a numbered deviation.

## Issues Encountered

- Task 1's own `<verify>` command (`pytest tests/test_sales.py -k oversell -x -q`) substring-matches the Task-2-dependent web test (`test_web_sale_oversell_shows_warning_and_confirm_writes` contains "oversell"), the same overlap already noted in the 04-02 SUMMARY for a different keyword. Ran the narrower `-k "oversell and not web"` slice to confirm the 3 service-level tests independently (3/3 passed), then confirmed the full 4-test `-k oversell` slice (including the web test) passes once Task 2 landed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `uv run pytest tests/test_sales.py -q` — 20 passed, 2 failed (both customer-picker tests: `test_web_customer_search_returns_rows`, `test_web_customer_quick_create_returns_chip`), exactly the tests deferred to Plan 04-05 (executed in parallel this wave by a sibling worktree agent).
- `uv run pytest -q --ignore=tests/test_customers.py` — 134 passed, 2 failed (the same two customer-picker tests). SAL-01/02/04/05 are now fully green.
- `uv run ruff check app/services/sales.py app/routes/sales.py` and `uv run ruff format --check` on the same two files both exit 0.
- No blockers. Plan 04-05 (customer picker, running concurrently) needs no changes from this plan — the oversell insertion point and the customer-header insertion point in `sale_form.html` are independent commented regions.

---
*Phase: 04-sales-customers*
*Completed: 2026-07-09*

## Self-Check: PASSED

All created/modified files verified present on disk (`app/services/sales.py`, `app/routes/sales.py`, `app/templates/partials/sale_form.html`, `app/templates/partials/sale_oversell.html`, this summary). All 3 commits (`ef09f9b`, `cface6e`, `f9d54a2`) verified present in git log.
