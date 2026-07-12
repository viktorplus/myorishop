---
status: diagnosed
phase: 11-dedicated-mobile-flow
source: [11-VERIFICATION.md]
started: 2026-07-13T00:00:00Z
updated: 2026-07-13T01:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Phone-width auto-redirect from / to /m/
expected: Open the app in a real browser (or devtools responsive mode) at <600px viewport width and navigate to / — browser auto-redirects to /m/ (the mobile home tile grid)
result: issue
reported: "перешел на m а там {\"detail\":\"Not Found\"}"
severity: blocker

### 2. Redirect scope does not break desktop-only pages
expected: At a desktop-width viewport (>=600px), navigate to / and confirm no redirect occurs; separately, at a phone-width viewport, navigate directly to /customers, /backup, /dictionary, /warehouses, /categories, /export and confirm none of them silently bounce to /m/
result: issue
reported: "http://127.0.0.1:8000/transfers - переход на мобильную не смотря на ширину больше 600 остальные страницы нормально"
severity: major

### 3. All 8 home tiles reach their mapped screens
expected: On a phone-width browser (or emulator), tap each of the 8 home tiles from /m/ and confirm each reaches its mapped screen — Продажа -> /m/sales, Приход -> /m/receipts, Поиск -> /m/search, Списание -> /m/writeoff, Корректировка -> /m/corrections, Перемещение -> /m/transfers, История -> /m/history, Сроки годности -> /m/reports/expiry
result: blocked
blocked_by: prior-phase
reason: "Cannot test — /m/ home page returns 404 (see Test 1)"

### 4. Batch cards show all fields with no truncation at phone width
expected: At a batch-selection step (Sale/Write-off/Correction/Transfer) for a product with 2+ open batches, visually confirm every card shows price, expiry, remaining quantity, and comment with no truncation and no "expand to see more" interaction
result: blocked
blocked_by: prior-phase
reason: "Cannot test — /m/sales returns 404, entire /m/ router appears broken (see Test 1)"

### 5. Wizards feel thumb-operable, one action per screen
expected: Walk through each wizard (Sale, Receipt, Write-off, Correction, Transfer) on a real phone or emulator, confirming one action per screen, 44px+ tap targets, and thumb-operability
result: blocked
blocked_by: prior-phase
reason: "Cannot test — entire /m/ router appears broken (see Test 1)"

### 6. Desktop pages remain visually unchanged
expected: At desktop width (>=600px), spot-check the category page, batch picker, transfer form, expiry report, and other pre-existing pages for pixel-for-pixel visual parity with pre-Phase-11 screenshots/memory
result: issue
reported: "перемещение переключает на мобильную версию которая не работает уже писал об этом остальные норм (same root cause as Test 2 — /transfers redirects to broken /m/ at desktop width)"
severity: major

## Summary

total: 6
passed: 0
issues: 3
pending: 0
skipped: 0
blocked: 3

## Gaps

- truth: "Browser auto-redirects to /m/ (the mobile home tile grid)"
  status: failed
  reason: "User reported: перешел на m а там {\"detail\":\"Not Found\"}"
  severity: blocker
  test: 1
  root_cause: "Not a code defect — stale dev server process. app/main.py registers all 10 mobile routers correctly (verified: commit 5904e47 'feat(11-09): register all 10 mobile routers in app.main' at 2026-07-12 23:37:56+02:00), and a fresh TestClient against the current app returns HTTP 200 with correct HTML for /m/ and /m/sales. run.bat starts uvicorn without --reload, so any server process started before 23:37:56 kept serving the pre-wiring route table (no /m/... routes at all) for the rest of the session, producing FastAPI's default 404 on every /m/ request. UAT ran at 00:48:59, 71 minutes after the wiring commit — well within a plausible forgot-to-restart window."
  artifacts:
    - path: "app/main.py"
      issue: "Correct on disk — no fix needed. Confirmed via route enumeration and TestClient smoke test."
  missing:
    - "No code change required. Restart the uvicorn server (stop run.bat, relaunch) so it picks up the router registration, then re-run UAT."
  debug_session: .planning/debug/mobile-router-404.md

- truth: "At a desktop-width viewport (>=600px), navigating to /transfers must not redirect to /m/"
  status: failed
  reason: "User reported: http://127.0.0.1:8000/transfers - переход на мобильную не смотря на ширину больше 600 остальные страницы нормально"
  severity: major
  test: 2
  root_cause: "Investigation inconclusive as a code defect — extensive review (redirect script, transfers.py, mobile_transfers.py routing, middleware, template inheritance, 30 passing tests) found no mechanism in the codebase that could redirect /transfers to /m/ at desktop width; base.html's redirect script is provably scoped to exact pathname '/' only. Leading hypothesis: the tester was still inside the mobile session (auto-redirected from / to /m/ at phone width per Test 1) and tapped the mobile 'Перемещение' tile, landing on the already-broken /m/transfers (same stale-server cause as Test 1), rather than a fresh desktop-width navigation to the literal /transfers URL."
  artifacts: []
  missing:
    - "Re-verify with a hard-refreshed browser (cache cleared, fresh tab) against a restarted server, navigating directly to the /transfers URL bar entry at desktop width — not via a tap from within an already-mobile session."
  debug_session: .planning/debug/transfers-desktop-mobile-redirect.md

- truth: "At desktop width (>=600px), the transfer form page must render normally, not redirect to /m/"
  status: failed
  reason: "User reported: перемещение переключает на мобильную версию которая не работает (same root cause as Test 2)"
  severity: major
  test: 6
  root_cause: "Same as Test 2 — see debug_session .planning/debug/transfers-desktop-mobile-redirect.md. No code-level redirect mechanism found; leading hypothesis is a stale mobile session state during testing rather than a genuine desktop-width redirect bug."
  artifacts: []
  missing:
    - "Re-verify together with Test 2 after server restart and a fresh desktop-width navigation."
  debug_session: .planning/debug/transfers-desktop-mobile-redirect.md
