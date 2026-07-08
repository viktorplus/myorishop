# Phase 1: Foundation & Ledger Core - Research

**Researched:** 2026-07-08
**Domain:** FastAPI + SQLAlchemy 2.0 + SQLite (local-first, append-only ledger foundation) on Windows
**Confidence:** HIGH (stack versions verified against PyPI today; core patterns cited from official SQLAlchemy/Alembic/SQLite docs this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Runtime & Startup**
- Python 3.13 managed with uv; dependencies in pyproject.toml
- run.bat starts uvicorn with a single worker on 127.0.0.1:8000 and opens the default browser
- htmx 2.0.10 vendored locally in app/static/ (offline requirement — no CDN)
- No PyInstaller/Docker in v1; plain `uv run` via run.bat

**Data Model Conventions**
- UUID (uuid4, stdlib) TEXT primary keys on ALL tables — sync-safe, no autoincrement collisions
- Money stored as integer minor units (cents); column names end in `_cents`
- Timestamps stored as UTC ISO-8601 TEXT (`created_at`, `updated_at`); single configurable local timezone for display
- `operations` table is append-only: id, type, product_id, qty_delta, unit_cost_cents, unit_price_cents, payload (JSON for type-specific fields), device_id, seq (per-device counter), created_at (UTC), created_by, synced_at (nullable — future sync cursor)
- Stock quantity is a cached projection on product, always recomputable from the ledger; no direct quantity edits
- Soft deletes (`deleted_at`) on products/customers; no hard deletes

**App Skeleton**
- Thin routes / fat services layering: app/routes/, app/services/, app/models.py, app/templates/, app/static/
- Sync SQLAlchemy 2.0 Session with plain `def` endpoints (no async/aiosqlite)
- Alembic from day one with `render_as_batch=True`
- SQLite PRAGMAs set per-connection via SQLAlchemy event listener: WAL, foreign_keys=ON, busy_timeout
- Jinja2 server-rendered pages; HTMX for partial updates; python-multipart for forms
- pytest for tests; Ruff for lint

**Operator Identity**
- Single operator name from a local settings/config value; recorded as `created_by` on every operation
- No login/auth in v1 (single user); roles deferred to v2 per REQUIREMENTS.md

### Claude's Discretion
- Exact directory naming, template structure, base layout HTML, and Alembic env details
- UUIDv4 vs UUIDv7 (v4 acceptable; stdlib-trivial)

### Deferred Ideas (OUT OF SCOPE)
- Sync engine, CRDTs, server replay — v2 (schema only stays sync-ready)
- Multi-operator device_id negotiation — v2 (v1 uses one fixed device_id)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FND-01 | All stock changes recorded in an append-only operations ledger; stock quantity derived from it | Pattern 1 (ledger + projection), Pattern 2 (append-only DB triggers), `rebuild_stock()` recompute function, Code Examples 3–5 |
| FND-02 | Money as integer minor units; timestamps in UTC; UUID identifiers | Data conventions section: `Integer` `_cents` columns, ISO-8601 UTC TEXT timestamps via helper, `str(uuid4())` TEXT PKs — Code Example 4 |
| FND-03 | Every operation records who performed it and when (audit trail) | `created_by` (from settings) + `created_at` (UTC) NOT NULL on every operations row; skeleton page shows who/when — Code Example 5 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Project `./CLAUDE.md` is GSD-managed; actionable directives for the planner:

- **Stack is locked:** Python, FastAPI, SQLAlchemy, SQLite, HTMX server-rendered UI (no SPA, no Docker, no async DB)
- **Deployment:** local, browser at localhost, fully offline in v1
- **1 operator in v1** — no auth machinery
- **GSD workflow enforcement:** file changes go through GSD commands (`/gsd-execute-phase` for this phase's work)
- From user's global instructions: UI text in Russian, code/comments/commits in English; never hardcode secrets; do not commit unless asked (GSD `commit_docs: true` governs planning docs)

## Summary

This phase is a walking skeleton on a carefully-shaped data foundation. The milestone-level research (STACK.md, ARCHITECTURE.md, PITFALLS.md — all verified 2026-07-08) already settled the stack and ledger architecture; this phase research adds the execution-level specifics: the exact per-connection PRAGMA listener pattern (verified against SQLAlchemy 2.0 official docs, including the autocommit gotcha), Alembic `render_as_batch` + naming-convention setup (verified against Alembic official docs), DB-level append-only enforcement via `RAISE(ABORT)` triggers (verified against SQLite official docs), and the Windows/uv environment reality on this machine.

Two things the planner must reconcile: (1) ARCHITECTURE.md's Operation schema sketch uses `Numeric(10, 2)` money columns and explicit `customer_id`/`note` columns — **CONTEXT.md overrides both**: integer `_cents` columns and a JSON `payload` for type-specific fields. (2) Python 3.13 is **not installed** on this machine (uv has 3.12.13 managed; system has 3.11/3.14); the plan needs a one-time-online `uv python install 3.13` step or an explicit fallback to 3.12.

**Primary recommendation:** Build exactly the CONTEXT.md skeleton — uv project, `app/` package with db.py (engine + PRAGMA listener), models.py (Product + Operation with sync-ready conventions), one `record_operation()` service, Alembic initial migration that also creates append-only triggers, one page + one HTMX partial exercising a real ledger write, run.bat — and prove FND-01/02/03 with pytest before adding anything else.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ledger writes (operation insert + stock projection) | Backend service layer (`app/services/ledger.py`) | Database (triggers, UNIQUE constraint) | Single write path is the phase's whole point; DB triggers are the last-resort guard |
| Append-only enforcement | Database (SQLite triggers) | Service layer (no update/delete code paths) | App discipline can be bypassed by future bugs; `RAISE(ABORT)` cannot |
| Stock recomputation / verification | Backend service layer | — | Pure SQL aggregate over ledger; exposed as function + test |
| Schema conventions (UUID/cents/UTC) | Database schema + models.py | Helper module (`app/core.py` utils) | Column types locked in migration #1; helpers keep usage consistent |
| Page rendering + HTMX partial | Frontend server (Jinja2 templates) | Routes layer | Server-rendered app; no client-side state |
| Static assets (htmx.min.js, css) | FastAPI StaticFiles mount | — | Offline requirement — vendored, no CDN |
| Startup / deployment | run.bat (Windows shell) | uvicorn single worker | v1 deployment story per locked decision |
| Operator identity (`created_by`) | Config (pydantic-settings `.env`) | Service layer stamps it on rows | Single operator name from settings, no auth |

## Standard Stack

All versions below were verified against PyPI registry metadata on 2026-07-08 in `.planning/research/STACK.md` [VERIFIED: PyPI JSON API, 2026-07-08]. Re-verified for legitimacy this session via `gsd-tools query package-legitimacy` (see audit below).

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.x (fallback 3.12.13 — already uv-managed on this machine) | Runtime | Locked decision; all libs support it |
| fastapi | 0.139.0 | Web framework | Locked stack; Pydantic v2 forms/validation |
| uvicorn[standard] | 0.51.0 | ASGI server | Standard FastAPI server; works on Windows; single worker |
| sqlalchemy | 2.0.51 | ORM (2.0 declarative style: `DeclarativeBase`, `Mapped[]`, `mapped_column()`) | Locked stack; portable to PostgreSQL later |
| alembic | 1.18.5 | Migrations from day one | Locked decision; `render_as_batch=True` required for SQLite |
| jinja2 | 3.1.6 | Templating | Standard for server-rendered FastAPI |
| htmx | 2.0.10 (vendored static file) | Partial updates | Locked decision; do NOT use 4.0 beta |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | 0.0.32 | Form parsing | Required by any `Form(...)` endpoint — needed in this phase for the skeleton form |
| pydantic-settings | 2.14.2 | Settings from `.env` (DB path, operator name, device_id, timezone) | This phase — operator identity is a locked decision |
| pytest | 9.1.1 | Test runner (dev) | This phase — FND verification tests |
| httpx | 0.28.1 | Required by FastAPI TestClient (dev) | This phase — smoke test of routes |
| ruff | 0.15.20 | Lint + format (dev) | Locked decision |
| Pico.css classless | 2.x, vendored | Zero-build styling | Optional; drop into static/ alongside htmx |

**Skip in this phase:** jinja2-fragments (add later when partials multiply — one partial doesn't justify it).

### Alternatives Considered
Settled at milestone level (STACK.md): no SQLModel, no async/aiosqlite, no Docker/PyInstaller, no CDN. Do not revisit.

**Installation:**
```bash
uv init myorishop --python 3.13        # or: adapt existing repo; see Open Questions Q1
uv add "fastapi==0.139.*" "uvicorn[standard]" sqlalchemy alembic jinja2 python-multipart pydantic-settings
uv add --dev pytest httpx ruff
# htmx: one-time download (needs internet once), commit to repo:
#   https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js -> app/static/htmx.min.js
```

## Package Legitimacy Audit

Seam run: `gsd-tools query package-legitimacy check --ecosystem pypi ...` (2026-07-08).

| Package | Registry | Latest Publish | Downloads | Source Repo | Seam Verdict | Disposition |
|---------|----------|----------------|-----------|-------------|--------------|-------------|
| fastapi | PyPI | 2026-07-01 | n/a (PyPI) | github.com/fastapi/fastapi | SUS (too-new, unknown-downloads) | Approved — seam artifact, see note |
| uvicorn | PyPI | 2026-07-08 | n/a | github.com/Kludex/uvicorn | SUS (same) | Approved |
| sqlalchemy | PyPI | 2026-06-15 | n/a | sqlalchemy.org | SUS (same) | Approved |
| alembic | PyPI | 2026-06-25 | n/a | github.com/sqlalchemy/alembic | SUS (same) | Approved |
| jinja2 | PyPI | 2025-03-05 | n/a | github.com/pallets/jinja | SUS (unknown-downloads) | Approved |
| python-multipart | PyPI | 2026-06-04 | n/a | github.com/Kludex/python-multipart | SUS (unknown-downloads) | Approved |
| pydantic-settings | PyPI | 2026-06-19 | n/a | github.com/pydantic/pydantic-settings | SUS (same) | Approved |
| pytest | PyPI | 2026-06-19 | n/a | github.com/pytest-dev/pytest | SUS (same) | Approved |
| httpx | PyPI | 2024-12-06 | n/a | github.com/encode/httpx | SUS (unknown-downloads) | Approved |
| ruff | PyPI | 2026-06-25 | n/a | docs.astral.sh/ruff | SUS (same) | Approved |

**Packages removed due to [SLOP] verdict:** none — all exist on PyPI with canonical source repos.
**Packages flagged as suspicious [SUS]:** Formally all, but every SUS verdict is caused by two seam limitations, not by real risk signals: (1) PyPI does not expose weekly-download counts to the seam (`unknown-downloads` fires on every PyPI package), and (2) `too-new` triggers on the *latest release date* of packages that are 8–18 years old. All ten are canonical, long-established projects with official repos, independently verified against PyPI JSON metadata in STACK.md the same day [VERIFIED: PyPI registry + package-legitimacy seam]. **No `checkpoint:human-verify` gates are warranted for these installs.** No PyPI package here has install-time script risk flags surfaced by the seam (`postinstall: null` for all).

## Architecture Patterns

### System Architecture Diagram (this phase's slice)

```
run.bat ──► uv run uvicorn app.main:app (127.0.0.1:8000, 1 worker)
                     │
Browser (offline) ◄──┘  GET /  ──────────────────────────────┐
   │                                                          ▼
   │ POST /ops (HTMX form: skeleton ledger write)     routes/home.py, routes/ops.py
   │        │                                          (thin: parse form, render template)
   │        ▼                                                 │
   │  services/ledger.py: record_operation()                  │ Jinja2 templates
   │        │  one transaction:                               │ (base.html + partial)
   │        │  1. next_seq(device_id)                         │
   │        │  2. INSERT operations row (UUID, cents,         │
   │        │     UTC ISO text, created_by, seq)              │
   │        │  3. UPDATE products.quantity += qty_delta       │
   │        ▼                                                 │
   │  db.py: engine + Session ── connect event ──► PRAGMA WAL,│
   │        │                     foreign_keys=ON, busy_timeout
   │        ▼                                                 │
   │  SQLite file (data/myorishop.db, WAL mode)               │
   │    • operations table + BEFORE UPDATE/DELETE             │
   │      RAISE(ABORT) triggers (append-only enforced in DB)  │
   │    • products table (cached quantity projection)         │
   │    • alembic_version (migration #1 applied)              │
   └──── HTML partial swap: new ledger row + recomputed stock ◄┘
```

### Recommended Project Structure

Per locked decision (`app/models.py` single file — not the `models/` package from ARCHITECTURE.md; CONTEXT wins):

```
myorishop/
├── pyproject.toml           # uv-managed; deps + dev deps + ruff config
├── run.bat                  # start uvicorn + open browser
├── alembic.ini
├── alembic/
│   ├── env.py               # render_as_batch=True, imports app metadata
│   └── versions/            # migration #1: products, operations, triggers
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, StaticFiles mount, template config, routers
│   ├── config.py            # pydantic-settings: db_path, operator_name, device_id, display_tz
│   ├── core.py              # helpers: new_id(), utcnow_iso(), money to_cents()/format_cents()
│   ├── db.py                # engine, SessionLocal, get_session dependency, PRAGMA listener
│   ├── models.py            # Base (with naming_convention), Product, Operation
│   ├── services/
│   │   ├── __init__.py
│   │   └── ledger.py        # record_operation(), next_seq(), compute_stock(), rebuild_stock()
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── home.py          # GET / — page with ledger table + form
│   │   └── ops.py           # POST /ops — HTMX partial response
│   ├── templates/
│   │   ├── base.html        # loads /static/htmx.min.js; lang="ru"; UI text Russian
│   │   ├── pages/home.html
│   │   └── partials/ledger_rows.html
│   └── static/
│       ├── htmx.min.js      # vendored 2.0.10
│       └── style.css        # or pico.min.css vendored
├── data/                    # SQLite file lives here (gitignored)
└── tests/
    ├── conftest.py          # tmp-file SQLite engine fixture + TestClient
    ├── test_pragmas.py
    ├── test_ledger.py
    └── test_smoke.py
```

### Pattern 1: Ledger Insert + Projection Update in One Transaction (FND-01)

**What:** `record_operation()` is the ONLY code path that writes `operations` or touches `products.quantity`. Inside one session transaction: compute `next_seq`, INSERT operation row, `product.quantity += qty_delta`, commit. `compute_stock(product_id)` = `SELECT COALESCE(SUM(qty_delta),0) FROM operations WHERE product_id=:id` and `rebuild_stock()` resets all cached quantities from the ledger.
**When to use:** Every stock mutation, this phase and all later phases.
**Why safe here:** Single uvicorn worker + WAL + busy_timeout + short transactions = no lock contention; UNIQUE(device_id, seq) makes the MAX(seq)+1 pattern safe for one writer (see Pitfalls).

### Pattern 2: DB-Level Append-Only Enforcement (FND-01, FND-03)

**What:** The initial Alembic migration creates `BEFORE UPDATE` and `BEFORE DELETE` triggers on `operations` whose body is `SELECT RAISE(ABORT, '...')` — history becomes immutable at the database level, not just by convention. [CITED: sqlite.org/lang_createtrigger.html]
**Caveat the planner must record:** `synced_at` is a future sync cursor that WILL need UPDATE in v2. For v1 block ALL updates (synced_at is unused); the v2 sync milestone relaxes the trigger with a `WHEN` clause in a new migration. Cheap then, simpler now.
**Alembic note:** triggers are raw `op.execute()` in the migration; also note the Alembic batch-mode caveat — batch "move and copy" drops/recreates tables, so future batch migrations of `operations` must recreate the triggers (document this in the migration docstring). [CITED: alembic.sqlalchemy.org/en/latest/batch.html]

### Pattern 3: Sync-Ready Row Conventions (FND-02)

- **IDs:** `id: Mapped[str] = mapped_column(String(36), primary_key=True)`, value `str(uuid4())` generated in Python (stdlib). UUIDv4 is fine per CONTEXT discretion note.
- **Money:** `Integer` columns named `*_cents`. Conversion only at the edges via `app/core.py` helpers (`to_cents(str) -> int` using `decimal.Decimal`, `format_cents(int) -> str`). Never `float`. **This overrides ARCHITECTURE.md's `Numeric(10,2)` sketch — CONTEXT.md decision wins.**
- **Timestamps:** stored as UTC ISO-8601 TEXT per locked decision. Recommended implementation: `String(32)` columns + `utcnow_iso()` helper returning `datetime.now(timezone.utc).isoformat(timespec="seconds")` (e.g., `2026-07-08T12:00:00+00:00`). ISO-8601 UTC strings sort lexicographically = chronologically, so ordering and range queries work as TEXT. Do NOT use SQLAlchemy `DateTime` here: the SQLite dialect's default storage format drops the timezone offset, violating the "ISO-8601 UTC TEXT" decision [ASSUMED — based on SQLAlchemy SQLite dialect behavior; low risk, and the String approach sidesteps it entirely].
- **Soft delete:** `deleted_at` nullable TEXT on `products` (customers arrive in Phase 4).
- **payload:** `sqlalchemy.JSON` column (stores TEXT on SQLite, JSONB-able on PostgreSQL later) for type-specific fields per CONTEXT decision.

### Pattern 4: Per-Connection PRAGMA Event Listener

Official SQLAlchemy pattern — including the non-obvious autocommit gotcha (the sqlite3 driver silently ignores `PRAGMA foreign_keys` when `autocommit=False`). See Code Example 1. [CITED: docs.sqlalchemy.org/en/20/dialects/sqlite.html]

### Pattern 5: HTMX Fragment Endpoint (walking-skeleton slice)

One page (`GET /`) renders the ledger table + a minimal operation form; `POST /ops` returns only the partial (`partials/ledger_rows.html` + updated stock) which HTMX swaps in. Use `hx-post`/`hx-target`/`hx-swap`; add `hx-disabled-elt="this"` on the submit button (double-submit guard from PITFALLS.md #6). UI text in Russian.

**Walking-skeleton content recommendation (planner's choice on details):** seed one demo product in migration or via a tiny form, and let the skeleton form record a `correction` operation (qty_delta ±N) — `correction` is the one op type that needs no prices, exercising the full ledger path without pulling Phase 3/5 semantics forward.

### Anti-Patterns to Avoid
- **Business logic in route handlers** — routes parse forms and render templates only (ARCHITECTURE.md anti-pattern 5)
- **`Base.metadata.create_all()` as the schema mechanism** — Alembic migration #1 is the schema source of truth from day one (locked decision); `create_all` acceptable only inside test fixtures
- **Any UPDATE/DELETE on `operations`** — enforced by triggers; corrections are new rows
- **`datetime.now()` naive, `float()` on money, autoincrement PKs** — all blocked by conventions above
- **Binding to `0.0.0.0`** — locked to 127.0.0.1 (no auth in v1)
- **SQLite-specific SQL** (`INSERT OR REPLACE`, `strftime`) — ORM-portable constructs only (PostgreSQL later)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema evolution | Manual ALTER scripts / drop-and-recreate | Alembic (batch mode) | SQLite can't ALTER most things; Alembic batch does move-and-copy correctly |
| Settings loading | Custom config parser | pydantic-settings + `.env` | Typed, standard, keeps paths/identity out of code |
| Form parsing | Manual body parsing | FastAPI `Form(...)` + python-multipart | Validation for free |
| Decimal money input parsing | Regex/float parsing of "12,50" | `decimal.Decimal` in one `to_cents()` helper | Float corruption; comma decimal separator in Russian locale — handle `,`→`.` in the helper |
| UUIDs / timestamps | Custom ID or time formats | stdlib `uuid.uuid4()`, `datetime.now(timezone.utc).isoformat()` | Zero deps, sync-safe |
| Test HTTP calls | Spinning up real server in tests | `fastapi.testclient.TestClient` (httpx) | In-process, fast, standard |
| Frontend interactivity | Custom JS fetch/DOM code | htmx attributes | Locked decision; zero build step |

**Key insight:** every hand-rolled piece here (config, migrations, money parsing) is exactly where beginner projects rot; the standard tools are each < 20 lines of integration.

## Common Pitfalls

Phase-1-relevant subset of `.planning/research/PITFALLS.md` (full detail there), plus phase-specific additions:

### Pitfall 1: PRAGMAs set once instead of per-connection
**What goes wrong:** WAL/foreign_keys "configured at startup" but connections from the pool don't have them; FKs silently unenforced.
**How to avoid:** `@event.listens_for(engine, "connect")` listener (Code Example 1); assert PRAGMA values in a test on a live pooled connection.
**Warning signs:** `PRAGMA foreign_keys` returns 0 in the test; orphan rows possible.

### Pitfall 2: foreign_keys PRAGMA silently ignored (autocommit gotcha)
**What goes wrong:** The sqlite3 driver does not apply `PRAGMA foreign_keys` while a transaction is implicitly open (`autocommit=False`) — the listener runs, nothing errors, FKs stay off. [CITED: docs.sqlalchemy.org/en/20/dialects/sqlite.html]
**How to avoid:** In the listener, temporarily set `dbapi_connection.autocommit = True`, execute PRAGMAs, restore. Exact official snippet in Code Example 1.

### Pitfall 3: `Numeric`/`Float` money columns sneaking in from ARCHITECTURE.md sketch
**What goes wrong:** The Operation sketch in ARCHITECTURE.md uses `Numeric(10,2)` — copying it violates FND-02 and the locked decision; SQLAlchemy `Numeric` on SQLite round-trips through float.
**How to avoid:** Planner must specify `Integer` `_cents` columns explicitly in the task; verification greps models.py for `Numeric|Float`.

### Pitfall 4: Alembic autogenerate without a naming convention
**What goes wrong:** SQLite allows unnamed constraints; future batch migrations can't target them for drop — dead end discovered months later. [CITED: alembic.sqlalchemy.org/en/latest/batch.html]
**How to avoid:** Set `naming_convention` on `MetaData` in `models.py` from day one (Code Example 2).

### Pitfall 5: Browser opens before uvicorn is listening (run.bat race)
**What goes wrong:** `start http://...` fires instantly; uvicorn takes ~1–2 s; operator sees "connection refused" on first launch.
**How to avoid:** Delay the browser open ~2 s in run.bat (Code Example 6), or accept one manual refresh. Keep run.bat ASCII-only (no Russian text — cmd codepage mangling).

### Pitfall 6: seq computed outside the write transaction
**What goes wrong:** `MAX(seq)+1` read in one transaction, insert in another → duplicate seq under concurrent requests (double-click).
**How to avoid:** Compute and insert in the same transaction (single writer + WAL serializes writes); `UNIQUE(device_id, seq)` constraint catches any violation loudly; `hx-disabled-elt` guards the UI.

### Pitfall 7: Tests sharing the dev database
**What goes wrong:** pytest runs pollute `data/myorishop.db` with test operations.
**How to avoid:** conftest fixture builds an engine on `tmp_path` SQLite file (file-based, not `:memory:` — `:memory:` is per-connection and breaks with pooled sessions unless `StaticPool` is used); apply schema via `Base.metadata.create_all` + `op.execute` trigger DDL, or run Alembic upgrade against the tmp DB.

### Pitfall 8: Windows console + UTF-8
**What goes wrong:** Russian UI text is fine in the browser (UTF-8 templates) but uvicorn logs/print of Cyrillic can garble in cmd.
**How to avoid:** Keep logs English-only; templates saved as UTF-8; add `<meta charset="utf-8">` and `lang="ru"` in base.html. [ASSUMED — standard Windows console behavior; low risk]

## Code Examples

### 1. Engine + per-connection PRAGMAs (db.py)
```python
# Source: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html (verified 2026-07-08)
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

engine = create_engine(f"sqlite:///{settings.db_path}")  # sync driver, no aiosqlite

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    # sqlite3 driver ignores PRAGMA foreign_keys while autocommit=False
    ac = dbapi_connection.autocommit
    dbapi_connection.autocommit = True
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
    dbapi_connection.autocommit = ac

SessionLocal = sessionmaker(bind=engine)

def get_session():           # FastAPI dependency, plain def
    with SessionLocal() as session:
        yield session
```

### 2. Base with naming convention (models.py)
```python
# Source: https://alembic.sqlalchemy.org/en/latest/batch.html (naming convention requirement)
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

### 3. Alembic env.py core + append-only triggers in migration #1
```python
# env.py — Source: https://alembic.sqlalchemy.org/en/latest/batch.html
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    render_as_batch=True,          # SQLite-safe migrations from day one
)
```
```python
# in versions/0001_initial.py upgrade(), after create_table("operations", ...):
# Source: https://sqlite.org/lang_createtrigger.html (verified 2026-07-08)
op.execute("""
    CREATE TRIGGER operations_no_update
    BEFORE UPDATE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
""")
op.execute("""
    CREATE TRIGGER operations_no_delete
    BEFORE DELETE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
""")
# NOTE: any future batch (move-and-copy) migration of `operations`
# drops the table and must recreate these triggers.
```

### 4. Operation model per CONTEXT.md schema (models.py)
```python
# Conventions: UUID TEXT PK, integer cents, UTC ISO-8601 TEXT, JSON payload
from sqlalchemy import String, Integer, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

class Operation(Base):
    __tablename__ = "operations"
    __table_args__ = (UniqueConstraint("device_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)   # str(uuid4())
    type: Mapped[str] = mapped_column(String(20))   # receipt|sale|writeoff|return|correction
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    qty_delta: Mapped[int] = mapped_column(Integer)                 # signed
    unit_cost_cents: Mapped[int | None] = mapped_column(Integer)
    unit_price_cents: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict | None] = mapped_column(JSON)              # type-specific fields
    device_id: Mapped[str] = mapped_column(String(36))
    seq: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(32))             # UTC ISO-8601 TEXT
    created_by: Mapped[str] = mapped_column(String(100))
    synced_at: Mapped[str | None] = mapped_column(String(32))       # v2 sync cursor
```

### 5. Ledger service — the single write path (services/ledger.py)
```python
# Pattern verified against ARCHITECTURE.md Pattern 2; money/time per CONTEXT.md
from uuid import uuid4
from sqlalchemy import select, func
from app.models import Operation, Product
from app.core import utcnow_iso

def next_seq(session, device_id: str) -> int:
    current = session.scalar(
        select(func.max(Operation.seq)).where(Operation.device_id == device_id)
    )
    return (current or 0) + 1

def record_operation(session, *, type_: str, product_id: str, qty_delta: int,
                     unit_cost_cents: int | None = None,
                     unit_price_cents: int | None = None,
                     payload: dict | None = None) -> Operation:
    op = Operation(
        id=str(uuid4()), type=type_, product_id=product_id, qty_delta=qty_delta,
        unit_cost_cents=unit_cost_cents, unit_price_cents=unit_price_cents,
        payload=payload, device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(), created_by=settings.operator_name,
    )
    session.add(op)
    product = session.get(Product, product_id)
    product.quantity += qty_delta          # cached projection, same transaction
    session.commit()
    return op

def compute_stock(session, product_id: str) -> int:
    return session.scalar(
        select(func.coalesce(func.sum(Operation.qty_delta), 0))
        .where(Operation.product_id == product_id)
    )
```

### 6. run.bat [ASSUMED — trivial Windows batch, low risk]
```bat
@echo off
cd /d "%~dp0"
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:8000"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Single worker is uvicorn's default (no `--workers` flag — one SQLite writer). `--reload` is for dev only, not in run.bat.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SQLAlchemy 1.x `declarative_base()`, `Column()` | 2.0 `DeclarativeBase`, `Mapped[]`, `mapped_column()`, `select()` | SQLAlchemy 2.0 (2023) | Most web tutorials are outdated — use only 2.0-style examples |
| pip + venv + requirements.txt | uv + pyproject.toml | community shift 2024–2025 | Locked decision; uv 0.11.x installed |
| htmx 1.x / htmx 4.0 beta | htmx 2.0.10 stable | 4.0.0-beta5 is beta (2026-06) | Vendor 2.0.10; do not touch 4.x |
| `@app.on_event("startup")` | lifespan context manager | FastAPI deprecation | Use `lifespan=` if startup hooks needed [ASSUMED] |

**Deprecated/outdated:** `declarative_base()` legacy style; FastAPI `on_event`; Pydantic v1 patterns.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SQLAlchemy `DateTime` on SQLite drops tz offset, so `String` + ISO helper is the right way to honor "ISO-8601 TEXT" decision | Pattern 3 | Low — String approach works regardless; only matters if planner prefers `DateTime` |
| A2 | run.bat browser-delay pattern (`timeout /t 2` + `start`) works on Windows 11 cmd | Code Example 6 | Low — worst case: operator refreshes once; verify at checkpoint |
| A3 | `lifespan` is the current FastAPI startup-hook style (on_event deprecated) | State of the Art | None for this phase — no startup hooks strictly needed |
| A4 | Cyrillic-safe console behavior / UTF-8 template handling on Windows | Pitfall 8 | Low — visible immediately, trivial fix |
| A5 | `sqlite3` CLI absence is harmless (Python's bundled sqlite3 module suffices for all phase tasks) | Environment | Low — tests use Python; no task should shell out to sqlite3 |

## Open Questions

1. **Q1: Repo layout — project root already contains .planning/**
   - What we know: `E:\dev\myorishop` has `.planning/` but no git repo and no Python project yet; `uv init myorishop` would nest a folder.
   - What's unclear: whether to `uv init` in-place at repo root (recommended) — and the plan likely needs `git init` since GSD commits are configured (`commit_docs: true`) but no repo exists.
   - Recommendation: `uv init --python 3.13` (or manual pyproject) in-place at `E:\dev\myorishop`; include `git init` + `.gitignore` (data/, .venv/, __pycache__/, *.db*) as an early task.
2. **Q2: Python 3.13 not installed on this machine**
   - What we know: uv 0.11.11 present; uv-managed 3.12.13 exists; system 3.11.9/3.14.x present; `uv python find 3.13` fails.
   - Recommendation: task step `uv python install 3.13` (one-time internet). Fallback if offline at execution time: pin `requires-python = ">=3.12"` and use 3.12.13; STACK.md explicitly allows 3.12+.
3. **Q3: What does the walking-skeleton UI interaction record?**
   - What we know: success criteria need one real ledger write via HTMX; correction ops need no prices.
   - Recommendation: seed one demo product; skeleton form records a `correction` with signed qty; page lists operations (who/when — FND-03 visible) and shows cached vs recomputed stock. Planner may swap for a minimal product-create form if preferred.
4. **Q4: `payload` JSON vs real columns for future FKs (Phase 4)**
   - What we know: CONTEXT locks payload JSON for type-specific fields; ARCHITECTURE.md sketched a `customer_id` FK column.
   - Recommendation: no action now; Phase 4 planning decides whether `customer_id` gets promoted to a real column via migration (referential integrity for SAL-03). Note for STATE.md, not this phase.

## Environment Availability

Probed on this machine 2026-07-08:

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | package/env management (locked) | ✓ | 0.11.11 | — (works; 0.11.28 in STACK.md is just newer) |
| Python 3.13 | locked runtime decision | ✗ | — | `uv python install 3.13` (one-time internet) or uv-managed 3.12.13 (present) |
| Python 3.12 (uv-managed) | fallback runtime | ✓ | 3.12.13 | — |
| git | version control, GSD commits | ✓ | 2.45.1.windows.1 | — (but **repo not initialized** — needs `git init`) |
| sqlite3 CLI | nothing (optional inspection) | ✗ | — | Python bundled `sqlite3` module (sufficient) |
| Internet (one-time) | `uv add` deps, htmx.min.js download, `uv python install` | assumed available at build time | — | none — flag: initial setup requires internet once; runtime is fully offline after |
| Default browser | run.bat opens UI | ✓ (Windows 11) | — | manual navigation to localhost:8000 |

**Missing dependencies with no fallback:** none blocking — initial dependency download requires internet once (unavoidable for a greenfield project).
**Missing dependencies with fallback:** Python 3.13 (install via uv, or use 3.12.13).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (+ httpx 0.28.1 for TestClient) |
| Config file | none yet — see Wave 0 (`[tool.pytest.ini_options]` in pyproject.toml) |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FND-01 | UPDATE/DELETE on operations raises (triggers); stock == SUM(qty_delta) after mixed ops; rebuild_stock repairs a tampered cache | unit/integration | `uv run pytest tests/test_ledger.py -x` | ❌ Wave 0 |
| FND-02 | Money columns are Integer `_cents`; ids are 36-char uuid4 strings; created_at parses as ISO-8601 UTC | unit | `uv run pytest tests/test_ledger.py -x -k conventions` | ❌ Wave 0 |
| FND-03 | Every recorded operation has non-null created_by (== settings operator) and created_at | unit | `uv run pytest tests/test_ledger.py -x -k audit` | ❌ Wave 0 |
| — (infra) | Live pooled connection has journal_mode=WAL, foreign_keys=1, busy_timeout=5000 | integration | `uv run pytest tests/test_pragmas.py -x` | ❌ Wave 0 |
| — (skeleton) | GET / returns 200 with htmx script tag; POST /ops returns partial with new row | smoke | `uv run pytest tests/test_smoke.py -x` | ❌ Wave 0 |
| — (deploy) | run.bat starts app, browser shows page offline | manual-only (needs real browser + Windows shell) | human checkpoint at phase end | — |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest` + `uv run ruff check .`
- **Phase gate:** full suite green + manual run.bat check before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/conftest.py` — tmp-path SQLite engine + session fixture + TestClient fixture (covers all FND tests)
- [ ] `tests/test_pragmas.py` — PRAGMA assertions on live connection
- [ ] `tests/test_ledger.py` — covers FND-01, FND-02, FND-03
- [ ] `tests/test_smoke.py` — route smoke tests
- [ ] Framework install: `uv add --dev pytest httpx ruff` + `[tool.pytest.ini_options]` in pyproject.toml

## Security Domain

ASVS Level 1 scope (config: `security_enforcement: true`, level 1). Localhost single-user app — the dominant risks are data exposure and injection, not intrusion.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (locked: no auth in v1) | deferred to v2 (AUTH-V2-01) |
| V3 Session Management | no | — |
| V4 Access Control | no (single local user) | network-level: bind 127.0.0.1 only |
| V5 Input Validation | yes | FastAPI `Form(...)`/Pydantic typing; `to_cents()` Decimal parsing rejects garbage |
| V6 Cryptography | no (no secrets/crypto this phase) | — |

### Known Threat Patterns for FastAPI + SQLite + Jinja2

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| App exposed on LAN (no auth) | Information Disclosure | uvicorn `--host 127.0.0.1` hard-coded in run.bat AND docs; never `0.0.0.0` in v1 |
| SQL injection via search/filter strings | Tampering | SQLAlchemy ORM/parameterized only; zero raw f-string SQL (grep-verifiable) |
| XSS via product/operator names in templates | Tampering | Jinja2 autoescape (on by default via Jinja2Templates); never `\| safe` on user input |
| Secrets in code/git | Information Disclosure | pydantic-settings + `.env` (gitignored) from day one; no secrets exist yet in v1 |
| Ledger tampering (integrity of audit trail) | Repudiation/Tampering | DB-level RAISE(ABORT) triggers; single write path in services/ledger.py |

## Sources

### Primary (cited from official documentation this session)
- https://docs.sqlalchemy.org/en/20/dialects/sqlite.html — PRAGMA connect-event listener + autocommit gotcha (fetched 2026-07-08)
- https://alembic.sqlalchemy.org/en/latest/batch.html — render_as_batch config, naming-convention and trigger-recreation caveats (fetched 2026-07-08)
- https://sqlite.org/lang_createtrigger.html — RAISE(ABORT) append-only trigger syntax (fetched 2026-07-08)
- PyPI registry metadata via package-legitimacy seam — all 10 packages exist, canonical repos, no deprecations (2026-07-08)

### Secondary (milestone research, verified 2026-07-08)
- `.planning/research/STACK.md` — all versions verified against PyPI/unpkg/GitHub (HIGH)
- `.planning/research/ARCHITECTURE.md` — ledger/event-log patterns, project structure (MEDIUM-HIGH)
- `.planning/research/PITFALLS.md` — SQLite/money/schema pitfalls with sources (MEDIUM-HIGH)

### Tertiary (training knowledge, tagged [ASSUMED] inline)
- run.bat browser-launch pattern; Windows console UTF-8 behavior; FastAPI lifespan deprecation note; SQLAlchemy DateTime tz-storage detail

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified against PyPI registry on research date; legitimacy seam run this session
- Architecture: HIGH — locked by CONTEXT.md decisions; load-bearing snippets (PRAGMA listener, batch config, triggers) cited from official docs this session
- Pitfalls: MEDIUM-HIGH — official-docs-backed for SQLite/SQLAlchemy behavior; environment findings (Python 3.13 absent, no git repo) verified by direct probe
- Environment: HIGH — probed directly on the target machine

**Research date:** 2026-07-08
**Valid until:** 2026-08-07 (stable stack; re-verify only htmx 4.x status and FastAPI minor version if planning slips)
