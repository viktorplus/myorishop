---
status: diagnosed
trigger: "receipt-batch-chooser-ux: In the goods-receipt form's batch chooser (top-up vs new-batch), the radio button state is ambiguous on load, the product name doesn't autofill when an existing product code is entered, and batches have no name/label field."
created: 2026-07-12T00:00:00Z
updated: 2026-07-12T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED (three separate root causes, one per symptom) — see Resolution
test: code inspection (template + route + model), cross-checked against existing test suite coverage
expecting: n/a — find_root_cause_only mode, stopping here
next_action: none — return diagnosis to caller

## Symptoms

expected: Chooser forces an explicit top-up/new choice; new-batch fields (срок/место/комментарий) hide/show on «Новая партия» selection and disabled inputs never submit on top-up.
actual: "при загрузке форм не понятно какая форма выбрана радиокнопка всего одна и непонятно к чему относится и уже выбрана. при вводе кода существующего продукта название не подставляется. партия должна иметь название при создании имя и текущая дата"
errors: None reported
reproduction: Test 1 in UAT (.planning/phases/09-batch-tracking-ledger-integration/09-UAT.md) — open the receipt form, enter the code of a product with existing open batches, pick a warehouse, observe the batch chooser radios.
started: Discovered during UAT of Phase 9 (batch tracking / ledger integration)

## Eliminated

- hypothesis: "open_batches() query is broken and always returns an empty list, so batch radios never render."
  evidence: app/services/batches.py:15-32 — query is correct (product_id + quantity>0 + optional warehouse_id filter, nullslast ordering). No evidence of a query bug; the always-checked-single-radio state is explained by `new_selected = not batches` being trivially true whenever `batches` is `[]` for the mundane reason "no code typed yet / no product resolved yet" (see Resolution for symptom 1), not a query defect.
  timestamp: 2026-07-12T00:00:00Z

- hypothesis: "/receipts/lookup fails to return the product name server-side (route or service bug)."
  evidence: app/services/receipts.py:249-276 (`lookup_prefill`) and app/routes/receipts.py:102-144 are correct and directly covered by passing tests: tests/test_receipts.py:708 `test_web_lookup_product_fills_name_and_prices` asserts the product name IS present in the 200 response body. Server-side data path works; the failure must be client-side (see Resolution for symptom 2).
  timestamp: 2026-07-12T00:00:00Z

## Evidence

- timestamp: 2026-07-12T00:00:00Z
  checked: app/templates/partials/receipt_batch_chooser.html:19,34-41
  found: "`{% set new_selected = not batches %}` and the «Новая партия» radio is the ONLY one rendered with `checked` set from that flag. When `batches == []` (any reason — no code yet, code not resolved, or a resolved product with zero open batches in the selected warehouse), the template renders exactly one radio, already checked, with no sibling to contrast it against and no fieldset/legend tying it to the choice being made."
  implication: On every fresh page load (before any code is typed) this exact empty-batches state is what renders.

- timestamp: 2026-07-12T00:00:00Z
  checked: app/routes/receipts.py:74-83 (`receipt_new_page`), 42-59 (`_chooser_context`)
  found: "`receipt_new_page` calls `_form_extras(session)` with `code=\"\"` (default). `_chooser_context` strips code to `\"\"`, so `product` stays `None`, so `batches = []` unconditionally — regardless of whether the pre-selected default warehouse actually holds batches for anything. This happens on literally every GET /receipts/new."
  implication: The ambiguous single-checked-radio state described as happening \"при загрузке форм\" (on form load) is the DEFAULT, unconditional render for the empty form, before the operator has entered anything — confirms the user's literal complaint about load-time ambiguity.

- timestamp: 2026-07-12T00:00:00Z
  checked: tests/test_receipts.py (full grep for "checked", "new_selected", "batch-chooser")
  found: "No test in the suite asserts on the `checked` attribute of the batch-chooser radios (only test_sales.py:791 checks `checked` for the unrelated sale-side single-batch auto-select). test_receipts.py:784-788 only asserts the `#batch-chooser` div id is present on the page, not its radio state."
  implication: The ambiguous-on-load state was never exercised by an automated assertion — a coverage gap that let this ship.

- timestamp: 2026-07-12T00:00:00Z
  checked: app/templates/partials/receipt_form.html:18-19 (before-swap guard), app/routes/receipts.py:116-117 (`if name.strip(): return Response(status_code=204)`)
  found: "Both the client-side `hx-on::before-swap` guard and the server-side `name.strip()` check use \"is the #name field currently non-empty\" as a proxy for \"the operator deliberately typed a name, never overwrite it\" (Pitfall 7). Neither can distinguish a deliberately-typed name from a STALE value already sitting in that field for an unrelated reason — e.g. a name auto-filled by an earlier code lookup in the same form session (nothing resets #name when the operator edits the code field again), or a value placed there by the browser's native autofill (the field has `name=\"name\" id=\"name\"` with no `autocomplete=\"off\"` — app/templates/partials/name_input.html:7)."
  implication: Once the Название field holds ANY value (autofilled from a previous lookup, or via browser autocomplete), the SAME server 204 guard and the SAME client shouldSwap=false guard permanently suppress ANY subsequent code-triggered name autofill for the rest of that form session — the operator must manually clear the field first. Matches the reported \"при вводе кода существующего продукта название не подставляется\".

