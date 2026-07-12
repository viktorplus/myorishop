# Phase 9: Batch Tracking & Ledger Integration - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 22 new/modified files
**Analogs found:** 21 / 22 (only `tests/test_batches.py` migration-test portion has no in-repo precedent)

All analogs are current (touched in Phases 4–8) and follow the locked repo conventions: fat services returning `(result, errors)`, thin routes, single write path via `record_operation()`, RU UI text, warn-but-allow `confirm=1`, HTMX server-decides-fill-vs-204.

## File Classification

| New/Modified File | New? | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|------|-----------|----------------|---------------|
| `app/models.py` (`Batch` model, `Operation.batch_id`) | modify | model | CRUD | `Warehouse` + `Operation.sale_id` in same file | exact |
| `alembic/versions/0008_batches.py` | NEW | migration | batch/data-seed | `alembic/versions/0004_sales_customers.py` (add_column) + `0007_warehouses.py` (frozen seed) | exact |
| `app/services/ledger.py` (`record_operation` batch_id param, dual projection, `rebuild_stock` invariant) | modify | service | event-append + cache projection | itself — `sale_id` param + `Product.quantity` increment pattern | exact |
| `app/services/batches.py` | NEW | service (read helpers) | query/read | `app/services/warehouses.py` (module shape) + `sales.py::lookup_prefill` | role-match |
| `app/services/receipts.py` (warehouse + batch resolve-or-create) | modify | service | transactional write | itself — `register_receipt` auto-create-in-same-txn | exact |
| `app/services/sales.py` (batch_id[] parsing, per-batch oversell) | modify | service | transactional multi-line write | itself — `requested_by_product` oversell block (lines 137-153) | exact |
| `app/services/writeoffs.py` | modify | service | transactional write | `app/services/sales.py` oversell + own confirm=1 gate | exact |
| `app/services/corrections.py` (batch-scoped count/delta) | modify | service | transactional write | itself — `register_correction` count/delta modes | exact |
| `app/services/returns.py` (origin batch inheritance) | modify | service | transactional write | itself — origin-op frozen-copy pattern (lines 91-102) | exact |
| `app/services/operations.py` (`history_view` batch join) | modify | service | read/report | itself — existing Operation↔Product join; `sales.py::recent_sales` outer-join shape | exact |
| `app/routes/receipts.py` (`/receipts/batches` chooser endpoint) | modify | route | request-response (HTMX fragment) | `app/routes/sales.py::sale_lookup` + `sale_customer_search` | exact |
| `app/routes/sales.py` (`/sales/batch-pick`, `_build_lines` batch echo) | modify | route | request-response | itself — `sale_lookup` + `_build_lines` + `_ROW_ID_RE` | exact |
| `app/routes/writeoffs.py`, `app/routes/corrections.py` | modify | route | request-response | `app/routes/sales.py` lookup/confirm patterns | exact |
| `app/routes/history.py` + history partials | modify | route/template | read/display | itself + `partials/history_rows.html` | exact |
| `app/templates/partials/batch_picker.html` | NEW | template partial | HTMX fragment | `partials/sale_lookup.html` (oob fill) + `partials/sale_customer.html` (hidden-input sync) + `partials/customer_picker.html` (list picker) | role-match |
| `app/templates/partials/receipt_batch_chooser.html` | NEW | template partial | HTMX fragment | `partials/correction_form.html` radio show/hide + disabled toggle (lines 44-76) | role-match |
| `app/templates/partials/sale_row.html` (wrapper `<tr>` + hidden `batch_id[]`) | modify | template partial | form arrays | itself + `sale_customer.html` hidden input | exact |
| `app/templates/partials/receipt_form.html` (warehouse select, oob guard extension) | modify | template partial | form | itself — oob-before-swap guard (lines 18-21) | exact |
| `app/templates/partials/writeoff_form.html`, `correction_form.html` | modify | template partial | form | own lookup wiring + shared `batch_picker.html` | exact |
| `tests/conftest.py` (warehouse/batch fixtures, `stocked_product` update) | modify | test fixture | — | itself — `stocked_product` fixture (lines 52-71) | exact |
| `tests/test_batches.py` | NEW | test | — | `tests/test_ledger.py` / `tests/test_sales.py` structure (session-fixture unit + TestClient integration) | role-match |
| Migration-replay test (inside test_batches.py) | NEW | test | migration verification | **no analog** — no existing test runs Alembic against a temp DB | none |

