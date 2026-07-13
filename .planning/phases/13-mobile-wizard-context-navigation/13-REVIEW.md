---
phase: 13-mobile-wizard-context-navigation
reviewed: 2026-07-14T00:00:00Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - app/routes/mobile_corrections.py
  - app/routes/mobile_receipts.py
  - app/routes/mobile_sales.py
  - app/routes/mobile_transfers.py
  - app/routes/mobile_writeoff.py
  - app/templates/mobile_pages/corrections.html
  - app/templates/mobile_pages/receipts.html
  - app/templates/mobile_pages/transfers.html
  - app/templates/mobile_pages/writeoff.html
  - app/templates/mobile_partials/_wizard_header.html
  - app/templates/mobile_partials/batch_card_picker.html
  - app/templates/mobile_partials/corrections_step_batch.html
  - app/templates/mobile_partials/corrections_step_mode.html
  - app/templates/mobile_partials/corrections_step_product.html
  - app/templates/mobile_partials/corrections_step_value.html
  - app/templates/mobile_partials/receipts_step_batch.html
  - app/templates/mobile_partials/receipts_step_product.html
  - app/templates/mobile_partials/sale_basket.html
  - app/templates/mobile_partials/sale_step_qty_price.html
  - app/templates/mobile_partials/search_product_detail.html
  - app/templates/mobile_partials/transfers_step_batch.html
  - app/templates/mobile_partials/transfers_step_product.html
  - app/templates/mobile_partials/writeoff_step_batch.html
  - app/templates/mobile_partials/writeoff_step_product.html
  - app/templates/mobile_partials/writeoff_step_qty.html
  - app/templates/mobile_partials/writeoff_step_reason.html
  - app/templates/mobile_partials/writeoff_warning.html
  - tests/test_mobile_corrections.py
  - tests/test_mobile_receipts.py
  - tests/test_mobile_sales.py
  - tests/test_mobile_search.py
  - tests/test_mobile_transfers.py
  - tests/test_mobile_writeoff.py
findings:
  critical: 0
  warning: 6
  info: 3
  total: 9
status: issues
---

# Phase 13: Code Review Report

**Reviewed:** 2026-07-14
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

