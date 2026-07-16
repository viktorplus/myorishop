---
phase: 20-warehouses-batch-split-transfers
reviewed: 2026-07-16T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - app/routes/mobile_transfers.py
  - app/routes/transfers.py
  - app/routes/warehouses.py
  - app/routes/writeoffs.py
  - app/services/transfers.py
  - app/services/warehouses.py
  - app/templates/mobile_partials/transfers_step_dest.html
  - app/templates/pages/warehouse_form.html
  - app/templates/pages/warehouses.html
  - app/templates/partials/transfer_batch_wrap.html
  - app/templates/partials/transfer_form.html
  - app/templates/partials/warehouse_delete_wrap.html
  - app/templates/partials/warehouse_rows.html
  - tests/test_mobile_transfers.py
  - tests/test_transfers.py
  - tests/test_warehouses.py
  - tests/test_writeoffs.py
findings:
  critical: 1
  warning: 2
  info: 3
  total: 6
status: issues_found
---

# Phase 20: Code Review Report

**Reviewed:** 2026-07-16T00:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Reviewed the warehouse CRUD pages (WH-01/WH-02) and the batch-split transfer
feature (WH-03, desktop + mobile) added in this phase. The service layer
(`app/services/transfers.py`, `app/services/warehouses.py`) is careful about
write-ordering, ownership re-validation of client-supplied ids, and
zero-writes-until-confirmed semantics, and is well covered by
`tests/test_transfers.py` / `tests/test_mobile_transfers.py` /
`tests/test_warehouses.py`.

However, tracing the actual browser round-trip (not just the server-side
service call, which is what the existing tests exercise) surfaced one
reproducible **BLOCKER**: the destination-warehouse control
(`<select>`/radio group) is never re-populated with the operator's previous
choice when the form is re-rendered after a validation error or an
over-transfer warning. Because the oversell "confirm anyway" button
re-submits the *current DOM state* of the form (via the HTML `form=`
attribute), this silently breaks the documented D-06 warn-then-confirm flow
for transfers in real usage — even though `test_transfer_post_oversell_then_confirm`
passes, because it manually re-supplies `dest_warehouse_id` in its second
POST instead of simulating what the rendered HTML would actually resubmit.

Two smaller WARNING-level gaps and three INFO-level quality/consistency
items are listed below.

## Critical Issues

### CR-01: Destination-warehouse selection is dropped on re-render, breaking the transfer oversell "confirm anyway" flow

**File:** `app/templates/partials/transfer_batch_wrap.html:28-40`, `app/templates/mobile_partials/transfers_step_dest.html:37-48`, `app/routes/transfers.py:126-132,177-200`, `app/routes/mobile_transfers.py:245-272`

**Issue:**
Neither the desktop `<select id="dest_warehouse_id">` (in
`transfer_batch_wrap.html`) nor the mobile
`<input type="radio" name="dest_warehouse_id">` group (in
`transfers_step_dest.html`) ever marks a previously-chosen option as
`selected`/`checked`. The routes never thread the submitted
`dest_warehouse_id` back into the re-render context either:

- `app/routes/transfers.py`'s `form_echo` dict (used for every 422/oversell
  re-render) includes `code`, `name`, `qty`, `new_expiry`, `new_comment` —
  **but not `dest_warehouse_id`** (see lines 126-132, reused at 163-200).
- `app/routes/mobile_transfers.py`'s `_render_dest_step()` has no
  `dest_warehouse_id` parameter at all, so it can't be echoed even if a
  caller wanted to (lines 88-121, called from the oversell/errors branches
  at 247-272).

Both `partials/transfer_form.html` and `mobile_partials/transfers_step_dest.html`
fully replace the `<form>` (`hx-swap="outerHTML"` on `#transfer-form-wrap` /
`#wizard-step`) on **every** POST /transfers or POST /m/transfers response —
including the over-transfer warning. `partials/transfer_oversell.html` and
`mobile_partials/transfers_warning.html` both document (and rely on) a
"confirm anyway" button that re-submits the *same, already-swapped* form via
the HTML `form="transfer-form"` / `form="transfer-dest-form"` attribute
(`transfer_oversell.html:11`, `transfers_warning.html:10`) — i.e. it submits
whatever is currently selected in the DOM, not what the operator originally
typed.

