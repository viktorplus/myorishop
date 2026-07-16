# Phase 18: Two-Price Model Consolidation (ДЦ/ПЦ) - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 19 (2 new, 17 modified — surface taken verbatim from 18-RESEARCH.md §"Authoritative `catalog_cents` Removal Surface"; NOT re-derived)
**Analogs found:** 19 / 19

> **Scope note.** 18-RESEARCH.md already supplies the full removal inventory (36 sites / 17 files), the `0014` migration shape, the `price-cue.js` source, and the cue CSS. This document does **not** repeat them. It answers only the question research left open: **for each MODIFIED file, which existing code is the pattern of record.**

## File Classification

### New files (research already assigned precedents — listed for completeness only)

| New File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `alembic/versions/0014_drop_product_catalog_cents.py` | migration | batch | `alembic/versions/0002_catalog_dictionary.py:75` | **exact** — contains `op.drop_column("products", "catalog_cents")` verbatim |
| `app/static/price-cue.js` | client utility | event-driven | `app/templates/base.html:6-14` (inline viewport-redirect script) | partial — see §price-cue.js below |

### Modified files (this document's value-add)

| Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/routes/sales.py` (D-23 constants) | route | request-response | `app/routes/receipts.py:22-31` | **exact** |
| `app/routes/mobile_sales.py` (D-23 constants) | route | request-response | `app/routes/mobile_sales.py:18` (already imports `PRODUCT_NOT_FOUND_TMPL` from the shared service) | **exact** |
| `app/routes/receipts.py` (drop `catalog`) | route | request-response | `app/routes/receipts.py` itself — `cost`/`sale` are the surviving twins of `catalog` at every one of the 10 sites | **exact** |
| `app/routes/mobile_receipts.py` (drop `catalog`) | route | request-response | same — `cost`/`sale` twins | **exact** |
| `app/routes/products.py` (drop `fill_catalog`) | route | request-response | `products.py:149-150` (`fill_cost`/`fill_sale` twins) | **exact** |
| `app/routes/catalogs.py` (D-18 link) | route | request-response | read-only route; template-only change — see §D-18 | role-match |
| `app/services/catalog.py` | service | CRUD | its own `cost_cents`/`sale_cents` twins at each of the 6 sites | **exact** |
| `app/services/receipts.py` | service | CRUD + ledger | same twins; `:169-196` write-back is **do-not-touch** | **exact** |
| `app/services/pricing.py` (D-22) | service | read | `pricing.py:14-32` itself — one `.where()` clause removed | **exact** |
| `app/services/export.py` | service | file-I/O | its own adjacent CSV columns | **exact** |
| `app/models.py` | model | — | `catalog_cents`'s sibling columns at `:151-155` | **exact** |
| `partials/receipt_price_inputs.html` (D-14 `ref_cents`) | template partial | request-response | **the file's own `oob` param** — see §Q2 | **exact** |
| `partials/receipt_form.html` | template partial | request-response | its own `cost`/`sale` `{% with %}` blocks `:70-76` | **exact** |
| `partials/product_price_autofill.html` | template partial (OOB) | request-response | its own `fill_cost`/`fill_sale` blocks `:9-16` | **exact** |
| `pages/product_form.html` | template page | request-response | `:103-114` **STAYS** (research Pitfall 6); only `:77-81` goes | **exact** |
| `pages/categories.html`, `partials/product_rows.html`, `partials/receipt_rows.html` | template partial | request-response | adjacent surviving price columns in each table | **exact** |
| `pages/catalog_detail.html` (D-19 labels) | template page | request-response | `product_form.html:107-110` label wording | role-match |
| `mobile_partials/receipts_step_{details,batch,confirm}.html` | template partial | request-response | adjacent `cost`/`sale` inputs in each file | **exact** |
| `mobile_partials/sale_step_qty_price.html` | template partial | request-response | `partials/sale_row.html:35` (desktop twin) | **exact** |
| `app/static/style.css` | config/style | — | `style.css:277-286` (Batch picker / name-search blocks) | **exact** — see §Q5 |
| `tests/test_receipts.py`, `test_catalog.py`, `test_export.py`, `test_pricing_feature.py`, `test_sales.py`, `test_mobile_sales.py`, `test_catalogs_feature.py` | test | — | `tests/test_receipts.py:1048-1061` | **exact** — see §Q4 |

---

## Pattern Assignments — the five load-bearing questions

### Q1. The `CARD_FILL_HINT` constant pattern (D-23)

**Analog:** `app/routes/receipts.py:22-31`

Declaration — module-level, public UPPER_SNAKE, immediately after `router = APIRouter()`, each constant carrying a comment naming its governing decision:

```python
SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."
CARD_FILL_HINT = "Данные подставлены из карточки товара — новые цены обновят карточку."
# D-01/D-04 (Phase 12): unknown-to-Product code matched by Dictionary and/or
# CatalogPrice. Must stay non-empty — name_input.html's `hint | default(...)`
# filter falls back to the dictionary wording for an empty hint string.
CATALOG_FILL_HINT = "Цена и название подставлены из каталога — можно изменить."
```

Consumption — assigned to a bare local, then passed through the context dict under a generic key (`receipts.py:128,146,152`):

```python
        hint = CARD_FILL_HINT      # :128  (product branch)
    else:
        hint = CATALOG_FILL_HINT   # :146  (catalog branch)
    context = {"hint": hint, ...}  # :152
