# Phase 4: Sales & Customers - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 24 (new/modified)
**Analogs found:** 24 / 24 (every new file has a proven in-repo analog)

> Grounding: every excerpt below was read from the live source, not paraphrased.
> Stack rules (CLAUDE.md): money = integer cents (`to_cents`/`format_cents`), UUID PKs (`new_id`), UTC ISO text (`utcnow_iso`), ORM-only portable SQL, Cyrillic folded in Python, autoescape only (never `|safe`). Thin routes / fat services. ALL stock writes ONLY through `record_operation`, staged `commit=False`, ONE commit per request.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/sales.py` (NEW) | service | CRUD / transactional write | `app/services/receipts.py` | exact (basket = multi-line receipt) |
| `app/services/customers.py` (NEW) | service | CRUD + search | `app/services/catalog.py` (CRUD/search) + `app/services/dictionary.py` (204 lookup) | exact |
| `app/routes/sales.py` (NEW) | route | request-response + HTMX partials | `app/routes/receipts.py` | exact |
| `app/routes/customers.py` (NEW) | route | CRUD + search partial | `app/routes/products.py` + `app/routes/dictionary.py` | exact |
| `app/models.py` (MODIFY) | model | schema | existing `Product`/`Dictionary`/`Operation` in same file | exact |
| `app/services/ledger.py` (MODIFY) | service | transactional write | existing `record_operation` signature | exact (add one kwarg) |
| `alembic/versions/0004_*.py` (NEW) | migration | schema | `0002_catalog_dictionary.py` (native ADD COLUMN) + `0001` (FK/index/table) | exact |
| `app/templates/pages/sale_form.html` (NEW) | template (page) | render | `pages/receipt_form.html` | exact |
| `app/templates/partials/sale_form.html` (NEW) | template (partial) | HTMX swap whole | `partials/receipt_form.html` | exact |
| `app/templates/partials/sale_row.html` (NEW) | template (partial) | HTMX beforeend + oob | `partials/receipt_price_inputs.html` (oob field fragment) | role-match |
| `app/templates/partials/sale_lookup.html` (NEW) | template (partial) | HTMX fill fragment | `partials/receipt_lookup.html` | exact |
| `app/templates/partials/sale_oversell.html` (NEW) | template (partial) | HTMX warning block | `.error-block` pattern in `partials/receipt_form.html` | role-match |
| `app/templates/partials/customer_picker.html` (NEW) | template (partial) | HTMX search rows + `<mark>` | `partials/product_rows.html` | exact |
| `app/templates/partials/recent_sales.html` (NEW) | template (partial) | oob-refresh list | `partials/receipt_rows.html` | exact |
| `app/templates/pages/customers_list.html` (NEW) | template (page) | search page | `pages/products_list.html` | exact |
| `app/templates/partials/customer_rows.html` (NEW) | template (partial) | HTMX search rows | `partials/product_rows.html` | exact |
| `app/templates/pages/customer_form.html` (NEW) | template (page) | form | `pages/product_form.html` (stacked-form) | role-match |
| `app/templates/pages/customer_detail.html` (NEW) | template (page) | render + history table | `pages/products_list.html` + `partials/receipt_rows.html` | role-match |
| `app/templates/partials/purchase_history.html` (NEW) | template (partial) | history table | `partials/receipt_rows.html` | exact |
| `app/templates/base.html` (MODIFY) | template | nav | existing nav links | exact |
| `app/main.py` (MODIFY) | config | router include | existing `include_router` block | exact |
| `tests/test_sales.py` (NEW) | test | service + web slice | `tests/test_receipts.py` | exact |
| `tests/test_customers.py` (NEW) | test | service + web slice | `tests/test_receipts.py` + `tests/test_catalog.py` | exact |
| `tests/conftest.py` (MODIFY) | test fixture | fixtures | existing `product` fixture | exact |

---

## Pattern Assignments

### `app/services/ledger.py` (MODIFY — add ONE keyword param)

**Analog:** the function being edited (`record_operation`, lines 29-84).

**Current signature (lines 29-39):**
```python
def record_operation(
    session: Session,
    *,
    type_: str,
    product_id: str,
    qty_delta: int,
    unit_cost_cents: int | None = None,
    unit_price_cents: int | None = None,
    payload: dict | None = None,
    commit: bool = True,
) -> Operation:
```

**Change (backward compatible — Pitfall 3):** add `sale_id: str | None = None` after `payload`, and pass it into the `Operation(...)` constructor (currently lines 65-77):
```python
    op = Operation(
        id=new_id(),
        type=type_,
        product_id=product_id,
        qty_delta=qty_delta,
        unit_cost_cents=unit_cost_cents,
        unit_price_cents=unit_price_cents,
        payload=payload,
        sale_id=sale_id,                       # NEW — set at INSERT time only
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
    )
