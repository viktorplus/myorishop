# Phase 12: Code & Name Autofill - Pattern Map

**Mapped:** 2026-07-13
**Files analyzed:** 12
**Analogs found:** 12 / 12 (all internal, no analog gaps — this phase is 100% pattern reuse/extension)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `app/services/receipts.py` (`lookup_prefill`, new `source=="catalog"` branch) | service | request-response (read-only lookup, combine 2 sources) | `app/services/pricing.py::latest_price_for_code()` + existing `lookup_prefill` 2-branch shape (same file) | exact — extends existing function |
| `app/routes/receipts.py` (`/receipts/lookup`) | route | request-response (debounced OOB) | Same file, `source=="product"` branch (lines ~102-144) | exact — sibling branch, same route |
| `app/templates/partials/receipt_lookup.html` | template (OOB fragment) | request-response | Same file (only conditionally guarded on `source=="product"` today; extend guard) | exact |
| `app/templates/partials/receipt_price_inputs.html` | template (OOB fragment) | request-response | itself — reused unchanged, fed new data (D-04/Pitfall 3) | exact (no changes needed) |
| `app/routes/mobile_receipts.py` (`mobile_receipt_step_batch`) | route | request-response (wizard step, hidden-field carry-forward) | Same file/function — currently only forwards `name`, not `prices` | exact — extends existing handler |
| `app/templates/mobile_partials/receipts_step_batch.html` | template (wizard step, hidden field emitter) | request-response | Same file (need to add `prices.*` hidden inputs alongside existing `name`/`code`) | exact |
| `app/templates/mobile_partials/receipts_step_details.html` | template (wizard step, form fields) | request-response | Same file (currently hides `code`/`name`, lines 7 & 9; needs D-12 visible line + prefilled cost/sale/catalog values) | exact |
| `app/routes/sales.py` (new `GET /sales/search-name`) | route | request-response (new dropdown search) | `app/routes/products.py::/products/search` (search_view usage) and existing `/sales/lookup` in same file | role-match (new route, closely modeled on 2 existing ones) |
| `app/templates/partials/sale_name_search.html` (NEW, name per planner) | template (dropdown OOB/inline fragment) | request-response | `app/templates/partials/product_rows.html` (`<mark>` highlight rows) + `app/templates/partials/sale_lookup.html` (`<template>`-wrapped table OOB) | role-match — combine both patterns |
| `app/templates/partials/sale_row.html` | template (trigger field wiring) | request-response | itself — add a second `hx-get` trigger on the `name[]` input, modeled on the existing `code[]` trigger (lines 16-24) | exact |
| `app/templates/mobile_partials/sale_step_batch.html`, `sale_step_qty_price.html` | template (wizard step) | request-response | Same files — `name` already computed by `lookup_prefill()` in `app/routes/mobile_sales.py`, just needs visible rendering (D-13) | exact |
| `app/templates/mobile_partials/transfers_step_dest.html` (+ carry from `transfers_step_batch` handler) | template (wizard step) + route | request-response | `app/routes/mobile_transfers.py::transfers_step_batch` (currently discards `lookup_prefill()` result, line 131) — mirror D-13's fix (D-14) | exact |

## Pattern Assignments

### `app/services/receipts.py::lookup_prefill()` (service, request-response)

**Analog:** same file, current 2-branch shape (verified, lines 260-287 per RESEARCH.md)

**Current shape to extend:**
```python
# app/services/receipts.py:260-287 (current state)
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
```

**D-01/D-02 new branch — combine Dictionary + CatalogPrice, never touch `sale`:**
```python
# New import needed: from app.services.pricing import latest_price_for_code
    entry = dictionary_lookup(session, code)
    latest = latest_price_for_code(session, code)
    if entry is not None or latest is not None:
        return {
            "source": "catalog",
            "name": entry.name if entry is not None else None,
            "prices": {
                "cost": latest.consultant_cents if latest is not None else None,
                "catalog": latest.consumer_cents if latest is not None else None,
                "sale": None,  # D-02: CatalogPrice never fills the shop's own sale price
            },
        }
    return None
```

