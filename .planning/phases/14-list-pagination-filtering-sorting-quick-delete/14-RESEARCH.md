# Phase 14: List Pagination, Filtering, Sorting & Quick Delete - Research

**Researched:** 2026-07-14
**Domain:** Server-rendered HTMX/Jinja2 list ergonomics over a single-operator SQLite app (FastAPI + SQLAlchemy 2.0)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Page-number style pagination (1 2 3 … Next) uniformly across ALL list pages — not "load more".
- **D-02:** History's existing "Показать ещё" (load-more) pattern is replaced with page-number pagination too. Requires a total-count query alongside the existing offset pagination in `app/services/operations.py`.
- **D-03:** Page size is a single constant across all lists: **20 rows per page**. Applies to products, warehouses, customers, dictionary, catalogs, and history alike.
- **D-04:** Filter inputs/selects live **inside the table header row** (per-column), not a single search box above the table and not a separate filter panel. Column filterability per list is left to research/planning.
- **D-05:** Filters apply immediately on input (debounce), matching the existing `hx-trigger="input changed delay:300ms..."` pattern — no "Apply" button.
- **D-06:** Sorting UI is a **"Сортировать по…" dropdown** near/above the table — not clickable column headers.
- **D-07:** Default order (nothing selected) matches each list's CURRENT default: products/customers by name, warehouses active-first, dictionary by code, history newest-first (`created_at desc, seq desc`), catalogs newest-first by year.
- **D-08:** NEW guard — product quick-delete from the list is **blocked if the product has stock on hand > 0**. Did not exist before this phase; introduced specifically for the quick-delete list action.
- **D-09:** Confirmation is a **browser-native `confirm()`** dialog before the delete request is sent.
- **D-10:** After successful product delete, the row **disappears from the list entirely** (unchanged final outcome — only the swap mechanism changes, see Integration Points).
- **D-11:** NEW guard — warehouse quick-delete is blocked if the warehouse **still has stock on hand** (mirrors D-08).
- **D-12:** The new "must be empty" guard applies **together with** the existing last-active-warehouse guard (`app/services/warehouses.py:76-102`) — BOTH conditions must pass. Neither guard replaces the other.
- **D-13:** Confirmation is the same browser-native `confirm()` as products (D-09).
- **D-14:** **Behavior change:** after quick-delete from the list, the warehouse row **disappears from the list entirely** — no longer stays visible grayed-out with an inline restore button. Restore path (if any) is not decided — flagged as an open question.

