---
phase: 05-stock-operations-history
plan: 01
subsystem: ledger
tags: [sqlalchemy, jinja2, pytest, fastapi, ru-labels, tdd-contract]

# Dependency graph
requires:
  - phase: 01-foundation-ledger-core
    provides: record_operation single write path, append-only Operation ledger, OPERATION_TYPES tuple
  - phase: 04-sales-customers
    provides: Sale header + sale ops + Operation.sale_id link, register_sale frozen-snapshot pattern, recent_sales/purchase_history partials (return entry points)
provides:
  - WRITEOFF_REASONS constant (6 latin reason codes -> RU labels, D-02/D-03) — the server-side write-off allow-list
  - OPERATION_TYPE_LABELS constant (every OPERATION_TYPES member -> RU label, D-16)
  - Both constants registered as Jinja globals (app/routes/__init__.py) — templates read them without per-route passing
  - Four Wave-0 RED test files fixing the interface contract for Waves 2-5 (app.services.writeoffs/returns/corrections/operations)
  - Extended append-only invariant test in tests/test_ledger.py (return/correction ops)
affects: [05-02-writeoffs, 05-03-returns, 05-04-corrections, 05-05-history]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "RU-label lookup constants live in app/models.py next to OPERATION_TYPES and are exposed as Jinja globals — no per-route context passing needed"
    - "Wave-0 RED test files import the not-yet-existing service module at module top so pytest collection itself fails until the service lands (mirrors Phase 4's tests/test_sales.py)"

key-files:
  created:
    - tests/test_writeoffs.py
    - tests/test_returns.py
    - tests/test_corrections.py
    - tests/test_history.py
  modified:
    - app/models.py
    - app/routes/__init__.py
    - tests/test_ledger.py

key-decisions:
  - "price_change RU label is «Изменение цены» (per PLAN.md task text), not «Цена» (05-PATTERNS.md draft) — PLAN.md is the authoritative task spec for this plan"
  - "Wave-0 test files fix these route URLs for later waves: GET/POST /writeoff + GET /writeoff/lookup, GET/POST /returns, GET/POST /corrections (replaces POST /ops), GET /history"
  - "register_writeoff/register_return/register_correction all follow the (result|None, errors) tuple contract established by register_receipt/register_sale"
  - "history_view(session, *, type_filter=None, product_id=None, page=0, page_size=50) returns {rows, has_next, page} — fetch-one-extra pagination, never the whole ledger"

patterns-established:
  - "Server-side allow-list validation: WRITEOFF_REASONS is the single source of truth both the write-off service and any future report must consult — never trust the <select>"

requirements-completed: []  # OPS-01..04 are this plan's target requirements (per PLAN.md frontmatter) but NOT yet functionally complete: only the Wave-0 foundation (RU-label constants + RED test contract) landed. Each requirement closes when its implementing wave (05-02..05) turns its RED test GREEN. See Deviations from Plan.

# Metrics
duration: 12min
completed: 2026-07-09
---

# Phase 5 Plan 1: Shared Foundation Summary

**WRITEOFF_REASONS + OPERATION_TYPE_LABELS RU-label constants wired as Jinja globals, plus four Wave-0 RED test files (test_writeoffs/returns/corrections/history) that fix the OPS-01..04 interface contract before any service exists.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-09T22:12:06Z
- **Completed:** 2026-07-09T22:24:04Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Added `WRITEOFF_REASONS` (6 latin reason codes -> RU labels) and `OPERATION_TYPE_LABELS` (every `OPERATION_TYPES` member -> RU label) to `app/models.py`, and registered both as Jinja globals in `app/routes/__init__.py` — no template will need routes to pass them explicitly.
- Created `tests/test_writeoffs.py`, `tests/test_returns.py`, `tests/test_corrections.py`, `tests/test_history.py` — RED by design (each imports its not-yet-built service module at module top, e.g. `app.services.writeoffs`, failing collection until Waves 2-5 land). Test names match the exact `-k` selectors required by `05-VALIDATION.md`'s Requirements->Test Map (`stock_and_reason`, `reason_allowlist`, `form`, `oversell`, `link_and_freeze`, `returnable_cap`, `entry_point`, `count_vs_delta`, `zero_net_noop`, `ledger_equals_cache`, `ops_replaced`, `rows`, `filters`, `pagination`).
- Extended `tests/test_ledger.py` with `test_append_only_preserved_for_return_and_correction` — this one is GREEN today (return/correction types already exist in `OPERATION_TYPES`), guarding the append-only invariant against regression in later waves.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add WRITEOFF_REASONS + OPERATION_TYPE_LABELS constants and register as Jinja globals** - `7c041ff` (feat)
2. **Task 2: Create the four Wave-0 RED test files and extend test_ledger.py append-only coverage** - `276d2f9` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `app/models.py` - added `WRITEOFF_REASONS` and `OPERATION_TYPE_LABELS` module constants next to `OPERATION_TYPES`
- `app/routes/__init__.py` - registered both constants as `templates.env.globals` entries
- `tests/test_writeoffs.py` - OPS-01 RED contract (write-off stock/reason, allow-list rejection, form + oversell web tests)
- `tests/test_returns.py` - OPS-02 RED contract (frozen sale-line snapshot, returnable cap, entry-point web test)
- `tests/test_corrections.py` - OPS-03 RED contract (count vs delta arithmetic, zero-net no-op, ledger==cache, `/ops` replacement web test)
- `tests/test_history.py` - OPS-04 RED contract (paginated read, filtered rows, RU-labeled rendering web tests)
- `tests/test_ledger.py` - added `test_append_only_preserved_for_return_and_correction`

