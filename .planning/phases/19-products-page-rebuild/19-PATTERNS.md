# Phase 19: Products Page Rebuild - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 4 (2 modified templates, 1 modified route, 1 new service function; 1 CSS addition)
**Analogs found:** 4 / 4 (all analogs are files this phase itself sits beside — this is a targeted rebuild of existing files, not new-file scaffolding)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `app/services/batches.py::batches_for_products` (NEW function in existing file) | service | CRUD (batched read) | `app/services/reports.py::stale_products` (grouped/joined query over a page of parents) + `app/services/batches.py::open_batches` (ordering to mirror) | exact (ordering) + role-match (batching shape) |
| `app/routes/products.py::_products_context` (MODIFIED) | controller/route | request-response | itself (existing function, same file) — extend, don't replace | exact |
| `app/templates/partials/product_rows.html` (MODIFIED) | component (Jinja partial) | request-response (SSR) | itself (existing file) — extend rows with quantity column + `<details>` batch block + `<a class="link-danger">` | exact |
| `app/templates/pages/products_list.html` (MODIFIED) | component (Jinja page) | request-response (SSR) | itself — delete one `<p class="page-actions">` line | exact |
| `app/static/style.css` (MODIFIED, additive) | config/style | — | existing `button.danger` (lines 194-197) and `.batch-picker` (lines 278-280) rules — new `.link-danger` rule follows the same file convention (named color token, one-line comment) | role-match |

## Pattern Assignments

### `app/services/batches.py` — add `batches_for_products(session, product_ids)`

**Analog 1 (ordering to mirror exactly):** `app/services/batches.py::open_batches`, lines 15-32 (already in this file — read in full above).

```python
def open_batches(
    session: Session, product_id: str, warehouse_id: str | None = None
) -> list[Batch]:
    stmt = select(Batch).where(Batch.product_id == product_id, Batch.quantity > 0)
    if warehouse_id is not None:
        stmt = stmt.where(Batch.warehouse_id == warehouse_id)
    return list(
        session.scalars(
            stmt.order_by(nullslast(Batch.expiry.asc()), Batch.created_at.asc())
        )
    )
```
Reuse: `nullslast(Batch.expiry.asc())` then `Batch.created_at.asc()` — same tuple, same portability comment style (module docstring at lines 1-7 already establishes "read-only, session-first" framing; new function should get a similar one-paragraph docstring).

**Analog 2 (grouped-query-over-a-page-of-parents shape):** `app/services/reports.py::stale_products`, lines 170-194.
```python
stmt = (
    select(Product, last_sale)
    .outerjoin(Operation, (Operation.product_id == Product.id) & (Operation.type == "sale"))
    .where(Product.deleted_at.is_(None))
    .group_by(Product.id)
)
rows = session.execute(stmt).all()
```
Established house precedent: one query over the whole result set, grouped/joined in SQL or in Python — never per-row. `batches_for_products` should follow the `IN (...)` + Python `defaultdict` grouping variant, exactly as already drafted in RESEARCH.md's Pattern 1 (already reviewed against both analogs above and is consistent with both):
```python
from collections import defaultdict
from sqlalchemy import nullslast, select

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
**Imports:** `nullslast, select` already imported at top of `batches.py` line 9; `defaultdict` needs a new `from collections import defaultdict` import.

**Error handling:** none needed — read-only query, empty list guarded explicitly (`if not product_ids: return {}`), matching `open_batches`'s defensive style (no try/except anywhere in this file; SQLAlchemy exceptions are allowed to propagate, consistent with the rest of the module).

---

### `app/routes/products.py::_products_context` (lines 35-78, already read in full)

**Analog:** itself. Current imports (lines 14-24) already pull from `app.services.catalog`; add `batches_for_products` to the `app.services.batches` import (there is currently no import from `app.services.batches` in this file — will be a new import line).

**Core pattern to extend (lines 48-78):**
```python
result = list_products_view(
    session, code=code, name=name, category=category, sort=sort, page=page
)
...
return {
    "rows": result["rows"],
    ...
}
```
Insert after `list_products_view(...)` call: collect `[p.id for p in result["rows"]]`, call `batches_for_products(session, ids)`, add `"batches_by_id": ...` to the returned dict. Keep every existing key unchanged (success criterion 5 — filter/sort/pagination contract must not move).

---

### `app/templates/partials/product_rows.html` (full file already read, 87 lines)

**Analog:** itself — this is the file being extended, not replaced.

**Header column pattern (lines 24-31) — add a `Кол-во` `<th>` between Категория and Закупочная:**
```jinja
<th>Код</th>
<th>Название</th>
<th>Категория</th>
<th class="num">Закупочная</th>
<th class="num">Продажа</th>
<th>Действия</th>
```
Filter row (lines 32-48) has one `<th></th>` per data column with no filter control for Закупочная/Продажа/Действия already — the new quantity column gets the same empty `<th></th>` (no filter control), keeping Pitfall 1's "zero new `<input>`/`<select>` beyond what's needed" constraint.

**Row pattern (lines 51-65) — insert quantity `<td>` and swap the delete `<button>` for `<a class="link-danger">`:**
```jinja
<tr>
  <td>{{ product.code }}</td>
  <td>{{ product.name }}</td>
  <td>{% if product.category %}{{ product.category }}{% else %}<span class="muted">—</span>{% endif %}</td>
  <td class="num">{% if product.cost_cents is not none %}{{ product.cost_cents | cents }}{% else %}<span class="muted">—</span>{% endif %}</td>
  <td class="num">{% if product.sale_cents is not none %}{{ product.sale_cents | cents }}{% else %}<span class="muted">—</span>{% endif %}</td>
  <td>
    <a href="/products/{{ product.id }}/edit">Изменить</a>
    <button type="button" class="danger"
            hx-post="/products/{{ product.id }}/quick-delete?page={{ page }}{{ extra_qs }}"
            hx-confirm="Удалить товар „{{ product.name }}“? Он будет скрыт из каталога и поиска, история операций сохранится."
            hx-target="#product-rows" hx-swap="outerHTML">Удалить</button>
  </td>
