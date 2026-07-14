# Phase 14: List Pagination, Filtering, Sorting & Quick Delete - Pattern Map

**Mapped:** 2026-07-14
**Files analyzed:** 17 (5 services extended, 1 new service, 6 routes extended, 5+ templates new/extended, 1 migration)
**Analogs found:** 17 / 17

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/services/pagination.py` (NEW) | utility | transform | `app/services/operations.py:14-53` (offset pagination shape) | role-match (new module, no direct precedent) |
| `app/services/operations.py` (`history_view`) | service | CRUD (read, paginated) | itself — extend with total-count query | exact (self-extension) |
| `app/services/catalog.py` (`list_products` → filter/sort/page; NEW `quick_delete_product`) | service | CRUD | `app/services/warehouses.py:76-102` (`soft_delete_warehouse` guard shape) for quick_delete; `search_products`/`category_options` for filter/sort | exact for guard pattern, exact for list pattern |
| `app/services/warehouses.py` (`list_warehouses` → filter/sort/page; `soft_delete_warehouse` → new stock guard) | service | CRUD | itself — extend in place | exact (self-extension) |
| `app/services/customers.py` (new list/filter/sort function) | service | CRUD | `app/services/catalog.py:327-336` (`list_products`) + `search_customers` | role-match |
| `app/services/dictionary.py` (`list_entries` → SQL LIMIT/OFFSET+COUNT, filter/sort) | service | CRUD | `app/services/operations.py:14-53` (`history_view`, SQL-side pagination shape) | exact |
| `app/services/catalogs.py` (`list_catalogs` → year filter + sort + Python pagination) | service | CRUD/transform | `app/services/warehouses.py:19-27` (`list_warehouses`, Python-side sort) | role-match |
| `alembic/versions/0012_dictionary_name_lc.py` (NEW) | migration | batch | existing `alembic/versions/` convention (`render_as_batch=True`); Python-side backfill per Pitfall 1 | role-match, no exact prior `_lc` migration to cite directly (name_lc was added at model-creation time for Product/Customer) |
| `app/routes/products.py` (list route → filter/sort/page query params; NEW `POST /products/{id}/quick-delete`) | route | request-response | `app/routes/history.py` (`history_page`, is_hx dual-response) for filter/sort/page; `app/routes/warehouses.py:81-97` (`warehouse_delete`) for quick-delete shape | exact |
| `app/routes/warehouses.py` (list route → filter/sort/page; `warehouse_delete` → new stock guard, no new route) | route | request-response | itself — extend in place; `history_page` for filter/sort/page pattern | exact |
| `app/routes/customers.py` (list route → filter/sort/page, retire `/customers/search`) | route | request-response | `app/routes/history.py` (`history_page`) | role-match |
| `app/routes/dictionary.py` (list route → filter/sort/page) | route | request-response | `app/routes/history.py` (`history_page`) | role-match |
| `app/routes/catalogs.py` (list route → year filter/sort/page) | route | request-response | `app/routes/history.py` (`history_page`) | role-match |
| `app/routes/history.py` (`history_page` → sort param, page_size 20, drop `has_next`-only shape) | route | request-response | itself — extend in place | exact |
| `app/templates/partials/pagination.html` (NEW, shared) | component (Jinja partial) | request-response | UI-SPEC Contract A (copy-paste-ready markup); `partials/history_load_more.html` (the control it replaces) | exact (spec-provided) |
| `app/templates/partials/product_rows.html` (filter-row `<thead>`, sort dropdown, quick-delete button, pagination include) | component | request-response | `partials/warehouse_rows.html` (existing danger-button + hx-confirm pattern); `partials/history_filters.html` (filter-row precedent) | exact |
| `app/templates/partials/warehouse_rows.html` (filter-row, sort dropdown, stock guard error, drop deleted-row branch, pagination include) | component | request-response | itself — extend in place | exact |
| `app/templates/partials/customer_rows.html` / `dictionary_rows.html` / `catalog_rows.html` (NEW, extracted from `pages/catalogs.html`) / `history_rows.html` (filter-row migration from `.filter-bar`) | component | request-response | `partials/product_rows.html` (filter-row + rows-wrapper-div shape); `partials/history_filters.html` (select-filter shape) | role-match / exact |

## Pattern Assignments

### `app/services/pagination.py` (NEW module)

**No direct analog** — RESEARCH.md already specifies the exact code (Pattern 1). Cite `app/services/warehouses.py:91-97`'s `func.count().select_from(...)` shape as the precedent for the SQL-side total-count queries that call sites (dictionary, history) will pair with this module's `page_window()`.

```python
LIST_PAGE_SIZE = 20