## Decisions Made
- Followed PLAN.md's exact RU label for `price_change` («Изменение цены») rather than the earlier 05-PATTERNS.md draft («Цена») — PLAN.md's task action text is the authoritative, more recently reconciled spec for this plan.
- Fixed the Wave-0 route contract that Waves 2-5 must implement: `GET /writeoff` (page), `GET /writeoff/lookup`, `POST /writeoff` (create); `GET /returns` (entry point + create), `POST /returns`; `GET /corrections` implied by `POST /corrections` (replaces `POST /ops`, which must now 404/405); `GET /history` with `type`/`product` query filters.
- Fixed service signatures the tests exercise: `register_writeoff(session, *, code, name, qty_raw, reason_code, note)`, `register_return(session, *, origin_op_id, qty_raw)` + `returnable_qty(session, sale_id, product_id)`, `register_correction(session, *, code, mode, value_raw, note)`, `history_view(session, *, type_filter=None, product_id=None, page=0, page_size=50)`.

## Deviations from Plan

None in the implementation itself - plan executed exactly as written. The one wording reconciliation (price_change RU label) is documented above under Decisions Made, not a deviation — PLAN.md's task action text explicitly specified «Изменение цены» and was followed verbatim.

**Requirement-tracking correction:** The plan's frontmatter lists `requirements: [OPS-01, OPS-02, OPS-03, OPS-04]` (these are the requirements this WHOLE PHASE closes, spread across all 5 plans). Running the standard `requirements.mark-complete` step against this list would have marked OPS-01..04 "Complete" in `.planning/REQUIREMENTS.md` after only the Wave-0 foundation plan — none of write-off, return, correction, or history is actually usable yet (the four services don't exist; their tests are intentionally RED). Reverted that mark: `.planning/REQUIREMENTS.md` now shows OPS-01..04 as "In Progress (Wave 0 foundation landed; service/route pending Wave N)" instead of "Complete", so the traceability table stays accurate. They will be marked Complete as each implementing wave (05-02..05-05) lands.

## Issues Encountered

`uv run ruff check tests/` initially flagged import-ordering (I001) on all four new Wave-0 files, because ruff/isort cannot classify an unresolvable module (`app.services.writeoffs` etc., which doesn't exist yet) into the standard first-party/third-party buckets. Ran `ruff check --fix` on the four new files only (matching the existing accepted pattern already present in `tests/test_sales.py`/`tests/test_customers.py` from Phase 4, which have the same pre-existing, out-of-scope warning). All four new files are now ruff-clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The RU-label constants and Jinja globals are ready for every Phase 5 template (write-off dropdown, `/history` "Тип" column, correction form).
- The Wave-0 RED contract is frozen: Wave 2 (`app/services/writeoffs.py` + routes) turns `tests/test_writeoffs.py` GREEN; Wave 3 turns `tests/test_returns.py` GREEN; Wave 4 turns `tests/test_corrections.py` GREEN (and must delete `app/routes/ops.py`); Wave 5 turns `tests/test_history.py` GREEN.
- No blockers. Full suite green except the four intentionally-RED Wave-0 files (150 passed when excluded; those 4 fail collection exactly as designed).

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-09*

## Self-Check: PASSED

All created/modified files exist on disk; both task commits (`7c041ff`, `276d2f9`) verified present in git log.
