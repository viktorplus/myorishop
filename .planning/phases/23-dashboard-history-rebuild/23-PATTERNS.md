# Phase 23: Dashboard & History Rebuild - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 15 (new + modified)
**Analogs found:** 15 / 15

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/models.py` (+`ActiveCatalog`) | model | CRUD (singleton row) | `app/models.py` `Customer`/`Warehouse` shape (via 0015 migration precedent) | role-match |
| `alembic/versions/0016_active_catalog.py` | migration | file-I/O (schema) | `alembic/versions/0015_customer_contacts.py` | exact |
| `app/services/active_catalog.py` (NEW) | service | CRUD | `app/services/catalogs.py` (small helper style) | role-match |
| `app/services/dashboard.py` (NEW) | service | request-response (read composition) | `app/routes/finance.py::_metrics_context` + `app/services/sales.py::recent_sales` | exact (composition) |
| `app/routes/home.py` | route/controller | request-response | `app/routes/finance.py::finance_page` (context composition + template render) | exact |
| `app/routes/mobile_home.py` | route/controller | request-response | `app/routes/finance.py` desktop route generalized to mobile pattern; also see `app/routes/mobile_history.py` | role-match |
| `app/routes/catalogs.py` (+POST form) | route/controller | CRUD (form submit) | `app/routes/finance.py` (POST-form + Depends(get_session) pattern), see also any `Form(...)` route | role-match |
| `app/services/operations.py::history_view` (extended) | service | CRUD (filtered query) | itself (existing function, extend in place) | exact |
| `app/routes/history.py` | route/controller | request-response | itself (existing route, extend in place) | exact |
| `app/routes/mobile_history.py` | route/controller | request-response | `app/routes/history.py` (desktop numbered-pagination target pattern) | role-match |
| `app/templates/pages/home.html` | template | request-response | `app/templates/pages/catalogs.html` / `app/templates/pages/history.html` (list+tiles page shape) | role-match |
| `app/templates/mobile_pages/home.html` | template | request-response | itself (existing tile grid — ADD ABOVE, don't replace) | exact |
| `app/templates/partials/history_rows.html` | template (partial) | streaming (HTMX swap) | itself (existing swap-on-filter-change partial, extend column set) | exact |
| `app/templates/mobile_partials/history_cards.html` | template (partial) | streaming (HTMX swap) | `app/templates/partials/history_rows.html` (numbered pagination target) + itself (card layout) | role-match |
| `app/templates/partials/dashboard_tiles.html` (NEW) | template (partial) | request-response | `app/templates/pages/finance.html`/tiles used by `_metrics_context` (metrics tile rendering) | role-match |

## Pattern Assignments

### `app/services/dashboard.py` (service, request-response / read composition)

**Analog:** `app/routes/finance.py::_metrics_context` (lines 69-99) + `app/services/sales.py::recent_sales` (lines 332-352)

**Multi-period composition pattern** (copy verbatim, generalize to 3 periods):
```python
# app/routes/finance.py:69-99 (existing, verified)
def _metrics_context(session: Session, from_: str, to: str) -> dict:
    period = _resolve_period(from_, to, settings.display_tz)
    metrics = None
    if not period["error"]:
        start_iso, end_iso = local_day_bounds_utc(
            period["from_date"], period["to_date"], settings.display_tz
        )
        gross = sales_profit_report(session, start_iso, end_iso)
        expense = cash_expense_total(session, start_iso, end_iso)
        metrics = {
            "gross_profit_cents": gross["totals"]["profit_cents"],
            "cost_unknown_count": gross["totals"]["cost_unknown_count"],
            "net_profit_cents": gross["totals"]["profit_cents"] + expense,  # ADDITION, never subtraction
        }
    valuation = stock_valuation(session)
    return {...}
```
For DASH-03, call this shape 3x (today/week/month) using `app/routes/reports.py::_resolve_period`'s exact Monday-start-week / calendar-month boundary math — do not invent new boundary logic. Import `local_day_bounds_utc` from `app.core`, `sales_profit_report` from `app.services.reports`, `cash_expense_total`/`stock_valuation` from `app.services.finance_reports`.

**Feed query — double-outerjoin pattern** (copy verbatim, generalize WHERE only):
```python
# app/services/sales.py:332-352 (existing, verified) — docstring explicitly warns:
# "Both hops MUST stay outerjoin ... Do not 'simplify' to `.join`"
def recent_sales(session: Session, limit: int = 10) -> list[dict]:
    rows = session.execute(
        select(Operation, Product, Customer)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
        .where(Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product, "customer": customer} for op, product, customer in rows]
