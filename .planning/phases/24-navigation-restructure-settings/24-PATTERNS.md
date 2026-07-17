# Phase 24: Navigation Restructure & Settings - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 17 (new + modified)
**Analogs found:** 15 / 17

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/templates/base.html` (nav reduction to 8 items, NAV-08) | component (chrome) | request-response | itself (in-place edit) | exact — pattern already present |
| `app/templates/partials/products_toolbar.html` (NEW, D-01/D-04) | component | request-response | `app/templates/pages/catalog_detail.html` (`.form-actions` block, lines 6-8) + `app/static/style.css` `.filter-bar`/`.form-actions` | role-match |
| `app/routes/products.py` (products_list gains toolbar context) | controller | CRUD/request-response | itself (`products_list`, lines 85-101) | exact — additive only |
| `app/routes/settings.py` (NEW, D-06) | controller | request-response | `app/routes/backup.py` (`backup_page`, lines 27-34) — thin GET-only page composing a service call | role-match |
| `app/services/settings.py` (NEW, D-06) | service | transform/CRUD-read | `app/services/warehouses.py::list_warehouses` + `app/services/backup.py::list_backups` (composition pattern) | role-match |
| `app/templates/pages/settings.html` (NEW) | component | request-response | `app/templates/pages/export.html` (simple link-list hub page, 10 lines) | role-match |
| `app/routes/backup.py` (MODIFIED — embed export section, D-07) | controller | file-I/O | itself + `app/templates/pages/export.html` (source of the 3 `<a>` links to inline) | exact |
| `app/routes/transfers.py` (MODIFIED — `GET /transfers?code=`, D-14) | controller | request-response | `app/routes/products.py::product_new` (lines 174-203, `?code=` resolve-then-prefill) | exact |
| `app/templates/partials/product_rows.html` (MODIFIED — add Перемещение action, D-13) | component | CRUD (row actions) | itself (existing actions `<td>`, lines 61-64) | exact — additive only |
| `app/templates/mobile_base.html` (MODIFIED — top tab bar block, D-09) | component (chrome) | request-response | `app/templates/base.html` (`<nav>` active-state pattern, lines 34-52) | role-match |
| `app/templates/mobile_pages/home.html` (MODIFIED — remove tile grid, D-10) | component | request-response | itself (in-place deletion of lines 5-16) | exact |
| `app/templates/mobile_pages/finance.html` (MODIFIED — remove report link, D-12/Pitfall 2) | component | request-response | itself (in-place deletion of line 15) | exact |
| `app/routes/mobile_products.py` (NEW, MOB-01/Pitfall 1) | controller | CRUD (read + delete) | `app/routes/mobile_search.py` (thin route, dual HX/full-page response, lines 20-29) reusing `app/services/catalog.list_products_view` | role-match |
| `app/routes/mobile_customers.py` (NEW, MOB-01/Pitfall 1) | controller | CRUD (read) | `app/routes/mobile_search.py` (same shape) reusing `app/services/customers.list_customers_view` | role-match |
| `app/templates/mobile_pages/products.html` (NEW) | component | request-response | `app/templates/mobile_pages/home.html` (`{% extends "mobile_base.html" %}` shell) + desktop `products_list.html` for column shape | role-match |
| `app/templates/mobile_pages/customers.html` (NEW) | component | request-response | `app/templates/mobile_pages/home.html` shell | role-match |
| `app/templates/pages/reports_{sales,writeoffs,stock,expiry,products}.html` (MODIFIED x5, RPT-01) | component | request-response | `app/templates/pages/catalog_detail.html` (line 3, back-link precedent) | exact |

## Pattern Assignments

### `app/templates/partials/products_toolbar.html` (NEW component, D-01/D-04)

**Analog:** `app/templates/pages/catalog_detail.html` lines 6-8 + `app/static/style.css` lines 20-36

**Existing `.form-actions` group usage** (`catalog_detail.html:6-8`):
```html
<div class="form-actions">
  <a class="button" href="/catalogs/{{ catalog.url_code }}/file" target="_blank" rel="noopener">Открыть PDF</a>
