---
status: testing
phase: 17-financial-reports-export-dashboard-analytics
source: [17-VERIFICATION.md]
started: 2026-07-15T00:00:00Z
updated: 2026-07-15T00:00:00Z
---

## Current Test

number: 1
name: Dashboard tiles + period selector behavior (desktop and mobile)
expected: |
  Three tiles render with exact UI-SPEC copy; net tile always shows the cash-outflow
  caveat; stock tile always shows «на текущий момент»; changing the period updates
  gross/net only — stock tile, balance, forms, and history stay visually unchanged.
awaiting: user response

## Tests

### 1. Dashboard tiles + period selector behavior (desktop and mobile)
expected: |
  Open /finance and /m/finance; change the light period selector preset. Three tiles
  render with exact UI-SPEC copy; net tile always shows the cash-outflow caveat; stock
  tile always shows «на текущий момент»; changing the period updates gross/net only —
  stock tile, balance, forms, and history stay visually unchanged.
result: [pending]

### 2. CSV export opens correctly in Excel
expected: |
  Download CSV from /finance/report and /m/finance/report, open in Excel (RU locale).
  Single BOM detected, ;-separated columns (Когда/Категория/Комментарий/Сумма), correct
  Cyrillic, signed amounts like «-12,00», no formula execution on notes starting with
  =/+/-/@.
result: [pending]

### 3. Mobile dashboard tile layout on a real/emulated phone viewport
expected: |
  Open /m/finance and /m/finance/report on a ~360-414px viewport. Tiles remain readable
  without overflow/clipping, in a 2-column layout (fixed in commit 3b62940 — standard
  end-of-phase visual confirmation).
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
