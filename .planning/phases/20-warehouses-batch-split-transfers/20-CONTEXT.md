# Phase 20: Warehouses & Batch-Split Transfers - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Operator manages warehouses through dedicated forms (not inline row-editing) and can split part of a batch out — under a different expiry date or condition — into a new destination batch, whether or not that split also moves the stock to a different warehouse. The already-shipped delete-guard (WH-03: a warehouse holding stock cannot be deleted) is not touched, only exercised through the new UI shape.

**Explicitly NOT in this phase:** No new warehouse-level fields beyond WH-01's two read metrics (item count, last receipt date). No change to `Batch.price_cents` inheritance rules on transfer — only expiry/comment(condition) become overridable. No mobile transfer flow changes beyond whatever the desktop route/service changes force (`app/routes/mobile_transfers.py` was not scouted this session — verify during planning whether it calls into `register_transfer` and needs the same override fields).

</domain>

<decisions>
## Implementation Decisions

### Warehouse dedicated forms (WH-02)

- **D-01: Picker list + single dedicated edit/delete page (Option B).** `/warehouses` becomes a plain picker table (name, address, item count, last receipt date — no inline `<input>` edit fields, no inline delete). Clicking a row's "Изменить" link navigates to `GET /warehouses/{id}/edit`, which hosts both the edit form and the delete action (with the existing warn-then-confirm / stock-blocked logic). `GET /warehouses/new` is the separate add form. This matches WH-02's own wording ("pick-a-warehouse-then-edit/delete flow") exactly, one destination for edit+delete, not two.
- **D-02: The existing warn-then-confirm and stock-blocked delete UI (WH-03 guard, already correct in `app/services/warehouses.py`) must be ported from its current in-list-row rendering to the edit page** — this is a real rework of the response shape (partial-swapped-in-list → page-level), not a copy-paste. `soft_delete_warehouse`'s guard logic itself is untouched; only where/how its warning renders changes.
- Rejected: Option A (full Products mirror, keeping an inline quick-delete link in the list in addition to edit-page delete) — two delete entry points is more than WH-02's text asks for. Rejected: Option C (add-only dedication, edit/delete stay inline) — does not close WH-02 for edit/delete.

### Item count & last receipt date (WH-01)

- **D-03: "Item count" = distinct product count**, i.e. `COUNT(DISTINCT Batch.product_id)` per warehouse, filtered to `quantity > 0`. Chosen over total units (`SUM(quantity)`) and open-batch count. Open-batch count was explicitly rejected: XFER-01 ships in this same phase and batch-split transfers would inflate a batch-count metric with zero change in actual stock, undermining the number the phase itself introduces.
- **D-04: "Last goods receipt date" = a single grouped query for the whole page of warehouse ids**, not N+1 per row: `outerjoin(Operation, (Operation.batch_id == Batch.id) & (Operation.type == "receipt"))` joined to `Batch.warehouse_id`, `func.max(Operation.created_at)`, `group_by(Batch.warehouse_id)`. Model directly on `app/services/reports.py::stale_products`'s `outerjoin` + `func.max(...)` + `group_by` shape — this codebase's established anti-N+1 precedent for "last X date per parent row" (the `outerjoin`, not an inner join, so a warehouse with zero receipts still appears with `None`, not disappears).
- Both counts must be computed as page-wide grouped queries (IN(...) over the current page's warehouse ids), mirroring `app/services/batches.py::batches_for_products`'s "one query per page, not per-row" pattern — never per-row queries in a loop.

### Batch-split transfer semantics (XFER-01)

- **D-05: One unified form covers both scenarios (Option 3).** Extend the existing `/transfers` form with optional destination-batch override fields (new expiry date, new condition/comment) AND relax `SAME_WAREHOUSE_ERROR` so submitting the same warehouse as source and destination becomes the in-place "split" operation (no separate route/service, no second UI for the operator to learn). The ledger layer (`record_operation`) has no warehouse-equality constraint to fight — this was verified, not assumed.
- **D-06: When destination warehouse == source warehouse, at least one override field (expiry or condition/comment) is REQUIRED — block with a validation error if both are blank.** This prevents a meaningless empty duplicate batch (same product, same warehouse, same expiry, same comment) from being created by mistake. Cross-warehouse transfers (destination ≠ source) keep today's behavior: override fields stay optional, blank means inherit from source, exactly as `register_transfer` already does.
- **D-07: `register_transfer`'s existing `dest = Batch(...)` construction is the extension point** — add two optional params (new expiry, new comment) that override `source.expiry`/`source.comment` when non-blank, falling back to the source's values when blank (mirrors the direct-assignment-never-bare-`or` convention already used for `price_cents` in that same constructor, per the file's own D-05 comment — a legitimate blank must not silently become "keep old value" via a falsy-string trap; treat "field present but blank" as "no override" explicitly, not via `or`).
- **D-08: Removing/relaxing `SAME_WAREHOUSE_ERROR` changes tested behavior** — `tests/test_transfers.py` currently asserts this guard fires for same-warehouse submissions; that test's premise needs to change to "same warehouse + no override fields → blocked (D-06's new error), same warehouse + at least one override → allowed."
- **D-09: `_dest_warehouses()` in `app/routes/transfers.py` currently filters the destination `<select>` to exclude the source batch's own warehouse** (`app/routes/transfers.py`'s `_dest_warehouses` helper) — this filtering must be removed/changed so the source warehouse becomes a selectable destination option again, otherwise D-05's same-warehouse path is unreachable from the UI.

