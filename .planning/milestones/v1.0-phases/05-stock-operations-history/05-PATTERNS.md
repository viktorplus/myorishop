# Phase 5: Stock Operations & History - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 20 new/modified (3 services + optional read helper, 4 routes, ~8 templates, 1 constant edit, 4 tests, 2 wiring edits)
**Analogs found:** 20 / 20 (every target has a shipped analog — pure internal wiring, no new infrastructure)

All new stock writes go through `app/services/ledger.py::record_operation` (single write path). No Alembic migration expected: `writeoff`/`return`/`correction` are already in `OPERATION_TYPES` (`app/models.py:34-43`); `Operation.payload`/`sale_id` and `ix_operations_sale_id` already exist.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/writeoffs.py` | service | CRUD (append) | `app/services/receipts.py` (`register_receipt`, `lookup_prefill`) | exact |
| `app/services/returns.py` | service | CRUD (append) + aggregate | `app/services/sales.py` (`register_sale` freeze) + `app/services/customers.py` (`purchase_history` agg query) | role-match |
| `app/services/corrections.py` | service | CRUD (append) | `app/routes/ops.py` (logic to migrate) + `app/services/receipts.py` (validation shape) | role-match |
| `app/services/operations.py` (optional history read helper) | service | request-response (read) | `app/services/sales.py::recent_sales` + `app/services/ledger.py::ledger_view` | exact |
| `app/routes/writeoffs.py` | route | request-response | `app/routes/receipts.py` | exact |
| `app/routes/returns.py` | route | request-response | `app/routes/sales.py` + `app/routes/receipts.py` | exact |
| `app/routes/corrections.py` (REPLACES `app/routes/ops.py`) | route | request-response | `app/routes/receipts.py` + `app/routes/ops.py` | exact |
| `app/routes/history.py` | route | request-response (read, query params) | `app/routes/receipts.py::receipt_new_page` | role-match |
| `app/templates/pages/writeoff_form.html` | template | — | `app/templates/pages/receipt_form.html` | exact |
| `app/templates/partials/writeoff_form.html` | template | — | `app/templates/partials/receipt_form.html` | exact |
| `app/templates/partials/writeoff_lookup.html` | template | — | `app/templates/partials/receipt_lookup.html` | exact |
| `app/templates/pages/correction_form.html` (+ partial) | template | — | `app/templates/partials/receipt_form.html` + `pages/home.html` form | role-match |
| return entry (extend `partials/recent_sales.html` / `partials/purchase_history.html` + a `return_confirm.html`) | template | — | `app/templates/partials/recent_sales.html`, `purchase_history.html`, `sale_oversell.html` | exact |
| `app/templates/pages/history.html` | template | — | `app/templates/pages/receipt_form.html` (page shell) | role-match |
| `app/templates/partials/history_rows.html` | template | — | `app/templates/partials/ledger_rows.html` (+ `recent_sales.html` columns) | role-match |
| `app/templates/base.html` (nav link, MODIFY) | template | — | existing nav `<a>` entries (lines 17-25) | exact |
| `app/models.py` constants (ADD `WRITEOFF_REASONS`, `OPERATION_TYPE_LABELS`) | config | — | `OPERATION_TYPES` tuple (`app/models.py:34-43`) | exact |
| `app/main.py` (register new routers, MODIFY) | config | — | `app/main.py:8, 25-32` | exact |
| `tests/test_writeoffs.py` | test | — | `tests/test_sales.py` + `tests/test_ledger.py` | exact |
| `tests/test_returns.py` | test | — | `tests/test_sales.py` + `tests/test_ledger.py` | exact |
| `tests/test_corrections.py` | test | — | `tests/test_ledger.py` | exact |
| `tests/test_history.py` | test | — | `tests/test_sales.py` (client tests) | role-match |

## Pattern Assignments

### `app/services/writeoffs.py` (service, append-CRUD)

**Analog:** `app/services/receipts.py::register_receipt` (validation + single-line ledger write) and `lookup_prefill`/`recent_receipts` (read helpers).

**Signature to copy** (mirror `register_receipt` return contract `(result|None, errors)`):
```python
def register_writeoff(session, *, code, name, qty_raw, reason_code, note) -> tuple[dict | None, dict[str, str]]:
```

**Validation pattern** — copy the qty guard, but use the **`.isascii()` fix from `sales.py:92-93`** (receipts.py:58 lacks it):
```python
qty_text = qty_raw.strip()
qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
if qty <= 0:
    errors["quantity"] = "Укажите количество — целое число больше нуля."
