# Phase 22: Sales Page Rebuild - Pattern Map

**Mapped:** 2026-07-17
**Files analyzed:** 14 new/modified
**Analogs found:** 13 / 14 (1 no-analog: `mobile_partials/customer_picker.html` — no mobile picker exists in any wizard)

All excerpts below were read from the repo in this session. Line numbers are current as of 2026-07-17.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/routes/sales.py` (+`GET /sales/customer-mode`, `_customer_context`) | route | request-response | `app/routes/sales.py::sale_customer_create` (:343-386) | exact (same file) |
| `app/routes/sales.py::sale_create` error branches (D-10/D-12) | route | request-response | its own success branch (:457+) + `_build_lines` (:43-94) | exact |
| `app/routes/mobile_sales.py::mobile_sale_create` (D-04) | route | request-response | `app/routes/sales.py::sale_create` (:389-409) | exact |
| `app/services/sales.py::recent_sales` (SALE-07) | service | CRUD/read | `app/services/export.py::stream_sales_csv` (:117-125) | exact |
| `app/templates/partials/sale_customer.html` (restructured) | template partial | request-response | `partials/receipt_batch_chooser.html` (:19-50) — radio group; itself for the chip/picker | exact |
| `app/templates/partials/sale_form.html` (+`#sale-total`) | template partial | request-response | `partials/finance_tiles.html:13` — `<p class="num"><strong>` | role-match |
| `app/templates/partials/sale_row.html` (+recompute hook) | template partial | event-driven | itself, `sale_row.html:49` | exact |
| `app/templates/partials/recent_sales.html` (+column) | template partial | request-response | itself (:25-35) | exact |
| `app/static/sale-total.js` (NEW) | client utility | event-driven | `app/static/price-cue.js` (whole file, 23 lines) | exact |
| `app/templates/base.html` (+script tag) | layout | — | `base.html:22-26` | exact |
| `app/templates/mobile_base.html` (+script tag) | layout | — | `mobile_base.html:16-22` | exact |
| `app/templates/mobile_partials/sale_customer.html` (NEW) | template partial | request-response | `mobile_partials/receipts_step_batch.html:30-51` — mobile fieldset/legend/`.mobile-card` radios | role-match |
| `app/templates/mobile_partials/sale_basket.html` (+selector, +total) | template partial | request-response | itself (:5-46) | exact |
| `app/templates/mobile_partials/batch_card_picker.html` (D-11) | shared partial | request-response | `writeoff_step_batch.html:20`, `corrections_step_batch.html:25` — `hx-include="closest form"` | partial — **see WARNING below** |
| `app/templates/mobile_partials/customer_picker.html` (NEW) | template partial | request-response | **none** — see §No Analog Found |
| `tests/test_sales_total.py` (NEW) | test | — | `tests/test_sales.py` | exact |

---

## Pattern Assignments

### `app/routes/sales.py` — `_customer_context()` + `GET /sales/customer-mode` (route, request-response)

**Analog:** `app/routes/sales.py::sale_customer_create` (:343-386) — the shipped endpoint that already renders `partials/sale_customer.html` from a hand-built context dict on three paths.

**Imports pattern** (`sales.py:1-28`) — note what is **missing**:
```python
from app.core import new_id
from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.customers import create_customer, customer_search_view
```
> **`get_customer` is NOT imported here today.** It exists at `app/services/customers.py:227` and is currently imported only by `app/routes/customers.py:16`. `_customer_context` must add it to the `app.services.customers` import line — this is a real new import, not a reuse-in-place.

**Route-order rule to copy verbatim** (`sales.py:30-32`):
```python
# Route order: literal paths (/sales/new, /sales/lookup, /sales/row) MUST
# stay declared before any parameterized /sales/{...} route added later
# (04-05 customer picker endpoints are also literal paths, so this holds).
```

**Allow-list precedent** (`sales.py:36-40`) — the *heavier* guard, deliberately NOT the one to copy:
```python
# CR-01: row_id is echoed unescaped into an hx-on::load JS-evaluated
# attribute (sale_row.html), so it must be constrained to the exact shape
# new_id() produces (a UUID4 string) before it is ever trusted. Anything
# that doesn't match is discarded in favor of a freshly generated id.
_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")
```
> `customer_mode` never reaches a JS-evaluated attribute (only `{% if mode == "new" %}` comparisons), so copy the *lighter* `_SORT_MAP` allow-list shape from `app/services/customers.py:262` instead: a module-level tuple/dict, membership-checked, default on miss.

