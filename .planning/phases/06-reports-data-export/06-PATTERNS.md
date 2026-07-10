# Phase 6: Reports & Data Export - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 17 (new) + 5 (modified)
**Analogs found:** 17 / 17

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `app/core.py` (+`local_day_bounds_utc`) | utility | transform | `app/core.py::iso_to_local` (same file, same section) | exact |
| `app/config.py` (+`low_stock_threshold`/`stale_days`) | config | request-response | `app/config.py::Settings` (backup fields) | exact |
| `app/models.py` (Product +2 nullable cols) | model | CRUD | `app/models.py::Product` (existing nullable `cost_cents` etc.) | exact |
| `alembic/versions/000X_product_thresholds.py` | migration | batch | `alembic/versions/0003_products_code_active_unique.py` | exact |
| `app/services/reports.py` (sales/profit, writeoffs, top/stale) | service | CRUD (read-only aggregate) | `app/services/operations.py::history_view` (query shape) + `app/services/sales.py` (Python-side aggregation, lines ~125-145) | exact (structure) / role-match (aggregation) |
| `app/services/stock.py` (current + low-stock) | service | CRUD (read-only) | `app/services/operations.py::filter_products` | role-match |
| `app/services/export.py` (3 CSV streams) | service | streaming/file-I/O | `app/services/backup.py` (file listing / streaming-adjacent) | role-match |
| `app/routes/reports.py` | route | request-response | `app/routes/history.py` | exact |
| `app/routes/export.py` | route | streaming | `app/routes/backup.py` | exact |
| `app/templates/pages/reports_sales.html` | template | request-response | `app/templates/pages/history.html` | exact |
| `app/templates/pages/reports_stock.html` | template | request-response | `app/templates/pages/history.html` | role-match |
| `app/templates/pages/reports_writeoffs.html` | template | request-response | `app/templates/pages/history.html` | exact |
| `app/templates/pages/reports_products.html` | template | request-response | `app/templates/pages/history.html` | role-match |
| `app/templates/pages/export.html` | template | request-response | `app/templates/pages/backup.html` | exact |
| `app/templates/partials/period_filter.html` | template | request-response | `app/templates/partials/history_filters.html` | exact |
| `app/templates/partials/sales_report_rows.html` etc. | template | request-response | `app/templates/partials/history_rows.html` | exact |
| `app/main.py` (+`include_router` x2) | config | request-response | `app/main.py` lines 37-47 | exact |
| `app/templates/pages/product_form.html` (+2 threshold fields) | template (modified) | request-response | same file, `cost`/`sale` field blocks (lines 50-60) | exact |
| `app/routes/products.py` / `app/services/catalog.py` (accept 2 new form fields) | controller/service (modified) | CRUD | existing `cost`/`sale` field parse+save path | exact |
| `tests/test_core.py`, `tests/test_reports.py`, `tests/test_export.py` | test | — | `tests/conftest.py` fixtures + existing `tests/test_*.py` style | exact |

## Pattern Assignments

### `app/core.py` — add `local_day_bounds_utc()`

**Analog:** `app/core.py` itself (`iso_to_local`, lines 56-59) — same module, same docstring conventions, same `ZoneInfo` import already present at line 10.

**Pattern to copy** (module already has everything needed — just append):
```python
# app/core.py lines 1-10 (existing imports — extend, don't duplicate)
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo
```
Follow the docstring style of `iso_to_local` (lines 56-59): one-line summary + example in the docstring, no separate comment block. Add `date`, `time`, `timedelta` to the `datetime` import line.

---

### `app/config.py` — add `low_stock_threshold` / `stale_days`

**Analog:** `app/config.py::Settings` — the `backup_*` fields (lines 18-23) are the direct precedent for "new settings block with a comment explaining WHY it's a flag/knob."

**Pattern** (lines 9-24):
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    db_path: str = "data/myorishop.db"
    operator_name: str = "operator"
    device_id: str = "device-01"
    display_tz: str = "Europe/Moscow"
    backup_dir: str = "backups"
    backup_on_startup: bool = True
    backup_keep: int = 30
```
Add `low_stock_threshold: int = 5` / `stale_days: int = 90` with a `# RPT-02/RPT-04 (D-05):` comment referencing the fallback rule, same style as the `# BCK-01 (D-08/D-09/D-10):` comment above `backup_dir`.

---

### `app/models.py` — `Product` gains `low_stock_threshold` / `stale_days`

**Analog:** `app/models.py::Product` — existing nullable `Integer` columns `cost_cents`/`sale_cents`/`catalog_cents` (lines 97-99).