**Source of `latest_price_for_code()` signature** (`app/services/pricing.py:14-32`) — returns `CatalogPrice | None` with `.consumer_cents` / `.consultant_cents`; call unchanged.

---

### `app/routes/receipts.py::receipt_lookup()` (route, request-response)

**Analog:** same function, `source == "product"` branch (verified read, current file)

**Current shape (full function, lines ~102-144):**
```python
@router.get("/receipts/lookup")
def receipt_lookup(
    request: Request, code: str = "", name: str = "", cost: str = "", sale: str = "",
    catalog: str = "", warehouse_id: str = "", session: Session = Depends(get_session),
):
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    if result["source"] == "product":
        typed = {"cost": cost, "sale": sale, "catalog": catalog}
        fill_fields = [f for f in ("cost", "sale", "catalog") if not typed[f].strip()]
        hint = CARD_FILL_HINT
        actives = active_warehouses(session)
        chooser = _chooser_context(session, code, warehouse_id.strip(), actives)
        include_chooser = True
    else:
        fill_fields = []
        hint = ""
        chooser = {"zero_warehouses": False, "batches": [], "code_entered": False}
        include_chooser = False
    context = {
        "name": result["name"], "hint": hint, "source": result["source"],
        "fill_fields": fill_fields, "prices": result["prices"],
        "include_chooser": include_chooser, **chooser,
    }
    return templates.TemplateResponse(request, "partials/receipt_lookup.html", context)
```

**D-04/D-01 change:** the `else` branch currently sets `fill_fields = []` for ANY non-"product" source. Split it so `source == "catalog"` computes `fill_fields` from `typed` (Pitfall 1 — reuse the SAME `fill_fields` computation as the product branch, do not skip it just because the code is new):
```python
if result["source"] == "product":
    ...  # unchanged (D-03)
elif result["source"] == "catalog":
    typed = {"cost": cost, "sale": sale, "catalog": catalog}
    fill_fields = [f for f in ("cost", "catalog") if not typed[f].strip()]  # D-02: never "sale"
    hint = ""  # falls back to dictionary/catalog wording in name_input.html
    chooser = {"zero_warehouses": False, "batches": [], "code_entered": False}
    include_chooser = False
else:  # "dictionary" or None-name catalog-less match
    fill_fields = []
    ...
```

**Error handling:** existing 204-vs-200 contract (Phase 2 D-23) — no try/except needed, `Response(status_code=204)` is the "no-op" signal htmx is configured to ignore (via `<meta name="htmx-config">` in `base.html`).

---

### `app/templates/partials/receipt_lookup.html` (OOB fragment)

**Analog:** same file (verified read, full file above)

**Current guard to widen:**
```jinja
{% if source == "product" %}
{% set labels = {"cost": "Закупочная цена", "sale": "Цена продажи", "catalog": "Цена по каталогу"} %}
{% for f in fill_fields %}
{% with field = f, label = labels[f], value = (prices[f] | cents) if prices[f] is not none else "", oob = True %}
{% include "partials/receipt_price_inputs.html" %}
{% endwith %}
{% endfor %}
{% endif %}
```
D-04: change `{% if source == "product" %}` to `{% if source in ("product", "catalog") %}` — `fill_fields`/`prices` already computed correctly per-branch by the route, so the template only needs the widened guard. `receipt_price_inputs.html` itself (verified, 10 lines) needs ZERO changes — same `id="{field}-wrap"`, same `oob` param (Pitfall 3).

---

### `app/routes/mobile_receipts.py::mobile_receipt_step_batch()` (route, wizard step)

**Analog:** same function (verified read, lines 97-122)