**Error handling pattern — copy this shape exactly** (`sales.py:354-373`):
```python
    try:
        customer, errors = create_customer(
            session, name=name, surname=surname, consultant_number=consultant_number
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-02: log so a real bug isn't silently reduced to a generic
        # user-facing message with no server-side trace.
        logger.exception("create_customer failed")
        # "quick_create" (not "form") — sale_customer.html is included inside
        # sale_form.html on the normal basket routes, which already renders
        # its OWN errors.form; a shared "form" key would double-render the
        # same error block when both are present.
        context = {
            "selected": None,
            "errors": {"quick_create": SAVE_FAILED_ERROR},
            "form": {"name": name, "surname": surname, "consultant_number": consultant_number},
        }
        return templates.TemplateResponse(
            request, "partials/sale_customer.html", context, status_code=422
        )
```
> The `noqa: BLE001` comment, the `logger.exception(...)` line, and the `errors.quick_create` key choice are all load-bearing house conventions. `SAVE_FAILED_ERROR` is at `sales.py:34`.

**The three context dicts `_customer_context` must replace** — these are the D-12 bug surface, all in `sale_create`:
```python
# sales.py:414-420  (unexpected-exception branch)
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "lines": _build_lines(session, code, qty, price, batch_id, {}),
            "customer_id": customer_id,          # <-- no `selected`, no `mode`, no `form`
            "focus_code": False,
            "include_oob_rows": False,
        }
# sales.py:432-440  (oversell/below_minimum branch) — same `"customer_id": customer_id,`
# sales.py:444-450  (validation-errors branch)      — same `"customer_id": customer_id,`
```
And the fourth path, `sale_new_page` (`sales.py:98-106`):
```python
    context = {
        "errors": {},
        "lines": [],
        "customer_id": "",
        "focus_code": False,
        "sales": recent_sales(session),
    }
```
> All four hand-write `customer_id` with no `selected`. `sale_customer.html:17` renders the chip on `{% if selected %}` → chip never appears on a re-render while `#customer-id-input` (:14-15) still carries the id. **Warning sign for review:** any surviving `"customer_id": customer_id,` literal in a `sale_create` branch.

**`sale_create`'s signature — do not widen beyond one param** (`sales.py:389-398`):
```python
@router.post("/sales")
def sale_create(
    request: Request,
    code: list[str] = Form([], alias="code[]"),
    qty: list[str] = Form([], alias="qty[]"),
    price: list[str] = Form([], alias="price[]"),
    batch_id: list[str] = Form([], alias="batch_id[]"),
    customer_id: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
```
> D-10's 422 guard needs `customer_mode`, `name`, `surname`, `consultant_number` added as `Form("")` params. FastAPI binds only declared params, so the echoed hidden inputs are otherwise ignored — do **not** add `**kwargs`.

---

### `app/routes/mobile_sales.py::mobile_sale_create` (route, request-response)

**Analog:** `app/routes/sales.py::sale_create` — same service call, same error/warn/success branch shape.

**The exact lines to change** (`mobile_sales.py:333-352`):
```python
@router.post("/m/sales")
def mobile_sale_create(
    request: Request,
    code_acc: list[str] = Form([], alias="code_acc[]"),
    qty_acc: list[str] = Form([], alias="qty_acc[]"),
    price_acc: list[str] = Form([], alias="price_acc[]"),
    batch_acc: list[str] = Form([], alias="batch_acc[]"),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        result, errors = register_sale(
            session,
            customer_id="",  # D-04: no mobile customer picker this phase
            codes=code_acc,
```
> Add `customer_id: str = Form("")` to the signature; replace the hardcode with `customer_id=customer_id`. **Delete the `# D-04: no mobile customer picker this phase` comment** — it is explicitly superseded and will mislead.

**Mobile-specific error handling that desktop does NOT have** (`mobile_sales.py:353-359`) — copy this if any new mobile branch queries after a failure:
```python
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-01: rollback FIRST — an unexpected failure may have left the
        # session needing rollback (e.g. a failed flush/commit); the
        # _basket_lines query below would otherwise raise an unhandled
        # PendingRollbackError instead of this graceful 422.
        session.rollback()
        logger.exception("register_sale failed")
```

---

### `app/services/sales.py::recent_sales` (service, CRUD/read)

**Analog:** `app/services/export.py:117-125` — the shipped double-outerjoin, verbatim.

**Core pattern to copy** (`export.py:117-125`):
```python
    query = (
        select(Operation, Product, Sale, Customer)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
        .where(Operation.type == "sale")
        .order_by(Operation.created_at)
    )
```

**The function being extended, in full** (`services/sales.py:333-342`):
```python
def recent_sales(session: Session, limit: int = 10) -> list[dict]:
    """Last N sale ops joined to their products, newest first (mirrors D-04)."""
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
```
> Keep the `.order_by(Operation.created_at.desc(), Operation.seq.desc())` and `.limit(limit)` — those differ from `export.py` on purpose (newest-first UI listing vs chronological dump; `export.py:114-116` documents the divergence). `Customer` is not yet in this module's `app.models` import — add it. **`.join` (inner) on `Customer` would drop every walk-in sale.**

---

### `app/templates/partials/sale_customer.html` (template partial, request-response)