if reason_code not in WRITEOFF_REASONS:          # server-side allow-list (V5)
    errors["reason"] = "Выберите причину списания."
```

**Active-only product lookup** (copy verbatim from `receipts.py:71-73`):
```python
product = session.scalars(
    select(Product).where(Product.code == code, Product.deleted_at.is_(None))
).first()
if product is None:
    return None, {"code": f"Товар с кодом „{code}“ не найден."}
```

**Ledger write** (negative delta, reason in payload; model on `receipts.py:124-133`):
```python
op = record_operation(
    session, type_="writeoff", product_id=product.id,
    qty_delta=-qty, payload={"reason_code": reason_code, "note": note.strip()},
    commit=True,
)
```
Wrap in `try/except (IntegrityError, ValueError): session.rollback()` exactly like `sales.py:183-185`.

**Lookup + recent helpers:** copy `lookup_prefill` (`receipts.py:145-172`) but return **name only, no price fields** (D-04); copy `recent_receipts` (`receipts.py:175-184`) filtering `Operation.type == "writeoff"`.

---

### `app/services/returns.py` (service, append-CRUD + aggregate)

**Analogs:** `app/services/sales.py:174` (frozen `unit_cost_cents`/`unit_price_cents` snapshot) and `app/services/customers.py::purchase_history` (`func.sum` aggregate query joining on `sale_id`).

**Returnable-qty aggregation** (new logic; query style from `customers.py:152-158` + `ledger.py:95-98`):
```python
from sqlalchemy import func, select
def returnable_qty(session, sale_id, product_id):
    sold = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.sale_id == sale_id, Operation.product_id == product_id,
            Operation.type == "sale")) or 0
    returned = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.sale_id == sale_id, Operation.product_id == product_id,
            Operation.type == "return")) or 0
    return (-sold) - returned   # positive remaining
```

**Return write — copy the FROZEN origin op snapshot** (Pitfall 2 / D-07 — never read `Product.*_cents`). Fetch the clicked origin `sale` op and copy its amounts (mirrors `sales.py:169-178` freeze but reversed sign):
```python
origin = session.get(Operation, origin_op_id)   # the clicked recent-sales / purchase-history row
if qty > returnable_qty(session, origin.sale_id, origin.product_id):
    return None, {"quantity": "Нельзя вернуть больше, чем было продано."}
op = record_operation(
    session, type_="return", product_id=origin.product_id,
    qty_delta=+qty, unit_price_cents=origin.unit_price_cents,
    unit_cost_cents=origin.unit_cost_cents, sale_id=origin.sale_id,
    payload={"origin_op_id": origin.id}, commit=True,
)
```
Guard soft-deleted origin product (`record_operation` raises `ValueError` — Pitfall 7): catch and surface an RU 4xx, same as `ops.py:27-30`.

---

### `app/services/corrections.py` (service, append-CRUD) — REPLACES `app/routes/ops.py` logic (D-12)

**Analog:** current `app/routes/ops.py:24-30` (the raw-delta correction to migrate) + `receipts.py` validation shape.

**Two-mode arithmetic + zero-net rejection** (D-09/D-10; use cached `Product.quantity`, NOT `compute_stock`, per `sales.py:126-128` A4):
```python
def register_correction(session, *, code, mode, value_raw, note) -> tuple[dict | None, dict]:
    if mode not in ("count", "delta"):          # allow-list (V5)
        return None, {"mode": "Неверный режим."}
    # ... resolve active product by code (copy receipts.py:71-73) ...
    if mode == "count":
        qty_delta = counted - product.quantity   # counted = parsed absolute int
    else:
        qty_delta = entered                       # signed int, delta mode
    if qty_delta == 0:
        return None, {"quantity": "Количество не изменилось — нечего записывать."}
    op = record_operation(
        session, type_="correction", product_id=product.id,
        qty_delta=qty_delta, payload={"note": note.strip() or None, "mode": mode},
        commit=True,
    )
