# Phase 12: Code & Name Autofill - Research

**Researched:** 2026-07-13
**Domain:** Internal HTMX autofill patterns (extending an already-shipped ad-hoc feature) — no new external technology
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Receipt price-data sources (PRICE-04)**
- **D-01:** When a receipt code is unknown to `Product`, combine Dictionary (name) and `CatalogPrice` (via `latest_price_for_code()`) into a single new `lookup_prefill()` result branch (`source="catalog"`), rather than an exclusive priority chain. If both a Dictionary name and a CatalogPrice price exist for the same unknown code, both surface together — matches the literal PRICE-04 wording ("catalog price, consultant price, and name").
- **D-02:** The `sale` field (this shop's own sale price) is NEVER filled from `CatalogPrice` — `CatalogPrice` only has `consumer_cents` (Oriflame retail/ПЦ → maps to the receipt's `catalog` field) and `consultant_cents` (Oriflame consultant/ОП → maps to `cost`). This mirrors the existing hard boundary already enforced elsewhere (e.g. `sales.py` D-10) between Oriflame's price and the shop's own price.
- **D-03:** The existing `source == "product"` branch (code already in `Product`) is untouched — it keeps filling from the product's own stored `cost_cents`/`sale_cents`/`catalog_cents`, as today.

**Desktop receipt autofill UX**
- **D-04:** Reuse the exact same debounced (300ms) OOB-swap pattern already live on `/receipts/lookup` for the `source=="product"` case — extend it to also emit price OOB-swaps (via `receipt_price_inputs.html`, same fill-only-if-empty guard) when `source=="catalog"` (D-01). No new endpoint, no explicit "fill from catalog" button.
- **D-05:** The batch chooser (`#batch-chooser`) is untouched by this work — it already renders the empty/new-batch path whenever `Product` is None, regardless of price data, so there's no interaction to redesign.

