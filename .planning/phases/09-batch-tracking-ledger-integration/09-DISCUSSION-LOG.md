# Phase 9: Batch Tracking & Ledger Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-11
**Phase:** 9-Batch Tracking & Ledger Integration
**Areas discussed:** Batch creation & receipt flow, Batch picker in operation forms, Ledger schema & batch quantities, Legacy data migration
**Mode:** Advisor (4 parallel research agents, calibration tier: standard)

---

## Batch creation & receipt flow

| Option | Description | Selected |
|--------|-------------|----------|
| Resolve-or-create with operator choice | After code+warehouse, HTMX shows open batches; operator picks "top up existing" or "new batch" (advisor-recommended; matches .planning/research/ARCHITECTURE.md receipt flow) | ✓ |
| Always new batch | Every receipt line creates a fresh batch — minimal change, but catalog-period reorders clutter the sale picker | |
| Silent server-side auto-merge | Match on (product, warehouse, expiry, price) — invisible magic, NULL-expiry matching trap, rejected | |

**User's choice:** Resolve-or-create with operator choice (recommended option).
**Notes:** Receipt form gains required warehouse select (default preselected) + optional expiry/location/comment. No new price input — Batch.price_cents snapshots the existing "Цена продажи" field. No standalone batch-management page.

---

## Batch picker in operation forms

| Option | Description | Selected |
|--------|-------------|----------|
| Inline batch table under the line | Code lookup swaps in a table (price/expiry/remaining/comment), radio + hidden batch_id[]; batch price pre-fills line price (advisor-recommended) | ✓ |
| Per-line `<select>` dropdown | All four attributes crammed into one option string — hard to compare, comments truncate | |
| Explicit pick step with chip | Customer-picker pattern; cleanest for many batches but +1 mandatory click per line | |

**User's choice:** Inline batch table (recommended option).
**Notes:** Single matching batch = auto-selected with visible "Партия выбрана автоматически — единственная" note. Ordering: earliest expiry first, NULL last. Return does NOT re-ask — targets the origin sale line's batch (legacy batch fallback for pre-Phase-9 sales). Per-batch oversell reuses confirm=1 warn-but-allow.

---

## Ledger schema & batch quantities

| Option | Description | Selected |
|--------|-------------|----------|
| A: Nullable batch_id column, NULL=legacy (display-side) | Native add_column per migration 0004's sale_id precedent; triggers untouched; cached Batch.quantity in record_operation (advisor-recommended) | ✓ |
| B: Backfill old rows | Drop triggers → UPDATE historical ops → recreate; uniform rows but mutates the append-only ledger | |
| C: batch_id in JSON payload | No schema change but no index/FK; contradicts sale_id precedent | |
| D: No cached Batch.quantity | Compute on the fly — breaks symmetry with Product.quantity, impossible for seeded legacy batches | |

**User's choice:** Option A with cached Batch.quantity (recommended option).
**Notes:** batch_id required at service level for qty_delta != 0 types; audit ops stay batch-less. rebuild_stock gains per-batch pass + Product.quantity == SUM(batches) invariant.

---

## Legacy data migration

| Option | Description | Selected |
|--------|-------------|----------|
| Per-product legacy batch (stock > 0 only) | Quantity seeded from SUM(qty_delta) in plain SQL, default warehouse frozen UUID, expiry/price NULL, name "Остаток до внедрения партий" (advisor-recommended) | ✓ |
| One global legacy batch | Batch without product_id poisons every query; criterion 5 unverifiable — effectively not viable | |
| Legacy price = product card sale_cents | Same as option 1 but price copied at migration time — rejected in favor of honest NULL (card pre-fill remains the fallback) | |

**User's choice:** Per-product legacy batch (recommended option).
**Notes:** Old operation rows untouched; /history renders NULL batch_id with a legacy label/dash at read time.

---

## Claude's Discretion

- Batch model column names, partial filenames, index placement.
- Receipt-form "top up vs new" chooser rendering within the D-01 contract.
- hidden batch_id[] sync wiring and 422 re-echo mechanics.
- Post-selection visual treatment of the batch table (must stay visible/changeable).
- NULL-bucket handling inside rebuild_stock's per-batch recompute.

## Deferred Ideas

- Batch merge/editing tooling (future milestone, only if picker clutter appears).
- Read-only per-product batch list on the product card / CAT-01 page.
