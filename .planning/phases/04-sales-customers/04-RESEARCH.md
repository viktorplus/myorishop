# Phase 4: Sales & Customers - Research

**Researched:** 2026-07-09
**Domain:** Local server-rendered CRUD on an append-only ledger (FastAPI + SQLAlchemy 2.0 + SQLite + HTMX)
**Confidence:** HIGH (grounded in the existing codebase; external research intentionally skipped per objective)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Sale is a **basket (multi-line)**: one sale = several product lines to (at most) one optional customer.
- **D-02:** Fast entry lives *inside* the basket: add a line (code → name/prices auto-fill, quantity, sale price), add another, then one "Оформить продажу" writes all lines + attaches the customer in ONE transaction. Reuse the receipt form's autofill/focus ergonomics per line.
- **D-03:** Sale header + lines: a sale/order **header** record (id UUID, optional customer_id, created_at/created_by) groups the lines; each product line is a `sale` **operation** (qty_delta < 0) linked back to the header. Exact link mechanism is a schema decision for research/planning. Constraint: stock is still computed ONLY from ledger `sale` operations; the header must be reconstructable/portable for future sync. Empty basket cannot be finalized.
- **D-04:** Customer is **optional** — a walk-in sale with no customer is valid.
- **D-05:** In the sale form: search existing customers (HTMX autocomplete, reuse 204/debounce) **and** quick-create a new customer inline without leaving the sale.
- **D-06:** Separate `/customers` page for full CRUD + the customer detail view.
- **D-07:** New `customers` table: id (UUID), name, surname, consultant_number, created_at/updated_at, plus a lowercase shadow for Cyrillic-safe search consistent with Phase 2's `name_lc`.
- **D-08:** On finalize, if any line oversells, show an inline warning (product, available vs requested) with an explicit **«Продать всё равно»** confirm. No silent block.
- **D-09:** After confirmation the sale proceeds and stock **may go negative** (allow-negative locked).
- **D-10:** Sale price per line **pre-fills from the product card** `sale_cents`, editable per line; the snapshot stored on the op is the actual entered price (`unit_price_cents`).
- **D-11:** Unit **cost is frozen** from the product card `cost_cents` at sale time into `unit_cost_cents`.
- **D-12:** If card `cost_cents` is NULL, store snapshot as **NULL**, show profit «неизвестна», do NOT block the sale. Sale price NULL must be rejected.

### Claude's Discretion
- Exact templates/partials structure, basket UI layout, empty-state and confirmation texts (RU).
- Migration numbering (0004+) and index choices; whether sale lines are a table or payload-linked operations.
- Where/how the oversell check runs — must warn+confirm before any negative write.
- Customer purchase-history view layout (must show product, date, quantity, unit price per CST-02).
- Whether the recent-sales list is a partial under the form or its own view.

### Deferred Ideas (OUT OF SCOPE)
- Purchase-frequency analysis + "customer running low" reminders (CST-V2-01).
- On goods receipt, surface likely-interested customers (CST-V2-02).
- Sale-linked returns, write-offs, stock corrections, full history browsing (Phase 5).
- Sales/profit/customer reports and CSV export (Phase 6).
- Multi-currency, multi-operator sync, user roles (out of scope per PROJECT.md).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SAL-01 | Register a sale by product code with quantity; stock decreases, sale saved to history | `sale` op via `record_operation(qty_delta=-qty)`; basket write path (see Pattern 2) |
| SAL-02 | Sale price can differ per line from the standard price | `unit_price_cents` = entered price, pre-filled from `Product.sale_cents` (Finding 5) |
| SAL-03 | Optional link to a customer (name, surname, consultant number) | `sales.customer_id` nullable FK; inline picker/quick-create (Finding 2, Pattern 4) |
| SAL-04 | Warned when selling more than in stock | Two-step validate → warn → confirm-to-proceed HTMX flow (Finding 3, Pattern 3) |
| SAL-05 | Each sale line snapshots unit cost and sale price at sale time | `unit_cost_cents` frozen from `Product.cost_cents`, `unit_price_cents` from entry (Finding 5) |
| CST-01 | Create/edit customer profiles | `customers` table + `/customers` CRUD (Finding 2, Pattern 4) |
| CST-02 | View a customer's purchase history (what, when, at what price) | JOIN `operations`(type=sale) → `sales`(sale_id) WHERE customer_id (Finding 1, Code Example 4) |
</phase_requirements>

## Summary

