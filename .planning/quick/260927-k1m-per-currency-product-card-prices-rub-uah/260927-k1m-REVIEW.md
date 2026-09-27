---
phase: quick-260927-k1m
reviewed: 2026-09-27T00:00:00Z
depth: deep
files_reviewed: 23
files_reviewed_list:
  - alembic/versions/0028_product_currency_prices.py
  - app/__init__.py
  - app/core.py
  - app/models.py
  - app/routes/mobile_receipts.py
  - app/routes/mobile_sales.py
  - app/routes/products.py
  - app/routes/receipts.py
  - app/routes/sales.py
  - app/services/batches.py
  - app/services/catalog.py
  - app/services/export.py
  - app/services/finance_reports.py
  - app/services/pricing.py
  - app/services/receipts.py
  - app/services/sales.py
  - app/templates/pages/product_form.html
  - app/templates/partials/price_history.html
  - app/templates/partials/receipt_form.html
  - app/templates/partials/receipt_lookup.html
  - app/templates/partials/receipt_price_inputs.html
  - scripts/import_inventory_receipt.py
  - tests/test_migrations.py
findings:
  critical: 2
  warning: 3
  info: 5
  total: 10
status: issues_found
---

# Quick 260927-k1m: Code Review Report

**Reviewed:** 2026-09-27
**Depth:** deep (cross-checked against `merge.py`, `sync_client.py`, `sync.py`, `transfers.py`, the mobile wizard templates, `name_input.html`, `price-cue.js`, and FastAPI 0.139.0 `_get_multidict_value`)
**Files Reviewed:** 23 (the source files in `git diff 931c057 9b497f3`, plus `tests/test_migrations.py`; the other test files were read only where they back a claim)
**Status:** issues_found

## Summary

The core model holds up. Card prices are read and written through `card_price_fields(warehouse_currency(...))` on the receipt, sale-guard, cost-freeze and valuation paths, and none of those paths converts stored money.

- **Migration 0028 is portable.** Batch `add_column` does not recreate the table on SQLite. The downgrade uses plain `drop_column`, the partial index is preserved, and the round-trip test covers it.
- **Sync is safe for 0027 peers.**
  - The server's `_upsert_reference` is insert-only for existing UUIDs, so a 0027 push cannot null UAH/EUR prices.
  - An ahead client gets a 409 and never pulls from a behind server (`sync_client.py:387-397`).
  - `_reference_row` drops unknown wire keys.
- **Jinja is clean.** There is no `| tojson` in the diff. The `hx-on:change` attribute is double-quoted and contains only single-quoted JS literals, with no interpolated data. All new `value="{{ ... }}"` sites are autoescaped.
- **Rounding** is `Decimal` half-up, as required.

Two defects break stated requirements:

1. **CR-01:** the web product form cannot clear a UAH/EUR price at all. This is proven by an executed request.
2. **CR-02:** the "never write RUB suggestions into a UAH receipt" protection is lost on any 422 re-render of the desktop receipt form. That path reproduces the original incident.

## Fix Status (2026-09-27, gsd-code-fixer, selected findings only)

| Finding | Status | Commit | Note |
|---------|--------|--------|------|
| CR-01 | fixed | `e6aa06c` | Hidden `currency_prices_posted` marker on the product form; with it an empty ₴/€ field clears the price, without it empty = unchanged. Route tests (TestClient POST) for both. |
| CR-02 | fixed: requires human (browser) verification | `cad4135` | Form `hx-vals='js:…'` posts the live `data-autofilled` state of name/cost/sale; route echoes it; 422 re-render restores the marks. Route test replays the review scenario. The `js:` evaluation itself runs only in a browser — not exercised here. |
| WR-01 | fixed | `9b40a20` | «Цена пересчитана из рублёвой (÷2) — уточните.» under each converted receipt price (desktop lookup, mobile step 3); sale hint gets the same wording plus the sale-only scope (desktop lookup / batch pick, mobile qty-price). |
| WR-02 | not in scope (left as is) | — | |
| WR-03 | fixed | `66611aa` | Docstring + `downgrade()` comment: DATA-LOSSY, back up first. No behaviour change. |
| IN-01 | not in scope (left as is) | — | |
| IN-02 | fixed | `57d44d6` | Mobile step/batch: posted (typed) prices win over the fresh suggestion. |
| IN-03 | not needed, left as is | — | After CR-01 every render of `product_form.html` with a `product` passes either `form=None` or the full 422 echo carrying all six keys (None when not submitted), so the lenient-`Undefined` path still never meets a stored product. |
| IN-04 | not in scope (left as is) | — | |
| IN-05 | not in scope (left as is) | — | |

