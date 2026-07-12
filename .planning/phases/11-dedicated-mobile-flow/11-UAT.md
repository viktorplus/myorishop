---
status: partial
phase: 11-dedicated-mobile-flow
source: [11-VERIFICATION.md]
started: 2026-07-13T00:00:00Z
updated: 2026-07-13T00:35:00Z
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
  artifacts: []
  missing: []

- truth: "At a desktop-width viewport (>=600px), navigating to /transfers must not redirect to /m/"
  status: failed
  reason: "User reported: http://127.0.0.1:8000/transfers - переход на мобильную не смотря на ширину больше 600 остальные страницы нормально"
  severity: major
  test: 2
  artifacts: []
  missing: []

- truth: "At desktop width (>=600px), the transfer form page must render normally, not redirect to /m/"
  status: failed
  reason: "User reported: перемещение переключает на мобильную версию которая не работает (same root cause as Test 2)"
  severity: major
  test: 6
  artifacts: []
  missing: []
