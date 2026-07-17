---
phase: 22-sales-page-rebuild
reviewed: 2026-07-17T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - app/routes/mobile_sales.py
  - app/routes/sales.py
  - app/services/sales.py
  - app/static/sale-total.js
  - app/templates/base.html
  - app/templates/mobile_base.html
  - app/templates/mobile_partials/batch_card_picker.html
  - app/templates/mobile_partials/customer_picker.html
  - app/templates/mobile_partials/sale_basket.html
  - app/templates/mobile_partials/sale_customer.html
  - app/templates/partials/recent_sales.html
  - app/templates/partials/sale_customer.html
  - app/templates/partials/sale_form.html
  - app/templates/partials/sale_row.html
  - tests/test_core.py
  - tests/test_mobile_sales.py
  - tests/test_sales.py
  - tests/test_sales_total.py
findings:
  critical: 1
  warning: 4
  info: 1
  total: 6
status: issues_found
---

# Phase 22: Code Review Report

**Reviewed:** 2026-07-17
**Depth:** standard
**Files Reviewed:** 17 (+ 1 dependency file inspected for cross-reference: `app/templates/partials/batch_picker.html`)
**Status:** issues_found

## Summary

Reviewed the sale-basket rebuild (desktop `app/routes/sales.py` + `app/services/sales.py`, and the mobile wizard `app/routes/mobile_sales.py`), their templates, the advisory `sale-total.js` running total, and the associated test suites.

The core write path (`register_sale`) is solid: single-transaction all-or-nothing basket writes, per-batch oversell aggregation, per-line price-floor checks, and negative-price rejection are all correctly implemented and well covered by tests. The `basket-add`/wizard step machinery, batch-ownership re-validation (T-09-08 pattern), and the `_customer_context`/`_m_customer_context` chip-resolution builders are also correct.

However, the desktop route module (`app/routes/sales.py`) has a **real, provable robustness regression relative to its own mobile twin**: three of its `except Exception` handlers rebuild a response by re-querying the database WITHOUT first calling `session.rollback()`, even though the identical pattern was correctly fixed (with an explicit "WR-01" comment) in `app/routes/mobile_sales.py` for this exact phase. That fix was never backported to the desktop routes it mirrors, so the desktop error-handling path can itself raise an unhandled 500 in exactly the scenario it exists to guard against — directly contradicting the "UI-SPEC: block error, never a raw 500" contract stated in the same lines. Also found: a documented-but-broken JS money-parsing edge case, a missing error guard in the mobile customer-mode route, and an un-backported `hx-vals` JSON-injection fix in the desktop batch picker (already fixed in the mobile equivalent shipped this phase).

## Critical Issues

### CR-01: Desktop sale routes' exception handlers can crash with an unhandled 500 (missing `session.rollback()`)

**File:** `app/routes/sales.py:406-426` (`sale_customer_create`), `app/routes/sales.py:483-494` (`sale_customer_mode`), `app/routes/sales.py:546-563` (`sale_create`)

**Issue:** All three `except Exception:` blocks re-run a database query (`_customer_context(...)` → `get_customer` → `session.get()`, and/or `_build_lines(...)` → multiple `session.get`/`session.scalars` calls) to rebuild the error-response context — but none of them call `session.rollback()` first.

