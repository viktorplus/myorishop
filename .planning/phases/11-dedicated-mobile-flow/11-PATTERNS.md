# Phase 11: Dedicated Mobile Flow - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** ~20 new files (routes, templates, one CSS extension, one base-template edit)
**Analogs found:** 20 / 20 (every new file has a direct desktop analog — this phase is additive-only, zero new domain logic per RESEARCH.md)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/templates/mobile_base.html` | config/layout | request-response | `app/templates/base.html` | exact (new sibling layout, same htmx-config + viewport meta requirements) |
| `app/templates/base.html` (edit: add redirect `<script>`) | config/layout | request-response | itself (in-place edit) | exact |
| `app/routes/mobile_home.py` | route | request-response | `app/routes/home.py` | role-match (home is even simpler: no service call, static tile list) |
| `app/templates/mobile_pages/home.html` | component | request-response | `app/templates/pages/home.html` | role-match |
| `app/routes/mobile_search.py` | route | request-response | `app/routes/sales.py::sale_lookup` (GET, read-only lookup) | role-match |
| `app/routes/mobile_receipts.py` | route | CRUD (wizard, multi-step) | `app/routes/receipts.py` | exact (same service `register_receipt`) |
| `app/routes/mobile_sales.py` | route | CRUD (wizard, basket) | `app/routes/sales.py` | exact (same service `register_sale`, same array-shaped POST body) |
| `app/routes/mobile_writeoff.py` | route | CRUD (wizard) | `app/routes/writeoffs.py` | exact (same service `register_writeoff`) |
| `app/routes/mobile_corrections.py` | route | CRUD (wizard) | `app/routes/corrections.py` (same shape as writeoffs.py) | exact (same service `register_correction`) |
| `app/routes/mobile_transfers.py` | route | CRUD (wizard) | `app/routes/transfers.py` | exact (same service `register_transfer`) |
| `app/routes/mobile_returns.py` | route | CRUD (single-step, entry from history) | `app/routes/returns.py` | exact (same service `register_return`) |
| `app/routes/mobile_history.py` | route | request-response (read, paginated) | `app/routes/history.py` | exact (same service `history_view`, same HX-Request branch pattern) |
| `app/routes/mobile_reports.py` | route | request-response (read-only) | `app/routes/reports.py::reports_expiry_page` | exact (same service `expiring_batches`) |
| `app/templates/mobile_partials/*_wizard_step_*.html` | component | request-response (htmx swap fragment) | `app/templates/partials/sale_lookup.html`, `sale_batch_pick.html`, `writeoff_lookup.html`, `writeoff_batch_wrap.html` | role-match (hidden-field carry-forward + OOB conventions) |
| `app/templates/mobile_partials/batch_card_picker.html` | component | request-response (htmx swap fragment) | `app/templates/partials/batch_picker.html` | exact (same 4 fields: price, expiry, remaining qty, comment — reshaped from `<table>` radios to `<div class="mobile-card">` tappable cards) |
| `app/templates/mobile_pages/history.html` + `mobile_partials/history_*.html` | component | request-response (read, paginated) | `app/templates/pages/history.html`, `app/templates/partials/history_response.html`, `history_filters.html`, `history_rows.html`, `history_load_more.html` | exact |
| `app/templates/mobile_pages/reports_expiry.html` | component | request-response (read-only) | `app/templates/pages/reports_expiry.html` | exact |
| `app/static/style.css` (edit: append mobile classes) | config | n/a | itself (in-place additive edit) | exact |
| `tests/test_mobile_*.py` (9 files) | test | request-response / CRUD | `tests/test_sales.py`, `tests/test_writeoffs.py`, `tests/test_history.py`, `tests/test_reports.py`, `tests/conftest.py` fixtures | exact (same TestClient + fixture reuse pattern) |

## Pattern Assignments

### `app/routes/mobile_home.py` (route, request-response)

**Analog:** `app/routes/home.py`

**Full pattern** (`app/routes/home.py:1-16`):
```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.ledger import ledger_view

router = APIRouter()


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    context = ledger_view(session)
    return templates.TemplateResponse(request, "pages/home.html", context)
```
Mobile home (`GET /m/`) needs no service call at all — it's a static 8-tile list (D-03) — so the mirrored route is even thinner: build the tile list inline (or a tiny constant) and pass it as context to `mobile_pages/home.html`. Keep the same `APIRouter()` + `templates.TemplateResponse(request, "mobile_pages/home.html", context)` shape.

---

### `app/routes/mobile_sales.py` (route, CRUD wizard + basket)

**Analog:** `app/routes/sales.py`

**Imports pattern** (lines 1-19):
```python
import logging
import re

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import new_id
from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import open_batches
from app.services.customers import create_customer, customer_search_view
from app.services.sales import lookup_prefill, non_blank_lines, recent_sales, register_sale

router = APIRouter()
logger = logging.getLogger(__name__)
SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."
```
Mobile wizard imports the same services (`open_batches`, `lookup_prefill`, `register_sale`) — zero new service imports. Reuse `_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")` verbatim if any mobile step echoes an id into an `hx-on::load`/`hx-vals` attribute (CR-01 precedent).

**Batch ownership re-validation pattern** (lines 191-194, repeat verbatim in every mobile batch-pick endpoint per T-09-08):
```python
picked: Batch | None = None
if batch_id and product is not None:
    candidate = session.get(Batch, batch_id)
    if candidate is not None and candidate.product_id == product.id:
        picked = candidate
```

**Final-step write + guardrail branching pattern** (lines 298-375, `sale_create`):
```python
@router.post("/sales")
def sale_create(
    request: Request,
    code: list[str] = Form([], alias="code[]"),
    qty: list[str] = Form([], alias="qty[]"),
    price: list[str] = Form([], alias="price[]"),
    batch_id: list[str] = Form([], alias="batch_id[]"),
    customer_id: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        result, errors = register_sale(
            session, customer_id=customer_id, codes=code, qtys=qty,
            prices=price, batch_ids=batch_id, confirm=confirm,
        )
    except Exception:  # noqa: BLE001
        logger.exception("register_sale failed")
        ...  # 422 with SAVE_FAILED_ERROR

    # D-06/Pitfall 5: check BOTH oversell and below_minimum, zero writes
    if result and (result.get("oversell") or result.get("below_minimum")):
        ...  # re-render with warning, confirm button re-POSTs with confirm=1

    if errors:
        ...  # 422 re-render

    # success: fresh state
```
Mobile's final wizard-step POST (`/m/sales` or `/m/sales/step/confirm`) must reuse this exact `try/except` -> `oversell or below_minimum` -> `errors` -> success branching order, calling `register_sale` unchanged, threading `confirm` through exactly as here (Pitfall 5).

**Array-shaped basket POST body** (lines 301-307) is the exact shape a mobile basket wizard naturally accumulates via hidden-field carry-forward (RESEARCH.md Pattern 1) — no adaptation needed at the write boundary.

---

### `app/routes/mobile_writeoff.py` / `mobile_corrections.py` (route, CRUD wizard, single scalar batch_id)

**Analog:** `app/routes/writeoffs.py` (corrections.py follows the identical shape — same lookup/batch-pick/create structure, swap `register_writeoff` for `register_correction`)

**Lookup + batch pre-fetch pattern** (lines 36-67, `writeoff_lookup`):
```python
@router.get("/writeoff/lookup")
def writeoff_lookup(request: Request, code: str = "", name: str = "", session: Session = Depends(get_session)):
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    code_clean = code.strip()
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    batches = open_batches(session, product.id) if product is not None else []
    context = {
        "name": result["name"], "code": code_clean, "batches": batches,
        "selected_batch_id": None, "batch_id_value": "",
        "show_empty": product is not None and not batches,
    }
    return templates.TemplateResponse(request, "partials/writeoff_lookup.html", context)
```
Mobile's "find product" wizard step (D-05 step 1) follows this exact shape, rendering a mobile partial instead. `show_empty` -> Pitfall 6 (block forward progress when zero open batches).

**Write endpoint with echo + rollback safety** (lines 99-189): same `try/except` with `session.rollback()` on the except branch (WR-03 precedent) -> `oversell` warn branch -> `errors` 422 branch -> success branch with `include_oob_rows` toggle. Mobile confirm step reuses this unchanged, calling `register_writeoff`/`register_correction`.

---

### `app/routes/mobile_history.py` (route, request-response, paginated read)

**Analog:** `app/routes/history.py`

**Full pattern** (lines 1-52):
```python
@router.get("/history")
def history_page(request: Request, type: str = "", product: str = "", page: int = 0, session: Session = Depends(get_session)):
    result = history_view(session, type_filter=type or None, product_id=product or None, page=page)
    is_hx = bool(request.headers.get("HX-Request"))
    context = {
        "rows": result["rows"], "has_next": result["has_next"], "page": result["page"],
        "type_filter": result["type_filter"], "product_id": result["product_id"],
    }
    if is_hx:
        return templates.TemplateResponse(request, "partials/history_response.html", context)
    context["products"] = filter_products(session)
    return templates.TemplateResponse(request, "pages/history.html", context)
```
Mobile history (CONTEXT.md: single simplified filter) reuses `history_view` unchanged, same `HX-Request` branch to avoid the CR-01 bare-fragment bug — a plain GET always gets full `mobile_base.html` chrome; only a genuine htmx request gets the rows-only partial.

---

### `app/routes/mobile_reports.py` (route, request-response, read-only)

**Analog:** `app/routes/reports.py::reports_expiry_page`

**Full pattern** (lines 169-178):
```python
@router.get("/reports/expiry")
def reports_expiry_page(request: Request, session: Session = Depends(get_session)):
    today = datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()
    context = {"rows": expiring_batches(session), "today": today}
    return templates.TemplateResponse(request, "pages/reports_expiry.html", context)
```
Mobile expiry report (`/m/reports/expiry`) is a direct copy of this route, rendering `mobile_pages/reports_expiry.html` (card layout per D-07 style, read-only, no filter).

---

### `app/templates/mobile_partials/batch_card_picker.html` (component, request-response fragment)

**Analog:** `app/templates/partials/batch_picker.html` (full file, lines 1-69)

Key fields to carry into the mobile card (D-07 requirement — all visible, no truncation):
```html
<td class="num">{% if b.price_cents is not none %}{{ b.price_cents | cents }}{% else %}<span class="muted">—</span>{% endif %}</td>
<td>{% if b.expiry %}{{ b.expiry | ru_date }}{% else %}<span class="muted">—</span>{% endif %}</td>
<td class="num">{{ b.quantity }}</td>
<td>
  {%- if b.location or b.comment -%}
    {%- if b.location %}<span class="muted">{{ b.location }}</span>{% endif -%}
    {%- if b.location and b.comment %} · {% endif -%}
    {%- if b.comment %}{{ b.comment }}{% endif -%}
  {%- else -%}<span class="muted">—</span>{%- endif -%}
</td>
```
Reshape each `<tr>` into a `<div class="mobile-card">` with the same four fields inline (price, expiry, remaining qty, comment/location), keep the hidden `batch_id` input pattern (line 27: `<input type="hidden" name="{{ batch_input_name }}" value="{{ batch_id | default('') or '' }}">`), keep the empty state text verbatim: `<p class="muted">Нет партий с остатком.</p>` (line 67). Tapping the card = the same `hx-get`/`hx-vals`/`hx-target`/`hx-swap="outerHTML"` idiom as the radio input (lines 44-49), just moved onto the whole card element instead of a radio.

**Ownership/untrusted-text note** (lines 22-23, comment preserved): batch comment/location are untrusted stored text — Jinja autoescape only, never `| safe`.

---

### `app/templates/mobile_base.html` (config/layout)

**Analog:** `app/templates/base.html` (full file, lines 1-37)

**Must copy verbatim** (Pitfall 3 + Pitfall 4):
```html
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="htmx-config"
      content='{"responseHandling":[{"code":"204","swap":false},{"code":"[23]..","swap":true},{"code":"422","swap":true},{"code":"[45]..","swap":false,"error":true}]}'>
<link rel="stylesheet" href="/static/style.css">
<script src="/static/htmx.min.js" defer></script>
```
Difference from `base.html`: no `<nav>` with 12 links — D-03/D-04 require only a "← Главная" back control per operation screen instead. `mobile_base.html` is a new, separate file (not `{% extends "base.html" %}` — RESEARCH.md is explicit on this).

---

### `app/templates/base.html` (edit: add redirect script)

**Analog:** itself — insert at the very top of `<head>`, before the stylesheet and before htmx loads (RESEARCH.md Pattern 2):
```html
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script>
    if (window.location.pathname === "/" &&
        window.matchMedia("(max-width: 599px)").matches) {
      window.location.replace("/m/");
    }
  </script>
  ...
```
Scope strictly to `pathname === "/"` (Pitfall 2 — a broader scope makes desktop-only pages like `/customers`, `/backup` unreachable from phone width).

## Shared Patterns

### Guardrail warn-but-allow (min-price, oversell, over-removal)
**Source:** `app/routes/sales.py:340-350` (oversell/below_minimum), `app/routes/writeoffs.py:152-164` (oversell)
**Apply to:** every mobile wizard's final confirm step (sales, writeoff, corrections, transfers)
```python
if result and (result.get("oversell") or result.get("below_minimum")):
    context = {..., "oversell": result.get("oversell"), "below_minimum": result.get("below_minimum")}
    return templates.TemplateResponse(request, "partials/sale_form.html", context)  # NO status_code override — 200, re-render with warning
```
Never omit `confirm` when re-calling the service on the danger-button re-POST (Pitfall 5).

### Batch ownership re-validation
**Source:** `app/routes/sales.py:191-194`, `app/routes/writeoffs.py:84-88`
**Apply to:** every mobile batch-pick endpoint (sales, writeoff, corrections, transfers)
```python
candidate = session.get(Batch, batch_id)
if candidate is not None and candidate.product_id == product.id:
    picked = candidate
```

### HX-Request branch for read-only list pages (avoid CR-01 bare-fragment bug)
**Source:** `app/routes/history.py:41-52`, `app/routes/reports.py:114-119`
**Apply to:** `mobile_history.py`, any mobile report page with filtering
```python
is_hx = bool(request.headers.get("HX-Request"))
if is_hx:
    return templates.TemplateResponse(request, "mobile_partials/history_response.html", context)
return templates.TemplateResponse(request, "mobile_pages/history.html", context)
```

### `<meta name="htmx-config">` + `<meta name="viewport">` in every new base template
**Source:** `app/templates/base.html:5,9-10`
**Apply to:** `mobile_base.html` (Pitfall 3, Pitfall 4 — both must be copied verbatim or 422 responses/small-rendering bugs occur)

### `<template>`-wrapped OOB fragments
**Source:** `app/templates/partials/sale_lookup.html` (per RESEARCH.md Pitfall 1, Phase 9 Plan 06 fix)
```html
{% if picked is not none %}
<template>
  <td id="price-{{ row_id }}" hx-swap-oob="true">
    <input name="price[]" value="{{ fill_price_cents | cents }}">
  </td>
</template>
{% endif %}
```
**Apply to:** any mobile step that OOB-refreshes a sibling hint (e.g. an auto-filled price) whose root tag is `<tr>/<td>/<th>/<li>/<option>`/etc. Mobile batch cards themselves use `<div>` so this is unlikely to recur for the card UI, but applies to any other sibling OOB hint.

### Row-id echo format validation (CR-01)
**Source:** `app/routes/sales.py:31` (`_ROW_ID_RE`)
```python
_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")
```
**Apply to:** any mobile wizard step that echoes a client-supplied id into an `hx-on::load`/`hx-vals` JS-evaluated attribute.

## No Analog Found

None — every new/modified file for this phase has a direct desktop analog (this is an explicitly additive phase with zero new domain logic; see RESEARCH.md "Summary" and "Don't Hand-Roll" table).

## Metadata

**Analog search scope:** `app/routes/`, `app/templates/pages/`, `app/templates/partials/`, `app/templates/base.html`, `tests/`
**Files scanned:** `home.py`, `sales.py`, `writeoffs.py`, `history.py`, `reports.py`, `base.html`, `batch_picker.html` (read in full); `receipts.py`, `corrections.py`, `transfers.py`, `returns.py` referenced by RESEARCH.md's verified service map (not re-read — same shape as `writeoffs.py`/`sales.py`, confirmed via RESEARCH.md's Don't-Hand-Roll table and Code Examples section)
**Pattern extraction date:** 2026-07-12
