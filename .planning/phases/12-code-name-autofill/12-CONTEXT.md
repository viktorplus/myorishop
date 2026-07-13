# Phase 12: Code & Name Autofill - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Wherever the operator types a product code — product-add form, goods receipt (desktop + mobile), or the sales page — the system surfaces known price/name data instead of requiring a manual lookup, without ever overwriting a value the operator already typed.

**Already shipped on this branch (`feat/catalogs-pricing`), confirmed by code inspection — NOT new work, just needs formalizing:**
- PRICE-02 (catalog + consultant price autofill on product-add form) — `GET /products/lookup-price` in `app/routes/products.py:44-70`, using `latest_price_for_code()` from `app/services/pricing.py:14-32`. Debounced (300ms), OOB-swap into `#catalog`/`#cost`, fill-only-if-empty.
- PRICE-03 (name autofill on product-add form) — `GET /dictionary/lookup` in `app/routes/dictionary.py:27`, renders `partials/name_input.html`. Same debounce pattern.
- SAL-06 first half (code → name inline on sales page) — `GET /sales/lookup` in `app/routes/sales.py`, `lookup_prefill()` in `app/services/sales.py`. Same debounce pattern.

**Actual new work for this phase:**
- PRICE-04: goods receipt price+name autofill for codes not yet in the product catalog (desktop `app/routes/receipts.py` + mobile `app/routes/mobile_receipts.py`).
- SAL-06 second half: name-fragment → code dropdown on the sales page (does not exist anywhere in the app today).

</domain>

<decisions>
## Implementation Decisions

### Receipt price-data sources (PRICE-04)
- **D-01:** When a receipt code is unknown to `Product`, combine Dictionary (name) and `CatalogPrice` (via `latest_price_for_code()`) into a single new `lookup_prefill()` result branch (`source="catalog"`), rather than an exclusive priority chain. If both a Dictionary name and a CatalogPrice price exist for the same unknown code, both surface together — matches the literal PRICE-04 wording ("catalog price, consultant price, and name").
- **D-02:** The `sale` field (this shop's own sale price) is NEVER filled from `CatalogPrice` — `CatalogPrice` only has `consumer_cents` (Oriflame retail/ПЦ → maps to the receipt's `catalog` field) and `consultant_cents` (Oriflame consultant/ОП → maps to `cost`). This mirrors the existing hard boundary already enforced elsewhere (e.g. `sales.py` D-10) between Oriflame's price and the shop's own price.
- **D-03:** The existing `source == "product"` branch (code already in `Product`) is untouched — it keeps filling from the product's own stored `cost_cents`/`sale_cents`/`catalog_cents`, as today.

### Desktop receipt autofill UX
- **D-04:** Reuse the exact same debounced (300ms) OOB-swap pattern already live on `/receipts/lookup` for the `source=="product"` case — extend it to also emit price OOB-swaps (via `receipt_price_inputs.html`, same fill-only-if-empty guard) when `source=="catalog"` (D-01). No new endpoint, no explicit "fill from catalog" button.
- **D-05:** The batch chooser (`#batch-chooser`) is untouched by this work — it already renders the empty/new-batch path whenever `Product` is None, regardless of price data, so there's no interaction to redesign.

### Mobile receipt autofill approach
- **D-06:** Do NOT add live/debounced autofill to the mobile receipt wizard's step-1 code field (that would be new interaction-model surface, and risks pre-empting Phase 13's mobile navigation rework). Instead extend the existing "resolve once per step-submit" pattern: `mobile_receipt_step_batch` (in `app/routes/mobile_receipts.py`) already calls `lookup_prefill()` and gets back a `prices` dict — forward `cost`/`sale`/`catalog` from that call into step 3 (`receipts_step_details.html`, where the actual price fields live) as pre-filled values.
- **D-07:** This decision intentionally stays out of any back-button/step-indicator/navigation changes — those are Phase 13's scope (UI-02..05), not this phase's.

