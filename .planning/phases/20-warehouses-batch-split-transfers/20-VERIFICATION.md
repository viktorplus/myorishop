---
phase: 20-warehouses-batch-split-transfers
verified: 2026-07-16T17:59:52Z
status: human_needed
score: 4/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Warehouse delete three-state flow in a live browser: (1) delete a warehouse with stock -> stock-blocked message + button stays; (2) delete the last active warehouse -> warn card appears, 'Удалить всё равно' completes the delete, 'Отмена' dismisses the card client-side; (3) delete a non-last-active warehouse with zero stock -> redirected to /warehouses."
    expected: "All three states render correctly and the HX-Redirect actually navigates the browser (TestClient only asserts the header is present, it does not execute the redirect)."
    why_human: "HTMX response headers (HX-Redirect) and client-side hx-on:click dismiss handlers are not executed by TestClient — only a live browser proves the DOM behaves as coded."
  - test: "Desktop /transfers: pick a batch, select the SAME warehouse as destination, leave both override fields blank, submit, see the D-06 error, then trigger an over-transfer (qty > available) with a filled override, click 'Переместить всё равно' on the oversell warning."
    expected: "The destination-warehouse <select> keeps the operator's original choice pre-selected through the oversell re-render (this exact scenario was CR-01, a real bug found only by tracing actual browser round-trips — TestClient's own tests re-supply dest_warehouse_id explicitly on the second POST and would not have caught the original bug)."
    why_human: "CR-01 was invisible to the automated suite by construction; the fix (dest_warehouse_id_value threaded + selected attribute) is confirmed by direct code read but the actual re-rendered <select>'s pre-selected state has not been observed in a live DOM."
  - test: "Mobile wizard (/m/transfers): pick a batch, advance to step 3, confirm the two override fields (Новый срок годности / Новое состояние или комментарий) appear, fill only the expiry override, choose the SAME warehouse as the source, submit."
    expected: "A new destination batch is created in the same warehouse holding only the moved quantity; the success screen shows the correct transferred qty."
    why_human: "End-to-end wizard navigation (three HTMX-swapped steps) is covered by TestClient at the HTTP-response level, but the actual step-to-step swap UX (back/forward, radio pre-check) has not been visually confirmed."
---

# Phase 20: Warehouses & Batch-Split Transfers Verification Report

