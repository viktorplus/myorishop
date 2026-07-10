# Pitfalls Research

**Domain:** Retrofitting multi-warehouse + batch/lot stock tracking onto an existing single-quantity-per-product inventory app (MyOriShop v1.1 "Multi-Warehouse & Batch Tracking")
**Researched:** 2026-07-10
**Confidence:** HIGH for architecture-fit findings (grounded in direct reading of `app/models.py`, `app/services/ledger.py`, `app/services/sales.py`, `app/services/stock.py`, `app/services/reports.py`, `app/services/writeoffs.py`, `app/services/returns.py`, `app/services/corrections.py`, `app/services/receipts.py`, `app/services/catalog.py`, `app/services/export.py`, `app/templates/base.html`, `app/templates/partials/sale_row.html`, `app/static/style.css`, `alembic/versions/*`, `.planning/PROJECT.md`). MEDIUM for generic multi-location-inventory domain color (web search, marketing-oriented sources, cited at the bottom) used only to round out the generic Performance/UX tables.

**Note:** This supersedes the v1.0 pitfalls research (SQLite/money/ledger fundamentals, dated 2026-07-08) which is already-addressed groundwork baked into the shipped architecture. This file is scoped specifically to what breaks when v1.1's multi-warehouse + batch/lot features are added on top of that architecture.

## Critical Pitfalls

### Pitfall 1: `Product.quantity` stops being "the" stock number, but every read path still trusts it alone

**What goes wrong:**
`Product.quantity` (D-09) is currently the single authoritative cached projection of `SUM(operations.qty_delta)` per product, updated atomically inside `record_operation()` (`product.quantity = Product.quantity + qty_delta`, IN-02). Once stock is split by warehouse + batch, this one number becomes, at best, a rollup — but `app/services/stock.py` (`low_stock_products`, `all_active_products`), `app/services/reports.py`, `app/services/corrections.py` (counted-mode baseline), and the sale/write-off oversell checks in `app/services/sales.py` / `app/services/writeoffs.py` all read `product.quantity` directly today. If a `batches` table is added with its own `quantity` cache but `Product.quantity` isn't kept as a genuinely correct rollup updated in the *same* write, you get two independently-drifting notions of "how much stock exists."

**Why it happens:**
The natural incremental path is "add a `batches` table with its own `quantity` column, leave `Product.quantity` alone for now, wire it up later." That's exactly how the drift starts — two denormalized caches, one write path (`record_operation`) that initially only updates one of them.

**How to avoid:**
Decide explicitly, before writing any migration: `Product.quantity` becomes a derived rollup of all its batches' quantities, updated by the same SQL-side atomic increment, in the *same* `record_operation` call that increments the batch's quantity — never as a separate later step. Every operation that changes stock must carry a `batch_id` (see Pitfall 4) so `record_operation` can update both the batch row and the product row in one transaction, mirroring the existing IN-02 pattern.

**Warning signs:**
- Two code paths that each do `some_row.quantity = SomeModel.quantity + delta` for the same operation.
- A report or low-stock check that reads `product.quantity` while another screen (e.g. the batch picker) shows per-batch remaining that doesn't sum to it.
- `rebuild_stock()` (ledger.py) recomputing product totals correctly while batch totals stay wrong because it was never extended (see Pitfall 6).

**Phase to address:**
Phase 1 of this milestone (schema + ledger write-path changes), before any UI work.

---

### Pitfall 2: Oversell checks are duplicated across services and keyed by `product_id` only — batches need a different key

**What goes wrong:**
`register_sale` (sales.py) aggregates requested quantity **per `product.id`** across every basket line (`requested_by_product: dict[str, int]`) before comparing to `product.quantity` — explicitly to prevent the same product appearing on two lines from bypassing the check (existing code comment: "Pitfall 6"). `register_writeoff` (writeoffs.py) does a simpler single-line check against `product.quantity`. Neither has any concept of "batch." Once a sale line references a specific batch, an operator adding the same product twice with **two different batches** on one basket must be validated against *each batch's own remaining quantity*, not the product's total. If the existing product-keyed aggregation is left as-is and a `batch_id` field is bolted on without joining the aggregation key, a basket like "5 units from batch A (which only has 2 left) + 5 units from batch B (which has 50 left)" passes the check (10 requested ≤ 52 total) while silently overselling batch A.

