# Phase 20: Warehouses & Batch-Split Transfers - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 12
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `app/services/warehouses.py::list_warehouses` (extend) | service | CRUD + aggregate-query | `app/services/reports.py::stale_products` (aggregate shape) + `app/services/batches.py::batches_for_products` (page-wide `IN(...)` shape) | role-match (aggregate pattern), exact-file (same service) |
| `app/routes/warehouses.py` (restructure: add `/new`, `/{id}/edit` GET routes) | route | request-response | `app/routes/products.py` (`product_new`, `product_edit`, `product_create`, `product_update`) | exact |
| `app/templates/pages/warehouse_form.html` (NEW) | component (template) | request-response | `app/templates/pages/product_form.html` | exact (dedicated add/edit page shape) |
| `app/templates/partials/warehouse_rows.html` (simplify to picker, keep filter/sort/status bar) | component (template) | request-response | itself (current file) — no external analog needed, in-place edit | exact (self-analog) |
| `app/services/transfers.py::register_transfer` (extend: override params, D-06 same-warehouse validation) | service | CRUD (ledger write) | itself (current file) — `dest = Batch(...)` extension point | exact (self-analog) |
| `app/routes/transfers.py` (`transfers_create`, `_dest_warehouses`, ownership guard) | route | request-response | itself (current file) + `app/routes/writeoffs.py::writeoff_batch_pick` (ownership-check pattern for D-10) | exact (self) / role-match (ownership pattern) |
| `app/routes/mobile_transfers.py` (`_dest_warehouses`, `transfers_create`, step/dest) | route | request-response (wizard) | itself (current file) — mirrors desktop `transfers.py` | exact (self-analog, must mirror desktop changes) |
| `app/routes/writeoffs.py::writeoff_create` (D-10 ownership guard port only) | route | request-response | `app/routes/transfers.py::transfers_batch_pick` (ownership-check pattern, lines 93-96) | exact (pattern already proven in same file's own GET endpoint) |
| `app/templates/partials/transfer_form.html` (add override fields) | component (template) | request-response | itself (current file) | exact (self-analog) |
| `app/templates/partials/transfer_batch_wrap.html` (dest select gains source warehouse) | component (template) | request-response | itself (current file) | exact (self-analog) |
| `app/templates/mobile_partials/transfers_step_dest.html` (add override fields, mobile parity) | component (template) | request-response | `app/templates/partials/transfer_form.html` (desktop override fields, once added) | role-match |
| `tests/test_warehouses.py` (rewrite web-slice `test_web_*`) | test | request-response | itself (current file) — structural rewrite, not net-new pattern | exact (self-analog) |
| `tests/test_transfers.py` (rewrite `test_reject_same_warehouse`, add override/ownership/qty-echo tests) | test | request-response | itself (current file) | exact (self-analog) |

## Pattern Assignments

### `app/services/warehouses.py::list_warehouses` (service, aggregate query extension for WH-01)

**Analog:** `app/services/reports.py::stale_products` (lines 170-192) and `app/services/batches.py::batches_for_products` (lines 37-53)

**Grouped outerjoin + func.max pattern** (`app/services/reports.py:182-191`):
```python
last_sale = func.max(Operation.created_at).label("last_sale")
stmt = (
    select(Product, last_sale)
    .outerjoin(
        Operation,
        (Operation.product_id == Product.id) & (Operation.type == "sale"),
    )
    .where(Product.deleted_at.is_(None))
    .group_by(Product.id)
)
rows = session.execute(stmt).all()
```
D-04's analogous shape for last-receipt-date per warehouse (from RESEARCH.md, verified structurally sound against this analog):
```python
last_receipt = func.max(Operation.created_at).label("last_receipt")
stmt = (
    select(Batch.warehouse_id, last_receipt)
    .outerjoin(
        Operation,
        (Operation.batch_id == Batch.id) & (Operation.type == "receipt"),
    )
    .where(Batch.warehouse_id.in_(warehouse_ids))
    .group_by(Batch.warehouse_id)
)
```
Use `outerjoin` (not `.join()`) — a warehouse/product with zero matching operations must still appear with `None`, never silently drop from the result set.

**Page-wide `IN(...)` + Python grouping pattern** (`app/services/batches.py:37-53`):
```python
def batches_for_products(session: Session, product_ids: list[str]) -> dict[str, list[Batch]]:
    if not product_ids:
        return {}
    rows = session.scalars(
        select(Batch)
        .where(Batch.product_id.in_(product_ids), Batch.quantity > 0)
        .order_by(nullslast(Batch.expiry.asc()), Batch.created_at.asc())
    )
    grouped: dict[str, list[Batch]] = defaultdict(list)
    for batch in rows:
        grouped[batch.product_id].append(batch)
    return dict(grouped)
```
D-03/D-04: item-count and last-receipt-date must both be computed as ONE query scoped to `.in_(warehouse_ids)` for the current page, never a per-row loop query inside `list_warehouses`' existing `session.scalars(select(Warehouse))` loop (`app/services/warehouses.py:43`).

**Item count query (D-03, distinct products with quantity > 0)** — same grouped shape:
```python
item_count = func.count(func.distinct(Batch.product_id)).label("item_count")
stmt = (
    select(Batch.warehouse_id, item_count)
    .where(Batch.warehouse_id.in_(warehouse_ids), Batch.quantity > 0)
    .group_by(Batch.warehouse_id)
)
```

**Existing `list_warehouses` return-dict convention to extend** (`app/services/warehouses.py:66-76`):
```python
page_rows, total, total_pages = paginate(rows, page)
return {
    "warehouses": page_rows,
    "total": total,
    "total_pages": total_pages,
    "page": page,
    "name": result["name"],
    ...
}
```
Add `item_count`/`last_receipt` as a dict merged onto each `Warehouse` row (or a parallel dict keyed by warehouse id) after computing the grouped queries for the page's warehouse ids — do not restructure the existing filter/sort/paginate logic (lines 43-66), only append the new metrics after `paginate()`.

---

### `app/routes/warehouses.py` (route, restructure for WH-02 D-01/D-02)

**Analog:** `app/routes/products.py` — `product_new` (lines 174-203), `product_edit` (lines 261-277)

**Dedicated add-page GET route pattern** (`app/routes/products.py:174-203`):
```python
@router.get("/products/new")
def product_new(request: Request, code: str = "", session: Session = Depends(get_session)):
    context = {"product": None, "categories": category_options(session), "errors": {}, "form": ...}
    return templates.TemplateResponse(request, "pages/product_form.html", context)
```

**Dedicated edit-page GET route pattern** (`app/routes/products.py:261-277`):
```python
@router.get("/products/{product_id}/edit")
def product_edit(request: Request, product_id: str, session: Session = Depends(get_session)):
    product = get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    context = {"product": product, "categories": category_options(session), "errors": {}, ...}
    return templates.TemplateResponse(request, "pages/product_form.html", context)
```

D-01 requires `GET /warehouses/new` and `GET /warehouses/{id}/edit` to follow this exact shape. IMPORTANT deviation from the analog: `update_warehouse` only returns `WAREHOUSE_NOT_FOUND_ERROR` on the POST path today (`app/services/warehouses.py:100-102`) — the new `GET /warehouses/{id}/edit` route needs its OWN fresh `session.get(Warehouse, warehouse_id)` lookup + explicit `if warehouse is None: raise HTTPException(status_code=404, ...)`, mirroring `product_edit`'s own lookup rather than reusing `update_warehouse`.

**Existing context-builder convention to preserve** (`app/routes/warehouses.py:37-89`, `_warehouses_context`) — this function must keep computing `list_name`/`list_address`/`list_status`/`list_sort`/`list_page` echo state; the new edit-page delete action must still pass these through so the operator returns to the same filtered/sorted list view they came from (same convention already used by `warehouse_update`/`warehouse_delete`, lines 132-203).

**Existing delete/warn-then-confirm route to relocate rendering for (D-02)** (`app/routes/warehouses.py:172-203`):
```python
@router.post("/warehouses/{warehouse_id}/delete")
def warehouse_delete(request: Request, warehouse_id: str, confirm: str = Form(""), ...):
    _, warning = soft_delete_warehouse(session, warehouse_id, confirm=confirm == "1")
    context = _warehouses_context(session, ..., warning_id=..., stock_blocked_id=..., stock_blocked_qty=...)
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
```
`soft_delete_warehouse`'s guard logic (`app/services/warehouses.py:125-164`) stays untouched — only the response template target changes from `partials/warehouse_rows.html` to a warehouse-edit-page partial/context per D-02.

---

### `app/templates/pages/warehouse_form.html` (NEW, component/template, WH-02)

**Analog:** `app/templates/pages/product_form.html` (lines 1-60 read)

**Add/edit page structural pattern**:
```jinja
{% extends "base.html" %}
{% block content %}
{% if product %}
<h1>Редактирование товара</h1>
{% else %}
<h1>Новый товар</h1>
{% endif %}
...
<form method="post" action="{% if product %}/products/{{ product.id }}{% else %}/products{% endif %}" class="stacked-form">
  <div class="field">
    <label for="code">Код</label>
    <input ... value="{% if form %}{{ form.code or '' }}{% elif product %}{{ product.code or '' }}{% endif %}" required autofocus>
    {% if errors.code %}<p class="error">{{ errors.code }}</p>{% endif %}
  </div>
  ...
</form>
{% endblock %}
```
`warehouse_form.html` should follow this exact shape (single `{% if warehouse %}`/else branch, `form`-or-`warehouse` value fallback per field, `errors.<field>` inline). Per D-02/Pitfall notes in CONTEXT.md, the delete button + warn-then-confirm/stock-blocked states (currently rendered in `warehouse_rows.html` lines 100-128) must be relocated onto this page, not copied from Products (Products' delete has no warn state — see "Delete-with-redirect" note below, do NOT use it for warehouses).

**Delete pattern NOT to copy verbatim** (Products' simple one-shot delete, `app/routes/products.py:338-343`, referenced for contrast):
```python
@router.post("/products/{product_id}/delete")
def product_delete(product_id: str, session: Session = Depends(get_session)):
    soft_delete_product(session, product_id)
    return Response(status_code=200, headers={"HX-Redirect": "/products"})
```
Warehouses' delete has two warn states (stock-blocked, last-active-warn) that must remain visible/interactive on `warehouse_form.html` — do not reduce to a blind `HX-Redirect`.

---

### `app/services/transfers.py::register_transfer` (service, XFER-01 D-05/D-06/D-07)

**Analog:** itself — the file's own existing `dest = Batch(...)` extension point and `price_cents` inheritance convention

**Current same-warehouse guard to relax (D-05/D-06)** (`app/services/transfers.py:83-90`):
```python
dest_warehouse_id = dest_warehouse_id.strip()
active_ids = {w.id for w in active_warehouses(session)}
if dest_warehouse_id not in active_ids:
    return None, {"warehouse": WAREHOUSE_ERROR}
if dest_warehouse_id == source.warehouse_id:
    return None, {"warehouse": SAME_WAREHOUSE_ERROR}
```
D-06 replaces the last unconditional check with a conditional one (must stay at THIS position, before the oversell check at line 95, per Pitfall 4): if `dest_warehouse_id == source.warehouse_id` AND both override fields are blank, return a new blocking error immediately; otherwise proceed.

**Current dest construction, the extension point** (`app/services/transfers.py:113-124`):
```python
dest = Batch(
    id=new_id(),
    product_id=product.id,
    warehouse_id=dest_warehouse_id,
    name=source.name,
    expiry=source.expiry,
    price_cents=source.price_cents,
    location=source.location,
    comment=source.comment,
    quantity=0,
    is_legacy=0,
)
session.add(dest)
```
Direct-assignment discipline (never bare `or`) — required change shape for D-07:
```python
new_expiry_clean = new_expiry.strip() if new_expiry else ""
new_comment_clean = new_comment.strip() if new_comment else ""
dest = Batch(
    ...,
    expiry=new_expiry_clean if new_expiry_clean else source.expiry,
    comment=new_comment_clean if new_comment_clean else source.comment,
    ...,
)
```
This mirrors the file's own `price_cents=source.price_cents` unconditional-inherit convention (the file's docstring, lines 1-12, calls this out explicitly).

**Existing qty validation discipline to reuse for any new string fields** (`app/services/transfers.py:59-64`):
```python
qty_text = qty_raw.strip()
qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
if qty <= 0:
    errors["quantity"] = QTY_ERROR
```
Apply the same `.strip()`-then-check discipline to the new `new_expiry`/`new_comment` params (plain string handling, no new validation library, per RESEARCH.md's V5 note).

**D-11 return-dict change** — current success return (`app/services/transfers.py:149`):
```python
return {"product": product, "source": source, "dest": dest}, {}
```
Needs the actual transferred integer added so `transfers_create`'s echo can use it instead of the raw form string (D-11):
```python
return {"product": product, "source": source, "dest": dest, "qty": qty}, {}
```

---

### `app/routes/transfers.py` (route, D-05..D-11)

**Analog:** itself (existing `_dest_warehouses`, `transfers_create`) + `app/routes/writeoffs.py::writeoff_batch_pick` (D-10 ownership pattern)

**Current `_dest_warehouses` filter to remove (D-09)** (`app/routes/transfers.py:26-30`):
```python
def _dest_warehouses(session: Session, source: Batch | None) -> list:
    """Active warehouses minus the source batch's own warehouse (D-02)."""
    if source is None:
        return []
    return [w for w in active_warehouses(session) if w.id != source.warehouse_id]
```
D-09 removes the `if w.id != source.warehouse_id` exclusion so the source warehouse becomes selectable again:
```python
def _dest_warehouses(session: Session, source: Batch | None) -> list:
    if source is None:
        return []
    return list(active_warehouses(session))
```

**Ownership-check pattern to PORT into `transfers_create` (D-10)** — the CORRECT existing pattern, proven in `transfers_batch_pick` (`app/routes/transfers.py:92-96`) and identically in `writeoffs.py::writeoff_batch_pick` (lines 84-88):
```python
picked: Batch | None = None
if batch_id and product is not None:
    candidate = session.get(Batch, batch_id)
    if candidate is not None and candidate.product_id == product.id:
        picked = candidate
```
**Current buggy pattern to fix (D-10 target)** — `transfers_create` at `app/routes/transfers.py:130` (and `writeoffs.py::writeoff_create` at line 123, identical bug):
```python
selected_batch = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
```
This has NO ownership/product-match check — must gain the same guard as `transfers_batch_pick` above, resolving `product` first (via the same `select(Product).where(Product.code == code_clean, ...)` lookup already used earlier in the same handler family) before trusting `batch_id`.

**D-11 qty-echo fix target** (`app/routes/transfers.py:187-195`):
```python
context = {
    "errors": {},
    "form": {},
    "saved": {"name": result["product"].name, "qty": qty},  # BUG: raw form string
    "focus_code": True,
    "transfers": recent_transfers(session),
    "include_oob_rows": True,
}
```
Change `"qty": qty` to `"qty": result["qty"]` (the parsed integer added to `register_transfer`'s return dict per D-11 above) — mirrors `writeoffs.py`'s already-correct pattern of computing the real qty from the service result rather than echoing the raw form string.

---

### `app/routes/mobile_transfers.py` (route, mobile parity — Pitfall 3)

**Analog:** itself — must mirror every desktop `transfers.py` change

Confirmed identical `register_transfer(...)` call signature at lines 199-207, and its OWN duplicate `_dest_warehouses` at lines 36-40 (byte-identical logic to desktop's pre-D-09 version):
```python
def _dest_warehouses(session: Session, source: Batch | None) -> list[Warehouse]:
    """Active warehouses minus the source batch's own warehouse (D-02, mirrors desktop)."""
    if source is None:
        return []
    return [w for w in active_warehouses(session) if w.id != source.warehouse_id]
```
Apply the SAME D-09 filter removal here. `transfers_create` (mobile, lines 184-258) and `_render_dest_step` (lines 86-115) need the same two new override `Form(...)` params threaded through, plus D-11's qty-echo fix in the `saved={"name": result["product"].name, "qty": qty}` dict at line 257 (same bug pattern as desktop, confirm/fix during implementation even though RESEARCH.md scoped D-11 to desktop `transfers.py` only — verify D-11's stale-scoping note against mobile's own `saved` dict before assuming it's clean).

Mobile's `_pick_batch` (lines 74-83) ALREADY has the correct ownership-check pattern — do NOT touch it; it is the reference other files copy FROM, not a D-10 target.

---

### `app/routes/writeoffs.py::writeoff_create` (route, D-10 port target only)

**Analog:** `app/routes/transfers.py::transfers_batch_pick` (lines 93-96) — same ownership-check pattern, and `writeoff_batch_pick` in the SAME file (lines 84-88) already has it correctly for its own GET endpoint.

**Bug to fix** (`app/routes/writeoffs.py:123`):
```python
selected_batch = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
```
Port the same 4-line ownership guard from `writeoff_batch_pick` (same file, lines 84-88) into `writeoff_create`. D-11 (qty echo) does NOT apply here — `writeoffs.py` already computes the real parsed quantity from `operation.qty_delta` for its success echo (per D-11's note, this file is correct today).

---

## Shared Patterns

### Ownership-check-before-echo (D-10)
**Source:** `app/routes/transfers.py::transfers_batch_pick` (lines 92-96), duplicated identically in `app/routes/writeoffs.py::writeoff_batch_pick` (lines 84-88) and `app/routes/mobile_transfers.py::_pick_batch` (lines 74-83, already correct).
**Apply to:** `transfers_create` (`app/routes/transfers.py:130`) and `writeoff_create` (`app/routes/writeoffs.py:123`) — both currently missing this guard on their POST create handlers.
```python
picked: Batch | None = None
if batch_id and product is not None:
    candidate = session.get(Batch, batch_id)
    if candidate is not None and candidate.product_id == product.id:
        picked = candidate
```

### Grouped page-wide aggregate query (never per-row loop)
**Source:** `app/services/reports.py::stale_products` (outerjoin + func.max + group_by) and `app/services/batches.py::batches_for_products` (`.in_()` + Python `defaultdict` grouping).
**Apply to:** `app/services/warehouses.py::list_warehouses`'s new item-count/last-receipt-date metrics (D-03/D-04) — must be ONE query scoped to `.in_(warehouse_ids)` for the page, not inserted into the existing `for w in rows` filter/sort loop.

### Direct-assignment-never-bare-`or` for override fields
**Source:** `app/services/transfers.py`'s existing `price_cents=source.price_cents` convention (file docstring, lines 1-12) and `dest = Batch(...)` construction (lines 113-124).
**Apply to:** the new `expiry`/`comment` override params in `register_transfer` (D-07) — explicit `.strip()`-then-ternary, never `new_expiry or source.expiry`.

### Dedicated add/edit page GET routes (mirrors Products)
**Source:** `app/routes/products.py::product_new` (174-203), `product_edit` (261-277); `app/templates/pages/product_form.html`.
**Apply to:** new `app/routes/warehouses.py::warehouse_new` / `warehouse_edit` GET routes and `app/templates/pages/warehouse_form.html` (D-01).

### List filter/sort/status query-param echo (must survive D-01 restructure)
**Source:** `app/routes/warehouses.py::_warehouses_context` (lines 37-89) — existing `list_name`/`list_address`/`list_status`/`list_sort`/`list_page` echo convention already used by `warehouse_update`/`warehouse_delete`.
**Apply to:** the edit-page delete action's redirect/context so the operator returns to the same filtered list view (Pitfall 1's warning).

## No Analog Found

None — every file in scope either has a direct cross-domain analog (Products for warehouse forms, reports/batches for aggregate queries, writeoffs/transfers for ownership checks) or is a self-extension of its own existing code (transfers.py, mobile_transfers.py). No net-new architectural pattern is introduced by this phase (confirmed by RESEARCH.md's own "no new mechanism design" conclusion).

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/pages/`, `app/templates/partials/`, `app/templates/mobile_partials/`
**Files scanned:** `app/services/warehouses.py`, `app/routes/warehouses.py`, `app/services/transfers.py`, `app/routes/transfers.py`, `app/routes/mobile_transfers.py`, `app/routes/writeoffs.py` (partial), `app/routes/products.py` (partial), `app/services/reports.py` (partial), `app/services/batches.py`, `app/templates/pages/product_form.html` (partial)
**Pattern extraction date:** 2026-07-16