Phase 4 is a well-understood local CRUD slice built entirely on patterns already proven in Phases 1–3. A **sale** is a multi-line basket: a new **`sales` header row** (UUID, optional `customer_id`) groups N `sale` **operations** (`qty_delta < 0`) written through the existing single write path `record_operation`, all in ONE transaction. Stock stays a pure projection of the ledger — nothing new there. Two genuinely new things need schema: (1) the **header↔line link** and (2) the **`customers` table**. Everything else (per-line autofill, Cyrillic-safe autocomplete, 204 lookup, money-as-cents, RU errors, HTMX partial swaps, oob refresh, one-commit-per-request) is a direct copy of the receipt/catalog/dictionary code.

The three design questions with real weight are answered below with a single recommendation each: **link mechanism = a nullable `sale_id` FK column on `operations` + a `sales` header table** (not JSON payload, not a duplicate `sale_lines` table); **oversell = a server-side check at finalize that returns a warning partial with zero writes, re-submitted with `confirm=1`** via HTMX `hx-vals`; **snapshot = freeze `Product.cost_cents` into `unit_cost_cents` at write, take the entered price into `unit_price_cents`, reject empty price, allow NULL cost**.

The one non-obvious constraint that shapes the schema: **the `operations` table is protected by append-only DB triggers, and any Alembic *batch* migration on it silently DROPs those triggers** (0001 warns of this explicitly). Therefore the `sale_id` column MUST be added with a **native `ADD COLUMN`** (nullable, default NULL) — never batch. SQLite permits a `REFERENCES` clause on a native ADD COLUMN when the default is NULL, so the FK can be kept without a table rebuild.

**Primary recommendation:** Add a `customers` table and a `sales` header table (migration 0004), add a nullable `sale_id` FK column to `operations` via native ALTER, extend `record_operation` with an optional `sale_id` kwarg, and build `app/services/sales.py` + `app/services/customers.py` as fat services that mirror `receipts.py`/`catalog.py`. Do not bypass `record_operation`; do not duplicate line data.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Stock decrement on sale | Database / Ledger (`record_operation`) | — | Single write path; stock is a projection of `SUM(qty_delta)` (FND-01) |
| Sale header grouping | Database (`sales` table) | Service (`sales.py`) | Portable grouping row; reconstructable for sync |
| Cost/price snapshot | Service (`sales.py`) writes onto the op | Database (immutable columns) | Frozen at write; append-only triggers guarantee it never changes |
| Oversell warn/confirm | API / Backend (`routes/sales.py` + service) | Browser (HTMX resubmit) | Check must run server-side BEFORE any negative write; UI only re-submits |
| Basket multi-line entry | Browser (HTMX partials) | API (row/lookup endpoints) | Server-rendered rows; no client framework |
| Customer autocomplete | Service (`customers.py` search) | Browser (debounced HTMX) | Cyrillic folding must happen in Python (Phase 2 rule) |
| Customer CRUD + history | API + Service | Database (`customers`/`sales`/`operations` join) | Plain CRUD; history is a read query |

## Standard Stack

No new libraries. Everything required is already installed and proven in Phases 1–3.

### Core (already present — reuse)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.139.0 | Routing, `Form(...)`, thin routes | Established pattern (`routes/receipts.py`) `[VERIFIED: codebase]` |
| SQLAlchemy | 2.0.51 | ORM models, `select()`, UoW ordering | `Mapped[]`/`mapped_column()` 2.0 style already used `[VERIFIED: codebase]` |
| SQLite | bundled | Local store; WAL + `foreign_keys=ON` | `app/db.py` connect listener `[VERIFIED: codebase]` |
| Alembic | 1.18.5 | Migration 0004 | Frozen-style migrations 0001–0003 `[VERIFIED: codebase]` |
| Jinja2 | 3.1.6 | Templates + `cents`/`local_dt` filters | `app/routes/__init__.py` filters `[VERIFIED: codebase]` |
| htmx | 2.0.10 (vendored) | Debounced lookup, partial + oob swaps, `hx-vals` | `base.html` htmx-config already opts 422 into swapping `[VERIFIED: codebase]` |
| python-multipart | 0.0.32 | Form parsing incl. repeated fields (`list[str] = Form([])`) | Required for the multi-line basket `[VERIFIED: codebase]` |
| pytest / httpx | 9.1.1 / 0.28.1 | Service + TestClient tests | `tests/conftest.py` fixtures `[VERIFIED: codebase]` |