**Phase Goal:** Operator manages warehouses through dedicated forms and can move part of a batch out under a different expiry or condition without corrupting the batch it came from.
**Verified:** 2026-07-16T17:59:52Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | Warehouse list shows each warehouse's current item count and the date of its last goods receipt | ✓ VERIFIED | `app/services/warehouses.py::list_warehouses` computes `.item_count` (grouped distinct-product count, quantity>0) and `.last_receipt` (grouped outerjoin max of receipt-type `Operation.created_at`) per page — both consumed in `app/templates/partials/warehouse_rows.html` as "Товаров" / "Последняя приёмка" columns. `tests/test_warehouses.py::test_web_warehouses_page_shows_item_count_and_last_receipt_columns` passes. |
| 2 | Operator adds, edits, and deletes a warehouse via links that open a dedicated form rather than inline row controls | ✓ VERIFIED | `GET /warehouses/new` and `GET /warehouses/{id}/edit` render `pages/warehouse_form.html` (`app/routes/warehouses.py:100-136`); list page (`warehouses.html`) has a `page-actions` "Добавить склад" link, list rows (`warehouse_rows.html`) render one "Изменить" `<a href="/warehouses/{{w.id}}/edit">` link per active row — zero inline `<input>`/save/delete controls remain in the row markup (confirmed by direct read). `test_web_warehouses_row_action_is_edit_link_not_inline_buttons` passes. |
| 3 | Deleting a warehouse that still holds stock is refused; deleting one holding zero stock succeeds | ✓ VERIFIED | `app/services/warehouses.py::soft_delete_warehouse` checks `warehouse_stock > 0` first (non-overridable, zero writes) before the last-active-warn/confirm path; unchanged from the pre-phase implementation, only its rendering location moved (D-02) to `partials/warehouse_delete_wrap.html`. `test_soft_delete_warehouse_blocked_when_stock_positive`, `test_web_warehouse_delete_stock_blocked_renders_in_wrap`, `test_web_warehouse_delete_success_redirects` all pass. |
| 4 | Transferring part of a batch under a different expiry date or condition creates a new destination batch holding only the moved portion, leaving the source batch's remaining quantity and attributes unchanged | ✓ VERIFIED | `app/services/transfers.py::register_transfer` gained `new_expiry`/`new_comment` params (D-05/D-07): same-warehouse destination + at least one non-blank override creates a fresh `Batch` via override-or-inherit ternary (never bare `or`), blocked with zero writes when both overrides are blank (D-06). Wired end-to-end on desktop (`app/routes/transfers.py`, `partials/transfer_batch_wrap.html`) and mobile (`app/routes/mobile_transfers.py`, `mobile_partials/transfers_step_dest.html`). 29 tests in `tests/test_transfers.py` covering same-warehouse split, blank-override rejection, cross-warehouse regression guard, and whitespace-only-treated-as-blank all pass; mobile parity covered by `tests/test_mobile_transfers.py` (20 tests). |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `app/services/warehouses.py` | `list_warehouses()` carries `.item_count`/`.last_receipt` via grouped queries | ✓ VERIFIED | Confirmed via direct read: one grouped `func.count(func.distinct(...))` query and one grouped `outerjoin`+`func.max` query, both scoped by `warehouse_id.in_(page_rows ids)`, no per-row query. |
| `app/templates/pages/warehouse_form.html` | Dedicated add/edit page, mirrors `product_form.html` | ✓ VERIFIED | Heading branch, name/address fields with value fallback, destructive zone including `warehouse_delete_wrap.html` include — all present. |
| `app/templates/partials/warehouse_delete_wrap.html` | Relocated warn/stock-blocked/default delete UI | ✓ VERIFIED | Three mutually exclusive branches present, all `hx-post`ing to `/warehouses/{id}/delete`, targeting `#warehouse-delete-wrap`. |
| `app/templates/partials/warehouse_rows.html` | 5-column read-only picker | ✓ VERIFIED | Header row: Название, Адрес, Товаров, Последняя приёмка, Действия. Zero `<input>`/inline-edit markup in the row body; filter-bar/sort/status chrome (Phase 14) preserved. |
| `app/services/transfers.py` | `register_transfer(..., new_expiry='', new_comment='')` with D-05/D-06/D-07/D-11 semantics | ✓ VERIFIED | `SAME_WAREHOUSE_REQUIRES_OVERRIDE_ERROR` constant present, override-or-inherit ternary present, success dict carries real `"qty"` int. |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `app/services/warehouses.py::list_warehouses` | `app/models.py::Batch, Operation` | grouped `select(...).where(warehouse_id.in_(...))` | ✓ WIRED | Confirmed by direct read, both queries present. |
| `app/routes/warehouses.py::warehouse_new, warehouse_edit` | `pages/warehouse_form.html` | `templates.TemplateResponse(...)` | ✓ WIRED | Both GET routes render the template; POST routes redirect-after-success / 422-re-render on the same page. |
| `app/routes/warehouses.py::warehouse_delete` | `app/services/warehouses.py::soft_delete_warehouse` | unchanged call | ✓ WIRED | Confirmed; stock guard runs first, non-overridable. |
| `app/routes/transfers.py::transfers_create` | `app/services/transfers.py::register_transfer` | `new_expiry=new_expiry, new_comment=new_comment` | ✓ WIRED | Both kwargs threaded through the single call site; `form_echo` carries `dest_warehouse_id`/`new_expiry`/`new_comment` for 422/oversell re-renders (CR-01 fix). |
| `app/templates/partials/transfer_form.html` | `app/templates/partials/transfer_batch_wrap.html` | `dest_warehouse_id_value` / `new_expiry_value` / `new_comment_value` via `{% with %}` | ✓ WIRED | `transfer_batch_wrap.html` renders `selected` on the matching `<option>` and echoes typed override values in `value="..."`. |
| `app/routes/mobile_transfers.py::transfers_create` | `app/services/transfers.py::register_transfer` | `new_expiry=new_expiry, new_comment=new_comment` | ✓ WIRED | All three re-render branches (exception/oversell/errors) forward `dest_warehouse_id`, `new_expiry`, `new_comment` into `_render_dest_step`. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full phase-relevant suite | `uv run pytest tests/test_warehouses.py tests/test_transfers.py tests/test_mobile_transfers.py tests/test_writeoffs.py -q` | 98 passed | ✓ PASS |
| Full project suite (regression check) | `uv run pytest -q` | 752 passed, 0 failed | ✓ PASS |
| Code-review fixes present in tree | `git log` shows `cf7dec6` (CR-01), `27131f0` (WR-01), `a3d6ef6` (WR-02) on the branch; confirmed by direct read of `app/services/warehouses.py`, `app/routes/warehouses.py`, `app/templates/partials/transfer_batch_wrap.html`, `app/routes/mobile_transfers.py`, `app/templates/mobile_partials/transfers_step_dest.html` | All three fixes present in current file contents | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| WH-01 | 20-01, 20-03 | Warehouse list shows item count and last-receipt date | ✓ SATISFIED | See Truth #1 above. |
| WH-02 | 20-02, 20-03 | Add/edit/delete reached via dedicated-form links | ✓ SATISFIED | See Truth #2 above. |
| WH-03 | 20-02, 20-03 | Delete blocked while stock > 0 | ✓ SATISFIED | See Truth #3 above. |
| XFER-01 | 20-04, 20-05, 20-06, 20-07 | Partial-batch transfer with different expiry/condition splits correctly | ✓ SATISFIED | See Truth #4 above. |

