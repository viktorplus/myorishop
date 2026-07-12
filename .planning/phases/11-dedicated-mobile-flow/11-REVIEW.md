---
phase: 11-dedicated-mobile-flow
reviewed: 2026-07-13T00:00:00Z
depth: standard
files_reviewed: 65
files_reviewed_list:
  - app/main.py
  - app/routes/mobile_corrections.py
  - app/routes/mobile_history.py
  - app/routes/mobile_home.py
  - app/routes/mobile_receipts.py
  - app/routes/mobile_reports.py
  - app/routes/mobile_returns.py
  - app/routes/mobile_sales.py
  - app/routes/mobile_search.py
  - app/routes/mobile_transfers.py
  - app/routes/mobile_writeoff.py
  - app/static/style.css
  - app/templates/base.html
  - app/templates/mobile_base.html
  - app/templates/mobile_pages/corrections.html
  - app/templates/mobile_pages/history.html
  - app/templates/mobile_pages/home.html
  - app/templates/mobile_pages/receipts.html
  - app/templates/mobile_pages/reports_expiry.html
  - app/templates/mobile_pages/sales.html
  - app/templates/mobile_pages/search.html
  - app/templates/mobile_pages/transfers.html
  - app/templates/mobile_pages/writeoff.html
  - app/templates/mobile_partials/batch_card_picker.html
  - app/templates/mobile_partials/corrections_name_echo.html
  - app/templates/mobile_partials/corrections_step_batch.html
  - app/templates/mobile_partials/corrections_step_mode.html
  - app/templates/mobile_partials/corrections_step_value.html
  - app/templates/mobile_partials/corrections_warning.html
  - app/templates/mobile_partials/history_cards.html
  - app/templates/mobile_partials/history_load_more.html
  - app/templates/mobile_partials/receipts_step_batch.html
  - app/templates/mobile_partials/receipts_step_confirm.html
  - app/templates/mobile_partials/receipts_step_details.html
  - app/templates/mobile_partials/return_confirm.html
  - app/templates/mobile_partials/sale_basket.html
  - app/templates/mobile_partials/sale_step_batch.html
  - app/templates/mobile_partials/sale_step_product.html
  - app/templates/mobile_partials/sale_step_qty_price.html
  - app/templates/mobile_partials/sale_warning.html
  - app/templates/mobile_partials/search_product_detail.html
  - app/templates/mobile_partials/search_results.html
  - app/templates/mobile_partials/transfers_step_batch.html
  - app/templates/mobile_partials/transfers_step_dest.html
  - app/templates/mobile_partials/transfers_warning.html
  - app/templates/mobile_partials/writeoff_batch_wrap.html
  - app/templates/mobile_partials/writeoff_name_fill.html
  - app/templates/mobile_partials/writeoff_step_batch.html
  - app/templates/mobile_partials/writeoff_step_qty.html
  - app/templates/mobile_partials/writeoff_step_reason.html
  - app/templates/mobile_partials/writeoff_warning.html
  - pyproject.toml
  - tests/conftest.py
  - tests/test_mobile_corrections.py
  - tests/test_mobile_foundation.py
  - tests/test_mobile_history.py
  - tests/test_mobile_home.py
  - tests/test_mobile_receipts.py
  - tests/test_mobile_reports.py
  - tests/test_mobile_returns.py
  - tests/test_mobile_sales.py
  - tests/test_mobile_search.py
  - tests/test_mobile_transfers.py
  - tests/test_mobile_wiring.py
  - tests/test_mobile_writeoff.py
findings:
  critical: 2
  warning: 3
  info: 1
  total: 6
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-07-13
**Depth:** standard
**Files Reviewed:** 65
**Status:** issues_found

## Summary

Reviewed the full dedicated-mobile-flow (Phase 11) surface: 10 mobile routers, 22 mobile templates, `app/main.py` wiring, `style.css`, and all 13 mobile test modules. The Sale/Приход/Списание/Перемещение/Возврат/История/Поиск/Отчёты wizards are internally consistent, re-validate every client-supplied `batch_id` server-side, and reuse the existing `register_*` write paths correctly — most of the phase is solid and well-tested.

