---
phase: quick-260927-nnj
reviewed: 2026-09-27T00:00:00Z
depth: deep
files_reviewed: 10
files_reviewed_list:
  - app/__init__.py
  - app/services/transfers.py
  - app/routes/transfers.py
  - app/routes/mobile_transfers.py
  - app/templates/partials/transfer_price_fields.html
  - app/templates/partials/transfer_batch_wrap.html
  - app/templates/partials/transfer_form.html
  - app/templates/mobile_partials/transfers_step_dest.html
  - tests/test_transfers.py
  - tests/test_mobile_transfers.py
findings:
  critical: 0
  warning: 6
  info: 5
  total: 11
status: issues_found
---

# Quick 260927-nnj: Code Review Report

**Reviewed:** 2026-09-27
**Depth:** deep (diff `b422566..d72f523`, plus the called helpers `receipts.lookup_prefill`, `core.card_price_suggestion` / `rub_suggestion` / `converted_price_hint`, `batches.warehouse_currency` / `active_warehouses`, `catalog.parse_optional_cents`, the sale-side NULL fallbacks in `routes/sales.py` / `routes/mobile_sales.py` / `services/finance_reports.py`, the oversell partials, and the sync merge path)
**Files Reviewed:** 10
**Status:** issues_found

## Summary

The core fix is correct. `register_transfer` no longer copies `source.price_cents` across currencies (`app/services/transfers.py:148-160, 204-216`). A cross-currency destination batch gets either the parsed `sale_price_raw` or NULL. The same-currency branch still inherits `source.price_cents` and ignores `sale_price_raw`. The product card is never written: there is no `Product` price attribute in the diff, and `record_operation` writes no card columns. Every downstream consumer of a NULL `Batch.price_cents` falls back to the card price in the batch's own currency (`routes/sales.py:338-350`, `routes/mobile_sales.py:401-412`, `finance_reports.py:76`), so NULL is safe to store.

The rest of the review checked these areas:

- **Ownership / id guards in the new GET routes.** `transfer_price_fields` (`services/transfers.py:283-304`) requires all of the following, the same guards as `register_transfer`: an active product by code, `source.product_id == product.id`, a destination in `active_warehouses`, and a resolvable source warehouse. Suggestions are then taken from `lookup_prefill(session, code, …)` for that same `code`. A foreign `batch_id` therefore yields `cross_currency False` and no prices. The route never returns another product's or batch's data, and the card prices it can return are the ones `/receipts/lookup` already returns behind the app-wide `auth_guard` (`services/security.py:188-200`; none of the new paths is in `PUBLIC_PATHS`).
- **Templates.** No new `| tojson`. The two new `hx-vals='js:{…}'` attributes are single-quoted and contain no Jinja interpolation. Echoed `cost` / `sale_price` go through Starlette's default autoescape; there is no `|safe`.
- **htmx requests.** Requests from the same element are queued ("last"), so two destination-change GETs cannot be applied out of order.

No finding shows a source-currency price, or a converted suggestion, being stored without an operator submit. The defects are all at the UI boundary:

- a value entered for one currency can be saved under another (WR-01, WR-05);
- the prefilled ÷2 suggestions make the "real cost required" guard and the D-03 NULL path easy to bypass without noticing (WR-02, WR-03);
- an in-flight fragment can overwrite typing (WR-04);
- batches written before 1.140 are not repaired (WR-06).

## Fix Status

Fixed 2026-09-27 on `main` after `d72f523`. Not pushed. Version stays 1.140.

