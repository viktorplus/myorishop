# Phase 2: Catalog, Dictionary & Search - Pattern Map

**Mapped:** 2026-07-08
**Files analyzed:** 18 new/modified files
**Analogs found:** 15 / 18 (3 have no close analog — patterns provided by 02-RESEARCH.md)

## File Classification

| New/Modified File | Change | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|--------|------|-----------|----------------|---------------|
| `app/services/catalog.py` | NEW | service | CRUD + audit write | `app/services/ledger.py` | role-match |
| `app/services/dictionary.py` | NEW | service | CRUD | `app/services/ledger.py` (read helpers) | role-match |
| `app/services/ledger.py` | MODIFY | service | append-only write | itself (add deleted guard) | exact |
| `app/routes/products.py` | NEW | route | request-response + HTMX partial | `app/routes/ops.py` + `app/routes/home.py` | exact |
| `app/routes/dictionary.py` | NEW | route | request-response + HTMX partial | `app/routes/ops.py` | exact |
| `app/models.py` | MODIFY | model | — | itself (`Product`, `Operation`) | exact |
| `app/main.py` | MODIFY | config | — | itself (router registration) | exact |
| `alembic/versions/0002_catalog_dictionary.py` | NEW | migration | batch DDL | `alembic/versions/0001_initial_schema.py` | exact |
| `app/templates/base.html` | MODIFY | template | — | itself (add nav) | exact |
| `app/templates/pages/products_list.html` | NEW | template | page | `app/templates/pages/home.html` | exact |
| `app/templates/pages/product_form.html` | NEW | template | page (form) | `app/templates/pages/home.html` | role-match |
| `app/templates/pages/dictionary.html` | NEW | template | page (form + rows) | `app/templates/pages/home.html` | role-match |
| `app/templates/partials/product_rows.html` | NEW | template | HTMX partial | `app/templates/partials/ledger_rows.html` | exact |
| `app/templates/partials/dictionary_rows.html` | NEW | template | HTMX partial | `app/templates/partials/ledger_rows.html` | exact |
| `app/templates/partials/name_input.html` | NEW | template | HTMX partial | `app/templates/partials/ledger_rows.html` | role-match |
| `app/templates/partials/price_history.html` | NEW | template | partial/include | `app/templates/partials/ledger_rows.html` (ops table) | exact |
| `tests/test_catalog.py` | NEW | test | unit + integration | `tests/test_ledger.py` + `tests/conftest.py` | exact |
| `tests/test_search.py` | NEW | test | unit | `tests/test_ledger.py` | role-match |
| `tests/test_dictionary.py` | NEW | test | integration (TestClient) | `tests/conftest.py::client` usage | role-match |

## Pattern Assignments

### `app/routes/products.py`, `app/routes/dictionary.py` (routes, request-response + HTMX)

**Analog:** `app/routes/ops.py` (write route, whole file, lines 1–33) and `app/routes/home.py` (read route, lines 13–16)

**Imports + templates access** (`app/routes/ops.py` lines 7–12):
```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.ledger import ledger_view, record_operation
```
Templates come from `app/routes/__init__.py` (shared `Jinja2Templates` with `local_dt` and `cents` filters registered) — never instantiate a second `Jinja2Templates`.

**Write route pattern** (`app/routes/ops.py` lines 17–32) — copy exactly for POST /products, POST /products/{id}, POST /products/{id}/delete, POST /dictionary:
```python
@router.post("/ops")
def create_op(
    request: Request,
    product_id: str = Form(...),
    qty_delta: int = Form(...),
    session: Session = Depends(get_session),
):
    try:
        record_operation(session, type_="correction", product_id=product_id, qty_delta=qty_delta)
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail="unknown product") from exc
    context = ledger_view(session)
    return templates.TemplateResponse(request, "partials/ledger_rows.html", context)
```
Key conventions to copy: plain `def` (sync), typed `Form(...)` as first validation line, ValueError from service → `session.rollback()` + 4xx (never raw 500), HTMX endpoints return partials only.