def page_window(page: int, total_pages: int, spread: int = 2) -> list[int | str]:
    """0-based page indices to render, with '…' markers for gaps."""
    ...

def paginate(rows: list, page: int) -> tuple[list, int, int]:
    """Python-side slice for small lists; clamps page into [0, total_pages-1]."""
    ...
```

---

### `app/services/operations.py` — `history_view` (extend in place)

**Analog:** itself, lines 14-53.

**Current offset pattern to extend** (lines 33-53):
```python
stmt = (
    select(Operation, Product, Batch)
    .join(Product, Operation.product_id == Product.id)
    .outerjoin(Batch, Operation.batch_id == Batch.id)
    .order_by(Operation.created_at.desc(), Operation.seq.desc())
)
if type_filter and type_filter in OPERATION_TYPES:
    stmt = stmt.where(Operation.type == type_filter)
if product_id:
    stmt = stmt.where(Operation.product_id == product_id)
stmt = stmt.limit(page_size + 1).offset(page * page_size)
```
**Change:** replace `page_size + 1`/`has_next` sentinel with a real `func.count()` query using the SAME `.where()` filters (mirrors `app/services/warehouses.py:91-97`), default `page_size` 50 → `LIST_PAGE_SIZE` (20, from `app/services/pagination.py`), add a `sort` param mapped through an allow-list dict (Pattern 2 below) — default stays `created_at desc, seq desc` per D-07.

**Allow-list filter pattern to reuse everywhere** (line 39, `app/services/operations.py`):
```python
if type_filter and type_filter in OPERATION_TYPES:
    stmt = stmt.where(Operation.type == type_filter)
```

---

### `app/services/warehouses.py` — `list_warehouses` (filter/sort/page) + `soft_delete_warehouse` (new stock guard)

**Analog:** itself, lines 19-27 and 76-102.

**Current Python-side sort pattern to extend** (lines 19-27):
```python
def list_warehouses(session: Session) -> list[Warehouse]:
    rows = list(session.scalars(select(Warehouse)))
    return sorted(rows, key=lambda w: (w.deleted_at is not None, w.name))
```
Add `name`/`address` substring filters (Python `.lower()` — small cardinality, no `_lc` needed per RESEARCH.md A1) and a `sort` param allow-list before calling `app/services/pagination.py:paginate()`.

**Existing guard pattern to extend (D-11/D-12 — stock guard runs FIRST, non-overridable)** (lines 76-102):
```python
def soft_delete_warehouse(
    session: Session, warehouse_id: str, *, confirm: bool = False
) -> tuple[bool, dict]:
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None or warehouse.deleted_at is not None:
        return False, {}

    if not confirm:
        active_count = session.scalar(
            select(func.count())
            .select_from(Warehouse)
            .where(Warehouse.deleted_at.is_(None))
        )
        if active_count <= 1:
            return False, {"warehouse": warehouse}

    warehouse.deleted_at = utcnow_iso()
    session.commit()
    return True, {}
```
**New stock guard to insert BEFORE the `confirm` check** (per Contract E step 1 — hard block, no override), using the NEW per-warehouse stock query from RESEARCH.md (Code Examples section, no existing precedent — `Product.quantity` is a global total, not per-warehouse):
```python
from app.models import Batch

warehouse_stock = session.scalar(
    select(func.coalesce(func.sum(Batch.quantity), 0)).where(
        Batch.warehouse_id == warehouse_id
    )
)
if warehouse_stock > 0:
    return False, {"stock": warehouse_stock}