This review covers the FULL Phase 13 file set (all 6 plans, 13-01 through 13-06) — corrections, write-off, receipts, transfers, and sale mobile wizards — and supersedes the prior `13-REVIEW.md` (which predated 13-06's sale-wizard warehouse-visibility gap closure and did not include `batch_card_picker.html` or `sale_step_qty_price.html` in scope).

No security vulnerabilities were found. Batch/product-ownership re-validation (the recurring T-09-08/T-11-x precedent: never trust a client-supplied `batch_id`, always re-query and check `product_id` match before use) is applied consistently and correctly across all five wizards, including the newly-reviewed `mobile_sales.py` code paths. Untrusted stored text (batch comment/location/warehouse name/product name) is rendered with Jinja autoescape only — no `|safe` usage found anywhere in the reviewed templates. Every write path (`register_correction`/`register_receipt`/`register_sale`/`register_transfer`/`register_writeoff`) is called inside a `try/except` with an explicit `session.rollback()` before re-rendering — no bare 500s, no unhandled `PendingRollbackError`.

All issues found are quality/UX regressions in the "hidden-field carry-forward" contract this phase is built around (RESEARCH Pattern 1: state travels only via posted/echoed fields, no server-side wizard session), or in the still-outstanding forward-navigation guard pattern corrections established but sale/write-off/receipts never adopted. None cause bad writes — the `app/services/*` layer still catches every invalid state before a row is written — but several produce confusing operator-facing dead ends, and one (WR-04) now also affects the sale wizard as of 13-06's warehouse-name additions to `batch_card_picker.html`.

## Warnings

### WR-01: "Назад" from receipts step 2 silently reverts the chosen warehouse

**File:** `app/routes/mobile_receipts.py:79-95`
**Issue:** `mobile_receipt_new` (`GET /m/receipts`) is used both for the cold page load and — per `receipts_step_batch.html`'s `hx-get="/m/receipts" hx-include="closest form"` "Назад" button (confirmed by `tests/test_mobile_receipts.py::test_step_batch_back_is_hx_get_to_receipts`) — as the step-2-to-step-1 back target. The route signature only declares `code: str = ""`; it never reads a `warehouse_id` parameter, even though `receipts_step_batch.html` carries `<input type="hidden" name="warehouse_id" value="{{ warehouse_id }}">` in the very form the "Назад" button includes. `selected_warehouse_id` is always recomputed via `_preselect_warehouse_id(actives)` with no submitted value, so it always falls back to the seeded default (or first active) warehouse — discarding whatever warehouse the operator explicitly picked on step 1. If unnoticed, tapping "Назад" then "Далее" again can route a receipt into the wrong warehouse.
**Fix:**
```python
@router.get("/m/receipts")
def mobile_receipt_new(
    request: Request, code: str = "", warehouse_id: str = "", session: Session = Depends(get_session)
):
    actives = active_warehouses(session)
    context = {
        "zero_warehouses": not actives,
        "active_warehouses": actives,
        "selected_warehouse_id": _preselect_warehouse_id(actives, warehouse_id),
        "code": code,
    }
    ...
```

### WR-02: "Назад" from write-off step 2 always wipes the typed product code

**File:** `app/routes/mobile_writeoff.py:67-74`
**Issue:** Every sibling wizard's step-1 GET route accepts and echoes a `code` query/form param specifically so its own "Назад" button preserves the operator's typed code (`mobile_correction_start`, `mobile_receipt_new`, `transfers_step_product` all declare `code: str = ""`). `mobile_writeoff_start` is the one outlier — `def mobile_writeoff_start(request: Request):` takes no `code` parameter at all, and always renders `context = {"errors": {}, "code": "", "name": "", "saved": None}`. `writeoff_step_batch.html`'s "Назад" button (`hx-get="/m/writeoff" hx-include="closest form"`) sends the current `code` field along as a query param, but it is silently discarded — the operator has to retype the code from scratch after tapping "Назад".
**Fix:**
```python
@router.get("/m/writeoff")
def mobile_writeoff_start(request: Request, code: str = ""):
    context = {"errors": {}, "code": code, "name": "", "saved": None}
    ...
```

### WR-03: "Назад" from corrections step 4 discards the selected mode despite carrying it as a hidden field

**File:** `app/routes/mobile_corrections.py:149-170`
**Issue:** `mobile_correction_step_mode` (`POST /m/corrections/step/mode`) is the "Назад" target from `corrections_step_value.html`, whose form includes `<input type="hidden" name="mode" value="{{ mode }}">`. The route never declares a `mode` Form parameter and hardcodes `"mode": ""` in the returned context, so every time the operator goes back from "Значение" to "Режим", both radio buttons render unchecked, discarding whichever mode ("count"/"delta") was previously selected. The hidden field is submitted and then silently ignored — dead data with no reason not to be honored (unlike batch selection, preserving a 2-value radio state carries no re-validation cost).
**Fix:**
```python
@router.post("/m/corrections/step/mode")
def mobile_correction_step_mode(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    batch_id: str = Form(""),
    batch_qty: str = Form(""),
    mode: str = Form(""),
    session: Session = Depends(get_session),
):
    ...
    context = {
        ...
        "mode": mode if mode in ("count", "delta") else "",
    }
```

### WR-04: Batch cards show a blank "Склад:" line when the batch's warehouse has been deactivated (transfers AND sale)

**Files:** `app/templates/mobile_partials/transfers_step_batch.html:37`, `app/templates/mobile_partials/batch_card_picker.html:63`, `app/routes/mobile_transfers.py:43-45`, `app/routes/mobile_sales.py:38-40`
**Issue:** Both `mobile_transfers.py::_warehouse_names()` and `mobile_sales.py::_warehouse_names()` map only `active_warehouses(session)` (`deleted_at IS NULL`) to their names. Both the transfer batch card (`transfers_step_batch.html:37`) and the shared picker's per-card warehouse line — now also used by the sale wizard's `sale_step_batch.html` as of 13-06 — render `warehouse_names.get(b.warehouse_id, "")` with an empty-string fallback. If a batch's warehouse has since been soft-deleted/deactivated while the batch is still open (deactivating a location doesn't retroactively close its batches), the card silently shows "Склад: " with nothing after the colon instead of the real (deactivated) warehouse name. This contradicts `_wizard_header.html`'s own documented contract ("must be `None`/absent, never `''`, to correctly omit their line"), which every single-value carried-warehouse display (`_carried_warehouse_name` in corrections/write-off, `_wizard_header.html` itself) already honors correctly via a `None`-returning `.get(...)`.
**Fix:** Either build a separate all-warehouses id->name map (not gated on `active_warehouses`) for card-list display purposes, or fall back to a non-empty placeholder, e.g. `warehouse_names.get(b.warehouse_id, "—")`, consistently in both `transfers_step_batch.html` and `batch_card_picker.html`.

### WR-05: Sale wizard batch step lets the operator advance without picking a batch