## Pattern Assignments

### `app/models.py` — `Batch` model + `Operation.batch_id` (model)

**Analog:** `Warehouse` model, `app/models.py:119-137`, and `Operation.sale_id`, lines 176-178.

**Model conventions to copy** (`app/models.py:129-137`):
```python
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
```
Note: `Batch` gets NO `deleted_at` (D-03) — deviate from Warehouse there deliberately, with a docstring saying why (repo docstrings always cite the decision ID).

**Nullable ledger-link column pattern** (`app/models.py:176-178` — copy verbatim shape for `batch_id`):
```python
    sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", name="fk_operations_sale_id_sales"), index=True
    )
```
The explicit FK `name=` matters: naming convention (lines 24-30) + future batch-migration targetability.

Cached-projection column precedent (`Product.quantity`, line 112): `Mapped[int] = mapped_column(Integer, nullable=False, default=0)` with the "cached projection of SUM(...); recomputable" comment — copy for `Batch.quantity`.

RESEARCH.md already contains a full ready `Batch` model draft (its "Batch model" code example) consistent with these conventions — use it.

---

### `alembic/versions/0008_batches.py` (migration)

**Analog A — native add_column, no batch mode:** `alembic/versions/0004_sales_customers.py:72-82`:
```python
    # NATIVE add-column (NO batch — preserves the operations_no_update /
    # operations_no_delete triggers from migration 0001). BARE column, no
    # DB-level FK (A1 fallback — see module docstring): Alembic's SQLite
    # dialect cannot ALTER in a constraint outside batch mode.
    op.add_column(
        "operations",
        sa.Column("sale_id", sa.String(36), nullable=True),
    )
    op.create_index(op.f("ix_operations_sale_id"), "operations", ["sale_id"])
```
Copy verbatim for `batch_id` (rename only). Downgrade mirror at 0004:85-87 (drop index first, then column).

**Analog B — create_table with named constraints:** 0004:43-70 (`sa.PrimaryKeyConstraint(..., name=op.f("pk_..."))`, `sa.ForeignKeyConstraint([...], [...], name=op.f("fk_..."))`, `op.create_index(op.f("ix_..."))`). New-table FKs ARE allowed (only `operations` alters are restricted).

**Analog C — frozen-literal seed:** `alembic/versions/0007_warehouses.py:30-33` (frozen constant + timestamp):
```python
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"
_SEED_CREATED_AT = "2026-07-11T00:00:00+00:00"
```
Re-declare `DEFAULT_WAREHOUSE_ID` in 0008 (never import 0007). 0007 uses `sa.table`/`op.bulk_insert` for static rows; the legacy seed is data-dependent, so use `op.get_bind()` + `sa.text` SELECT/INSERT per RESEARCH's Migration 0008 skeleton (which is precedent-consistent).

**Docstring pattern:** every migration carries a module docstring citing decision IDs, the batch-mode trigger warning, and "Immutability rule (WR-06): this file must never import app modules" (0004:1-29, 0007:1-18). Copy this shape.

---

### `app/services/ledger.py` — `record_operation` extension (service, single write path)

**Analog:** itself. Copy these exact in-file patterns:

**Guard-before-stage pattern** (`app/services/ledger.py:60-68`) — mirror for batch:
```python
    product = session.get(Product, product_id)
    if product is None:
        raise ValueError(f"unknown product: {product_id!r}")
    if product.deleted_at is not None:
        raise ValueError(f"product is deleted: {product_id!r}")
```
Add the batch guard right after (get Batch, ValueError on unknown / wrong product ownership / missing-when-required — D-12), before `session.add(op)`.

**SQL-side increment** (line 85-87) — duplicate for the batch projection:
```python
    # IN-02: SQL-side increment (UPDATE ... SET quantity = quantity + ?) —
    # atomic, no stale-ORM-value window. Same transaction (D-09).
    product.quantity = Product.quantity + qty_delta
```
New line: `batch.quantity = Batch.quantity + qty_delta` (only when `batch is not None`). Keep the existing product line untouched.

