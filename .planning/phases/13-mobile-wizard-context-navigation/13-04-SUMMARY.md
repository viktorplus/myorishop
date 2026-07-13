---
phase: 13-mobile-wizard-context-navigation
plan: 04
subsystem: ui
tags: [fastapi, jinja2, htmx, mobile-wizard]

# Dependency graph
requires:
  - phase: 13-mobile-wizard-context-navigation (plan 01)
    provides: hx-get/hx-post uniformity pattern for wizard "Назад" buttons (open_question_resolution)
provides:
  - Transfers wizard step 2 ("Партия") "Назад" now uses hx-get, matching every other wizard's back-navigation convention
  - GET /m/transfers accepts an optional ?code= query param and serves both a full page and a bare HX-Request fragment from the same context
  - transfers_step_product.html extracted as a standalone, reusable fragment
  - Explicit UI-02 regression test guarding the pre-existing Phase 12 code/name header on transfers_step_batch.html
affects: [phase-13-mobile-wizard-context-navigation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "hx-get + hx-vals (not hx-include) for 'Назад' buttons in wizard steps with no wrapping <form> of their own — matches transfers_step_dest.html's and transfers_step_batch.html's existing batch-pick card technique"

key-files:
  created:
    - app/templates/mobile_partials/transfers_step_product.html
  modified:
    - app/routes/mobile_transfers.py
    - app/templates/mobile_pages/transfers.html
    - app/templates/mobile_partials/transfers_step_batch.html
    - tests/test_mobile_transfers.py

key-decisions:
  - "Extended the D-01/D-02 hx-get uniformity fix (already applied to corrections/receipts in Plan 13-01) to transfers' step 2 Назад button, since direct verification during planning showed 13-CONTEXT.md's D-06 claim that transfers needed no changes did not hold for this one control."
  - "UI-02's header format was already correct in transfers_step_batch.html (shipped Phase 12) — no functional fix needed there, only an explicit regression assertion added since this plan is the only one touching that file."

patterns-established:
  - "GET routes serving both a full page and a bare HTMX fragment from the same context branch on bool(request.headers.get('HX-Request')) — mirrors the mobile_search.py idiom."

requirements-completed: [UI-02, UI-03]

# Metrics
duration: 8min
completed: 2026-07-14
---

# Phase 13 Plan 04: Transfers Wizard Step-2 Назад Fix Summary

**Converted transfers wizard step 2's plain `<a>` "Назад" link to an explicit `hx-get="/m/transfers"` + `hx-vals` request, and extended `GET /m/transfers` to accept an optional `?code=` query param served as both a full page and a bare HX-Request fragment.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-14T00:26:00+02:00 (approx, first task commit)
- **Completed:** 2026-07-14T00:30:19+02:00
- **Tasks:** 2 completed
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- Transfers step 2's "Назад" is now `hx-get="/m/transfers"` with `hx-vals` carrying `code`, never a plain `<a>` link — closing the last plain-link gap Phase 13's own audit found beyond the originally-scoped file list.
- `GET /m/transfers` accepts and echoes an optional `?code=` query param, and branches on `HX-Request` to serve either the full page (`mobile_pages/transfers.html`) or a bare fragment (`mobile_partials/transfers_step_product.html`) from identical context — same idiom as `mobile_search.py`.
- Extracted `transfers_step_product.html` as a standalone fragment shared by both response shapes, matching the wrapper-carrying convention already used by `transfers_step_batch.html`/`transfers_step_dest.html` (this wizard's swap convention is `outerHTML`, unlike receipts' `innerHTML`).
- Added an explicit UI-02 regression assertion protecting the pre-existing Phase 12 visible `<strong>{{code}}</strong> — {{name}}` header on `transfers_step_batch.html`, since this plan's Назад-button refactor is the only change touching that file this phase.

## Task Commits

Each task was committed atomically:

1. **Task 1: transfers_step_product — code query param + HX-Request branch** - `2c57aa5` (feat)
2. **Task 2: Extract transfers_step_product.html + fix transfers_step_batch.html's Назад + tests** - `b87c219` (feat)

**Plan metadata:** committed separately by orchestrator after this SUMMARY (worktree mode — STATE.md/ROADMAP.md updates deferred to orchestrator).

## Files Created/Modified
- `app/routes/mobile_transfers.py` - `transfers_step_product` signature changed to `(request: Request, code: str = "")`; branches on `HX-Request` header to serve the bare fragment vs. the full page.
- `app/templates/mobile_partials/transfers_step_product.html` - New: extracted step-1 ("Товар") fragment, its own `#wizard-step` wrapper, shared by the full-page GET and the HX-Request bare-fragment branch.
- `app/templates/mobile_pages/transfers.html` - `{% block content %}` now just `<h1>Перемещение</h1>` + `{% include "mobile_partials/transfers_step_product.html" %}` instead of inlining the step-1 markup.
- `app/templates/mobile_partials/transfers_step_batch.html` - Replaced `<a class="mobile-back" href="/m/transfers">Назад</a>` with `<button type="button" class="secondary" hx-get="/m/transfers" hx-vals="{{ {'code': code} | tojson }}" hx-target="#wizard-step" hx-swap="outerHTML">Назад</button>`.
- `tests/test_mobile_transfers.py` - 4 new tests: no-plain-link assertion on the batch step's Назад, HX-Request bare-fragment + code-echo assertion, plain-GET full-page + code-echo assertion, and the UI-02 header regression guard.

## Decisions Made
- Reused the exact `hx-vals` technique `transfers_step_batch.html`'s own batch-pick cards already use for carrying `code` forward, rather than `hx-include`, since this partial has no wrapping `<form>` of its own — consistent with `transfers_step_dest.html`'s existing "Назад" button.
- Did not touch `transfers_step_dest.html`'s "Назад" (step 3) — it already correctly uses `hx-post`/`hx-vals`, out of scope for this plan.

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed incorrect literal-string assertion drafted from the plan's own acceptance criteria text**
- **Found during:** Task 2 (writing the new HX-Request/full-page tests)
- **Issue:** The plan's action text specifies checking for the literal string `"&lt;html"` (HTML-escaped `<html`) to distinguish a bare fragment from a full page. This string never appears in real output — the codebase's established convention (`test_reports.py`) checks the raw `"<html"` substring instead. Following the plan's literal text verbatim would have produced vacuously-true assertions in the fragment test and a failing assertion in the full-page test.
- **Fix:** Used `"<html"` (matching `test_reports.py`'s precedent) instead of `"&lt;html"` in both new tests.
- **Files modified:** `tests/test_mobile_transfers.py`
- **Verification:** Both tests pass and correctly discriminate fragment-vs-full-page output (manually confirmed the fragment test fails if the route's HX-Request branch is removed).
- **Committed in:** `b87c219` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — test assertion string)
**Impact on plan:** No scope creep; the underlying route/template behavior matches the plan exactly. Only the literal test-assertion string was corrected to match actual (and codebase-precedented) template output.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 4 success criteria met: step 2's "Назад" is `hx-get`-driven with `hx-vals` carrying `code`; `GET /m/transfers` accepts/echoes `?code=`; the pre-existing Phase 12 header is now explicitly regression-tested (UI-02); `uv run pytest tests/test_mobile_transfers.py` is green (16/16) with zero regressions.
- Full project test suite (`uv run pytest`) passes at 491/491 — no regressions introduced elsewhere.
- No blockers for remaining Phase 13 plans.

---
*Phase: 13-mobile-wizard-context-navigation*
*Completed: 2026-07-14*

## Self-Check: PASSED

- FOUND: app/templates/mobile_partials/transfers_step_product.html
- FOUND: .planning/phases/13-mobile-wizard-context-navigation/13-04-SUMMARY.md
- FOUND commit: 2c57aa5 (Task 1)
- FOUND commit: b87c219 (Task 2)
- FOUND commit: 68fd5d3 (SUMMARY metadata commit)