```
Return-shape convention: extend the existing `(deleted, blocked_info)` tuple — do not add a third state; a new dict key (`"stock"`) distinguishes the new guard's blocked reason from the existing `"warehouse"` key.

---

### `app/services/catalog.py` — `list_products` (filter/sort/page) + NEW `quick_delete_product`

**Analog for filter/sort:** `search_products` (lines 347-371) and `category_options` (lines 400-413) — both already do Cyrillic-safe Python-lowered filtering against `Product.name_lc`.

**Analog for the quick-delete guard shape:** `app/services/warehouses.py:76-102` (`soft_delete_warehouse`'s `(deleted, blocked_info)` tuple return) — RESEARCH.md Pitfall 4 explicitly directs a NEW function, not reuse of `soft_delete_product`.

**Existing stock-check precedent (Product.quantity is already a cached total, no query needed)** (RESEARCH.md Code Examples, `app/models.py:113-114`):
```python
if product.quantity > 0:
    return False, {"blocked_qty": product.quantity}
```

**New function skeleton, mirroring `soft_delete_product` (lines 295-301) + the warehouse guard tuple shape:**
```python
def quick_delete_product(session: Session, product_id: str) -> tuple[bool, dict]:
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        return False, {}
    if product.quantity > 0:
        return False, {"blocked_qty": product.quantity}
    product.deleted_at = utcnow_iso()
    session.commit()
    return True, {}
```
Leave `soft_delete_product` (lines 295-301) and `/products/{id}/delete` completely untouched (Pitfall 4).

**Existing capped-list pattern to extend for filter/sort/page** (lines 327-336):
```python
def list_products(session: Session) -> list[Product]:
    return list(
        session.scalars(
            select(Product)
            .where(Product.deleted_at.is_(None))
            .order_by(Product.name)
            .limit(20)
        )
    )
```
Add code/name/category filters (Python `.lower()` against `name_lc`, mirroring `search_products`'s `_escape_like`/`.contains(q_lc, autoescape=True)` pattern) + sort allow-list + `pagination.paginate()`. Note: this REPLACES the standalone `/products/search` route's role (Pitfall 6) — fold `search_view`'s query logic into the main list route's is_hx branch.

---

### `app/services/customers.py` — new filter/sort/page list function

**Analog:** `app/services/catalog.py:327-336` (`list_products`) for the list shape; `search_customers` (lines 119-130) for the existing Cyrillic-safe `search_lc` filtering to reuse per-field.

**Existing search pattern to split into independent per-column filters:**
```python
def search_customers(session: Session, q: str) -> list[Customer]:
    q_lc = q.strip().lower()
    stmt = select(Customer)
    if q_lc:
        stmt = stmt.where(Customer.search_lc.contains(q_lc, autoescape=True))
    stmt = stmt.order_by(Customer.search_lc).limit(20)
    return list(session.scalars(stmt))
```
Per RESEARCH.md's filterable-columns table: name/surname/consultant_number become independent Python-side `.lower()` comparisons directly on `Customer.name`/`.surname`/`.consultant_number` (no per-field shadow column needed — filtering is Python-side per A1). Retire `/customers/search` (Pitfall 6), fold into the main list route.

---

### `app/services/dictionary.py` — `list_entries` (SQL LIMIT/OFFSET + COUNT + filter/sort)

**Analog:** `app/services/operations.py:14-53` (`history_view`) — the ONLY existing SQL-side offset+filter+count precedent in the codebase; dictionary (6,856 rows) needs the same shape, not the Python-side pattern used by the other four lists.

**Current unbounded query to replace:**
```python
def list_entries(session: Session) -> list[Dictionary]:
    return list(session.scalars(select(Dictionary).order_by(Dictionary.code)))
