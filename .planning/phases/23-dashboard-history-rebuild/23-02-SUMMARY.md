---
phase: 23-dashboard-history-rebuild
plan: 02
subsystem: api
tags: [sqlalchemy, fastapi, history-ledger, operations]

# Dependency graph
requires:
  - phase: 23-dashboard-history-rebuild
    provides: 23-CONTEXT.md/23-UI-SPEC.md decisions D-03/D-05/D-06/D-27 and Interaction 8's authoritative per-type column table
provides:
  - "app.services.operations.HISTORY_TYPE_COLUMNS — dict[str, tuple[str, ...]], keyed by the 6 STOCK_AFFECTING_TYPES, one shared source of truth for per-type columns"
  - "history_view(...) extended with customer/category/start_iso/end_iso kwargs, all additive and AND-combined with the existing type_filter/product_id filters"
  - "history_view(...) return dict gains a \"columns\" key (per-type tuple or None) and each row dict gains a \"warehouse\" key"
affects: ["23-03 (dashboard feed, DASH-05 shares HISTORY_TYPE_COLUMNS)", "23-04 (desktop History UI)", "23-05 (mobile History UI)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bounded candidate resolution in Python (category_options()/search_customers()) before a parameterized .in_() filter — Cyrillic-safe, no SQL string interpolation, mirrors D-27 precedent"
    - "Server-side type-gated filter (customer only applied when type_filter in sale/return) as defence-in-depth independent of caller correctness"

key-files:
  created: []
  modified:
    - app/services/operations.py
    - tests/test_history.py

key-decisions:
  - "customer/category/start_iso/end_iso are keyword-only, all default to None (no-op) — every existing call site (routes/history.py, routes/mobile_history.py) behaves byte-identically"
  - "Warehouse is always outerjoined (cheap, Batch already outerjoined) rather than conditionally, so every row — not just transfer rows — carries a warehouse key"
  - "A transfer's two sibling rows are never merged; each resolves its own batch/warehouse independently (Pitfall 6), verified by a dedicated regression test using register_transfer"

patterns-established:
  - "HISTORY_TYPE_COLUMNS as the single per-type column source of truth, to be reused unchanged by Plan 03's dashboard feed and Plan 04/05's History UIs"

requirements-completed: [HIST-01, HIST-02, HIST-03]

# Metrics
duration: 20min
completed: 2026-07-17
---

# Phase 23 Plan 02: History Backend Extension Summary

**Extended `history_view` with customer/category/date-range filters plus a shared `HISTORY_TYPE_COLUMNS` per-type column map and a per-row Warehouse join, all additive to the existing OPS-04 service.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-17T16:14:00Z (approx)
- **Completed:** 2026-07-17T16:30:50Z
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- `history_view` now accepts `customer`, `category`, `start_iso`, `end_iso` kwargs (HIST-02), all combining with AND with the existing `type_filter`/`product_id` filters, and all no-op when omitted — zero behavior change for existing callers.
- `category` resolves through `category_options(session)` in Python (Cyrillic-safe substring match) before a parameterized `Product.category.in_(...)`; `customer` resolves through the existing `search_customers(session, q)` service and is applied ONLY when `type_filter` is `"sale"` or `"return"` (D-05), enforced server-side regardless of caller intent.
- `start_iso`/`end_iso` apply a half-open `[start, end)` window on `Operation.created_at` only when both are supplied — mirrors `cash_expense_total`'s existing bound convention.
- New module constant `HISTORY_TYPE_COLUMNS: dict[str, tuple[str, ...]]`, one entry per `STOCK_AFFECTING_TYPES` member, matching 23-UI-SPEC.md Interaction 8's authoritative column table verbatim — the single shared source of truth Plan 03's dashboard feed and Plan 04/05's History UIs will reuse.
- The base query now always `outerjoin`s `Warehouse` (via `Batch.warehouse_id`), so every row dict gains a `"warehouse"` key; `history_view`'s return dict gains a `"columns"` key (`HISTORY_TYPE_COLUMNS.get(type_filter)` — `None` for "no filter" and for the 3 audit types, per D-04).
- A transfer's two sibling ledger rows are verified to each carry their OWN batch/warehouse independently — no synthesized "from → to" merge (Pitfall 6 regression test, seeded via the real `register_transfer` service).

## Task Commits

Each task followed the RED → GREEN TDD cycle with its own commits:

1. **Task 1: history_view — customer, category, date-range filters**
   - `0ef283b` (test) — 4 failing tests (RED): category Cyrillic substring match, customer no-op outside sale/return, customer narrows sale rows, half-open date-range boundary
   - `4d9d3cd` (feat) — implementation: all 4 new tests + 12 pre-existing tests green
2. **Task 2: HISTORY_TYPE_COLUMNS + Warehouse join + columns key**
   - `eb54577` (test) — 4 failing tests (RED, module-level ImportError on `HISTORY_TYPE_COLUMNS`): columns key for sale type, columns None for no-type/audit-type, every row carries a warehouse key, transfer rows carry their own warehouse (Pitfall 6)
   - `292eba8` (feat) — implementation: all 20 tests in `tests/test_history.py` green
3. **Style follow-up (in scope, lines introduced by the two feat commits only)**
   - `c4ccf47` (style) — `ruff format` applied to the new rows list comprehension and one new test literal; pre-existing unrelated formatting drift elsewhere in the file left untouched (out of scope per the task's file list)

**Plan metadata:** committed separately per worktree protocol (SUMMARY.md commit below).

## Files Created/Modified

- `app/services/operations.py` — `history_view` extended with `customer`/`category`/`start_iso`/`end_iso` kwargs; new `HISTORY_TYPE_COLUMNS` module constant; base query outerjoins `Warehouse`; return dict gains `"columns"`, row dicts gain `"warehouse"`
- `tests/test_history.py` — 8 new tests (4 for Task 1's filters, 4 for Task 2's columns/warehouse), plus 3 new imports (`Batch`, `Customer`, `Sale`, `Warehouse`, `select`, `HISTORY_TYPE_COLUMNS`, `register_transfer`)

## Decisions Made

- Kept `customer`/`category`/`start_iso`/`end_iso` out of the return dict's echoed-filter keys (unlike `type_filter`/`product_id`/`sort`) — the plan's interface contract only specifies the new `"columns"` key for the return dict; echoing the new filter values back is deferred to Plan 04/05's route layer, which owns the filter-bar template state.
- Used `assert set(HISTORY_TYPE_COLUMNS) == STOCK_AFFECTING_TYPES` as a lightweight self-check that the constant stays in sync with the ledger's stock-affecting type set if either changes in the future.

## Deviations from Plan

None — plan executed exactly as written. Both tasks matched their `must_haves`/`acceptance_criteria` without requiring any Rule 1-4 auto-fixes.

## Issues Encountered

None. One minor executor-side correction: an early `pytest`/`ruff` invocation was accidentally run against the main repo checkout (`E:\dev\myorishop`) instead of this worktree — caught immediately via a stale test-collection count, corrected by re-running from the worktree path for all subsequent commands.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `HISTORY_TYPE_COLUMNS` and the extended `history_view` are ready for Plan 03 (dashboard feed, DASH-05) and Plan 04/05 (desktop/mobile History UIs) to build template work on top of, per the plan's explicit "no template work happens in this plan" scope.
- Full test suite: 857 passed, 0 failed (up from 853 before this plan — the 4 net-new Task 2 tests; Task 1's 4 tests landed in the same intermediate full-suite run).
- No blockers or concerns for downstream plans in this phase.

---
*Phase: 23-dashboard-history-rebuild*
*Completed: 2026-07-17*

## Self-Check: PASSED

- FOUND: app/services/operations.py
- FOUND: tests/test_history.py
- FOUND: .planning/phases/23-dashboard-history-rebuild/23-02-SUMMARY.md
- FOUND commits: 0ef283b, 4d9d3cd, eb54577, 292eba8, c4ccf47, a134dc6
