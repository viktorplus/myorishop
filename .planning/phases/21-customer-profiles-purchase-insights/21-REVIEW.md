---
phase: 21-customer-profiles-purchase-insights
reviewed: 2026-07-17T09:29:51Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - alembic/versions/0015_customer_contacts.py
  - app/models.py
  - app/routes/__init__.py
  - app/routes/customers.py
  - app/services/customers.py
  - app/static/style.css
  - app/templates/pages/customer_detail.html
  - app/templates/pages/customer_form.html
  - app/templates/partials/contact_row.html
  - app/templates/partials/customer_contacts.html
  - app/templates/partials/customer_insights.html
  - app/templates/partials/favorite_products.html
  - tests/conftest.py
  - tests/test_customers.py
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 21: Code Review Report

**Reviewed:** 2026-07-17T09:29:51Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Reviewed the customer-profile / purchase-insights slice: the `customer_contacts` migration, the `Customer.address` column, the new `CustomerContact` model, the contact/address/spend/favorites service functions, the thin routes, all five new/changed templates, and the CSS additions.

The implementation is careful about the things that usually go wrong in this kind of feature: contact values are never rendered through an unescaping filter (verified against the templates and the repo-wide `| safe` ban test), `kind` is allow-listed both when interpolated into a rendered attribute (`/customers/contact-row`) and when written to the DB, the `_spend_stmt`/`_favorites_stmt` queries are portability-tested against both dialects and use bound parameters only, the double-coalesce NULL-price guard is correctly implemented and tested, and the full-replace contact write path validates before any write (no partial-write risk on the `ValueError` path for an unknown `kind`). Migration 0015 correctly duplicates (never imports) the `CONTACT_KINDS` constant and its naming-convention-expanded constraint name matches the ORM model.

No Critical/security findings. Two Warning-level maintainability/completeness gaps and one Info-level latent template defect were found; details below.

## Warnings

### WR-01: Blank-name early return silently skips the new address/contact validation

**File:** `app/services/customers.py:149-157` (create_customer), `app/services/customers.py:206-214` (update_customer)
**Issue:** Both `create_customer` and `update_customer` validate in this order:
```python
if not name:
    errors["name"] = NAME_REQUIRED_ERROR
    return None, errors          # <-- returns immediately

_validate_lengths(name, surname, consultant_number, address, errors)
if contacts is not None:
    _validate_contacts(contacts, errors)
if errors:
    return None, errors
```
When `name` is blank, the function returns before `_validate_lengths` (which now also checks the new `address` field, D-02/CUST-05) and before `_validate_contacts` (CUST-01..04) ever run. If an operator submits a blank name together with a 301-character address or an overlong contact value, the 422 response shows only "Укажите имя покупателя." — the address/contact errors are silently withheld until the operator fixes the name and resubmits. This pre-existing pattern (blank-name short-circuit) was safe when it only guarded `surname`/`consultant_number` (which have no phase-21-added validation); now that `address` and `contacts` validation were added to the same functions, the gap silently swallows more feedback than before. No data is written on this path (safe), but it's an incomplete-validation UX defect directly touching this phase's new requirements.
**Fix:** Run all validations before checking for `errors`, e.g.:
```python
errors: dict[str, str] = {}
name = name.strip()
...
if not name:
    errors["name"] = NAME_REQUIRED_ERROR
_validate_lengths(name, surname, consultant_number, address, errors)
if contacts is not None:
    _validate_contacts(contacts, errors)
if errors:
    return None, errors
```
(Guard the `contacts`/`address` validation calls against being reached only when it's safe to do so — `_validate_contacts` already tolerates an empty/blank name.)

### WR-02: `spend_view` duplicates `spend_totals`'s window-loop instead of composing on it

**File:** `app/services/customers.py:426-471`
**Issue:** `spend_totals` (lines 426-448) and `spend_view` (lines 451-471) both independently loop over `_period_starts(today)`, call `local_day_bounds_utc`, and call `_spend_window` — the exact same three steps, duplicated rather than `spend_view` building its `{cents, start_iso}` shape on top of `spend_totals`'s already-computed totals. `spend_totals` is not called anywhere in application code (only in tests) — it exists purely as a duplicate of `spend_view`'s inner logic with a different return shape. Any future change to the window/netting logic (e.g. an additional period, a different rounding rule) has to be made in two places, and it is easy to update one and miss the other since nothing currently forces them to agree beyond the shared tests.
**Fix:** Have `spend_view` reuse `spend_totals`, e.g.:
```python
def spend_view(session: Session, customer_id: str, today: date | None = None) -> dict:
    if today is None:
        today = datetime.now(ZoneInfo(settings.display_tz)).date()
    totals = spend_totals(session, customer_id, today=today)
    return {
        name: {"cents": totals[name], "start_iso": start.isoformat()}
        for name, start in _period_starts(today).items()
    }
```

## Info

### IN-01: `favorite_products.html` renders `Product.code` without a null guard

**File:** `app/templates/partials/favorite_products.html:22`
**Issue:** `<td>{{ row.product.name }} ({{ row.product.code }})</td>` — `Product.code` is `Mapped[str | None]` (`app/models.py:158`, nullable). If a favorite product has `code is None`, the cell would literally render "Товар (None)". This mirrors several other existing templates that have the same gap (`purchase_history.html`, `top_selling_rows.html`, `sales_report_results.html`, `history_rows.html`), so it is a pre-existing codebase convention rather than something introduced fresh by this phase — flagging for awareness since this is a newly-added template that could have closed the gap (other templates in the same diff, e.g. `reports_stock.html`/`categories.html`, do use `product.code or ""`).
**Fix:**
```html
<td>{{ row.product.name }} ({{ row.product.code or "" }})</td>
```

---

_Reviewed: 2026-07-17T09:29:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