```
**Target shape (copy `history_view`'s structure):** `.where()` allow-listed filters (code via `func.lower()` — ASCII-safe per A1; name via NEW `Dictionary.name_lc` shadow column, Cyrillic-unsafe `func.lower()` forbidden per Pitfall 1) + `.order_by(allow-list.get(sort, Dictionary.code))` + `.limit(LIST_PAGE_SIZE).offset(page * LIST_PAGE_SIZE)`, paired with a `func.count().select_from(Dictionary)` query using the SAME `.where()` clauses (mirrors `app/services/warehouses.py:91-97`).

**New migration companion** — `alembic/versions/0012_dictionary_name_lc.py`: add `name_lc` column (`render_as_batch=True`, existing convention), backfill in Python (NOT raw SQL `lower()`, per Pitfall 1):
```python
# Backfill step — Python loop, not op.execute("UPDATE ... lower(name)")
for row in session.execute(select(Dictionary)):
    row.name_lc = row.name.lower()
```
Also update `add_entry`/`update_entry` (lines 38-76) to set `entry.name_lc = name.lower()` going forward, mirroring `create_product`'s `name_lc=name.lower()` (`app/services/catalog.py:112`).

---

### `app/services/catalogs.py` — `list_catalogs` (year filter + sort + Python pagination)

**Analog:** `app/services/warehouses.py:19-27` (`list_warehouses`) for the Python-side sort-after-fetch shape; `list_catalogs` itself (lines 96-112) already sorts in Python.

**Current sort to extend:**
```python
catalogs.sort(key=lambda c: (c["year"], c["number"]), reverse=True)
```
Add a `year` filter (list comprehension before sort) and a `sort` param allow-list (`"oldest"` → `reverse=False`, default unchanged per D-07), then `pagination.paginate()` the flat list BEFORE any template year-grouping loop runs (Pitfall 5 — critical: paginate first, then let `loop.first`/`loop.last` in the extracted `catalog_rows.html` partial re-open/close per page, not per full list).

---

### `app/routes/products.py` — list route (filter/sort/page) + NEW quick-delete route

**Analog for filter/sort/page + is_hx dual response:** `app/routes/history.py` (`history_page`, lines 13-52).

**Analog for quick-delete route shape:** `app/routes/warehouses.py:81-97` (`warehouse_delete`) — POST handler re-rendering the rows partial, NOT `HX-Redirect`.

**Existing full-page redirect pattern to AVOID reusing for quick-delete** (lines 216-221):
```python
@router.post("/products/{product_id}/delete")
def product_delete(product_id: str, session: Session = Depends(get_session)):
    soft_delete_product(session, product_id)
    return Response(status_code=200, headers={"HX-Redirect": "/products"})
```
**New route to add** (mirrors `warehouse_delete`'s partial re-render shape instead):
```python
@router.post("/products/{product_id}/quick-delete")
def product_quick_delete(request: Request, product_id: str, session: Session = Depends(get_session)):
    _, blocked = quick_delete_product(session, product_id)
    context = {...list_view context..., "blocked_id": product_id if blocked else None, "blocked_qty": blocked.get("blocked_qty")}
    return templates.TemplateResponse(request, "partials/product_rows.html", context)
```
Leave `product_delete`/`/products/{id}/delete` (lines 216-221) untouched (Pitfall 4). Retire `/products/search` (lines 37-41) by folding `search_view`'s filter logic into `products_list`'s is_hx branch (Pitfall 6).

---

### `app/routes/warehouses.py` — extend `warehouse_delete` in place (NO new route)

**Analog:** itself, lines 81-97 — Pitfall 3 is explicit that this must NOT become a new `/warehouses/{id}/quick-delete` endpoint.

```python
@router.post("/warehouses/{warehouse_id}/delete")
def warehouse_delete(
    request: Request, warehouse_id: str, confirm: str = Form(""), session: Session = Depends(get_session),
):
    _, warning = soft_delete_warehouse(session, warehouse_id, confirm=confirm == "1")
    context = {
        "warehouses": list_warehouses(session),
        "errors": {}, "form": {},
        "warning_id": warehouse_id if warning.get("warehouse") else None,
        "stock_blocked_id": warehouse_id if warning.get("stock") else None,
        "stock_blocked_qty": warning.get("stock"),
    }
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
```
Only the context dict and `list_warehouses()`'s own filter/sort/page params change; the route signature/shape is otherwise unchanged.

---

### `app/routes/history.py` — extend `history_page` (sort param, page_size 20)

**Analog:** itself, lines 13-52. Add `sort: str = ""` query param, pass through to `history_view`; `history_load_more.html`/`history_response.html` responses get replaced by the shared `partials/pagination.html` (retire the `<tfoot>` oob-swap dance entirely — Contract A explicitly retires this control).

---

## Shared Patterns

### Allow-listed filter/sort query params (apply to EVERY list service)
**Source:** `app/services/operations.py:39`
```python
if type_filter and type_filter in OPERATION_TYPES:
    stmt = stmt.where(Operation.type == type_filter)