**Optional-param signature precedent** (lines 38, 78): `sale_id: str | None = None` in the kwargs-only signature, assigned into the `Operation(...)` constructor — `batch_id` follows identically.

**`compute_stock`/`rebuild_stock`** (lines 93-107): the per-batch pass extends this loop. RESEARCH's `compute_batch_stock`/invariant example is the target shape.

---

### `app/services/batches.py` (NEW service — read helpers)

**Analog (module shape):** `app/services/warehouses.py:1-27` — module docstring citing decision IDs, RU error constants at top, small focused functions taking `session` first:
```python
def list_warehouses(session: Session) -> list[Warehouse]:
    """ALL rows, active + deleted (D-09) — sorted active-first, then by name."""
    rows = list(session.scalars(select(Warehouse)))
    return sorted(rows, key=lambda w: (w.deleted_at is not None, w.name))
```
Contents: `open_batches()` (D-07 `nullslast(Batch.expiry.asc()), Batch.created_at.asc()` ordering) and `legacy_batch()` — RESEARCH's code example gives both, consistent with this module shape. Note: `list_warehouses` deliberately includes deleted rows — the receipt form needs an active-only filter (`Warehouse.deleted_at.is_(None)`); put an `active_warehouses()` helper here or in warehouses.py.

---

### `app/services/receipts.py` — warehouse + batch resolve-or-create (service)

**Analog:** itself, `register_receipt`.

**Resolve-or-create in one transaction** (`app/services/receipts.py:71-97`) — the batch resolve-or-create mirrors this exactly:
```python
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()

    if product is None:
        # D-05: auto-create the card inside the same transaction.
        product = Product(id=new_id(), code=code, name=name, ..., quantity=0)
        session.add(product)
        record_operation(session, type_="product_created", ..., commit=False)
```
Batch analog: `batch_choice == "new"` → construct `Batch(..., quantity=0)` + `session.add`; existing id → `session.get(Batch, ...)` + validate `batch.product_id == product.id and batch.warehouse_id == warehouse_id` (Pitfall 10), then `record_operation(type_="receipt", batch_id=batch.id, ..., commit=False)`.

**Single-commit + IntegrityError → RU error** (lines 139-146):
```python
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, {"code": DUPLICATE_CODE_ERROR}
```

**Optional-cents parsing** (lines 62-64): `parse_optional_cents(cost_raw, errors, "cost")` — the new `parse_optional_expiry` helper follows this exact `(raw, errors, key) -> value|None` signature convention (RESEARCH gives the body).

---

### `app/services/sales.py` — `batch_id[]` + per-batch oversell (service)

**Analog:** itself.

**Parallel-array filter to extend** (`app/services/sales.py:43-57`):
```python
def non_blank_lines(
    codes: list[str], qtys: list[str], prices: list[str]
) -> list[tuple[str, str, str]]:
    return [
        (code, qty, price)
        for code, qty, price in zip(codes, qtys, prices, strict=False)
        if code.strip() or qty.strip() or price.strip()
    ]
```
Grow a 4th `batch_ids` array; blankness stays keyed on code/qty/price; pad `batch_ids` with `""` to `len(codes)` BEFORE zipping (RESEARCH Pattern 2 — a short array must degrade to "no batch", never shift).

**Oversell block to re-key from product_id to batch_id** (lines 137-183) — copy structure, swap the key:
```python
    if confirm != "1":
        requested_by_product: dict[str, int] = {}
        products_by_id: dict[str, Product] = {}
        for line in resolved:
            product = line["product"]
            requested_by_product[product.id] = requested_by_product.get(product.id, 0) + line["qty"]
            products_by_id[product.id] = product

        oversold = [
            {"product": products_by_id[pid], "available": products_by_id[pid].quantity,
             "requested": requested}
            for pid, requested in requested_by_product.items()
            if requested > products_by_id[pid].quantity
        ]
        ...
        # Pitfall 2: both checks are computed above BEFORE any return
        if oversold or below_minimum:
            ...
            return result, {}
```
Critical discipline to preserve: BOTH warn lists computed before any return; `confirm == "1"` skips the whole block; zero writes on warn.

**Write loop** (lines 199-220): add `batch_id=line["batch_id"]` to the `record_operation(...)` call inside the existing `try/except (IntegrityError, ValueError): rollback` shell — unchanged otherwise.