Because the destination control was reset to its blank/unchecked state by
the oversell re-render, clicking "Переместить всё равно" resubmits
`dest_warehouse_id=""`:
- **Desktop**: the `<select>` has no `required` attribute, so the browser
  happily submits the empty value, and `register_transfer` returns
  `{"warehouse": WAREHOUSE_ERROR}` ("Выберите склад назначения") — a
  confusing bounce-back for an operator who already picked a warehouse and
  clicked confirm.
- **Mobile**: the radios *are* `required`
  (`transfers_step_dest.html:40`), so the browser's native HTML5 validation
  blocks the submit outright with no explanation the operator can act on,
  since (from their perspective) they already made a selection earlier in
  the wizard.

The same root cause also silently discards the destination choice on an
ordinary validation bounce (e.g. a qty typo) — `qty`, `new_expiry`, and
`new_comment` all correctly survive a 422 re-render, but the destination
warehouse does not, forcing the operator to re-pick it after fixing an
unrelated field.

This gap is invisible in the current test suite:
`test_transfer_post_oversell_then_confirm` and
`test_transfers_oversell_then_confirm_zero_writes_until_confirmed` both
issue a fresh `client.post(...)` with `dest_warehouse_id` supplied
explicitly a second time, which exercises the service/route logic correctly
but does not simulate what the rendered oversell HTML would actually
resubmit via the `form=` association.

**Fix:** Thread the submitted `dest_warehouse_id` back through the context
and render it as selected/checked, e.g.:

```html
<!-- app/templates/partials/transfer_batch_wrap.html -->
{% set _wh_list = warehouses | default([]) %}
{% set _dest_value = dest_warehouse_id_value | default('') %}
{% if selected_batch_id and _wh_list %}
<div class="field">
  <label for="dest_warehouse_id">Склад назначения</label>
  <select id="dest_warehouse_id" name="dest_warehouse_id">
    <option value=""></option>
    {% for w in _wh_list %}
    <option value="{{ w.id }}"{% if w.id == _dest_value %} selected{% endif %}>{{ w.name }}</option>
    {% endfor %}
  </select>
  ...
```

```html
<!-- app/templates/partials/transfer_form.html: add to the existing {% with %} block -->
{% with ...,
        dest_warehouse_id_value = form.dest_warehouse_id or '' %}
```

```python
# app/routes/transfers.py: add to form_echo
form_echo = {
    "code": code,
    "name": name,
    "qty": qty,
    "dest_warehouse_id": dest_warehouse_id,
    "new_expiry": new_expiry,
    "new_comment": new_comment,
}
```

```html
<!-- app/templates/mobile_partials/transfers_step_dest.html -->
<input type="radio" name="dest_warehouse_id" value="{{ w.id }}"
       {% if w.id == dest_warehouse_id %}checked{% endif %} required>
```

```python
# app/routes/mobile_transfers.py: add a dest_warehouse_id param to _render_dest_step
# and pass dest_warehouse_id=dest_warehouse_id from the oversell/errors branches
# in transfers_create().
```

## Warnings

### WR-01: Mobile final-submit dest step never surfaces `errors.code`/`errors.batch`

**File:** `app/templates/mobile_partials/transfers_step_dest.html:21,47,53`

**Issue:** `_render_dest_step()` in `app/routes/mobile_transfers.py` re-renders
this template with whatever `errors` dict `register_transfer()` returns, but
the template only checks `errors.form`, `errors.warehouse`, and
`errors.quantity` — there is no branch for `errors.code` or `errors.batch`.
`register_transfer` (`app/services/transfers.py:79-87`) can return either of
those keys (product not found / batch id no longer valid, e.g. if the
underlying data changed between wizard steps). When that happens the mobile
wizard re-renders step 3 with **no visible error text at all** (status 422),
leaving the operator with a form that appears to have silently failed. The
desktop equivalent (`transfer_form.html:37`, `transfer_batch_wrap.html:26`)
already renders both of these keys, so this is a mobile-only regression risk.

