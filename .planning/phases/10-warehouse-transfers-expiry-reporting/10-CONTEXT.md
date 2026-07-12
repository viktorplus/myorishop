# Phase 10: Warehouse Transfers & Expiry Reporting - Context

**Gathered:** 2026-07-12
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers two features on top of the Phase 9 batch ledger:

1. **WH-03 — Warehouse transfers:** the operator can move a batch (or part of its quantity) from one warehouse to another without losing cost/price history, and the move is recorded in the operation history like any other stock-affecting operation.
2. **LOT-06 — Expiry report:** a read-only report page listing batches with an approaching or already-passed expiry date.

**Guiding constraint from the user:** *«максимально примитивно»* — for every decision take the simplest option that satisfies the requirement. No configurability, no new surfaces beyond what the two features strictly need.

**Explicitly out of scope for this phase:**
- Any mobile-flow screens (UI-01) — Phase 11.
- Automatic FEFO/FIFO batch selection — permanently out of scope (REQUIREMENTS.md Out of Scope); source-batch selection stays manual.
- CSV export gaining warehouse/batch columns (EXP-V2-01) — deferred milestone-wide.
- A standalone batch-management/CRUD page — still no such page (Phase 9 D-03 carried forward); the transfer page is a single-purpose operation page, not a batch manager.
- Inline "write off from the report" action on the expiry report — the operator uses the existing write-off page (see D-08).
- Configurable expiry threshold / warehouse filter on the report (see D-06).

</domain>

<decisions>
## Implementation Decisions

### Transfer entry point (WH-03)

- **D-01:** Transfers get a **dedicated `/transfers` page**, one per the existing operation-page-per-route convention (receipts, sales, writeoffs, corrections each have their own page + route). Rationale: there is no batch-management surface to hang a per-batch "Переместить" button on (Phase 9 D-03), so a dedicated page is both the simplest and the only viable entry point. A nav link is added in `app/templates/base.html`.
- **D-02:** Transfer flow on that page: operator enters the **product code** → an HTMX lookup lists that product's **open batches** (`quantity > 0`) via the shared `batch_picker.html` partial (reused from Phase 9, D-04) → operator **picks the source batch** → picks a **destination warehouse `<select>`** (active warehouses only; the source batch's own warehouse excluded/disabled so you cannot transfer to the same warehouse) → enters a **quantity** → submits. Reuse the existing lookup + batch-picker interaction machinery rather than inventing new UI.

### Transfer ledger representation (WH-03)

- **D-03:** A transfer is recorded as **two ledger rows in one transaction** through the existing single write path `record_operation()` (staged with `commit=False`, one commit — the multi-line basket discipline): a `transfer` row with **negative** `qty_delta` on the **source batch**, and a `transfer` row with **positive** `qty_delta` on the **destination batch**. Both projections (`Product.quantity` net-zero across the pair, per-`Batch.quantity`) update via the existing SQL-side increment. The append-only triggers are never touched.
- **D-04:** A **new operation type `"transfer"`** is added to `STOCK_AFFECTING_TYPES` in `app/services/ledger.py` (so `batch_id` is mandatory on both rows — source batch on the out row, destination batch on the in row; the existing batch-ownership/tampering guard in `record_operation()` applies unchanged). A RU display label for `"transfer"` (e.g. «Перемещение») is added wherever op types are rendered (`/history` rows, and any op-type label map).
- **D-05:** The **destination batch is always created new**, inheriting `price_cents`, `expiry`, `comment`, and the storage-location tag from the source batch (only `warehouse_id` differs; `is_legacy=0`; a fresh `id`). **No resolve-or-create / top-up matching** at the destination — this is the primitive path chosen by the user and it also sidesteps the known NULL-expiry equality-matching trap (Phase 9 D-01). Cost/price history is preserved precisely because the new batch copies the source's frozen `price_cents`. A full transfer drives the source batch to `quantity = 0` (it drops out of pickers naturally, D-03 semantics); a partial transfer leaves the remainder on the source.
- **D-06 (transfer guardrail):** Transferring **more than the source batch's remaining quantity** reuses the existing per-batch **warn-but-allow** `confirm=1` zero-write re-POST pattern (Phase 9 D-09), scoped to the source batch's remaining quantity. (Implementation detail — follow the established pattern; not a new interaction.)