```
All 5 existing callers (`catalog.create_product`, `catalog.update_product`, `receipts.register_receipt` ×3 types) keep working untouched — `sale_id` defaults to `None`. **Why it must be a kwarg on this function, not a later UPDATE:** the `operations_no_update` trigger ABORTs any UPDATE, so `sale_id` is unsettable after insert.

**Reuse as-is:** `compute_stock` (lines 87-93) is the oversell/stock read helper; the cached `Product.quantity` (maintained at line 81 `product.quantity = Product.quantity + qty_delta`) is authoritative for the oversell check (RESEARCH A4).

---

### `app/models.py` (MODIFY — add `Customer`, `Sale`, `Operation.sale_id`)

**Analog:** existing `Product`/`Dictionary`/`Operation` classes in the same file.

**Conventions to mirror (from `Product` lines 66-83, `Dictionary` lines 96-100):** `String(36)` UUID PK `default=new_id`; `created_at`/`updated_at` `String(32)` with `default=utcnow_iso`, `updated_at` also `onupdate=utcnow_iso`; a `name_lc`/`search_lc` `String(...)` `index=True` Cyrillic shadow maintained by the SERVICE (never SQL `lower()` — see `Product.name_lc` comment lines 75-77). Naming convention dict (lines 24-30) auto-names every FK/index/UQ — declare FKs with `name=op.f(...)`-compatible names.

**New column on `Operation`** (Pattern 1 in RESEARCH; add after `payload`, line 117):
```python
sale_id: Mapped[str | None] = mapped_column(
    ForeignKey("sales.id", name="fk_operations_sale_id_sales"), index=True
)
```
Declaring the ORM `ForeignKey` makes the Unit-of-Work insert the `Sale` header BEFORE the sale ops in one flush (satisfies `foreign_keys=ON` — Pitfall 2). `Operation` already carries `unit_cost_cents`/`unit_price_cents` (lines 115-116) — the SAL-05 snapshot columns; **no schema change needed for the snapshot.** `OPERATION_TYPES` (lines 34-43) already includes `"sale"` — no edit there.

**New models** (see RESEARCH Code Example 2 for the full field list): `Customer` (id, name NOT NULL, surname nullable, consultant_number nullable, `search_lc` indexed, created_at/updated_at) and `Sale` (id, `customer_id` nullable FK→customers with `index=True`, created_at NOT NULL, created_by NOT NULL, optional nullable `device_id`).

---

### `app/services/sales.py` (NEW — service, transactional basket write)

**Analog:** `app/services/receipts.py` (`register_receipt` lines 30-142, `lookup_prefill` 145-172, `recent_receipts` 175-184).

**Imports pattern (receipts.py lines 17-25):**
```python
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Operation, Product, Sale
from app.services.catalog import parse_optional_cents
from app.services.ledger import record_operation
```

**Service return contract (receipts.py line 39, 47-68):** `-> tuple[dict | None, dict[str, str]]`; strip inputs, accumulate RU errors in a dict, `if errors: return None, errors` BEFORE staging anything (zero writes on any validation error).

**Money/qty parsing — reuse verbatim:** `parse_optional_cents(raw, errors, field)` from `catalog.py` (lines 21-30) for prices; qty via the receipts.py idiom (lines 57-60):
```python
qty_text = qty_raw.strip()
qty = int(qty_text) if qty_text.isdigit() else 0
if qty <= 0:
    errors["quantity"] = QTY_ERROR   # "Укажите количество — целое число больше нуля."
