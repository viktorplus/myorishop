# Phase 6: Reports & Data Export - Research

**Researched:** 2026-07-10
**Domain:** Read-only SQL reporting over an existing append-only ledger (SQLAlchemy 2.0 / SQLite) + CSV export (Python stdlib `csv`) inside an established FastAPI + Jinja2 + htmx app
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Preset buttons (Сегодня / Неделя / Месяц) pre-fill an editable "с/по" (from/to) date range — one code path always: two date query params. User can adjust the dates after clicking a preset. (Chosen over a mode-toggle radio and over plain date-inputs-only.)
- **D-02:** **Local-day boundary correctness is mandatory regardless of UI**: operations are stored as UTC ISO text (`Operation.created_at`); "day/week/month" boundaries MUST be computed by converting local midnight (via `ZoneInfo(settings.display_tz)`, same tz already used by `iso_to_local`) to UTC before filtering — never slice the UTC string by date directly, or evening sales shift into the wrong day's report.
- **D-03:** **Separate page per report type** (e.g. `/reports/sales`, `/reports/stock`, `/reports/writeoffs`, `/reports/products`), each with its own nav entry — matches the existing project convention of one route+template+nav-link per capability (`/receipts`, `/sales`, `/writeoff`, `/returns`, `/corrections`, `/history`). (Chosen over one unified dashboard and over a single tabbed HTMX page.) The stock/low-stock report (RPT-02) does not need a period selector at all — keeping it a separate page avoids mixing period-based and non-period reports on one screen.
  - Planner's discretion: exact URLs, whether a `/reports` landing page links out to the four report pages, or nav lists them directly.