</div>
```

**Existing nav active-state CSS to extend, NOT reinvent** (`style.css:20-36`):
```css
nav {
  display: flex;
  gap: 16px;
  background: #ffffff;
  border-bottom: 1px solid #d9d9d9;
  margin: 0 -16px 32px;
  padding: 8px 16px;
}
nav a { text-decoration: none; }
nav a.active { font-weight: 600; }
```

**Pattern to copy (per RESEARCH.md Pattern 2, verbatim-ready markup):**
```html
{# app/templates/partials/products_toolbar.html — NEW.
   Use <div class="toolbar">, NEVER <nav> (Pitfall 5 — base.html already owns
   the one <nav> landmark; report HX-partial tests assert `"<nav" not in text`). #}
<div class="toolbar">
  <div class="toolbar-group">
    <span class="muted">Действия</span>
    <div class="form-actions">
      <a class="button" href="/receipts/new">Приход</a>
      <a class="button" href="/writeoff">Списание</a>
    </div>
  </div>
  <div class="toolbar-group">
    <span class="muted">Справочники</span>
    <div class="form-actions">
      <a class="button" href="/categories">Категории</a>
      <a class="button" href="/dictionary">Справочник</a>
      <a class="button" href="/catalogs">Каталоги</a>
    </div>
  </div>
</div>
```
Only `.toolbar`/`.toolbar-group` need ~2 new CSS rules in `style.css` (simple flex wrappers, near the existing `nav`/`.form-actions`/`.filter-bar` rules at lines 20-36); everything else (`.form-actions`, `.button`, `.muted`) reuses verbatim.

**Include point:** `{% include "partials/products_toolbar.html" %}` at the top of `app/templates/pages/products_list.html` content block (always visible, D-05 — no `<details>`).

---

### `app/routes/settings.py` (NEW controller, D-06)

**Analog:** `app/routes/backup.py` lines 1-34 (thin GET route composing one service call, no HX branch needed — Настройки has no partial-swap use case)

**Imports pattern** (`backup.py:9-19`):
```python
from pathlib import Path
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services import backup as backup_service

router = APIRouter()
```

**Core GET pattern** (`backup.py:27-34`, `backup_page`):
```python
@router.get("/backup")
def backup_page(request: Request):
    context = {
        "backups": backup_service.list_backups(Path(settings.backup_dir)),
        "message": None,
        "error": None,
    }
    return templates.TemplateResponse(request, "pages/backup.html", context)
```
Apply the same shape for `GET /settings`: call `settings_service.settings_summary(session, Path(settings.backup_dir))` and render `pages/settings.html`.

---

### `app/services/settings.py` (NEW service, D-06)

**Analogs:** `app/services/warehouses.py::list_warehouses` (lines 21-36) and `app/services/backup.py::list_backups` (lines 59-78) — both read verbatim, no new tracking needed.

```python
# app/services/warehouses.py:21-29 — signature/defaults to call
def list_warehouses(session, *, name="", address="", status="", sort="", page=0) -> dict:
    # status="" -> active rows only (D-14 default) => result["total"] is the
    # active-warehouse count the operator expects on /settings.
    ...

# app/services/backup.py:59-78 — signature to call
def list_backups(backup_dir: Path) -> list[dict]:
    # newest-first; entries[0]["created_iso"] is the last-backup timestamp.
    ...
```

**Pattern to write** (per RESEARCH.md Pattern 3):
```python
def settings_summary(session: Session, backup_dir: Path) -> dict:
    warehouse_count = list_warehouses(session)["total"]
    backups = list_backups(backup_dir)
    last_backup_iso = backups[0]["created_iso"] if backups else None
    return {"warehouse_count": warehouse_count, "last_backup_iso": last_backup_iso}
```

---

### `app/templates/pages/settings.html` (NEW component)

**Analog:** `app/templates/pages/export.html` (full file, 10 lines) — simplest existing "hub of plain links" page in the codebase.

```html
{% extends "base.html" %}
{% block content %}
<h1>Экспорт данных</h1>
<p class="muted">Выгрузите данные в CSV — файлы открываются в Excel.</p>
<p><a class="button" href="/export/products.csv">Скачать товары (CSV)</a></p>
{% endblock %}
```
Copy this `{% extends %}` + `<h1>` + plain `<p><a>` shape; add the D-06 status-summary text inline or as a subtitle next to each link (Claude's discretion on exact treatment), e.g.:
```html
<p><a href="/warehouses">Склады</a> <span class="muted">— {{ warehouse_count }} шт.</span></p>
<p><a href="/backup">Резервные копии</a> <span class="muted">— последняя: {{ last_backup_iso | local_dt if last_backup_iso else "нет" }}</span></p>
<p><a href="/finance/report">Экспорт кассы</a></p>
```

---

### `app/routes/backup.py` (MODIFIED — embed export, D-07)

**Analog:** itself, `backup_page` (lines 27-34) — no route-logic change needed, only template composition; `app/templates/pages/export.html` (full file, above) is the source of the 3 `<a>` links to copy/include into `pages/backup.html`.

No new context keys required — the CSV endpoints (`/export/products.csv` etc.) take no params (V12 pattern, per `export.py` docstring), so a plain `{% include "pages/export.html" %}`-style copy of the 3 `<a class="button">` lines into `backup.html`'s content block is sufficient; no route change is strictly needed unless the export section needs its own heading/wrapper, in which case inline the 3 `<a>` tags directly.

---

### `app/routes/transfers.py` (MODIFIED — `?code=` param, D-14)

**Analog:** `app/routes/products.py::product_new` lines 174-203 — the exact resolve-then-prefill shape to mirror, read verbatim.

```python
# app/routes/products.py:174-203 — pattern to mirror for GET /transfers?code=
@router.get("/products/new")
def product_new(request: Request, code: str = "", session: Session = Depends(get_session)):
    code_clean = code.strip()
    if code_clean:
        existing = session.scalars(
            select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
        ).first()
        if existing is not None:
            return RedirectResponse(f"/products/{existing.id}/edit")
    context = {
        "product": None,
        ...
        "form": {"code": code_clean} if code_clean else {},
        ...
    }
    return templates.TemplateResponse(request, "pages/product_form.html", context)
```

**Current transfers_page to modify** (`transfers.py:33-41`):
```python
@router.get("/transfers")
def transfers_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "errors": {},
        "form": {},
        "focus_code": False,
        "transfers": recent_transfers(session),
    }
    return templates.TemplateResponse(request, "pages/transfer_form.html", context)
