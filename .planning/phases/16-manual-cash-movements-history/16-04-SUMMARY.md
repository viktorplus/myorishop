---
phase: 16-manual-cash-movements-history
plan: 04
subsystem: ui
tags: [fastapi, htmx, jinja2, finance, cash-ledger, mobile]

# Dependency graph
requires:
  - phase: 16-01
    provides: CASH_CATEGORIES/CASH_BUCKETS/CASH_BUCKET_LABELS constants + Jinja globals
  - phase: 16-02
    provides: record_manual_movement + cash_history_view services
  - phase: 16-03
    provides: shared withdraw_form/deposit_form/cash_negative_balance/cash_balance partials + finance_base pattern
provides:
  - Mobile POST /m/finance/withdraw and /m/finance/deposit reusing the shared forms + service (no fork)
  - Mobile-native cash history — .mobile-card stacks + a «Тип» bucket filter + «Показать ещё» load-more
  - GET /m/finance/history (HX cards + oob load-more; plain GET full page) and an extended full-page GET /m/finance
affects: [phase-17, financial-reports, mobile]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "finance_base-parameterised shared forms reused on the mobile surface (/m/finance)"
    - "mobile card-list history: oob-wrapper flag on the cards partial drives page-include vs oob-refresh vs beforeend-append modes"
    - "has_next load-more sentinel (mobile) instead of the desktop numbered pagination bar"

key-files:
  created:
    - app/templates/mobile_partials/cash_history_cards.html
    - app/templates/mobile_partials/cash_history_load_more.html
  modified:
    - app/routes/mobile_finance.py
    - app/templates/mobile_pages/finance.html
    - tests/test_finance.py

key-decisions:
  - "Mobile history uses cards + «Показать ещё» load-more (has_next sentinel), never the desktop numbered pagination bar (UI-SPEC Q1 / Pitfall 7)"
  - "cash_history_cards.html owns an optional `#cash-history-cards` oob wrapper (via an `oob` flag) so one partial serves page-include, oob-refresh, and beforeend-append without nesting"
  - "Mobile withdraw/deposit copy the desktop route branch logic verbatim, changing only finance_base=/m/finance; write path + forms fully reused, no fork"

patterns-established:
  - "Pattern 1: shared HTMX forms parameterised by finance_base resolve on either desktop or mobile router"
  - "Pattern 2: mobile action-success composes an HTMLResponse of fresh form + oob balance + oob cards + oob load-more (sibling-concat, mirrors mobile_history)"

requirements-completed: [FIN-03, FIN-04, FIN-05, FIN-07]

# Metrics
duration: 20min
completed: 2026-07-15
---

# Phase 16 Plan 04: Mobile Manual Cash Movements & History Summary

**Mobile `/m/finance` at desktop parity — withdraw/deposit reusing the shared forms + service, negative-balance warn-but-allow, and a card-list «Тип»-filterable history with a «Показать ещё» load-more (no numbered bar).**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-15T07:30:00Z
- **Completed:** 2026-07-15T07:50:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- Mobile POST `/m/finance/withdraw` + `/m/finance/deposit` delegating ALL validation to `record_manual_movement` (D-00c) with the same 200/422/negative-warn branching as desktop — the write path and the shared forms are reused verbatim (finance_base=`/m/finance`), no fork.
- Mobile-native cash history: `mobile_partials/cash_history_cards.html` (one `.mobile-card` per movement, 4 D-07b fields, autoescape only) + `cash_history_load_more.html` (`has_next` «Показать ещё» sentinel), plus a «Тип» bucket filter wired on the finance page.
- `GET /m/finance/history` returns HX cards + an oob `#cash-history-load-more`; a successful withdraw/deposit oob-refreshes the balance AND the card list in place.

## Task Commits

Each task was committed atomically (TDD: failing tests written first, then implementation in the same commit):

1. **Task 1: Mobile withdraw/deposit reusing the shared forms** - `54fee9d` (feat)
2. **Task 2: Mobile cash history (cards + «Показать ещё» load-more)** - `f3f6146` (feat)

## Files Created/Modified
- `app/routes/mobile_finance.py` - Added POST withdraw/deposit, GET /m/finance/history, extended full-page GET /m/finance, `_history_context` + `_movement_success` helpers; imports `record_manual_movement` + `cash_history_view`.
- `app/templates/mobile_pages/finance.html` - Balance + both shared forms + «История движений» block («Тип» select, `#cash-history-cards`, load-more include).
- `app/templates/mobile_partials/cash_history_cards.html` - `.mobile-card` per movement (date · label / note / signed amount), two empty states, optional oob wrapper.
- `app/templates/mobile_partials/cash_history_load_more.html` - `#cash-history-load-more` sentinel + «Показать ещё» button (hx-get carries next page + active bucket).
- `tests/test_finance.py` - 16 new mobile web tests (withdraw/deposit/negative/history/filter/escape/oob) via `mobile_client_factory`.

## Decisions Made
- Mobile history presentation forked to cards + load-more (UI-SPEC Q1); no numbered pagination on the phone.
- The cards partial carries its own optional `#cash-history-cards` oob wrapper (via an `oob` flag) so a single partial serves the page include, the oob success-refresh, and the beforeend load-more append without nested divs.

## Deviations from Plan

None - plan executed exactly as written. (One cosmetic adjustment: reworded a template comment so the literal token `|safe` does not appear in `cash_history_cards.html`, satisfying the `grep -c "|safe" == 0` acceptance guard while the substantive "autoescape only, never the safe filter" instruction is preserved.)

## Issues Encountered
- Initial `grep -c "|safe"` returned 1 because a template comment contained the literal `|safe` while warning against it. Reworded the comment to "the safe filter is NEVER applied" — grep now returns 0. No functional change.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- FIN-03/04/05/07 now delivered on both desktop and mobile surfaces at parity (D-06a) — the Financial Reports/Export/Dashboard phase (17) can build on a complete manual-movement ledger.
- Human visual check outstanding (verification `<human-check>`): open `/m/finance` on the phone and confirm withdraw/deposit persist, the over-balance warn appears, and «Показать ещё» loads the next page.
- Full suite green: `634 passed`; `ruff check app/routes/mobile_finance.py` clean.

## Self-Check: PASSED

All created files exist on disk; both task commits (`54fee9d`, `f3f6146`) are present in git history.

---
*Phase: 16-manual-cash-movements-history*
*Completed: 2026-07-15*