Verification: targeted suites green (`tests/test_catalog.py` 85 passed; `tests/test_core.py tests/test_receipts.py tests/test_mobile_receipts.py tests/test_sales.py tests/test_mobile_sales.py` 318 passed; `tests/test_mobile_receipts.py tests/test_mobile_foundation.py` 37 passed after IN-02). The full suite (`uv run pytest -q -p no:cacheprovider`) was started but stopped by Claude Code at ~26% (all dots, no failures) because the system ran low on memory — **full-suite gate not completed, needs a re-run.**

## Critical Issues

### CR-01: A UAH/EUR price can never be cleared from the product edit form. FastAPI turns a posted `""` into `None`, which means "not submitted"

**File:** `app/routes/products.py:316-321` (with `app/services/catalog.py:259-266`)

**Issue:** The update route declares the six new fields as `str | None = Form(None)`. FastAPI 0.139.0 `_get_multidict_value` (`.venv/Lib/site-packages/fastapi/dependencies/utils.py:765-777`) replaces an **empty-string form value with the field default**. So an operator who empties «ДЦ — закупочная цена, ₴» posts `cost_uah=""`, the route receives `None`, and `update_product` keeps the stored value (`getattr(product, field) if raw is None`). The save then returns 303 as if it succeeded. The RUB fields are declared `Form("")` and clear correctly, so the behaviour is inconsistent within one form.

This contradicts the `update_product` docstring («"" clears that one field»). The only test for clearing (`test_update_product_empty_currency_price_clears_only_that_field`) calls the service directly, so it never exercises this path.

Reproduced (executed, scratch test outside the repo, using `_web_form()` from `tests/test_catalog.py`). The product was first saved with `cost_uah=717`, `min_sale_uah=1000`. It was then posted again with `cost=""`, `cost_uah=""` and `min_sale_uah=""`:
```
STATUS 303
AFTER CLEAR cost_cents= None cost_uah_cents= 71700 min_sale_uah_cents= 100000
```

**Money impact:** a wrong UAH/EUR price can be overwritten but never removed. A wrong price can come from an accidentally saved RUB/2 guess, or from a cross-currency value such as the one in CR-02.
- `cost_*_cents` stays as the sale cost-freeze fallback (`sales.py:334-338`). It is then frozen into `operations.unit_cost_cents`, an append-only column, so every later profit figure is wrong.
- `min_sale_*_cents` keeps raising below-minimum warnings, and nothing can turn it off.
- The 422 echo (`products.py:363-370`) also re-shows the stored value, so the page hides the fact that the clear was dropped.

**Fix:** decide "submitted" from the presence of the key, not from its value. The simplest version that keeps the old-cached-page protection is a presence marker in the template:
```html
{# product_form.html, inside the <form> #}
<input type="hidden" name="currency_prices_posted" value="1">
```
```python
# products.py product_update
cost_uah: str = Form(""), ...,  # same shape as the RUB fields
currency_prices_posted: str = Form(""),
...
posted = currency_prices_posted == "1"
extra = dict(
    cost_uah_raw=cost_uah if posted else None,
    # ... same for the other five
)
```
Add a web-level test: POST with `cost_uah=""` must leave `cost_uah_cents is None`. The route must also still accept a POST without the marker and leave the prices unchanged.

### CR-02: On any 422 re-render of the desktop receipt form, RUB suggestions lose their "autofilled" mark. A later switch to a UAH warehouse keeps the RUB values and saves them into the UAH card and batch

**File:** `app/templates/partials/receipt_form.html:92-98`, `app/routes/receipts.py:272-282` (echo), `app/templates/partials/receipt_price_inputs.html:16`

**Issue:** The warehouse-change protection works only while the inputs carry `data-autofilled="true"`. That attribute is emitted only by the `/receipts/lookup` OOB fragment (`receipt_lookup.html:21`). The 422 path re-renders the whole form from `form_echo`, and the static `receipt_price_inputs.html` includes never pass `autofilled`, so an echoed suggestion looks exactly like a typed value. The echoed `name` is also rendered with `autofilled = False` (`receipt_form.html:45`). As a result the `rewarehouse` lookup answers 204 (`receipts.py:135-136`) and nothing is re-suggested.

