# Phase 8: Warehouses - Pattern Map

**Mapped:** 2026-07-11
**Files analyzed:** 8 (new) + 3 (modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `app/models.py` (+ `Warehouse` class) | model | CRUD | `Dictionary` class (`app/models.py` lines 119-133) | exact |
| `alembic/versions/0007_warehouses.py` | migration | batch (one-time seed) | `alembic/versions/0001_initial_schema.py` (seed) + `0002_catalog_dictionary.py` (create_table) | exact |
| `app/services/warehouses.py` | service | CRUD + warn-but-allow | `app/services/dictionary.py` (CRUD) + `app/services/catalog.py::soft_delete_product/restore_product` (soft-delete) + `app/services/sales.py::register_sale` (confirm-gate) | exact (composite) |
| `app/routes/warehouses.py` | route/controller | request-response | `app/routes/dictionary.py` (add/edit shape) + `app/routes/products.py::product_delete/product_restore` (delete/restore shape, response ADAPTED) | role-match (response shape must diverge, see Shared Patterns) |
| `app/templates/pages/warehouses.html` | template (page) | request-response | `app/templates/pages/dictionary.html` | exact |
| `app/templates/partials/warehouse_rows.html` | template (partial) | request-response | `app/templates/partials/dictionary_rows.html` (row structure/edit branching) + `app/templates/partials/sale_price_warning.html` (inline `.error-block` warning shape, not read verbatim but same class names confirmed via RESEARCH.md/UI-SPEC) | role-match (composite) |
| `app/templates/base.html` (modify: add nav link) | template (layout) | request-response | existing nav `<a>` entries, e.g. `/categories` link (line 20) | exact |
| `app/routes/__init__.py` — no change needed | — | — | n/a (router registration happens in `app/main.py`) | — |
| `app/main.py` (modify: register router) | config/bootstrap | — | existing `app.include_router(categories.router)` line (line 42) | exact |
| `tests/test_warehouses.py` | test | CRUD + web + migration | `tests/test_dictionary.py` (service/web CRUD tests) + `tests/test_catalog.py::test_migration_0006_adds_min_sale_cents_column` (migration test) | exact (composite) |

## Pattern Assignments

### `app/models.py` (+ `Warehouse` class)

**Analog:** `Dictionary` class, `app/models.py` lines 119-133; soft-delete columns from `Product`, lines 91-116.

**Core pattern** (Dictionary shape, lines 119-133):
```python
class Dictionary(Base):
    __tablename__ = "dictionary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
```

**Soft-delete column to graft on** (from `Product`, line 116):
```python
    deleted_at: Mapped[str | None] = mapped_column(String(32))
```

**What to build** (per D-04/D-05, RESEARCH.md "Code Examples > Model"): a `Warehouse` class with `id`, `name` (required, `String(200)`), `address` (optional, `String(300)`, nullable), `created_at`/`updated_at` (Dictionary shape), `deleted_at` (Product shape). No `code`, no unique constraint (D-04 says "no uniqueness enforced").

**Imports:** already present at top of `app/models.py` (`String`, `Mapped`, `mapped_column`, `new_id`, `utcnow_iso`) — no new imports needed.

---

### `alembic/versions/0007_warehouses.py`

**Analog A — table creation:** `alembic/versions/0002_catalog_dictionary.py` (`op.create_table` shape for a new standalone table, no FK).
**Analog B — seed insert:** `alembic/versions/0001_initial_schema.py` (`op.bulk_insert` with `sa.table()`/`sa.column()` shim and a frozen demo-row UUID, e.g. `DEMO_PRODUCT_ID`).

**Revision chain:** last existing revision is `0006` (`0006_product_min_sale_price.py`) — new file must declare `revision = "0007"`, `down_revision = "0006"`.

**Critical rule (WR-06, verified across all 6 existing migration files):** migration files never import `app.models` or `app.core` — every column definition and seed value is a frozen literal written directly in the migration file. Use `sa.table()` + `sa.column()` for the bulk-insert shim, never the ORM `Warehouse` class.

**Frozen values to pick and record** (per RESEARCH.md Pitfall 5 / D-03): a stable `DEFAULT_WAREHOUSE_ID` UUID literal (e.g. `"00000000-0000-4000-8000-000000000010"`, following the same `0000...0001`-style demo-id convention as migration 0001) and a stable RU seed name (e.g. `"Склад по умолчанию"`) — Phase 9's migration will need to reference these same literal values (re-declared, not imported).

**Structure to copy (RESEARCH.md's Code Examples section already contains a verified, ready-to-adapt full file)** — `op.create_table("warehouses", ...)` with columns `id, name, address, created_at, updated_at, deleted_at`, PK named via `op.f("pk_warehouses")` (matches the project's `NAMING_CONVENTION` in `app/models.py`), followed by one `op.bulk_insert` seeding exactly one row; `downgrade()` does `op.drop_table("warehouses")`.

---

### `app/services/warehouses.py`

**Analog A — CRUD shape:** `app/services/dictionary.py` (`add_entry`, `update_entry`, `list_entries`).

**Imports pattern** (lines 8-13 of `dictionary.py`):
```python
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Dictionary
```
For warehouses: drop `IntegrityError` (no unique constraint on `name`, per D-04), add `func` from sqlalchemy for the active-count check (Pattern 3 below), import `Warehouse` and `utcnow_iso` instead of/in addition to `new_id`.

**Add-entry pattern** (lines 38-55 of `dictionary.py`) — adapt to `add_warehouse(session, *, name, address)`: strip both fields, require non-blank `name` only (no duplicate-check needed since D-04 has no uniqueness), `session.add`, `session.commit()`.

**List pattern — MUST NOT filter `deleted_at`** (deviates from `list_entries`'s simple `order_by`, per D-09 / RESEARCH.md Pitfall 2): sort active-first then by name in Python, per RESEARCH.md's `list_warehouses`:
```python
def list_warehouses(session: Session) -> list[Warehouse]:
    rows = list(session.scalars(select(Warehouse)))
    return sorted(rows, key=lambda w: (w.deleted_at is not None, w.name))
```

**Analog B — soft-delete/restore shape:** `app/services/catalog.py` lines 295-310 (`soft_delete_product`/`restore_product`):
```python
def soft_delete_product(session: Session, product_id: str) -> None:
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        return
    product.deleted_at = utcnow_iso()
    session.commit()


def restore_product(session: Session, product_id: str) -> None:
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is None:
        return
    product.deleted_at = None
    session.commit()
```
`restore_warehouse` copies this shape verbatim (idempotent, `session.get` + None-check). `soft_delete_warehouse` needs the extra warn-but-allow gate below — do not copy `soft_delete_product` verbatim for delete.

**Analog C — warn-but-allow confirm-gate:** `app/services/sales.py` lines 137-143 (`register_sale`'s oversell check) — the shape is: compute a read-only check BEFORE any write, gated on `confirm != "1"`; return zero-write result if the check fails. Adapt to a single-row delete exactly as RESEARCH.md's Pattern 3 code (already verified against this codebase, safe to use verbatim):
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

---

### `app/routes/warehouses.py`

**Analog A — page + add/edit routes:** `app/routes/dictionary.py` lines 21-24 (page) and lines 43-87 (`dictionary_add`/`dictionary_update`).

**Imports pattern** (lines 8-13 of `dictionary.py`):
```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.dictionary import add_entry, list_entries, lookup, update_entry
```
For warehouses, swap the last import for `app.services.warehouses` (`add_warehouse`, `update_warehouse`, `list_warehouses`, `soft_delete_warehouse`, `restore_warehouse`); no `lookup`-equivalent function needed.

**Page + add route pattern** (lines 21-24, 43-61) — same shape, `entries` -> `warehouses`, template -> `pages/warehouses.html` / `partials/warehouse_rows.html`:
```python
@router.get("/dictionary")
def dictionary_page(request: Request, session: Session = Depends(get_session)):
    context = {"entries": list_entries(session), "errors": {}, "form": {}}
    return templates.TemplateResponse(request, "pages/dictionary.html", context)


@router.post("/dictionary")
def dictionary_add(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    entry, errors = add_entry(session, code=code, name=name)
    context = {
        "entries": list_entries(session),
        "errors": errors,
        "form": {"code": code, "name": name} if errors else {},
    }
    return templates.TemplateResponse(
        request, "partials/dictionary_rows.html", context,
        status_code=422 if errors else 200,
    )
```

**Edit route pattern** (lines 64-87) — same `error_entry_id`/`error_form` branching shape for `update_warehouse`.

**Analog B — delete/restore routes, ADAPTED NOT COPIED:** `app/routes/products.py` lines 182-193:
```python
@router.post("/products/{product_id}/delete")
def product_delete(product_id: str, session: Session = Depends(get_session)):
    soft_delete_product(session, product_id)
    return Response(status_code=200, headers={"HX-Redirect": "/products"})


@router.post("/products/{product_id}/restore")
def product_restore(product_id: str, session: Session = Depends(get_session)):
    restore_product(session, product_id)
    return Response(status_code=200, headers={"HX-Redirect": f"/products/{product_id}/edit"})
```
**CRITICAL DEVIATION (RESEARCH.md Pitfall 1 / UI-SPEC Interaction Contract):** do NOT copy the `HX-Redirect` response. Warehouses has no separate edit/detail page. Both routes must instead re-render `partials/warehouse_rows.html` in place, per RESEARCH.md's verified route example:
```python
@router.post("/warehouses/{warehouse_id}/delete")
def warehouse_delete(
    request: Request,
    warehouse_id: str,
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    deleted, warning = soft_delete_warehouse(session, warehouse_id, confirm=confirm == "1")
    context = {
        "warehouses": list_warehouses(session),
        "errors": {},
        "form": {},
        "warning_id": warehouse_id if warning else None,
    }
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
```
`warehouse_restore` mirrors this shape (no `warning_id` needed, always succeeds/no-ops).

---

### `app/templates/pages/warehouses.html`

**Analog:** `app/templates/pages/dictionary.html` (entire file, 17 lines) — copy structure verbatim, renaming `code`/`name` fields to `name`/`address`, target id `#dictionary-rows` -> `#warehouse-rows`, endpoint `/dictionary` -> `/warehouses`:
```html
{% extends "base.html" %}
{% block content %}
<h1>Справочник</h1>

<form hx-post="/dictionary"
      hx-target="#dictionary-rows"
      hx-swap="outerHTML"
      hx-disabled-elt="find button"
      class="form-actions">
  <input type="text" name="code" placeholder="Код" autofocus>
  <input type="text" name="name" placeholder="Название">
  <button type="submit">Добавить код</button>
</form>

{% include "partials/dictionary_rows.html" %}
{% endblock %}
```
Per UI-SPEC: h1 -> «Склады», field order Название (autofocus, required) then Адрес (optional, placeholder «Адрес (необязательно)»), button -> «Добавить склад».

---

### `app/templates/partials/warehouse_rows.html`

**Analog:** `app/templates/partials/dictionary_rows.html` (entire file, 51 lines) — same edit-row/`error_entry_id` branching shape, PLUS new delete/restore/`warning_id` branching (no existing partial has this exact combination; RESEARCH.md's Code Examples section already contains a verified adaptation — use it as the base):
```html
{# from dictionary_rows.html, lines 22-44: per-row edit-form pattern to copy #}
{% for e in entries %}
<tr>
  {% if error_entry_id == e.id and error_form %}
  {% set row = error_form %}
  {% else %}
  {% set row = {"code": e.code, "name": e.name} %}
  {% endif %}
  <td><input type="text" name="code" value="{{ row.code }}" form="edit-{{ e.id }}"></td>
  <td><input type="text" name="name" value="{{ row.name }}" form="edit-{{ e.id }}"></td>
  <td>
    <form id="edit-{{ e.id }}"
          hx-post="/dictionary/{{ e.id }}"
          hx-target="#dictionary-rows"
          hx-swap="outerHTML"
          hx-disabled-elt="find button">
      <button type="submit" class="secondary">Сохранить код</button>
    </form>
    {% if error_entry_id == e.id %}
    {% for message in errors.values() %}<p class="error">{{ message }}</p>{% endfor %}
    {% endif %}
  </td>
</tr>
{% endfor %}
```
Extend with delete/restore buttons and the `warning_id` inline `.error-block` row (already drafted, verified-consistent-with-classes in RESEARCH.md's template example) — see Shared Patterns > Warn-but-allow below for the exact markup to use. Empty-state fallback per Dictionary's `{% else %}` branch (line 47-48) — but per D-09/UI-SPEC this should never trigger post-migration (seeded default row always present).

---

### `app/templates/base.html` (modify)

**Analog:** existing nav `<a>` line for `/categories`, `app/templates/base.html` line 20:
```html
<a href="/categories"{% if request.url.path.startswith("/categories") %} class="active"{% endif %}>Категории</a>
```
Insert an identical-shape line directly after it (per UI-SPEC nav ordering — «Склады» placed right after «Категории», before «Приход»):
```html
<a href="/warehouses"{% if request.url.path.startswith("/warehouses") %} class="active"{% endif %}>Склады</a>
```

---

### `app/main.py` (modify)

**Analog:** existing router registration lines, e.g. line 42 `app.include_router(categories.router)`. Add the import (alongside the other `from app.routes import ...` lines near the top of `main.py`, not read in this session but same convention as the 12 other routers) and one new `app.include_router(warehouses.router)` line, placed near `categories.router` to match nav grouping.

---

### `tests/test_warehouses.py`

**Analog A — service/web CRUD tests:** `tests/test_dictionary.py` (add/update/list coverage shape — not read this session, but RESEARCH.md confirms this is the established test-file shape for a Dictionary-style CRUD service).
**Analog B — migration test:** `tests/test_catalog.py::test_migration_0006_adds_min_sale_cents_column` — shape confirmed by RESEARCH.md's own verified example:
```python
def test_migration_0007_creates_and_seeds_default_warehouse(tmp_path, monkeypatch):
    db_file = tmp_path / "fresh.db"
    monkeypatch.setattr(settings, "db_path", db_file.as_posix())
    cfg = Config("alembic.ini")

    command.upgrade(cfg, "0006")
    command.upgrade(cfg, "head")

    with closing(sqlite3.connect(db_file)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(warehouses)")}
        assert {"id", "name", "address", "created_at", "updated_at", "deleted_at"} <= cols

        rows = conn.execute("SELECT name, deleted_at FROM warehouses").fetchall()
        assert rows == [("Склад по умолчанию", None)]
```
Also add: web test asserting a soft-deleted warehouse STAYS VISIBLE with a restore button (per D-09, the inverse of `Product`'s existing "delete hides" test — do not copy that assertion direction), and a test for the last-active-warehouse warn-but-allow round trip (delete blocked -> confirm=1 -> delete succeeds).

## Shared Patterns

### Soft-delete/restore idempotency
**Source:** `app/services/catalog.py` lines 295-310 (`soft_delete_product`/`restore_product`)
**Apply to:** `app/services/warehouses.py::restore_warehouse` (verbatim shape) and the pre-write-guard section of `soft_delete_warehouse` (None/already-deleted early return).

### Warn-but-allow confirm gate
**Source:** `app/services/sales.py` lines 137-143 (oversell check in `register_sale`)
**Apply to:** `soft_delete_warehouse` (service) and `warehouse_delete` (route) — `confirm` arrives as a `Form("")` string, compared via `confirm == "1"`; the check computing whether the guard fires MUST run before any DB write, and zero rows are staged/committed on the blocked path.

### Route response shape: rows-partial re-render, never `HX-Redirect`
**Source:** `app/routes/dictionary.py` lines 43-61 (all four future warehouse routes must follow this response shape)
**Apply to:** ALL FOUR of `warehouse_add`, `warehouse_update`, `warehouse_delete`, `warehouse_restore` — every one re-renders `partials/warehouse_rows.html`. Do NOT reuse `app/routes/products.py`'s `Response(status_code=200, headers={"HX-Redirect": ...})` shape (RESEARCH.md Pitfall 1).

### Inline row-level error/warning branching
**Source:** `app/templates/partials/dictionary_rows.html` lines 3-10, 24-28, 39-41 (`error_entry_id`/`error_form` pattern)
**Apply to:** `partials/warehouse_rows.html`'s `warning_id` branching (last-active-warehouse delete warning) — same per-row conditional-render technique, new flag name.

### UUID PK + UTC ISO timestamps
**Source:** `app/core.py` (`new_id`, `utcnow_iso` — imported and used identically in every model/service in `app/models.py` and `app/services/dictionary.py`/`catalog.py`)
**Apply to:** `Warehouse` model column defaults and `app/services/warehouses.py`'s `add_warehouse`/`soft_delete_warehouse` writes. Never used inside the migration file itself (WR-06 — migration uses frozen literals only).

## No Analog Found

None — every file in this phase has a strong, verified codebase analog. This phase is explicitly a same-shape extension of three existing precedents (Dictionary CRUD, Product soft-delete/restore, sales.py warn-but-allow), per RESEARCH.md's own summary.

## Metadata

**Analog search scope:** `app/models.py`, `app/routes/`, `app/services/`, `app/templates/pages/`, `app/templates/partials/`, `alembic/versions/`, `app/main.py`, `app/templates/base.html`, `tests/`
**Files read directly this session:** `app/models.py`, `app/routes/dictionary.py`, `app/services/dictionary.py`, `app/templates/pages/dictionary.html`, `app/templates/partials/dictionary_rows.html`, `app/routes/products.py`, `app/services/catalog.py` (soft_delete/restore section), `app/services/sales.py` (confirm-gate section), `app/templates/base.html` (nav section), `app/routes/__init__.py`, `app/main.py` (router registration section), `alembic/versions/` directory listing.
**Pattern extraction date:** 2026-07-11