```

**Where the two new constants belong.** `CARD_FILL_HINT` sits in a route module because only desktop receipts uses it. D-23's constants are needed by **both** `sales.py` and `mobile_sales.py`, and the repo already has an exact precedent for that shape: `app/services/sales.py` declares `PRODUCT_NOT_FOUND_TMPL`, which `mobile_sales.py:18` imports:

```python
from app.services.sales import PRODUCT_NOT_FOUND_TMPL, lookup_prefill, register_sale
```

This matches the dominant house convention — **operator-facing message constants live in `app/services/*.py` as public UPPER_SNAKE names and are imported by routes** (`catalog.py:18-20` `PRICE_ERROR`/`DUPLICATE_CODE_ERROR`/`THRESHOLD_ERROR`, `corrections.py:23-29`, `customers.py:18-21`, `dictionary.py:16`).

**Recommendation:** declare `SALE_CARD_FILL_HINT` and `SALE_BATCH_FILL_HINT` in `app/services/sales.py` beside `PRODUCT_NOT_FOUND_TMPL`; import both into `sales.py` and `mobile_sales.py`. Six inline literals collapse to two names. Copy `receipts.py:24-27`'s comment style — name D-17/D-23 and the sale-only scope rationale on the constant itself.

**The six sites** (from research; each is a bare literal assigned to `fill_price_hint`):
- card: `sales.py:128`, `sales.py:253`, `mobile_sales.py:226`
- batch: `sales.py:154`, `sales.py:249`, `mobile_sales.py:223`

Verified shape at `sales.py:246-253` — both families appear in one if/else, so both constants land in the same edit:

```python
    if picked is not None:
        if picked.price_cents is not None:
            fill_price_cents = picked.price_cents
            fill_price_hint = "Цена подставлена из партии — можно изменить."
        else:
            # D-14: a legacy NULL-price batch falls back to the card sale_cents.
            fill_price_cents = product.sale_cents
            fill_price_hint = "Цена подставлена из карточки товара — можно изменить."
```

---

### Q2. Optional params through `receipt_price_inputs.html` and its `oob=True` path (D-14)

**Analog: the file's own `oob` parameter.** This is the exact pattern `ref_cents` must copy — same file, same mechanism.

Full source (`app/templates/partials/receipt_price_inputs.html:1-9`):

```jinja
{# Single source for ONE receipt price field (PD-10): the static form include
   renders it today; Plan 03-02's lookup fill re-renders the same fragment
   with oob=True targeting id="{field}-wrap". Parameters: field, label,
   value, error (optional), oob (optional, default false). #}
<div class="field" id="{{ field }}-wrap"{% if oob %} hx-swap-oob="true"{% endif %}>
  <label for="{{ field }}">{{ label }} <span class="muted">(необязательно)</span></label>
  <input type="text" id="{{ field }}" name="{{ field }}" inputmode="decimal" placeholder="0,00" value="{{ value or '' }}">
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
</div>
```

**The optional-param idiom, precisely:**
1. The docstring at `:1-4` **enumerates every parameter** and marks optionality verbatim: `"error (optional), oob (optional, default false)"`. `ref_cents` must be added to that list — the docstring is the partial's contract.
2. Optional params are **never defaulted with `{% set %}`**. They rely on Jinja's Undefined being falsy: `{% if oob %}` / `{% if error %}`. Callers that do not pass them simply omit them.
3. Both call paths pass params via `{% with %}` + `{% include %}`, never `{% import %}`.

**Static path** (`receipt_form.html:70-80`) — omits `oob` entirely, so `{% if oob %}` is falsy:

```jinja
{% with field = "cost", label = "Закупочная цена", value = form.cost or "", error = errors.cost %}
{% include "partials/receipt_price_inputs.html" %}
{% endwith %}

{% with field = "sale", label = "Цена продажи", value = form.sale or "", error = errors.sale %}
{% include "partials/receipt_price_inputs.html" %}
{% endwith %}
```

**OOB path** (`receipt_lookup.html:14-21`) — loops `fill_fields`, adds `oob = True`, and maps labels through a `{% set %}` dict:

```jinja
{% if source in ("product", "catalog") %}
{% set labels = {"cost": "Закупочная цена", "sale": "Цена продажи", "catalog": "Цена по каталогу"} %}
{% for f in fill_fields %}
{% with field = f, label = labels[f], value = (prices[f] | cents) if prices[f] is not none else "", oob = True %}
{% include "partials/receipt_price_inputs.html" %}
{% endwith %}
{% endfor %}
{% endif %}
```

**Concrete instruction for `ref_cents`:**
- In the partial, mirror the `oob` conditional on the `<input>`: `{% if ref_cents is not none and ref_cents %}data-ref-cents="{{ ref_cents }}"{% endif %}`. Use the `{% if %}`-guard form, **not** an `| default` filter — no optional param in this file uses a filter.
- Add `ref_cents (optional)` to the `:1-4` docstring parameter list.
- Static path: add `ref_cents = ...` to the `{% with %}` at `:70` and `:74`. The `:78-80` `catalog` block is **deleted**, not extended.
- OOB path: add a second `{% set refs = {"cost": ..., "sale": ...} %}` dict beside `labels` at `:15` and pass `ref_cents = refs[f]` in the `{% with %}` at `:17`. Drop `"catalog"` from the `labels` dict in the same edit.
- **This one file covers both receipt fields on both render paths** — which is exactly why research Pitfall 2 (OOB swaps stripping `data-ref-cents`) does *not* bite here. It **does** bite `product_price_autofill.html`, which is a separate, unshared template — see below.

**`product_price_autofill.html` has no such sharing** and must be patched independently (`:1-16`):

```jinja
{# CAT-05: out-of-band price inputs returned by /products/lookup-price. Each
   input mirrors the static field markup in product_form.html and replaces the
   live input by id (hx-swap-oob), filling it with the latest catalog price.
   Only the fields that should be filled are emitted; the rest stay untouched. #}
{% if fill_catalog %}                       {# <- DELETE this block (:5-8) #}
<input type="text" id="catalog" ... hx-swap-oob="true">
{% endif %}
{% if fill_cost %}
<input type="text" id="cost" name="cost" inputmode="decimal" placeholder="0,00"
       value="{{ cost_cents | cents }}" hx-swap-oob="true">   {# <- needs data-ref-cents #}
{% endif %}
```

Its docstring says these inputs *"mirror the static field markup in product_form.html"* — that mirroring obligation is the reason a bare re-render silently strips the attribute. Both `:10` and `:14` need `data-ref-cents`, and the docstring should note the mirror now includes it.

---

### Q3. Desktop ↔ mobile parity convention

**Answer: shared service layer, deliberately duplicated route/presentation layer.** Both mobile route modules state this verbatim in their docstrings — this is a documented house rule, not an accident.

`app/routes/mobile_receipts.py:1-12`:

```python
"""Mobile Приход (goods receipt) wizard (UI-01, Phase 11 Plan 03).
...
Подтверждение — that together produce the exact same register_receipt()
call as the desktop /receipts/new form (app/routes/receipts.py). State is
carried step-to-step via hidden fields inside one persistent <form>
(RESEARCH Pattern 1) — no server-side wizard session.

_preselect_warehouse_id/_chooser_context mirror the module-private helpers
in app/routes/receipts.py (same logic, re-declared here — not imported,
since they are underscore-prefixed private helpers of another route file).
"""
```

`app/routes/mobile_sales.py:1-6`:

```python
"""Mobile sale wizard (UI-01/D-05): ...
The final write is the
exact same array-shaped register_sale() call the desktop basket already
uses (app/routes/sales.py::sale_create) — zero changes to the write path.
"""
```

**The rule this yields, in three parts:**

1. **Business logic is never duplicated** — both trees import the same service functions. `mobile_receipts.py:26` and `receipts.py:13` both do `from app.services.receipts import lookup_prefill, register_receipt`; `mobile_sales.py:18` and `sales.py` both use `register_sale`. → Phase 18's `catalog_cents` removal from `app/services/*` is a **single** edit that both trees inherit.
2. **Private (`_`-prefixed) route helpers ARE re-declared per tree, never cross-imported** — stated explicitly above. → Any private helper touched must be touched twice.
3. **Public constants ARE cross-imported** — `mobile_sales.py:18` imports `PRODUCT_NOT_FOUND_TMPL` from `app.services.sales`. This is the loophole that makes Q1's two-constants/six-sites plan legal: the docstring bars importing *underscore-prefixed private helpers*, not public names.

**Consequence for the plan:** the `catalog` **form-parameter threading** (`receipts.py:113,126,127,136,142,144,145,174,190,205` vs `mobile_receipts.py:106,127,128,136,145,163,181,201,215,234,248,264`) is duplicated by design and must be swept in both trees **in the same task** — that is precisely research Pitfall 1. Templates are likewise fully duplicated (`partials/` vs `mobile_partials/`), with `mobile_base.html:9-11` stating verbatim that it does not inherit from `base.html` and that tags **"must be duplicated here verbatim."**

---

### Q4. How tests assert rendered HTML attributes

**Analog: `tests/test_receipts.py:1048-1061`.** This is a near-perfect structural match for the Wave 0 `data-ref-cents` tests — it asserts a `data-*` attribute is **present in the OOB fragment** and **absent from the static form**, which is exactly the Pitfall 2 + Pitfall 8 shape:

```python
def test_web_receipt_name_input_has_autofill_markers(client, session, product):
    """09-08: the autofill fragment carries data-autofilled + autocomplete=off; the
    plain form include carries autocomplete=off but NOT the autofilled marker."""
    lookup = client.get(
        "/receipts/lookup", params={"code": "TEST-001", "name": ""}
    )
    assert lookup.status_code == 200
    assert 'data-autofilled="true"' in lookup.text
    assert 'autocomplete="off"' in lookup.text

    form = client.get("/receipts/new")
    assert form.status_code == 200
    assert 'autocomplete="off"' in form.text
    assert 'data-autofilled="true"' not in form.text
```

**The conventions to copy:**
- Plain `in response.text` substring assertions on the **raw attribute string including its quotes** — `'data-autofilled="true"'`, never a parsed DOM, never BeautifulSoup. No HTML parser is a dependency of this project.
- Status asserted first (`assert response.status_code == 200`), then attributes.
- **Negative assertions use the identical literal** with `not in` — this is the exact idiom Pitfall 8 needs (`data-ref-cents` absent on `min_sale`) and Pitfall 3 needs (inverting `test_export.py:230`'s `"Каталог"` to `not in`).
- Docstring opens with the plan/decision ID (`"""09-08: ..."""`) then states the contract in one sentence. Phase 18's should open with `D-14:` / `Pitfall 2:` etc.
- One test asserts both the positive and negative half — do not split.

**Supporting idioms already in the suite:**
- `tests/test_pricing_feature.py:70-81` — the closest *route*-level analog, testing `/products/lookup-price` (the very endpoint Pitfall 2 concerns). Note it asserts `'id="catalog"' in r.text` at `:77` and `'hx-swap-oob="true"' in r.text` at `:81`; `:77` must be inverted to `not in` and its `r.text.count("12,00") == 2` at `:80` recomputed once `catalog` is gone.
- `tests/test_receipts.py:397-398` — `assert 'inputmode="decimal"' in response.text` (same attribute-literal idiom on a price input).
- `tests/test_sales.py:976` — the one place a regex is used (`r'<template>\s*<tr id="batch-wrap-first" hx-swap-oob="outerHTML"'`); reserve regex for structure spanning tags. `data-ref-cents` needs no regex.

**Concrete Wave 0 shape** (`data-ref-cents` present on ДЦ/ПЦ, absent on `min_sale`):

```python
def test_product_form_cues_only_dc_and_pc(client, priced):
    """D-14/Pitfall 8: ДЦ and ПЦ carry data-ref-cents; min_sale — the guardrail —
    must NOT, or the cue invents a third price (criterion 1)."""
    r = client.get("/products/new", params={"code": "100"})
    assert r.status_code == 200
    assert 'id="cost"' in r.text and 'data-ref-cents="700"' in r.text
    assert 'id="sale"' in r.text and 'data-ref-cents="1200"' in r.text
    # min_sale renders, but bare — no reference, no cue
    assert 'id="min_sale"' in r.text
```

Fixture to reuse: `test_pricing_feature.py`'s `priced` fixture (`:30-38`) already seeds `_price("100", 2026, 1, consumer=1200, consultant=700)` — **the D-05 ДЦ/ПЦ pair the cue needs** — and `_price("200", 2026, 1, consumer=500)` (no consultant). D-22's new ДЦ-without-ПЦ test needs the mirror of `"200"`: a consultant-only row. Add it to the same fixture list.

---

### Q5. The `style.css` colour-token commenting convention (D-14)

The stylesheet **polices new colour roles in comments**, and every recent block either names its token role or explicitly disclaims inventing one. Three verified exhibits:

Header (`style.css:1-3`) — declares the global token set:
```css
/* Minimal readable defaults — no framework, no build step.
   Normalized to the Phase 2 UI-SPEC scale: 4/8/16/24/32/48px spacing,
   16/14/20/24px type at weights 400/600, accent #2563eb, destructive #b91c1c. */