Concrete sequence (the same shape as the 42499 incident):
1. The default warehouse is RUB. The operator types `42499`, and the lookup fills 1434,00 / 2499,00 (autofilled).
2. The operator forgets the quantity and presses «Сохранить приход». The response is 422 and the form is re-rendered with cost=1434,00 and sale=2499,00, with no `data-autofilled`.
3. The operator notices the wrong warehouse and switches to «Запорожье» (UAH). The handler treats both prices as operator-typed. It keeps the values and only drops the cue. The lookup returns 204 because `name` is non-empty.
4. The operator enters the quantity and saves. `register_receipt` writes `cost_uah_cents=143400` and `sale_uah_cents=249900`, and the new batch gets `price_cents=249900` in a UAH warehouse. The UAH card is now double the intended value, and the cross-currency write this task exists to prevent has happened.

**Fix:** carry the autofilled provenance through the POST so the re-render can restore it. For example, emit a hidden flag next to each autofilled input and drop it on the first keystroke:
```html
{# receipt_price_inputs.html #}
{% if autofilled %}<input type="hidden" name="{{ field }}_autofilled" value="1" id="{{ field }}-autofilled">{% endif %}
<input ... {% if autofilled %}data-autofilled="true"
       oninput="this.removeAttribute('data-autofilled'); var h=document.getElementById('{{ field }}-autofilled'); if (h) h.remove();"{% endif %}>
```
Then echo `cost_autofilled`/`sale_autofilled` (and a `name_autofilled` equivalent) in `form_echo`, and pass `autofilled = form.cost_autofilled == "1"` in the two static includes and the name include. Add a route test: a 422 re-render of a lookup-filled price must still carry `data-autofilled="true"`.

## Warnings

### WR-01: Converted RUB/2 and RUB/100 suggestions are labelled as card prices, so the operator cannot tell a guess from a verified UAH price

**File:** `app/routes/receipts.py:24,164` (`CARD_FILL_HINT`), `app/services/sales.py:58-61` (`SALE_CARD_FILL_HINT`), used at `app/routes/sales.py:242,342` and `app/routes/mobile_sales.py:405-408`

**Issue:** When `card_price_suggestion` / `lookup_prefill` falls back to `rub_suggestion`, the UI still says «Данные подставлены из карточки товара — новые цены обновят карточку» (receipt) or «Цена подставлена из карточки товара…» (sale). In a UAH receipt the value is RUB/2, not a card price. The locked decision relies on the operator correcting converted prices («мы будем менять цену там где будет уточнение»). With this wording the operator has no signal that a correction is needed, and saving stores the guess permanently in `*_uah_cents` and in the batch.

**Fix:** have `lookup_prefill` and the sale fill return a per-field `converted: bool`, which is true whenever `rub_suggestion` produced the value. Then show a distinct hint, for example «Цена пересчитана из рублёвой (÷2) — проверьте перед сохранением.». The desktop receipt path can reuse `hint`. The sale paths need a third hint constant.

### WR-02: 0027 clients keep writing UAH amounts into the RUB card fields, and their new products land on the server that way

**File:** `app/services/merge.py:539-566` (`_upsert_reference`), `app/services/sync.py:238-302` (`push_schema_ok` accepts behind clients)

**Issue:**
- **Card prices.** A behind (0027) desktop client that holds the synced «Запорожье» warehouse still runs the old `register_receipt`. A UAH receipt of a code the client does not know yet creates a local card with UAH amounts in `cost_cents`/`sale_cents`. When the client pushes, `_upsert_reference` inserts that product verbatim. The server's RUB set then holds UAH values, and the UAH set stays NULL.
- **Cost freeze.** The same client's sale path freezes the RUB `product.cost_cents` into `unit_cost_cents` for UAH baskets. Those ledger rows are append-only once merged.

The merge layer is correct as written, since it projects to known columns. The gap is operational: this task does not stop the incident on old clients, and nothing in SUMMARY states that dependency.

