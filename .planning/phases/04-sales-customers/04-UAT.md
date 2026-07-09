---
status: resolved
phase: 04-sales-customers
source: [04-VERIFICATION.md]
started: 2026-07-09T14:18:05Z
updated: 2026-07-09T16:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Add a basket line via «Добавить строку» without clicking into the new row
expected: Focus lands on the new row's «Код» field automatically (no click required)
result: pass

### 2. Type a sale price, then quickly type a known product code in the same row (before the 300ms lookup debounce fires)
expected: The in-flight lookup response does not clobber the price the operator already typed (oob-swap guard holds)
result: issue
reported: "не подставляется имя товара после ввода цены - ввода кода."
severity: major

### 3. Oversell a line (qty > stock), observe the warning, click «Продать всё равно»
expected: Warning shows zero committed sale ops; confirm re-POSTs the same basket and writes, allowing Product.quantity to go negative; «Вернуться к корзине» dismisses with no write
result: pass

### 4. In the sale form: type a customer name in the picker, select a row, verify the chip appears with «Убрать»; then quick-create a new customer inline without leaving the sale
expected: Selecting a picker row (client-side dataset-read JS) flips the header to the chip state with the correct hidden customer_id; quick-create renders a chip from the server response; «Убрать» reverts to search state
result: pass

## Summary

total: 4
passed: 3
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "The in-flight lookup response does not clobber the price the operator already typed (oob-swap guard holds)"
  status: resolved
  reason: "User reported: не подставляется имя товара после ввода цены - ввода кода."
  severity: major
  test: 2
  root_cause: "GET /sales/lookup (app/routes/sales.py:71-96) declares bare query params code/name/price, but the basket row inputs (app/templates/partials/sale_row.html) use array-form names code[]/name[]/price[] with hx-include=\"closest tr\", so every request sends bracketed keys FastAPI never binds to the bare params. code always arrives as \"\", lookup_prefill() returns None, and the route always answers 204 — no swap ever happens. Unconditional break, not specific to typing price first."
  artifacts:
    - path: "app/routes/sales.py"
      issue: "sale_lookup() query params (code/name/price) unaliased; real requests send code[]/name[]/price[]"
    - path: "app/templates/partials/sale_row.html"
      issue: "code input name=\"code[]\" + hx-include=\"closest tr\" sends bracketed keys to /sales/lookup"
  missing:
    - "Alias the /sales/lookup query params to code[]/name[]/price[] (mirroring the alias=\"code[]\" pattern already used on POST /sales), or change the lookup request to send bare-named params instead of relying on the array-named row inputs"
  debug_session: ".planning/debug/sale-lookup-name-not-filling.md"