</tr>
```
- Insert `<td class="num">{{ product.quantity }}</td>` after the category cell — `product.quantity` needs no `is not none` guard (it's an `Integer` cached column, never NULL, per RESEARCH D-09).
- Replace the `<button type="button" class="danger" ...>Удалить</button>` with `<a href="#" class="link-danger" hx-post=... hx-confirm=... hx-target="#product-rows" hx-swap="outerHTML">Удалить</a>` — copy the three `hx-*` attributes and `hx-confirm` text **verbatim**, only the tag and class change (Pitfall 2: `href="#"`, never a real delete URL; keep default underline, no `text-decoration:none`).

**Blocked-delete row `colspan` (line 68):** currently `colspan="6"` — must become `colspan="7"` once the quantity column is added (6 existing columns + 1 new = 7). Same for the new batch-breakout row's `colspan`.

**Conditional sibling-`<tr>` pattern to copy (lines 66-70) — this is the direct in-repo precedent for "a conditional extra `<tr>` under a product row":**
```jinja
{% if blocked_id == product.id %}
<tr>
  <td colspan="6"><p class="error">Нельзя удалить: на остатке {{ blocked_qty }} шт. Спишите остаток, чтобы удалить товар.</p></td>
</tr>
{% endif %}
```
The new batch `<details>` row (RESEARCH Pattern 2) follows this exact shape: `{% if product_batches %}<tr><td colspan="7">...</td></tr>{% endif %}`.

**Empty-state CTA to delete (line 83):**
```jinja
<p><a class="button" href="/products/new">Добавить товар</a></p>
```
PROD-01 removes this line from the empty-state block (lines 79-85) but the block itself (`<h2>Товаров пока нет</h2>` + muted paragraph) stays.

**Category filter (lines 41-44) — reference for Open Question 2's optional `datalist` polish, not required to change:**
```jinja
<th><input type="text" name="category" placeholder="Фильтр…" value="{{ category }}"
           hx-get="/products" hx-trigger="input changed delay:300ms"
           hx-include="#product-rows input, #product-rows select"
           hx-target="#product-rows" hx-swap="outerHTML" hx-push-url="true"></th>
```
If adding `list="cat-options"`, the analog for the `<datalist>` markup itself is `app/templates/pages/product_form.html:54-56` (not read this session — RESEARCH.md already cites it directly; confirm exact lines when implementing).

---

### `app/templates/pages/products_list.html` (full file already read, 9 lines)

**Analog:** itself.
```jinja
{% extends "base.html" %}
{% block content %}
<h1>Товары</h1>

<p class="page-actions"><a class="button" href="/products/new">Добавить товар</a></p>