**File:** `app/templates/mobile_partials/sale_step_batch.html:21-25`
**Issue:** When a product has more than one open batch (no D-06 auto-select), the "Далее" button is rendered unconditionally once `not show_empty`:
```html
{% if not show_empty %}
<button type="button"
        hx-post="/m/sales/step/qty-price"
        hx-target="#wizard-step" hx-swap="innerHTML">Далее</button>
{% endif %}
```
There is no guard on `selected_batch_id`/`batch_id`, unlike `corrections_step_batch.html:27` (`{% if not selected_batch_id %} disabled{% endif %}`). The operator can tap "Далее" with no card selected, proceed through "Количество и цена" and "Корзина", and only get rejected at final `POST /m/sales` with `BATCH_REQUIRED_ERROR` ("Выберите партию.") from `app/services/sales.py` — after already typing qty/price for that line. No data-integrity issue (server-side re-validation in `register_sale` catches it), but it is a preventable UX dead end that the corrections wizard already solved.
**Fix:** Mirror the corrections pattern:
```html
{% if not show_empty %}
<button type="button"{% if not selected_batch_id %} disabled{% endif %}
        hx-post="/m/sales/step/qty-price"
        hx-target="#wizard-step" hx-swap="innerHTML">Далее</button>
{% endif %}
```
(htmx does not fire requests from `disabled` elements, so this closes the gap without any route change.)

### WR-06: Write-off wizard batch step has the same missing forward-navigation guard

**File:** `app/templates/mobile_partials/writeoff_step_batch.html:19-24`, `app/routes/mobile_writeoff.py:92-120`
**Issue:** Same shape as WR-05 — `mobile_writeoff_step_batch` never auto-selects a batch (`"batch_id": None, "selected_batch_id": None` even for exactly one open batch), and the template's "Далее" is gated only on `not show_empty`, not on a picked batch:
```html
{% if not show_empty %}
<button type="submit" hx-post="/m/writeoff/step/qty" hx-include="closest form">Далее</button>
{% endif %}
```
An operator can skip picking a batch entirely (including the single-open-batch case) and only hit `BATCH_REQUIRED_ERROR` from `app/services/writeoffs.py` after also filling in "Количество" and "Причина".
**Fix:** Same as WR-05 — gate the button on `selected_batch_id`:
```html
{% if not show_empty %}
<button type="submit"{% if not selected_batch_id %} disabled{% endif %} hx-post="/m/writeoff/step/qty" hx-include="closest form">Далее</button>
{% endif %}
```

## Info

### IN-01: Receipt batch-choice radios have no client-side forward guard

**File:** `app/templates/mobile_partials/receipts_step_batch.html:40-51`
**Issue:** Unlike every sibling wizard's batch-selection step, the receipt batch-choice radios have no `required` attribute, and — when open batches exist — none is pre-checked (only the zero-batches fallback auto-checks "Новая партия"). The operator can tap "Далее" through steps 3 and 4 with `batch_choice=""`, and only learns of the omission at final submit via the server-side batch-choice error in `app/services/receipts.py`. Functionally safe (no bad write), but an avoidable round trip inconsistent with this phase's own established pattern (see also WR-05/WR-06).
**Fix:** Add `required` to both radio groups, or disable the "Далее" button client-side until a `batch_choice` is picked, mirroring `corrections_step_batch.html`'s `{% if not selected_batch_id %} disabled{% endif %}`.

### IN-02: Quick-action links do not URL-encode `product.code`

**File:** `app/templates/mobile_partials/search_product_detail.html:19-20`
**Issue:** `href="/m/sales?code={{ product.code }}"` and the receipts equivalent rely on Jinja's HTML autoescape only. A code containing `&`, `#`, `%`, or `+` would produce a malformed query string when the browser navigates the link (e.g. an embedded `&` starts a new, bogus query parameter instead of remaining part of `code`). Low real-world likelihood given typical Oriflame numeric codes, but it is a correctness gap.
**Fix:** `href="/m/sales?code={{ product.code | urlencode }}"` (Jinja's built-in `urlencode` filter).

### IN-03: Stale "Оформить продажу" button after client-side basket removal

**File:** `app/templates/mobile_partials/sale_basket.html:29-30, 40-44`
**Issue:** Each basket line's "Удалить" button is a pure client-side `hx-on:click="this.closest('.mobile-card').remove()"` (no server round trip). The "Оформить продажу" button's visibility is fixed at render time by `{% if lines %}` — it does not react to cards being removed afterward. If the operator deletes the only/last line, the checkout button remains visible and clickable, submitting an empty basket. Harmless (server-side `EMPTY_BASKET_ERROR` in `app/services/sales.py` blocks it), but a confusing dead UI state — the operator sees a "ready to submit" checkout button pointing at nothing.
**Fix:** Wrap cards and checkout button in one client-observed container, or re-check basket emptiness via a small script/`hx-on` on the "Удалить" handler that also toggles the checkout button.

---

_Reviewed: 2026-07-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