### Claude's Discretion
- Exact filterable columns per list (beyond what's implied by existing search behavior).
- Exact sort options offered in each "Сортировать по…" dropdown per list.
- Whether/how a restore path for quick-deleted warehouses should be preserved elsewhere (see D-14) — flag as an open question for planning; not to be silently dropped without a decision.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| LIST-01 | Every list page supports pagination | See "Pagination Strategy per List" — a shared `paginate()`/`page_window()` helper module, plus `partials/pagination.html` from the UI-SPEC, applied per-list with either SQL LIMIT/OFFSET+COUNT or Python-side slicing depending on cardinality. |
| LIST-02 | Every list page supports filtering on its relevant columns | See "Filterable Columns per List" and "Cyrillic-Safe Filtering" — per-list column candidates and the `_lc` shadow-column pattern already established for `Product.name_lc`/`Customer.search_lc`. |
| LIST-03 | Every list page supports sorting on its relevant columns | See "Sort Options per List" and the allow-list `sort` param pattern (never string-interpolate a column name into `order_by()`). |
| LIST-04 | Delete a warehouse directly from the list | See "Warehouse Quick Delete" — this is an EXTENSION of the existing `soft_delete_warehouse`/`/warehouses/{id}/delete`, not a new endpoint. New stock guard runs FIRST, before the existing last-active guard. |
| LIST-05 | Delete a product directly from the list | See "Product Quick Delete" — this is a NEW `quick_delete_product` service function + NEW `/products/{id}/quick-delete` route, separate from the existing (unchanged) `/products/{id}/delete` used by the edit page. |
</phase_requirements>

## Summary

This is a cross-cutting infrastructure phase with an unusually complete UI-SPEC (`14-UI-SPEC.md`) that already pins down markup shape, copy, CSS, and five interaction contracts (A–E). The remaining planning work is almost entirely **backend/service-layer**: deciding how each of the six lists sources its paginated/filtered/sorted rows, and wiring the two new delete guards into the correct (and different!) call sites.

A live query against `data/myorishop.db` shows the six lists have wildly different cardinality: **dictionary has 6,856 rows**, while products (7), warehouses (2), customers (4), and batches (8) are tiny. History is an append-only ledger (23 rows today, unbounded by design) and catalogs is not a DB table at all (a folder scan of PDFs, grouped by year). This size gap is the single most important research finding: a uniform SQL-LIMIT/OFFSET+COUNT implementation is correct for dictionary and history, but Python-side filter/sort/slice (already the established precedent for `list_warehouses`, per its own docstring: "Cardinality is small... so sorting in Python after fetch") is simpler and sufficient for products/warehouses/customers/catalogs, and avoids adding Cyrillic-safe `_lc` shadow columns (and their migrations) to entities that don't need them for performance.

The two quick-delete requirements are structurally asymmetric in the existing code, which the UI-SPEC's Contract D/E already reflects but is easy to miss: **products** need a brand-new endpoint and service function (the existing `/products/{id}/delete` stays untouched, used only by the edit page, no new guard), while **warehouses** need the EXISTING `soft_delete_warehouse`/`/warehouses/{id}/delete` extended with a new stock check that runs before the existing last-active-warehouse check.

**Primary recommendation:** Build one shared `app/services/pagination.py` (page-size constant + page-window helper + a generic Python-side `paginate()` for small lists), extend `operations.py`'s existing offset pattern with a total-count query for history, add SQL LIMIT/OFFSET+COUNT plus a new `Dictionary.name_lc` shadow column (with a Python-side backfill, not raw SQL `lower()`) for dictionary, and do Python-side filter/sort/paginate for products, warehouses, customers, and catalogs. Add `quick_delete_product` as a new function/route; extend `soft_delete_warehouse` in place.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Pagination (page math, LIMIT/OFFSET or slicing) | API/Backend (`app/services/*.py`) | — | All six lists are server-rendered; page state lives in query params, computed server-side per request. No client-side pagination logic. |
| Per-column filtering | API/Backend (`app/services/*.py`) | Browser (debounced `hx-get`) | Filter values arrive as query params via HTMX; matching/validation happens server-side (ORM `.where()` or Python list comprehension). The browser only debounces the trigger. |
| Sorting | API/Backend (`app/services/*.py`) | — | Sort key is an allow-listed string mapped to an `order_by()` expression or Python `key=` function server-side — never client-side. |
| Quick delete (guards + soft-delete write) | API/Backend (`app/services/catalog.py`, `app/services/warehouses.py`) | — | Both new stock guards are pure business-rule checks over `Product.quantity` / `SUM(Batch.quantity)` — belong entirely server-side, consistent with the existing `soft_delete_warehouse` guard. |
| Row-level UI (pagination bar, filter row, sort select, delete button) | Frontend Server (Jinja2 templates) | Browser (HTMX swap) | Server renders the full markup; HTMX only swaps `outerHTML`/`innerHTML` fragments returned by the server — no client-side templating. |

## Standard Stack

No new libraries. This phase is pure application code within the existing stack (FastAPI 0.139, SQLAlchemy 2.0, Jinja2 3.1, htmx 2.0.10, vanilla CSS) as locked in `CLAUDE.md`. No `npm install`/`uv add` is required.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy 2.0 | 2.0.51 (pinned in `pyproject.toml`) | `func.count()`, `.limit()`, `.offset()` for the SQL-side lists (dictionary, history) | Already the project's ORM; `func.count()...select_from(...)` pattern already used in `app/services/warehouses.py:92-96`. |
| Alembic | 1.18.5 (pinned) | ONE new migration: `Dictionary.name_lc` shadow column (see Cyrillic-Safe Filtering) | Only DB schema change this phase plausibly needs; `render_as_batch=True` already configured for SQLite. |

### Supporting
None beyond what's already installed.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Python-side filter/sort/paginate for products/warehouses/customers/catalogs | Uniform SQL LIMIT/OFFSET+COUNT for all six lists | Simpler mental model (one pattern everywhere) but forces 3-4 new `_lc` shadow-column migrations (`Warehouse.name_lc`/`address_lc`, `Customer.surname_lc`, `Product.category_lc`) for entities with single-digit row counts today — pure overhead for lists this small. Rejected as premature optimization; flagged as an open question below in case the operator expects thousands of products/customers. |

**Installation:** None — no new packages.

**Version verification:** Not applicable — no new dependencies. Existing pinned versions (`fastapi==0.139.*`, `sqlalchemy==2.0.*`, `alembic==1.18.*`) confirmed current via `pyproject.toml` (already verified HIGH confidence in `CLAUDE.md`'s Sources section, dated 2026-07-08).

## Package Legitimacy Audit

Not applicable — this phase introduces zero external packages. All work is new Python modules/functions and Jinja2 template changes within the existing dependency set.

## Architecture Patterns

### System Architecture Diagram

```
Browser (table with header-row filters + "Сортировать по…" select + pagination bar)
   │  debounced hx-get (filter input / sort change / pagination click)
   │  query params: page, sort, <per-column filter keys>
   ▼
FastAPI route (e.g. GET /products, GET /dictionary, GET /warehouses, GET /catalogs, GET /history, GET /customers)
   │  is_hx = bool(request.headers.get("HX-Request"))
   │
   ├─► app/services/<entity>.py  list/search/filter function
   │      ├─ SQL-side (dictionary, history):
   │      │    .where(<allow-listed filters>).order_by(<allow-listed sort map>).limit(20).offset(page*20)
   │      │    + a separate func.count() query for total_pages
   │      └─ Python-side (products, warehouses, customers, catalogs):
   │           fetch all active rows → Python filter (case-insensitive via .lower())
   │           → Python sort (key=) → app/services/pagination.py: paginate(rows, page, 20)
   │
   ▼
Jinja2 TemplateResponse
   ├─ is_hx=True  → chrome-less partial (rows + partials/pagination.html), swapped into #<entity>-rows
   └─ is_hx=False → full page (nav + filter-row table + partials/pagination.html), for reload/bookmark/shared URL
```

### Recommended Project Structure
```
app/
├── services/
│   ├── pagination.py        # NEW — LIST_PAGE_SIZE=20, page_window(), paginate() for Python-side lists
│   ├── operations.py        # EXTEND — history_view() gains sort param + a total-count query (D-02)
│   ├── catalog.py           # EXTEND — list_products() gains filter/sort/page; NEW quick_delete_product()
│   ├── warehouses.py        # EXTEND — list_warehouses() gains filter/sort/page; soft_delete_warehouse() gains stock guard
│   ├── customers.py         # EXTEND — customer_search_view() or a new list function gains per-column filter/sort/page
│   ├── dictionary.py        # EXTEND — list_entries() becomes SQL LIMIT/OFFSET+COUNT with filter/sort
│   └── catalogs.py          # EXTEND — list_catalogs() gains year filter + sort + Python-side pagination
├── templates/
│   └── partials/
│       └── pagination.html  # NEW — shared partial from UI-SPEC Contract A
alembic/versions/
└── 0012_dictionary_name_lc.py   # NEW — adds Dictionary.name_lc, Python-side backfill (not raw SQL lower())
```

### Pattern 1: Shared pagination helper (avoid six divergent implementations)
**What:** One `app/services/pagination.py` module providing `LIST_PAGE_SIZE = 20`, `page_window(page, total_pages, spread=2) -> list[int | str]` (returns page indices with `'…'` markers for the Contract A template), and `paginate(rows: list, page: int) -> tuple[list, int, int]` (slice + total + total_pages) for the four Python-side lists.
**When to use:** Every list service that needs page-number pagination — SQL-side lists use `LIST_PAGE_SIZE` for their own `.limit()`/`.offset()` and compute `total_pages` from their own `COUNT`, but should still call the SAME `page_window()` helper so the pagination bar's ellipsis logic is identical everywhere.
**Example:**
```python
# app/services/pagination.py — new module, no existing precedent to cite;
# based on the standard "clamp + 2-either-side + ellipsis" pagination window
# algorithm (a well-known pattern, not vendor-specific).
LIST_PAGE_SIZE = 20


def page_window(page: int, total_pages: int, spread: int = 2) -> list[int | str]:
    """0-based page indices to render, with '…' markers for gaps."""
    if total_pages <= 1:
        return [0] if total_pages == 1 else []
    pages = {0, total_pages - 1}
    pages.update(range(max(0, page - spread), min(total_pages, page + spread + 1)))
    ordered = sorted(pages)
    result: list[int | str] = []
    prev = None
    for p in ordered:
        if prev is not None and p - prev > 1:
            result.append("…")
        result.append(p)
        prev = p
    return result


def paginate(rows: list, page: int) -> tuple[list, int, int]:
    """Python-side slice for small lists; clamps page into [0, total_pages-1]."""
    total = len(rows)
    total_pages = max(1, -(-total // LIST_PAGE_SIZE))  # ceil div
    page = max(0, min(page, total_pages - 1))
    start = page * LIST_PAGE_SIZE
    return rows[start : start + LIST_PAGE_SIZE], total, total_pages
```

### Pattern 2: Allow-listed sort keys (never string-format into `order_by()`)
**What:** Each list service maps its dropdown's `sort` value to a fixed `order_by()` expression (SQL-side) or a Python `key=` function (Python-side) via a dict lookup, defaulting to the list's D-07 current behavior for an unknown/empty value.
**When to use:** Every list's `sort` query param — mirrors the existing `type_filter` allow-list check in `history_view` (`if type_filter and type_filter in OPERATION_TYPES`).
**Example:**
```python
# Source: app/services/operations.py:39 (existing precedent for allow-listing
# an untrusted query param before using it in a query)
_SORT_MAP = {
    "name_desc": Product.name.desc(),
    "code": Product.code.asc(),
}


def list_products(session, *, sort: str = "", ...):
    stmt = select(Product).where(Product.deleted_at.is_(None))
    stmt = stmt.order_by(_SORT_MAP.get(sort, Product.name.asc()))  # D-07 default
    ...
```

### Anti-Patterns to Avoid
- **String-interpolating a column name into `order_by(f"{col} {direction}")`:** even though SQLAlchemy Core ultimately parameterizes values, building `ORDER BY` clauses from unvalidated strings is a well-known injection-adjacent anti-pattern. Always map through a fixed dict (Pattern 2).
- **Raw SQL `lower()` for a Cyrillic-safe shadow-column backfill:** SQLite's `lower()`/`LIKE` fold ASCII only (already documented as D-27 in `app/services/catalog.py`). A migration that does `UPDATE dictionary SET name_lc = lower(name)` will silently produce wrong results for every Cyrillic name. Backfill in Python (see Common Pitfalls).
- **Treating `/products/{id}/quick-delete` and `/warehouses/{id}/delete` as symmetric implementations:** they are not (see Product/Warehouse Quick Delete sections below) — copying one pattern onto the other will either duplicate the warehouse delete endpoint unnecessarily or silently skip the product's new guard.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pagination page-window / ellipsis math | A bespoke implementation per list template | The single `page_window()` helper (Pattern 1) | Six independent implementations of the same "1 2 3 … 8" logic is exactly the kind of duplication that causes off-by-one bugs in exactly one of the six lists later. |
| Cyrillic case-insensitive filtering | `func.lower()` in SQL on a raw Cyrillic column | The already-established `_lc` shadow-column pattern (`Product.name_lc`, `Customer.search_lc`), Python-lowered at write time | SQLite's `lower()`/`LIKE` are ASCII-only (documented D-27); this has already bitten the project once and the workaround is a locked, tested convention — do not reinvent it. |
| Total-row counting for SQL-paginated lists | A second full `SELECT *` and `len()` in Python | `select(func.count()).select_from(...)` with the SAME `.where()` filters as the row query | Already the exact pattern used in `soft_delete_warehouse`'s active-count check (`app/services/warehouses.py:92-96`) — reuse it, don't invent a new counting idiom. |

**Key insight:** This phase touches six lists with three different underlying data-access shapes (ORM query, folder scan, append-only ledger). The temptation is to write six bespoke pagination/filter/sort implementations matching each list's existing code. Resist that for the page-window math and the count-query shape (both are genuinely identical across all six); do NOT resist it for filter/sort semantics (those are correctly list-specific, per D-04/D-06's "left to research/planning" wording).

## Common Pitfalls

### Pitfall 1: Backfilling a new `_lc` shadow column with raw SQL
**What goes wrong:** A migration for `Dictionary.name_lc` (recommended below) that runs `op.execute("UPDATE dictionary SET name_lc = lower(name)")` will silently mis-fold every Cyrillic dictionary name (SQLite `lower()` is ASCII-only), producing broken filter results discovered only when an operator searches a Cyrillic name and gets nothing.
**Why it happens:** It looks like the "obvious" one-line migration; the ASCII-only limitation is not visible until tested with real Cyrillic data.
**How to avoid:** Backfill in a Python migration step: `for row in session.execute(select(Dictionary)): row.name_lc = row.name.lower()` (or an equivalent batched Python loop), mirroring how the SERVICE layer already maintains `name_lc`/`search_lc` going forward.
**Warning signs:** A migration file containing SQL `lower(...)` applied to any column that can contain non-ASCII text.

### Pitfall 2: Unclamped `page` query param causing a negative OFFSET or an out-of-range slice
**What goes wrong:** The existing `history_page` route accepts `page: int = 0` directly from the query string with no clamping — a malformed/stale bookmarked URL (`?page=-1` or `?page=99999`) either raises a SQLite error (negative OFFSET) or silently returns an empty page with no "back to page 1" affordance. This phase touches five more list routes with the same shape.
**Why it happens:** `page` looks like a trusted internal value because the pagination bar only ever generates valid values — until the URL is bookmarked, shared, or hand-edited (which `hx-push-url="true"` explicitly enables per the UI-SPEC).
**How to avoid:** Clamp `page` server-side into `[0, total_pages - 1]` in every list service (the `paginate()` helper in Pattern 1 already does this for Python-side lists; do the equivalent for the SQL-side dictionary/history queries after computing `total_pages` from the count query).
**Warning signs:** A list route that passes the raw `page` query param straight into `.offset(page * page_size)` without a preceding clamp.

### Pitfall 3: Assuming warehouse quick-delete is a new endpoint (like products)
**What goes wrong:** Building a `/warehouses/{id}/quick-delete` route mirroring the new product route duplicates `soft_delete_warehouse`/`/warehouses/{id}/delete`, which already IS the list's inline delete action (there is no separate warehouse edit page — `app/services/warehouses.py`'s docstring: "this backs a single settings-style page... every write response re-renders `partials/warehouse_rows.html` in place"). The UI-SPEC's Contract E is explicit: "no change needed to that copy or mechanism" — only the guard logic and the post-success row-removal behavior change.
**Why it happens:** LIST-04 and LIST-05 read as parallel requirements, and the product side genuinely does need a new endpoint, making the warehouse side look like it should too.
**How to avoid:** Extend `soft_delete_warehouse` in place with the new stock check as the FIRST check (before the existing `active_count <= 1` check), and change `warehouse_rows.html`'s row-rendering loop to stop rendering `deleted_at`-set rows (D-14) — no new route.
**Warning signs:** A plan task titled "add POST /warehouses/{id}/quick-delete".