**Pattern** (lines 91-108, especially 97-99):
```python
cost_cents: Mapped[int | None] = mapped_column(Integer)
sale_cents: Mapped[int | None] = mapped_column(Integer)
catalog_cents: Mapped[int | None] = mapped_column(Integer)
```
Add `low_stock_threshold: Mapped[int | None] = mapped_column(Integer)` and `stale_days: Mapped[int | None] = mapped_column(Integer)` in the same block, with a `# D-04/D-05:` comment (mirroring the `# D-19:` comment style above `cost_cents`).

---

### `alembic/versions/000X_product_thresholds.py`

**Analog:** `alembic/versions/0003_products_code_active_unique.py` (full file, 41 lines) — nearest prior products-table migration; also check `0002_catalog_dictionary.py` if it adds plain columns (0003 adds an index, not a column — use it for the header/docstring/"FROZEN copies" convention only).

**Pattern — header and immutability rule** (lines 1-19):
```python
"""<short description>

Revision ID: 000X
Revises: 0004
Create Date: 2026-07-10

<why, referencing D-04/D-05>

Immutability rule (WR-06): this file must never reference application
modules. All values below are FROZEN copies.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "000X"
down_revision = "0004"
branch_labels = None
depends_on = None
```
For adding nullable Integer columns, use `op.add_column("products", sa.Column("low_stock_threshold", sa.Integer(), nullable=True))` (native `add_column`, no batch mode needed for a nullable column add — SQLite supports this directly; confirmed by RESEARCH.md's "native `op.add_column`, no batch mode" note). Mirror `downgrade()` with `op.drop_column`.

---

### `app/services/reports.py` (sales/profit RPT-01, write-offs RPT-03, top/stale RPT-04)

**Analog 1 — query shape & module docstring:** `app/services/operations.py::history_view` (full file, 58 lines)

**Imports pattern** (lines 1-11):
```python
"""Operations read service (OPS-04): the /history browsing slice.

Read-only — no writes happen here. All stock writes still go through the
single write path (app.services.ledger.record_operation). Portable ORM
only, no SQLite-specific SQL (D-05 sync-readiness).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import OPERATION_TYPES, Operation, Product
```
Adapt the docstring for reports.py: state it is 100% read-only (Phase 6 boundary), references RPT-01/03/04, and portability constraint. Add `from sqlalchemy import func` for aggregates.

**Core period-filter pattern** — reuse `select(Operation, Product).join(...)` + `.where(...)` shape (lines 29-38 of `history_view`).

**Analog 2 — Python-side small-cardinality aggregation (for write-off report):** `app/services/sales.py` lines 125-145 (oversell check).

```python
# app/services/sales.py lines 130,134,143 (exact excerpt)
requested_by_product: dict[str, int] = {}
...
requested_by_product[product.id] = requested_by_product.get(product.id, 0) + line["qty"]
...
for product_id, requested in requested_by_product.items()
```
Use `defaultdict` the same way for `writeoff_report` grouping by `reason_code`, iterating `WRITEOFF_REASONS` (from `app/models.py`) for stable RU-labeled order — see RESEARCH.md Pattern 5 for the exact target shape.

**Analog 3 — SQL aggregation (top-selling/stale, RPT-04):** no direct in-repo precedent for `func.sum`/`.group_by()`; use RESEARCH.md Pattern 4 verbatim (SQLAlchemy 2.0 documented idiom) since this codebase has none yet. Follow `history_view`'s `select(...)` / `.order_by()` / `.limit()` chaining style for consistency.

---

### `app/services/stock.py` (current stock + low-stock, RPT-02)

**Analog:** `app/services/operations.py::filter_products` (lines 51-57):
```python
def filter_products(session: Session) -> list[Product]:
    """Active products ordered by name_lc, for the «Товар» history filter."""
    return list(
        session.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
        ).all()
    )
```
Same `session.scalars(select(...).where(deleted_at.is_(None)).order_by(name_lc)).all()` shape for `low_stock_products`. Use `is not None` (never bare `or`) for the effective-threshold fallback per RESEARCH.md Pitfall 3 — see RESEARCH.md Pattern 3 code block for the exact function to copy.

---

### `app/services/export.py` (CSV streams, BCK-02)

**Analog:** `app/services/backup.py` (full file, 121 lines) — closest read-oriented file/stream service; same module docstring convention (decision-ID references), same `list_*`-style read function shape as `list_backups` (lines 59-78).

**Imports & docstring pattern** (lines 1-25):
```python
"""Backup service (BCK-01, D-08/D-09/D-10): VACUUM INTO snapshots + retention.
...
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Operation, Product
```
Adapt: docstring references BCK-02/D-06/D-07; imports add `csv`, `io`, `collections.abc.Generator`, `fastapi.responses.StreamingResponse`, `app.core.format_cents`.

**Core streaming pattern:** use RESEARCH.md's "CSV streaming export" code example verbatim (verified FastAPI-docs-derived pattern; no closer in-repo analog exists since this is the first CSV/streaming feature) — `_csv_rows()` generator + `encoded()` wrapper emitting `utf-8-sig` on the first chunk only, `;` delimiter (Pitfall 4), server-hardcoded filenames only (V12, matches `backup.py`'s "NEITHER endpoint accepts a filename" comment at lines 3-7).