### Expiry report — threshold & scope (LOT-06)

- **D-07:** The report shows **ALL open batches that have a set expiry date, with NO threshold** (user decision, chosen over a fixed 30-day window as even simpler). Scope: batches with `quantity > 0` **and** a non-NULL `expiry`. Legacy batches (NULL expiry) are excluded automatically by that filter. Sorted **earliest expiry first** (`nullslast` not needed since NULL is filtered out — but reuse the `open_batches` ordering idiom). Expired batches (`expiry < today`) are **visually marked** (e.g. a muted/red note or a «просрочено» badge) but stay in the same list. Columns include product, warehouse, expiry date, remaining quantity, price, comment. **No warehouse filter** and **no period filter** (kept primitive; the `/reports/*` `period_filter.html` is NOT reused here — expiry is not a period query).

### Expiry report — actions & placement (LOT-06)

- **D-08:** The report is **read-only**, served at **`/reports/expiry`** inside the existing `/reports/*` family (mirrors `/reports/stock`), with a **link added on the reports landing** (`app/templates/pages/reports_landing.html`, alongside «Остатки склада», «Списания», etc.). **No inline write-off/list action** — to remove an expired batch the operator uses the existing write-off page and its batch picker. Nav stays under the existing «Отчёты» entry in `base.html` (no new top-level nav item for the report).

