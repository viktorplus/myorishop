---
phase: 08-warehouses
reviewed: 2026-07-11T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - alembic/versions/0007_warehouses.py
  - app/main.py
  - app/models.py
  - app/routes/warehouses.py
  - app/services/warehouses.py
  - app/templates/base.html
  - app/templates/pages/warehouses.html
  - app/templates/partials/warehouse_rows.html
  - tests/test_warehouses.py
findings:
  critical: 0
  warning: 1
  info: 2
  total: 3
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-07-11T00:00:00Z
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the WH-01 warehouse management slice: migration `0007`, the `Warehouse`
model, the CRUD service (`app/services/warehouses.py`), the thin route layer,
the settings-style page/partial templates, and `tests/test_warehouses.py`. I
traced every branch of `add_warehouse`/`update_warehouse`/`soft_delete_warehouse`/
`restore_warehouse` by hand (blank-name validation, unknown-id handling, the
warn-but-allow last-active-warehouse guard, idempotent restore) and cross-checked
the Jinja context keys each route passes against what `warehouse_rows.html`
reads (`errors`, `form`, `error_entry_id`, `error_form`, `warning_id`) — no
missing-key crashes, no state leaking between routes. I ran the full test file
(`uv run pytest tests/test_warehouses.py -q`): all 15 tests pass. `ruff check`
on the changed Python files is clean. The migration's up/down pair, seed row,
and column set match the ORM model exactly, and the `active_count <= 1` guard
in `soft_delete_warehouse` is a correct TOCTOU-free check within a single
synchronous session.

This is a small, well-scoped, well-tested slice. I did not find any
correctness or security defect. The two issues below are pre-existing,
codebase-wide patterns (not introduced by this phase) that this phase's new
files also inherit — flagged because they apply to the reviewed files, not
because they are unique to warehouses.

## Warnings

### WR-01: No length validation/enforcement on `name`/`address` against the declared column widths

**File:** `app/services/warehouses.py:30-44` (also `app/models.py:131-133`, `alembic/versions/0007_warehouses.py:40-41`)
**Issue:** `Warehouse.name` is `String(200)` and `Warehouse.address` is
`String(300)`, but `add_warehouse`/`update_warehouse` only `.strip()` and
check for blankness — nothing rejects or truncates input longer than those
widths, and the HTML inputs in `warehouse_rows.html`/`warehouses.html` have no
`maxlength`. SQLite does not enforce `VARCHAR(N)` length (type affinity only),
so oversized input is silently accepted today. CLAUDE.md explicitly states
the goal that "same models will run on PostgreSQL later with only a
connection-string change" — on PostgreSQL, `VARCHAR(200)`/`VARCHAR(300)` *are*
enforced, so any warehouse name/address stored today beyond those widths will
raise a `DataError` (hard failure) on that future migration instead of failing
fast now. This is the same gap that exists in `services/dictionary.py` and
`services/products.py`, so it is systemic rather than unique to this phase —
but it is present in the newly-added file under review.
**Fix:** Add an explicit length check in the service layer (mirroring the
blank-name check) and a matching `maxlength` on the HTML inputs, e.g.:
```python
if len(name) > 200:
    errors["name"] = "Название слишком длинное (максимум 200 символов)."
if address and len(address) > 300:
    errors["address"] = "Адрес слишком длинный (максимум 300 символов)."
```
If this is deemed out of scope for Phase 8 alone, consider tracking it as a
project-wide follow-up covering all entities with `String(N)` columns.

## Info

### IN-01: `warehouse_update`'s 404 branch has no HTTP-level test

**File:** `app/routes/warehouses.py:64-65`
**Issue:** `if "warehouse" in errors: raise HTTPException(status_code=404, ...)`
is reachable only when `update_warehouse` is called with an unknown
`warehouse_id`. `tests/test_warehouses.py` covers this at the service level
(`test_update_warehouse_unknown_id_returns_error`) but there is no
`client.post("/warehouses/<unknown-id>", ...)` test asserting the route
actually returns 404 (unlike, e.g., verifying the 422 swap path via
`test_web_add_invalid_returns_swappable_422_partial`). A regression here
(wrong status code, wrong condition, swallowed exception) would go unnoticed.
**Fix:** Add a small web-level test, e.g.:
```python
def test_web_update_unknown_id_returns_404(client):
    response = client.post(
        "/warehouses/00000000-0000-4000-8000-000000000099",
        data={"name": "X", "address": ""},
    )
    assert response.status_code == 404
```

### IN-02: No `maxlength` attribute on the name/address inputs

**File:** `app/templates/pages/warehouses.html:11-12`, `app/templates/partials/warehouse_rows.html:30-31`
**Issue:** Related to WR-01 — even as a pure UX nicety independent of backend
enforcement, the `<input type="text" name="name">`/`name="address">` elements
don't cap input length client-side, so operators get no early feedback before
a 200/300-char field is silently accepted.
**Fix:** Add `maxlength="200"` / `maxlength="300"` to the respective inputs
once/if WR-01's server-side check is added, so the two stay in sync.

---

_Reviewed: 2026-07-11T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