---

### `app/services/writeoffs.py` / `app/services/corrections.py` (service)

**Analog:** own files + sales oversell above. Corrections' count-mode baseline (`app/services/corrections.py:63-67`) must be re-pointed at the picked batch:
```python
    if mode == "count":
        if s.isascii() and s.isdigit():
            counted = int(s)
            qty_delta = counted - product.quantity   # ← becomes batch.quantity (Pitfall 7)
```
Also copy: allow-list mode guard (line 46-47 — precedent for validating `batch_choice`), the isascii+isdigit int guard, and the `except (IntegrityError, ValueError): rollback → {"form": SAVE_FAILED_ERROR}` shell (lines 85-96).

---

### `app/services/returns.py` — batch inheritance (service)

**Analog:** itself — origin frozen-copy pattern (`app/services/returns.py:91-102`):
```python
        op = record_operation(
            session,
            type_="return",
            product_id=origin.product_id,
            qty_delta=qty,
            unit_price_cents=origin.unit_price_cents,  # D-07 frozen copy
            unit_cost_cents=origin.unit_cost_cents,   # D-07 frozen copy
            sale_id=origin.sale_id,
            payload={"origin_op_id": origin.id},
            commit=True,
        )
```
Batch inheritance rides identically: `batch_id=origin.batch_id` or, when `origin.batch_id is None`, `legacy_batch(session, origin.product_id)` (lazy-create per RESEARCH Open Question 1 — flag for planner sign-off). The origin-validation gate (lines 72-74: `origin is None or origin.type != "sale" or origin.sale_id is None`) is the precedent for rejecting forged ids before anything else.

---

### `app/routes/sales.py` — `/sales/batch-pick` + `_build_lines` echo (route)

**Analog:** itself.

**Lookup endpoint shape** (`app/routes/sales.py:71-96`) — `/sales/batch-pick` and `/receipts/batches` copy this: `Query` aliases for `[]` names, server-decides (204 vs fragment), thin route:
```python
@router.get("/sales/lookup")
def sale_lookup(
    request: Request,
    code: str = Query("", alias="code[]"),
    ...
    row: str = "",
    session: Session = Depends(get_session),
):
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    context = {"row": row, ..., "fill_price": result["source"] == "product" and not price.strip()}
    return templates.TemplateResponse(request, "partials/sale_lookup.html", context)
```
Note the `fill_price` server-side decision — this is where the "skip card fill when open batches exist" rule (Pitfall 4) plugs in.

**Untrusted `row` id validation** (lines 28, 106-107) — MANDATORY for any new endpoint accepting `row`:
```python
_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")
...
    row_id = row if _ROW_ID_RE.fullmatch(row) else new_id()
```

**`_build_lines` echo** (lines 31-56): add `batch_ids` param, a `"batch_id"` key per line dict, and resolve `session.get(Batch, batch_id)` per non-empty id for the selected-summary render (Pattern 4). The three response branches in `sale_create` (lines 195-251: exception → 422, warn → 200 with oversell context, errors → 422) all pass through `_build_lines`, so the echo works everywhere once.

**POST form arrays** (lines 179-181): `code: list[str] = Form([], alias="code[]")` — add `batch_id: list[str] = Form([], alias="batch_id[]")` identically.

---

### `app/templates/partials/sale_row.html` — wrapper row (template)

**Analog:** itself (`app/templates/partials/sale_row.html:8-40`). Copy the id-derivation convention for new ids:
```jinja
{% set code_id = "code" if not row_id else "code-" + row_id %}
```
→ `{% set batch_wrap_id = "batch-wrap-" + (row_id or 'first') %}` matching `<tr id="row-{{ row_id or 'first' }}">` (line 12). The delete button (line 38) must grow the wrapper removal:
```html
<button type="button" class="secondary" hx-on:click="this.closest('tr').remove()">Удалить строку</button>
```
→ also remove `#batch-wrap-{row}` (RESEARCH Pattern 2 delete-handler snippet). RESEARCH's "sale_row.html wrapper row" example is the target markup.

---

### `app/templates/partials/batch_picker.html` (NEW template)