```

`style.css:252-256` — the token's origin, named by role not by hex:
```css
/* Search match highlight: accent-tinted background, text color unchanged. */
mark {
  background: #e8effd;
  color: inherit;
}
```

`style.css:277-286` — **the closest analog for D-14's block**: phase-tagged header, purpose sentence, and an explicit "NOT a new color" disclaimer, with trailing per-line comments justifying each value:
```css
/* Batch picker (Phase 9): nested batch table under a form field / basket line. */
.batch-picker { margin: 8px 0 0; }                         /* sm gap instead of the default table margin-top */
.batch-picker tr.selected-batch td { background: #e8effd; } /* selection highlight — existing mark/search tint, NOT a new color */

/* Sales name->code search dropdown (Phase 12, D-09): click-to-select list
   rendered below the sales name input. Reuses the existing token scale and
   the existing mark/search tint (#e8effd) — no new color role. */
.name-search-list li button:hover, .name-search-list li button:focus-visible { background: #e8effd; }
```

**The convention, distilled:**
1. Block comment opens with **`/* <Feature> (Phase N[, D-NN]): <one-sentence purpose>.`**
2. It states the token provenance explicitly — either *"reuses the existing X tint — no new color role"* or, for genuinely new values, names the role.
3. New numbers are called out as exceptions (`:288-290`: *"the only new number is the 44px touch-target minimum (spacing exception, see UI-SPEC)"*).
4. Rules are one-liners; per-line trailing comments justify individual values.
5. `#2563eb` and `#b91c1c` are **named in the file header** — reusing them requires no justification. Anything else does.

**Applied to D-14** — research's proposed block (§Code Examples) already conforms; it is the correct text to land, and it correctly (a) tags the phase and decision, (b) justifies the three new tokens, (c) names the `#e8effd` avoidance, and (d) disclaims `#2563eb` as a reuse. Place it near `:277-286` with the other selection/highlight semantics. `#b45309` / `#fef9e7` / `#eff6ff` are the **only** new roles in this phase; per rule 5 they must be named as such — consider extending the `:1-3` header to list `#b45309` beside `accent`/`destructive`, since it becomes the fourth global colour role.

---

## Shared Patterns

### Decision-ID comments on every non-obvious line
**Source:** everywhere — `receipts.py:24-31`, `sales.py:140-142,251`, `receipt_lookup.html:7-10`, `style.css:279`
**Apply to:** all modified files
Every non-obvious branch cites its governing decision (`# D-01: ...`, `# PD-10: ...`, `# Pitfall 4: ...`, `{# WR-01: ... #}`). Phase 18 edits must cite `D-01`..`D-24` the same way. `receipts.py:142-143`'s *"D-02 superseded: the catalog consumer price (ПЦ) is this shop's default sale price"* is the model for recording a decision that overturns an earlier one — relevant because `catalog` is removed from `fill_fields` at `:127,145` in that exact comment's blast radius.

### Money inputs
**Source:** `receipt_price_inputs.html:7`
**Apply to:** every price input touched
`<input type="text" ... inputmode="decimal" placeholder="0,00" value="{{ value or '' }}">` — verbatim, identical across desktop and mobile. `data-ref-cents` is additive to this line and changes nothing else. Guarded by `tests/test_receipts.py:397-398`.

### Money is a string at the route boundary
**Source:** `receipts.py:182-183`
```python
    # Money/qty fields arrive as strings on purpose: Pydantic v2 rejects ""
    # for int | None, and parsing in the service gives the RU errors.
```
**Apply to:** `receipts.py`, `mobile_receipts.py`, `sales.py`, `mobile_sales.py`
Reinforces D-13: the route never parses money; `parse_optional_cents` does. Deleting `catalog: str = Form("")` shrinks this surface — it does not change the rule.

### Validation errors
**Source:** `receipt_price_inputs.html:8` — `{% if error %}<p class="error">{{ error }}</p>{% endif %}`
**Apply to:** all templates. One message per field, server-rendered. The cue is **not** an error and must never render as `.error` (criterion: it is advisory — see §Specific Ideas in CONTEXT.md).

### Service-owned message constants
**Source:** `app/services/catalog.py:18-20`, `corrections.py:23-29`, `customers.py:18-21`
**Apply to:** D-23's two new hint constants (see Q1)

---

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `app/static/price-cue.js` | client utility | event-driven | **No standalone first-party JS file exists.** `app/static/` holds only `htmx.min.js` (vendored) and `style.css`. The nearest precedents are *inline* scripts — `base.html:6-14`'s viewport redirect and the 42 `hx-on:` handlers (D-11). So the *file* has no analog, but research §Code Examples supplies complete source, and D-10/D-12/D-13 pin the design. **Pattern to carry over from `style.css`/route modules regardless: the leading comment block naming the phase, the requirement (PROD-06), and the governing decisions — research's proposed header already does this and should land verbatim.** Its `<script src="/static/price-cue.js" defer></script>` tag copies `base.html:22` / `mobile_base.html:16`'s existing vendored-htmx line, duplicated in both (mobile_base does not inherit). |

Everything else has an exact in-repo analog — usually the file's own surviving `cost`/`sale` twins, since `catalog_cents` was added as a third sibling to an existing pair and is removed by deleting one of three parallel branches at each site.

## Metadata

**Analog search scope:** `app/routes/`, `app/services/`, `app/templates/{pages,partials,mobile_partials}/`, `app/static/`, `tests/`, `alembic/versions/`
**Files read for extraction:** 12 (`receipts.py`, `sales.py`, `mobile_sales.py:1-30`, `mobile_receipts.py:1-30`, `receipt_price_inputs.html`, `receipt_form.html:60-89`, `receipt_lookup.html`, `product_price_autofill.html`, `style.css:1-12,245-294`, `test_receipts.py:1044-1061`, `test_pricing_feature.py:30-89`)
**Removal surface:** taken from `18-RESEARCH.md` §"Authoritative `catalog_cents` Removal Surface" — not re-derived
**Pattern extraction date:** 2026-07-16
