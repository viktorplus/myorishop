# Phase 21: Customer Profiles & Purchase Insights - Research

**Researched:** 2026-07-17
**Domain:** SQLAlchemy 2.0 aggregate queries + child-table modeling + HTMX repeatable form rows, inside an existing shipped FastAPI/SQLite codebase
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Contact fields storage (CUST-01..04)**

- **D-01: One generic child table, `CustomerContact(id, customer_id, kind, value, label?)`, with a `kind` discriminator** covering all four contact types (`phone`, `telegram`, `email`, `social`), guarded by a SQLite `CHECK (kind IN (...))` constraint (portable to PostgreSQL). Chosen over four separate tables (`CustomerPhone`/`CustomerTelegram`/`CustomerEmail`/`CustomerSocial` — rejected as 4x boilerplate for data that is structurally identical, a label+value pair, per requirements as written) and over JSON/list columns directly on `Customer` (rejected because deleting a single contact would require rewriting a whole array instead of one HTMX row-delete, breaking the app's existing per-row-partial CRUD pattern).
- **D-02: The physical address (CUST-05) is a plain nullable column directly on `Customer`**, independent of D-01 — the requirement wording is singular ("a physical address field"), not "multiple", so it does not belong in the `CustomerContact` table.
- Follow the codebase's existing FK convention: plain `mapped_column(ForeignKey(...))`, no ORM `relationship()`/`back_populates` (there are none anywhere in `app/models.py` today — confirmed by research).

**Contact fields edit UI (CUST-01..04)**

- **D-03: Dynamic repeatable rows added via HTMX**, mirroring the exact pattern already shipped in `app/templates/partials/sale_form.html:74` (`hx-get="/sales/row" hx-target="#basket-rows" hx-swap="beforeend"`) and its row partial `sale_row.html` — an "Добавить строку" button appends a blank input row per contact kind; row removal is a client-side `hx-on:click` with no server round-trip. This repeats 4 times (phone/telegram/email/social) rather than the sale basket's once, but reuses one mental model already proven in this codebase rather than introducing a new UI convention (textarea-per-type was considered and rejected — no textarea exists anywhere in `app/templates` today).
- Each contact row maps to one `CustomerContact` row with its own id — add/delete are per-row HTMX operations, consistent with D-01's schema choice.

**Favorite products ranking (CUST-08)**

- **D-04: One ranked list, sorted by purchase frequency** (count of distinct sale operations/lines for that product), with total quantity sold shown alongside as a secondary column — not a separate ranking and not a blended weighted score (a blended score was explicitly rejected: it would require inventing unweighted business rules nobody asked for and would be unexplainable to the operator, "why is this #1?").
- **D-04a: Show the top 10 products.**
- Query mirrors the existing `purchase_history` join (`app/services/customers.py:202-214`: `Operation` → `Sale` → `Product`, filtered `Sale.customer_id == customer_id, Operation.type == "sale"`), grouped by product with `func.count()` for frequency and `func.sum(-Operation.qty_delta)` for quantity — sale operations store `qty_delta` negated, confirmed against the existing pattern in `app/services/reports.py:47,110,153` and `app/services/returns.py:53`. Returns/write-offs are excluded from the ranking by keeping the `type == "sale"` filter, same as `purchase_history` already does.

**Spend periods (CUST-07)**

- **D-05: Calendar-aligned period-to-date** — current calendar month, current calendar quarter, and current calendar year, each computed from its period start through today via the existing shared helper `local_day_bounds_utc(start_day, end_day, tz_name)` (`app/core.py:75`, the single reused date-math path for all period-based reports since Phase 6). This mirrors the month-preset convention the operator already sees on `/reports/sales` (`app/routes/reports.py`'s `_resolve_period`). Rolling 30/90/365-day windows and "last complete period" were both considered and rejected — rolling windows would silently drift from calendar months the operator is already trained to expect from the reports pages; "last complete period" excludes the customer's activity so far this period, the opposite of "what to act on now" per this phase's own goal.
- **D-06: Spend is net of returns.** The query sums both `sale` and `return` Operation rows for the customer with the SAME formula `-Operation.qty_delta * Operation.unit_price_cents` — a `return` row's `qty_delta` is the positive mirror of the original sale's negative `qty_delta`, at the same frozen `unit_price_cents` (confirmed via `app/services/returns.py`'s frozen-price-copy contract on `register_return`), so the formula nets out returned revenue automatically with zero extra branching. This is a **new** query in `app/services/customers.py`, distinct from `purchase_history()`, which stays `type == "sale"`-only (it displays what was bought, not net financial exposure) — a deliberate scope boundary, not an oversight.

**Phase boundary — explicitly NOT in this phase:** No changes to the sale form's customer picker/new-customer flow (SALE-03..06, Phase 22 — this phase only extends the `Customer` profile itself and its own form/detail pages). No anonymous/walk-in customer row (Phase 22, SALE-06). No structured/validated contact formats (phone number format validation, email format validation) — plain free-text values per the roadmap's Out of Scope note ("A structured multi-provider contacts schema... is unnecessary complexity for a single-operator local tool — plain repeatable text fields suffice").

### Claude's Discretion

- Exact Russian field labels/placeholders for each contact kind (e.g. "Телефон", "Telegram", "Email", "Соцсеть") and the per-section "Добавить строку" button copy.
- Whether `CustomerContact.label` (optional free-text sub-label, e.g. "рабочий"/"личный") ships in this phase or is left null-only for now — CUST-01..04 do not ask for labeled contacts, only for multiple values per kind.
- Exact `kind` CHECK-constraint literal values (`"phone"`, `"telegram"`, `"email"`, `"social"` or Russian equivalents) — internal implementation detail, not operator-facing.
- Layout of the new purchase-insights blocks (last order date, month/quarter/year spend, top-10 favorites) on `customer_detail.html` relative to the existing purchase-history section.
- How "last order date" (CUST-06) is computed — trivially derivable as `max(created_at)` over the existing `purchase_history` rows, or a small dedicated query; no gray area, just an implementation choice.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope. No scope creep occurred across the 4 discussed areas (contact storage, contact UI, favorites ranking, spend periods).

**Research note on D-03:** the two bullets under "Contact fields edit UI" are mutually inconsistent (form-array submit vs per-row server CRUD). This research resolves the conflict in favour of the form-array reading, which is the only one that works on the new-customer form and the only one the cited `sale_form.html`/`sale_row.html` precedent actually implements. See Pitfall 2. All other locked decisions were verified sound as written and are honored unchanged.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CUST-01 | Customer profile supports multiple phone numbers | `CustomerContact` model w/ `kind='phone'` (Code Examples); `Form([], alias="phone[]")` array binding (Pattern 3, verified at `sales.py:392`); Pitfall 1 (named CHECK), Pitfall 2 (form-array not per-row CRUD) |
| CUST-02 | Customer profile supports multiple Telegram handles | Same `CustomerContact` table, `kind='telegram'`; `CONTACT_KINDS` allow-list |
| CUST-03 | Customer profile supports multiple email addresses | Same table, `kind='email'`. No format validation (out of scope per CONTEXT/roadmap) |
| CUST-04 | Customer profile supports other social-network profile links (free-form, multiple) | Same table, `kind='social'`. **Security Domain: the one real threat surface** — render as plain text, not `<a href>`, or allow-list the URL scheme (autoescape alone does not stop `javascript:` in an href) |
| CUST-05 | Customer profile supports a physical address field | `Customer.address` nullable `String(300)` mirroring `Warehouse.address` (`models.py:190`); native `op.add_column`, no batch mode (Pitfall 5, `0005` precedent). Open Question 2: CSV export drift |
| CUST-06 | Customer profile shows the date of the customer's most recent order | Free from the already-loaded `purchase_history` (ordered `created_at DESC` → `history[0]`) — Pitfall 6 / Code Examples. Render with the existing `\| local_dt` filter |
| CUST-07 | Customer profile shows spend totals for the last month, quarter, and year | `spend_totals()` + `_spend_window()` + `_period_starts()` (Code Examples, dual-dialect compiled). Pattern 2 (Python-computed UTC bounds — the `strftime` ban). Pitfall 4 (double coalesce), Pitfall 7 (injectable `today`), Pitfall 8 (return-date attribution / negative totals) |
| CUST-08 | Customer profile shows favorite products, ranked by purchase frequency and quantity | `favorite_products()` copy-adapted from `top_selling_products` (`reports.py:144`), dual-dialect compiled. Pitfall 3 (`count(distinct sale_id)` vs `count(lines)` — Assumption A1). D-04a limit 10; add `Product.name` as a stable tie-break |
</phase_requirements>

## Summary

This phase is **almost entirely codebase-grounded**: every pattern it needs already exists and ships in this repo. No new packages, no new libraries, no external documentation required. The research therefore focused on *verifying* the locked CONTEXT.md decisions against the real code rather than surveying alternatives — and on compiling the proposed queries against both SQLite and PostgreSQL dialects to prove portability.

**All six CONTEXT.md decision groups (D-01..D-06) were verified as sound against the actual code.** In particular D-06's net-of-returns formula — the one decision that could have silently produced wrong money numbers — is confirmed correct: `app/services/returns.py:157` copies `unit_price_cents=origin.unit_price_cents` onto a positive-`qty_delta` return op, so a single `SUM(-qty_delta * unit_price_cents)` over `type IN ('sale','return')` nets returned revenue with zero branching [VERIFIED: read of returns.py].

Four issues were found that the planner **must** resolve, none of which invalidate a locked decision:
1. **`CheckConstraint` has zero precedent in this codebase and hard-fails if unnamed** under the existing `NAMING_CONVENTION` (reproduced live — see Pitfall 1). D-01 introduces the first CHECK constraint in the project.
2. **D-03 is internally ambiguous** about whether contact rows are per-row server CRUD or form-array submit. Only form-array submit works for the "new customer" case (no id yet). See Pitfall 2.
3. **"purchase frequency" (D-04) is under-specified** — `count(lines)` vs `count(distinct sale_id)` give different rankings. See Pitfall 3.
4. **`unit_price_cents` is nullable**, so money aggregates need `coalesce` at two levels. See Pitfall 4.

**Primary recommendation:** Add one `CustomerContact` child table + one `Customer.address` column in a single Alembic migration; add three new read functions to `app/services/customers.py` (`favorite_products`, `spend_totals`, `last_order_date`) built by copy-adapting the already-shipped `top_selling_products` (`app/services/reports.py:144`) and `purchase_history` (`app/services/customers.py:202`) query shapes; submit contact rows as `Form([], alias="phone[]")` arrays exactly like `sale_row.html` already does, and full-replace them on save.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Contact storage (CUST-01..04) | Database / Storage | — | New `customer_contacts` child table + Alembic migration |
| Address storage (CUST-05) | Database / Storage | — | Nullable column on existing `customers` table |
| Contact validation / normalization | API / Backend (`services/customers.py`) | — | House rule: all writes + validation live in the service layer, never the route (`routes/customers.py:1` docstring: "thin routes, all writes in app/services/customers.py") |
| Add/remove contact row UI | Browser / Client (HTMX) | Frontend Server (Jinja2 partial) | `hx-get` returns a blank row partial; removal is client-side only. Mirrors `/sales/row` |
| Last order date (CUST-06) | API / Backend | — | Derived from existing ledger; no storage |
| Spend windows (CUST-07) | API / Backend | — | Period boundaries computed in **Python** (`local_day_bounds_utc`), passed as bound params — the DB never does date math (portability rule) |
| Favorites ranking (CUST-08) | Database / Storage (SQL aggregate) | — | `GROUP BY`/`ORDER BY`/`LIMIT` pushed to SQL, per the `top_selling_products` precedent ("sales history can be large") |
| Money rendering | Frontend Server (Jinja2 `\| cents` filter) | — | Integers stay integers until the template |

**Tier-assignment note for the planner:** date math belongs to the **Python/backend** tier, *never* the database tier. This is the single most important tier boundary in this phase — putting it in the DB means `strftime`, which CLAUDE.md forbids.

## Project Constraints (from CLAUDE.md)

Directives extracted from `CLAUDE.md` that bind this phase:

| Directive | Applies to this phase | Compliance approach |
|-----------|----------------------|---------------------|
| No SQLite-specific SQL; portable ORM constructs only | **Critically** — spend windows are date-filtered | Python-computed UTC bounds as bound params; **no `strftime`**. Verified by dual-dialect compile (see Code Examples) |
| Money as `Integer` minor units; never `FLOAT`/`REAL` | Spend totals, favorites | `SUM()` over integer cents → integer cents; format only at render via `\| cents` |
| SQLAlchemy 2.0 style (`Mapped[]`, `mapped_column()`, `select()`) | `CustomerContact` model | Copy the `Batch`/`Customer` model shape verbatim |
| UUID `String(36)` PK alongside/instead of int PK | `CustomerContact.id` | `mapped_column(String(36), primary_key=True, default=new_id)` — matches every other table |
| Append-only ledger: never UPDATE/DELETE `operations` | Spend/favorites are **read-only** | This phase writes zero ledger rows. `customer_contacts` is a normal mutable table (append-only triggers cover only `operations` and `cash_movements` — verified in `app/db.py` `APPEND_ONLY_TRIGGERS`) |
| Timezone-aware UTC timestamps | Period boundaries | `local_day_bounds_utc` already returns UTC ISO text |
| Alembic with `render_as_batch=True` | New table + new column | Already configured (`alembic/env.py:48,72`). **Neither operation needs batch mode** — see Pitfall 5 |
| htmx 2.0.10 vendored, offline, no CDN | Contact rows UI | Reuse existing vendored `app/static/htmx.min.js`; add no scripts |

Additional binding directive from the **global** CLAUDE.md: **UI strings and operator-facing copy in Russian**; code/comments/commits in English. Every existing template and error constant in this codebase follows this.

## Standard Stack

### Core

No new packages. Everything this phase needs is already installed and pinned.

| Library | Version (installed, verified) | Purpose | Why Standard |
|---------|------------------------------|---------|--------------|
| SQLAlchemy | 2.0.51 | `func.count`/`func.sum`/`func.distinct`/`func.coalesce` aggregates, `CheckConstraint` | Already the project ORM; version confirmed by `uv run python -c "import sqlalchemy; print(sqlalchemy.__version__)"` → `2.0.51` [VERIFIED: local interpreter] |
| Alembic | 1.18.x | One migration: `create_table` + `add_column` | Already configured with `render_as_batch=True` |
| FastAPI | 0.139.x | `Form([], alias="phone[]")` array binding | Pattern already shipped at `app/routes/sales.py:392-395` |
| Jinja2 | 3.1.x | Insights blocks + contact row partials | Existing `\| cents`, `\| local_dt`, `\| ru_date` filters cover all rendering |
| htmx | 2.0.10 (vendored) | `hx-get` blank-row append | Existing `sale_form.html:74` mechanism |
| Python stdlib `datetime` | 3.13 | Calendar period-start math | No `dateutil` needed — see "Don't Hand-Roll" |

### Supporting

None required.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib `date.replace()` quarter math | `python-dateutil` `relativedelta` | Adds a dependency to save ~3 lines. Quarter start is `today.replace(month=3*((today.month-1)//3)+1, day=1)` — verified across 5 boundary dates (see Code Examples). **Do not add dateutil.** |
| One generic `CustomerContact` table (D-01, locked) | 4 typed tables / JSON column | Locked by D-01; both alternatives were reasoned through and rejected in CONTEXT.md. Research concurs — JSON in particular would break the per-row delete UX and has no index story. |

**Installation:**
```bash
# Nothing to install. Verify the existing environment instead:
uv run pytest -q          # baseline: 754 tests collected, all green
```

**Version verification:** Performed against the **installed** environment (`uv run`), not a registry — this phase adds no dependencies, so registry lookups are not applicable. SQLAlchemy 2.0.51 confirmed in-session and matches the CLAUDE.md pin [VERIFIED: local interpreter].

## Package Legitimacy Audit

**Not applicable — this phase installs zero external packages.**

Every library used (SQLAlchemy, Alembic, FastAPI, Jinja2, htmx, pytest) is already a pinned, shipped dependency of this project, vetted in earlier phases. No new package names were sourced from search or training data, so there is no slopsquatting surface in this phase.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
GET /customers/{id}                    POST /customers/{id}
        │                                       │
        ▼                                       ▼
┌──────────────────────┐          ┌────────────────────────────┐
│ routes/customers.py  │          │ routes/customers.py        │
│ customer_detail()    │          │ customer_update()          │
│ (thin: no logic)     │          │ Form arrays: phone[]...    │
└──────────┬───────────┘          └──────────────┬─────────────┘
           │                                     │
           │ 5 independent read calls            │ one service call
           ▼                                     ▼
┌────────────────────────────────┐   ┌────────────────────────────┐
│ services/customers.py (READ)   │   │ services/customers.py      │
│                                │   │ update_customer()          │
│ get_customer() ────────► customers  │  + replace_contacts()      │
│ purchase_history() ──┐         │   │   (validate → full replace)│
│ last_order_date() ───┤         │   └──────────────┬─────────────┘
│ spend_totals() ──────┤         │                  │
│ favorite_products() ─┤         │                  ▼
└──────────────────────┼─────────┘        ┌──────────────────┐
                       │                  │ customer_contacts│
       ┌───────────────┴────────────┐     │ (mutable child)  │
       │ period bounds computed in  │     └──────────────────┘
       │ PYTHON first:              │
       │ local_day_bounds_utc()     │            ▲
       │ → ('2026-06-30T21:00:00+   │            │ FK customer_id
       │    00:00', '...')          │            │
       └───────────────┬────────────┘     ┌──────┴───────┐
                       │ bound params     │  customers   │
                       ▼                  │  + address   │
        ┌──────────────────────────────┐  └──────────────┘
        │ SQL: operations ⋈ sales      │
        │      ⋈ products              │
        │ WHERE sales.customer_id = ?  │
        │   AND created_at >= ?        │   ◄── string compare on
        │   AND created_at <  ?        │       UTC ISO TEXT
        │ (NO strftime, NO date fns)   │       (sorts lexicographically
        └──────────────┬───────────────┘        == chronologically)
                       ▼
        ┌──────────────────────────────┐
        │ integer cents / int qty      │
        └──────────────┬───────────────┘
                       ▼
        ┌──────────────────────────────┐
        │ Jinja2: {{ x | cents }}      │  ◄── ONLY place ints become
        │ templates/pages/             │       display strings
        │   customer_detail.html       │
        └──────────────────────────────┘
```

**The load-bearing arrow:** `local_day_bounds_utc()` → bound params → SQL. Date math happens *before* SQL, never inside it. Reverse that arrow and the PostgreSQL migration breaks.

### Recommended Project Structure

No new directories. Extend in place:

```
app/
├── models.py                          # + CustomerContact, + Customer.address
├── services/customers.py              # + favorite_products, spend_totals,
│                                      #   last_order_date, contact CRUD
├── routes/customers.py                # + /customers/contact-row,
│                                      #   extend detail + create/update
├── templates/
│   ├── pages/customer_detail.html     # + insights blocks
│   ├── pages/customer_form.html       # + 4 contact sections + address
│   └── partials/
│       ├── contact_row.html           # NEW — mirrors sale_row.html
│       ├── customer_insights.html     # NEW (optional split)
│       └── favorite_products.html     # NEW (optional split)
alembic/versions/
└── 0015_customer_contacts.py          # NEW (next free revision — 0014 is HEAD)
tests/
└── test_customers.py                  # extend (19 tests today, all green)
```

Next Alembic revision id is **0015**; `0014_drop_product_catalog_cents.py` is current head [VERIFIED: `ls alembic/versions/`].

### Pattern 1: SQL-side aggregate with a labeled expression reused in ORDER BY

**What:** Build the aggregate once as a labeled expression, use the label object in both `select()` and `.order_by()`.
**When to use:** Both the favorites query (D-04) and the spend query (D-06).
**Example — already shipped in this repo:**
```python
# Source: app/services/reports.py:153-165 (VERIFIED — read in-session)
units_sold = func.sum(-Operation.qty_delta).label("units_sold")
stmt = (
    select(Product, units_sold)
    .join(Operation, Operation.product_id == Product.id)
    .where(
        Operation.type == "sale",
        Operation.created_at >= start_iso,
        Operation.created_at < end_iso,
    )
    .group_by(Product.id)
    .order_by(units_sold.desc())
    .limit(limit)
)
```
The favorites query (D-04) is this shape **plus** a `Sale` join and a `count(distinct)` column. Copy-adapt it; do not invent a new shape.

### Pattern 2: Python-computed UTC window → bound parameters

**What:** Turn local calendar periods into UTC ISO string bounds in Python, then use plain `>=` / `<` string comparisons in SQL.
**When to use:** Every date-filtered query in this codebase, without exception.
**Why it works:** `Operation.created_at` is `String(32)` holding `utcnow_iso()` output (`'2026-07-17T12:00:00+00:00'`), and `local_day_bounds_utc` emits the identical format. ISO-8601 UTC strings sort lexicographically == chronologically (`app/core.py:23` docstring) [VERIFIED: read of core.py + models.py].
**Example:**
```python
# Source: app/routes/reports.py:_resolve_period + app/core.py:75 (VERIFIED)
start_iso, end_iso = local_day_bounds_utc(month_start, today, settings.display_tz)
# -> ('2026-06-30T21:00:00+00:00', '2026-07-17T21:00:00+00:00')  [live output, Europe/Moscow]
stmt = stmt.where(Operation.created_at >= start_iso, Operation.created_at < end_iso)
```
Note the bounds are **half-open** `[start, end)` — `local_day_bounds_utc` returns midnight of the day *after* `end_day` precisely so callers never write a closed range and double-count (`app/core.py:80-86`).

### Pattern 3: Array-named form inputs → `Form([], alias="x[]")`

**What:** Repeatable rows post as `name="phone[]"`; FastAPI binds them to a list.
**When to use:** The contact rows (D-03).
**Example — already shipped:**
```python
# Source: app/routes/sales.py:392-395 (VERIFIED — read in-session)
code: list[str] = Form([], alias="code[]"),
qty: list[str] = Form([], alias="qty[]"),
price: list[str] = Form([], alias="price[]"),
batch_id: list[str] = Form([], alias="batch_id[]"),
```
```jinja
{# Source: app/templates/partials/sale_row.html:15 (VERIFIED) #}
<input type="text" id="{{ code_id }}" name="code[]" value="{{ code or '' }}">
```

### Pattern 4: Service-layer max-length guard mirroring the column

**What:** Validate string length in the service against a module constant that mirrors the declared column width.
**When to use:** `CustomerContact.value`, `CustomerContact.label`, `Customer.address`.
**Why:** `app/services/customers.py:23-29` documents the rationale — SQLite silently truncates an overlong value, PostgreSQL hard-errors, so the service must reject it to keep the future migration safe (WR-05).
```python
# Source: app/services/customers.py:27-29 (VERIFIED)
_NAME_MAX_LEN = 200
_SURNAME_MAX_LEN = 200
_CONSULTANT_NUMBER_MAX_LEN = 50
```

### Anti-Patterns to Avoid

- **`strftime`/`date_trunc`/`EXTRACT` in a query:** breaks the PostgreSQL-is-a-connection-string-change promise. Compute bounds in Python. (CLAUDE.md, explicit.)
- **Reading `Product.sale_cents` for historical spend:** the ledger's frozen `Operation.unit_price_cents` is the only truth. `purchase_history`'s docstring says so and `test_purchase_history_frozen` (`tests/test_customers.py:158`) enforces it. The spend/favorites queries must not regress this.
- **Adding an ORM `relationship()` for `Customer → contacts`:** there are **zero** `relationship()`/`back_populates` declarations anywhere in `app/models.py` [VERIFIED: full read]. Every FK is a bare `mapped_column(ForeignKey(...))`, queried explicitly. D-01's FK must match — introducing lazy-loading relationships here would be a new, unowned convention and a silent N+1 source.
- **Python-side aggregation over the sale ledger:** `top_selling_products`' docstring explicitly rejects this ("sales history can be large, unlike the small fixed-cardinality write-off grouping"). Favorites/spend must aggregate in SQL. (The small, bounded `list_customers_view` filters Python-side — that's a different, deliberately-scoped case; don't cite it as precedent here.)
- **Interpolating a client-supplied row id into an HTMX/JS attribute unvalidated:** `app/routes/sales.py:312-320` validates `row` against `_ROW_ID_RE` before use, citing CR-01. The contact-row route must do the same.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Local-calendar → UTC window | A custom `datetime` juggle per period | `app.core.local_day_bounds_utc` | The **only sanctioned** local→UTC range conversion (`core.py:85` D-02). Handles the half-open upper bound; a hand-rolled closed range double-counts a row landing exactly on UTC midnight |
| Rendering cents | `f"{cents/100:.2f}"` | `app.core.format_cents` / the `\| cents` Jinja filter | Float division on money is the exact thing CLAUDE.md bans |
| Parsing operator money input | `float(text.replace(",","."))` | `app.core.to_cents` | Handles the RU comma separator, `ROUND_HALF_UP`, and rejects `inf`/`nan` (WR-02/WR-03) |
| UTC "now" | `datetime.utcnow()` (naive!) | `app.core.utcnow_iso` | Naive datetimes are banned (`core.py:5`) |
| Row ids / PKs | `uuid4()` inline | `app.core.new_id` | Single sanctioned id factory |
| Quarter-start date | `dateutil.relativedelta` | `today.replace(month=3*((today.month-1)//3)+1, day=1)` | 1 line of stdlib vs a new dependency; verified across quarter boundaries |
| Cyrillic-safe lowercase matching | SQL `lower()`/`LIKE` | Python `str.lower()` + an `_lc` shadow column | SQLite's `lower()` folds ASCII only (`models.py:166`, `customers.py:5-7`). *(Only relevant if contact search is ever added — out of scope here, but do not "fix" it the naive way.)* |
| Last order date | A new dedicated query, if `purchase_history` is already loaded | `max()` over the loaded history rows | See Pitfall 6 — the detail page already loads them |

**Key insight:** This codebase has an unusually disciplined set of "single sanctioned conversion point" helpers (`app/core.py:1-5` states this explicitly). Every hand-rolled alternative in this phase would re-introduce a bug those helpers were written to close. The correct instinct in Phase 21 is *"which existing helper does this?"*, never *"how do I write this?"*.

## Runtime State Inventory

> Not a rename/refactor/migration phase — this section is scoped to the one item that *is* stateful: the new schema.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `customers` table (existing rows) gains a nullable `address` column; new empty `customer_contacts` table | Code + migration only. **No data migration** — `address` is NULL for existing rows and contacts start empty. Nothing to backfill |
| Live service config | None — verified: app runs locally, no external services | None |
| OS-registered state | None — verified: `run.bat` + uvicorn, no scheduler/service registration | None |
| Secrets/env vars | None — verified: no new config keys. `settings.display_tz` (`app/config.py:17`, `Europe/Moscow`) already exists and is reused unchanged | None |
| Build artifacts | None — no compiled artifacts; `uv` venv unchanged since no dependency changes | None |

**Operator-data note:** the migration is additive-only (`add_column` nullable + `create_table`), so a downgrade is lossless for `customers` and merely drops the (new) contacts. The existing `.db` file needs no manual intervention.

## Common Pitfalls

### Pitfall 1: An unnamed `CheckConstraint` hard-fails at DDL compile — and this is the codebase's first one

**What goes wrong:** D-01 calls for `CHECK (kind IN ('phone','telegram','email','social'))`. Writing it the obvious way raises before any SQL is emitted:
```
sqlalchemy.exc.InvalidRequestError: Naming convention including %(constraint_name)s token
requires that constraint is explicitly named.
```
**Why it happens:** `app/models.py:24-30` sets `NAMING_CONVENTION["ck"] = "ck_%(table_name)s_%(constraint_name)s"`. The `%(constraint_name)s` token has no value unless you pass `name=`. **There is not a single `CheckConstraint` anywhere in `app/` or `alembic/` today** [VERIFIED: repo-wide grep returned nothing], so there is no in-repo example to copy — this is genuinely new ground for the project.
**How to avoid:** always pass `name=`:
```python
CheckConstraint("kind IN ('phone','telegram','email','social')", name="kind_valid")
# emits: CONSTRAINT ck_customer_contacts_kind_valid CHECK (kind IN (...))
```
**Warning signs:** import of `app.models` explodes instantly — every test fails to collect, not just the new ones. Reproduced and confirmed in-session [VERIFIED: live SQLAlchemy 2.0.51 probe].

**Additional planner note:** the CHECK is a *DB backstop*, not the primary gate. This codebase's established convention for a closed value set is a **module-level Python dict/tuple allow-list** the service validates against — `OPERATION_TYPES`, `WRITEOFF_REASONS`, `CASH_CATEGORIES` (`models.py:34,49,69`), and `models.py:32-34` explicitly records the decision *not* to add a CHECK to `operations.type`. Ship the Python allow-list (it produces the RU error message; a CHECK produces an untranslatable `IntegrityError`); the CHECK per D-01 rides along as defence-in-depth.

### Pitfall 2: D-03 describes two incompatible contact-row models; only one works

**What goes wrong:** CONTEXT D-03 says both *"an 'Добавить строку' button appends a blank input row … row removal is a client-side `hx-on:click` with no server round-trip"* (form-array model) **and** *"add/delete are per-row HTMX operations"* (server-CRUD model). These contradict. If the planner picks server-CRUD, `POST /customers/{id}/contacts` is unreachable on the **new-customer** form — there is no `customer.id` until the customer is saved (`routes/customers.py:99-101`: `customer_new` renders with `"customer": None`).
**Why it happens:** the sale-basket precedent D-03 cites is itself a form-array flow — rows only become DB rows on final submit. The phrase "per-row HTMX operations" describes the *sale* basket's add-row UX, not its persistence.
**How to avoid:** use the **form-array model** for both create and edit, mirroring `sale_row.html` exactly:
- `hx-get="/customers/contact-row?kind=phone"` appends a blank `<input name="phone[]">` row.
- Removal is client-side DOM removal (no server call).
- On `POST /customers` / `POST /customers/{id}`, bind `phone: list[str] = Form([], alias="phone[]")` (×4 kinds), then **delete-all-and-reinsert** that customer's contacts inside the existing transaction.
Full-replace is safe here because `customer_contacts` is an ordinary mutable table — the append-only triggers cover only `operations` and `cash_movements` [VERIFIED: `app/db.py` `APPEND_ONLY_TRIGGERS`, `models.py:296,380`].
**Warning signs:** a plan task that says "POST a new contact row to the server" while the new-customer form is in scope.

### Pitfall 3: "Purchase frequency" is ambiguous — the two readings rank differently

**What goes wrong:** D-04 says frequency is the *"count of distinct sale operations/lines for that product"* — but `count(Operation.id)` (lines) and `count(distinct Operation.sale_id)` (orders) diverge whenever one basket contains the same product on two lines. A customer who bought product X twice in one order scores 2 under lines and 1 under orders.
**Why it happens:** nothing prevents two `sale` ops for the same product in one sale — different batches produce exactly that (the batch picker writes one op per batch). So this is a **routine** occurrence in this app, not an edge case.
**How to avoid:** use `func.count(func.distinct(Operation.sale_id))`. "How often does this person buy X" means *how many shopping trips included X* — a two-batch split of one purchase is one purchase. Total quantity is already the D-04 secondary column, so per-line volume is not lost.
**Warning signs:** a customer whose favorite is a product they bought once, from a batch-split order.
**Confidence:** the *ambiguity* is [VERIFIED] (both readings compile and diverge); the *recommendation* is [ASSUMED] — it is my reading of operator intent, not a stated user decision. See Assumptions Log A1.

### Pitfall 4: `unit_price_cents` is nullable — money aggregates need `coalesce` twice

**What goes wrong:** `Operation.unit_price_cents` is `Mapped[int | None]` (`models.py:308`). In SQL, `NULL * anything` is `NULL`, and `SUM()` skips NULLs — so a price-less line silently contributes nothing. Worse, if *every* matching row is NULL (or there are no rows at all), `SUM()` returns `NULL`, and `spend_totals()` hands the template `None`, which `| cents` will choke on.
**Why it happens:** cost/price were optional in early phases; `sales_profit_report` documents this exact hazard as its own "RESEARCH Pitfall 2" (`reports.py:22-30`) and handles it Python-side with `(op.unit_price_cents or 0)`. A SQL-side aggregate needs the SQL equivalent.
**How to avoid:** coalesce at **both** levels, matching the shipped `returns.py:56` precedent (`func.coalesce(func.sum(...), 0)`):
```python
func.coalesce(func.sum(-Operation.qty_delta * func.coalesce(Operation.unit_price_cents, 0)), 0)
```
**Warning signs:** a customer with zero orders renders `None` instead of `0,00`, or a `TypeError` inside the `cents` filter. **A "customer with no orders at all" test is mandatory** — it is the likeliest first bug in this phase.

### Pitfall 5: `render_as_batch` is configured — but neither DDL op here needs it

**What goes wrong:** a planner reads "SQLite needs batch mode" and wraps `create_table`/`add_column` in `op.batch_alter_table`, which triggers a move-and-copy of the whole `customers` table.
**Why it happens:** `render_as_batch=True` is set in `alembic/env.py:48,72` — but it only affects *autogenerate rendering* of operations that genuinely need table rebuilds (drop column, alter type, add constraint to an existing table).
**How to avoid:** use native ops. Migration `0005_product_thresholds.py` is the exact precedent and states the rule in its own docstring: *"Native ADD COLUMN, no batch mode … never batch-alter a table whose migrations must stay replayable forever."* [VERIFIED: read of 0005]. A brand-new table needs `op.create_table`; a nullable column needs `op.add_column`. Both are natively supported by SQLite.
**Also:** migration files **must never import application modules** — `0005`'s docstring calls this the immutability rule (WR-06). The `kind` allow-list literals must be re-declared as frozen strings in `0015`, **not** imported from `app.models`.
**Warning signs:** a migration that copies `customers` — that's a data-loss risk for zero benefit.

### Pitfall 6: N+1 is not the risk here; redundant whole-history scans are

**What goes wrong:** the naive detail page issues: 1 customer + 1 history + 1 last-order + 3 spend windows + 1 favorites = 7 queries — and `purchase_history` already returns every row needed to compute last-order-date for free (it's ordered `created_at DESC`, so `history[0]` *is* the most recent).
**Why it happens:** each insight is written as an independent function without noticing the detail route already loads the full history (`routes/customers.py:132`).
**How to avoid:** there is **no N+1** in the classic sense — no lazy-loading relationships exist to trigger one (see Anti-Patterns). Each query is a single flat aggregate. Keep it that way, and take the free win: derive `last_order_date` (CUST-06) from the already-loaded `purchase_history` rows rather than issuing a 7th query. CONTEXT explicitly leaves this to Claude's discretion.
The 3 spend windows are 3 separate cheap aggregates — **do not** try to fuse them into one query with conditional sums; that would need `CASE WHEN`, hurt readability, and save nothing at single-operator scale. Five focused queries is the right shape.
**Warning signs:** any `for` loop that issues a query per product or per contact.

### Pitfall 7: In Jan/Apr/Jul/Oct, month spend == quarter spend — tests must inject the date

**What goes wrong:** a test asserting "month total differs from quarter total" passes in February and fails in April. Today is **2026-07-17**, and July *is* Q3's first month — so month-to-date and quarter-to-date are **identical right now** (both bounds `2026-06-30T21:00:00+00:00 → 2026-07-17T21:00:00+00:00`) [VERIFIED: live computation].
**Why it happens:** period starts are derived from `datetime.now(tz)`, making the assertion's truth a function of the calendar.
**How to avoid:** make the period-start helper take an injectable `today: date` parameter (defaulting to `datetime.now(ZoneInfo(settings.display_tz)).date()`), exactly as `stale_products` isolates `today_local` (`reports.py:194`). Tests then pass a fixed date. This is also the only way to test "a sale 13 months ago is excluded from the year window" deterministically.
**Warning signs:** a test that reads `date.today()`; a suite that goes red on the 1st of a quarter.
**Operator-facing note (not a bug):** the operator will see two identical numbers for all of July. That is correct calendar-period-to-date behaviour per D-05, but the planner may want the labels to make the periods unambiguous (e.g. «Июль» / «III квартал» rather than bare «Месяц»/«Квартал»).

### Pitfall 8: A return is attributed to the window of the RETURN date, not the sale date

**What goes wrong:** a customer buys 10 000 ₽ of product in June and returns it in July. July's month spend shows **−10 000 ₽** — a negative number on the profile.
**Why it happens:** D-06 filters `Operation.created_at` for both `sale` and `return` rows, and a return op's `created_at` is when the return was *registered*. This is cash-basis attribution, and it is consistent with how `finance`'s cash ledger already books the debit (`returns.py:168-176`: the debit is written at return time).
**How to avoid:** this is **arguably correct** and matches the operator's stated intent ("how much money is left from this customer" — CONTEXT specifics). Do not "fix" it by re-attributing to the origin sale's date; that would silently disagree with the Finance pages and would need a join back to the origin op. **But the template must handle a negative total** — `format_cents` already renders a leading `-` correctly (`core.py:50-53`, verified), so this is a display/CSS concern, not a math one.
**Warning signs:** a template that assumes spend ≥ 0, or a `.num` cell that styles negatives as an error.

## Code Examples

All examples below were **compiled against both the SQLite and PostgreSQL dialects in-session** to prove portability [VERIFIED: live SQLAlchemy 2.0.51].

### Favorite products, ranked by frequency then quantity (CUST-08 / D-04)

```python
# app/services/customers.py — copy-adapted from reports.py:144 top_selling_products
def favorite_products(session: Session, customer_id: str, limit: int = 10) -> list[dict]:
    """Top products for one customer by purchase frequency (D-04/D-04a).

    Frequency = count of DISTINCT sales containing the product (not lines):
    a batch-split purchase writes 2 sale ops in 1 sale and must count once.
    Quantity is the secondary sort key and a displayed column.
    `type == "sale"` only — mirrors purchase_history: this ranks what was
    BOUGHT, not net financial exposure (returns are spend_totals' concern).
    """
    freq = func.count(func.distinct(Operation.sale_id)).label("freq")
    qty = func.coalesce(func.sum(-Operation.qty_delta), 0).label("qty")
    stmt = (
        select(Product, freq, qty)
        .join(Operation, Operation.product_id == Product.id)
        .join(Sale, Operation.sale_id == Sale.id)
        .where(Sale.customer_id == customer_id, Operation.type == "sale")
        .group_by(Product.id)
        .order_by(freq.desc(), qty.desc())
        .limit(limit)
    )
    return [
        {"product": product, "freq": f, "qty": q}
        for product, f, q in session.execute(stmt).all()
    ]
```

Compiles to (SQLite — note zero date functions, all values bound):
```sql
SELECT products.id, ..., count(distinct(operations.sale_id)) AS freq,
       coalesce(sum(-operations.qty_delta), ?) AS qty
FROM products JOIN operations ON operations.product_id = products.id
              JOIN sales ON operations.sale_id = sales.id
WHERE sales.customer_id = ? AND operations.type = ?
GROUP BY products.id ORDER BY freq DESC, qty DESC LIMIT ? OFFSET ?
```
The PostgreSQL render is byte-identical apart from paramstyle (`%(name)s` vs `?`) and the `LIMIT`/`OFFSET` clause. **Tie-breaking:** `freq DESC, qty DESC` leaves ties on *both* keys in DB-arbitrary order. For a stable, reproducible list add a third deterministic key — `.order_by(freq.desc(), qty.desc(), Product.name)`. Recommended; without it a test asserting exact ordering of two equal-scoring products is flaky.

Deliberately **not** filtering `Product.deleted_at`: this is a historical view, matching `sales_profit_report`'s documented "Pitfall 5" rule (`reports.py:30-33`). A soft-deleted product a customer genuinely loved still belongs in their history.

### Net spend for one window (CUST-07 / D-05 + D-06)

```python
def _spend_window(session: Session, customer_id: str, start_iso: str, end_iso: str) -> int:
    """Net cents for one UTC [start_iso, end_iso) window (D-06: net of returns).

    ONE formula for both types: a `sale` op has qty_delta<0 (=> positive
    revenue), a `return` op has qty_delta>0 at the SAME frozen
    unit_price_cents (returns.py:157 D-07 frozen copy) => negative revenue.
    The sum nets automatically; no branching.
    Double coalesce (Pitfall 4): unit_price_cents is nullable, and SUM over
    zero rows is NULL.
    """
    net = func.coalesce(
        func.sum(-Operation.qty_delta * func.coalesce(Operation.unit_price_cents, 0)), 0
    )
    return session.scalar(
        select(net)
        .join(Sale, Operation.sale_id == Sale.id)
        .where(
            Sale.customer_id == customer_id,
            Operation.type.in_(("sale", "return")),
            Operation.created_at >= start_iso,
            Operation.created_at < end_iso,
        )
    )
```

Compiles to (SQLite):
```sql
SELECT coalesce(sum((-operations.qty_delta) * coalesce(operations.unit_price_cents, ?)), ?)
FROM operations JOIN sales ON operations.sale_id = sales.id
WHERE sales.customer_id = ? AND operations.type IN (?, ?)
  AND operations.created_at >= ? AND operations.created_at < ?
```
The `sales` join is valid for `return` rows: `register_return` sets `sale_id=origin.sale_id` (`returns.py:159`), so returns are reachable from the customer [VERIFIED].

### Calendar period starts + the three windows (D-05)

```python
def _period_starts(today: date) -> dict[str, date]:
    """Calendar period-to-date starts. `today` is INJECTABLE (Pitfall 7)."""
    return {
        "month": today.replace(day=1),
        "quarter": today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1),
        "year": today.replace(month=1, day=1),
    }


def spend_totals(session: Session, customer_id: str, today: date | None = None) -> dict[str, int]:
    """Net spend cents for month/quarter/year period-to-date (CUST-07)."""
    tz_name = settings.display_tz
    if today is None:
        today = datetime.now(ZoneInfo(tz_name)).date()
    return {
        name: _spend_window(session, customer_id, *local_day_bounds_utc(start, today, tz_name))
        for name, start in _period_starts(today).items()
    }
```

Quarter math verified across boundaries [VERIFIED: live execution]:

| `today` | month | quarter | year |
|---------|-------|---------|------|
| 2026-07-17 | 2026-07-01 | 2026-07-01 | 2026-01-01 |
| 2026-01-01 | 2026-01-01 | 2026-01-01 | 2026-01-01 |
| 2026-03-31 | 2026-03-01 | 2026-01-01 | 2026-01-01 |
| 2026-04-01 | 2026-04-01 | 2026-04-01 | 2026-01-01 |
| 2026-12-31 | 2026-12-01 | 2026-10-01 | 2026-01-01 |

### Last order date (CUST-06) — free from the already-loaded history

```python
# In routes/customers.py customer_detail, history is ALREADY loaded and is
# ordered created_at DESC (customers.py:212) -> row 0 IS the most recent.
history = purchase_history(session, customer_id)
last_order_iso = history[0]["op"].created_at if history else None
```
Render with the existing `| local_dt` filter (as `purchase_history.html` already does). If the planner prefers a standalone function for symmetry, `select(func.max(Operation.created_at)).join(Sale, ...)` mirrors `stale_products`' `last_sale` shape (`reports.py:182`) — but it is a 7th query for data already in memory.

### `CustomerContact` model (D-01) — note the mandatory constraint name

```python
CONTACT_KINDS = {          # Python allow-list = the primary gate (Pitfall 1)
    "phone": "Телефон",
    "telegram": "Telegram",
    "email": "Email",
    "social": "Соцсеть",
}


class CustomerContact(Base):
    """One reachable contact value for a customer (CUST-01..04).

    D-01: one generic table with a `kind` discriminator — all four kinds
    share an identical label+value shape. No relationship() (house rule):
    the FK is a bare mapped_column, queried explicitly.
    """

    __tablename__ = "customer_contacts"
    __table_args__ = (
        # name= is MANDATORY: NAMING_CONVENTION's ck_%(table_name)s_%(constraint_name)s
        # raises InvalidRequestError without it (verified).
        CheckConstraint(
            "kind IN ('phone', 'telegram', 'email', 'social')", name="kind_valid"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[str] = mapped_column(String(300), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso)
    updated_at: Mapped[str] = mapped_column(String(32), default=utcnow_iso, onupdate=utcnow_iso)
```
`index=True` on `customer_id` matches every other FK in the file (`Operation.sale_id`, `Batch.product_id`, `Sale.customer_id`) and is what makes the profile-page contact fetch a single indexed lookup.

**`PRAGMA foreign_keys=ON` is active** (`app/db.py`, `tests/test_pragmas.py` guards it), so the FK is enforced at runtime — a contact can never orphan.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Query`/`session.query()` 1.x style | `select()` + `session.execute()/scalars()` | SQLAlchemy 2.0 | Already the codebase style everywhere; keep it. Web tutorials showing `session.query(...)` are 1.x-era and must not be copied (CLAUDE.md explicitly warns) |
| `declarative_base()` | `class Base(DeclarativeBase)` + `Mapped[]`/`mapped_column()` | SQLAlchemy 2.0 | `models.py:125` already correct |

**Deprecated/outdated (observed in this repo, not this phase's problem):**
- `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` — emitted by every `client`-fixture test run today. **Pre-existing, unrelated to Phase 21, and out of scope.** Flagging only so it is not mistaken for a regression introduced by this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | "Purchase frequency" should be `count(distinct sale_id)` (orders containing the product), not `count(lines)` | Pitfall 3, Code Examples | Favorites ranking is wrong in a way the operator would notice but might not diagnose. **Low blast radius, cheap to flip** (one expression). Worth one confirming question at plan time |
| A2 | Showing top-10 favorites by frequency with quantity as a secondary column satisfies CUST-08's "ranked by purchase frequency **and** quantity" | Code Examples | CUST-08's wording could be read as demanding a blended score. CONTEXT D-04 **explicitly rejected** a blended score with reasoning, so this is a locked user decision, not my assumption — recorded here only because the requirement text and the decision differ in wording |
| A3 | Negative spend totals (Pitfall 8) are acceptable to display rather than clamped to 0 | Pitfall 8 | Operator confusion at worst; the number is arithmetically correct and `format_cents` renders it fine. Display-layer decision, trivially reversible |
| A4 | Contact `value` max length of 300 chars is adequate (matches `Warehouse.address`'s `String(300)`) | Code Examples | An over-long social URL is rejected with an RU error. Column width is the one thing that is *expensive* to change later on SQLite — but 300 comfortably exceeds real phone/email/handle lengths and matches in-repo precedent |
| A5 | `Customer.address` should be `String(300)`, mirroring `Warehouse.address` (`models.py:190`) | Architecture | Same as A4; the in-repo precedent for "a physical address" is exactly `String(300)`, so this is well-grounded |

**Everything else in this document is `[VERIFIED]`** — read from the codebase, compiled against both dialects, or executed in-session. This is an unusually high-confidence research phase precisely because the answers were all *in the repo*, not on the web.

## Open Questions (RESOLVED)

> All three were resolved during planning (2026-07-17). Each recommendation below was
> accepted; see the `RESOLVED:` line under each for where the decision now lives.

1. **Should `CustomerContact.label` ship in this phase?**
   - What we know: CONTEXT lists this as explicitly Claude's discretion. CUST-01..04 ask only for *multiple values per kind*, never for labeled ones.
   - What's unclear: whether the operator wants «рабочий»/«личный» sub-labels.
   - Recommendation: **include the nullable column in the migration, but do not surface it in the UI.** Adding a nullable column later to SQLite is cheap, but a *second* migration for a field we already know might be wanted is churn. Zero UI cost, keeps the form simple, and the column costs nothing if unused. This is the one place where speculative schema is justified — the requirement's own shape (a value that may want a name) predicts it.
   - **RESOLVED:** recommendation accepted — nullable `label` column ships in migration 0015, no UI surface. Decided in `21-01-PLAN.md` (objective).

2. **Do the CSV export and the `customers.csv` contract need updating for `address`?**
   - What we know: `app/services/export.py:152-169` `stream_customers_csv` hardcodes `header = ["Имя", "Фамилия", "Номер консультанта", "Создан"]` and is described as a *"Full customer profile dump."* `tests/test_export.py:296` round-trips it.
   - What's unclear: Phase 21 has no export requirement, but the docstring's promise ("full profile dump") becomes false the moment address/contacts exist.
   - Recommendation: **out of scope — do not change the export in this phase.** Flag it for the planner to note as a known documentation/behaviour drift. If the planner wants a cheap win, adding `"Адрес"` to the header + `_csv_safe(customer.address or "")` to the row is a 2-line change with one test update — but contacts (a 1-to-many) genuinely do not fit the flat CSV shape and must not be forced in here.
   - **RESOLVED:** recommendation accepted — export is out of scope and written into `21-01-PLAN.md` / `21-02-PLAN.md` as an explicit do-not-touch. The stale *"full customer profile dump"* docstring is **accepted debt**, recorded in STATE.md Deferred Items for a future phase.

3. **Is `/customers/contact-row` the right route name?**
   - What we know: the precedent is `GET /sales/row` (`routes/sales.py:312`). Route order matters: `routes/customers.py:22-25` warns that literal paths **must** be declared before `/customers/{customer_id}`.
   - Recommendation: `GET /customers/contact-row?kind=phone`, declared **above** `customer_detail`. Otherwise `/customers/{customer_id}` swallows it and the operator gets a 404-shaped surprise. Validate `kind` against `CONTACT_KINDS` and reject unknown values — the kind is interpolated into the rendered input's `name`, so it is untrusted input (the CR-01 rule from `/sales/row`).
   - **RESOLVED:** recommendation accepted — `GET /customers/contact-row`, declared above `customer_detail`, `kind` allow-listed → 404. Decided in `21-04-PLAN.md` (Task 1), with a line-number acceptance criterion plus `test_web_contact_row_route_declared_before_customer_detail`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Everything | ✓ | 3.13 (venv; `.pyc` shows 3.11 + 3.13 caches) | — |
| uv | Run/test commands | ✓ | present (`uv run` works) | pip + venv |
| SQLAlchemy | Models, queries | ✓ | 2.0.51 | — |
| pytest | Validation | ✓ | 9.1.x — 754 tests collect, `test_customers.py` 19/19 green | — |
| Alembic | Migration 0015 | ✓ | configured, head = 0014 | — |
| htmx (vendored) | Contact rows | ✓ | 2.0.10 at `app/static/htmx.min.js` | — |
| Internet | — | not required | — | Phase is fully offline-capable |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none.

**Baseline verified in-session:** `uv run pytest tests/test_customers.py -q` → **19 passed**; `uv run pytest -q --collect-only` → **754 tests collected**. The suite is green before this phase starts, so any red is attributable to Phase 21 work.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.x |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` (`testpaths = ["tests"]`, `pythonpath = ["."]`) |
| Quick run command | `uv run pytest tests/test_customers.py -q` (~4.3s, 19 tests today) |
| Full suite command | `uv run pytest -q` (754 tests) |

Conventions to follow (from `tests/test_customers.py:11-14`): route/e2e tests are prefixed `test_web_`; everything else is service-level. Fixtures `session`, `client`, `customer`, `stocked_product` already exist in `tests/conftest.py`; seed sales via `register_sale` + `_only_batch(session, product)` as the existing history tests do.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CUST-01 | Multiple phones persist + render | integration | `uv run pytest tests/test_customers.py -k contacts_phone -x` | ✅ extend |
| CUST-02 | Multiple Telegram handles persist | integration | `uv run pytest tests/test_customers.py -k contacts_telegram -x` | ✅ extend |
| CUST-03 | Multiple emails persist | integration | `uv run pytest tests/test_customers.py -k contacts_email -x` | ✅ extend |
| CUST-04 | Multiple social links persist | integration | `uv run pytest tests/test_customers.py -k contacts_social -x` | ✅ extend |
| CUST-01..04 | Blank rows discarded; kind allow-list rejects unknown kind | unit | `uv run pytest tests/test_customers.py -k contacts_validation -x` | ✅ extend |
| CUST-01..04 | Re-saving replaces (not duplicates) contacts | integration | `uv run pytest tests/test_customers.py -k contacts_replace -x` | ✅ extend |
| CUST-01..04 | Contacts survive the **new-customer** create path (Pitfall 2) | integration | `uv run pytest tests/test_customers.py -k web_customer_create_with_contacts -x` | ✅ extend |
| CUST-05 | Address persists + renders | integration | `uv run pytest tests/test_customers.py -k address -x` | ✅ extend |
| CUST-06 | Last order date = most recent sale | unit | `uv run pytest tests/test_customers.py -k last_order -x` | ✅ extend |
| CUST-06 | Customer with zero orders → no date, no crash | unit | `uv run pytest tests/test_customers.py -k last_order_empty -x` | ✅ extend |
| CUST-07 | Month/quarter/year totals with **injected** `today` (Pitfall 7) | unit | `uv run pytest tests/test_customers.py -k spend_totals -x` | ✅ extend |
| CUST-07 | Return subtracts from spend (D-06 net) | unit | `uv run pytest tests/test_customers.py -k spend_net_of_returns -x` | ✅ extend |
| CUST-07 | Sale outside the window excluded | unit | `uv run pytest tests/test_customers.py -k spend_window_excludes -x` | ✅ extend |
| CUST-07 | **Zero orders → 0, not None** (Pitfall 4) | unit | `uv run pytest tests/test_customers.py -k spend_empty -x` | ✅ extend |
| CUST-07 | NULL `unit_price_cents` line doesn't crash the sum (Pitfall 4) | unit | `uv run pytest tests/test_customers.py -k spend_null_price -x` | ✅ extend |
| CUST-08 | Favorites ranked by frequency, qty secondary | unit | `uv run pytest tests/test_customers.py -k favorite_products -x` | ✅ extend |
| CUST-08 | Batch-split purchase counts once (Pitfall 3) | unit | `uv run pytest tests/test_customers.py -k favorites_batch_split -x` | ✅ extend |
| CUST-08 | Capped at 10 (D-04a) | unit | `uv run pytest tests/test_customers.py -k favorites_limit -x` | ✅ extend |
| CUST-08 | Scoped to THIS customer only | unit | `uv run pytest tests/test_customers.py -k favorites_scoped -x` | ✅ extend |
| CUST-06..08 | Detail page renders all insight blocks | e2e | `uv run pytest tests/test_customers.py -k web_customer_detail_insights -x` | ✅ extend |
| — (regression) | Frozen-price contract still holds | unit | `uv run pytest tests/test_customers.py -k frozen -x` | ✅ exists (`test_purchase_history_frozen`) |
| — (regression) | Migration 0015 applies to a 0014 DB | smoke | `uv run alembic upgrade head` | ⚠️ manual — no migration test harness exists in this repo |

**Portability guard (recommended, high value / low cost):** add one test that compiles the new statements against the PostgreSQL dialect and asserts `"strftime" not in sql`. This mechanically enforces the CLAUDE.md rule that is otherwise only enforced by reviewer memory, and it is the single highest-leverage test in this phase:

```python
def test_spend_query_is_portable():
    from sqlalchemy.dialects import postgresql
    sql = str(_spend_stmt("x", "A", "B").compile(dialect=postgresql.dialect()))
    assert "strftime" not in sql
```

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_customers.py -q` (~4.3s — fast enough to run on every commit)
- **Per wave merge:** `uv run pytest -q` (754 tests) + `uv run ruff check` + `uv run ruff format --check`
- **Phase gate:** full suite green + `uv run alembic upgrade head` applied cleanly to a copy of a real 0014-era `.db` before `/gsd-verify-work`

**Rationale for the rate:** the per-commit sample is one file because the phase's blast radius is one file's worth of surface — but `app/models.py` is imported by *everything*, so the CHECK-constraint pitfall (Pitfall 1) would take the whole suite red. That is precisely why the full suite runs at wave merge and not only at the phase gate: a models.py mistake must not survive a wave.

### Wave 0 Gaps

- [ ] No new test files needed — `tests/test_customers.py` and `tests/conftest.py` already exist and cover the fixtures this phase needs (`session`, `client`, `customer`, `stocked_product`).
- [ ] **Fixture gap:** no fixture seeds a sale at a **controlled past date**. Every CUST-07 window test needs one (a sale 2 months ago must fall outside the month window but inside the year window). `record_operation` sets `created_at` itself — the plan must establish how tests place a sale in the past. Recommended: a small helper in `test_customers.py` that inserts an `Operation` + `Sale` with an explicit `created_at` **directly via the session**, bypassing `record_operation`. This is safe *for reads* (the append-only triggers block UPDATE/DELETE, not INSERT) and avoids monkeypatching `utcnow_iso` globally. **This is the single most likely thing to block Wave 1 — resolve it in Wave 0.**
- [ ] Framework install: none — pytest 9.1.x present and green.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single local operator, no auth in v1 by explicit project decision (CLAUDE.md: *"Do not add auth machinery in v1"*). Contact PII is protected by the machine's own login, not the app |
| V3 Session Management | no | No sessions exist |
| V4 Access Control | no | No multi-user model. **Note for v2 sync:** contact data is the most PII-dense table this app will have — when multi-operator sync lands, `customer_contacts` is the row set that most needs an access-control story. Out of scope now; worth a line in STATE.md |
| V5 Input Validation | **yes** | Service-layer validation before write (house rule): `kind` gated against the `CONTACT_KINDS` allow-list; `value`/`label`/`address` length-guarded against module constants mirroring column widths (WR-05 precedent, `customers.py:23-29`). `limit`/`page` never string-interpolated |
| V6 Cryptography | no | No secrets, no hashing, no crypto in this phase |

### Known Threat Patterns for FastAPI + SQLAlchemy + Jinja2 + HTMX

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via contact value / `kind` | Tampering | SQLAlchemy Core constructs only — every value is a bound parameter (proven in the compiled SQL above: all literals render as `?`). **Never** f-string a value into a query |
| SQL injection via sort/filter key | Tampering | Allow-list map, never interpolation — the `_SORT_MAP` precedent (`customers.py:150-153`) cites T-14-18 for exactly this |
| **XSS via a stored social-profile URL** | Tampering / Elevation | **The top threat in this phase.** CUST-04 stores operator-supplied free-form links, which are then rendered. Jinja2 autoescape (on by default, and `purchase_history.html:3` states the house rule: *"Autoescape only; never \|safe"*) neutralizes the HTML-injection vector. **But if a social link is rendered as a clickable `<a href="{{ c.value }}">`, autoescape does NOT stop `javascript:` URLs.** If the planner makes links clickable, the scheme must be allow-listed to `http`/`https` server-side. **Safest for this phase: render contact values as plain text, not anchors.** No requirement asks for clickable links |
| XSS via `kind` interpolated into a rendered input `name` | Tampering | Validate `kind` against `CONTACT_KINDS` in the `/customers/contact-row` route before rendering — the CR-01 rule `/sales/row` already follows with `_ROW_ID_RE` (`sales.py:312-320`) |
| CSV injection via exported contact data | Tampering | `_csv_safe` already exists in `app/services/export.py` and is applied to every customer field. **Only relevant if Open Question 2 is answered "yes"** — if `address` is added to the export, it must go through `_csv_safe` like every sibling field |
| Mass assignment via extra form fields | Tampering | Routes bind named `Form(...)` params explicitly; no `**kwargs` splat into the model. Existing convention, keep it |
| Orphaned/dangling contact rows | — (integrity) | `PRAGMA foreign_keys=ON` is enforced and guarded by `tests/test_pragmas.py`; the FK makes orphans impossible |

**Security summary:** this phase's realistic threat surface is **one item — stored XSS via the free-form social link (CUST-04)**, and it is already closed by the codebase's autoescape-only rule *provided the value is not rendered as an `href`*. Everything else is inherited mitigation. The planner should treat "are contact values clickable?" as a security-relevant decision, not a cosmetic one.

## Sources

### Primary (HIGH confidence)

Codebase reads — the authoritative source for this phase (all read in-session, 2026-07-17):
- `app/models.py` — `Customer` (333-351), `Operation` (295-331), `Sale` (354-370), `Batch`, `NAMING_CONVENTION` (24-30), allow-list dicts (34-122), no `relationship()` anywhere
- `app/services/customers.py` — `purchase_history` (202-214), `_SORT_MAP` (150-153), WR-05 length guards (23-29)
- `app/services/reports.py` — `top_selling_products` (144-167), `sales_profit_report` (20-82), `stale_products` (170-221)
- `app/services/returns.py` — `register_return` D-07 frozen-price copy (157-158), `sold_qty` coalesce precedent (55-62)
- `app/core.py` — `local_day_bounds_utc` (75-93), `format_cents` (49-53), `to_cents` (28-46), `utcnow_iso` (20-25)
- `app/routes/customers.py` — thin-route convention, route-order warning (22-25), `customer_detail` (127-133)
- `app/routes/sales.py` — `Form([], alias="code[]")` (392-395), `/sales/row` + CR-01 validation (312-320)
- `app/routes/reports.py` — `_resolve_period` (32-60)
- `app/services/export.py` — `stream_customers_csv` (152-169)
- `app/templates/partials/sale_form.html` (74), `sale_row.html` (1-30), `purchase_history.html`, `pages/customer_detail.html`, `pages/customer_form.html`
- `alembic/versions/0005_product_thresholds.py` — native-ADD-COLUMN + WR-06 immutability rule; `0014` = current head
- `tests/test_customers.py` (19 tests), `tests/conftest.py` (fixtures), `pyproject.toml` (pytest/ruff config)

Live execution — claims proven, not assumed:
- SQLAlchemy 2.0.51 confirmed via `uv run python -c "import sqlalchemy; print(sqlalchemy.__version__)"`
- Favorites + spend statements compiled against **both** `sqlite.dialect()` and `postgresql.dialect()` — no date functions, all bound params
- Unnamed `CheckConstraint` → `InvalidRequestError` reproduced; named → `ck_customer_contacts_kind_valid` emitted correctly
- Quarter-start math executed across 5 boundary dates; `local_day_bounds_utc` output inspected for all 3 windows
- `uv run pytest tests/test_customers.py -q` → 19 passed; `--collect-only` → 754 collected
- Repo-wide grep: `CheckConstraint` → **zero matches** in `app/` and `alembic/`

### Secondary (MEDIUM confidence)
- `.planning/phases/21-.../21-CONTEXT.md` — locked decisions D-01..D-06 (each independently re-verified against the code above; D-02's line refs and D-06's frozen-price contract both check out exactly as written)
- `.planning/REQUIREMENTS.md` §Customers (CUST-01..08), §Out of Scope
- `CLAUDE.md` — stack pins, "What NOT to Use" table

### Tertiary (LOW confidence)
- None. **No web search was performed and none was warranted** — every question this phase raised was answerable from the repository itself, which is a stronger source than any external documentation would have been.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — zero new dependencies; installed versions verified in-session
- Architecture: **HIGH** — every pattern copy-adapted from shipped, tested code; queries compiled against both target dialects
- Pitfalls: **HIGH** — Pitfalls 1, 4, 7 reproduced live; 2, 3, 5, 6, 8 derived from direct code reads with line citations
- Validation: **HIGH** — baseline suite green (754 collected / 19 in scope), commands executed, one real Wave-0 fixture gap identified
- Favorites frequency semantics: **MEDIUM** — the ambiguity is verified, the recommended resolution is a judgment call (A1)

**Research date:** 2026-07-17
**Valid until:** 2026-08-16 (30 days — stable, fully-pinned local stack with no external moving parts; findings are invalidated only by changes to this repo, not by upstream releases)
