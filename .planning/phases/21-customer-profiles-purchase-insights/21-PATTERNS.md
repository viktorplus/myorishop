# Phase 21: Customer Profiles & Purchase Insights - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 9 (2 new, 7 modified)
**Analogs found:** 8 / 9 (1 partial — see "No Analog Found")

All analogs below were **read in-session and verified** against the live codebase. Every
line-number citation inherited from `21-RESEARCH.md` / `21-UI-SPEC.md` was re-checked;
discrepancies are called out inline. See "Citation Verification Log" at the bottom.

## File Classification

| New/Modified File | New? | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|------|-----------|----------------|---------------|
| `app/models.py` (+`CustomerContact`, +`Customer.address`) | mod | model | CRUD | `Sale` / `CashMovement` (`models.py:354-370`, `373-384`); `Warehouse.address` (`models.py:190`) | exact (FK+PK shape) / **none** (CheckConstraint) |
| `alembic/versions/0015_customer_contacts.py` | **NEW** | migration | batch DDL | `0013_cash_movements.py` (create_table) + `0005_product_thresholds.py` (add_column) | exact ×2 |
| `app/services/customers.py` (+`favorite_products`, `spend_totals`, `_spend_window`, `_period_starts`, contact CRUD) | mod | service | CRUD + SQL aggregate | `purchase_history` (`customers.py:202-214`); `top_selling_products` (`reports.py:144-167`) | exact |
| `app/routes/customers.py` (+`/customers/contact-row`, extended create/update/detail) | mod | route | request-response | `sale_row` (`sales.py:312-333`); `sale_create` (`sales.py:389-399`); own `customer_update` (`customers.py:145-173`) | exact |
| `app/templates/partials/contact_row.html` | **NEW** | component (htmx partial) | request-response | `sale_row.html` (esp. `:49` removal) | role-match (`<div>` not `<tr>`) |
| `app/templates/pages/customer_form.html` | mod | component | request-response | own `:19-24` field block; `warehouse_form.html:20-23` (address) | exact |
| `app/templates/pages/customer_detail.html` | mod | component | request-response | `finance_tiles.html` (tiles); `top_selling_rows.html` (ranked table) | exact |
| `app/static/style.css` (+`.contact-row`) | mod | config | — | `form.stacked-form input` (`:94`) | role-match |
| `tests/test_customers.py` | mod | test | — | own header (`:1-14`) + `test_purchase_history_frozen` | exact |

---

## Pattern Assignments

### `app/models.py` — `CustomerContact` + `Customer.address` (model, CRUD)

**Analog A (table shape):** `app/models.py:354-370` (`Sale`) and `:295-331` (`Operation`).

**VERIFIED — the `relationship()` claim is true.** A repo-wide grep for
`relationship|back_populates` returns **zero hits in `app/`**. Every FK in this codebase is a bare
`mapped_column(ForeignKey(...))`, joined explicitly in the service. `CustomerContact.customer_id`
MUST follow. The only `relationship` hits repo-wide are in `.planning/` prose.

**PK / FK / timestamp pattern to copy verbatim** (`models.py:345-351`, `364-367`):
```python
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
customer_id: Mapped[str | None] = mapped_column(
    ForeignKey("customers.id", name="fk_sales_customer_id_customers"), index=True
)
created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
```
Note the **explicit `name=` on the ForeignKey** — `Sale.customer_id`, `Operation.sale_id` (`:315`)
and `Operation.batch_id` (`:324`) all pass one. Copy that habit; do not rely on the convention
token here.

**Analog B (address column):** `models.py:190` — `Warehouse.address`, VERIFIED as exactly:
```python
address: Mapped[str | None] = mapped_column(String(300))
```
This grounds RESEARCH A4/A5 (300-char width). `Customer.address` is a byte-identical line.

