---
status: testing
phase: 09-batch-tracking-ledger-integration
source: [09-VERIFICATION.md]
started: 2026-07-12T00:00:00Z
updated: 2026-07-12T00:00:00Z
---

## Current Test

number: 1
name: Receipt batch chooser — top-up vs new batch + conditional new-batch fields
expected: |
  Chooser forces an explicit top-up/new choice; new-batch fields (срок/место/комментарий)
  hide/show on «Новая партия» selection and disabled inputs never submit on top-up.
awaiting: user response

## Tests

### 1. Receipt batch chooser — top-up vs new batch + conditional new-batch fields
expected: For a product with existing batches, after entering the code and picking a warehouse, the chooser lists «Пополнить партию» radios per open batch AND a «Новая партия» radio; the new-batch fields (срок/место/комментарий) appear only when «Новая партия» is selected, and disabled inputs never submit on top-up.
result: [pending]

### 2. Sale batch picker — four columns, D-07 order, oob price fill
expected: For a 2-batch product, the inline picker shows exactly four columns (Цена, Срок годности, Остаток, Комментарий) in earliest-expiry-first / NULL-last order; picking a batch fills the line price with the batch price via hx-swap-oob and shows the hint «Цена подставлена из партии — можно изменить».
result: [pending]

### 3. Single-batch auto-select
expected: A single-batch product at sale time auto-selects the only batch (pre-checked, highlighted) with the note «Партия выбрана автоматически — единственная», and the selection remains changeable.
result: [pending]

### 4. Per-batch oversell warn-but-allow across sale/write-off/correction
expected: Picking a batch whose remaining is smaller than another batch of the same product and requesting more than that batch holds shows a warning scoped to the picked batch's remaining (not the product total); no write happens until «...всё равно» (confirm=1), which then commits.
result: [pending]

### 5. Basket array-drift — delete middle line keeps batch attribution
expected: With three sale lines each on a distinct batch, deleting the MIDDLE line removes both its <tr>s; on submit each remaining line's op is attributed to its own picked batch, and a 422 re-render keeps every pick.
result: [pending]

### 6. /history legacy vs batched attribution after migration
expected: A pre-Phase-9 (NULL batch_id) stock op renders the muted «До внедрения партий» second line; a batched op renders «Партия: {срок}{ — comment}»; price-change/product rows show no batch second line; a return of a legacy sale shows «Возврат в партию: Остаток до внедрения партий».
result: [pending]

## Summary

total: 6
passed: 0
issues: 0
pending: 6
skipped: 0
blocked: 0

## Gaps
