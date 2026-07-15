---
status: testing
phase: 16-manual-cash-movements-history
source: [16-VERIFICATION.md]
started: 2026-07-15T10:20:00Z
updated: 2026-07-15T10:20:00Z
---

## Current Test

number: 1
name: Desktop /finance interactive flow
expected: |
  Balance drops after a withdraw and the row appears in history; an over-balance
  withdrawal shows «Баланс уйдёт в минус» + «Снять всё равно» and writes nothing
  until confirmed; a deposit raises the balance; the «Тип» → Снятие filter shows
  only withdrawals; paging preserves the active filter.
awaiting: user response

## Tests

### 1. Desktop /finance interactive flow
expected: Run the app, open http://localhost:8000/finance. Withdraw «Оплата поставщику» 15,00 → balance drops and the row appears in history. Try a withdrawal larger than the balance → «Баланс уйдёт в минус» warning with «Снять всё равно» (nothing written until confirmed). Deposit «Начальный остаток» 100 → balance rises. Filter «Тип» → Снятие → only withdrawals shown. Page through history → the active filter is preserved on every page link.
result: [pending]

### 2. Mobile /m/finance interactive flow
expected: Open http://localhost:8000/m/finance (or on a phone). Withdraw and deposit → they persist and the balance updates. Trigger an over-balance withdrawal → warning + «Снять всё равно». Scroll the card history, use the «Тип» filter, tap «Показать ещё» → history renders as cards (not a numbered bar) and «Показать ещё» appends the next page.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