**Allow-list dict pattern to copy** (`models.py:49-56`, `WRITEOFF_REASONS`) — latin key → RU label,
docstring naming it "the exact server-side allow-list":
```python
WRITEOFF_REASONS = {
    "damaged": "Брак",
    "expired": "Просрочка",
    ...
}
```
`CONTACT_KINDS` is this shape. `models.py:32-33` is the load-bearing precedent comment: *"no CHECK
constraint on operations.type"* — the project's established gate for a closed value set is the
Python dict, not DDL.

**⚠️ NO ANALOG — `CheckConstraint`.** See "No Analog Found" below. This is the one place the planner
cannot say "copy X".

---

### `alembic/versions/0015_customer_contacts.py` (migration, DDL)

**0014 is HEAD — VERIFIED** (`ls alembic/versions/` → `0014_drop_product_catalog_cents.py`;
`revision = "0014"`, `down_revision = "0013"`). So `revision = "0015"`, `down_revision = "0014"`.

**Analog A (create_table):** `0013_cash_movements.py:51-76` — the most recent new-table migration.
```python
def upgrade() -> None:
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("sale_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cash_movements")),
        sa.ForeignKeyConstraint(
            ["sale_id"], ["sales.id"], name=op.f("fk_cash_movements_sale_id_sales"),
        ),
        sa.UniqueConstraint("device_id", "seq", name=op.f("uq_cash_movements_device_id")),
    )
    op.create_index(
        op.f("ix_cash_movements_sale_id"), "cash_movements", ["sale_id"], unique=False
    )
```
**Critical detail the planner must not miss:** every constraint name in a migration is wrapped in
`op.f(...)` and is the **fully-expanded** name (`pk_cash_movements`, not `cash_movements`). `op.f`
marks a name as already-conventionalized so Alembic does not re-apply the convention. The new CHECK
must therefore be `name=op.f("ck_customer_contacts_kind_valid")` in the migration — **fully
expanded** — while the ORM model passes the **short** token (`name="kind_valid"`) and lets
`NAMING_CONVENTION` expand it. These two spellings differ on purpose; mixing them produces
`ck_customer_contacts_ck_customer_contacts_kind_valid` or a bare unexpanded name.

**Analog B (add_column):** `0005_product_thresholds.py:33-46` — VERIFIED, and its docstring states
the rule verbatim:
```python
def upgrade() -> None:
    op.add_column("products", sa.Column("low_stock_threshold", sa.Integer(), nullable=True))

def downgrade() -> None:
    op.drop_column("products", "stale_days")
```
> *"Native ADD COLUMN, no batch mode … never batch-alter a table whose migrations must stay
> replayable forever."* (`0005:16-19`)

**Immutability rule (WR-06) — stated in BOTH analogs** (`0005:13-14`, `0013:17-21`):
> *"this file must never reference application modules. All values below are FROZEN copies."*

So `0015` must **re-declare the `kind` literals as frozen strings**, never `from app.models import
CONTACT_KINDS`. `0013:34-37` shows the sanctioned way to write that frozen copy with a comment:
```python
# Frozen snapshot of ... (duplicated from app.db.APPEND_ONLY_TRIGGERS on purpose —
# migrations may duplicate app constants, they must not reference them).
```

**Do NOT copy `0013`'s triggers.** `customer_contacts` is a mutable table; append-only triggers are
scoped to `operations` / `cash_movements` only.

---

### `app/services/customers.py` — insight functions (service, SQL aggregate)

**Analog A (the join):** `customers.py:202-214`, VERIFIED at the cited lines:
```python
def purchase_history(session: Session, customer_id: str) -> list[dict]:
    """Sale ops for one customer joined to their products, newest first (CST-02).

    Reads the FROZEN op.unit_price_cents — never the current Product price.
    """
    rows = session.execute(
        select(Operation, Product)
        .join(Sale, Operation.sale_id == Sale.id)
        .join(Product, Operation.product_id == Product.id)
        .where(Sale.customer_id == customer_id, Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
```
Both new queries extend this `Operation → Sale → Product` join. Note `.order_by(created_at.desc(),
seq.desc())` — this is why `history[0]` is the last order (CUST-06) with no 7th query.

