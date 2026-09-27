---
phase: quick-260927-k1m
verified: 2026-09-27T16:30:00Z
status: human_needed
score: 9/9 must-haves verified (1 with a browser-only part pending)
overrides_applied: 0
human_verification:
  - test: "Desktop receipt form on s1 after deploy: choose a RUB warehouse, type code 42499 (cost/sale autofill 1434,00 / 2499,00), then switch the warehouse to «Запорожье»"
    expected: "Autofilled cost/sale are cleared and re-suggested as 717,00 / 1249,50 (the rewarehouse event re-runs /receipts/lookup with the UAH warehouse)"
    why_human: "The hx-on:change handler and htmx.trigger run only in a browser; TestClient only proves the markup and the server response"
  - test: "Same form: type a price by hand, then switch the warehouse"
    expected: "The typed value stays; its colour cue (price-below/price-above) disappears; nothing is re-suggested into that field"
    why_human: "Client-side JS behaviour (dataset/classList), not reachable by server tests"
  - test: "Switch UAH -> RUB with autofilled values"
    expected: "Values re-suggest as the RUB card prices (1434,00 / 2499,00)"
    why_human: "Browser JS path"
---

# Quick 260927-k1m: Per-currency product card prices — Verification Report

**Goal:** each product has its own cost/sale/min_sale per currency (RUB existing, UAH, EUR); every operation uses its warehouse's currency fields; nothing writes another currency's fields; autofill = card price in warehouse currency, else RUB card/catalog converted (UAH /2, EUR /100, half-up) as a suggestion only; a missing currency cost stays NULL in stored money.
**Verified:** 2026-09-27, commit `9b497f3` (base `931c057`)
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Real case: UAH warehouse, card 143400/249900 -> lookup suggests 717,00/1249,50; save writes cost_uah_cents=71700/sale_uah_cents=124950, RUB untouched; next lookup suggests STORED UAH even after the RUB card changes | VERIFIED | `tests/test_receipts.py::test_web_receipt_uah_real_case_end_to_end` (L1733) drives GET /receipts/lookup -> POST /receipts -> DB read -> sets RUB to 300000/500000 -> second lookup still 717,00/1249,50 (RUB/2 would be 1500,00/2500,00, so the stored UAH value is what is read). Passed in my run. Code: `receipts.py:178` `fields = card_price_fields(warehouse_currency(...))`, `:196` new card, `:234-263` existing card keyed by `fields`; `lookup_prefill` uses `card_price_suggestion` (own field first). Direct helper check: `rub_suggestion(143400,'UAH')=71700`, `(249900,'UAH')=124950` |
| 2 | RUB receipt behaves as before; pre-existing tests in test_receipts.py / test_mobile_receipts.py pass unmodified | VERIFIED | `git diff 931c057 9b497f3` shows zero removed lines in test_receipts.py; test_mobile_receipts.py only swaps one import line. For RUB `card_price_fields` returns the unsuffixed names, so `entered`/new-card kwargs are identical. Both files green |
| 3 | UAH sale: unit_cost = batch.cost_cents, else card cost_uah_cents, else NULL (never RUB, never converted); min guard uses min_sale_uah_cents only | VERIFIED | `sales.py:271` `min_field = card_price_fields(basket_currency)["min_sale"]`; `:337` cost freeze `getattr(product, card_price_fields(basket_currency)["cost"])`. Grep gate: 0 non-comment uses of `rub_suggestion`/`card_price_suggestion` in sales.py + finance_reports.py. Tests `test_uah_sale_freezes_uah_card_cost`, `..._without_uah_card_cost_freezes_null`, `..._min_guard_uses_uah_minimum`, `..._ignores_rub_minimum_when_uah_minimum_unset` pass |
| 4 | stock_valuation(currency=X) COALESCEs to card field of X; missing stays NULL/unknown | VERIFIED | `finance_reports.py:74-76`; tests `test_stock_valuation_uah_falls_back_to_uah_card_prices`, `..._uah_without_uah_card_prices_is_unknown` pass. Pre-existing `test_stock_valuation_scopes_by_currency` was edited (deviation 1) because it asserted the old cross-currency fallback that the locked decision forbids — justified |
| 5 | Desktop product form edits/persists all three sets; omitted set unchanged; one price_change op per changed field naming it | VERIFIED | `catalog.py` `_PRICE_FIELDS` = 9 names RUB-first, `update_product` None -> keep old (`getattr(product, field)`), setattr loop; `products.py` update route `Form(None)`; `product_form.html` 6 new inputs. Tests `test_update_product_*`, `test_web_product_form_edits_all_three_price_sets`, `test_web_product_create_stores_currency_prices` pass |
| 6 | Warehouse change clears AUTOFILLED cost/sale and re-runs the lookup in the new currency; typed values never replaced | VERIFIED (server side) / HUMAN (browser) | `receipt_form.html:38` `hx-trigger="input changed delay:300ms, rewarehouse"`, `:60-64` hx-on:change handler clears only `data-autofilled="true"` fields, drops cue on typed ones, fires `htmx.trigger(#code,'rewarehouse')`; `receipt_price_inputs.html` marks lookup fills with `data-autofilled` + `oninput` removal. Markup test `test_web_receipt_form_warehouse_change_reruns_lookup` passes. The JS itself was not executed (no browser) — see Human Verification |
| 7 | Old-schema push cannot null UAH/EUR on server; pull carries them to a 0028 client; 0027 client ignores surplus keys | VERIFIED | `test_merge.py` 4 new tests (old push existing/new, new push, old-client pull with monkeypatched `KIND_TO_FIELDS`) and `test_sync_client.py::test_pull_keeps_server_currency_prices` pass |
| 8 | Migration 0028 up/down on SQLite; uq_products_code_active keeps WHERE; 4 append-only triggers survive | VERIFIED | `alembic/versions/0028_product_currency_prices.py`: batch add_column up, plain `op.drop_column` down; `alembic heads` -> `0028 (head)`; `test_0028_product_currency_columns_roundtrip` + retargeted VA-6 pass |
| 9 | Import script sends no catalog prices into a non-RUB warehouse | VERIFIED | `scripts/import_inventory_receipt.py` Rule 4 gated on `card_price_fields(currency) == CARD_PRICE_FIELDS[DEFAULT_CURRENCY]`, `run_import` passes `currency=warehouse.currency`; `test_non_rub_warehouse_import_sends_no_catalog_prices` asserts all 9 card fields and batch price/cost None |

