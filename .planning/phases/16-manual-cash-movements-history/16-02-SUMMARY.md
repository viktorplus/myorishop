---
phase: 16-manual-cash-movements-history
plan: 02
subsystem: finance
tags: [cash-ledger, sqlalchemy, service-layer, pagination, validation, tdd]

# Dependency graph
requires:
  - phase: 15-cash-ledger-foundation
    provides: record_cash_movement (single write path), compute_balance (live SUM), CashMovement model, append-only triggers
  - phase: 16-manual-cash-movements-history (plan 01)
    provides: CASH_CATEGORIES (9 keys), CASH_BUCKETS (4 buckets), CASH_BUCKET_LABELS
provides:
  - record_manual_movement — thin manual-entry write wrapper (server-side sign, allow-list, comment rule, negative-balance gate)
  - cash_history_view — paginated, bucket-filtered, newest-first read over the whole cash ledger
  - RU validation constants (AMOUNT_ERROR, CATEGORY_ERROR, NOTE_REQUIRED_ERROR, SAVE_FAILED_ERROR)
affects: [16-03-routes-templates-desktop, 16-04-routes-templates-mobile]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Manual-entry service wrapping the single write path (validate -> gate -> single-write, mirrors register_writeoff)"
    - "Coarse bucket -> category set filter via CASH_BUCKETS.get(bucket) -> category.in_(cats)"
    - "Server-applied sign by direction (never trust client sign)"

key-files:
  created: []
  modified:
    - app/services/finance.py
    - tests/test_finance.py

key-decisions:
  - "Basic sign tests pre-seed a covering balance so the D-05 negative gate does not fire (the plan's bare-balance example collides with D-05; sign behavior verified independently)"
  - "Blank note stored as NULL (note.strip() or None); non-blank note stored stripped"

patterns-established:
  - "record_manual_movement: (result, errors) shape identical to register_writeoff so routes branch verbatim"
  - "cash_history_view: operations.history_view read shape, simplified to bare CashMovement rows, coarse-bucket .in_ filter"

requirements-completed: [FIN-03, FIN-04, FIN-05, FIN-07]

# Metrics
duration: 12min
completed: 2026-07-15
---

# Phase 16 Plan 02: Manual Cash Movements & History Service Layer Summary

**Two new functions in the single-write-path module: `record_manual_movement` (server-side sign + allow-list + mandatory-comment + negative-balance warn-but-allow) and `cash_history_view` (paginated, coarse-bucket-filtered, newest-first read), with `record_cash_movement`/`compute_balance` untouched.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 (both TDD)
- **Files modified:** 2

## Accomplishments
- `record_manual_movement` enforces the full security-critical (V5) tier server-side: direction-based sign (D-02a), category allow-list via `CASH_BUCKETS` membership (T-16-02), amount parse via `to_cents` rejecting blank/zero/negative (T-16-01), mandatory-comment rule for `withdrawal_other`/`deposit_correction` (D-04), and the negative-balance warn-but-allow gate for withdrawals only (D-05) — ZERO writes on any validation/gate path, one signed row on success delegated to `record_cash_movement`.
- `cash_history_view` paginates/sorts/bucket-filters the entire cash ledger with portable ORM: newest-first (`created_at desc, seq desc`), coarse bucket via `CASH_BUCKETS.get(bucket) -> category.in_(cats)` (Pitfall 3), unknown bucket ignored (T-16-07), server-side page clamp, returning the `{rows, page, total, total_pages, bucket}` contract for Plans 03/04.
- Single-write-path invariant preserved: `record_cash_movement` and `compute_balance` are byte-for-byte unchanged.

## Task Commits

Each task was committed atomically (TDD: test -> feat):

1. **Task 1 RED: failing tests for record_manual_movement** - `b4dfdfd` (test)
2. **Task 1 GREEN: record_manual_movement wrapper** - `10d53be` (feat)
3. **Task 2 RED: failing tests for cash_history_view** - `de9a2b2` (test)
4. **Task 2 GREEN: cash_history_view read service** - `26c359d` (feat)

## Files Created/Modified
- `app/services/finance.py` - Added `record_manual_movement`, `cash_history_view`, `_CASH_DEFAULT_ORDER`, and RU error constants; extended imports (`to_cents`, `CASH_BUCKETS`, `LIST_PAGE_SIZE`, `IntegrityError`). `record_cash_movement`/`compute_balance` unchanged.
- `tests/test_finance.py` - Added FIN-03/04/05 service tests (`test_withdraw_*`, `test_deposit_*`, `test_negative_*`) and FIN-07 read tests (`test_cash_history_*`).

## Decisions Made
- The plan's `<behavior>` example for the basic withdrawal sign test ("balance 0, withdraw 15,00 -> writes one row") collides with the D-05 negative-balance gate (a withdrawal on a zero balance correctly warns instead of writing). Resolved by pre-seeding a covering `sale` credit in the sign/comment success tests so the gate does not fire — the sign and comment behaviors are verified independently of the gate, and the gate itself is verified in dedicated `test_negative_*` tests. Implementation matches the plan's action step (6) verbatim.
- Blank `note` is persisted as `NULL` (`note.strip() or None`); the comment rule only blocks the two mandatory-comment categories.

## Deviations from Plan

None to the implementation contract — `record_manual_movement` and `cash_history_view` were built exactly as specified (signatures, steps, return shapes, portable ORM). The only adjustment was in **test authoring** (seeding a covering balance in the sign/comment success cases, see Decisions) to reconcile the plan's loose bare-balance example with the hard D-05 gate. No source-code deviation, no scope creep.

## Issues Encountered
- Initial GREEN run failed 3 tests (`test_withdraw_writes_one_negative_row`, `test_withdraw_other_with_comment_succeeds`, `test_withdraw_supplier_allows_blank_comment`) because they withdrew from a zero balance and correctly hit the D-05 negative-balance gate (zero writes). Fixed by pre-seeding a positive balance in those tests — confirming the gate works and isolating the sign/comment assertions.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Service layer for FIN-03/04/05/07 is complete and green (42/42 `test_finance.py` tests pass, ruff clean, no raw SQL, no `|safe`).
- Plans 03 (desktop routes/templates) and 04 (mobile routes/templates) can now branch on `(result, errors)` identically to the writeoff/sale routes: `result.get("negative_balance")` -> 200 warn, `errors` -> 422, success -> 200; and render `cash_history_view`'s `{rows, page, total, total_pages, bucket}` contract.

## Self-Check: PASSED

- FOUND: app/services/finance.py (record_manual_movement, cash_history_view)
- FOUND: tests/test_finance.py (FIN-03/04/05/07 service tests)
- FOUND commits: b4dfdfd, 10d53be, de9a2b2, 26c359d
- 42/42 test_finance.py tests pass; ruff clean; no raw/SQLite SQL; no `|safe`.

---
*Phase: 16-manual-cash-movements-history*
*Completed: 2026-07-15*
