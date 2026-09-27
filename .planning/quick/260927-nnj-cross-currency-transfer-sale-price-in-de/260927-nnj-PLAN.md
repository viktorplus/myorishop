---
quick_id: 260927-nnj
phase: quick-260927-nnj
plan: 01
type: execute
mode: quick
wave: 1
depends_on: []
files_modified:
  - tests/test_transfers.py
  - tests/test_mobile_transfers.py
  - app/services/transfers.py
  - app/routes/transfers.py
  - app/routes/mobile_transfers.py
  - app/templates/partials/transfer_price_fields.html
  - app/templates/partials/transfer_batch_wrap.html
  - app/templates/partials/transfer_form.html
  - app/templates/mobile_partials/transfers_step_dest.html
  - app/__init__.py
autonomous: true
requirements: [CUR-02]

must_haves:
  truths:
    - "D-03: a cross-currency transfer (source RUB batch price_cents=1500 -> UAH warehouse) with an empty «Цена продажи в валюте склада назначения» creates the destination batch with price_cents NULL, and /sales/batch-pick for that batch then fills the card's UAH price (sale_uah_cents=130000 -> 1300,00)"
    - "D-03/D-04: a typed sale price 450,50 lands only in the destination batch (price_cents=45050); the source batch keeps 1500 and all nine product-card price columns are unchanged"
    - "D-01/D-02: choosing a UAH destination (desktop GET /transfers/dest-pick, mobile GET /m/transfers/step/dest-prices) shows the sale price field and pre-fills EMPTY cost/sale with 717,00 / 1249,50 (card RUB 143400/249900 / 2), marked data-autofilled, each with «Цена пересчитана из рублёвой (÷2) — уточните.»; a card UAH price (sale_uah_cents=130000) is suggested as 1300,00 with no hint; an operator-typed value is never replaced"
    - "D-01: cross-currency cost stays REQUIRED — COST_REQUIRED_ERROR and every existing CUR-02 test are unchanged"
    - "D-05: a same-currency transfer shows no sale price field, inherits source.price_cents, ignores a posted sale_price, and every pre-existing test in tests/test_transfers.py and tests/test_mobile_transfers.py passes unmodified"
    - "A 422 re-render of a cross-currency transfer keeps the typed cost and sale price and the autofilled marks; an empty sale price is NOT re-suggested on a POST re-render, so an operator who clears it gets NULL"
    - "No new conversion code: suggestions come only from receipts.lookup_prefill(..., currency=) and core.converted_price_hint; no migration"
  artifacts:
    - path: "app/services/transfers.py"
      provides: "register_transfer(sale_price_raw=...) and read-only transfer_price_fields(...)"
      contains: "def transfer_price_fields"
    - path: "app/templates/partials/transfer_price_fields.html"
      provides: "Single source of the cost + sale-price fields for desktop, mobile and both fragment routes"
      contains: "id=\"transfer-price-fields\""
    - path: "app/routes/transfers.py"
      provides: "GET /transfers/dest-pick fragment; POST echoes price_fields"
      contains: "/transfers/dest-pick"
    - path: "app/routes/mobile_transfers.py"
      provides: "GET /m/transfers/step/dest-prices fragment; POST echoes price_fields"
      contains: "/m/transfers/step/dest-prices"
    - path: "app/__init__.py"
      provides: "Version bump"
      contains: "1.140"
  key_links:
    - from: "app/services/transfers.py::register_transfer"
      to: "app/services/catalog.py::parse_optional_cents"
      via: "cross-currency branch parses the destination sale price (empty -> None)"
      pattern: "parse_optional_cents\\(sale_price_raw"
    - from: "app/services/transfers.py::transfer_price_fields"
      to: "app/services/receipts.py::lookup_prefill"
      via: "suggestions in the destination warehouse's currency"
      pattern: "lookup_prefill\\(session, .*currency="
    - from: "app/templates/partials/transfer_batch_wrap.html select#dest_warehouse_id"
      to: "GET /transfers/dest-pick"
      via: "hx-get on change, hx-target #transfer-price-fields"
      pattern: "hx-get=\"/transfers/dest-pick\""
    - from: "app/templates/mobile_partials/transfers_step_dest.html dest radios"
      to: "GET /m/transfers/step/dest-prices"
      via: "hx-get on change, hx-target #transfer-price-fields"
      pattern: "hx-get=\"/m/transfers/step/dest-prices\""