```
Note: `count` mode needs an unsigned-int parse; `delta` mode needs a **signed** int parse (accept leading `-`), so the `isascii()+isdigit()` guard must handle a sign for delta. Keep the ValueError catch from `ops.py:27-30`.

**Migration duty:** delete `app/routes/ops.py`, remove `ops` from `app/main.py:8,26`, and update `app/templates/pages/home.html:6-11` (its form posts to `/ops`) to point at the new correction route or be simplified (D-17 discretion).

---

### `app/services/operations.py` — history read helper (OPS-04)

**Analog:** `app/services/sales.py::recent_sales` (`sales.py:219-228`) generalized — same `select(Operation, Product).join(...)` + `order_by(created_at.desc(), seq.desc())`.

**Filter + paginate query** (fetch-one-extra sentinel for "has next"):
```python
def history_view(session, *, type_filter=None, product_id=None, page=0, page_size=50):
    stmt = (select(Operation, Product)
            .join(Product, Operation.product_id == Product.id)
            .order_by(Operation.created_at.desc(), Operation.seq.desc()))
    if type_filter:  stmt = stmt.where(Operation.type == type_filter)
    if product_id:   stmt = stmt.where(Operation.product_id == product_id)
    rows = session.execute(stmt.limit(page_size + 1).offset(page * page_size)).all()
    has_next = len(rows) > page_size
    return {"rows": [{"op": op, "product": p} for op, p in rows[:page_size]],
            "has_next": has_next, "page": page}
```
Portable ORM only — no SQLite-specific SQL.

---

### `app/routes/writeoffs.py` / `returns.py` / `corrections.py` (thin routes)

**Analog:** `app/routes/receipts.py` (whole file) — page GET, lookup GET (204 pattern), POST create with 422-on-error.

**Router + template import** (copy `receipts.py:1-16`):
```python
from fastapi import APIRouter, Depends, Form, Request, Response
from app.db import get_session
from app.routes import templates
router = APIRouter()
```

**204 lookup pattern** (copy `receipts.py:30-62` — server decides fill vs 204; never overwrite typed name):
```python
if name.strip():
    return Response(status_code=204)
result = lookup_prefill(session, code)
if result is None:
    return Response(status_code=204)