| ID | Status | Commit | What was done |
|----|--------|--------|---------------|
| WR-01 | fixed | `c8ae530` | `transfer_price_fields` returns `currency` (the destination's code, "" until an active one is chosen). The cost and sale labels show its symbol («Себестоимость партии, ₴», «Цена продажи, ₴»), desktop + mobile. Typed values are still kept on a currency switch (orchestrator decision). |
| WR-02 | fixed: requires human verification | `c8ae530` | A converted cost is never the input's value. It is shown only as `cost_hint` = «Ориентир: N — пересчитана из рублёвой, укажите реальную себестоимость.», where N is `rub_suggestion(source.cost_cents, dest)` when the source warehouse is RUB and the batch has a cost, else lookup_prefill's converted card/catalog cost. A card cost in the destination currency still prefills. The sale price keeps its prefill. An untouched cost field now gets COST_REQUIRED_ERROR. |
| WR-03 | not fixed (accepted) | — | Orchestrator: a suggested sale price is stored if the operator saves, same as receipts. |
| WR-04 | fixed: requires human verification | `468dc31` | Desktop `#transfer-form` and mobile `#transfer-dest-form` snapshot cost/sale in `hx-on::before-request` for requests targeting `#transfer-price-fields`. `hx-on::before-swap` vetoes the swap if either value changed and re-fires the destination control's request (`htmx.trigger(event.detail.requestConfig.elt, 'change')`). Tests only pin the markup; the race itself needs a browser check. |
| WR-05 | fixed | `765b2e3` | Both «Переместить всё равно» buttons post `hx-vals='js:{confirm: "1", cost_autofilled: …, sale_price_autofilled: …}'`. |
| WR-06 | not applicable | — | Orchestrator: s1 has 0 batches in non-RUB warehouses. |
| IN-01 | fixed | `c8ae530` | Module docstring, the COST_REQUIRED_ERROR comment, the CUR-02 comment in `register_transfer` and the template comment now describe the guide-only cost. |
| IN-02 | fixed | `082f536` (+ WR tests in `c8ae530`, `468dc31`, `765b2e3`, `4e64dcb`) | Foreign batch, foreign code, unknown code and soft-deleted destination on both fragment routes give no sale field, price, guide or hint. The WR-01 test covers UAH→EUR with a typed value, and the WR-05 tests cover the oversell-confirm POST carrying `sale_price` (desktop + mobile). |
| IN-03 | not applicable | — | Orchestrator: no offline clients exist. |
| IN-04 | not fixed (left by orchestrator) | — | — |
| IN-05 | fixed | `4e64dcb` | The desktop POST builds `price_fields` inside the `try`, only for a 422/oversell re-render; the `except` branch rebuilds it after the rollback (the mobile pattern). |

Gates:
- `uv run pytest tests/test_transfers.py tests/test_mobile_transfers.py -q -p no:cacheprovider`: `112 passed, 1 warning in 33.87s`. Before the fix (RED) it was `14 failed, 98 passed`.
- ruff on the five .py files: only the baseline `app\routes\transfers.py:64:101: E501`.
- Full suite `uv run pytest -q -p no:cacheprovider`: `4 failed, 1917 passed, 14 skipped, 3 warnings in 560.80s (0:09:20)`. All 4 are in `tests/test_sync_ui.py`, the allowed pre-existing set.

Pending human browser checks (no server started here):
1. WR-04: on `/transfers` and `/m/transfers` step 3, pick a UAH destination and type into «Себестоимость» at once (slow network or DevTools throttling). The typed value must survive, and the sale field must still appear.
2. WR-02: pick a UAH destination for a RUB batch. The cost field must stay empty with the «Ориентир» line under it, and «Переместить» without a cost must show COST_REQUIRED_ERROR.

## Warnings

### WR-01: A typed cost or sale price survives a change of destination currency and is saved in the new currency, and the form never shows which currency is meant

**File:** `app/services/transfers.py:311-319`; `app/templates/partials/transfer_price_fields.html:14-17, 29-31`; `app/templates/partials/transfer_batch_wrap.html:40-42`; `app/templates/mobile_partials/transfers_step_dest.html:49-53`

**Issue:** On a destination change (`suggest=True`), a non-autofilled value is kept verbatim (`elif suggest and (not value or autofilled)` is false for a typed value). The server does not know which currency the value was typed for.

The labels say only «в валюте склада назначения», and neither the `<select>` options nor the radio cards show the warehouse currency. Nothing on the screen tells the operator that the meaning of the number changed. This contradicts the invariant the change claims (module docstring, lines 10-14: "stored money never crosses currencies").

Concrete scenarios, with source = RUB batch:

1. Choose «Запорожье» (UAH). Cost prefills to 717,00. The operator overwrites it with 650, meaning 650 ₴. The operator then realises the wrong warehouse was chosen and switches to a RUB warehouse. The sale field disappears and cost «650» stays (A3). On submit, the same-currency branch stores `cost_cents = 65000` as **RUB** instead of inheriting `source.cost_cents`.
2. With a EUR warehouse active: choose UAH, type sale 450 (₴), then switch to EUR. `sale_price` «450» is kept and saved as `price_cents = 45000` in a **EUR** batch, roughly 40× the intended value.

This follows the k1m "typed wins" precedent (k1m IN-02). Here, though, the currency switch is the whole point of the control, and there is no currency cue anywhere.

**Fix:** Carry the currency the values were rendered for, and treat typed values as stale when it changes. Also show the currency:

```jinja
{# transfer_price_fields.html, inside #transfer-price-fields #}
<input type="hidden" name="price_currency" value="{{ _pf.currency | default('') }}">
<label for="cost">Себестоимость партии в валюте склада назначения{% if _pf.currency %} ({{ CURRENCIES.get(_pf.currency, _pf.currency) }}){% endif %}</label>
```

```python
# transfer_price_fields(..., price_currency: str = "")
fields["currency"] = dest_currency if dest_id else ""
stale = suggest and price_currency and price_currency != fields["currency"]
...
elif suggest and (not value or autofilled or stale):
    ...
```

Optionally, `register_transfer` can also reject a POST whose `price_currency` is non-empty and differs from `warehouse_currency(dest_warehouse_id)`. That catches a stale DOM as well.

### WR-02: The prefilled ÷2 cost satisfies the CUR-02 "real destination cost required" rule with one click, and it comes from the card, not from the batch being moved

**File:** `app/services/transfers.py:41-46, 147-154, 302-319`; `app/services/receipts.py:369-372` (`card_price_suggestion(product, "cost", currency)`)

**Issue:** `COST_REQUIRED_ERROR` exists so that a cross-currency move records a cost the operator actually states ("no conversion, no FX rate", line 41-42). After this change, every destination change fills the cost with `card cost_uah_cents` or `card cost_cents / 2`, or with the catalog value divided by 2. On submit, `register_transfer` ignores `cost_autofilled`, so the guard never fires in the UI flow.

The suggestion is also built from the product card's current cost, not from `source.cost_cents`, which is the frozen cost of the physical lot being moved. With the plan's own fixture, the source batch cost is 400 kopecks while the card cost is 143400. The operator sees 717,00 ₴ with a «пересчитана — уточните» hint. One click on «Переместить» stores `cost_cents = 71700` on the destination batch, and that batch's profit in UAH reports is then based on a converted list price of an unrelated lot. The hint disappears once the value is stored.

This is D-02 as decided, so it is a design risk, not a code defect. It does, however, silently weaken a shipped guard, and the stale comment at 41-42 still claims the opposite (see IN-01).

**Fix (pick one, product decision):**

- (a) Suggest the moved lot's own cost, `rub_suggestion(source.cost_cents, dest_currency)` when the source is RUB, so the conversion at least applies to the right number.
- (b) Keep the suggestion but make `register_transfer` return `COST_REQUIRED_ERROR` when `cost_autofilled == "true"` and the kind was converted. The operator must touch the field before the value is stored.
- (c) Show the converted value as a `placeholder` rather than a `value`.

### WR-03: The autofilled sale suggestion makes D-03's "empty → NULL → live card fallback" path unreachable in normal use, and freezes a converted guess as an authoritative batch price

**File:** `app/services/transfers.py:311-319`; `app/templates/partials/transfer_price_fields.html:24-35`; `app/routes/sales.py:338-341` / `app/routes/mobile_sales.py:401-403`

**Issue:** Whenever the product has any RUB card or catalog sale price, choosing a cross-currency destination fills `sale_price` (for example 1249,50). NULL is now stored only if the operator actively clears a prefilled field. The plan's must-have #1 is exercised only by POSTs that omit `sale_price`, never through the UI flow.

When the suggestion is accepted, the ÷2 guess is written to `Batch.price_cents`. At sale time `sale_batch_pick` then fills it with `SALE_BATCH_FILL_HINT` (a batch price) instead of the `sale_converted_fill_hint` cue the NULL path would show. A UAH card price set later (`sale_uah_cents`) is never picked up for that batch.

The k1m design ("a suggestion is only an input value") permits this, but it defeats the reason D-03 chose NULL.

**Fix:** For a converted sale suggestion (`"sale" in converted`), do not autofill the value. Render it as the placeholder together with the hint, so an untouched field posts empty and stores NULL:

```python
if key == "sale_price" and kind in converted and not raw.strip():
    fields["sale_price_placeholder"] = format_cents(price); value, autofilled = "", False
```

Alternatively, have `register_transfer` store NULL when `sale_price_autofilled == "true"` and the posted value equals the converted suggestion. Needs a user decision, because D-02 asked for the value to be suggested.

### WR-04: The destination-change fragment replaces the price inputs wholesale, so typing done while the GET is in flight is lost and replaced by the suggestion

**File:** `app/templates/partials/transfer_batch_wrap.html:36-38`; `app/templates/mobile_partials/transfers_step_dest.html:43-45`; `app/templates/partials/transfer_form.html:32-33`

**Issue:** `hx-swap="outerHTML"` on `#transfer-price-fields` swaps the cost and sale inputs regardless of what was typed after the request was sent. The desktop form's `hx-on::before-swap` guard covers only `#name-wrap`, and the mobile form has no guard at all.

Scenario: on the phone (the server is on s1, so the round-trip is real), the operator taps the UAH radio, then immediately taps «Себестоимость» and types 300. The response arrives and replaces the input with `value="717,00" data-autofilled="true"`. If the operator does not re-read the field, 717,00 is stored. The plan acknowledges the missing guard (A7), but the consequence is a silent change of a money value, not a UI glitch.

**Fix:** Extend the swap guard to the price fragment on both forms. For example, snapshot the values on `htmx:beforeRequest` and veto the swap if either input changed:

```html
hx-on::before-request="if (event.detail.target && event.detail.target.id === 'transfer-price-fields') this.dataset.pf = (document.getElementById('cost')||{}).value + '|' + (document.getElementById('sale_price')||{}).value"
hx-on::before-swap="if (event.detail.target.id === 'transfer-price-fields' && this.dataset.pf !== (document.getElementById('cost')||{}).value + '|' + (document.getElementById('sale_price')||{}).value) event.detail.shouldSwap = false"
```

When the swap is vetoed, fire a new dest-pick request so the sale field still appears for a cross-currency destination.

### WR-05: The oversell «Переместить всё равно» button does not carry the autofilled flags, so a 422 on the confirm POST turns suggestions into "typed" values that then survive a currency switch (same class as k1m CR-02)

**File:** `app/templates/partials/transfer_oversell.html:11-14`; `app/templates/mobile_partials/transfers_warning.html:10-13`

**Issue:** Both confirm buttons sit outside `#transfer-form` / `#transfer-dest-form` in the DOM. `hx-vals` is resolved from DOM ancestors, not from the associated `form=`, so the confirm POST has `cost_autofilled=""` and `sale_price_autofilled=""`.

After the warning, the form stays editable. If the operator, for example, clears `qty` or picks a future date and then presses confirm, the 422 re-render echoes 717,00 / 1249,50 with no autofilled mark and no hint. A subsequent switch to another currency (EUR, or a same-currency RUB warehouse for the cost) keeps them, and they are saved in the wrong currency. This is exactly the k1m CR-02 failure, reintroduced on a narrower path. The plan accepted it as A7, but the k1m review classed the same effect as critical.

**Fix:** Give the confirm buttons the same flag expression, merged with `confirm`:

```html
hx-vals='js:{confirm: "1", cost_autofilled: document.getElementById("cost") ? document.getElementById("cost").dataset.autofilled || "" : "", sale_price_autofilled: document.getElementById("sale_price") ? document.getElementById("sale_price").dataset.autofilled || "" : ""}'
```

### WR-06: Destination batches created by cross-currency transfers before 1.140 keep the copied source price, and nothing detects or repairs them

**File:** `app/services/transfers.py:204-216` (the removed `price_cents=source.price_cents`); consumers `app/routes/sales.py:339-341`, `app/routes/mobile_sales.py:402-403`, `app/services/finance_reports.py:76`

**Issue:** The fix only changes new writes, and there is deliberately no migration (D-05). Every UAH/EUR batch created by an earlier cross-currency transfer still has a RUB number in `price_cents`. The sale forms fill that number as a trusted batch price («цена партии»), and `stock_valuation(currency="UAH")` sums it as UAH. If any such batch exists on s1, the money error this task set out to close is still live for that stock. Needs verification.

**Fix:** Run a read-only check on s1 and, if it returns rows, clear those prices (NULL → card fallback) through the batch edit form, or with a reviewed one-off script:

```sql
SELECT b.id, p.code, w.currency, b.price_cents, b.created_at
FROM batches b
JOIN warehouses w ON w.id = b.warehouse_id
JOIN products p ON p.id = b.product_id
WHERE b.price_cents IS NOT NULL
  AND EXISTS (SELECT 1 FROM operations o
              WHERE o.batch_id = b.id AND o.type = 'transfer' AND o.qty_delta > 0)
  AND EXISTS (SELECT 1 FROM operations o2
              JOIN batches sb ON sb.id = o2.batch_id
              JOIN warehouses sw ON sw.id = sb.warehouse_id
              WHERE o2.type = 'transfer' AND o2.qty_delta < 0
                AND sb.product_id = b.product_id AND sw.currency <> w.currency
                AND sb.price_cents = b.price_cents);
```

## Info

### IN-01: Comments now contradict the behaviour

**File:** `app/services/transfers.py:41-42`, `app/services/transfers.py:126-129`, `app/templates/partials/transfer_price_fields.html:10-12`

**Issue:** "always requires a real destination cost — no conversion, no FX rate" and "no conversion — the operator states the real cost" are no longer true: the UI now prefills a converted cost (WR-02).

**Fix:** Reword these comments to "required; the form may pre-fill a ÷N suggestion that the operator must confirm", or change the behaviour per WR-02.

### IN-02: The T-nnj-01 guards and the currency-switch rule have no tests

**File:** `tests/test_transfers.py`, `tests/test_mobile_transfers.py` (new blocks)

**Issue:** None of the new tests calls `/transfers/dest-pick` or `/m/transfers/step/dest-prices` with any of these inputs:

- a foreign `batch_id` (a batch of another product);
- a soft-deleted destination warehouse;
- an unknown code.

The ownership guard, which is the only thing preventing a suggestion for the wrong product/batch pair, is therefore unpinned. There is also no test for:

- a cross→cross switch (UAH→EUR) with a typed value (WR-01);
- the oversell-confirm POST carrying `sale_price` (desktop and mobile).

**Fix:** Add three GET tests that assert `name="sale_price"` is absent and no `value="717,00"` is present for each bad id. Add one service test for the UAH→EUR typed-value case, pinning whatever WR-01 decides.

### IN-03: The sync merge path accepts batch rows verbatim, so an older client can still push a copied cross-currency price

**File:** `app/services/merge.py` (`_reference_row` copies every declared `batch` column, see the comment at lines 98-108)

**Issue:** The fix lives only in `register_transfer`. A desktop client below 1.140 that syncs to s1 would still create a UAH batch with the RUB `price_cents` and upsert it to the server unchanged. Needs verification: whether any synced desktop client is live. Project memory says the client release tag has not been cut yet.

**Fix:** No code change needed if no such client exists. Otherwise, note in the release checklist that 1.140 must be the minimum client version before cross-currency transfers are used.

### IN-04: The «пересчитана — уточните» hint stays visible after the operator overwrites the suggestion

**File:** `app/templates/partials/transfer_price_fields.html:16, 20, 31, 34`

**Issue:** `oninput` removes only `data-autofilled`. The hint `<p>` stays until the next render, so the screen labels a typed value as a converted guess. This is the same idiom as `receipt_price_inputs.html:18-20`, so it is consistent with the rest of the app, but misleading.

**Fix:** `oninput="this.removeAttribute('data-autofilled'); var h=this.parentNode.querySelector('.converted-hint'); if (h) h.remove()"`, with `class="muted converted-hint"` on the hint paragraph.

### IN-05: The desktop POST computes `price_fields` outside the `try`, so a DB error there becomes a raw 500

**File:** `app/routes/transfers.py:218-227`

**Issue:** `transfer_price_fields` runs several queries, including `lookup_prefill` and the catalog lookup, before the `try` whose comment promises "block error, never a raw 500". A locked or unavailable DB at that point bypasses the `SAVE_FAILED_ERROR` block. The mobile route computes the same data after `session.rollback()`, inside `_render_dest_step`, so the two routes are inconsistent.

**Fix:** Compute `price_fields` lazily inside each re-render branch (after the rollback in the `except`), as the mobile route does.

---

_Reviewed: 2026-09-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