### Supporting
None new. `pydantic-settings` (`settings.device_id`, `settings.operator_name`) is already consumed inside `record_operation`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `sale_id` FK column on `operations` | header id inside JSON `payload` | JSON is not portably indexable; CST-02 + Phase 6 reports would filter JSON — slow and non-portable to PostgreSQL. Rejected. |
| `sale_id` FK column | separate `sale_lines` table duplicating qty/price | Creates a second source of truth for line data + a second write path; stock must still come from `operations` — the `sale_lines` rows would be redundant and drift-prone. Rejected. |
| Repeated form fields (`list[str]`) | indexed field names `line-0-code`, `line-1-code` | Parallel `list[str] = Form([])` maps directly to arrays and matches FastAPI idiom; indexed names need manual reassembly. Prefer arrays. |

**Installation:** none — `uv sync` already satisfies all dependencies.

## Package Legitimacy Audit

Phase 4 installs **no external packages**. All dependencies are already locked in `pyproject.toml`/`uv.lock` and verified in Phases 1–3. No legitimacy gate required.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Runtime State Inventory

Not applicable — Phase 4 is a greenfield feature slice (new tables, new services, one additive column), not a rename/refactor/migration. No existing stored strings, service configs, OS registrations, or build artifacts are being renamed. **None — verified by reading the phase scope and CONTEXT.md.**

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────────────────────┐
  Browser (HTMX)         │  GET /sales/new  → pages/sale_form.html      │
   sale basket           │  "add line"      → GET /sales/row  (partial) │
   ├─ code input ────────┼─ GET /sales/lookup?code=  → 204 | name+price │
   ├─ qty / price        │                                              │
   ├─ customer search ───┼─ GET /sales/customer-search?q= → picker rows │
   │   or quick-create ──┼─ POST /sales/customer → selected-chip partial│
   └─ "Оформить продажу" │                                              │
        POST /sales ─────┼──────────────┐                               │
                         └──────────────┼───────────────────────────────┘
                                        ▼
                        app/services/sales.register_sale()
                          1. parse lines (code, qty, price)  ── validate ──▶ 422 RU errors (0 writes)
                          2. resolve active products by code
                          3. OVERSELL CHECK (sum requested/product vs Product.quantity)
                                 │ oversell && confirm != 1
                                 └────────────▶ partials/sale_oversell.html (0 writes)
                                                 «Продать всё равно» → re-POST hx-vals confirm=1
                          4. INSERT sales header (staged, commit=False)
                          5. for each line:
                               record_operation(type_="sale", qty_delta=-qty,
                                 unit_cost_cents=Product.cost_cents,   ← frozen (D-11)
                                 unit_price_cents=entered_price,       ← D-10
                                 sale_id=header.id, commit=False)
                          6. ONE session.commit()  ─────────────────────▶ ledger + header + stock
                                        │
                                        ▼
                          success partial (fresh basket + recent sales oob)

  /customers  (separate CRUD, Finding 2 / Pattern 4)
    GET /customers                 → list + search rows
    GET /customers/new, POST       → create_customer
    GET /customers/{id}            → detail + purchase_history  (CST-02)
    GET /customers/{id}/edit, POST → update_customer
