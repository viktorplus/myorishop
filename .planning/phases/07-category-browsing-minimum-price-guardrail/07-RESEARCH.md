# Phase 7: Category Browsing & Minimum Price Guardrail - Research

**Researched:** 2026-07-10
**Domain:** Server-rendered FastAPI/Jinja2/HTMX CRUD extension (read-only grouped listing page + warn-but-allow sale-time price guardrail) on an existing, mature codebase
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Category Browsing Page (CAT-01)**
- **D-01:** New top-level nav entry with its own dedicated route: `/categories`. Deliberately NOT merged into `/reports/stock` (that page's job is low-stock alerting) and NOT nested under `/products` — a separate nav item avoids ambiguity with the existing "Остатки склада" report at `/reports/stock`.
- **D-02:** Row columns, per product: Код, Название, Остаток (quantity), Закупочная (cost), Продажа (sale), Каталог (catalog price), Действия (edit link to `/products/{id}/edit`). No separate "Категория" column — redundant once rows are grouped under a category heading.
- **D-03:** Category groups sorted alphabetically — reuse the same ordering already used for the category `<datalist>` (`catalog.category_options()` style, `.order_by(Product.category)`).
- **D-04:** Products with `Product.category IS NULL` (or empty) go into a visible "Без категории" bucket, sorted last (after all named categories) — NOT hidden.
- **D-05:** Only active products (`Product.deleted_at IS NULL`), same convention as `/products` and all other catalog views.

**Minimum Price Guardrail (PRICE-01)**
- **D-06:** New nullable `Integer` column on `Product` for the minimum sale price, stored in cents (suggest `min_sale_cents`, exact name is planner/executor's call). **No global-settings fallback** — NULL means "no floor is set," full stop. Must be checked with `is not None`, never a bare `or`.
- **D-07:** Field placed on `product_form.html` immediately **after** "Цена продажи" (`sale`), **before** "Цена по каталогу" (`catalog`). Label: "Минимальная цена продажи" with a muted "(необязательно)" hint — deliberately WITHOUT a "(по умолчанию: N)" hint. Reuses `to_cents()` parsing / `inputmode="decimal"` / `placeholder="0,00"`.
- **D-08:** Guardrail applies only at **Sale** time. Write-offs and stock corrections have no price field, so out of scope.
- **D-09:** Check is **per-line** (not aggregated like oversell quantity sum). Compare each line's entered sale price against that line's `product.min_sale_cents`, guarded by `is not None`.
- **D-10:** Boundary is **strict less-than**: `line_price_cents < product.min_sale_cents` triggers the warning; equal-to-minimum passes silently. Mirrors oversell boundary (`requested > quantity`).
- **D-11:** Warning presentation: **one combined block**, not per-line inline, not a separate confirm step. New partial mirroring `sale_oversell.html` (same `.error-block`/`button.danger` styling, same "Продать всё равно" wording), listing every line below its product's minimum. Shares the **same `confirm=1` flag** already used for oversell in `register_sale`. If both oversell AND price floor trip, operator sees both blocks stacked, resolves both with one click. Zero writes until `confirm=1` on resubmit.

### Claude's Discretion
- Exact column/field name for the new minimum-price column (suggested `min_sale_cents`).
- Exact route module placement (new `app/routes/categories.py` vs. adding to `app/routes/products.py`).
- Exact partial filename for the new price-warning block (suggested `sale_price_warning.html`).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. No scope-creep items were raised.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAT-01 | "Товары на складе" page groups products by category/rubric | Verified query pattern in `app/services/catalog.py::category_options()`, verified read-only page pattern in `app/templates/pages/reports_stock.html` + `app/routes/reports.py`, verified nav pattern in `app/templates/base.html`. See Architecture Patterns. |
| PRICE-01 | Optional minimum sale price per product — selling below it shows a warning but allows override (same pattern as existing oversell warning) | Verified oversell warn-but-allow contract end-to-end in `app/services/sales.py::register_sale`, `app/routes/sales.py::sale_create`, `app/templates/partials/sale_oversell.html`, `app/templates/partials/sale_form.html`, and test pattern in `tests/test_sales.py`. See Code Examples. |
</phase_requirements>

## Summary

This phase is a pure additive extension of an already-mature, internally consistent codebase — no new external dependencies, no new architectural layers, no new UI framework decisions. Both capabilities have a near-exact existing precedent already shipped in the same repo: CAT-01's grouped read-only listing mirrors `reports_stock.html`'s "as-of-now, no-HTMX, full-page-GET" report pattern, and PRICE-01's warn-but-allow guardrail mirrors the oversell check in `register_sale` line-for-line (same `confirm` flag, same zero-writes-until-confirmed contract, same `.error-block`/`button.danger` styling already defined in `style.css`).

The codebase enforces several hard conventions that this phase MUST follow without exception: money is `Integer` cents everywhere (never float), nullable-override fields are checked with `is not None` never a bare `or` (Pitfall 3, already documented in `app/services/stock.py`), soft delete is `deleted_at IS NULL` filtering applied uniformly, Cyrillic text is folded in Python not SQL (`name_lc` shadow columns, not relevant to this phase's fields since category/price aren't searched), and every schema change ships as a plain, forward-only Alembic migration (`0001`...`0005` exist; this phase adds `0006`). The existing `to_cents()`/`parse_optional_cents()` helpers in `app/core.py`/`app/services/catalog.py` already handle exactly the parsing/validation this phase's new `min_sale_cents` field needs — no new parsing logic should be written.

**Primary recommendation:** Add `min_sale_cents` as a nullable `Integer` column via Alembic migration `0006` (plain `op.add_column`, no batch mode — mirrors `0005`), reuse `parse_optional_cents` (not `parse_optional_int`) for its form parsing since it is money not a plain threshold, extend `register_sale`'s existing pre-write validation block with a parallel per-line minimum-price pass using the identical `confirm != "1"` gate, and add `/categories` as a new thin route (recommend a new `app/routes/categories.py` + a new `catalog.py` query function) rendering a plain full-page GET with no HTMX partial machinery, exactly like `/reports/stock`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Category-grouped product listing (CAT-01) | Backend (FastAPI route + service query) | Frontend Server (SSR, Jinja2 template) | Pure read query over `products` table, grouped/sorted in the DB query or Python, rendered server-side with no client-side filtering (no search/filter this phase per UI-SPEC) |
| Minimum-price schema field (PRICE-01, storage) | Database / Storage | Backend (SQLAlchemy model + Alembic migration) | Nullable column on `Product`, no computed/derived state |
| Minimum-price form input (PRICE-01, capture) | Frontend Server (SSR form) | Backend (validation via `parse_optional_cents`) | Same trio pattern as `cost`/`sale`/`catalog` — server-side parse/validate, no client-side JS validation |
| Minimum-price sale-time guardrail (PRICE-01, enforcement) | Backend (`register_sale` service) | Frontend Server (warning partial render) | Business-rule enforcement (warn-but-allow) MUST happen server-side before any DB write — mirrors the existing oversell check; the template only renders the pre-computed warning list, it does not decide it |

## Standard Stack

### Core
No new libraries are introduced by this phase. It is implemented entirely with the stack already installed and pinned in `pyproject.toml` (verified 2026-07-10):

| Library | Version (installed) | Purpose in this phase | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.139.* [VERIFIED: pyproject.toml] | New `/categories` GET route; extends `/products` POST validation | Already the project's only web framework |
| SQLAlchemy 2.0 | 2.0.* [VERIFIED: pyproject.toml] | New `min_sale_cents` `Mapped[int \| None]` column; grouped `select()` query for categories | Already the project's only ORM; 2.0 declarative style is locked project convention |
| Alembic | 1.18.* [VERIFIED: pyproject.toml] | New migration `0006` adding the column | Already the project's only migration tool; `alembic/versions/0001`-`0005` establish the exact pattern to mirror |
| Jinja2 | 3.1.* [VERIFIED: pyproject.toml] | New `pages/categories.html`, new `partials/sale_price_warning.html`, edits to `product_form.html`/`sale_form.html` | Already the project's only templating engine |
| htmx | 2.0.10 vendored [VERIFIED: app/static/htmx.min.js referenced in base.html] | NOT used for `/categories` (plain full-page GET per UI-SPEC/D-01 precedent); reused unchanged for the price-warning confirm/dismiss buttons (identical `hx-vals`/`hx-on:click` pattern already in `sale_oversell.html`) | Already vendored; UI-SPEC explicitly forbids new HTMX machinery where a static page load suffices |

### Supporting
No new supporting libraries. `pytest`/`httpx` (already dev dependencies) cover this phase's tests exactly as they cover every prior phase's tests (`tests/test_catalog.py`, `tests/test_sales.py` are the direct precedents to extend).

### Alternatives Considered
Not applicable — CLAUDE.md and PROJECT.md already closed the stack-choice question for the whole project; this phase does not introduce any decision point where an alternative library/approach would be considered (e.g., no charting library needed for a plain grouped table, no client-side validation library needed since `to_cents()` already exists server-side).

**Installation:**
No new packages to install. This phase only runs `alembic upgrade head` after adding migration `0006` to the existing `alembic/versions/` directory.

**Version verification:** Skipped — no new packages recommended. Existing pinned versions confirmed via `pyproject.toml` (read 2026-07-10): `fastapi==0.139.*`, `sqlalchemy==2.0.*`, `alembic==1.18.*`, `jinja2==3.1.*`.

## Package Legitimacy Audit

**Not applicable this phase.** No new external packages are installed — the phase is implemented entirely with dependencies already present in `pyproject.toml`. No `npm view`/`pip index versions` verification is needed; no legitimacy check was run because no new package names are introduced.

## Architecture Patterns

### System Architecture Diagram

```
CAT-01 (read path):
  Browser GET /categories
        │
        ▼
  app/routes/categories.py  (new thin route)
        │  calls
        ▼
  app/services/catalog.py :: products_by_category(session)  (new query fn)
        │  SELECT Product WHERE deleted_at IS NULL
        │  ORDER BY category (NULLs/'' last), name
        ▼
  Python groups rows by category key (SQL GROUP BY not needed —
  simple ORDER BY + Python itertools.groupby or dict-accumulate,
  since row count is small and grouping logic is presentation-only)
        │
        ▼
  pages/categories.html  (Jinja2, extends base.html)
        │  h1 + repeated h2/table per group, "Без категории" forced last
        ▼
  Browser renders full page (no HTMX partial swap)


PRICE-01 (write path, extends existing oversell flow):
  Browser POST /sales  (code[]/qty[]/price[]/confirm)
        │
        ▼
  app/routes/sales.py :: sale_create
        │  calls
        ▼
  app/services/sales.py :: register_sale
        │
        ├─ per-line validation (qty/price/code) — UNCHANGED
        │
        ├─ if confirm != "1":
        │     ├─ existing: aggregate oversell check (SUM qty per product)
        │     └─ NEW: per-line price-floor check
        │           for each resolved line:
        │             if product.min_sale_cents is not None
        │                and line.price_cents < product.min_sale_cents:
        │                  add to below_minimum[]
        │     if oversold or below_minimum: return early, ZERO writes
        │
        └─ if confirm == "1": skip BOTH checks, write ops, commit
        │
        ▼
  partials/sale_form.html
        │  {% if oversell %} sale_oversell.html {% endif %}
        │  {% if below_minimum %} sale_price_warning.html {% endif %}   <- NEW
        ▼
  Browser renders warning block(s) above the still-intact basket form;
  "Продать всё равно" re-POSTs the SAME basket with confirm=1
```

### Recommended Project Structure
```
app/
├── models.py                          # add Product.min_sale_cents (nullable Integer)
├── routes/
│   ├── categories.py                  # NEW — GET /categories (thin route)
│   └── sales.py                       # UNCHANGED — register_sale already returns
│                                       #   a dict the route re-renders; add the new
│                                       #   below_minimum key to the existing branches
├── services/
│   ├── catalog.py                     # add products_by_category(); add
│                                       #   min_sale_cents to parse_optional_cents
│                                       #   calls in create_product/update_product
│   └── sales.py                       # extend register_sale's pre-write block
├── templates/
│   ├── base.html                      # add one nav <a> for /categories
│   ├── pages/
│   │   ├── categories.html            # NEW
│   │   └── product_form.html          # insert one new .field block
│   └── partials/
│       ├── sale_price_warning.html    # NEW, mirrors sale_oversell.html
│       ├── sale_form.html             # include the new partial
│       └── price_history.html         # if min_sale_cents joins _PRICE_FIELDS
│                                       #   (see Open Questions), add one elif
alembic/versions/
└── 0006_product_min_sale_price.py     # NEW — mirrors 0005's plain op.add_column
```

### Pattern 1: Read-only grouped report page (no HTMX)
**What:** A full-page GET that queries active products, groups them, and renders a static page — no partial-swap machinery.
**When to use:** Any browsing/reporting page with no search/filter/interaction this phase (CAT-01 explicitly has none).
**Example (verified precedent, `app/routes/reports.py` lines 153-165):**
```python
# Source: app/routes/reports.py (verified in this codebase, 2026-07-10)
@router.get("/reports/stock")
def reports_stock_page(request: Request, session: Session = Depends(get_session)):
    """RPT-02/D-03: "as of now" stock view — no period filter, always the full page."""
    low_stock_rows = [...]
    context = {"low_stock_rows": low_stock_rows, "all_products": all_active_products(session)}
    return templates.TemplateResponse(request, "pages/reports_stock.html", context)
```
The `/categories` route should follow this exact shape: no `HX-Request` header branching (unlike `reports_sales.py`/`reports_products.py`, which DO branch because they have a period filter — `/categories` has none per UI-SPEC).

### Pattern 2: Warn-but-allow guardrail (the PRICE-01 core pattern)
**What:** A read-only check runs after per-line field validation but before any DB write; a `confirm` flag bypasses it; the response is zero-write and the basket form stays intact until confirmed.
**When to use:** PRICE-01's minimum-price check — this is a direct extension of the existing oversell check, not a new pattern.
**Example (verified precedent, `app/services/sales.py` lines 129-148):**
```python
# Source: app/services/sales.py (verified in this codebase, 2026-07-10)
if confirm != "1":
    requested_by_product: dict[str, int] = {}
    products_by_id: dict[str, Product] = {}
    for line in resolved:
        product = line["product"]
        requested_by_product[product.id] = requested_by_product.get(product.id, 0) + line["qty"]
        products_by_id[product.id] = product

    oversold = [
        {"product": products_by_id[pid], "available": products_by_id[pid].quantity, "requested": req}
        for pid, req in requested_by_product.items()
        if req > products_by_id[pid].quantity
    ]
    if oversold:
        oversold.sort(key=lambda entry: entry["product"].name)
        return {"oversell": oversold}, {}
```
The new price-floor check is simpler (no aggregation needed — D-09 says it's per-LINE not per-product-sum) and should be added as a sibling block in the same `if confirm != "1":` guard, e.g.:
```python
# NEW block, added inside the same "if confirm != \"1\":" guard, AFTER the
# oversold check (established-pattern-first convention per UI-SPEC):
below_minimum = [
    {"product": line["product"], "entered": line["price_cents"], "minimum": line["product"].min_sale_cents}
    for line in resolved
    if line["product"].min_sale_cents is not None
    and line["price_cents"] < line["product"].min_sale_cents
]
if oversold or below_minimum:
    result = {}
    if oversold:
        result["oversell"] = oversold
    if below_minimum:
        result["below_minimum"] = below_minimum
    return result, {}
```
Both checks must be evaluated BEFORE returning (not short-circuited) so a single submission that trips both shows both blocks stacked in one round trip (CONTEXT D-11 requirement, UI-SPEC "Manual UAT gate: a submission that trips BOTH ... shows both blocks stacked").

### Pattern 3: Nullable-override field, `is not None` discipline
**What:** An optional per-product `Integer` column with NO global-settings fallback, checked with `is not None` never a bare `or`, so an explicit `0` stays meaningful.
**When to use:** `min_sale_cents` (D-06) — differs from `low_stock_threshold`/`stale_days` (which DO fall back to `settings.*`) in that there is no fallback at all; NULL simply means "skip the check."
**Example (verified precedent showing the discipline, `app/services/stock.py` lines 19-25 — note this phase's field has NO fallback, unlike this example, but the `is not None` guard style is identical):**
```python
# Source: app/services/stock.py (verified in this codebase, 2026-07-10)
def effective_low_stock_threshold(product: Product) -> int:
    """Product's own threshold if set (even 0), else the global default."""
    return (
        product.low_stock_threshold
        if product.low_stock_threshold is not None
        else settings.low_stock_threshold
    )
```
For `min_sale_cents`, the analogous check has no `else` branch — it's a straight guard clause: `if product.min_sale_cents is not None and price_cents < product.min_sale_cents: ...`.

### Anti-Patterns to Avoid
- **Bare `or` on `min_sale_cents`:** `product.min_sale_cents or 0` silently treats an explicit `0` minimum as "unset" — this is Pitfall 3, already documented and explicitly guarded against elsewhere in this codebase (`stock.py` docstring), and CONTEXT.md success criterion 4 depends on avoiding it here too.
- **Writing a new money parser for `min_sale_cents`:** `to_cents()`/`parse_optional_cents()` already exist and are used by `cost`/`sale`/`catalog` — reuse them verbatim; do not hand-roll a fourth copy of the same parsing logic.
- **Adding HTMX search/filter to `/categories`:** UI-SPEC explicitly scopes this page to a static full-page GET with no interaction this phase — do not add search/filter machinery "for consistency" with `/products`; that is out of scope (CAT-01 has no filter requirement).
- **Aggregating the price-floor check like the oversell check:** D-09 is explicit that this check is per-LINE, not summed across duplicate-product lines. Do not copy the oversell aggregation loop verbatim — that would produce wrong results (e.g., averaging or summing prices makes no sense per-line).
- **Hiding uncategorized products:** A `WHERE category IS NOT NULL` filter on the categories query would silently violate success criterion 1 (D-04 requires a visible "Без категории" bucket, sorted last, never hidden).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parsing/validating a money string into cents | A new regex/float parser for `min_sale_cents` | `app/core.py::to_cents()` via `app/services/catalog.py::parse_optional_cents()` | Already handles comma/dot decimal, `ROUND_HALF_UP`, negative rejection, RU error message — exactly the same shape as `cost`/`sale`/`catalog` |
| Grouping/sorting categories with "no category" last | Custom SQL `CASE WHEN category IS NULL THEN 1 ELSE 0 END, category` ORDER BY, or a raw SQL query | Reuse the query shape from `catalog.category_options()` (`.order_by(Product.category)`) for the distinct-category list, then a plain Python `sorted()`/`groupby` with an explicit "" → "Без категории" sentinel appended last | Keeps the query portable ORM-only (project convention: "no SQLite-specific SQL", CLAUDE.md), and Python-side sorting avoids NULL-ordering differences between SQLite and the future PostgreSQL target |
| Confirm/warn UI interaction | A new modal library, a new JS confirm() dialog, a second confirm parameter | The existing `confirm=1` form re-POST pattern (`hx-vals='{"confirm": "1"}'`, `form="sale-form"`) already proven in `sale_oversell.html` | Zero new JS, zero new server-side flag — CONTEXT D-11 explicitly requires reusing the SAME flag, not inventing a second one |
| Schema migration for a new nullable column | Autogenerate + hand-editing, or a batch-mode `ALTER TABLE` | Plain `op.add_column("products", sa.Column("min_sale_cents", sa.Integer(), nullable=True))`, mirroring `alembic/versions/0005_product_thresholds.py` exactly | SQLite natively supports `ADD COLUMN` for a simple nullable column with no default — no batch mode needed, matching the precedent set by `0005` for the same table |

**Key insight:** Every problem this phase touches already has a shipped, tested precedent in this exact codebase from Phases 1-6. There is no domain research to do outside the repo itself — the risk in this phase is drifting from established conventions, not missing external knowledge.

## Common Pitfalls

### Pitfall 1: Bare `or` swallowing an explicit `0`
**What goes wrong:** `product.min_sale_cents or 0` (or any bare-`or` fallback) evaluates falsy for `0`, so a product with an explicit `0,00` minimum silently behaves as if unset.
**Why it happens:** Python's `or` treats `0` as falsy, a classic footgun already named "Pitfall 3" elsewhere in this codebase.
**How to avoid:** Always write `product.min_sale_cents is not None` as the guard, never `product.min_sale_cents or ...`. Success criterion 4 explicitly tests this.
**Warning signs:** Any code path where a `0` minimum-price product behaves identically to a NULL minimum-price product.

### Pitfall 2: Short-circuiting on the first failed check
**What goes wrong:** If the oversell check `return`s early when it finds a problem, the price-floor check never runs in the same request — a basket that trips BOTH conditions only shows the oversell warning on the first submit, then (after the operator clicks "Продать всё равно" and it resubmits with `confirm=1`) skips straight to a write, never surfacing the price-floor warning at all.
**Why it happens:** Naively converting the existing `if oversold: return {"oversell": oversold}, {}` into a second identical `if below_minimum: return ...` block executed sequentially, rather than collecting both results before returning.
**How to avoid:** Compute BOTH `oversold` and `below_minimum` first, then return a single result dict containing whichever keys are non-empty (see Pattern 2 code example above). CONTEXT D-11 and UI-SPEC's manual UAT gate both require this.
**Warning signs:** A test where a basket line simultaneously oversells AND is below its minimum price shows only one warning block, not two.

### Pitfall 3: Forgetting the migration is additive-only, no data backfill needed
**What goes wrong:** Attempting to backfill `min_sale_cents` for existing products (e.g., copying `sale_cents` into it) — this is out of scope and NOT requested; every existing product must have `min_sale_cents = NULL` after migration (no floor set), matching CONTEXT D-06 ("No global-settings fallback ... NULL here means 'no floor is set'").
**Why it happens:** Confusing this feature with `low_stock_threshold`/`stale_days` (Phase 6), which also added nullable columns but those DO have a settings fallback — pattern-matching too closely to that precedent could tempt a fallback-style backfill that doesn't apply here.
**How to avoid:** The migration adds the column with no `server_default`, no backfill UPDATE statement — exactly like `0005`. Existing products get NULL automatically.
**Warning signs:** A migration file containing an `UPDATE products SET min_sale_cents = ...` statement.

### Pitfall 4: `price_history.html`'s hardcoded field-name elif chain
**What goes wrong:** If the planner decides `min_sale_cents` should join `_PRICE_FIELDS` (so edits are audited as `price_change` ops, consistent with it being a price), the existing `price_history.html` partial has a hardcoded `{%- if op.payload.field == "cost_cents" -%}...{%- elif ... == "sale_cents" -%}...{%- elif ... == "catalog_cents" -%}...{%- else -%}{{ op.payload.field }}{%- endif -%}` chain (verified, `app/templates/partials/price_history.html` lines 20-24). Without a new `elif` branch, a `min_sale_cents` change would render the raw field name `min_sale_cents` instead of a Russian label.
**Why it happens:** The elif chain was written before this field existed and has no fallback-to-labeled-string mechanism.
**How to avoid:** See Open Questions below — this is a decision the planner must make explicitly (add to `_PRICE_FIELDS` + one new `elif "min_sale_cents"` branch, OR treat it like `low_stock_threshold`/`stale_days` via `product_edited` with no per-change price display). Either is technically valid; only the audit-trail granularity differs.
**Warning signs:** Price history table showing a raw `min_sale_cents` string instead of "Минимальная" (or whatever label is chosen) after an edit.

## Code Examples

### Warn-but-allow price-floor check (extends verified `register_sale`)
```python
# Source: pattern extension of app/services/sales.py::register_sale
# (verified in this codebase, 2026-07-10). Insert AFTER the existing
# oversold computation, inside the same "if confirm != \"1\":" block,
# BEFORE the early return, so both checks are evaluated together.
below_minimum = [
    {
        "product": line["product"],
        "entered": line["price_cents"],
        "minimum": line["product"].min_sale_cents,
    }
    for line in resolved
    if line["product"].min_sale_cents is not None
    and line["price_cents"] < line["product"].min_sale_cents
]

if oversold or below_minimum:
    result: dict = {}
    if oversold:
        oversold.sort(key=lambda entry: entry["product"].name)
        result["oversell"] = oversold
    if below_minimum:
        below_minimum.sort(key=lambda entry: entry["product"].name)
        result["below_minimum"] = below_minimum
    return result, {}
```

### Category grouping query (new function for `app/services/catalog.py`)
```python
# Pattern derived from the VERIFIED category_options() query
# (app/services/catalog.py lines 393-406) and all_active_products()
# (app/services/stock.py lines 38-44), both read in this codebase 2026-07-10.
from itertools import groupby

def products_by_category(session: Session) -> list[dict]:
    """Active products grouped by category, alphabetical, 'Без категории' last (D-03/D-04)."""
    products = list(
        session.scalars(
            select(Product)
            .where(Product.deleted_at.is_(None))
            .order_by(Product.category.is_(None), Product.category == "", Product.category, Product.name_lc)
        )
    )
    groups: list[dict] = []
    for category, items in groupby(products, key=lambda p: p.category or None):
        groups.append({"label": category or "Без категории", "products": list(items)})
    # groupby already yields NULL/'' group last due to the ORDER BY above,
    # since Product.category.is_(None) and == "" both sort True(1) after
    # named categories (False/0) in ascending order — verify with a test
    # covering a product with category="" alongside named categories.
    return groups
```
**Note:** the `ORDER BY` trick above (`Product.category.is_(None), Product.category == ""`) needs empirical verification against SQLite's boolean-as-integer ordering (0/1) before relying on it — a simpler and more obviously correct alternative is to fetch all active products ordered by `name_lc`, group them by category in **Python** with `sorted(categories, key=lambda c: (c == "", c or ""))`, and append the "Без категории" bucket explicitly rather than relying on SQL ordering of NULL/empty. The planner should choose whichever is proven correct by test, not assume the SQL trick works without verification.

### Nullable minimum-price form field (mirrors verified `cost`/`sale`/`catalog` fields)
```jinja2
{# Source: pattern mirrors app/templates/pages/product_form.html lines 56-60
   (verified in this codebase, 2026-07-10) — insert between the "sale" field
   and the "catalog" field per CONTEXT D-07. #}
<div class="field">
  <label for="min_sale">Минимальная цена продажи <span class="muted">(необязательно)</span></label>
  <input type="text" id="min_sale" name="min_sale" inputmode="decimal" placeholder="0,00"
         value="{% if form %}{{ form.min_sale or '' }}{% elif product and product.min_sale_cents is not none %}{{ product.min_sale_cents | cents }}{% endif %}">
  {% if errors.min_sale %}<p class="error">{{ errors.min_sale }}</p>{% endif %}
</div>
```

## State of the Art

Not applicable in the "framework evolved" sense — this phase touches no external library whose API has changed. The only relevant "evolution" is internal: this is the third generation of nullable per-product override field in this codebase (`category`/`cost`/`sale`/`catalog` in Phase 2, `low_stock_threshold`/`stale_days` in Phase 6, `min_sale_cents` now in Phase 7) and the second generation of warn-but-allow guardrail (oversell in Phase 4, price-floor now). No deprecated approach is being replaced; this phase extends the current, still-current pattern.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The SQL `ORDER BY Product.category.is_(None), Product.category == ""` trick reliably sorts NULL/empty categories after named ones in SQLite | Code Examples, category grouping query | Low — flagged explicitly in the code example as needing test verification before use; a documented pure-Python fallback is provided in the same section, so this does not block planning, only signals "write a test for this ordering before trusting it" |
| A2 | `min_sale_cents` should (or should not) join `_PRICE_FIELDS` for `price_change` audit-trail treatment, vs. a `product_edited`-only treatment like `low_stock_threshold`/`stale_days` | Open Questions, Pitfall 4 | Medium — affects whether `price_history.html` needs a new `elif` branch and whether price-floor edits get old/new-value audit rows; CONTEXT.md does not decide this explicitly, so the planner must choose and document the choice as a plan decision |

**If this table is empty:** N/A — see rows above. Both assumptions are low-to-medium risk with mitigations already noted; neither blocks planning.

## Open Questions (RESOLVED)

1. **(RESOLVED — plan 07-02) Should `min_sale_cents` be audited via `_PRICE_FIELDS` (per-change `price_change` op with old/new cents, shown in "История цен") or via the `product_edited` path (change noted by field name only, no history line, like `low_stock_threshold`/`stale_days`)?**
   - What we know: CONTEXT.md (D-06/D-07) specifies the field's storage, form placement, and copy, but is silent on its audit-trail treatment. The codebase has two established patterns for optional Integer/money fields: the three `_PRICE_FIELDS` (cost/sale/catalog) get per-field `price_change` ops with old/new cents shown in `price_history.html`; `low_stock_threshold`/`stale_days` get folded into a single `product_edited` op's `fields` list with no visible before/after value.
   - What's unclear: Which precedent this field should follow. It is semantically a *price* (money, in cents) which argues for `_PRICE_FIELDS`; but it is also a *threshold/guardrail* like `low_stock_threshold` (an operational control rather than a transactional price), which argues for the `product_edited` path.
   - Resolution: Plan 07-02 joins `_PRICE_FIELDS` — `min_sale_cents` gets per-change `price_change` audit history in `price_history.html` (label "Минимальная"), matching the recommendation below.
   - Recommendation (as given, now adopted): Treat it as a price (join `_PRICE_FIELDS`) since it is literally stored in cents and the existing `price_history.html` UI already has a natural slot for "what was the minimum before, what is it now" — this is valuable audit information for a guardrail whose entire purpose is preventing accidental underselling. This requires: (1) adding `"min_sale_cents"` to `_PRICE_FIELDS` in `catalog.py`, and (2) adding one new `elif op.payload.field == "min_sale_cents"` branch (label suggestion: "Минимальная") to `price_history.html`.

2. **(RESOLVED — plan 07-01) Exact grouping/sorting implementation for the "Без категории" bucket (SQL-side vs. Python-side)?**
   - What we know: The bucket must sort last, always visible, never hidden (D-04). A working Python-side `groupby`/`sorted` approach is shown in Code Examples with an explicit sentinel; a SQL-side `ORDER BY` shortcut is also shown but flagged as unverified.
   - What's unclear: Whether SQLite's boolean-as-integer ordering behaves as assumed without an actual test run against a seeded DB with mixed NULL/empty/named categories.
   - Resolution: Plan 07-01 uses the Python-side grouping, matching the recommendation below.
   - Recommendation (as given, now adopted): Default to the Python-side grouping (simpler to reason about, portable to PostgreSQL without relying on dialect-specific NULL-ordering behavior) unless a plan-time spike proves the SQL approach correct and prefers it for performance (irrelevant at this data scale — a single local operator's catalog is small).

## Environment Availability

Skipped — this phase has no new external dependencies. It runs entirely within the existing installed toolchain (Python 3.13, FastAPI, SQLAlchemy, Alembic, Jinja2, htmx-vendored, SQLite), all of which are already verified present and working by every prior shipped phase (1-6) in this same repository.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* [VERIFIED: pyproject.toml `[dependency-groups] dev`] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `uv run pytest tests/test_catalog.py tests/test_sales.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAT-01 | Active products grouped by category, alphabetical, "Без категории" last, none hidden | unit (service) | `uv run pytest tests/test_catalog.py -k products_by_category -x` | ❌ Wave 0 — new test function needed in `tests/test_catalog.py` |
| CAT-01 | `/categories` page renders all groups, only active products, edit link works | web/integration | `uv run pytest tests/test_catalog.py -k web_categories -x` | ❌ Wave 0 — new test function needed (mirrors `test_web_sale_page_renders_form`-style pattern already used across route test files) |
| PRICE-01 | Product form saves/round-trips `min_sale_cents` including explicit `0` | unit (service) | `uv run pytest tests/test_catalog.py -k min_sale -x` | ❌ Wave 0 — new test function needed, mirrors `test_create_product_persists_all_fields_and_name_lc` |
| PRICE-01 | Sale below minimum without confirm -> warning, zero writes; `is not None` guard (NULL and 0 both correctly handled) | unit (service) | `uv run pytest tests/test_sales.py -k below_minimum -x` | ❌ Wave 0 — new test function needed, mirrors `test_oversell_blocks_without_confirm`/`test_oversell_confirm_writes_negative_stock` |
| PRICE-01 | Boundary: price exactly equal to minimum passes silently (strict `<`) | unit (service) | `uv run pytest tests/test_sales.py -k min_price_boundary -x` | ❌ Wave 0 — new test function needed |
| PRICE-01 | Basket tripping BOTH oversell and price-floor shows both warnings in one response | unit (service) + web | `uv run pytest tests/test_sales.py -k both_warnings -x` | ❌ Wave 0 — new test function needed, this is the highest-value single test for CONTEXT D-11 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_catalog.py tests/test_sales.py -x` (quick run, phase-scoped)
- **Per wave merge:** `uv run pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_catalog.py` — add test functions for `products_by_category` grouping/ordering and `min_sale_cents` create/update round-trip (including explicit `0`)
- [ ] `tests/test_sales.py` — add test functions for the price-floor check (no-confirm warns, confirm writes, boundary at exact minimum, combined-with-oversell case)
- [ ] `alembic/versions/0006_product_min_sale_price.py` — new migration; the existing `tests/conftest.py` `engine` fixture uses `Base.metadata.create_all` (not Alembic) for test fixtures, so the new column is automatically picked up by tests once added to `models.py` — no test-fixture change needed, but a manual/CI check that `alembic upgrade head` on a copy of a pre-Phase-7 DB succeeds is still warranted
- No new test framework or fixture infrastructure needed — `tests/conftest.py`'s existing `session`/`client`/`product`/`stocked_product` fixtures cover every scenario this phase needs

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Project has no auth in v1 (single local operator, CLAUDE.md/PROJECT.md explicit decision) — unaffected by this phase |
| V3 Session Management | No | No sessions used anywhere in this app |
| V4 Access Control | No | Single-user local app, no roles/permissions this milestone |
| V5 Input Validation | Yes | `min_sale_cents`: reuse `parse_optional_cents()` (already rejects non-finite, negative, and unparsable values with a RU error) — the SAME validation already applied to `cost`/`sale`/`catalog`. Category grouping query: no user-supplied filter input this phase (no search box), so no injection surface beyond what already exists for `/products`. |
| V6 Cryptography | No | Not applicable — no crypto operations in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stored XSS via product name rendered on the new `/categories` page | Tampering / Elevation of Info Disclosure | Jinja2 autoescape only, never `\|safe` on `product.name` — verified this is already the codebase-wide convention (`sale_oversell.html` comment: "Product names are untrusted stored input... autoescape only, never `\|safe`"); the new `categories.html` template must follow the identical rule, and this is worth an explicit verification step in the plan since it's a NEW template rendering the same untrusted field |
| Negative or malformed `min_sale_cents` input tampering the guardrail into a no-op or nonsensical floor | Tampering | Reuse `parse_optional_cents()` verbatim — it already rejects negative amounts with the same `PRICE_ERROR` as `cost`/`sale`/`catalog` (verified, `app/services/catalog.py` lines 22-40); do not write a separate, potentially laxer parser for this field |
| A crafted basket submission that races `confirm=1` before the server-side check completes (TOCTOU) | Tampering | Not a new risk — the existing single-transaction, server-side-only check (no client-side bypass possible since `confirm` is just a form value the server itself validates against fresh DB state on the SAME request) already covers this; PRICE-01 adds no new attack surface here since it uses the identical mechanism as the already-shipped oversell check |

## Sources

### Primary (HIGH confidence — direct codebase inspection, 2026-07-10)
- `app/models.py` — Product model, existing nullable-Integer field conventions, naming convention block
- `app/services/sales.py` — `register_sale()`, oversell warn-but-allow implementation (the direct pattern this phase extends)
- `app/services/catalog.py` — `category_options()`, `parse_optional_cents()`, `parse_optional_int()`, `create_product()`/`update_product()` (`_PRICE_FIELDS` audit pattern)
- `app/services/stock.py` — `effective_low_stock_threshold()` (the `is not None` discipline precedent)
- `app/routes/sales.py`, `app/routes/products.py`, `app/routes/reports.py` — thin-route conventions, HX-Request branching precedent (or lack thereof, for `/reports/stock`)
- `app/templates/partials/sale_oversell.html`, `app/templates/partials/sale_form.html` — the exact partial/include structure to mirror
- `app/templates/pages/product_form.html`, `app/templates/pages/reports_stock.html`, `app/templates/partials/price_history.html` — form-field and read-page precedents
- `app/templates/base.html`, `app/static/style.css` — nav structure and confirmed-existing CSS classes (`.error-block`, `.empty-state`, `.muted`, `.num`, `button.danger`, `button.secondary`, `.field`) — no new CSS required
- `app/core.py` — `to_cents()`/`format_cents()` (the single sanctioned money conversion point)
- `alembic/versions/0005_product_thresholds.py`, `alembic/env.py` — migration pattern precedent (plain `op.add_column`, no batch mode needed for simple nullable-column adds)
- `tests/test_sales.py`, `tests/test_catalog.py`, `tests/conftest.py` — test pattern precedents and existing fixtures
- `pyproject.toml` — pinned dependency versions, pytest config
- `.planning/phases/07-category-browsing-minimum-price-guardrail/07-CONTEXT.md` — locked user decisions (D-01 through D-11)
- `.planning/phases/07-category-browsing-minimum-price-guardrail/07-UI-SPEC.md` — approved visual/interaction contract
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — requirement text and project decision history

### Secondary (MEDIUM confidence)
None — this phase required no external web research; every fact needed for planning was verifiable directly in the local, already-shipped codebase.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all versions verified against `pyproject.toml`
- Architecture: HIGH — both capabilities have a near-exact, already-shipped precedent in this same repo, directly read and quoted above
- Pitfalls: HIGH — all four pitfalls are either already-documented codebase conventions (Pitfall 1/3) or derived from direct comparison of the two required checks' semantics (Pitfall 2/4)

**Research date:** 2026-07-10
**Valid until:** 2026-08-09 (30 days — stable, internal-codebase-only research with no external library version dependency)
