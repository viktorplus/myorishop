---
status: complete
phase: 09-batch-tracking-ledger-integration
source: [09-VERIFICATION.md]
started: 2026-07-12T00:00:00Z
updated: 2026-07-12T13:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Receipt batch chooser — top-up vs new batch + conditional new-batch fields
expected: For a product with existing batches, after entering the code and picking a warehouse, the chooser lists «Пополнить партию» radios per open batch AND a «Новая партия» radio; the new-batch fields (срок/место/комментарий) appear only when «Новая партия» is selected, and disabled inputs never submit on top-up.
result: issue
reported: "при загрузке форм не понятно какая форма выбрана радиокнопка всего одна и непонятно к чему относится и уже выбрана. при вводе кода существующего продукта название не подставляется. партия должна иметь название при создании имя и текущая дата"
severity: major

### 2. Sale batch picker — four columns, D-07 order, oob price fill
expected: For a 2-batch product, the inline picker shows exactly four columns (Цена, Срок годности, Остаток, Комментарий) in earliest-expiry-first / NULL-last order; picking a batch fills the line price with the batch price via hx-swap-oob and shows the hint «Цена подставлена из партии — можно изменить».
result: pass

### 3. Single-batch auto-select
expected: A single-batch product at sale time auto-selects the only batch (pre-checked, highlighted) with the note «Партия выбрана автоматически — единственная», and the selection remains changeable.
result: pass

### 4. Per-batch oversell warn-but-allow across sale/write-off/correction
expected: Picking a batch whose remaining is smaller than another batch of the same product and requesting more than that batch holds shows a warning scoped to the picked batch's remaining (not the product total); no write happens until «...всё равно» (confirm=1), which then commits.
result: issue
reported: "выберите партию написано дважды после клика на партию, внизу появляется еще одна таблица, поля количество что бы ввести 8 нет, или не подписано. при нажатии на кнопку оформить продажу - введите партию, хотя партия была выбрана"
severity: blocker

### 5. Basket array-drift — delete middle line keeps batch attribution
expected: With three sale lines each on a distinct batch, deleting the MIDDLE line removes both its <tr>s; on submit each remaining line's op is attributed to its own picked batch, and a 422 re-render keeps every pick.
result: issue
reported: "все сработало до оформления продажи, запросило количество после ввода ошибка выберите партию под каждой позицией"
severity: blocker

### 6. /history legacy vs batched attribution after migration
expected: A pre-Phase-9 (NULL batch_id) stock op renders the muted «До внедрения партий» second line; a batched op renders «Партия: {срок}{ — comment}»; price-change/product rows show no batch second line; a return of a legacy sale shows «Возврат в партию: Остаток до внедрения партий».
result: issue
reported: "все хорошо но кнопки возврат не нашел и нужна еще одна колонка код продукта вместо поиска ее в поле Товар"
severity: major

## Summary

total: 6
passed: 2
issues: 4
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "Chooser forces an explicit top-up/new choice; radio pre-selection is unambiguous; only one radio should not appear ambiguously; product name autofills on existing product code entry; batches have a name (auto-generated from creation date) at creation time."
  status: failed
  reason: "User reported: при загрузке форм не понятно какая форма выбрана радиокнопка всего одна и непонятно к чему относится и уже выбрана. при вводе кода существующего продукта название не подставляется. партия должна иметь название при создании имя и текущая дата"
  severity: major
  test: 1
  artifacts: []
  missing: []

- truth: "Picking a batch in the sale line picker shows exactly one clear selection state (no duplicated 'Выберите партию' text, no stray extra table), the quantity input is present and labeled, and submitting the sale recognizes the picked batch instead of rejecting with «Выберите партию.»."
  status: failed
  reason: "User reported: выберите партию написано дважды после клика на партию, внизу появляется еще одна таблица, поля количество что бы ввести 8 нет, или не подписано. при нажатии на кнопку оформить продажу - введите партию, хотя партия была выбрана"
  severity: blocker
  test: 4
  artifacts: []
  missing: []

- truth: "Submitting a multi-line sale with a batch picked on every line recognizes each line's picked batch instead of rejecting all lines with «Выберите партию.»."
  status: failed
  reason: "User reported: все сработало до оформления продажи, запросило количество после ввода ошибка выберите партию под каждой позицией"
  severity: blocker
  test: 5
  artifacts: []
  missing: []

- truth: "A return action is discoverable in /history for a legacy sale (so the «Возврат в партию: Остаток до внедрения партий» line can be verified); /history has a product-code column instead of requiring search-by-name in the Товар field."
  status: failed
  reason: "User reported: все хорошо но кнопки возврат не нашел и нужна еще одна колонка код продукта вместо поиска ее в поле Товар"
  severity: major
  test: 6
  artifacts: []
  missing: []
