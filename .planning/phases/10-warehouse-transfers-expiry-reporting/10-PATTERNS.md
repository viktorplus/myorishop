# Phase 10: Warehouse Transfers & Expiry Reporting - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 20 (7 new, 13 modified)
**Analogs found:** 20 / 20 (every file has an in-repo analog — this phase is almost entirely wiring existing verified components)

## File Classification

### New files

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `app/services/transfers.py` | service | CRUD (write) | `app/services/writeoffs.py` (+ `receipts.py` for batch-create) | exact (role + confirm-gate flow) |
| `app/routes/transfers.py` | route | request-response + HTMX | `app/routes/writeoffs.py` | exact |
| `app/templates/pages/transfer_form.html` | template (page) | server-render | `app/templates/pages/writeoff_form.html` | exact |
| `app/templates/partials/transfer_form.html` | template (partial) | HTMX swap | `app/templates/partials/writeoff_form.html` | exact |
| `app/templates/partials/transfer_lookup.html` | template (partial) | HTMX oob-swap | `app/templates/partials/writeoff_lookup.html` | exact |
| `app/templates/partials/transfer_batch_wrap.html` | template (partial) | HTMX swap | `app/templates/partials/writeoff_batch_wrap.html` | exact |
| `app/templates/partials/transfer_oversell.html` | template (partial) | HTMX swap | `app/templates/partials/writeoff_oversell.html` | exact |
| `app/templates/partials/transfer_rows.html` | template (partial) | oob-swap list | `app/templates/partials/writeoff_rows.html` | exact |
| `app/templates/pages/reports_expiry.html` | template (page) | server-render (read-only) | `app/templates/pages/reports_stock.html` | exact |
| `tests/test_transfers.py` | test | unit + integration | `tests/test_writeoffs.py` / `tests/test_receipts.py` | exact |

> **Discretion resolved (RESEARCH):** service lives in a NEW `app/services/transfers.py` (batches.py is read-only). `expiring_batches()` goes in `app/services/batches.py` beside `open_batches()`.

### Modified files

| Modified File | Role | Change | Analog / Reference |
|---------------|------|--------|--------------------|
| `app/models.py` | model | add `"transfer"` to `OPERATION_TYPES` (line 34-43) + `OPERATION_TYPE_LABELS` (line 59-68) | existing tuple/dict entries |
| `app/services/ledger.py` | service | add `"transfer"` to `STOCK_AFFECTING_TYPES` (line 18) | existing frozenset |
| `app/services/batches.py` | service | add `expiring_batches()` read helper | `open_batches()` (line 15-32) |
| `app/routes/reports.py` | route | add `/reports/expiry` GET handler | `reports_stock_page` (line 153-165) |
| `app/main.py` | config | import + `include_router(transfers.router)` (line 8-24, 41-55) | existing router registrations |
| `app/templates/base.html` | template | nav link `<a href="/transfers">Перемещение</a>` (after line 24) | writeoff nav link (line 24) |
| `app/templates/pages/reports_landing.html` | template | add `· <a href="/reports/expiry">Сроки годности</a>` (line 5) | existing report links |
| `tests/test_batches.py` | test | add `expiring_batches()` cases | existing `open_batches` tests |
| `tests/test_reports.py` | test | add `/reports/expiry` route cases | existing report route tests |

> `history_rows.html` needs NO change — `"transfer"` is stock-affecting, so it already renders the «Партия: …» line, and the «Тип» label comes from the `OPERATION_TYPE_LABELS` Jinja global (registered in `app/routes/__init__.py:18`).
> `app/routes/__init__.py` needs NO change — it exposes `OPERATION_TYPE_LABELS` globally; the new dict entry flows through automatically.
> **No Alembic migration** — `operations.type` is `String(20)` with no CHECK constraint; the destination batch is an ordinary `batches` row.

---

## Pattern Assignments

### `app/services/transfers.py` (service, CRUD/write) — NEW

**Analogs:** `app/services/writeoffs.py` (confirm-gate + validation shape), `app/services/receipts.py` (batch creation + `record_operation(commit=False)` + one commit).

