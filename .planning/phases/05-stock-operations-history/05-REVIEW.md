---
phase: 05-stock-operations-history
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 34
files_reviewed_list:
  - app/main.py
  - app/models.py
  - app/routes/__init__.py
  - app/routes/corrections.py
  - app/routes/history.py
  - app/routes/returns.py
  - app/routes/writeoffs.py
  - app/services/corrections.py
  - app/services/operations.py
  - app/services/returns.py
  - app/services/writeoffs.py
  - app/static/style.css
  - app/templates/base.html
  - app/templates/pages/correction_form.html
  - app/templates/pages/history.html
  - app/templates/pages/home.html
  - app/templates/pages/writeoff_form.html
  - app/templates/partials/correction_form.html
  - app/templates/partials/correction_lookup.html
  - app/templates/partials/history_filters.html
  - app/templates/partials/history_rows.html
  - app/templates/partials/purchase_history.html
  - app/templates/partials/recent_sales.html
  - app/templates/partials/return_form.html
  - app/templates/partials/writeoff_form.html
  - app/templates/partials/writeoff_lookup.html
  - app/templates/partials/writeoff_oversell.html
  - app/templates/partials/writeoff_rows.html
  - tests/test_corrections.py
  - tests/test_history.py
  - tests/test_ledger.py
  - tests/test_returns.py
  - tests/test_smoke.py
  - tests/test_writeoffs.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-10
**Depth:** standard
**Files Reviewed:** 34
**Status:** issues_found

## Summary

Phase 5 adds three new write verticals (write-off, sale-linked return, stock
correction) plus the read-only `/history` ledger browser, all built on the
existing single-write-path (`record_operation`) and RU-error-partial
conventions established in earlier phases. The service-layer validation
(allow-lists, zero-write-on-error, capped returns, oversell warn-but-allow)
is implemented carefully and matches its own test suite.

However, three genuine correctness/completeness defects were found that
would surface in real usage and are not caught by the current tests (which
only exercise `TestClient` HTTP calls, not the client-side htmx swap
behavior or UI navigation):

1. The new `/writeoff` page has no link anywhere in the rendered UI — it is
   only reachable by typing the URL directly.
2. `GET /returns`'s explicit 404 "origin not found" branch is silently
   swallowed by the app's own htmx `responseHandling` config, so the
   dedicated RU error message is never shown to the user.
3. `POST /returns`'s broad exception handler re-queries the same
   (potentially broken) SQLAlchemy session, risking an unhandled 500 instead
   of the graceful error page the code is explicitly trying to guarantee.

Several lower-severity robustness/consistency gaps are listed under
Warnings/Info.

## Critical Issues

### CR-01: `/writeoff` page has no navigation entry point anywhere in the UI

**File:** `app/templates/base.html:17-26`, also `app/templates/pages/home.html:9`
**Issue:** The main nav bar lists Главная/Товары/Приход/Продажи/Покупатели/История/Справочник/Резервные копии, but has no link to `/writeoff`. `home.html` links to `/corrections` and `/history` but not `/writeoff`. Grepping every template in the project for `/writeoff` (excluding the write-off page/partials themselves) turns up zero links — the write-off feature (OPS-01), fully implemented and tested, is unreachable through the running application except by typing the URL directly into the browser.
**Fix:**
```html
<!-- app/templates/base.html -->
<a href="/writeoff"{% if request.url.path.startswith("/writeoff") %} class="active"{% endif %}>Списание</a>
```
Add this next to the other primary nav links (and consider whether `/corrections` deserves the same top-level treatment instead of only a small text link on the home page).

### CR-02: `GET /returns` 404 "origin not found" response is silently discarded by htmx