```

### Recommended Project Structure
```
app/
├── models.py                    # + Customer, Sale models; + Operation.sale_id column
├── services/
│   ├── sales.py                 # register_sale, lookup_sale_prefill, recent_sales
│   ├── customers.py             # create/update/get/list, search_customers, purchase_history
│   └── ledger.py                # EXTEND record_operation(..., sale_id=None)
├── routes/
│   ├── sales.py                 # /sales/new, /sales/lookup, /sales/row, POST /sales, customer picker
│   └── customers.py             # /customers CRUD + detail
├── templates/
│   ├── pages/  sale_form.html, customers_list.html, customer_form.html, customer_detail.html
│   └── partials/  sale_row.html, sale_lookup.html, sale_oversell.html,
│                  customer_picker.html, recent_sales.html, customer_rows.html,
│                  purchase_history.html
alembic/versions/
└── 0004_sales_customers.py      # customers + sales tables, operations.sale_id, indexes
tests/
├── test_sales.py                # SAL-01..05 service + web slice
└── test_customers.py            # CST-01/02 service + web slice
```

### Pattern 1: Header↔line link = nullable `sale_id` FK on `operations`
**What:** A first-class `sales` header row (UUID, optional `customer_id`); each line is a `sale` op whose new nullable `sale_id` column points at the header. Non-sale ops leave `sale_id` NULL.
**When to use:** This phase — it is the only option that keeps stock as a pure ledger projection, gives an indexed portable query for CST-02 and Phase 6, and leaves the append-only ledger intact.
**Why the op cannot be linked after insert:** The `operations_no_update` trigger raises `ABORT` on any UPDATE, so `sale_id` MUST be set at INSERT time — i.e. inside `record_operation`. Hence the kwarg extension.
**Example:**
```python
# app/models.py  — additive column on the existing Operation
sale_id: Mapped[str | None] = mapped_column(
    ForeignKey("sales.id", name="fk_operations_sale_id_sales"), index=True
)
# Declaring the ORM ForeignKey also makes the Unit-of-Work insert the Sale
# header BEFORE the sale ops in one flush (FK ordering), so foreign_keys=ON
# is satisfied without a manual intermediate commit.
```

### Pattern 2: Multi-line basket, ONE transaction (reuse `record_operation`)
**What:** Stage the header, then one `record_operation(..., commit=False)` per line, then a single `session.commit()`.
**Example:**
```python
# app/services/sales.py  (shape; RU errors + oversell omitted here)
def register_sale(session, *, customer_id, lines, confirm):
    header = Sale(id=new_id(), customer_id=customer_id or None,
                  created_at=utcnow_iso(), created_by=settings.operator_name)
    session.add(header)                       # staged; flushed before ops (FK order)
    for ln in lines:
        record_operation(
            session, type_="sale", product_id=ln.product_id,
            qty_delta=-ln.qty,
            unit_cost_cents=ln.product.cost_cents,   # D-11 freeze (may be None)
            unit_price_cents=ln.price_cents,         # D-10 entered price
            sale_id=header.id, commit=False,
        )
    session.commit()                          # WR-03: one commit closes the txn
```

### Pattern 3: Oversell = validate → warn → confirm-to-proceed (HTMX)
**What:** Server checks aggregated requested qty per product against `Product.quantity`; if any line oversells and `confirm != "1"`, return `partials/sale_oversell.html` with **zero writes**. The «Продать всё равно» button re-POSTs the same basket with `confirm=1`.
**Re-submit mechanism (idiomatic HTMX):** one button, no re-serialization of the basket —
```html
<button type="submit" form="sale-form"
        hx-post="/sales" hx-vals='{"confirm": "1"}'
        hx-target="#sale-form-wrap" hx-swap="outerHTML">Продать всё равно</button>