The **Корректировка (corrections) wizard is the outlier**: it diverges from the pattern every sibling wizard follows, and does so in two separate, provable ways — both untested by the existing suite. One corrupts the DOM on the wizard's most common success path (every completed correction) and one dead-ends the operator when an over-removal warning fires. Both are classified Critical. A handful of smaller consistency/robustness issues are listed as Warnings.

## Critical Issues

### CR-01: Corrections wizard returns a full HTML document where an htmx fragment is required — corrupts the DOM on every successful save and on "product not found"

**File:** `app/routes/mobile_corrections.py:65-67` and `app/routes/mobile_corrections.py:220-226`

**Issue:** Every step-2/3/4 form in the corrections wizard is htmx-driven with `hx-target="#corrections-step-wrap"` and `hx-swap="outerHTML"` (see `mobile_partials/corrections_step_value.html:13-17` and `mobile_partials/corrections_warning.html:13-17`). An `outerHTML` swap takes the *entire* raw response body and uses it to replace the target element — it does not search the response for a matching id.

Two response paths in this router return the full `mobile_pages/corrections.html` page (which `{% extends "mobile_base.html" %}`, i.e. a complete `<!doctype html><html><head>...<body>...` document) instead of a step fragment, even though the request that triggers them is an htmx `outerHTML` swap:

1. `mobile_correction_step_batch` (product-not-found branch, line 67) — reached from step 1's `hx-post="/m/corrections/step/batch"` (see `mobile_pages/corrections.html:23-26`).
2. `mobile_correction_create` (the final, successful save, line 226) — reached from step 4's `hx-post="/m/corrections"` (see `mobile_partials/corrections_step_value.html:13-17` and `corrections_warning.html:13-17`).

Per the WHATWG HTML fragment-parsing algorithm, when a full document string is used to set an element's `outerHTML`, the browser strips the `<html>`/`<head>`/`<body>` tags but still inserts their *contents* (a second `<meta>`, a second `<link rel="stylesheet">`, a second `<script src="htmx.min.js">`, and critically a second nested `<main class="mobile-shell">` with its own "← Главная" back link) directly into the surrounding DOM in place of `#corrections-step-wrap`. This means **every successful correction** (the happy path) and **every "product not found" retry** renders duplicated/broken markup instead of the intended step fragment — this is not a rare edge case, it is the primary success path of the entire wizard.

Contrast with every sibling wizard, which returns a bare fragment (no `{% extends %}`) for its htmx-swapped success/error responses: `mobile_partials/sale_step_product.html`, `mobile_partials/receipts_step_confirm.html`, `mobile_partials/transfers_step_dest.html` all do this correctly. Only corrections gets it wrong.

This is untested: `tests/test_mobile_corrections.py` only asserts substrings (`"Корректировка сохранена" in response.text`), which still pass even though the response is a full document, so the existing suite does not catch the structural corruption. There is also no test at all for the not-found branch.

As a secondary, smaller inconsistency: the not-found branch also returns HTTP 200 instead of 422 (every sibling "not found" branch — `mobile_sale_step_product`, `mobile_writeoff_step_batch` — returns 422).

**Fix:** Return a step fragment, not the full page, for both branches — e.g. a small `corrections_not_found.html` partial rooted at `<div id="corrections-step-wrap">` (mirroring the `not_found` block already inside `mobile_pages/corrections.html`), and a `corrections_success.html` partial for the save-success screen. Reserve `mobile_pages/corrections.html` for the plain-GET, non-htmx entry point only (`mobile_correction_start`, line ~32-35, which is correct as-is). Also set `status_code=422` on the not-found response to match sibling wizards.

```python
# app/routes/mobile_corrections.py
if product is None:
    context = {"code": code_clean, "not_found": True}
    return templates.TemplateResponse(
        request, "mobile_partials/corrections_not_found.html", context, status_code=422
    )
...
context = {"saved": {"name": result["product"].name, "new_qty": result["new_qty"]}}
return templates.TemplateResponse(request, "mobile_partials/corrections_success.html", context)
```