**Current shape:**
```python
def mobile_receipt_step_batch(request, code=Form(""), warehouse_id=Form(""), name=Form(""), session=Depends(get_session)):
    actives = active_warehouses(session)
    selected = _preselect_warehouse_id(actives, warehouse_id)
    chooser = _chooser_context(session, code, selected, actives)
    resolved_name = _lookup_name(session, code)
    final_name = resolved_name or name.strip()
    context = {
        "code": code.strip(), "warehouse_id": selected, "name": final_name,
        "name_known": bool(resolved_name), **chooser,
    }
    return templates.TemplateResponse(request, "mobile_partials/receipts_step_batch.html", context)
```

**D-06 change:** `_lookup_name(session, code)` appears to be a name-only helper; replace/augment with the full `lookup_prefill(session, code)` result so `result["prices"]` is also available, then thread cents-to-string conversion (Pitfall 4 — use the same `cents` Jinja filter used in `receipt_lookup.html:13`, e.g. `prices.cost | cents if prices.cost is not none else ''`) into the context and forward as hidden fields on `receipts_step_batch.html`, which step 3 (`receipts_step_details.html`) already reads via `value="{{ cost }}"` etc.

**Pitfall 4 (critical):** do NOT interpolate `None` directly into `value="{{ x }}"` — it renders literal `"None"`. Convert cents to display strings server-side before the template renders.

---

### `app/templates/mobile_partials/receipts_step_details.html` (D-12 visible readout)

**Analog:** same file (verified read, full file above — 45 lines)

**Current hidden-only code/name (lines 7, 9):**
```jinja
<input type="hidden" name="code" value="{{ code }}">
...
<input type="hidden" name="name" value="{{ name }}">
```

**D-12 addition** — insert a minimal static text line above the price fields (after line 10, before the qty field), reusing plain paragraph markup already used elsewhere in this file (e.g. `<span class="muted">`):
```jinja
<p>{{ code }} — {{ name }}</p>
```
Scope: only this line, no new CSS class, no step-indicator/back-button change (D-07 boundary).

---

### `app/routes/sales.py` (new `GET /sales/search-name`) + `app/templates/partials/sale_name_search.html` (NEW)

**Analogs:**
1. `app/services/catalog.py::search_products()`/`split_match()` (verified, lines 326-345) — reuse verbatim per D-08.
2. `app/templates/partials/product_rows.html` (verified, `<mark>` highlight rows, lines 22-23) — row-rendering shape to mirror.
3. `app/templates/partials/sale_lookup.html` (verified, full file above) — `<template>`-wrapped OOB `<td>`/`<tr>` pattern, REQUIRED because `sale_row.html`'s `name[]` field lives inside a `<table>` row (Pattern 2, RESEARCH Open Question 1).

**search_products/split_match (exact reuse target, no modification):**
```python
# app/services/catalog.py:326-345
def search_products(session: Session, q: str) -> list[Product]:
    base = select(Product).where(Product.deleted_at.is_(None))
    q_lc = q.strip().lower()
    if not q_lc:
        return list(session.scalars(base.order_by(Product.name).limit(20)))
    code_prefix = func.lower(Product.code).like(_escape_like(q_lc) + "%", escape="\\")
    rank = case((func.lower(Product.code) == q_lc, 0), (code_prefix, 1), else_=2)
    stmt = (base.where(code_prefix | Product.name_lc.contains(q_lc, autoescape=True))
        .order_by(rank, Product.name_lc).limit(20))
    return list(session.scalars(stmt))

def split_match(text: str, q_lc: str) -> tuple[str, str, str]:
    idx = text.lower().find(q_lc) if q_lc else -1
    if idx < 0:
        return text, "", ""
    return text[:idx], text[idx : idx + len(q_lc)], text[idx + len(q_lc) :]
```