**Analog 1 — oob price fill with hint:** `partials/sale_lookup.html:11-16`:
```html
{% if fill_price %}
<td id="{{ price_wrap_id }}" hx-swap-oob="true">
  <input type="text" name="price[]" inputmode="decimal" placeholder="0,00" value="{{ (prices.sale | cents) if prices and prices.sale is not none else '' }}">
  <p class="muted">Цена подставлена из карточки товара — можно изменить.</p>
</td>
{% endif %}
```
The batch-pick response reuses this exact oob shape with hint text "Цена подставлена из партии — можно изменить" (D-05). The `| cents` filter formats integer cents.

**Analog 2 — hidden input synced by selection:** `partials/sale_customer.html:14-15`:
```html
  <input type="hidden" id="customer-id-input" name="customer_id" form="sale-form"
         value="{{ selected.id if selected else (customer_id or '') }}">
```
The `batch_id[]` hidden input follows this "server renders the value, selection re-renders the block" idea — but server-driven (radio `hx-get=/sales/batch-pick` re-renders the wrapper, RESEARCH Pattern 3 radio snippet) rather than client-side dataset JS.

**Typed-value oob guard (already exists, zero new code):** the form-level guard in `receipt_form.html:20-21` / analog in `sale_form.html`:
```html
        hx-on::oob-before-swap="if (['cost-wrap','sale-wrap','catalog-wrap'].includes(event.detail.target.id)
          && document.getElementById(event.detail.target.id.replace('-wrap','')).value.trim()) event.detail.shouldSwap = false"
```

---

### `app/templates/partials/receipt_batch_chooser.html` (NEW) + `receipt_form.html` changes

**Analog — radio show/hide with disabled toggling:** `partials/correction_form.html:44-76` (the count/delta switch):
```html
        <input type="radio" name="mode" value="count"{% if mode == "count" %} checked{% endif %}
               hx-on::change="document.getElementById('count-block').hidden = false;
                 document.getElementById('delta-block').hidden = true;
                 document.getElementById('count-value').disabled = false;
                 document.getElementById('delta-value').disabled = true;">
    ...
    <div class="field" id="count-block"{% if mode != "count" %} hidden{% endif %}>
      <input type="text" id="count-value" name="value" ... {% if mode != "count" %}disabled{% endif %}>
```
The "top up vs new batch" chooser copies this idiom (disabled inputs never submit). CAUTION (RESEARCH A1): this analog uses `hx-on::change` (double colon); htmx 2.x docs say plain DOM events need single-colon `hx-on:change` — verify in-browser and normalize when copying; the delete button on `sale_row.html:38` correctly uses single-colon `hx-on:click`.

**Debounced lookup + hx-include extension:** `receipt_form.html:25-31` — the code input's `hx-include="[name='name'],[name='cost'],...` list grows `[name='warehouse_id']`; the warehouse `<select>` gets its own `hx-get="/receipts/batches"` `hx-trigger="change"` per RESEARCH Pattern 5.

---

### `app/routes/history.py` + `app/services/operations.py` + `history_rows.html`

**Analog — Operation↔Product join to extend to LEFT OUTER JOIN Batch:** `app/services/sales.py:254-263`:
```python
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
```
`history_view` in `app/services/operations.py` follows the same shape — add `.outerjoin(Batch, Operation.batch_id == Batch.id)` and a `"batch"` key per row dict; render as a muted second line in the Товар cell (RESEARCH Open Question 3 recommendation). NULL batch_id on stock-affecting types → legacy label at read time (D-15); route stays untouched except context passthrough (`app/routes/history.py:41-52` HX-Request branching stays as-is).

---

### `tests/conftest.py` + `tests/test_batches.py`

**Analog — fixture to extend:** `tests/conftest.py:52-71`:
```python
@pytest.fixture()
def stocked_product(session):
    """Seed a product with real ledger-backed stock (Phase 4: sale/oversell tests)."""
    product = Product(id=new_id(), code="STK-001", name="Товар со склада", quantity=0)
    session.add(product)
    session.commit()
    record_operation(
        session, type_="receipt", product_id=product.id, qty_delta=8,
        unit_cost_cents=1000, unit_price_cents=1500,
    )
    return product
```
This call breaks the moment D-12 lands — the same wave must add `warehouse` and `batch` fixtures (same shape as `product`/`customer` fixtures, lines 38-49/74-86) and pass `batch_id=` here. `Base.metadata.create_all` (line 23) auto-covers the new tables; the append-only triggers are installed at lines 24-27 — the migration-replay test (trigger-survival assertion) has NO analog and must run real Alembic against a temp DB (new pattern; see RESEARCH Pitfall 6 verification SQL).

