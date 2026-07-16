# Phase 19: Products Page Rebuild - Research

**Researched:** 2026-07-16
**Domain:** Server-rendered (FastAPI + Jinja2 + htmx) list-page rebuild over an existing SQLAlchemy 2.0 schema — grouping, template refactor, no new external dependency
**Confidence:** HIGH

## Summary

Phase 19 is **not** a from-scratch build — it is a targeted rebuild of one existing route
(`GET /products`, `app/routes/products.py`), one existing service function
(`list_products_view`, `app/services/catalog.py`), and two existing templates
(`app/templates/pages/products_list.html`, `app/templates/partials/product_rows.html`). Every
piece of infrastructure the five requirements need already exists in the codebase and is
already covered by tests: `Product.code` is already unique among active products (one row per
code today), `Product.quantity` is already a maintained cached sum of ledger deltas
(`app/models.py:169`), `Product.category` already exists and is already filterable
(`app/services/catalog.py:391-393`, wired in `product_rows.html:41-44`), and
`app/services/batches.py::open_batches(session, product_id)` already returns exactly the
per-batch data (expiry, name, quantity) PROD-04 asks to surface, ordered earliest-expiry-first,
open (quantity > 0) batches only. **The phase's real work is UI, not data modeling**: add a
quantity column, add a batch-expand affordance under each product row, delete the "Добавить
товар" button, and convert the delete `<button>` to a text `<a>` link — while keeping the
existing filter/sort/pagination contract (`list_products_view`, `page_window`, `paginate`)
intact, since success criterion 5 requires it to keep working unchanged.

The phase-goal wording ("not a flat per-batch dump") describes an anti-pattern to avoid, **not
the current state** — today's `/products` list already renders one row per product code with
zero batch visibility at all (no quantity column, no batch breakdown). The real gap is the
*opposite* of "too flat": batch data is currently invisible on this page, and PROD-04 asks to
add it back in a **grouped**, not flat, shape (nested under each code, not as sibling rows).

**Primary recommendation:** Extend `list_products_view`'s output with each page row's open
batches (fetched via one additional grouped query, not N+1, mirroring the
`SELECT ... WHERE product_id IN (...)` shape already used by `stale_products` in
`app/services/reports.py`), add a `quantity` column and a native `<details>`/`<summary>`
batch-breakout row to `product_rows.html`, delete the `Добавить товар` link and convert the
`Удалить` `<button class="danger">` to an `<a>` styled with a new `.link-danger` class reusing
the existing `#b91c1c` destructive token — and touch nothing else. No new package, no schema
migration, no new route is required.

## Project Constraints (from CLAUDE.md)

Directives from `E:\dev\myorishop\CLAUDE.md` that bear directly on this phase:

- **Sync SQLAlchemy `Session` + plain `def` routes only** — no `async`/`aiosqlite`. Every file
  touched in this phase (`products.py`, `catalog.py`, `batches.py`) already follows this; new
  code must too.
- **Portable ORM only, no raw/SQLite-specific SQL** — the new batch-grouping query must use
  `select(Batch).where(Batch.product_id.in_(ids))`, never string-interpolated SQL or SQLite
  functions (mirrors the existing `nullslast()` portability comment in
  `app/services/batches.py:30`).
- **Money as integer cents, never float** — `cost_cents`/`sale_cents`/`price_cents` are already
  integers; this phase only *displays* them (via the existing `cents` Jinja filter), it does not
  parse or write money.
- **No SPA/build-step frontend** — htmx 2.0.10 (vendored at `app/static/htmx.min.js`) + Jinja2
  only. The batch-expand UI must not introduce new JavaScript; native `<details>` is the
  no-JS-required option (see Architecture Patterns).
- **No Tailwind, no CSS build step** — extend `app/static/style.css` directly, following its
  existing "name the color token, disclaim new roles" comment convention (see
  `18-PATTERNS.md` Q5, already established for this exact file).
- **WCAG 1.4.1 (Use of Color) awareness is an established project concern** — `style.css:290-292`
  already documents a known 1.4.1 gap for the PROD-06 price cue. The new delete text link must
  not rely on color alone to read as interactive (see Pitfall 2 below).
- **GSD workflow enforcement**: file edits happen only through `/gsd-execute-phase` — noted for
  completeness, not a research finding.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROD-01 | Remove "Добавить товар" from the product list | Two literal occurrences found in `product_rows.html` (page-action button `products_list.html:5` mirrored by the empty-state CTA `product_rows.html:83`) plus the same button in the unrelated `/categories` page. `/products/new` and `POST /products` **must stay** — `catalog_detail.html:37` links `/products/new?code=...` for "изменить цену", and goods receipt (`app/services/receipts.py:146-159`) already auto-creates products, confirming the requirement's premise. |