```

**Reusable resolution logic already in the same file** (`transfers.py:44-75`, `transfers_lookup`) — extract a shared helper (e.g. `_resolve_transfer_lookup(session, code)`) used by both the new `?code=` branch on `transfers_page` and the existing `transfers_lookup` endpoint, per RESEARCH.md Pattern 1. It already imports `lookup_prefill` (from `app.services.receipts`) and `open_batches` (from `app.services.batches`) — no new imports needed.

**V5 input-validation note (RESEARCH.md Security Domain):** `.strip()` the raw `code` string, look up via parameterized `select(Product).where(Product.code == code_clean, ...)` (already this file's convention, lines 63-65, 88-90, 139-141), and treat "not found" as silent no-prefill — never a 500 or an error echoing unsanitized input. Never add `|safe` to the prefilled value in the template.

---

### `app/templates/partials/product_rows.html` (MODIFIED — Перемещение row action, D-13)

**Analog:** itself, existing actions `<td>` (lines 61-64), read verbatim.

```html
<!-- app/templates/partials/product_rows.html:61-64, existing -->
<td>
  <a href="/products/{{ product.id }}/edit">Изменить</a>
  <a href="#" class="link-danger" hx-post="/products/{{ product.id }}/quick-delete?page={{ page }}{{ extra_qs }}" hx-confirm="Удалить товар „{{ product.name }}“? Он будет скрыт из каталога и поиска, история операций сохранится." hx-target="#product-rows" hx-swap="outerHTML">Удалить</a>
</td>
```
Add a third plain link (no htmx — this is page navigation, mirroring the `catalog_detail.html:37` precedent `<a href="/products/new?code={{ entry.code }}">изменить цену</a>`):
```html
  <a href="/transfers?code={{ product.code }}">Переместить</a>