**Signature + validation pattern** — copy from `writeoffs.py:32-102` (`register_writeoff`):
```python
def register_transfer(
    session: Session, *, code: str, name: str, qty_raw: str,
    batch_id: str = "", dest_warehouse_id: str = "", confirm: str = "",
) -> tuple[dict | None, dict[str, str]]:
    errors: dict[str, str] = {}
    code = code.strip()
    if not code:
        errors["code"] = "Укажите код товара."
    # WR-01 qty guard verbatim from writeoffs.py:63-66 — isascii()+isdigit(), never bare int()
    qty_text = qty_raw.strip()
    qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
    if qty <= 0:
        errors["quantity"] = QTY_ERROR
    if errors:
        return None, errors
    # active-only product lookup (writeoffs.py:77-81)
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is None:
        return None, {"code": PRODUCT_NOT_FOUND_TMPL.format(code=code)}
    # source-batch ownership guard (writeoffs.py:86-88) — client batch_id untrusted
    source = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
    if source is None or source.product_id != product.id:
        return None, {"batch": BATCH_REQUIRED_ERROR}
    # NEW guard (Pitfall 4): dest warehouse must be active AND != source WH.
    # Validate dest_warehouse_id against active_warehouses(session) ids.
    # reject dest_warehouse_id == source.warehouse_id with a RU error.
```

**Warn-but-allow over-qty gate** — copy verbatim from `writeoffs.py:92-102`, scoped to `source.quantity`:
```python
if confirm != "1" and qty > source.quantity:
    return ({"oversell": {"product": product,
                          "available": source.quantity,
                          "requested": qty}}, {})
```

**Two-row write (the ONLY genuinely new logic)** — copy from `receipts.py:210-257`:
```python
local_today = datetime.now(ZoneInfo(settings.display_tz)).date()  # only if regenerating name
dest = Batch(
    id=new_id(),
    product_id=product.id,
    warehouse_id=dest_warehouse_id,
    name=source.name,                 # discretion (Open Q1): copy source name — preserves identity
    expiry=source.expiry,
    price_cents=source.price_cents,   # THIS preserves cost/price history — direct assign, never `or`
    location=source.location,
    comment=source.comment,
    quantity=0,
    is_legacy=0,
)
session.add(dest)                     # MUST precede record_operation so autoflush inserts it (Pitfall 2)
try:
    record_operation(session, type_="transfer", product_id=product.id,
                     qty_delta=-qty, batch_id=source.id, commit=False)
    record_operation(session, type_="transfer", product_id=product.id,
                     qty_delta=+qty, batch_id=dest.id, commit=False)
    session.commit()
except (IntegrityError, ValueError):
    session.rollback()
    return None, {"form": SAVE_FAILED_ERROR}
return {"product": product, "source": source, "dest": dest}, {}
```

**Recent list helper** — copy `recent_writeoffs` from `writeoffs.py:121-130`, filter `Operation.type == "transfer"` (note: two rows per transfer — the recent-list query returns both directions; render accordingly or filter to `qty_delta < 0` for the "out" line).

---

### `app/routes/transfers.py` (route, request-response + HTMX) — NEW

**Analog:** `app/routes/writeoffs.py` (entire file — 1:1 mirror).

**Route set** — mirror `writeoffs.py`:
- `GET /transfers` → page (writeoffs.py:25-33)
- `GET /transfers/lookup` → 204-vs-fill contract via `lookup_prefill()` + `open_batches()` oob-swap (writeoffs.py:36-67). Note: transfer lookup lists open batches across **ALL** warehouses (source may be any WH).
- `GET /transfers/batch-pick` → re-query + re-validate ownership on every pick (writeoffs.py:70-96). **Also** compute the destination-warehouse `<select>` options here = `active_warehouses(session)` minus `source.warehouse_id`.
- `POST /transfers` → the full try/except + oversell + errors + success flow (writeoffs.py:99-189).

**Defensive rollback on POST failure** — copy verbatim from `writeoffs.py:135-150` (Pitfall 7):
```python
except Exception:  # noqa: BLE001 — block error, never a raw 500
    session.rollback()
    logger.exception("register_transfer failed")
    context = {"errors": {"form": SAVE_FAILED_ERROR}, "form": form_echo,
               "focus_code": False, "include_oob_rows": False,
               "selected_batch": selected_batch}
    return templates.TemplateResponse(request, "partials/transfer_form.html",
                                      context, status_code=422)
```

**Oversell + errors + success branches** — copy structure from `writeoffs.py:152-189` (oversell → no status change; errors → 422; success → fresh form + `focus_code=True` + oob recent rows).

**Route-order note (writeoffs.py:19-20):** declare literal `/transfers/lookup`, `/transfers/batch-pick` BEFORE any parameterized `/transfers/{...}`.

**Imports** — mirror `writeoffs.py:1-17`:
```python
from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import open_batches, active_warehouses
from app.services.receipts import lookup_prefill
from app.services.transfers import recent_transfers, register_transfer
```

---

### `app/services/batches.py` — add `expiring_batches()` (read helper)

**Analog:** `open_batches()` (batches.py:15-32) — same `quantity > 0` idiom, portable ORM.

