---
phase: quick-260927-nnj
plan: 01
subsystem: transfers (desktop + mobile)
tags: [currency, transfers, CUR-02, htmx]
requires: [260927-k1m per-currency card prices (lookup_prefill currency=, converted_price_hint)]
provides:
  - register_transfer(sale_price_raw=...) — cross-currency dest price = typed value or NULL
  - transfer_price_fields(...) — read-only cost/sale-price field values + suggestions
  - GET /transfers/dest-pick, GET /m/transfers/step/dest-prices fragments
  - partials/transfer_price_fields.html (single source, desktop + mobile)
affects: [sales batch-pick fallback now reached for cross-currency transferred batches]
tech-stack:
  added: []
  patterns: [k1m autofilled-marker + form-level js hx-vals flags, reused lookup_prefill for suggestions]
key-files:
  created:
    - app/templates/partials/transfer_price_fields.html
  modified:
    - app/services/transfers.py
    - app/routes/transfers.py
    - app/routes/mobile_transfers.py
    - app/templates/partials/transfer_batch_wrap.html
    - app/templates/partials/transfer_form.html
    - app/templates/mobile_partials/transfers_step_dest.html
    - app/__init__.py
    - tests/test_transfers.py
    - tests/test_mobile_transfers.py
decisions:
  - "Cross-currency transfer no longer copies source.price_cents; empty sale price -> NULL, typed -> dest batch only"
  - "Suggestions only on destination change (suggest=True); POST re-renders echo, never fill"
metrics:
  duration: ~35 min
  completed: 2026-09-27
requirements: [CUR-02]
---

# Quick 260927-nnj: Cross-currency transfer sale price in destination currency — Summary

A transfer into a warehouse of another currency no longer copies the source batch's
sale price: the destination batch takes an optional «Цена продажи в валюте склада
назначения» (empty -> `price_cents` NULL, so a sale falls back to the card price of
the destination currency), with cost/sale suggestions in the destination currency
reused from k1m's `lookup_prefill`; same-currency transfers are unchanged. Version 1.140.

## Commit

| Hash | Message |
|------|---------|
| `d72f523` | fix(260927-nnj): cross-currency transfer takes a destination sale price instead of copying the source price |

One code commit, 10 explicit paths, no trailer (`git log -1 --format=%B` checked). Not pushed; s1 not touched; no server started; `data/myorishop.db` not opened. SUMMARY/PLAN/STATE not committed; ROADMAP.md and STATE.md not edited.

## What changed

- `app/services/transfers.py`
  - `register_transfer(..., sale_price_raw="")`: in the cross-currency branch, after the unchanged cost rule, `parse_optional_cents(sale_price_raw, ...)` -> `price_cents` (None when empty); garbage/negative -> `{"sale_price": PRICE_ERROR}`, zero writes. Same-currency branch: `price_cents = source.price_cents`, `sale_price_raw` ignored. The dest `Batch` uses the branch-computed `price_cents` (`price_cents=source.price_cents` no longer exists). Product card never written.
  - New read-only `transfer_price_fields(...)`: same guards as `register_transfer` (active product, batch ownership, dest in `active_warehouses`, resolvable source warehouse) — any miss -> `cross_currency False`, never raises. Suggestions come only from `lookup_prefill(session, code, currency=dest_currency)`; hint only from `converted_price_hint`. No conversion arithmetic written.
- `partials/transfer_price_fields.html` (new): `<div id="transfer-price-fields">` with the cost field (moved verbatim, now with autofilled marker + hint) and, only for cross-currency, the sale field. No `tojson`, no `|safe`.
- Desktop: dest `<select>` gets `hx-get="/transfers/dest-pick"` (change, include closest form, target `#transfer-price-fields`, outerHTML); `transfer_form.html` gets the single-quoted form-level `hx-vals='js:{cost_autofilled..., sale_price_autofilled...}'`; orphaned `cost_value` removed from the with-block; POST `/transfers` takes `sale_price`, `cost_autofilled`, `sale_price_autofilled`, computes `price_fields` once (suggest=False) for exception/oversell/errors re-renders; `"cost"` dropped from `form_echo`.
- Mobile: `_render_dest_step` computes `price_fields` (flat `cost` key replaced); new GET `/m/transfers/step/dest-prices`; POST `/m/transfers` threads the three new fields into all three re-render calls; step-3 template includes the shared partial (still before op_date), radios container wired with `hx-get`, form gets the same flags `hx-vals`. POST `/m/transfers/step/dest` and batch-pick untouched.

## Assumptions (reversible)