**Analog B (SQL-side ranked aggregate):** `reports.py:144-167`, VERIFIED:
```python
def top_selling_products(session, start_iso, end_iso, limit=10) -> list[dict]:
    """Top products by units sold (descending) in a UTC [start_iso, end_iso) period.

    RESEARCH Pattern 4: SQL-side aggregation (func.sum/.group_by()/.order_by()
    /.limit()), not a Python accumulator — sales history can be large,
    unlike the small fixed-cardinality write-off grouping in writeoff_report.
    """
    units_sold = func.sum(-Operation.qty_delta).label("units_sold")
    stmt = (
        select(Product, units_sold)
        .join(Operation, Operation.product_id == Product.id)
        .where(Operation.type == "sale", Operation.created_at >= start_iso, Operation.created_at < end_iso)
        .group_by(Product.id)
        .order_by(units_sold.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    return [{"product": product, "units_sold": units} for product, units in rows]
```
`favorite_products` = this shape + a `Sale` join + a `count(distinct)` column. The
labeled-expression-reused-in-`order_by` idiom and the `list[dict]` return shape are both house
style — copy both.

**Analog C (frozen price contract, D-06's foundation):** `returns.py:152-163` — VERIFIED, and the
RESEARCH citation of "line 157" is **exact**:
```python
op = record_operation(
    session,
    type_="return",
    product_id=origin.product_id,
    qty_delta=qty,
    unit_price_cents=origin.unit_price_cents,  # D-07 frozen copy
    unit_cost_cents=origin.unit_cost_cents,  # D-07 frozen copy
    sale_id=origin.sale_id,
    ...
)
```
`sale_id=origin.sale_id` (`:159`) is what makes the `Sale` join reachable from `return` rows — D-06's
single-formula netting depends on this line. `returns.py:168` also shows the house `(x or 0)`
null-price guard: `debit = qty * (origin.unit_price_cents or 0)`.

**Analog D (WR-05 length guards):** `customers.py:23-45` — VERIFIED at the cited lines:
```python
# WR-05: mirror the declared column lengths (app/models.py Customer) here so
# an overlong value is rejected in the service layer instead of silently
# truncated by SQLite today and hard-erroring after a future PostgreSQL
# migration (CLAUDE.md: "same models will run on PostgreSQL later").
_NAME_MAX_LEN = 200
_SURNAME_MAX_LEN = 200
_CONSULTANT_NUMBER_MAX_LEN = 50


def _validate_lengths(name, surname, consultant_number, errors: dict[str, str]) -> None:
    """WR-05: shared max-length guard for create_customer/update_customer."""
    if len(name) > _NAME_MAX_LEN:
        errors["name"] = NAME_TOO_LONG_ERROR
```
Add `_CONTACT_VALUE_MAX_LEN = 300` / `_ADDRESS_MAX_LEN = 300` here and extend `_validate_lengths`
(or add a sibling). RU error constants live at module top (`customers.py:18-21`), UPPER_SNAKE,
suffixed `_ERROR`.

**Analog E (allow-list, never interpolated):** `customers.py:148-153`, VERIFIED:
```python
# LIST-01..03: allow-list of sort keys for list_customers_view — never
# string-interpolated into a sort expression (T-14-18 mitigation).
_SORT_MAP = {
    "surname": lambda c: (c.surname or "").lower(),
    "consultant_number": lambda c: (c.consultant_number or "").lower(),
}
```
This is the in-file precedent for gating `kind` against `CONTACT_KINDS`.

**Analog F (write-path shape):** `create_customer` (`:48-78`) / `update_customer` (`:81-112`) —
`(obj | None, dict[str, str])` return, `.strip()` every input, `x or None` before assign, single
`session.commit()` at the end. `replace_contacts` must slot inside this transaction (no extra
commit).

---

### `app/routes/customers.py` (route, request-response)

**Analog A (the CR-01 allow-list guard on an htmx row route):** `sales.py:312-333` — VERIFIED, the
RESEARCH citation of `312-320` is **exact**:
```python
@router.get("/sales/row")
def sale_row(request: Request, row: str = ""):
    # A fresh row is always appended alongside existing rows (hx-swap
    # "beforeend"), so it needs a unique, never-blank row id.
    # CR-01: row_id is later interpolated into an hx-on::load JS attribute
    # (sale_row.html), so client input must be format-validated before use
    # instead of trusted as-is.
    row = row.strip()
    row_id = row if _ROW_ID_RE.fullmatch(row) else new_id()
    context = {"row_id": row_id, "code": "", ...}
    return templates.TemplateResponse(request, "partials/sale_row.html", context)
```
**Adaptation note:** `sale_row` *falls back* to a fresh id on invalid input. For `kind` there is no
sensible fallback — a `kind` outside `CONTACT_KINDS` should `raise HTTPException(status_code=404)`,
matching this file's own unknown-resource convention (`customers.py:131,140,164`:
`raise HTTPException(status_code=404, detail="unknown customer")`). The *principle* to copy from
`sale_row` is "validate before interpolating", not the specific fallback.

