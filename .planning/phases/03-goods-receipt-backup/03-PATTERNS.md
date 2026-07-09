# Phase 3: Goods Receipt & Backup - Pattern Map

**Mapped:** 2026-07-08
**Files analyzed:** 14 new/modified files
**Analogs found:** 11 / 14 (3 have no direct analog — backup track novelties, patterns from RESEARCH.md)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/receipts.py` | service | CRUD (write transaction + reads) | `app/services/catalog.py` | exact |
| `app/routes/receipts.py` | route | request-response (forms + HTMX partials) | `app/routes/products.py` + `app/routes/dictionary.py` | exact |
| `app/templates/pages/receipt_form.html` | template (page) | request-response | `app/templates/pages/product_form.html` | exact |
| `app/templates/partials/receipt_form.html` | template (partial) | request-response | `app/templates/partials/name_input.html` (single-source rule) | role-match |
| `app/templates/partials/receipt_rows.html` | template (partial) | request-response | `app/templates/partials/ledger_rows.html` | exact |
| `app/services/backup.py` | service | file-I/O | — (VACUUM INTO is new) | no analog — use RESEARCH.md Pattern 4; connection style from `app/db.py` |
| `app/routes/backup.py` | route | request-response | `app/routes/products.py` (thin route shape) | role-match |
| `app/templates/pages/backup.html` | template (page) | request-response | `app/templates/pages/dictionary.html` (list + action button page) | role-match |
| `app/main.py` (modify: lifespan) | config/entry | startup hook | current `app/main.py` (extend, don't rewrite) | exact (modify) |
| `app/config.py` (modify: 3 settings) | config | — | current `app/config.py` | exact (modify) |
| `app/templates/base.html` (modify: nav links) | template | — | current `base.html` nav block | exact (modify) |
| `restore.bat` | script | file-I/O | `run.bat` (batch style) | partial — body from RESEARCH.md Pattern 6 |
| `tests/test_receipts.py` | test | — | `tests/test_dictionary.py` | exact |
| `tests/test_backup.py` | test | file-I/O | `tests/conftest.py` engine fixture + RESEARCH.md roundtrip example | role-match |
| `tests/conftest.py` (modify: backup gate) | test fixture | — | current `client` fixture | exact (modify) |

## Pattern Assignments

### `app/services/receipts.py` (service, CRUD transaction)

**Analog:** `app/services/catalog.py` — the strongest analog in the codebase; `register_receipt` is a composition of `create_product` and `update_product` shapes.

**Imports pattern** (`app/services/catalog.py:9-18`):
```python
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id, to_cents, utcnow_iso
from app.models import Operation, Product
from app.services.ledger import record_operation