- **A1:** For a RUB destination (UAH/EUR -> RUB transfer) suggestions are the RUB card price only, no catalog fallback — `lookup_prefill`'s unchanged RUB branch (k1m A1).
- **A2:** Suggestions are made only when the destination changes (the two new GET fragment routes, `suggest=True`). A POST re-render (422/oversell/exception) echoes posted values and autofilled marks and never fills an empty field, so a deliberately cleared sale price stays empty -> NULL.
- **A3:** Switching to a same-currency destination hides the sale field (its value is dropped) and clears an AUTOFILLED cost; a typed cost is kept.
- **A4:** "Byte-identical" (D-05) means same stored data and same visible fields. The cost field markup is unchanged but lives in the shared partial inside `<div id="transfer-price-fields">`, and the destination control gained hx attributes.
- **A5:** A `sale_price` posted on a same-currency transfer is ignored (the field is never rendered there).
- **A6:** Sale-price validation runs after the cost rule inside the cross-currency branch (single early-return error): garbage or negative -> `{"sale_price": PRICE_ERROR}`, zero writes.
- **A7 (accepted limitation):** The oversell «Переместить всё равно» button sits outside the form, so it does not inherit the form's autofilled flags; only a 422 AFTER a confirm loses the marks. No in-flight race guard on the destination-change fragment (a `change` event, not live typing).
- Additional (execution): the mobile «Назад» button's own `hx-vals` now merges with the inherited form-level flags, so `/m/transfers/step/batch` receives two extra, unused params — harmless (FastAPI ignores unknown form fields).

## Gate outputs (pasted)

Task 1 RED — `uv run pytest tests/test_transfers.py tests/test_mobile_transfers.py -q -p no:cacheprovider`:
```
20 failed, 79 passed, 1 warning in 37.84s
```
Failure reasons (as planned): `TypeError: register_transfer() got an unexpected keyword argument 'sale_price_raw'`, `ImportError: cannot import name 'transfer_price_fields'`, `assert 404 == 200` (new routes), `assert 1500 is None` / `assert 1500 == 45050` (price copied), missing `hx-get="/transfers/dest-pick"` / `name="sale_price"`. Zero collection errors, all 79 pre-existing tests passed. The named guard `test_web_same_currency_422_has_no_sale_price_field` passed before the fix (as the plan anticipated).

Task 2 — `uv run pytest tests/test_transfers.py -q -p no:cacheprovider`:
```
60 passed, 1 warning in 19.00s
```
No-conversion grep (`grep -hv '^\s*#' app/services/transfers.py | grep -cE 'rub_suggestion|_RUB_DIVISOR|Decimal|product\.(cost|sale|min_sale)'`): `0` (exit 1).

Task 3 gate 1 — both transfer files:
```
99 passed, 1 warning in 30.92s
```
Gate 2 — `uv run pytest tests/test_receipts.py tests/test_mobile_receipts.py tests/test_sales.py tests/test_mobile_sales.py tests/test_mobile_foundation.py -q -p no:cacheprovider`:
```
252 passed, 2 warnings in 76.57s (0:01:16)
```
Gate 3 — ruff on the five .py files:
```
app\routes\transfers.py:64:101: E501 Line too long (102 > 100)
Found 1 error.
```
(baseline only)

Gate 4 — full suite `uv run pytest -q -p no:cacheprovider`:
```
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial - assert 'Син...
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru - assert 'Нет с...
FAILED tests/test_sync_ui.py::test_not_configured_run_is_a_noop - assert 'Син...
FAILED tests/test_sync_ui.py::test_lock_hit_returns_locked_partial - assert F...
4 failed, 1904 passed, 14 skipped, 3 warnings in 510.98s (0:08:30)
```
All 4 failures are in the allowed pre-existing set (tests/test_sync_ui.py lifespan lock). `tests/test_offline.py::test_login_rate_limited` passed in this run, so no re-run was needed.

Verification greps: `hx-get="/transfers/dest-pick"` in transfer_batch_wrap.html = 1; `hx-get="/m/transfers/step/dest-prices"` in transfers_step_dest.html = 1; `include "partials/transfer_price_fields.html"` = 1 in each; `price_cents=source.price_cents` in app/services/transfers.py = no match.

## Deviations from Plan

- **[Rule 3 - lint] Re-wrapped a comment** in `app/services/transfers.py` (the D-05 comment edit produced a 137-char line; ruff flagged it). Fixed before commit; no behavior change.
- **Artifacts location:** the output contract's `reports/<plan-id>.{xml,sha,dirty}` would add untracked files to the repo, which the orchestrator's constraints forbid (only AGENTS.md, input/, plan1.txt and this SUMMARY may be untracked). They were written to the session scratchpad instead: `260927-nnj.xml` (transfer files, 99 passed), `260927-nnj.sha` (`d72f523ccb40d48e0a132559b36e22451d087d0c`), `260927-nnj.dirty` (only the four expected untracked entries).

Otherwise the plan was executed as written.

## Pending human browser checks (not run here — no server started by constraint)

1. Desktop `/transfers`: code of a product with RUB card prices only (like STK-001), pick a batch in a RUB warehouse, choose a UAH warehouse -> cost and sale fields fill with RUB/2 values, each with «Цена пересчитана из рублёвой (÷2) — уточните.»; type a cost; switch to a RUB warehouse -> the sale field disappears and the typed cost stays; switch back to UAH -> the sale price is re-suggested and the typed cost is kept.
2. The same on `/m/transfers` step 3 (radio change instead of select).
3. Save a cross-currency transfer with an empty sale price, then pick that destination batch on `/sales` -> the UAH card price (or its RUB/2 suggestion) fills.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model (T-nnj-01..04 applied: guarded ids, parse_optional_cents, autoescape-only echo, flags compared to "true" and never echoed).

## Self-Check: PASSED

- FOUND: app/templates/partials/transfer_price_fields.html
- FOUND: commit d72f523 (10 files, version 1.140)
