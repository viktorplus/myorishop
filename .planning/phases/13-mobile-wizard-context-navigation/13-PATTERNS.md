# Phase 13: Mobile Wizard Context & Navigation - Pattern Map

**Mapped:** 2026-07-13
**Files analyzed:** 15 (existing files modified) + 1 new partial
**Analogs found:** 15 / 15 (all files have close in-codebase analogs — this phase is pure consistency-fix, no new architecture)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/templates/mobile_partials/_wizard_header.html` (NEW) | component (Jinja partial) | request-response (SSR include) | `sale_step_batch.html` line 12 + `receipts_step_details.html` line 11 (inline code/name line) | pattern-source (no direct analog file exists — synthesized from repeated inline pattern) |
| `app/templates/mobile_partials/corrections_step_batch.html` | component (wizard step) | request-response | `writeoff_step_batch.html` (same role: batch-pick step) / `receipts_step_details.html` (target back-nav shape) | role-match + pattern-target |
| `app/templates/mobile_partials/corrections_step_mode.html` | component (wizard step) | request-response | `receipts_step_details.html` (back-nav shape) | pattern-target |
| `app/templates/mobile_partials/corrections_step_value.html` | component (wizard step) | request-response | `receipts_step_confirm.html` (back-nav shape, final-step-with-warning shape) | pattern-target |
| `app/templates/mobile_partials/writeoff_step_batch.html` | component (wizard step) | request-response | `receipts_step_batch` fragment shape (target) + itself (source of drifted header) | pattern-target |
| `app/templates/mobile_partials/writeoff_step_qty.html` | component (wizard step) | request-response | `receipts_step_details.html` (exact fragment/back-nav shape to copy) | exact (structural target) |
| `app/templates/mobile_partials/writeoff_step_reason.html` | component (wizard step) | request-response | `receipts_step_confirm.html` (exact fragment/back-nav shape to copy) | exact (structural target) |
| `app/templates/mobile_pages/writeoff.html` | component (persistent shell page) | request-response | `app/templates/mobile_pages/receipts.html` | exact |
| `app/routes/mobile_writeoff.py` | controller/route | request-response (CRUD wizard) | `app/routes/mobile_receipts.py` | exact |
| `app/templates/mobile_partials/sale_basket.html` | component | request-response | `transfers_step_dest.html` line 9 (`mobile-step-indicator` usage) | role-match (CSS class reuse only) |
| `app/templates/mobile_partials/search_product_detail.html` | component | request-response | itself (add plain `<a href>` links) — no wizard-entry analog needed, "Продать"/"Принять" is a plain nav link | n/a — trivial addition |
| `app/routes/mobile_search.py` | controller/route | request-response | itself; `HX-Request` branch pattern (lines 20-29) reused elsewhere in this phase | exact (source of Pattern 2) |
| `app/routes/mobile_sales.py` (`mobile_sales_page`) | controller/route | request-response | `app/routes/mobile_receipts.py::mobile_receipt_new` (adding `code` query param, same shape) | exact |
| `app/routes/mobile_receipts.py` (`mobile_receipt_new`) | controller/route | request-response | itself — trivial edit (hardcoded `"code": ""` → `code` param) | exact |
| `app/routes/mobile_corrections.py` | controller/route | request-response | `app/routes/mobile_writeoff.py` (parallel wizard structure) + `mobile_search.py`'s `HX-Request` branch (for `mobile_correction_start`, if Open Question resolved to fix step-2 back-nav) | role-match |
| `app/routes/mobile_transfers.py` (`_warehouse_names`, read-only reference) | utility (helper) | CRUD (lookup) | n/a — this IS the reusable helper to copy into `mobile_writeoff.py`/`mobile_corrections.py` | exact (copy source) |

## Pattern Assignments

### `app/templates/mobile_partials/_wizard_header.html` (NEW component)

**Analog:** inline pattern already duplicated in `sale_step_batch.html:12` and `receipts_step_details.html:11`

**Current inline pattern (to extract into the new partial), verbatim from `sale_step_batch.html` line 12:**
```html
<p><strong>{{ code }}</strong>{% if name %} — {{ name }}{% endif %}</p>
```

**Recommended new file content** (per RESEARCH Code Examples section, context: `code` required, `name`/`warehouse_name` optional):
```html
<p><strong>{{ code }}</strong>{% if name %} — {{ name }}{% endif %}</p>
{% if warehouse_name %}<p>Склад: {{ warehouse_name }}</p>{% endif %}
```

**Usage from each of the 8 step templates:**
```html
{% include "mobile_partials/_wizard_header.html" %}
```

**Critical guard (Pitfall 3):** `warehouse_name` must be `None`/absent in the context dict when no batch is picked yet — never pass `""` — so the `{% if warehouse_name %}` correctly omits the line. Do NOT add this include to any wizard's step-1 "Товар" screen (out of scope per D-03's file list; those already have their own `name-fill`/`name_echo` partials, untouched).

---

### `app/templates/mobile_partials/corrections_step_batch.html`, `corrections_step_mode.html`, `corrections_step_value.html` (component, request-response)

**Analog for header:** `_wizard_header.html` (new, see above) — include right after the `<div id="corrections-step-wrap">` opening tag, before the `<h1>`.

**Analog for back-nav fix:** `app/templates/mobile_partials/receipts_step_details.html` line 43 and `receipts_step_confirm.html` line 51 — the `hx-post` + `hx-include="closest form"` idiom:
```html
<button type="button" class="secondary" hx-post="/m/receipts/step/batch" hx-include="closest form">Назад</button>
```

**Current corrections "Назад" (all 3 steps currently identical, WRONG for steps 3/4 per Pitfall 5), verbatim from `corrections_step_batch.html` line 22 / `corrections_step_mode.html` line 31 / `corrections_step_value.html` line 39:**
```html
<a class="mobile-back" href="/m/corrections">Назад</a>
```

**Required per-step fix (target routes, per Pitfall 5 — differs per step):**
- `corrections_step_batch.html` (step 2 → step 1): plain link to `/m/corrections` is actually correct target-wise (matches receipts' own step-2 precedent per Open Question) — decide during planning whether to leave as plain `<a>` or convert to `hx-get`+`HX-Request` branch (Pattern 2). Either is defensible; RESEARCH recommends converting for full consistency.
- `corrections_step_mode.html` (step 3 → step 2): must become `hx-post="/m/corrections/step/batch" hx-include="closest form"` (currently wrongly points at step 1, skipping step 2 — confirmed bug).
- `corrections_step_value.html` (step 4 → step 3): must become `hx-post="/m/corrections/step/mode" hx-include="closest form"` (currently wrongly points at step 1, skipping steps 2+3 — confirmed bug).

Note: `mobile_correction_step_mode`/`mobile_correction_step_batch` routes already return bare `#corrections-step-wrap` fragments (verified `mobile_corrections.py` lines 83-85, 115-117) — no route changes needed for the step 3/4 back-nav fix, only template attribute changes. `mode` value must additionally be threaded as a hidden input on step-4's form when re-deriving step-3 (mode route already accepts it via `Form(...)` params seen in signatures).