```
**D-12 divergence from receipts:** sale PRICE is required per line → RU error «Укажите цену продажи.» when empty/invalid; COST is frozen from the card and may be `None` (no block). Do NOT reuse receipts' "empty price = None, no error" for the sale price field.

**Active-product-by-code resolution — copy receipts.py lines 71-73:**
```python
product = session.scalars(
    select(Product).where(Product.code == code, Product.deleted_at.is_(None))
).first()
```
Unknown code on a line → RU error «Товар с кодом „{code}" не найден. Сначала оприходуйте товар.» (UI-SPEC copy), zero writes.

**Basket ONE-transaction write (Pattern 2 — mirror receipts.py's staged commit=False + single commit at lines 90-142):**
```python
header = Sale(id=new_id(), customer_id=customer_id or None,
              created_at=utcnow_iso(), created_by=settings.operator_name)
session.add(header)                               # flushed before ops (FK order)
for ln in lines:
    record_operation(
        session, type_="sale", product_id=ln.product.id,
        qty_delta=-ln.qty,
        unit_cost_cents=ln.product.cost_cents,    # D-11 freeze (may be None)
        unit_price_cents=ln.price_cents,          # D-10 entered price
        sale_id=header.id, commit=False,
    )
session.commit()                                  # WR-03: one commit closes txn
```
Wrap the commit in `try/except IntegrityError: session.rollback()` exactly like receipts.py lines 137-141.

**Oversell check (Pattern 3 — no receipts analog; new logic, but reads cached `Product.quantity`):** aggregate requested qty per `product_id` across ALL lines (Pitfall 6), compare to `Product.quantity`; if any oversells AND `confirm != "1"` → return a signal the route turns into `sale_oversell.html`, ZERO writes. On `confirm=1` skip the block and write (stock may go negative, D-09).

**`lookup_prefill` for per-line code lookup — copy receipts.py lines 145-172 shape**, but pre-fill Цена продажи from `Product.sale_cents` (D-10) instead of all three price fields.

**`recent_sales` — copy `recent_receipts` (lines 175-184) JOIN shape:**
```python
select(Operation, Product)
    .join(Product, Operation.product_id == Product.id)
    .where(Operation.type == "sale")
    .order_by(Operation.created_at.desc(), Operation.seq.desc())
    .limit(limit)
```

---

### `app/services/customers.py` (NEW — service, CRUD + Cyrillic search + history)

**Analogs:** `app/services/catalog.py` (CRUD + `search_products` + `split_match`) and `app/services/dictionary.py` (validate + duplicate-race guard).

**CRUD create/update — mirror `dictionary._validate`/`add_entry`/`update_entry` (lines 18-76):** strip inputs, RU errors dict, `session.get` for update, `session.commit()` wrapped in `try/except IntegrityError` (only if a unique constraint is added — RESEARCH A2 says customers likely need NONE). Name-required RU error «Укажите имя покупателя.» (UI-SPEC). On every create/update maintain the shadow (mirror `catalog.create_product` line 79 `name_lc=name.lower()`):
```python
customer.search_lc = f"{name} {surname or ''}".strip().lower()   # Python folds Cyrillic
```

**Cyrillic-safe search — copy `catalog.search_products` (lines 283-307) + `split_match` (lines 310-319) verbatim in shape:**
```python
def search_customers(session, q: str) -> list[Customer]:
    q_lc = q.strip().lower()                       # Python lowers Cyrillic; SQL lower() cannot
    stmt = select(Customer)
    if q_lc:
        stmt = stmt.where(Customer.search_lc.contains(q_lc, autoescape=True))
    return list(session.scalars(stmt.order_by(Customer.search_lc).limit(20)))
```
Reuse `split_match(text, q_lc)` from `catalog.py` (import or replicate) so the picker renders `<mark>` autoescaped — NEVER build HTML in Python (catalog.py lines 310-319 comment).

**Purchase history (CST-02) — extend the `recent_receipts` JOIN with a `Sale` join** (RESEARCH Code Example 4):
```python
select(Operation, Product)
    .join(Sale, Operation.sale_id == Sale.id)
    .join(Product, Operation.product_id == Product.id)
    .where(Sale.customer_id == customer_id, Operation.type == "sale")
    .order_by(Operation.created_at.desc(), Operation.seq.desc())
