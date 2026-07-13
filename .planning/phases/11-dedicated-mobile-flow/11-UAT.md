---
status: complete
phase: 11-dedicated-mobile-flow
source: [11-VERIFICATION.md]
started: 2026-07-13T00:00:00Z
updated: 2026-07-13T03:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Phone-width auto-redirect from / to /m/
expected: Open the app in a real browser (or devtools responsive mode) at <600px viewport width and navigate to / — browser auto-redirects to /m/ (the mobile home tile grid)
result: pass

### 2. Redirect scope does not break desktop-only pages
expected: At a desktop-width viewport (>=600px), navigate to / and confirm no redirect occurs; separately, at a phone-width viewport, navigate directly to /customers, /backup, /dictionary, /warehouses, /categories, /export and confirm none of them silently bounce to /m/
result: pass

### 3. All 8 home tiles reach their mapped screens
expected: On a phone-width browser (or emulator), tap each of the 8 home tiles from /m/ and confirm each reaches its mapped screen — Продажа -> /m/sales, Приход -> /m/receipts, Поиск -> /m/search, Списание -> /m/writeoff, Корректировка -> /m/corrections, Перемещение -> /m/transfers, История -> /m/history, Сроки годности -> /m/reports/expiry
result: pass

### 4. Batch cards show all fields with no truncation at phone width
expected: At a batch-selection step (Sale/Write-off/Correction/Transfer) for a product with 2+ open batches, visually confirm every card shows price, expiry, remaining quantity, and comment with no truncation and no "expand to see more" interaction
result: pass
note: |
  RE-TEST after 11-10 fix. Check A (card legibility): PASS on first pass —
  confirmed dark/readable text at rest with product 32021 (3 open batches).
  Check B (Назад returns to batch step): user initially reported
  "Нет партий с остатком" after Назад. Investigated live — dev server (PID
  31976, started 01:14) was running code from before the 11-10 fix
  (files modified 02:04, no --reload in run.bat — same stale-server class
  as the Test 1/2/6 issue earlier in this phase, see debug_session
  mobile-router-404.md). Killed and restarted the server; re-verified via
  direct HTTP calls: POST /m/sales/step/qty-price now renders Назад wired
  to hx-get /m/sales/step/batch (from_batch_step=True), and that endpoint
  returns all 3 open batches for product 32021 with correct qty/price/expiry.
  No code change needed — confirmed fixed.

### 5. Wizards feel thumb-operable, one action per screen
expected: Walk through each wizard (Sale, Receipt, Write-off, Correction, Transfer) on a real phone or emulator, confirming one action per screen, 44px+ tap targets, and thumb-operability
result: pass

### 6. Desktop pages remain visually unchanged
expected: At desktop width (>=600px), spot-check the category page, batch picker, transfer form, expiry report, and other pre-existing pages for pixel-for-pixel visual parity with pre-Phase-11 screenshots/memory
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Previous Session (server was stale — see debug sessions for diagnosis)

- Test 1: issue (blocker) — /m/ 404. Root cause: stale server, no --reload, router wiring committed but not picked up. debug_session: .planning/debug/mobile-router-404.md
- Test 2: issue (major) — /transfers redirected to mobile at desktop width. Root cause inconclusive as code defect; leading hypothesis was stale mobile session. debug_session: .planning/debug/transfers-desktop-mobile-redirect.md
- Test 6: issue (major) — same as Test 2
- Tests 3, 4, 5: blocked (depended on /m/ working)
- Server has since been restarted (2026-07-13T01:30) and /m/, /m/sales, /transfers all verified returning HTTP 200 via curl. Re-testing all 6 from scratch below.

## Resolved (previous session — confirmed fixed on re-test, no code change needed)

- Test 1 (/m/ 404), Test 2 (/transfers redirect), Test 6 (transfer form redirect): all caused by a stale dev server process not picking up the mobile-router-wiring commit (run.bat has no --reload). Server restarted 2026-07-13T01:30; all three re-tested and now pass. debug_sessions: .planning/debug/mobile-router-404.md, .planning/debug/transfers-desktop-mobile-redirect.md

## Resolved (Plan 11-10 — code fix, confirmed via UAT re-test)

- Test 4 Bug A (white-on-white batch card text): fixed by adding an explicit `color: #222` to `button.mobile-card` in app/static/style.css (plus matching :hover/.selected states). Re-tested with product 32021 (3 open batches) — text legible at rest. debug_session: .planning/debug/mobile-batch-card-white-on-white.md
- Test 4 Bug B (Назад from qty-price skipped the batch step): fixed by adding a `from_batch_step` context flag (app/routes/mobile_sales.py) that wires the qty-price step's Назад button to `GET /m/sales/step/batch` (app/templates/mobile_partials/sale_step_qty_price.html) instead of unconditionally routing to the product step. Re-tested: initial re-test hit a stale dev server (same class of issue as Test 1/2/6 above — server running pre-fix code, no --reload); restarted server and re-verified via direct HTTP calls that Назад now returns to the batch step with all open batches rendered correctly. debug_session: .planning/debug/mobile-sale-back-nav-loses-batch-step.md

## Gaps

[none]