---

### CR-02: Corrections over-removal warning is a dead end — no editable fields, no way back, only "force through"

**File:** `app/templates/mobile_partials/corrections_warning.html` (whole file), rendered from `app/routes/mobile_corrections.py:196-206`

**Issue:** When `register_correction` returns `oversell` (the operator tried to remove more than the batch has — a warn-but-allow guardrail, zero writes so far), the route returns `mobile_partials/corrections_warning.html` standalone. Unlike every sibling wizard's oversell warning, this template does **not** include the underlying editable step form — it hand-rolls its own copy of step 4 with `value` and `note` as **hidden** inputs (lines 18-22: `<input type="hidden" name="value" ...>`, `<input type="hidden" name="note" ...>`), not the `type="text"` inputs `corrections_step_value.html` normally renders.

The only two controls offered are:
- "Сохранить всё равно" — resubmits the exact same (over-limit) value with `confirm=1`.
- "Вернуться к форме" — a client-side `hx-on:click` that only removes the `#corrections-warning` message div. Since the surrounding form's `value`/`note` inputs are `type="hidden"`, dismissing the warning leaves the operator looking at a bare "Значение" screen with **no visible or editable field at all** — just the (now-message-less) form and its submit button.

There is no "Назад" link in this partial (contrast every other step, which has `<a class="mobile-back" href="/m/corrections">`). The operator cannot revise the value, cannot see what they typed, and cannot navigate back into the wizard — the only way out is to force through the over-removal or to manually reload `/m/corrections` from scratch (losing the picked product/batch/mode).

Compare to the pattern used correctly elsewhere in this same phase:
- `sale_warning.html` includes the full editable `sale_basket.html` below the warning.
- `writeoff_warning.html` is included *inside* `writeoff_step_reason.html`, above the still-editable reason/note fields.
- `transfers_warning.html` is included *inside* `transfers_step_dest.html`, above the still-editable warehouse/qty fields.
- Desktop's own `partials/correction_oversell.html` is included inside the still-fully-editable `partials/correction_form.html` (see `app/routes/corrections.py:159-170`).

Corrections is the only wizard (mobile or desktop) where the oversell warning replaces the editable form instead of augmenting it. This is untested — `tests/test_mobile_corrections.py::test_mobile_correction_over_removal_warns_then_confirms` only re-POSTs a hand-constructed form with the same value and `confirm=1`; it never inspects whether the returned HTML actually contains an editable/visible value field, so it does not catch this regression.

