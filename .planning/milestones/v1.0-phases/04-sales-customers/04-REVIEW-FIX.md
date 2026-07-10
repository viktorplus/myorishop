---
phase: 04-sales-customers
fixed_at: 2026-07-09T14:00:00Z
review_path: .planning/phases/04-sales-customers/04-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-07-09T14:00:00Z
**Source review:** .planning/phases/04-sales-customers/04-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6 (CR-01, WR-01..WR-05; IN-01 excluded by fix_scope=critical_warning)
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: Reflected XSS via `row` query param into an `hx-on::load` JS sink

**Files modified:** `app/routes/sales.py`
**Commit:** fec18a2
**Applied fix:** Added `_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")` and validated the
`row` query param against it in `GET /sales/row` before using it as `row_id`; any value
that doesn't match the UUID4 shape produced by `new_id()` is discarded in favor of a
freshly generated id, closing the JS-evaluated-attribute injection sink in
`sale_row.html`.

### WR-01: `qty_text.isdigit()` is not a safe precondition for `int()`

**Files modified:** `app/services/sales.py`
**Commit:** 73e5a28
**Applied fix:** Changed `int(qty_text) if qty_text.isdigit() else 0` to
`int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0`, so non-ASCII
"digit" characters that `int()` can't parse fall through to the `QTY_ERROR` path
instead of raising an uncaught `ValueError`. (The sibling occurrence in
`app/services/receipts.py:58` was left untouched — out of this phase's scope per the
review.)

### WR-02: Broad exception swallowing with no logging in sales routes

**Files modified:** `app/routes/sales.py`
**Commit:** 729100e
**Applied fix:** Added a module-level `logger = logging.getLogger(__name__)` and a
`logger.exception(...)` call in both `sale_customer_create`'s and `sale_create`'s
`except Exception:` blocks, before returning the existing generic user-facing error.

### WR-03: Basket write loop has no explicit rollback on non-`IntegrityError` failures

**Files modified:** `app/services/sales.py`
**Commit:** b253026
**Applied fix:** Moved the per-line `record_operation` write loop inside the existing
`try` block (previously only `session.commit()` was guarded) and widened the `except`
clause to `(IntegrityError, ValueError)`, so a `ValueError` raised by
`record_operation`'s own guards (e.g. a TOCTOU soft-delete race) now triggers an
explicit `session.rollback()` instead of propagating with uncommitted pending inserts
left on the session. Full test suite (148 tests) re-verified green after this change.

### WR-04: Basket-line filtering logic duplicated between service and route

**Files modified:** `app/services/sales.py`, `app/routes/sales.py`
**Commit:** 3ca887a
**Applied fix:** Extracted the "line counts only if code/qty/price is non-blank" filter
into a new `app/services/sales.py::non_blank_lines()` helper; both `register_sale` and
the route's `_build_lines` now call it, so the two can no longer drift out of sync.

### WR-05: `search_lc`/name fields have no max-length guard before insert

**Files modified:** `app/services/customers.py`, `app/templates/pages/customer_form.html`,
`app/templates/partials/sale_customer.html`
**Commit:** acbbffa
**Applied fix:** Added `_validate_lengths()` in `app/services/customers.py`, mirroring
the declared `Customer.name`/`surname`/`consultant_number` column lengths
(200/200/50), called from both `create_customer` and `update_customer` before any
insert/update. Also added the corresponding `errors.surname`/`errors.consultant_number`
paragraphs to `customer_form.html` and the sale-header quick-create partial
(`sale_customer.html`) so the new validation errors are actually visible to the
operator rather than silently returning a 422 with no message.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-09T14:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
