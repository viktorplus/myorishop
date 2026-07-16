---
phase: 20-warehouses-batch-split-transfers
plan: 04
subsystem: api
tags: [sqlalchemy, fastapi, tdd, inventory, transfers]

# Dependency graph
requires: []
provides:
  - "register_transfer(new_expiry='', new_comment='') same-warehouse split support (D-05/D-06/D-07)"
  - "register_transfer success dict carries real transferred int qty under 'qty' key (D-11)"
affects: [20-05, 20-06, 20-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Override-or-inherit ternary discipline: `x_clean if x_clean else source.x`, never a bare `or` (preserves legitimate falsy source values, mirrors existing price_cents direct-assignment convention)"

key-files:
  created: []
  modified:
    - app/services/transfers.py
    - tests/test_transfers.py

key-decisions:
  - "SAME_WAREHOUSE_ERROR removed entirely (confirmed via grep: zero other references in repo) and replaced with SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR, gated on both new_expiry/new_comment being blank after .strip()"
  - "Same-warehouse-blank-overrides validation placed BEFORE the oversell warn-but-allow check, per RESEARCH Pitfall 4, so a blocked same-warehouse split never reaches the oversell screen"

patterns-established:
  - "Free-text override params follow .strip()-then-ternary discipline (never bare truthy or `or`) — same convention later plans (20-05..07) must follow when wiring these params through routes/templates"

requirements-completed: [XFER-01]

# Metrics
duration: 10min
completed: 2026-07-16
---

# Phase 20 Plan 04: Same-Warehouse Batch Split + Qty-Echo Fix Summary

**Extended `register_transfer` with same-warehouse "split" support gated by a required-override validation (D-05/D-06/D-07), plus a fix to the success return dict so it carries the actual transferred integer quantity instead of the caller's raw string (D-11).**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-16T18:15:37+02:00
- **Completed:** 2026-07-16T18:21:01+02:00
- **Tasks:** 2 completed
- **Files modified:** 2 (`app/services/transfers.py`, `tests/test_transfers.py`)

## Accomplishments
- Same-warehouse transfers with at least one non-blank override (`new_expiry` or `new_comment`) now succeed and create a correctly split destination batch, leaving the source batch's remaining quantity and other attributes unchanged.
- Same-warehouse transfers with both overrides blank (or whitespace-only) are blocked before any write, with the exact locked UI-SPEC Russian copy rendered via `errors["form"]`.
- Cross-warehouse transfers are fully unaffected — override params remain optional, blank still inherits from source (regression guard test added).
- `register_transfer`'s success dict now includes `"qty"` as the real parsed integer, closing the pre-existing v1.1 code-review debt item tracked in STATE.md Deferred Items.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN):

1. **Task 1: D-05/D-06/D-07 — same-warehouse split + override-or-inherit**
   - `00c3188` (test) — add failing tests for same-warehouse split + override discipline
   - `5424b0a` (feat) — allow same-warehouse batch split with required override
2. **Task 2: D-11 — success return dict carries the real transferred quantity**
   - `7065689` (test) — add failing test for D-11 qty echo as int
   - `a651235` (feat) — success return dict carries actual transferred qty

**Plan metadata:** committed with this SUMMARY.md (worktree mode — STATE.md/ROADMAP.md excluded, owned by orchestrator)

## Files Created/Modified
- `app/services/transfers.py` - `SAME_WAREHOUSE_ERROR` constant removed; `SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR` added; `register_transfer` gained `new_expiry`/`new_comment` keyword-only params, same-warehouse-blank-overrides validation, override-or-inherit ternary for `dest.expiry`/`dest.comment`, and `"qty"` key in the success dict
- `tests/test_transfers.py` - `test_reject_same_warehouse` rewritten to `test_same_warehouse_blank_overrides_blocked`; 5 new tests added (expiry override split, comment override split, cross-warehouse override wins, cross-warehouse blank-inherits regression guard, whitespace-only-treated-as-blank) plus `test_transfer_qty_echo_is_int_not_raw_string`

## Decisions Made
- Followed plan's exact validation ordering: same-warehouse-blank-overrides check placed immediately after destination-warehouse-active validation and BEFORE the oversell check, matching the plan's action spec and RESEARCH Pitfall 4.
- Confirmed via repo-wide grep (`app` + `tests`) that `SAME_WAREHOUSE_ERROR` had zero remaining references before removing it — no dead references left elsewhere.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`register_transfer(new_expiry=, new_comment=)` and the `"qty"` return key are now the stable interface for wave 2 plans (desktop routes, mobile routes, templates) to wire the override fields and success messaging through. Full test suite (726 tests) green — no regressions in adjacent files.

---
*Phase: 20-warehouses-batch-split-transfers*
*Completed: 2026-07-16*