### Sales reverse search (name fragment → code)
- **D-08:** Reuse `search_products()` / `search_view()` (`app/services/catalog.py:347-397`) as-is via a new route (e.g. `/sales/search-name`) — do not build a separate name-only matcher. `search_products` already does ranked (exact code=0, code-prefix=1, name-substring=2), Cyrillic-safe, 20-row-capped search over exactly the `Product` table that sale rows are constrained to.
- **D-09:** Render results as a click-to-select dropdown partial (reusing the `<mark>`-highlighting/two-column code+name row shape already established, not a native `<datalist>` — datalist can't show two columns or highlighting).
- **D-10:** Trigger threshold: the dropdown fires only once the name field has **3 or more characters** typed (guard added in the new route/template — `search_products`'s own empty-query "first 20 by name" fallback is skipped for this live-typing use case).
- **D-11:** On selecting a dropdown result, fill BOTH the code and name fields directly from the clicked row (do not just fill code and let the existing `/sales/lookup` re-fire) — the result already carries both, avoiding a redundant round trip.

### Claude's Discretion
- Exact response fragment/template names and the shape of the new `/sales/search-name` route are left to the planner/executor, as long as they follow D-08 through D-11.
- Whether `lookup_prefill()`'s new `source="catalog"` branch lives in `app/services/receipts.py` or is factored differently is left to the planner, as long as the resulting behavior matches D-01/D-02.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap
- `.planning/REQUIREMENTS.md` — PRICE-02, PRICE-03, PRICE-04, SAL-06 (full requirement text)
- `.planning/ROADMAP.md` — Phase 12 section (goal, success criteria, dependency on Phase 11)

### Existing autofill implementations to mirror/extend
- `app/services/pricing.py` — `latest_price_for_code()` (CatalogPrice lookup, already used by product-add form)
- `app/routes/products.py:44-70` — `/products/lookup-price` (the debounced OOB-swap pattern to replicate on receipts)
- `app/routes/dictionary.py:27` — `/dictionary/lookup` (name autofill pattern)
- `app/services/receipts.py:260-287` — `lookup_prefill()` (needs the new `source="catalog"` branch per D-01)
- `app/routes/receipts.py:102-144` — `/receipts/lookup` (needs price OOB-swap extension per D-04)
- `app/routes/mobile_receipts.py` — `mobile_receipt_step_batch` (needs price forwarding per D-06)
- `app/services/catalog.py:347-397` — `search_products()`/`search_view()` (to reuse per D-08)
- `app/routes/sales.py` / `app/services/sales.py` — `/sales/lookup`, `lookup_prefill()` (existing code→name pattern on sales page)

### Project-level context
- `.planning/PROJECT.md` — Key Decisions table; v1.1 decision "mobile flow reuses existing services unchanged"

No external ADRs/specs beyond the above — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `latest_price_for_code()` (`app/services/pricing.py`) — already returns a `CatalogPrice | None` with `consumer_cents`/`consultant_cents`; ready to call from the receipt path unchanged.
- `search_products()`/`search_view()` (`app/services/catalog.py`) — ranked, Cyrillic-safe, capped fuzzy search with `<mark>` highlighting via `split_match()`; directly reusable for the sales name-dropdown.
- `partials/name_input.html`, `partials/receipt_price_inputs.html`, `partials/product_price_autofill.html` — existing OOB-swap fragment patterns to mirror for the new receipt price fill.

### Established Patterns
- Debounced (300ms) `hx-get` on the code field, fill-only-if-empty, OOB-swap response — used identically on product-add, desktop receipt, and desktop/mobile sales forms. This phase's desktop work (D-04) continues that pattern; explicitly does NOT extend it to mobile receipts (D-06).
- `lookup_prefill()` exists as three near-identical per-form functions (`sales.py`, `corrections.py`, `receipts.py`) — this phase only touches the `receipts.py` one (adds a third branch).

### Integration Points
- `mobile_receipt_step_batch` (step 1→2 transition) is the existing single resolution point for mobile receipt code lookups — step 3 (`receipts_step_details.html`) is where price fields are rendered and where the forwarded price data lands (D-06).
- `sale_row.html`'s existing code field (`hx-get="/sales/lookup"`) sits next to the name field where the new dropdown trigger will be added.

</code_context>

<specifics>
## Specific Ideas

No specific UI mockups or exact wording given — user deferred to the researched recommendations for all four areas, confirming the advisor's rationale (Option B/A/B/A across the four gray areas) without modification, plus one explicit parameter: 3-character minimum before the sales name→code dropdown fires (D-10).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Mobile wizard navigation/step-indicator/back-button work was explicitly kept out (belongs to Phase 13, already on the roadmap).

</deferred>

---

*Phase: 12-code-name-autofill*
*Context gathered: 2026-07-13*