- timestamp: 2026-07-12T00:00:00Z
  checked: tests/test_receipts.py:708-765 (all /receipts/lookup tests)
  found: "test_web_lookup_204_when_name_typed (line 759) only covers the case name=\"Своё\" is passed explicitly by the test — it does not exercise the realistic sequence of (1) a first lookup auto-fills the name, then (2) the operator edits the code again for a second/different product without clearing Название. No test simulates that stale-autofill-blocks-relookup sequence."
  implication: The guard's blind spot (autofilled value treated identically to a manually-typed value) is untested and is the most likely trigger for the reported non-autofill, given the server-side lookup logic itself is proven correct by the passing tests.

- timestamp: 2026-07-12T00:00:00Z
  checked: app/models.py:140-173 (`Batch` model)
  found: "The `Batch` table has NO name/label column at all — only `id, product_id, warehouse_id, expiry, price_cents, location, comment, quantity, is_legacy, created_at, updated_at`. The batch chooser radio label (app/templates/partials/receipt_batch_chooser.html:29-31) identifies a batch purely by expiry + price + quantity + optional comment/location; there is no dedicated identifying label field anywhere in the schema."
  implication: A batch cannot be given a name at creation because no such column/field exists to store it — this is a schema/feature gap, not a display-only bug.

- timestamp: 2026-07-12T00:00:00Z
  checked: app/services/receipts.py:201-213 (`register_receipt`, new-batch construction) and app/templates/partials/receipt_batch_chooser.html:47-62 (new-batch-fields block)
  found: "The new-batch creation path only collects/writes `expiry`, `price_cents` (from `sale_cents`), `location`, `comment` — no name/label input exists in the form and no name/label kwarg is passed to `Batch(...)`."
  implication: Confirms the missing-name gap spans the full stack: no DB column, no form field, no write-path parameter — nothing auto-generates \"name + creation date\" anywhere.

## Resolution

root_cause: |
  THREE independent root causes, one per reported symptom:

  1. Radio ambiguity on load (app/templates/partials/receipt_batch_chooser.html:19,34-41
     + app/routes/receipts.py:42-59,74-83): `new_selected = not batches` auto-checks the
     sole «Новая партия» radio whenever `batches` is empty — which is the UNCONDITIONAL
     state on every fresh GET /receipts/new (code is always "" before the operator types
     anything, so `_chooser_context` never even attempts a product lookup and `batches`
     is trivially `[]`). The template has no sibling contrast, no fieldset/legend tying
     the radio group to the "top-up vs new" decision, and no visual distinction between
     "genuinely nothing to top up" and "you haven't told me a product/warehouse yet" —
     so a lone pre-checked radio with no context renders on every load, exactly matching
     "радиокнопка всего одна и непонятно к чему относится и уже выбрана".

  2. Product name not autofilling (app/templates/partials/receipt_form.html:18-19,
     app/routes/receipts.py:116-117, app/templates/partials/name_input.html:7):
     the "never overwrite an operator-typed name" guard (both client `hx-on::before-swap`
     shouldSwap=false and server `if name.strip(): return 204`) uses "is #name currently
     non-empty" as its sole signal. It cannot tell a deliberately-typed name apart from a
     STALE value already in that field for an unrelated reason (a previous lookup's
     autofill left over when the operator edits the code again for a different product —
     nothing ever resets #name on a code change; or native browser autofill, since the
     field has no `autocomplete="off"`). Once #name holds any value, BOTH guards
     permanently block any further code-triggered autofill until the operator manually
     clears the field — server-side lookup logic itself is proven correct by passing
     tests (test_web_lookup_product_fills_name_and_prices), so the defect is specifically
     in this overwrite-guard's inability to distinguish "typed" from "stale/autofilled".

  3. Batches have no name field (app/models.py:140-173, app/services/receipts.py:201-213,
     app/templates/partials/receipt_batch_chooser.html:47-62): the `Batch` model has no
     name/label column, the new-batch form only collects expiry/location/comment, and
     `register_receipt` never writes any name-like value when constructing a new Batch.
     This is a genuine schema + feature gap — there is nowhere to store, and nothing that
     generates, a "name + creation date" batch label.

fix: (not applied — find_root_cause_only mode)
verification: (not applied — find_root_cause_only mode)
files_changed: []