**Why it happens:**
The aggregation key (`product.id`) is deeply embedded in `sales.py`'s oversell logic and is the easiest thing to leave unchanged while adding a batch selector as "just another form field."

**How to avoid:**
Change the aggregation key from `product.id` to `(product.id, batch.id)` in `register_sale`'s oversell block, and compare against the batch's own cached quantity, not the product's. Audit `register_writeoff`/`register_correction` too — explicitly decide whether write-offs/corrections also operate at batch granularity (see Pitfall 3), or document that they intentionally stay product-level, because right now both silently assume "one stock number per product."

**Warning signs:**
- A test basket with two lines of the same product code but different batches passes oversell validation when it shouldn't.
- `requested_by_product` (or its renamed equivalent) is still typed as `dict[str, int]` keyed by a single id after batches ship.

**Phase to address:**
Phase covering batch/lot tracking + sale-time batch picker (LOT-01/LOT-02). Must ship together with Pitfall 1's schema change — cannot be deferred without leaving a real oversell hole.

---

### Pitfall 3: Stock correction's "counted" mode computes delta against the wrong (aggregate) baseline

**What goes wrong:**
`register_correction` (corrections.py) has a `count` mode where the operator enters the *physically counted* quantity and the service computes `qty_delta = counted - product.quantity`. This assumes the operator counted **all** stock of that product everywhere. Once stock is split across warehouses/batches, an operator counting *one warehouse's shelf* will type a number that only reflects that location — but the code diffs it against the product's grand total across all warehouses/batches, producing a `qty_delta` that corrupts stock everywhere except the counted location (e.g., silently subtracting stock that was correctly sitting in a different warehouse or batch).

**Why it happens:**
The correction form (`partials/correction_form.html`, `correction_lookup.html`) currently round-trips only a product code + a single quantity; the "counted" semantics were correct for a single-quantity-per-product model and become silently wrong the moment the baseline is actually a sum of several numbers.

**How to avoid:**
Correction must become scoped: require selecting a warehouse + batch when correcting (mirroring the sale batch picker) and diff against that batch's cached quantity — do not let the existing single-number `count` mode survive unchanged with a batch dropdown quietly bolted on. If a whole-product recount mode is kept, it must be a distinct, clearly-labeled path, not the default.

**Warning signs:**
- A correction QA test: count one batch, and watch the product-level total *and* a different, untouched batch's number both change.
- Correction form UI shows a batch picker, but `register_correction`'s `qty_delta = counted - product.quantity` line is untouched.

**Phase to address:**
Same phase as Pitfall 1/2 (batch schema + ledger writes) — at minimum, block/hide count-mode-against-total once a product has more than one batch, or the ledger gets corrupted the first time someone uses corrections after batches ship.

---

### Pitfall 4: Putting `warehouse_id`/`batch_id` only in `Operation.payload` (JSON) instead of real, indexed FK columns

