---
phase: quick-260927-nnj
verified: 2026-09-27T16:10:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Desktop /transfers: product with RUB card prices only; pick a batch in a RUB warehouse; choose a UAH warehouse in «Склад назначения»"
    expected: "Cost and «Цена продажи в валюте склада назначения» fill with RUB/2 values, each with «Цена пересчитана из рублёвой (÷2) — уточните.»; type a cost, switch to a RUB warehouse -> sale field disappears, typed cost stays; switch back to UAH -> sale price re-suggested, typed cost kept"
    why_human: "Relies on htmx in a real browser: hx-trigger=change on the select, hx-include=closest form, and inheritance of the form-level js: hx-vals flags into the GET. TestClient only calls the fragment route directly"
  - test: "Mobile /m/transfers step 3: same flow with the destination radios"
    expected: "Same as desktop; the radio change swaps #transfer-price-fields without losing a typed cost"
    why_human: "Same htmx event and attribute-inheritance path, untestable without a browser"
  - test: "Save a cross-currency transfer with an empty sale price, then pick that destination batch on /sales"
    expected: "The sale price field fills with the UAH card price (or its RUB/2 suggestion with the converted hint)"
    why_human: "End-to-end UI check. The server side is covered by test_web_cross_currency_blank_sale_price_falls_back_to_card_on_sale, but not the browser flow"
---

# Quick 260927-nnj: Cross-currency transfer sale price. Verification report

