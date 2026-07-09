---
status: testing
phase: 04-sales-customers
source: [04-VERIFICATION.md]
started: 2026-07-09T14:18:05Z
updated: 2026-07-09T14:18:05Z
---

## Current Test

number: 1
name: Add a basket line via «Добавить строку» without clicking into the new row
expected: |
  Focus lands on the new row's «Код» field automatically (no click required)
awaiting: user response

## Tests

### 1. Add a basket line via «Добавить строку» without clicking into the new row
expected: Focus lands on the new row's «Код» field automatically (no click required)
result: [pending]

### 2. Type a sale price, then quickly type a known product code in the same row (before the 300ms lookup debounce fires)
expected: The in-flight lookup response does not clobber the price the operator already typed (oob-swap guard holds)
result: [pending]

### 3. Oversell a line (qty > stock), observe the warning, click «Продать всё равно»
expected: Warning shows zero committed sale ops; confirm re-POSTs the same basket and writes, allowing Product.quantity to go negative; «Вернуться к корзине» dismisses with no write
result: [pending]

### 4. In the sale form: type a customer name in the picker, select a row, verify the chip appears with «Убрать»; then quick-create a new customer inline without leaving the sale
expected: Selecting a picker row (client-side dataset-read JS) flips the header to the chip state with the correct hidden customer_id; quick-create renders a chip from the server response; «Убрать» reverts to search state
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