---

<objective>
A transfer into a warehouse of another currency must not copy the source
batch's sale price (`app/services/transfers.py:192`, `price_cents=source.price_cents`)
into the destination batch. Cross-currency transfers get an optional field
«Цена продажи в валюте склада назначения»; empty -> destination `price_cents`
NULL (sales fall back to the card price of the destination currency, already
shipped by 260927-k1m), typed -> that value on the destination batch only. Both
empty price inputs (cost, sale) get a suggestion in the destination currency via
the k1m helpers. Same-currency transfers stay as today.

Purpose: closes k1m review item IN-05 / SUMMARY "Not scheduled" Open Q2 — the last
path where stored money crosses currencies.
Output: tests first (red), service + desktop, then mobile, version 1.140, one code commit.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@.planning/quick/260927-k1m-per-currency-product-card-prices-rub-uah/260927-k1m-SUMMARY.md
@app/services/transfers.py
@app/routes/transfers.py
@app/routes/mobile_transfers.py
@app/templates/partials/transfer_batch_wrap.html
@app/templates/partials/transfer_form.html
@app/templates/mobile_partials/transfers_step_dest.html
@app/templates/partials/receipt_price_inputs.html

## Locked decisions (orchestrator decisions 1-5, numbered here D-01..D-05)
- D-01: cross-currency only — desktop + mobile forms add the optional field «Цена продажи в валюте склада назначения», next to the cost field; cost stays REQUIRED for cross-currency (COST_REQUIRED_ERROR unchanged).
- D-02: when currencies differ, suggest into both EMPTY fields: card price in the destination currency, else RUB card/catalog price converted (UAH /2, EUR /100, half-up) with the «пересчитана» hint. Reuse k1m helpers only; a suggestion is only an input value.
- D-03: empty sale price on a cross-currency transfer -> destination `price_cents` NULL; a typed value goes into the destination batch only.
- D-04: a transfer never writes the product card.
- D-05: same-currency transfers unchanged (price inherited, cost optional, no new field shown). No migration.

## Staleness check (plan time, HEAD b422566, version 1.139)
- k1m SUMMARY cites `transfers.py:189`; the line is now 192, same code (`price_cents=source.price_cents`). Still true.
- k1m REVIEW IN-05 says the inherited `cost_cents` also crosses currencies. STALE: lines 136-143 already require a cost for cross-currency (CUR-02). Only `price_cents` crosses.
- `stocked_product`'s fixture batch has `price_cents` = None (conftest builds `Batch(quantity=0)`), despite the `_source_batch` docstrings saying 1500. Every new test MUST set `source.price_cents = 1500` and commit, or the NULL assertions pass vacuously before the fix.
- ruff baseline on the touched .py files: exactly one finding, `app\routes\transfers.py:64:101: E501` (pre-existing).

## Reused mechanisms (do not add second ones)
- `app.services.receipts.lookup_prefill(session, code, currency=...)` -> `{"prices": {"cost", "sale"}, "converted": [...]}`: own-currency card price, else RUB card converted, else (non-RUB) RUB catalog converted. This IS the D-02 rule.
- `app.core.converted_price_hint(currency)` -> «Цена пересчитана из рублёвой (÷2) — уточните.»; `app.core.format_cents`.
- `app.services.batches.warehouse_currency(session, id)`.
- `app.services.catalog.parse_optional_cents(raw, errors, field)` — empty -> None, garbage/negative -> PRICE_ERROR.
- Autofill marker idiom from `receipt_price_inputs.html:18` (`data-autofilled="true" oninput="this.removeAttribute('data-autofilled')"`) and the form-level `hx-vals='js:{...}'` flag post from `receipt_form.html:28-32` (k1m CR-02).

