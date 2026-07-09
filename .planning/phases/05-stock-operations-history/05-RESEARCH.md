# Phase 5: Stock Operations & History - Research

**Researched:** 2026-07-09
**Domain:** Internal codebase wiring — non-sale stock movements (write-off, return, correction) + full operation history, all through the existing append-only ledger. No external technology domain.
**Confidence:** HIGH (every claim verified by reading the current source; external research skipped per CONTEXT — well-understood local-CRUD on ledger patterns already shipped in Phases 1–4)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Write-off reason is a **hybrid**: required category (fixed list) + optional free-text note.
- **D-02:** Both stored in operation `payload`, shape `{"reason_code": "<latin>", "note": "<free text or empty>"}`. `reason_code` values are Latin/portable; RU labels live in a code constant.
- **D-03:** Default category set (RU label → code): Брак → `damaged`, Просрочка → `expired`, Потеря → `lost`, Личное использование → `personal`, Подарок → `gift`, Прочее → `other`. `other` pairs with the note. This is exactly what Phase 6 RPT-03 will group by. Wording adjustable by planner.
- **D-04:** Write-off is by product code (reuse receipt/sale lookup + name autofill), quantity required (positive int), no price fields. Stock may go to/through zero. Planner confirms whether an oversell-style warn/confirm is shown (recommended: yes — reuse Phase 4 pattern — Claude's discretion).
- **D-05:** Return **starts from a line of the original sale** (recent-sales list and/or a customer's purchase history). Operator picks the sale line to return.
- **D-06:** Return is a `return` operation with **qty_delta > 0**, carrying `sale_id` = original `Sale.id` and `product_id` = the sold product.
- **D-07:** **Price/cost symmetry** — return copies `unit_price_cents` and `unit_cost_cents` from the original sale line's frozen snapshot, NOT from the current product card (preserves SAL-05).
- **D-08:** **Partial returns allowed.** Returnable qty for a line = sold − already returned. Service must aggregate prior `return` ops for that `sale_id`+`product_id` so returned qty ≤ remaining returnable. Planner decides aggregation granularity (by sale line vs by sale+product).
- **D-09:** **Both correction input modes**: counted-absolute (qty_delta = counted − current, show current next to input) AND delta (+/−, written as-is).
- **D-10:** Correction is **always** a `correction` operation, never a direct edit of `products.quantity`. A zero net delta is a no-op / rejected gracefully.
- **D-11:** Optional reason/note for correction in `payload` (e.g. `{"note": "...", "mode": "count"|"delta"}`). Recommended default UI mode = counted quantity.
- **D-12:** This **replaces the walking-skeleton `POST /ops`** correction (`app/routes/ops.py`). Migrate its behavior; do NOT leave two correction paths.
- **D-13:** A **dedicated `/history` page**: all operations, all products, newest first.
- **D-14:** **Filters:** by operation type and by product only. **Date-range filtering deferred to Phase 6.**
- **D-15:** **Pagination / limit** so the ledger stays fast (e.g. 50 rows/page or "load more" — planner's discretion; must not load the whole ledger unbounded).
- **D-16:** **Columns:** type (RU-labeled), product (name/code), quantity (signed ±), unit price/cost where present, reason (from `payload`), who (`created_by`), when (`created_at | local_dt`). Reuse/extend `partials/ledger_rows.html`.
- **D-17:** Add a **nav link** in `base.html` (e.g. «История» / «Операции»). Home single-product ledger may stay or be simplified (Claude's discretion); authoritative full history is `/history`.

### Claude's Discretion
- Page/route/template structure & naming: whether write-off, return, correction are three separate pages/forms or share a shell; exact URLs (e.g. `/writeoff`, `/returns`, `/corrections`, `/history`).
- Migration number **0005** only if genuinely new column/index is justified — but note `writeoff`/`return`/`correction` already in `OPERATION_TYPES`, `sale_id`/`payload` already exist, and `ix_operations_sale_id` already exists → **no schema change expected**.
- Exact RU UI text, empty-state and confirmation wording; form layout.
- Whether write-off shows an oversell-style warn/confirm (recommended: yes) and floor behavior.
- Default correction input mode in the UI (recommended: counted quantity).
- Pagination mechanism and page size for `/history`; whether a per-product history view is also surfaced on the product card (optional).
- Exact `payload` key names/shape (proposals are guidance, not locked schema).

### Deferred Ideas (OUT OF SCOPE)
- Write-off / sales / profit / stock reports and CSV export — Phase 6 (RPT-01..04, BCK-02). This phase only captures the data.
- Date-range filtering on history — Phase 6 (D-14).
- Per-product history view on the product card — optional, not required by OPS-04.
- Purchase-frequency reminders / interested-customer lists — CST-V2-01/02.
- Multi-currency, multi-operator sync, user roles — out of scope per PROJECT.md.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OPS-01 | User can write off stock with a reason | New `app/services/writeoffs.py` → `record_operation(type_="writeoff", qty_delta=-qty, payload={"reason_code","note"})`. Reuse receipt lookup ergonomics (§Pattern 2). Category constant (§Don't Hand-Roll). |
| OPS-02 | User can register a return linked to the original sale; stock increases | New `app/services/returns.py`. Entry point = existing `recent_sales`/`purchase_history` rows (already carry `op.sale_id` + `product`). `record_operation(type_="return", qty_delta=+qty, sale_id=<Sale.id>, unit_price_cents/unit_cost_cents copied from origin sale op)`. Returnable-qty aggregation (§Pattern 3). |
| OPS-03 | User can correct stock (recorded as an operation, not a direct edit) | Correction service (new `app/services/corrections.py` or fold into an operations service) → `record_operation(type_="correction", qty_delta=<signed>)`. Two input modes (§Pattern 4). Replaces `POST /ops` (D-12). |
| OPS-04 | User can view full operation history (what, when, how much) | New `GET /history` route + service query over all `operations` with type/product filters + pagination. New history table partial extending `ledger_rows.html` (§Pattern 5). |
</phase_requirements>

## Summary

Phase 5 is pure internal wiring on top of a data foundation that is already complete. The append-only ledger, the single write path (`record_operation`), the three operation types (`writeoff`, `return`, `correction`), the `payload` JSON column, the `sale_id` FK link, and the `ix_operations_sale_id` index all already exist and are exercised by shipped code. No schema migration is expected. Every one of the four flows is a thin route + a fat service that stages ledger rows through `record_operation` and commits once — the exact shape already used by `receipts.py` (write-off analog) and `sales.py` (return analog).

The only genuinely new logic is: (1) the **returnable-quantity aggregation** for partial returns (sum sold vs. sum already-returned per `sale_id`+`product_id`), (2) the **counted-vs-delta correction** arithmetic and zero-net rejection, (3) a **fixed write-off category constant** with RU labels, and (4) a **paginated, filterable `/history` view** with RU type labels and a payload-aware "reason" column. Three of the four success criteria are stock-mutating and must be proven by asserting ledger state (`compute_stock` / `Product.quantity`); the fourth is a read view proven by row content and filter/pagination behavior.

**Primary recommendation:** Add three services (`writeoffs.py`, `returns.py`, `corrections.py`), three thin routes + form templates, a `GET /history` route with a new `history_rows.html` partial, and a nav link — all built strictly on `record_operation` (staged `commit=False`, one commit per request). Add NO migration. Replace `app/routes/ops.py` + the home correction form rather than duplicating it. Introduce two small constants: `WRITEOFF_REASONS` (RU→latin) and `OPERATION_TYPE_LABELS` (latin→RU).

## Architectural Responsibility Map

This is a single-process server-rendered FastAPI + HTMX monolith. "Tiers" here are the app's own layers (thin routes / fat services / templates / ledger-DB), per the established convention.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Write-off validation + ledger write | Service (`writeoffs.py`) | Ledger (`record_operation`) | Fat services own business rules; ledger owns the single write path (WR-03). |
| Write-off reason category set | Constant (module-level) | Template (dropdown) | Latin codes stored, RU labels rendered — mirrors how UI text stays RU while stored values stay portable (D-02). Never trust the posted code; validate against the constant server-side. |
| Return returnable-qty cap | Service (`returns.py`) | Ledger (read: aggregate ops) | Aggregation is business logic; reads `operations` filtered by the existing `sale_id` index. |
| Return price/cost snapshot | Service (`returns.py`) | Ledger (read origin sale op) | Copy the origin op's frozen `unit_*_cents`; must NOT read the current product card (D-07 / SAL-05). |
| Correction arithmetic (count vs delta) | Service (`corrections.py`) | — | Pure server-side computation of signed `qty_delta`; zero-net rejected before any write. |
| Correction persistence | Ledger (`record_operation`) | — | OPS-03 core rule: never edit `products.quantity` directly; the single write path already enforces this. |
| History query + filter + pagination | Service (read helper) | Route (query params) | Fat service returns page rows + filter state; route parses `type`/`product`/page query params. |
| History rendering (RU labels, reason, signed qty) | Template (`history_rows.html`) | Filters (`local_dt`, `cents`) | Presentation only; autoescape (no `\|safe`) because payload notes are untrusted operator text. |
| Nav entry point | Template (`base.html`) | — | One `<a href="/history">` link (D-17). |

## Standard Stack

**No new libraries.** CONTEXT explicitly forbids proposing new external dependencies — this phase uses only what Phases 1–4 already installed. The stack is fixed in `./CLAUDE.md` (FastAPI, SQLAlchemy 2.0, SQLite, Jinja2, vendored htmx 2.0.10, pytest, ruff, uv). `[VERIFIED: pyproject.toml, app/* source]`

### Reused internal modules (the real "stack" for this phase)

| Module / Symbol | Role in Phase 5 | Verified |
|-----------------|-----------------|----------|
| `app.services.ledger.record_operation(session, *, type_, product_id, qty_delta, unit_cost_cents=, unit_price_cents=, payload=, sale_id=, commit=)` | THE single write path for all three ops. Guards unknown/soft-deleted product (ValueError). Stamps audit fields, seq, timestamps. | `[VERIFIED: app/services/ledger.py:29-90]` |
| `app.services.ledger.compute_stock(session, product_id)` | Ledger-truth recompute — use for assertions/tests and to show "current" in correction if desired. | `[VERIFIED: app/services/ledger.py:93-99]` |
| `app.models.OPERATION_TYPES` | Already contains `writeoff`, `return`, `correction`. No edit needed. | `[VERIFIED: app/models.py:34-43]` |
| `app.models.Operation` (`qty_delta` signed, `unit_cost_cents`, `unit_price_cents`, `payload` JSON, `sale_id` FK→sales.id, `product_id` indexed) | Row shape for every op. `sale_id` set at INSERT only (trigger blocks later UPDATE). | `[VERIFIED: app/models.py:103-129]` |
| `app.services.sales.recent_sales(session, limit)` → `[{"op","product"}]` | Return entry point #1. Rows already expose `op.sale_id` and `op.unit_price_cents`/`unit_cost_cents`. | `[VERIFIED: app/services/sales.py:219-228]` |
| `app.services.customers.purchase_history(session, customer_id)` → `[{"op","product"}]` | Return entry point #2 (per-customer). Same row shape. | `[VERIFIED: app/services/customers.py:147-159]` |
| `app.services.receipts.lookup_prefill` + `GET /receipts/lookup` (204 pattern) | Closest analog for the write-off code→name autofill form. | `[VERIFIED: app/services/receipts.py:145-172, app/routes/receipts.py:30-62]` |
| `app.services.dictionary.lookup` + `GET /dictionary/lookup` | Underlying 204 autofill primitive. | `[VERIFIED: app/routes/dictionary.py:27-40]` |
| `app.core.to_cents / format_cents / utcnow_iso / new_id` | Money/id/time conversions (only sanctioned points). | `[VERIFIED: app/core.py]` |
| Jinja filters `local_dt`, `cents` (registered in `app/routes/__init__.py`) | Timestamp + money rendering in `/history`. | `[VERIFIED: app/routes/__init__.py:8-12]` |
| `tests/conftest.py` fixtures: `session`, `product`, `stocked_product` (8 in stock), `customer`, `client` | Test scaffolding. `stocked_product` fits write-off/correction; build a sale for return tests. | `[VERIFIED: tests/conftest.py]` |

### Installation
None. `[VERIFIED: no new packages required]`

## Package Legitimacy Audit

**N/A — this phase installs zero external packages.** All work is internal wiring on the existing dependency set (fixed in `./CLAUDE.md`). No registry verification required.

## Architecture Patterns

### System Architecture Diagram

```
                     ┌──────────────────────────────────────────────┐
  Operator (browser) │  HTMX forms (RU UI, vendored htmx.min.js)     │
                     └───────────────┬──────────────────────────────┘
                                     │ POST (form-encoded) / GET (lookup, history)
                                     ▼
   ┌───────────────────────── Thin routes (app/routes/*) ────────────────────────┐
   │  /writeoff  /writeoff/lookup   /returns   /corrections   /history            │
   │  Typed Form(...)/Query(...) = input gate (422 on garbage) → call service     │
   └───────────────┬───────────────┬───────────────┬───────────────┬─────────────┘
                   ▼               ▼               ▼               ▼
        writeoffs.py       returns.py      corrections.py    history read helper
        (validate reason,  (returnable cap, (count/delta →    (filter type+product,
         qty>0)             copy frozen      signed delta,      paginate, newest-first)
                            price/cost)      reject zero-net)
                   │               │               │               │ (read-only)
                   └───────┬───────┴───────┬───────┘               │
                           ▼               ▼                        ▼
           record_operation(...) — SINGLE WRITE PATH        SELECT operations
           stage commit=False → ONE session.commit()        JOIN products
           (guards unknown/soft-deleted product)            ORDER BY created_at DESC, seq DESC
                           │                                 LIMIT/OFFSET
                           ▼
           operations (append-only; triggers ABORT UPDATE/DELETE)
           products.quantity += qty_delta  (cached projection, recomputable)
                           │
                           ▼
           Rendered partial swapped into the page (form reset + oob recent list,
           or /history rows) — autoescape only, never |safe
```

### Recommended Project Structure (additions only)
```
app/
├── services/
│   ├── writeoffs.py     # register_writeoff(): reason validation + record_operation(writeoff)
│   ├── returns.py       # returnable_qty(), register_return(): cap + frozen price/cost copy
│   ├── corrections.py   # register_correction(): count|delta → signed delta, zero-net reject
│   └── operations.py    # (optional) history_view(): filtered + paginated read helper
├── routes/
│   ├── writeoffs.py     # /writeoff, /writeoff/lookup  (or fold lookup reuse)
│   ├── returns.py       # /returns  (+ return entry from recent-sales / purchase-history rows)
│   ├── corrections.py   # /corrections  (REPLACES ops.py)
│   └── history.py       # GET /history  (+ filter/pagination params)
└── templates/
    ├── pages/{writeoff_form,return_form,correction_form,history}.html
    └── partials/{writeoff_form,writeoff_lookup,return_confirm,correction_form,
                  history_rows,history_filters}.html
```
Naming/URLs are Claude's discretion (D-17). `app/routes/ops.py` is **deleted or repurposed**, not kept alongside the new correction route.

### Pattern 1: Single-line ledger write (write-off / return / correction)
**What:** Each op is one `record_operation` call staged `commit=False`, then one `session.commit()` in a try/except that rolls back on `(IntegrityError, ValueError)`. For a genuinely single-row op you *may* call with `commit=True`, but the staged+one-commit shape matches the codebase and keeps error handling uniform.
**When to use:** All three write flows.
**Example (write-off, modeled on `receipts.register_receipt` / `sales.register_sale`):**
```python
# Source: derived from app/services/receipts.py + app/services/sales.py (VERIFIED)
def register_writeoff(session, *, code, qty_raw, reason_code, note):
    errors = {}
    code = code.strip()
    if not code:
        errors["code"] = "Укажите код товара."
    qty_text = qty_raw.strip()
    # Pitfall: isdigit() alone accepts non-ASCII digits int() can't parse (sales.py WR-01)
    qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
    if qty <= 0:
        errors["quantity"] = "Укажите количество — целое число больше нуля."
    if reason_code not in WRITEOFF_REASONS:          # server-side allow-list (V5)
        errors["reason"] = "Выберите причину списания."
    if errors:
        return None, errors

    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is None:
        return None, {"code": f"Товар с кодом „{code}“ не найден."}

    # (Optional D-04 oversell warn/confirm: compare qty to product.quantity, reuse Phase 4 shape)
    try:
        op = record_operation(
            session, type_="writeoff", product_id=product.id,
            qty_delta=-qty, payload={"reason_code": reason_code, "note": note.strip()},
            commit=True,
        )
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"form": "Не удалось сохранить. Попробуйте ещё раз."}
    return {"product": product, "operation": op}, {}
```

### Pattern 2: Code→name autofill form (write-off entry)
**What:** Reuse the receipt/sale lookup ergonomics — a debounced `hx-get` to a lookup endpoint that returns a name-fill partial or **204 No Content** when there is nothing to fill; a non-empty typed name is never overwritten; htmx is configured to ignore 204 (`base.html` htmx-config).
**When to use:** Write-off form (D-04). Correction form can optionally reuse the same lookup.
**Example:** copy `GET /receipts/lookup` (`app/routes/receipts.py:30-62`) structure; the service call is `receipts.lookup_prefill` or a write-off-specific one that returns name only (no price fields — D-04). `[VERIFIED: app/routes/receipts.py, app/templates/pages/receipt_form.html]`

### Pattern 3: Returnable-quantity aggregation (partial returns, D-08)
**What:** For a chosen `sale_id` + `product_id`:
- `sold = -SUM(qty_delta)` over `type='sale'` rows (sale deltas are negative → negate to positive)
- `returned = SUM(qty_delta)` over `type='return'` rows (positive)
- `remaining = sold - returned`; reject a requested return where `qty > remaining`.
**Index:** `ix_operations_sale_id` already exists (migration 0004) and `product_id` is indexed — the aggregate filter is covered; **no migration 0005 needed for the cap.** `[VERIFIED: alembic/versions/0004_sales_customers.py:82, app/models.py:111-124]`
**Aggregation granularity (planner decision, D-08):** Recommend **aggregate the CAP by `sale_id`+`product_id`** (simplest, matches the index) while **copying the clicked origin sale op's own frozen `unit_price_cents`/`unit_cost_cents`** onto the return op (D-07). Edge case to note for the planner: if one basket contains the same product on two lines at different prices, a sale+product cap is unambiguous but "which frozen price" is only well-defined if you return from a *specific* line — which the D-05 entry point (a recent-sales / purchase-history row = one sale op) naturally gives you. So: cap by sale+product, price from the specific origin op.
**Example:**
```python
# Source: query style from app/services/customers.py:147-159 + app/services/ledger.py (VERIFIED)
def returnable_qty(session, sale_id, product_id):
    sold = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.sale_id == sale_id, Operation.product_id == product_id,
            Operation.type == "sale")) or 0
    returned = session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(
            Operation.sale_id == sale_id, Operation.product_id == product_id,
            Operation.type == "return")) or 0
    return (-sold) - returned   # positive remaining returnable
```
The `return` op is then `record_operation(type_="return", product_id=..., qty_delta=+qty, sale_id=sale_id, unit_price_cents=<origin op>, unit_cost_cents=<origin op>, commit=True)`.

### Pattern 4: Correction with two input modes (D-09/D-10)
**What:** Compute a signed `qty_delta`, then reject a zero net before writing.
- **counted (absolute):** `qty_delta = counted - current`. Use the cached `Product.quantity` as "current" (the authoritative projection — `sales.py` A4 says do NOT recompute via `compute_stock` in the write path); display it next to the input.
- **delta:** `qty_delta = entered` (signed int).
- **zero net:** `if qty_delta == 0: return None, {"quantity": "Количество не изменилось — нечего записывать."}` (no-op, no row).
- `payload = {"note": note.strip() or None, "mode": mode}` where `mode ∈ {"count","delta"}` — validate `mode` server-side (V5).
**Replaces `POST /ops`:** the current route takes a raw `qty_delta` with no reason and re-renders the single-product home ledger (`ledger_view` + `ledger_rows.html`). Migrate that behavior into the correction flow; update `home.html`'s form (it posts to `/ops`). `[VERIFIED: app/routes/ops.py, app/templates/pages/home.html:6-11]`

### Pattern 5: /history read view (OPS-04, D-13..D-16)
**What:** A read-only service query over ALL operations joined to products, newest-first, with optional `type` and `product` filters and LIMIT/OFFSET pagination; a template that RU-labels the type, shows signed qty, price/cost where present, and a payload-derived reason.
**Query shape (extends `recent_sales`/`recent_receipts`):**
```python
# Source: app/services/sales.py:219-228 (recent_sales) generalized (VERIFIED pattern)
stmt = (select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .order_by(Operation.created_at.desc(), Operation.seq.desc()))
if type_filter:    stmt = stmt.where(Operation.type == type_filter)
if product_id:     stmt = stmt.where(Operation.product_id == product_id)
stmt = stmt.limit(page_size + 1).offset(page * page_size)   # +1 sentinel = "has next page"
```
**Pagination mechanism (D-15, planner discretion):** recommend simple LIMIT/OFFSET page-based navigation with a fetch-one-extra sentinel to know whether a "Показать ещё" / next-page control should render. Adequate for a single operator for years; keyset pagination is unnecessary complexity here.
**Type labels:** add `OPERATION_TYPE_LABELS = {"receipt":"Приход","sale":"Продажа","writeoff":"Списание","return":"Возврат","correction":"Корректировка","price_change":"Цена","product_created":"Создан","product_edited":"Изменён"}` (planner may scope /history to stock-affecting types only, but OPS-04 says "full operation history"). Render `LABELS.get(op.type, op.type)`.
**Reason column:** payload is a dict (JSON). Render per type: write-off → `WRITEOFF_REASONS` label + note; correction → note (+ mode). Keep autoescape — note is untrusted operator text.
**Template:** `ledger_rows.html` today is single-product (has a stock-summary block + a 4-col table: type/qty/who/when). For /history, create a **new `history_rows.html`** partial with columns type/product/qty(±)/price/cost/reason/who/when rather than overloading the home partial; the home partial can stay for the (optional) simplified home view. `[VERIFIED: app/templates/partials/ledger_rows.html]`

### Anti-Patterns to Avoid
- **Editing `products.quantity` directly (correction).** OPS-03 forbids it; `record_operation` is the only write path. `[VERIFIED: app/services/ledger.py:85-87]`
- **Reading the current product card price for a return.** Breaks D-07/SAL-05; copy the frozen origin-op snapshot. `[VERIFIED: app/templates/partials/purchase_history.html:1-3 warns of exactly this]`
- **Trusting the posted `reason_code`/`mode`.** Validate against the allow-list server-side (client dropdowns are tamperable — V5). `[ASSUMED — standard control]`
- **`\|safe` on payload notes / product names.** Stored operator text is untrusted (T-4-01 stored-XSS). Autoescape only. `[VERIFIED: codebase convention, e.g. recent_sales.html:3-4]`
- **`UPDATE`/`DELETE` on operations to "fix" a mistake.** Triggers ABORT it; a return/correction is a NEW row. `[VERIFIED: tests/test_ledger.py:42-60]`
- **`qty_text.isdigit()` without `.isascii()`.** Accepts superscript/other Unicode digits that `int()` rejects → uncaught ValueError. `[VERIFIED: app/services/sales.py:88-93]`
- **Leaving two correction paths.** Delete/repurpose `POST /ops` (D-12). `[VERIFIED: app/routes/ops.py]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Insert an operation + update stock | Manual `INSERT` / `products.quantity =` | `record_operation(...)` | Single write path; stamps audit/seq/time, guards soft-deleted product, atomic SQL increment. `[VERIFIED: ledger.py]` |
| Parse RU money "12,50" | Custom float parse | `app.core.to_cents` | Rejects inf/nan, ROUND_HALF_UP, integer cents. (Write-off/correction have no price, but any future amount uses this.) `[VERIFIED: core.py:28-47]` |
| Render cents / timestamps | Ad-hoc formatting | `\| cents`, `\| local_dt` filters | Already registered; consistent display. `[VERIFIED: routes/__init__.py]` |
| Code→name autofill | New JS/endpoint from scratch | Copy `GET /receipts/lookup` 204 pattern | Debounce, no-op-on-204, don't-overwrite-typed-name already solved. `[VERIFIED: routes/receipts.py]` |
| Returnable-qty tracking | Per-line ledger of returns in a new table | Aggregate existing `sale`/`return` ops by `sale_id`+`product_id` | Ledger is already the source of truth; `ix_operations_sale_id` exists. `[VERIFIED: models.py, migration 0004]` |
| Reason category storage | New `reasons` table / enum column | `payload` JSON + module constant `WRITEOFF_REASONS` | D-02/D-03; latin codes portable, RU labels in code; RPT-03 groups on the same codes. `[VERIFIED: models.py payload JSON; CONTEXT D-02/03]` |

**Key insight:** Phase 5 adds *behavior*, not *infrastructure*. The temptation is a new column/table for returns or reasons; the ledger + `payload` + the existing `sale_id` index already carry everything.

## Runtime State Inventory

Not a rename/refactor/migration phase — **section omitted** (greenfield feature wiring on existing schema). The one migration-adjacent question (does a schema change / migration 0005 exist?) is answered under Common Pitfalls and Open Questions: **no migration required**.

## Common Pitfalls

### Pitfall 1: Adding an unnecessary migration 0005
**What goes wrong:** Planner adds a migration for the new op types or a `sale_id`/`payload` column that already exists, or a batch migration that silently drops the append-only triggers.
**Why it happens:** Assuming new op types imply schema change. They don't — `OPERATION_TYPES` is a Python tuple with no DB CHECK constraint; `payload`, `sale_id`, and `ix_operations_sale_id` already exist.
**How to avoid:** Add **no** migration. If the planner ever decides a new index is warranted (it is not — sale_id is indexed), it MUST use a **native** `op.create_index`, never `batch_alter_table("operations")` (batch rebuild drops the immutability triggers — see migration 0004's docstring and `test_migration_0004_preserves_append_only_triggers`).
**Warning signs:** Any `alembic` file appearing in a Phase 5 plan; any `batch_alter_table("operations")`. `[VERIFIED: models.py:34-43, migration 0004, tests/test_ledger.py:136-181]`

### Pitfall 2: Return snapshot drift
**What goes wrong:** Return records the current card price/cost, so a later price change makes the reversed amount ≠ the sold amount, corrupting profit.
**How to avoid:** Read the origin sale **op's** `unit_price_cents`/`unit_cost_cents` and pass them straight into the return `record_operation`. Never touch `Product.*_cents`.
**Warning signs:** `returns.py` importing/reading `Product.sale_cents` or `Product.cost_cents`. `[VERIFIED: D-07; app/services/sales.py:174 freezes cost at sale time]`

### Pitfall 3: Over-returning
**What goes wrong:** Operator returns more than was sold (or more than remains), inflating stock.
**How to avoid:** Compute `returnable_qty(sale_id, product_id)` and reject `qty > remaining` with an RU error before writing. `[VERIFIED: D-08]`

### Pitfall 4: Correction sign confusion / no-op rows
**What goes wrong:** In counted mode the operator's number is written as a delta (huge wrong swing), or a zero-net correction writes a meaningless row.
**How to avoid:** In counted mode compute `counted - current`; reject `qty_delta == 0` gracefully. Show the current quantity next to the input (D-09). Default the UI to counted mode (safer). `[VERIFIED: D-09/D-10/D-11]`

### Pitfall 5: Focus lost after HTMX swap
**What goes wrong:** After a save the form is swapped and the cursor doesn't return to «Код», slowing fast entry.
**How to avoid:** Reuse the `hx-on::load="document.getElementById('code').focus()"` hook — `autofocus` does NOT fire inside swapped content. `[VERIFIED: app/templates/partials/receipt_form.html:5]`

### Pitfall 6: 4xx responses not swapped by htmx
**What goes wrong:** Validation partials returned with 422 are silently dropped.
**How to avoid:** The app already opts 422 into swapping via the `htmx-config` meta in `base.html`; return validation partials with `status_code=422` exactly like receipts/sales/dictionary do. `[VERIFIED: app/templates/base.html:9-10, app/routes/sales.py:159]`

### Pitfall 7: Returning/correcting a soft-deleted product
**What goes wrong:** `record_operation` raises `ValueError("product is deleted")` (IN-01 guard) — an uncaught raise becomes a 500.
**How to avoid:** Catch `ValueError` and surface a 4xx/RU message (routes already do this pattern for unknown products). A return whose product card was later soft-deleted is a real edge; decide gracefully (reject with a clear message). `[VERIFIED: app/services/ledger.py:66-68, app/routes/ops.py:27-30]`

## Code Examples

### Write-off op (stock decreases)
```python
# Source: app/services/ledger.py signature (VERIFIED)
record_operation(session, type_="writeoff", product_id=pid,
                 qty_delta=-qty, payload={"reason_code": "expired", "note": "партия просрочена"},
                 commit=True)
```

### Return op (stock increases, frozen amounts, linked to sale)
```python
# Source: app/services/sales.py sale write + Operation.sale_id (VERIFIED)
origin = session.get(Operation, origin_sale_op_id)   # the clicked recent-sales / purchase-history row
record_operation(session, type_="return", product_id=origin.product_id,
                 qty_delta=+qty, unit_price_cents=origin.unit_price_cents,
                 unit_cost_cents=origin.unit_cost_cents, sale_id=origin.sale_id,
                 commit=True)
```

### Correction op (counted mode)
```python
# Source: app/services/ledger.py + D-09 (VERIFIED signature, derived logic)
delta = counted - product.quantity          # product.quantity = cached projection
if delta == 0:
    return None, {"quantity": "Количество не изменилось — нечего записывать."}
record_operation(session, type_="correction", product_id=product.id,
                 qty_delta=delta, payload={"note": note or None, "mode": "count"}, commit=True)
```

### History filter + paginate (read)
```python
# Source: app/services/sales.py:219-228 generalized (VERIFIED pattern)
rows = session.execute(
    select(Operation, Product).join(Product, Operation.product_id == Product.id)
    .where(*( [Operation.type == t] if t else [] ))
    .order_by(Operation.created_at.desc(), Operation.seq.desc())
    .limit(page_size + 1).offset(page * page_size)
).all()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Walking-skeleton `POST /ops` raw correction (no reason, single-product home ledger) | Real `/corrections` flow with count/delta modes + optional note (D-12) | Phase 5 | `ops.py` deleted/repurposed; `home.html` form updated |
| Home single-product `ledger_view` as the only ledger display | Dedicated `/history` (all products, filters, pagination) as authoritative trail (D-13) | Phase 5 | Home view optional/simplified; `ledger_rows.html` complemented by `history_rows.html` |

**Deprecated/outdated:** `app/routes/ops.py` after this phase — do not extend it, replace it.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Cap-by-`sale_id`+`product_id` with price copied from the specific origin op is the right granularity | Pattern 3 | Low — D-08 leaves granularity to planner; both modes satisfy "returned ≤ returnable". Only edge (same product twice at different prices in one basket) is rare for a single reseller. |
| A2 | LIMIT/OFFSET page-based pagination is adequate (vs keyset) | Pattern 5 | Low — single operator, ledger grows slowly; OFFSET cost is negligible for years. |
| A3 | Server-side allow-list validation of `reason_code`/`mode` is expected | Anti-Patterns / Security | Low — standard V5 control; matches existing "don't trust client" posture. |
| A4 | `/history` should include ALL op types (incl. price_change/product_created), RU-labeled | Pattern 5 | Low — OPS-04 says "full operation history"; planner may scope to stock-affecting types (D-16 lists reason columns oriented to writeoff/correction). Confirm during planning. |
| A5 | Write-off default reason wording (Брак/Просрочка/…) is acceptable as-is | User Constraints D-03 | Low — CONTEXT marks wording adjustable by planner/operator. |

## Open Questions

1. **Return aggregation granularity (sale+product vs sale line).**
   - What we know: index supports sale_id aggregation; entry point is a specific sale op (row) exposing `op.sale_id`, `op.product_id`, frozen prices.
   - What's unclear: whether to also store the origin sale op id in the return payload for per-line traceability.
   - Recommendation: cap by `sale_id`+`product_id`; copy the clicked op's frozen price/cost; optionally store `{"origin_op_id": ...}` in the return payload for auditability (cheap, no schema cost).

2. **/history scope: all op types or stock-affecting only?**
   - What we know: OPS-04 = "full operation history"; D-16 columns emphasize writeoff/correction reasons.
   - Recommendation: include all types with RU labels; type filter lets the operator narrow to writeoff/return/correction. Confirm with planner.

3. **Write-off oversell warn/confirm (D-04, Claude's discretion).**
   - Recommendation: reuse the Phase 4 `sale_oversell` warn-but-allow pattern (`app/templates/partials/sale_oversell.html`, `confirm=1` re-POST) so stock can go to/through zero with an explicit confirm.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime | ✓ | 3.13 (per STATE 01-01) | — |
| uv | run/test | ✓ | project-managed | pip+venv |
| pytest | tests | ✓ | 9.1.* | — |
| ruff | lint gate | ✓ | 0.15.* | — |
| SQLite (stdlib) | DB | ✓ | bundled | — |
| Vendored htmx | UI | ✓ | 2.0.10 (`app/static/htmx.min.js`) | — |

All dependencies already present from Phases 1–4. No new external tools. `[VERIFIED: pyproject.toml, app/static, CLAUDE.md]`

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (+ FastAPI `TestClient` via httpx) |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest -x` |
| Full suite command | `uv run pytest` |
| Lint gate | `uv run ruff check` + `uv run ruff format --check` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPS-01 | Write-off decreases stock; reason persisted in payload | unit (service) | `uv run pytest tests/test_writeoffs.py -x` | ❌ Wave 0 |
| OPS-01 | Invalid/absent reason_code rejected (allow-list) | unit | `uv run pytest tests/test_writeoffs.py -x` | ❌ Wave 0 |
| OPS-01 | Write-off form renders + submits (autofill, 422 on error) | integration (client) | `uv run pytest tests/test_writeoffs.py -x` | ❌ Wave 0 |
| OPS-02 | Return increases stock; qty_delta>0; sale_id + frozen price/cost copied | unit | `uv run pytest tests/test_returns.py -x` | ❌ Wave 0 |
| OPS-02 | Over-return rejected; partial return respects remaining returnable | unit | `uv run pytest tests/test_returns.py -x` | ❌ Wave 0 |
| OPS-02 | Return entry from recent-sales / purchase-history row works | integration | `uv run pytest tests/test_returns.py -x` | ❌ Wave 0 |
| OPS-03 | Counted mode writes `counted-current`; delta mode writes as-is | unit | `uv run pytest tests/test_corrections.py -x` | ❌ Wave 0 |
| OPS-03 | Zero-net correction is a no-op (no row written) | unit | `uv run pytest tests/test_corrections.py -x` | ❌ Wave 0 |
| OPS-03 | Correction never edits products.quantity outside record_operation (ledger==cache) | unit | `uv run pytest tests/test_corrections.py -x` | ❌ Wave 0 |
| OPS-03 | Old `POST /ops` removed / migrated (no duplicate path) | integration | `uv run pytest tests/test_corrections.py -x` | ❌ Wave 0 |
| OPS-04 | /history returns all ops newest-first with product+reason+signed qty | integration | `uv run pytest tests/test_history.py -x` | ❌ Wave 0 |
| OPS-04 | Type filter + product filter narrow results | integration | `uv run pytest tests/test_history.py -x` | ❌ Wave 0 |
| OPS-04 | Pagination returns a bounded page (not the whole ledger) | integration | `uv run pytest tests/test_history.py -x` | ❌ Wave 0 |
| — | Append-only preserved: return/correction are new rows, UPDATE/DELETE still ABORT | unit | `uv run pytest tests/test_ledger.py -x` | ✅ existing |

**Assertion style (from `tests/test_ledger.py`):** mutate via service → `session.expire_all()` → assert `product.quantity` AND `compute_stock(session, pid)` agree; count `operations` rows; for reason/link, assert `op.payload`, `op.sale_id`, `op.unit_price_cents`. Build a real sale for return tests by calling `register_sale` (or `record_operation(type_="sale", ..., sale_id=header.id)`) on a `stocked_product`.

### Sampling Rate
- **Per task commit:** `uv run pytest -x` (fast, stops on first failure) + `uv run ruff check`.
- **Per wave merge:** `uv run pytest` (full suite).
- **Phase gate:** full suite green + ruff clean before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_writeoffs.py` — OPS-01 (stock delta, reason payload, allow-list, form).
- [ ] `tests/test_returns.py` — OPS-02 (stock delta, sale_id link, frozen price/cost, returnable cap, entry point).
- [ ] `tests/test_corrections.py` — OPS-03 (count/delta arithmetic, zero-net no-op, ledger==cache, `/ops` replacement).
- [ ] `tests/test_history.py` — OPS-04 (ordering, type+product filters, pagination bound, RU labels/reason column).
- [ ] No new fixtures required — `session`, `product`, `stocked_product`, `customer`, `client` in `tests/conftest.py` cover it; a returns test builds a sale inline.

## Security Domain

`security_enforcement: true`, ASVS level 1, block_on: high. No auth in v1 (single local operator — PROJECT.md). The relevant surface is input validation on operator-supplied form fields and safe rendering of stored text.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single local operator, no login in v1 (per project constraints). |
| V3 Session Management | no | No sessions/cookies. |
| V4 Access Control | no | No multi-user/roles in v1. |
| V5 Input Validation | **yes** | Typed `Form(...)`/`Query(...)` (422 on malformed) + service-layer allow-lists: `reason_code ∈ WRITEOFF_REASONS`, `mode ∈ {"count","delta"}`, qty via `isascii()+isdigit()`, existence checks on `product_id`/`sale_id`, returnable-qty cap. |
| V6 Cryptography | no | No secrets/crypto in this phase. |
| V7 Error Handling & Logging | yes | Routes catch service exceptions → RU 4xx partial, never a raw 500; `logger.exception(...)` on unexpected failures (existing pattern in `routes/sales.py`). Audit fields (`created_by`,`created_at`,`seq`) stamped by `record_operation` (FND-03). |
| V5 Output encoding | **yes** | Jinja autoescape ON; **never `\|safe`** on product names or payload notes (stored-XSS T-4-01). |

### Known Threat Patterns for FastAPI + HTMX + SQLite
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via product name / write-off note rendered in `/history` | Tampering | Autoescape only; no `\|safe`. `[VERIFIED: existing convention]` |
| Tampered `reason_code` / `mode` bypassing the dropdown | Tampering | Server-side allow-list validation, not just the `<select>`. |
| Over-return inflating stock (business-logic abuse) | Tampering | `returnable_qty` cap enforced in the service before write. |
| SQL injection | Tampering | SQLAlchemy Core/ORM parameterized queries only (portable, no raw SQL). `[VERIFIED: all services use select()]` |
| Ledger falsification (edit/delete a past op) | Repudiation/Tampering | DB triggers ABORT UPDATE/DELETE; corrections/returns are new rows. `[VERIFIED: tests/test_ledger.py]` |
| Unhandled exception leaking a stack trace (500) | Info disclosure | Route-level `try/except → 422 RU partial` + `logger.exception`. `[VERIFIED: routes/sales.py:195-208]` |

## Project Constraints (from CLAUDE.md)
- Money as **integer cents** only — never float/Numeric (`_cents` columns Integer; use `to_cents`/`format_cents`). Write-off/correction carry no price, but any amount uses these helpers.
- **Portable SQLAlchemy ORM only** — no SQLite-specific SQL (`INSERT OR REPLACE`, `strftime`), so the same code runs on PostgreSQL later.
- **Append-only ledger** — all stock changes only through `record_operation`, staged `commit=False`, ONE commit per request (WR-03); operations are immutable (returns/corrections are new rows).
- **UUID PKs, UTC ISO-8601 text timestamps** everywhere (`new_id`, `utcnow_iso`).
- **RU UI text / Latin stored codes** — reason labels RU in a constant, `reason_code` values Latin/portable.
- **Thin routes / fat services**; typed `Form(...)`; HTMX partials; autoescape (no `\|safe`).
- **Alembic migrations frozen** — no imports of mutable app constants; SQLite `render_as_batch=True`; NEVER `batch_alter_table("operations")` (drops triggers). Expect **no** migration this phase.
- Gates: **ruff** (`check` + `format`) and **pytest** must pass. Do not commit unless explicitly asked.
- Do not remove existing logic/tests/comments without a clear reason; smallest safe change.

## Sources

### Primary (HIGH confidence — read this session)
- `app/services/ledger.py` — `record_operation`, `compute_stock`, `rebuild_stock`, `ledger_view`, single-write-path guards.
- `app/models.py` — `OPERATION_TYPES` (has writeoff/return/correction), `Operation` (payload, sale_id, indexes), naming convention.
- `app/services/sales.py` — `register_sale` (cost/price freeze, oversell), `recent_sales`, `lookup_prefill`.
- `app/services/receipts.py` + `app/templates/pages/receipt_form.html`, `partials/receipt_form.html` — write-off form analog (204 autofill, focus hook, staged commit).
- `app/services/customers.py` + `app/templates/partials/purchase_history.html` — per-customer return entry point.
- `app/routes/ops.py` + `app/templates/pages/home.html` — the correction path to replace (D-12).
- `app/routes/{sales,receipts,dictionary,customers,home}.py`, `app/routes/__init__.py` — route/template/filter conventions, 422-swap, error handling.
- `app/templates/base.html` — nav + htmx-config (204/422 handling).
- `app/templates/partials/ledger_rows.html`, `recent_sales.html` — history table base + oob refresh pattern.
- `alembic/versions/0004_sales_customers.py` — `ix_operations_sale_id`, native-add-column + trigger-preservation rule.
- `tests/conftest.py`, `tests/test_ledger.py` — fixtures + assertion style (ledger==cache, append-only).
- `.planning/config.json`, `pyproject.toml` — nyquist_validation on, security L1, pytest/ruff config.
- CONTEXT/REQUIREMENTS/ROADMAP/STATE — decisions D-01..D-17, OPS-01..04, phase boundary.

### Secondary / Tertiary
- None. External research intentionally skipped per CONTEXT (no external libraries introduced).

## Metadata

**Confidence breakdown:**
- Standard stack (reused modules): HIGH — every symbol read directly in source this session.
- Architecture / patterns: HIGH — all patterns are copies of shipped Phase 3/4 code; only returnable-qty aggregation and count/delta arithmetic are new logic (still HIGH, verified against schema + index).
- Pitfalls: HIGH — each pitfall is anchored to a specific verified line or shipped test.
- Assumptions: LOW-risk planner decisions only (aggregation granularity, pagination style, /history scope) — logged above.

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (30 days — stable internal codebase; re-verify only if Phase 5 execution changes the ledger service or Operation schema)