**D-10 3-char guard — implement in the NEW route (not in `search_products`):**
```python
@router.get("/sales/search-name")
def sales_search_name(request: Request, q: str = "", row: str = "", session: Session = Depends(get_session)):
    q = q.strip()
    if len(q) < 3:
        return Response(status_code=204)  # mirror the 204-no-op contract
    rows = search_products(session, q)
    q_lc = q.lower()
    context = {
        "rows": [{"product": p, "code_seg": split_match(p.code, q_lc), "name_seg": split_match(p.name, q_lc)} for p in rows],
        "row": row,
    }
    return templates.TemplateResponse(request, "partials/sale_name_search.html", context)
```
`row` param mirrors `sale_row.html`'s existing `hx-vals='{"row": "{{ row_id }}"}'` convention (see `/sales/lookup` trigger) so multi-line baskets stay index-aligned.

**`sale_row.html` trigger wiring (D-09/D-11) — add second `hx-get` to the `name[]` input**, modeled directly on the existing `code[]` trigger (verified lines 16-24 above):
```html
<input type="text" name="name[]" value="{{ name or '' }}"
       hx-get="/sales/search-name"
       hx-trigger="input changed delay:300ms"
       hx-vals='{"row": "{{ row_id }}", "q": "this.value"}'
       hx-target="#{{ name_search_id }}"
       hx-swap="innerHTML">
```
(Exact attribute values/ids left to planner per CONTEXT.md Discretion — must satisfy D-10's 3-char gate server-side per pitfall 5, and D-11's click-fills-both-fields via the dropdown row's own `hx-vals`/`hx-on:click` setting both `code[]` and `name[]` inputs directly, no re-trigger of `/sales/lookup`.)

**`<mark>` highlight row shape to copy** (verified, `product_rows.html:22-23`):
```jinja
<td>{% set pre, match, post = row.code_seg %}{{ pre }}{% if match %}<mark>{{ match }}</mark>{% endif %}{{ post }}</td>
<td>{% set pre, match, post = row.name_seg %}{{ pre }}{% if match %}<mark>{{ match }}</mark>{% endif %}{{ post }}</td>
```

**`<template>`-wrap requirement if targeting table-context** (verified, `sale_lookup.html:18-26`, comment: "UAT tests 4/5... Do not remove"):
```jinja
<template>
<td id="{{ some_wrap_id }}" hx-swap-oob="true">
  ...dropdown content...
</td>
</template>
```

---

### `app/routes/mobile_sales.py` step handlers + `sale_step_batch.html`/`sale_step_qty_price.html` (D-13)

**Analog:** same route file (verified read, lines 72-97) — `lookup_prefill()` already called and `result["name"]` already available in context-building code; currently only price-related keys are forwarded to the template context, `name` is computed but not threaded into steps 2-3's visible output.

**Fix pattern:** add `"name": result["name"]` (already computed, just not currently placed in the returned `context` dict for steps 2/3) to the context dicts already built at lines ~84-97+, then render it as visible text (not hidden-only) in `sale_step_batch.html`/`sale_step_qty_price.html`, mirroring D-12's plain `<p>{{ code }} — {{ name }}</p>` shape.

---

### `app/routes/mobile_transfers.py::transfers_step_batch()` + `transfers_step_dest.html` (D-14)

**Analog:** same function (verified, lines 122-132)

**Current shape:**
```python
def transfers_step_batch(request: Request, code: str = Form(""), session: Session = Depends(get_session)):
    # D-04: reuses the receipt lookup ... result is unused beyond confirming a name is resolvable
    if code.strip():
        lookup_prefill(session, code)
    return _render_batch_step(request, session, code)
```

**Fix pattern:** capture `result = lookup_prefill(session, code.strip()) if code.strip() else None`, pass `result["name"] if result else ""` into `_render_batch_step`'s context, thread it forward through `_render_dest_step` (verified, lines 85-106 — already accepts `code`, add `name` alongside), render visibly in `transfers_step_dest.html` mirroring the same `<p>{{ code }} — {{ name }}</p>` shape used for D-12/D-13.

---

## Shared Patterns

### Fill-only-if-empty debounced OOB autofill (the ONE pattern underlying every file above)
**Source:** `app/routes/dictionary.py:27-40` (canonical minimal example) and `app/templates/partials/sale_row.html:16-24` (canonical trigger wiring)
**Apply to:** `receipt_lookup.html`/`receipt_price_inputs.html` (D-04), the new `/sales/search-name` route+template (D-08..D-11)
```python
@router.get("/dictionary/lookup")
def dictionary_lookup(request, code="", name="", session=Depends(get_session)):
    entry = lookup(session, code)
    if entry is None or name.strip():   # never overwrite a typed name
        return Response(status_code=204)
    context = {"name": entry.name, "autofilled": True}
    return templates.TemplateResponse(request, "partials/name_input.html", context)
```
```html
<input ... hx-get="/sales/lookup" hx-trigger="input changed delay:300ms"
       hx-include="closest tr" hx-target="#{{ name_wrap_id }}" hx-swap="outerHTML" hx-sync="this:replace">
```

### `<template>`-wrapped table-context OOB swap
**Source:** `app/templates/partials/sale_lookup.html:18-26` (load-bearing comment: "UAT tests 4/5... Do not remove")
**Apply to:** any OOB target inside `sale_row.html`'s `<table>` — specifically the new `/sales/search-name` dropdown fragment if it swaps a `<td>`/`<tr>`.

### Mobile wizard hidden-field carry-forward (no server session)
**Source:** `app/routes/mobile_receipts.py::mobile_receipt_step_batch` / `receipts_step_batch.html` (existing `code`/`name`/`warehouse_id` hidden-input echo)
**Apply to:** D-06 (price forwarding), D-13 (mobile sales name), D-14 (mobile transfers name) — add the value to the step's render context, echo as `<input type="hidden">` (or now-visible `<p>`) in that step's template; it rides forward automatically via each step button's `hx-include="closest form"`.

### `cents` Jinja filter for server-computed price display
**Source:** used in `receipt_lookup.html:13`, `product_rows.html:25-27`, `sale_lookup.html:23` — pattern: `{{ value | cents if value is not none else '' }}`
**Apply to:** D-06's price forwarding (Pitfall 4) — never interpolate a raw `int | None` cents value into a plain `value="{{ x }}"` attribute.

### Server-side "fill vs 204" decision (never client-side JS)
**Source:** every lookup route above — `Response(status_code=204)` when the target field already has operator-typed content (checked via posted form value, never `input.value === ''` in JS)
**Apply to:** all new/extended lookup routes in this phase (D-01 catalog branch, `/sales/search-name`'s 3-char gate).

## No Analog Found

None — every file in this phase's scope is either a direct extension of an existing function/template or closely modeled on 2-3 existing analogs (see Pattern Assignments above). This phase is explicitly "90% wiring, not new logic" per RESEARCH.md.

## Metadata

**Analog search scope:** `app/routes/`, `app/services/`, `app/templates/partials/`, `app/templates/mobile_partials/` — all files directly named in CONTEXT.md's canonical_refs section, cross-verified by direct reads in this session plus RESEARCH.md's already-verified excerpts.
**Files scanned:** 12 target files + 8 analog source files read directly this session (`receipts.py` route, `receipts_step_details.html`, `receipt_price_inputs.html`, `receipt_lookup.html`, `mobile_receipts.py` step_batch handler, `sale_row.html`, `sale_lookup.html`, `mobile_transfers.py` transfer handlers, `product_rows.html`, `mobile_sales.py` step handler) plus RESEARCH.md's already-quoted excerpts (`pricing.py`, `catalog.py` search_products/split_match, `dictionary.py` route, `products.py` lookup-price route).
**Pattern extraction date:** 2026-07-13
