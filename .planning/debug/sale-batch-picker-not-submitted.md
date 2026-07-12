---
status: diagnosed
trigger: "sale-batch-picker-not-submitted: In the sale form's inline batch picker, clicking a batch shows duplicated \"Выберите партию\" text and an unexpected extra table at the bottom, the quantity input is missing/unlabeled, and submitting the sale rejects with «Выберите партию.» even though a batch was clearly picked."
created: 2026-07-12T00:00:00Z
updated: 2026-07-12T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED (see Resolution). Investigation complete for goal=find_root_cause_only.
test: n/a
expecting: n/a
next_action: none — return ROOT CAUSE FOUND to caller.

## Symptoms

expected: Picking a batch whose remaining is smaller than another batch of the same product and requesting more than that batch holds shows a warning scoped to the picked batch's remaining (not the product total); no write happens until confirm=1, which then commits. More fundamentally, picking a batch should be recognized by the server on submit.
actual: "выберите партию написано дважды после клика на партию, внизу появляется еще одна таблица, поля количество что бы ввести 8 нет, или не подписано. при нажатии на кнопку оформить продажу - введите партию, хотя партия была выбрана" — reproduced with both a single sale line (Test 4) and a 3-line basket (Test 5); every line rejected with «Выберите партию» despite every line having a batch picked.
errors: Form validation error "Выберите партию." on submit for every line despite a batch being selected client-side.
reproduction: /sales/new -> type a product code with 2 open batches -> click a batch radio in the inline picker -> observe duplicated "Выберите партию:" text + extra table -> enter qty -> submit -> rejected with «Выберите партию.» for every line.
started: Discovered during UAT of Phase 9 (batch tracking / ledger integration), Test 4 and Test 5.

## Eliminated

- hypothesis: Server-side register_sale/non_blank_lines index-alignment logic is buggy.
  evidence: Direct TestClient calls (bypassing the browser/DOM entirely) posting a correctly-aligned single batch_id[] reproduce the CORRECT oversell warning, not a rejection. register_sale correctly resolves/validates a properly-submitted batch id every time. Server-side unit/route tests (tests/test_sales.py, test_web_sale_batch_drift_attribution_holds, test_web_sale_oversell_body_is_batch_scoped, etc.) all pass — the service layer is correct in isolation.
  timestamp: 2026-07-12T00:00:00Z

- hypothesis: Template-level duplication (Jinja rendering the picker twice server-side).
  evidence: TestClient text inspection of /sales/lookup and /sales/batch-pick responses in isolation shows exactly ONE "Выберите партию:" label and ONE `<table class="batch-picker">` per response — the SERVER-rendered HTML fragments are correct and non-duplicated on their own.
  timestamp: 2026-07-12T00:00:00Z

## Evidence

- timestamp: 2026-07-12T00:00:00Z
  checked: Server-rendered fragments via FastAPI TestClient for /sales/lookup and /sales/batch-pick (2-batch product) in isolation.
  found: Each response independently contains exactly 1 "Выберите партию:" occurrence and 1 `<table>`; the hidden `batch_id[]` input's value is set correctly per response.
  implication: The bug is not in template logic per se — it must be in how the browser/htmx APPLIES these fragments to the live DOM (client-side swap mechanics), not in what the server sends.

- timestamp: 2026-07-12T00:00:00Z
  checked: Ran the real app (uvicorn) against a seeded scratch SQLite DB with a 2-batch product ("REPRO-1": batch A qty=3, batch B qty=20), driven end-to-end with a real Chromium browser via Playwright (app/static/htmx.min.js, real DOM, no mocking).
  found: After typing the code (triggering GET /sales/lookup), `#basket-rows` structure dump shows `<tr id="row-first">` ends up with 6 `<td>` children instead of the expected 5 — a THIRD `<td colspan="5">` (containing the hidden batch_id[] input + "Выберите партию:" + `<table class="batch-picker">`) is spliced directly into row-first's own `<tr>`, sitting BETWEEN name-wrap and qty. Meanwhile the SEPARATE, intended `<tr id="batch-wrap-first">` sibling row (targeted by /sales/lookup's `hx-swap-oob="outerHTML"`) is left completely untouched — still just its original empty hidden `batch_id[]` input, no table.
  implication: /sales/lookup's OOB swap of `<tr id="batch-wrap-first" hx-swap-oob="outerHTML">` silently fails to replace the live element. Instead its content gets merged as a bogus extra table cell into row-first's own `<tr>`. This single misplacement explains all three visual symptoms at once: (1) duplicated "Выберите партию:" text is not truly duplicated content from the server, it is one correct copy misfiled inside row-first plus the untouched (empty, tableless) separate sibling row; (2) the bogus extra `<td colspan="5">` visually looks like "an extra table appearing" and, because it claims a 5-column span inside a row that already has its own 5 real columns, it pushes/misaligns the qty input so it no longer lines up under the "Кол-во" header — explaining "no quantity field / unlabeled"; (3) it sets up the exact hidden-input duplication that breaks submission (next finding).

