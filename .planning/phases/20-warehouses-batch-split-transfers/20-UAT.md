---
status: testing
phase: 20-warehouses-batch-split-transfers
source: [20-VERIFICATION.md]
started: 2026-07-16T18:01:29Z
updated: 2026-07-16T18:01:29Z
---

## Current Test

number: 1
name: Warehouse delete three-state flow in a live browser
expected: |
  All three states render correctly and the HX-Redirect actually navigates the browser:
  (1) delete a warehouse with stock -> stock-blocked message + button stays;
  (2) delete the last active warehouse -> warn card appears, "Удалить всё равно" completes the delete, "Отмена" dismisses the card client-side;
  (3) delete a non-last-active warehouse with zero stock -> redirected to /warehouses.
awaiting: user response

## Tests

### 1. Warehouse delete three-state flow in a live browser
expected: All three states render correctly and the HX-Redirect actually navigates the browser (TestClient only asserts the header is present, it does not execute the redirect).
result: [pending]

### 2. Desktop /transfers: destination-warehouse selection survives oversell re-render (CR-01)
expected: |
  Pick a batch, select the SAME warehouse as destination, leave both override fields blank, submit, see the D-06 error, then trigger an over-transfer (qty > available) with a filled override, click "Переместить всё равно" on the oversell warning.
  The destination-warehouse <select> keeps the operator's original choice pre-selected through the oversell re-render (this exact scenario was CR-01, a real bug found only by tracing actual browser round-trips).
result: [pending]

### 3. Mobile wizard same-warehouse split with override fields
expected: |
  Pick a batch, advance to step 3, confirm the two override fields (Новый срок годности / Новое состояние или комментарий) appear, fill only the expiry override, choose the SAME warehouse as the source, submit.
  A new destination batch is created in the same warehouse holding only the moved quantity; the success screen shows the correct transferred qty.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
