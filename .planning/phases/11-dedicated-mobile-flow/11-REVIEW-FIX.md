---
phase: 11-dedicated-mobile-flow
fixed_at: 2026-07-13T00:00:00Z
review_path: .planning/phases/11-dedicated-mobile-flow/11-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 11: Code Review Fix Report

**Fixed at:** 2026-07-13
**Source review:** .planning/phases/11-dedicated-mobile-flow/11-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (Critical: 2, Warning: 3 — `fix_scope: critical_warning`, Info excluded)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Corrections wizard returns a full HTML document where an htmx fragment is required

**Files modified:** `app/routes/mobile_corrections.py`, `app/templates/mobile_partials/corrections_not_found.html` (new), `app/templates/mobile_partials/corrections_success.html` (new)
**Commit:** 8689a5a
**Applied fix:** Added two new bare fragment partials (`corrections_not_found.html`, `corrections_success.html`), each rooted at `<div id="corrections-step-wrap">` with no `{% extends %}`. Updated `mobile_correction_step_batch`'s product-not-found branch and `mobile_correction_create`'s success branch to render these partials instead of the full `mobile_pages/corrections.html` document, matching every sibling wizard's htmx-fragment contract. `mobile_pages/corrections.html` is now only reached by the plain-GET entry point, as the fix guidance specified. Also folds in WR-03 (see below).

### CR-02: Corrections over-removal warning is a dead end

**Files modified:** `app/routes/mobile_corrections.py`, `app/templates/mobile_partials/corrections_step_value.html`, `app/templates/mobile_partials/corrections_warning.html`
**Commit:** 38245aa
**Applied fix:** The oversell branch in `mobile_correction_create` now re-renders `corrections_step_value.html` (the real, editable step-4 template) with `oversell` set, instead of a separate hand-rolled fragment. `corrections_step_value.html` gained an `id="corrections-value-form"` and now includes `corrections_warning.html` above its still-visible/editable `value`/`note` text inputs when `oversell` is set. `corrections_warning.html` was rewritten to drop its hidden-field form wrapper entirely — its danger button now re-submits the real visible form via `form="corrections-value-form"` + `hx-vals='{"confirm": "1"}'` (mirroring `transfers_warning.html`'s pattern), and its dismiss button just removes the warning div, leaving the operator's typed value/note intact and visible. Verified via `test_mobile_correction_over_removal_warns_then_confirms`, which still passes and confirms the write proceeds correctly with `confirm=1`.

### WR-01: `mobile_sale_create`'s exception handler missing defensive `session.rollback()`

**Files modified:** `app/routes/mobile_sales.py`
**Commit:** d75b542
**Applied fix:** Added `session.rollback()` as the first line of the `except Exception:` block in `mobile_sale_create`, before `logger.exception` and the `_basket_lines` re-query, matching the pattern already used in `mobile_receipts.py`, `mobile_writeoff.py`, `mobile_corrections.py`, and `mobile_returns.py` (with the same rationale comment referencing the `PendingRollbackError` risk).

### WR-02: `hx-vals` JSON built by raw Jinja string interpolation is not JSON-safe

**Files modified:** `app/templates/mobile_partials/batch_card_picker.html`, `app/templates/mobile_partials/transfers_step_batch.html`, `app/templates/mobile_partials/transfers_step_dest.html`
**Commit:** ea0778f
**Applied fix:** Replaced all three manually-concatenated `hx-vals='{"key": "{{ value }}"}'` attributes with Jinja's `tojson` filter (`hx-vals="{{ {...} | tojson }}"`), which correctly escapes for both JSON and the HTML attribute context regardless of embedded quote characters. `batch_card_picker.html`'s conditional `row` key is now built via a ternary dict expression rather than string-level `{% if %}` splicing.

### WR-03: `mobile_correction_step_batch`'s not-found response uses HTTP 200 instead of 422

**Files modified:** `app/routes/mobile_corrections.py` (same change as CR-01)
**Commit:** 8689a5a
**Applied fix:** Folded into the CR-01 fix as the review's own Fix section specified — the not-found `TemplateResponse` call now passes `status_code=422`, matching the sibling "not found" branches in `mobile_sales.py` and `mobile_writeoff.py`.

## Skipped Issues

None — all in-scope findings (CR-01, CR-02, WR-01, WR-02, WR-03) were fixed. IN-01 was out of scope for this run (`fix_scope: critical_warning` excludes Info-tier findings) and was not attempted.

**Verification:** Full test suite (`uv run pytest -q`) run after all four commits: 434 passed, 0 failed (3 pre-existing warnings unrelated to this phase).

---

_Fixed: 2026-07-13_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