No orphaned requirements — `.planning/REQUIREMENTS.md`'s "By phase" table maps exactly WH-01, WH-02, WH-03, XFER-01 to Phase 20, matching every plan's `requirements:` frontmatter field.

**Note (non-blocking):** `.planning/REQUIREMENTS.md`'s per-requirement checklist (lines 42-48) still shows WH-01/WH-02/WH-03 as unchecked `[ ]` and its Traceability table (line 117-119) shows them as "Pending", while XFER-01 is already marked complete. This is a stale-documentation lag (REQUIREMENTS.md is conventionally updated at ship time in this project, not at phase-verification time) — the codebase evidence above confirms all four requirements are actually implemented and tested. Flagging for the ship workflow to update these rows, not treating it as a phase gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | No TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER markers found in any file this phase modified | — | None |

One quality observation (info-level, not a gap): the WR-02 fix (`GET /warehouses/{id}/edit` and `update_warehouse` reject a soft-deleted warehouse — commit `a3d6ef6`) is present and correct by direct code read, but `tests/test_warehouses.py` has no dedicated regression test exercising "GET edit on a soft-deleted warehouse id returns 404" or "POST update on a soft-deleted warehouse is rejected." The fix itself is verified correct; only its automated regression coverage is thin.

### Human Verification Required

See the `human_verification` list in the frontmatter — three items covering: (1) the warehouse delete three-state HTMX flow, (2) the CR-01 oversell/confirm-anyway destination-preservation fix in a live browser (this exact class of bug was invisible to TestClient before the code review caught it), and (3) the mobile same-warehouse split wizard end-to-end. None of these are "must-haves failing" — the code-level wiring for all three is confirmed correct by direct read and passing TestClient-level tests — but real-time HTMX DOM behavior (redirect execution, pre-selected `<option>`/`<input>` state after a swap, client-side dismiss handlers) cannot be proven by TestClient alone, and this exact class of gap (CR-01) was already found once in this phase by tracing an actual browser round-trip rather than trusting the test suite.

### Gaps Summary

No blocking gaps. All four ROADMAP success criteria are verified against the actual codebase (not just SUMMARY.md claims): the data layer, routes, and templates for warehouse CRUD and batch-split transfers are all wired end-to-end, the three code-review findings (CR-01 critical, WR-01/WR-02 warnings) are confirmed fixed in the current tree, and the full test suite (752 tests) passes with zero failures. Status is `human_needed` rather than `passed` solely because this is an HTMX-heavy UI phase where real-browser behavior — redirects, DOM swap state, pre-selected form values — cannot be fully proven by TestClient, and one class of exactly this gap (CR-01) was already found once in this phase.

---

*Verified: 2026-07-16T17:59:52Z*
*Verifier: Claude (gsd-verifier)*
