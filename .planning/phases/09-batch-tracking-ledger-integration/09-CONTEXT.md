# Phase 9: Batch Tracking & Ledger Integration - Context

**Gathered:** 2026-07-11
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers batch/lot-level stock tracking (WH-02, LOT-01..05): a product code can have multiple batches — each with its own warehouse, optional free-text storage-location tag, optional expiry date, price, and optional comment — and every stock-affecting operation (receipt, sale, write-off, return, correction) is attributed to a specific batch. The sale/write-off/correction forms gain a manual batch picker; existing v1.0 stock and history remain intact via per-product legacy batches.

**Explicitly out of scope for this phase:**
- Warehouse transfers (WH-03) and the expiring-batches report (LOT-06) — Phase 10.
- Any mobile-flow screens (UI-01) — Phase 11.
- Automatic FEFO/FIFO batch selection — permanently out of scope (REQUIREMENTS.md Out of Scope); selection stays manual. Sorting the picker by expiry is allowed as a nudge, auto-picking on submit is not.
- CSV export gaining warehouse/batch columns (EXP-V2-01) — deferred milestone-wide.
- A standalone batch-management/CRUD page — batches come into existence only through goods receipts plus the one-time legacy migration (see D-03).

</domain>

<decisions>
## Implementation Decisions

### Batch creation & receipt flow
- **D-01:** Batch creation is **resolve-or-create with operator choice**: after the product code AND warehouse are set on a receipt line, an HTMX lookup loads that product's open batches (quantity > 0) in that warehouse; the operator explicitly chooses "top up an existing batch" or "new batch" (the new-batch fields — expiry, location, comment — are shown only for the new-batch path). No silent server-side auto-merge (rejected: invisible matching logic contradicts the app's explicit-manual-selection philosophy; NULL-expiry equality matching is a known trap).
- **D-02:** The receipt form gains: a **required warehouse `<select>`** preselected to the Phase 8 seeded default warehouse, plus three optional fields per new batch — **expiry date** (LOT-03), **free-text storage-location tag** (WH-02, e.g. "стеллаж А3"), and **comment** (LOT-04). There is NO new price input: `Batch.price_cents` snapshots the existing "Цена продажи" field at batch creation time. Existing cost/sale/catalog semantics (op snapshot + card update) stay untouched; on a top-up the batch's frozen price is NOT rewritten (a changed typed price still updates the product card as today). Zero active warehouses → the form renders a blocking RU hint linking to warehouse creation instead of the batch picker (Phase 8 D-07 carried forward).
- **D-03:** No separate batch-management page in this phase. Batches are born only via receipts + the legacy migration; a batch disappears from pickers when its remaining quantity hits zero. `Batch` gets no soft-delete and no standalone CRUD.

### Batch picker in operation forms (sale, write-off, return, correction)
- **D-04:** Picker presentation is an **inline batch table swapped in under the line by the code lookup** — columns: price, expiry, remaining quantity, comment (all four LOT-02 attributes readable). Selection is a radio row that syncs a per-row hidden `batch_id[]` input (customer-chip precedent) so the basket's parallel-array alignment (`code[]`/`qty[]`/`price[]`) is preserved; a 422 re-render must re-echo the picked batch per row. The same batch-list partial is reused under the single-line write-off and correction forms.
- **D-05:** Picking a batch **pre-fills the line's price with the batch's price** (replacing the current `Product.sale_cents` card pre-fill when a batch price exists), using the existing `hx-swap-oob` + "Цена подставлена — можно изменить" muted-hint convention and the typed-value before-swap guard. The operator can still override the price manually.
- **D-06:** When a product has **exactly one matching batch, it is auto-selected** — but rendered visibly highlighted with a muted note "Партия выбрана автоматически — единственная", and remains changeable. LOT-02's "manually selects" intent is preserved because the selection is visible and reversible; forcing a click on a no-choice decision only slows the operator.
- **D-07:** Batch ordering in the picker: **earliest expiry first, NULL expiry last**, tie-broken by oldest receipt. This nudges FEFO practice without auto-picking (which stays out of scope).
- **D-08:** The **return flow does NOT re-ask for a batch**: a return restores stock to the batch its origin sale line came from. The origin sale op carries its `batch_id`; the return form displays the origin batch info read-only. For pre-Phase-9 sale ops (batch_id NULL), the return targets the product's legacy batch.
- **D-09:** The per-batch oversell/over-removal warning (ROADMAP success criterion 4) plugs into the existing warn-but-allow `confirm=1` zero-write re-POST pattern unchanged — scoped to the picked batch's remaining quantity, not the product total.