```
`hx-vals` merges `confirm=1` into the existing form fields, so the whole basket rides along unchanged. Allow-negative (D-09): on `confirm=1` the service skips the block and writes; stock may go negative.
**Aggregate across duplicate lines:** sum requested qty per `product_id` across all basket lines before comparing to `Product.quantity` (a product on two lines must not each pass individually).

### Pattern 4: Customer inline picker + Cyrillic-safe autocomplete
**What:** Reuse the Phase 2 search: lower the query in **Python**, compare to a `search_lc` shadow column (SQLite `lower()`/`LIKE` fold ASCII only). Debounced `hx-get` returns a rows partial. Quick-create posts name/surname/consultant to `POST /sales/customer`, which returns a "selected customer" chip carrying a hidden `customer_id` into the sale form.

### Anti-Patterns to Avoid
- **Batch-migrating `operations`:** an Alembic `batch_alter_table("operations")` rebuilds the table and **DROPs the append-only triggers** (0001 warns of exactly this). Use native `op.add_column` only.
- **Recomputing profit from current card prices:** always read the frozen `unit_cost_cents`/`unit_price_cents` — never `Product.sale_cents`/`cost_cents` at report time (the whole point of SAL-05).
- **A second write path for stock:** never insert `operations` rows or touch `Product.quantity` outside `record_operation`.
- **`|safe` on stored names:** customer/product names are untrusted input (T-3-02 precedent) — autoescape only.
- **SQLite-specific SQL** (`INSERT OR REPLACE`, `strftime`) — ORM constructs only, for the PostgreSQL path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stock decrement + audit row | Custom UPDATE of `Product.quantity` | `record_operation(..., sale_id=..., commit=False)` | Single write path, atomic increment, seq/audit stamping, soft-delete guard all handled |
| Money parsing (RU comma) | `float(price)` / manual split | `to_cents()` / `parse_optional_cents()` | Decimal ROUND_HALF_UP, rejects inf/nan; floats corrupt profit |
| Money display | f-string formatting | `cents` Jinja filter | Single render point (`format_cents`) |
| UTC timestamp / UUID | `datetime.now()` / manual uuid | `utcnow_iso()` / `new_id()` | Sync-safe conventions; tz-aware; sortable text |
| Cyrillic search | SQL `lower()` / `LIKE` | Python `str.lower()` + `search_lc` shadow + `.contains(..., autoescape=True)` | SQLite folds ASCII only (Phase 2 Finding) |
| Local time display | manual tz math | `local_dt` filter | `iso_to_local` + `settings.display_tz` |
| Duplicate-race safety | app-only checks | DB constraint + `IntegrityError` → RU error | Phase 2/3 precedent (though customers likely need NO unique constraint — see Finding 2) |

**Key insight:** Almost every "new" need in this phase already has a sanctioned helper. The only genuinely new code is the `sales` header, the `sale_id` link, the `customers` table, and the two-step oversell UX.

## Common Pitfalls

### Pitfall 1: Batch migration silently drops append-only triggers
**What goes wrong:** Adding `sale_id` to `operations` via `batch_alter_table` rebuilds the table (move-and-copy) and destroys `operations_no_update`/`operations_no_delete`; the ledger becomes mutable and no test catches it until immutability is asserted.
**Why:** SQLite has limited `ALTER`; Alembic batch mode recreates the table.
**How to avoid:** Use native `op.add_column("operations", sa.Column("sale_id", sa.String(36), sa.ForeignKey("sales.id", ...), nullable=True))`. SQLite permits a `REFERENCES` clause on a native ADD COLUMN **only when the column default is NULL** (satisfied). Create the `sales` table *before* adding the column. `[VERIFIED: codebase 0001 warning]` `[CITED: sqlite.org/lang_altertable.html — ADD COLUMN with REFERENCES requires NULL default]`
**Warning signs:** migration diff shows `CREATE TABLE _alembic_tmp_operations`; an immutability test starts passing writes.

### Pitfall 2: FK insert ordering with `foreign_keys=ON`
**What goes wrong:** Inserting a `sale` op before its `sales` header raises a FK violation (PRAGMA foreign_keys=ON is set in `app/db.py`).
**How to avoid:** Declare the ORM `ForeignKey` on `Operation.sale_id`; SQLAlchemy's Unit-of-Work then orders the `Sale` INSERT before the `Operation` INSERTs within the single flush. Staging `session.add(header)` first also helps: `record_operation` calls `session.get(Product)` and `next_seq`, both of which autoflush pending rows.
**Warning signs:** `IntegrityError: FOREIGN KEY constraint failed` on commit of a basket.

### Pitfall 3: `record_operation` extension must stay backward-compatible
**What goes wrong:** Changing the signature breaks catalog/receipts callers.
**How to avoid:** Add `sale_id: str | None = None` as a keyword-only param with a default; pass it straight into `Operation(...)`. All existing calls (`product_created`, `price_change`, `receipt`, etc.) keep working untouched. `[VERIFIED: codebase — 5 existing callers]`

### Pitfall 4: Focus/autofocus does not fire in swapped content
**What goes wrong:** After finalize, focus does not return to the first field.
**How to avoid:** Reuse the receipt precedent — an explicit `hx-on::load="document.getElementById('code').focus()"` on the swapped wrapper (autofocus covers initial page load only). `[VERIFIED: codebase receipt_form.html]`

### Pitfall 5: Empty sale price must be rejected; empty cost must be allowed
**What goes wrong:** Treating both prices the same either blocks fast entry (rejecting NULL cost) or writes a priceless sale.
**How to avoid:** `unit_price_cents` is required per line → RU error «Укажите цену продажи» on empty/invalid; `unit_cost_cents` is frozen from the card and may be NULL (profit «неизвестна», no block) per D-12. `[VERIFIED: CONTEXT D-12]`

### Pitfall 6: Oversell aggregation across duplicate basket lines
**What goes wrong:** Same product on two lines each passes the stock check individually but oversells in total.
**How to avoid:** Sum requested qty per `product_id` across the whole basket before comparing to `Product.quantity`.

### Pitfall 7: In-memory vs file SQLite in tests
**What goes wrong:** In-memory DBs break with pooled sessions.
**How to avoid:** Reuse the `tmp_path` file-based `engine` fixture; it already installs the append-only triggers via `APPEND_ONLY_TRIGGERS`. New models are created by `Base.metadata.create_all` — so `Customer`, `Sale`, and `Operation.sale_id` must live in `models.py` for tests to see them. `[VERIFIED: conftest.py]`

## Code Examples

### 1. Extend the single write path (minimal, backward-compatible)
```python
# app/services/ledger.py  — add ONE keyword param
def record_operation(session, *, type_, product_id, qty_delta,
                     unit_cost_cents=None, unit_price_cents=None,
                     payload=None, sale_id=None, commit=True):
    ...
    op = Operation(
        id=new_id(), type=type_, product_id=product_id, qty_delta=qty_delta,
        unit_cost_cents=unit_cost_cents, unit_price_cents=unit_price_cents,
        payload=payload, sale_id=sale_id,          # NEW
        device_id=settings.device_id, seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(), created_by=settings.operator_name,
    )
    ...