```
Generalize the WHERE only: `.where(Operation.type.in_(STOCK_AFFECTING_TYPES))` (import from `app.services.ledger`). Keep both outerjoins exactly as-is — non-sale rows have NULL `sale_id` by construction (verified `app/services/ledger.py:15-20`).

**Distinct-code count** (no existing precedent — new SQL-side aggregation, matches project convention of never Python-looping for counts):
```python
select(func.count()).select_from(Product).where(Product.deleted_at.is_(None), Product.quantity > 0)
```

---

### `app/routes/home.py` (controller, request-response) — full rebuild

**Analog:** `app/routes/finance.py::finance_page` (context composition, Depends(get_session), thin route delegating to service)

Current stub (`app/routes/home.py:1-17`, entire file):
```python
"""GET / — main page: ledger table + correction form (thin route, D-11/D-12)."""
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
Replace `ledger_view(session)` call with the new `app/services/dashboard.py` composition function(s), following `finance_page`'s pattern of spreading multiple context dicts: `{**_history_context(session), **_metrics_context(session, ...)}`.

---

### `app/routes/mobile_home.py` (controller, request-response) — full rebuild

**Analog:** current file itself (static stub) + `app/routes/finance.py`/`app/routes/mobile_history.py` for the Depends(get_session)+service-call shape

Current stub (entire file, 13 lines):
```python
"""Mobile home (D-03): static 8-tile grid, no service call."""
from fastapi import APIRouter, Request
from app.routes import templates

router = APIRouter()

@router.get("/m/")
def mobile_home(request: Request):
    return templates.TemplateResponse(request, "mobile_pages/home.html", {})
```
Add `Depends(get_session)` and call the SAME `app/services/dashboard.py` functions as desktop `home.py` (D-10: same data, own template). **Pitfall 1 (from RESEARCH.md):** `mobile_pages/home.html`'s existing 10-tile navigation grid is the ONLY way to reach `/m/sales`, `/m/receipts`, etc. — the new dashboard content must be ADDED above/around it, not replace it (no persistent mobile nav bar exists until Phase 24/MOB-01).

---

### `app/services/active_catalog.py` (NEW service, CRUD) + `app/models.py::ActiveCatalog`

**Analog:** `alembic/versions/0015_customer_contacts.py` (migration shape), `app/services/catalogs.py` (small get/set helper style, module docstring convention)

**Migration pattern** (copy structure, adapt columns — verified `alembic/versions/0015_customer_contacts.py:34-59`):
```python
def upgrade() -> None:
    op.create_table(
        "active_catalog",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("number", sa.String(20), nullable=True),
        sa.Column("close_date", sa.String(10), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_active_catalog")),
    )

def downgrade() -> None:
    op.drop_table("active_catalog")
```
Next revision id: `0016` (down_revision = `"0015"`), per `0015`'s own header block. **Pitfall 2:** there is currently NO `Catalog` DB table at all — `app/services/catalogs.py`'s module docstring (lines 1-6) states catalogs are a pure filename scan; do not assume `get_catalog()`/`list_catalogs()` can just grow fields.

---

### `app/routes/catalogs.py` (+ new POST form for DASH-02)

**Analog:** itself (existing GET routes, thin-route + Depends(get_session) + `templates.TemplateResponse` pattern, verified lines 52-63)

