---
phase: 19-products-page-rebuild
reviewed: 2026-07-16T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - app/services/batches.py
  - app/routes/products.py
  - app/templates/partials/product_rows.html
  - app/templates/pages/products_list.html
  - app/static/style.css
  - tests/test_batches.py
  - tests/test_catalog.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 19: Code Review Report

**Reviewed:** 2026-07-16
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Phase 19 Plan 01 diff (`53005e0..HEAD`): `batches_for_products()` (batched, non-N+1 open-batch query), its wiring into `_products_context()`, the new `Кол-во` column + collapsed per-row batch breakout in `product_rows.html`, the `<button>`→`<a class="link-danger">` delete-control change, and the "Добавить товар" CTA removal.

The implementation is small, well-tested (9 new tests across `test_batches.py`/`test_catalog.py`, all traced against the actual behavior), and correctly follows the project's own pre-flight research (`19-RESEARCH.md` Pitfalls 1–5): the N+1 batched-query pattern is used instead of a per-row `open_batches()` call, legacy NULL `expiry`/`name` fields are guarded with the `—` fallback, the zero-batch case renders no `<details>` affordance, `colspan` was correctly bumped from 6 to 7 to match the new column, and no `|safe` filter is used anywhere near the untrusted `Batch.name`/`expiry` fields (autoescape only, matching the project's established XSS-mitigation convention). No SQL injection, XSS, hardcoded secrets, or data-loss risks were found in this diff. No Critical/Blocker findings.

Two Warning-level and two Info-level findings are listed below — none block shipping, but are worth addressing for polish/consistency.

## Warnings

### WR-01: Delete link is keyboard-operable only via Enter, not Space

**File:** `app/templates/partials/product_rows.html:63`
**Issue:** The delete control was intentionally changed from `<button class="danger">` to `<a href="#" class="link-danger" hx-post=... hx-confirm=...>` (PROD-02, per `19-RESEARCH.md` Pitfall 2). `19-RESEARCH.md` explicitly worked through the WCAG 1.4.1 (color-only) and htmx click-interception risks for this change, but did not address WCAG 2.1.1 (keyboard) operability: native `<a>` elements only fire a `click` event on <kbd>Enter</kbd>, not <kbd>Space</kbd> (unlike `<button>`), and the element carries no `role="button"` to signal to assistive tech that it behaves as an action trigger rather than a navigation link. A keyboard/screen-reader user who expects Space to activate the control (as it would on the "Изменить" `<a>` used for navigation, that expectation is arguably reasonable either way) gets no feedback.
**Fix:** Add `role="button"` to signal the non-navigational semantics to AT, matching the deliberate "text link, not `<button>`" visual requirement:
```html
<a href="#" class="link-danger" role="button" hx-post="/products/{{ product.id }}/quick-delete?page={{ page }}{{ extra_qs }}" hx-confirm="..." hx-target="#product-rows" hx-swap="outerHTML">Удалить</a>
```
`role="button"` alone does not restore Space-key activation (that needs a small `hx-on:keydown` shim, or accept Enter-only as this codebase's established convention — the same pattern is already used unaddressed elsewhere, e.g. `warehouse_rows.html`'s cancel control, per `19-RESEARCH.md:361-364`). At minimum, add `role="button"` so screen readers announce the correct semantics.

### WR-02: `batches_for_products` runs even when a `quick-delete` request fails/blocks

**File:** `app/routes/products.py:104-130`
**Issue:** Not a functional bug (verified correct output), but worth flagging as a design smell: `product_quick_delete` always rebuilds the full `_products_context` (including the batched `batches_for_products` query and the paginated `list_products_view` query) even when the POST fails validation or the target product doesn't exist (`quick_delete_product` silently no-ops and returns `(False, {})` for an unknown id — see `test_quick_delete_product_idempotent_on_unknown_or_deleted`). There's no 404 for a bogus `product_id` on this endpoint; a POST to `/products/does-not-exist/quick-delete` returns 200 with the current (unfiltered) product list, silently discarding the invalid id. This is consistent with the pre-existing `quick_delete_product` service contract (not introduced by this diff) and is low risk since the endpoint is same-origin/POST-only, but it is a silent-failure pattern that could mask a future stale-page-reference bug (e.g., a delete link race, an already-deleted product's link left in a cached page) without any operator-visible signal.
**Fix:** Optional: consider having `quick_delete_product` distinguish "unknown id" from "blocked, positive stock" if useful for debugging, or add a debug log line when `quick_delete_product` returns a no-op for an unknown id. Not required for this phase.

## Info

### IN-01: `product_rows.html` header comment omits the new `batches_by_id` context key

**File:** `app/templates/partials/product_rows.html:1-5`
**Issue:** The file-level comment enumerates the context variables the partial expects (`rows`, `page/total/total_pages/page_window`, `code/name/category/sort`, `list_url`, `rows_target_id`, `extra_qs`, `blocked_id/blocked_qty`) but was not updated when `batches_by_id` was added in this same phase (`app/routes/products.py:81`). A future reader relying on this comment as the source of truth for what the partial needs would miss the batch-breakdown dependency.
**Fix:**
```jinja
{# ... extra_qs, blocked_id/blocked_qty (LIST-01..05, Phase 14), batches_by_id
   (Phase 19, PROD-04, batched non-N+1 query via batches_for_products). #}
```

### IN-02: Batch breakdown shows no warehouse column when a product's open batches span multiple warehouses

**File:** `app/templates/partials/product_rows.html:77-95`
**Issue:** `batches_for_products()` groups strictly by `product_id`, not `(product_id, warehouse_id)`, so if a product has open batches in two different warehouses, the collapsed breakdown lists them together with no way to tell which batch is in which warehouse. This matches `19-UI-SPEC.md:115` verbatim (headers are "Срок годности"/"Партия"/"Остаток" only, no warehouse column specified), so it is an intentional scope decision, not a defect against the contract — flagged here only as a forward-looking usability note for whenever Phase 20 (Warehouses & Batch-Split Transfers, already listed as an `affects:` dependency in `19-01-SUMMARY.md`) increases multi-warehouse batch splitting.
**Fix:** No action needed for this phase; consider a warehouse column or a warehouse filter toggle in a future warehouse-aware iteration of this table.

---

_Reviewed: 2026-07-16_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