### Ledger schema & per-batch remaining quantity
- **D-10:** `Operation` gains a **nullable `batch_id` column via native `op.add_column`** — the exact precedent of migration 0004's `sale_id` (bare column, no DB-level inline FK — Alembic's SQLite dialect raises `NotImplementedError`; ORM-side `ForeignKey` only). The append-only triggers (`operations_no_update`/`operations_no_delete`) are NEVER touched and no historical row is mutated. `batch_id` on ledger rows is set at INSERT time only. Rejected: storing batch_id in the JSON `payload` (no index/FK, contradicts the repo's own `sale_id` precedent, PostgreSQL-portability friction) and backfilling old rows (mutates the ledger the whole architecture protects; risks future sync replay divergence).
- **D-11:** **`Batch.quantity` is a cached projection** maintained inside `record_operation()` exactly like the existing `Product.quantity` — SQL-side increment (`Batch.quantity + qty_delta`), same transaction, both projections updated together. `record_operation()` grows a `batch_id` parameter and stays the SINGLE write path. `rebuild_stock()` grows a per-batch pass plus the invariant check `Product.quantity == SUM(active batches' quantity)` per product.
- **D-12:** `batch_id` is **required at the service level** (raise `ValueError`) for all stock-affecting operation types (`receipt`, `sale`, `writeoff`, `return`, `correction` — qty_delta != 0); the qty_delta == 0 audit types (`price_change`, `product_created`, `product_edited`) stay batch-less (`batch_id=None`). A DB-level NOT NULL is impossible without batch-mode migration (would drop triggers) and NULL is reserved for legacy rows — so the guard lives in `record_operation()`.

### Legacy data migration
- **D-13:** **One legacy batch per product with ledger stock > 0** (no legacy batches for zero-stock products; a single global cross-product batch rejected — a batch without product_id poisons every query and criterion 5 becomes unverifiable per product). Legacy batch quantity is seeded **from `SUM(operations.qty_delta)` computed in plain SQL in the migration — NOT from the `products.quantity` cache** — so success criterion 5 balances even against a stale cache.
- **D-14:** Legacy batch field values (frozen literals in the migration, per repo convention that migrations never import app modules): `warehouse_id` = the re-declared frozen default-warehouse UUID `00000000-0000-4000-8000-000000000010` (Phase 8 D-03 contract), `expiry` = NULL, `price_cents` = NULL (historical price unknown — the picker simply doesn't pre-fill a price for legacy batches; the card `sale_cents` pre-fill remains the fallback), name/comment = frozen string "Остаток до внедрения партий".
- **D-15:** Pre-batch operation rows stay untouched: **`batch_id` NULL means legacy**, resolved display-side. The /history view renders NULL `batch_id` with the legacy label (or a dash) at read time — attribution is a display concern, not a data rewrite.

### Claude's Discretion
- Exact `Batch` model column names and the batch-list partial filename(s).
- Exact shape of the receipt-form batch chooser UI (how "top up vs new" is rendered) within D-01's contract.
- How the per-row hidden `batch_id[]` sync is wired (`hx-on:change` vs alternative), and 422 re-echo mechanics.
- Whether the batch table on a basket line collapses/highlights after selection — any treatment that keeps the selection visible and changeable.
- Index placement for `operations.batch_id` and `batches` table indexes.
- How `compute_stock`-style per-batch recompute handles the NULL-bucket (legacy) special case in `rebuild_stock()`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & requirements
- `.planning/PROJECT.md` — v1.1 milestone goal, constraints, Out of Scope (no auto-FEFO/FIFO, no CSV batch columns).
- `.planning/REQUIREMENTS.md` — WH-02, LOT-01..05 full requirement text and traceability (LOT-06/WH-03 are Phase 10; UI-01 is Phase 11).
- `.planning/ROADMAP.md` §"Phase 9: Batch Tracking & Ledger Integration" — goal and 5 success criteria (incl. criterion 4: oversell scoped per batch; criterion 5: legacy data intact and balancing).
- `.planning/research/ARCHITECTURE.md` — milestone-level architecture research; its receipt data flow (lines ~156-169) and Pattern 3 (Batch has no soft-delete/standalone CRUD) are the basis for D-01/D-03.

### Prior phase contracts
- `.planning/phases/08-warehouses/08-CONTEXT.md` — D-03 (frozen default-warehouse identity for the legacy batch), D-07 (zero-active-warehouses defensive handling is Phase 9's own job).

### Ledger invariants (critical)
- `alembic/versions/0001_initial_schema.py` — frozen trigger DDL (`operations_no_update`/`operations_no_delete`) and the explicit warning that batch-mode (move-and-copy) migrations silently DROP these triggers.
- `alembic/versions/0004_sales_customers.py` — the `sale_id` native-`add_column` precedent D-10 mirrors (incl. the documented Alembic-SQLite inline-FK limitation).
- `alembic/versions/0007_warehouses.py` — frozen `DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"` seed pattern to re-declare in this phase's migration.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/ledger.py` `record_operation()` — the single write path to extend with `batch_id` + the second SQL-side quantity projection (line ~87 pattern: `Product.quantity + qty_delta`).
- `app/services/receipts.py` `register_receipt()` — D-05 resolve-or-create-in-one-transaction discipline (product auto-create) that D-01's batch resolve-or-create mirrors; the `/receipts/lookup` server-decides-fill-vs-204 HTMX contract.
- `app/templates/partials/sale_form.html`, `sale_row.html`, `sale_lookup.html` — the basket's parallel-array inputs (`code[]`/`qty[]`/`price[]`), swap-time typed-value guards, and oob price prefill ("Цена подставлена — можно изменить") that D-04/D-05 extend.
- `app/templates/partials/sale_customer.html` — hidden-input-plus-chip precedent for the per-row hidden `batch_id[]`.
- `app/services/sales.py` `register_sale()` — the confirm=1 zero-write warn-but-allow gate (oversell + below_minimum computed before any early return, both blocks stacked) to extend with the per-batch oversell scope (D-09).
- `app/routes/returns.py` / `app/services/returns.py` — origin-sale-line resolution and frozen price/cost copy that D-08's batch inheritance rides on.
- `app/services/ledger.py` `compute_stock`/`rebuild_stock` — patterns for the per-batch recompute + invariant check (D-11).

### Established Patterns
- Append-only ledger, DB-trigger-enforced; `record_operation()` is the only writer of operations rows and quantity caches; multi-line baskets stage with `commit=False` + one commit.
- Warn-but-allow: read-only check → `confirm=1` bypass → zero writes until confirmed.
- UUID String(36) PKs, integer-cents money, UTC ISO text timestamps, soft-delete via `deleted_at` (note: `Batch` deliberately gets NO soft-delete, D-03).
- Migrations use native `ADD COLUMN`/new-table (no batch mode — it drops triggers) and never import application modules (frozen literal values only).
- Optional fields checked with `is not None`, never bare `or`.

### Integration Points
- `app/models.py` — new `Batch` model; `Operation.batch_id` nullable column.
- New Alembic migration `0008_batches.py` (next after 0007): `batches` table + `operations.batch_id` native add_column + per-product legacy-batch seed computed from ledger SUM.
- `app/services/ledger.py` — `record_operation(batch_id=...)`, dual projection update, `rebuild_stock` invariant.
- New `app/services/batches.py` (suggested) — open-batch queries (quantity > 0, per product/warehouse, D-07 ordering).
- `app/services/receipts.py` + `app/routes/receipts.py` + receipt form partials — warehouse select, batch resolve-or-create chooser, new-batch fields.
- `app/services/sales.py`/`writeoffs.py`/`returns.py`/`corrections.py` + their routes/templates — batch_id parsing, per-batch oversell scope, picker partial wiring.
- `app/routes/history.py` + history partials — NULL-batch legacy label display (D-15).

</code_context>

<specifics>
## Specific Ideas

No external mockups. The concrete references are in-repo: the `/receipts/lookup` and `/sales/lookup` HTMX fill contracts, the customer-picker chip pattern, and the stacked oversell/min-price warning blocks — Phase 9 extends these rather than inventing new interaction machinery.

</specifics>

<deferred>
## Deferred Ideas

- "Merge batches" / batch-editing tooling — only becomes relevant if picker clutter appears despite D-01's top-up path; future milestone.
- Read-only per-product batch list on the product card or the CAT-01 stock page — nice-to-have surface, not required by LOT-01..05; can ride on a later phase.

</deferred>

---

*Phase: 9-Batch Tracking & Ledger Integration*
*Context gathered: 2026-07-11*
