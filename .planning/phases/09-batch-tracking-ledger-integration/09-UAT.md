---
status: diagnosed
phase: 09-batch-tracking-ledger-integration
source: [09-VERIFICATION.md]
started: 2026-07-12T00:00:00Z
updated: 2026-07-12T15:10:00Z
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
  root_cause: "Three independent causes. (1) Radio ambiguity: receipt_batch_chooser.html sets `new_selected = not batches`, so on a fresh GET /receipts/new (code always empty -> batches always []) the ONLY radio rendered is a pre-checked «Новая партия» with no sibling to contrast and no fieldset/legend tying the group to the top-up/new decision. (2) Name not autofilling: both the client before-swap guard (receipt_form.html:18-19) and the server 204 guard (routes/receipts.py:116-117) use 'is #name non-empty' as a proxy for 'operator deliberately typed a name'; a stale value from an earlier code lookup or native browser autofill (name_input.html has no autocomplete=off) permanently suppresses further autofill. (3) Batch has no name: Batch model (models.py:140-173) has no name/label column, register_receipt never sets one, and the new-batch form never collects one — genuine schema+form+write-path gap."
  artifacts:
    - path: "app/templates/partials/receipt_batch_chooser.html"
      issue: "new_selected = not batches auto-checks lone «Новая партия» on empty-batch/initial-load state; no fieldset/legend; no name field"
    - path: "app/routes/receipts.py"
      issue: "_chooser_context / receipt_new_page always render empty-batch state on load; name-overwrite 204 guard keyed only on field emptiness (lines 42-59, 74-83, 116-117)"
    - path: "app/templates/partials/receipt_form.html"
      issue: "client hx-on::before-swap guard suppresses name autofill whenever #name is non-empty (lines 18-19)"
    - path: "app/templates/partials/name_input.html"
      issue: "no autocomplete=off, so browser autofill leaves a stale name that blocks lookup autofill"
    - path: "app/models.py"
      issue: "Batch model has no name/label column (lines 140-173)"
    - path: "app/services/receipts.py"
      issue: "register_receipt new-batch construction never sets a name (lines 201-213)"
  missing:
    - "Distinguish 'no product/warehouse chosen yet' from 'no open batches found'; wrap the radiogroup in a fieldset/legend; do not auto-check «Новая партия» on the bare initial-load state"
    - "Replace the 'field non-empty' overwrite proxy with an explicit autofilled-vs-edited dirty flag so a NEW code lookup can refresh a previously autofilled name"
    - "Add a name/label column to Batch (or auto-generate '{product.name} — {date}' server-side at creation), thread it through register_receipt and surface it in the chooser radio label"
  debug_session: .planning/debug/receipt-batch-chooser-ux.md

- truth: "Picking a batch in the sale line picker shows exactly one clear selection state (no duplicated 'Выберите партию' text, no stray extra table), the quantity input is present and labeled, and submitting the sale recognizes the picked batch instead of rejecting with «Выберите партию.»."
  status: failed
  reason: "User reported: выберите партию написано дважды после клика на партию, внизу появляется еще одна таблица, поля количество что бы ввести 8 нет, или не подписано. при нажатии на кнопку оформить продажу - введите партию, хотя партия была выбрана"
  severity: blocker
  test: 4
  root_cause: "SHARED with test 5. sale_lookup.html emits a bare <td id=\"name-wrap\"> as the first top-level tag of the response, then a later sibling <tr id=\"batch-wrap-{row}\" hx-swap-oob=\"outerHTML\">. htmx 2.0.10 picks the fragment-parsing context from the FIRST tag (<td>), so the later <tr> is parsed as if already inside a row; the browser folds the OOB <tr>'s content (hidden batch_id[] input + «Выберите партию:» label + picker table) into the currently-open row-{row} as a bogus 6th <td colspan=5>, leaving the real <tr id=batch-wrap-{row}> sibling untouched with its ORIGINAL empty batch_id[] input. Result: two batch_id[] inputs per line (stale empty one first in DOM order, correctly-picked one second). On submit FastAPI collects both in DOM order [\"\", \"<picked>\"], and non_blank_lines' positional zip pairs each code[] with the FIRST (empty) value -> register_sale rejects «Выберите партию.» though a batch was visibly picked. Same misplaced cell explains the duplicated label text and the qty input looking unlabeled/misaligned. Verified end-to-end in a real browser (Playwright) — server fragments are correct in isolation, so this is purely the client-side htmx nesting-context bug. Multi-line just compounds it once per line."
  artifacts:
    - path: "app/templates/partials/sale_lookup.html"
      issue: "response starts with bare <td id=name-wrap> then a later sibling OOB <tr id=batch-wrap-{row}>; mixed first-tag context makes htmx misfile the OOB <tr> into the open row"
    - path: "app/templates/partials/sale_batch_pick.html"
      issue: "same pattern (a <tr> main-swap followed by a trailing bare <td hx-swap-oob=true>) leaves a cosmetically-harmless orphaned empty <tr> — same root cause, lower impact"
    - path: "app/services/sales.py"
      issue: "non_blank_lines/register_sale not buggy in isolation but receive the corrupted duplicated batch_id[] array and emit the «Выберите партию.» rejection"
  missing:
    - "Wrap the OOB <tr>/<td> fragments in <template> tags (htmx's documented pattern for table-element OOB), or reorder/split the response so the OOB <tr> is the first top-level element of its own response"
    - "Verify after fix: exactly one batch_id[] hidden input per sale line in the DOM, one «Выберите партию:» label, and a correctly column-aligned qty input"
  debug_session: .planning/debug/sale-batch-picker-not-submitted.md