**Analog A — the radio group shape:** `partials/receipt_batch_chooser.html:19-50`, the shipped `fieldset`+`legend`+wrapped-`label` group.

```jinja
  {% set new_selected = not batches %}
  <fieldset class="field">
    <legend>Партия</legend>
    {% if not code_entered %}
    <p class="muted">Введите код товара и выберите склад, чтобы увидеть его партии. Пока товар не выбран, приход создаст новую партию.</p>
    {% elif not batches %}
    <p class="muted">У этого товара нет открытых партий — приход создаст новую.</p>
    {% else %}
    <p class="muted">Выберите партию для пополнения или создайте новую.</p>
    {% endif %}
    {% for batch in batches %}
    <label>
      <input type="radio" name="batch_choice" value="{{ batch.id }}"
             hx-on:change="document.getElementById('new-batch-fields').hidden = true; ...">
      Пополнить партию: ...
    </label>
    {% endfor %}
    <label>
      <input type="radio" name="batch_choice" value="new"{% if new_selected %} checked{% endif %}
             hx-on:change="...">
      Новая партия
    </label>
    {% if errors and errors.batch_choice %}<p class="error">{{ errors.batch_choice }}</p>{% endif %}
  </fieldset>
```
> Copy: `class="field"` on the `fieldset` (supplies the 16px gap), `<legend>` as the group's accessible name, each `<input type="radio">` **wrapped inside** its `<label>` (no `for=`/`id=` pairing), `{% if ... %} checked{% endif %}` for the default, and the `<p class="muted">` caption inside the fieldset (this is the precedent for D-06's anon caption). **Do not copy** the `hx-on:change` per-radio JS — Phase 22's radio uses one `hx-get` on the `<fieldset>` itself.
> Note this partial also shows the `.muted` caption and per-field `<p class="error">` idioms the new-customer block already uses.

**Analog B — the chip + hidden-input contract to preserve:** the file itself (`sale_customer.html:1-23`).

```jinja
{# Customer header (SAL-03/D-05): search existing customers, quick-create
   inline, or leave walk-in (D-04). Lives OUTSIDE <form id="sale-form"> (the
   basket form must not nest another form) — every input here associates via
   form="sale-form" so it still submits with the basket on finalize. Root
   id="customer-header" is the outerHTML swap target for the quick-create
   POST below, so a create fully re-renders this block. ... #}
<div id="customer-header" class="customer-header">
  <input type="hidden" id="customer-id-input" name="customer_id" form="sale-form"
         value="{{ selected.id if selected else (customer_id or '') }}">

  <div id="customer-selected" class="customer-chip"{% if not selected %} hidden{% endif %}>
    <span id="customer-chip-text">{% if selected %}Покупатель: {{ selected.name }} {{ selected.surname or '' }}{% endif %}</span>
    <button type="button" class="secondary"
            hx-on:click="document.getElementById('customer-id-input').value = '';
              document.getElementById('customer-selected').hidden = true;
              document.getElementById('customer-default').hidden = false;">Убрать</button>
  </div>
```
> Four ids are hard contracts (`sale_oversell.html` and `customer_picker.html` reach them by name): `customer-header`, `customer-id-input`, `customer-selected`, `customer-chip-text`, plus `customer-default`. `form="sale-form"` on `#customer-id-input` is what makes the oversell confirm re-POST carry the customer.

**Existing quick-create button — note the `hx-include` selector already in use** (`sale_customer.html:57-62`):
```jinja
      <button type="button"
              hx-post="/sales/customer"
              hx-include="#customer-header input"
              hx-target="#customer-header"
              hx-swap="outerHTML"
              hx-disabled-elt="this">Добавить покупателя</button>
```
> It ships as `#customer-header input` (element-scoped), not `#customer-header`. RESEARCH's Pattern-1 example writes `#customer-header`. Either works for htmx; pick one and be consistent across the radio's `hx-get` and this button.