```
The template reads FROZEN `op.unit_price_cents` (qty = `-op.qty_delta`) — never current `Product.sale_cents` (Anti-Pattern in RESEARCH).

---

### `app/routes/sales.py` (NEW — thin routes)

**Analog:** `app/routes/receipts.py` (whole file).

**Router + imports (receipts.py lines 3-10):**
```python
from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session
from app.db import get_session
from app.routes import templates
router = APIRouter()
```
**Route-order rule (receipts.py comment lines 12-13):** declare literal paths (`/sales/new`, `/sales/lookup`, `/sales/row`, `/sales/customer-search`, `/sales/customer`) BEFORE any parameterized `/sales/{...}`.

**GET page (receipts.py lines 19-27):** context `{errors, form, focus_code, sales/recent}` → `pages/sale_form.html`.

**Lookup 204 pattern (receipts.py lines 30-62 + dictionary.py lines 27-40):** if operator already typed the target field → `Response(status_code=204)`; unknown code → 204; else render the fill partial. htmx-config in `base.html` (line 10) already sets `{"code":"204","swap":false}`.

**POST money-as-string (receipts.py lines 65-75 comment):** every money/qty field is `Form("")` string — Pydantic v2 rejects `""` for `int | None`; parse in the service. For the basket use repeated fields: `code: list[str] = Form([])`, `qty: list[str] = Form([])`, `price: list[str] = Form([])`, `confirm: str = Form("")`.

**POST error/success flow (receipts.py lines 86-126):** wrap the service call in `try/except Exception` → 422 with `errors={"form": SAVE_FAILED_ERROR}` (RESEARCH V7; SAVE_FAILED_ERROR text = «Не удалось сохранить…» receipts.py line 15). `if errors:` → 422 partial with echoed form. Oversell (no writes) → return `sale_oversell.html`. Success → 200 fresh `partials/sale_form.html` with `focus_code=True` + oob `recent_sales`.

---

### `app/routes/customers.py` (NEW — thin CRUD routes)

**Analogs:** `app/routes/products.py` (CRUD + `RedirectResponse` 303 + search partial) and `app/routes/dictionary.py` (204 lookup).

- List/search: copy products.py lines 26-38 — `/customers` renders `pages/customers_list.html`, `/customers/search` (or the sale picker `/sales/customer-search`) renders ONLY the rows partial.
- Create/edit: copy products.py lines 41-91 & 94-152 — GET form page, POST → on error 422 re-render form with echoed `form` dict, on success `RedirectResponse("/customers", status_code=303)`.
- Detail `/customers/{id}`: mirror products.py `product_edit` (lines 94-106) `session.get`→404 pattern; pass `purchase_history(...)` into `pages/customer_detail.html`.
- Route order: literal `/customers/new`, `/customers/search` BEFORE `/customers/{customer_id}` (products.py comment lines 22-23).

---

### `alembic/versions/0004_sales_customers.py` (NEW)

**Analogs:** `0002_catalog_dictionary.py` (native `op.add_column`, no batch) and `0001_initial_schema.py` (create_table + FK + index).

**Frozen-file rule (0001 lines 16-21, 0002 lines 14-19):** NEVER import app modules; all values frozen copies. Header:
```python
revision = "0004"; down_revision = "0003"
branch_labels = None; depends_on = None
```

**CRITICAL — trigger preservation (RESEARCH Pitfall 1 / Anti-Pattern):** add `sale_id` to `operations` with a NATIVE `op.add_column` (like 0002 lines 36-40 which explicitly say "no batch, triggers untouched"). NEVER `batch_alter_table("operations")` — it rebuilds the table and DROPs `operations_no_update`/`operations_no_delete`. Create the `sales` table BEFORE adding the FK column (SQLite allows inline `REFERENCES` on ADD COLUMN only when default is NULL). Full skeleton in RESEARCH Code Example 3.

**Index/FK/PK naming — copy 0001 style (lines 82-92):** `op.f("pk_...")`, `op.f("fk_...")`, `op.f("ix_...")`. **Verification gate (RESEARCH A1):** after `alembic upgrade head`, assert ledger still append-only (extend `tests/test_ledger.py`). Fallback if Alembic emits a rebuild: add a BARE `sale_id` column (no DB FK), keep the ORM `ForeignKey` for UoW ordering + PostgreSQL portability.

---

### Templates

**`pages/sale_form.html`** ← `pages/receipt_form.html` (lines 1-10): `{% extends "base.html" %}`, `{% include "partials/sale_form.html" %}`, then include `partials/recent_sales.html`.

**`partials/sale_form.html`** ← `partials/receipt_form.html` (whole file). Copy: the `id="...-wrap"` swap wrapper with conditional `hx-on::load="document.getElementById('code').focus()"` (line 5, Pitfall 4 — autofocus does not fire in swapped content); the `hx-post`/`hx-target`/`hx-swap="outerHTML"`/`hx-disabled-elt="find button"` form attributes (lines 13-17); the `hx-on::before-swap`/`hx-on::oob-before-swap` typed-value guards (lines 18-21). Basket is a full-width `.basket` table (NOT `.stacked-form`) per UI-SPEC. The customer header (search input + quick-create + selected chip) and the `#basket-rows` tbody live here; oversell block and `confirm=1` re-post button use `.error-block` + `button.danger`.

