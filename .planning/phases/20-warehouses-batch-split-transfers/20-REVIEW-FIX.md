---
phase: 20-warehouses-batch-split-transfers
fixed_at: 2026-07-16T17:47:12Z
review_path: .planning/phases/20-warehouses-batch-split-transfers/20-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 20: Code Review Fix Report

**Fixed at:** 2026-07-16T17:47:12Z
**Source review:** .planning/phases/20-warehouses-batch-split-transfers/20-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (fix_scope: critical_warning — CR-01, WR-01, WR-02; the 3 Info findings were out of scope and not attempted)
- Fixed: 3
- Skipped: 0

## Fixed Issues

### CR-01: Destination-warehouse selection is dropped on re-render, breaking the transfer oversell "confirm anyway" flow

**Files modified:** `app/routes/transfers.py`, `app/routes/mobile_transfers.py`, `app/templates/partials/transfer_batch_wrap.html`, `app/templates/partials/transfer_form.html`, `app/templates/mobile_partials/transfers_step_dest.html`
**Commit:** cf7dec6
**Applied fix:** Added `dest_warehouse_id` to the desktop `form_echo` dict in `transfers.py` and threaded it through `transfer_form.html` into `transfer_batch_wrap.html`, where the previously-chosen `<option>` is now rendered `selected`. On the mobile side, added a `dest_warehouse_id` parameter to `_render_dest_step()` in `mobile_transfers.py` and passed it from all three re-render branches (exception/oversell/errors) of `POST /m/transfers`; `transfers_step_dest.html` now marks the matching radio `checked`. This matches the fix suggested in REVIEW.md and was verified against the actual current code (matched the reviewer's description closely). All 49 desktop + 20 mobile transfer tests pass after the change.

### WR-01: Mobile final-submit dest step never surfaces `errors.code`/`errors.batch`

**Files modified:** `app/templates/mobile_partials/transfers_step_dest.html`
**Commit:** 27131f0
**Applied fix:** Added the two missing error branches (`errors.code`, `errors.batch`) right after the existing `errors.form` branch, mirroring the desktop templates (`transfer_form.html`, `transfer_batch_wrap.html`). All 20 mobile transfer tests pass after the change.

### WR-02: `GET /warehouses/{id}/edit` does not guard against a soft-deleted warehouse

**Files modified:** `app/routes/warehouses.py`, `app/services/warehouses.py`
**Commit:** a3d6ef6
**Applied fix:** Chose the 404 option from REVIEW.md's two suggested alternatives (404 vs. banner), since the codebase already has an established `session.get(...) is None or ...deleted_at is not None -> 404` pattern (`app/routes/mobile_search.py:39`) for exactly this shape of guard. `warehouse_edit()` (GET) now 404s on a soft-deleted warehouse the same way it does on an unknown id. Additionally guarded the POST path the Issue text also called out (`warehouse_update` silently re-saving a deleted warehouse): `update_warehouse()` in `app/services/warehouses.py` now rejects a soft-deleted warehouse up front (mirroring `update_product`'s existing D-20 check), reusing the `"warehouse"` error key the route already 404s on — no route-level change needed for the POST path. All 39 warehouse tests pass after the change.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-16T17:47:12Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