**Corrections' `register_correction` has NO `name` param (Pitfall 2)** — `name` in corrections templates is purely a carried hidden field, never passed to the service call (`mobile_correction_create` at `mobile_corrections.py` line 173 already omits it — do not add it).

---

### `app/templates/mobile_partials/writeoff_step_batch.html`, `writeoff_step_qty.html`, `writeoff_step_reason.html` (component, request-response) + `app/templates/mobile_pages/writeoff.html` (persistent shell) + `app/routes/mobile_writeoff.py` (controller)

**Analog (structural target for the whole migration):** `app/templates/mobile_pages/receipts.html` (shell) + `app/templates/mobile_partials/receipts_step_details.html`/`receipts_step_confirm.html` (fragment shape) + `app/routes/mobile_receipts.py` (route shape).

**Shell page pattern to mirror, verbatim from `mobile_pages/receipts.html`:**
```html
{% extends "mobile_base.html" %}
{% block content %}
<h1>Приход</h1>
...
<form id="receipt-form" hx-target="#wizard-step" hx-swap="innerHTML">
<div id="wizard-step">
  <p class="mobile-step-indicator">Шаг 1 из 4</p>
  ...
  <div class="mobile-actions">
    <button type="submit" hx-post="/m/receipts/step/batch" hx-include="closest form">Далее</button>
  </div>
</div>
</form>
{% endif %}
{% endblock %}
```