### Code-review debt closure (not a formal requirement — pre-flagged in STATE.md)

- **D-10: Fix WR-01 (batch-ownership leak) in BOTH `app/routes/transfers.py` AND `app/routes/writeoffs.py`.** Both files' POST create handlers (`transfers_create` at `transfers.py:130`, and the equivalent in `writeoffs.py:123`) currently do `session.get(Batch, batch_id.strip())` with no ownership/product-match check before re-rendering `selected_batch` into the picker on error/oversell/exception branches — this can leak another product's batch data into the picker UI. Port the same 4-line ownership guard already proven in each file's own `*_batch_pick` endpoint (`transfers_batch_pick` at `transfers.py:93-96`, `writeoff_batch_pick` at `writeoffs.py:85-88`): reject `candidate.product_id != product.id` before assigning `selected_batch`.
- **D-11: Fix WR-02 (unstripped qty echo) in `transfers.py` ONLY.** `writeoffs.py` already computes the real parsed quantity from `operation.qty_delta` for its success echo — it does not reproduce there; the STATE.md deferred-items note naming both files for WR-02 was imprecise/stale. In `transfers.py`, `register_transfer`'s success return dict needs the actual transferred integer added (not just `{"product", "source", "dest"}`), and `transfers_create`'s `context["saved"]` must use that integer instead of the raw `qty` form string.
- Both fixes are marginal-cost because Phase 20's XFER-01 work rewrites the exact lines (`selected_batch` resolution, context echo, `register_transfer`'s return dict) where these bugs live — fixing now avoids either baking the same unvalidated pattern into new split/override code paths, or a near-immediate second pass.

### Claude's Discretion