### Pitfall 4: Product quick-delete accidentally reusing `soft_delete_product`/`/products/{id}/delete` unchanged
**What goes wrong:** The opposite of Pitfall 3 — wiring the new "Удалить" button in `product_rows.html` to the EXISTING `/products/{id}/delete` endpoint means the new D-08 stock guard never runs (that endpoint has none today and is also used by the edit page, where changing its behavior would be an unplanned scope change), and the response is a full-page `HX-Redirect` rather than the partial-swap row removal Contract D specifies.
**Why it happens:** The endpoint already exists and already does "soft delete + redirect to /products" — reusing it looks like the smallest change.
**How to avoid:** Add a new `quick_delete_product(session, product_id) -> tuple[bool, dict]` service function (return shape mirrors `soft_delete_warehouse`'s `(deleted, blocked_info)` tuple) and a new `POST /products/{id}/quick-delete` route that re-renders `partials/product_rows.html` (or the paginated rows partial) instead of issuing `HX-Redirect`. Leave `soft_delete_product`/`/products/{id}/delete` untouched.
**Warning signs:** A plan task that says "add the stock guard to `soft_delete_product`" (that function is also called from a hypothetical future direct-delete path and has no natural place to surface a blocked-with-quantity response back to a list row).

### Pitfall 5: Catalogs' year-grouped rendering breaking under naive pagination
**What goes wrong:** `pages/catalogs.html` renders a `<h2>{{ c.year }}</h2><table>...</table>` block per year using a `namespace` tracker that assumes the FULL, contiguous, pre-sorted list is iterated in one pass (`{% if not loop.first %}</tbody></table>{% endif %}` / `{% if loop.last %}</tbody></table>{% endif %}`). Naively slicing this list to a 20-row page BEFORE the year-grouping loop runs can leave an unclosed `</table>` if a page boundary falls mid-year, or silently repeat a year heading across pages (usually harmless, but the current template's `loop.first`/`loop.last` logic assumes it owns the WHOLE list, not a slice).
**Why it happens:** Catalogs is the only one of the six lists that is not a flat table — it has no existing `catalog_rows.html` partial or `#catalog-rows` wrapper id to swap either.
**How to avoid:** Paginate the flat, pre-sorted `catalogs` list FIRST (`paginate(list_catalogs(session), page)`), THEN run the existing year-grouping template loop over just that page's slice — the `loop.first`/`loop.last` markers will then correctly open/close per PAGE rather than per full list, which is exactly the desired per-page table structure. Extract the loop into a new `partials/catalog_rows.html` wrapped in `<div id="catalog-rows">` so it can be an HTMX swap target (mirrors `#product-rows`/`#customer-rows`).
**Warning signs:** A plan task for catalogs pagination that doesn't mention extracting a `catalog_rows.html` partial, or that describes catalogs identically to the other five (flat-table) lists.

### Pitfall 6: The two now-superseded search routes leaking through
**What goes wrong:** `GET /products/search` and `GET /customers/search` already exist and are still linked to from `products_list.html`/`customers_list.html`'s standalone `<input type="search">` boxes. D-04 explicitly rejects "a single search box above the table" in favor of per-column header-row filters — if the plan adds header-row filters WITHOUT removing the old search box and its route, the page ends up with two competing, out-of-sync filtering mechanisms.
**Why it happens:** The old search input is easy to leave in place since removing it isn't explicitly one of the five success criteria.
**How to avoid:** CONTEXT.md's Integration Points section already flags this ("the standalone `q` search inputs... are superseded... retiring them is in scope for this phase, not a parallel addition") — treat the standalone search box removal as an explicit task, and fold `/products/search`'s query/filter logic into the main `/products` route (is_hx pattern) rather than keeping both routes alive.
**Warning signs:** `products_list.html`/`customers_list.html` still containing the old `<input type="search" hx-get="/products/search" ...>` after this phase.

## Code Examples

### Existing total-count pattern to reuse for history/dictionary (Source: `app/services/warehouses.py:91-97`)
```python
active_count = session.scalar(
    select(func.count())
    .select_from(Warehouse)
    .where(Warehouse.deleted_at.is_(None))
)
```
Apply the same shape to `history_view` and `list_entries`, with the SAME `.where()` filter clauses as the paginated row query, so the count matches the filtered set (not the whole table).

### Existing allow-list guard for an untrusted filter param (Source: `app/services/operations.py:39`)
```python
if type_filter and type_filter in OPERATION_TYPES:
    stmt = stmt.where(Operation.type == type_filter)
```
Mirror this shape for every new select-based column filter (e.g. a warehouse `status` filter with values `"active"`/`"deleted"`/`""`).

### Existing warehouse-level stock query — does NOT exist yet, needs to be added (mirrors `app/services/returns.py:55` shape)
```python
# NEW — app/services/warehouses.py, for the D-11 stock guard.
# Product.quantity is a cached TOTAL across all warehouses (models.py:113-114
# comment), so it cannot be reused for a per-warehouse check — a fresh
# SUM(Batch.quantity) scoped to warehouse_id is required.
from sqlalchemy import func, select
from app.models import Batch

warehouse_stock = session.scalar(
    select(func.coalesce(func.sum(Batch.quantity), 0)).where(
        Batch.warehouse_id == warehouse_id
    )
)
```

### Product stock guard — Product.quantity is ALREADY the total (Source: `app/models.py:113-114`)
```python
# NEW — app/services/catalog.py, for the D-08 guard. No new query needed;
# Product.quantity is documented as "cached projection of SUM(operations.qty_delta)".
if product.quantity > 0:
    return False, {"blocked_qty": product.quantity}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| History: offset pagination with a `has_next` sentinel, no total count, "Показать ещё" button | Page-number pagination with a real total-count query | This phase (D-02) | `history_view` gains a `func.count()` query; `page_size` default changes 50 → 20 (D-03); `history_load_more.html`/`history_response.html` are retired in favor of the shared `partials/pagination.html`. |
| Products/customers: standalone `q` search box + separate `/search` GET route | Per-column header-row filters on the main list route, is_hx dual-response (mirrors history.py) | This phase (D-04) | `/products/search` and `/customers/search` become redundant (Pitfall 6) — fold into `/products`/`/customers`. |
| Warehouses: deleted rows always visible, grayed out, with a restore button | Deleted rows disappear from the list entirely after quick-delete | This phase (D-14) | `warehouse_rows.html`'s `{% if w.deleted_at %} class="muted"{% endif %} {% else %} restore button {% endif %}` branch is removed for the list render; existing test `test_web_deleted_warehouse_stays_visible_with_restore` in `tests/test_warehouses.py:194` will need to be updated or replaced to match the new behavior. |

**Deprecated/outdated:**
- `history_load_more.html` / the `oob`-swap `<tfoot>` load-more control: superseded by the shared pagination partial (D-02).
- `warehouse_rows.html`'s "stays visible with restore" branch: superseded for the list view by D-14 (restore path elsewhere is an open question, not resolved).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Products, warehouses, customers, and catalogs will remain small enough (low hundreds at most, for a single reseller) that Python-side filter/sort/paginate is performant and appropriate, vs. SQL LIMIT/OFFSET+COUNT for all six lists uniformly | Standard Stack (Alternatives Considered), Architecture Patterns | If the operator's product catalog or customer base grows into the thousands, Python-side full-table scans on every filtered/sorted request become a real (though still probably sub-100ms locally) cost; would need a follow-up migration to SQL-side pagination for whichever list actually grows. Confirm expected list sizes with the user before planning locks this in. |
| A2 | Adding a `Dictionary.name_lc` shadow column (new Alembic migration) is the right fix for Cyrillic-safe dictionary name filtering, rather than accepting ASCII-only fold or doing full Python-side filtering of all 6,856 rows per request | Standard Stack, Recommended Project Structure | If the planner instead chooses Python-side filtering for dictionary (consistent with products/warehouses/customers), no migration is needed but every filter keystroke does a 6,856-row Python scan — likely still fast enough locally, but untested; flag for a quick benchmark during planning/execution if chosen. |
| A3 | The "restore a quick-deleted warehouse" path can be safely left unresolved for THIS phase per D-14's explicit "flag as open question" instruction, rather than blocking planning | User Constraints, Open Questions | If left fully unresolved, `restore_warehouse`/`/warehouses/{id}/restore` becomes dead code with no UI entry point — acceptable per CONTEXT.md's explicit framing, but the plan should record this as a deliberate, named decision (e.g. "no restore UI in this phase; `restore_warehouse` intentionally orphaned pending a future 'Показать удалённые' toggle") rather than an oversight. |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Is there a restore path for quick-deleted warehouses after this phase, or is `restore_warehouse` intentionally orphaned?**
   - What we know: `restore_warehouse` and `POST /warehouses/{id}/restore` already exist and work; D-14 removes the ONLY current UI path to them (the grayed-out restore button in the list).
   - What's unclear: Whether the planner should add a lightweight "Показать удалённые" toggle/select-filter (natural fit with D-04's per-column filter row — a `status` select with `"Все склады"/"Активные"/"Удалённые"` options, where selecting "Удалённые" shows the existing restore button again) or leave restore unreachable in v1.2, deferring a proper UI to a later milestone.
   - Recommendation: Surface this explicitly to the user during planning/discuss rather than deciding silently either way — CONTEXT.md marks it "not to be silently dropped." A `status` filter select is the lowest-effort option that reuses 100% existing restore machinery, and fits D-04's "warehouses (name, address, active/deleted — new select)" filter candidate list already noted in the UI-SPEC's Contract B.

2. **Should the product-list "Название" sort actually differ from the default, given the list is also filterable by category?**
   - What we know: D-07 locks the DEFAULT (name A→Я); D-06/CONTEXT leaves the non-default OPTIONS to planning.
   - What's unclear: Whether operators would find a category-grouped or price-sorted view more useful than a simple Я→А reverse-alpha option.
   - Recommendation: Keep the non-default sort set minimal for v1.2 (reverse-alpha + code) per the UI-SPEC's illustrative example (`"Название (Я→А)"`), and treat richer sort options as a possible small follow-up rather than scope-creeping this phase.

## Filterable Columns per List (Claude's Discretion, recommended)

| List | Filter columns (per-column header-row inputs) | Rationale |
|------|------------------------------------------------|-----------|
| Products | code (text), name (text), category (text) | Mirrors existing `search_products` fields (code prefix + name substring) plus the existing `category_options()` datalist source; category as free-text input (not select) matches the existing datalist UX rather than introducing a new select control. |
| Warehouses | name (text), address (text), status (select: `Все склады`/`Активные`/`Удалённые`) | name/address are the only two data columns; status select doubles as the D-14 restore-path answer (Open Question 1). |
| Customers | name (text), surname (text), consultant_number (text) | Matches the three fields already combined in `Customer.search_lc`; splitting into independent per-column filters requires Python-side `.lower()` comparison per field (no per-field shadow columns needed since filtering is Python-side, see Standard Stack). |
| Dictionary | code (text), name (text) | Only two columns exist; code filter can use `func.lower(Dictionary.code)` (ASCII-safe, already precedented in `catalog.search_products`), name filter needs the new `name_lc` shadow column (see Pitfall 1). |
| Catalogs | year (select, populated from `list_catalogs()`'s distinct years) | The only structured/filterable dimension besides free-text label; catalogs has no "name" field to text-filter, and there's no DB query to add a `WHERE` clause to — the select narrows the in-memory list before pagination. |
| History | type (select, existing), product (select, existing) — unchanged | Already implemented in `history_filters.html`; this phase only needs to MOVE these two selects from the standalone `.filter-bar` into the header-row shape per D-04 (Contract B explicitly calls this out), not add new filter columns. |

## Sort Options per List (Claude's Discretion, recommended)

| List | Default (D-07, unchanged) | Additional options |
|------|---------------------------|---------------------|
| Products | Название (А→Я) | Название (Я→А), Код (А→Я) |
| Warehouses | Активные сначала | Название (А→Я), Название (Я→А) |
| Customers | Имя (А→Я) | Фамилия (А→Я), Номер консультанта |
| Dictionary | Код (по возрастанию) | Название (А→Я) |
| Catalogs | Сначала новые (по году/номеру) | Сначала старые |
| History | Сначала новые | Сначала старые |

## Environment Availability

Not applicable — no external tools, services, or runtimes beyond what's already installed and verified in `CLAUDE.md` (Python 3.13, uv, the existing SQLite database file at `data/myorishop.db`). This phase is pure application code.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (`pyproject.toml` `[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Config file | `pyproject.toml` |
| Quick run command | `uv run pytest tests/test_warehouses.py tests/test_catalog.py tests/test_history.py tests/test_customers.py tests/test_dictionary.py tests/test_catalogs_feature.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIST-01 | Every list paginates 20/page, page-number UI | integration | `uv run pytest tests/test_history.py::test_history_pagination -x` (existing pattern to extend/copy per list) | ✅ partial (history only) — ❌ Wave 0 for products/warehouses/customers/dictionary/catalogs |
| LIST-02 | Per-column filters narrow rows | integration | `uv run pytest tests/test_history.py -k filter -x` (existing pattern to extend/copy per list) | ✅ partial (history only) — ❌ Wave 0 for the other five |
| LIST-03 | Sort dropdown reorders rows, default unchanged | integration | new tests per list, e.g. `uv run pytest tests/test_catalog.py -k sort -x` | ❌ Wave 0 for all six lists |
| LIST-04 | Warehouse quick-delete: stock guard + last-active guard both enforced, row disappears on success | unit + integration | `uv run pytest tests/test_warehouses.py -k delete -x` | ⚠️ Wave 0 — existing `test_delete_last_active_warehouse_warns_then_allows` covers the OLD guard only; new stock-guard test and updated success-behavior test (replacing `test_web_deleted_warehouse_stays_visible_with_restore`, `tests/test_warehouses.py:194`) needed |
| LIST-05 | Product quick-delete: stock guard, browser confirm, partial row removal | unit + integration | `uv run pytest tests/test_catalog.py -k delete -x` | ❌ Wave 0 — no existing quick-delete test; `soft_delete_product` currently has no stock guard test at all |

### Sampling Rate
- **Per task commit:** the relevant single test file (`uv run pytest tests/test_<entity>.py -x`)
- **Per wave merge:** `uv run pytest tests/test_warehouses.py tests/test_catalog.py tests/test_history.py tests/test_customers.py tests/test_dictionary.py tests/test_catalogs_feature.py`
- **Phase gate:** `uv run pytest` (full suite) green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Pagination test coverage for products, warehouses, customers, dictionary, catalogs (only history has one today — `tests/test_history.py:67`)
- [ ] Filter test coverage for products, warehouses, customers, dictionary, catalogs (only history has one today — `tests/test_history.py:107`)
- [ ] Sort test coverage for all six lists (none exist today)
- [ ] `tests/test_catalog.py` — new tests for `quick_delete_product` (blocked-with-stock case, success case, idempotent-on-already-deleted case)
- [ ] `tests/test_warehouses.py` — new test for the D-11 stock guard on `soft_delete_warehouse`, and an update/replacement for `test_web_deleted_warehouse_stays_visible_with_restore` (`tests/test_warehouses.py:194`) which currently asserts the OLD grayed-out-with-restore behavior that D-14 changes
- [ ] `tests/test_catalogs_feature.py` — check whether this file already covers `list_catalogs`/`catalog_detail`; likely needs new pagination/filter/sort tests

*(Framework and fixtures already exist — `tests/conftest.py` provides `session`, `client`, `product`, `stocked_product`, `batch` fixtures used throughout the existing list tests; no new fixture infrastructure is anticipated.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single local operator, no auth in v1 (explicit `CLAUDE.md` constraint: "1 operator in year one — no auth complexity needed in v1"). |
| V3 Session Management | No | Same as above — no sessions exist. |
| V4 Access Control | No | Same as above. |
| V5 Input Validation | Yes | `page`/`sort`/per-column filter query params must be validated server-side: `page` clamped to `[0, total_pages-1]` (Pitfall 2), `sort` mapped through a fixed allow-list dict (Pattern 2), filter text values passed only into parameterized ORM `.where()`/`.contains()` calls or Python string comparisons — never raw SQL string formatting. |
| V6 Cryptography | No | No new cryptographic operations in this phase. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via a `sort`/filter query param | Tampering | SQLAlchemy ORM `.where()`/`.order_by()` with parameterized values only; sort keys resolved through a fixed Python dict (Pattern 2), never string-interpolated into `order_by()`. |
| Reflected/stored XSS via a filter value or a deleted-product name echoed back in an error message | Tampering / Information Disclosure | Jinja2 autoescape is the project default (already relied on throughout — e.g. `product_rows.html`'s explicit comment: "Pattern 5: segments are autoescaped... NEVER `|safe`"); continue that convention for the new "Нельзя удалить: на остатке {{ qty }} шт." error strings. |
| Confused deputy via an unclamped `page`/`confirm` param crafted into a bookmarked/shared URL | Tampering | `page` clamping (Pitfall 2); the warehouse `confirm=1` override param already only skips the WARN state, never the (new, in this phase) hard stock-guard block — D-11/D-12 explicitly make the stock guard non-overridable, unlike the last-active guard. |

## Sources

### Primary (HIGH confidence)
- `E:\dev\myorishop\.planning\phases\14-list-pagination-filtering-sorting-quick-delete\14-CONTEXT.md` — locked decisions and existing-code integration points, gathered 2026-07-14.
- `E:\dev\myorishop\.planning\phases\14-list-pagination-filtering-sorting-quick-delete\14-UI-SPEC.md` — verified interaction contracts A–E, copy, CSS.
- `app/services/operations.py`, `app/services/warehouses.py`, `app/services/catalog.py`, `app/services/customers.py`, `app/services/dictionary.py`, `app/services/catalogs.py`, `app/services/batches.py`, `app/services/stock.py` — read directly, this session.
- `app/models.py` — read directly, this session (Product.quantity cached-total comment, Batch.quantity per-batch comment, Dictionary/Customer schema).
- `app/routes/products.py`, `app/routes/warehouses.py`, `app/routes/history.py`, `app/routes/customers.py`, `app/routes/dictionary.py`, `app/routes/catalogs.py` — read directly, this session.
- `app/templates/partials/*.html`, `app/templates/pages/*.html` for the six lists — read directly, this session.
- `app/static/style.css` — read directly, this session (confirms `.filter-bar`, `button.secondary`, `button.danger`, `.error`, `.error-block`, `.empty-state`, `.muted`, `.num`, focus-visible rules already exist as UI-SPEC claims).
- Live row counts from `data/myorishop.db` via direct sqlite3 query, this session: products=7, warehouses=2, customers=4, dictionary=6856, operations=23, batches=8. **[VERIFIED: local sqlite live query]**
- `tests/conftest.py`, `tests/test_warehouses.py`, `tests/test_history.py` — read directly, this session (existing fixture/test shape).
- `alembic/versions/` directory listing — read directly, this session (migration naming convention `NNNN_description.py`, latest is `0011_catalog_prices.py`).
- `pyproject.toml` — read directly, this session (pytest/ruff config, pinned dependency versions).

### Secondary (MEDIUM confidence)
None used — all findings this session were verified directly against the codebase or the two upstream planning documents (CONTEXT.md, UI-SPEC.md), which themselves cite exact file:line locations.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all patterns cited to exact existing file:line locations in this codebase.
- Architecture: HIGH — the per-list SQL-vs-Python pagination split is grounded in a live row-count query, not a guess; the two quick-delete asymmetries are read directly from `14-UI-SPEC.md`'s Contracts D/E.
- Pitfalls: HIGH — every pitfall traces to either an existing documented convention (D-27 Cyrillic-fold), an existing test that will break (`test_web_deleted_warehouse_stays_visible_with_restore`), or an existing template structural assumption (`catalogs.html`'s `loop.first`/`loop.last` grouping).

**Research date:** 2026-07-14
**Valid until:** 30 days (stable internal codebase, no external dependency drift risk)
