---
phase: 25-authentication-roles-user-attribution
plan: 08
subsystem: ui
tags: [history, reports, attribution, htmx, sqlalchemy, filter]

# Dependency graph
requires:
  - phase: 25-07
    provides: author_id stamped on every ledger/cash write via the single write path
  - phase: 25-02
    provides: User model + author_id FK columns on Operation/Sale/CashMovement
  - phase: 25-03
    provides: users service (list_users) for the filter option source
provides:
  - History «Кто» column shows the live author display_name (author LEFT OUTER JOIN), muted frozen created_by fallback for pre-auth NULL rows
  - «Пользователь» filter select on /history (top filter-bar) and /reports/sales
  - author_id kwarg on history_view + sales_profit_report (parameterized, AND-combined)
  - author query param passthrough on both routes with pagination re-serialization
affects: [26-postgres-portability, phase-27-merge-core, reporting]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Read-time author attribution: LEFT OUTER JOIN User via Operation.author_id (never inner) so pre-auth NULL-author rows are never dropped; live display_name resolved at read, ledger never rewritten"
    - "Additive parameterized author filter mirroring the existing customer/category/period kwarg blocks (applied to both stmt and count_stmt)"
    - "HTMX filter select placed inside the innerHTML-swapped results partial so a shared period_filter hx-include can reach it and it survives swaps"

key-files:
  created: []
  modified:
    - app/services/operations.py
    - app/routes/history.py
    - app/services/reports.py
    - app/routes/reports.py
    - app/templates/partials/history_rows.html
    - app/templates/partials/sales_report_results.html
    - tests/test_attribution.py

key-decisions:
  - "History «Кто» column shows the LIVE display_name via the author join; pre-auth NULL-author rows fall back to the frozen created_by text rendered .muted (never dropped — LEFT OUTER JOIN)"
  - "Selecting a user excludes NULL-author rows (correct — they predate auth); no user selected reproduces the full unfiltered view/report exactly"
  - "The /reports/sales «Пользователь» select lives in sales_report_results.html (the innerHTML-swapped partial), not reports_sales.html, so the shared period_filter hx-include (#sales-results select) picks it up and it survives swaps"

patterns-established:
  - "Author display + filter reuses the exact History filter HTMX idiom (hx-get/hx-trigger=change/hx-include siblings/hx-target/hx-push-url)"

requirements-completed: [USER-06, RPT-01]

# Metrics
duration: 25 min
completed: 2026-07-18
---

# Phase 25 Plan 08: History author column + user filter on History & Reports Summary

**History «Кто» column now resolves the live operator display_name via a LEFT OUTER JOIN on author_id (muted «operator» fallback for pre-auth rows), plus a «Пользователь» filter select on both /history and /reports/sales backed by a parameterized author_id kwarg that tolerates NULL-author history everywhere.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-18
- **Tasks:** 3
- **Files modified:** 6 (+1 test file)

## Accomplishments
- `history_view` gains a LEFT OUTER JOIN on `User` (live `display_name` per row, NULL-tolerant) and an optional `author_id` filter applied to both the page and count statements
- `sales_profit_report` gains an optional `author_id` kwarg (extra parameterized `.where`), leaving the all-authors report byte-identical when unset
- Both routes pass an `author` query param through (history re-serializes it into pagination links); both inject `list_users()` for the select
- «Пользователь» selects added to the History top filter-bar and the sales report, «Все пользователи» first, live display_name options (autoescape only)
- Pre-auth NULL-author rows verified tolerated: shown as muted `operator` in the unfiltered views, excluded (never crashing) when a user is selected

## Task Commits

Each task was committed atomically:

1. **Task 1: history_view author join + author_id filter** - `c9121f5` (feat)
2. **Task 2: sales_profit_report author filter + route param** - `d4275bf` (feat)
3. **Task 3: «Пользователь» filter selects + filter_by_user tests** - `f8f51e4` (feat)

**Plan metadata:** committed with STATE/ROADMAP/REQUIREMENTS.