**`partials/sale_row.html`** ← `partials/receipt_price_inputs.html` (oob wrapper pattern, lines 5-9). One basket line, array-named inputs (`code[]`, `name[]`, `qty[]`, `price[]`); Код input carries the per-line `hx-get="/sales/lookup"` `hx-trigger="input changed delay:300ms"` `hx-sync="this:replace"` (copy receipt_form.html lines 26-31). Re-rendered oob on lookup fill (like `receipt_price_inputs.html` with `oob=True`).

**`partials/sale_lookup.html`** ← `partials/receipt_lookup.html` (lines 1-17): main swap fills the row's Название + oob-fills Цена продажи from `sale_cents`; `value = (prices.sale | cents) if ... else ""`.

**`partials/recent_sales.html`** ← `partials/receipt_rows.html` (lines 1-37): `<div id="recent-sales"{% if oob %} hx-swap-oob="true"{% endif %}>` with heading INSIDE the partial; money via `| cents`, date via `| local_dt`; empty-state «Продаж пока нет…» (UI-SPEC). Autoescape only (T-3-02).

**`partials/customer_picker.html` / `customer_rows.html`** ← `partials/product_rows.html` (lines 1-44): the `{% set pre, match, post = ... %}{{ pre }}{% if match %}<mark>{{ match }}</mark>{% endif %}{{ post }}` highlight idiom (lines 22-23); empty-search «Ничего не найдено по запросу „{{ q }}"…» block (lines 33-36).

**`pages/customers_list.html`** ← `pages/products_list.html` (lines 1-17): `<input type="search" name="q" ... autofocus hx-get="/customers/search" hx-trigger="input changed delay:300ms, keyup[key=='Enter']" hx-target="#customer-rows" hx-swap="outerHTML" hx-sync="this:replace">`.

**`pages/customer_form.html`** ← `pages/product_form.html` (`.stacked-form`, max-width 480px); fields Имя (required, autofocus) / Фамилия / Номер консультанта; «Сохранить покупателя» + «Отмена».

**`pages/customer_detail.html` + `partials/purchase_history.html`** ← `partials/receipt_rows.html` table shape; columns Когда/Код/Название/Кол-во/Цена/Сумма; reads FROZEN `op.unit_price_cents`, qty = `-op.qty_delta`, money via `| cents`; empty «Покупок пока нет.».

**`base.html` (MODIFY)** ← existing nav (lines 17-23). Add after Приход, before Справочник:
```html
<a href="/sales/new"{% if request.url.path.startswith("/sales") %} class="active"{% endif %}>Продажи</a>
<a href="/customers"{% if request.url.path.startswith("/customers") %} class="active"{% endif %}>Покупатели</a>
```

**`app/main.py` (MODIFY)** ← lines 8, 25-30: add `sales, customers` to the routes import and two `app.include_router(...)` lines.

---

### Tests

**`tests/test_sales.py` / `tests/test_customers.py`** ← `tests/test_receipts.py` (whole file). Copy conventions: service-level tests take `(session, product)` fixtures and assert on `select(Operation)`/`compute_stock`; web tests take `client` and assert status + RU text + partial (`"<html" not in response.text`); `test_web_` prefix for route tests; unexpected-error test monkeypatches the service to raise and asserts 422 + error block (test_receipts.py lines 240-253). Required coverage per RESEARCH Test Map: stock decrement, empty-basket, price_override, customer_link, oversell (0 writes then confirm=1 negative), snapshot frozen, null_cost, one_transaction; customers crud/search/history/history_frozen. Also EXTEND `tests/test_ledger.py`: assert `record_operation(..., sale_id=...)` sets the column AND `operations` stays append-only after 0004.