```

---

### `app/templates/mobile_base.html` (MODIFIED — persistent top tab bar, D-09)

**Analog:** `app/templates/base.html` `<nav>` active-state pattern (lines 34-52) for the Jinja `startswith`/`active`-class idiom; current `mobile_base.html` block structure (lines 29-34) for where to add the new block.

**Existing block structure to extend** (`mobile_base.html:29-34`):
```html
<body>
  <main class="mobile-shell">
    {% block back %}<a class="mobile-back" href="/m/">← Главная</a>{% endblock %}
    {% block step_indicator %}{% endblock %}
    {% block content %}{% endblock %}
  </main>
</body>
```

**Active-state idiom to reuse** (`base.html:36`):
```html
<a href="/products"{% if request.url.path.startswith("/products") %} class="active"{% endif %}>Товары</a>
```

**Per Pitfall 4/5:** add the tab bar as a NEW `{% block tabbar %}` in `mobile_base.html` itself (sibling to `{% block back %}`), never duplicated per-page (no `hx-boost` in this project — confirmed zero matches — so full page reload re-renders the shell every navigation, no oob-swap risk). Use `<nav class="mobile-tabbar">` — a second legitimate `<nav>` landmark is fine for mobile since `base.html`'s single-`<nav>` assumption / `"<nav" not in text` tests are desktop-report-partial-specific (`tests/test_reports.py:316,459`), not global. Give it namespaced classes/ids (`.mobile-tabbar`, not `.nav`/`#tabs`) to avoid collision with existing oob-swap target ids (`#cash-history-cards`, `#finance-metrics`, etc.).

---

### `app/routes/mobile_products.py` / `app/routes/mobile_customers.py` (NEW controllers, MOB-01/Pitfall 1)

**Analog:** `app/routes/mobile_search.py` (full file, 59 lines) — thin route, dual HX-partial/full-page response, reusing an existing desktop service unchanged.

**Imports + dual-response pattern** (`mobile_search.py:1-29`):
```python
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from app.db import get_session
from app.models import Product
from app.routes import templates
from app.services.catalog import search_view

router = APIRouter()

@router.get("/m/search")
def mobile_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    context = search_view(session, q)
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(request, "mobile_partials/search_results.html", context)
    return templates.TemplateResponse(request, "mobile_pages/search.html", context)
```
Mirror this exactly for `GET /m/products` (reusing `app.services.catalog.list_products_view`, same as desktop `app/routes/products.py::products_list`, lines 85-101) and `GET /m/customers` (reusing `app.services.customers.list_customers_view` — verify exact service function name before use). Also mirror `mobile_search_product_detail` (lines 32-58) if a per-product mobile detail view is needed, and the desktop `product_quick_delete` (`products.py:104-130`) if D-11's mobile toolbar needs delete parity — confirm scope with the plan before adding write routes.