**Read route pattern** (`app/routes/home.py` lines 13–16) — copy for GET /products, GET /products/{id}/edit, GET /dictionary:
```python
@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    context = ledger_view(session)
    return templates.TemplateResponse(request, "pages/home.html", context)
```

**Deviations from analog required by Phase 2 decisions:**
- Money fields must be `cost: str = Form("")` etc. (NOT `int | None = Form(None)`) — parse via `to_cents` in the service (RESEARCH Pattern 4).
- Lookup endpoint returns `Response(status_code=204)` when nothing should be filled (RESEARCH Pattern 2).
- Use `APIRouter(prefix="/products")` or full paths — either is fine; register both routers in `app/main.py` like lines 10–11.

---

### `app/services/catalog.py` (service, CRUD + audit)

**Analog:** `app/services/ledger.py`

**Imports pattern** (lines 8–13):
```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import OPERATION_TYPES, Operation, Product
```

**Transaction convention (CRITICAL):** `record_operation` (lines 29–72) does `session.get(Product, ...)` (autoflush), stages the Operation, mutates quantity SQL-side, and calls `session.commit()` itself. The catalog service must therefore **stage Product mutations without committing** and let `record_operation`'s commit close the transaction atomically:
```python
# catalog.create_product sketch (follows ledger.py conventions):
product = Product(id=new_id(), code=code, name=name, name_lc=name.lower(), ...)
session.add(product)  # NO commit here
record_operation(session, type_="product_created", product_id=product.id,
                 qty_delta=0, payload={...})  # autoflush inserts product; commit is here
```
For price edits: snapshot old values BEFORE mutating, then one `record_operation(type_="price_change", qty_delta=0, payload={"field": ..., "old_cents": ..., "new_cents": ...})` per changed field (RESEARCH Finding 5, Pitfall 7).

**Read/query pattern** (`ledger_view`, lines 92–110) — copy the select/filter/order idiom:
```python
product = session.scalars(
    select(Product)
    .where(Product.deleted_at.is_(None))
    .order_by(Product.created_at)
    .limit(1)
).first()
operations = session.scalars(
    select(Operation)
    .order_by(Operation.created_at.desc(), Operation.seq.desc())
    .limit(50)
).all()
```
Price history query = same idiom filtered `Operation.product_id == id, Operation.type == "price_change"`, ordered `created_at DESC, seq DESC` (RESEARCH Finding 6). Search query uses `case()` ranking + `LIMIT 20` per RESEARCH Pattern 3 — no codebase analog for `case()`; copy from RESEARCH.

**Docstring style:** module docstring stating the contract (see ledger.py lines 1–6), decision IDs in comments (`# WR-01:`, `# D-09:`).

---

### `app/services/ledger.py` (MODIFY — soft-delete guard)

**Insertion point:** after the unknown-product check, lines 50–52:
```python
product = session.get(Product, product_id)
if product is None:
    raise ValueError(f"unknown product: {product_id!r}")
# ADD HERE (IN-01):
# if product.deleted_at is not None:
#     raise ValueError(f"product is deleted: {product_id!r}")
```
Same ValueError style so routes' existing `except ValueError → 4xx` handling covers it. Existing tests use only active products — suite stays green (verified in tests/test_ledger.py).

---

### `app/models.py` (MODIFY — Product columns, Dictionary model, OPERATION_TYPES)

**Column style to copy** (`Product`, lines 34–42):
```python
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
code: Mapped[str | None] = mapped_column(String(20))
created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
deleted_at: Mapped[str | None] = mapped_column(String(32))
```
New columns follow the same shape: `category: Mapped[str | None] = mapped_column(String(100))`, `cost_cents/sale_cents/catalog_cents: Mapped[int | None] = mapped_column(Integer)`, `name_lc: Mapped[str | None] = mapped_column(String(200), index=True)`.

**OPERATION_TYPES** (line 24) — extend the tuple:
```python
OPERATION_TYPES = ("receipt", "sale", "writeoff", "return", "correction",
                   "price_change", "product_created", "product_edited")
```
No migration needed — migration 0001 has no CHECK on `operations.type` (verified).

