---
phase: 07-category-browsing-minimum-price-guardrail
plan: 04
subsystem: sales
tags: [validation, gap-closure, sqlalchemy, pytest]

# Dependency graph
requires:
  - phase: 07-category-browsing-minimum-price-guardrail
    provides: "register_sale basket write path (plan 07-02), min_sale_cents guardrail (plan 07-03)"
provides:
  - "Negative-value guard on register_sale's per-line price parse, closing 07-VERIFICATION.md's one open gap and 07-REVIEW.md CR-01"
affects: [sales, catalog, reports]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Reuse catalog.PRICE_ERROR + parse_optional_cents's negative-amount convention at every money-field parse site, including per-line sale prices"]

key-files:
  created: []
  modified:
    - app/services/sales.py
    - tests/test_sales.py

key-decisions:
  - "Guard placed as an else-clause on the existing try/except (fires only after a successful to_cents parse), keeping the ValueError and empty-string branches untouched"

patterns-established: []

requirements-completed: [PRICE-01]

# Metrics
duration: 12min
completed: 2026-07-10
---

# Phase 07 Plan 04: Reject Negative Sale-Line Prices Summary

**register_sale now rejects a negative per-line sale price with catalog.PRICE_ERROR, independent of whether the product has a min_sale_cents floor configured, closing CR-01.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-10T21:47:00Z
- **Completed:** 2026-07-10T21:59:31Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- `register_sale`'s per-line price parse now rejects `price_cents < 0` after a successful `to_cents` parse, mirroring `catalog.parse_optional_cents`'s existing negative-amount guard verbatim (same `catalog.PRICE_ERROR` constant/convention, no new error path).
- The guard fires whether or not `Product.min_sale_cents` is set, so the default no-floor product state (every product until an operator opts in, per D-06) is no longer able to slip a negative "revenue" line past validation.
- Three regression tests added: unset-floor rejection, set-floor rejection (proves independence from the `below_minimum` check), and a web-level `POST /sales` 422 assertion with zero ledger writes.

## Task Commits

Each task was committed atomically:

1. **Task 1: Reject negative sale-line prices in register_sale** - `def53f9` (fix)

**Plan metadata:** (final docs commit follows this summary)

_Note: this task carried `tdd="true"` but was executed as a single commit (test edits + implementation together) rather than separate RED/GREEN commits — see TDD Gate Compliance below._

## Files Created/Modified

- `app/services/sales.py` - Added an `else` clause to the existing per-line price `try/except` in `register_sale`: after a successful `to_cents` parse, `price_cents < 0` sets `errors[f"price-{i}"] = catalog.PRICE_ERROR` and resets `price_cents = None`.
- `tests/test_sales.py` - Added `from app.services import catalog` import and 3 new tests: `test_negative_price_rejected_without_min_sale_configured`, `test_negative_price_rejected_with_min_sale_configured`, `test_web_sale_negative_price_rejected`.

## Decisions Made

- Placed the new check as an `else` on the existing `try/except` block (executes only when `to_cents` succeeds) rather than restructuring the parse block, keeping the diff minimal and the existing `PRICE_REQUIRED_ERROR`/`ValueError` branches untouched, per the plan's explicit instruction.

## Deviations from Plan

None — plan executed exactly as written. One out-of-scope, pre-existing issue was discovered and logged (not fixed) per the executor's scope-boundary rule:

- **Pre-existing `ruff check` I001 (import block un-sorted)** in `tests/test_sales.py` line 20. Confirmed via `git show <prior-commit>:tests/test_sales.py | ruff check --stdin-filename tests/test_sales.py -` that this warning already fired on the file before this plan's edits. Logged to `.planning/phases/07-category-browsing-minimum-price-guardrail/deferred-items.md` (consistent with the same pre-existing pattern documented for other test files in Phase 06's deferred-items.md). Not fixed here — `app/services/sales.py` (the file this plan's behavior change lives in) passes `ruff check` cleanly.

## TDD Gate Compliance

This task has `tdd="true"` in its frontmatter. The plan's `<action>` described the test additions and the implementation change together as one unit of work for a small, well-understood gap fix (a single `if` guard mirroring an existing pattern). The executor made one `fix(07-04): ...` commit containing both the test file and the implementation change, rather than a separate `test(...)` (RED) commit followed by a `feat(...)` (GREEN) commit.

- The pre-fix "tests fail" (RED) state was not verified as a separate step/commit — no intermediate commit exists confirming the 3 new tests failed before the guard was added.
- Post-fix, all 3 new tests pass (`uv run pytest tests/test_sales.py -k "negative_price" -x` — 3 passed) and the full `test_sales.py` suite passes (33 passed) with no regression.
- **Gate sequence in git log:** no separate `test(...)` commit precedes the `fix(...)` commit — RED/GREEN gate separation was not followed for this task.

Flagging per the TDD gate enforcement rule; the net functional/test outcome (guard present, 3 new regression tests, zero regressions, full suite green) is unaffected.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 07-VERIFICATION.md's one open gap and 07-REVIEW.md's CR-01 are closed. Full test suite (`uv run pytest`) passes at 247/247 with the 3 new tests included.
- No blockers for phase re-close. Recommend the orchestrator re-run phase-level verification to confirm the gap is closed before archiving Phase 07.

---
*Phase: 07-category-browsing-minimum-price-guardrail*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/services/sales.py
- FOUND: tests/test_sales.py
- FOUND: .planning/phases/07-category-browsing-minimum-price-guardrail/07-04-SUMMARY.md
- FOUND commit: def53f9 (fix(07-04): reject negative sale-line prices in register_sale)
- FOUND commit: 14cdc98 (docs(07-04): complete negative sale-price gap-closure plan)
