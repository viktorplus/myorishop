---
phase: 05-stock-operations-history
plan: 08
subsystem: api
tags: [fastapi, jinja2, htmx, html5-parsing, regression-test]

# Dependency graph
requires:
  - phase: 05-stock-operations-history
    provides: /history route and templates (05-05) that this plan patches
provides:
  - GET /history chrome decision keyed solely on the real HX-Request header (is_hx), not on filter presence
  - A plain (non-htmx) top-level GET to /history - filtered or not - always renders the full page chrome (nav + filter bar + table)
  - Regression test proving the fix and guarding against future regression
affects: [05-stock-operations-history, OPS-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "/history chrome-vs-partial decision depends only on the real HX-Request header - filter query params never change which template renders"

key-files:
  created: []
  modified:
    - app/routes/history.py
    - tests/test_history.py

key-decisions:
  - "Scoped test_web_history_filters and the new regression test's row assertions to <td>...</td> markup instead of bare substring checks - the full page's filter-bar <select> unconditionally lists every RU type/product label as <option> text regardless of the active filter, so a bare substring check false-positives on that dropdown text once the fix routes filtered non-hx requests to the full chrome"

patterns-established:
  - "Route-level chrome-vs-partial branching keys only on transport signal (HX-Request header), never on request payload/query content"

requirements-completed: [OPS-04]

# Metrics
duration: ~15min
completed: 2026-07-10
---

# Phase 5 Plan 08: Fix /history chrome-decision branch (CR-01) Summary

**Closed the last blocking gap-closure item (CR-01) by keying `/history`'s chrome-vs-partial decision solely on the real `HX-Request` header, so a plain top-level reload/bookmark/shared filtered URL always gets the full navigable page instead of a bare rows fragment a real browser silently drops.**

## Performance

- **Duration:** ~15 min (2 commits: RED test, GREEN fix)
- **Tasks:** 1 completed (TDD: RED -> GREEN)
- **Files modified:** 2

## Accomplishments

- `app/routes/history.py`'s `history_page` handler now branches on `if is_hx:` only — the dead `is_filtered = bool(type) or bool(product)` variable and the old `if is_hx or is_filtered:` condition are both removed
- A plain (non-htmx) `GET /history?type=writeoff` (or with a `product` filter) now renders the full `pages/history.html` chrome — `<html>`, `<nav>`, `<table>`, and the filter bar pre-selecting the active filter via `partials/history_filters.html`'s existing `selected` logic — instead of a bare rows-only fragment that HTML5 tree-construction rules would cause a real browser to discard
- Genuine htmx-driven filter/pagination requests (real `HX-Request` header) are unaffected — they still receive the chrome-less rows-only partial with `oob=True`
- New regression test `test_web_history_filtered_reload_returns_full_chrome` in `tests/test_history.py` proves the fix and guards against future regression
- OPS-04 fully satisfied: the operator can browse the full operation history under every reachable interaction path (unfiltered, filtered, htmx-driven, plain reload/bookmark/share)

## Task Commits

Each task was committed atomically (TDD: test -> feat):

1. **Task 1 (RED): add failing regression test for /history chrome decision** - `26863f9` (test)
2. **Task 1 (GREEN): key /history chrome decision solely on HX-Request header** - `a7dab51` (fix)

_No plan-metadata commit in this response — worktree mode; orchestrator handles STATE.md/ROADMAP.md after merge._

## Files Created/Modified

- `app/routes/history.py` - `history_page`'s chrome-decision branch changed from `if is_hx or is_filtered:` to `if is_hx:`; dead `is_filtered` variable removed; comment block rewritten to document the corrected behavior and explicitly warn that filter presence alone must never route to the chrome-less partial
- `tests/test_history.py` - added `test_web_history_filtered_reload_returns_full_chrome`; scoped `test_web_history_filters`'s type/product filter assertions to `<td>...</td>` row markup (see Deviations below)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in the plan's own test assertions] Scoped filter-narrowing assertions to `<td>` row markup instead of bare substrings**

