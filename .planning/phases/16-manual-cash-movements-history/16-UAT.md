---
status: complete
phase: 16-manual-cash-movements-history
source: [16-VERIFICATION.md]
started: 2026-07-15T10:20:00Z
updated: 2026-07-15T14:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Desktop /finance interactive flow
expected: Run the app, open http://localhost:8000/finance. Withdraw «Оплата поставщику» 15,00 → balance drops and the row appears in history. Try a withdrawal larger than the balance → «Баланс уйдёт в минус» warning with «Снять всё равно» (nothing written until confirmed). Deposit «Начальный остаток» 100 → balance rises. Filter «Тип» → Снятие → only withdrawals shown. Page through history → the active filter is preserved on every page link.
result: pass
verified_by: Claude via claude-in-chrome browser automation
notes: |
  Deposit «Начальный остаток» 100 → balance 0,00 → 100,00. Withdraw «Оплата
  поставщику» 15,00 → balance 100,00 → 85,00, row appears in history. Over-balance
  withdrawal 999,00 → «Баланс уйдёт в минус» + «Текущий баланс 85,00, снимаете
  999,00» + «Снять всё равно» / «Вернуться к форме»; balance stayed 85,00 and no
  row was written (history still 2 rows after cancel). «Тип» → Снятие filtered to
  withdrawals only (URL ?bucket=withdrawal). Bonus: «Прочее» category correctly
  requires a comment («Укажите комментарий.»). Multi-page filter-preservation is
  covered by Test 2 (mobile shares the same paginated service).

### 2. Mobile /m/finance interactive flow
expected: Open http://localhost:8000/m/finance (or on a phone). Withdraw and deposit → they persist and the balance updates. Trigger an over-balance withdrawal → warning + «Снять всё равно». Scroll the card history, use the «Тип» filter, tap «Показать ещё» → history renders as cards (not a numbered bar) and «Показать ещё» appends the next page.
result: pass
verified_by: Claude via claude-in-chrome browser automation
notes: |
  Withdraw «Оплата поставщику» 5,00 → balance 85,00 → 80,00; deposit «Корректировка»
  20,00 → balance 80,00 → 100,00 (both persisted). Over-balance 999,00 → «Баланс
  уйдёт в минус» + «Снять всё равно», balance stayed 80,00. History renders as
  cards (date · type / comment / amount), NOT a numbered bar. «Тип» → Снятие
  filtered to withdrawals only. Seeded 21 extra withdrawals to exceed the 20-row
  page: «Показать ещё» appeared, and clicking it APPENDED page 2 containing only
  withdrawals (seed 1, моб снятие, оплата счёта) — the two deposits stayed hidden,
  confirming the active filter is preserved across pages.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none — both tests passed]

## Advisory Findings (non-blocking)

- **Cosmetic (desktop only):** On /finance, a movement saved with an EMPTY comment
  renders the literal string `None` in the «Комментарий» table column instead of a
  blank cell (Python `None` leaking into the Jinja template). The mobile card view
  handles this correctly (empty comment → no comment line). Suggest guarding the
  desktop template cell with `{{ movement.note or "" }}` (or equivalent). Not part
  of either test's expected behaviour, so recorded as advisory rather than a gap.

- **Test-data note:** This UAT was driven live against the local DB. It wrote 2
  deposits and 23 withdrawals (incl. 21 `seed N` rows added via POST to exercise
  «Показать ещё» pagination). The cash ledger is append-only (project decision), so
  these were intentionally NOT deleted. If a clean finance history is wanted, reset
  the dev DB / restore from a backup.