**Current write-off step 1 shell (to migrate), verbatim from `mobile_pages/writeoff.html`:**
```html
{% extends "mobile_base.html" %}
{% block step_indicator %}
{% if not saved %}<p class="mobile-step-indicator">Шаг 1 из 4</p>{% endif %}
{% endblock %}
{% block content %}
<h1>Списание</h1>
{% if saved %}
...
{% else %}
<form method="post" action="/m/writeoff/step/batch" class="stacked-form">
  ...
  <div class="mobile-actions">
    <button type="submit">Далее</button>
  </div>
</form>
{% endif %}
{% endblock %}
```
Needs: wrap the form body in `<div id="wizard-step">`, change `method="post" action=...` to `hx-target="#wizard-step" hx-swap="innerHTML"` on the `<form>`, change the submit button to `hx-post="/m/writeoff/step/batch" hx-include="closest form"`.

**Anti-pattern being removed (3 occurrences, Pitfall/Anti-Pattern section):** verbatim from `writeoff_step_batch.html` line 21, `writeoff_step_qty.html` line 17, `writeoff_step_reason.html` line 46:
```html
<button type="button" class="secondary" onclick="history.back()">Назад</button>
```
Replace each with the receipts idiom, targeting each step's own immediate-predecessor route:
- `writeoff_step_batch.html` "Назад" → `hx-post="/m/writeoff"` (or `hx-get` via `HX-Request` branch on `mobile_writeoff_start`, since that route currently ALWAYS returns the full page — Pitfall 4). This is the one write-off transition requiring a route change (`HX-Request` branch on `GET /m/writeoff`, mirroring `mobile_search.py` lines 20-29 exactly).
- `writeoff_step_qty.html` "Назад" → `hx-post="/m/writeoff/step/batch" hx-include="closest form"` (route already returns a bare fragment — verified `mobile_writeoff.py` line 94).
- `writeoff_step_reason.html` "Назад" → `hx-post="/m/writeoff/step/qty" hx-include="closest form"` (route already returns a bare fragment — verified `mobile_writeoff.py` line 134).

**`HX-Request` branch pattern to copy for `mobile_writeoff_start`, verbatim from `app/routes/mobile_search.py` lines 20-29:**
```python
@router.get("/m/search")
def mobile_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    context = search_view(session, q)
    # CR-01-precedent (history.py): only a genuine HX-Request gets the
    # rows-only fragment; a bookmarked/reloaded ?q=... URL still gets chrome.
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(
            request, "mobile_partials/search_results.html", context
        )
    return templates.TemplateResponse(request, "mobile_pages/search.html", context)
```

**Pitfall 1 fix (name-threading gap), current buggy state verbatim from `mobile_writeoff.py` lines 127-134 and 138-153:**
```python
@router.post("/m/writeoff/step/qty")
def mobile_writeoff_step_qty(request: Request, code: str = Form(""), batch_id: str = Form("")):
    context = {
        "errors": {},
        "code": code.strip(),
        "batch_id": batch_id.strip(),
        "qty": "",
    }
```
Missing: `name: str = Form("")` parameter and `"name": name.strip()` in context (same gap in `mobile_writeoff_step_reason`). Also `mobile_writeoff_submit` line 174 hardcodes `name=""` in the `register_writeoff(...)` call — should thread the real carried value once available (cosmetic per RESEARCH, not required by literal success criteria but consistent with other wizards).

**Warehouse-name helper to reuse, verbatim from `app/routes/mobile_transfers.py` lines 43-45:**
```python
def _warehouse_names(session: Session) -> dict[str, str]:
    """id -> name map so the batch-step card can show its own «Склад:» line."""
    return {w.id: w.name for w in active_warehouses(session)}
```
Copy this exact helper (or call `active_warehouses` inline) into `mobile_writeoff.py` and `mobile_corrections.py` to resolve `warehouse_name` from a picked `Batch.warehouse_id` (`Batch` has no ORM relationship to `Warehouse` — confirmed in RESEARCH — so build the dict once per request, do not query per-row).