**Fix:** at minimum, record in the SUMMARY/operator note that client release 1.139 must ship together with the s1 deploy, and that any desktop client holding a non-RUB warehouse must be upgraded before its next receipt. Optionally, add a merge-time guard:
- when a push has `schema_version < "0028"` and inserts a new product whose only batches in the same push are in non-RUB warehouses, move `cost_cents`/`sale_cents` into that currency's fields;
- or reject such pushes with 409 so the client upgrades first.

### WR-03: The downgrade drops UAH/EUR prices without warning, and the revert path has no backup step

**File:** `alembic/versions/0028_product_currency_prices.py:56-61`

**Issue:** `downgrade()` drops six money columns. Every UAH/EUR card price entered after the deploy is destroyed, and some of those values also appear in `price_change` payloads, which leaves them orphaned. The docstring says the downgrade preserves the index, but it does not say that it destroys data. Given the project's backup discipline (see the s1 import procedure), a routine `alembic downgrade -1` during a rollback would silently lose operator work.

**Fix:** add a loud docstring/comment («DATA-LOSSY: take `pg_dump` / copy the .db first»). Optionally, have `downgrade()` refuse to run when any of the six columns is non-NULL unless an env override is set.

## Info

### IN-01: `lookup_prefill` still returns an unconverted RUB `"catalog"` key for non-RUB currencies

**File:** `app/services/receipts.py:388`
**Issue:** `prices["catalog"]` is `latest.consumer_cents` in RUB, even when `currency="UAH"`. No caller reads it today, because `fill_fields` is only cost/sale. A future consumer would get RUB presented as UAH.
**Fix:** either drop the key, since it is dead after Phase 18, or pass it through `rub_suggestion`.

### IN-02: The mobile receipt "Назад → Далее" bounce replaces a typed step-3 price with the converted suggestion

**File:** `app/routes/mobile_receipts.py:137-138`
**Issue:** `final_cost = resolved_cost or cost.strip()` lets a fresh lookup win over a typed value (pre-existing CR-01 logic). In a RUB warehouse this happened only when the card had a price. In a UAH/EUR warehouse there is now almost always a suggestion (card, RUB/2 or catalog/2). So an operator who typed a UAH price on step 3, went back to step 2 and returned sees their value silently replaced by RUB/2. The value is visible on step 3, so this is not a silent money write.
**Fix:** thread a `cost_typed`/`sale_typed` flag through the wizard, or only let the lookup win when `code` changed.

### IN-03: `product_form.html` relies on lenient `Undefined` for the new fields when `form` lacks the keys

**File:** `app/templates/pages/product_form.html:962-1005` (the six `{% if form and form.cost_uah is not none %}` tests)
**Issue:** `/products/new?code=X` passes `form={"code": X}`. `form.cost_uah` is then `Undefined`, and `Undefined is not none` is True, so the template renders an empty value. This is harmless only because `product` is None on that path. After CR-01 is fixed ("" then clears), any future render path that passes a partial `form` together with a `product` would clear stored prices on the next save.
**Fix:** test `form.get('cost_uah') is not none`, or have every `form` dict carry all six keys.

### IN-04: The below-minimum warnings and the UAH/EUR minimums have no currency label

**File:** `app/templates/partials/sale_price_warning.html:8`, `app/templates/mobile_partials/sale_warning.html:12`, `app/services/export.py:98-120`
**Issue:** `e.minimum` is now the basket-currency minimum, but it is rendered without a symbol. `min_sale_uah/eur` also do not appear in the products CSV (Assumption A2). This makes it hard to audit a wrong UAH floor, which matters together with CR-01.
**Fix:** render `currency_symbol(basket_currency)` in the warning, and consider exporting the min-sale columns.

### IN-05: A cross-currency transfer still copies RUB batch prices into a UAH batch (pre-existing, acknowledged as unscheduled)

**File:** `app/services/transfers.py:186-193`
**Issue:** `dest.price_cents = source.price_cents` (and the inherited `cost_cents`) moves RUB money into a UAH batch. Because `register_sale` freezes `batch.cost_cents` first, that RUB cost reaches `unit_cost_cents` of UAH sales. This is the one remaining path where stored money crosses currencies. SUMMARY names it as unscheduled. It is listed here so it is not lost.
**Fix:** schedule it separately. When source and destination currencies differ, require the operator to enter the destination price and cost, or store NULL.

---

_Reviewed: 2026-09-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
