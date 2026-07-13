# Phase 12: Code & Name Autofill - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-13
**Phase:** 12-code-name-autofill
**Areas discussed:** Receipt price-data sources, Desktop receipt autofill UX, Mobile receipt autofill approach, Sales reverse search (name → code)

---

## Receipt price-data sources

| Option | Description | Selected |
|--------|-------------|----------|
| A | Exclusive priority chain: Product → Dictionary → CatalogPrice, first hit wins | |
| B | Merge branch: combine Dictionary (name) + CatalogPrice (price) into one `source="catalog"` result | ✓ |
| C | Parallel independent call mirroring `/products/lookup-price`, separate from `lookup_prefill` | |

**User's choice:** B (research-recommended)
**Notes:** PRICE-04's wording ("catalog price, consultant price, and name") reads as a combined autofill, not a fallback chain. `sale` field stays excluded — no source for it in `CatalogPrice`.

---

## Desktop receipt autofill UX

| Option | Description | Selected |
|--------|-------------|----------|
| A | Extend existing `/receipts/lookup` debounced OOB-swap pattern to also fill price for the new `source="catalog"` branch | ✓ |
| B | Explicit "Fill from catalog" button/affordance instead of automatic-on-type | |
| C | New dedicated endpoint mirroring `/products/lookup-price`, second independent `hx-get` | |

**User's choice:** A (research-recommended)
**Notes:** Batch chooser is orthogonal to price data (only reacts to Product existence), so the form's added complexity doesn't entangle with this decision.

---

## Mobile receipt autofill approach

| Option | Description | Selected |
|--------|-------------|----------|
| A | Add live debounced code→price/name autofill to step 1, matching mobile sales | |
| B | Extend the existing step-submit resolve (`mobile_receipt_step_batch`) to forward `prices` into step 3 | ✓ |

**User's choice:** B (research-recommended)
**Notes:** Keeps this phase's scope out of mobile wizard navigation/step-boundary work, which is reserved for Phase 13.

---

## Sales reverse search (name → code)

| Option | Description | Selected |
|--------|-------------|----------|
| A | Reuse `search_products()`/`search_view()` via a new `/sales/search-name` route + click-to-select dropdown | ✓ |
| B | New narrow name-only matcher | |
| C | Native `<datalist>` | |

**User's choice:** A (research-recommended)
**Notes:** Follow-up question locked the trigger threshold at 3 characters minimum before the dropdown fires. Selecting a result fills both code and name directly (no redundant round trip through `/sales/lookup`).

---

## Claude's Discretion

- Exact response fragment/template names and the internal shape of the new `/sales/search-name` route.
- Whether `lookup_prefill()`'s new `source="catalog"` branch is factored as a helper or inline, as long as behavior matches the locked decisions.

## Deferred Ideas

None — discussion stayed within phase scope.