### Claude's Discretion
- Exact `/transfers` route/handler and template/partial filenames, and how the destination-warehouse `<select>` excludes the source warehouse (server-filtered list vs disabled option).
- Exact RU label string for the `transfer` op type and how the two paired rows are rendered/grouped in `/history` (two lines vs one combined line — either is acceptable as long as both directions are visible).
- Exact query/service shape for the expiry report (new helper in `app/services/batches.py` vs `app/services/reports.py`) and the expired-marker styling.
- Whether the transfer service lives in a new `app/services/transfers.py` or extends an existing module.
- Index/query specifics for the expiry query.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & requirements
- `.planning/PROJECT.md` — v1.1 milestone goal, constraints, Out of Scope (no auto-FEFO/FIFO, no CSV batch columns, integer-cents money).
- `.planning/REQUIREMENTS.md` — WH-03 and LOT-06 full requirement text and traceability (both are the only two open v1.1 requirements before Phase 11's UI-01).
- `.planning/ROADMAP.md` §"Phase 10: Warehouse Transfers & Expiry Reporting" — goal and the 3 success criteria (transfer preserves cost history; transfer recorded in history; expiry report page).

### Prior phase contracts (critical — this phase rides entirely on Phase 9)
- `.planning/phases/09-batch-tracking-ledger-integration/09-CONTEXT.md` — the whole batch architecture: D-03 (no batch CRUD page), D-04 (shared `batch_picker.html`), D-09 (per-batch warn-but-allow), D-10/D-11/D-12 (ledger `batch_id`, cached `Batch.quantity` projection, `record_operation()` as single write path), D-01 (NULL-expiry matching trap — the reason D-05 avoids destination matching).
- `.planning/phases/08-warehouses/08-CONTEXT.md` — warehouse identity/soft-delete semantics; the destination `<select>` lists active warehouses only.
- `.planning/research/ARCHITECTURE.md` — milestone-level architecture research (append-only ledger, batch projection).

### Ledger invariants (critical)
- `alembic/versions/0001_initial_schema.py` — frozen append-only trigger DDL (`operations_no_update`/`operations_no_delete`); transfers add rows only, never mutate.
- `alembic/versions/0008_batches.py` — the `Batch` model/table shape (columns to copy when creating the destination batch: `price_cents`, `expiry`, `comment`, location tag, `is_legacy`).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/ledger.py` `record_operation()` — single write path; already accepts `batch_id`, enforces batch ownership, updates dual projection. Transfer = two calls (source −qty, destination +qty) staged in one transaction. `STOCK_AFFECTING_TYPES` (line ~18) gains `"transfer"`.
- `app/services/batches.py` `open_batches()` — powers the source-batch lookup on `/transfers`; its `quantity > 0` + expiry-ordering idiom is the basis for the expiry-report query.
- `app/templates/partials/batch_picker.html` (Phase 9 D-04) — reused to present the source batch list on the transfer page.
- `app/services/receipts.py` / the `/receipts/lookup` server-decides HTMX fill contract — the code-lookup interaction the transfer page mirrors.
- `app/services/writeoffs.py` / `sales.py` — the `confirm=1` zero-write warn-but-allow oversell gate that D-06 reuses for the transfer over-quantity guard.
- `app/templates/pages/reports_landing.html` + `app/routes/reports.py` (`/reports/stock` etc.) — the read-only report page pattern `/reports/expiry` follows; add the landing link here.
- `app/templates/partials/history_rows.html` — where the new `"transfer"` op type gets its RU label and rendering.

### Established Patterns
- Append-only ledger, DB-trigger-enforced; `record_operation()` is the only writer of operation rows and quantity caches; multi-row operations stage with `commit=False` + one commit (transfer's two rows follow this).
- `Batch.quantity` is a cached projection maintained SQL-side inside `record_operation()`; `rebuild_stock()` invariant `Product.quantity == SUM(active batches)` must still hold after a transfer (net-zero product delta).
- Warn-but-allow: read-only check → `confirm=1` bypass → zero writes until confirmed.
- UUID String(36) PKs, integer-cents money, UTC ISO text timestamps, soft-delete via `deleted_at` (Batch has none, D-03 carried forward).
- Migrations use native `ADD COLUMN`/new-table only (batch mode drops triggers) and never import app modules. NOTE: this phase likely needs **no migration** — `transfer` is a value in the existing `operations.type` column and the destination batch is an ordinary `batches` row. Confirm during planning.

### Integration Points
- `app/services/ledger.py` — add `"transfer"` to `STOCK_AFFECTING_TYPES`.
- New transfer service (`app/services/transfers.py` suggested) — validate source batch/qty, create destination batch, call `record_operation()` twice, warn-but-allow over-qty guard.
- New `app/routes/transfers.py` + templates — `/transfers` page, code lookup, batch picker reuse, destination-warehouse select, submit + confirm re-POST; router registration; nav link in `base.html`.
- `app/services/batches.py` (or `reports.py`) — expiry-report query (open batches with non-NULL expiry, earliest first).
- `app/routes/reports.py` + new `reports_expiry.html` page + landing link — `/reports/expiry` read-only report.
- `app/templates/partials/history_rows.html` — `"transfer"` op-type label + rendering.

</code_context>

<specifics>
## Specific Ideas

No external mockups. All concrete references are in-repo: the `/receipts/lookup` HTMX fill contract, the shared `batch_picker.html`, the `confirm=1` warn-but-allow gate, and the `/reports/*` read-only report family. Phase 10 extends these rather than inventing new interaction machinery. The user's one explicit steer is *«максимально примитивно»* — reflected in D-05 (always-new destination batch, no matching), D-07 (no expiry threshold at all), and D-08 (read-only report, no inline actions).

</specifics>

<deferred>
## Deferred Ideas

- Configurable expiry threshold / "expiring within N days" filter on the report — deliberately dropped for primitiveness; could return in a later polish pass.
- Warehouse filter on the expiry report — same.
- Inline "write off this expired batch" action from the report — the operator uses the existing write-off page instead; revisit if it proves annoying.
- Resolve-or-create / top-up of the destination batch (merge with an existing matching batch instead of always creating new) — deferred; only relevant if batch clutter appears (mirrors Phase 9's deferred "merge batches" idea).

None of the above is required by WH-03 / LOT-06.

</deferred>

---

*Phase: 10-Warehouse Transfers & Expiry Reporting*
*Context gathered: 2026-07-12*
