# Phase 7: Category Browsing & Minimum Price Guardrail - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 10 (7 new, 6 modified — some files appear in both create+extend categories below; see table)
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `alembic/versions/0006_product_min_sale_price.py` (NEW) | migration | file-I/O (schema) | `alembic/versions/0005_product_thresholds.py` | exact |
| `app/models.py` (MODIFY — `Product.min_sale_cents`) | model | CRUD | same file, `low_stock_threshold`/`stale_days` columns (lines 100-103) | exact |
| `app/services/catalog.py` (MODIFY — `products_by_category()`, `_PRICE_FIELDS`, form parsing in `create_product`/`update_product`) | service | CRUD + transform | same file, `category_options()` (lines 393-406) + `_PRICE_FIELDS`/price-change block (lines 144, 208-284) | exact |
| `app/routes/categories.py` (NEW) | route | request-response | `app/routes/reports.py::reports_stock_page` (lines 153-165) | exact |
| `app/templates/pages/categories.html` (NEW) | component (page) | request-response | `app/templates/pages/reports_stock.html` | exact |
| `app/templates/base.html` (MODIFY — nav link) | component | request-response | same file, nav `<a>` list (lines 17-29) | exact |
| `app/templates/pages/product_form.html` (MODIFY — new field) | component (form) | request-response | same file, `sale`/`catalog` field blocks (lines 56-66) | exact |
| `app/services/sales.py` (MODIFY — `register_sale` price-floor block) | service | CRUD (warn-but-allow write gate) | same file, oversell block (lines 129-148) | exact |
| `app/templates/partials/sale_price_warning.html` (NEW) | component (partial) | request-response | `app/templates/partials/sale_oversell.html` | exact |
| `app/templates/partials/sale_form.html` (MODIFY — include new partial) | component (partial) | request-response | same file, `{% if oversell %}` include block (lines 15-20) | exact |
| `app/templates/partials/price_history.html` (MODIFY — new elif, if planner joins `_PRICE_FIELDS`) | component (partial) | request-response | same file, field-label elif chain (lines 19-25) | exact |
| `app/routes/products.py` (MODIFY — new Form param + context) | route | request-response | same file, `product_create`/`product_update` (lines 56-100+, `low_stock_threshold` Form param) | exact |

## Pattern Assignments

### `alembic/versions/0006_product_min_sale_price.py` (migration)

**Analog:** `alembic/versions/0005_product_thresholds.py` (full file, 47 lines)