**Score:** 9/9 truths verified (truth 6 browser part pending human check)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0028_product_currency_prices.py` | 6 nullable Integer columns, revision "0028" | VERIFIED | 55 lines, no defaults, down_revision 0027 |
| `app/core.py` | CARD_PRICE_FIELDS, card_price_fields, rub_suggestion, card_price_suggestion | VERIFIED | Decimal ROUND_HALF_UP; used by receipts, sales, catalog, finance, pricing, routes |
| `app/models.py` | six `*_uah/_eur_cents` columns | VERIFIED | no Python default |
| `app/services/batches.py` | `warehouse_currency` | VERIFIED | imported by receipts service + 4 route modules |
| `app/templates/partials/receipt_form.html` | rewarehouse wiring | VERIFIED | trigger + handler present |
| `app/__init__.py` | 1.139 | VERIFIED | `__version__ = "1.139"` |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| receipts.register_receipt | core.card_price_fields | `card_price_fields(warehouse_currency(` (receipts.py:178) | WIRED |
| routes/receipts.receipt_lookup | services/receipts.lookup_prefill | `lookup_prefill(session, code, currency=currency)` (routes/receipts.py:140) | WIRED |
| receipt_form.html select#warehouse_id | input#code hx-trigger | `htmx.trigger(..., 'rewarehouse')` (L70) + trigger (L38) | WIRED |
| sales.register_sale | core.card_price_fields | `card_price_fields(basket_currency)` (L271, L337) | WIRED |
| finance_reports.stock_valuation | Product currency columns | `getattr(Product, fields[...])` (L75-76) | WIRED |
| routes/products.product_update | catalog.update_product | `cost_uah_raw=` etc. (products.py:337) | WIRED |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Real Data | Status |
|----------|---------------|--------|-----------|--------|
| receipt_lookup.html OOB price inputs | `prices[f]` | `lookup_prefill(..., currency)` -> card own field / `rub_suggestion` of RUB card / catalog | Yes (DB) | FLOWING |
| sale fill (lookup / batch-pick / mobile qty-price) | `fill_price_cents` | batch.price_cents else `card_price_suggestion(product,"sale",currency)` | Yes | FLOWING |
| product_form.html ₴/€ inputs | `product.*_uah/_eur_cents` / `form.*` | DB product row | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Conversion helpers | `uv run python -c "...rub_suggestion..."` | `71700 124950 1434 2499 3 3 None`; UAH field map correct; USD/None -> RUB set; stored UAH 124000 wins over RUB/2 | PASS |
| Alembic head | `uv run alembic heads` | `0028 (head)` | PASS |
| Targeted tests (13 plan files + test_business_date) | `uv run pytest -q -p no:cacheprovider tests/test_core.py ... tests/test_business_date.py` | `688 passed, 2 warnings in 184.11s` | PASS |
| Conversion kept out of stored-money code | `grep -hv '^\s*#' app/services/sales.py app/services/finance_reports.py \| grep -c 'rub_suggestion\|card_price_suggestion'` | `0` | PASS |
| No conversion in register_receipt | awk slice of register_receipt grep for helpers | no match | PASS |
| Lint | `uv run ruff check` on changed sources + 0028 | 1 finding, `products.py:135 E501` — present at base 931c057 (confirmed via stdin lint of the base file) | PASS (no new) |

Full suite not re-run (orchestrator reported 4 failed / 1870 passed: 3 known test_sync_ui + test_offline::test_login_rate_limited, which passes in isolation).

### Probe Execution

Not applicable — no probes declared.

### Requirements Coverage

| Requirement | Description | Status | Evidence |
|-------------|-------------|--------|----------|
| CUR-01 | Per-warehouse currency, never mixed | SATISFIED | Stored money never converted; the one conversion is a form suggestion; REQUIREMENTS.md:107 amended in the working tree (uncommitted, for the orchestrator's docs commit) |
| CUR-02 | Batch/sale money in the warehouse's currency | SATISFIED | cost freeze + min guard + valuation in basket/warehouse currency |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (added lines of the commit) | — | TBD/FIXME/XXX/TODO/HACK | none found | — |
| app/services/transfers.py | 192 | cross-currency transfer copies source `price_cents` into the destination batch | WARNING (pre-existing, not scheduled, named in SUMMARY) | A RUB->UAH transfer yields a UAH batch whose sale price is a RUB number; the sale form then fills that batch price, not the UAH suggestion. Batch money, not card fields; s1 has 0 non-RUB batches today |
| app/templates/pages/categories.html, partials/product_rows.html, mobile_partials/search_product_detail.html | — | RUB-only card display cells | INFO | Display only; named unscheduled |
| tests/test_merge.py | 677-697 | docstring now inaccurate | INFO | Test still passes |

### Deviations reviewed

- Orchestrator amendment to A1: a non-RUB lookup on a card with neither own nor RUB price falls back to the RUB catalog price converted (`receipts.py` lookup_prefill). Consistent with the goal ("else RUB card/catalog converted"); RUB path unchanged.
- `tests/test_finance_reports.py::test_stock_valuation_scopes_by_currency` edited — the old assertion encoded the cross-currency fallback that the locked decision forbids.
- `tests/test_business_date.py` seeds products via raw SQL on a 0026 schema (required by the new model columns); outside the plan's file list but in the commit.
- Update-route 422 echo keeps None for unposted ₴/€ fields (safer than the planned `x or ""`).

### Human Verification Required

1. **Warehouse switch re-suggests (RUB -> UAH).** On s1 after deploy, desktop receipt form, RUB warehouse, code 42499, then switch to «Запорожье». Expected: 717,00 / 1249,50. Why human: browser JS (`hx-on:change` + `htmx.trigger`).
2. **Typed value survives a switch.** Type a price, switch warehouse. Expected: value stays, colour cue removed. Why human: client-side JS.
3. **Switch back UAH -> RUB.** Expected: 1434,00 / 2499,00 re-suggested. Why human: browser JS.

### Gaps Summary

No code gaps. Every must-have truth is backed by code on the real path and by passing tests that I ran; the real case (717,00 / 1249,50 suggested, UAH fields written, RUB untouched, second lookup reads stored UAH) is confirmed. The only open items are the browser-side warehouse-switch checks and the deploy itself (migration 0028 on s1, re-download of offline bundles), which are outside what can be verified here.

---

_Verified: 2026-09-27_
_Verifier: Claude (gsd-verifier)_