RESEARCH-verified implementation (10-RESEARCH.md:312-333):
```python
def expiring_batches(session: Session) -> list[dict]:
    """Open batches (quantity > 0) with a set expiry, earliest first (LOT-06/D-07)."""
    rows = session.execute(
        select(Batch, Product, Warehouse)
        .join(Product, Batch.product_id == Product.id)
        .join(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(Batch.quantity > 0, Batch.expiry.is_not(None))
        .order_by(Batch.expiry.asc(), Batch.created_at.asc())
    ).all()
    return [{"batch": b, "product": p, "warehouse": w} for b, p, w in rows]
```
Note: NULL expiry excluded by `is_not(None)`, so `nullslast` is unnecessary. `Warehouse` import must be added (already imported in this module).

---

### `app/routes/reports.py` — add `/reports/expiry`

**Analog:** `reports_stock_page` (reports.py:153-165) — plain GET, full-page render, no HX partial, no period filter.
```python
@router.get("/reports/expiry")
def reports_expiry_page(request: Request, session: Session = Depends(get_session)):
    today = datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()  # LOCAL date, not UTC
    context = {"rows": expiring_batches(session), "today": today}
    return templates.TemplateResponse(request, "pages/reports_expiry.html", context)
```
Import `expiring_batches` from `app.services.batches`; `settings`/`ZoneInfo` already used in reports.py for local-date logic (verify import block).

---

### `app/templates/pages/reports_expiry.html` — NEW read-only report

**Analog:** `pages/reports_stock.html` (whole file). Extend base, single `<table>`, empty-state row.
- Columns (D-07): product, warehouse, expiry (`{{ row.batch.expiry | ru_date }}`), remaining qty, price (`{{ row.batch.price_cents | cents }}`), comment.
- Expired marker: `{% if row.batch.expiry < today %}` → muted/«просрочено» badge, row stays in list.
- Empty state: `<p class="empty-state muted">…</p>` (reports_stock.html:7).
- Comment/name are untrusted stored input → autoescape only, NEVER `|safe`.
- Do NOT include `period_filter.html` (D-07 — expiry is not a period query).

---

### `app/templates/partials/transfer_form.html` — NEW (the main swapped partial)

**Analog:** `partials/writeoff_form.html` (whole file). Copy verbatim, rename `writeoff`→`transfer` on ids/urls, and:
- Keep the `hx-on::load` focus hook (Pitfall 6) — `id="transfer-form-wrap"`, form `id="transfer-form"`.
- Keep the code→lookup `hx-get="/transfers/lookup"` debounced input (writeoff_form.html:28-34).
- Keep the `name-wrap` before-swap guard (writeoff_form.html:23-24).
- Include `partials/transfer_batch_wrap.html` for the source batch picker (writeoff_form.html:52-58).
- **Replace** the reason/note fields with the **destination-warehouse `<select>`** (options = active warehouses minus source WH) and the qty field. Model the `<select>` on the `WRITEOFF_REASONS` select block (writeoff_form.html:65-70) but iterate warehouses passed in context.
- Success line: «Перемещение сохранено: {name} — {qty} шт.» (writeoff_form.html:7).
- oob recent rows via `include_oob_rows` (writeoff_form.html:86-90).

### `app/templates/partials/transfer_oversell.html` — NEW

**Analog:** `partials/writeoff_oversell.html` (whole file, 22 lines). Copy verbatim; change ids `writeoff-oversell-warning`→`transfer-oversell-warning`, `form="transfer-form"`, `hx-post="/transfers"`, RU text «Товара не хватает в партии … перемещаете {requested}», button «Переместить всё равно». Keep `hx-vals='{"confirm": "1"}'` re-POST (writeoff_oversell.html:12-15) and the client-only dismiss button (writeoff_oversell.html:18-19). Autoescape only, never `|safe`.

### `app/templates/partials/transfer_batch_wrap.html` — NEW

**Analog:** `partials/writeoff_batch_wrap.html` (whole file, 23 lines). Copy verbatim; set `batch_input_name = "batch_id"`, `pick_url = "/transfers/batch-pick"`, id `batch-wrap-first`. Reuses the shared `partials/batch_picker.html` (Phase 9 D-04) unchanged.

### `app/templates/partials/transfer_lookup.html` — NEW

**Analog:** `partials/writeoff_lookup.html`. The `/transfers/lookup` route renders this to oob-swap the open-batch picker after a code lookup.

### `app/templates/pages/transfer_form.html` — NEW (page wrapper)

**Analog:** `pages/writeoff_form.html` (10 lines):
```jinja
{% extends "base.html" %}
{% block content %}
<h1>Перемещение</h1>
{% include "partials/transfer_form.html" %}
{% with oob = False %}
{% include "partials/transfer_rows.html" %}
{% endwith %}
{% endblock %}
```