- **D-04:** **Both thresholds are per-product, configurable on the product card** — not global-only settings, not hardcoded. This requires a schema change: new nullable columns on `products` (e.g. `low_stock_threshold`, `stale_days`) plus product-form fields to set them (planner's discretion on exact column names/migration number).
- **D-05:** **Global fallback default** from settings (e.g. `settings.low_stock_threshold`, `settings.stale_days`) applies to any product whose per-product field is empty/NULL — so products never silently drop out of the "мало/залежалось" report just because the operator hasn't set a per-product value yet. Effective threshold = per-product value if set, else the global default.
- **D-06:** **Three separate CSV files** (products.csv, sales.csv, customers.csv), each its own download button, on a **dedicated `/export` page** — mirrors the existing `/backup` page pattern (dedicated route, simple list/buttons). (Chosen over a combined ZIP archive and over scattering export buttons across existing pages.)
- **D-07:** Each CSV is a streamed `StreamingResponse` built with `csv.writer`, encoded **`utf-8-sig`** (UTF-8 with BOM) so Cyrillic product/customer names open correctly in Excel — this is a hard technical requirement, not a style choice.

### Claude's Discretion

- Exact URLs/route names, template/partial structure for each report page.
- Migration number and exact column names for the per-product threshold fields (D-04).
- Names/keys of the new global fallback settings (D-05).
- Sales/profit report grouping and layout details (e.g. whether profit is shown per line, per product, or only as a period total) — must use the frozen `unit_cost_cents`/`unit_price_cents` snapshot per SAL-05, never recompute from current product card prices.
- Write-off report grouping — group by the existing `reason_code` categories from Phase 5 (`damaged`/`expired`/`lost`/`personal`/`gift`/`other`), since that's what those categories were designed for (05-CONTEXT.md D-03).
- Top-selling ranking metric (units vs revenue vs profit) and lookback window for RPT-04 — default recommendation: rank by units sold within the selected report period; "stale" uses `stale_days` independent of the period selector (it's about recency of last sale, not a report period).
- Exact CSV column sets for each entity export.
- RU UI text, empty-state and confirmation wording.

### Deferred Ideas (OUT OF SCOPE)

- Date-range filtering directly on `/history` — stays deferred; period reporting lives in the new `/reports/*` pages instead (per Phase 5 D-14, resolved here as "separate pages", not a `/history` upgrade).
- Combined ZIP export, single-dashboard report layout, global-only (non-per-product) thresholds — considered and explicitly not chosen (see Implementation Decisions above).
- Purchase-frequency reminders / interested-customer lists — CST-V2-01/02, later milestone.
- Multi-currency, multi-operator sync, user roles — out of scope per PROJECT.md.

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RPT-01 | View sales and profit reports for a day, week, month, or custom period | Local-day boundary helper (Code Example 1) + sales/profit aggregate pattern (Code Example 2), handling nullable `unit_cost_cents` (Pitfall 2) |
| RPT-02 | View current stock levels including a low-stock items list | `Product.quantity` is already the authoritative cached projection (no new query engine needed); effective-threshold COALESCE pattern (Code Example 3) for the low-stock filter |
| RPT-03 | View write-off reports for a chosen period | Reuse `local_day_bounds_utc` + group-in-Python-by-`reason_code` pattern (matches existing `sales.py` oversell aggregation style), labels via existing `WRITEOFF_REASONS` |
| RPT-04 | View top-selling products and products with no sales for a long time | SQL `GROUP BY`/`func.sum`/`func.max` pattern (Code Example 4) for both rankings; stale computed from `MAX(created_at)` per product vs. effective `stale_days` |
| BCK-02 | Export products, sales, customers to CSV | `StreamingResponse` + `csv.writer` + `utf-8-sig` pattern (Code Example 5), RU-locale delimiter pitfall (Pitfall 4) |
</phase_requirements>

## Summary

This phase adds zero new runtime dependencies — everything needed (`csv`, `io`, `datetime`, `zoneinfo`) is Python stdlib, and every architectural building block (thin routes, fat read-only services, `select()`-only ORM, Jinja2 `templates` shared env, RU label constants, `format_cents`/`iso_to_local` filters) already exists in this codebase from Phases 1-5. The only genuinely new technical risk is **local-day boundary math** (D-02): `Operation.created_at` is stored as UTC ISO-8601 text, so "today"/"this week"/"this month" must be computed by converting *local* midnight to UTC via `ZoneInfo(settings.display_tz)` before filtering — the existing `iso_to_local` helper only goes the other direction (UTC → local for display), so a new `local_day_bounds_utc()`-style helper is needed in `app/core.py`. Because those UTC ISO strings are lexicographically sortable, the resulting UTC bounds can be compared directly as strings (`created_at >= start_iso AND created_at < end_iso`) with no `datetime` parsing at the SQL layer — consistent with every other query in this codebase.

The report queries themselves split into two shapes that already have direct precedent in the codebase: (1) small, fixed-cardinality groupings (write-off reasons: 6 categories) are best aggregated **in Python** after a single filtered `select()` — exactly how `sales.py`'s oversell check aggregates `requested_by_product` today; (2) genuinely per-product aggregates over potentially many rows (top-selling, stale, sales/profit totals) use SQLAlchemy 2.0's `func.sum`/`func.max`/`.group_by()`/`.order_by()`/`.limit()` — a pattern not yet used elsewhere in this codebase but a standard, well-documented SQLAlchemy 2.0 Core construct, fully portable to the future PostgreSQL sync target.

The per-product `low_stock_threshold`/`stale_days` columns (D-04) are the phase's only schema change — nullable `Integer` columns on `products`, added the same way as every prior products-table migration (native `op.add_column`, no batch mode). The "effective threshold" (D-05: per-product value else global settings default) is a straightforward `func.coalesce(Product.low_stock_threshold, :default)` in SQL or `product.low_stock_threshold or settings.low_stock_threshold` in Python — either works at this data scale; Python-side is simpler and matches the codebase's existing preference for doing business logic in the service layer rather than in SQL expressions.

CSV export (BCK-02) is FastAPI's documented `StreamingResponse` pattern with a `csv.writer` over an `io.StringIO()`, `utf-8-sig` encoded. One RU-specific pitfall surfaced by research and worth flagging early: this project already renders money with a **comma** decimal separator (`format_cents`, e.g. `"12,50"`), and Excel on Russian-locale Windows opens CSV files using the OS "list separator" setting — which on a comma-decimal locale is typically **semicolon**, not comma. A comma-delimited CSV containing comma-formatted money will very likely open as one un-split column when the operator double-clicks it in Excel. The safe, low-effort fix is to write the CSV with `;` as the delimiter (or add a `sep=;` marker line) rather than fighting the operator's regional settings.

**Primary recommendation:** Add one new `app/services/reports.py` (sales/profit, write-offs, top/stale — all read-only `select()`), fold current-stock/low-stock into it or a sibling `stock.py`, add `app/services/export.py` for the three CSV streams, add migration `0005` for the two nullable threshold columns + matching `app/config.py` settings, and reuse the local-day boundary helper from `app/core.py` everywhere a period is involved. No new pip packages; `csv`/`io` are stdlib.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Local-day boundary computation (D-02) | API / Backend (service layer, `app/core.py`) | — | Pure Python date/timezone math; must happen before any SQL filter is built — cannot be pushed into SQLite (no reliable IANA tz support in SQLite itself) |
| Sales/profit aggregation (RPT-01) | API / Backend (`app/services/reports.py`) | Database / Storage (SQL `WHERE`/`GROUP BY` does the heavy lifting) | Business logic (profit = revenue − cost, handling NULL cost) belongs in the service layer per existing codebase convention (fat services, thin routes) |
| Current stock / low-stock list (RPT-02) | Database / Storage (`Product.quantity` cached projection) | API / Backend (effective-threshold fallback logic) | Stock is already a materialized column — no live ledger recomputation needed; only the threshold fallback is new logic |
| Write-off grouping (RPT-03) | API / Backend (Python-side grouping over a filtered `select()`) | — | Fixed 6-category grouping over a small local dataset; matches the existing in-service aggregation pattern (`sales.py` oversell) rather than adding new SQL JSON-path complexity |
| Top-selling / stale products (RPT-04) | Database / Storage (SQL `GROUP BY`/`func.sum`/`func.max`) | API / Backend (effective `stale_days` comparison) | Potentially many rows across all history — push the aggregation into SQL rather than loading every sale op into Python |
| CSV export streaming (BCK-02) | API / Backend (`StreamingResponse` + `csv.writer`) | — | Stdlib-only; no browser or DB tier involvement beyond the query that feeds each writer |
| Report page rendering | Frontend Server (Jinja2 SSR via shared `templates` env) | Browser (htmx partial swaps for filter changes, mirroring `/history`) | Matches every existing page in this app — server-rendered HTML, no client-side state |

## Standard Stack

### Core

No new core libraries. This phase is built entirely on the stack already locked in `./CLAUDE.md` and used by Phases 1-5:

| Library | Version | Purpose | Why Standard (for this phase) |
|---------|---------|---------|-------------------------------|
| SQLAlchemy | 2.0.51 (already installed) | `select()`/`func.sum`/`func.max`/`.group_by()` report queries | Same ORM already used for every other query in the app; 2.0-style aggregate queries are the documented pattern [CITED: docs.sqlalchemy.org — SQL Expression Language aggregate functions] |
| Python stdlib `csv` | bundled (3.13) | `csv.writer`/`csv.DictWriter` for CSV generation | No package needed; FastAPI's own docs recommend exactly this combination for CSV downloads [CITED: fastapi.tiangolo.com/advanced/custom-response] |
| Python stdlib `io` | bundled (3.13) | `io.StringIO()` buffer fed to `StreamingResponse` | Standard FastAPI CSV-export idiom |
| Python stdlib `zoneinfo` | bundled (3.13, `tzdata` already a runtime dep for Windows) | Local-midnight → UTC conversion for period boundaries | Already used in `app/core.py::iso_to_local`; this phase adds the inverse direction with the same `ZoneInfo(settings.display_tz)` [CITED: docs.python.org/3/library/zoneinfo.html] |
| `fastapi.responses.StreamingResponse` | bundled with FastAPI 0.139.* (already installed) | Streams the CSV body without buffering the whole file in memory | Documented FastAPI response type for exactly this use case [CITED: fastapi.tiangolo.com/advanced/custom-response/#streamingresponse] |

### Supporting

None required. No `pandas`, no dedicated CSV/report library — at this data scale (single local operator, one SQLite file) stdlib `csv` + SQLAlchemy aggregates are sufficient and keep the dependency surface at zero (see Don't Hand-Roll below for the inverse case — things NOT to reach for).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `csv` + `StreamingResponse` | `pandas.DataFrame.to_csv()` | Pulls in a large dependency (NumPy transitively) for a task stdlib already solves cleanly; rejected — violates the project's "no npm/no build step, minimal deps" philosophy already stated in `./CLAUDE.md` |
| SQL `GROUP BY`/`func.sum` for top/stale (RPT-04) | Load all rows, aggregate in Python (`dict` accumulation) | Fine at today's data volume, but SQL aggregation scales correctly as ledger rows grow over years of operation; mixed approach recommended (SQL for potentially-large aggregates, Python for small fixed-cardinality groupings like write-off reasons) |
| `func.coalesce()` in SQL for effective threshold (D-05) | `product.threshold or settings.default` in Python | Either is correct at this scale; Python-side is simpler to read/test and matches the codebase's preference for business logic in the service layer, not embedded in query expressions — recommended default |

**Installation:** None — no new packages this phase.

**Version verification:** Not applicable — no new packages added. Existing pinned versions (FastAPI 0.139.*, SQLAlchemy 2.0.*, Python 3.13) are already verified and locked in `./CLAUDE.md`.

## Package Legitimacy Audit

**Not applicable — this phase installs no external packages.** All functionality (CSV writing, streaming responses, timezone math, SQL aggregation) is covered by the Python standard library and packages already vetted and pinned in `./CLAUDE.md` (SQLAlchemy, FastAPI). No `npm install`/`uv add`/`pip install` step is needed for this phase's requirements (RPT-01..04, BCK-02).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Operator's browser (localhost)
        │
        │  GET /reports/sales?preset=week&from=2026-07-06&to=2026-07-12
        ▼
FastAPI route (app/routes/reports.py)
        │  parses from/to (or preset), calls service with raw date strings
        ▼
app/core.py: local_day_bounds_utc(from_date, to_date, tz) ──► (start_utc_iso, end_utc_iso)
        │
        ▼
app/services/reports.py: sales_profit_report(session, start_iso, end_iso)
        │  select(Operation, Product).where(type='sale', created_at>=start, created_at<end)
        │  aggregate: units sold, revenue (unit_price_cents), cost (unit_cost_cents, NULL-aware)
        ▼
SQLite (operations, products tables — read-only SELECT, no writes)
        │
        ▼
dict result (totals + optional per-product/per-day breakdown)
        │
        ▼
Jinja2 template (app/templates/pages/reports_sales.html)
        │  reuses shared `templates` env: `cents` filter, `local_dt` filter
        ▼
Rendered HTML (full page) OR htmx partial (filter/preset change, same pattern as /history)
        │
        ▼
Operator's browser


Parallel flow — CSV export:

GET /export  ──►  app/routes/export.py  ──►  three buttons, each POSTs/GETs its own path
        │
        ▼
GET /export/products.csv (or /sales.csv, /customers.csv)
        │
        ▼
app/services/export.py: stream_products_csv(session) -> generator yielding CSV rows
        │  csv.writer over io.StringIO(), utf-8-sig encoded, ';' delimiter
        ▼
StreamingResponse(media_type="text/csv", headers={"Content-Disposition": "attachment; ..."})
        │
        ▼
Browser downloads file / Excel opens it directly
```

### Recommended Project Structure

```
app/
├── core.py                       # + local_day_bounds_utc() (new helper, D-02)
├── config.py                     # + low_stock_threshold / stale_days global defaults (D-05)
├── models.py                     # Product gains low_stock_threshold / stale_days columns (D-04)
├── services/
│   ├── reports.py                # NEW — sales/profit (RPT-01), write-offs (RPT-03), top/stale (RPT-04)
│   ├── stock.py                  # NEW (or folded into reports.py) — current levels + low-stock (RPT-02)
│   └── export.py                 # NEW — three CSV stream generators (BCK-02)
├── routes/
│   ├── reports.py                # NEW — one router, multiple GET paths (/reports/sales, /reports/stock, /reports/writeoffs, /reports/products)
│   └── export.py                 # NEW — GET /export (page) + GET /export/{entity}.csv (three routes)
├── templates/
│   ├── pages/
│   │   ├── reports_sales.html    # NEW
│   │   ├── reports_stock.html    # NEW
│   │   ├── reports_writeoffs.html# NEW
│   │   ├── reports_products.html # NEW (top-selling / stale)
│   │   └── export.html           # NEW — mirrors backup.html's "list of downloads" layout
│   └── partials/
│       ├── period_filter.html    # NEW — shared preset-buttons + от/до inputs (D-01), reused by 3 of the 4 report pages
│       ├── sales_report_rows.html    # NEW
│       ├── writeoffs_report_rows.html # NEW
│       └── stock_report_rows.html     # NEW
alembic/versions/
└── 0005_product_thresholds.py    # NEW — nullable low_stock_threshold / stale_days columns
```

### Pattern 1: Local-day boundary conversion (D-02, mandatory correctness)

**What:** Convert a local calendar date (or date range) into a half-open UTC ISO string range for filtering `Operation.created_at`.
**When to use:** Every period-based report (RPT-01, RPT-03) and every preset button (Сегодня/Неделя/Месяц).
**Example:**
```python
# app/core.py — new helper alongside iso_to_local (D-02)
# Source: pattern verified against docs.python.org/3/library/zoneinfo.html
from datetime import UTC, date, datetime, time, timedelta

def local_day_bounds_utc(start_day: date, end_day: date, tz_name: str) -> tuple[str, str]:
    """UTC ISO bounds for the LOCAL half-open range [start_day, end_day] inclusive.

    end_day is the LAST included local calendar day; the returned upper
    bound is local midnight of the day AFTER end_day, converted to UTC —
    so callers filter created_at >= start AND created_at < end (never a
    closed range, which would double-count a row landing exactly on a
    UTC-midnight boundary).
    """
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(start_day, time.min, tzinfo=tz)
    end_local = datetime.combine(end_day, time.min, tzinfo=tz) + timedelta(days=1)
    return (
        start_local.astimezone(UTC).isoformat(timespec="seconds"),
        end_local.astimezone(UTC).isoformat(timespec="seconds"),
    )
```
A single day (Сегодня) calls `local_day_bounds_utc(today, today, tz)`; a week/month preset computes `start_day`/`end_day` from `date.today()` (ISO week: Monday-Sunday is the RU convention — `[ASSUMED]`, confirm with user/planner) and passes them through the same function; the custom "с/по" inputs (D-01) parse to `date` objects and call the same function — **one code path**, matching D-01's explicit requirement.

### Pattern 2: String-range filtering on UTC ISO text (no datetime parsing in SQL)

**What:** Because `Operation.created_at` is UTC ISO-8601 text with a fixed `timespec="seconds"` format (`utcnow_iso()` in `app/core.py`), and ISO-8601 UTC strings sort lexicographically == chronologically, the boundaries from Pattern 1 can be compared directly as strings.
**When to use:** Every report query with a period filter.
**Example:**
```python
# Source: existing codebase convention (app/core.py utcnow_iso doc comment:
# "ISO-8601 UTC strings sort lexicographically == chronologically")
from sqlalchemy import select
from app.models import Operation, Product

start_iso, end_iso = local_day_bounds_utc(from_date, to_date, settings.display_tz)
stmt = (
    select(Operation, Product)
    .join(Product, Operation.product_id == Product.id)
    .where(
        Operation.type == "sale",
        Operation.created_at >= start_iso,
        Operation.created_at < end_iso,
    )
)
```
No `datetime.fromisoformat()` round-trip is needed at the SQL layer — matching how `history_view` and every other existing query in this codebase already treats `created_at` as an opaque, sortable string.

### Pattern 3: Effective-threshold fallback (D-05)

**What:** Per-product value if set, else the global settings default.
**When to use:** Low-stock filter (RPT-02) and stale-product filter (RPT-04).
**Example:**
```python
# app/services/stock.py — Python-side fallback (simplest, matches codebase style)
def effective_low_stock_threshold(product: Product) -> int:
    return product.low_stock_threshold if product.low_stock_threshold is not None else settings.low_stock_threshold

def low_stock_products(session: Session) -> list[Product]:
    products = session.scalars(
        select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
    ).all()
    return [p for p in products if p.quantity <= effective_low_stock_threshold(p)]
```
SQL-side equivalent (only worth it if the products table grows very large — not the case here): `Product.quantity <= func.coalesce(Product.low_stock_threshold, bindparam("default_threshold"))`.

### Pattern 4: SQL aggregation for top-selling / stale products (RPT-04)

**What:** `GROUP BY` + `func.sum`/`func.max` over `Operation` joined to `Product`.
**When to use:** Rankings that must scan potentially many rows across all history (unlike the small fixed-cardinality write-off grouping — see Pattern 5).
**Example:**
```python
# Source: SQLAlchemy 2.0 aggregate query pattern
# https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html#selecting-orm-entities-and-attributes
from sqlalchemy import func, select

# Top-selling within a period: units sold per product, descending.
units_sold = func.sum(-Operation.qty_delta).label("units_sold")  # sale ops store negative qty_delta
stmt = (
    select(Product, units_sold)
    .join(Operation, Operation.product_id == Product.id)
    .where(Operation.type == "sale", Operation.created_at >= start_iso, Operation.created_at < end_iso)
    .group_by(Product.id)
    .order_by(units_sold.desc())
    .limit(10)
)

# Stale: last sale date per ACTIVE product (products never sold need a
# LEFT OUTER JOIN so they still appear with NULL last_sale).
last_sale = func.max(Operation.created_at).label("last_sale")
stmt = (
    select(Product, last_sale)
    .outerjoin(
        Operation, (Operation.product_id == Product.id) & (Operation.type == "sale")
    )
    .where(Product.deleted_at.is_(None))
    .group_by(Product.id)
)
# Compare last_sale (or "never sold") against each product's effective
# stale_days cutoff IN PYTHON after fetching — the cutoff is per-product
# (D-05), which SQL GROUP BY output can't easily re-filter per row without
# a correlated subquery; a plain Python filter over the (already small)
# active-product list is simpler and matches Pattern 3.
```

### Pattern 5: Python-side grouping for small fixed-cardinality categories (RPT-03)

**What:** For the write-off report, group by `payload["reason_code"]` (only 6 possible values — `WRITEOFF_REASONS`) using a plain `select()` + Python `dict` accumulation, not SQL JSON-path extraction.
**When to use:** Any grouping where the key set is small, fixed, and already lives inside a JSON payload column.
**Example:**
```python
# app/services/reports.py — mirrors the existing sales.py oversell
# aggregation style (requested_by_product: dict[str, int] = {}).
from collections import defaultdict
from app.models import WRITEOFF_REASONS, Operation, Product

def writeoff_report(session: Session, start_iso: str, end_iso: str) -> dict:
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(
            Operation.type == "writeoff",
            Operation.created_at >= start_iso,
            Operation.created_at < end_iso,
        )
        .order_by(Operation.created_at.desc())
    ).all()
    by_reason: dict[str, dict] = defaultdict(lambda: {"qty": 0, "lines": []})
    for op, product in rows:
        reason = (op.payload or {}).get("reason_code", "other")
        by_reason[reason]["qty"] += -op.qty_delta  # writeoff qty_delta is negative
        by_reason[reason]["lines"].append({"op": op, "product": product})
    # Sort by the WRITEOFF_REASONS dict's own key order for stable display.
    return {
        reason: by_reason[reason]
        for reason in WRITEOFF_REASONS
        if reason in by_reason
    }
```
Avoids SQLite JSON-path extraction operators (`json_extract`, `->>`) entirely — those work but add a portability wrinkle (SQLite vs. PostgreSQL JSON operator syntax differs) for zero benefit at this data scale, where a full period's write-offs is at most a few hundred rows.

### Anti-Patterns to Avoid

- **Slicing the UTC `created_at` string by date directly** (e.g. `created_at.startswith("2026-07-10")`): breaks the moment local time is not UTC (Europe/Moscow is UTC+3) — an evening sale after 21:00 local time on day N is stored with a UTC date of day N+1 and would silently vanish from "today's" report. This is the exact bug D-02 exists to prevent.
- **Recomputing profit from `Product.cost_cents`/`Product.sale_cents`**: violates SAL-05's frozen-snapshot guarantee — always read `Operation.unit_cost_cents`/`unit_price_cents` from the sale operation rows, never the current product card.
- **Reaching for `pandas` or a reporting library**: unnecessary dependency weight for report volumes a single local operator generates; stdlib `csv` + SQLAlchemy aggregates are sufficient (see Don't Hand-Roll for the flip side of this — things that ARE worth using a library for).
- **Writing CSV with the default comma delimiter while also formatting money with a comma decimal separator, without testing an actual Excel-open on the target locale**: technically valid CSV (Python's `csv.writer` auto-quotes fields containing the delimiter), but very likely to visually "not split into columns" for a Russian-locale Windows user double-clicking the file (see Pitfall 4).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV row escaping (quoting, embedded commas/newlines/quotes in product names) | Manual string-joining with `,` | Python stdlib `csv.writer`/`csv.DictWriter` | `csv.writer` handles RFC 4180 quoting correctly (a product name containing a comma or a newline would silently corrupt a hand-rolled CSV) |
| Timezone-aware date math | Manual UTC-offset arithmetic (`+3 hours`) | `zoneinfo.ZoneInfo` + `datetime.astimezone()` | Hand-rolled offset math breaks silently on DST transitions in regions that observe them; `ZoneInfo` uses the IANA tz database (already a project dependency via `tzdata`) and is correct by construction |
| CSV file streaming for potentially large exports | Building the whole CSV string in memory, then `Response(content=...)` | `StreamingResponse` over a generator | At this data scale either works today, but `StreamingResponse` is the documented, no-extra-cost FastAPI idiom and avoids a full-file memory buffer as sales history grows over years |
| Excel locale/delimiter compatibility | Guessing / assuming comma always works | `;` delimiter (or `sep=;` marker line) given this app already uses comma-decimal money formatting | See Pitfall 4 — this is a well-documented, recurring Excel/regional-settings gotcha, not a made-up edge case |

**Key insight:** Every "don't hand-roll" item above already has a battle-tested stdlib or already-installed-library answer — this phase adds a formatting/reporting *layer* over existing data, not new infrastructure. The only place custom logic belongs is the local-day boundary conversion (Pattern 1), because that logic is specific to this app's `display_tz` setting and cannot be delegated to a library.

## Common Pitfalls

### Pitfall 1: Off-by-one on period end boundaries
**What goes wrong:** A "custom period" report from 2026-07-06 to 2026-07-08 silently excludes all of July 8th's sales, or double-counts a sale that lands exactly at local midnight.
**Why it happens:** Treating the "to" date as the exclusive upper bound instead of the last *included* day, or using `<=` against a same-day UTC bound instead of `<` against the next day's local midnight.
**How to avoid:** Always call `local_day_bounds_utc(from_date, to_date, tz)` (Pattern 1) which already returns the correct half-open `[start, end)` range — never construct period bounds ad hoc per report.
**Warning signs:** A report for "today" shows fewer sales than `/history` filtered by eye for the same day; a report's last day is always empty.

### Pitfall 2: NULL `unit_cost_cents` silently inflating profit totals
**What goes wrong:** `unit_cost_cents` is nullable (a sale can happen on a product whose cost price was never entered — `sales.py` comment: "unit_cost_cents is frozen from Product.cost_cents at write time and may be NULL"). SQL `SUM()` skips NULL rows rather than treating them as zero, so `SUM(unit_price_cents * qty) - SUM(unit_cost_cents * qty)` **overstates profit** by the full revenue of every cost-unknown line (its revenue is summed, but zero cost is subtracted for it — not because cost was 0, but because it was excluded from the cost sum entirely).
**Why it happens:** SQL `SUM` and NULL-propagating multiplication (`NULL * qty = NULL`) interact in a way that's easy to miss when writing an aggregate query.
**How to avoid:** Either (a) exclude cost-unknown lines from the profit calculation and show a separate count ("N продаж без указанной себестоимости — прибыль не учитывает их"), or (b) show revenue and cost as two separate totals rather than a single blended profit figure, letting the operator see the gap. Recommend (a) with a visible caveat — matches the project's "never invent/never silently guess at money figures" ethos.
**Warning signs:** A report's total profit looks suspiciously close to total revenue; profit exceeds a sanity check against known margins.

### Pitfall 3: `stale_days`/`low_stock_threshold` of `0` treated as falsy in Python
**What goes wrong:** `product.low_stock_threshold or settings.low_stock_threshold` (Pattern 3) falls through to the global default even when the operator explicitly set the per-product threshold to `0` (a legitimate "alert me the instant this hits zero stock" choice) — because `0` is falsy in Python.
**Why it happens:** `or`-based fallback conflates "unset" (`None`) with "falsy" (`0`).
**How to avoid:** Use an explicit `is not None` check (as shown correctly in Pattern 3's `effective_low_stock_threshold`), never a bare `or`.
**Warning signs:** A product configured with threshold `0` still shows up as low-stock at the *global* default threshold instead of only when it hits exactly zero.

### Pitfall 4: CSV delimiter vs. RU-locale Excel "list separator"
**What goes wrong:** The operator double-clicks `sales.csv` and Excel shows every row crammed into a single column A, with no visible splitting into Код/Название/Цена etc.
**Why it happens:** Excel's CSV auto-detection uses the OS Regional Settings "List Separator", which on locales where the decimal separator is a comma (Russian included) is typically **semicolon**, not comma. This project already formats money with a comma decimal separator (`format_cents` → `"12,50"`), so the mismatch is doubly likely to bite: even if Excel does try comma-splitting, comma-formatted money cells would (correctly, via `csv.writer`'s auto-quoting) each become one quoted field — but only if Excel's separator guess happens to be comma, which on a RU-locale machine it usually isn't. [CITED: multiple sources on Excel CSV regional list-separator behavior — ablebits.com, exceldemy.com, Microsoft Q&A]
**How to avoid:** Write each CSV with `;` as the `csv.writer` delimiter (`csv.writer(buffer, delimiter=";")`), which matches the RU-locale Excel default and sidesteps any ambiguity with comma-decimal money fields entirely. `[ASSUMED]` — the operator's exact Windows regional settings are not verified in this session; flag as a decision needing a quick manual check ("does `sales.csv` open correctly when double-clicked on the actual target machine") before considering BCK-02 done.
**Warning signs:** Manual test of opening an exported CSV in Excel (not just viewing it as text) shows one column instead of many.

### Pitfall 5: Products soft-deleted mid-period still needing to appear in historical reports
**What goes wrong:** A write-off or sales report for last month excludes a product that has since been soft-deleted (`deleted_at` set), because the report query filters `Product.deleted_at.is_(None)` the way `list_products`/`search_products` do for the live catalog.
**Why it happens:** Copy-pasting the "active products only" filter from catalog-browsing services into report services, without noticing reports are inherently historical and must show what *happened*, not what currently exists in the catalog.
**How to avoid:** Sales/profit and write-off reports (RPT-01, RPT-03) must NOT filter by `Product.deleted_at` — they join `Operation` to `Product` and show whatever product each historical operation actually touched, deleted or not. Only RPT-02 (current stock) and the "products never sold" half of RPT-04 should filter to active products, since those are inherently "as of now" views.
**Warning signs:** A write-off report total for a past month doesn't match `/history` filtered by eye for the same period, specifically missing rows for products that were later deleted.

## Code Examples

### CSV streaming export (BCK-02, D-06/D-07)
```python
# Source: FastAPI official docs pattern (fastapi.tiangolo.com/advanced/custom-response/)
# adapted with utf-8-sig (D-07) and ';' delimiter (Pitfall 4).
import csv
import io
from collections.abc import Generator

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import format_cents
from app.models import Product


def _csv_rows(header: list[str], rows: list[list]) -> Generator[str, None, None]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    for row in rows:
        writer.writerow(row)
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)


def stream_products_csv(session: Session) -> StreamingResponse:
    products = session.scalars(
        select(Product).order_by(Product.name_lc)  # ALL products, including deleted — export is a full data dump
    ).all()
    header = ["Код", "Название", "Категория", "Закупка", "Продажа", "Каталог", "Остаток"]
    rows = [
        [
            p.code or "",
            p.name,
            p.category or "",
            format_cents(p.cost_cents) if p.cost_cents is not None else "",
            format_cents(p.sale_cents) if p.sale_cents is not None else "",
            format_cents(p.catalog_cents) if p.catalog_cents is not None else "",
            p.quantity,
        ]
        for p in products
    ]
    # utf-8-sig: prepend the encoder, since StreamingResponse encodes text
    # chunks to bytes itself — encode explicitly and stream bytes instead
    # of relying on an implicit text->bytes step, so the BOM lands exactly
    # once at the very start of the byte stream.
    def encoded() -> Generator[bytes, None, None]:
        first = True
        for chunk in _csv_rows(header, rows):
            data = chunk.encode("utf-8-sig") if first else chunk.encode("utf-8")
            first = False
            yield data

    return StreamingResponse(
        encoded(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=products.csv"},
    )
```
**Note on `utf-8-sig` + streaming:** encoding EVERY chunk with `"utf-8-sig"` would repeat the BOM bytes on every yielded chunk, corrupting the file. The BOM must be emitted exactly once, at the start of the byte stream — the pattern above encodes only the first chunk with `utf-8-sig` and every subsequent chunk with plain `utf-8`. This is a subtle detail worth a dedicated unit test (see Validation Architecture below).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A | N/A | — | No ecosystem churn relevant to this phase — `csv`, `zoneinfo`, `StreamingResponse` are all stable, unchanged APIs; this phase is pure application logic over an already-locked stack. |

**Deprecated/outdated:** None relevant.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | ISO week starts Monday (RU convention) for the "Неделя" preset | Pattern 1 | Low — cosmetic; a Sunday-start week would just shift which 7 days the preset shows. Confirm with user during planning or leave as an easy config knob. |
| A2 | Default global fallback values: `low_stock_threshold = 5` units, `stale_days = 90` days | Recommended in D-05 discretion area, not yet in RESEARCH tables above | Low-Medium — wrong defaults just mean the low-stock/stale lists are initially too noisy or too quiet until the operator tunes them; no data-loss risk. Needs explicit user confirmation before locking into `app/config.py`. |
| A3 | The operator's actual Windows install uses a comma-decimal regional format, making semicolon the correct Excel CSV delimiter (Pitfall 4) | Common Pitfalls, Code Examples | Medium — if the target machine's Regional Settings differ from the RU default assumed here, the semicolon delimiter could itself cause a one-column-open problem instead of fixing it. A one-time manual "open the exported CSV in Excel" check during Phase 6 execution resolves this cheaply. |
| A4 | Top-selling ranking (RPT-04) defaults to units sold within the selected report period (not revenue or profit) | Phase Requirements table / Pattern 4 | Low — this is explicitly listed as Claude's Discretion in 06-CONTEXT.md with this exact default recommended there; not a research risk, restated here for traceability. |

## Open Questions

1. **Week boundary convention (Monday vs. Sunday start) for the "Неделя" preset**
   - What we know: RU convention is ISO 8601 (Monday-start) weeks; the app's `display_tz` is already `Europe/Moscow`.
   - What's unclear: Whether the operator has any existing mental model (e.g. Oriflame catalog cycles use their own week numbering unrelated to calendar weeks) that should override the ISO default.
   - Recommendation: Default to Monday-start ISO week; surface as an easy planner decision rather than hardcoding without flagging it (see A1).

2. **Should `/reports/products` (top-selling/stale, RPT-04) show deleted products in the "stale" list?**
   - What we know: A soft-deleted product's `Operation` rows still exist and are joinable; Pitfall 5 argues historical reports should include deleted products' past activity.
   - What's unclear: Whether an operator actively wants a *currently retired* product cluttering the "залежалось" (stale) action list, since there's nothing actionable to do about a deleted product's stock.
   - Recommendation: Exclude deleted products from RPT-04's forward-looking "stale/never-sold" list (nothing to act on), but keep them in RPT-01/RPT-03's period-based sales/write-off reports (Pitfall 5) — these are different questions ("what should I act on now" vs. "what happened in this period") answered differently.

## Environment Availability

Skipped — this phase has no new external dependencies (no new tools, services, runtimes, or CLIs beyond the already-verified stack in `./CLAUDE.md`). `csv`, `io`, `zoneinfo` are stdlib; `tzdata` (needed for `zoneinfo` on Windows) is already a locked runtime dependency per `./CLAUDE.md`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (already configured, `tests/` dir, `pythonpath=["."]`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_reports.py tests/test_export.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| RPT-01 | Local-day boundary correctness — an evening sale (local time) near a UTC-date rollover lands in the correct day's report | unit | `pytest tests/test_core.py::test_local_day_bounds_utc_dst_boundary -x` | ❌ Wave 0 |
| RPT-01 | Sales/profit totals exclude cost-unknown lines from profit but still count their revenue, per Pitfall 2 | unit | `pytest tests/test_reports.py::test_sales_report_null_cost -x` | ❌ Wave 0 |
| RPT-02 | Effective threshold: per-product `0` is NOT treated as "unset" (Pitfall 3) | unit | `pytest tests/test_reports.py::test_effective_threshold_zero_not_fallback -x` | ❌ Wave 0 |
| RPT-02 | Low-stock list includes products whose threshold is NULL, using the global default | unit | `pytest tests/test_reports.py::test_low_stock_uses_global_fallback -x` | ❌ Wave 0 |
| RPT-03 | Write-off report groups correctly by `reason_code`, matching `WRITEOFF_REASONS` keys | unit | `pytest tests/test_reports.py::test_writeoff_report_groups_by_reason -x` | ❌ Wave 0 |
| RPT-04 | Top-selling ranks by units sold descending within period | unit | `pytest tests/test_reports.py::test_top_selling_orders_by_units -x` | ❌ Wave 0 |
| RPT-04 | Stale list includes a product with zero sales ever (LEFT OUTER JOIN correctness) | unit | `pytest tests/test_reports.py::test_stale_includes_never_sold -x` | ❌ Wave 0 |
| BCK-02 | Exported CSV round-trips through `csv.reader` with correct row count and header | integration | `pytest tests/test_export.py::test_products_csv_roundtrip -x` | ❌ Wave 0 |
| BCK-02 | CSV byte stream starts with the UTF-8 BOM exactly once (not per-chunk) | unit | `pytest tests/test_export.py::test_csv_bom_appears_once -x` | ❌ Wave 0 |
| BCK-02 | Money field renders with comma decimal AND the `;` delimiter doesn't collide with it | unit | `pytest tests/test_export.py::test_money_field_not_split_by_delimiter -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_reports.py tests/test_export.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_reports.py` — covers RPT-01, RPT-02, RPT-03, RPT-04
- [ ] `tests/test_export.py` — covers BCK-02
- [ ] `tests/test_core.py` — add `local_day_bounds_utc` cases alongside existing `to_cents`/`format_cents`/`iso_to_local` tests (file already exists, needs new test functions, not a new file)
- [ ] Fixtures: extend `tests/conftest.py` with a `sold_product` or period-spanning seed fixture (multiple sale/writeoff ops across distinct local days) — the existing `stocked_product` fixture only creates one receipt, insufficient for period-boundary tests
- [ ] Framework install: none — pytest already configured

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | Single local operator, no auth in v1 (per `./CLAUDE.md`) |
| V3 Session Management | No | No sessions — stateless local app |
| V4 Access Control | No | No roles/permissions in v1 |
| V5 Input Validation | Yes | Report date-range query params (`from`/`to`) must be validated as well-formed dates before being passed to `local_day_bounds_utc` — invalid input should fall back to a safe default (e.g. today) or return a RU validation error, never raise an uncaught `ValueError` from `date.fromisoformat` into a 500. CSV export routes take **zero** client-supplied parameters (mirrors the existing `/backup` route's V12 pattern — "NEITHER endpoint accepts a filename, path, Form or Query parameter") since export always dumps the full table. |
| V6 Cryptography | No | No new crypto surface in this phase |
| V12 File and Resources | Yes | CSV export must never accept a client-controlled path/filename (matches `app/routes/backup.py`'s existing V12 comment/pattern exactly — export filenames are server-hardcoded `products.csv`/`sales.csv`/`customers.csv`, never derived from request input) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|------------------------|
| Unvalidated `from`/`to` date query params causing an unhandled exception (DoS via crash, or a report silently showing the wrong/huge range) | Denial of Service / Tampering | Parse with `date.fromisoformat()` inside a `try/except ValueError`, return a RU error or fall back to a safe default; never let a malformed date param reach `local_day_bounds_utc` unchecked |
| CSV/formula injection — a product or customer name starting with `=`, `+`, `-`, or `@` being interpreted as an Excel formula on open | Tampering (client-side, via a later Excel open) | Low realistic risk here (single local operator enters their own product/customer names — not an external-input surface), but cheap to harden: prefix any cell value starting with `=+-@` with a leading `'` (or a space) before writing, standard CSV-injection mitigation. `[ASSUMED]` risk level — flag as a nice-to-have hardening step, not a blocking requirement given the trust model (single operator, local data, no external CSV upload path). |
| `Operation.payload` (arbitrary JSON) rendered into a report template without escaping (e.g. write-off `note` field) | Tampering / Injection (stored XSS in a future multi-user context) | Already covered by the existing global Jinja2 autoescape (no `|safe` anywhere in the codebase per `history_rows.html`'s own comment: "NEVER `|safe`") — new report templates must follow the same rule, no new mitigation needed beyond continuing the existing convention |

## Sources

### Primary (HIGH confidence)
- Codebase itself (`app/models.py`, `app/core.py`, `app/config.py`, `app/services/*.py`, `app/routes/*.py`, `app/templates/**`, `alembic/versions/*.py`, `tests/conftest.py`) — read directly this session; every architectural claim about existing patterns is grounded in these files, not training-data assumption.
- `.planning/phases/06-reports-data-export/06-CONTEXT.md` — locked decisions D-01..D-07, discretion areas, canonical references to prior-phase decisions.
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — requirement text and traceability.

### Secondary (MEDIUM confidence)
- FastAPI official docs, `fastapi.tiangolo.com/advanced/custom-response/` — `StreamingResponse` pattern for CSV downloads [CITED].
- Python official docs, `docs.python.org/3/library/zoneinfo.html` — `ZoneInfo`/`astimezone()` local-to-UTC conversion pattern [CITED].
- SQLAlchemy 2.0 official docs, `docs.sqlalchemy.org/en/20/orm/queryguide/select.html` — aggregate query (`func.sum`, `.group_by()`) pattern [CITED].
- Multiple independent sources (ablebits.com, exceldemy.com, Microsoft Q&A) converging on the same Excel CSV regional-list-separator behavior [CITED — cross-checked across 3+ independent sources, treated as MEDIUM-HIGH].

### Tertiary (LOW confidence)
- ISO week Monday-start assumption for the "Неделя" preset (A1) — training-knowledge convention, not verified against this specific operator's expectations. `[ASSUMED]`.
- Suggested default threshold values (5 units / 90 days, A2) — reasonable retail heuristics, not derived from this business's actual sales velocity data (no historical sales volume exists yet to calibrate against). `[ASSUMED]`.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies; every tool is either already locked in `./CLAUDE.md` or Python stdlib with official-docs-verified usage patterns.
- Architecture: HIGH — every pattern is either a direct extension of an existing, working codebase convention (thin routes, fat services, shared `templates` env, `select()`-only ORM) or a documented standard library/framework idiom.
- Pitfalls: HIGH — Pitfalls 1, 2, 3, 5 derive directly from this codebase's own data model (nullable `unit_cost_cents`, UTC-text timestamps, nullable threshold columns, soft-delete semantics); Pitfall 4 (Excel locale) is cross-checked against 3+ independent web sources but the operator's actual machine settings are unverified (see A3).

**Research date:** 2026-07-10
**Valid until:** 30 days (stable stdlib/FastAPI/SQLAlchemy APIs; no fast-moving ecosystem risk for this phase)