**Dictionary model — HARD CONSTRAINT from `tests/test_ledger.py::test_conventions_uuid_cents_utc` (lines 87–99):** every table's PK must be `String(36)` UUID, and no Numeric/Float anywhere. Therefore Dictionary MUST use UUID surrogate PK + `UNIQUE(code)` (RESEARCH Finding 3 resolution 1), following Product's column style plus `Operation.__table_args__` style (line 49) for the unique constraint:
```python
class Dictionary(Base):
    __tablename__ = "dictionary"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
```
Naming convention (lines 15–21) auto-names the unique constraint `uq_dictionary_code`.

---

### `alembic/versions/0002_catalog_dictionary.py` (migration)

**Analog:** `alembic/versions/0001_initial_schema.py`

**Header/frozen style** (lines 1–31): module docstring explaining the migration and the WR-06 immutability rule ("this file must never import app modules"); then:
```python
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None
```

**Table/constraint naming style** (lines 56–89): explicit `sa.Column(...)`, `sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary"))`, `sa.UniqueConstraint("code", name=op.f("uq_dictionary_code"))`, `op.create_index(op.f("ix_products_name_lc"), ...)`.

**Constraints specific to 0002 (from analog docstring + RESEARCH Pattern 6):**
- Plain `op.add_column` only for the 5 nullable products columns — NO batch mode (batch on `operations` would drop the append-only triggers; this migration must not touch `operations` at all).
- `name_lc` backfill in **Python** (`(name or "").lower()` per row via `op.get_bind()`), never `UPDATE ... SET name_lc = lower(name)` — SQLite `lower()` is ASCII-only.
- Downgrade mirrors 0001's (lines 124–129): drop indexes, `op.drop_table("dictionary")`, `op.drop_column` × 5.

---

### Templates: `pages/products_list.html`, `product_form.html`, `dictionary.html`

**Analog:** `app/templates/pages/home.html` (whole file, 17 lines)

**Page skeleton** (lines 1–2, 13–17):
```jinja
{% extends "base.html" %}
{% block content %}
<h1>...</h1>
...
{% include "partials/ledger_rows.html" %}
{% endblock %}
```
RU headings/labels; empty-state fallback like `{% else %}<p>Нет товаров</p>{% endif %}`.

**HTMX form pattern** (home.html lines 6–11):
```jinja
<form hx-post="/ops" hx-target="#ledger" hx-swap="outerHTML" hx-disabled-elt="find button">
  <input type="hidden" name="product_id" value="{{ product.id }}">
  <label for="qty_delta">Изменение количества (±)</label>
  <input type="number" id="qty_delta" name="qty_delta" required>
  <button type="submit">Записать корректировку</button>
</form>
```
Conventions: label+input pairs, `hx-disabled-elt="find button"` on submitting forms, all values autoescaped (`{{ ... }}`, never `|safe`). Search input and code-autofill inputs add `hx-trigger="input changed delay:300ms"` + `hx-sync="this:replace"` per RESEARCH Patterns 1–2 (attributes verified present in vendored htmx 2.0.10).

**`base.html` modification:** current file (15 lines) has no nav — add a `<nav>` inside `<main class="container">` before `{% block content %}` with links Главная / Товары / Справочник. Keep `lang="ru"`, utf-8 meta, local `/static/` assets only (lines 2–8).

---

### Partials: `product_rows.html`, `dictionary_rows.html`, `price_history.html`, `name_input.html`

**Analog:** `app/templates/partials/ledger_rows.html` (whole file, 29 lines)

**Swap-target + table pattern** (lines 1, 8–27):
```jinja
<div id="ledger">
  <table>
    <thead><tr><th>Тип</th><th>Кол-во</th><th>Кто</th><th>Когда</th></tr></thead>
    <tbody>
      {% for op in operations %}
      <tr>
        <td>{{ op.type }}</td>
        <td>{{ op.qty_delta }}</td>
        <td>{{ op.created_by }}</td>
        <td>{{ op.created_at | local_dt }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```
Conventions to copy: partial's root element carries the stable `id` used as `hx-target` (swap `outerHTML`); RU headers; `| local_dt` for timestamps; use `| cents` filter for all money columns (registered in `app/routes/__init__.py` lines 10–11). `price_history.html` is the closest 1:1 copy of this table (columns: Когда / Кто / Поле / Было → Стало). Match highlighting uses the pre/match/post segment approach (RESEARCH Pattern 5) — `<mark>` is literal template HTML, segments autoescaped.