**File:** `app/routes/returns.py:88-92`, `app/templates/base.html:9-10`
**Issue:** `base.html`'s `htmx-config` `responseHandling` only special-cases `204` and `422` for swapping; everything else matching `[45]..` (i.e. every 4xx/5xx, including 404) gets `swap:false, error:true`. `GET /returns` is invoked exclusively via `hx-get="/returns?..." hx-target="#return-slot" hx-swap="innerHTML"` from `recent_sales.html`/`purchase_history.html`. When `_resolve_origin` can't find a valid origin op, the route returns the rendered error partial with `status_code=404` — but per the htmx config this response is never swapped into `#return-slot`; it only fires a silent `htmx:responseError` event. The user clicks "Вернуть" and nothing visibly happens — the `ORIGIN_NOT_FOUND_ERROR` message ("Исходная продажа не найдена.") is built and rendered server-side but never reaches the screen. This directly contradicts the app's own documented UI-SPEC ("never a raw 500 / never silently discarded", see the CR-01 comment already in `base.html` about 422). Every other route in the codebase that needs an htmx-swappable error response uses `422` (which IS allowlisted); `returns.py` is the only one using `404` for a swappable body.
**Fix:** Either change the status code to `422` (matching the sitewide convention for htmx-swappable errors) or add `404` to `htmx-config`'s allowed-swap patterns:
```python
# app/routes/returns.py:91 — align with the rest of the app's convention
return templates.TemplateResponse(
    request, "partials/return_form.html", context, status_code=422
)
```

### CR-03: `POST /returns` exception handler can itself crash with `PendingRollbackError`

**File:** `app/routes/returns.py:107-120`, `app/services/returns.py:91-110`
**Issue:** `register_return()` only rolls back the session for `ValueError` and `IntegrityError` raised by `record_operation`. Any other exception (e.g. `OperationalError` from a locked/busy SQLite file, or any unexpected bug) propagates uncaught out of the service and is caught by the route's bare `except Exception:`. That handler then calls `_origin_context(session, origin, {"form": SAVE_FAILED_ERROR})`, which issues fresh `SELECT`s (`sold_qty`, `returnable_qty`) on the *same* session. Per SQLAlchemy semantics, a session whose flush/commit failed with an exception is left in a state requiring an explicit `session.rollback()` before it can be used again — any further query raises `sqlalchemy.exc.PendingRollbackError`. That error is not caught anywhere in this code path, so it would propagate out as an unhandled 500 — exactly what the surrounding `# noqa: BLE001 — UI-SPEC: block error, never a raw 500` comment says must never happen. (`corrections.py`/`writeoffs.py`'s equivalent exception handlers are safe only because their error-context builders don't touch the DB at all.)
**Fix:**
```python
# app/routes/returns.py
try:
    result, errors = register_return(session, origin_op_id=origin_op_id, qty_raw=qty)
except Exception:  # noqa: BLE001
    logger.exception("register_return failed")
    session.rollback()  # <-- add this before re-querying the same session
    context = (
        _origin_context(session, origin, {"form": SAVE_FAILED_ERROR})
        if origin_valid
        else _empty_context(origin_op_id, {"form": SAVE_FAILED_ERROR})
    )
    ...
```

## Warnings

### WR-01: `/history` "Показать ещё" control gets stuck in place after the first click

**File:** `app/templates/partials/history_rows.html:44-52`, `app/routes/history.py:47-49`
**Issue:** The "Показать ещё" button uses `hx-target="#history-tbody" hx-swap="beforeend"`, while the response's trailing `<tr id="load-more">` row is marked `hx-swap-oob="true"`. htmx strips oob-marked elements out of the response before applying the main swap, so only the plain data `<tr>`s get appended via `beforeend` — i.e. appended *after* whatever is currently the last child of `#history-tbody`, which is the (in-place-updated, not moved) `<tr id="load-more">` row itself. After the first click, the load-more control is left sandwiched where it was originally rendered, and every subsequent batch of rows keeps stacking below it instead of above it — the control never returns to the bottom of the list.
**Fix:** Target the control row itself and insert new rows immediately before it, e.g.:
```html
<button ... hx-get="/history?...&page={{ page + 1 }}"
        hx-target="#load-more" hx-swap="beforebegin" hx-disabled-elt="this">Показать ещё</button>
```
(keeping the oob-marked `<tr id="load-more">` in the response to replace/remove the control once `has_next` becomes false).

### WR-02: `writeoff_rows.html` doesn't guard against a falsy/None `payload`

**File:** `app/templates/partials/writeoff_rows.html:28-30`
**Issue:** `{{ WRITEOFF_REASONS.get(r.op.payload.reason_code, r.op.payload.reason_code) }}` assumes `r.op.payload` is always a dict. `history_rows.html` (line 28) defensively checks `r.op.type == "writeoff" and r.op.payload` first; this partial does not. Every write-off written through today's single write path always populates `payload`, so this is not currently reachable — but it is an inconsistent defensive posture between two templates rendering the same op type, and any future/legacy/synced row with `payload IS NULL` would raise a Jinja `UndefinedError` on `None.reason_code`, taking down the entire `/writeoff` page render (not just one row).
**Fix:**
```html
{% if r.op.payload %}
{{ WRITEOFF_REASONS.get(r.op.payload.reason_code, r.op.payload.reason_code) }}{% if r.op.payload.note %} — {{ r.op.payload.note }}{% endif %}
{% else %}<span class="muted">—</span>{% endif %}
```