## Assumptions (reversible; restate in SUMMARY)
- Assumption A1: suggestions for a RUB destination (UAH/EUR -> RUB transfer) are the RUB card price only, no catalog fallback — that is `lookup_prefill`'s unchanged RUB branch (k1m A1).
- Assumption A2: suggestions are made only when the destination changes (the two new GET fragment routes, `suggest=True`). A POST re-render (422/oversell/exception) echoes the posted values and autofilled marks and never fills an empty field, so a deliberately cleared sale price stays empty -> NULL.
- Assumption A3: switching to a same-currency destination hides the sale field (its value is dropped) and clears an AUTOFILLED cost; a typed cost is kept (same rule as the k1m receipt warehouse change).
- Assumption A4: "byte-identical" (D-05) means same stored data and same visible fields. The cost field markup is unchanged but moves into the shared partial inside `<div id="transfer-price-fields">`, and the destination control gains hx attributes.
- Assumption A5: a `sale_price` posted on a same-currency transfer is ignored (the field is never rendered there).
- Assumption A6: sale-price validation runs after the cost rule inside the cross-currency branch (single early-return error, the service's existing style): garbage or negative -> `{"sale_price": PRICE_ERROR}`, zero writes.
- Assumption A7 (accepted limitation): the oversell «Переместить всё равно» button sits outside the form in the DOM, so it does not inherit the form's autofilled flags; only a 422 AFTER a confirm loses the marks. No in-flight race guard on the destination-change fragment (a `change` event, not live typing).
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED — failing tests for service, desktop and mobile (D-01..D-05)</name>
  <files>tests/test_transfers.py, tests/test_mobile_transfers.py</files>
  <behavior>
    Fixture set-up for every new test: `stocked_product.cost_cents = 143400`, `stocked_product.sale_cents = 249900` (RUB card only), source = the fixture batch with `price_cents = 1500`, `cost_cents = 400`, committed; UAH destination = a new `Warehouse(name="Запорожье", currency="UAH")` via a new `_uah_warehouse(session)` helper next to the existing `_eur_warehouse` in each file; same-currency destination = existing `_second_warehouse`.
    Service (tests/test_transfers.py; import `transfer_price_fields`, `PRICE_ERROR` from `app.services.catalog`, `converted_price_hint` INSIDE each new test so collection of the old tests never breaks):
    - cross UAH, cost_raw="300", no sale_price_raw -> errors {}, dest.price_cents is None, source.price_cents == 1500 (D-03).
    - cross UAH, cost_raw="300", sale_price_raw="450,50" -> dest.price_cents == 45050; source 1500; snapshot of the nine card columns (`cost_cents, sale_cents, min_sale_cents` + `_uah_` + `_eur_` variants) identical before/after (D-03, D-04).
    - cross UAH, sale_price_raw "abc" and separately "-5" -> (None, {"sale_price": PRICE_ERROR}), zero `transfer` operations.
    - same currency, sale_price_raw="999" -> dest.price_cents == 1500 (D-05, A5).
    - transfer_price_fields(suggest=True, UAH dest, empty inputs) -> cross_currency True, cost "717,00", sale_price "1249,50", cost_autofilled and sale_price_autofilled True, both hints == converted_price_hint("UAH").
    - with `sale_uah_cents = 130000` -> sale_price "1300,00", sale_price_hint "" (cost still converted with hint).
    - suggest=True, cost="800" (no flag) kept "800" / not autofilled; sale_price="5,00" + sale_price_autofilled="true" replaced by "1249,50".
    - suggest=True, RUB dest, cost="717,00" + cost_autofilled="true" -> cross_currency False, cost "", sale_price "" (A3).
    - suggest=False, UAH dest, empty inputs -> cost "" and sale_price "" (A2).
    Desktop routes (tests/test_transfers.py, `client` fixture):
    - GET /transfers/dest-pick with code, batch_id, dest_warehouse_id=UAH -> 200, contains `id="transfer-price-fields"`, `name="sale_price"`, `value="717,00"`, `value="1249,50"`, `data-autofilled="true"`, "пересчитана".
    - same with the RUB second warehouse -> 200, `id="cost"` present, `name="sale_price"` and "пересчитана" absent.
    - GET /transfers/batch-pick (batch picked, no dest yet) -> contains `hx-get="/transfers/dest-pick"`, no `name="sale_price"`; GET /transfers contains `sale_price_autofilled` (form-level hx-vals).
    - POST /transfers cross UAH, cost "300", no sale_price -> 200 «Перемещение сохранено»; dest batch (open_batches(session, product.id, uah.id)[0]) price_cents None; then set `sale_uah_cents = 130000`, commit, GET /sales/batch-pick params {"row": "", "batch_id": dest.id, "code": code} -> `value="1300,00"` (real sale path, D-03).
    - POST /transfers cross UAH with sale_price "450,50" -> dest price_cents 45050.
    - POST /transfers cross UAH, qty "abc", cost "717,00", cost_autofilled "true", sale_price "450,50" -> 422, `name="sale_price"`, `value="450,50"`, `value="717,00"`, `data-autofilled="true"`, "пересчитана".
    - POST /transfers same-currency, qty "abc" -> 422, `id="cost"` present, `name="sale_price"` absent (guard; may already pass before the fix — say so in SUMMARY).
    Mobile (tests/test_mobile_transfers.py, `mobile_client_factory(mobile_transfers.router)`):
    - GET /m/transfers/step/dest-prices UAH -> same assertions as desktop dest-pick; RUB -> no sale field.
    - GET /m/transfers/step/batch-pick -> contains `hx-get="/m/transfers/step/dest-prices"` and `sale_price_autofilled`, no `name="sale_price"`.
    - POST /m/transfers cross UAH cost "300", no sale_price -> 200, dest price_cents None; with sale_price "450,50" -> 45050.
    - POST /m/transfers cross UAH qty "abc", cost "300", sale_price "450,50" -> 422, `name="sale_price"`, `value="450,50"`, `value="300"`, UAH radio `checked`.
  </behavior>
  <action>Write the tests listed in behavior, appended in the style of the existing CUR-02 blocks (tests/test_transfers.py:402-470, tests/test_mobile_transfers.py:298-385). Do not edit or delete any existing test. Keep new imports inside the new test functions (the files' own idiom at test_transfers.py:412-415) so a missing symbol fails only the new tests. Run the two files and confirm: zero collection errors, every pre-existing test passes, every new test fails for the expected reason (TypeError on `sale_price_raw`, ImportError of `transfer_price_fields`, 404 on the new routes, or the NULL/field assertions) except the one named guard. Record the exact "N failed, M passed" line for the SUMMARY. Do not commit.</action>
  <verify>
    <automated>uv run pytest tests/test_transfers.py tests/test_mobile_transfers.py -q -p no:cacheprovider</automated>
  </verify>
  <done>The run reports 0 errors, all pre-existing tests passed, and only the new tests failed (the same-currency 422 guard may pass). The failure count and reasons are recorded.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN — service rule, shared price-fields partial, desktop wiring (D-01..D-05)</name>
  <files>app/services/transfers.py, app/templates/partials/transfer_price_fields.html, app/templates/partials/transfer_batch_wrap.html, app/templates/partials/transfer_form.html, app/routes/transfers.py</files>
  <behavior>
    - Every service and desktop test from Task 1 passes; the mobile ones still fail.
  </behavior>
  <action>
Service (app/services/transfers.py):
- Add a keyword arg `sale_price_raw: str = ""` to `register_transfer`, right after `cost_raw`. In the cross-currency branch (lines 137-143), after the cost parse, parse the sale price with `parse_optional_cents(sale_price_raw, sale_errors, "sale_price")` into a fresh dict. If that dict is non-empty, return `(None, sale_errors)` before any write (A6). Otherwise the parsed value, possibly None, becomes `price_cents` (D-03).
- In the same-currency branch, `price_cents = source.price_cents`, and `sale_price_raw` is ignored (D-05, A5).
- Build the dest `Batch` with `price_cents=price_cents`. Never touch the product's price attributes (D-04).
- Update the module docstring (lines 3-8), the CUR-02 comment (118-121) and the D-05 comment (180-185) to state the new rule.

Add `transfer_price_fields(session, *, code, batch_id, dest_warehouse_id, cost="", sale_price="", cost_autofilled="", sale_price_autofilled="", suggest=False) -> dict`. It is read-only (no add/commit) and returns keys `cross_currency, cost, cost_autofilled, cost_hint, sale_price, sale_price_autofilled, sale_price_hint`, with str values and bool flags.

`cross_currency` is True only when all of these hold. It uses the same guards as `register_transfer`, so an untrusted id never raises:
- the code resolves to an active product;
- the batch id resolves to a batch of that product;
- `dest_warehouse_id` is in `active_warehouses`;
- `session.get(Warehouse, source.warehouse_id)` is not None;
- that warehouse's currency differs from the destination's.

Compare currencies exactly as line 137 does. When cross, call `lookup_prefill(session, code, currency=warehouse_currency(session, dest_warehouse_id))` for `prices` and `converted`.

Per pair (kind "cost" -> key "cost", kind "sale" -> key "sale_price"): start from the stripped posted value and `flag == "true"`.
- `sale_price` when not cross: "" / False.
- If `suggest` is set and the value is empty or autofilled: when cross and the price is not None, use `format_cents(price)` with autofilled True; otherwise "" / False.
- Hint: `converted_price_hint(dest_currency)` only when cross, autofilled, and the kind is in `converted`; else "".

Imports to add: `format_cents`, `converted_price_hint` from app.core; `warehouse_currency` from app.services.batches; `parse_optional_cents` from app.services.catalog; `lookup_prefill` from app.services.receipts. Check with `uv run python -c "import app.services.transfers, app.main"` that there is no import cycle. Write no conversion arithmetic (D-02).

New partial app/templates/partials/transfer_price_fields.html. It is the single source for desktop, mobile and both fragment routes. It reads `price_fields` (default `{}`) and `errors`.
- Root: `<div id="transfer-price-fields">`.
- Cost field: moved verbatim from transfer_batch_wrap.html:58-68, including its CUR-02 comment, label, muted text and `errors.cost`, with these changes:
  - value from `price_fields.cost`;
  - when `price_fields.cost_autofilled`, the marker attributes from receipt_price_inputs.html:18;
  - `<p class="muted">` with `price_fields.cost_hint` when set.
- Then, only if `price_fields.cross_currency`, the sale field (D-01), mirroring the cost field:
  - label for `sale_price`: «Цена продажи в валюте склада назначения»;
  - input `type="text" id="sale_price" name="sale_price" inputmode="decimal" placeholder="0,00"`, value from `price_fields.sale_price`;
  - the same autofilled marker and hint;
  - muted text «Можно оставить пустым — при продаже подставится цена из карточки товара в валюте склада назначения.»;
  - `errors.sale_price`.
- Guard every error access with `errors is defined and`. No `tojson` in this file.

transfer_batch_wrap.html:
- Replace the cost block (58-68) with an include of the new partial.
- Add to the `<select id="dest_warehouse_id">` (line 33): `hx-get="/transfers/dest-pick" hx-trigger="change" hx-include="closest form" hx-target="#transfer-price-fields" hx-swap="outerHTML"`.
- Update the header comment.

transfer_form.html:
- Delete `cost_value = form.cost or ''` from the with-block (orphaned).
- Add to the `<form id="transfer-form">` the single-quoted attribute `hx-vals='js:{cost_autofilled: document.getElementById("cost") ? document.getElementById("cost").dataset.autofilled || "" : "", sale_price_autofilled: document.getElementById("sale_price") ? document.getElementById("sale_price").dataset.autofilled || "" : ""}'`.
- Add a comment citing k1m CR-02: the flags reach the POST, and through htmx attribute inheritance (not disabled; base.html htmx-config sets only responseHandling) they also reach the select's dest-pick GET.

app/routes/transfers.py:
- Import `transfer_price_fields`.
- Add GET `/transfers/dest-pick` after `/transfers/batch-pick`, a literal path per the module's route-order comment. Its query params are code, batch_id, dest_warehouse_id, cost, sale_price, cost_autofilled and sale_price_autofilled, all `str = ""`. It renders `partials/transfer_price_fields.html` with `{"price_fields": transfer_price_fields(..., suggest=True), "errors": {}}`.
- In POST `/transfers`:
  - add `sale_price`, `cost_autofilled` and `sale_price_autofilled` as `Form("")`;
  - pass `sale_price_raw=sale_price`;
  - compute `price_fields` once before the `try`, with suggest=False;
  - add `"price_fields": price_fields` to the exception, oversell and errors contexts;
  - remove the now-unread `"cost": cost` key from `form_echo`, and do not add sale_price to it.
  </action>
  <verify>
    <automated>uv run pytest tests/test_transfers.py -q -p no:cacheprovider</automated>
  </verify>
  <done>tests/test_transfers.py is fully green: pre-existing and new tests pass. `grep -hv '^\s*#' app/services/transfers.py | grep -cE 'rub_suggestion|_RUB_DIVISOR|Decimal|product\.(cost|sale|min_sale)'` prints 0 (exit 1 counts as a pass). `uv run ruff check app/services/transfers.py app/routes/transfers.py --output-format concise` shows only the baseline E501 at transfers.py:64.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: GREEN mobile, version 1.140, full gate, single code commit</name>
  <files>app/routes/mobile_transfers.py, app/templates/mobile_partials/transfers_step_dest.html, app/__init__.py</files>
  <behavior>
    - Every Task 1 mobile test passes; both transfer test files are fully green.
  </behavior>
  <action>
app/routes/mobile_transfers.py:
- Import `transfer_price_fields`.
- `_render_dest_step` gains kwargs `sale_price`, `cost_autofilled` and `sale_price_autofilled`, all defaulting to "". It computes `price_fields = transfer_price_fields(session, code=code, batch_id=picked.id if picked else "", dest_warehouse_id=dest_warehouse_id, cost=cost, sale_price=sale_price, cost_autofilled=..., sale_price_autofilled=...)` with suggest=False, and replaces the flat `"cost": cost` context key with `"price_fields": price_fields`.
- Add GET `/m/transfers/step/dest-prices`. It takes the same seven query params as the desktop dest-pick and renders `partials/transfer_price_fields.html` with suggest=True and `errors` {}.
- POST `/m/transfers` adds `sale_price`, `cost_autofilled` and `sale_price_autofilled` as `Form("")`, passes `sale_price_raw=sale_price`, and forwards all three to the exception, oversell and errors `_render_dest_step` calls.
- Leave POST `/m/transfers/step/dest` and `transfers_step_batch_pick` unchanged. They carry no destination, so the sale field could not show there.

transfers_step_dest.html:
- Replace the cost block (lines 69-79) with an include of `partials/transfer_price_fields.html`. Keep it before the op_date field; tests/test_mobile_transfers.py:678 checks that order.
- Add to the destination radios' container `<div class="field">` (line 37): `hx-get="/m/transfers/step/dest-prices" hx-trigger="change" hx-include="closest form" hx-target="#transfer-price-fields" hx-swap="outerHTML"`.
- Add to `<form id="transfer-dest-form">` the same single-quoted `hx-vals='js:{...}'` flags attribute as the desktop form. The «Назад» button keeps its own single-quoted hx-vals unchanged.

app/__init__.py: `__version__ = "1.140"`.

Gates, in order:
1. The two transfer files.
2. The related set: `uv run pytest tests/test_receipts.py tests/test_mobile_receipts.py tests/test_sales.py tests/test_mobile_sales.py tests/test_mobile_foundation.py -q -p no:cacheprovider`.
3. `uv run ruff check app/services/transfers.py app/routes/transfers.py app/routes/mobile_transfers.py tests/test_transfers.py tests/test_mobile_transfers.py --output-format concise`. Only the baseline E501 is allowed.
4. The full suite `uv run pytest -q -p no:cacheprovider`. It takes about 14 minutes, which is over the 10-minute foreground Bash limit, so start it with `run_in_background: true`, redirect its output to a file in your scratchpad, and read the tail when it finishes. Allowed failures: any test in tests/test_sync_ui.py (lifespan lock) and tests/test_offline.py::test_login_rate_limited (timing; re-run it alone to show it passes). Anything else red must be fixed before committing.

Never start a server and never open data/myorishop.db.

Commit, once:
- Stage exactly these ten paths by explicit name: tests/test_transfers.py, tests/test_mobile_transfers.py, app/services/transfers.py, app/routes/transfers.py, app/routes/mobile_transfers.py, app/templates/partials/transfer_price_fields.html, app/templates/partials/transfer_batch_wrap.html, app/templates/partials/transfer_form.html, app/templates/mobile_partials/transfers_step_dest.html, app/__init__.py.
- Never stage AGENTS.md, input/, plan1.txt, or any PLAN/SUMMARY/STATE file.
- Write the message to a file in your scratchpad, outside the repo, and run `git commit -F <that file>`.
- Subject: `fix(260927-nnj): cross-currency transfer takes a destination sale price instead of copying the source price`. The body lists D-01..D-05 in one line each.
- Add NO attribution or Co-Authored-By trailer.

Then write the SUMMARY. Do not commit it. It must contain:
- assumptions A1-A7;
- the pasted gate outputs;
- the pending human browser check: desktop /transfers: code STK-like product with RUB card prices, pick a RUB batch, choose a UAH warehouse -> cost/sale filled with the «пересчитана» hint; type a cost; switch to a RUB warehouse -> the sale field disappears and the typed cost stays; switch back -> the sale price is re-suggested. The same on /m/transfers step 3.
  </action>
  <verify>
    <automated>uv run pytest tests/test_transfers.py tests/test_mobile_transfers.py -q -p no:cacheprovider</automated>
  </verify>
  <done>
- Both transfer files are green, and the related set is green.
- ruff reports only the baseline.
- The full suite has no failures outside the allowed set, with the tail pasted verbatim.
- `git log -1 --format=%B` shows no trailer.
- `git show --stat HEAD` lists exactly the ten paths.
- `git show HEAD:app/__init__.py` contains 1.140.
- No server was started.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| browser -> GET /transfers/dest-pick, GET /m/transfers/step/dest-prices | untrusted code, batch_id, dest_warehouse_id, cost, sale_price, flag query params |
| browser -> POST /transfers, POST /m/transfers | untrusted sale_price text and autofilled flags |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-nnj-01 | Tampering | transfer_price_fields ids | mitigate | same guards as register_transfer: active product by code, batch ownership (`source.product_id == product.id`), dest in `active_warehouses`, source warehouse resolvable; any miss -> cross_currency False, never an exception |
| T-nnj-02 | Tampering | register_transfer sale_price_raw | mitigate | `parse_optional_cents`: garbage/negative -> PRICE_ERROR, zero writes; value lands only on the new dest Batch, never on Product (D-04) |
| T-nnj-03 | Information disclosure / XSS | transfer_price_fields.html echo | mitigate | values rendered through Jinja autoescape only, never `|safe`; flags compared to "true", never echoed raw; no `tojson` added (single-quote rule untouched) |
| T-nnj-04 | Information disclosure | dest-pick card-price suggestions | accept | same data the existing /receipts/lookup already returns behind the app-wide auth_guard |
</threat_model>

<verification>
- The Task 1 red run is recorded, then Tasks 2 and 3 turn it green.
- `grep -c 'hx-get="/transfers/dest-pick"' app/templates/partials/transfer_batch_wrap.html` gives 1. `grep -c 'hx-get="/m/transfers/step/dest-prices"' app/templates/mobile_partials/transfers_step_dest.html` gives 1.
- `grep -c 'include "partials/transfer_price_fields.html"'` gives 1 in each of transfer_batch_wrap.html and transfers_step_dest.html.
- `grep -n 'price_cents=source.price_cents' app/services/transfers.py` gives no match, because the dest Batch now takes the branch-computed `price_cents`.
- `git status --short` after the commit shows only the untracked AGENTS.md, input/ and plan1.txt, plus the uncommitted SUMMARY.
</verification>

<success_criteria>
- Cross-currency transfer:
  - an empty sale price gives destination price_cents NULL, and the sale path then fills the card price of the destination currency;
  - a typed sale price lands on the destination batch only, and the card is untouched;
  - cost is still required.
- Desktop and mobile show «Цена продажи в валюте склада назначения» only for a cross-currency destination. Empty cost and sale fields are pre-filled with suggestions in the destination currency, and converted values carry the «пересчитана» hint.
- A same-currency transfer is unchanged, and all pre-existing transfer tests pass unmodified.
- Version 1.140. There is one code commit, with no trailer and only explicit paths staged. The full suite is green apart from the allowed pre-existing failures.
</success_criteria>

<output>
Create `.planning/quick/260927-nnj-cross-currency-transfer-sale-price-in-de/260927-nnj-SUMMARY.md` when done (do NOT commit it).
</output>
