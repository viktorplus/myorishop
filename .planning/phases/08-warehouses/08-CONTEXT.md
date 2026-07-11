# Phase 8: Warehouses - Context

**Gathered:** 2026-07-11
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers WH-01 only: operators can create, edit, and soft-delete/restore multiple physical warehouses through a dedicated management page. It introduces the `Warehouse` model as a standalone reference table, seeded with one default warehouse via the migration so v1.0 data is unaffected.

**Explicitly out of scope for this phase** (deferred to Phase 9, "Batch Tracking & Ledger Integration", per ROADMAP.md):
- Any FK/wiring from `Product` or `Operation` to `Warehouse` — that connection is made via `Batch.warehouse_id` in Phase 9, not here.
- Per-batch storage-location tag (WH-02, e.g. "стеллаж А3") — lives on `Batch`, not on `Warehouse`.
- Warehouse selection in sale/receipt/write-off/correction forms — those forms don't exist for batches yet.

</domain>

<decisions>
## Implementation Decisions

### Warehouse ↔ stock attribution (the central architectural decision)
- **D-01:** `Warehouse` is a **standalone table** in this phase — no FK added to `Product` or `Operation`. Modeled directly on the `Dictionary` precedent (migration 0002): a new table introduced with zero wiring into existing tables. The real stock↔warehouse link (`Batch.warehouse_id`) is Phase 9's job, per the ROADMAP.md dependency note ("structural prerequisite for Phase 9 — `Batch.warehouse_id` needs `Warehouse` to exist first").
- **D-02:** Success criterion 2 ("all existing v1.0 stock is automatically attributed to a seeded default warehouse after migration, with no data loss") is satisfied **conceptually**, not via an explicit FK row-by-row: the migration seeds exactly one default `Warehouse` row (via `op.bulk_insert`, same pattern as migration 0001's initial seed), and nothing is lost because nothing yet references warehouses to lose. Do NOT add a `Product.warehouse_id` column — that would model a false 1-product-to-1-warehouse relationship that Phase 9 immediately breaks (a product code can span multiple batches across multiple warehouses, LOT-01).
- **D-03:** Phase 9's `Batch` migration is expected to point its default "legacy batch" at this same seeded default-warehouse row (Phase 9 success criterion 5 already commits to a default legacy batch). Downstream planners for Phase 9 should treat the seeded warehouse's identity (e.g., a stable name or a documented lookup) as something Phase 9 can rely on.

### Warehouse fields
- **D-04:** `Warehouse` has `name` (required) **plus an optional free-text address/note field** — mirrors the `Customer` model's optional-extras pattern (`surname`, `consultant_number`: nullable, no uniqueness enforced). Exact column name is the planner/executor's call (e.g. `address` or `note`).
- **D-05:** Standard soft-delete/audit columns matching the `Product`/`Customer` convention: `id` (UUID String(36) PK via `new_id`), `created_at`/`updated_at` (`utcnow_iso`), `deleted_at` (nullable, soft-delete only, no hard deletes).

### Default warehouse deletion guard
- **D-06:** Soft-deleting the last remaining **active** warehouse uses the **warn-but-allow** pattern already established for oversell (`app/services/sales.py`) and below-minimum-price (Phase 7) — a warning block requiring one extra confirm click, not a hard block. This keeps the interaction language consistent app-wide; soft-delete is already fully reversible via restore, so nothing is destroyed either way.
- **D-07:** This guard governs *deletion*, not *consumption*. Phase 9's batch-creation flow must still defensively handle a "zero active warehouses" state on its own (e.g., clear message, disabled form) — it cannot assume the Phase 8 guard makes that state impossible forever (a fresh/test DB or manual data edit could still reach it).

### Management page style
- **D-08:** Single settings-style page (`/warehouses`), **not** a full Products-style list+search+`/new`+`/{id}/edit` CRUD scaffold. Modeled on the existing `Dictionary` page pattern (`app/routes/dictionary.py`, `app/templates/pages/dictionary.html`, `app/templates/partials/dictionary_rows.html`): one page, inline add row, inline per-row edit, `hx-post`/`hx-swap="outerHTML"` against a shared rows partial.
- **D-09:** Unlike `Dictionary` (which has no delete today), this page adds inline delete/restore buttons directly in the row table — both active and soft-deleted warehouses stay visible in the same list (deleted rows shown distinctly, e.g. grayed out, with a "Восстановить" button), so a deleted warehouse is never a dead end reachable only via a direct edit URL. This is a deliberate deviation from the Products pattern (where a soft-deleted item disappears from the list entirely and is reachable only via `/products/{id}/edit`) — Products' pattern was rejected specifically because it creates a discoverability trap for a small, rarely-changing entity set. Reuse the existing `hx-confirm` delete / restore convention from `app/routes/products.py` for the actual delete/restore actions.
- **D-10:** No search bar, no pagination — matches the roadmap's own phrasing ("a warehouse management page", singular) and the expected cardinality (a handful of physical locations for a single small reseller, not hundreds).

### Claude's Discretion
- Exact column name for the optional address/note field (`address` vs `note` vs similar).
- Exact route module placement (new `app/routes/warehouses.py` vs. folding into an existing module) — new module is the obvious fit given `Dictionary`/`Product`/`Customer` precedent, but final call is the planner's.
- Exact partial filename for the rows table (suggested `warehouse_rows.html`, mirroring `dictionary_rows.html`).
- How exactly the active-row edit state and deleted-row restore state are visually/structurally distinguished in the single rows table (mirrors the existing `error_entry_id`-style branching already used in `dictionary_rows.html`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & requirements
- `.planning/PROJECT.md` — v1.1 milestone goal, constraints (integer-cents money, soft-delete-only, no global roles), WH-01 requirement.
- `.planning/REQUIREMENTS.md` — WH-01 full requirement text and traceability (confirms WH-02/LOT-01..05 are Phase 9, not Phase 8).
- `.planning/ROADMAP.md` §"Phase 8: Warehouses" — goal, success criteria, and the explicit dependency note naming `Batch.warehouse_id` (Phase 9) as the consumer of this phase's `Warehouse` table.
- `.planning/ROADMAP.md` §"Phase 9: Batch Tracking & Ledger Integration" — success criterion 5 (default legacy batch for existing stock/sales history) that this phase's seeded default warehouse must support without rework.

No external ADRs/specs beyond the above — requirements are fully captured in the Decisions section above plus the existing codebase precedents listed in Existing Code Insights.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/models.py` `Dictionary` — closest structural precedent for `Warehouse`: simple table, no FK from `Product`, introduced standalone in migration 0002.
- `app/models.py` `Product`/`Customer` — soft-delete/audit column convention (`id: UUID String(36)`, `created_at`/`updated_at` via `utcnow_iso`, `deleted_at` nullable) to copy for `Warehouse`.
- `app/routes/dictionary.py`, `app/templates/pages/dictionary.html`, `app/templates/partials/dictionary_rows.html`, `app/services/dictionary.py` — direct template for the single-page inline-CRUD structure; needs delete/restore added net-new (Dictionary itself has none today).
- `app/routes/products.py` (`product_delete`, `product_restore`) — reuse the existing `hx-confirm` + `HX-Redirect`-or-partial-refresh soft-delete/restore convention for the new inline delete/restore buttons.
- `app/services/sales.py` (oversell warn-but-allow) and the Phase 7 min-price warning (`confirm=1` gate, `.error-block` partial) — pattern to mirror for the "delete last active warehouse" warning.
- `alembic/versions/0001_initial_schema.py` (`op.bulk_insert` seed pattern) — reuse for seeding the one default `Warehouse` row in this phase's migration.
- `alembic/versions/0002_catalog_dictionary.py` through `0006_...` — migration conventions: native `ADD COLUMN`/new-table (no batch mode), files never reference application modules (frozen values only).

### Established Patterns
- Soft delete via `deleted_at IS NULL` filtering, applied consistently across catalog views — no hard deletes anywhere in the codebase.
- Warn-but-allow: a read-only check runs before any DB write; a `confirm` flag bypasses it; zero-write until confirmed.
- Money stored as `Integer` cents everywhere — not directly relevant to `Warehouse` (no money fields), but a reminder for any future field additions.
- UUID String(36) surrogate PK on every table (frozen Phase 1 convention), never int autoincrement.

### Integration Points
- New nav link in `base.html` for `/warehouses`.
- New route module `app/routes/warehouses.py` (suggested) with page + inline add/edit/delete/restore routes.
- New service module `app/services/warehouses.py` (suggested, mirroring `app/services/dictionary.py`) for the CRUD + warn-but-allow-last-warehouse logic.
- New model `Warehouse` in `app/models.py`.
- New Alembic migration `0007_warehouses.py` (next revision after `0006`), adding the table and seeding the default row.

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups or external references given. The `Dictionary` page IS the concrete reference for the page's inline-CRUD shape; the oversell/min-price warning partials ARE the concrete reference for the last-warehouse-deletion warning.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No scope-creep items were raised. (Warehouse-to-stock wiring, per-batch location tags, and warehouse selection in operation forms were all recognized as Phase 9 territory during discussion, not pulled into this phase.)

</deferred>

---

*Phase: 8-Warehouses*
*Context gathered: 2026-07-11*
