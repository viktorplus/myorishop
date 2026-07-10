---
phase: 05-stock-operations-history
plan: 06
subsystem: ui
tags: [jinja2, htmx, navigation, gap-closure]

# Dependency graph
requires:
  - phase: 05-stock-operations-history
    provides: "/writeoff route + service (05-02) — fully implemented and tested but unreachable via UI"
provides:
  - "base.html nav bar link to /writeoff (Списание), positioned between Продажи and Покупатели"
  - "home.html contextual link to /writeoff alongside /corrections and /history"
  - "regression test test_web_writeoff_reachable_from_nav guarding the link renders on GET /"
affects: [05-VERIFICATION, 05-REVIEW]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - app/templates/base.html
    - app/templates/pages/home.html
    - tests/test_writeoffs.py

key-decisions:
  - "No new decisions — pure template wiring, no service/route changes"

patterns-established: []

requirements-completed: [OPS-01]

# Metrics
duration: 6min
completed: 2026-07-10
---

# Phase 05 Plan 06: Wire /writeoff into nav and home page Summary

**Closed the OPS-01 UI gap: base.html nav bar and home.html now both link to /writeoff, with a regression test guarding against it silently regressing again.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-10T01:51:00Z
- **Completed:** 2026-07-10T01:57:36Z
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- `base.html` nav bar gained a `Списание` link to `/writeoff`, positioned between `Продажи` and `Покупатели`, using the same active-class pattern as every sibling link.
- `home.html`'s product-present content block gained a leading `<a href="/writeoff">Списание</a> ·` before the existing `/corrections`/`/history` links.
- Added `test_web_writeoff_reachable_from_nav` to `tests/test_writeoffs.py`, asserting `GET /` returns 200 and contains `href="/writeoff"`.
- Closed `05-VERIFICATION.md`'s Gap #1 / `05-REVIEW.md`'s CR-01: OPS-01's write-off feature is now reachable from the running app's own navigation, not only by typing the URL.

## Task Commits

Each task was committed atomically:

1. **Task: Wire /writeoff into the nav bar and home page (CR-01/OPS-01 gap)** - `337ad94` (feat)

_Note: single-task plan, one commit._

## Files Created/Modified
- `app/templates/base.html` - added `<a href="/writeoff">Списание</a>` nav anchor with active-state matching sibling links
- `app/templates/pages/home.html` - added `/writeoff` link to the `{% if product %}` content block, updated the D-12/D-17 comment to note the gap closure
- `tests/test_writeoffs.py` - added `test_web_writeoff_reachable_from_nav` regression test

## Decisions Made
None - followed plan as specified. Pure template/test wiring, no service or route changes, consistent with the plan's threat model (no new trust boundary).

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Pre-existing ruff `I001` (import-block-unsorted) finding in `tests/test_writeoffs.py` lines 17-21 exists both before and after this plan's changes (verified via `git stash`/re-check) — unrelated to this task's edits (the task only appended a new test function; imports were untouched). Out of scope per the plan's own acceptance note ("or only pre-existing, unrelated findings already noted in 05-VERIFICATION.md"). `ruff format --check` passes clean.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- OPS-01 is now fully achievable through the running app's own navigation. `05-VERIFICATION.md`'s Gap #1 is closed; a re-run of phase verification would find 4/4 must-haves verified.
- Full test suite: 163 passed (162 existing + 1 new), no regressions.
- `grep -c 'href="/writeoff"'` >= 1 in both `base.html` and `home.html`, confirmed.
- No blockers for Phase 5 completion.

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-10*