### WR-03: Bare `except Exception` in write routes never rolls back the session

**File:** `app/routes/corrections.py:76-87`, `app/routes/writeoffs.py:82-92`, `app/routes/returns.py:109-120`
**Issue:** All three POST routes catch any exception from their service call and render an error partial, but none call `session.rollback()` first. It happens to be harmless today for corrections/writeoffs (their error contexts don't touch the session again), and is the direct cause of CR-03 for returns. This is a systemic gap: any future change to these error-context builders (e.g. adding a "show current stock" hint on save-failure) would silently reintroduce CR-03-style crashes.
**Fix:** Add `session.rollback()` as the first line of each of these three `except Exception:` blocks, defensively, regardless of whether the current context builder queries the DB.

### WR-04: `/history` product filter dropdown only lists active products

**File:** `app/services/operations.py:51-57`
**Issue:** `filter_products()` filters `Product.deleted_at.is_(None)`. Operations recorded against a product that is later soft-deleted remain visible in the unfiltered `/history` view (correct — the ledger join has no deleted-filter), but the operator has no way to *filter down to* that product's history once it's soft-deleted, since it no longer appears as an `<option>` in the "Товар" select.
**Fix:** Either include soft-deleted products in the filter list (perhaps visually marked, e.g. "Название (архив)"), or accept this as a known limitation and document it.

### WR-05: `corrections.py` "delta" mode silently reclassifies `-0` as a generic "nothing changed" error

**File:** `app/services/corrections.py:70-83`
**Issue:** Input `"-0"` passes the delta-mode format check (`body = "0"`, `"0".isdigit()` is `True`), producing `qty_delta = int("-0") == 0`. It then falls into the `qty_delta == 0` branch and returns `ZERO_NET_ERROR` ("Остаток не изменился — нечего сохранять.") instead of `DELTA_QTY_ERROR` ("Укажите изменение — целое число, отличное от нуля."). Functionally harmless (the write is still correctly blocked), but the message shown doesn't match the more specific validation rule that's supposed to catch a "must be nonzero" input.
**Fix:** Not required to block ship; if message precision matters, special-case `"-0"`/`"+0"` before the generic zero-delta check.

## Info

### IN-01: `return_form.html` uses a `max` attribute on a `type="text"` input

**File:** `app/templates/partials/return_form.html:24`
**Issue:** `<input type="text" id="qty" name="qty" inputmode="numeric" value="{{ remaining }}" max="{{ remaining }}">` — the HTML `max` attribute has no effect on `type="text"` inputs (only on `number`/`range`/`date`-family inputs); it's a no-op here. Server-side validation is correctly still authoritative, so this is cosmetic only.
**Fix:** Remove the dead `max` attribute, or switch to `type="number"` with equivalent `inputmode`/pattern handling if client-side capping is desired.

### IN-02: `history.py` route parameter `type` shadows the Python builtin

**File:** `app/routes/history.py:16`
**Issue:** `def history_page(request: Request, type: str = "", ...)` shadows the built-in `type()` within the function body. No current bug (the builtin isn't needed in this function), but it's a readability/naming smell that could bite a future edit.
**Fix:** Rename to `type_` or `op_type` and update the corresponding query-string handling (`Form`/`Query` alias can keep the wire name `type` via `Query(alias="type")` if the querystring key must stay `type`).

### IN-03: `return_create` duplicates the origin/validity check `register_return` already performs

**File:** `app/routes/returns.py:104-105`, `app/services/returns.py:72-74`
**Issue:** The route independently re-derives `origin_valid` by fetching the same `Operation` and re-checking `type == "sale" and sale_id is not None` before calling `register_return`, which does the identical check internally. This duplication (not a functional bug today) risks the two copies drifting out of sync if one is updated without the other.
**Fix:** Have `register_return` (or a small shared helper) return enough information for the route to build its error context without re-implementing the validity check.

---

_Reviewed: 2026-07-10_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