---

### `app/templates/mobile_partials/sale_basket.html` (component, request-response) — UI-04

**Analog:** `mobile-step-indicator` CSS class usage in `transfers_step_dest.html` line 9:
```html
<p class="mobile-step-indicator">{{ step_label }}</p>
```
and in numbered wizard steps, e.g. `receipts_step_details.html` line 6:
```html
<p class="mobile-step-indicator">Шаг 3 из 4</p>
```

**Current `sale_basket.html` (needs the one-line addition), verbatim lines 5-6:**
```html
<div id="wizard-basket">
  <h2>Корзина</h2>
```

**Required change:** insert directly after the opening `<div id="wizard-basket">` (before or after `<h2>Корзина</h2>`, either order acceptable per D-07):
```html
<p class="mobile-step-indicator">Корзина</p>
```
No route change needed — this is a template-only edit, no new context variable required.

---

### `app/templates/mobile_partials/search_product_detail.html` + `app/routes/mobile_search.py` (component/route) — UI-05

**Analog:** the file's own existing plain-navigation convention (its own header comment, lines 1-4) confirms quick-action links must be plain `<a href>`, not htmx.

**Current file (no actions block yet), verbatim lines 7-17:**
```html
<h1>{{ product.name }} ({{ product.code or "" }})</h1>
{% if product.category %}
<p>{{ product.category }}</p>
{% else %}
<p class="muted">—</p>
{% endif %}
<p>Мин. цена: {% if product.min_sale_cents is not none %}{{ product.min_sale_cents | cents }}{% else %}—{% endif %}</p>
{% for row in stock_rows %}
<p>{{ row.warehouse_name }}: {{ row.total_qty }} шт.</p>
{% endfor %}
```

**Required addition** (mobile-actions block, mirroring the `<div class="mobile-actions">` convention used across every other wizard screen, e.g. `sale_step_batch.html` lines 17-26):
```html
<div class="mobile-actions">
  <a class="button" href="/m/sales?code={{ product.code }}">Продать</a>
  <a class="button secondary" href="/m/receipts?code={{ product.code }}">Принять</a>
</div>
```
Per D-09: "Продать" is always rendered regardless of `stock_rows`/zero-stock — no conditional wrapping.

**Route changes needed (D-08), verbatim target shape from RESEARCH Code Examples, applied to `mobile_sales.py::mobile_sales_page` (currently `mobile_sales.py` lines 38-46 — NO `code` param today):**
```python
# Current (mobile_sales.py lines 38-46):
@router.get("/m/sales")
def mobile_sales_page(request: Request):
    context = {
        "code": "",
        "error": None,
        "saved": None,
        **_acc_context([], [], [], []),
    }
    return templates.TemplateResponse(request, "mobile_pages/sales.html", context)
```
Change to accept `code: str = ""` and use it instead of the hardcoded `""`.