{% include "partials/product_rows.html" %}
{% endblock %}
```
PROD-01: delete line 5 (`<p class="page-actions">...`) entirely. `<h1>` and the `{% include %}` stay untouched. Do **not** touch `/products/new` or `POST /products` routes — only this page's CTA link goes away.

---

### `app/static/style.css` — new `.link-danger` rule

**Analog 1 (existing destructive-button rule, lines 194-197):**
```css
button.danger {
  background: #b91c1c;
  border-color: #b91c1c;
}
```

**Analog 2 (existing nested-table CSS convention with a one-line disclaiming comment, lines 278-280):**
```css
/* Batch picker (Phase 9): nested batch table under a form field / basket line. */
.batch-picker { margin: 8px 0 0; }                         /* sm gap instead of the default table margin-top */
.batch-picker tr.selected-batch td { background: #e8effd; } /* selection highlight — existing mark/search tint, NOT a new color */
```

**New rule to add (RESEARCH.md Pattern 3, already vetted against WCAG 1.4.1 — file convention of naming the reused token and disclaiming "no new role" is followed):**
```css
/* Text-link delete action (Phase 19, PROD-02): reuses the destructive token
   (#b91c1c) already named in the file header — no new color role. Keeps the
   browser's default underline (no text-decoration:none) so the link reads
   as interactive by shape, not color alone (WCAG 1.4.1). */
a.link-danger {
  color: #b91c1c;
}
a.link-danger:hover {
  color: #7f1414;
}
```
The `.batch-picker` class is reused as-is (no new CSS needed) for the batch-breakout `<table class="batch-picker">` inside the new `<details>` block — the existing `margin: 8px 0 0` rule applies cleanly; the `.selected-batch` highlight rule is inert here since no `<input type="radio">` selection exists in this read-only context.

---

## Shared Patterns

### Batch field null-guarding (Pitfall 4)
**Source:** `app/templates/partials/product_rows.html` itself — the exact guard idiom already used for `product.category`/`product.cost_cents`/`product.sale_cents` (lines 55-57):
```jinja
{% if product.category %}{{ product.category }}{% else %}<span class="muted">—</span>{% endif %}
```
**Apply to:** every field rendered inside the new batch-breakout table — `b.expiry`, `b.name` — must use the identical `{% if %}...{% else %}<span class="muted">—</span>{% endif %}` shape (legacy batches have `name`/`expiry` = NULL).

### htmx swap-target hygiene (Pitfall 1)
**Source:** `app/templates/partials/product_rows.html` lines 10-13, 33-44 — every filter/sort control uses `hx-include="#product-rows input, #product-rows select"`.
**Apply to:** the new `<details>`/batch table and the new `<a class="link-danger">` — neither may introduce an `<input>` or `<select>` anywhere inside `#product-rows`, or it gets silently swept into every subsequent filter/sort/pagination request.

### Money display filter
**Source:** `app/templates/partials/product_rows.html` lines 56-57 — `{{ product.cost_cents | cents }}` — the existing `cents` Jinja filter (already registered; not re-derived).
**Apply to:** none new in this phase — batches don't need money display (only expiry/name/quantity per PROD-04), but if `price_cents` were ever surfaced in the batch table it must go through the same filter, never raw division/formatting.

### Route/service/template layering (D-18)
**Source:** `app/routes/products.py` line 1 docstring — `"""Product catalog pages (D-18): thin routes, all writes in app/services/catalog.py."""`
**Apply to:** `batches_for_products` belongs in `app/services/batches.py` (read-only query layer), not inlined into the route — matches this file's own stated convention and `batches.py`'s own docstring ("Read-only, session-first... mirroring the warehouses service shape").

## No Analog Found

None. Every file in scope is a modification of an existing file with a direct in-repo precedent; no wholly new file/module is introduced by this phase (confirmed by RESEARCH.md's "Recommended Project Structure" — modified files only, no new route, no new endpoint, no new package).

## Metadata

**Analog search scope:** `app/services/batches.py`, `app/services/reports.py`, `app/routes/products.py`, `app/templates/partials/product_rows.html`, `app/templates/pages/products_list.html`, `app/static/style.css` — all read in full or via targeted grep+read this session; RESEARCH.md (already the product of a full-codebase read this same day) cross-checked against live file contents for line-number drift — none found, all cited line numbers still accurate as of this session.
**Files scanned:** 6
**Pattern extraction date:** 2026-07-16