```python
# app/routes/catalogs.py:52-63 (existing pattern to mirror for the new POST handler)
@router.get("/catalogs")
def catalogs_page(request: Request, year: str = "", sort: str = "", page: int = 0,
                   session: Session = Depends(get_session)):
    context = _catalogs_context(session, year=year, sort=sort, page=page)
    is_hx = bool(request.headers.get("HX-Request"))
    template = "partials/catalog_rows.html" if is_hx else "pages/catalogs.html"
    return templates.TemplateResponse(request, template, context)
```
Route stays thin; all write validation goes in `app/services/active_catalog.py` (mirrors D-00c discipline noted in `app/routes/finance.py`'s module docstring: "Routes stay THIN — ALL validation lives in the service").

---

### `app/services/operations.py::history_view` (EXTENDED, same function) — HIST-01/02/03

**Analog:** itself (existing function, verified lines 23-78) — extend in place, do not create a v2/parallel function (D-03 explicit)

```python
# app/services/operations.py:17-20 — existing allow-list sort pattern to extend
_SORT_MAP = {
    "oldest": (Operation.created_at.asc(), Operation.seq.asc()),
}
_DEFAULT_ORDER = (Operation.created_at.desc(), Operation.seq.desc())
```
```python
# app/services/operations.py:57-62 — existing filter-membership-check pattern to extend
# to new customer_id/category/date_from/date_to params (never string-interpolated)
if type_filter and type_filter in OPERATION_TYPES:
    stmt = stmt.where(Operation.type == type_filter)
    count_stmt = count_stmt.where(Operation.type == type_filter)
if product_id:
    stmt = stmt.where(Operation.product_id == product_id)
    count_stmt = count_stmt.where(Operation.product_id == product_id)
```
New customer filter needs `Operation.sale_id -> Sale.customer_id` — reuse `recent_sales`'s double-outerjoin shape (only add the join when customer filter is active, per D-05). New category filter joins `Product.category` (Product already joined). New date filters: use `date.fromisoformat` + `local_day_bounds_utc`, mirroring `app/routes/reports.py::_resolve_period`'s malformed/inverted-range fallback-to-today pattern — do not reinvent.

**Existing pagination pattern to keep unchanged** (lines 64-69):
```python
total = session.scalar(count_stmt) or 0
total_pages = max(1, -(-total // page_size))
page = max(0, min(page, total_pages - 1))
stmt = stmt.limit(page_size).offset(page * page_size)
```

**Customer filter source:** `app/services/customers.py::search_customers` (lines 232-243) — reuse verbatim for the dropdown/autocomplete source, do not build a new search widget.

**Category filter source:** `app/services/catalog.py::category_options` (lines 474-484) — reuse verbatim.

---

### `app/routes/history.py` (EXTENDED, same route)

**Analog:** itself (existing route, verified full file 63 lines) — extend query params in place

```python
# app/routes/history.py:16-27 — existing signature to extend with customer/category/date_from/date_to
@router.get("/history")
def history_page(request: Request, type: str = "", product: str = "", sort: str = "",
                  page: int = 0, session: Session = Depends(get_session)):
    result = history_view(session, type_filter=type or None, product_id=product or None,
                           sort=sort, page=page)
```
```python
# lines 36-45 — existing extra_qs re-serialization pattern; new filter params must be added here too
qs_parts = {k: v for k, v in {"type": result["type_filter"], "product": result["product_id"],
                                "sort": result["sort"]}.items() if v}
extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
```

---

### `app/templates/partials/history_rows.html` (EXTENDED — column set swap)

**Analog:** itself (existing swap-on-filter-change partial, verified full file)

```html
<!-- history_rows.html:9-21 — existing swap-in-place trigger pattern (hx-target="#history-rows" hx-swap="outerHTML") -->
<div id="history-rows">
  <div class="filter-bar">
    <div class="field">
      <select id="sort" name="sort" hx-get="/history" hx-trigger="change"
              hx-include="#history-rows input, #history-rows select"
              hx-target="#history-rows" hx-swap="outerHTML" hx-push-url="true">
```
For HIST-01, the same `hx-get="/history" ... hx-target="#history-rows" hx-swap="outerHTML"` trigger already fires on the type `<select>` (lines 39-48) — no new HTMX wiring needed, just make the returned `<thead>`/`<tbody>` column set conditional on `type_filter` (server-side Jinja `{% if %}` branching, per-type column map from RESEARCH.md's `HISTORY_TYPE_COLUMNS` dict pattern). **Pitfall 5:** keep all 9 types in the dropdown (line 44 `{% for t, label in OPERATION_TYPE_LABELS.items() %}`) — the 3 audit types fall back to today's existing generic 10-column render, only the 6 `STOCK_AFFECTING_TYPES` get narrowed columns.

**Sign-aware quantity rendering (reuse verbatim, don't reinvent per type):**
```html
<!-- history_rows.html:102 -->
<td class="num">{% if r.op.qty_delta > 0 %}+{{ r.op.qty_delta }}{% else %}{{ r.op.qty_delta }}{% endif %}</td>
```

**Correction note formatting (reuse verbatim inside narrower correction column set):**
```html
<!-- history_rows.html:108-109 -->
{{ "Пересчёт" if r.op.payload.mode == "count" else "Изменение" }}{% if r.op.payload.note %} — {{ r.op.payload.note }}{% endif %}
```

---

### `app/routes/mobile_history.py` (EXTENDED — migrate to numbered pagination)

**Analog:** `app/routes/history.py` (desktop's numbered `page_window` pattern to migrate onto) + itself (existing HX-Request/OOB-swap branching, verified full file)

```python
# app/routes/mobile_history.py:22-54 (existing) — currently derives has_next locally
# and renders TWO sibling templates (cards + oob load-more). D-10 replaces the
# load-more oob-swap with the SAME page_window()/extra_qs mechanism history.py
# already uses (verified app/services/pagination.py::page_window, LIST_PAGE_SIZE=20).
result = history_view(session, type_filter=type or None, product_id=None, page=page)
context = {
    "rows": result["rows"],
    "has_next": result["page"] < result["total_pages"] - 1,  # DELETE — replace w/ page_window
    "page": result["page"],
    "type_filter": result["type_filter"],
}
```
Replace the `has_next`-sentinel context with `page_window`/`total_pages`/`extra_qs`, mirroring `app/routes/history.py:35-58` and `app/routes/finance.py::_history_context:51-66` exactly. Do NOT migrate `mobile_finance.py`'s load-more pagination — that stays out of scope (confirmed by RESEARCH.md's own note quoting `mobile_finance.py`'s "NOT the desktop numbered pagination bar" comment).

---

## Shared Patterns

### Sign convention for expense/profit
**Source:** `app/routes/finance.py::_metrics_context` line 87, `app/routes/mobile_finance.py::_metrics_context` (identical)
**Apply to:** `app/services/dashboard.py`'s period-metrics composition
```python
"net_profit_cents": gross["totals"]["profit_cents"] + expense,  # cash_expense_total already signed negative — ADDITION only
```

### Allow-list filter validation (never string-interpolate into SQL)
**Source:** `app/services/operations.py:57-59` (`type_filter in OPERATION_TYPES`), `app/services/operations.py:17-20` (`_SORT_MAP.get(sort, default)`)
**Apply to:** all new History filter params (customer_id, category, date_from/date_to) and any new sort options

### Numbered pagination (single sanctioned implementation)
**Source:** `app/services/pagination.py::page_window`/`paginate` (`LIST_PAGE_SIZE = 20`)
**Apply to:** `app/routes/history.py` (unchanged), `app/routes/mobile_history.py` (migrated), any dashboard list if paginated

### Thin routes / service does the writing
**Source:** `app/routes/finance.py` module docstring ("Routes stay THIN — every ... write and ALL validation ... live in the service, D-00c")
**Apply to:** `app/routes/catalogs.py`'s new POST handler, `app/routes/home.py`, `app/routes/mobile_home.py`

### extra_qs re-serialization for pagination links
**Source:** `app/routes/history.py:36-45`, `app/routes/finance.py::_history_context:52-54`
**Apply to:** `app/routes/mobile_history.py`'s pagination migration, any new History filter params added to the query string

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `app/templates/partials/dashboard_tiles.html` | template (partial) | request-response | No existing "3-period tile grid" template exists; closest precedent is `finance.html`'s single-period metrics tiles (`_metrics_context`'s consumer) — structurally similar but only 1 period, not 3. Build fresh, following that template's tile markup conventions. |
| Mobile dashboard card/accordion layout (`mobile_pages/home.html` additions) | template | request-response | D-10 explicitly requires "mobile's own card/accordion layout," not a copy of any existing template — Claude's discretion per CONTEXT.md. Closest structural precedent for accordion/card patterns: `app/templates/mobile_pages/history.html` + `mobile_partials/history_cards.html` (card list shape), but no accordion precedent exists in the codebase yet. |

## Metadata

**Analog search scope:** `app/routes/`, `app/services/`, `app/templates/pages/`, `app/templates/partials/`, `app/templates/mobile_pages/`, `app/templates/mobile_partials/`, `alembic/versions/`
**Files scanned:** `finance.py`, `mobile_finance.py`, `sales.py`, `operations.py`, `history.py`, `mobile_history.py`, `home.py`, `mobile_home.py`, `catalogs.py`, `catalogs.py` (service), `ledger.py`, `pagination.py`, `customers.py`, `catalog.py`, `history_rows.html`, `0015_customer_contacts.py`
**Pattern extraction date:** 2026-07-17
