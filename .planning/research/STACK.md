# Stack Research

**Domain:** Warehouse inventory web app — v1.1 "Multi-Warehouse & Batch Tracking" milestone
**Researched:** 2026-07-10
**Confidence:** HIGH

> Scope note: this file is scoped to the v1.1 milestone (multi-warehouse, batch/lot tracking,
> category page, min-price warning, mobile-responsive layout). The full v1.0 stack rationale
> (FastAPI/SQLAlchemy/SQLite/HTMX/Jinja2/uv/Alembic, versions, "what not to use") is preserved
> verbatim in the project's `CLAUDE.md` "Technology Stack" section and is not repeated here —
> it is unchanged and not re-researched per milestone instructions.

## Bottom Line

**No new runtime dependency is needed for any of the four target features.** Multi-warehouse,
batch/lot tracking, the category page, and the minimum-price warning are all schema + query +
service-layer additions on top of the existing FastAPI / SQLAlchemy 2.0 / SQLite / HTMX / Jinja2
stack, following patterns the codebase already established in Phases 1-6 (append-only
`operations` ledger via `record_operation()`, native `ALTER TABLE ADD COLUMN` on `operations` to
preserve its triggers, TEXT-encoded ISO dates/money-as-cents, warn-but-allow gates). Mobile
responsiveness is a CSS/HTML concern, solvable with plain CSS media queries and a CSS-only nav
disclosure — introducing a CSS framework or a JS library would violate the project's own
"no build step, no JS framework" constraint for zero benefit at this scale.

## Recommended Stack (unchanged — reused, not added)

### Core Technologies

| Technology | Version (pinned, unchanged) | Purpose for v1.1 | Why no change needed |
|------------|------|---------|-----------------|
| SQLAlchemy | 2.0.* (2.0.51 validated) | New `warehouses` and `batches` tables, `Operation.batch_id`/`Product.min_price_cents` columns | 2.0 declarative style (`Mapped[]`/`mapped_column()`) already used throughout `app/models.py`; new tables are ordinary FK-related mapped classes, nothing exotic |
| Alembic | 1.18.* (1.18.5 validated) | Migrations 0006+ for the new tables/columns | Already the sole schema-change tool (5 migrations exist: `0001`-`0005`); `render_as_batch` already configured for SQLite |
| SQLite (stdlib `sqlite3` via SQLAlchemy) | bundled | Stores the new tables | No new storage engine; composite/partial indexes and multi-table joins used elsewhere (`uq_products_code_active` partial unique index in `0003`) cover everything batches need |
| FastAPI + Jinja2 + HTMX 2.0.10 (vendored) | 0.139.*/3.1.*/2.0.10 | Warehouse/category pages, batch picker partial, mobile nav | Batch picker is the same "type code -> `hx-get` a filtered partial" pattern already used for product/customer autocomplete (`app/routes/sales.py`, `app/routes/customers.py`) |

### Supporting Libraries

**None required.** Specifically checked and rejected as unnecessary:

