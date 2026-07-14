---
phase: 15-cash-ledger-foundation
plan: 04
subsystem: ui
tags: [fastapi, jinja2, htmx, finance-display]

# Dependency graph
requires:
  - phase: 15-02
    provides: "app/services/finance.py — compute_balance(session)"
  - phase: 15-03
    provides: "register_sale/register_return cash-write hooks (proven correct balance state to display)"
provides:
  - "GET /finance and GET /m/finance — read-only «Баланс кассы» display, routes import compute_balance ONLY"
  - "«Финансы» reachable from the desktop nav (after /export) and the mobile hub tile grid (after /m/reports/expiry)"
  - "3 new page-render tests (desktop empty/non-zero + mobile) in tests/test_finance.py"
affects: [16-manual-cash-movements-history]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Finance display routes mirror the writeoffs.py/mobile_reports.py thin-route shape exactly: Depends(get_session) -> service call -> TemplateResponse, zero business logic in the route"

key-files:
  created:
    - app/routes/finance.py
    - app/routes/mobile_finance.py
    - app/templates/pages/finance.html
    - app/templates/mobile_pages/finance.html
  modified:
    - app/main.py
    - app/templates/base.html
    - app/templates/mobile_pages/home.html
    - tests/test_finance.py

key-decisions:
  - "Balance-only templates (D-01) — no movement list/table this phase; both desktop and mobile pages are a single <h1> + one cents-filtered figure"
  - "Desktop nav link placed after /export (D-02, analytical section, near Отчёты/Экспорт); mobile tile placed after the expiry-report tile in the hub grid"

patterns-established: []

requirements-completed: [FIN-06]

# Metrics
duration: 12min
completed: 2026-07-14
---

# Phase 15 Plan 04: Cash Balance Display (Финансы) Summary

**Two thin read-only routes (`GET /finance`, `GET /m/finance`) render `compute_balance` into a «Баланс кассы» page on desktop and mobile, reachable from the desktop nav and the mobile hub, proven by 3 new page-render tests plus the full 577-test suite green.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 3 completed
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments
- `app/routes/finance.py`: `GET /finance` renders `pages/finance.html` with `{"balance_cents": compute_balance(session)}`. Imports `compute_balance` ONLY — no cash-write function imported (D-00c, verified via grep).
- `app/routes/mobile_finance.py`: `GET /m/finance` mirrors it for `mobile_pages/finance.html`, same context shape.
- `app/main.py`: `finance` and `mobile_finance` added to the routes import block; both routers registered via `include_router`.
- `app/templates/pages/finance.html` (extends `base.html`) and `app/templates/mobile_pages/finance.html` (extends `mobile_base.html`): both render `<h1>Баланс кассы</h1>` + `{{ balance_cents | cents }}`, balance-only, no movement list (D-01/D-04).
- `app/templates/base.html`: `/finance` nav link added after `/export`, with the standard `request.url.path.startswith("/finance")` active-state check.
- `app/templates/mobile_pages/home.html`: `/m/finance` tile added to the mobile hub grid after the expiry-report tile.
- `tests/test_finance.py` extended with 3 tests: `test_page_empty_shows_zero` (200 + «Баланс кассы» + "0,00" on an empty ledger), `test_page_shows_balance` (records a 12500-cent credit via `record_cash_movement`, asserts "125,00" in the rendered body), `test_mobile_page_shows_balance` (mobile-router variant via `mobile_client_factory`, same assertions).
- `uv run pytest tests/test_finance.py -x` → 14 passed.
- Full suite: `uv run pytest -q` → 577 passed, 0 failures (2 pre-existing unrelated SAWarning noise in test_receipts.py/test_returns.py, no new warnings introduced).

## Task Commits

Each task was committed atomically:

1. **Task 1: Create finance + mobile_finance routes and register them** - `417077b` (feat)
2. **Task 2: Create balance templates + desktop nav + mobile tile** - `445f611` (feat)
3. **Task 3: Route/render test for the balance page** - `b9cbb17` (test)

**Plan metadata:** committed together with this SUMMARY (worktree mode — orchestrator merges).

## Files Created/Modified
- `app/routes/finance.py` - `finance_page` (GET /finance), imports `compute_balance` only
- `app/routes/mobile_finance.py` - `mobile_finance_page` (GET /m/finance), mirrors the desktop route
- `app/templates/pages/finance.html` - «Баланс кассы» heading + cents-formatted balance figure, extends `base.html`
- `app/templates/mobile_pages/finance.html` - same content, extends `mobile_base.html`
- `app/main.py` - imports + registers `finance.router` and `mobile_finance.router`
- `app/templates/base.html` - `/finance` nav link (after `/export`)
- `app/templates/mobile_pages/home.html` - `/m/finance` tile (after the expiry-report tile)
- `tests/test_finance.py` - 3 new page-render tests (desktop empty/non-zero + mobile)

## Decisions Made
Followed the plan exactly for route shape, template content (balance-only, no list), nav/tile placement, and test coverage. No architectural deviations.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All three tasks' acceptance criteria passed on first run; no auto-fixes needed. The Task 3 TDD test was written after Tasks 1-2's implementation already existed (sequential task execution within the same plan run), so it went straight to GREEN rather than a separate RED commit — this matches the plan's own task ordering (routes/templates in Tasks 1-2, tests in Task 3) and is not a gate violation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- FIN-06 (balance display) is now observably correct end-to-end: `/finance` and `/m/finance` both show the live `compute_balance` figure via the `cents` filter, reachable from both nav surfaces.
- Phase 15 success criteria are now all satisfiable through the UI: registering a sale raises the displayed balance (proven by Plan 03's integration tests + this plan's page tests reading the same `compute_balance`), and a matching return restores it.
- No blockers. Phase 16 (manual cash movements + history) can build directly on `compute_balance` and the now-registered `/finance` routes.

## Self-Check: PASSED

All created/modified files verified present on disk; all 3 commit hashes (`417077b`, `445f611`, `b9cbb17`) verified present in `git log --oneline --all`.

---
*Phase: 15-cash-ledger-foundation*
*Completed: 2026-07-14*
