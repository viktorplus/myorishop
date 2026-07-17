---
phase: 22-sales-page-rebuild
plan: 02
subsystem: testing
tags: [pytest, fastapi, htmx, sqlalchemy, tdd-red, characterization-tests]

# Dependency graph
requires:
  - phase: 22-01
    provides: 22-UI-SPEC.md (approved design contract) and 22-RESEARCH.md (Pattern 2's
      verified to_cents accept-set table) this plan's tests assert against
provides:
  - "tests/test_sales_total.py: 6 strict-xfail tests pinning SALE-02 markup/wiring
    (#sale-total, no-name= security control, both-shell script tag, 422/delete-button
    stale-total triggers, hidden-by-default warning marker)"
  - "tests/test_mobile_sales.py: 4 strict-xfail tests pinning D-04 (mobile customer
    selector markup, customer linking, swap-target guard) and D-11 (batch-card
    hx-include markup fix), plus 2 non-xfail regression-guard/contract tests"
  - "tests/test_core.py: to_cents accept-set boundaries and format_cents output shape
    frozen as passing characterization tests — the contract sale-total.js must mirror"
affects: [22-04, 22-06, 22-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Strict-xfail red-side test pins for a feature with no JS runtime coverage
      (markup/wiring assertions only, arithmetic stays manual-only per
      22-VALIDATION.md)"
    - "When a plan's xfail grouping instruction conflicts with actual current
      behavior (a 'new' test already passes), pin it as a plain regression-guard
      test instead of xfail(strict=True) — an unexpected XPASS is a red failure,
      and 'the suite stays green' is the higher-priority invariant"

key-files:
  created:
    - tests/test_sales_total.py
    - .planning/phases/22-sales-page-rebuild/deferred-items.md
  modified:
    - tests/test_mobile_sales.py
    - tests/test_core.py

key-decisions:
  - "test_mobile_walkin and test_batch_step_echoes_acc_when_supplied pinned as plain
    passing tests instead of the plan's xfail grouping, because both assertions
    already hold under today's code (verified by direct execution) — xfail(strict=True)
    on an already-passing assertion would XPASS and break the suite-green invariant"
  - "Repo-wide pre-existing ruff debt (49 files needing format, 9 pre-existing lint
    errors in files this plan did not touch) logged to deferred-items.md and left
    unfixed — out of this plan's <files> scope per the Scope Boundary rule"

patterns-established:
  - "Markup + wiring pins (never arithmetic) as the sanctioned red-side coverage
    strategy for JS-runtime-less SALE-02 features"

requirements-completed: [SALE-01, SALE-02, SALE-03, SALE-06]

# Metrics
duration: ~30min
completed: 2026-07-17
---

# Phase 22 Plan 02: Sales-Page-Rebuild Red-Side Test Coverage Summary

**Landed 10 strict-xfail red-side tests (SALE-02 live total, D-04 mobile customer
selector, D-11 batch-card basket fix) plus froze `to_cents`/`format_cents` as passing
characterization tests — the contract the untestable `sale-total.js` client parser
must mirror. Full suite stays green: 810 passed, 10 xfailed, 0 failed.**

## Performance

- **Tasks:** 3/3 completed
- **Files modified:** 3 test files + 1 deferred-items log

## Accomplishments

- `tests/test_sales_total.py` (new): 6 strict-xfail tests pin the `#sale-total`
  element's markup/placement, the no-`name=` structural security control (T-22-03),
  both-shell (`base.html` + `mobile_base.html`) script-tag loading, the 422-rerender
  stale-total path, the delete-button `recalcSaleTotal` hook, and the hidden-by-default
  «итог неполный» marker.
- `tests/test_mobile_sales.py` (extended): 4 strict-xfail tests pin the D-04 mobile
  customer selector (`#m-customer-header`, 3-way radio group, `existing` default),
  `customer_id` linking (retiring the `mobile_sales.py:346` hardcode), the
  `/m/sales/customer-mode` swap-target guard, and the D-11 batch-card
  `hx-include="closest form"` markup fix. 2 non-xfail tests pin already-working
  behavior as regression guards (see Deviations).
- `tests/test_core.py` (extended): `to_cents` accept-set boundaries (comma/dot decimal,
  ROUND_HALF_UP ties-away-from-zero, common rejects) and the deliberate
  server-vs-JS-mirror divergence (exponents, PEP-515 underscores, signs, Unicode digit
  scripts) frozen as passing tests, plus `format_cents`'s exact display shape. All
  values verified by direct execution against `app/core.py` before writing the test —
  `app/core.py` itself is untouched (`git diff --stat app/core.py` is empty).

## Task Commits

1. **Task 1: tests/test_sales_total.py — SALE-02 markup and wiring** - `aedb9de` (test)
2. **Task 2: tests/test_mobile_sales.py — D-04 selector + D-11 batch-card basket preservation** - `f9cb670` (test)
3. **Task 3: tests/test_core.py — pin the to_cents accept-set the JS mirrors** - `24de7bf` (test)

_No plan-metadata commit in worktree mode — SUMMARY.md is committed separately per the
worktree executor's parallel_execution instructions._

## Files Created/Modified