If the exception that triggered the handler was a SQLAlchemy/DBAPI-level failure (e.g. `OperationalError` from `"database is locked"` — a realistic scenario for this app: CLAUDE.md's own backup guidance is "copy the .db file while app is closed", implying a live-copy race is a real possibility with WAL mode), the `Session` is left in a state requiring rollback. The very next query issued inside the `except` block (via `_customer_context`/`_build_lines`) will then raise `sqlalchemy.exc.PendingRollbackError`, which is **not caught by this handler** (it only wraps the original `try`), so it propagates uncaught to FastAPI and produces a raw 500 — the exact outcome the comment on the same line explicitly says must never happen: `# noqa: BLE001 — UI-SPEC: block error, never a raw 500`.

This is provably a regression relative to this phase's own mobile module: `app/routes/mobile_sales.py`'s `mobile_sale_customer_create` (lines 158-167) and `mobile_sale_create` (lines 536-541) both call `session.rollback()` first, with an explicit comment:
```python
# WR-01 (mobile-specific): rollback FIRST — an unexpected failure
# may have left the session needing rollback (e.g. a failed
# flush/commit); a following query would otherwise raise an
# unhandled PendingRollbackError instead of this graceful 422.
session.rollback()
```
The label "mobile-specific" is misleading — the identical failure mode exists in the desktop routes that were never given the same fix.

**Fix:** Add `session.rollback()` as the first line of all three desktop `except Exception:` blocks, mirroring the mobile fix exactly:
```python
except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
    session.rollback()  # WR-01: rollback FIRST — see mobile_sales.py precedent
    logger.exception("register_sale failed")
    context = {
        **_customer_context(session, customer_mode, customer_id, new_customer_form),
        ...
    }
```
Apply the same one-line fix to `sale_customer_create` and `sale_customer_mode`.

## Warnings

### WR-01: `sale-total.js` rejects a trailing-separator price (`"5."`) that the server accepts, contradicting its own documented contract

**File:** `app/static/sale-total.js:36,46-56`

**Issue:** The file's header comment explicitly documents the accept-set parity contract: *"accepted here AND by server: `"7"`, `"12,50"`, `"12.50"`, `".5"`, `"5."`, `"12.505"`"*. `tests/test_core.py::test_to_cents_accept_set_boundaries` pins `("5.", 500)` as server-accepted. But `MONEY_RE = /^(?:\d+(?:[.,]\d+)?|[.,]\d+)$/` does **not** match `"5."` (or `"5,"`): the optional group `(?:[.,]\d+)?` requires at least one digit after the separator, so a trailing bare separator with no following digit fails the whole anchored match. Verified directly:
```python
import re
re.match(r'^(?:\d+(?:[.,]\d+)?|[.,]\d+)$', "5.")  # -> None
```
Effect: an operator who types a price as `"5."` (a value the server's `to_cents` happily parses to 500 cents) will see the advisory running total flip the `#sale-total-warning` ("итог неполный: проверьте кол-во и цену") even though the value is complete and will be accepted on submit. This is not a data-loss bug (the server remains authoritative and `register_sale` will accept the value), but it is a functional defect that contradicts the file's own documented accept-set.

**Fix:** Extend the regex to allow a bare trailing separator, e.g.:
```js
const MONEY_RE = /^(?:\d+(?:[.,]\d*)?|[.,]\d+)$/;
```
(changing `\d+` to `\d*` inside the optional fractional group so `"5."`/`"5,"` matches; `moneyToCents`'s existing `(parts[1] || "")` handling already tolerates an empty fractional part correctly.)

### WR-02: Mobile `customer-mode` route has no error handling, unlike its desktop twin

**File:** `app/routes/mobile_sales.py:96-128` (`mobile_sale_customer_mode`)

**Issue:** Every other write/lookup-adjacent route in both `mobile_sales.py` and `sales.py` wraps its `_customer_context`/`_m_customer_context` call in a `try/except Exception` that logs and returns a graceful 422 (`SAVE_FAILED_ERROR`) instead of letting an unexpected exception propagate — this is the established, repeatedly-documented "UI-SPEC: block error, never a raw 500" convention (see `sale_customer_mode` in `sales.py:466-495`, `mobile_sale_customer_create` and `sale_customer_create`). `mobile_sale_customer_mode` is the sole exception: it calls `_m_customer_context(...)` directly with no guard at all. Any exception raised inside it (e.g. from `get_customer`) will propagate as a raw 500, breaking the pattern the rest of the module follows.

**Fix:** Wrap the context-building block in the same `try/except Exception` pattern used by `sale_customer_mode` (desktop) — and remember to apply CR-01's `session.rollback()` fix inside the `except` block too, since this route performs a follow-up query on the fallback path.

### WR-03: Desktop `batch_picker.html` still has the `hx-vals` quote-breaking bug that was fixed in this phase's mobile equivalent

**File:** `app/templates/partials/batch_picker.html:47` (included by the in-scope `app/templates/partials/sale_row.html:60-61`)

**Issue:** `batch_picker.html` builds its `hx-vals` attribute via manual string concatenation:
```jinja
hx-vals='{"row": "{{ row_id | default('') }}", "batch_id": "{{ b.id }}", "code": "{{ code | default('') }}"}'
```
`code` here is the operator/import-controlled `Product.code` value (free text, not restricted to a safe character set as far as this review can verify). This phase's new `app/templates/mobile_partials/batch_card_picker.html` (in the reviewed file set) documents that this exact pattern is a **known, previously-shipped defect**:
```jinja
{# WR-02: tojson (not manual string concatenation) correctly escapes
   a double quote inside code/row_id for both JSON and this HTML
   attribute — manual concatenation broke on a quote character. #}
hx-vals="{{ ({'batch_id': b.id, 'code': code | default(''), 'row': row_id} if row_id else {'batch_id': b.id, 'code': code | default('')}) | tojson }}"
```
So the fix is known and was applied to the new mobile picker, but never backported to the desktop `batch_picker.html` that `sale_row.html` (in scope for this review) still includes on every basket row, `sale_lookup.html`'s OOB fragment, and `sale_batch_pick.html`'s OOB fragment. A product code containing a literal `"` will corrupt the JSON payload of `hx-vals` on the desktop sale basket's batch picker (htmx either fails to parse it or drops params), causing the batch-pick request to lose `code`/`row`/`batch_id`.

**Fix:** Apply the same `| tojson` fix used in `batch_card_picker.html` to `batch_picker.html:47`, e.g.:
```jinja
hx-vals="{{ {'row': row_id | default(''), 'batch_id': b.id, 'code': code | default('')} | tojson }}"
```
(Note the outer attribute quotes must switch from `'...'` to `"..."` to match the mobile file's convention, since `tojson`'s output itself uses double quotes.)

### WR-04: `non_blank_lines` only length-guards `batch_ids`; a length mismatch in `qtys`/`prices` silently drops trailing basket lines

**File:** `app/services/sales.py:66-93`

**Issue:** `non_blank_lines` explicitly pads `batch_ids` to `len(codes)` before zipping (with a comment explaining why: "a short/missing array degrades to 'no batch picked' ... rather than shifting attribution onto the wrong line"). But the zip itself —
```python
return [
    (code, qty, price, batch_ids[i])
    for i, (code, qty, price) in enumerate(zip(codes, qtys, prices, strict=False))
    if code.strip() or qty.strip() or price.strip()
]
```
— uses `strict=False` across `codes`/`qtys`/`prices` with **no equivalent length check or error** for those three arrays. If `qtys` or `prices` is shorter than `codes` (e.g. a future template/JS regression drops a hidden `qty_acc[]`/`price_acc[]` input for one basket line, or a malformed direct POST), `zip(..., strict=False)` silently truncates to the shortest array — the trailing code(s) are dropped from `non_blank` entirely, with **no error surfaced anywhere**, and `register_sale` proceeds to sell only the truncated set of lines. This directly conflicts with the project's stated core value ("the operator can quickly and reliably record receipts and sales ... without losing any data") — a client-side bug that misaligns these arrays would silently omit basket lines rather than raising a validation error the operator could see.

**Fix:** At minimum, mirror the `batch_ids` treatment for `qtys`/`prices` (pad-and-flag, or use `zip(..., strict=True)` and raise a clear service-level error `EMPTY_BASKET_ERROR`-style if the arrays don't align), so a misaligned submission fails loudly instead of silently shipping a partial sale.

## Info

### IN-01: `sale-total.js`'s mobile row selector relies on incidental filtering rather than a scoped class

**File:** `app/static/sale-total.js:80-89`, `app/templates/mobile_partials/sale_customer.html:56,60,64`

**Issue:** `recalcSaleTotal()`'s mobile branch selects `#wizard-basket .mobile-card`, but `.mobile-card` is also used by the customer-mode radio `<label class="mobile-card">` elements and the customer-search result `<button class="mobile-card">` cards rendered by the included `mobile_partials/sale_customer.html`/`customer_picker.html` — both of which live inside `#wizard-basket`. This currently self-corrects because the loop's `if (!qtyEl || !priceEl) continue;` guard skips any card lacking `qty_acc[]`/`price_acc[]` inputs, but the correctness of the total depends on that guard rather than a properly scoped selector — a future change that adds a `qty_acc[]`/`price_acc[]`-named field inside a customer-picker card (unlikely, but a maintenance trap) would silently corrupt the total with no test catching it.

**Fix:** Consider a dedicated class (e.g. `mobile-basket-card`) for basket-line cards so the selector is scoped by construction rather than by the accidental absence of matching field names elsewhere on the page.

---

_Reviewed: 2026-07-17_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