**Fix:** Re-render `mobile_partials/corrections_step_value.html` with the `oversell` context set (mirroring desktop's `correction_form.html` and `mobile_writeoff_step_reason.html`), including `corrections_warning.html`'s message above the *existing* visible `value`/`note` text inputs, instead of shipping a separate hand-written fragment with hidden fields:

```python
# app/routes/mobile_corrections.py
if result and result.get("oversell"):
    context = {
        "oversell": result["oversell"],
        "form": form_echo,
        "code": code.strip(),
        "batch_id": batch_id.strip(),
        "batch_qty": batch_qty,
        "mode": mode or "count",
    }
    return templates.TemplateResponse(
        request, "mobile_partials/corrections_step_value.html", context
    )
```
...and add `{% if oversell %}{% include "mobile_partials/corrections_warning.html" %}{% endif %}` near the top of `corrections_step_value.html`'s content (removing the duplicated wrapper/hidden-fields from `corrections_warning.html` itself, keeping only the message + buttons), matching `writeoff_step_reason.html`'s shape.

## Warnings

### WR-01: `mobile_sale_create`'s exception handler is missing the defensive `session.rollback()` every sibling create route has

**File:** `app/routes/mobile_sales.py:294-302`

**Issue:** `mobile_receipt_create`, `mobile_writeoff_submit`, `mobile_correction_create`, and `transfers_create` all call `session.rollback()` as the first line of their `except Exception:` block, with an explicit comment in `mobile_returns.py:123-126` explaining why: "an unexpected failure may have left the session needing rollback ... any further query below would otherwise raise an unhandled `PendingRollbackError` instead of this graceful 422." `mobile_sale_create` is missing this call, even though its own except block (line 298) immediately runs further queries via `_basket_lines(session, ...)`.

`register_sale` (`app/services/sales.py:250-272`) already rolls back internally for `IntegrityError`/`ValueError` raised during its own write loop, which covers the most common failure mode — but any *other* exception type raised after a partial flush (e.g. from `record_operation`'s other guard paths, or a future change to `register_sale`) would leave the session's transaction unrollable, and the `_basket_lines` call on line 298 would then raise a second, uncaught `PendingRollbackError`, producing the raw 500 the `# noqa: BLE001 — UI-SPEC: block error, never a raw 500` comment on line 294 explicitly says must never happen.

**Fix:**
```python
except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
    session.rollback()
    logger.exception("register_sale failed")
    ...
```

### WR-02: `hx-vals` JSON built by raw Jinja string interpolation is not JSON-safe for values containing a double quote

**File:** `app/templates/mobile_partials/batch_card_picker.html:43`, `app/templates/mobile_partials/transfers_step_batch.html:23`, `app/templates/mobile_partials/transfers_step_dest.html:57`

**Issue:** Each of these builds an `hx-vals` attribute by hand, e.g.:
```jinja
hx-vals='{"batch_id": "{{ b.id }}", "code": "{{ code | default('') }}"...}'
```
Jinja's autoescape converts a literal `"` inside `code` to `&quot;` in the emitted HTML attribute, but the browser decodes that entity back to `"` when reading the attribute value — so a product code containing a double quote (nothing prevents an operator from typing one into the code/search field) breaks the JSON structure htmx parses from `hx-vals`, at minimum breaking the batch-pick round trip and at worst letting the decoded string inject additional JSON keys. Server-side ownership re-validation (`candidate.product_id == product.id`) limits the security blast radius, but the robustness issue (wizard breaking on a quote character) is real. This is a pre-existing pattern copied verbatim from `app/templates/partials/batch_picker.html:47` (not a new defect), but this phase propagates it into three more call sites.

**Fix:** Use Jinja's `tojson` filter instead of manual concatenation, e.g. `hx-vals="{{ {'batch_id': b.id, 'code': code} | tojson }}"`, which correctly escapes for both JSON and the HTML attribute context.

### WR-03: `mobile_correction_step_batch`'s not-found response uses HTTP 200 instead of 422

**File:** `app/routes/mobile_corrections.py:65-67`

**Issue:** Every other "code not found" branch in this phase returns 422 (`mobile_sale_step_product` via `PRODUCT_NOT_FOUND_TMPL`, `mobile_writeoff_step_batch`). The corrections equivalent returns the default 200. Minor, but breaks the otherwise-consistent status-code contract this phase establishes, and combined with `htmx-config`'s per-status-code swap rules (`mobile_base.html:12-13`), a future change relying on 422 to distinguish error responses would silently misbehave here.

**Fix:** Add `status_code=422` to the `TemplateResponse` call (see CR-01's fix, which folds this in).

## Info

### IN-01: `mobile_correction_step_batch`/`mobile_correction_create` full-page responses are entirely untested

**File:** `tests/test_mobile_corrections.py`

**Issue:** No test in this file exercises the product-not-found branch of `POST /m/corrections/step/batch`, and the existing over-removal test (`test_mobile_correction_over_removal_warns_then_confirms`) only checks for a text substring rather than parsing/validating the returned fragment's structure (e.g. absence of `<!doctype html>`/`<html>` in an htmx fragment response, presence of a visible `<input type="text" name="value">`). Both gaps directly correspond to CR-01 and CR-02 above and would have caught them.

**Fix:** Add a regression test asserting `"<!doctype html>" not in response.text` (or equivalent) for every htmx-fragment-returning mobile endpoint, and a test asserting the oversell-warning response contains an editable (non-hidden) `value` input.

---

_Reviewed: 2026-07-13_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
