# Phase 8: Warehouses - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-11
**Phase:** 8-Warehouses
**Areas discussed:** Привязка остатков к складу, Поля склада, Защита склада по умолчанию, Стиль страницы управления

---

## Привязка остатков к складу (Warehouse ↔ stock attribution)

| Option | Description | Selected |
|--------|-------------|----------|
| (a) Temporary `Product.warehouse_id` FK, seeded to default warehouse | Interim FK on Product now, expected to be dropped/migrated when Phase 9 introduces `Batch.warehouse_id` | |
| (b) `Warehouse` standalone table, seeded default row, no FK on Product/Operation | Mirrors the `Dictionary` precedent (migration 0002); real stock↔warehouse link deferred to Phase 9's `Batch.warehouse_id` | ✓ |

**User's choice:** (b) Standalone table (advisor-recommended)
**Notes:** Advisor research confirmed option (a) would model a false 1-product-to-1-warehouse relationship that Phase 9 immediately breaks (LOT-01 allows multiple batches per product across warehouses). ROADMAP.md's dependency note names `Batch.warehouse_id`, not `Product.warehouse_id`, as the actual consumer.

---

## Поля склада (Warehouse identity fields)

| Option | Description | Selected |
|--------|-------------|----------|
| Bare minimum — `name` only | Mirrors `Dictionary` (code+name lookup table) | |
| `name` + optional free-text address/note | Mirrors `Customer`'s optional-extras pattern (surname, consultant_number) | ✓ |

**User's choice:** name + optional address/note
**Notes:** Advisor recommended name-only as the tighter fit for Phase 8's stated criteria, but user opted for the richer option (address/note field), matching the `Customer` precedent.

---

## Защита склада по умолчанию (Default warehouse deletion guard)

| Option | Description | Selected |
|--------|-------------|----------|
| Hard block | Reject deleting the last active warehouse outright | |
| Warn-but-allow | Same confirm=1 pattern as oversell / below-minimum-price warnings | ✓ |
| No special guard | Matches current Product deletion (no "last one" check) | |

**User's choice:** Warn-but-allow (advisor-recommended)
**Notes:** Keeps the interaction language consistent with the rest of the app (oversell, min-price warnings). Phase 9's batch-creation flow still needs to defensively handle a zero-active-warehouse state regardless of this guard.

---

## Стиль страницы управления складами (Management page style)

| Option | Description | Selected |
|--------|-------------|----------|
| Full CRUD (Products pattern: list+search, /new, /{id}/edit) | Proven pattern, scales well | |
| Hybrid: list + separate /new and /{id}/edit, deleted rows shown inline | Middle ground | |
| Single settings-style page, inline add/edit/delete/restore (Dictionary pattern) | Matches expected small/rarely-changing warehouse count; deleted rows stay visible/restorable in the same table | ✓ |

**User's choice:** Single page, inline (advisor-recommended)
**Notes:** Advisor flagged that the Products pattern (deleted item vanishes from the list, restorable only via a direct edit URL) is a discoverability trap for a small entity set — this was the deciding factor against the Products-style approach.

---

## Claude's Discretion

- Exact column name for the optional address/note field (`address` vs `note`).
- Exact route module placement (new `app/routes/warehouses.py` assumed).
- Exact partial filename for the rows table (suggested `warehouse_rows.html`).
- How the active-edit vs. deleted-restore row states are visually/structurally distinguished in the single rows table.

## Deferred Ideas

None — discussion stayed within Phase 8 scope. Warehouse-to-stock wiring, per-batch location tags, and warehouse selection in operation forms were all recognized as Phase 9 territory, not pulled into this phase.