```

### 2. New models (mirror existing conventions)
```python
# app/models.py
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    surname: Mapped[str | None] = mapped_column(String(200))
    consultant_number: Mapped[str | None] = mapped_column(String(50))
    # Cyrillic-safe shadow of "name surname", maintained by the SERVICE layer.
    search_lc: Mapped[str | None] = mapped_column(String(400), index=True)
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)

class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str | None] = mapped_column(
        ForeignKey("customers.id", name="fk_sales_customer_id_customers"), index=True
    )
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    # device_id optional for sync provenance (planner discretion)
```

### 3. Migration 0004 skeleton (frozen style — no app imports)
```python
# alembic/versions/0004_sales_customers.py
revision = "0004"; down_revision = "0003"
def upgrade() -> None:
    op.create_table("customers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("surname", sa.String(200), nullable=True),
        sa.Column("consultant_number", sa.String(50), nullable=True),
        sa.Column("search_lc", sa.String(400), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customers")))
    op.create_index(op.f("ix_customers_search_lc"), "customers", ["search_lc"])
    op.create_table("sales",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("customer_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"],
            name=op.f("fk_sales_customer_id_customers")))
    op.create_index(op.f("ix_sales_customer_id"), "sales", ["customer_id"])
    # NATIVE add-column (NO batch — preserves append-only triggers). Default NULL
    # allows the inline REFERENCES on SQLite.
    op.add_column("operations",
        sa.Column("sale_id", sa.String(36),
            sa.ForeignKey("sales.id", name=op.f("fk_operations_sale_id_sales")),
            nullable=True))
    op.create_index(op.f("ix_operations_sale_id"), "operations", ["sale_id"])
```
> **Verification note `[ASSUMED]`:** If Alembic emits a table rebuild (batch) for the inline FK on SQLite instead of a native `ADD COLUMN`, fall back to adding a **bare** `sale_id` column (no DB-level FK; keep the ORM `ForeignKey` in the model for UoW ordering + PostgreSQL portability). The trigger-preservation constraint outranks the physical FK. Confirm by inspecting the emitted DDL / running `test_pragmas`-style immutability assertions after `alembic upgrade head`.

### 4. CST-02 purchase history (ORM only, portable)
```python
# app/services/customers.py
def purchase_history(session, customer_id: str) -> list[dict]:
    rows = session.execute(
        select(Operation, Product)
        .join(Sale, Operation.sale_id == Sale.id)
        .join(Product, Operation.product_id == Product.id)
        .where(Sale.customer_id == customer_id, Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
    ).all()
    return [{"op": op, "product": p} for op, p in rows]   # qty = -op.qty_delta
```

### 5. Cyrillic-safe customer search (mirror `search_products`)
```python
def search_customers(session, q: str) -> list[Customer]:
    q_lc = q.strip().lower()                       # Python folds Cyrillic
    stmt = select(Customer)
    if q_lc:
        stmt = stmt.where(Customer.search_lc.contains(q_lc, autoescape=True))
    return list(session.scalars(stmt.order_by(Customer.search_lc).limit(20)))
# On create/update: customer.search_lc = f"{name} {surname or ''}".strip().lower()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| — | Project already on the current stack (FastAPI 0.139, SQLAlchemy 2.0, htmx 2.0.10) | Phases 1–3 | No migration needed; copy existing patterns |

**Deprecated/outdated:** none relevant. Do not follow SQLAlchemy 1.x tutorials or add async/aiosqlite (CLAUDE.md forbids both).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Alembic emits a **native** `ADD COLUMN` (not batch) for `operations.sale_id` with an inline FK on SQLite | Code Example 3 / Pitfall 1 | If it rebuilds the table, append-only triggers drop — mitigated by the documented bare-column fallback |
| A2 | Customers need **no** unique constraint (walk-in quick-create tolerates duplicate names/consultant numbers) | Finding 2 | If a uniqueness rule is later required, add a partial unique index migration |
| A3 | `consultant_number` is stored as **String** (may have leading zeros / non-numeric) not Integer | Finding 2 | If numeric-only is required, validation tightens — low risk |
| A4 | Oversell check reads the cached `Product.quantity` (a maintained projection) rather than recomputing via `compute_stock` per line | Pattern 3 | Cache is authoritative (maintained by `record_operation`); if ever stale, `rebuild_stock` repairs it |

**Note:** A1 is the only assumption with real blast radius; it is gated by an explicit verification step in the plan (run `alembic upgrade head` and assert the ledger is still immutable before proceeding).

## Open Questions

1. **Does the `sales` header need `device_id`/`seq` for sync?**
   - What we know: `operations` already carry `device_id`+`seq` (UNIQUE); the header is grouping metadata with its own UUID + UTC + `created_by`.
   - What's unclear: whether v2 sync wants provenance on the header itself.
   - Recommendation: add a nullable `device_id` on `sales` for symmetry (cheap, sync-friendly); leave `seq` off (headers are not stock events). Planner discretion.

2. **Should the recent-sales list live under the form or as its own page?**
   - Recommendation: mirror `recent_receipts` — an oob-refreshed partial under the form (`partials/recent_sales.html`), lowest-friction and consistent. D-explicitly leaves this to discretion.

## Environment Availability

Skip — Phase 4 adds no external tools, services, or runtimes. All dependencies (`uv`, Python 3.13, the locked libraries, SQLite) are already present and exercised by Phases 1–3.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (+ httpx TestClient) `[VERIFIED: codebase]` |
| Config file | `pyproject.toml` (`pytest pythonpath=['.']`) |
| Quick run command | `uv run pytest tests/test_sales.py tests/test_customers.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SAL-01 | Basket writes N `sale` ops, `qty_delta<0`, stock decreases, `compute_stock` agrees | unit | `pytest tests/test_sales.py -k stock -x` | ❌ Wave 0 |
| SAL-01 | Empty basket cannot be finalized (RU error, 0 writes) | unit | `pytest tests/test_sales.py -k empty_basket -x` | ❌ Wave 0 |
| SAL-02 | Entered price overrides card `sale_cents`; snapshot = entered `unit_price_cents` | unit | `pytest tests/test_sales.py -k price_override -x` | ❌ Wave 0 |
| SAL-03 | Sale links to `customer_id`; walk-in (NULL customer) also valid | unit | `pytest tests/test_sales.py -k customer_link -x` | ❌ Wave 0 |
| SAL-04 | Oversell → warning partial, **0 writes**; `confirm=1` re-submit writes & allows negative | web | `pytest tests/test_sales.py -k oversell -x` | ❌ Wave 0 |
| SAL-05 | `unit_cost_cents` frozen from card at write; later card price change does NOT alter the op | unit | `pytest tests/test_sales.py -k snapshot -x` | ❌ Wave 0 |
| SAL-05/D-12 | NULL card cost → op cost NULL, sale NOT blocked; empty price → RU error, 0 writes | unit | `pytest tests/test_sales.py -k null_cost -x` | ❌ Wave 0 |
| SAL-01 | Whole basket in ONE transaction (crash-mid = 0 committed ops) | unit | `pytest tests/test_sales.py -k one_transaction -x` | ❌ Wave 0 |
| CST-01 | Create/edit customer; `search_lc` maintained; RU validation | unit | `pytest tests/test_customers.py -k crud -x` | ❌ Wave 0 |
| CST-01 | Cyrillic autocomplete via `search_lc`, capped 20 | unit | `pytest tests/test_customers.py -k search -x` | ❌ Wave 0 |
| CST-02 | Purchase history shows product, date, qty, unit price for the customer | unit | `pytest tests/test_customers.py -k history -x` | ❌ Wave 0 |
| CST-02 | History reads frozen `unit_price_cents`, not current card price | unit | `pytest tests/test_customers.py -k history_frozen -x` | ❌ Wave 0 |
| — | Ledger still immutable after 0004 (`sale_id` add did not drop triggers) | unit | `pytest tests/test_ledger.py -k append_only -x` | ⚠️ extend existing |

### Observable signals (what proves each behavior)
- **Stock decremented:** `Product.quantity` and `compute_stock()` both drop by the summed line qty; sale ops have `qty_delta<0`.
- **Oversell warn-then-confirm:** POST /sales with an oversell + no confirm → 200/422 partial containing the RU warning and «Продать всё равно», and `select(Operation).where(type=='sale')` is empty; a second POST with `confirm=1` writes and `Product.quantity` goes negative.
- **Snapshot frozen:** record a sale, then mutate `Product.cost_cents`/`sale_cents`, then re-read the op — `unit_cost_cents`/`unit_price_cents` unchanged.
- **Customer link optional:** a sale with `customer=""` commits with `sales.customer_id IS NULL`.
- **Purchase history:** join returns the exact product/date/qty/price rows for that customer only.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_sales.py tests/test_customers.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** full suite green + `ruff check` + `ruff format --check` before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_sales.py` — SAL-01..05 service + web slice
- [ ] `tests/test_customers.py` — CST-01/02 service + web slice
- [ ] `tests/conftest.py` — add a `customer` fixture and a `stocked_product` fixture (existing `product` has `quantity=0`; oversell/decrement tests need stock — seed via `record_operation(type_="receipt", qty_delta=N)` or a dedicated fixture)
- [ ] Extend `tests/test_ledger.py` — assert `record_operation(..., sale_id=...)` sets the column and that `operations` remains append-only after migration 0004

*(Framework already installed — no install gap.)*

## Security Domain

`security_enforcement: true`, ASVS level 1. This is a single-operator, localhost, no-auth v1 app; most auth/session/access-control categories are out of scope by design (PROJECT.md).

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single local operator, no login in v1 (deferred AUTH-V2-01) |
| V3 Session Management | no | No sessions/cookies |
| V4 Access Control | no | No multi-user roles in v1 |
| V5 Input Validation | **yes** | `to_cents`/`parse_optional_cents` for money; `str.isdigit()`+`int>0` for qty; `.strip()` on all text; required-price rejection (D-12) |
| V6 Cryptography | no | No secrets/PII crypto; local file store |
| V7 Error Handling | **yes** | Service returns `(None, RU errors)`; route wraps unexpected exceptions in the UI-SPEC error block (never a raw 500) — receipt precedent |
| V12 Files/Resources | no | No file upload in this phase |
| V14 Config | minor | `foreign_keys=ON`, WAL already enforced in `app/db.py` |

### Known Threat Patterns for FastAPI + Jinja2 + SQLite
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via customer/product name in history & pickers | Tampering/Info | Jinja **autoescape on**, no `|safe` (T-3-02 precedent) |
| SQL injection in autocomplete `q` | Tampering | SQLAlchemy ORM parametrization; `_escape_like`/`autoescape=True` for LIKE wildcards |
| Ledger tampering (edit a sale after the fact) | Repudiation/Tampering | Append-only DB triggers — verify they survive migration 0004 (Pitfall 1) |
| Money precision / negative-price abuse | Tampering | Integer cents + `to_cents` ROUND_HALF_UP; reject empty/garbage price server-side |
| Mass-assignment via extra form fields | Tampering | Explicit `Form(...)` params only; service reads named fields, ignores extras |

## Sources

### Primary (HIGH confidence)
- `app/services/ledger.py`, `app/services/receipts.py`, `app/services/catalog.py`, `app/services/dictionary.py`, `app/core.py`, `app/db.py`, `app/config.py`, `app/models.py` — the write-path, snapshot, money, Cyrillic-search, and convention patterns copied throughout this research.
- `app/routes/receipts.py`, `app/routes/products.py`, `app/templates/partials/receipt_*.html`, `app/templates/partials/name_input.html`, `app/templates/base.html` — HTMX lookup/oob/422-swap patterns, nav wiring.
- `alembic/versions/0001..0003` — frozen migration style, append-only trigger DDL + the explicit batch-drops-triggers warning.
- `tests/conftest.py`, `tests/test_receipts.py` — fixture + service/web test conventions.
- `.planning/phases/04-sales-customers/04-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `./CLAUDE.md`.

### Secondary (MEDIUM confidence)
- `[CITED: sqlite.org/lang_altertable.html]` — native `ADD COLUMN` permits a `REFERENCES` clause when the column default is NULL (basis for keeping the FK without a table rebuild). Confirm empirically per A1.

### Tertiary (LOW confidence)
- None. External web providers were disabled by config and are not required for this phase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all patterns verified in-repo.
- Architecture (link mechanism, basket txn, oversell, snapshot): HIGH — derived from existing single-write-path + receipt analog.
- Migration mechanics (native ADD COLUMN + inline FK): MEDIUM — SQLite semantics cited; Alembic emission gated by verification step A1.
- Pitfalls: HIGH — grounded in explicit in-repo warnings (append-only triggers, Cyrillic folding, focus-after-swap).

**Research date:** 2026-07-09
**Valid until:** 2026-08-08 (stable stack; re-verify only if the ledger write path or migration chain changes)
