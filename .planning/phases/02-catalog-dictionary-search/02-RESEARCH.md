# Phase 2: Catalog, Dictionary & Search - Research

**Researched:** 2026-07-08
**Domain:** SQLite/SQLAlchemy catalog CRUD, Cyrillic-safe search, HTMX active search & autofill, ledger-audited price history
**Confidence:** HIGH (all load-bearing claims verified against the on-disk Phase 1 codebase, empirically against the project's own SQLite 3.50.4, or against official docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Product Cards
- Pages: /products (list + search), /products/new (create), /products/{id}/edit (edit); product card detail shows price history
- Fields: code (required, unique among non-deleted), name (required), category (optional free text with datalist suggestions from existing categories), cost_cents, sale_cents, catalog_cents (all optional)
- Soft delete via deleted_at; deleted products hidden from lists/search; operations on soft-deleted products are REJECTED in the service layer (resolves review finding IN-01)
- Direct stock quantity editing stays impossible (corrections only, Phase 5)

#### Reference Dictionary
- Separate `dictionary` table: code (PK, TEXT), name (TEXT) — pre-loadable code→name reference, editable via simple UI page /dictionary (add/edit rows, paste-friendly)
- On product create / receipt forms: typing a known code auto-fills name via HTMX GET lookup (debounced ~300ms)
- Dictionary is a helper only; products remain the catalog source of truth

#### Search
- Instant search on /products: single input, HTMX-driven partial results (debounced ~300ms), case-insensitive LIKE on code prefix and name substring
- Results ranked: exact code match first, code prefix next, name substring last; cap 20 rows
- Cyrillic case-insensitivity: normalize with Python-side lower() comparison via SQLAlchemy func.lower (SQLite NOCASE is ASCII-only) — store a lowercase shadow column `name_lc` maintained by the service layer for indexable search

#### Price History
- Price changes recorded as ledger operations (type `price_change`, qty_delta=0) with payload {field, old_cents, new_cents}; product row updated in same transaction via the single write path (extend app/services — catalog service calls ledger)
- Product card shows price history table (when, who, field, old → new) read from operations
- Creating a product records operation type `product_created` (qty_delta=0) for audit; editing non-price fields records `product_edited` with changed fields in payload

### Claude's Discretion
- Exact template structure, pagination (optional if list is long), empty-state texts
- Migration numbering and index choices (index on products.code, products.name_lc)

### Deferred Ideas (OUT OF SCOPE)
- Barcode input — out of scope (v1)
- Excel import of dictionary — out of scope per user decision (manual entry); paste-friendly UI is the concession
- Operations on soft-deleted products semantics beyond rejection (restore flow) — minimal restore link on product card is Claude's discretion
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAT-01 | Create and edit product cards: code, name, category, cost/sale/catalog price (most optional) | Migration 0002 column additions (Finding 2), catalog service pattern extending the ledger single write path (Finding 5), optional-money form parsing (Pattern 4), grep-gate relaxation (Finding 4) |
| CAT-02 | Reference dictionary (code → name) auto-fills name when entering a code | Dictionary table design & PK conflict resolution (Finding 3), HTMX autofill via 204 No Content (Pattern 2, verified against htmx docs) |
| CAT-03 | Instant search by partial code/name | Verified Cyrillic case-folding behavior (Finding 1), `name_lc` shadow column, ranked-CASE query (Pattern 3), HTMX active-search attributes (Pattern 1) |
| CAT-04 | Price changes kept as history | New operation types price_change/product_created/product_edited with qty_delta=0 (Finding 6), price-history read query (Pattern 5), append-only triggers already guarantee immutability |
</phase_requirements>

## Summary

Phase 2 is an extension phase, not a greenfield phase: every building block (single write path, append-only triggers, cents/UUID/UTC helpers, HTMX partial pattern, Alembic frozen-migration style) already exists on disk from Phase 1 and was inspected during this research. No new packages are required — the entire phase is buildable with the pinned dependencies in `pyproject.toml`.

Three findings materially change how the planner should write tasks. **(1)** SQLite's `lower()` SQL function and `LIKE` are ASCII-only — verified empirically on this project's SQLite 3.50.4: `lower('ДЕМО') → 'ДЕМО'` (unchanged). The CONTEXT.md wording "via SQLAlchemy func.lower" is therefore a trap for the name column: `func.lower(Product.name)` emits SQL `lower()` and will NOT fold Cyrillic. The correct implementation of the locked decision is Python-side `str.lower()` at write time into `name_lc`, plus Python-side lowering of the query string; `func.lower()` is acceptable only for the code column (ASCII codes). **(2)** The `Product` model currently has NO category or price columns — migration 0002 must add `category`, `cost_cents`, `sale_cents`, `catalog_cents`, and `name_lc`, all via plain `op.add_column` (no batch mode, no trigger risk). **(3)** The locked decision "dictionary: code (PK, TEXT)" directly conflicts with the existing Phase 1 contract test `test_conventions_uuid_cents_utc`, which asserts every table's PK is a 36-char String UUID. The planner must resolve this explicitly (recommendation: UUID surrogate PK + `UNIQUE(code)` — functionally identical, keeps the test and the D-05 sync convention intact).

**Primary recommendation:** Extend, don't rebuild — add three operation types to `OPERATION_TYPES`, add a `catalog.py` service that stages product-row mutations and lets `record_operation`'s existing commit close the transaction, add migration 0002 with plain column adds + dictionary table + indexes, and implement search on `name_lc` (Python-lowered) with the htmx active-search pattern already vendored in `app/static/htmx.min.js`.

## Project Constraints (from CLAUDE.md)

- Tech stack locked: Python 3.13 / FastAPI 0.139 / SQLAlchemy 2.0 / SQLite / Jinja2 / htmx 2.0.10 vendored — no SPA, no CDN assets, no Tailwind, offline runtime [VERIFIED: E:\dev\myorishop\CLAUDE.md + pyproject.toml]
- No SQLite-specific SQL in queries (portability to PostgreSQL) — use portable ORM constructs; `INSERT OR REPLACE` and `strftime` forbidden
- No FLOAT/REAL for money — integer cents only (enforced by existing test)
- Sync SQLAlchemy `Session` + plain `def` endpoints (no aiosqlite/async)
- SQLAlchemy 2.0 style only (`Mapped[]`, `mapped_column()`, `select()`)
- uv for all commands (`uv run pytest`, `uv run ruff check .`); Windows environment
- GSD workflow enforcement: changes go through `/gsd-execute-phase`
- User global CLAUDE.md: UI text Russian, code/comments/commits English; do not commit unless asked
- Established Phase 1 gates (from 01-03-SUMMARY): no `session.add(`/quantity mutation outside services (see Finding 4 for required gate wording update); no `| safe` in templates; no CDN/http(s) asset URLs; `lang="ru"` + utf-8 in base.html; ruff + pytest green

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Product CRUD + validation | API/Backend (FastAPI routes → `app/services/catalog.py`) | — | Thin routes / fat services pattern locked in Phase 1; typed Form → 422 is first validation line |
| Price-change audit trail | Backend service (`catalog.py` → `ledger.record_operation`) | Database (append-only triggers) | Single write path is FND-01; triggers make history tamper-proof at DB level |
| Case-insensitive search normalization | Backend service (Python `str.lower()` at write time) | Database (index on `name_lc`) | SQLite cannot fold Cyrillic (verified); normalization MUST happen in Python |
| Search ranking & capping | Database query (ORM `case()` ORDER BY + LIMIT 20) | — | Single portable query; no Python-side re-sorting needed |
| Instant-search debounce / autofill triggering | Browser (htmx attributes, declarative) | Backend returns partials/204 | No custom JS allowed; htmx 2.0.10 vendored provides delay/changed/sync |
| Dictionary lookup | Backend endpoint (GET, read-only) | Browser (htmx swap or 204 ignore) | Server decides whether to fill (knows dictionary); client stays dumb |
| Match highlighting (`<mark>`) | Backend (split into pre/match/post segments) | Template (autoescaped rendering) | Building HTML strings + `|safe` is forbidden (XSS gate); segment approach keeps autoescape on |
| Soft-delete gating | Backend service layer (reject ops on deleted products) | — | IN-01 resolution is a locked decision; DB has no such constraint |

## Standard Stack

### Core (unchanged — all already installed and pinned)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.139.* | Routes, typed Form validation | Already pinned in pyproject.toml [VERIFIED: E:\dev\myorishop\pyproject.toml] |
| SQLAlchemy | 2.0.* | ORM, `select()`, `case()`, `func.lower` | Already pinned; 2.0 style established in app/models.py |
| Alembic | 1.18.* | Migration 0002 | Already pinned; frozen-migration style established in 0001 |
| Jinja2 | 3.1.* | Templates, autoescape on | Already pinned |
| htmx | 2.0.10 vendored | Active search, autofill, confirm | `app/static/htmx.min.js` verified to contain hx-trigger/delay/hx-sync/hx-confirm/hx-disabled-elt/hx-include [VERIFIED: grep on vendored file] |
| python-multipart | 0.0.32 | Form parsing | Already pinned |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest / httpx / ruff | 9.1.* / 0.28.* / 0.15.* | Tests + lint gates | Every task commit (`uv run pytest -q`, `uv run ruff check .`) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `name_lc` shadow column | SQLite ICU extension / custom collation via `create_collation` | ICU not bundled on Windows Python; `sqlite3.Connection.create_collation` is per-connection, non-portable to PostgreSQL, and can't back an index usefully. Shadow column is portable and locked anyway |
| LIKE on `name_lc` | FTS5 full-text search | SQLite-specific virtual table — violates the portability constraint; overkill for ≤ a few thousand rows |
| jinja2-fragments (`Jinja2Blocks`) | separate partial files | Phase 1 established one-file-per-partial (`partials/ledger_rows.html`); stay consistent, do not add the dependency this phase |

**Installation:** none — `uv sync` already provides everything. No new packages this phase.

## Package Legitimacy Audit

**No new packages are installed in this phase.** All dependencies were pinned and audited in Phase 1 (`pyproject.toml` + `uv.lock` unchanged by this phase's scope).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Critical Findings (read these before planning)

### Finding 1 — SQLite cannot case-fold Cyrillic anywhere: NOCASE, `lower()`, and `LIKE` are all ASCII-only

Verified two ways:

- Official docs: "the 26 upper case characters of ASCII are folded… Note that only ASCII characters are case folded. SQLite does not attempt to do full UTF case folding due to the size of the tables required." [CITED: sqlite.org/datatype3.html]
- Empirically on this project's own SQLite 3.50.4 via `uv run python` [VERIFIED: local sqlite3 3.50.4]:
  - `SELECT lower('ДЕМО-Товар ABC')` → `ДЕМО-Товар abc` (Cyrillic untouched, ASCII folded)
  - `SELECT 'ДЕМО' LIKE 'демо'` → `0`; `SELECT 'ABC' LIKE 'abc'` → `1`

**Consequence for the locked decision:** CONTEXT.md's phrase "comparison via SQLAlchemy func.lower" must NOT be applied to the name column — `func.lower(Product.name)` emits SQL `lower()`, which does not fold Cyrillic. The correct realization of the locked `name_lc` decision:

1. **Write time (service layer):** `product.name_lc = name.lower()` — Python `str.lower()` folds Cyrillic correctly (`'ДЕМО-Товар'.lower() → 'демо-товар'`, verified).
2. **Query time:** lower the query string in Python (`q_lc = q.strip().lower()`), then plain `Product.name_lc.contains(q_lc, autoescape=True)` — no SQL-side folding at all for names.
3. **Code column:** `func.lower(Product.code)` is acceptable because Oriflame codes are ASCII digits [ASSUMED — see A1]; ASCII folding is exactly what SQL `lower()` does.

**Pitfall inside the pitfall:** the migration-0002 backfill of `name_lc` must NOT be `UPDATE products SET name_lc = lower(name)` — same ASCII-only problem. Backfill in Python inside the migration (stdlib only, frozen-compliant — see Pattern 6).

### Finding 2 — Product model is missing every CAT-01 field except code/name

`app/models.py` Product currently has only: id, code, name, quantity, created_at, updated_at, deleted_at [VERIFIED: E:\dev\myorishop\app\models.py]. Migration 0002 and the model must add:

| Column | Type | Nullable |
|--------|------|----------|
| category | String(100) | yes |
| cost_cents | Integer | yes |
| sale_cents | Integer | yes |
| catalog_cents | Integer | yes |
| name_lc | String(200) | yes in DB (service always fills it) |

All five are plain `op.add_column` — SQLite supports `ALTER TABLE ADD COLUMN` for nullable columns natively; **no batch mode needed, therefore zero risk to the append-only triggers** (the 0001 docstring caveat about batch migrations dropping triggers applies only to move-and-copy recreation of the `operations` table, which this migration never touches) [VERIFIED: alembic/versions/0001_initial_schema.py docstring + migration content].

Note: the existing Phase 1 conventions test enforces `*_cents` columns are `Integer` and forbids Numeric/Float — the three new price columns automatically fall under it [VERIFIED: tests/test_ledger.py::test_conventions_uuid_cents_utc].

### Finding 3 — CONFLICT: dictionary `code TEXT PK` breaks an existing Phase 1 contract test

`test_conventions_uuid_cents_utc` iterates **all** tables in `Base.metadata` and asserts every PK column is `String` with `length == 36` (UUID4) [VERIFIED: tests/test_ledger.py lines 96–99]. A `Dictionary` model with `code: Mapped[str] = mapped_column(String(20), primary_key=True)` makes the existing suite RED.

**Resolution options (planner must pick one explicitly):**

1. **RECOMMENDED — UUID surrogate PK + `UNIQUE(code)`:** `id String(36) PK, code String(20) NOT NULL UNIQUE, name String(200) NOT NULL`. Functionally identical for lookup (`WHERE code = :code` hits the unique index), preserves the D-05 sync-readiness convention (v2 multi-device sync will want UUID rows here too), and keeps the Phase 1 test contract untouched. Deviation from the CONTEXT letter ("code (PK, TEXT)") but not its intent (code-keyed reference).
2. Amend the Phase 1 test to exempt `dictionary` — touches a frozen contract test, weakens the convention gate, and creates a sync-migration problem later. Not recommended.

### Finding 4 — The Phase 1 grep gate must be re-worded, or catalog writes are impossible

Phase 1 gate: "no `session.add(`/quantity mutation outside services/ledger.py" [VERIFIED: 01-03-SUMMARY.md]. The catalog service must `session.add(Product)` and mutate product fields (name, code, category, prices, deleted_at). New gate wording for Phase 2 plans:

- `session.add(` and any write to `Product.*` fields: allowed only inside `app/services/*.py` (routes stay write-free)
- `Operation` inserts and `products.quantity` mutation: still ONLY in `app/services/ledger.py` (`record_operation`)
- Direct `quantity` assignment anywhere else remains forbidden (locked: no direct stock editing)

### Finding 5 — How to extend the single write path without breaking anything

`record_operation` (a) validates type against `OPERATION_TYPES`, (b) `session.get(Product, ...)` with autoflush, (c) stages the Operation row, (d) does SQL-side `quantity = quantity + delta`, (e) `session.commit()` [VERIFIED: app/services/ledger.py].

Consequences verified against the code:

- **New types are a one-line change:** extend the tuple in `app/models.py` to `("receipt", "sale", "writeoff", "return", "correction", "price_change", "product_created", "product_edited")`. There is NO CHECK constraint on `operations.type` in migration 0001 — no migration needed for new types [VERIFIED: alembic/versions/0001_initial_schema.py — no CheckConstraint on type].
- **`qty_delta=0` is harmless:** `product.quantity = Product.quantity + 0` still emits an UPDATE on products (SQL-expression assignment always dirties), which bumps `updated_at` via `onupdate` — desirable for edits; `compute_stock`/`rebuild_stock` are unaffected (SUM of 0-deltas).
- **Transaction pattern (this is how "same transaction" is achieved without touching the ledger contract):** the catalog service mutates/creates the Product on the session WITHOUT committing, then calls `record_operation(...)` — its internal `session.commit()` commits the product-row changes and the audit op atomically. For `product_created`: `session.add(product)` first; `record_operation`'s `session.get` triggers autoflush, which INSERTs the pending product before the SELECT, so the FK and the unknown-product guard both pass.
- **Multiple changed price fields in one save = multiple `record_operation` calls** (locked payload shape is singular: `{field, old_cents, new_cents}`). Each call commits separately — acceptable for a single-user local app; capture old values BEFORE mutating the product. Do NOT refactor `record_operation` to defer commits — that changes the Phase 1 contract for zero MVP benefit.
- **Soft-delete rejection (IN-01, locked):** add a guard in `record_operation` after the unknown-product check: `if product.deleted_at is not None: raise ValueError(f"product is deleted: {product_id!r}")`. Existing tests use only active products — suite stays green [VERIFIED: tests/test_ledger.py uses the active `product` fixture throughout]. Soft-delete/restore themselves are product-row writes in the catalog service (no ledger op required by CONTEXT), so the guard does not deadlock the restore flow.
- **Existing tests unaffected** by the type-tuple extension: every test passes `type_="correction"` explicitly.

### Finding 6 — Price history reads come straight off the ledger

`SELECT` operations `WHERE product_id = :id AND type IN ('price_change')` (optionally + `product_created` for the initial values) `ORDER BY created_at DESC, seq DESC` — same ordering idiom as `ledger_view` [VERIFIED: app/services/ledger.py::ledger_view]. Append-only triggers already make CAT-04 tamper-proof at the DB level; no new mechanism needed. The `payload` JSON column round-trips dicts (write-once — no mutation-tracking concern).

## Architecture Patterns

### System Architecture Diagram

```
Browser (htmx 2.0.10, vendored, no custom JS)
  │
  │ GET /products ──────────────────────────────► products.py ──► catalog.list/search ──► SELECT (name_lc/code, ranked CASE, LIMIT 20)
  │ GET /products/search?q= (input changed 300ms,
  │   hx-sync this:replace) ─────────────────────► products.py ──► catalog.search ──► partial: products table tbody
  │ GET /products/lookup?code=&name= (autofill,
  │   hx-include current name) ──────────────────► products.py ──► dictionary.lookup ──► 204 (name filled/unknown code)
  │                                                                                  └─► partial: name input pre-filled + hint
  │ POST /products  /products/{id} (typed Form) ─► products.py ──► catalog.create/update
  │                                                   │  stage Product mutations (NO commit)
  │                                                   ▼
  │                                             ledger.record_operation(product_created |
  │                                                product_edited | price_change, qty_delta=0)
  │                                                   │  one transaction: product row + op row
  │                                                   ▼
  │                                             SQLite (WAL, FK ON, append-only triggers on operations)
  │
  │ GET/POST /dictionary ───────────────────────► dictionary.py ──► dictionary service (plain CRUD, NOT via ledger)
  └ GET /products/{id}/edit ────────────────────► products.py ──► catalog.get + price_history(ops WHERE type='price_change')
```

### Recommended Project Structure (additions only)

```
app/
├── services/
│   ├── ledger.py          # extend: deleted-product guard; OPERATION_TYPES grows in models.py
│   ├── catalog.py         # NEW: create/update/soft-delete/restore/search/price_history (fat service)
│   └── dictionary.py      # NEW: dictionary CRUD + lookup (plain writes, no ledger)
├── routes/
│   ├── products.py        # NEW: pages + search partial + lookup endpoint (thin)
│   └── dictionary.py      # NEW: /dictionary page + row add/edit (thin)
├── templates/
│   ├── base.html          # ADD: nav «Главная / Товары / Справочник» (base.html has no nav today)
│   ├── pages/products_list.html, product_form.html, dictionary.html
│   └── partials/product_rows.html, name_input.html, dictionary_rows.html, price_history.html
alembic/versions/
└── 0002_catalog_dictionary.py   # NEW (revision "0002", down_revision "0001")
tests/
├── test_catalog.py        # NEW: CRUD, unique-code, soft-delete rejection, name_lc maintenance
├── test_search.py         # NEW: Cyrillic case-insensitivity, ranking, cap 20, LIKE-escape
└── test_dictionary.py     # NEW: CRUD + lookup + autofill 204 behavior
```

### Pattern 1: HTMX active search (verified attribute set)

```html
<!-- Source: htmx.org/docs/ (delay/changed) + htmx.org/attributes/hx-sync/ ("replace" strategy, active-search example) -->
<input type="search" name="q" placeholder="Код или название товара…" autofocus
       hx-get="/products/search"
       hx-trigger="input changed delay:300ms, keyup[key=='Enter']"
       hx-target="#product-rows"
       hx-swap="outerHTML"
       hx-sync="this:replace">
```

`hx-sync="this:replace"` aborts the in-flight request when a newer keystroke fires — prevents stale results overwriting fresh ones [CITED: htmx.org/attributes/hx-sync/]. All attributes confirmed present in the vendored `app/static/htmx.min.js` [VERIFIED: grep on vendored file]. Endpoint returns only the `partials/product_rows.html` fragment (Phase 1 pattern: "HTMX endpoints return partials only").

### Pattern 2: Dictionary autofill — fill name only if empty, via 204 No Content

htmx ignores the response body and performs no swap on `204 No Content` [CITED: htmx.org/docs/ — "you can return a 204 - No Content response code, and htmx will ignore the content of the response"]. This is the clean way to implement "fill only when name is empty" without client-side JS:

```html
<input id="code" name="code" required autofocus
       hx-get="/products/lookup"
       hx-trigger="input changed delay:300ms"
       hx-include="[name='name']"        <!-- send current name value along -->
       hx-target="#name-wrap"
       hx-swap="outerHTML"
       hx-sync="this:replace">
```

```python
# Route: thin decision, no writes
@router.get("/products/lookup")
def lookup(request: Request, code: str = "", name: str = "", session: Session = Depends(get_session)):
    entry = dictionary.lookup(session, code)      # SELECT by code
    if entry is None or name.strip():
        return Response(status_code=204)          # nothing to fill -> htmx does nothing
    return templates.TemplateResponse(
        request, "partials/name_input.html",
        {"name": entry.name, "autofilled": True},  # partial renders input + RU hint
    )
```

The swapped partial re-renders the name input (value autoescaped) plus the muted hint «Название подставлено из справочника — можно изменить.» Focus is unaffected — the user is typing in the code field, not the swapped one.

### Pattern 3: Ranked, capped, Cyrillic-safe, LIKE-escaped search query

```python
# Source: verified against SQLAlchemy 2.0 idioms already used in app/services/ledger.py
from sqlalchemy import case, select

def search_products(session: Session, q: str) -> list[Product]:
    base = select(Product).where(Product.deleted_at.is_(None))
    q_lc = q.strip().lower()                      # Python folds Cyrillic; SQL lower() cannot
    if not q_lc:
        return list(session.scalars(base.order_by(Product.name).limit(20)))
    rank = case(
        (func.lower(Product.code) == q_lc, 0),                              # exact code
        (func.lower(Product.code).like(_escaped(q_lc) + "%", escape="\\"), 1),  # code prefix
        else_=2,                                                             # name substring
    )
    stmt = (
        base.where(
            func.lower(Product.code).like(_escaped(q_lc) + "%", escape="\\")
            | Product.name_lc.contains(q_lc, autoescape=True)   # emits LIKE with escaping
        )
        .order_by(rank, Product.name_lc)
        .limit(20)                                              # locked cap
    )
    return list(session.scalars(stmt))
```

`ColumnOperators.contains(..., autoescape=True)` escapes `%`, `_`, and the escape char in user input — never interpolate raw input into a LIKE pattern (a `%`-only query would otherwise match everything) [CITED: docs.sqlalchemy.org/en/20/core/operators.html — contains/startswith autoescape]. For the manual prefix `like()`, escape `%`/`_`/`\` in a tiny `_escaped()` helper. Portable ORM only — no SQLite-specific SQL.

### Pattern 4: Optional-money form fields (empty string → NULL)

FastAPI/Pydantic v2 rejects `""` for `int | None = Form(None)` fields — take prices as **strings** and parse in the service with the existing `to_cents` [VERIFIED: app/core.py — raises ValueError on any invalid input, accepts comma and dot]:

```python
# Route signature (thin): cost: str = Form(""), sale: str = Form(""), catalog: str = Form("")
# Service:
def parse_optional_cents(raw: str, field_label: str, errors: dict) -> int | None:
    raw = raw.strip()
    if not raw:
        return None                                # empty -> NULL column
    try:
        return to_cents(raw)                       # '12,50' / '12.50' / '7' -> cents
    except ValueError:
        errors[field_label] = "Неверный формат цены — введите число, например 12,50."
        return None
```

On errors, re-render the form template with the errors dict (inline destructive-color messages per UI-SPEC) and HTTP 422/400; never a raw 500.

### Pattern 5: `<mark>` highlight WITHOUT `|safe` (XSS gate)

The `no |safe` grep gate is live [VERIFIED: 01-03-SUMMARY.md]. Do not build HTML strings in Python. Split server-side, render autoescaped segments:

```python
def split_match(text: str, q_lc: str) -> tuple[str, str, str]:
    """Return (pre, match, post); match == '' when q not found."""
    idx = text.lower().find(q_lc) if q_lc else -1
    if idx < 0:
        return text, "", ""
    return text[:idx], text[idx : idx + len(q_lc)], text[idx + len(q_lc) :]
```

```jinja
{# each segment is autoescaped; <mark> is literal template HTML #}
{{ pre }}{% if match %}<mark>{{ match }}</mark>{% endif %}{{ post }}
```

### Pattern 6: Migration 0002 — frozen style, plain ADD COLUMN, Python backfill

```python
# alembic/versions/0002_catalog_dictionary.py — NO app imports (WR-06), stdlib + sqlalchemy + alembic only
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"

def upgrade() -> None:
    # 1) products: plain ADD COLUMN (nullable) — native SQLite ALTER, no batch, triggers untouched
    op.add_column("products", sa.Column("category", sa.String(100), nullable=True))
    op.add_column("products", sa.Column("cost_cents", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("sale_cents", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("catalog_cents", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("name_lc", sa.String(200), nullable=True))

    # 2) backfill name_lc in PYTHON — SQL lower() cannot fold Cyrillic (frozen, stdlib str.lower)
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, name FROM products")).fetchall()
    for row_id, name in rows:
        bind.execute(
            sa.text("UPDATE products SET name_lc = :lc WHERE id = :id"),
            {"lc": (name or "").lower(), "id": row_id},
        )

    # 3) dictionary table (UUID PK + unique code — see Finding 3)
    op.create_table(
        "dictionary",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dictionary")),
        sa.UniqueConstraint("code", name=op.f("uq_dictionary_code")),
    )

    # 4) search indexes (locked discretion: code + name_lc)
    op.create_index(op.f("ix_products_code"), "products", ["code"])
    op.create_index(op.f("ix_products_name_lc"), "products", ["name_lc"])
```

Downgrade: drop indexes, drop dictionary, `op.drop_column` × 5 (SQLite ≥ 3.35 supports native DROP COLUMN; this machine runs 3.50.4 [VERIFIED: local]).

**Unique code among non-deleted:** enforce in the service layer (SELECT for an active product with the same code before insert/update → RU error «Код уже используется другим товаром…»). A partial unique index (`sqlite_where=sa.text("deleted_at IS NULL")`) is a possible DB backstop, but it is dialect-flagged SQL and single-user MVP gains little — service-layer check is the recommendation; add the partial index only if the planner wants defense in depth.

### Anti-Patterns to Avoid

- **`func.lower(Product.name)` for search** — ASCII-only in SQLite; silently breaks Cyrillic (Finding 1)
- **`ilike()` on name** — SQLAlchemy renders it as `lower(x) LIKE lower(y)` on SQLite → same ASCII trap
- **`UPDATE products SET name_lc = lower(name)` in the migration** — same trap at backfill time
- **`|safe` for match highlighting** — violates the XSS grep gate; use segment splitting (Pattern 5)
- **Raw query string in LIKE patterns** — `%`/`_` injection; use `autoescape=True` / `escape="\\"`
- **Batch-mode migration on `operations`** — drops the append-only triggers (0001 docstring caveat); this phase never needs to touch `operations`
- **Committing in the catalog service before `record_operation`** — splits the product-row change and its audit op into separate transactions; stage, then let `record_operation` commit
- **`int | None = Form(None)` for money inputs** — `""` fails Pydantic v2 int parsing with an opaque 422; accept `str` and parse via `to_cents`
- **Forgetting `name_lc` on edit** — stale search results; make `name_lc = name.lower()` unconditional in create AND update paths, and test it

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Money parsing (comma/dot, rounding) | New parser | `app/core.py::to_cents` (ROUND_HALF_UP, rejects inf/nan) | Already battle-tested in Phase 1; WR-02/WR-03 contract |
| Money display | f-strings | `cents` Jinja filter (`format_cents`) | Registered in app/routes/__init__.py |
| Timestamps / IDs | ad-hoc datetime/uuid | `utcnow_iso` / `new_id` | D-05/D-07 conventions, tested |
| Audit rows / quantity writes | direct Operation inserts | `ledger.record_operation` | The single write path; triggers + tests enforce it |
| Debounce/race handling for search | custom JS timers | htmx `delay:300ms` + `hx-sync="this:replace"` | Declarative, vendored, verified in htmx docs |
| "Fill only if empty" autofill logic | client-side JS | server decision + 204 No Content | htmx ignores 204 (verified); zero JS |
| LIKE escaping | manual replace chains | `.contains(q, autoescape=True)` | SQLAlchemy built-in, handles `%`, `_`, escape char |
| Local time display | new formatting | `local_dt` Jinja filter | Already handles Europe/Moscow via tzdata |

**Key insight:** Phase 1 deliberately built every primitive this phase needs; the entire phase is composition, and any hand-rolled duplicate (second money parser, second write path) is a regression against tested contracts.

## Common Pitfalls

### Pitfall 1: Cyrillic search silently case-sensitive
**What goes wrong:** Search for «демо» misses «Демо-товар»; tests pass if written with ASCII fixtures only.
**Why it happens:** SQLite NOCASE/`lower()`/`LIKE` fold ASCII only (verified, Finding 1).
**How to avoid:** `name_lc` maintained by Python `str.lower()` at every write; Python-lowered query; Python backfill in migration.
**Warning signs:** any `func.lower(...name...)`, `ilike` on name, or SQL-side backfill in a diff. Test MUST use a Cyrillic fixture (e.g., create «Губная Помада», search «губная»).

### Pitfall 2: New dictionary PK breaks the Phase 1 conventions test
**What goes wrong:** `test_conventions_uuid_cents_utc` fails on `dictionary.code` PK (not String(36)).
**Why it happens:** the test iterates ALL metadata tables (Finding 3).
**How to avoid:** UUID surrogate PK + `UNIQUE(code)`; run the full existing suite in the same task that adds the model.
**Warning signs:** red `test_ledger.py` after adding a model that "shouldn't affect the ledger".

### Pitfall 3: Grep gate contradiction blocks catalog writes
**What goes wrong:** Plan verification rejects `session.add(Product)` in catalog.py, or worse, someone routes product creation through `record_operation` hacks.
**How to avoid:** update the gate wording per Finding 4 in the plan's verification steps: product-field writes in `app/services/*`; Operation/quantity writes only in `ledger.py`; routes write-free.

### Pitfall 4: Deleted-product guard placed only in catalog.py
**What goes wrong:** IN-01 resurfaces — Phase 3/4 receipt/sale code paths can still operate on soft-deleted products.
**How to avoid:** put the `deleted_at` guard inside `record_operation` itself (locked: "REJECTED in the service layer"); one guard covers all future op types. Add a regression test (soft-delete product → `record_operation` raises ValueError).

### Pitfall 5: Autofill overwrites what the operator typed
**What goes wrong:** operator types a name first, then edits the code — swap replaces their name.
**How to avoid:** `hx-include="[name='name']"` sends the current value; server returns 204 whenever name is non-empty (Pattern 2). Test both branches via TestClient (200-with-fragment vs 204).

### Pitfall 6: Empty search box shows nothing (or everything)
**What goes wrong:** `LIKE '%%'` matches all rows uncapped, or empty q returns an empty table on page load.
**How to avoid:** explicit branch — empty query returns first 20 active products ordered by name; always `LIMIT 20` (locked cap). Empty-result partial renders «Ничего не найдено по запросу „{q}“…» per UI-SPEC.

### Pitfall 7: Price-history op recorded with stale "old" value
**What goes wrong:** service mutates `product.sale_cents` first, then reads it as `old_cents` → history shows old == new.
**How to avoid:** snapshot `{field: getattr(product, field)}` for all three price fields BEFORE applying form values; compare, mutate, then emit one `price_change` per actually-changed field.

### Pitfall 8: `updated_at` string type surprises
**What goes wrong:** assuming datetime semantics on `created_at`/`updated_at` — they are ISO-8601 TEXT columns (D-07).
**How to avoid:** keep using `utcnow_iso()`; sort with `created_at DESC, seq DESC` like `ledger_view` does; render via `local_dt` filter.

## Code Examples

See Patterns 1–6 above (kept inline with their findings). All SQLAlchemy snippets follow the exact 2.0 idioms already present in `app/services/ledger.py` [VERIFIED: on-disk]. Additional micro-examples:

### Category datalist (CAT-01 optional free text with suggestions)

```python
# service
def category_options(session: Session) -> list[str]:
    return list(session.scalars(
        select(Product.category).where(
            Product.deleted_at.is_(None), Product.category.is_not(None), Product.category != ""
        ).distinct().order_by(Product.category)
    ))
```

```jinja
<input list="cat-options" name="category" value="{{ product.category or '' }}">
<datalist id="cat-options">{% for c in categories %}<option value="{{ c }}">{% endfor %}</datalist>
```

### Soft delete with hx-confirm (UI-SPEC copy)

```html
<button class="danger"
        hx-post="/products/{{ product.id }}/delete"
        hx-confirm="Удалить товар „{{ product.name }}“? Он будет скрыт из каталога и поиска, история операций сохранится.">
  Удалить товар
</button>
```

(`hx-confirm` present in vendored htmx [VERIFIED: grep].) Delete = `product.deleted_at = utcnow_iso()` in catalog service; restore = set to None. POST, not DELETE — form/htmx simplicity, consistent with Phase 1.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `hx-trigger="keyup changed delay:500ms"` (htmx 1.x examples) | `input changed delay:300ms` + `hx-sync="this:replace"` | htmx 2.x docs; `input` catches paste/IME, sync kills races | Use the CONTEXT-locked 300ms with `input` event |
| SQLite without DROP COLUMN (pre-3.35 batch dance) | Native `ALTER TABLE ... DROP COLUMN` | SQLite 3.35 (2021); local runtime is 3.50.4 [VERIFIED] | Downgrade path in 0002 can use plain drop_column |
| `declarative_base()` 1.x style | `DeclarativeBase` + `Mapped[]` | SQLAlchemy 2.0 | Already the codebase style; keep it |

**Deprecated/outdated:** htmx 4.0 is still beta — stay on vendored 2.0.10 (STACK.md lock). No library changes this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Oriflame product codes are ASCII (digits/latin), so `func.lower(code)` suffices for code matching | Finding 1, Pattern 3 | If codes can contain Cyrillic letters, code search becomes case-sensitive for those codes. Cheap hedge: also match the code against `q_lc` via a Python-lowered comparison, or store codes normalized (trimmed) at write time; name search is unaffected either way |
| A2 | Catalog stays small (≤ low thousands of rows), so LIKE scans within LIMIT 20 are instant even where indexes can't serve `LIKE '%…%'` substring patterns | Pattern 3, index choices | Only a perf concern; FTS5 or prefix-range queries exist as later escape hatches (post-PG migration, use PG trigram/ILIKE) |
| A3 | No ledger op is required for soft-delete/restore themselves (CONTEXT lists ops only for create/edit/price) | Finding 5 | If auditors want delete events later, add a `product_deleted` type in a follow-up — append-only design makes this additive |

## Open Questions

1. **Dictionary seed data source (carried from STATE.md blocker)**
   - What we know: no verified source for the Oriflame code→name dictionary; Excel import explicitly out of scope; UI must be paste-friendly manual entry.
   - What's unclear: whether the user will want a one-off bulk paste (many rows at once) vs strictly row-by-row.
   - Recommendation: build row-by-row add (locked) with a plain-text-friendly form; if the planner wants a cheap concession, a single textarea "add many lines `code name`" endpoint is ~20 lines — flag as optional, not required by CAT-02.
2. **Dictionary PK shape** — conflict documented in Finding 3; planner must record the resolution (recommended: UUID PK + UNIQUE(code)) as an explicit plan decision since it deviates from the CONTEXT letter.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | all commands | ✓ | 0.11.11 [VERIFIED] | — |
| Python | runtime | ✓ | 3.13.13 [VERIFIED] | — |
| SQLite (bundled) | DB, native ADD/DROP COLUMN | ✓ | 3.50.4 [VERIFIED] | — |
| htmx vendored | UI interactivity | ✓ | 2.0.10 at app/static/htmx.min.js; hx-trigger/hx-sync/hx-confirm/hx-include/hx-disabled-elt all present [VERIFIED: grep] | — |
| alembic/pytest/ruff via uv | migration + gates | ✓ | pinned in pyproject.toml/uv.lock | — |

**Missing dependencies with no fallback:** none. **Missing with fallback:** none. Fully offline-capable.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (with httpx 0.28.* for TestClient) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=.) |
| Quick run command | `uv run pytest -q tests/test_catalog.py -x` (per-area) |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CAT-01 | create/edit product incl. optional prices, unique active code, soft-delete + rejection guard | unit + integration | `uv run pytest -q tests/test_catalog.py -x` | ❌ Wave 0 |
| CAT-02 | dictionary CRUD; lookup returns fill fragment / 204 when name non-empty or code unknown | integration (TestClient) | `uv run pytest -q tests/test_dictionary.py -x` | ❌ Wave 0 |
| CAT-03 | Cyrillic case-insensitive match, ranking order (exact>prefix>substring), LIMIT 20, LIKE-wildcard escape | unit + integration | `uv run pytest -q tests/test_search.py -x` | ❌ Wave 0 |
| CAT-04 | price change writes price_change op with correct old/new; history endpoint renders it; ledger triggers still block UPDATE/DELETE | unit + integration | `uv run pytest -q tests/test_catalog.py -x` (history cases) | ❌ Wave 0 |
| regression | existing Phase 1 contract stays green after OPERATION_TYPES extension + deleted-guard + new model | full suite | `uv run pytest -q` | ✅ tests/test_ledger.py etc. |

### Sampling Rate
- **Per task commit:** `uv run pytest -q` + `uv run ruff check .` (suite is small/fast; full run per commit is cheap)
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** full suite green + `alembic upgrade head` on a fresh temp DB before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_catalog.py` — covers CAT-01, CAT-04 (incl. deleted-product `record_operation` rejection regression)
- [ ] `tests/test_search.py` — covers CAT-03 (MUST include a Cyrillic fixture, a `%`-in-query escape case, and a 21-product cap case)
- [ ] `tests/test_dictionary.py` — covers CAT-02 (200-fragment vs 204 branches)
- [ ] Existing `tests/conftest.py` fixtures reusable as-is (file-based tmp engine + triggers + client override) — no framework install needed

## Security Domain

### Applicable ASVS Categories (L1, single local user, loopback-only)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (v1 single local operator, loopback bind hard-coded in run.bat) | deferred to AUTH-V2-01 |
| V3 Session Management | no | — |
| V4 Access Control | no (no roles in v1) | — |
| V5 Input Validation | yes | typed FastAPI Form params (garbage → 422); `to_cents` for money; service-layer RU validation messages; LIKE autoescape for search input |
| V6 Cryptography | no | — |

### Known Threat Patterns for FastAPI + SQLite + Jinja2/HTMX

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via search/code/name | Tampering | ORM parameterized queries only (already the codebase rule); no raw SQL with user input |
| LIKE wildcard injection (`%`, `_` in q) | Tampering/DoS-lite | `.contains(q, autoescape=True)` / `like(..., escape="\\")` (Pattern 3) |
| Stored XSS via product name/category rendered in results and `<mark>` highlight | Tampering | Jinja2 autoescape stays on; `no |safe` grep gate; segment-split highlight (Pattern 5) |
| Ledger tampering (price history rewrite) | Repudiation/Tampering | DB-level append-only triggers (existing, verified by tests); qty_delta=0 ops inherit protection |
| CSRF on state-changing POSTs | Tampering | Accepted residual risk for v1: no auth, loopback-only bind (`127.0.0.1` hard-coded); revisit with AUTH-V2-01. Destructive action gated by `hx-confirm` |
| Direct stock manipulation via new endpoints | Tampering | quantity writes remain locked to `record_operation`; no form field ever maps to quantity |

## Sources

### Primary (HIGH confidence)
- On-disk codebase inspection: `app/models.py`, `app/services/ledger.py`, `app/db.py`, `app/core.py`, `app/config.py`, `app/routes/*`, `alembic/env.py`, `alembic/versions/0001_initial_schema.py`, `tests/*`, `pyproject.toml`, templates — all read this session
- Empirical verification on project runtime [VERIFIED]: Python 3.13.13, SQLite 3.50.4 — `lower()`/LIKE ASCII-only behavior for Cyrillic; uv 0.11.11
- sqlite.org/datatype3.html — NOCASE folds only the 26 ASCII letters; no full UTF case folding [CITED]
- htmx.org/docs/ — 204 No Content is ignored (no swap); `delay`/`changed` trigger modifiers [CITED]
- htmx.org/attributes/hx-sync/ — `replace` strategy + active-search example [CITED]
- Vendored `app/static/htmx.min.js` — grep-confirmed presence of hx-trigger/hx-sync/hx-confirm/hx-include/hx-disabled-elt [VERIFIED]

### Secondary (MEDIUM confidence)
- docs.sqlalchemy.org/en/20/core/operators.html — `contains`/`startswith` `autoescape=True` semantics [CITED, matches pinned SQLAlchemy 2.0 line]
- SQLite 3.35 native DROP COLUMN (release notes knowledge, corroborated by local 3.50.4 runtime)

### Tertiary (LOW confidence)
- A1 (Oriflame codes are ASCII digits) — training knowledge, [ASSUMED], hedged in Pattern 3

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages; everything pinned and on disk
- Architecture: HIGH — pure extension of inspected Phase 1 code; transaction/autoflush behavior reasoned from the actual `record_operation` implementation
- Pitfalls: HIGH for Cyrillic/test-conflict/gate findings (empirically or file-verified); MEDIUM for the multi-price-field commit-granularity judgment (design tradeoff, not a fact)

**Research date:** 2026-07-08
**Valid until:** 2026-08-07 (stable stack, pinned versions, offline app)