---

### `app/routes/reports.py`

**Analog:** `app/routes/history.py` (full file, 53 lines) — closest thin-route-over-read-service precedent, including the htmx-vs-full-page branching pattern relevant to `period_filter.html` partial swaps.

**Imports + route pattern** (lines 1-21):
```python
"""History page (OPS-04): thin route, read-only via app/services/operations.py."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.operations import filter_products, history_view

router = APIRouter()


@router.get("/history")
def history_page(
    request: Request,
    type: str = "",
    product: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    result = history_view(session, type_filter=type or None, product_id=product or None, page=page)
```
For date-range query params (`from`/`to`, `preset`), wrap `date.fromisoformat()` in `try/except ValueError` per RESEARCH.md's V5 security note — no existing in-repo precedent for this validation; add it fresh, falling back to a safe default (e.g. today) rather than raising a 500.

**HX-Request branching pattern** (lines 41-52) — copy directly: full-page render vs. rows-only partial keyed off `request.headers.get("HX-Request")`.

---

### `app/routes/export.py`

**Analog:** `app/routes/backup.py` (full file, 58 lines) — exact structural match: a GET page route + POST/GET action routes, zero client-supplied filename/path parameters (V12).

**Imports + page route pattern** (lines 1-34):
```python
"""Backup pages (BCK-01): thin routes, all file/VACUUM work in the service.

Security V12 / T-3-09: NEITHER endpoint accepts a filename, path, Form or
Query parameter — the list is a server-side glob of settings.backup_dir
only, ...
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services import backup as backup_service

router = APIRouter()

...

@router.get("/backup")
def backup_page(request: Request):
    context = {
        "backups": backup_service.list_backups(Path(settings.backup_dir)),
        "message": None,
        "error": None,
    }
    return templates.TemplateResponse(request, "pages/backup.html", context)
```
For `/export/{entity}.csv` routes, return `export_service.stream_products_csv(session)` etc. directly (the service function itself returns a `StreamingResponse` per RESEARCH.md's code example) — no template involved for the CSV routes, only for `GET /export`.

---

### Templates: `reports_*.html`, `export.html`, `period_filter.html`, `*_rows.html`

**Analog for report pages:** `app/templates/pages/history.html` (full file, 29 lines):
```html
{% extends "base.html" %}
{% block content %}
<h1>История операций</h1>

{% include "partials/history_filters.html" %}

<table>
  <thead>
    <tr>...</tr>
  </thead>
  <tbody id="history-tbody">
    {% include "partials/history_rows.html" %}
  </tbody>
</table>
{% endblock %}
```
Each `reports_*.html` extends `base.html`, includes a shared `partials/period_filter.html` (for RPT-01/03/04 — omit for RPT-02 per D-03) followed by a `<table>` + `{% include "partials/<name>_rows.html" %}`.

**Analog for `export.html`:** `app/templates/pages/backup.html` (full file, 22 lines) — three `hx-get` download buttons instead of one `hx-post`; same "simple page listing available downloads" ergonomics per CONTEXT.md's explicit instruction.

**Analog for `period_filter.html`:** `app/templates/partials/history_filters.html` — read this partial before writing (not yet read in this pass; same directory/convention as `backup_list.html`/`history_rows.html` already inspected — Grep confirms it exists at `app/templates/partials/history_filters.html`).

**Shared template env:** all new templates use `app/routes/__init__.py`'s existing `templates` object — never re-instantiate `Jinja2Templates`. Its `local_dt`/`cents` filters (lines 11-12) and `WRITEOFF_REASONS`/`OPERATION_TYPE_LABELS` globals (lines 15-16) are directly reusable for the write-off report grouping display.

---

### `app/main.py` — register new routers

**Analog:** existing `include_router` block (lines 37-47):
```python
app.include_router(home.router)
app.include_router(products.router)
app.include_router(dictionary.router)
app.include_router(receipts.router)
app.include_router(sales.router)
app.include_router(customers.router)
app.include_router(backup.router)
app.include_router(writeoffs.router)
app.include_router(returns.router)
app.include_router(corrections.router)
app.include_router(history.router)
```
Append `app.include_router(reports.router)` and `app.include_router(export.router)`, plus the matching top-of-file import lines (mirror however `backup`/`history` are imported above line 37 — not yet inspected but same-file, trivial one-line addition each).

---

### `app/templates/pages/product_form.html` — add threshold fields

**Analog:** same file's `cost`/`sale` field blocks (lines 50-60):
```html
<div class="field">
  <label for="cost">Закупочная цена <span class="muted">(необязательно)</span></label>
  <input type="text" id="cost" name="cost" inputmode="decimal" placeholder="0,00" value="{% if form %}{{ form.cost or '' }}{% elif product and product.cost_cents is not none %}{{ product.cost_cents | cents }}{% endif %}">
  {% if errors.cost %}<p class="error">{{ errors.cost }}</p>{% endif %}
</div>
```
Add two analogous `<div class="field">` blocks for `low_stock_threshold`/`stale_days` — plain integer inputs (`inputmode="numeric"`, no `| cents` filter since these are unit counts / day counts, not money), same `{% if form %}...{% elif product %}...{% endif %}` value-fallback and `{% if errors.X %}` pattern.

---

## Shared Patterns

### Read-only service module docstring convention
**Source:** `app/services/operations.py` lines 1-6
**Apply to:** `reports.py`, `stock.py`, `export.py`
```python
"""<Feature> read service (<REQ-ID>): <one-line purpose>.

Read-only — no writes happen here. ... Portable ORM only, no
SQLite-specific SQL (sync-readiness).
"""
```

### Shared `templates` env — never re-instantiate
**Source:** `app/routes/__init__.py` (full file, 17 lines)
**Apply to:** every new route module
```python
from app.routes import templates
```

### HX-Request full-page vs. partial branching
**Source:** `app/routes/history.py` lines 41-52
**Apply to:** all period-filterable report routes (`reports_sales`, `reports_writeoffs`, `reports_products`)

### Money — never recompute, always read frozen snapshot
**Source:** `app/models.py::Operation` (`unit_cost_cents`/`unit_price_cents`, lines 140-141) + CONTEXT.md D-11/D-12 reference
**Apply to:** `reports.py` sales/profit + top-selling functions — read `Operation.unit_cost_cents`/`unit_price_cents`, never `Product.cost_cents`/`sale_cents`.

### Effective-threshold fallback — explicit `is not None`
**Source:** RESEARCH.md Pattern 3 (no in-repo precedent yet; Pitfall 3 explicitly warns against bare `or`)
**Apply to:** `stock.py::effective_low_stock_threshold`, `reports.py` stale-product filter
```python
def effective_low_stock_threshold(product: Product) -> int:
    return product.low_stock_threshold if product.low_stock_threshold is not None else settings.low_stock_threshold
```

### V12 — no client-controlled filenames/paths
**Source:** `app/routes/backup.py` lines 3-7 comment + route bodies (no Form/Query filename params anywhere)
**Apply to:** `app/routes/export.py` — CSV filenames are hardcoded `products.csv`/`sales.csv`/`customers.csv` server-side, identical to backup's pattern.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| SQL `func.sum`/`func.max`/`.group_by()` aggregate queries (inside `reports.py`, RPT-04) | service (query) | batch/transform | No existing query in this codebase uses SQLAlchemy `.group_by()`/aggregate functions yet — RESEARCH.md Pattern 4 is the sole reference; treat it as authoritative since it is a documented SQLAlchemy 2.0 idiom, not a guess. |
| `StreamingResponse` CSV generator with single-BOM-chunk handling (`export.py`) | service | streaming | First streaming-response feature in the codebase; use RESEARCH.md's verified FastAPI-docs-derived code example directly. |
| `local_day_bounds_utc()` local-midnight→UTC conversion | utility | transform | `iso_to_local` in `app/core.py` only goes UTC→local; the inverse direction is new. Use RESEARCH.md Pattern 1 code block verbatim. |

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/pages/`, `app/templates/partials/`, `app/models.py`, `app/core.py`, `app/config.py`, `alembic/versions/`, `app/main.py`
**Files scanned:** ~20 (operations.py, backup.py, sales.py, history.py, backup.py routes, __init__.py, config.py, models.py, core.py, 0003 migration, backup.html, history.html, product_form.html, main.py)
**Pattern extraction date:** 2026-07-10
