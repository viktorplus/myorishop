---
phase: 21-customer-profiles-purchase-insights
plan: 03
subsystem: database
tags: [sqlalchemy, sqlite, pytest, customer-insights, service-layer, portability]

# Dependency graph
requires:
  - phase: 21-customer-profiles-purchase-insights (Plan 02)
    provides: contacts/address write+read path on create_customer/update_customer, contacts_by_kind
provides:
  - "spend_totals/spend_view (D-05/D-06/CUST-07): month/quarter/year net-of-returns spend, injectable today"
  - "favorite_products (D-04/D-04a/CUST-08): distinct-order frequency ranking, batch-split-safe"
  - "last_order_date (CUST-06): pure derivation from an already-loaded purchase_history"
  - "test_spend_and_favorites_queries_are_portable: mechanical PostgreSQL-portability guard for both new statements"
affects: [21-04-customer-form, 21-05-customer-detail]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Unexecuted-Select private builders (_spend_stmt/_favorites_stmt) so a fixture-free test can compile them against both dialects without a session — the phase's highest-leverage portability enforcement"
    - "Double coalesce (inner on the nullable column, outer on the SUM) prevents both a NULL price line and a zero-order customer from producing None"
    - "Injectable `today: date | None = None` parameter on every calendar-relative service function, defaulting to datetime.now(ZoneInfo(settings.display_tz)).date() only at the call boundary — never date.today() inside, and never inside a test"
    - "All calendar-to-UTC-window conversion goes through the existing local_day_bounds_utc; zero date functions appear in generated SQL under either dialect"

key-files:
  created: []
  modified:
    - app/services/customers.py
    - tests/test_customers.py

key-decisions:
  - "Docstrings that explain WHY a banned SQL pattern (strftime/date_trunc/EXTRACT), a rejected dependency (python-dateutil), a real-calendar read (date.today()), or a deliberately-not-filtered column (deleted_at) must NOT appear had to be phrased without literally containing those substrings, because the plan's own acceptance criteria greps app/services/customers.py for those exact tokens and expects a count of 0 — a docstring mentioning 'no strftime' would otherwise self-fail its own guard. Rephrased all five occurrences (e.g. 'no python-dateutil' -> 'zero new date-math dependencies', 'Product.deleted_at' -> 'soft-deleted products') while preserving the same explanatory content."
  - "Split the single cohesive implementation pass into 3 atomic commits after verification, by temporarily removing Task 2/3 code blocks (Edit, not git plumbing), running each task's own verification subset, committing, then restoring the next block — since all three tasks share the same two files and were designed/verified together, this was safer than attempting a partial git-hunk split."

requirements-completed: [CUST-06, CUST-07, CUST-08]

# Metrics
duration: ~40min
completed: 2026-07-17
---

# Phase 21 Plan 03: Purchase Insights Read Path Summary

**Month/quarter/year net-of-returns spend totals, a distinct-order favorite-products ranking, and last-order-date — all SQL-side aggregates in `app/services/customers.py`, with a fixture-free test that compiles every new statement against both PostgreSQL and SQLite dialects to mechanically enforce zero date functions and zero literal-value leakage.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-07-17
- **Tasks:** 3/3 completed
- **Files modified:** 2

## Accomplishments