- **Found during:** Task 1, running the new test after the GREEN fix
- **Issue:** The plan's `<behavior>` block and `<action>` text specified asserting `"Корректировка" not in response.text` on a filtered, non-htmx `/history` response. Once the CR-01 fix routes that request to the full page, the filter bar's `<select>` unconditionally renders every `OPERATION_TYPE_LABELS` value (including "Корректировка") as `<option>` text regardless of which filter is active — that's normal `<select>` behavior, not a bug. A bare substring check therefore always fails on the full-chrome path, and the plan's claim that the pre-existing `test_web_history_filters` "continues to pass... no change to that test is required" was incorrect: that test hits the exact same false-positive once its `type`/`product`-filtered requests also start returning full chrome.
- **Fix:** Rewrote both the new test's and `test_web_history_filters`'s row-narrowing assertions to check for the exact `<td>{label}</td>` / `<td>{product.name} ({product.code})</td>` row markup rather than a bare substring, which correctly isolates "is this row present in the table" from "is this label present anywhere on the page (including the always-populated dropdown)". Confirmed both tests pass after the fix and that the new test is genuinely RED before it (fails with `<html` missing, i.e., the old code still returns the rows-only partial).
- **Files modified:** `tests/test_history.py`
- **Commit:** `26863f9` (RED test commit, includes the scoped-assertion rewrite)

**2. [Rule 3 - out-of-scope, deferred] Pre-existing ruff `I001` in `tests/test_history.py` left unfixed**

- **Found during:** Final `ruff check` verification pass
- **Issue:** `uv run ruff check app/routes/history.py tests/test_history.py` reports one `I001` (import block un-sorted) in `tests/test_history.py`, on the file's pre-existing two-group import layout (`from app.services.operations import history_view  # noqa: F401` isolated above `from app.config import settings` / `from app.services.ledger import record_operation`). Confirmed via `git show HEAD:tests/test_history.py` that this import block predates this plan's diff — it was not introduced or touched by this plan (which only appended/edited test function bodies). The identical pattern also fails `I001` in `tests/test_backup.py`, `tests/test_corrections.py`, `tests/test_customers.py`, `tests/test_sales.py`, and `tests/test_writeoffs.py` — a repo-wide, pre-existing convention, not specific to this file.
- **Action:** Not fixed, per the executor's Scope Boundary rule (only auto-fix issues directly caused by the current task's changes). Logged to `.planning/phases/05-stock-operations-history/deferred-items.md`. `app/routes/history.py` alone (the plan's other touched file) passes `ruff check` and `ruff format --check` clean.
- **Files modified:** `.planning/phases/05-stock-operations-history/deferred-items.md` (new, logging only)
- **Commit:** N/A (SUMMARY/deferred-items committed with plan-metadata commit)

---

**Total deviations:** 2 (1 auto-fixed test-assertion bug; 1 logged-and-deferred pre-existing out-of-scope lint finding)
**Impact on plan:** No scope creep on the application fix itself — `app/routes/history.py`'s change is exactly as specified (`if is_hx or is_filtered:` -> `if is_hx:`, dead variable removed). Only the test file's assertion precision needed correction to match the real, correct behavior of an always-populated `<select>` filter bar.

## Issues Encountered

None beyond the two deviations documented above. The full test suite (166 tests, up from the 165-passed baseline in `05-VERIFICATION.md`) and `ruff check`/`ruff format --check` on `app/routes/history.py` are all clean.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- CR-01 (the last blocking gap-closure item from `05-VERIFICATION.md`) is closed. All three gap-closure rounds for Phase 5 (05-06: OPS-01 nav link; 05-07: CR-02/CR-03/WR-03 session-rollback reliability; 05-08: CR-01 chrome decision) are now complete.
- Non-blocking items explicitly out of scope for this plan remain deferred, unchanged: WR-01 (pagination control stranding), WR-02 (`/corrections` missing persistent nav entry), WR-04 (product filter dropdown only lists active products), IN-01/02/03/05/06/07 from `05-REVIEW.md`, and the REQUIREMENTS.md traceability table's stale "In Progress" wording.
- No blockers for phase completion.

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: app/routes/history.py
- FOUND: tests/test_history.py
- FOUND: .planning/phases/05-stock-operations-history/05-08-SUMMARY.md
- FOUND: .planning/phases/05-stock-operations-history/deferred-items.md
- FOUND commit: 26863f9 (test)
- FOUND commit: a7dab51 (fix)