Include the D-11 mobile Товары toolbar (same two-group shape as desktop's `products_toolbar.html`, adapted for touch) inside `mobile_pages/products.html`.

---

### `app/templates/mobile_pages/home.html` (MODIFIED — remove tile grid, D-10)

**Exact deletion target** (`home.html:5-16`, plus the anticipatory comment at 18-22 that can now also be removed/updated):
```html
<div class="mobile-tile-grid">
  <a class="mobile-tile" href="/m/sales">Продажа</a>
  <a class="mobile-tile" href="/m/receipts">Приход</a>
  <a class="mobile-tile" href="/m/search">Поиск</a>
  <a class="mobile-tile" href="/m/writeoff">Списание</a>
  <a class="mobile-tile" href="/m/corrections">Корректировка</a>
  <a class="mobile-tile" href="/m/transfers">Перемещение</a>
  <a class="mobile-tile" href="/m/history">История</a>
  <a class="mobile-tile" href="/m/reports/expiry">Сроки годности</a>
  <a class="mobile-tile" href="/m/finance">Финансы</a>
  <a class="mobile-tile" href="/m/finance/report">Экспорт кассы</a>
</div>
```
Remove entirely; the dashboard content below (lines 23+, `<h2>Показатели</h2>` onward) stays untouched (D-10 explicitly preserves dashboard content, only removes the grid).

---

### `app/templates/mobile_pages/finance.html` (MODIFIED — remove report CTA, D-12/Pitfall 2)

**Deletion target** (`finance.html:15`, referenced in RESEARCH.md, not yet read verbatim in this session — confirm exact line before editing):
```html
<p><a class="button" href="/m/finance/report">Отчёт и экспорт CSV</a></p>
```
Remove this in-page link (independent of the home-grid tile removal above) to fully honor D-12 — Настройки-hosted destinations (including Экспорт кассы) must be unreachable from any `/m/*` page, not just absent from the tile grid and future tab bar.

---

### `app/templates/pages/reports_{sales,writeoffs,stock,expiry,products}.html` (MODIFIED x5, RPT-01)

**Analog:** `app/templates/pages/catalog_detail.html` lines 1-4, read verbatim.

```html
{% extends "base.html" %}
{% block content %}
<p><a href="/catalogs">← Все каталоги</a></p>
<h1>{{ catalog.label }}</h1>
```

**Current shape of each report template to insert into** (`reports_sales.html:1-4`, representative of all 5):
```html
{% extends "base.html" %}
{% block content %}
<h1>Продажи и прибыль</h1>
```

**Pattern to apply identically to all 5 files** (insert immediately before each `<h1>`):
```html
<p><a href="/reports">← Назад к отчётам</a></p>
```

---

## Shared Patterns

### Active-nav-item highlighting
**Source:** `app/templates/base.html:35-51`
**Apply to:** `base.html` (reduced to 8 items), `mobile_base.html` (new tab bar block)
```html
<a href="/products"{% if request.url.path.startswith("/products") %} class="active"{% endif %}>Товары</a>
```
Do not invent a new JS-based active-state mechanism — this Jinja `request.url.path` idiom is already used 17 times and extends trivially.

### Thin route + service composition
**Source:** `app/routes/backup.py:27-34`, `app/routes/warehouses.py:81-97`
**Apply to:** `settings.py`, `mobile_products.py`, `mobile_customers.py`
All new routes must stay thin (route calls one service function, builds a context dict, picks a template) — no business logic, no direct SQL in routes.

### Query-param resolve-then-prefill
**Source:** `app/routes/products.py:174-203` (`product_new`)
**Apply to:** `transfers.py` (`GET /transfers?code=`, D-14)
`.strip()` the param, look up via parameterized `select()`, treat "not found" as a no-op (empty form), never `|safe` the echoed value.

### `.form-actions`/`.filter-bar`/`.button`/`.muted` CSS reuse
**Source:** `app/static/style.css` (405 lines total — `.form-actions`, `.filter-bar`, `.button`, `.muted` all pre-existing)
**Apply to:** `products_toolbar.html`, `settings.html`
Only `.toolbar`/`.toolbar-group` (simple flex wrappers) are net-new CSS; everything nested inside must reuse existing classes verbatim.

### `<nav>` landmark is reserved
**Source:** `app/templates/base.html:34`; `tests/test_reports.py:316,459` (`"<nav" not in response.text` assertions on desktop HX-partials)
**Apply to:** `products_toolbar.html` (use `<div class="toolbar">`, never `<nav>`); `mobile_base.html` tab bar may use a second `<nav class="mobile-tabbar">` since it's a legitimately distinct landmark and the negative assertions are desktop-report-partial-scoped only.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `app/templates/mobile_pages/products.html` | component | request-response | No existing mobile product-list template; synthesize from `mobile_pages/home.html`'s `{% extends "mobile_base.html" %}` shell + desktop `pages/products_list.html`'s column/toolbar shape (RESEARCH.md Pitfall 1) |
| `app/templates/mobile_pages/customers.html` | component | request-response | No existing mobile customer-list template; same synthesis approach, desktop analog is `pages/customers_list.html` (not read this session — read before implementing) |

## Metadata

**Analog search scope:** `app/routes/`, `app/templates/{pages,partials,mobile_pages,mobile_partials}/`, `app/services/`, `app/static/style.css`
**Files scanned:** `base.html`, `mobile_base.html`, `products.py`, `warehouses.py`, `backup.py`, `transfers.py`, `product_rows.html`, `mobile_search.py`, `mobile_finance.py`, `mobile_pages/home.html`, `catalog_detail.html`, `export.html`, `reports_sales.html`, `style.css` (lines 1-60), `services/warehouses.py` (list_warehouses), `services/backup.py` (list_backups)
**Pattern extraction date:** 2026-07-17
