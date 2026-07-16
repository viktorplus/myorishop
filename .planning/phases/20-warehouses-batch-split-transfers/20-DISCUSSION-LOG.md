# Phase 20: Warehouses & Batch-Split Transfers - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 20-Warehouses & Batch-Split Transfers
**Areas discussed:** Warehouse dedicated forms (WH-02), Item count & last receipt date (WH-01), Batch-split transfer semantics (XFER-01), Code-review debt closure (WR-01/WR-02)

---

## Warehouse dedicated forms (WH-02)

Research agent produced a 3-option comparison table grounded in `app/routes/warehouses.py` (current inline-edit, D-08-flagged gap) vs. `app/routes/products.py` (existing dedicated-form precedent from Phase 19).

| Option | Description | Selected |
|--------|-------------|----------|
| A — Full Products mirror | Dedicated `/warehouses/new` + `/warehouses/{id}/edit`; list keeps inline quick-delete link (two delete entry points, matching Products exactly) | |
| B — Picker list + single dedicated edit/delete form | List becomes a plain picker table; clicking navigates to one `/warehouses/{id}/edit` page hosting both edit form and delete action | ✓ |
| C — Add-only dedication | Only `/warehouses/new` added; edit/delete stay inline as today | |

**User's choice:** B — matches WH-02's own wording ("pick-a-warehouse-then-edit/delete flow") exactly; also pairs naturally with WH-01's new list columns which don't fit alongside per-row `<input>` edit fields.
**Notes:** Requires porting the existing warn-then-confirm/stock-blocked delete UI from its current in-list-row rendering to the edit page — a real rework, not copy-paste (D-02 in CONTEXT.md).

---

## Item count & last receipt date (WH-01)

Research agent noted the "last receipt date" query shape is not a live choice (a single grouped `func.max` query mirroring `stale_products` is the only option consistent with the codebase's anti-N+1 convention); the real gray area is the definition of "item count."

| Option | Description | Selected |
|--------|-------------|----------|
| Distinct product count | `COUNT(DISTINCT product_id)`, qty>0 — number of different products on the shelf | ✓ |
| Total units | `SUM(quantity)` — total physical stock; expression already exists in `soft_delete_warehouse` | |
| Open batch count | `COUNT(Batch)`, qty>0 — cheapest but inflates when XFER-01 splits a batch | |

**User's choice:** Distinct product count — stable under XFER-01's batch splits (a purely administrative split shouldn't move this number), matches how "item" reads to an operator scanning a shelf.
**Notes:** Batch count was flagged by the research agent as self-contradicting within this same phase (XFER-01 ships alongside it) and effectively ruled out before the question was even asked.

---

## Batch-split transfer semantics (XFER-01)

Research agent confirmed the existing `/transfers` feature already does partial-quantity moves with a fresh destination batch, but hardcodes inheritance of the source's expiry/comment — no override exists, and same-warehouse transfers are currently blocked (`SAME_WAREHOUSE_ERROR`, tested).

| Option | Description | Selected |
|--------|-------------|----------|
| 1 — Override fields only, cross-warehouse required | Add optional expiry/condition fields to the existing form; destination warehouse still can't equal source | |
| 2 — Separate "split batch" operation | New same-warehouse-only route/service, no destination warehouse picker | |
| 3 — Both unified in one form | Override fields + relax same-warehouse restriction so same-warehouse submission becomes the split | ✓ |

**User's choice:** 3 — one form for both scenarios, no duplicated ledger-writing logic, since `record_operation` has no warehouse-equality constraint to fight.
**Notes:** Follow-up question asked and resolved: when destination = source warehouse and neither expiry nor condition override is provided, the submission is now BLOCKED with a validation error (not silently allowed) — prevents a meaningless empty-duplicate batch. This also means `tests/test_transfers.py`'s `SAME_WAREHOUSE_ERROR` assertion needs its premise updated (D-08), and `_dest_warehouses()`'s filter excluding the source warehouse must be removed (D-09).

---

## Code-review debt closure (WR-01 / WR-02, transfers.py / writeoffs.py)

Not a formal requirement — pre-flagged in `.planning/STATE.md`'s Deferred Items table as intended to close "when Phase 20 touches transfers.py." Research agent verified against live code (not just the STATE.md summary) that WR-02 does NOT reproduce in `writeoffs.py` — that file already echoes a correctly parsed quantity; the STATE.md wording naming both files for WR-02 was stale/imprecise.

| Option | Description | Selected |
|--------|-------------|----------|
| WR-01 in both files + WR-02 in transfers.py only | Closes the tracked STATE.md item exactly as pre-designated, mechanical port of the ownership-check guard already proven in each file's own `*_batch_pick` endpoint | ✓ |
| transfers.py only | Strict phase-scope discipline; leaves writeoffs.py's identical ownership gap live | |
| Defer further | Zero added diff this phase; risks baking the same unvalidated pattern into the new XFER-01 override/split code paths being written this same phase | |

**User's choice:** WR-01 in both files, WR-02 in transfers.py only — marginal-cost since Phase 20 already rewrites the exact lines these bugs live in.
**Notes:** None.

---

## Claude's Discretion

- Exact Russian wording for the transfer form's expiry/condition override fields and the new same-warehouse-no-override validation error message.
- Whether the edit-page delete button uses a full-page redirect or an HTMX in-place update (as long as warn/stock-blocked states remain reachable).
- Whether `app/routes/mobile_transfers.py` needs the same override-field/same-warehouse changes threaded through — not scouted this session, flagged for verification during research/planning.

## Deferred Ideas

None — discussion stayed within phase scope.