- `tests/test_sales_total.py` - New file: 6 strict-xfail SALE-02 markup/wiring tests
- `tests/test_mobile_sales.py` - +6 tests (4 strict-xfail D-04/D-11, 2 non-xfail regression guards)
- `tests/test_core.py` - +3 tests (to_cents boundaries, JS-mirror divergence, format_cents shape)
- `.planning/phases/22-sales-page-rebuild/deferred-items.md` - New file: logs pre-existing
  repo-wide ruff debt found but not fixed (out of scope)

## Decisions Made

- **test_mobile_walkin pinned as a plain passing test, not xfail.** The plan groups it
  under the D-04 xfail block ("D-05 — the mobile walk-in path must not regress"), but
  `mobile_sales.py:346`'s `customer_id=""` hardcode already coerces to `NULL` via
  `register_sale`'s `customer_id or None` regardless of what the test posts — verified
  by direct execution before writing the test. Marking it `xfail(strict=True)` would
  XPASS (a red failure under strict mode), directly violating this plan's own
  `must_haves.truths`: "The full suite stays green after this plan — new tests land as
  strict xfail, not as red failures." The test is written as a genuine regression guard
  instead, documented inline.
- **test_batch_step_echoes_acc_when_supplied pinned as a plain passing test**, matching
  the plan's own instruction ("assertion (b) may already pass today ... that is expected
  and fine").
- **Pre-existing repo-wide ruff debt left unfixed**, logged to `deferred-items.md`
  instead — the plan's `<files>` frontmatter scopes this plan to 3 specific test files,
  all 3 of which pass `ruff check` / `ruff format --check` individually. The debt (49
  files needing reformat, an unused import in `test_mobile_receipts.py`) predates this
  plan (confirmed via `pyproject.toml` at the worktree's base commit) and is unrelated
  to any file this plan touches.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — test-suite-green invariant takes priority over literal xfail grouping] `test_mobile_walkin` written as a plain test instead of `xfail(strict=True)`**
- **Found during:** Task 2 (tests/test_mobile_sales.py)
- **Issue:** The plan's task text groups `test_mobile_walkin` under the D-04
  `xfail(strict=True, reason="D-04: mobile customer selector lands in 22-06/22-07")`
  block. Empirically running the described scenario against current code (before
  writing the test) showed the assertion already holds — `mobile_sale_create`'s
  hardcoded `customer_id=""` already produces `Sale.customer_id IS NULL` with or
  without a `customer_id` posted, since no such handler parameter exists yet.
  Marking an already-passing assertion `xfail(strict=True)` produces an XPASS, which
  pytest reports as a failure under strict mode — this would have made the plan's own
  acceptance criterion ("0 XPASS") and the phase-wide must-have ("suite stays green")
  mutually impossible to satisfy simultaneously with the literal xfail grouping.
- **Fix:** Wrote `test_mobile_walkin` as a normal (non-xfail) test with a docstring
  explaining the deviation and citing both source lines (`mobile_sales.py:346`,
  `services/sales.py:254`).
- **Verification:** `uv run pytest tests/test_mobile_sales.py -k mobile_walkin -q` →
  1 passed. Full suite: 810 passed, 10 xfailed, 0 failed.
- **Files modified:** `tests/test_mobile_sales.py`
- **Committed in:** `f9cb670`

**2. [Rule 3 — out-of-scope, logged not fixed] Pre-existing repo-wide ruff debt**
- **Found during:** final verification (`uv run ruff check .` / `ruff format --check .`)
- **Issue:** 49 test files (none touched by this plan) would be reformatted, and
  `tests/test_mobile_receipts.py` has a pre-existing unused import
  (`app.services.dictionary.add_entry`). Confirmed pre-existing via
  `git show <base-commit>:pyproject.toml` (ruff config predates this plan).
- **Fix:** Not fixed — out of this plan's `<files>` scope. Logged to
  `.planning/phases/22-sales-page-rebuild/deferred-items.md` per the Scope Boundary
  rule instead.
- **Files modified:** none (log only)
- **Committed in:** not committed as part of a task; `deferred-items.md` is a new file
  alongside this SUMMARY.

---

**Total deviations:** 2 (1 test-design correction to preserve the suite-green
invariant, 1 out-of-scope debt logged and deferred).
**Impact on plan:** No scope creep. Both deviations preserve the plan's own stated
invariants (suite stays green; only this plan's 3 files are touched).

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `app/static/sale-total.js` and the `#sale-total` markup (22-04) will flip the 6
  `test_sales_total.py` xfails to real passes — no test changes needed there.
- The mobile customer selector work (22-06/22-07) will flip 4 `test_mobile_sales.py`
  xfails; `mobile_sales.py:346`'s `customer_id=""` hardcode and its stale comment
  still need deleting per 22-UI-SPEC.md Interaction 9 (this plan only pins the tests,
  it does not touch `app/`).
- `to_cents`/`format_cents` are now a frozen, test-backed contract — 22-04's
  `sale-total.js` implementer can read `tests/test_core.py`'s two new parametrized
  tests directly as the accept-set spec instead of re-deriving it.
- No blockers. `app/core.py`, `app/routes/sales.py`, `app/routes/mobile_sales.py`, and
  every template are untouched by this plan (test-only, as scoped).

---
*Phase: 22-sales-page-rebuild*
*Completed: 2026-07-17*