**Fix:** Add the missing branches, mirroring the desktop template:
```html
{% if errors is defined and errors.code %}<p class="error">{{ errors.code }}</p>{% endif %}
{% if errors is defined and errors.batch %}<p class="error">{{ errors.batch }}</p>{% endif %}
```

### WR-02: `GET /warehouses/{id}/edit` does not guard against a soft-deleted warehouse

**File:** `app/routes/warehouses.py:126-134`

**Issue:** `warehouse_edit()` only checks `warehouse is None` (404 for an
unknown id); it never checks `warehouse.deleted_at`. The list page only
links "Изменить" for non-deleted rows (`warehouse_rows.html:73-74`), but the
edit URL is still reachable directly (bookmarked link, browser history,
typed URL), and `POST /warehouses/{id}` (`warehouse_update`, same file,
137-158) will happily rename/re-address a soft-deleted warehouse without
restoring it or telling the operator it is currently hidden from every
active-warehouse picker. This produces a confusing, silently-edited "ghost"
record.

**Fix:** Either 404 (or redirect with a notice) when
`warehouse.deleted_at is not None`, or surface a visible "this warehouse is
deleted — restore it to make changes" banner on the edit page.

## Info

### IN-01: Stale comments claim the destination list excludes the source's own warehouse

**File:** `app/templates/partials/transfer_batch_wrap.html:9-13`, `app/templates/partials/transfer_form.html:5-7`

**Issue:** Both docstring comments describe the destination-warehouse
options as "active warehouses minus the source's own warehouse". This was
true before D-09; the actual behavior (and `_dest_warehouses()` in both
`app/routes/transfers.py:26-30` and `app/routes/mobile_transfers.py:36-42`)
now deliberately *includes* the source warehouse to support same-warehouse
batch splits. Leaving the old comment in place risks a future edit
re-introducing the exclusion "to match the docs".

**Fix:** Update both comments to state that the source's own warehouse is
included (same-warehouse split), consistent with the D-09 comments already
present elsewhere in the same files.

### IN-02: Warehouse delete/restore buttons lack the double-submit guard used elsewhere

**File:** `app/templates/partials/warehouse_delete_wrap.html:8-35`, `app/templates/partials/warehouse_rows.html:76-79`

**Issue:** Every `hx-post` button in this phase's transfer/write-off forms
uses `hx-disabled-elt="find button"` (or `"this"`) to prevent a double
submit while the request is in flight (see e.g.
`transfer_form.html:24`, `transfer_oversell.html:14`). The warehouse
delete/confirm/restore buttons introduced by this phase do not, so a fast
double-click can fire two POSTs before the first response lands (harmless
here only because `soft_delete_warehouse`/`restore_warehouse` happen to be
idempotent no-ops on the second call, but the inconsistency invites the
guard being forgotten somewhere it does matter).

**Fix:** Add `hx-disabled-elt="this"` to the three buttons in
`warehouse_delete_wrap.html` and the restore button in `warehouse_rows.html`
for consistency with the rest of the codebase.

### IN-03: `SAVE_FAILED_ERROR` duplicated verbatim across three route modules

**File:** `app/routes/mobile_transfers.py:33`, `app/routes/transfers.py:23`, `app/routes/writeoffs.py:22`

**Issue:** The identical Russian string
`"Не удалось сохранить. Проверьте данные и попробуйте ещё раз."` is defined
as a module-level constant independently in all three files. This is a
minor duplication smell — a future copy-edit of the message is likely to
update only one or two of the three copies.

**Fix:** Move the constant into a shared module (e.g. `app/services/errors.py`
or similar) and import it from the three route modules.

---

_Reviewed: 2026-07-16T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