## Shared Patterns

### 1. Single write path + staged commit
**Source:** `app/services/ledger.py:29-90`; staging discipline in `sales.py:199-220`, `receipts.py:139-146`.
**Apply to:** every service touching stock. `record_operation(..., commit=False)` per line, ONE `session.commit()`, `except (IntegrityError, ValueError): session.rollback(); return None, {"form": RU_ERROR}`.

### 2. Warn-but-allow `confirm=1` zero-write gate
**Source:** `app/services/sales.py:137-183` (basket, aggregated), `app/services/warehouses.py:91-98` (single-object variant).
**Apply to:** per-batch oversell in sales/writeoffs/corrections (D-09). Contract: check ONLY when `confirm != "1"`; compute ALL warn lists before any return; return warn payload with `errors == {}`; the route re-renders the intact form and the confirm button re-POSTs with `confirm=1`.

### 3. Fat service returning `(result | None, errors: dict[str, str])`
**Source:** every `register_*` (e.g. `receipts.py:30-46` docstring contract).
**Apply to:** all modified services and any new function in `batches.py` that validates. RU error constants live at module top.

### 4. Thin route with logged catch-all → RU 422
**Source:** `app/routes/sales.py:186-208`:
```python
    try:
        result, errors = register_sale(...)
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        logger.exception("register_sale failed")
        context = {...}
        return templates.TemplateResponse(request, "partials/sale_form.html", context, status_code=422)
```
**Apply to:** all modified POST routes.

### 5. Server-decides-fill-vs-204 HTMX lookup
**Source:** `app/routes/sales.py:71-96` + `sale_row.html:15-23` (debounced input: `hx-trigger="input changed delay:300ms"`, `hx-sync="this:replace"`, `hx-include`).
**Apply to:** `/receipts/batches`, `/sales/batch-pick`, and the extended lookups on writeoff/correction forms.

### 6. Typed-value swap guards
**Source:** `receipt_form.html:18-21` (`hx-on::before-swap` for main target, `hx-on::oob-before-swap` for price fills).
**Apply to:** batch price oob fills — extend the existing id allow-lists rather than writing new guard code. Server side must pick ONE fill source per line (Pitfall 4: skip card fill when open batches exist).

### 7. Input validation idioms
**Source:** qty guard `sales.py:92-93` (`qty_text.isascii() and qty_text.isdigit()`); allow-list `corrections.py:46-47`; optional-cents `receipts.py:62-64`; untrusted `row` id `routes/sales.py:28,106-107`; batch ownership guard mirrors `ledger.py:61-68`.
**Apply to:** `batch_choice` allow-list, expiry `date.fromisoformat`, all new endpoints. Optional fields: `is not None`, never bare `or`.

### 8. Migration immutability rules
**Source:** `0004_sales_customers.py` (docstring + native add_column, bare column, no inline FK) and `0007_warehouses.py` (frozen literals, never import app modules).
**Apply to:** `0008_batches.py` in full. Never `batch_alter_table("operations")`.

## No Analog Found

| File/Portion | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Alembic migration-replay test (in `tests/test_batches.py`) | test | migration verification | No existing test executes `alembic upgrade` against a temp DB; existing tests build schema via `Base.metadata.create_all`. Use RESEARCH Pitfall 6's verification SQL (trigger count == 2, UPDATE aborts) as the spec. |

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/partials/`, `alembic/versions/`, `tests/`, `app/models.py`
**Files scanned:** 15 read in full (ledger, sales, receipts, returns, corrections, warehouses services; sales/history routes; models; migrations 0004/0007; sale_row/sale_lookup/sale_customer/receipt_form/correction_form partials; conftest)
**Pattern extraction date:** 2026-07-12
**Note for planner:** RESEARCH.md's Code Examples section already contains phase-ready drafts (migration 0008, Batch model, open_batches, per-batch oversell, rebuild_stock, expiry parse, wrapper row) that are verified consistent with the analogs above — plans should reference both this file's line-numbered sources and those drafts.