- truth: "Submitting a multi-line sale with a batch picked on every line recognizes each line's picked batch instead of rejecting all lines with «Выберите партию.»."
  status: failed
  reason: "User reported: все сработало до оформления продажи, запросило количество после ввода ошибка выберите партию под каждой позицией"
  severity: blocker
  test: 5
  root_cause: "Same root cause as test 4 — the sale_lookup.html OOB <tr> nesting-context bug produces two batch_id[] inputs per line (stale empty first, picked second); with a 3-line basket every line's stale empty value wins the positional zip, so register_sale rejects every line with «Выберите партию.». Fixing the sale_lookup.html fragment fixes both tests."
  artifacts:
    - path: "app/templates/partials/sale_lookup.html"
      issue: "same OOB <tr> misparse as test 4, compounded once per basket line"
  missing:
    - "Covered by the test-4 fix (single <template>-wrapped OOB fragment); re-verify with a 3-line basket that each line submits its own picked batch"
  debug_session: .planning/debug/sale-batch-picker-not-submitted.md

- truth: "A return action is discoverable in /history for a legacy sale (so the «Возврат в партию: Остаток до внедрения партий» line can be verified); /history has a product-code column instead of requiring search-by-name in the Товар field."
  status: failed
  reason: "User reported: все хорошо но кнопки возврат не нашел и нужна еще одна колонка код продукта вместо поиска ее в поле Товар"
  severity: major
  test: 6
  root_cause: "Template-only omission on /history, not a backend bug. A fully working return flow already exists (GET/POST /returns, services/returns.py) and is wired into recent_sales.html (/sales) and purchase_history.html (customer detail) — both have a «Код» column and a «Действие» column with a «Вернуть» link (hx-get=\"/returns?sale_id=...&product_id=...&origin_op_id=...\") plus a #return-slot div. history_rows.html never carried either piece over: product code is inlined into the «Товар» cell as `Name (CODE)` instead of a separate column, and there is no «Вернуть» link or #return-slot anywhere in history.html. No data gap: operations.py::history_view() already returns {op, product, batch} per row with op.sale_id/op.id/product.id/product.code. This blocked test 6 specifically because /sales' recent-sales list is capped at 10, so an old legacy sale is only reachable via /history."
  artifacts:
    - path: "app/templates/partials/history_rows.html"
      issue: "product code inlined into «Товар» cell (line 29); no «Код» column, no «Действие»/«Вернуть» link, no #return-slot"
    - path: "app/templates/pages/history.html"
      issue: "<thead> has 8 columns (Когда/Тип/Товар/Кол-во/Цена/Себестоимость/Причина/Кто) — missing «Код» and «Действие» <th>"
  missing:
    - "Add a «Код» <td> ({{ r.product.code }}) to history_rows.html and matching <th> in history.html"
    - "Add a «Действие» <td> with the same «Вернуть» hx-get=\"/returns?sale_id=...&product_id=...&origin_op_id=...\" link (conditional on r.op.type == 'sale'), mirroring purchase_history.html/recent_sales.html"
    - "Add a <div id=\"return-slot\"></div> to history.html, respecting the existing oob/#history-tbody swap boundaries noted in history_rows.html's CR-01 comments"
  debug_session: .planning/debug/history-return-button-and-code-column.md