| Considered | Verdict | Reason |
|------------|---------|--------|
| A date/calendar library (e.g. `python-dateutil`, `pendulum`) for batch `expiry_date` | Not needed | `app/core.py` already handles all dates with stdlib `datetime.date`/`zoneinfo` (`local_day_bounds_utc`, `iso_to_local`) — zero third-party date library exists in this codebase today; expiry date needs only `date.fromisoformat()`/`date.isoformat()`, both stdlib |
| A CSS framework (Pico.css, Bootstrap, Tailwind) for "mobile-responsive" | Not needed | `app/static/style.css` is already a hand-rolled, from-scratch stylesheet (not Pico — the original stack doc's "optional" Pico.css was never actually adopted); it needs media queries added, not replaced |
| Alpine.js / a JS library for a mobile hamburger nav toggle | Not needed | A CSS-only `<details>`/checkbox disclosure toggles the nav with zero JavaScript — matches the "no JS framework" constraint exactly |
| `jinja2-fragments` (listed "optional" in the original stack doc, still not installed) | Optional, not mandatory this milestone | v1.1 adds a few more HTMX partials (batch picker, warehouse/category views), but the existing one-partial-per-`{% include %}` pattern has scaled through 6 phases already; adding it now is a template-sprawl call for the roadmap/planning step, not a hard requirement — YAGNI for this milestone |
| A dedicated "inventory batch/FEFO" package (none exist as a general-purpose Python + SQLAlchemy library) | Not applicable | Batch selection here is manual (operator picks from a list), not automatic FIFO/FEFO allocation — explicitly out of scope per PROJECT.md ("Batch FIFO costing" listed under Out of Scope); no library solves "render a list, let a human click one" |

### Development Tools

No changes. Same `uv` / `ruff` / `pytest` workflow as v1.0.

## Installation

```bash
# No new packages. Existing environment is sufficient:
uv sync
```

No `uv add` is required for this milestone.

## Schema & Integration Design (the actual work, not a library choice)

This is what "no new dependency" cashes out to concretely, so the roadmap can plan phases against it.

### 1. Multi-warehouse + free-text location (WH-01, WH-02)

- New `warehouses` table: `id` (UUID String(36) PK, matching every other table), `name`,
  `created_at`, `deleted_at` (soft delete — matches `Product`'s pattern, never hard-delete).
- Location is **not** its own table — PROJECT.md specifies "free-text storage location tag", so
  it is a plain `String` column on the batch row (see below), not a normalized `locations` table.
  Adding a table for it would be over-engineering a field the operator types freely.
- `Operation` needs to know which warehouse a stock movement affects. Since every operation will
  also carry a `batch_id` (batches are already warehouse-scoped), the warehouse is reachable via
  `batch.warehouse_id` — no separate `warehouse_id` column needed on `operations` itself. Keep the
  ledger schema minimal (one join to `batches`, same cost as the existing join to `products`).

### 2. Batch/lot tracking (LOT-01..04) — the core schema change

- New `batches` table: `id` (UUID PK), `product_id` (FK -> products), `warehouse_id` (FK ->
  warehouses), `location` (nullable free text), `expiry_date` (nullable, **`String(10)`**, ISO-8601
  `'YYYY-MM-DD'` — deliberately matching the project's existing convention of TEXT-encoded dates
  that "sort lexicographically == chronologically" (`app/core.py:utcnow_iso` docstring), not a
  SQLAlchemy `Date`/`DateTime` type; the codebase has never used those column types and mixing
  conventions would break the beginner-consistency goal), `price_cents` (Integer, same
  integer-cents convention as `Product.cost_cents`/`sale_cents`), `comment` (nullable free text),
  `quantity` (Integer, cached projection — same pattern as `Product.quantity`), `created_at`,
  `deleted_at`.
- **`Operation` gains a nullable `batch_id` FK column.** This must be added via a **native**
  `op.add_column("operations", sa.Column("batch_id", sa.String(36), nullable=True))` — **never**
  `batch_alter_table("operations")`. Migration `0001` installs `operations_no_update` /
  `operations_no_delete` triggers on the table, and migration `0004`'s docstring already
  documents (and migration `0004` itself demonstrates, adding `sale_id` the same way) that
  Alembic's batch mode on SQLite recreates the table and **silently drops those triggers**. Any
  future migration touching `operations` must follow the exact `0004` recipe: bare column, ORM
  level `ForeignKey` only (SQLite's `ALTER` can't add an inline FK constraint either — the same
  `NotImplementedError` fallback `0004` already hit and documented).
- **`record_operation()`** (`app/services/ledger.py`) is the single write path and must gain an
  optional `batch_id: str | None = None` parameter, mirroring how it already accepts optional
  `sale_id`. Inside the same transaction it should also do
  `batch.quantity = Batch.quantity + qty_delta` alongside the existing
  `product.quantity = Product.quantity + qty_delta` — the exact same "SQL-side atomic increment,
  no stale-ORM-value window" pattern (`IN-02` in the current code), just applied to a second
  cached-projection row. Add a `compute_batch_stock()` next to `compute_stock()` for the same
  recompute-from-ledger repair story `rebuild_stock()` already provides for products.
- Selling from a batch still writes exactly **one** `sale` operation row (with both `product_id`
  and `batch_id` set) — the append-only, single-write-path invariant is unchanged, only the row
  shape grows one nullable column, matching how `sale_id` was added in `0004` for the sales
  feature.

### 3. "Товары на складе" category page (CAT-01)

Pure read-side: `GROUP BY Product.category` / `ORDER BY category, name_lc` query plus a Jinja2
template — same shape as the existing catalog listing code in `app/services/catalog.py`. No
schema change beyond what batches/warehouses already add (the page will also need to roll up
batch quantities per product per warehouse, which `compute_batch_stock` and the cached
`batches.quantity` support directly).

### 4. Minimum sale price warning (PRICE-01)

- Add nullable `min_price_cents` to `products` via a plain native `op.add_column` (SQLite can
  `ADD COLUMN` a nullable column without batch mode) — same shape as the `0005` migration that
  added `low_stock_threshold`/`stale_days`.
- Reuse the **exact** warn-but-allow shape already implemented for the oversell check in
  `app/services/sales.py` (`confirm != "1"` -> return a warning dict with **zero writes**;
  `confirm == "1"` -> proceed). Add a `below_min_price` check alongside the existing `oversold`
  aggregate check in the same function, so a sale can warn on both conditions in one round trip.

### 5. Mobile-responsive layout (UI-01)

- `app/templates/base.html` already ships a correct `<meta name="viewport">` tag — that part of
  "mobile-ready" is done.
- The real gap: `<nav>` is a flat `flex` row of 11 links (`app/templates/base.html`) with no
  wrapping/collapse behavior, and `app/static/style.css` has zero `@media` queries today. Fix
  entirely in CSS:
  - Add `@media (max-width: 640px)` rules to the existing hand-rolled `style.css` (narrower
    padding, stacked form rows, full-width tap targets — forms are the majority of this app's UI).
  - Collapse the nav using a **CSS-only** `<details>`/`<summary>` (or hidden-checkbox + `:checked`
    sibling selector) disclosure pattern below the breakpoint. Zero JavaScript, zero new markup
    dependency, and it does not conflict with htmx (htmx only needs the links/forms it already
    has; a collapsed nav is invisible to it).
  - Do **not** reach for Alpine.js "just for the hamburger toggle" — that is exactly the kind of
    small addition the project's own CLAUDE.md flags as unnecessary until real client-side state
    is needed, and a hamburger open/close is pure CSS, not state.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Plain SQLAlchemy 2.0 tables (`warehouses`, `batches`) | A generic "multi-tenancy" or "inventory" library/extension | None exist as a good SQLAlchemy fit for this domain; hand-rolled tables are simpler and match the codebase's existing hand-rolled `Product`/`Sale`/`Operation` models |
| CSS-only nav disclosure | Alpine.js sprinkle | If a later milestone needs real client-side state (multi-step wizards, optimistic UI) beyond simple show/hide — not needed for a nav toggle |
| Hand-rolled `style.css` + media queries | Pico.css (classless) | If the hand-rolled stylesheet ever becomes a maintenance burden and the team wants semantic-HTML-only styling; today it already has an established scale (spacing/type/colors) that Pico would fight with, not complement |
| `String(10)` ISO date for `expiry_date` | SQLAlchemy `Date`/`DateTime` column type | If the project ever needs native date arithmetic in SQL (e.g. `expiry_date - CURRENT_DATE`) rather than in Python/Jinja2 — not needed here since "batches expiring soon" can be computed the same way `local_day_bounds_utc` already compares ISO strings |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `batch_alter_table("operations")` for the new `batch_id` column | Recreates the table on SQLite and silently drops the `operations_no_update`/`operations_no_delete` append-only triggers (documented pitfall already hit once in migration `0004`) | Native `op.add_column("operations", ...)` with a bare column (no inline FK) + ORM-level `ForeignKey` in `app/models.py`, exactly as `0004` did for `sale_id` |
| Inline FK constraint in `op.add_column` on SQLite | Alembic's SQLite dialect raises `NotImplementedError` ("No support for ALTER of constraints in SQLite dialect") — already confirmed by the team in `0004`'s docstring | Bare column + ORM-side `ForeignKey` only |
| `FLOAT`/`REAL` for `batches.price_cents` | SQLite has no true DECIMAL; floats corrupt profit math (already a documented "What NOT to Use" for the whole project) | Integer cents, same as every other money column |
| A CSS framework (Pico.css/Bootstrap/Tailwind) to "make it responsive faster" | Would require either an npm build step (Tailwind) or fighting the already-established custom spacing/type scale (Pico/Bootstrap) for a problem that is 3-4 media-query rules | Extend the existing hand-rolled `style.css` with `@media` breakpoints |
| A JS library/framework for the mobile nav | Violates the project's explicit "no JS framework, no build step" constraint for a problem that is pure CSS (disclosure widget) | `<details>`/checkbox CSS-only toggle |
| Adding `jinja2-fragments` reactively mid-milestone without a concrete pain point | Premature dependency for a "might need it" concern; the existing partial-template pattern has scaled through 6 phases | Keep current pattern this milestone; revisit only if template duplication becomes a real, felt problem |

## Stack Patterns by Variant

**If a future phase needs automatic FEFO/FIFO batch allocation (explicitly out of scope for
v1.1 per PROJECT.md):**
- Do not retrofit a generic Python inventory-allocation package at that point either — the
  allocation rule (soonest-expiry-first, oldest-first, etc.) is a two-line `ORDER BY` on the
  existing `batches` table. Keep it in the service layer, not a dependency.

**If v2.0 multi-operator sync (deferred) later needs per-warehouse device scoping:**
- `Operation.device_id`/`seq` already exist for sync provenance (D-05); no schema rework is
  needed for warehouses/batches specifically — `batch_id` on `operations` and `warehouse_id` on
  `batches` are both UUID FKs already, so they carry across devices exactly like every other
  UUID-keyed table in this codebase.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| sqlalchemy 2.0.51 | alembic 1.18.5 | Unchanged from v1.0; no version bump needed for composite/partial indexes or additional FK tables — both already used (`0003`'s partial unique index, `0004`'s FK tables) |
| htmx 2.0.10 (vendored) | new batch-picker partial (`hx-get`/`hx-target`/`hx-swap`) | No htmx feature beyond what `sales.py`'s product/customer autocomplete already exercises is required for the batch picker |

## Sources

- Direct inspection of the existing codebase (`app/models.py`, `app/services/ledger.py`,
  `app/services/operations.py`, `app/core.py`, `alembic/versions/0001_initial_schema.py`,
  `alembic/versions/0004_sales_customers.py`, `app/templates/base.html`, `app/static/style.css`,
  `pyproject.toml`) — HIGH confidence, these are the ground truth for what already exists and
  what conventions must be matched.
- `.planning/PROJECT.md` — v1.1 milestone scope, explicit Out of Scope list (batch FIFO costing,
  barcodes) that rules out certain library categories. HIGH confidence (first-party project doc).
- No external package research was performed because the conclusion — zero new runtime
  dependencies — makes version verification of a *new* package moot. The already-pinned
  technologies named in this doc (htmx 2.0.10, SQLAlchemy 2.0.51, Alembic 1.18.5) are carried
  over unchanged from the project's existing, already-verified `CLAUDE.md` stack table and were
  not re-verified per the milestone instructions ("DO NOT re-research the existing stack").

---
*Stack research for: MyOriShop v1.1 — Multi-Warehouse & Batch Tracking*
*Researched: 2026-07-10*