```

**POST create with block-error + 422** (copy `receipts.py:65-126` / `sales.py:186-208`): typed `Form("")` string inputs (never `int | None` — Pydantic rejects `""`), `try/except Exception → logger.exception → 422 partial`, then `if errors: → 422 partial`, then success partial with fresh form + oob recent list. Return validation partials with `status_code=422` (base.html htmx-config opts 422 into swapping — Pitfall 6).

**History route** (query params, no writes): `GET /history` with `type: str = ""`, `product: str = ""`, `page: int = 0` query params → `history_view(...)` → render `pages/history.html`.

**Register in `app/main.py`:** add `writeoffs, returns, corrections, history` to the import (`main.py:8`) and `app.include_router(...)` block (`main.py:25-32`); remove `ops`.

---

### `app/templates/partials/history_rows.html` (extend `ledger_rows.html`)

**Analog:** `app/templates/partials/ledger_rows.html` (table shell) + `recent_sales.html:22-30` (product code/name, signed qty, `| cents`, `| local_dt` columns).

`ledger_rows.html` today is single-product (stock-summary block + 4 cols: type/qty/who/when). Create a **NEW** partial with columns: type (RU via `OPERATION_TYPE_LABELS`), product (name/code), qty (`{{ op.qty_delta }}` signed), unit price/cost (`| cents` where not none, `—` fallback like `purchase_history.html:25-26`), reason (payload-derived), who (`op.created_by`), when (`op.created_at | local_dt`).

**RU type label + reason** (autoescape only — payload note is untrusted, Pitfall / T-4-01):
```jinja
<td>{{ OPERATION_TYPE_LABELS.get(r.op.type, r.op.type) }}</td>
...
{# reason: writeoff -> WRITEOFF_REASONS[code] label + note; correction -> note #}
```
Pass `OPERATION_TYPE_LABELS`/`WRITEOFF_REASONS` into the template context from the route (or register as a Jinja global). Never `|safe`.

---

### `app/models.py` — new constants (ADD, next to `OPERATION_TYPES:34-43`)

```python
WRITEOFF_REASONS = {   # code -> RU label (store latin code, render RU) — D-03
    "damaged": "Брак", "expired": "Просрочка", "lost": "Потеря",
    "personal": "Личное использование", "gift": "Подарок", "other": "Прочее",
}
OPERATION_TYPE_LABELS = {   # latin type -> RU label for /history «Тип» column
    "receipt": "Приход", "sale": "Продажа", "writeoff": "Списание",
    "return": "Возврат", "correction": "Корректировка", "price_change": "Цена",
    "product_created": "Создан", "product_edited": "Изменён",
}
```

---

### `app/templates/base.html` — nav link (MODIFY, line 17-25)

Add one entry mirroring existing nav `<a>` shape (`base.html:20`):
```jinja
<a href="/history"{% if request.url.path.startswith("/history") %} class="active"{% endif %}>История</a>
```

---

### Tests (`tests/test_{writeoffs,returns,corrections,history}.py`)

**Analog:** `tests/test_sales.py` (service + `test_web_` client tests) and `tests/test_ledger.py` (assertion style).

**Assertion pattern** (copy `test_ledger.py:22-32`): mutate via service → `session.expire_all()` → assert `product.quantity` AND `compute_stock(session, pid)` agree → count rows via `select`/`text("SELECT COUNT(*)...")`.

**Fixtures (no new ones needed — `conftest.py`):** `stocked_product` (8 in stock via receipt op) for write-off/correction; build a real sale for return tests by calling `register_sale` or `record_operation(type_="sale", qty_delta=-n, sale_id=header.id, unit_price_cents=..., unit_cost_cents=...)` then assert return copies those frozen amounts.

Key assertions: write-off → `op.payload["reason_code"]`, allow-list rejection; return → `op.qty_delta > 0`, `op.sale_id`, `op.unit_price_cents == origin`, over-return rejected; correction → count vs delta arithmetic, zero-net writes 0 rows, `/ops` route gone; history → newest-first order, type+product filters, bounded page.

## Shared Patterns

### Single write path (ALL three write services)
**Source:** `app/services/ledger.py:29-90` (`record_operation`)
**Apply to:** writeoffs, returns, corrections.
```python
record_operation(session, type_=..., product_id=..., qty_delta=<signed>,
                 unit_cost_cents=..., unit_price_cents=..., payload=..., sale_id=..., commit=True)
```
Never write `operations` rows or `products.quantity` directly. It stamps `seq`/`created_at`/`created_by`/`device_id` and guards unknown/soft-deleted products (raises `ValueError`).

### Rollback / block-error (all write services + routes)
**Source:** `app/services/sales.py:183-185` (service) + `app/routes/sales.py:195-208` (route)
```python
try:
    ... record_operation ...; session.commit()
except (IntegrityError, ValueError):
    session.rollback(); return None, {"form": "Не удалось сохранить. Попробуйте ещё раз."}
```
Route wraps the service call in `try/except Exception: logger.exception(...) → 422 partial` — never a raw 500 (V7).

### 204 code→name autofill (write-off form, optional correction form)
**Source:** `app/routes/receipts.py:30-62` + `app/templates/partials/receipt_form.html:24-38` + `receipt_lookup.html`
Debounced `hx-get` (`input changed delay:300ms`), server answers 204 when nothing to fill, typed name never overwritten (`hx-on::before-swap` guard, `receipt_form.html:18-21`).

### Focus-back-to-code after HTMX swap (all forms)
**Source:** `app/templates/partials/receipt_form.html:5`
```jinja
<div id="..."{% if focus_code %} hx-on::load="document.getElementById('code').focus()"{% endif %}>
```
`autofocus` does NOT fire inside swapped content (Pitfall 5).

### 422 swap opt-in (all validation partials)
**Source:** `app/templates/base.html:9-10` (htmx-config meta — already global)
Return validation partials with `status_code=422`; htmx swaps them because base.html opts `422` in. Nothing to add — just use `status_code=422`.

### Money / timestamp rendering (history + any amount)
**Source:** `app/routes/__init__.py:8-12` (registered `| cents`, `| local_dt` filters)
Never format cents/timestamps ad-hoc. Write-off/correction carry no price; return copies frozen cents rendered via `| cents`.

### Autoescape-only output (history reason, product names)
**Source:** convention in `recent_sales.html:3-4`, `purchase_history.html:1-3`
Never `|safe` on payload notes or product names (stored-XSS T-4-01).

## No Analog Found

None. Every target file has a shipped Phase 1–4 analog. The only genuinely new logic (returnable-qty aggregation, count/delta arithmetic, paginated history query) is composed from existing query/validation primitives, not new infrastructure.

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/{pages,partials}/`, `app/models.py`, `tests/`
**Files scanned (read in full or targeted):** ledger.py, receipts.py + route, sales.py + route, customers.py, ops.py, models.py, main.py, __init__.py, ledger_rows.html, receipt_form.html (page+partial), recent_sales.html, purchase_history.html, base.html, home.html, conftest.py, test_ledger.py, test_sales.py
**No migration:** confirmed — `OPERATION_TYPES` (models.py:34-43), `Operation.payload`/`sale_id` (models.py:117-124), `ix_operations_sale_id` all pre-exist. Do NOT add migration 0005; never `batch_alter_table("operations")` (drops append-only triggers).
**Pattern extraction date:** 2026-07-09
</content>
</invoke>