## Files Created/Modified
- `app/services/operations.py` - `history_view`: `User` LEFT OUTER JOIN + `author_id` kwarg filter; each row dict carries `author` (User|None); returned dict echoes `author_id`
- `app/routes/history.py` - `author` query param → `history_view(author_id=...)`; re-serialized into `extra_qs`; `users` + `author_id` added to context
- `app/services/reports.py` - `sales_profit_report(..., author_id=None)`: extra parameterized `.where(Operation.author_id == author_id)`
- `app/routes/reports.py` - `/reports/sales` `author` param → service; `users` + `author_id` in context (full-page + HX)
- `app/templates/partials/history_rows.html` - «Пользователь» top-bar select; «Кто» column shows live display_name with muted created_by fallback; empty-state accounts for the author filter
- `app/templates/partials/sales_report_results.html` - «Пользователь» select inside the swapped partial, wired to preserve the от/по period on change
- `tests/test_attribution.py` - `test_filter_by_user_history` + `test_filter_by_user_reports` (two attributed users + a pre-auth NULL-author row; service + HTTP proofs)

## Decisions Made
- History «Кто» column shows the LIVE `display_name` (resolved via the author join at read time), not the frozen `created_by`, EXCEPT for pre-auth NULL-author rows which keep their frozen `created_by` text rendered `.muted` per the Copywriting Contract.
- The `/reports/sales` author select is placed in `sales_report_results.html` (the innerHTML-swapped partial), not directly in `reports_sales.html`. The shared `period_filter.html` `hx-include` is scoped to `#sales-results input, #sales-results select`, so the select must live inside `#sales-results` to be picked up; and because that div is innerHTML-swapped, the select must be part of the swapped payload to survive and reflect its selection.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reports author select relocated to the swapped partial + empty-state condition extended**
- **Found during:** Task 3 (filter selects)
- **Issue:** The plan named `reports_sales.html` for the sales author select, but the shared `period_filter.html` `hx-include` targets `#sales-results …` and that div is innerHTML-swapped — a select placed in `reports_sales.html` outside `#sales-results` is unreachable by the period filter, and one placed inside `#sales-results` in the page template is wiped on every swap. Separately, the History empty-state message keyed on `type_filter or product_id or category or customer or from_date`, so an author-only filter that matched nothing would have shown «Операций пока нет» instead of «Нет операций по выбранным фильтрам».
- **Fix:** Placed the sales author select inside `sales_report_results.html` (the swap payload) with an explicit `hx-include="[name='from'], [name='to']"` so the period survives an operator change; added `author_id` to both History empty-state conditions.
- **Files modified:** app/templates/partials/sales_report_results.html, app/templates/partials/history_rows.html
- **Verification:** `uv run pytest tests/test_attribution.py -k filter_by_user` and the full suite pass (981 passed).
- **Committed in:** f8f51e4 (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking/wiring correctness)
**Impact on plan:** Location adjustment required for the HTMX wiring to actually work; no behavior change vs. the plan's intent, no scope creep.

## Issues Encountered
None - planned work completed without problem-solving detours.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 25 (Authentication, Roles & User Attribution) execution is complete: all 8 plans have SUMMARYs. USER-06 and RPT-01 are the last requirements in the phase.
- Full suite green (981 passed) — the 25-VALIDATION "full suite green before /gsd-verify-work" gate is satisfied.
- Recommended next: `/gsd-verify-work 25`, then `/gsd-plan-phase 26` (PostgreSQL Portability & Append-Only Parity).

---
*Phase: 25-authentication-roles-user-attribution*
*Completed: 2026-07-18*

## Self-Check: PASSED
- All 7 modified files exist on disk (verified below).
- Task commits c9121f5, d4275bf, f8f51e4 present in git log.
- Task acceptance criteria + plan `<verification>` re-run: `tests/test_history.py` (20), `tests/test_reports.py` (41), `tests/test_attribution.py -k filter_by_user` (2), and the FULL suite (981 passed) all green.
- No `|safe` on display_name/login/created_by (autoescape only).