**Goal:** A cross-currency transfer never copies the source batch's sale price. An empty sale price gives a destination `price_cents` of NULL. A typed price goes to the destination batch only. Suggestions (the card price in the destination currency, else RUB/2 or RUB/100 marked «пересчитана») are only input values. A transfer never writes the product card. Same-currency transfers are unchanged. Cost is still required for cross-currency.
**Verified:** 2026-09-27, commit `d72f523` (base `b422566`)
**Status:** human_needed. All automated checks pass; only the browser htmx flows remain.
**Re-verification:** No. This is the initial verification.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-03: cross UAH transfer with an empty sale price -> dest `price_cents` NULL; `/sales/batch-pick` then fills the UAH card price 1300,00 | VERIFIED | `app/services/transfers.py:155` `price_cents = parse_optional_cents(sale_price_raw, ...)` (empty -> None) and the dest `Batch(price_cents=price_cents)`. The string `price_cents=source.price_cents` no longer exists. The sales fallback is at `app/routes/sales.py:339-345` (NULL -> `card_price_suggestion(product,"sale",currency)`). Tests: `test_cross_currency_blank_sale_price_leaves_dest_price_null`, `test_web_cross_currency_blank_sale_price_falls_back_to_card_on_sale`, and the mobile `..._sale_price_blank_and_typed`. All pass at HEAD; on base they fail with `assert 1500 is None`. |
| 2 | D-03/D-04: typed 450,50 -> dest 45050, source keeps 1500, all 9 card price columns unchanged | VERIFIED | `register_transfer` never assigns to Product attributes (grep for `product.(cost\|sale\|min_sale)` and `setattr(product` finds 0). `test_cross_currency_typed_sale_price_lands_on_dest_only` snapshots the 9 columns in `_CARD_PRICE_COLUMNS`, and it passes. |
| 3 | D-01/D-02: choosing a UAH dest (desktop dest-pick, mobile dest-prices) shows the sale field and pre-fills EMPTY fields with 717,00 / 1249,50, `data-autofilled` and the «пересчитана» hint. A UAH card price gives 1300,00 with no hint. A typed value is never replaced | VERIFIED (server side) | `transfer_price_fields` is at `app/services/transfers.py:261-327`. Both GET routes exist (`app/routes/transfers.py:136`, `app/routes/mobile_transfers.py:221`). The select and the radio container carry `hx-get` (`transfer_batch_wrap.html`, `transfers_step_dest.html`). Covered by 5 service tests, 2 desktop route tests and 2 mobile route tests. The browser event path is listed under human checks. |
| 4 | D-01: cross-currency cost stays REQUIRED; COST_REQUIRED_ERROR and the existing CUR-02 tests are unchanged | VERIFIED | `transfers.py:146-147` is unchanged: an empty cost returns `{"cost": COST_REQUIRED_ERROR}` before the sale-price parse. The test diff has 0 removed lines. The pre-existing CUR-02 tests pass. |
| 5 | D-05: same currency -> no sale field, `source.price_cents` inherited, a posted sale_price ignored, all pre-existing tests unmodified and passing | VERIFIED | `transfers.py:159-160`: the else branch sets `price_cents = source.price_cents`. The partial shows the sale field only when `_pf.cross_currency` is set. The pre-existing tests in both files are untouched (`git diff` shows 557 insertions and 0 deletions). On base the 79 pre-existing tests pass; at HEAD all 99 pass. Tests `test_same_currency_transfer_ignores_posted_sale_price` (1500) and `test_web_same_currency_422_has_no_sale_price_field` cover this. |
| 6 | A 422 re-render keeps the typed cost/sale and the autofilled marks; an empty sale price is NOT re-suggested on a POST re-render | VERIFIED | Both POST handlers compute `price_fields` with suggest=False (`routes/transfers.py:215`, `_render_dest_step`). With suggest=False, `transfer_price_fields` only echoes values. Tests: `test_web_cross_currency_422_keeps_typed_prices_and_marks`, mobile `..._422_keeps_typed_prices`, `test_transfer_price_fields_no_suggestion_without_suggest`. |
| 7 | No new conversion code (only `lookup_prefill(..., currency=)` and `converted_price_hint`); no migration | VERIFIED | The no-conversion grep on non-comment lines of `app/services/transfers.py` returns 0. The suggestions come from `lookup_prefill(session, code, currency=dest_currency)` (line 297). The commit stat lists 10 files and no alembic or migration files. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/transfers.py` | `register_transfer(sale_price_raw=)` + `def transfer_price_fields` | VERIFIED | Substantive. Used by both route modules. |
| `app/templates/partials/transfer_price_fields.html` | `id="transfer-price-fields"`, the single source of the fields | VERIFIED | Included by `transfer_batch_wrap.html` and `transfers_step_dest.html` (1 include each) and rendered by both GET fragment routes. Autoescape only; no `|safe` or `tojson`. |
| `app/routes/transfers.py` | GET `/transfers/dest-pick`; POST echoes `price_fields` | VERIFIED | Declared before any parameterized route. The exception, oversell and error contexts all carry `price_fields`. |
| `app/routes/mobile_transfers.py` | GET `/m/transfers/step/dest-prices`; POST echoes | VERIFIED | All three `_render_dest_step` calls in POST forward `sale_price` and both flags. |
| `app/__init__.py` | 1.140 | VERIFIED | `__version__ = "1.140"` |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `register_transfer` | `catalog.parse_optional_cents` | `parse_optional_cents(sale_price_raw, ...)` in the cross branch | WIRED (transfers.py:155) |
| `transfer_price_fields` | `receipts.lookup_prefill` | `lookup_prefill(session, code, currency=dest_currency)` | WIRED (transfers.py:297) |
| `transfer_batch_wrap.html` select | GET `/transfers/dest-pick` | `hx-get` + `hx-trigger="change"` + target `#transfer-price-fields` | WIRED (the markup is asserted by `test_web_batch_pick_wires_dest_select_to_dest_pick`) |
| `transfers_step_dest.html` radios | GET `/m/transfers/step/dest-prices` | `hx-get` on the radios' container div (the change event bubbles) | WIRED (asserted by `test_transfers_dest_step_wires_radios_to_dest_prices`) |
| form-level `hx-vals='js:{...}'` | dest-pick GET and POST | htmx attribute inheritance; `base.html` and `mobile_base.html` htmx-config set only `responseHandling` | WIRED in markup. The runtime inheritance needs a human check. |

### Data-Flow Trace (Level 4)