**`mobile_receipts.py::mobile_receipt_new` (currently lines 73-82 — NO `code` param today):**
```python
@router.get("/m/receipts")
def mobile_receipt_new(request: Request, session: Session = Depends(get_session)):
    actives = active_warehouses(session)
    context = {
        "zero_warehouses": not actives,
        "active_warehouses": actives,
        "selected_warehouse_id": _preselect_warehouse_id(actives),
        "code": "",
    }
    return templates.TemplateResponse(request, "mobile_pages/receipts.html", context)
```
Change to accept `code: str = ""` query param and use it in place of the hardcoded `"code": ""`. No lookup/prefill call is required — the existing debounced `hx-get`/`hx-trigger="input changed delay:300ms"` on the code `<input>` (already present in both wizards' step-1 templates) runs the name lookup once the field has a value, whether typed or pre-filled via `value="{{ code }}"`.

**Reference for query-param pattern already proven in this codebase**, verbatim `mobile_search.py` lines 20-21:
```python
@router.get("/m/search")
def mobile_search(request: Request, q: str = "", session: Session = Depends(get_session)):
```

---

## Shared Patterns

### Pattern A: Visible code/name/warehouse header
**Source:** new `_wizard_header.html` (synthesized from `sale_step_batch.html:12`, `receipts_step_details.html:11`)
**Apply to:** `corrections_step_batch.html`, `corrections_step_mode.html`, `corrections_step_value.html`, `writeoff_step_qty.html`, `writeoff_step_reason.html`, `writeoff_step_batch.html` (align existing partial format)
```html
<p><strong>{{ code }}</strong>{% if name %} — {{ name }}{% endif %}</p>
{% if warehouse_name %}<p>Склад: {{ warehouse_name }}</p>{% endif %}
```
Guard: `warehouse_name` must be `None` (not `""`) in route context until a batch is picked (Pitfall 3).

### Pattern B: "Назад" step-back navigation (previous step's own route redraws it)
**Source:** `app/templates/mobile_partials/receipts_step_details.html` line 43, `receipts_step_confirm.html` line 51
**Apply to:** all write-off steps (replacing `history.back()`), corrections steps 3 and 4 (fixing wrong target), corrections step 2 (optional, per Open Question)
```html
<button type="button" class="secondary" hx-post="/m/<wizard>/step/<previous>" hx-include="closest form">Назад</button>
```
Key rule: target the SAME route the previous step's own forward-post already hits — never invent a dedicated "back" endpoint (Anti-Pattern section, RESEARCH).

### Pattern C: `HX-Request` header branch for a route serving both full page and bare fragment
**Source:** `app/routes/mobile_search.py` lines 20-29 (`mobile_search`)
**Apply to:** `mobile_writeoff_start` (`GET /m/writeoff`) — required for write-off step 2's new "Назад" target; optionally `mobile_correction_start` (`GET /m/corrections`) if the Open Question is resolved toward full step-2 consistency
```python
if bool(request.headers.get("HX-Request")):
    return templates.TemplateResponse(request, "mobile_partials/<step1-fragment>.html", context)
return templates.TemplateResponse(request, "mobile_pages/<wizard>.html", context)
```

### Pattern D: Warehouse-id → name lookup dict
**Source:** `app/routes/mobile_transfers.py` lines 43-45 (`_warehouse_names`)
**Apply to:** `mobile_writeoff.py`, `mobile_corrections.py` (wherever a `warehouse_name` must be resolved from a picked `Batch.warehouse_id` for Pattern A's header line)
```python
def _warehouse_names(session: Session) -> dict[str, str]:
    return {w.id: w.name for w in active_warehouses(session)}
```
Never resolve via a raw per-row `session.get(Warehouse, ...)` — `Batch` has no ORM relationship to `Warehouse`.

### Pattern E: `?code=` GET query-param pre-fill
**Source:** `app/routes/mobile_search.py` line 21 (`q: str = ""` precedent), applied per RESEARCH Code Examples to `mobile_sales_page`/`mobile_receipt_new`
**Apply to:** `mobile_sales.py::mobile_sales_page`, `mobile_receipts.py::mobile_receipt_new`
```python
def mobile_sales_page(request: Request, code: str = ""):
    context = {"code": code, ...}
```

## No Analog Found

None — every file in scope has a directly applicable in-codebase analog (this phase is explicitly a consistency retrofit, not new capability; RESEARCH confirms zero new packages/architecture).

## Open Item Requiring Planner Decision

**Corrections step 2 "Назад"** (`corrections_step_batch.html` line 22, currently `<a class="mobile-back" href="/m/corrections">`): RESEARCH flags this as ambiguous — D-05's literal wording ("each step's Назад... mirroring receipts... exactly") could mean either (a) leave as plain link, matching receipts' own step-2 precedent (`receipts_step_batch.html` line 53, verified plain link there too), or (b) convert to `hx-get` + Pattern C for full internal consistency. The planner must make and log this call explicitly before task breakdown (affects whether `mobile_correction_start` needs a route change).

## Metadata

**Analog search scope:** `app/templates/mobile_partials/`, `app/templates/mobile_pages/`, `app/routes/mobile_*.py`
**Files scanned:** 19 (all 5 wizards' step templates/shells/routes + `mobile_search.py`/`search_product_detail.html`)
**Pattern extraction date:** 2026-07-13