---

### Tests: `test_catalog.py`, `test_search.py`, `test_dictionary.py`

**Analogs:** `tests/conftest.py` (fixtures) + `tests/test_ledger.py` (test style)

**Fixture reuse** (conftest.py): `engine` (tmp_path file-based SQLite + `Base.metadata.create_all` + append-only triggers, lines 17–27), `session` (30–34), `product` (37–48, seeds active «Тестовый товар»), `client` (51–72, TestClient with `get_session` override). New model columns flow in automatically via `create_all` — but only after `app/models.py` is updated, so model changes and tests land in the same wave.

**Service test style** (test_ledger.py lines 22–31):
```python
def test_record_operation_appends_and_updates_projection(session, product):
    record_operation(session, type_="correction", product_id=product.id, qty_delta=5)
    session.expire_all()
    assert product.quantity == 3
```
Copy: docstring citing requirement ID, `session.expire_all()` before asserting refreshed ORM state, `pytest.raises(ValueError, match=...)` + `session.rollback()` for error paths (lines 34–39), raw `text("SELECT COUNT(*)...")` for row-count assertions.

**Route test style:** use the `client` fixture and assert status + RU fragment content; test both the 200-with-fragment and 204 branches of the lookup endpoint.

**Regression requirements:** soft-deleted product → `record_operation` raises ValueError; Cyrillic fixture for search («Губная Помада» found by «губная»); `%`-in-query escape case; 21-product cap case (RESEARCH Wave 0 gaps).

## Shared Patterns

### Single write path (audit)
**Source:** `app/services/ledger.py::record_operation` (lines 29–72)
**Apply to:** every catalog write that changes prices or creates/edits products. Operation rows and `products.quantity` are written ONLY here. Catalog stages Product mutations, `record_operation` commits.

### Grep-gate wording (updated for Phase 2 — RESEARCH Finding 4)
- `session.add(` and Product-field writes: allowed only in `app/services/*.py`; routes stay write-free.
- `Operation` inserts and `quantity` mutation: only in `app/services/ledger.py`.
- No `| safe` in templates; no CDN/http(s) asset URLs; `lang="ru"` retained.

### Helpers — never hand-roll
**Source:** `app/core.py` and `app/routes/__init__.py`
- `to_cents` (comma/dot, ROUND_HALF_UP) for money parsing; `format_cents` via `| cents` filter for display
- `new_id()` for all PKs; `utcnow_iso()` for all timestamps; `| local_dt` for display

### Error handling
**Source:** `app/routes/ops.py` lines 25–30 — service raises `ValueError`; route does `session.rollback()` + `HTTPException(4xx)`. Form validation errors: re-render the form template with an `errors` dict and RU messages (no analog yet; RESEARCH Pattern 4).

### Cyrillic normalization (write-time)
No codebase analog. Rule: `name_lc = name.lower()` (Python) on EVERY create AND update; query strings lowered in Python; `func.lower()` allowed only on `Product.code` (ASCII). Never `func.lower(Product.name)`, never `ilike` on name (RESEARCH Finding 1).

## No Analog Found

| File/Concern | Role | Reason | Fallback |
|--------------|------|--------|----------|
| Search ranking query (`case()` + LIKE escape) | service query | No `case()` usage in Phase 1 | RESEARCH Pattern 3 (verbatim) |
| HTMX active-search / autofill attributes | template | Phase 1 has only plain form posts | RESEARCH Patterns 1–2 (attributes verified in vendored htmx.min.js) |
| Form error re-render with errors dict | route+template | Phase 1 has no form-validation UI | RESEARCH Pattern 4 |

## Metadata

**Analog search scope:** `app/routes/`, `app/services/`, `app/templates/`, `app/models.py`, `app/main.py`, `alembic/versions/`, `tests/`
**Files scanned:** 13 read in full (all Phase 1 source files relevant to this phase)
**Pattern extraction date:** 2026-07-08
