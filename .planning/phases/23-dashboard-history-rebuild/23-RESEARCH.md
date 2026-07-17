# Phase 23: Dashboard & History Rebuild - Research

**Researched:** 2026-07-17
**Domain:** Server-rendered read-model rebuild (FastAPI + Jinja2 + HTMX) over an existing append-only ledger; one small new write path (active-catalog metadata)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Active catalog + close date (DASH-02)**
- **D-01: Fully manual** — both the catalog number and the close date are separate operator-entered fields, not derived from `scan_catalog_files()`'s PDF-filename scan.
- **D-02: Editing lives on the existing `/catalogs` page** (`app/routes/catalogs.py`, `app/services/catalogs.py`), not a new dedicated route and not under Настройки (doesn't exist until Phase 24).
- Empty state (no active catalog configured yet): the rest of the dashboard (DASH-01, 03, 04, 05) must still render independently — a missing catalog is a placeholder, not a blocking error.

**History type-first UX (HIST-01, HIST-02)**
- **D-03: Single `/history` route/page** — HTMX swaps both the row set AND the column set in place when a type is selected, extending `history_rows.html`'s existing swap-on-filter-change pattern. No new per-type routes. Existing pagination (`page_window`/`paginate`) and the `/history` URL/query-param contract stay intact.
- **D-04: Before a type is explicitly picked, show today's existing generic view** (10 fixed columns, all types combined) — type selection is an additional refinement, not a mandatory first gate.
- **D-05: The customer filter appears only for types that carry `Sale.customer_id` (sale, return); the category filter appears only where `Product.category` is meaningful; the date-range filter stays visible for every type.**
- **D-06: The type-first view and the recent-operations feed (DASH-05) cover the same 6 stock-affecting operation types** — `receipt, sale, writeoff, return, correction, transfer` (`STOCK_AFFECTING_TYPES` in `app/services/ledger.py`). The 3 audit-only types (`price_change`, `product_created`, `product_edited`) carry no `batch_id`/expiry/quantity/cost and are out of scope for type-first browsing.

**Dashboard totals & feed (DASH-03, DASH-04, DASH-05)**
- **D-07: "Expense" uses the same definition as Финансы** — cash-ledger withdrawals/returns (`cash_expense_total`), not cost-of-goods-sold.
- **D-08: The "profit" tile shows net profit** — gross profit + cash expense — the identical `net_profit_cents = gross + expense` formula already used by `app/routes/finance.py::_metrics_context` (addition, since `cash_expense_total` is already signed negative).
- **D-09: The day/week/month totals need a new service function generalizing `_metrics_context`'s single-period composition (`sales_profit_report` + `cash_expense_total` via `local_day_bounds_utc`) to 3 simultaneous periods.** The recent-operations feed reuses `recent_sales`'s Operation→Product join + Operation→Sale→Customer outerjoin shape, generalized from `type == "sale"` to all 6 `STOCK_AFFECTING_TYPES`, `limit=10` rows, each row linkable to `/history?type={op.type}&product={product.id}`. DASH-04's stock valuation reuses `stock_valuation()` as-is alongside a new "distinct product codes with quantity > 0" count query.

**Mobile scope (DASH/HIST on `/m/`)**
- **D-10: Mobile Главная and История get full data parity with desktop** — same service calls/data, rendered in mobile's own card/accordion layout, not a squeezed copy of desktop's tile grid/table. Closes the known pagination generation-gap — mobile history currently still uses the legacy `history_load_more.html` "load more" button instead of the numbered pagination desktop migrated to in Phase 14.

### Claude's Discretion
- Exact Russian field labels/placeholder text for the catalog-number/close-date fields on `/catalogs`, and the exact empty-state wording when no active catalog is configured.
- Exact card/accordion layout for the mobile dashboard tiles and the mobile per-type History cards.
- Whether the recent-operations feed is its own new service function or a generalized variant of `recent_sales` — implementation detail.
- Which sort options apply per operation type on the rebuilt History page (extending `history_view`'s existing sort allow-list per type).
- Whether the customer/category filter controls are hidden entirely or shown disabled/greyed for types where they don't apply (D-05) — as long as they never silently apply to a type they have no data for.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope across all 4 discussed areas (active catalog source, History type-first UX, dashboard totals/feed definition, mobile scope). No scope creep occurred.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DASH-01 | Home page shows current date, weekday, time | New `dashboard_view()` composes `datetime.now(ZoneInfo(settings.display_tz))`; no new query. Pure presentation, verified pattern already used in `reports.py::_resolve_period` and `reports.py::stale_products` (`today_local`). |
| DASH-02 | Home page shows active catalog number + days remaining | Requires a **new** `ActiveCatalog` table + Alembic migration (confirmed: no `Catalog` DB table exists today — `/catalogs` is a pure folder scan, see Common Pitfalls). Edit UI added to `/catalogs` page (D-02). Days-remaining = `(close_date - today_local).days`, mirrors `stale_products`'s day-diff idiom. |
| DASH-03 | Home page shows revenue/profit/expense totals for today/week/month | New `dashboard_metrics()` calls `sales_profit_report` + `cash_expense_total` (via `local_day_bounds_utc`) 3x, using the SAME Monday-start-week/calendar-month boundaries as `reports.py::_resolve_period` (do not invent different week/month math). |
| DASH-04 | Home page shows distinct product codes in stock + combined valuation | `stock_valuation()` reused as-is (verified in `finance_reports.py`). New count query: `count(Product) WHERE deleted_at IS NULL AND quantity > 0` — confirmed nothing existing computes this. |
| DASH-05 | Recent-operations feed, columns adapted per operation type | New feed query generalizing `recent_sales`'s `Operation→Product` join + `Operation→Sale→Customer` DOUBLE outerjoin (verified in `app/services/sales.py:332-352`) from `type == "sale"` to `Operation.type.in_(STOCK_AFFECTING_TYPES)`, `limit=10`. |
| HIST-01 | Type-first menu, type's relevant columns only | Extends `history_view` (`app/services/operations.py`) with a per-type column-set map; extends `history_rows.html`'s existing swap-on-filter-change (verified: `hx-target="#history-rows" hx-swap="outerHTML"`) to also swap columns. |
| HIST-02 | Filter by product code, date range, customer, category | `history_view` currently filters only `type_filter`/`product_id` (verified, no date/customer/category filters exist yet) — needs 3 new filter params + a Sale/Customer outerjoin (only when customer filter active) + a Product.category filter (`category_options()` already exists in `app/services/catalog.py` for the dropdown source). |
| HIST-03 | Sort by relevant columns | `history_view`'s `_SORT_MAP` currently has only `"oldest"` (verified) — extend per type, Claude's discretion on exact options. |
| HIST-04 | Paginated | Already implemented via `page_window`/`paginate` (Phase 14) on desktop; D-10 requires migrating mobile History off `history_load_more.html` onto the same numbered mechanism. |
</phase_requirements>

## Summary

This phase is a **read-model rebuild over an already-complete, already-correct data layer** — every number the dashboard and History need (sales/profit, cash expense, stock valuation, ledger rows) is already computed correctly by Phase 6/16/17's reporting services. The only genuinely new persisted state is the active-catalog number + close date (DASH-02), which requires a brand-new table and Alembic migration because — confirmed by reading `app/services/catalogs.py` and `app/models.py` — **there is currently no `Catalog` database table at all**; `/catalogs` is a pure filesystem scan (`scan_catalog_files()`) with zero stored metadata. Every other requirement is composition-and-presentation work: generalizing two existing single-purpose queries (`_metrics_context`'s single-period composition, `recent_sales`'s type-locked feed query) to multi-period and multi-type, and extending `history_view`'s existing filter/sort/paginate shape with 3 new filter dimensions and a per-type column map.

The critical risk this research surfaces that CONTEXT.md does not address: **mobile `/m/` currently has no persistent navigation bar** — `mobile_base.html` renders only a single `← Главная` back-link per page, and `/m/` itself is a static 10-tile grid that IS the only way to reach `/m/sales`, `/m/receipts`, `/m/writeoff`, etc. (verified: no bottom-tab-bar template exists; MOB-01's tab bar ships in Phase 24, not this phase). Replacing `/m/`'s tile grid outright with dashboard tiles would silently break mobile navigation to every other page until Phase 24 ships. The recommended resolution — new dashboard content ABOVE the existing 10-tile grid, not instead of it — is detailed in Common Pitfalls.

**Primary recommendation:** Build one new service module `app/services/dashboard.py` composing existing reporting functions (no ledger writes, no new report math); extend `app/services/operations.py::history_view` in place (new params, same function) rather than creating a parallel service; add one small new `ActiveCatalog` table via Alembic for DASH-02; keep the mobile home tile grid intact and add dashboard content above it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Date/time/catalog-countdown display (DASH-01/02) | API / Backend (route+service) | Browser (renders server HTML) | Server computes local time/day-diff once per request; no client-side clock needed (page reload gets a fresh timestamp — established pattern, no JS timer anywhere else in the app). |
| Period totals (DASH-03) | API / Backend | Database (aggregation) | `sales_profit_report`/`cash_expense_total` are SQL-side SUM aggregations; route only orchestrates 3 calls. |
| Stock valuation + distinct-code count (DASH-04) | API / Backend | Database | Same tier as `stock_valuation()` today (point-in-time, no period arg). |
| Recent-operations feed (DASH-05) | API / Backend | Database | Direct generalization of `recent_sales`'s join shape; SQL does the join/order/limit. |
| Active-catalog write (DASH-02 edit form) | API / Backend | Database (new table) | New table + service function on the write side, thin route on `/catalogs` (mirrors every other form in this codebase — routes never write directly, D-00c-style discipline is a house convention across `finance.py`, `sales.py`, `catalog.py`). |
| Type-first column/filter/sort swap (HIST-01..03) | API / Backend (query building) | Browser (HTMX swap target) | `history_view` builds the filtered/sorted/paginated query server-side; HTMX only swaps the returned HTML fragment — no client-side column-hiding logic (explicitly ruled out by D-03). |
| Pagination (HIST-04) | API / Backend | Browser (renders page-number bar) | `page_window`/`paginate` are pure Python helpers; already the established pattern for every list page. |
| Mobile presentation shape (D-10) | Browser / Client (templates only) | API / Backend (identical service calls to desktop) | D-10 explicitly locks "same data, own simpler layout" — mobile routes call the SAME service functions as desktop, only the Jinja templates differ. |

## Standard Stack

No new external packages are introduced by this phase. All work uses the existing project stack already locked in `CLAUDE.md` (FastAPI, SQLAlchemy 2.0 sync, Jinja2, HTMX 2.0.10, Alembic). `[VERIFIED: codebase]`

### Core (unchanged, reused)
| Library | Version (from CLAUDE.md) | Purpose in this phase |
|---------|---------|------------------------|
| SQLAlchemy | 2.0.51 | New `ActiveCatalog` model + queries generalizing `sales_profit_report`/`recent_sales`/`history_view` |
| Alembic | 1.18.5 | One new migration (`0016_active_catalog.py` or next sequential number) for DASH-02's table |
| Jinja2 / HTMX | 3.1.6 / 2.0.10 | Dashboard tiles + History column/filter swap-in-place |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| A new dedicated `ActiveCatalog` table | Reusing/extending `Dictionary` or adding columns to a settings-style global row | Rejected: no existing singleton-settings table exists in this schema; a new small table with the established UUID-PK/created_at/updated_at shape is the least-surprising fit, matching `Warehouse`'s minimal-table precedent. |
| Generalizing `history_view` in place | A parallel `history_view_v2` or per-type functions | Rejected by D-03 itself: "extends... not replaces", single route/function, no route fragmentation. |

**Installation:** No new packages — nothing to add to `pyproject.toml`.

**Version verification:** N/A — no new dependencies. Existing versions already verified in `CLAUDE.md`'s Sources section (dated 2026-07-08 to 2026-07-15).

## Package Legitimacy Audit

**Not applicable** — this phase introduces zero new external packages (npm/PyPI/crates or otherwise). All work is internal SQLAlchemy models, Alembic migrations, service functions, and Jinja templates using only already-installed, already-audited dependencies.

## Architecture Patterns

### System Architecture Diagram

```
Browser (desktop /  or mobile /m/)
        |
        | GET /  or  GET /m/
        v
+-------------------------+
| app/routes/home.py      |  <-- rebuilt: was ledger_view() stub
| app/routes/mobile_home  |      now calls dashboard service
+-------------------------+
        |
        v
+---------------------------------------------+
| app/services/dashboard.py  (NEW)             |
|  - now/today/catalog-countdown composition   |
|  - dashboard_metrics(): 3x local_day_bounds_ |
|    utc -> sales_profit_report + cash_expense_|
|    total  (today/week/month)                 |
|  - distinct-code-count + stock_valuation()   |
|  - recent_operations(limit=10): generalized  |
|    recent_sales() query over 6 STOCK_        |
|    AFFECTING_TYPES                           |
+---------------------------------------------+
        |                       |
        v                       v
+------------------+   +---------------------------+
| app/services/     |   | app/services/finance_     |
| reports.py         |   | reports.py                |
| sales_profit_report|   | cash_expense_total,       |
|                     |   | stock_valuation           |
+------------------+   +---------------------------+
        |                       |
        v                       v
              SQLite (operations, cash_movements, products)


GET /catalogs
        |
        v
app/routes/catalogs.py  --calls-->  app/services/catalogs.py (folder scan, unchanged)
        |                                    +
        |                          app/services/active_catalog.py (NEW)
        |                          get_active_catalog() / set_active_catalog()
        v
     ActiveCatalog table (NEW, 1 row) -- Alembic migration


GET /history  (type=&product=&sort=&page=&customer=&category=&date_from=&date_to=)
        |
        v
app/routes/history.py
        |
        v
app/services/operations.py :: history_view()  (EXTENDED, same function)
  - existing: type_filter, product_id, sort, page
  - NEW: customer_id filter (only sale/return: Operation.sale_id -> Sale.customer_id)
  - NEW: category filter (Product.category)
  - NEW: date_from/date_to filter (Operation.created_at, via local_day_bounds_utc)
  - NEW: per-type column-set selection (server picks which columns to render)
        |
        v
partials/history_rows.html  (EXTENDED: swaps column set, not just rows)
```

### Recommended Project Structure
```
app/
├── services/
│   ├── dashboard.py         # NEW: composes reports.py + finance_reports.py + sales.py-style feed query
│   ├── active_catalog.py    # NEW: get/set the single ActiveCatalog row (thin, mirrors catalog.py's small helpers)
│   └── operations.py        # EXTENDED: history_view() gains customer/category/date filters + per-type columns
├── routes/
│   ├── home.py               # REBUILT: dashboard_view() replaces ledger_view()
│   ├── mobile_home.py        # REBUILT: was static, now calls the SAME dashboard service
│   ├── history.py            # EXTENDED: new query params, same route
│   ├── mobile_history.py     # EXTENDED: adopt numbered pagination, add filters (D-10)
│   └── catalogs.py           # EXTENDED: GET/POST for the active-catalog edit form
├── templates/
│   ├── pages/home.html                    # REBUILT
│   ├── mobile_pages/home.html             # REBUILT (dashboard content ADDED above existing tile grid — see Pitfall 1)
│   ├── partials/history_rows.html         # EXTENDED (column set swap)
│   ├── partials/dashboard_tiles.html      # NEW (shared desktop; mobile gets its own card layout per D-10)
│   └── mobile_partials/history_cards.html # EXTENDED
alembic/versions/
└── 0016_active_catalog.py    # NEW migration (next sequential number after 0015)
```

### Pattern 1: Multi-period composition over a single-period report function
**What:** Call an existing single-period aggregation function N times with different `local_day_bounds_utc` inputs, rather than writing a new N-period SQL query.
**When to use:** DASH-03's today/week/month totals — exactly what `_metrics_context` already does once; this phase does it 3x.
**Example:**
```python
# Source: app/routes/finance.py::_metrics_context (existing, verified) — generalize this shape
from app.core import local_day_bounds_utc
from app.services.reports import sales_profit_report
from app.services.finance_reports import cash_expense_total

def _period_metrics(session, start_day, end_day, tz_name):
    start_iso, end_iso = local_day_bounds_utc(start_day, end_day, tz_name)
    gross = sales_profit_report(session, start_iso, end_iso)
    expense = cash_expense_total(session, start_iso, end_iso)
    return {
        "revenue_cents": gross["totals"]["revenue_cents"],
        "gross_profit_cents": gross["totals"]["profit_cents"],
        "expense_cents": expense,                                   # already negative
        "net_profit_cents": gross["totals"]["profit_cents"] + expense,  # D-08: addition, never subtraction
    }
```
Reuse `app/routes/reports.py::_resolve_period`'s week/month boundary math (Monday-start week, calendar month via `(month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)`) for consistency — do not invent different boundaries for the dashboard (see Common Pitfalls).

### Pattern 2: Generalizing a type-locked join to a type-set join
**What:** `recent_sales` hardcodes `Operation.type == "sale"`; the new feed needs `Operation.type.in_(STOCK_AFFECTING_TYPES)`.
**When to use:** DASH-05's feed.
**Example:**
```python
# Source: app/services/sales.py::recent_sales (existing, verified lines 332-352) — generalize the WHERE clause only
from app.services.ledger import STOCK_AFFECTING_TYPES

rows = session.execute(
    select(Operation, Product, Customer)
    .join(Product, Operation.product_id == Product.id)
    .outerjoin(Sale, Operation.sale_id == Sale.id)      # MUST stay outer (walk-in sales, and every non-sale type: sale_id is NULL)
    .outerjoin(Customer, Sale.customer_id == Customer.id)  # MUST stay outer
    .where(Operation.type.in_(STOCK_AFFECTING_TYPES))
    .order_by(Operation.created_at.desc(), Operation.seq.desc())
    .limit(10)
).all()
```

### Pattern 3: Per-type column set for HIST-01
**What:** A Python dict mapping each of the 6 `STOCK_AFFECTING_TYPES` to its relevant column list, driving both the `<thead>` and the filter-row rendering.
**When to use:** HIST-01's type-first column narrowing.
**Example:**
```python
# NEW — no existing precedent, but mirrors OPERATION_TYPE_LABELS' dict-of-constants shape (app/models.py)
HISTORY_TYPE_COLUMNS = {
    "receipt":    ["when", "code", "name", "expiry", "qty", "cost"],
    "sale":       ["when", "code", "name", "expiry", "qty", "cost", "price", "profit", "customer"],
    "writeoff":   ["when", "code", "name", "expiry", "qty", "cost", "reason"],
    "return":     ["when", "code", "name", "expiry", "qty", "cost", "price", "profit", "customer"],
    "correction": ["when", "code", "name", "expiry", "qty", "note"],
    "transfer":   ["when", "code", "name", "expiry", "qty", "from_warehouse", "to_warehouse"],
}
```
Note: `transfer` writes TWO `Operation` rows per move (one negative from the source batch, one positive to the dest batch — verified in `app/services/transfers.py:144-159`, no `payload` field set). Neither row alone carries "from/to warehouse" — that must be resolved from each row's own `Batch.warehouse_id` at read time (join `Batch`, which `history_view` already does). Flag this as a column-mapping subtlety for the planner: a transfer's two history rows are NOT symmetric in what they can show without the batch join already in place.

### Anti-Patterns to Avoid
- **Hand-rolling week/month boundaries for the dashboard that differ from `_resolve_period`'s Monday-start/calendar-month convention** — would make Финансы/Отчёты and Главная disagree on "this week"'s numbers for the same underlying data.
- **Client-side (CSS/JS) column hiding for HIST-01** — explicitly ruled out by D-03; the server must render only the relevant `<th>`/`<td>` set.
- **Treating `cash_expense_total`'s return value as needing negation before combining with gross profit** — it is already signed negative; combine with `+`, never `-` (D-08, documented gotcha in `finance_reports.py` and `finance.py`).
- **Building a brand-new /catalogs edit form/route** — D-02 explicitly says extend the existing page.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Week/month boundary math | A new date-range calculator for the dashboard | `app/routes/reports.py::_resolve_period`'s preset logic (import or replicate its exact Monday-start/calendar-month formulas) | Two different "this week" definitions across pages is a direct UX inconsistency bug — DASH-03 says "current week/month" without specifying which convention; the only existing convention in this codebase IS `_resolve_period`'s. |
| Page-number pagination bar | A second numbered-pagination implementation for mobile History | `app/services/pagination.py::page_window`/`paginate` (already the sole sanctioned helper per its own docstring: "no list may hand-roll its own... math") | D-10 explicitly closes this exact gap — mobile History currently uses the OLDER `history_load_more.html` pattern that predates Phase 14's numbered pagination; don't perpetuate it, don't invent a third pagination style. |
| Distinct-code-in-stock count | A Python-side loop over all products counting quantity>0 | SQL `select(func.count()).select_from(Product).where(Product.deleted_at.is_(None), Product.quantity > 0)` | Matches the existing SQL-side-aggregation convention used everywhere in `finance_reports.py`/`stock.py` — never a Python accumulator for a value SQL can compute directly. |
| Customer/category filter dropdowns | New autocomplete/search widgets | `app/services/customers.py::search_customers(session, q)` (existing, used by SALE-04's customer picker) and `app/services/catalog.py::category_options(session)` (existing, used by PROD-08's category filter) | Both already exist and are already wired into other forms in this exact codebase — reuse verbatim. |

**Key insight:** Nearly everything this phase needs already exists in some single-purpose form (one period, one operation type, one filter dimension). The actual engineering work is *generalizing cardinality* (1 period → 3, 1 type → 6, 2 filters → 5) on top of already-correct SQL, not inventing new aggregation logic. The highest-risk hand-roll temptation is re-deriving week/month boundaries or re-inventing pagination — both already have a single sanctioned implementation in this codebase.

## Common Pitfalls

### Pitfall 1: Mobile `/m/` has no persistent nav bar — rebuilding it into a dashboard can strand every other mobile page
**What goes wrong:** `app/templates/mobile_base.html` (verified) renders only `{% block back %}<a class="mobile-back" href="/m/">← Главная</a>{% endblock %}` — there is no bottom tab bar, no side menu, nothing else. `/m/` itself (`app/templates/mobile_pages/home.html`, verified) is currently a static 10-tile grid of links (`/m/sales`, `/m/receipts`, `/m/search`, `/m/writeoff`, `/m/corrections`, `/m/transfers`, `/m/history`, `/m/reports/expiry`, `/m/finance`, `/m/finance/report`) — this grid IS the only navigation surface reaching those pages from mobile. MOB-01 (the tab-bar requirement) ships in **Phase 24**, not this phase.
**Why it happens:** D-10 says mobile Главная gets a full rebuild into "an operational dashboard... rendered in mobile's own card/accordion layout" and explicitly rejects "a squeezed copy of desktop's tile grid" — read literally this could mean the 10 navigation tiles are removed/replaced by dashboard tiles.
**How to avoid:** The dashboard content (date/time, catalog countdown, day/week/month totals, valuation, recent-ops feed) should be ADDED to `/m/` — above, or in a new accordion section on, the existing 10-link tile grid — not IN PLACE OF it. This satisfies D-10 (mobile gets full dashboard data parity, own simpler layout) without breaking navigation to every other mobile page for one milestone (until Phase 24's MOB-01 ships a proper tab bar).
**Warning signs:** A plan/task that says "replace mobile_pages/home.html's tile grid with dashboard tiles" without also re-adding equivalent links somewhere on the same page.

### Pitfall 2: No `Catalog` database table exists — DASH-02 is not a UI-only change
**What goes wrong:** Assuming `/catalogs`'s existing `get_catalog()`/`list_catalogs()` functions can just grow two new fields.
**Why it happens:** `/catalogs` looks like a normal CRUD page from the UI, but `app/services/catalogs.py`'s own module docstring states "there is NO catalog metadata table" — every catalog descriptor is synthesized per-request from `scan_catalog_files()` (a folder scan) plus `Dictionary.catalogs` (product membership, unrelated to this phase). Confirmed by reading `app/models.py` in full: no `Catalog` class exists.
**How to avoid:** DASH-02 needs (a) a new `ActiveCatalog` SQLAlchemy model, (b) a new Alembic migration (next sequential number after `0015_customer_contacts.py`, i.e. `0016_...`), (c) a small new service module or functions for get/set, (d) new form fields + POST handler on `/catalogs`. This is schema-affecting work, not a template change.
**Warning signs:** A plan task that touches only `app/templates/pages/catalogs.html` for DASH-02.

### Pitfall 3: `cash_expense_total` sign convention (recurring codebase gotcha, not new to this phase)
**What goes wrong:** Subtracting `cash_expense_total`'s return value from gross profit, producing double-negative (inflated) net profit.
**Why it happens:** The value is already stored/summed as negative (withdrawals negative, deposits/returns... actually only withdrawal+return categories are summed here, both negative-signed rows per `CASH_BUCKETS`).
**How to avoid:** `net_profit_cents = gross_profit_cents + cash_expense_total(...)` — verified identical in both `app/routes/finance.py::_metrics_context` and `app/routes/mobile_finance.py::_metrics_context`. D-08 locks this exact formula for the new dashboard's profit tile.
**Warning signs:** Any `- expense` or `abs(expense)` in the new dashboard service.

### Pitfall 4: Walk-in sales/returns have NULL `sale_id`/`customer_id` — both join hops must stay OUTER
**What goes wrong:** Using `.join()` (inner) instead of `.outerjoin()` anywhere in the `Operation → Sale → Customer` chain silently drops every walk-in sale AND every non-sale/return operation type (receipt, writeoff, correction, transfer all have `sale_id IS NULL` by construction — verified in `record_operation`'s signature, `sale_id` defaults to `None` and only `sales.py`/`returns.py` ever pass it) from the recent-operations feed.
**Why it happens:** `recent_sales`'s existing code already got this right (its docstring calls this out explicitly: "Both hops MUST stay outerjoin... Do not 'simplify' to `.join`"), but DASH-05 generalizes the WHERE clause from one type to six — it's easy to also "clean up" the join type while touching this code.
**How to avoid:** Copy the exact double-outerjoin shape verbatim (see Pattern 2 above); do not touch the join type when generalizing the WHERE clause.
**Warning signs:** A feed that shows zero rows for receipt/writeoff/correction/transfer types, or one that silently omits walk-in sales.

### Pitfall 5: Ambiguity in what happens to the 3 audit-only types (`price_change`, `product_created`, `product_edited`) on the rebuilt History page
**What goes wrong:** D-06 explicitly scopes "type-first browsing" (bespoke per-type columns) to the 6 `STOCK_AFFECTING_TYPES` and calls the 3 audit types "out of scope," but does not say whether those 3 types remain selectable in the type filter dropdown at all.
**Why it happens:** The existing `history_rows.html` filter dropdown (verified) iterates ALL of `OPERATION_TYPE_LABELS` (9 entries, including the 3 audit types) — HIST-01's rebuild must decide whether to keep offering all 9 in the dropdown (falling back to the current generic 10-column render for the 3 audit types) or narrow the dropdown to only the 6 stock-affecting types (audit types then only visible via the untype-filtered "all types combined" default view, per D-04).
**How to avoid:** Recommend (not locked by CONTEXT.md — flag for planner/discuss if ambiguity needs resolving): keep all 9 types in the dropdown for backward compatibility; selecting one of the 3 audit types renders the EXISTING generic 10-column table unchanged (no new per-type column set for those 3); only the 6 stock-affecting types get the new narrowed column set. This preserves 100% of current functionality while adding the new behavior only where D-06 scopes it.
**Warning signs:** A plan that removes `price_change`/`product_created`/`product_edited` from the type filter entirely (functionality regression — these types are how the operator currently audits price changes and product creation via `/history`).

### Pitfall 6: `transfer` operations write TWO ledger rows per move, with no `payload`
**What goes wrong:** Assuming a `transfer` row alone can show "from warehouse → to warehouse" the way a `sale` row alone shows its price/cost.
**Why it happens:** `app/services/transfers.py::register_transfer` (verified lines 144-159) calls `record_operation` twice per transfer — once with a negative `qty_delta` against the source `Batch`, once with a positive `qty_delta` against the destination `Batch` — and sets no `payload` on either row. The warehouse identity is only recoverable via each row's own `Batch.warehouse_id` (already joined by `history_view`, since it outerjoins `Batch`).
**How to avoid:** The `transfer` column set (HIST-01/DASH-05) should read warehouse info from the joined `Batch.warehouse_id`, not expect a payload field; each of the two rows shows only its own side (source row shows "from", dest row shows "to" — or both rows show their own batch's warehouse with a directional cue like ± qty already does).
**Warning signs:** A plan referencing `op.payload.from_warehouse` or similar for transfer rows — `transfer` ops carry no payload at all.

### Pitfall 7: `Operation.qty_delta` for `receipt`/`sale`/`writeoff`/`return`/`correction`/`transfer` is SIGNED — don't re-derive "quantity" as always-positive without checking type
**What goes wrong:** Displaying a raw negative quantity for a writeoff/sale row without the existing `+`/no-sign convention (`history_rows.html` already handles this: `{% if r.op.qty_delta > 0 %}+{{ }}{% else %}{{ }}{% endif %}`).
**How to avoid:** Reuse the existing sign-aware rendering, don't reinvent it per operation type.

## Code Examples

### Existing single-period metrics composition (generalize, don't replace)
```python
# Source: app/routes/finance.py::_metrics_context (verified, lines 69-99)
def _metrics_context(session: Session, from_: str, to: str) -> dict:
    period = _resolve_period(from_, to, settings.display_tz)
    metrics = None
    if not period["error"]:
        start_iso, end_iso = local_day_bounds_utc(
            period["from_date"], period["to_date"], settings.display_tz
        )
        gross = sales_profit_report(session, start_iso, end_iso)
        expense = cash_expense_total(session, start_iso, end_iso)
        metrics = {
            "gross_profit_cents": gross["totals"]["profit_cents"],
            "cost_unknown_count": gross["totals"]["cost_unknown_count"],
            "net_profit_cents": gross["totals"]["profit_cents"] + expense,
        }
    valuation = stock_valuation(session)
    ...
```

### Existing history_view signature to extend (verified, app/services/operations.py:23-31)
```python
def history_view(
    session: Session,
    *,
    type_filter: str | None = None,
    product_id: str | None = None,
    sort: str = "",
    page: int = 0,
    page_size: int = LIST_PAGE_SIZE,
) -> dict:
    # HIST-02 needs 3 new kwargs here: customer_id, category, date_from/date_to
    # HIST-01 needs the returned dict to also carry the resolved column-set for
    # the active type_filter (or None -> caller falls back to the generic 10-col set)
```

### Existing Alembic migration shape to follow for the new ActiveCatalog table
```python
# Source: alembic/versions/0015_customer_contacts.py (verified, adapt table/columns)
def upgrade() -> None:
    op.create_table(
        "active_catalog",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("number", sa.String(20), nullable=True),
        sa.Column("close_date", sa.String(10), nullable=True),  # ISO yyyy-mm-dd, mirrors Batch.expiry
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_active_catalog")),
    )
```

## State of the Art

Not applicable in the usual "library X moved to Y" sense — this is an internal codebase evolution, not an ecosystem-tracking question. The one relevant internal "old approach → current approach" shift:

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Mobile lists use a `has_next` sentinel + "Показать ещё" load-more button (`history_load_more.html`, `cash_history_load_more.html`) | Desktop lists use numbered `page_window`/`paginate` pagination | Phase 14 (desktop only) | D-10 explicitly migrates mobile History (but NOT mobile Финансы — that stays load-more, confirmed by `mobile_finance.py`'s own comment "NOT the desktop numbered pagination bar (Pitfall 7)") onto numbered pagination this phase — a deliberate, scoped exception to the established mobile-load-more precedent. Don't assume this phase migrates mobile Финансы too; it explicitly doesn't (out of scope). |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | New `ActiveCatalog` table should be a UUID-PK singleton row (mirroring `Warehouse`'s minimal-table shape) rather than a key-value settings table | Architecture Patterns / Code Examples | Low — this is Claude's-discretion-adjacent implementation detail; a key-value table would also work, just less consistent with existing table conventions in this schema. |
| A2 | The 3 audit-only operation types (`price_change`, `product_created`, `product_edited`) should stay selectable in History's type dropdown, falling back to the current generic 10-column view | Pitfall 5 | Medium — if the planner instead narrows the dropdown to 6 types, the operator loses the ability to filter History down to just price changes / product creation events, a currently-working feature. Recommend confirming with the operator during planning/discuss if not already settled. |
| A3 | `transfer`'s two per-move rows should each show only their own side's warehouse (via `Batch.warehouse_id`), not a synthesized "from → to" single-row summary | Pitfall 6 | Low — cosmetic; either rendering is achievable from the same joined data, but a "from → to" summary would require correlating the two sibling rows (same product, opposite-signed qty, same timestamp), which `history_view`'s per-row pagination model doesn't naturally support without extra work. |

## Open Questions (RESOLVED)

1. **Should the mobile dashboard replace or supplement the existing 10-tile navigation grid on `/m/`?**
   - What we know: D-10 says "full data parity... own simpler layout, never a reduced data set" for the DATA; it does not explicitly address the navigation tiles, which are a structural/navigational element, not dashboard data.
   - What's unclear: Whether "own simpler layout" implies removing the tile grid.
   - Recommendation: Supplement (dashboard content above/around the existing tile grid) — see Pitfall 1. This is the only option that doesn't regress mobile navigation before Phase 24 ships MOB-01's tab bar. If the planner disagrees, this should go back through `/gsd-discuss-phase` rather than being decided silently in a plan.
   - RESOLVED: Supplement, never replace — implemented in Plan 23-07 Task 2 (`mobile_pages/home.html`), which appends dashboard content below the untouched 10-tile nav grid and adds a structural regression test (`tests/test_mobile_home.py`) asserting the grid's last tile textually precedes the new «Показатели» heading (T-23-19).

2. **Exact per-type column list for `correction` and `receipt` in HIST-01/DASH-05.**
   - What we know: `correction`'s payload carries `{"note": ..., "mode": "count"|...}` (verified `app/services/corrections.py:122-125`); `receipt` carries no special payload beyond the standard cost/batch fields (verified `app/services/receipts.py`).
   - What's unclear: Whether `correction`'s mode (`Пересчёт` vs `Изменение`) should be a dedicated column or folded into the existing free-text "Причина"-style column (as `history_rows.html` already does today).
   - Recommendation: Reuse the existing `history_rows.html` rendering logic for this cell (`{{ "Пересчёт" if r.op.payload.mode == "count" else "Изменение" }}{% if note %} — {{ note }}{% endif %}`) verbatim inside whatever narrower correction-specific column set is built — don't re-derive this formatting.
   - RESOLVED: Recommendation adopted verbatim — implemented in Plan 23-02 Task 2's `HISTORY_TYPE_COLUMNS` constant, which reuses the existing `history_rows.html` reason/mode rendering logic rather than introducing new column vocabulary; no dedicated mode column was added.

## Environment Availability

Not applicable — this phase has no external tool/service/runtime dependencies beyond the already-installed project stack (Python/FastAPI/SQLAlchemy/SQLite/Alembic, all already verified present and in use by the existing test suite).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x (`[VERIFIED: pyproject.toml]` — `pytest==9.1.*`, `testpaths = ["tests"]`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_history.py tests/test_mobile_home.py tests/test_finance_reports.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | Home shows date/weekday/time | unit (service) + route smoke | `uv run pytest tests/test_home.py -x` | ❌ Wave 0 (no `test_home.py` today — `test_mobile_home.py` exists with 1 test, verified) |
| DASH-02 | Active catalog number + days-remaining; empty state renders without error | unit (new `active_catalog` service) + Alembic upgrade/downgrade round-trip | `uv run pytest tests/test_active_catalog.py -x`; `uv run alembic upgrade head && uv run alembic downgrade -1` | ❌ Wave 0 |
| DASH-03 | Revenue/profit/expense correct for today/week/month, including the D-08 sign convention | unit (mirrors `test_finance_reports.py`'s 38 existing cases) | `uv run pytest tests/test_dashboard.py -k metrics -x` | ❌ Wave 0 |
| DASH-04 | Distinct product-code count + valuation match manual SUM | unit | `uv run pytest tests/test_dashboard.py -k valuation -x` | ❌ Wave 0 |
| DASH-05 | Feed columns adapt per type; walk-in sale shows no customer; non-sale rows never crash on missing customer/price | unit + route smoke (mirrors `recent_sales`'s existing outerjoin test precedent in `tests/test_sales.py`) | `uv run pytest tests/test_dashboard.py -k feed -x` | ❌ Wave 0 |
| HIST-01 | Selecting a type swaps BOTH rows and columns; unselected default keeps the current generic 10-column view | route/e2e (`test_web_` prefix convention, verified in `tests/test_history.py`'s own docstring) | `uv run pytest tests/test_history.py -k test_web_type_columns -x` | ❌ Wave 0 (extend existing 12-test file) |
| HIST-02 | Product/date/customer/category filters compose correctly (AND semantics); customer/category filters absent-or-inert for types they don't apply to | unit + route | `uv run pytest tests/test_history.py -k filter -x` | ❌ Wave 0 (extend existing file) |
| HIST-03 | Sort options per type produce correctly-ordered results | unit | `uv run pytest tests/test_history.py -k sort -x` | ❌ Wave 0 (extend existing file — currently only "oldest" is tested) |
| HIST-04 | Pagination correct on both desktop and mobile after the mobile load-more → numbered migration | unit + route (mirrors `tests/test_pagination.py` + `tests/test_mobile_history.py`) | `uv run pytest tests/test_pagination.py tests/test_mobile_history.py -x` | ✅ (extend existing files) |

### Sampling Rate
- **Per task commit:** targeted `-k` subset above for the requirement being implemented.
- **Per wave merge:** `uv run pytest tests/test_dashboard.py tests/test_history.py tests/test_mobile_history.py tests/test_mobile_home.py tests/test_active_catalog.py`
- **Phase gate:** `uv run pytest` (full suite) green before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_home.py` — new file, covers DASH-01/DASH-05 desktop route smoke (no such file exists today — verified only `test_mobile_home.py` exists, with 1 test).
- [ ] `tests/test_active_catalog.py` — new file, covers the new `ActiveCatalog` model + service + `/catalogs` form round-trip + Alembic migration.
- [ ] `tests/test_dashboard.py` — new file, covers `dashboard_metrics()`/`stock_valuation` composition/feed generalization (money-math correctness, sign convention, join correctness).
- [ ] Extend `tests/test_history.py` (currently 12 tests) — new filter/sort/column-set cases.
- [ ] Extend `tests/test_mobile_history.py` — numbered-pagination migration cases (currently load-more-shaped).
- [ ] Framework install: none — pytest/httpx already installed and in use project-wide.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Single local operator, no auth in v1 (per `CLAUDE.md` constraints — unchanged this phase) |
| V3 Session Management | No | No sessions in v1 |
| V4 Access Control | No | No multi-user/role concept exists |
| V5 Input Validation | Yes | New History query params (`customer`, `category`, `date_from`, `date_to`) must follow the SAME allow-list/membership-check discipline `history_view` already uses for `type_filter` (verified: `if type_filter and type_filter in OPERATION_TYPES` — never string-interpolated into `order_by()`/raw SQL, per the existing `_SORT_MAP.get(sort, default)` pattern). New `date_from`/`date_to` params must go through `date.fromisoformat` + the SAME `local_day_bounds_utc` conversion already used everywhere else (`reports.py::_resolve_period`'s malformed/inverted-range fallback-to-today pattern is the established precedent to copy, not reinvent). New active-catalog number/close-date form fields need the same string-trim + `date.fromisoformat` validation as every other form in this codebase (`to_cents`-style bounded-exception discipline). |
| V6 Cryptography | No | No crypto/secrets touched this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unvalidated `sort`/`type`/`category` query param interpolated into `order_by()`/`WHERE` | Tampering | Allow-list membership check before use (`value in ALLOWED_SET`), exactly as `history_view`'s existing `_SORT_MAP.get(sort, _DEFAULT_ORDER)` and `type_filter in OPERATION_TYPES` already do — extend this pattern to the new `category`/`customer_id` params rather than trusting raw query-string values in a filter clause. |
| Malformed/out-of-range `date_from`/`date_to` causing a 500 or an inverted-range query | Denial of Service (minor, local single-user) | Bounded exception handling identical to `_resolve_period` — malformed dates fall back to "today" with an inline RU error, never raise past the route boundary. |
| Stored XSS via unescaped catalog number / close-date free text | Tampering/Information Disclosure | Jinja2 autoescaping is already the project-wide default (verified: every existing template relies on autoescape, `\|safe` is explicitly never used per multiple docstring comments, e.g. `history_rows.html`'s "Autoescape only... NEVER \|safe") — new catalog fields need no special handling beyond NOT adding `\|safe` anywhere, consistent with existing convention. |

## Sources

### Primary (HIGH confidence — read directly from the codebase this session)
- `app/services/finance_reports.py` — `cash_expense_total`, `stock_valuation` (exact signatures/sign convention)
- `app/services/reports.py` — `sales_profit_report`, `stale_products` (day-diff idiom)
- `app/routes/finance.py`, `app/routes/mobile_finance.py` — `_metrics_context` (exact D-08 formula, desktop/mobile parity precedent, and the explicit "NOT the desktop numbered pagination bar" mobile-Финансы exception)
- `app/services/sales.py` — `recent_sales` (exact double-outerjoin shape + its own "do not simplify to `.join`" warning)
- `app/services/operations.py`, `app/routes/history.py`, `app/templates/partials/history_rows.html` — `history_view` current signature/filters/sort/columns
- `app/services/pagination.py` — `page_window`, `paginate` (LIST_PAGE_SIZE=20, sanctioned-single-implementation docstring)
- `app/services/ledger.py` — `record_operation`, `STOCK_AFFECTING_TYPES`
- `app/services/catalogs.py`, `app/routes/catalogs.py` — confirmed NO `Catalog` DB table exists (pure folder scan)
- `app/models.py` — full model inventory (confirmed no `Catalog`/`ActiveCatalog` table; `OPERATION_TYPES`, `OPERATION_TYPE_LABELS`)
- `app/services/transfers.py` — confirmed two-row-per-transfer, no payload
- `app/services/corrections.py`, `app/services/receipts.py` — payload shapes for `correction`/`price_change`/`product_created`
- `app/services/customers.py` — `search_customers` (reusable for HIST-02 customer filter)
- `app/services/catalog.py` — `category_options`, `list_products_view` (reusable for HIST-02 category filter; confirms no existing "distinct codes in stock" count)
- `app/templates/mobile_base.html`, `app/templates/mobile_pages/home.html` — confirmed no persistent mobile nav bar beyond the tile grid on `/m/`
- `app/routes/reports.py::_resolve_period` — Monday-start-week/calendar-month boundary convention
- `alembic/versions/0015_customer_contacts.py` — most recent migration, exact style to follow for the new table
- `app/config.py` — `settings.display_tz`, `operator_name`, `device_id`, `low_stock_threshold`, `stale_days` confirmed
- `pyproject.toml` — pytest 9.1.x, `testpaths = ["tests"]` confirmed
- `.planning/config.json` — `nyquist_validation: true`, `security_enforcement: true`, `security_asvs_level: 1` confirmed; all external search-tool flags (`brave_search`, `exa_search`, `tavily_search`, `ref_search`, `perplexity`, `jina`, `firecrawl`) confirmed `false` — no external research tooling available or needed this session (100% internal codebase evidence, matching CONTEXT.md's own instruction to "go deeper" into named files rather than re-derive from external sources)

### Secondary / Tertiary
None — every claim in this document is either read directly from the codebase this session (`[VERIFIED: codebase]`) or is an explicit recommendation flagged `[ASSUMED]` in the Assumptions Log above. No web search was performed or needed (all external-search config flags are `false`, and the phase is 100% internal composition work).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all versions already verified in `CLAUDE.md`.
- Architecture: HIGH — every referenced function/table/template was read directly this session; the one genuinely new piece (`ActiveCatalog` table) follows an exact, verified precedent (`0015_customer_contacts.py`).
- Pitfalls: HIGH for Pitfalls 2-7 (all directly evidenced by reading the referenced files); MEDIUM for Pitfall 1 (the mobile-nav-stranding risk is a reasoned inference from `mobile_base.html`'s structure, not something CONTEXT.md explicitly flagged — worth a planner/operator confirmation).

**Research date:** 2026-07-17
**Valid until:** Stable until the next schema/route change touching `app/services/operations.py`, `app/routes/catalogs.py`, or `app/templates/mobile_base.html` — no external time-based decay (internal codebase research, not ecosystem-version research).