Full pattern to mirror verbatim (revision id, down_revision, plain `op.add_column`, no batch mode, no backfill, symmetric downgrade):
```python
"""minimum sale price guardrail

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-10

D-06: adds one nullable Integer column `min_sale_cents` to `products`.
NULL means "no floor is set" — unlike low_stock_threshold/stale_days,
there is NO global-settings fallback for this field.
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("min_sale_cents", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("products", "min_sale_cents")
```
**Rules:** no `server_default`, no backfill `UPDATE` (Pitfall 3 in RESEARCH.md) — existing products get NULL automatically. Never reference application modules (WR-06 immutability rule visible in the analog's docstring).

---

### `app/models.py` — `Product.min_sale_cents` column

**Analog:** same file, `low_stock_threshold`/`stale_days` columns (lines 100-103)

```python
# Source: app/models.py lines 100-103 (verified)
    # D-04/D-05 (Phase 6): per-product report thresholds; NULL = use
    # settings.{low_stock_threshold,stale_days}.
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer)
    stale_days: Mapped[int | None] = mapped_column(Integer)
```
New column follows the identical `Mapped[int | None] = mapped_column(Integer)` shape but is placed near `sale_cents`/`catalog_cents` (line 98-99) since it is semantically a price, not a threshold — add a comment noting D-06 "no global-settings fallback" to avoid future confusion with the threshold pair immediately below it in the file.

---

### `app/services/catalog.py` — `products_by_category()` (CAT-01 query)

**Analog:** same file, `category_options()` (lines 393-406)

```python
# Source: app/services/catalog.py lines 393-406 (verified)
def category_options(session: Session) -> list[str]:
    """Distinct non-empty categories of active products, sorted (datalist)."""
    return list(
        session.scalars(
            select(Product.category)
            .where(
                Product.deleted_at.is_(None),
                Product.category.is_not(None),
                Product.category != "",
            )
            .distinct()
            .order_by(Product.category)
        )
    )
```
New function per RESEARCH.md's recommended Python-side grouping (SQL NULL-ordering trick flagged unverified — use this safer approach):
```python
def products_by_category(session: Session) -> list[dict]:
    """Active products grouped by category, alphabetical, 'Без категории' last (D-03/D-04)."""
    products = list(
        session.scalars(
            select(Product)
            .where(Product.deleted_at.is_(None))
            .order_by(Product.name_lc)
        )
    )
    by_category: dict[str, list[Product]] = {}
    for p in products:
        by_category.setdefault(p.category or "", []).append(p)
    named = sorted(k for k in by_category if k)
    groups = [{"label": k, "products": by_category[k]} for k in named]
    if "" in by_category:
        groups.append({"label": "Без категории", "products": by_category[""]})
    return groups
```
Reuses the `Product.deleted_at.is_(None)` active-filter convention identical to `list_products`/`search_products` (same file, lines 320-329, 347).

**`_PRICE_FIELDS` extension** (lines 144, 232, 258-271) — if planner joins `min_sale_cents` to the audit-trail path per Open Question #1:
```python
# Source: app/services/catalog.py line 144 (verified)
_PRICE_FIELDS = ("cost_cents", "sale_cents", "catalog_cents")
# -> add "min_sale_cents" as a fourth tuple element; the changed_prices
# diff loop (lines 232, 258-271) needs NO other change — it already
# iterates _PRICE_FIELDS generically.
```

**Form parsing** — `create_product`/`update_product` (lines 94-100, 196-202) both call `parse_optional_cents(cost_raw, errors, "cost")` etc. Add a fourth call the same way: `min_sale_cents = parse_optional_cents(min_sale_raw, errors, "min_sale")`, plus a new `min_sale_raw: str = ""` keyword parameter mirroring `low_stock_threshold_raw`/`stale_days_raw`.

---

### `app/routes/categories.py` (new thin route)

**Analog:** `app/routes/reports.py::reports_stock_page` (lines 153-165)

```python
# Source: app/routes/reports.py lines 153-165 (verified)
@router.get("/reports/stock")
def reports_stock_page(request: Request, session: Session = Depends(get_session)):
    """RPT-02/D-03: "as of now" stock view — no period filter, always the full page."""
    low_stock_rows = [
        {"product": p, "threshold": effective_low_stock_threshold(p)}
        for p in low_stock_products(session)
    ]
    context = {
        "low_stock_rows": low_stock_rows,
        "all_products": all_active_products(session),
        "low_stock_ids": {row["product"].id for row in low_stock_rows},
    }
    return templates.TemplateResponse(request, "pages/reports_stock.html", context)
```
New route mirrors this exact shape — plain full-page GET, no `HX-Request` branching (unlike `reports_sales_page`/`reports_products_page`, which branch because they have a period filter; `/categories` has none per D-01):
```python
@router.get("/categories")
def categories_page(request: Request, session: Session = Depends(get_session)):
    context = {"groups": products_by_category(session)}
    return templates.TemplateResponse(request, "pages/categories.html", context)
```
Import pattern to mirror: `app/routes/products.py` lines 1-19 (`from app.routes import templates`, `from app.db import get_session`, `from app.services.catalog import ...`).

---

### `app/templates/pages/categories.html` (new page)

**Analog:** `app/templates/pages/reports_stock.html` (full file, 53 lines)

Structure to mirror: `{% extends "base.html" %}`, `{% block content %}`, `<h1>`, then a `<table>` per group with an `{% if not X %}<p class="empty-state muted">...</p>{% else %}` guard (lines 6-8). D-02's required columns (Код, Название, Остаток, Закупочная, Продажа, Каталог, Действия) extend the `reports_stock.html` table shape (which only has Код/Название/Остаток/Статус) — add the extra `<td class="num">` cells using the same `| cents` filter pattern already used in `product_form.html` (e.g. `product.cost_cents | cents`) and add an edit-link `<td><a href="/products/{{ product.id }}/edit">...</a></td>` per row. Loop groups with `{% for group in groups %}<h2>{{ group.label }}</h2><table>...{% for product in group.products %}...{% endfor %}</table>{% endfor %}`.

**Security note (from RESEARCH.md):** autoescape only, never `|safe` on `product.name` — same rule as `sale_oversell.html`'s documented convention.

---

### `app/templates/base.html` — nav link

**Analog:** same file, lines 17-29 (nav `<a>` list)

```html
<!-- Source: app/templates/base.html lines 24-25 (verified) -->
<a href="/writeoff"{% if request.url.path.startswith("/writeoff") %} class="active"{% endif %}>Списание</a>
<a href="/customers"{% if request.url.path.startswith("/customers") %} class="active"{% endif %}>Покупатели</a>
```
Add one new `<a href="/categories"{% if request.url.path.startswith("/categories") %} class="active"{% endif %}>Категории</a>` — insert after `/products` (D-01: separate nav item, not nested under Товары/Отчёты) — exact label TBD by planner but follow this active-class convention verbatim.

---

### `app/templates/pages/product_form.html` — new min-price field

**Analog:** same file, `sale` field block (lines 56-60)

```jinja2
{# Source: app/templates/pages/product_form.html lines 56-60 (verified) #}
<div class="field">
  <label for="sale">Цена продажи <span class="muted">(необязательно)</span></label>
  <input type="text" id="sale" name="sale" inputmode="decimal" placeholder="0,00" value="{% if form %}{{ form.sale or '' }}{% elif product and product.sale_cents is not none %}{{ product.sale_cents | cents }}{% endif %}">
  {% if errors.sale %}<p class="error">{{ errors.sale }}</p>{% endif %}
</div>
```
New field per D-07, inserted between the `sale` block (ends line 60) and the `catalog` block (starts line 62):
```jinja2
<div class="field">
  <label for="min_sale">Минимальная цена продажи <span class="muted">(необязательно)</span></label>
  <input type="text" id="min_sale" name="min_sale" inputmode="decimal" placeholder="0,00" value="{% if form %}{{ form.min_sale or '' }}{% elif product and product.min_sale_cents is not none %}{{ product.min_sale_cents | cents }}{% endif %}">
  {% if errors.min_sale %}<p class="error">{{ errors.min_sale }}</p>{% endif %}
</div>
```
Note: deliberately NO `(по умолчанию: N)` hint (unlike `low_stock_threshold` label at line 69) since D-06 has no global fallback.

---

### `app/routes/products.py` — wire new `min_sale` Form field

**Analog:** same file, `product_create` (lines 56-100), `low_stock_threshold` handling

```python
# Source: app/routes/products.py lines 56-79 (verified)
@router.post("/products")
def product_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    category: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    low_stock_threshold: str = Form(""),
    stale_days: str = Form(""),
    session: Session = Depends(get_session),
):
    product, errors = create_product(
        session,
        code=code, name=name, category=category,
        cost_raw=cost, sale_raw=sale, catalog_raw=catalog,
        low_stock_threshold_raw=low_stock_threshold,
        stale_days_raw=stale_days,
    )
```
Add `min_sale: str = Form("")` parameter and pass `min_sale_raw=min_sale` to `create_product`/`update_product`; add `"min_sale": min_sale` to the `form` re-render dict on error (line ~93) mirroring `"low_stock_threshold": low_stock_threshold`. `product_update` (line 123+) needs the identical treatment.

---

### `app/services/sales.py` — `register_sale` price-floor block (PRICE-01 core)

**Analog:** same file, oversell block (lines 129-148)

```python
# Source: app/services/sales.py lines 129-148 (verified)
    if confirm != "1":
        requested_by_product: dict[str, int] = {}
        products_by_id: dict[str, Product] = {}
        for line in resolved:
            product = line["product"]
            requested_by_product[product.id] = requested_by_product.get(product.id, 0) + line["qty"]
            products_by_id[product.id] = product

        oversold = [
            {
                "product": products_by_id[product_id],
                "available": products_by_id[product_id].quantity,
                "requested": requested,
            }
            for product_id, requested in requested_by_product.items()
            if requested > products_by_id[product_id].quantity
        ]
        if oversold:
            oversold.sort(key=lambda entry: entry["product"].name)
            return {"oversell": oversold}, {}
```
**Critical:** do NOT copy this `if oversold: return ...` early-return shape verbatim — Pitfall 2 (RESEARCH.md) requires BOTH checks computed before any return, so a basket tripping both surfaces both warnings in one round trip. Replace the tail with:
```python
        below_minimum = [
            {
                "product": line["product"],
                "entered": line["price_cents"],
                "minimum": line["product"].min_sale_cents,
            }
            for line in resolved
            if line["product"].min_sale_cents is not None
            and line["price_cents"] < line["product"].min_sale_cents
        ]

        if oversold or below_minimum:
            result: dict = {}
            if oversold:
                oversold.sort(key=lambda entry: entry["product"].name)
                result["oversell"] = oversold
            if below_minimum:
                below_minimum.sort(key=lambda entry: entry["product"].name)
                result["below_minimum"] = below_minimum
            return result, {}
```
D-09: this check is per-LINE — do not aggregate/sum like `requested_by_product` (Pitfall: "Aggregating the price-floor check like the oversell check"). D-10: strict `<`, equal-to-minimum passes silently.

---

### `app/templates/partials/sale_price_warning.html` (NEW)

**Analog:** `app/templates/partials/sale_oversell.html` (full file, 23 lines)

```html
<!-- Source: app/templates/partials/sale_oversell.html (verified, full file) -->
<div class="error-block" id="sale-oversell-warning">
  <p><strong>Товара не хватает на складе</strong></p>
  {% for e in oversell %}
  <p>{{ e.product.name }}: на складе {{ e.available }}, продаёте {{ e.requested }}.</p>
  {% endfor %}
  <div class="form-actions">
    <button type="submit" class="danger" form="sale-form"
            hx-post="/sales" hx-vals='{"confirm": "1"}'
            hx-target="#sale-form-wrap" hx-swap="outerHTML"
            hx-disabled-elt="this">Продать всё равно</button>
    <button type="button" class="secondary"
            hx-on:click="this.closest('#sale-oversell-warning').remove()">Вернуться к корзине</button>
  </div>
</div>
```
New partial, same structure, `id="sale-price-warning"`, same `confirm=1` flag (D-11: shares the SAME flag, not a second one):
```html
<div class="error-block" id="sale-price-warning">
  <p><strong>Цена ниже минимальной</strong></p>
  {% for e in below_minimum %}
  <p>{{ e.product.name }}: цена {{ e.entered | cents }}, минимум {{ e.minimum | cents }}.</p>
  {% endfor %}
  <div class="form-actions">
    <button type="submit" class="danger" form="sale-form"
            hx-post="/sales" hx-vals='{"confirm": "1"}'
            hx-target="#sale-form-wrap" hx-swap="outerHTML"
            hx-disabled-elt="this">Продать всё равно</button>
    <button type="button" class="secondary"
            hx-on:click="this.closest('#sale-price-warning').remove()">Вернуться к корзине</button>
  </div>
</div>
```

---

### `app/templates/partials/sale_form.html` — include the new partial

**Analog:** same file, oversell include block (lines 15-20)

```jinja2
{# Source: app/templates/partials/sale_form.html lines 15-20 (verified) #}
{% if oversell %}
{% include "partials/sale_oversell.html" %}
{% endif %}
```
Add directly after it: `{% if below_minimum %}{% include "partials/sale_price_warning.html" %}{% endif %}` — both blocks stack in the same response per D-11 when both keys are present in `register_sale`'s result dict.

---

### `app/templates/partials/price_history.html` — new elif branch (if `_PRICE_FIELDS` joined)

**Analog:** same file, lines 19-25

```jinja2
{# Source: app/templates/partials/price_history.html lines 19-25 (verified) #}
<td>
  {%- if op.payload.field == "cost_cents" -%}Закупочная
  {%- elif op.payload.field == "sale_cents" -%}Продажа
  {%- elif op.payload.field == "catalog_cents" -%}Каталог
  {%- else -%}{{ op.payload.field }}
  {%- endif -%}
</td>
```
Add `{%- elif op.payload.field == "min_sale_cents" -%}Минимальная` before the `{%- else -%}` fallback — only needed if the planner adopts RESEARCH.md's Open Question #1 recommendation (join `_PRICE_FIELDS`).

---

## Shared Patterns

### Warn-but-allow guardrail (confirm=1 gate)
**Source:** `app/services/sales.py` lines 129-148 (oversell), extended per Pattern 2 above
**Apply to:** `register_sale`'s new `below_minimum` block — MUST share the exact same `confirm != "1"` gate, zero-writes-until-confirmed contract, and be computed alongside (not after/instead of) the oversell check so both can surface in one response (Pitfall 2).

### Nullable-override field, `is not None` discipline
**Source:** `app/services/stock.py::effective_low_stock_threshold` (lines 19-25, per RESEARCH.md) — same discipline visible in `catalog.py::update_product`'s `product.low_stock_threshold is not none` Jinja check
**Apply to:** every read of `min_sale_cents` — Python: `is not None`, Jinja: `is not none`. Never a bare `or` (Pitfall 1) — this differs from `low_stock_threshold`/`stale_days` in having NO `else settings.*` fallback; it's a pure guard clause with no else branch.

### Optional money field parsing
**Source:** `app/services/catalog.py::parse_optional_cents` (lines 22-40)
**Apply to:** `min_sale` form field in `create_product`/`update_product` — reuse verbatim, do not hand-roll a new parser (RESEARCH.md "Don't Hand-Roll" table).

### Active-only soft-delete filtering
**Source:** `app/services/catalog.py::list_products`/`search_products`/`category_options` (`Product.deleted_at.is_(None)`)
**Apply to:** `products_by_category()` — identical filter, consistent with every other catalog view.

### Plain full-page GET (no HTMX partial machinery)
**Source:** `app/routes/reports.py::reports_stock_page` (lines 153-165)
**Apply to:** `/categories` route — no `HX-Request` header branching, unlike the period-filtered reports routes.

### RU error/label conventions
**Source:** `app/services/catalog.py` module-level error constants (`PRICE_ERROR`, `THRESHOLD_ERROR`), `product_form.html` label pattern (`<span class="muted">(необязательно)</span>`)
**Apply to:** all new user-facing strings in this phase (nav label, field label, warning block copy) — Russian text, matching existing tone/format exactly.

## No Analog Found

None — every file in this phase has a direct, exact-match precedent already shipped in this codebase (Phases 1-6).

## Metadata

**Analog search scope:** `app/models.py`, `app/services/{catalog,sales,stock}.py`, `app/routes/{reports,products,sales}.py`, `app/templates/{base.html,pages/*,partials/*}`, `alembic/versions/0005_product_thresholds.py`
**Files scanned:** 12 read directly (full or targeted), plus directory listings of `app/routes`, `app/services`, `app/templates/pages`, `app/templates/partials`, `alembic/versions`
**Pattern extraction date:** 2026-07-10