- `spend_totals`/`spend_view` (CUST-07/D-05/D-06): net spend in cents for the current calendar month/quarter/year, period-to-date, computed via `_period_starts` (stdlib `date.replace` only) + the existing `local_day_bounds_utc` helper. `_spend_stmt` nets `sale` and `return` ops with ONE unbranched formula (`-qty_delta * coalesce(unit_price_cents, 0)`, summed and outer-coalesced to 0) — a return subtracts from the window containing its OWN return date, not the origin sale's date (cash-basis, matching how Finance already books the debit). A zero-order customer gets `{"month": 0, "quarter": 0, "year": 0}`, never `None`. `today` is an injectable parameter on both functions, defaulting to `datetime.now(ZoneInfo(settings.display_tz)).date()` only at the boundary — no test reads the real calendar. `spend_view` hands the template `start_iso` as a `str` (`start.isoformat()`), closing a real `TypeError` the `| ru_date` filter would otherwise raise on a `date` object.
- `favorite_products` (CUST-08/D-04/D-04a): ranks by `count(DISTINCT sale_id)` — orders containing the product — NOT line count, so a batch-split purchase (two `sale` ops in one Sale for the same product, a routine shape in this app) counts as ONE purchase. Quantity is the secondary sort key and a returned column; `Product.name` is a mandatory third tie-break. Capped at 10 by default (`limit` is a bound int parameter, never string-interpolated). Deliberately does NOT filter soft-deleted products (historical view) and only counts `type == "sale"` (returns are `spend_totals`' concern).
- `last_order_date` (CUST-06): pure function — no session, no query — reading `purchase_history[0]["op"].created_at` (already ordered `created_at DESC, seq DESC`), returning `None` for an empty history.
- `test_spend_and_favorites_queries_are_portable`: compiles `_spend_stmt` and `_favorites_stmt` against both `postgresql.dialect()` and `sqlite.dialect()` (four compiled strings), asserting none contain `strftime`/`date_trunc`/`extract(`/`julianday`/`datetime(` and that the literal `"cust-id"` customer id never leaks into compiled SQL (proving bound-parameter usage mechanically, T-21-03/T-21-15). Fixture-free and fast — the phase's single highest-leverage test per RESEARCH/VALIDATION.
- Confirmed the pre-existing `test_purchase_history_frozen` regression contract is unmodified (`git diff` shows zero change to its body) and still green.

## Task Commits

Each task was committed atomically:

1. **Task 1: Calendar spend windows, net of returns (CUST-07/D-05/D-06)** - `f604b52` (feat)
2. **Task 2: Favorite products ranking + last order date (CUST-08/D-04/D-04a, CUST-06)** - `ede7c3d` (feat)
3. **Task 3: PostgreSQL portability guard + frozen-price regression** - `fb46ca7` (test)

_Worktree mode: STATE.md/ROADMAP.md are updated centrally by the orchestrator after merge — no separate plan-metadata commit was made here._

## Files Created/Modified

- `app/services/customers.py` — new imports (`date`, `ZoneInfo`, `func`, `settings`, `local_day_bounds_utc`); new symbols `_period_starts`, `_spend_stmt`, `_spend_window`, `spend_totals`, `spend_view`, `_favorites_stmt`, `favorite_products`, `last_order_date`
- `tests/test_customers.py` — 14 new service-level tests across the three tasks (spend windows/net-of-returns/exclusion/empty/null-price/start_iso-string, favorites ranking/batch-split/limit/scoping/returns-exclusion, last-order date/empty, portability guard); module docstring's `-k` selector list extended

## Decisions Made

- Docstring text explaining banned patterns (`strftime`, `python-dateutil`, `date.today()`, `Product.deleted_at`) had to avoid literally containing those substrings — see Deviations below.
- Split the implementation into 3 atomic commits after the fact (all three tasks were implemented and verified together due to their tight interdependency — Task 3's test imports Task 1's and Task 2's private statement builders directly) by temporarily removing/restoring code blocks between commits, rather than a risky git-hunk split.
- Kept `_spend_stmt`/`_favorites_stmt` as private, unexecuted `Select`-returning functions exactly as specified, so the portability guard can compile them without a session — no deviation from the plan's shape here.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring explanatory text self-failed its own acceptance-criteria greps**
- **Found during:** Task 1/2 verification — running the plan's own `grep -c "strftime\|date_trunc\|EXTRACT\|extract("`, `grep -c "dateutil"`, `grep -c "date.today()"`, and (Task 2) `grep -c "deleted_at"` checks against `app/services/customers.py` returned 1-2 instead of the required 0.
- **Issue:** My first draft of the docstrings explained the load-bearing rules by naming the exact banned patterns ("No strftime/date_trunc/EXTRACT/date function of any kind", "no python-dateutil", "this function never calls date.today() internally", "Does NOT filter Product.deleted_at") — correct in spirit, but the plan's acceptance criteria grep the whole file literally for those substrings and expect zero matches, since the criteria exist to catch actual *usage*, not commentary. The docstrings' own explanatory mentions triggered false positives.
- **Fix:** Reworded all five occurrences to convey the identical rationale without containing the literal banned substrings (e.g. "zero new date-math dependencies" instead of "no python-dateutil"; "no date-manipulation SQL function of any kind" instead of naming `strftime` etc.; "never reads the real calendar internally" instead of "never calls date.today()"; "does NOT filter out soft-deleted products" instead of "Product.deleted_at").
- **Files modified:** `app/services/customers.py`
- **Verification:** All five `grep -c` acceptance-criteria commands now return `0`; full test suite unaffected (docstrings only).
- **Committed in:** `f604b52` (Task 1, for the `strftime`/`dateutil`/`date.today()` occurrences) and `ede7c3d` (Task 2, for the `deleted_at` occurrence).

---

**Total deviations:** 1 auto-fixed (documentation-only correctness fix, no behavior change)
**Impact on plan:** None on functionality — purely a wording fix so the plan's own literal-grep acceptance criteria pass as written. No scope creep.

## Issues Encountered

Whole-repo `uv run ruff check` / `uv run ruff format --check` (run per Task 3's verify block) surfaced pre-existing findings in files this plan never touched: 9 lint errors (line-length, one unused import) across `app/routes/dictionary.py`, `app/routes/products.py`, `scripts/import_master_pricelist.py`, and three test files; and 51 files with formatting drift. Per the executor's scope-boundary rule (only fix issues directly caused by the current task's changes), these were left untouched and logged to `.planning/phases/21-customer-profiles-purchase-insights/deferred-items.md` rather than fixed. `app/services/customers.py` and `tests/test_customers.py` — this plan's only touched files — are clean on both checks.

## Known Stubs

None — this is a read-only service-layer plan with no UI wiring; nothing here renders to a template yet (that's Plan 05).

## Threat Flags

None — every threat this plan's `<threat_model>` names (T-21-03, T-21-15, T-21-16, T-21-17, T-21-18) is addressed by the implementation and mechanically verified by tests (`test_spend_and_favorites_queries_are_portable`, `test_favorites_scoped_to_this_customer`, `test_spend_empty_customer_returns_zero_not_none`, `test_spend_null_price_line_does_not_crash_sum`). No new network endpoints, auth paths, or schema changes were introduced.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `app/services/customers.py` now exposes the full CUST-06/07/08 read contract (`spend_totals`, `spend_view`, `favorite_products`, `last_order_date`) for Plan 05 (customer detail page) to render.
- Every new SQL statement is proven portable to PostgreSQL by a fast, fixture-free, mechanically-enforced test — no reviewer-memory-only rule remains for this plan's surface.
- Full 785/785 test suite is green (Wave 2 merge gate); `ruff check`/`ruff format --check` clean on both files this plan touched.

---
*Phase: 21-customer-profiles-purchase-insights*
*Completed: 2026-07-17*

## Self-Check: PASSED

All modified files exist on disk (`app/services/customers.py`, `tests/test_customers.py`) and all task commit hashes (`f604b52`, `ede7c3d`, `fb46ca7`) are present in git log.