| Artifact | Data | Source | Real data | Status |
|----------|------|--------|-----------|--------|
| `transfer_price_fields.html` | `price_fields.cost/sale_price/hints` | `transfer_price_fields` -> `lookup_prefill` -> `card_price_suggestion` / `rub_suggestion` on the Product row | Yes. Tests show 717,00 / 1249,50 / 1300,00 computed from the DB. | FLOWING |
| dest `Batch.price_cents` | the parsed sale price or None | form `sale_price` -> `register_transfer` | Yes. The tests read the DB (`open_batches`). | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Both transfer files green | `uv run pytest -q -p no:cacheprovider tests/test_transfers.py tests/test_mobile_transfers.py` | `99 passed, 1 warning in 35.89s` | PASS |
| New tests are real (red on base) | `b422566` app/tests extracted to scratchpad with the HEAD test files, then run with the project venv | `20 failed, 79 passed`. The NULL tests fail with `assert 1500 is None` / `[1500] == [None]`. | PASS (non-vacuous) |
| Related sales/receipts paths unaffected | `uv run pytest -q -p no:cacheprovider tests/test_sales.py tests/test_mobile_sales.py tests/test_receipts.py` | `215 passed, 2 warnings` | PASS |
| Lint | `uv run ruff check` on the 5 .py files | only the baseline `app\routes\transfers.py:64:101: E501` | PASS |
| No import cycle | `uv run python -c "import app.services.transfers, app.main"` | `import ok` | PASS |

The full suite was not re-run, as instructed. The executor reported `4 failed, 1904 passed`, and all 4 failures are the known `tests/test_sync_ui.py` lock failures.

### Probe Execution

Step 7c: SKIPPED. This is not a migration/tooling phase and it declares no probes.

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
|-------------|-------------|--------|----------|
| CUR-02 (cross-currency transfer money never crosses currencies) | 260927-nnj-PLAN | SATISFIED | Cost (pre-existing) and now sale price are both destination-currency or NULL. Truths 1-4. |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (all 10 touched files) | - | TBD/FIXME/XXX/TODO/placeholder | none found | The only `placeholder` hits are the HTML `placeholder="0,00"` input attributes, which are not stubs. |
| `app/routes/transfers.py` | 64 | E501 | Info | Pre-existing baseline, not introduced here. |

Other paths checked: the only other `Batch(` constructor near transfers is `app/services/merge.py`, which replicates rows as-is and does not create transfers. The only callers of `register_transfer` are the two routes, and both pass `sale_price_raw`.

Informational notes (not gaps):
- A7 (accepted in the plan): the oversell «Переместить всё равно» button sits outside the form, so a 422 after a confirm loses the autofilled marks. The values themselves are kept.
- The mobile «Назад» button now also sends the two inherited flag params to `/m/transfers/step/batch`. FastAPI ignores unknown form fields, so this is harmless.

### Human Verification Required

1. **Desktop destination change.** On `/transfers`, use a product with RUB card prices only. Pick a batch in a RUB warehouse, then choose a UAH destination. Expected: cost and sale fill with RUB/2 values, each with the «пересчитана» hint. Then type a cost and switch to a RUB warehouse. Expected: the sale field disappears and the typed cost stays. Switch back to UAH. Expected: the sale price is re-suggested and the typed cost is kept. Why a human is needed: the htmx `change` trigger and the `js:` hx-vals inheritance only run in a real browser.
2. **Mobile step 3.** Repeat the same flow on `/m/transfers` using the radios.
3. **Sale after an empty-price transfer.** Save a cross-currency transfer with the sale price left empty, then pick that batch on `/sales`. Expected: the UAH card price, or its converted suggestion, fills.

### Gaps Summary

There are no gaps. Every must-have holds at the code level, is covered by tests that fail on the base commit and pass at `d72f523`, and has its key links wired. The status is `human_needed` only because of the three browser checks above.

---

_Verified: 2026-09-27_
_Verifier: Claude (gsd-verifier)_