**The 3-field block — D-07's hard cap, reuse verbatim** (`sale_customer.html:42-56`):
```jinja
      <div class="field">
        <label for="customer-name">Имя</label>
        <input type="text" id="customer-name" name="name" value="{{ form.name if form else '' }}">
        {% if errors.name %}<p class="error">{{ errors.name }}</p>{% endif %}
      </div>
      <div class="field">
        <label for="customer-surname">Фамилия <span class="muted">(необязательно)</span></label>
        <input type="text" id="customer-surname" name="surname" value="{{ form.surname if form else '' }}">
        {% if errors.surname %}<p class="error">{{ errors.surname }}</p>{% endif %}
      </div>
      <div class="field">
        <label for="customer-consultant">Номер консультанта <span class="muted">(необязательно)</span></label>
        <input type="text" id="customer-consultant" name="consultant_number" value="{{ form.consultant_number if form else '' }}">
        {% if errors.consultant_number %}<p class="error">{{ errors.consultant_number }}</p>{% endif %}
      </div>
```
> Note the shipped guard is `{{ form.name if form else '' }}`, not `{{ form.name or '' }}` (RESEARCH's example uses the latter). If `_customer_context` always supplies `form`, either is safe — but the existing partial is rendered from `sale_form.html` include contexts that may not define `form`, so keep `if form else ''` unless every path is proven.

**Also present today and slated for removal from the default block** — `sale_customer.html:38`:
```jinja
    <p class="muted">Без покупателя (розница)</p>
```
> This is the verbatim source of UI-SPEC's anon-mode label. It is a carry-over, not an invention.

---

### `app/static/sale-total.js` (client utility, event-driven) — NEW

**Analog:** `app/static/price-cue.js` — the entire 23-line file, read verbatim:

```javascript
// app/static/price-cue.js — PROD-06 / D-10
// One delegated listener: covers desktop, mobile, and HTMX-added basket rows
// with no re-initialisation (D-12: never a round-trip per keystroke — swapping
// a focused input destroys focus AND caret, and sale_row.html's price[] inputs
// have no id for htmx to restore focus to).
//
// D-13: this is NOT client-side money math. The cue is advisory — it never
// parses for submission, computes, or persists. parse_optional_cents
// (app/services/catalog.py:106) stays the sole authority and the server
// re-renders the authoritative cue on every response. Parity with core.py:28
// to_cents is a one-liner: strip + comma→dot; space-separated thousands are
// rejected by both. Float math can flip the cue ONLY exactly at the equality
// boundary (12,505 → 1250 client vs 1251 server) — harmless for a hint, and
// the server re-render is the tiebreaker.
document.addEventListener("input", function (event) {
  const field = event.target;
  const ref = field.dataset ? field.dataset.refCents : null;
  if (!ref) return;                       // no reference → no cue (D-07: the MAIN path)
  const cents = Math.round(parseFloat(field.value.trim().replace(",", ".")) * 100);
  field.classList.remove("price-below", "price-above");
  if (!Number.isFinite(cents) || cents === Number(ref)) return;  // equal → neither (criterion 3)
  field.classList.add(cents < Number(ref) ? "price-below" : "price-above");
});
```

**What to copy structurally:**
- File-header comment block naming the requirement + decision ids, and stating the advisory-only contract with a pointer to the authoritative server function.
- One top-level `document.addEventListener("input", ...)` — no init function, no `DOMContentLoaded`, no per-element binding.
- Early-return guard first (`if (!ref) return;`), cheapest check before any parsing.
- `field.dataset ? ... : null` — defensive against non-element event targets.

**What to deliberately diverge from (and say so in the header comment):**
- `Math.round(parseFloat(...) * 100)` on line 19 is float math. `price-cue.js` earns it because it only *compares* and the server re-stamps `data-ref-cents` (`sale_row.html:41`). `sale-total.js` **displays a computed sum with no server-rendered fallback** → string→integer-cents only, per CLAUDE.md §What NOT to Use.

**The server parsers the JS must mirror** — `app/core.py:28-53`:
```python
def to_cents(value: str) -> int:
    """Parse a money string ('12,50', '12.50', '7') into integer cents.

    Accepts the Russian comma decimal separator. Raises ValueError on ANY
    invalid input, including non-finite values ('inf', 'nan') and huge
    exponents — callers may rely on catching ValueError alone (WR-02).

    Rounding policy (WR-03): ROUND_HALF_UP — ties round away from zero,
    the predictable retail behaviour ('12,505' -> 1251), NOT the Decimal
    default banker's rounding.
    """
    text = str(value).strip().replace(",", ".")
    try:
        amount = Decimal(text)
        if not amount.is_finite():
            raise InvalidOperation
        return int(amount.quantize(_CENTS, rounding=ROUND_HALF_UP) * 100)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc


def format_cents(cents: int) -> str:
    """Render integer cents as a display string with comma separator: 1250 -> '12,50'."""
    sign = "-" if cents < 0 else ""
    whole, frac = divmod(abs(cents), 100)
    return f"{sign}{whole},{frac:02d}"
```
> `format_cents` is the exact mirror target for the JS's `formatCents` (comma separator, 2 fraction digits, sign prefix). `_CENTS = Decimal("0.01")` at `core.py:12`, `ROUND_HALF_UP` imported at `core.py:9`.

**Script-tag pattern — `base.html:22-26`:**
```html
  <script src="/static/htmx.min.js" defer></script>
  {# PROD-06 / D-10: delegated price-cue listener — advisory only, never
     parses money for submission (D-13). Standalone file, mirrors the htmx
     vendored-script line above. #}
  <script src="/static/price-cue.js" defer></script>
```
**and `mobile_base.html:16-22`** — note the duplication rationale is already written down there:
```html
  <script src="/static/htmx.min.js" defer></script>
  {# PROD-06 / D-10: delegated price-cue listener — advisory only, never
     parses money for submission (D-13). mobile_base.html is standalone (does
     not inherit from base.html), so this tag must be duplicated here
     verbatim, same as the htmx line above. #}
  <script src="/static/price-cue.js" defer></script>
```

---

### `app/templates/partials/sale_form.html` (+`#sale-total`) (template partial, request-response)

**Analog for the total's shape:** `partials/finance_tiles.html:13` — `<p class="num">` used outside a table:
```jinja
    <p class="num"><strong>{{ metrics.gross_profit_cents | cents }}</strong></p>
```
and `finance_tiles.html:35-36`, the label-plus-figure variant closest to the live total:
```jinja
    <p class="num">По закупке: <strong>{{ valuation.cost_value_cents | cents }}</strong></p>
    <p class="num">По продаже: <strong>{{ valuation.sale_value_cents | cents }}</strong></p>
```
> `.num` is `style.css:225`; `.muted` is `style.css:230`. Both exist — no new CSS.
> `finance_tiles.html:7-8` also states the standing rule the total inherits: *"Money is NEVER sign-colored (UI-SPEC Q4): plain `| cents` in default text color."*

**Exact insertion point** (`sale_form.html:69-71`) — the total goes between `</table>` and the hint:
```jinja
      </tbody>
    </table>
    <p class="muted">Если товара с таким кодом ещё нет — сначала оприходуйте его.</p>
```

**Do not touch — the ids and guards this element sits between** (`sale_form.html:40-57`):
```jinja
  <form id="sale-form"
        hx-post="/sales"
        hx-target="#sale-form-wrap"
        hx-swap="outerHTML"
        hx-disabled-elt="find button"
        hx-on::before-swap="if (event.detail.target.id.startsWith('name') && event.detail.target.querySelector('input') && event.detail.target.querySelector('input').value.trim()) event.detail.shouldSwap = false"
        hx-on::oob-before-swap="if (event.detail.target.id.startsWith('price') && event.detail.target.querySelector('input') && event.detail.target.querySelector('input').value.trim()) event.detail.shouldSwap = false">
    <table class="basket">
      <thead>
        <tr>
          <th>Код</th>
          <th>Название</th>
          <th>Кол-во</th>
          <th>Цена продажи</th>
          <th></th>
        </tr>
      </thead>
      <tbody id="basket-rows">
```
> `#basket-rows` is the selector `sale-total.js` iterates (`document.querySelectorAll("#basket-rows tr")`). The two prefix-matching guards are why no new element may get an id starting with `name` or `price`. `sale_form.html:28-39` documents 18-REVIEW WR-02 as a deliberate accepted limitation — do not "tidy" it.

**The customer-header include contract** (`sale_form.html:10-14`):
```jinja
  {# SAL-03/D-05: customer header — search / quick-create / selected-chip.
     Lives OUTSIDE <form id="sale-form"> below (the basket form must not
     nest another form); its own hidden customer_id input associates via
     form="sale-form" so it still submits with the basket on finalize. #}
  {% include "partials/sale_customer.html" %}
```
> A bare `{% include %}` — it inherits `sale_form.html`'s whole context. So `_customer_context()`'s keys (`mode`, `selected`, `form`, `customer_id`) must be merged into every `sale_form.html` context dict, not nested under a sub-key.

---

### `app/templates/partials/sale_row.html` (+recompute hook) (template partial, event-driven)

**Analog:** the line being edited, `sale_row.html:46-49`:
```jinja
    {# Pitfall 2: deleting a line removes BOTH its input row AND its batch
       wrapper row, so the code[]/qty[]/price[]/batch_id[] arrays stay
       index-aligned no matter what order rows are added/removed in. #}
    <button type="button" class="secondary" hx-on:click="this.closest('tr').remove(); var w=document.getElementById('{{ batch_wrap_id }}'); if (w) w.remove()">Удалить строку</button>
```
Mobile twin, `mobile_partials/sale_basket.html:29-30`:
```jinja
    <button type="button" class="secondary"
            hx-on:click="this.closest('.mobile-card').remove()">Удалить</button>
```
> Both are plain DOM removals — no `input` event, no htmx event. Append `if (window.recalcSaleTotal) window.recalcSaleTotal()` to both, guarded so the button still works if the script hasn't loaded.

**Price input carrying the Phase-18 cue — must survive untouched** (`sale_row.html:40-42`):
```jinja
    <input type="text" name="price[]" inputmode="decimal" placeholder="0,00"
           {% if ref_pc_cents is not none %}data-ref-cents="{{ ref_pc_cents }}"{% endif %}
           value="{{ price or '' }}">
```
> `sale-total.js` reads `[name="price[]"]` on this same element. It must never touch `classList` here — that surface belongs to `price-cue.js`.

---

### `app/templates/partials/recent_sales.html` (+Покупатель column) (template partial, request-response)

**Analog:** the file itself (`recent_sales.html:11-36`):
```jinja
    <thead>
      <tr>
        <th>Когда</th>
        <th>Код</th>
        <th>Название</th>
        <th>Кол-во</th>
        <th>Цена</th>
        <th>Сумма</th>
        <th>Действие</th>
      </tr>
    </thead>
    <tbody>
      {% for r in sales %}
      <tr>
        <td>{{ r.op.created_at | local_dt }}</td>
        <td>{{ r.product.code }}</td>
        <td>{{ r.product.name }}</td>
        <td class="num">{{ -r.op.qty_delta }}</td>
        ...
```
**The muted-fallback idiom to copy** — `customer_picker.html:30`:
```jinja
        <td>{% if customer.surname %}{{ customer.surname }}{% else %}<span class="muted">—</span>{% endif %}</td>
```
> Same `{% if %}/<span class="muted">` structure; D-06 substitutes «Розница» for the em-dash. `surname or ''` guards the nullable surname (`sale_customer.html:18` precedent).

**The oob contract at the top of the file** (`recent_sales.html:1-6`) — unchanged by this phase but the reason `<th>`/`<td>` must land in one edit (three include sites: `pages/sale_form.html:8`, `partials/sale_form.html:84`, `partials/return_form.html:51`):
```jinja
{# Recent sales (mirrors D-04 recent_receipts): stable id so a POST-success
   response can refresh the list with hx-swap-oob. The heading lives IN the
   partial so the oob refresh carries it. Autoescape only — stored product
   names are untrusted (T-4-01). #}
<div id="recent-sales"{% if oob %} hx-swap-oob="true"{% endif %}>
```

---

### `app/templates/mobile_partials/sale_customer.html` (NEW) (template partial, request-response)

**Analog:** `mobile_partials/receipts_step_batch.html:30-51` — the shipped **mobile** fieldset/legend radio group using `.mobile-card` labels:
```jinja
<fieldset class="field">
  <legend>Партия</legend>
  {% if not code_entered %}
  <p class="muted">Введите код товара, чтобы увидеть его партии. Пока товар не выбран, приход создаст новую партию.</p>
  {% elif not batches %}
  ...
  {% endif %}
  {% for batch in batches %}
  <label class="mobile-card">
    <input type="radio" name="batch_choice" value="{{ batch.id }}">
    Пополнить партию: ...
  </label>
  {% endfor %}
  <label>
    <input type="radio" name="batch_choice" value="new"{% if not batches %} checked{% endif %}>
    Новая партия
  </label>
</fieldset>
```
> This is the exact mobile analog of `receipt_batch_chooser.html` and shows the `<label class="mobile-card">` idiom that supplies the 44px touch target (`style.css:329`). `.mobile-card.selected { background: #e8effd; }` is `style.css:334`.

**Wizard shell the selector must live inside** — `mobile_pages/sales.html`:
```jinja
{% block content %}
<h1>Продажа</h1>
<form id="sale-wizard-form">
  <div id="wizard-step">
    {% include "mobile_partials/sale_step_product.html" %}
  </div>
</form>
{% endblock %}
```
with its own header comment stating the swap contract:
```
   Продажа wizard shell (D-05): one persistent <form> wraps every step; the
   step-content region #wizard-step is the ONLY thing later step responses
   swap (hx-target="#wizard-step" hx-swap="innerHTML" everywhere, except the
   batch-pick card tap which self-replaces its own #batch-wrap root via
   outerHTML — RESEARCH.md Pattern 1).
```
> The batch-pick card tap is the *documented precedent* for a self-replacing `outerHTML` root inside `#wizard-step` — which is exactly what `#m-customer-header` must do. Follow it; do not target `#wizard-step`.

**Mobile basket insertion points** (`sale_basket.html:5-7` and `:36-45`):
```jinja
<div id="wizard-basket">
  <p class="mobile-step-indicator">Корзина</p>
  <h2>Корзина</h2>
  ...
  <div class="mobile-actions">
    <button type="button" class="secondary"
            hx-post="/m/sales/step/product"
            hx-target="#wizard-step" hx-swap="innerHTML">Добавить товар</button>
    {% if lines %}
    <button type="button"
            hx-post="/m/sales"
            hx-target="#wizard-step" hx-swap="innerHTML">Оформить продажу</button>
    {% endif %}
  </div>
```
> Selector goes after `<h2>Корзина</h2>`, above the card loop. The total goes after the loop, before `.mobile-actions`. «Оформить продажу» is `hx-post` (non-GET) → htmx auto-includes `#sale-wizard-form`, which is how `code_acc[]` (`sale_basket.html:14-17`) already reaches the server; `customer_id` rides it free.

---

### `app/templates/mobile_partials/batch_card_picker.html` (D-11) (shared partial, request-response)

**The defect line** (`batch_card_picker.html:46-54`):
```jinja
<button type="button"
        class="mobile-card{% if b.id == selected_batch_id %} selected{% endif %}"
        hx-get="{{ pick_url }}"
        {# WR-02: tojson (not manual string concatenation) correctly escapes
           a double quote inside code/row_id for both JSON and this HTML
           attribute — manual concatenation broke on a quote character. #}
        hx-vals="{{ ({'batch_id': b.id, 'code': code | default(''), 'row': row_id} if row_id else {'batch_id': b.id, 'code': code | default('')}) | tojson }}"
        hx-target="{{ batch_target }}"
        hx-swap="outerHTML">
```

**The `hx-include` idiom to copy** — `writeoff_step_batch.html:19-23`:
```jinja
<div class="mobile-actions">
  <button type="button" class="secondary" hx-get="/m/writeoff" hx-include="closest form">Назад</button>
  {% if not show_empty %}
  <button type="submit" hx-post="/m/writeoff/step/qty" hx-include="closest form">Далее</button>
  {% endif %}
</div>
```
and `corrections_step_batch.html:24-25`:
```jinja
      <button type="button" class="secondary" hx-get="/m/corrections" hx-include="closest form"
              hx-target="#corrections-step-wrap" hx-swap="outerHTML">Назад</button>
```

**Parameterisation precedent already in this file** (`batch_card_picker.html:41-42`) — the `| default(...)` shape to use if the fix ever needs to be opt-in per consumer:
```jinja
{% set batch_input_name = batch_input_name | default("batch_id") %}
{% set batch_target = batch_target | default("#batch-wrap") %}
```

> ⚠️ **CORRECTION FOR THE PLANNER — RESEARCH.md and UI-SPEC.md both misread this.** Both state *"Every sibling wizard already passes `hx-include="closest form"` (`writeoff_step_batch.html:20`, `receipts_step_batch.html:53`, `corrections_step_batch.html:24`); the sale wizard is the outlier."* Those cited lines are the wizards' **«Назад»/«Далее» buttons**, not their batch cards. `batch_card_picker.html` is a **shared** partial (`writeoff_step_batch.html:17` and `corrections_step_batch.html:21` both `{% include %}` it), so **the card tap is missing `hx-include` uniformly across all four wizards** — the sale wizard is not an outlier. Consequences for planning: (a) the one-attribute fix changes behavior for Sale/Write-off/Correction/Transfer simultaneously, so D-11's mandated full `test_mobile_*` regression pass is not optional; (b) the fix will start sending each wizard's own hidden `code`/`name` inputs (`writeoff_step_batch.html:14-15`) to its `pick_url` endpoint — verify each step endpoint declares or tolerates those `Query` params before assuming a no-op.

---

### `tests/test_sales_total.py` (NEW) + extensions (test)

**Analog:** `tests/test_sales.py` — the existing web-level suite. Fixtures (`client`, `session`, `customer`, `stocked_product`, `mobile_client_factory`) live in `tests/conftest.py`; the `customer` fixture already seeds «Анна Иванова» / consultant `12345` with `search_lc` set.

**Criterion-5 tripwire tests that must stay green untouched** (`tests/test_sales.py`):
- `test_web_sale_oversell_shows_warning_and_confirm_writes` (:615)
- `test_web_sale_below_minimum_shows_warning_and_confirm_writes` (:648)
- `test_web_sale_both_warnings_stack_and_single_confirm_resolves_both` (:684)
- `test_web_sale_missing_batch_pick_returns_422` (:1081)
- `test_web_sale_422_re_echoes_picked_batch` (:1041)

Existing tests to extend rather than duplicate: `test_web_sale_page_renders_form` (:570), `test_web_customer_search_returns_rows` (:749), `test_web_customer_quick_create_returns_chip` (:756), `test_customer_link_walkin_customer_id_null` (:255).

> Every command must be prefixed `uv run` — bare `python -m pytest` fails (deps live in the uv-managed `.venv`).

---

## Shared Patterns

### 1. Untrusted stored text: `.dataset` in, `.textContent` out
**Source:** `app/templates/partials/customer_picker.html:1-12` (contract) + `:21-28` (implementation)
**Apply to:** `sale_customer.html`, `mobile_partials/sale_customer.html`, `mobile_partials/customer_picker.html`, `recent_sales.html`, `sale-total.js`
```jinja
{# Picking a row is a pure client-side swap (T-4-05 — the row already
   carries the customer's id/name/surname as data-* attributes, which Jinja
   autoescape HTML-attribute-encodes; the handler reads them via .dataset
   and writes via .textContent, never building HTML/JS strings from
   untrusted text). #}
          <button type="button" class="secondary"
                  data-id="{{ customer.id }}" data-name="{{ customer.name }}" data-surname="{{ customer.surname or '' }}"
                  hx-on:click="document.getElementById('customer-id-input').value = this.dataset.id;
                    document.getElementById('customer-chip-text').textContent = 'Покупатель: ' + this.dataset.name + (this.dataset.surname ? (' ' + this.dataset.surname) : '');
                    document.getElementById('customer-selected').hidden = false;
                    document.getElementById('customer-default').hidden = true;">
            {% set pre, match, post = row.name_seg %}{{ pre }}{% if match %}<mark>{{ match }}</mark>{% endif %}{{ post }}
          </button>
```
> `<mark>` is literal template HTML around an autoescaped segment — never `|safe`. **There is no legitimate `| safe` in this phase.** The four hard-coded ids here are exactly why the mobile picker needs its own partial.

### 2. Route error handling: never a raw 500
**Source:** `app/routes/sales.py:354-373`, `app/routes/mobile_sales.py:353-359`
**Apply to:** `GET /sales/customer-mode`, the D-10 guard branch, any new mobile route
```python
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        logger.exception("<service_call> failed")
        context = {...}
        return templates.TemplateResponse(request, "<partial>.html", context, status_code=422)
```
> Mobile adds `session.rollback()` **first** (WR-01) when a query follows in the same branch.

### 3. Allow-list an untrusted client value before use
**Source:** `app/services/customers.py:262` `_SORT_MAP` (the proportionate guard) vs `app/routes/sales.py:36-40` `_ROW_ID_RE` (the heavier guard for JS-attribute echo)
**Apply to:** `_CUSTOMER_MODES = ("new", "existing", "anon")` in `routes/sales.py`
> Compare, never interpolate into an attribute. Membership-check with a default on miss.

### 4. Money: integer cents, one parser, one formatter
**Source:** `app/core.py:1-5` (module docstring), `:28` `to_cents`, `:49` `format_cents`; Jinja `cents` filter at `app/routes/__init__.py:18`
**Apply to:** everything in this phase that touches money
```python
"""Convention helpers (D-05/D-06/D-07): UUID4 ids, UTC ISO timestamps, integer cents.

These are the ONLY sanctioned conversion points for ids, money and time.
Never use float for money (Pitfall 3) and never store naive datetimes.
"""
```
> Server-side: `| cents` filter for render, `to_cents` for parse — never `f"{cents/100:.2f}"`. Client-side: `sale-total.js` mirrors `format_cents` and `to_cents`'s ROUND_HALF_UP tie rule with string→int math, no floats.

### 5. Manual FK joins in the service layer — zero `relationship()`
**Source:** house rule stated at `app/models.py:381-383`; enforced by `export.py:117-125`
**Apply to:** `recent_sales`'s new join
> Portable SQLAlchemy Core/ORM constructs only. One query, no N+1.

### 6. htmx GET does not include the enclosing form
**Source:** `writeoff_step_batch.html:20`, `corrections_step_batch.html:24`, `receipts_step_batch.html:53` — `hx-include="closest form"` on every non-POST wizard control
**Apply to:** the desktop mode radio (`hx-include="#customer-header"`), the mobile mode radio, `batch_card_picker.html`'s card tap
> Standing rule this phase establishes: **every non-POST htmx control that needs sibling state carries an explicit `hx-include`.** Warning sign: any `hx-get`/`hx-delete` inside `#sale-wizard-form` or `#customer-header` without one.

### 7. Standalone shell duplication for `<script>` tags
**Source:** `base.html:22-26`, `mobile_base.html:16-22`
**Apply to:** the `sale-total.js` tag
> `mobile_base.html` does not inherit from `base.html`. The tag must be duplicated verbatim, and the duplication rationale is already written as a comment at `mobile_base.html:17-21` — copy that comment shape for the new tag.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/templates/mobile_partials/customer_picker.html` | template partial | request-response | **No mobile search-picker exists in any wizard.** Every mobile pick surface in `mobile_partials/` is a *batch card list* driven by a server-rendered list, not a debounced search field. The closest structural pieces are `partials/customer_picker.html` (desktop, but hard-codes 4 desktop ids) for the `.dataset`/`.textContent` handler + `<mark>` highlighting, and `mobile_partials/receipts_step_batch.html:30-51` + `batch_card_picker.html:46-64` for the `.mobile-card` list shape. **Compose from both; the planner should not expect a single analog.** The search *backend* needs no analog — `customers.py:246 customer_search_view` already returns `q` + rows of `{customer, name_seg, consultant_seg}`, the exact context both pickers consume. |

Also worth flagging as *thin*: `mobile_partials/sale_customer.html`'s **hidden-echo** mechanism (D-03) has no mobile precedent at all. The nearest thing is the `*_acc[]` carry-forward in `sale_basket.html:14-17` / `sale_step_product.html:13-16`, which is a different pattern (per-line accumulator arrays, not per-mode scalar echo). RESEARCH's Pattern 3 avoids needing it by placing the selector on the Корзина screen — that placement is load-bearing, not cosmetic.

---

## Metadata

**Analog search scope:** `app/routes/`, `app/services/`, `app/static/`, `app/templates/{pages,partials,mobile_pages,mobile_partials}/`, `app/core.py`, `app/models.py`, `tests/`
**Files read this session:** 22
**Pattern extraction date:** 2026-07-17