### `app/templates/partials/transfer_rows.html` — NEW recent list

**Analog:** `partials/writeoff_rows.html`. Renders recent transfers (oob on success, plain on page load via `oob` flag).

---

### `tests/test_transfers.py` — NEW

**Analog:** `tests/test_writeoffs.py` / `tests/test_receipts.py`. Fixtures from `conftest.py`: `session`, `product`, `warehouse`, `batch`, `stocked_product`, `client`. Needs a stocked source batch in a known WH + a second active WH (extend fixtures or build inline). Test map from 10-RESEARCH.md:410-424 (two-row write, net-zero projection, dest inheritance, full-empties-source, confirm gate, same-WH reject, tampered-id reject, rebuild invariant, history label, HTTP happy paths).

---

## Shared Patterns

### Single write path (record_operation)
**Source:** `app/services/ledger.py:34-127`
**Apply to:** `transfers.py` — the ONLY sanctioned writer of operation rows + `Product.quantity`/`Batch.quantity`. Transfer stages two `commit=False` calls, one `session.commit()`. Never INSERT operations or mutate quantities directly. `session.add(dest_batch)` before the positive-delta call (autoflush inserts it so `session.get(Batch, dest.id)` resolves).

### Warn-but-allow confirm=1 gate
**Source:** `app/services/writeoffs.py:92-102` + `app/templates/partials/writeoff_oversell.html:12-15`
**Apply to:** transfer over-quantity guard — read-only check, ZERO writes until `confirm == "1"`, scoped to **`source.quantity`** (never `product.quantity` — a transfer is net-zero at product level, Pitfall 3).

### Untrusted-identifier re-validation (V4/T-09)
**Source:** `app/services/writeoffs.py:86-88`, `app/services/ledger.py:97-98`, `app/services/receipts.py:226-234`
**Apply to:** every `batch_id` and `warehouse_id` from the client — re-check `source.product_id == product.id`, `dest_warehouse_id ∈ active_warehouses`, `dest_warehouse_id != source.warehouse_id`. Server-side, before any write.

### qty parsing guard (V5)
**Source:** `app/services/writeoffs.py:63-66`
**Apply to:** transfer qty — `qty_text.isascii() and qty_text.isdigit()` then `> 0`, never bare `int()`.

### Local-date (not UTC) comparison
**Source:** `app/services/receipts.py:210`, RESEARCH Pattern 3
**Apply to:** expiry report `today` — `datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()`.

### HTMX 204-vs-fill lookup + 422 swap + focus hook
**Source:** `app/services/receipts.py:260-287` (`lookup_prefill`), `app/routes/writeoffs.py:36-67`, `app/templates/partials/writeoff_form.html:6,23-24,28-34`
**Apply to:** `/transfers/lookup`, the `name-wrap` before-swap guard, the `hx-on::load` focus-code hook, and returning the form partial at `status_code=422` on validation errors.

### Defensive rollback before re-query on POST failure
**Source:** `app/routes/writeoffs.py:135-150`
**Apply to:** the `POST /transfers` try/except — `session.rollback()` + log + return form partial at 422 (Pitfall 7 / PendingRollbackError).

### RU op-type label via Jinja global
**Source:** `app/routes/__init__.py:18`, `app/models.py:59-68`
**Apply to:** just add `"transfer": "Перемещение"` to `OPERATION_TYPE_LABELS`; `/history` renders it automatically (no template edit).

### Autoescape-only XSS discipline
**Source:** `app/templates/partials/batch_picker.html:22-23`, `writeoff_oversell.html:4-5`
**Apply to:** all new templates rendering `product.name` / batch `comment` / `location` — autoescape only, NEVER `|safe`.

---

## No Analog Found

None. Every file in this phase has a direct, verified in-repo analog. The only genuinely new logic is `register_transfer()` (two-row write via the existing single write path) and `expiring_batches()` (one `select()` mirroring `open_batches`).

---

## Metadata

**Analog search scope:** `app/services/`, `app/routes/`, `app/templates/pages/`, `app/templates/partials/`, `app/models.py`, `app/main.py`, `tests/`.
**Files read for extraction:** `writeoffs.py` (service + route), `receipts.py` (batch-create/lookup section), `ledger.py`, `batches.py`, `reports.py`, `models.py`, `main.py`, `routes/__init__.py`, `writeoff_form.html`, `writeoff_oversell.html`, `writeoff_batch_wrap.html`, `reports_stock.html`, `reports_landing.html`, `writeoff_form.html` (page), `base.html` (nav).
**Pattern extraction date:** 2026-07-12
</content>
</invoke>