**What goes wrong:**
`Operation.payload` is a JSON blob used today only for auxiliary, non-aggregated data (write-off reason/note, price-change old/new values, receipt's `catalog_cents`). `Operation.product_id` — the field every report and the ledger's `SUM(qty_delta)` groups by — is a real FK column with an index. If `batch_id`/`warehouse_id` are added as payload keys "to avoid a migration," every per-batch stock computation (oversell checks, the batch picker's "remaining qty" column, the batch-level `rebuild_stock` equivalent) has to filter/group by a JSON field SQLite cannot index — slow, and it cannot use `GROUP BY` cleanly the way `product_id` does today.

**Why it happens:**
Payload feels like the path of least resistance because it already exists and needs no migration — but it was designed for *descriptive*, non-aggregated fields, not for a value the system needs to `SUM()`/`GROUP BY` on every sale.

**How to avoid:**
Add `batch_id` (FK to a new `batches` table) and `warehouse_id` (FK to a new `warehouses` table, or derivable via the batch, since a batch belongs to one warehouse) as real, indexed, nullable columns on `Operation`, mirroring exactly how `product_id` and `sale_id` are modeled — nullable so historical pre-migration rows don't need a value (see Pitfall 7), indexed because every oversell check and the batch-picker's remaining-quantity display will filter/group by it on every request.

**Warning signs:**
- Any new query using `func.json_extract(Operation.payload, '$.batch_id')`.
- Batch remaining-quantity computed by looping Python-side over all ops for a product rather than one indexed `SUM ... WHERE batch_id = ?`.

**Phase to address:**
Phase 1 of this milestone, as an Alembic migration (`render_as_batch=True`, matching every prior migration in `alembic/versions/`).

---

### Pitfall 5: Sale/receipt price-cost freeze must snapshot the *batch's* price, not the product card's

**What goes wrong:**
Today, `register_sale` freezes `unit_cost_cents=product.cost_cents` (D-11) and takes the operator-entered `unit_price_cents` per line — there is exactly one cost/price source: the product card. Once batches carry their own distinct cost/price (LOT-01), a sale line's frozen cost must come from the **selected batch**, not the product card, or profit reports silently use a stale/wrong number instead of the batch actually sold from — breaking the existing "historical profit reports never change when today's prices change" guarantee (SAL-05), which batches are supposed to make *more* accurate, not less.

**Why it happens:**
`unit_cost_cents`/`unit_price_cents` freezing already exists and "just works" for the product-level model; it's easy to leave the freeze source as `product.cost_cents` and add `batch_id` only for *display* purposes without rewiring what actually gets frozen.

**How to avoid:**
Once a batch is selected at sale time, `unit_cost_cents` must be frozen from the batch's own cost field, and any price pre-fill must pull from the batch, not the product card. If batch prices ever become editable after creation, apply the same "snapshot the OLD value before mutating" discipline already used in `register_receipt`'s price_change block.

**Warning signs:**
- A sale test with two batches of the same product at different costs, both sold; the profit report shows the same (wrong) cost for both lines.
- `sales_profit_report` (reports.py) numbers stop matching a manual per-batch reconciliation.

**Phase to address:**
Same phase as batch/lot tracking (LOT-01/LOT-02) — not deferrable, since the profit reports already shipped in v1.0 and are actively relied on; a silent regression here is worse than a missing feature.

---

### Pitfall 6: `rebuild_stock()`/`compute_stock()` have no repair path for the new batch-level cache

**What goes wrong:**
`app/services/ledger.py`'s `compute_stock`/`rebuild_stock` are the FND-01 guarantee: the cached `Product.quantity` is "always recomputable" from the ledger alone, and this is the disaster-recovery tool if the cache ever drifts (bug, crash mid-write, manual DB edit). If a new `batches.quantity` cache is added without an equivalent recompute/repair function, that guarantee silently stops covering the numbers the batch picker and oversell checks actually depend on — the *new*, more failure-prone caches are exactly the ones with no safety net.

**Why it happens:**
`rebuild_stock` iterates `Product` rows and calls `compute_stock(session, product.id)`, both scoped to `product_id` only; extending them to also rebuild batch-level quantities is easy to forget because the function "already exists and already works" for the product level.

**How to avoid:**
Extend `compute_stock`/`rebuild_stock` (or add sibling functions with the same shape) to recompute `SUM(qty_delta)` grouped by `(product_id, batch_id)` and repair every batch's cached quantity in the same pass, in the same transaction, using the same "recomputable from the ledger alone" contract.

**Warning signs:**
- A manual DB edit or a bug leaves a batch's cached quantity wrong, and there is no documented/tested way to fix it short of hand-editing the DB.
- `rebuild_stock`'s docstring/tests still say "including soft-deleted" products but say nothing about batches.

**Phase to address:**
Same phase as Pitfall 1 (schema + ledger writes) — a repair tool shipped alongside the new cache, not bolted on after the first production drift incident.

---

### Pitfall 7: Migrating existing rows — NOT NULL FK columns on non-empty tables, and basket array-index misalignment

**What goes wrong:**
Two related migration risks:
1. **Schema:** `products`, `operations`, and `sales` already have real rows once this app is in daily use. Adding `warehouse_id`/`batch_id` and making them `NOT NULL` without first backfilling every existing row with a value fails the migration outright, or leaves pre-migration operations silently unattributed to any warehouse/batch.
2. **UI/forms:** the sale basket (`partials/sale_row.html`) uses parallel array-named inputs (`code[]`, `qty[]`, `price[]`) that `non_blank_lines()` (sales.py) `zip()`s together **positionally** — the posted arrays carry no explicit row id (DOM row ids like `row-3` never reach the server). Adding a `batch_id[]` array for the batch picker means a 4th parallel array that MUST stay index-aligned with the other three. The existing "Удалить строку" button just does `this.closest('tr').remove()` client-side; if the batch-picker fragment for a row isn't removed in lockstep, a submitted basket can end up with `batch_id[2]` describing a different logical line than `code[2]` — silently attributing a sale to the wrong batch.

**Why it happens:**
(1) is the classic "migration works on an empty test DB, breaks on the first real dataset" trap. (2) is specific to this codebase's row-array pattern, which was designed for exactly 3 aligned arrays and has no defensive index/row-id validation today.

**How to avoid:**
For (1): add `warehouse_id`/`batch_id` as **nullable** columns first; write a data-migration step that creates a single default "legacy"/"Основной склад" warehouse (and a default "legacy" batch if needed) and backfills existing rows to reference it — matching the existing project convention of `is not None` checks (never bare `or`) so a genuinely-unset historical row stays distinguishable from an explicit default. For (2): extend `non_blank_lines()`'s zip and the route's line-building to include `batch_id[]` as a 4th strictly-aligned array, and add a test basket that adds/removes rows out of order before submitting, specifically to catch index drift.

**Warning signs:**
- A migration that adds a NOT NULL FK with no default and no backfill step, tested only against a fresh empty DB.
- Manual QA: add 3 basket rows, delete the middle one, fill the remaining two with different batches, submit, and check the recorded batch_id actually matches the product on that line.

**Phase to address:**
Migration backfill: Phase 1 (schema). Basket array alignment: the batch-picker UI phase (LOT-02) — write this test before the picker ships.

---

### Pitfall 8: New minimum-sale-price field must repeat the exact `is not None` effective-threshold pattern — a bare `or` silently disables an explicit 0

**What goes wrong:**
The codebase already hit this bug once and fixed it: `effective_low_stock_threshold` (stock.py) and `_effective_stale_days` (reports.py) both use `product.field if product.field is not None else settings.default` specifically because a naive `product.field or settings.default` would treat an explicit `0` as falsy and wrongly fall through to the global default. The new optional per-product minimum sale price (PRICE-01) is the same shape of feature (per-product override, global-or-none fallback) and is at real risk of reintroducing exactly this bug — e.g. "minimum price of 0" is a legitimate value that a bare `or` would silently misinterpret as "not set."

**Why it happens:**
It's a new field likely implemented by copy-pasting the sale-price-entry code path, not the threshold-fallback code path, so the existing convention isn't automatically inherited.

**How to avoid:**
Implement the minimum-price check with the identical `is not None` guard, cross-referencing `effective_low_stock_threshold`/`_effective_stale_days` in a comment. Add a unit test asserting a minimum price of exactly `0` cents is honored (warns on any sale price below it) and is not treated as "no minimum."

**Warning signs:**
- Code review sees `product.min_price_cents or ...` anywhere.
- A product with `min_price_cents = 0` never triggers the warning — identical in shape to the low-stock-threshold bug this project already fixed once.

**Phase to address:**
The phase implementing PRICE-01 (minimum sale price / warn-but-allow).

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| Store `batch_id`/`warehouse_id` in `Operation.payload` JSON instead of real FK columns | No migration needed right away | Every oversell/rollup query becomes an unindexed JSON scan; batch-level `rebuild_stock` can't repair it (Pitfalls 4/6) | Never — this app's whole ledger design already treats FK columns as the correct pattern for anything aggregated |
| Keep `register_correction`'s count-mode diffing against `product.quantity` (grand total) even after batches ship, "just for now" | Correction feature doesn't need touching this milestone | First real-world use after batches exist corrupts stock at every batch/warehouse except the one counted (Pitfall 3) | Only if count-mode is explicitly disabled/hidden the moment a product has >1 batch, with a clear UI message, until reworked |
| Skip backfilling a default "legacy" warehouse/batch for existing rows, leave `warehouse_id`/`batch_id` NULL forever | Simpler migration | Every report/query that groups by warehouse or batch must special-case NULL as "unattributed," forever, in every phase after this one | Acceptable only as a deliberate, documented permanent design (NULL = "pre-migration, no location known") |
| Ship the batch picker without extending the CSV export (products/sales dumps) to include batch/warehouse columns | Export code untouched this milestone | Operator's own backup/export data becomes less detailed than the app's UI, and profit reconciliation against the sales export loses batch-level cost granularity (Pitfall 5) | Acceptable for one milestone if explicitly logged as an open gap in PROJECT.md, not acceptable to leave silently forever |

## Integration Gotchas

Not applicable in the usual external-service sense (no external services) — the closest equivalent is the app's own read/export layers being blind to the new granularity.

| "Integration point" | Common Mistake | Correct Approach |
|-------------|----------------|-----------------|
| CSV export (`app/services/export.py`) | Leave `stream_products_csv`'s "Остаток" column as the product-level rollup only, with no per-batch/per-warehouse breakdown | Add batch/warehouse columns (or a 4th export stream) so exported data matches what the UI now shows |
| Reports (`app/services/reports.py`) | `sales_profit_report`/`writeoff_report`/`stale_products` keep grouping strictly by `product.id`, silently hiding which warehouse/batch drove a number | Decide per-report whether warehouse/batch breakdown is in scope for this milestone; if not, say so explicitly rather than let it look already handled |
| Alembic migrations | Add the new FK columns and stop, assuming SQLite will "just work" like Postgres on partial constraints | Every new constraint needs `render_as_batch=True` (already the project convention) plus an explicit backfill step for existing rows |

## Performance Traps

Patterns that work at small scale but fail as usage grows. Reality check: still one operator, so absolute scale stays low — the real risk here is unbounded per-product history (batches accumulate over years), not concurrent load.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Batch picker queries all batches for a product with no filter/ordering | Sale-lookup HTMX response grows slowly as a long-lived product accumulates dozens of exhausted (0-qty) batches over years | Filter to batches with quantity > 0 (or show exhausted ones only on demand), order by expiry, cap the list | Noticeable once a fast-moving product has 50+ historical batches |
| Computing per-batch remaining quantity via a Python-side loop over all `operations` rows instead of an indexed `SUM ... WHERE batch_id = ?` | Batch picker slows as the ledger grows, even for a single product lookup | Aggregate via SQL (`func.sum`/`.group_by()`), matching the existing `top_selling_products`/`compute_stock` pattern | Becomes visible after a year or two of daily receipts/sales once `operations` has tens of thousands of rows |

## Security Mistakes

Domain-specific issues beyond general web security (trusted single-operator local app — the bar is "don't corrupt data," not "don't leak data").

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trusting a client-submitted `batch_id`/`warehouse_id` without re-validating server-side that it belongs to the product/warehouse on that line | A crafted/stale form submission (stale HTMX fragment, browser back-button resubmit) attributes a sale to an unrelated batch, corrupting that batch's stock and freezing the wrong cost/price | Server-side: re-look-up the batch by id, verify `batch.product_id == product.id` before writing, exactly as `register_return` already re-validates `origin.type == "sale"` before trusting a client-supplied `origin_op_id` |
| Trusting a minimum-sale-price / oversell "confirm" flag from a hidden form field without re-running the check server-side | An operator's stale page (or crafted request) sets `confirm=1` on a basket that was never actually shown the warning | Already correctly done today for oversell (`confirm != "1"` gate re-runs every submission); replicate exactly for minimum-price warn-but-allow |

## UX Pitfalls

Common user experience mistakes specific to this milestone's features.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Batch picker shows every batch including fully exhausted (0-qty) ones, unsorted | Operator wastes clicks/scroll finding a batch that actually has stock, especially on a small phone screen | Sort by expiry date (soonest first) or remaining qty; de-emphasize or hide 0-qty batches by default |
| Expiry date field (LOT-03) is stored but never surfaced as a warning anywhere | Stock quietly expires with no signal to the operator, defeating the point of tracking expiry | Even a minimal "batches expiring within N days" line on the stock/low-stock report closes this gap — flag as an explicit scope decision, not an accidental omission |
| Mobile nav bar (`base.html`) is a flat `<nav>` with 10 links and no collapse/hamburger behavior | On a phone-width screen the nav wraps into a multi-row ragged block above every page | Add a `@media (max-width: ...)` collapse (even a simple `<details>`-based disclosure, no JS framework needed) as part of the mobile-responsive item (UI-01) |
| Wide fixed-column tables (reports, `/history`, and the new batch-picker's price/expiry/qty/comment columns) have no horizontal-scroll wrapper | On a narrow phone screen a `<table>` either overflows the viewport or squishes columns unreadably | Wrap every data table in a `<div style="overflow-x:auto">` (or a shared CSS class) rather than trying to make table columns reflow — matches the "no framework, vendor a small CSS file" stack decision already made |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Batch/lot tracking (LOT-01):** Often missing the actual per-batch cached quantity repair path — verify `rebuild_stock` (or its batch-scoped sibling) can recompute every batch's quantity from the ledger alone, not just the product total.
- [ ] **Manual batch selection at sale (LOT-02):** Often missing server-side re-validation that the submitted `batch_id` actually belongs to the submitted product — verify a crafted/stale request with a mismatched batch is rejected, not silently written.
- [ ] **Oversell check after batches ship:** Often still keyed by `product_id` only — verify a basket with the same product split across two batches is validated per-batch, not per-product-total (Pitfall 2).
- [ ] **Multiple warehouses (WH-01):** Often modeled as free text instead of a real table — verify warehouses have their own id/table (so stock can be reliably grouped/filtered), distinct from the free-text location tag within a warehouse (WH-02).
- [ ] **Category browsing page (CAT-01):** Often reuses the raw free-text `Product.category` for grouping — verify near-duplicate categories differing only by case/whitespace/Cyrillic-fold don't fragment into separate groups (mirrors the already-fixed `name_lc` Cyrillic-case bug, D-27).
- [ ] **Minimum sale price (PRICE-01):** Often implemented with a bare `or` fallback — verify an explicit minimum of exactly 0 is honored, not treated as "unset" (Pitfall 8).
- [ ] **Mobile-responsive layout (UI-01):** Often "done" by just confirming the viewport meta tag exists — verify actual `@media` breakpoints exist in `style.css` (currently zero) and every wide table/basket/nav element has been checked at a real narrow width (360-400px), not just resized on a laptop.
- [ ] **CSV export / backup:** Often left untouched after a data-model change — verify the batch/warehouse dimension is either included in `app/services/export.py`'s dumps or explicitly documented as an out-of-scope gap.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|-----------------|
| Batch/product cache drift (Pitfall 1/6) | LOW, if a rebuild function exists | Run the batch-scoped `rebuild_stock` equivalent to recompute every batch (and the product rollup) from `SUM(operations.qty_delta)` grouped by `batch_id`/`product_id` — this is exactly why FND-01's "always recomputable" contract must be extended, not just kept for products |
| Correction "counted" mode corrupted a non-counted batch (Pitfall 3) | MEDIUM | Every write is an immutable ledger row (never UPDATE/DELETE), so the bad correction op is still visible in `/history`; write a compensating `correction` op restoring the affected batch's quantity, and fix the count-mode logic before it happens again — never hand-edit `products`/`batches` rows directly |
| Wrong batch attributed to a sale line due to array index drift (Pitfall 7) | MEDIUM-HIGH | Same recovery pattern: use the existing partial-return machinery to reverse the wrongly-decremented batch and a manual correction against the batch that should have been sold from, with a note explaining the reattribution — do not try to mutate the original `sale` operation, it is append-only by design (DB trigger enforced) |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Two independently-drifting stock caches (product vs batch) | Phase 1 — schema + ledger write path | After any receipt/sale/writeoff/correction, `product.quantity` equals `SUM` of that product's batch quantities, checked by an automated test |
| 2. Oversell check keyed by product, not (product, batch) | Batch/lot + sale-picker phase | Test: same product, two batches, one nearly empty — basket oversells only the empty batch and is caught |
| 3. Correction count-mode diffs against the wrong baseline | Phase 1 (block/redesign) | Test: count one batch, assert no *other* batch's or the product's unrelated total changes incorrectly |
| 4. `batch_id`/`warehouse_id` as JSON payload instead of FK columns | Phase 1 — schema migration | Migration review: both are real indexed nullable FK columns on `operations`, mirroring `product_id`/`sale_id` |
| 5. Sale freeze uses product-card price/cost instead of batch's | Batch/lot + sale-picker phase | Test: two batches with different costs, both sold — profit report shows the correct, distinct cost per line |
| 6. No repair path for batch-level cache | Phase 1, alongside the schema change | A `rebuild_stock`-equivalent function exists and is tested for batches, not just products |
| 7. NOT NULL migration on non-empty tables / basket array misalignment | Phase 1 (migration), batch-picker phase (array alignment) | Migration tested against a DB seeded with pre-existing rows, not just an empty one; a basket test adds/removes rows before submit and checks batch attribution |
| 8. Minimum price bare-`or` bug recurrence | Minimum-sale-price phase (PRICE-01) | Unit test: `min_price_cents = 0` still triggers the warning path |
| Mobile nav overflow / non-scrollable wide tables | Mobile-responsive phase (UI-01) | Manual check at 360-400px viewport width: nav collapses or wraps cleanly, every data table scrolls horizontally instead of breaking layout |
| Warehouse-as-free-text vs real entity | Multi-warehouse phase (WH-01/WH-02) | Warehouses list comes from a real table with stable ids, not a distinct-values query over a text column |
| Category grouping fragmented by case/whitespace | Category browsing phase (CAT-01) | Two products entered as "Косметика" and "косметика " (trailing space) land in the same group on the browsing page |

## Sources

- Direct reading of this repository (HIGH confidence — primary source for every architecture-specific pitfall above): `app/models.py`, `app/services/ledger.py`, `app/services/sales.py`, `app/services/stock.py`, `app/services/reports.py`, `app/services/writeoffs.py`, `app/services/returns.py`, `app/services/corrections.py`, `app/services/receipts.py`, `app/services/catalog.py`, `app/services/export.py`, `app/templates/base.html`, `app/templates/partials/sale_row.html`, `app/static/style.css`, `alembic/versions/0001..0005`, `.planning/PROJECT.md`.
- General multi-location/batch inventory practitioner guidance (MEDIUM/LOW confidence, marketing-oriented sources, used only for generic domain color in the Performance/UX sections, not as primary evidence for any architecture-specific claim):
  - [A Simple Guide to Multi-Location Inventory Management](https://www.inflowinventory.com/blog/multi-location-inventory-management/)
  - [Multi Location Inventory Management: Tools, Strategies & Best Practices](https://www.kladana.com/blog/inventory-management/multi-location-inventory-management/)
  - [Multi-Location Inventory Management: A Complete Guide](https://www.digit-software.com/blog/multi-location-inventory-software)
  - [7 Multi-Location Inventory Management Tips to Optimize Your Business | Sortly](https://www.sortly.com/blog/multiple-location-inventory-management/)
  - [Multi-Location Inventory Management: What to Know Before You Scale](https://www.handifox.com/handifox-blog/multi-location-inventory-management)

---
*Pitfalls research for: MyOriShop v1.1 — Multi-Warehouse & Batch Tracking*
*Researched: 2026-07-10*
