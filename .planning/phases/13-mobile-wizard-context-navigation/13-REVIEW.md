---
phase: 13-mobile-wizard-context-navigation
reviewed: 2026-07-14T00:00:00Z
depth: standard
files_reviewed: 30
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
  - app/templates/mobile_partials/corrections_step_batch.html
  - app/templates/mobile_partials/corrections_step_mode.html
  - app/templates/mobile_partials/corrections_step_product.html
  - app/templates/mobile_partials/corrections_step_value.html
  - app/templates/mobile_partials/receipts_step_batch.html
  - app/templates/mobile_partials/receipts_step_product.html
  - app/templates/mobile_partials/sale_basket.html
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
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-07-14
**Depth:** standard
**Files Reviewed:** 30
**Status:** issues_found

## Summary

Reviewed all five mobile wizard routers (corrections, receipts, sales, transfers, write-off), their step templates, the shared `_wizard_header.html` contract, and the corresponding test suites. No security vulnerabilities were found: every reviewed template relies on Jinja autoescape with no `|safe` usage, batch/product ownership is consistently re-validated server-side before any client-supplied id is trusted (`T-09-08`/`T-11-x` precedents are followed correctly), and every write path wraps the service call in `except Exception` with a defensive `session.rollback()` before re-rendering — no bare 500s, no unhandled `PendingRollbackError`.

The issues found are all in the "hidden-field carry-forward" contract this phase is explicitly built around (RESEARCH Pattern 1: "no server-side wizard session — state travels only via posted/echoed fields"). Several back-navigation and forward-navigation paths silently drop state that sibling wizards, and the same wizard's own hidden fields, imply should be preserved. None of these cause bad writes (server-side validation in the `app/services/*` layer still catches invalid states before any row is written), but they are real regressions against the pattern this phase's own code comments describe, and are untested (no test in the reviewed suites exercises "Назад" state preservation for warehouse_id / mode / write-off code).

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

### WR-04: Transfer batch card shows a blank "Склад:" line when the source warehouse has been deactivated

**File:** `app/templates/mobile_partials/transfers_step_batch.html:37`, `app/routes/mobile_transfers.py:43-45`
**Issue:** `_warehouse_names()` maps only `active_warehouses(session)` (`deleted_at IS NULL`) to their names. The batch card renders `<p>Склад: {{ warehouse_names.get(b.warehouse_id, "") }}</p>` with an empty-string fallback. If a batch's warehouse has since been soft-deleted/deactivated while the batch is still open (a realistic scenario — deactivating a location doesn't retroactively close its batches), the card silently shows "Склад: " with nothing after the colon instead of the real (deactivated) warehouse name. Contrast with `_wizard_header.html`'s explicit contract ("must be `None`/absent, never `''`, to correctly omit their line") which every other wizard's carried-warehouse display honors correctly via `dict.get(...)` returning `None`.
**Fix:** Either include inactive warehouses in a name-lookup map used only for display (a separate all-warehouses id->name map, not gated on `active_warehouses`), or fall back to a non-empty placeholder, e.g. `warehouse_names.get(b.warehouse_id, "—")`.

## Info

### IN-01: Receipt batch-choice radios have no client-side forward guard

**File:** `app/templates/mobile_partials/receipts_step_batch.html:40-51`
**Issue:** Unlike every sibling wizard's batch-selection step (e.g. corrections disables its "Далее" button until `selected_batch_id` is set), the receipt batch-choice radios have no `required` attribute, and — when open batches exist — none is pre-checked (only the zero-batches fallback auto-checks "Новая партия"). The operator can tap "Далее" through steps 3 and 4 with `batch_choice=""`, and only learns of the omission at final submit via the server-side `BATCH_CHOICE_ERROR` (`app/services/receipts.py`). Functionally safe (no bad write), but an avoidable round trip inconsistent with this phase's own established pattern.
**Fix:** Add `required` to both radio groups, or disable the "Далее" button client-side until a `batch_choice` is picked, mirroring `corrections_step_batch.html`'s `{% if not selected_batch_id %} disabled{% endif %}`.

### IN-02: Quick-action links do not URL-encode `product.code`

**File:** `app/templates/mobile_partials/search_product_detail.html:19-20`
**Issue:** `href="/m/sales?code={{ product.code }}"` and the receipts equivalent rely on Jinja's HTML autoescape only. A code containing `&`, `#`, `%`, or `+` would produce a malformed query string when the browser navigates the link (e.g. an embedded `&` starts a new, bogus query parameter instead of remaining part of `code`). Low real-world likelihood given typical Oriflame numeric codes, but it is a correctness gap.
**Fix:** `href="/m/sales?code={{ product.code | urlencode }}"` (Jinja's built-in `urlencode` filter).

### IN-03: Stale "Оформить продажу" button after client-side basket removal

**File:** `app/templates/mobile_partials/sale_basket.html:28-43`
**Issue:** "Удалить" removes a basket card purely client-side (`hx-on:click="this.closest('.mobile-card').remove()"`), but the "Оформить продажу" button's visibility is fixed at render time by `{% if lines %}` — it does not react to cards being removed afterward. If the operator deletes the only line, the checkout button remains visible and clickable, submitting an empty basket. Harmless (server-side `EMPTY_BASKET_ERROR` in `app/services/sales.py` blocks it), but a confusing dead UI state — the operator sees a "success-looking" checkout button pointing at nothing.
**Fix:** Wrap both the cards and the checkout button in one client-observed container, or re-check basket emptiness via a small script/`hx-on` on the "Удалить" handler that also toggles the checkout button.

---

_Reviewed: 2026-07-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