**Mobile receipt autofill approach**
- **D-06:** Do NOT add live/debounced autofill to the mobile receipt wizard's step-1 code field (that would be new interaction-model surface, and risks pre-empting Phase 13's mobile navigation rework). Instead extend the existing "resolve once per step-submit" pattern: `mobile_receipt_step_batch` (in `app/routes/mobile_receipts.py`) already calls `lookup_prefill()` and gets back a `prices` dict — forward `cost`/`sale`/`catalog` from that call into step 3 (`receipts_step_details.html`, where the actual price fields live) as pre-filled values.
- **D-07:** This decision intentionally stays out of any back-button/step-indicator/navigation changes — those are Phase 13's scope (UI-02..05), not this phase's.
- **D-12:** Narrow exception to D-07 — mobile receipt step 3 (`app/templates/mobile_partials/receipts_step_details.html`) currently renders `code` and `name` as hidden inputs only (confirmed: lines 7 and 9), no visible text. Since D-06 introduces autofilled price values on this exact step, add a minimal static line showing the code/name (already available in the step's context) above the price fields, so an autofilled number is visibly anchored to a product. Scope is deliberately narrow: **only receipt step 3**, **only code+name as plain text** (no styling system, no step-indicator, no back-button change). The full UI-02 sweep (all 5 wizards, every step, warehouse included) remains Phase 13's job — this is a targeted fix for the specific gap Phase 12's own autofill would otherwise expose, not a pull-forward of Phase 13's scope.

**Sales reverse search (name fragment → code)**
- **D-08:** Reuse `search_products()` / `search_view()` (`app/services/catalog.py:347-397`) as-is via a new route (e.g. `/sales/search-name`) — do not build a separate name-only matcher. `search_products` already does ranked (exact code=0, code-prefix=1, name-substring=2), Cyrillic-safe, 20-row-capped search over exactly the `Product` table that sale rows are constrained to.
- **D-09:** Render results as a click-to-select dropdown partial (reusing the `<mark>`-highlighting/two-column code+name row shape already established, not a native `<datalist>` — datalist can't show two columns or highlighting).
- **D-10:** Trigger threshold: the dropdown fires only once the name field has **3 or more characters** typed (guard added in the new route/template — `search_products`'s own empty-query "first 20 by name" fallback is skipped for this live-typing use case).
- **D-11:** On selecting a dropdown result, fill BOTH the code and name fields directly from the clicked row (do not just fill code and let the existing `/sales/lookup` re-fire) — the result already carries both, avoiding a redundant round trip.

**Mobile sales & mobile transfers — discarded-name bugs (found by full 8-menu audit)**
- **D-13 (mobile sales):** `lookup_prefill()` in `app/services/sales.py` already returns `name` alongside `sale` price, fetched by `mobile_sales.py`'s debounced code lookup — but today only the price reaches step 2/3 templates (`sale_step_batch.html`, `sale_step_qty_price.html`); the fetched name is computed and then discarded, so the operator sees no product name until the final basket review. Fix: carry the already-fetched `name` forward through the same context dicts that already carry `code`/price into steps 2-3, and render it as visible text (not just a hidden input) on those steps. Narrow scope: display data the service call already returns today — no new lookups, no change to the step-1 debounce trigger, no styling system, no warehouse visibility, no navigation/back-button change (those stay Phase 13's UI-02 job for the rest of the wizard).
- **D-14 (mobile transfers):** `transfers_step_batch` (`app/routes/mobile_transfers.py:130-132`) already calls `lookup_prefill(session, code)` — today purely to confirm the code resolves, then discards the result entirely; no template in the transfer wizard (not even step 1) ever displays the product name, only the code the operator typed and, later, batch cards showing warehouse/price/qty but not product name. Fix: use the already-fetched `name` from that existing call and render it as visible text starting from the step where it's resolved, carried through to the destination step (`transfers_step_dest.html`), instead of leaving product identity invisible until the final success message. Narrow scope: same as D-13 — display already-fetched data only, no new lookups, no touch to batch-card layout/navigation (Phase 13's job).
- **Boundary with Phase 13:** D-13/D-14 fix the specific "we fetched the name and threw it away" bug found in these two wizards. They do NOT constitute a full UI-02 pass — write-off and correction's identical "name only on step 1, nothing after" gap, and the general code/name/warehouse visibility work across all 5 wizards, remain entirely Phase 13's scope, unchanged by this audit.

### Claude's Discretion
- Exact response fragment/template names and the shape of the new `/sales/search-name` route are left to the planner/executor, as long as they follow D-08 through D-11.
- Whether `lookup_prefill()`'s new `source="catalog"` branch lives in `app/services/receipts.py` or is factored differently is left to the planner, as long as the resulting behavior matches D-01/D-02.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. Mobile wizard navigation/step-indicator/back-button work was explicitly kept out (belongs to Phase 13, already on the roadmap).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PRICE-02 | On the product-add form, typing a code suggests catalog price and consultant (cost) price from imported catalog data; operator can accept or override (formalize existing ad-hoc `feat/catalogs-pricing` behavior) | Already shipped — `GET /products/lookup-price` (`app/routes/products.py:44-70`) + `latest_price_for_code()` (`app/services/pricing.py:14-32`); Pattern 1 and Code Examples section document the exact shipped shape for formalization/testing |
| PRICE-03 | On the product-add form, typing a code suggests the product name from the dictionary; operator can accept or override | Already shipped — `GET /dictionary/lookup` (`app/routes/dictionary.py:27-40`) using `partials/name_input.html`; Pattern 1 documents this as the canonical fill-only-if-empty example |
| PRICE-04 | On goods receipt (desktop and mobile), typing a code not yet in the product catalog suggests catalog price, consultant price, and name from imported catalog/dictionary data; operator can accept or override | New `source=="catalog"` branch design for `lookup_prefill()` (`app/services/receipts.py`) documented under Architecture Patterns/Pattern 3 and Code Examples; desktop wiring via D-04 (Pattern 1 reuse) and mobile wiring via D-06/D-12 (Pattern 3, Pitfall 4); Don't-Hand-Roll table covers `latest_price_for_code()` reuse; Common Pitfalls #1-4 cover the specific PRICE-04 implementation risks |
| SAL-06 | On the sales page, typing a product code shows its name inline; typing part of a product name shows a dropdown of matching codes to pick from | First half already shipped (`GET /sales/lookup`, documented in Code Examples); second half (name→code dropdown) documented via D-08/D-09/D-10/D-11 reuse of `search_products()`/`split_match()` (Don't-Hand-Roll table, Code Examples, Common Pitfalls #5, Open Question #1 on template/`<template>`-wrapping considerations) |
</phase_requirements>

## Summary

Phase 12 formalizes and extends an autofill pattern that already exists and works in three places in this codebase: `/products/lookup-price`, `/dictionary/lookup`, and `/sales/lookup`. All three follow the identical shape — a debounced (300ms) `hx-get` on a code/name input, a server-side "fill or 204" decision (htmx is configured via `<meta name="htmx-config">` in `base.html` to never swap a 204 and to always swap a 422), and an out-of-band (`hx-swap-oob`) fragment that fills a *sibling* field without disturbing the field the operator is typing in. Every fill is guarded by "only if currently empty" so an operator's own typed value is never overwritten.

This phase's actual new work is narrow and entirely mechanical relative to that existing pattern: (1) add a third `source == "catalog"` branch to `app/services/receipts.py::lookup_prefill()` that combines `Dictionary` (name) + `CatalogPrice` (price) for a code unknown to `Product`, wired into the existing `/receipts/lookup` OOB response; (2) thread the price dict `mobile_receipt_step_batch` already computes (and currently discards) forward into step 3's hidden/visible fields, plus add a two-line visible code/name readout to `receipts_step_details.html`; (3) build one genuinely new route, `/sales/search-name`, that reuses `search_products()`/`split_match()` from `app/services/catalog.py` verbatim to render a click-to-select `<mark>`-highlighted dropdown; (4) two small "we already fetched the name, we just never displayed it" fixes in the mobile sales and mobile transfers wizards.

**Primary recommendation:** Do not invent a new autofill mechanism. Copy the existing `partials/name_input.html` + `partials/receipt_price_inputs.html` OOB-swap pattern exactly for every new surface in this phase; the only genuinely new client-side behavior needed is the name-fragment → code dropdown for SAL-06's second half, which should reuse `search_products()` and the `<mark>`-highlight row shape already used on `/products/search`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Code → price/name lookup (debounce trigger) | Browser (htmx attributes on existing inputs) | — | Pure HTML attribute wiring, no JS beyond vendored htmx |
| Code → price/name resolution (server decision: fill or 204) | API/Backend (FastAPI route) | — | "Fill only if empty" and "which fields exist for this source" is business logic, must stay server-side per the app's existing D-23 pattern |
| Price/name data (CatalogPrice, Dictionary lookup) | Database/Storage (SQLite via SQLAlchemy) | — | Read-only helpers already exist (`pricing.py`, `dictionary.py`) |
| OOB fragment rendering (which inputs get swapped) | API/Backend (Jinja2 partial) | Browser (htmx applies the swap) | Server decides content; browser only executes the swap — same split as every existing autofill route |
| Name-fragment → code dropdown search | API/Backend (new `/sales/search-name` route + `search_products()`) | Browser (3-char trigger threshold, click-to-select) | Ranking/search logic belongs server-side (reuses existing `search_products`); the 3-char gate is a client-trigger concern only |
| Mobile wizard step-to-step price/name carry-forward | API/Backend (route re-renders next step with forwarded context) | Browser (hidden fields in the persistent `<form>`) | Mirrors the established "no server-side wizard session" pattern (RESEARCH Pattern 1 from Phase 11) |

## Standard Stack

No new packages. This phase extends `app/services/pricing.py`, `app/services/catalogs.py`, `app/services/receipts.py`, `app/services/sales.py`, and `app/services/catalog.py` — all already in the dependency tree — plus the already-vendored `htmx.min.js` (2.0.10, `app/static/htmx.min.js`). No `pip install` / `uv add` is needed for this phase.

### Core (existing, reused)
| Library | Version | Purpose | Why Standard (for this repo) |
|---------|---------|---------|-------------------------------|
| htmx | 2.0.10 (vendored, `app/static/htmx.min.js`) [VERIFIED: codebase] | `hx-get` debounce + `hx-swap-oob` fragment injection | Already the sole interactivity mechanism per CLAUDE.md; confirmed current stable per project's own Technology Stack doc |
| FastAPI | 0.139.x [VERIFIED: codebase — `pyproject.toml`] | Routes returning 204/200 partials | Existing route pattern (`Response(status_code=204)` vs `TemplateResponse`) |
| Jinja2 | 3.1.x [VERIFIED: codebase] | OOB partial rendering | `name_input.html`, `receipt_price_inputs.html`, `product_price_autofill.html` already establish the fragment-per-field convention |
| SQLAlchemy 2.0 | 2.0.x [VERIFIED: codebase] | `latest_price_for_code()`, `dictionary_lookup()`, `search_products()` | Already-shipped read-only helpers this phase calls without modification |

### Supporting
None new.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Server-rendered `<mark>`-highlighted dropdown (D-09) | native `<datalist>` | Rejected in CONTEXT.md D-09: datalist cannot render two columns (code + name) or highlight the matched substring — already decided, not reopened here |
| Reusing `search_products()` for name search (D-08) | A dedicated name-only SQL query | Rejected in CONTEXT.md D-08: `search_products` already does ranked, Cyrillic-safe, 20-row-capped search over exactly the `Product` table sale rows are constrained to — no reason to duplicate |

**Installation:** None — no new dependencies for this phase.

**Version verification:** Not applicable (no new packages). Existing versions confirmed by reading `pyproject.toml` directly: `fastapi==0.139.*`, `jinja2==3.1.*`, `sqlalchemy==2.0.*`, `python-multipart==0.0.32` — matches CLAUDE.md's Technology Stack table.

## Package Legitimacy Audit

**Not applicable — this phase installs zero new external packages.** All work extends existing internal services (`app/services/pricing.py`, `app/services/catalogs.py`, `app/services/receipts.py`, `app/services/sales.py`, `app/services/catalog.py`, `app/services/dictionary.py`) and the already-vendored `htmx.min.js`. No `npm install` / `uv add` / `pip install` step exists in this phase's task list.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Operator types in a code/name field (Browser)
        |
        v  hx-get, hx-trigger="input changed delay:300ms"
        |  (fill-only-if-empty guard already encoded in the request:
        |   the currently-typed value of sibling fields rides along
        |   via hx-include="closest tr/form", so the server can see
        |   "is this field still blank?")
        v
FastAPI lookup route (e.g. /receipts/lookup, /sales/search-name)
        |
        |-- name.strip() non-empty? --> Response(204)  [htmx-config: 204 never swaps]
        |
        v  lookup_prefill(session, code)  /  search_products(session, q)
        |
   +----+----------------------------------+
   |                                        |
   v (Product row exists)                   v (Product row does NOT exist)
source == "product"                    source == "catalog" (NEW, D-01)
   name + cost/sale/catalog                Dictionary.name (if any)
   from Product columns                    + CatalogPrice.consumer_cents/
                                              consultant_cents (if any)
   |                                        |
   +--------------------+-------------------+
                         v
        Jinja2 partial (name_input.html + receipt_price_inputs.html,
        each with oob=True, id="{field}-wrap")
                         v
        HTTP 200 response, multiple hx-swap-oob elements in one body
                         v
        htmx applies each OOB swap to its target id (Browser)
                         v
        Operator sees suggested name/price already in the field,
        can accept (leave as-is) or overwrite (types over it)
```

### Recommended Project Structure

No new files/folders — every change lands in an existing file:
```
app/
├── services/
│   ├── receipts.py          # lookup_prefill(): add source=="catalog" branch (D-01/D-02/D-03)
│   ├── catalog.py           # search_products()/split_match() — reused as-is (D-08)
│   └── sales.py             # lookup_prefill() — untouched (SAL-06 first half already shipped)
├── routes/
│   ├── receipts.py          # /receipts/lookup: extend OOB fill to source=="catalog" (D-04)
│   ├── mobile_receipts.py   # mobile_receipt_step_batch: forward prices dict (D-06)
│   └── sales.py             # NEW: GET /sales/search-name (D-08/D-09/D-10/D-11)
└── templates/
    ├── partials/
    │   ├── receipt_lookup.html          # extend to emit price OOB for source=="catalog"
    │   └── sale_name_search.html        # NEW: dropdown partial (name TBD by planner)
    └── mobile_partials/
        ├── receipts_step_details.html   # D-12: add 2-line visible code/name readout
        ├── sale_step_batch.html         # D-13: render forwarded name visibly
        ├── sale_step_qty_price.html     # D-13: render forwarded name visibly
        └── transfers_step_dest.html     # D-14: render forwarded name visibly
```

### Pattern 1: Fill-only-if-empty OOB autofill (the ONE pattern this whole phase reuses)
**What:** A debounced `hx-get` on a code field targets a name/price wrapper `<div>`/`<td>` by id. The server checks whether the corresponding field arrived non-empty in the request (via `hx-include`) and returns either `204` (no-op, nothing typed is ever overwritten) or a partial containing the fill.
**When to use:** Every autofill surface in this phase (product-add already does it; receipts extends it; sales already does it for code→name and needs it added for name→code).
**Example (existing, verified in this codebase):**
```html
<!-- Source: app/templates/partials/sale_row.html:16-24 (already shipped) -->
<input type="text" id="{{ code_id }}" name="code[]" value="{{ code or '' }}"
       hx-get="/sales/lookup"
       hx-trigger="input changed delay:300ms"
       hx-include="closest tr"
       hx-vals='{"row": "{{ row_id }}"}'
       hx-target="#{{ name_wrap_id }}"
       hx-swap="outerHTML"
       hx-sync="this:replace">
```
```python
# Source: app/routes/dictionary.py:27-40 (already shipped)
@router.get("/dictionary/lookup")
def dictionary_lookup(request, code="", name="", session=Depends(get_session)):
    entry = lookup(session, code)
    if entry is None or name.strip():   # never overwrite a typed name
        return Response(status_code=204)
    context = {"name": entry.name, "autofilled": True}
    return templates.TemplateResponse(request, "partials/name_input.html", context)
```
Cross-checked against official htmx docs: `hx-trigger="input changed delay:300ms"` is htmx's documented debounce idiom (the `delay` modifier resets on each new event, i.e. true debounce, not throttle) [CITED: https://htmx.org/attributes/hx-trigger/]. `hx-swap-oob` swaps content into an element elsewhere in the DOM by id, independent of the main `hx-target` [CITED: https://htmx.org/attributes/hx-swap-oob/].

### Pattern 2: `<template>`-wrapped OOB fragments inside `<table>` rows
**What:** When an OOB swap targets a `<td>` or `<tr>` (table-context elements), the fragment MUST be wrapped in `<template>` or the browser's HTML parser strips it before htmx ever sees it (browsers refuse to parse a bare `<td>`/`<tr>` outside a table context).
**When to use:** Any OOB swap whose target lives inside a `<table>` — this repo already hit this exact bug (see `sale_lookup.html` comment: "UAT tests 4/5... Do not remove").
**Example:**
```html
<!-- Source: app/templates/partials/sale_lookup.html:21-26 (already shipped, load-bearing) -->
<template>
<td id="{{ price_wrap_id }}" hx-swap-oob="true">
  <input type="text" name="price[]" ...>
</td>
</template>
```
Not directly needed for this phase's new work (receipt form and product form are not tables), but the `/sales/search-name` dropdown, if it ever needs to OOB-swap a `<td>`, must follow this precedent.

### Pattern 3: Mobile wizard hidden-field carry-forward (no server-side session)
**What:** Every mobile wizard step is a separate POST that re-renders the next partial into `#wizard-step`; state travels ONLY as hidden `<input>` fields inside one persistent `<form>` (established in Phase 11, referenced as "RESEARCH Pattern 1" throughout `mobile_receipts.py`/`mobile_sales.py`/`mobile_transfers.py`).
**When to use:** D-06 (forward resolved prices from step 1→2 into step 3) and D-13/D-14 (forward the already-fetched name) both fit this pattern exactly — add the value to the step's render context, echo it as a hidden (or now visible) `<input>` in that step's template, and it rides forward automatically when the next step's button does `hx-include="closest form"`.
**Example:**
```python
# Source: app/routes/mobile_receipts.py:96-122 (existing step_batch handler)
# CURRENT: resolved_name = _lookup_name(session, code) -- only name is kept,
# the "prices" key from lookup_prefill()'s result dict is discarded.
# D-06 requires also keeping result["prices"] and threading cost/sale/catalog
# into this step's context so receipts_step_batch.html can echo them as
# hidden fields, which step 3 (receipts_step_details.html) then reads as its
# pre-filled cost/sale/catalog input values.
```

### Anti-Patterns to Avoid
- **Adding a live/debounced `hx-get` to the mobile receipt step-1 code field:** explicitly rejected by D-06/D-07 — mobile receipt autofill stays on the existing "resolve once per step-submit" model; a debounced live lookup on step 1 would be a new interaction surface that risks pre-empting Phase 13's mobile navigation rework.
- **Building a separate name-only search function for `/sales/search-name`:** D-08 requires reusing `search_products()`/`search_view()` verbatim — a parallel matcher would drift from the ranking/Cyrillic-safety rules already tested in `test_search.py`/`test_catalog.py`.
- **Letting `CatalogPrice` ever fill the receipt's `sale` field:** D-02 is an explicit hard boundary — `CatalogPrice.consumer_cents` → `catalog` field only, `CatalogPrice.consultant_cents` → `cost` field only. This mirrors an existing boundary already enforced elsewhere in the codebase (`sales.py` never lets Oriflame's own price bleed into the shop's price).
- **Re-firing `/sales/lookup` after a dropdown pick (D-11):** the dropdown result already carries both code and name — fill both directly from the clicked row's data, don't trigger a redundant round-trip through the code-lookup endpoint.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Ranked/Cyrillic-safe name search | A new SQL LIKE query for the sales dropdown | `search_products()` (`app/services/catalog.py:347-371`) | Already handles exact-code/code-prefix/name-substring ranking, LIKE-escaping (`_escape_like`), and Python-side Cyrillic lowering (SQLite's `lower()` is ASCII-only) — reinventing this risks silently breaking Cyrillic search |
| `<mark>`-highlighted match rendering | New highlight logic in the dropdown template | `split_match()` (`app/services/catalog.py:374-383`) | Already used by `product_rows.html`; returns `(pre, match, post)` so the template never builds raw HTML — autoescape-safe |
| Debounce timing | A custom JS `setTimeout`/`clearTimeout` handler | htmx's `hx-trigger="input changed delay:300ms"` | Zero JS, matches the 300ms already used identically on 3 other autofill inputs in this app — a 4th bespoke value would just be inconsistent UX |
| "Fill or leave alone" decision | Client-side JS checking `if (input.value === "")` before overwriting | Server-side check of the posted (possibly-typed) field value, returning 204 when it's non-empty | Matches the existing D-23 contract everywhere else in the app: the SERVER decides fill vs no-op, never the client |

**Key insight:** Every piece of "don't hand-roll" guidance here is really "don't re-invent what Phase 7/9/11 already built and tested" — this phase is 90% wiring, not new logic.

## Common Pitfalls

### Pitfall 1: Forgetting the fill-only-if-empty guard on the new `source == "catalog"` branch
**What goes wrong:** A newly-added price OOB fill overwrites a price the operator already typed for a not-yet-known code.
**Why it happens:** The existing `source == "product"` branch in `/receipts/lookup` computes `fill_fields` from the *posted* cost/sale/catalog values (`typed = {...}; fill_fields = [f for f in (...) if not typed[f].strip()]`) — a new `source == "catalog"` branch must reuse the exact same `fill_fields` computation, not skip it because "the code is new so there's nothing to conflict with" (the operator may have already typed a price before the debounced lookup returns).
**How to avoid:** Route the `source == "catalog"` branch through the same `fill_fields` list built for `source == "product"` (both need the same "what's still empty" check) rather than writing a second, divergent computation.
**Warning signs:** A test where the operator types a price BEFORE the code-lookup debounce fires, then the debounced response arrives and clobbers the typed price.

### Pitfall 2: `sale` field contamination from `CatalogPrice`
**What goes wrong:** A future maintainer sees "catalog price, consultant price, and name" in the PRICE-04 wording and assumes there are three price fields to fill including `sale`, but `CatalogPrice` has no concept of this shop's own resale price.
**Why it happens:** The receipt form has three price inputs (`cost`, `sale`, `catalog`) and it's easy to conflate "fill all three" with "fill the two `CatalogPrice` actually has data for."
**How to avoid:** D-02 is explicit — `consumer_cents` → `catalog`, `consultant_cents` → `cost`, and `sale` is NEVER touched by the `source == "catalog"` branch. Write this as an assertion or comment at the point where the branch's `prices` dict is built (mirror `sales.py` D-10's comment style: "the entered per-line price is REQUIRED... unlike receipts, where empty price = NULL").
**Warning signs:** A test asserting `sale` gets filled from `CatalogPrice` data — that test itself would be wrong and should fail the intent, not the code.

### Pitfall 3: `receipt_price_inputs.html` reused with `oob=True` for a code that doesn't exist in `Product` yet
**What goes wrong:** The existing `partials/receipt_price_inputs.html` fragment (`id="{{ field }}-wrap" hx-swap-oob="true"`) is the SAME fragment the static form uses for its initial render. If the new `source == "catalog"` branch is wired to a different partial or a different id scheme, the OOB swap silently fails (htmx finds no matching id in the live DOM).
**Why it happens:** It's tempting to build a parallel fragment for "catalog-sourced" fills since the data comes from a different table.
**How to avoid:** Reuse `receipt_price_inputs.html` unchanged (per D-04) — same `id="{field}-wrap"`, same `oob=True` parameter, just fed with `CatalogPrice`-derived values instead of `Product`-derived values. The receiving `<div id="cost-wrap">`/`<div id="catalog-wrap">` in the static form doesn't know or care which table the value came from.
**Warning signs:** The lookup response returns 200 with visible-looking HTML but the browser DOM never updates — check the response for a mismatched `id` before assuming htmx is broken.

### Pitfall 4: Mobile step 3 price forwarding arriving as an empty string, not `None`
**What goes wrong:** `lookup_prefill()`'s `prices` dict values are `int | None` (cents), but the mobile step 2→3 hidden fields are plain strings. Forwarding `None` naively into a Jinja `value="{{ x }}"` renders the literal text `"None"` into the input.
**Why it happens:** `receipt_price_inputs.html` already handles this correctly with `{{ value or '' }}` for the DESKTOP static-form/OOB case, and `receipts_step_details.html` already uses `value="{{ cost }}"` for the step-3 echo-from-post case — but that echo case assumes `cost` arrives as a string from `Form("")`, never `None`. When D-06 introduces prices computed server-side (not posted-and-echoed), the render must go through the same `| cents` filter used elsewhere (e.g. `{{ prices.cost | cents if prices.cost is not none else '' }}`) rather than raw string interpolation.
**How to avoid:** When building step 2's context in `mobile_receipt_step_batch`, convert the `prices` dict's cent-integers to display strings using the app's existing `cents` Jinja filter (confirm the filter name via `app/routes/__init__.py` or wherever `templates` is configured) BEFORE they reach step 3, mirroring how `receipt_lookup.html` does `{{ prices[f] | cents }}`.
**Warning signs:** A step-3 price field literally showing the text "None" or "0.00" when the field should have been left blank because no catalog price exists for that code.

### Pitfall 5: `/sales/search-name` dropdown firing on every keystroke below the 3-char threshold
**What goes wrong:** D-10 requires the dropdown to fire ONLY at 3+ characters; `search_products()`'s own behavior is "empty query → first 20 by name" (a useful default for `/products/search` but wrong for live-typing on the sales name field — showing 20 random products after 1-2 characters is noise, not help).
**Why it happens:** Naively wiring `hx-trigger="input changed delay:300ms"` straight to a route that calls `search_products(session, q)` inherits its empty/short-query fallback.
**How to avoid:** Per D-10, add the 3-character guard IN THE NEW ROUTE (or via an htmx trigger filter), not by modifying `search_products()` itself — `search_products` is shared with `/products/search`, which correctly wants the empty-query fallback for its own use case.
**Warning signs:** The dropdown shows 20 unrelated products after typing a single Cyrillic character into the sales name field.

## Code Examples

### Existing debounced code→name lookup (product-add form) — the template for every new lookup in this phase
```python
# Source: app/routes/products.py:44-70 (verified in this codebase)
@router.get("/products/lookup-price")
def product_price_lookup(request, code="", cost="", catalog="", session=Depends(get_session)):
    latest = latest_price_for_code(session, code)
    fill_catalog = latest is not None and latest.consumer_cents is not None and not catalog.strip()
    fill_cost = latest is not None and latest.consultant_cents is not None and not cost.strip()
    if not fill_catalog and not fill_cost:
        return Response(status_code=204)
    context = {
        "fill_catalog": fill_catalog,
        "catalog_cents": latest.consumer_cents if latest else None,
        "fill_cost": fill_cost,
        "cost_cents": latest.consultant_cents if latest else None,
    }
    return templates.TemplateResponse(request, "partials/product_price_autofill.html", context)
```

### Existing `lookup_prefill()` two-branch shape that D-01 extends to three branches
```python
# Source: app/services/receipts.py:260-287 (verified in this codebase, current state)
def lookup_prefill(session: Session, code: str) -> dict | None:
    code = code.strip()
    if not code:
        return None
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is not None:
        return {
            "source": "product",
            "name": product.name,
            "prices": {"cost": product.cost_cents, "sale": product.sale_cents, "catalog": product.catalog_cents},
        }
    entry = dictionary_lookup(session, code)
    if entry is not None:
        return {"source": "dictionary", "name": entry.name, "prices": None}
    return None
    # D-01: a THIRD branch belongs here, before or replacing the dictionary-only
    # fallback -- combine `entry` (Dictionary, name) with
    # `latest_price_for_code(session, code)` (CatalogPrice, price) into
    # {"source": "catalog", "name": ..., "prices": {"cost": consultant_cents,
    # "catalog": consumer_cents, "sale": None}} whenever EITHER has data.
```

### `search_products()` + `split_match()` — the exact reuse target for D-08/D-09
```python
# Source: app/services/catalog.py:347-383 (verified in this codebase)
def search_products(session: Session, q: str) -> list[Product]:
    base = select(Product).where(Product.deleted_at.is_(None))
    q_lc = q.strip().lower()
    if not q_lc:
        return list(session.scalars(base.order_by(Product.name).limit(20)))
    code_prefix = func.lower(Product.code).like(_escape_like(q_lc) + "%", escape="\\")
    rank = case((func.lower(Product.code) == q_lc, 0), (code_prefix, 1), else_=2)
    stmt = (
        base.where(code_prefix | Product.name_lc.contains(q_lc, autoescape=True))
        .order_by(rank, Product.name_lc)
        .limit(20)
    )
    return list(session.scalars(stmt))

def split_match(text: str, q_lc: str) -> tuple[str, str, str]:
    idx = text.lower().find(q_lc) if q_lc else -1
    if idx < 0:
        return text, "", ""
    return text[:idx], text[idx : idx + len(q_lc)], text[idx + len(q_lc) :]
```

## State of the Art

Not applicable — this is a purely internal, already-established pattern within a single codebase; there is no external ecosystem "state of the art" shift to track. htmx 2.0.10 remains the vendored stable line per CLAUDE.md's own Technology Stack doc (htmx 4.0 is still beta as of the doc's last verification and explicitly rejected).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `cents` Jinja filter (referenced in Pitfall 4) exists and is registered globally (used already in `receipt_lookup.html`, `product_rows.html`, etc.) and can be applied to the `prices` dict values forwarded through the mobile receipt wizard | Common Pitfalls #4 | Low — the filter is visibly used in ≥3 existing templates read during this research (`receipt_lookup.html:13`, `product_rows.html:25-27`, `sale_lookup.html:23`), so this is effectively verified by codebase inspection, not truly an assumption; flagged only because the filter's registration point (`app/routes/__init__.py` or similar) was not directly opened this session |

**If this table is empty:** N/A — one low-risk item logged above; everything else in this research was verified by direct file reads of the current codebase state.

## Open Questions

1. **Exact new-file/fragment names for `/sales/search-name`'s response partial**
   - What we know: CONTEXT.md explicitly leaves this to the planner/executor (see "Claude's Discretion"), as long as it follows D-08 through D-11 (reuse `search_products`, click-to-select dropdown with `<mark>` highlighting, 3-char threshold, fill both code+name on click).
   - What's unclear: Whether the dropdown should be a new `partials/sale_name_search.html` or reuse/extend an existing fragment; whether it needs `<template>` wrapping (Pattern 2 above) depends on whether the trigger field sits inside `sale_row.html`'s `<table>` structure (it does — `sale_row.html` is a `<tr>`).
   - Recommendation: Given the trigger field (`name[]`) lives inside a `<table>` row (`sale_row.html`), the new dropdown fragment likely needs the same `<template>`-wrapping precedent as `sale_lookup.html`'s OOB `<td>`/`<tr>` fragments if it swaps table-context elements — the planner should confirm during task breakdown whether the dropdown target is inside or outside the table (e.g. a `<td>`-scoped list vs. a page-level floating overlay) before locking the exact markup.

2. **Where exactly the `source == "catalog"` branch's price mapping lives** (service factoring)
   - What we know: CONTEXT.md leaves this to the planner ("whether `lookup_prefill()`'s new `source="catalog"` branch lives in `app/services/receipts.py` or is factored differently is left to the planner").
   - What's unclear: Nothing blocking — `app/services/receipts.py::lookup_prefill()` is the natural home (it already has the two-branch shape to extend), and no dependency prevents adding the branch there directly.
   - Recommendation: Add it directly inside `lookup_prefill()` in `app/services/receipts.py`, calling `latest_price_for_code()` (already imported nowhere in that file — will need a new import from `app.services.pricing`) — no new service module needed for a single new branch.

## Environment Availability

Skipped — this phase has no external tool/service/runtime dependencies beyond the project's own existing Python/FastAPI/SQLAlchemy/SQLite/htmx stack, which is already running (confirmed by the existing, passing test suite covering `pricing.py`, `receipts.py`, `sales.py`, `catalog.py`).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x [VERIFIED: codebase — `pyproject.toml` dev dependency-group] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `uv run pytest tests/test_pricing_feature.py tests/test_receipts.py tests/test_sales.py tests/test_dictionary.py tests/test_mobile_receipts.py tests/test_mobile_sales.py tests/test_mobile_transfers.py -x` |
| Full suite command | `uv run pytest` |

Fixtures used throughout this phase's tests (from `tests/conftest.py`, verified): `session` (file-based tmp_path SQLite), `client` (TestClient with `get_session` override, `app.main.app`), `mobile_client_factory` (isolated FastAPI instance per mobile router — see `test_mobile_receipts.py`/`test_mobile_sales.py`/`test_mobile_transfers.py` for the exact factory usage pattern already established).

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRICE-02 | Product-add form: code → catalog/consultant price autofill, override-able | unit/integration | `pytest tests/test_pricing_feature.py -k autofill -x` | ✅ (already shipped, passing — this phase only formalizes) |
| PRICE-03 | Product-add form: code → name autofill from dictionary, override-able | unit/integration | `pytest tests/test_dictionary.py -k lookup -x` | ✅ (already shipped) |
| PRICE-04 | Receipt (desktop+mobile): unknown code → catalog price/consultant price/name from catalog+dictionary | integration | `pytest tests/test_receipts.py -k lookup -x` (desktop); `pytest tests/test_mobile_receipts.py -x` (mobile) | ❌ new `source=="catalog"` branch test cases — Wave 0 gap |
| SAL-06 | Sales page: code → name inline (shipped); name fragment → code dropdown (new) | integration | `pytest tests/test_sales.py -k lookup -x` (shipped half); new test file/function for `/sales/search-name` | ❌ dropdown route test — Wave 0 gap |

### Sampling Rate
- **Per task commit:** the relevant single test file quick command above
- **Per wave merge:** `uv run pytest tests/test_pricing_feature.py tests/test_receipts.py tests/test_sales.py tests/test_dictionary.py tests/test_mobile_receipts.py tests/test_mobile_sales.py tests/test_mobile_transfers.py`
- **Phase gate:** `uv run pytest` (full suite) green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_receipts.py` — add cases for `lookup_prefill()`'s new `source=="catalog"` branch (D-01/D-02/D-03): CatalogPrice-only match, Dictionary-only match, both-present match, neither-present (still None), and the `sale` field NEVER filling from CatalogPrice (D-02 regression guard)
- [ ] `tests/test_mobile_receipts.py` — add case for D-06 price forwarding from step 2 into step 3's rendered value attributes, and D-12's visible code/name readout on step 3
- [ ] `tests/test_sales.py` (or a new `tests/test_sales_search.py`) — new `/sales/search-name` route: 3-char threshold (D-10), ranked results via `search_products`, click-fills both code+name (D-11)
- [ ] `tests/test_mobile_sales.py` — add case asserting the fetched `name` (already returned by `lookup_prefill`) now renders as visible text on `sale_step_batch.html`/`sale_step_qty_price.html` (D-13)
- [ ] `tests/test_mobile_transfers.py` — add case asserting the fetched `name` (already returned by `lookup_prefill`) now renders as visible text starting at the batch step through `transfers_step_dest.html` (D-14)

No new test framework or fixture infrastructure needed — all gaps are new test FUNCTIONS in existing, already-passing test files.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single-operator app, no auth in v1 per CLAUDE.md |
| V3 Session Management | No | No session state introduced — mobile wizards already use hidden-field carry-forward, not server sessions |
| V4 Access Control | No | No new access boundary introduced |
| V5 Input Validation | Yes | All lookup routes already validate/strip codes server-side (`code.strip()`) before querying; the new `/sales/search-name` route must apply the same `q.strip()` normalization `search_products()` already does internally — no new validation surface beyond what's already covered by existing helpers |
| V6 Cryptography | No | Not applicable — no crypto in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via search query | Tampering | Already mitigated — `search_products()` uses SQLAlchemy's parameterized `select()`/`.like()`/`.contains()`, never raw SQL string interpolation; the new route must call this existing function, not build its own query |
| Stored-XSS via product name/comment reflected in a dropdown | Tampering/Information Disclosure | Jinja2 autoescaping is on by default and already relied on throughout the codebase (explicit comments like "Jinja autoescape only, never `\|safe`" in `transfers_step_batch.html`, `batch_picker.html`) — the new dropdown template must follow the same rule: never mark product name/code `\|safe` |
| Untrusted `row`/id echoed into `hx-vals`/JS-evaluated attributes | Tampering | Already mitigated pattern exists — `sales.py`'s `_ROW_ID_RE` regex validates any client-supplied row id before it's echoed into an `hx-on::load` attribute; if the new dropdown echoes any client-supplied identifier back into an HTML attribute, apply the same allow-list-regex validation before trusting it |
| CatalogPrice/Dictionary data used to silently overwrite an operator-typed value (data integrity, not classic security) | Tampering (of user intent) | Enforced throughout this app via the "never overwrite a non-empty field" pattern (D-23) — every new autofill path in this phase must preserve this guarantee exactly as PRICE-02/PRICE-03/existing SAL-06 already do |

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection (all files read in full during this research session): `app/services/pricing.py`, `app/services/catalogs.py`, `app/services/receipts.py`, `app/services/sales.py`, `app/services/catalog.py` (lines 330-410), `app/services/dictionary.py`, `app/routes/products.py`, `app/routes/dictionary.py`, `app/routes/receipts.py`, `app/routes/mobile_receipts.py`, `app/routes/sales.py`, `app/routes/mobile_sales.py`, `app/routes/mobile_transfers.py`, `app/models.py` (Product/Dictionary/CatalogPrice), `app/templates/base.html`, `app/templates/partials/{name_input,receipt_lookup,receipt_price_inputs,product_price_autofill,sale_row,sale_lookup,product_rows,batch_picker}.html`, `app/templates/mobile_partials/{receipts_step_batch,receipts_step_details,sale_step_batch,sale_step_qty_price,transfers_step_batch,transfers_step_dest}.html`, `app/templates/mobile_pages/receipts.html`, `tests/conftest.py`, `tests/test_pricing_feature.py`, `pyproject.toml`
- [htmx hx-trigger Attribute](https://htmx.org/attributes/hx-trigger/) — confirmed `delay` modifier debounce semantics match the codebase's existing `delay:300ms` usage
- [htmx hx-swap-oob Attribute](https://htmx.org/attributes/hx-swap-oob/) — confirmed OOB-by-id swap semantics match the codebase's existing OOB fragment pattern

### Secondary (MEDIUM confidence)
None used beyond the two cited docs pages above (WebSearch results were consistent with and only confirmed already-observed codebase behavior).

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages, every reused function/pattern read directly from the current codebase
- Architecture: HIGH — the OOB-swap + fill-only-if-empty pattern is already implemented identically in 3 places and this phase's diagrams/patterns are drawn directly from that verified code
- Pitfalls: HIGH — every pitfall above is either an explicit CONTEXT.md decision (D-01/D-02/D-04) being called out for implementation risk, or a bug this exact codebase already hit and left a comment about (`<template>`-wrapping, "Do not remove")

**Research date:** 2026-07-13
**Valid until:** No external expiry — this research is tied to the current state of this codebase's own files (branch `feat/catalogs-pricing`), not to a fast-moving external ecosystem. Re-verify only if `app/services/receipts.py` or `app/services/sales.py` change again before this phase is planned/executed.