- timestamp: 2026-07-12T00:00:00Z
  checked: After clicking a batch radio (the one now visible inside row-first's misplaced `<td>`), dumped every `input[name="batch_id[]"]` in DOM order with its ancestor `<tr>` id.
  found: TWO hidden `batch_id[]` inputs exist for a single sale line at submit time: (1) value="" inside `<tr id="row-first">` (the stale, misplaced copy from the /sales/lookup mis-parse — the click never touches this one), (2) value="<picked-batch-id>" inside the separate `<tr id="batch-wrap-first">` (correctly updated by GET /sales/batch-pick, whose OWN response happens to parse correctly because its FIRST top-level element IS a `<tr>`, matching the target's own type).
  implication: On form submit, Starlette/FastAPI's `Form(alias="batch_id[]")` collects BOTH values in DOM order: `["", "<picked-id>"]`. Since `code[]` has only 1 entry, `non_blank_lines`'s `zip(codes, qtys, prices, batch_ids, strict=False)` pairs index 0 of every array together — code[0] gets paired with the STALE, EMPTY batch_id[0]="" (not the real pick at index 1). `register_sale` then correctly (per its own logic) rejects the line with «Выберите партию.» because the value it received really is empty — reproduced and confirmed by actually submitting via Playwright: response HTML contains `<p class="error">Выберите партию.</p>` even though the oversell scenario (batch with qty=3, requested qty=8) should have produced a "Товара не хватает в партии" warning instead. This exact same drift, compounded once per basket line, explains why the 3-line basket (Test 5) rejects EVERY line.
  implication (mechanism, why): htmx (2.0.10) determines the wrapping context it uses to parse a response fragment from the FIRST top-level tag of the response text (documented htmx quirk: `makeFragment` special-cases responses starting with `tr`/`td`/etc. to wrap them in the matching table context). `partials/sale_lookup.html`'s response starts with a bare `<td id="name-wrap">` (the main-swap content for the code-input's own `hx-target="#name-wrap"`), so htmx wraps the ENTIRE response text (including the LATER, structurally-different `<tr id="batch-wrap-first" hx-swap-oob="outerHTML">` sibling) in a `<td>`-appropriate context. A full `<tr>` appearing later inside that context is invalid per HTML5 nesting rules, so the browser's parser folds/merges it instead of preserving it as an independent row — the `hx-swap-oob="outerHTML"` marked `<tr>` never gets recognized as a proper oob element, and its content is instead glued onto the actively-open row. The analogous (but cosmetically harmless) version of the same mechanism produces a stray empty `<tr></tr>` after /sales/batch-pick's own main-`<tr>`-swap + trailing oob `<td id="price-wrap" hx-swap-oob="true">` (a bare `<td>` following a `<tr>`-rooted context triggers the same implicit-`<tr>`-insertion HTML5 recovery rule) — harmless there only because the extracted price `<td>` still gets correctly relocated and the leftover wrapper is empty, not duplicating visible/functional content.

## Resolution

root_cause: |
  In app/templates/partials/sale_lookup.html (and, in a lesser/cosmetic form, partials/sale_batch_pick.html),
  a table-ROW-level `hx-swap-oob="outerHTML"` element (`<tr id="batch-wrap-{row}">`) is emitted as a LATER
  sibling AFTER a bare `<td>` element (`<td id="name-wrap">`) that serves as the response's "main" swap
  content. htmx 2.0.10 picks its HTML-fragment parsing context from the FIRST top-level tag of the whole
  response body; since that first tag here is `<td>`, the entire fragment - including the later `<tr
  hx-swap-oob="outerHTML">` - gets parsed in a `<td>`-appropriate (i.e. already "inside a <tr>") context. A
  nested `<tr>` is invalid there, so the browser's HTML parser folds the OOB `<tr>`'s content into the
  currently-open row instead of treating it as an independent, oob-swappable row. Concretely: an extra
  `<td colspan="5">` (the whole batch picker: hidden `batch_id[]` input + "Выберите партию:" label + the
  `<table class="batch-picker">`) gets spliced directly into the basket line's own `<tr id="row-{row}">`,
  between name-wrap and qty, while the SEPARATE, real `<tr id="batch-wrap-{row}">` sibling that the oob swap
  was supposed to update is left completely untouched (still holding its original EMPTY hidden `batch_id[]`
  input). The operator only sees/clicks the misplaced copy; picking a batch there fires GET
  /sales/batch-pick, which DOES correctly update the separate, untouched `<tr id="batch-wrap-{row}">` (its
  own response starts with `<tr>`, matching context, so it parses fine) - but that is not the copy the
  operator is looking at, and now there are TWO `batch_id[]` hidden inputs in the DOM for that one line: a
  stale EMPTY one (first in DOM order, inside row-{row}) and the correctly-updated one (second in DOM order,
  inside batch-wrap-{row}). On submit, FastAPI's `Form(alias="batch_id[]")` collects both values in DOM
  order; `non_blank_lines`'s positional zip against `codes` (one entry per basket line) pairs each code with
  the FIRST (stale, empty) batch_id, so `register_sale` correctly-per-its-own-logic rejects every line with
  «Выберите партию.» even though a batch was visibly picked. The same misplaced `<td colspan="5">` also
  explains the visual symptoms directly: duplicated "Выберите партию:" text (one real copy misfiled into the
  row, one empty/tableless copy left in the untouched sibling row) and the qty input looking
  missing/unlabeled (the bogus colspan="5" cell pushed into the middle of the row breaks the column
  alignment between the qty `<td>` and the "Кол-во" `<th>`). Confirmed directly by driving the real app (real
  htmx.min.js, real templates, real FastAPI server) with a headless Chromium browser via Playwright: DOM
  dumps show exactly this row/cell/hidden-input duplication, and an actual form submit reproduces
  `<p class="error">Выберите партию.</p>` for a line where a batch was visibly picked.
fix: (not applied — find_root_cause_only mode)
verification: (not applicable — root cause only)
files_changed: []
