# Phase 7: Category Browsing & Minimum Price Guardrail - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers two independent, additive capabilities on top of the existing v1.0 catalog and sales flow:

1. **CAT-01** — a new page where operators browse all active products grouped by category/rubric (a read-only browsing view, not a new CRUD surface).
2. **PRICE-01** — an optional per-product minimum sale price. Selling a line below it warns but allows override, mirroring the existing v1.0 oversell warn-but-allow pattern exactly.

No new schema dependency on Warehouses/Batches (Phases 8-9) — this phase only touches `Product` and the existing sale flow.

</domain>

<decisions>
## Implementation Decisions

### Category Browsing Page (CAT-01)
- **D-01:** New top-level nav entry with its own dedicated route: `/categories`. Deliberately NOT merged into the existing `/reports/stock` report (that page's job is low-stock alerting, not general browsing) and NOT nested under `/products` — a separate nav item avoids ambiguity with the existing "Остатки склада" report at `/reports/stock`.
- **D-02:** Row columns, per product: Код, Название, Остаток (quantity), Закупочная (cost), Продажа (sale), Каталог (catalog price), Действия (edit link to `/products/{id}/edit`). No separate "Категория" column — redundant once rows are grouped under a category heading.
- **D-03:** Category groups sorted alphabetically — reuse the same ordering already used for the category `<datalist>` (`catalog.category_options()` style, `.order_by(Product.category)`).
- **D-04:** Products with `Product.category IS NULL` (or empty) go into a visible "Без категории" bucket, sorted last (after all named categories) — NOT hidden. Success criterion 1 requires seeing ALL active products, so silently excluding uncategorized products would fail it.
- **D-05:** Only active products (`Product.deleted_at IS NULL`), same convention as `/products` and all other catalog views.

### Minimum Price Guardrail (PRICE-01)
- **D-06:** New nullable `Integer` column on `Product` for the minimum sale price, stored in cents (suggest `min_sale_cents` to match the existing `cost_cents`/`sale_cents`/`catalog_cents` naming — exact name is the planner/executor's call). **No global-settings fallback** — unlike `low_stock_threshold`/`stale_days` (which fall back to `settings.*` when NULL), NULL here means "no floor is set," full stop. Must be checked with `is not None`, never a bare `or`, so an explicit 0 stays meaningful (success criterion 4).
- **D-07:** Field placed on `product_form.html` immediately **after** "Цена продажи" (`sale`), **before** "Цена по каталогу" (`catalog`). Label: "Минимальная цена продажи" with a muted "(необязательно)" hint — deliberately WITHOUT a "(по умолчанию: N)" hint (unlike `low_stock_threshold`/`stale_days`), since there is no global default to imply. Reuses the same `to_cents()` parsing / `inputmode="decimal"` / `placeholder="0,00"` pattern as the other three price fields.
- **D-08:** The guardrail applies only at **Sale** time. Write-offs and stock corrections have no price field in the current schema, so they are out of scope for this check (PROJECT.md's "same pattern as oversell" refers to the confirm/warn UX pattern, not to which operations it applies to).
- **D-09:** The check is inherently **per-line** (each basket line has its own editable "Цена продажи"), not aggregated like the oversell quantity sum. Compare each line's entered sale price against that line's `product.min_sale_cents`, guarded by `is not None`.
- **D-10:** Boundary is **strict less-than**: `line_price_cents < product.min_sale_cents` triggers the warning; a price exactly equal to the minimum passes silently. This mirrors the existing oversell boundary in `app/services/sales.py` (`requested > quantity` — hitting the limit exactly is fine).
- **D-11:** Warning presentation: **one combined block**, not per-line inline and not a separate confirm step. Add a new partial mirroring `app/templates/partials/sale_oversell.html` (same `.error-block` / `button.danger` styling, same "Продать всё равно" wording), listing every line that is below its product's minimum (product name, entered price, minimum price). It shares the **same `confirm=1` flag** already used for oversell in `register_sale` — no new confirm parameter. If a single submission trips both oversell AND the price floor, the operator sees both blocks stacked in one screen and resolves both with one click. Zero writes happen until `confirm=1` on resubmit (same WR-03-style contract as today).

### Claude's Discretion
- Exact column/field name for the new minimum-price column (suggested `min_sale_cents`, following existing `*_cents` naming).
- Exact route module placement (new `app/routes/categories.py` vs. adding to `app/routes/products.py`) — planner's call, no user preference expressed.
- Exact partial filename for the new price-warning block (suggested `sale_price_warning.html`, mirroring `sale_oversell.html`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project & requirements
- `.planning/PROJECT.md` — v1.1 milestone goal, constraints (integer-cents money, no global currency/roles), Phase 7 requirements (CAT-01, PRICE-01).
- `.planning/REQUIREMENTS.md` — CAT-01 and PRICE-01 full requirement text and traceability.
- `.planning/ROADMAP.md` §"Phase 7: Category Browsing & Minimum Price Guardrail" — goal, success criteria, dependencies.

No external ADRs/specs beyond the above — requirements are fully captured in the Decisions section above plus the existing codebase precedents listed in Existing Code Insights.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/services/catalog.py` — `to_cents()` parser and `category_options()`-style ordered category query; reuse both for the new min-price field and for category-group ordering.
- `app/services/sales.py` (`register_sale`, SAL-04/D-08/D-09 oversell block) — extend with a parallel per-line minimum-price pass sharing the exact same `confirm != "1"` gate and zero-writes-until-confirmed contract.
- `app/templates/partials/sale_oversell.html` — direct template to mirror for the new combined price-warning partial (same CSS classes, same button pattern, same `hx-vals='{"confirm": "1"}'` resubmit).
- `app/templates/partials/sale_form.html` — include the new warning partial alongside the existing `{% if oversell %}` block.
- `app/templates/pages/product_form.html` — the `cost`/`sale`/`catalog` field trio (parsing, layout, error handling) and the `low_stock_threshold`/`stale_days` fields (nullable-Integer-override pattern, `is not None` discipline) are both direct precedents for the new min-price field.
- `app/templates/pages/reports_stock.html` — precedent for an active-products + quantity query, useful for the CAT-01 page's data query even though the page itself stays separate.

### Established Patterns
- Warn-but-allow: a read-only check runs before any DB write; a `confirm` flag bypasses it; the response is zero-write and the basket form stays intact until confirmed (`WR-03`-style contract).
- Money stored as `Integer` cents everywhere — never `FLOAT`/`REAL`.
- Soft delete via `deleted_at IS NULL` filtering, applied consistently across catalog views.
- Optional per-product override fields use nullable `Integer`/`String` columns checked with `is not None`, never a bare `or`, to keep an explicit zero meaningful.

### Integration Points
- New nav link in `base.html` for `/categories`.
- New route (module TBD by planner) rendering the category-grouped page.
- `app/services/sales.py` `register_sale()` — add the price-floor check.
- `app/templates/partials/sale_form.html` — wire in the new warning partial.
- `app/templates/pages/product_form.html` — add the new field.
- `app/models.py` `Product` — add the new column (requires an Alembic migration, `render_as_batch=True`).

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups or external references given beyond "same pattern as oversell" (PROJECT.md) — the codebase precedent (`sale_oversell.html`) IS the specific reference to follow.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. No scope-creep items were raised.

</deferred>

---

*Phase: 7-Category Browsing & Minimum Price Guardrail*
*Context gathered: 2026-07-10*