**Analog B (route-order rule) — VERIFIED, `customers.py:22-25`** already documents it:
```python
# Route order: literal paths (/customers/new) MUST stay declared before the
# parameterized /customers/{customer_id} routes below. /customers/search was
# retired (LIST-02/D-04, Pitfall 6) — its filtering folded into /customers'
# header-row filters; the sale-picker's own /sales/customer-search is separate.
```
`GET /customers/new` sits at `:98`, `GET /customers/{customer_id}` at `:127`. **Declare
`/customers/contact-row` in the `:98-102` neighbourhood** — above `:127`. Extend the existing
comment rather than adding a second one.

**Analog C (form-array binding):** `sales.py:389-398` — VERIFIED verbatim at the cited lines:
```python
@router.post("/sales")
def sale_create(
    request: Request,
    code: list[str] = Form([], alias="code[]"),
    qty: list[str] = Form([], alias="qty[]"),
    price: list[str] = Form([], alias="price[]"),
    batch_id: list[str] = Form([], alias="batch_id[]"),
    customer_id: str = Form(""),
    ...
```

**Analog D (the exact handler to extend):** `customers.py:145-173`, `customer_update` — the 422
re-echo shape the new contact arrays must join:
```python
    customer, errors = update_customer(session, customer_id, name=name, ...)
    if errors:
        existing = get_customer(session, customer_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="unknown customer")
        context = {
            "customer": existing,
            "errors": errors,
            "form": {"name": name, "surname": surname, "consultant_number": consultant_number},
        }
        return templates.TemplateResponse(
            request, "pages/customer_form.html", context, status_code=422
        )
    return RedirectResponse("/customers", status_code=303)
```
The submitted contact arrays + address go into that `"form"` dict so UI-SPEC Interaction 9's re-echo
works. `customer_new` (`:98-101`) renders `{"customer": None, "errors": {}, "form": {}}` — **this is
the exact line that makes per-row server CRUD impossible** (RESEARCH Pitfall 2), verified.

**Analog E (detail context to extend):** `customers.py:127-133`:
```python
@router.get("/customers/{customer_id}")
def customer_detail(request: Request, customer_id: str, session: Session = Depends(get_session)):
    customer = get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="unknown customer")
    context = {"customer": customer, "history": purchase_history(session, customer_id)}
    return templates.TemplateResponse(request, "pages/customer_detail.html", context)
```
`history` is already loaded here → `history[0]["op"].created_at` is CUST-06 for free.

---

### `app/templates/partials/contact_row.html` (**NEW** — component, request-response)

**Analog:** `sale_row.html`. Match quality: **role-match, not exact** — copy the *mechanism*, not the
markup (`<div>` vs `<tr>`; one data column vs five).