**`tests/conftest.py` (MODIFY)** ← existing `product` fixture (lines 37-48). The existing `product` has `quantity=0`; oversell/decrement tests need stock. Add:
- `stocked_product(session)` — seed a product then `record_operation(session, type_="receipt", product_id=..., qty_delta=N)` to give real ledger-backed stock.
- `customer(session)` — mirror the `product` fixture: build a `Customer(id=new_id(), name=..., search_lc=...)`, `session.add` + `session.commit()`, return it.
New models are seen by tests because `conftest.engine` calls `Base.metadata.create_all` (lines 22-27) — so `Customer`, `Sale`, `Operation.sale_id` MUST live in `models.py` (Pitfall 7).

---

## Shared Patterns

### Single write path (ledger)
**Source:** `app/services/ledger.py:29-84`
**Apply to:** `sales.py` (every sale line). Never insert `operations` rows or touch `Product.quantity` outside `record_operation`. Stage `commit=False`, ONE `session.commit()` per request (receipts.py lines 90-142).

### Money as integer cents
**Source:** `app/core.py:28-53` (`to_cents`, `format_cents`) + `app/services/catalog.py:21-30` (`parse_optional_cents`)
**Apply to:** all price parsing in `sales.py`/`customers.py`; all money display via the `cents` Jinja filter (`app/routes/__init__.py:11`). Never `float()`.

### Cyrillic-safe search shadow
**Source:** `app/services/catalog.py:283-319` (`search_products` + `split_match`)
**Apply to:** `customers.search_customers` + the picker/list templates. Lower the query in Python; compare to `search_lc` via `.contains(q_lc, autoescape=True)`; render `<mark>` from template segments, never build HTML in Python.

### 204 debounced lookup
**Source:** `app/routes/dictionary.py:27-40` + `app/routes/receipts.py:30-62`
**Apply to:** `/sales/lookup` (per-line) and `/sales/customer-search`. Server decides fill vs 204; typed values never overwritten; `base.html:10` htmx-config already ignores 204 and swaps 422.

### RU errors, zero-write validation, thin-route error block
**Source:** service `-> tuple[obj|None, dict[str,str]]` (catalog/receipts/dictionary); route `try/except Exception` → 422 error block (`app/routes/receipts.py:96-115`)
**Apply to:** both new services and both new routers. Never a raw 500 (RESEARCH V7).

### UUID / UTC conventions
**Source:** `app/core.py:15-25` (`new_id`, `utcnow_iso`)
**Apply to:** `Sale`/`Customer` PKs and timestamps; sale header `created_at`/`created_by` (from `settings.operator_name`).

### Autoescape only (stored-name XSS)
**Source:** template comments in `partials/receipt_rows.html:4`, `partials/product_rows.html:3`
**Apply to:** every customer/product name rendered in pickers, chips, history. Never `|safe`.

---

## No Analog Found

None. Every Phase 4 file maps to a proven Phase 1–3 analog. The only genuinely NEW logic (no direct copy) is:
- **Oversell aggregate check + two-step confirm** (`sales.py` + `partials/sale_oversell.html`) — new behavior, but built from existing pieces: `Product.quantity` read, `.error-block`/`button.danger` styling, `hx-vals='{"confirm":"1"}'` re-post. See RESEARCH Pattern 3.
- **`sale_id` header↔line link** — new column, but the migration mechanics (native ADD COLUMN) and ORM FK conventions are copied from 0002 + `models.py`.

---

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/{pages,partials}/`, `alembic/versions/`, `tests/`, `app/core.py`, `app/models.py`, `app/main.py`, `app/routes/__init__.py`
**Files read for grounding:** ledger.py, receipts.py, catalog.py, dictionary.py (services); receipts.py, products.py, dictionary.py (routes); models.py, core.py, main.py, routes/__init__.py; 0001 + 0002 migrations; conftest.py, test_receipts.py; receipt_form.html (page+partial), receipt_lookup.html, receipt_rows.html, receipt_price_inputs.html, name_input.html, product_rows.html, products_list.html, base.html
**Pattern extraction date:** 2026-07-09
</parameter>
</invoke>