```
**Apply to:** every new `.where()` filter clause in `catalog.py`, `warehouses.py`, `customers.py`, `dictionary.py`, `catalogs.py` and every `sort` param — resolve through a fixed dict, never string-interpolate into `order_by()`.

### Total-count query paired with a filtered page query
**Source:** `app/services/warehouses.py:91-97`
```python
active_count = session.scalar(
    select(func.count())
    .select_from(Warehouse)
    .where(Warehouse.deleted_at.is_(None))
)
```
**Apply to:** `history_view` (D-02) and `dictionary.list_entries` — the SQL-side lists; use the SAME `.where()` clauses as the row query so total matches the filtered set, not the whole table.

### Cyrillic-safe lowercase filtering
**Source:** `app/services/catalog.py:355` (`search_products`) — `q_lc = q.strip().lower()` compared against `Product.name_lc`, never SQL `lower()`.
**Apply to:** all text filters on Cyrillic columns (product name/category, customer name/surname, dictionary name). Code/consultant_number columns (ASCII) may use `func.lower()` safely (as `search_products` does for `Product.code`).

### Debounced HTMX filter input
**Source:** UI-SPEC Contract B (mirrors the existing `/products/search` input, not directly read this session but referenced by `14-CONTEXT.md`'s D-05) and `app/templates/partials/history_filters.html:8-11` for the `hx-include`/`hx-target`/`hx-push-url` combo:
```html
<select hx-get="/history" hx-trigger="change" hx-include="[name='product']"
        hx-target="#history-tbody" hx-push-url="true">
```
**Apply to:** every new per-column filter input/select — text inputs use `hx-trigger="input changed delay:300ms"`, selects use `hx-trigger="change"`, all use `hx-include="closest table"` to combine with sort/pagination state (Contract B).

### Browser-native `hx-confirm` before a destructive POST
**Source:** `app/templates/partials/warehouse_rows.html:41-45`
```html
<button type="button" class="danger"
        hx-post="/warehouses/{{ w.id }}/delete"
        hx-confirm="Удалить склад «{{ w.name }}»? Он будет скрыт из списка выбора, история операций сохранится."
        hx-target="#warehouse-rows" hx-swap="outerHTML">Удалить</button>
```
**Apply to:** the new product quick-delete button (Contract D) — same shape, exact confirm copy from `product_form.html` reused verbatim per UI-SPEC.

### Guard tuple return shape `(success: bool, info: dict)`
**Source:** `app/services/warehouses.py:76-102` (`soft_delete_warehouse`)
**Apply to:** `quick_delete_product` (NEW) and the extended `soft_delete_warehouse` — a blocked-reason dict key (`"warehouse"` for last-active, `"stock"` for the new stock guard, `"blocked_qty"` for product) lets the route/template distinguish which error message to render, without adding new return states.

## No Analog Found

None — every file has at least a role-match analog; the SQL-vs-Python pagination split (dictionary/history vs. products/warehouses/customers/catalogs) is itself grounded directly in RESEARCH.md's live row-count finding, not a guess.

## Metadata

**Analog search scope:** `app/services/*.py`, `app/routes/*.py`, `app/templates/partials/*.html`, `app/templates/pages/*.html`, `alembic/versions/`
**Files scanned:** `operations.py`, `warehouses.py`, `catalog.py`, `customers.py`, `dictionary.py`, `catalogs.py`, `products.py` (route), `warehouses.py` (route), `history.py` (route), `product_rows.html`, `warehouse_rows.html`, `history_response.html`, `history_load_more.html`, `history_filters.html`, `14-UI-SPEC.md` (Contracts A-E)
**Pattern extraction date:** 2026-07-14
