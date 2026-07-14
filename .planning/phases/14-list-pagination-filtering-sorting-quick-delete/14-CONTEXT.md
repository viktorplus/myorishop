# Phase 14: List Pagination, Filtering, Sorting & Quick Delete - Context

**Gathered:** 2026-07-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Every list page in the app (products, warehouses, customers, dictionary, catalogs, history) gets uniform pagination, per-column filtering, and sorting — replacing today's mix of unbounded lists, ad-hoc search boxes, and fixed ordering. Additionally, warehouses and products get a one-click delete action directly from their list row, without opening the detail/edit page. Cross-cutting UI/infra phase, no new capabilities beyond LIST-01..05.

</domain>

<decisions>
## Implementation Decisions

### Pagination
- **D-01:** Page-number style pagination (1 2 3 … Next) uniformly across ALL list pages — not "load more".
- **D-02:** History's existing "Показать ещё" (load-more) pattern is replaced with page-number pagination too, for consistency across the app. This requires adding a total-count query alongside the existing offset pagination in `app/services/operations.py`.
- **D-03:** Page size is a single constant across all lists: **20 rows per page**. Applies to products, warehouses, customers, dictionary, catalogs, and history alike.

### Filters by column
- **D-04:** Filter inputs/selects live **inside the table header row** (per-column), not a single search box above the table and not a separate filter panel. Column filterability per list (which columns get a filter) is left to research/planning to determine per entity's relevant columns.
- **D-05:** Filters apply immediately on input (debounce), matching the existing product/customer search pattern (`hx-trigger="input changed delay:300ms..."`) — no "Apply" button.

### Sorting
- **D-06:** Sorting UI is a **"Сортировать по…" dropdown** near/above the table — not clickable column headers.
- **D-07:** Default order (when nothing selected in the sort dropdown) matches each list's CURRENT default: products/customers by name, warehouses active-first, dictionary by code, history newest-first (`created_at desc, seq desc`), catalogs newest-first by year.

### Quick delete — Products
- **D-08:** Adds a NEW guard: product quick-delete from the list is **blocked if the product has stock on hand > 0** (no existing guard today — `soft_delete_product` currently allows deleting a product with batches/stock still referencing it). This guard did not exist before this phase; it's being introduced specifically for the quick-delete list action.
- **D-09:** Confirmation is a **browser-native `confirm()`** dialog before the delete request is sent (not an inline row confirmation, not a modal).
- **D-10:** After successful delete, the row **disappears from the list entirely** (current behavior for products — no change needed here, deleted products are already filtered out of the list query).

### Quick delete — Warehouses
- **D-11:** Adds a NEW guard: warehouse quick-delete from the list is blocked if the warehouse **still has stock on hand** (not empty) — mirrors the product stock guard (D-08).
- **D-12:** This new "must be empty" guard applies **together with** the existing last-active-warehouse guard (`app/services/warehouses.py:76-102`) — both conditions must pass (warehouse empty AND not the last active warehouse) for quick-delete to succeed. Neither guard replaces the other.
- **D-13:** Confirmation is the same browser-native `confirm()` as products (D-09).
- **D-14:** **Behavior change from today:** after quick-delete from the list, the warehouse row **disappears from the list entirely** — it does NOT stay visible grayed-out with an inline restore button as the current warehouse list does. This changes existing warehouse-list UX (currently deleted warehouses remain visible with `class="muted"` + restore button); that restore-visible behavior is superseded by this phase for the list view. Restore, if still needed, would only be reachable elsewhere (not decided — flag for planner).

### Claude's Discretion
- Exact filterable columns per list (beyond what's implied by existing search behavior) — left to research/planning.
- Exact sort options offered in each "Сортировать по…" dropdown per list.
- Whether/how a restore path for quick-deleted warehouses should be preserved elsewhere, now that the list no longer shows deleted warehouses inline (see D-14) — flag as an open question for planning; not to be silently dropped without a decision.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs, ADRs, or docs were referenced by name during this discussion, and ROADMAP.md's Phase 14 entry lists no "Canonical refs:" line. Requirements are captured directly in REQUIREMENTS.md (LIST-01..05) and the decisions above.

### Existing code that anchors this phase's patterns
- `app/services/operations.py` (history pagination: offset `page`/`page_size=50`, `has_next` sentinel) — the closest existing pagination implementation; needs a total-count addition and page-size change to 20 per D-02/D-03.
- `app/services/warehouses.py:76-102` (`soft_delete_warehouse` last-active guard) — existing guard logic that D-12 adds to, not replaces.
- `app/services/catalog.py:295-301` (`soft_delete_product`) — needs the new stock-on-hand guard (D-08).
- `app/templates/partials/history_filters.html` — existing filter-row pattern (dropdowns) to generalize per D-04.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Debounced `hx-get` + `hx-trigger="input changed delay:300ms..."` pattern (used in product/customer search) — reuse for column-filter inputs per D-05.
- History's offset-pagination service function (`app/services/operations.py:14-53`) — closest existing precedent for page-number pagination; other services (`list_warehouses`, `list_entries`, catalog/customer search) currently return unbounded or hardcoded `.limit(20)` results and need pagination added from scratch.
- `soft_delete_warehouse`'s warn-then-`confirm=1`-repost guard pattern — existing precedent for a blocking guard with operator override, relevant when combining D-11+D-12 (though D-09/D-13 now specify a browser `confirm()` instead of the inline warning UI for the list's quick-delete action specifically).

### Established Patterns
- Plain `<table>` markup per entity, no shared table/list partial or macro exists today — each of `product_rows.html`, `warehouse_rows.html`, `dictionary_rows.html`, `customer_rows.html`, `history_rows.html`, and `catalogs.html` duplicates its own table structure. Whether to introduce a shared partial is an implementation choice for planning, not fixed here.
- `<td class="num">` for money/qty columns, `<span class="muted">—</span>` for empty values, `.empty-state` block — existing conventions to preserve.
- Soft-delete convention: `deleted_at` column on `Product` and `Warehouse` (`models.py:118, 139`); `Batch` (`models.py:142-181`) has no `deleted_at` and hard-FKs both `product_id` and `warehouse_id` — this is why stock-based guards (D-08, D-11) are needed before allowing quick-delete.

### Integration Points
- Products list currently uses `HX-Redirect: /products` on delete (full page reload) — D-10 keeps the row-disappears behavior but the quick-delete-from-list action should use a partial row-removal swap instead of full-page `HX-Redirect`, consistent with an in-list action (flag for planning).
- Warehouses list currently keeps deleted rows visible with a restore button — D-14 changes this specifically for the new quick-delete action; planning needs to decide whether the existing restore-visible list behavior is fully replaced or whether a separate path (e.g., an "Показать удалённые" toggle) preserves restore access.

</code_context>

<specifics>
## Specific Ideas

- Page size: exactly 20, one constant reused everywhere (D-03).
- Confirmation must be the plain browser `confirm()` dialog — no custom modal, no inline "Точно? Да/Нет" row state.
- Warehouse quick-delete needs BOTH guards simultaneously: empty (no stock) AND not the last active warehouse (D-12) — user was explicit that neither guard alone is sufficient.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 14-list-pagination-filtering-sorting-quick-delete*
*Context gathered: 2026-07-14*
