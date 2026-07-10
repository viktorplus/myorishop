---
phase: 05-stock-operations-history
plan: 07
subsystem: api
tags: [fastapi, sqlalchemy, htmx, session-management, error-handling]

# Dependency graph
requires:
  - phase: 05-stock-operations-history
    provides: return/correction/write-off write routes (05-01..05-05) that this plan hardens
provides:
  - GET /returns origin-not-found error uses status_code=422 (htmx-swappable) instead of 404 (silently discarded)
  - POST /returns's except Exception block rolls back the session before re-querying it for error context
  - POST /corrections and POST /writeoff except Exception blocks defensively roll back the session (same shape, no re-query today)
  - Two regression tests proving both fixes (RED before, GREEN after)
affects: [05-stock-operations-history, any future edit to returns/corrections/writeoffs error-context builders]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "except Exception: session.rollback() FIRST, before any further session query in the same handler (all three write routes now follow this shape)"

key-files:
  created: []
  modified:
    - app/routes/returns.py
    - app/routes/corrections.py
    - app/routes/writeoffs.py
    - tests/test_returns.py

key-decisions:
  - "A plain failed SELECT (SQLite) does not poison a SQLAlchemy Session the way a failed flush/commit does — the regression test that proves CR-03 had to trigger a genuine failed flush (duplicate primary key), not a raw failing query, to reproduce the real PendingRollbackError"

patterns-established:
  - "Bare except Exception: handler in a write route always calls session.rollback() as the first statement, before any error-context builder re-queries the session"

requirements-completed: [OPS-02]

# Metrics
duration: 5min
completed: 2026-07-10
---

# Phase 05 Plan 07: Session-rollback hardening for returns/corrections/writeoffs Summary

**Fixed GET /returns's origin-not-found 404->422 (htmx-swap discard bug) and added defensive session.rollback() to all three write routes' bare exception handlers, closing CR-02/CR-03/WR-03 from the code review.**

## Performance

- **Duration:** ~5 min (3 commits, 03:59-04:04 UTC+2)
- **Tasks:** 2 completed
- **Files modified:** 4

## Accomplishments
- `GET /returns`'s origin-not-found error partial now returns `status_code=422` instead of `404`, so `base.html`'s htmx `responseHandling` allow-list actually swaps the RU error message («Исходная продажа не найдена.») into the DOM instead of silently discarding it (CR-02)
- `POST /returns`'s bare `except Exception:` block now calls `session.rollback()` before `_origin_context`/`_empty_context` re-query the session, preventing an unhandled `PendingRollbackError` from turning an unexpected failure into a raw 500 (CR-03)
- The same defensive `session.rollback()` was applied to `POST /corrections` and `POST /writeoff`'s bare exception handlers (WR-03) — neither re-queries the session today, but this closes the systemic root cause before a future edit reintroduces the CR-03 class of bug
- Two new regression tests in `tests/test_returns.py` prove both fixes and were confirmed genuinely RED before the fix

## Task Commits

Each task was committed atomically (TDD: test -> feat for Task 1; single fix commit for Task 2):

1. **Task 1 (RED): add failing regression tests for CR-02/CR-03** - `95eb5d8` (test)
2. **Task 1 (GREEN): fix returns.py 404->422 and session rollback** - `784ee49` (feat)
3. **Task 2: defensive session.rollback() in corrections.py/writeoffs.py (WR-03)** - `cbb71a9` (fix)

_No plan-metadata commit in this response — worktree mode; orchestrator handles STATE.md/ROADMAP.md after merge._

## Files Created/Modified
- `app/routes/returns.py` - `return_form_page`'s origin-not-found response changed to `status_code=422`; `return_create`'s `except Exception:` block now calls `session.rollback()` first
- `app/routes/corrections.py` - `correction_create`'s `except Exception:` block now calls `session.rollback()` first (defensive, WR-03)
- `app/routes/writeoffs.py` - `writeoff_create`'s `except Exception:` block now calls `session.rollback()` first (defensive, WR-03)
- `tests/test_returns.py` - added `test_web_return_origin_not_found_uses_422` and `test_web_return_survives_unexpected_error`

## Decisions Made
- The plan's suggested RED-test mechanism (session.execute of a SELECT against a nonexistent table) does not actually taint a SQLAlchemy Session on SQLite the way it would on Postgres — SQLite does not abort a transaction on a failed statement the way Postgres does. To genuinely reproduce the `PendingRollbackError` that CR-03 describes, the test instead triggers a real failed `session.flush()` (duplicate primary key insert), which SQLAlchemy's ORM Session does mark as needing an explicit rollback. Verified this is a true RED before the fix (test failed with the real `PendingRollbackError` traceback) and true GREEN after.

## Deviations from Plan

**1. [Rule 1 - Bug in the plan's own test recipe] Adjusted the CR-03 regression test's session-tainting mechanism**
- **Found during:** Task 1, writing the RED test
- **Issue:** The plan's `<action>` specified tainting the session via `session.execute(text("SELECT * FROM no_such_table"))` before raising `RuntimeError`. Verified empirically (via a throwaway probe test) that this does NOT leave a SQLAlchemy Session needing rollback on SQLite — the subsequent `session.get(Product, ...)` succeeded without error, meaning the test would have passed even without the fix (a false-negative RED, i.e. a tautology).
- **Fix:** Replaced the tainting mechanism with a genuine failed `session.flush()` (duplicate primary-key insert, caught internally), which SQLAlchemy's ORM Session does correctly track as "needs rollback." Confirmed this reproduces the real `PendingRollbackError` traceback before the fix, and passes cleanly after.
- **Files modified:** `tests/test_returns.py`
- **Verification:** Ran the test suite before applying the returns.py fix — `test_web_return_survives_unexpected_error` failed with an unhandled `sqlalchemy.exc.PendingRollbackError` (not just an assertion mismatch), confirming a genuine RED. After the fix, all 5 tests in `tests/test_returns.py` pass.
- **Committed in:** `95eb5d8` (RED test commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in the plan's specified test mechanism, not the application code)
**Impact on plan:** No scope creep — the application-level fix (`session.rollback()` placement) is exactly as the plan specified in both `returns.py` and the two defensive-only files. Only the *test's* internal tainting mechanism needed correction to make it a real regression test rather than an always-passing one.

## Issues Encountered
None beyond the test-mechanism deviation documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three write routes (returns, corrections, writeoffs) now share the same defensive `session.rollback()` shape in their bare exception handlers, closing CR-02/CR-03/WR-03.
- Full suite: 164 passed (162 baseline + 2 new), `ruff check` and `ruff format --check` both clean on all touched files.
- `WR-01` (history "Показать ещё" pagination stranding) remains explicitly deferred, per the plan's stated scope boundary — not addressed here.
- No blockers for phase completion.

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/routes/returns.py
- FOUND: app/routes/corrections.py
- FOUND: app/routes/writeoffs.py
- FOUND: tests/test_returns.py
- FOUND: .planning/phases/05-stock-operations-history/05-07-SUMMARY.md
- FOUND commit: 95eb5d8 (test)
- FOUND commit: 784ee49 (feat)
- FOUND commit: cbb71a9 (fix)
- FOUND commit: 6bc31f6 (docs: summary)