- Exact Russian wording for the "override this portion's expiry/condition" fields on the transfer form, and for D-06's new validation error message.
- Whether the edit-page delete button on `/warehouses/{id}/edit` uses a full-page redirect response or an HTMX-driven in-place update, as long as the warn/stock-blocked states remain reachable and legible on that page.
- Whether `app/routes/mobile_transfers.py` needs the same override-field/same-warehouse changes — verify during research/planning whether it calls `register_transfer` directly (likely, per the single-write-path convention) and thread the same optional params through if so.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/REQUIREMENTS.md` — WH-01, WH-02, WH-03, XFER-01 (lines 42-48).
- `.planning/ROADMAP.md` §"Phase 20: Warehouses & Batch-Split Transfers" — goal, 4 success criteria, depends-on note (Phase 18 batch price shape; sequenced after Phase 19 but not blocked by it).
- `.planning/PROJECT.md` §Key Decisions — house conventions (single ledger write path, append-only operations, `Mapped[]`/`mapped_column()` SQLAlchemy 2.0 style).
- `.planning/STATE.md` §Deferred Items — the WR-01/WR-02 code-review debt entry naming Phase 20 as its closing point (D-10/D-11 above).

### Prior art this phase extends (not replaces)
- `app/services/transfers.py::register_transfer` — the existing cross-warehouse transfer with partial-quantity move + fresh destination batch; the extension point for D-05/D-06/D-07.
- `app/routes/transfers.py` — `transfers_create`, `_dest_warehouses()` (D-09's filter to remove), `transfers_batch_pick` (the ownership-check pattern D-10 ports from).
- `app/services/warehouses.py` — `list_warehouses`, `soft_delete_warehouse` (existing WH-03 stock guard + last-active warning, untouched logic; only its rendering location moves per D-02), `add_warehouse`, `update_warehouse`.
- `app/routes/warehouses.py` — current single-page inline-edit implementation (explicitly documented as D-08 gap in its own docstring) being replaced per D-01/D-02.
- `app/routes/writeoffs.py::writeoff_batch_pick` — the ownership-check pattern D-10 ports into `writeoffs.py`'s create handler.

### Precedent patterns to follow
- `app/services/reports.py::stale_products` — the `outerjoin` + `func.max(...)` + `group_by` shape D-04 must mirror for "last receipt date per warehouse."
- `app/services/batches.py::batches_for_products` — the `IN(...)` + Python grouping shape for "one query per page, not per-row," referenced by D-04's page-wide query requirement.
- `app/routes/products.py` + `app/templates/pages/product_form.html` — the dedicated add/edit page pattern (`GET /products/new`, `GET /products/{id}/edit`) that D-01's `/warehouses/new` and `/warehouses/{id}/edit` should structurally follow (routes/service/template layering, redirect-after-POST convention).

### Money and ledger rules
- `CLAUDE.md` §"What NOT to Use" — integer minor units only; portable SQLAlchemy Core/ORM constructs only.
- `CLAUDE.md` §"Stack Patterns by Variant" — append-only operation log; never UPDATE/DELETE its rows.
- `app/services/ledger.py::record_operation` — the single ledger write path; D-05 verified it has no warehouse-equality constraint.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/warehouses.py::soft_delete_warehouse` — already computes `select(func.coalesce(func.sum(Batch.quantity), 0)).where(Batch.warehouse_id == warehouse_id)`, an existing per-warehouse units expression (available if D-03's distinct-product choice ever needs a units figure alongside it, though D-03 itself uses `COUNT(DISTINCT product_id)`, not this sum).
- `app/services/batches.py::open_batches` — `nullslast(Batch.expiry.asc()), Batch.created_at.asc()` ordering convention, reusable if the split/override UI needs to list a product's batches.
- `app/templates/pages/product_form.html` — direct structural template for the new `warehouse_form.html` (dedicated add/edit page shape, redirect-after-POST, delete button with `HX-Redirect`).

### Established Patterns
- Server-rendered Jinja2 + HTMX 2.0.10 (vendored, offline). No SPA, no build step, plain CSS in one stylesheet.
- Route/service/template layering: routes stay thin, all writes live in `app/services/*.py` (stated convention in both `warehouses.py` and `products.py` docstrings).
- Single ledger write path: all `Operation` rows and `Product`/`Batch.quantity` cache updates go through `record_operation` only.
- Money/quantity as integer cents/units end-to-end; `Batch.quantity` is a recomputable cached projection of `SUM(operations.qty_delta)`, never hand-edited.
- Desktop and mobile are separate route/template trees (`app/routes/mobile_*.py`) — verify whether `mobile_transfers.py` needs parity changes (see Claude's Discretion).

### Integration Points
- `app/routes/warehouses.py` and `app/templates/partials/warehouse_rows.html`/`app/templates/pages/warehouses.html` — full restructure per D-01/D-02.
- `app/services/warehouses.py::list_warehouses` — needs D-03/D-04's new grouped queries merged into its return dict (item count, last receipt date per listed warehouse).
- `app/services/transfers.py::register_transfer` and `app/routes/transfers.py` (`transfers_create`, `_dest_warehouses`, `transfers_batch_pick`) — extended per D-05 through D-11.
- `app/routes/writeoffs.py` — touched only for D-10's ownership-check port, no other change.
- `app/templates/pages/transfer_form.html` (and its partials `transfer_lookup.html`, `transfer_batch_wrap.html`) — new override fields (D-05) and same-warehouse destination option (D-09).
- `tests/test_transfers.py` — premise update required per D-08.

</code_context>

<specifics>
## Specific Ideas

- The requirement's own examples for "condition" are concrete and should anchor the UI wording: "damaged packaging" (повреждена упаковка) and "opened sample" (вскрыт образец) — these are in-place, same-warehouse scenarios, which is exactly why D-05 rejected the cross-warehouse-only option.
- WH-02's phrasing "pick-a-warehouse-then-edit/delete flow" was treated as a literal design instruction (D-01), not just a loose gray-area label — it directly named the shape the operator wanted.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. The code-review debt closure (D-10/D-11) is not scope creep: it was pre-flagged in STATE.md as intended for this exact phase, and touches lines this phase rewrites anyway.

</deferred>

---

*Phase: 20-Warehouses & Batch-Split Transfers*
*Context gathered: 2026-07-16*