**Client-side row removal — VERIFIED at `sale_row.html:49`:**
```jinja
<button type="button" class="secondary" hx-on:click="this.closest('tr').remove(); var w=document.getElementById('{{ batch_wrap_id }}'); if (w) w.remove()">Удалить строку</button>
```
Copy `type="button" class="secondary" hx-on:click="this.closest(...).remove()"`. **Drop the
`var w=...` batch-wrapper cleanup** — contact rows have no parallel hidden array, so it has no analog
(UI-SPEC Interaction 5 says the same).

**Array-named input — VERIFIED at `sale_row.html:16`** (UI-SPEC cites `:16`, RESEARCH cites `:15`;
**`:16` is correct**):
```jinja
<input type="text" id="{{ code_id }}" name="code[]" value="{{ code or '' }}"
```
Copy `name="{{ kind }}[]" value="{{ value or '' }}"`. **Do not copy the `id=` scheme**
(`sale_row.html:8-12`'s `{% set code_id = ... %}` block) — those ids exist to serve `sale_row`'s
focus hook (`:13`) and `hx-target`s (`:22`); a contact row has neither (UI-SPEC Interaction 4).

**Docstring convention:** every partial opens with a `{# ... #}` block citing its decision ids
(`sale_row.html:1-7`, `purchase_history.html:1-3`, `finance_tiles.html:1-8`). `contact_row.html`
must too.

---

### `app/templates/pages/customer_form.html` (component, request-response)

**Analog A (the field block to replicate ×4 + address):** own `:19-24`, VERIFIED:
```jinja
  <div class="field">
    <label for="surname">Фамилия <span class="muted">(необязательно)</span></label>
    <input type="text" id="surname" name="surname"
           value="{% if form %}{{ form.surname or '' }}{% elif customer %}{{ customer.surname or '' }}{% endif %}">
    {% if errors.surname %}<p class="error">{{ errors.surname }}</p>{% endif %}
  </div>
```
The `{% if form %}…{% elif customer %}…{% endif %}` echo chain is the convention UI-SPEC
Interaction 9 requires. The `<span class="muted">(необязательно)</span>` optional marker is here at
`:20` and `:27` — VERIFIED.

**Analog B (address field):** `warehouse_form.html:20-23` — VERIFIED, the in-repo precedent for a
physical address, and it is an `<input type="text">`, **not** a textarea:
```jinja
    <label for="address">Адрес <span class="muted">(необязательно)</span></label>
    <input type="text" id="address" name="address"
           value="{% if form %}{{ form.address or '' }}{% elif warehouse %}{{ warehouse.address or '' }}{% endif %}">
    {% if errors.address %}<p class="error">{{ errors.address }}</p>{% endif %}
```
`Customer.address`'s block is this with `warehouse` → `customer`.

**Analog C (the add-row button):** `sale_form.html:74` (cited by CONTEXT/UI-SPEC as
`hx-get="/sales/row" hx-target="#basket-rows" hx-swap="beforeend"`). Structure per UI-SPEC
Interaction 2. Insert the 4 contact sections + address **between `:31` and `:33`** (after
consultant_number's `.field`, before `.form-actions`) — UI-SPEC Interaction 7's field order.

---

### `app/templates/pages/customer_detail.html` (component, request-response)

**Current file is 14 lines** — VERIFIED; the whole body is:
```jinja
<p class="page-actions"><a href="/customers/{{ customer.id }}/edit">Изменить</a></p>

<section id="customer-history">
  <h2>История покупок</h2>
  {% include "partials/purchase_history.html" %}
</section>
```
Three new `<section id=...><h2>…</h2>{% include %}</section>` blocks are inserted **above**
`#customer-history` (UI-SPEC Interaction 11). The `<section id>` + `<h2>` + `{% include %}` shape is
the analog — copy it.

**Analog A (metric tiles):** `finance_tiles.html:9-20`, VERIFIED:
```jinja
<div class="metric-grid">
  <div class="metric-tile">
    <p class="tile-label">Валовая прибыль</p>
    <p class="num"><strong>{{ metrics.gross_profit_cents | cents }}</strong></p>
```
And the mandatory-caveat precedent, VERIFIED at `:29-30`:
```jinja
    {# MANDATORY (D-01b) — always visible, never a title= tooltip alone. #}
    <p class="muted">Денежный поток: валовая прибыль минус снятия и возвраты за период. Это не бухгалтерская прибыль.</p>
```
This is the exact precedent for «С учётом возвратов.». The no-sign-coloring rule is stated at
`finance_tiles.html:7-8`: *"Money is NEVER sign-colored (UI-SPEC Q4): plain `| cents` in default
text color."*

**Analog B (ranked table + empty state):** `top_selling_rows.html`, VERIFIED at both cited lines —
`:12` empty state, `:25` product cell:
```jinja
{% elif top_selling | length == 0 %}
<p class="empty-state muted">За выбранный период продаж не было.</p>
{% else %}
<table>
  <thead>
    <tr>
      <th>Товар</th>
      <th class="num">Продано, шт.</th>
    </tr>
  </thead>
  <tbody>
    {% for row in top_selling %}
    <tr>
      <td>{{ row.product.name }} ({{ row.product.code }})</td>
      <td class="num">{{ row.units_sold }}</td>
    </tr>
```
Favorites = this + a third `<th class="num">`. **Do not copy the `{% if x is none %}` error-block
branch** (`:7-10`) — that exists for the period filter's bad-date case; favorites has no such state.

**Analog C (null-date guard + autoescape rule):** `purchase_history.html`, VERIFIED at all three
cited points:
```jinja
{# Purchase history (CST-02): reads the FROZEN op.unit_price_cents — NEVER
   the current Product.sale_cents (RESEARCH Anti-Pattern). Autoescape only;
   never |safe. #}
{% if not history %}
<p class="muted">Покупок пока нет.</p>
```
and the null guard at `:26` — **VERIFIED, and note it is `<span class="muted">—</span>`, exactly the
CUST-06 zero-orders treatment**:
```jinja
<td class="num">{% if h.op.unit_price_cents is not none %}{{ h.op.unit_price_cents | cents }}{% else %}<span class="muted">—</span>{% endif %}</td>
```
`| local_dt` renders the date at `:22`: `<td>{{ h.op.created_at | local_dt }}</td>`.

---

### `app/static/style.css` (config)

**`.contact-row` is genuinely absent — VERIFIED** (repo-wide grep: the only `.contact-row` hits are
inside `.planning/`). The UI-SPEC's stated reason is also verified — `style.css:94` is indeed
`.stacked-form input { ... }`, and `form.stacked-form` at `:71`. Confirmed present and reusable
without change: `.num` (`:225`), `.empty-state` (`:248`), `.metric-grid` (`:356`), `.metric-tile`
(`:369`), `.tile-label` (`:376`).

Append the single UI-SPEC rule block. Existing rules carry a `/* ... */` comment citing the phase —
match that.

---

### `tests/test_customers.py` (test)

**Analog:** own header, VERIFIED at `:1-14`:
```python
"""CST-01/02 executable contract for the customer CRUD + purchase-history slice.

Naming convention (used by -k filters): route/e2e tests are prefixed
test_web_; everything else is service level. Selectors mirror
04-VALIDATION.md's Requirements -> Test Map (crud, search, history,
history_frozen).
"""

from sqlalchemy import select

from app.models import Customer
from app.services.customers import (
    create_customer,
    get_customer,
    ...
)
from app.services.sales import register_sale  # noqa: F401 (used to seed linked sales)
```
`test_web_` prefix for route tests; bare names for service tests. Extend the module docstring's
selector list with the new phase's selectors rather than adding a second docstring.

**Mandatory tests flagged by RESEARCH** (Pitfalls 4, 7): a customer with **zero orders** (must yield
`0`, never `None`), and an **injected `today`** for every period-boundary assertion.

---

## Shared Patterns

### Jinja filter registration (already done — do NOT re-register)
**Source:** `app/routes/__init__.py:14-19` — VERIFIED at the cited lines.
```python
templates = Jinja2Templates(directory="app/templates")
# D-07: store UTC, display local; D-06: cents rendered only via helper.
templates.env.filters["local_dt"] = lambda iso: iso_to_local(iso, settings.display_tz)
templates.env.filters["cents"] = format_cents
# LOT-03: batch expiry stored as ISO text; rendered dd.mm.yyyy in every surface.
templates.env.filters["ru_date"] = format_ru_date
```
**Apply to:** all Phase 21 templates. All three filters this phase needs already exist — **no filter
work is required**.

**But note — a real gap:** `| ru_date` is `format_ru_date` (`core.py:56-66`), which calls
`date.fromisoformat(iso)` on a **string**. UI-SPEC Interaction 15 wants `{{ month_start | ru_date }}`
where `month_start` is a Python `date` from `_period_starts`. `date.fromisoformat(date(...))` raises
`TypeError`. **The route must pass `start.isoformat()` (a str), not the `date` object** — or the
caption crashes. This is not covered by RESEARCH or UI-SPEC. Flagging for the planner.

If `CONTACT_KINDS` must be readable from a template, register it as a **global** here — the
established pattern (`__init__.py:20-28`), which explicitly notes `CASH_BUCKETS` stays server-side
only:
```python
templates.env.globals["WRITEOFF_REASONS"] = WRITEOFF_REASONS
templates.env.globals["CASH_CATEGORIES"] = CASH_CATEGORIES
```

### Money rendering
**Source:** `app/core.py:49-53` — VERIFIED; renders negatives correctly (grounds UI-SPEC Color 1 and
Pitfall 8).
```python
def format_cents(cents: int) -> str:
    """Render integer cents as a display string with comma separator: 1250 -> '12,50'."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole},{frac:02d}"
```
**Apply to:** every money value in `customer_detail.html`, via `{{ x | cents }}` only.

### Period bounds
**Source:** `app/core.py:75-93` — VERIFIED. Signature is exactly
`local_day_bounds_utc(start_day: date, end_day: date, tz_name: str) -> tuple[str, str]`, and the
docstring states it is *"the ONLY sanctioned way to turn a local calendar day/range into a UTC
filter range (D-02)"*, returning a **half-open** `[start, end)` pair.
**Apply to:** all three spend windows. Never slice `created_at` strings by date.

### Error-constant convention
**Source:** `customers.py:18-21` — VERIFIED.
```python
NAME_REQUIRED_ERROR = "Укажите имя покупателя."
NAME_TOO_LONG_ERROR = "Слишком длинное имя."
```
Module-level, UPPER_SNAKE, `_ERROR` suffix, RU copy ending in a period. **Apply to:** the two new
length errors in UI-SPEC's Copywriting table.

### Service return contract
**Source:** `customers.py:54,88` — `tuple[Customer | None, dict[str, str]]`; `(obj, {})` on success,
`(None, errors)` on failure; the route branches on `if errors:`. **Apply to:** every new write
function.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/models.py` — the `CheckConstraint` on `customer_contacts.kind` | model | — | **VERIFIED: zero `CheckConstraint` occurrences anywhere in `app/` or `alembic/`.** Phase 21 introduces the project's first one. There is nothing to copy. |

**The planner must be told the exact form, because getting it wrong breaks the whole test suite at
import time.** `models.py:24-30` is VERIFIED as:
```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```
The `%(constraint_name)s` token has no value unless `name=` is passed, so an unnamed
`CheckConstraint` raises `InvalidRequestError` at **import** of `app.models` — every test fails to
collect, not just new ones.

**Model (short name — convention expands it):**
```python
__table_args__ = (
    # name= is MANDATORY: NAMING_CONVENTION's ck_%(table_name)s_%(constraint_name)s
    # raises InvalidRequestError without it.
    CheckConstraint("kind IN ('phone', 'telegram', 'email', 'social')", name="kind_valid"),
)
# -> emits: CONSTRAINT ck_customer_contacts_kind_valid CHECK (kind IN (...))
```
`CheckConstraint` must be added to the `from sqlalchemy import (...)` block at `models.py:8-17`
(currently: `JSON, ForeignKey, Index, Integer, MetaData, String, UniqueConstraint, text`).

**Migration (fully-expanded name, wrapped in `op.f`)** — per the `0013:64-72` convention:
```python
sa.CheckConstraint(
    "kind IN ('phone', 'telegram', 'email', 'social')",
    name=op.f("ck_customer_contacts_kind_valid"),
),
```
The literals are a **frozen copy** (WR-06) — never imported from `app.models`.

**Nearest thing to a precedent, and it argues for restraint:** `models.py:32-33`, VERIFIED:
```python
# Phase 1 shipped "correction"; Phase 2 adds the qty_delta=0 audit types
# (RESEARCH Finding 5 — no CHECK constraint on operations.type, no migration).
```
The house convention for a closed value set is the Python dict allow-list validated in the service
(`WRITEOFF_REASONS`, `models.py:49`, docstring: *"the exact server-side allow-list write-offs
validate against"*). Ship `CONTACT_KINDS` as the primary gate (it produces the RU error); the CHECK
per D-01 is defence-in-depth only.

---

## Citation Verification Log

Every inherited citation was re-checked against the live files. Results:

**Exact (23):** `models.py` `Customer` 333-351, `Operation` 295-331, `Sale` 354-370,
`NAMING_CONVENTION` 24-30, `Warehouse.address` 190 · `customers.py` `purchase_history` 202-214,
`_SORT_MAP` 150-153, WR-05 guards 23-29 · `returns.py` frozen copy 157, `sale_id` 159 ·
`reports.py` `top_selling_products` 144, `units_sold` 153-165 · `sales.py` `_ROW_ID_RE` guard
312-320, form arrays 392-395 · `routes/customers.py` route-order comment 22-25, `customer_new`
99-101, detail 132 · `routes/__init__.py` filters 16-19 · `core.py` `format_cents` 49-53,
`local_day_bounds_utc` 75 · `sale_row.html:49` · `purchase_history.html` 1-5, 26 ·
`top_selling_rows.html` 12, 25 · `warehouse_form.html:20` · `finance_tiles.html` 13, 29-30 ·
`style.css` 94, 356-379 · `0005` docstring rule.

**Corrections (3):**
1. **`sale_row.html` array input is line `16`, not `15`.** RESEARCH Pattern 3 cites `:15`; `:15` is
   the `{# D-10/RCP-02 analog #}` comment. UI-SPEC's `:16` is right.
2. **Alembic analog for the new table should be `0013_cash_movements.py`, not "the 0014-era
   migration".** `0014` is a `drop_column` — the wrong shape entirely. `0013` (create_table) and
   `0005` (add_column) are the two real analogs. `0014` is relevant only as the head pointer
   (`down_revision = "0014"`), which is VERIFIED correct.
3. **`| ru_date` takes a `str`, not a `date`** — see "Jinja filter registration" above. UI-SPEC
   Interaction 15's `{{ month_start | ru_date }}` will `TypeError` unless the route passes
   `.isoformat()`. Not flagged anywhere upstream.

**Confirmed absences (3):** `relationship()`/`back_populates` → zero in `app/`. `CheckConstraint` →
zero in `app/` and `alembic/`. `.contact-row` → zero in `style.css`.

## Metadata

**Analog search scope:** `app/models.py`, `app/core.py`, `app/routes/`, `app/services/`,
`app/templates/pages/`, `app/templates/partials/`, `app/static/style.css`, `alembic/versions/`,
`tests/`
**Files read in full or in targeted ranges:** 19
**Pattern extraction date:** 2026-07-17