| PROD-02 | Product-list delete is a text link, not a button | No existing "delete as text link" pattern exists anywhere in this codebase — every delete (`product_rows.html:60-63`, `warehouse_rows.html:84-88`, mobile equivalents) is `<button class="danger" hx-post=... hx-confirm=...>`. This phase introduces the pattern; recommended CSS + accessibility approach documented below. |
| PROD-03 | Group by code, show total quantity summed across batches | `Product.quantity` (`app/models.py:169`) is **already** the maintained cached projection of `SUM(operations.qty_delta)` per product — no computation needed, just render it. `Product.code` is already unique among active rows (`uq_products_code_active`), so "one row per code" is already true structurally; only the quantity column is missing from the template. |
| PROD-04 | Individual batches visible with own expiry + name | `app/services/batches.py::open_batches(session, product_id, warehouse_id=None)` already returns exactly `{expiry, name, quantity, price_cents, comment, location}` per open batch, correctly ordered (earliest expiry first, NULL-expiry last, then oldest-received). Needs a batched (not N+1) variant for a 20-row page — see Architecture Patterns. |
| PROD-08 | Category shown + filterable | **Already implemented** today: `product_rows.html:26,41-44,55` renders and filters by category (substring, case-insensitive, via `list_products_view`'s `category_q` param), covered by `test_list_products_view_filters_by_category` and `test_web_products_filter_row_narrows_results`. Only a UX polish gap remains (plain text input, no `datalist` of known categories) — see Open Questions. |
</phase_requirements>

## Architectural Responsibility Map

This is a single-process server-rendered app (FastAPI + Jinja2 + htmx) — there is no separate
API tier or SPA client tier. The table below maps each capability onto this app's actual
layers (route/service = backend; Jinja2 template = SSR; htmx-triggered partial swap = browser).

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Quantity-per-code total | Database / Storage | API/Backend | `Product.quantity` is already a DB-cached projection (D-09); backend just reads it, no new query logic |
| Batch grouping (expiry/name per code) | API/Backend | Frontend Server (SSR) | New grouped query lives in `app/services/batches.py` (or `catalog.py`); template only renders what the service hands it |
| Category display + filter | API/Backend | Frontend Server (SSR) | Filtering logic already lives in `list_products_view` (Python-side substring filter); template renders the input + column |
| Add-button removal | Frontend Server (SSR) | — | Template-only deletion; no backend change (route stays for the `/products/new?code=` entry point) |
| Delete-as-text-link | Frontend Server (SSR) | Browser (htmx) | Template swaps `<button>` for `<a>`; the existing `POST /products/{id}/quick-delete` htmx wiring is reused unchanged |
| Pagination / sort (must keep working) | API/Backend | Frontend Server (SSR) | `paginate()`/`page_window()` (`app/services/pagination.py`) and `_SORT_MAP` (`app/services/catalog.py:25-28`) are untouched by this phase |

## Standard Stack

No new library is required for this phase. Every capability is built on packages already
declared in `pyproject.toml` and already used by the exact files this phase touches.

### Core (existing, unchanged)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.139.0 | `GET /products` route, `POST .../quick-delete` | Already the app's routing layer [VERIFIED: `pyproject.toml`] |
| SQLAlchemy 2.0 | 2.0.51 | `Batch`/`Product` query composition | Already the app's ORM layer; new query uses the same `select().where().in_()`/`nullslast()` idioms as `app/services/batches.py` [VERIFIED: codebase] |
| Jinja2 | 3.1.6 | `product_rows.html` rendering, `<details>` markup | Already the app's templating layer [VERIFIED: codebase] |
| htmx | 2.0.10 (vendored, `app/static/htmx.min.js`) | Existing filter/sort/pagination/quick-delete AJAX wiring | Unchanged; the new delete link reuses the identical `hx-post`/`hx-confirm`/`hx-target` attributes already proven on the button it replaces [VERIFIED: codebase] |

### Supporting
None new. `app/static/style.css` gets additive rules only (no new file, no build step).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Native `<details>`/`<summary>` per-row batch expand | An htmx `hx-get` round-trip per row to a new `/products/{id}/batches` endpoint | Round-trip adds a new route + N extra requests when an operator expands several rows in a session; at 20 rows/page and typically few batches/product, prefetching server-side and rendering inert-until-expanded `<details>` is simpler, needs zero new endpoint, and works with JS disabled. Recommended: prefetch. |
| Python-side batched query (`product_id IN (...)`) | Per-row `open_batches()` call (N+1) | N+1 is not *wrong* at this scale (SQLite, 20 rows/page, single operator) — `open_batches` is already called per-row elsewhere in the app (single-entity contexts). But `app/services/reports.py::stale_products` establishes the house precedent of one grouped query over a per-row loop for *list* views; follow that precedent here for consistency, not because N+1 would fail. |
| Text-input category filter (existing) | `<select>` populated from `category_options()` | Category is explicitly modeled as **free text** with datalist suggestions (`app/models.py:148-149` comment), not an enum — a strict `<select>` filter would silently hide products whose category text doesn't exactly match a known option (typos, legacy values). Keep the substring text filter; optionally add `list="cat-options"` (datalist) for discoverability, matching `product_form.html:54-56`'s existing pattern. See Open Questions. |

**Installation:** none — no new dependency to add to `pyproject.toml`.

**Version verification:** not applicable — no new package. Existing versions confirmed present via `pyproject.toml` and a live `pytest` run (see Sources).

## Package Legitimacy Audit

**Not applicable.** This phase installs zero external packages — it is a template/service/CSS
change over the existing stack. No `npm view`/`pip index`/registry check is required.

## Architecture Patterns

### System Architecture Diagram

```
Operator's browser
      |
      | GET /products?code=&name=&category=&sort=&page=
      v
FastAPI route: products_list()  (app/routes/products.py:81-97)
      |
      | calls _products_context() -> list_products_view()
      v
Service: catalog.list_products_view()  (app/services/catalog.py:368-410)
      |  1. SELECT active Product rows (unchanged)
      |  2. filter by code/name/category substrings (unchanged)
      |  3. sort (unchanged, _SORT_MAP)
      |  4. paginate() -> 20 rows for this page (unchanged)
      |
      | NEW STEP: batch this page's 20 product ids into ONE query
      v
Service: batches_for_products(session, product_ids)  (NEW, app/services/batches.py)
      |  SELECT Batch WHERE product_id IN (ids) AND quantity > 0
      |  ORDER BY expiry ASC NULLS LAST, created_at ASC   (mirrors open_batches)
      |  group rows into {product_id: [Batch, ...]} in Python
      v
Route assembles context: rows = [{"product": p, "batches": batches_by_id.get(p.id, [])}, ...]
      |
      v
Template: product_rows.html
      |  one <tr> per product: code | name | category | quantity | ДЦ | ПЦ | actions
      |  <tr><td colspan><details><summary>N партий</summary>
      |        nested <table>: expiry | name | quantity per open batch
      |  </details></td></tr>   (rendered only when batches is non-empty)
      v
HTML response (full page OR #product-rows partial, same as today)
      |
      | operator clicks column-header filter input / sort select / pagination link
      | -> hx-get="/products" hx-target="#product-rows" hx-swap="outerHTML"  (UNCHANGED)
      |
      | operator clicks "Удалить" text link (was a button)
      | -> hx-post=".../quick-delete" hx-confirm="..." hx-target="#product-rows"  (UNCHANGED wiring, new element)
      v
Same round-trip as today, re-rendering #product-rows
```

### Recommended Project Structure

No new files/folders. Modified files only:

```
app/
├── routes/products.py              # _products_context(): thread batches into context
├── services/
│   ├── catalog.py                  # list_products_view(): unchanged internals; OR
│   └── batches.py                  # NEW: batches_for_products(session, product_ids) -> dict[str, list[Batch]]
└── templates/
    ├── pages/products_list.html    # remove "Добавить товар" <p class="page-actions">
    └── partials/product_rows.html  # + quantity column, + batch <details> row, delete -> <a>
```

### Pattern 1: Batched (non-N+1) per-row child data, grouped in Python

**What:** Fetch child rows (`Batch`) for an entire page of parent rows (`Product`) in one
`IN (...)` query, then group them into a `dict[parent_id, list[child]]` in Python — never one
query per parent row in a *list* view.

**When to use:** Whenever a list page needs to show child/detail data (here: batches) for every
row on the page, not just one entity (contrast with `open_batches()`'s existing single-product
call sites in the sale/receipt/write-off pickers, which are correctly N=1 there).

**Example (new function, mirrors `open_batches`'s exact ordering):**
```python
# Source: pattern derived from app/services/batches.py:15-32 (open_batches)
# and app/services/reports.py:170-192 (stale_products' single-grouped-query precedent)
from collections import defaultdict
from sqlalchemy import nullslast, select

def batches_for_products(session: Session, product_ids: list[str]) -> dict[str, list[Batch]]:
    """Open batches (quantity > 0) for a PAGE of products, grouped by product_id.

    Same ordering as open_batches (earliest expiry first, NULL last, then
    oldest receipt) but ONE query for the whole page instead of N+1.
    """
    if not product_ids:
        return {}
    rows = session.scalars(
        select(Batch)
        .where(Batch.product_id.in_(product_ids), Batch.quantity > 0)
        .order_by(nullslast(Batch.expiry.asc()), Batch.created_at.asc())
    )
    grouped: dict[str, list[Batch]] = defaultdict(list)
    for batch in rows:
        grouped[batch.product_id].append(batch)
    return dict(grouped)
```

### Pattern 2: Zero-JS expand/collapse via native `<details>`

**What:** Render every product row's batch breakdown server-side inside a `<details>` element
nested in a sibling `<tr><td colspan="...">`, collapsed by default. No JavaScript, no extra
HTTP round trip, works exactly the same with htmx present or absent.

**When to use:** When the child data is already fetched for the whole page (Pattern 1) and is
cheap to render — exactly this case (batches per product, single operator, local SQLite).

**Example:**
```jinja
{# Source: pattern — no direct in-repo analog for <details>; the closest
   precedent for a conditional sibling <tr> under a product row is the
   existing "blocked delete" row in product_rows.html:66-70. #}
<tr>
  <td>{{ product.code }}</td>
  <td>{{ product.name }}</td>
  <td>{% if product.category %}{{ product.category }}{% else %}<span class="muted">—</span>{% endif %}</td>
  <td class="num">{{ product.quantity }}</td>
  <td class="num">{% if product.cost_cents is not none %}{{ product.cost_cents | cents }}{% else %}<span class="muted">—</span>{% endif %}</td>
  <td class="num">{% if product.sale_cents is not none %}{{ product.sale_cents | cents }}{% else %}<span class="muted">—</span>{% endif %}</td>
  <td>
    <a href="/products/{{ product.id }}/edit">Изменить</a>
    <a href="#" class="link-danger"
       hx-post="/products/{{ product.id }}/quick-delete?page={{ page }}{{ extra_qs }}"
       hx-confirm="Удалить товар „{{ product.name }}“? Он будет скрыт из каталога и поиска, история операций сохранится."
       hx-target="#product-rows" hx-swap="outerHTML">Удалить</a>
  </td>
</tr>
{% set product_batches = batches_by_id.get(product.id, []) %}
{% if product_batches %}
<tr>
  <td colspan="7">
    <details>
      <summary>Партии ({{ product_batches | length }})</summary>
      <table class="batch-picker">
        <thead><tr><th>Срок годности</th><th>Партия</th><th class="num">Остаток</th></tr></thead>
        <tbody>
          {% for b in product_batches %}
          <tr>
            <td>{% if b.expiry %}{{ b.expiry | ru_date }}{% else %}<span class="muted">—</span>{% endif %}</td>
            <td>{% if b.name %}{{ b.name }}{% else %}<span class="muted">—</span>{% endif %}</td>
            <td class="num">{{ b.quantity }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </details>
  </td>
</tr>
{% endif %}
```
Reuses the existing `.batch-picker` CSS class (`style.css:279-280`, margin-only rule, no
selection-highlight side effects here since no `<input type="radio">` is present) and the
existing `ru_date` Jinja filter (`app/routes/__init__.py:19`).

### Pattern 3: Text-link destructive action (new CSS)

**What:** An `<a>` styled to read as a destructive action without relying on color alone
(WCAG 1.4.1), reusing the htmx attributes verbatim from the button it replaces.

**Code:**
```css
/* Text-link delete action (Phase 19, PROD-02): reuses the destructive token
   (#b91c1c) already named in the file header — no new color role. Keeps the
   browser's default underline (no text-decoration:none) so the link reads
   as interactive by shape, not color alone (WCAG 1.4.1 — see the existing
   price-cue disclaimer at :290-292 for this project's established stance). */
a.link-danger {
  color: #b91c1c;
}
a.link-danger:hover {
  color: #7f1414;
}
```

### Anti-Patterns to Avoid

- **Re-deriving quantity from a live `SUM(operations.qty_delta)` per row:** `Product.quantity`
  is already the maintained cached projection (D-09). Querying `Operation` directly for this
  page would duplicate work the ledger already does on every write and could drift from the
  cached value if done inconsistently elsewhere.
- **Deleting or gating `GET /products/new` / `POST /products`:** PROD-01 removes the *button*
  from the *list page* only. The route is a live entry point from `catalog_detail.html`'s
  "изменить цену" link and from the receipt flow's redirect-to-existing-product-edit logic
  (`products.py:184-189`). Deleting it breaks `test_web_categories_page_lists_groups_with_edit_link`
  indirectly (via the shared nav) and, directly, the catalog "изменить цену" flow.
- **Making the category filter an exact-match `<select>`:** category is explicitly free text
  (see Alternatives Considered above) — an exact-match dropdown would hide legitimately
  differently-cased/typo'd category values from the filtered view, silently.
- **Adding a new `/products/{id}/batches` htmx endpoint for the expand action:** unnecessary
  network round trip when the data is already cheap to prefetch for a 20-row page (Pattern 1);
  adds a new route + new test surface for no UX benefit at this data scale.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-code stock total | A new SUM query over `operations` | `Product.quantity` (already cached, D-09) | Already correct, already tested, already the value every other page in the app trusts (`quick_delete_product`'s stock guard reads it directly) |
| Batch ordering (expiry-first, NULL-last) | A custom sort key in Python | `nullslast(Batch.expiry.asc())` (already used in `open_batches`) | Portable across SQLite/PostgreSQL (D-05 sync-readiness); reinventing this risks a SQLite-only `ORDER BY expiry IS NULL, expiry` trick that breaks portability |
| Pagination page-window ("1 2 … 8") | Inline Jinja math | `app/services/pagination.py::page_window` | Already the single source of truth every list page (`products`, `warehouses`) shares — hand-rolling a second implementation is the exact anti-pattern the module's own docstring warns against |
| Expand/collapse interactivity | New JavaScript file | Native `<details>`/`<summary>` | Zero-JS requirement (CLAUDE.md: no SPA, offline-first); this app has exactly one first-party JS file (`price-cue.js`) and no precedent for adding a second for a non-money feature |

**Key insight:** every requirement in this phase maps to data or query patterns that already
exist and are already tested elsewhere in the codebase. The risk in this phase is almost
entirely template/UI risk (breaking the existing filter/sort/pagination contract while adding
rows), not data-modeling risk.

## Common Pitfalls

### Pitfall 1: Breaking the `#product-rows` htmx swap target
**What goes wrong:** Every filter input, the sort `<select>`, and pagination links target
`#product-rows` with `hx-swap="outerHTML"` and read state via
`hx-include="#product-rows input, #product-rows select"`. If the new quantity column or the
`<details>` batch block introduces a stray `<input>`/`<select>` inside `#product-rows`, it gets
silently included in every subsequent filter/sort/pagination request.
**Why it happens:** The whole filter/sort/page state machine works by including *every*
input/select found inside the wrapper div — adding new form controls anywhere inside it (even
unrelated ones) changes what gets submitted.
**How to avoid:** The `<details>` batch block must contain **zero** `<input>`/`<select>`
elements — it is read-only. The delete link becomes an `<a>`, which is not swept up by
`hx-include`'s `input, select` selector either way.
**Warning signs:** `test_web_products_filter_row_narrows_results` /
`test_web_products_pagination_bar_shows_correct_total` failing after the template change is the
canary.

### Pitfall 2: Delete link fails WCAG 1.4.1 or breaks htmx's click interception
**What goes wrong:** (a) Styling the new `<a class="link-danger">` with `text-decoration: none`
would make it distinguishable from the "Изменить" link *only* by color — the exact 1.4.1 gap
this project already flags for the price cue. (b) Anchors need an `hx-post`/`hx-confirm`
attribute pair to trigger the AJAX request on click; htmx intercepts the click and calls
`preventDefault()` for elements carrying `hx-*` attributes (including anchors), so `href="#"`
never actually navigates — but if the anchor is given a **real** `href` (e.g. accidentally
`href="/products/{{ product.id }}/delete"`), a user with JS/htmx disabled, or a slow first paint
before htmx attaches, could navigate there via a GET, which the route doesn't even support
(delete is POST-only) — 405.
**Why it happens:** Copy-pasting a "convert button to link" change without checking htmx's
click-interception contract or the existing color-only precedent flagged in `style.css:290-292`.
**How to avoid:** Keep the browser's default underline (don't reset `text-decoration`); use
`href="#"` (never a real delete URL) exactly as `warehouse_rows.html`'s cancel button pattern
(`hx-on:click`) does for its non-htmx cancel action, but here rely on htmx's `hx-post` click
interception instead.
**Warning signs:** Manual click-test with JavaScript disabled (or `htmx.min.js` load blocked)
navigating to a 405 page instead of doing nothing.

### Pitfall 3: N+1 exploding on a future larger catalog
**What goes wrong:** Calling `open_batches(session, product.id)` once per row inside the Jinja
loop (or in a Python list comprehension over `page_rows`) issues up to 20 separate `SELECT`
queries per page load.
**Why it happens:** `open_batches` already exists and is the obvious thing to reach for — it's
correct for a single-product context but not a list context.
**How to avoid:** Use the batched `IN (...)` query (Pattern 1) once per page load, not per row.
**Warning signs:** None functionally (SQLite is fast enough at this scale that tests will still
pass) — this is a style/consistency concern flagged because `stale_products` already
establishes the batched-query house convention for list views; a plan that doesn't follow it
isn't *broken*, just inconsistent with `app/services/reports.py`'s established pattern.

### Pitfall 4: Legacy batches with NULL name/expiry rendering as blank instead of "—"
**What goes wrong:** Batches seeded by the pre-Phase-9 legacy migration (`Batch.is_legacy == 1`)
have `name = NULL` and often `expiry = NULL`. A naive `{{ b.name }}` renders an empty cell with
no indication data is intentionally absent (vs. a rendering bug).
**Why it happens:** Not every batch has these fields populated — only receipts recorded after
Phase 9's batch tracking landed set `name`/`expiry`.
**How to avoid:** Guard every batch field exactly like `batch_picker.html:52` and
`receipt_batch_chooser.html:36` already do: `{% if b.expiry %}...{% else %}<span class="muted">—</span>{% endif %}`.
**Warning signs:** A product with only its legacy "Остаток до внедрения партий" batch showing
blank cells instead of "—" in the expanded batch table.

### Pitfall 5: Forgetting the `product` conftest fixture has zero batches
**What goes wrong:** The shared `client`/`session` test fixtures (`tests/conftest.py:38-49`)
seed a bare `product` with `quantity=0` and **no `Batch` row at all**. Most of `test_catalog.py`'s
existing `/products` tests use this fixture. If the new template code assumes every product has
at least one batch (e.g. `product_batches[0].expiry` without a length check), those tests break.
**Why it happens:** Only `stocked_product` (`tests/conftest.py:75-110`) seeds a real batch.
**How to avoid:** The `<details>` block must be conditionally rendered (`{% if product_batches %}`,
as shown in Pattern 2) — zero-batch products (new products, or legacy products with 0 stock)
must render the row with no expand affordance at all, not an empty/broken one.
**Warning signs:** Any of the 61 currently-passing `test_catalog.py` tests failing after the
template change — see Validation Architecture below for the exact regression command.

## Code Examples

### Existing: filter/sort/pagination wiring to preserve verbatim
```jinja
{# Source: app/templates/partials/product_rows.html:32-44 (current file, unmodified by this phase) #}
<th><input type="text" name="category" placeholder="Фильтр…" value="{{ category }}"
           hx-get="/products" hx-trigger="input changed delay:300ms"
           hx-include="#product-rows input, #product-rows select"
           hx-target="#product-rows" hx-swap="outerHTML" hx-push-url="true"></th>
```

### Existing: `Product.quantity` guard already trusted elsewhere (precedent for PROD-03)
```python
# Source: app/services/catalog.py:312-330 (quick_delete_product)
# D-09: Product.quantity is already a cached projection of
# SUM(operations.qty_delta) — no extra query is needed for the guard.
if product.quantity > 0:
    return False, {"blocked_qty": product.quantity}
```

### Existing: `open_batches` ordering to mirror in the new batched query (PROD-04)
```python
# Source: app/services/batches.py:15-32
def open_batches(session, product_id, warehouse_id=None):
    stmt = select(Batch).where(Batch.product_id == product_id, Batch.quantity > 0)
    if warehouse_id is not None:
        stmt = stmt.where(Batch.warehouse_id == warehouse_id)
    return list(
        session.scalars(
            stmt.order_by(nullslast(Batch.expiry.asc()), Batch.created_at.asc())
        )
    )
```

## State of the Art

Not applicable — this is an internal codebase pattern question, not an ecosystem/library
currency question. Nothing in this phase depends on library version freshness (see Standard
Stack: zero new packages).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Native `<details>`/`<summary>` is an acceptable UX pattern for "batches remain visible" (PROD-04) rather than an always-expanded inline sub-table | Architecture Patterns, Pattern 2 | If the operator wants batches **always** visible (no click needed), the `<details>` element should be rendered with the `open` attribute by default instead of collapsed — a one-line template change, not a redesign. Flagged because no CONTEXT.md exists to confirm the operator's preference; worth a `checkpoint:human-verify` or an explicit discuss-phase question before locking the collapsed-by-default choice. |
| A2 | The existing free-text category filter (already implemented) satisfies PROD-08's "can be filtered by category" as written, and only needs a UX polish (e.g. `datalist`), not a redesign into a `<select>` | Standard Stack, Alternatives Considered | If the operator/planner reads PROD-08 as requiring a *dropdown of known categories* (not free-text substring), the plan should add `list="cat-options"` sourced from the already-existing `category_options()` — low risk either way since both variants reuse existing functions. |
| A3 | Removing "Добавить товар" applies only to the `/products` list page, not the `/categories` page's own (separate) empty-state CTA at `categories.html:9` | Phase Requirements table (PROD-01) | `/categories` is not in this phase's requirement scope (PROD-01 says "product list", and the roadmap's phase boundary is `/products` specifically) — but an operator doing a visual pass after this phase ships might expect both removed for consistency. Low risk: leaving `/categories` unchanged doesn't break anything, just an inconsistency to flag. |

## Open Questions (RESOLVED)

1. **Should the batch breakdown be collapsed or expanded by default?**
   - What we know: PROD-04 only requires the batches to be "visible" (reachable), not
     necessarily always-rendered-open. Success criterion 2 says "Operator can see each code's
     individual batches" — satisfiable either way.
   - What's unclear: whether "can see" means "can see immediately without a click" or "can
     reach with one click." No CONTEXT.md exists to settle this (this phase skipped
     discuss-phase).
   - Recommendation: default to collapsed (`<details>` without `open`), since a fully-expanded
     20-row page with N batches each would be visually heavy and defeats the "scan by code"
     goal stated in the phase description itself ("reads as a stock list the operator can scan
     by code"). Flag as a planner discretion call, not a blocker.
   - **RESOLVED:** collapsed by default, per `19-UI-SPEC.md` Interaction & Layout Decision 1.

2. **Does PROD-08's category filter need to become a `<select>`/`datalist` in this phase, or is the existing substring `<input>` sufficient?**
   - What we know: the substring filter is already implemented, tested, and functionally
     satisfies the literal requirement text.
   - What's unclear: whether the operator considers a free-text filter "filterable by category"
     in spirit, given every other enum-like filter in the app (warehouse `status`, product-list
     `sort`) uses a `<select>`.
   - Recommendation: low-cost polish — add `list="cat-options"` to the existing category filter
     `<input>` (one attribute, reuses `category_options()` already imported into
     `products.py:16`), rather than converting to a strict `<select>` (see Anti-Patterns).
   - **RESOLVED:** no redesign — keep the existing free-text `<input>` unchanged, `datalist`
     polish left as planner's discretion (non-blocking), per `19-UI-SPEC.md` Interaction &
     Layout Decision 3.

3. **Should quantity be sortable?**
   - What we know: success criterion 5 only requires *existing* sort/filter/pagination to keep
     working — it does not ask for a new "sort by quantity" option, and `_SORT_MAP` currently
     only has `name_desc`/`code`.
   - What's unclear: nothing blocking — this is out of scope per the literal requirements, but
     worth a one-line callout since "scan by code" pages often want a low-stock-first sort.
   - Recommendation: do not add in this phase (no requirement covers it); note as a candidate
     follow-up.
   - **RESOLVED:** not in scope — no requirement covers it; not added in `19-01-PLAN.md`, noted
     as a possible future follow-up only.

## Environment Availability

Skipped — this phase has no external tool/service/runtime dependency beyond the already-running
local Python/uv/SQLite stack, unchanged by this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x [VERIFIED: `pyproject.toml` `[tool.pytest.ini_options]`, live run below] |
| Config file | `pyproject.toml` → `testpaths = ["tests"]`, `pythonpath = ["."]` |
| Quick run command | `uv run pytest tests/test_catalog.py -q` (**measured 12.23s, 61 passed**, 2026-07-16) |
| Full suite command | `uv run pytest -q` (**measured 125.66s, 711 passed, 3 warnings**, 2026-07-16 — this is the pre-phase-19 baseline; any post-change count below 711 is a regression) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROD-01 | "Добавить товар" absent from `/products`; `/products/new` still reachable | unit | `uv run pytest tests/test_catalog.py -q -k web_products` | ⚠️ Wave 0 — no existing test asserts the button's *absence*; `test_web_products_page_lists_created_product` etc. must be extended or a new negative assertion added |
| PROD-02 | Delete renders as `<a>` not `<button>`, htmx wiring unchanged | integration | `uv run pytest tests/test_catalog.py -q -k quick_delete` | ✅ `test_web_quick_delete_succeeds_and_removes_row` / `test_web_quick_delete_blocked_when_stock_positive` exist — **must stay green**, plus ⚠️ Wave 0 for a new "is an `<a>`, not a `<button>`" assertion |
| PROD-03 | Quantity column shows `Product.quantity` per code | unit | `uv run pytest tests/test_catalog.py -q` | ⚠️ Wave 0 — no existing test asserts a quantity value renders in `/products` rows (only `/categories`'s `products_by_category` path is covered, not `/products`) |
| PROD-04 | Batches (expiry, name) visible per code, zero-batch products unaffected | unit + integration | `uv run pytest tests/test_batches.py tests/test_catalog.py -q` | ✅ `open_batches` ordering fully covered (`test_open_batches_ordering`, `test_open_batches_ordering_excludes_zero_quantity`); ⚠️ Wave 0 for the new `batches_for_products` grouping function and its template rendering |
| PROD-08 | Category shown + filtered | unit | `uv run pytest tests/test_catalog.py -q -k category` | ✅ `test_list_products_view_filters_by_category`, `test_web_products_filter_row_narrows_results` — already green, must stay green (no behavior change expected) |
| (regression) | Existing filter/sort/pagination unaffected by new columns/rows | integration | `uv run pytest tests/test_catalog.py tests/test_pagination.py -q` | ✅ 61 + pagination-suite tests exist — the phase-gate canary |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_catalog.py -q` (~12s) + `uv run ruff check`
- **Per wave merge:** `uv run pytest tests/test_catalog.py tests/test_batches.py tests/test_pagination.py -q`
- **Phase gate:** `uv run pytest -q` must report **≥ 711 passed** before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_batches.py` — new `batches_for_products(session, product_ids)` grouping
      function: empty-list input, multiple products, quantity-0 batches excluded, ordering
      matches `open_batches`
- [ ] `tests/test_catalog.py` — `/products` list renders `product.quantity` per row
- [ ] `tests/test_catalog.py` — `/products` list renders a batch's `expiry`/`name` when the
      product has open batches, and renders nothing extra when it has none (covers Pitfall 5)
- [ ] `tests/test_catalog.py` — "Добавить товар" absent from `/products` response text;
      `/products/new` (GET) still returns 200 (regression guard for the retained entry point)
- [ ] `tests/test_catalog.py` — delete control is an `<a ... hx-post=".../quick-delete"...>`,
      not a `<button>`, on the `/products` list

*(No framework install needed — pytest and httpx are already dev dependencies, unchanged from
Phase 18's validation doc.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single local operator, no auth in v1 (CLAUDE.md) — unchanged by this phase |
| V3 Session Management | no | No session state introduced |
| V4 Access Control | no | No new authorization boundary; this phase reuses the existing unauthenticated local-only routes |
| V5 Input Validation | yes (unchanged surface) | The only user input on this page (`code`/`name`/`category` filter strings, `page`/`sort`) is already validated/escaped by existing code (Jinja autoescape on filter values, `list_products_view`'s Python-side substring matching) — this phase adds no new input field |
| V6 Cryptography | no | Not applicable |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Reflected XSS via `Batch.name`/`Batch.comment`/`Batch.location` (operator-entered free text, stored at rest) | Tampering/Information Disclosure | Jinja2 autoescape only, **never** `\| safe` — the exact rule already stated in `batch_picker.html:22-23` ("untrusted stored text ... Jinja autoescape only, never `\|safe`") and `batch_card_picker.html:39-40`. The new batch-breakdown table must follow the identical rule since it renders the same fields. |
| Delete-link CSRF-adjacent risk (a GET-triggerable delete) | Tampering | Already mitigated structurally: `POST /products/{id}/quick-delete` is POST-only (FastAPI route decorator), and the new `<a>` never carries a real `href` to that URL — see Pitfall 2. No new mitigation needed, just don't regress it. |
| Category/code/name filter substring used to probe deleted or unauthorized data | Information Disclosure | Already mitigated: `list_products_view` filters `Product.deleted_at.is_(None)` before any substring match — unchanged by this phase. |

## Sources

### Primary (HIGH confidence — direct codebase inspection this session)
- `E:\dev\myorishop\app\routes\products.py` — full route module read, all six endpoints
- `E:\dev\myorishop\app\services\catalog.py` — full service module read, `list_products_view`/`create_product`/`quick_delete_product`
- `E:\dev\myorishop\app\services\batches.py` — full service module read, `open_batches`/`legacy_batch`
- `E:\dev\myorishop\app\models.py` — full model module read, `Product`/`Batch` field definitions
- `E:\dev\myorishop\app\templates\partials\product_rows.html`, `pages\products_list.html`, `pages\product_form.html`, `pages\categories.html`, `partials\batch_picker.html`, `partials\receipt_batch_chooser.html`, `mobile_partials\batch_card_picker.html`, `partials\warehouse_rows.html` — read in full
- `E:\dev\myorishop\app\static\style.css` — read for existing color tokens, button/link/table CSS, `.batch-picker`/WCAG comments
- `E:\dev\myorishop\tests\test_catalog.py` (1221 lines, read in full) and `tests\conftest.py` — existing test coverage and fixtures
- `uv run pytest tests/test_catalog.py -q` and `uv run pytest -q` — live baseline run, 2026-07-16 (61 passed / 711 passed respectively)
- `.planning/phases/18-two-price-model-consolidation/18-PATTERNS.md`, `18-VALIDATION.md` — house conventions (decision-ID comments, CSS token discipline, validation doc shape) from the immediately-preceding, already-shipped phase

### Secondary (MEDIUM confidence)
- None — no external documentation lookup was needed; this phase has zero new external
  dependencies and the entire research surface is this project's own codebase.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages, all versions already pinned and verified in `pyproject.toml`/CLAUDE.md
- Architecture: HIGH — every pattern recommended has a direct, cited in-repo precedent (batched query in `reports.py`, ordering in `batches.py`, CSS token discipline in `18-PATTERNS.md`)
- Pitfalls: HIGH — all five pitfalls are grounded in specific existing test names/fixtures/CSS comments found this session, not speculative

**Research date:** 2026-07-16
**Valid until:** effectively indefinite for the architectural findings (internal codebase facts don't go stale like external library docs) — re-verify only if Phase 18's shipped state changes before Phase 19 executes (unlikely; Phase 18 is fully merged per `18-UAT.md`/`18-VERIFICATION.md`/git log)