PRICE_ERROR = "Неверный формат цены — введите число, например 12,50."
DUPLICATE_CODE_ERROR = "Код уже используется другим товаром — введите другой код."
```
Note: RU error messages as module-level constants; import and reuse `parse_optional_cents`, `PRICE_ERROR` from `app.services.catalog` rather than redefining.

**Validation pattern** — money parsing (`app/services/catalog.py:21-30`):
```python
def parse_optional_cents(raw: str, errors: dict, field: str) -> int | None:
    """Empty string -> NULL column; otherwise to_cents; RU error on garbage."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return to_cents(raw)
    except ValueError:
        errors[field] = PRICE_ERROR
        return None
```
Return contract everywhere: `tuple[Product | None, dict[str, str]]` — `(obj, {})` on success, `(None, errors)` with RU messages and NOTHING written on failure (`catalog.py:42-47`).

**Auto-create pattern** (D-05) — copy `create_product`, `app/services/catalog.py:48-102`:
- strip code/name (`lines 49-51`), required-field RU errors (`lines 53-56`)
- active-only duplicate check: `select(Product).where(Product.code == code, Product.deleted_at.is_(None))` (`lines 60-64`) — Pitfall 5: query `deleted_at IS NULL` only
- Product construction with `id=new_id()`, `name_lc=name.lower()` (Cyrillic fold in Python, D-27), `quantity=0` (`lines 73-84`)
- stage `session.add(product)` then `record_operation(type_="product_created", qty_delta=0, payload={"code": ..., "name": ...})` — in the receipt flow pass `commit=False` since more ops follow
- IntegrityError → rollback → `{"code": DUPLICATE_CODE_ERROR}` (`lines 99-101`)

**Core transaction pattern** (D-06/D-07, WR-03 stage-then-single-commit) — copy `update_product`, `app/services/catalog.py:167-228`:
```python
# Pitfall 7: snapshot old values BEFORE any mutation.
old_prices = {field: getattr(product, field) for field in _PRICE_FIELDS}
...
changed_prices = [f for f in _PRICE_FIELDS if old_prices[f] != new_prices[f]]
...
try:
    for field in changed_prices:
        payload = {"field": field, "old_cents": old_prices[field], "new_cents": new_prices[field]}
        record_operation(session, type_="price_change", product_id=product.id,
                         qty_delta=0, payload=payload, commit=False)
    ...
    session.commit()
except IntegrityError:
    session.rollback()
    return None, {"code": DUPLICATE_CODE_ERROR}
```
`_PRICE_FIELDS = ("cost_cents", "sale_cents", "catalog_cents")` (`catalog.py:110`). After price_change ops, add the receipt op itself with `commit=False`, then the single `session.commit()`.

**Ledger write pattern** — `record_operation` signature (`app/services/ledger.py:29-39`): keyword-only `type_`, `product_id`, `qty_delta`, `unit_cost_cents=None`, `unit_price_cents=None`, `payload=None`, `commit=True`. Facts: `OPERATION_TYPES` already includes `"receipt"`; it rejects soft-deleted products (ValueError, `ledger.py:62-63`); updates `products.quantity` SQL-side (`ledger.py:81`); autoflush makes staged Products visible to its `session.get` — no manual flush needed.

**Recent-receipts read pattern** — copy ordering from `price_history`/`ledger_view` (`catalog.py:249-260`, `ledger.py:116-120`): `.order_by(Operation.created_at.desc(), Operation.seq.desc()).limit(N)`, join to Product per RESEARCH.md Code Example.

---

### `app/routes/receipts.py` (route, request-response + HTMX)

**Analog:** `app/routes/products.py` (form POST) + `app/routes/dictionary.py` (lookup 204 endpoint)

**Imports + router pattern** (`app/routes/products.py:1-24`):
```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates

router = APIRouter()

# Route order: literal paths (/products/new, ...) MUST stay
# declared before the parameterized /products/{product_id} routes below.
```
Same rule here: declare `/receipts/new` and `/receipts/lookup` before any parameterized route (there likely are none, but keep the comment convention).

**Form POST pattern** (`app/routes/products.py:52-91`) — money fields as `str = Form("")`:
```python
@router.post("/products")
def product_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    ...
    session: Session = Depends(get_session),
):
    # Money fields arrive as strings on purpose: Pydantic v2 rejects ""
    # for int | None, and to_cents in the service gives the RU error.
    product, errors = create_product(session, code=code, ...)
    if errors:
        context = {..., "errors": errors, "form": {"code": code, ...}}
        return templates.TemplateResponse(request, "pages/product_form.html", context, status_code=422)
    return RedirectResponse("/products", status_code=303)
```
Difference for receipts (D-02, Pattern 3 in RESEARCH.md): instead of 303 redirect, success returns the fresh **form partial** (200) + `hx-swap-oob` recent rows; failure returns the form partial with 422 (already whitelisted in htmx-config).

**Lookup 204 pattern** (`app/routes/dictionary.py:27-40`):
```python
@router.get("/dictionary/lookup")
def dictionary_lookup(request: Request, code: str = "", name: str = "",
                      session: Session = Depends(get_session)):
    # Pattern 2 (D-23): the SERVER decides fill vs no-op; htmx ignores 204.
    # Pitfall 5: a non-empty operator name is never overwritten.
    entry = lookup(session, code)
    if entry is None or name.strip():
        return Response(status_code=204)
    context = {"name": entry.name, "autofilled": True}
    return templates.TemplateResponse(request, "partials/name_input.html", context)
```
New `/receipts/lookup` copies this contract but checks active products first (pre-fill name + prices, D-03), falls back to the dictionary, else 204.

**Partial-with-status pattern** (`app/routes/dictionary.py:43-61`): `status_code=422 if errors else 200` on a `TemplateResponse` rendering a partial — this is the save-and-next response shape.

---

### `app/templates/pages/receipt_form.html` + `partials/receipt_form.html` (templates)

**Analog:** `app/templates/pages/product_form.html` (page/HTMX wiring) + `partials/name_input.html` (single-source partial rule PD-6)

**Debounced lookup wiring** (`product_form.html:18-31`) — copy verbatim, retarget to `/receipts/lookup`:
```html
<form ... class="stacked-form"
      hx-on::before-swap="if (event.detail.target.id === 'name-wrap'
        && document.getElementById('name').value.trim()) event.detail.shouldSwap = false">
  ...
  <input type="text" id="code" name="code" ... required autofocus
         hx-get="/dictionary/lookup"
         hx-trigger="input changed delay:300ms"
         hx-include="[name='name']"
         hx-target="#name-wrap"
         hx-swap="outerHTML"
         hx-sync="this:replace">
```
For receipts the lookup fills name + 3 prices — per RESEARCH.md Pattern 2 use one wrapper fragment (single `hx-target`), extend the swap-time guard to price fields the operator already typed (Pitfall 7).

**Money input pattern** (`product_form.html:50-66`):
```html
<input type="text" id="cost" name="cost" inputmode="decimal" placeholder="0,00"
       value="{% if form %}{{ form.cost or '' }}{% elif product and product.cost_cents is not none %}{{ product.cost_cents | cents }}{% endif %}">
{% if errors.cost %}<p class="error">{{ errors.cost }}</p>{% endif %}
```
Filters available: `| cents` and `| local_dt` (registered in `app/routes/__init__.py:10-11`).

**Single-source partial rule** (`partials/name_input.html:1-8`): the static form include AND the lookup swap render the SAME partial via `{% include %}` + `{% with %}` (`product_form.html:37-39`) — apply the same rule to the receipt form partial (page includes it; POST response returns it).

**Focus return** (D-02): no codebase analog — use RESEARCH.md Pattern 3: `hx-on::htmx:load="document.getElementById('code').focus()"` on the fresh form partial; keep `autofocus` for initial page load.

---

### `app/templates/partials/receipt_rows.html` (partial, recent list)

**Analog:** `app/templates/partials/ledger_rows.html` — table with RU headers, `{{ op.created_at | local_dt }}`, wrapped in a stable `id` div (`<div id="ledger">`, lines 1-28). Give the receipts list a stable id (e.g. `id="recent-receipts"`) so the POST response can target it with `hx-swap-oob="true"`. Autoescape only — no `|safe` (XSS guard from Security Domain).

---

### `app/services/backup.py` (service, file-I/O) — NO direct analog

Use RESEARCH.md Pattern 4 (AUTOCOMMIT + bound parameter) verbatim:
```python
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    conn.exec_driver_sql("VACUUM INTO ?", (str(target),))
```
Codebase conventions to follow anyway:
- module docstring style with decision refs (see `app/services/ledger.py:1-6`)
- `exec_driver_sql` precedent exists in `tests/conftest.py:25` and `app/db.py`
- filename timestamp: derive from UTC like `app.core.utcnow_iso` but formatted `YYYYMMDD-HHMMSS` (lexicographic = chronological, matching ISO-sorting convention)
- `prune_backups` / `list_backups` per RESEARCH.md Code Examples; prune only after successful backup (D-10); `target.unlink(missing_ok=True)` on failure (Pitfall 4)

---

### `app/routes/backup.py` (route)

**Analog:** `app/routes/products.py` thin-route shape. `GET /backup` renders `pages/backup.html` with server-enumerated `list_backups(...)`; `POST /backup` calls `create_backup` + `prune_backups` then re-renders the list (full page or partial). **Never accept a filename/path parameter** (Security V12). Uses module-level `app.db.engine` (not the request session) since VACUUM needs its own connection.

---

### `app/main.py` (modify — lifespan)

Current file is 14 lines (`app/main.py:1-13`): plain `app = FastAPI(title="MyOriShop")`, static mount, 4 routers. Modify minimally:
- add `lifespan` per RESEARCH.md Pattern 5 (`@asynccontextmanager`, gate on `settings.backup_on_startup` + DB exists/non-empty, then `create_backup` + `prune_backups`, then `yield`)
- `app = FastAPI(title="MyOriShop", lifespan=lifespan)`
- `app.include_router(receipts.router)` and `app.include_router(backup.router)` following the existing lines 10-13

### `app/config.py` (modify — settings)

Add fields to `Settings` (`app/config.py:9-17` style — plain typed defaults):
```python
backup_dir: str = "backups"
backup_on_startup: bool = True
backup_keep: int = 30
```

### `app/templates/base.html` (modify — nav)

Add two links following `base.html:18-20` pattern:
```html
<a href="/receipts/new"{% if request.url.path.startswith("/receipts") %} class="active"{% endif %}>Приход</a>
```
(same for `/backup`). Note `base.html:9-10` htmx-config already whitelists 204 (no swap) and 422 (swap) — no change needed there.

### `restore.bat`

No behavioral analog; body from RESEARCH.md Pattern 6 (copy + mandatory `del` of `-wal`/`-shm`). Match `run.bat` style (`cd /d "%~dp0"`; the app binds 127.0.0.1 per run.bat).

---

### `tests/test_receipts.py` (test)

**Analog:** `tests/test_dictionary.py` — module docstring listing covered decisions (`lines 1-11`), naming convention `test_web_*` for route/e2e tests vs plain names for service tests (`lines 9-10`), `EMPTY_MONEY = {"cost_raw": "", "sale_raw": "", "catalog_raw": ""}` helper-dict idiom (`line 19`), fixtures `session` / `product` / `client` from conftest. Assert RU error substrings, UUID length 36, op rows via `select(Operation)`.

### `tests/test_backup.py` (test)

**Analog:** `tests/conftest.py:17-27` engine fixture — `build_engine(str(tmp_path / "test.db"))` + `Base.metadata.create_all` + `APPEND_ONLY_TRIGGERS` via `exec_driver_sql`. Restore roundtrip per RESEARCH.md Code Example: backup live engine → `shutil.copyfile` → `build_engine(restored_path)` → read quantity + `compute_stock` back; also assert append-only triggers survived (attempt UPDATE on operations → expect error) to close Assumption A2.

### `tests/conftest.py` (modify — Pitfall 1)

In the `client` fixture (`conftest.py:51-72`): `with TestClient(app)` runs lifespan → the startup backup would VACUUM the real `data/myorishop.db`. Gate it: monkeypatch `settings.backup_on_startup = False` (or set env) before `TestClient(app)` enters.

## Shared Patterns

### Single write path (ledger)
**Source:** `app/services/ledger.py:29-84` (`record_operation`)
**Apply to:** every stock/audit write in `app/services/receipts.py`. Never insert Operation rows or touch `products.quantity` elsewhere. Multi-op logical changes: every call `commit=False`, ONE `session.commit()` at the end (WR-03).

### Error handling
**Source:** `app/services/catalog.py` return contract + `app/routes/products.py:74-90`
**Apply to:** receipts service and routes. Services return `(obj, errors_dict)` — RU messages, nothing written on error. Routes render the form with `errors` + `form` (raw entered strings) at `status_code=422`. Duplicate-code races: catch `IntegrityError` → `session.rollback()` → RU error dict, never a 500.

### Validation
**Source:** `app/services/catalog.py:21-30` (`parse_optional_cents`), `app/core.to_cents`
**Apply to:** all money fields on the receipt form. Quantity: new strict positive-int parse (no analog — qty inputs are new; follow the same errors-dict + RU-message shape). Fields arrive as `str = Form("")`, parsed only in the service.

### HTMX conventions
**Source:** `app/templates/base.html:9-10` (htmx-config), `product_form.html:18-31` (debounce + swap guard), `app/routes/dictionary.py:34-40` (204 contract)
**Apply to:** receipt form lookup and save-and-next loop. htmx 2.x `hx-on::` double-colon syntax; partials returned bare (no base extend); vendored `/static/htmx.min.js` only.

### Templates plumbing
**Source:** `app/routes/__init__.py:1-11`
**Apply to:** both new routers — `from app.routes import templates`; filters `| cents` and `| local_dt` already registered.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/services/backup.py` | service | file-I/O | First filesystem/VACUUM service; use RESEARCH.md Pattern 4 + `app/db.py` connection idioms |
| lifespan in `app/main.py` | startup hook | event | First lifespan usage; RESEARCH.md Pattern 5 (on_event deprecated) |
| `restore.bat` | script | file-I/O | Only `run.bat` exists (launcher, different purpose); RESEARCH.md Pattern 6 |

## Metadata

**Analog search scope:** `app/` (services, routes, templates, config/db/main), `tests/`
**Files scanned:** 13 read in full (services x3, routes x4, templates x5 incl. base, config/db/main, conftest, test_dictionary excerpt)
**Pattern extraction date:** 2026-07-08
