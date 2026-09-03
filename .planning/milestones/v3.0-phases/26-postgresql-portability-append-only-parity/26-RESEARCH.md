# Phase 26: PostgreSQL Portability & Append-Only Parity - Research

**Researched:** 2026-07-18
**Domain:** Database dialect portability (SQLite ↔ PostgreSQL), Alembic single-history migrations, DB-level append-only enforcement, CI with a real Postgres service
**Confidence:** HIGH (repo is fully inspected; external facts verified against SQLAlchemy 2.0 + GitHub Actions docs)

## Summary

This phase is a **mechanical dialect-gating pass** on an existing, well-disciplined SQLite codebase. The models, the money-as-integer-cents convention, UUID text PKs, ISO-8601 text timestamps, generic `sa.JSON()` columns, and the partial unique index are **already portable** — the last one (`uq_products_code_active`) already carries both `sqlite_where=` and `postgresql_where=`. There is **no** SQLite-specific SQL in the query layer: every case-insensitive Cyrillic search compares a Python-lowercased query string against a Python-maintained `name_lc`/`search_lc`/`name_lc` shadow column via `LIKE '%…%'` (SQLAlchemy `.contains()`), which behaves identically on both dialects. The only `func.lower()` SQL call is on ASCII product codes, which fold identically everywhere.

The real work concentrates in **four small, coupled surfaces**: (1) the append-only triggers in migrations `0001` and `0013` are written in SQLite trigger syntax (`RAISE(ABORT, …)`) that is invalid on PostgreSQL and will crash `alembic upgrade head` at revision `0001` on an empty PG database; (2) `alembic/env.py` hardcodes a `sqlite:///` URL and unconditional `render_as_batch=True`; (3) `app/db.py`'s `build_engine()` hardcodes a `sqlite://` engine plus a `connect`-event listener that issues SQLite-only `PRAGMA` statements which error on PG; (4) there is **no `postgresql+psycopg://` engine path and no CI at all** (`.github/` does not exist, though a GitHub remote does). The test fixtures (`tests/conftest.py`) build schema via `create_all` + SQLite trigger DDL — fine to leave as-is for the existing suite, but a **new PG integration test that runs the real migration history** is required to prove Success Criteria 1 & 3.

**Primary recommendation:** Retrofit dialect branching (`op.get_bind().dialect.name`) into migrations `0001` and `0013` so the SQLite output is byte-for-behavior unchanged while PostgreSQL gets an equivalent PL/pgSQL trigger-function guard; gate `render_as_batch`, the connect-event PRAGMAs, and the engine URL by dialect; add `psycopg` (v3) as a dependency; and stand up a GitHub Actions job with a `services: postgres` container that runs `alembic upgrade head` against empty PG and asserts schema parity + UPDATE/DELETE rejection on `operations` and `cash_movements`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRV-01 | The same data models and single Alembic migration history run unchanged on both SQLite (client) and PostgreSQL (server). | §"SQLite-Coupled Surfaces" enumerates every coupled file; §"render_as_batch gating", §"Connect-event PRAGMA gating", §"psycopg engine builder", §"Cyrillic search parity" show the exact changes. Success proven by the CI job in §"Validation Architecture" running `alembic upgrade head` on empty PG. |
| SRV-02 | The central server runs on PostgreSQL and enforces the same append-only ledger guarantee (UPDATE/DELETE of ledger rows blocked at the DB) as the SQLite client. | §"Append-Only Trigger Parity" gives the PL/pgSQL trigger-function equivalent and the single-history dialect-branch pattern for migrations 0001/0013; CI asserts UPDATE and DELETE both raise on both tables. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema definition (one model set) | ORM / `app/models.py` | Alembic migrations | Models already declare dual-dialect index predicates; migrations are the schema source of truth. |
| Migration history (one chain) | Alembic `alembic/versions/*` | `alembic/env.py` | Same numbered chain must run on both engines; env.py chooses URL + batch mode by dialect. |
| Append-only enforcement | Database (triggers) | — | The guarantee must live in the DB, not the app, so it holds regardless of caller; this is the SRV-02 contract. |
| Engine / connection setup | `app/db.py` | `app/config.py` | Driver choice, connect-args, and per-connection PRAGMAs are engine-tier concerns; must branch by URL scheme. |
| Case-insensitive Cyrillic search | Service layer (`catalog.py`, `customers.py`) | DB (indexed shadow column) | Folding is done in Python (`str.lower()`); the DB only does a `LIKE` on the pre-lowered shadow — dialect-agnostic by construction. |
| CI Postgres provisioning | CI (GitHub Actions `services:`) | — | A throwaway PG container per run proves parity without any production server existing yet. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| psycopg (v3) | 3.3.4 | PostgreSQL DBAPI driver for SQLAlchemy 2.0 | The modern PostgreSQL adapter; SQLAlchemy 2.0's `postgresql+psycopg://` dialect targets it. `[VERIFIED: pip index versions psycopg → 3.3.4]` `[CITED: docs.sqlalchemy.org/en/20/dialects/postgresql.html — "psycopg (a.k.a. psycopg 3)", URL `postgresql+psycopg://`]` |
| SQLAlchemy | 2.0.* (installed) | ORM / dialect abstraction | Already the project ORM; its generic types (`JSON`, `String`, `Integer`) and `postgresql_where=` already produce portable DDL. `[VERIFIED: pyproject.toml]` |
| Alembic | 1.18.* (installed) | Migration history | Already the migration tool; `op.get_bind().dialect.name` is the standard dialect-branch hook inside a migration. `[VERIFIED: pyproject.toml]` |
| PostgreSQL (server) | 16 or 17 (CI image `postgres`) | Target server DB | The v3.0 milestone's central-server database. Any modern major version supports `CREATE FUNCTION … plpgsql` + `BEFORE UPDATE OR DELETE` triggers. `[ASSUMED — pin the exact major in CI, e.g. `postgres:17`]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psycopg[binary] | 3.3.* | Prebuilt libpq wheels (no local C build) | Use the `[binary]` extra in CI/dev so no system libpq/compiler is needed. `[CITED: psycopg 3 install docs — the `binary` extra ships prebuilt wheels]` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg (v3) | psycopg2 (`postgresql+psycopg2://`) | psycopg2 is legacy/maintenance-mode; v3 is the current line and the project targets a fresh server. No reason to adopt the old driver. |
| GitHub Actions `services: postgres` | Local `docker run postgres` + pytest marker | CI on a Linux runner is the canonical proof of "in CI" (SRV-01/02 wording); a local docker path is a useful Windows-dev fallback (see §Environment Availability) but is not the deliverable. |
| PL/pgSQL trigger function | PostgreSQL `RULE` (`CREATE RULE … DO INSTEAD NOTHING`) | A rule that silently swallows the UPDATE would *not* raise — SRV-02 needs a hard rejection, so a `RAISE EXCEPTION` trigger is required, matching SQLite's `RAISE(ABORT)`. |

**Installation:**
```bash
uv add "psycopg[binary]"
```

**Version verification:** `pip index versions psycopg` → `3.3.4` latest (verified 2026-07-18). Pin as `psycopg==3.3.*` in `pyproject.toml` to match the project's existing minor-pin style.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| psycopg | PyPI | Mature (v3 line since 2021; 3.3.4 current) | Very high (millions/mo) | github.com/psycopg/psycopg | OK | Approved — official PostgreSQL adapter, SQLAlchemy-documented driver |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

> Note: the `package-legitimacy` seam is unavailable in this environment (`Unknown command`). Verified manually: `psycopg` exists on PyPI (`pip index versions psycopg`), is the project name at psycopg.org / github.com/psycopg/psycopg, and is the driver named in the official SQLAlchemy PostgreSQL dialect docs. Confidence HIGH.

## SQLite-Coupled Surfaces (current state — cite paths/lines)

Every file below is dialect-coupled **today** and is in scope for this phase. Line numbers are as of research date.

| # | File / location | Coupling | Action this phase |
|---|-----------------|----------|-------------------|
| 1 | `alembic/env.py:19` | `config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.db_path}")` — URL hardcoded to sqlite | Choose URL from config; support a `postgresql+psycopg://` override (e.g. `DATABASE_URL` env or `settings.database_url`). |
| 2 | `alembic/env.py:48` and `:72` | `render_as_batch=True` unconditional (offline + online configure) | Gate: `render_as_batch = connection.dialect.name == "sqlite"`. Harmless-but-clean; see §render_as_batch gating. |
| 3 | `app/db.py:46-63` `build_engine()` | Always `create_engine(f"sqlite:///{db_path}")`; registers a `connect` listener issuing `PRAGMA journal_mode=WAL / foreign_keys=ON / busy_timeout` | Branch engine creation by URL scheme; attach the PRAGMA listener **only** for sqlite. See §psycopg engine builder + §Connect-event PRAGMA gating. |
| 4 | `app/db.py:22-43` `APPEND_ONLY_TRIGGERS` | Four SQLite `CREATE TRIGGER … RAISE(ABORT,…)` statements used by **test fixtures** | Leave for the SQLite suite; add a PG-equivalent DDL constant (or a PG integration test that runs migrations instead of fixtures). |
| 5 | `alembic/versions/0001_initial_schema.py:38-49, 95-96, 125-126` | Frozen SQLite trigger DDL on `operations` emitted unconditionally; `downgrade` `DROP TRIGGER IF EXISTS` | **Retrofit dialect branch** (see §Append-Only Trigger Parity). This is the migration that fails first on PG. |
| 6 | `alembic/versions/0013_cash_movements.py:37-48, 80-81, 85-86` | Frozen SQLite trigger DDL on `cash_movements`, same shape | Retrofit dialect branch identically. |
| 7 | `tests/conftest.py:15, 22-32` | `engine` fixture builds SQLite file DB, `create_all`, then execs `APPEND_ONLY_TRIGGERS` (SQLite DDL) | Keep for existing suite. Add a **separate** PG fixture/test that runs `alembic upgrade head`. |
| 8 | `tests/test_pragmas.py` | Asserts SQLite `PRAGMA` values + queries `sqlite_master` for trigger names | SQLite-only test — keep, but guard/skip if ever parametrized for PG; PG parity gets its own assertions. |
| 9 | `app/services/backup.py:44` | `VACUUM INTO ?` — SQLite-only | **Client-only** runtime feature; the server never runs it. Out of scope for schema parity, but flag: never call `create_backup()` against a PG engine. See Pitfall 4. |

**Already portable (verified — no action):**
- `app/models.py:158-166` — `Index("uq_products_code_active", …, sqlite_where=…, postgresql_where=…)` dual-dialect partial unique index. `[VERIFIED: app/models.py]`
- `alembic/versions/0003_products_code_active_unique.py:34` — same partial index in migration form with both predicates. `[VERIFIED]`
- All money columns are `Integer` cents; all PKs are `String(36)` UUID text with Python `default=new_id` (no `AUTOINCREMENT`); all timestamps are `String(32)` UTC ISO text; `is_active`/`is_legacy` are `Integer` not `Boolean`; `payload`/`catalogs` are generic `sa.JSON()`. All portable. `[VERIFIED: app/models.py]`
- No migration calls `op.batch_alter_table(...)` and none calls `op.alter_column(...)`; every schema change uses native `op.add_column` / `op.create_table` / `op.create_index` / `op.drop_column`. `[VERIFIED: grep across alembic/versions/*.py]`
- `strftime` occurrences are **Python** `datetime.strftime` (`app/core.py`, `app/services/dashboard.py`, `app/services/backup.py`), not SQLite SQL. `[VERIFIED]`

## Architecture Patterns

### System Architecture Diagram (data/DDL flow this phase)

```
                    ┌─────────────────────────┐
                    │  ONE Alembic history     │
                    │  0001 … 0017 (unchanged  │
                    │  numbering)              │
                    └───────────┬──────────────┘
                                │  op.get_bind().dialect.name
                 ┌──────────────┴───────────────┐
                 ▼                               ▼
        dialect == "sqlite"             dialect == "postgresql"
        RAISE(ABORT) triggers           CREATE FUNCTION plpgsql
        PRAGMA WAL/FK on connect         + BEFORE UPD/DEL triggers
        render_as_batch=True             render_as_batch=False
                 │                               │
                 ▼                               ▼
        ┌─────────────────┐             ┌─────────────────────┐
        │ sqlite:///…db   │             │ postgresql+psycopg://│
        │ (desktop client)│             │ (server / CI service)│
        └─────────────────┘             └─────────────────────┘
                 │                               │
                 └──────────┬────────────────────┘
                            ▼
              app/db.build_engine(url) chooses driver
              & attaches PRAGMA listener ONLY for sqlite
                            │
                            ▼
              Service layer (unchanged): Python str.lower()
              shadow columns → LIKE '%q%' → identical results
```

### Pattern 1: Single-history dialect-branched trigger DDL
**What:** One migration emits different DDL per backend from the same `upgrade()`.
**When to use:** Any DB-object whose syntax differs between SQLite and PostgreSQL (triggers here).
**Example:**
```python
# Source: Alembic runtime API — op.get_bind().dialect.name
# (pattern; PG DDL below is the equivalent of the existing SQLite RAISE(ABORT))
from alembic import op

_SQLITE_OPERATIONS_TRIGGERS = (
    """CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
       BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END""",
    """CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations
       BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END""",
)

_PG_OPERATIONS_DDL = (
    """CREATE OR REPLACE FUNCTION operations_append_only()
       RETURNS trigger LANGUAGE plpgsql AS $$
       BEGIN RAISE EXCEPTION 'operations ledger is append-only'; END; $$""",
    """CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
       FOR EACH ROW EXECUTE FUNCTION operations_append_only()""",
    """CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations
       FOR EACH ROW EXECUTE FUNCTION operations_append_only()""",
)

def upgrade() -> None:
    # ... create_table(operations) ... (unchanged, portable)
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_OPERATIONS_DDL:
            op.execute(stmt)
    else:  # sqlite — output byte-for-behavior identical to today
        for stmt in _SQLITE_OPERATIONS_TRIGGERS:
            op.execute(stmt)
```
Note the trigger **names** (`operations_no_update`, `operations_no_delete`) are kept identical across dialects so `tests/test_pragmas.py`-style name assertions and Phase 28's column-scoped relaxation can target the same names on both.

### Pattern 2: One combined PG trigger vs two SQLite triggers (optional)
PostgreSQL allows `BEFORE UPDATE OR DELETE` in a single trigger. **Recommendation:** keep **two** separate PG triggers named `operations_no_update` / `operations_no_delete` (not one combined) to preserve name parity with SQLite and to leave Phase 28's future "relax UPDATE but not DELETE" change trivially targetable. `[ASSUMED — parity-driven design choice; confirm in discuss-phase]`

### Pattern 3: Dialect-gated engine + connect listener
```python
# Source: app/db.py build_engine() refactor (pattern)
def build_engine(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            ...  # existing WAL / foreign_keys / busy_timeout block, unchanged
    return engine
```
`settings.db_path` → a full URL. Simplest: add `settings.database_url` (default `f"sqlite:///{db_path}"`), let `.env` override with `postgresql+psycopg://…`. `env.py` reads the same setting so client and migrations agree.

### Anti-Patterns to Avoid
- **Editing 0001/0013 in a way that changes SQLite output.** The dialect branch must leave the SQLite path emitting the exact same statements it does today (WR-06 immutability = deterministic replay). Adding a PG-only branch does not change SQLite replay — that is the whole point.
- **A brand-new "fix triggers on PG" migration appended at the end.** It cannot work: `alembic upgrade head` on empty PG fails at revision `0001` (SQLite `RAISE(ABORT)` syntax) long before any later revision runs. The branch must live *in* 0001 and 0013.
- **`func.lower()` on Cyrillic columns.** SQLite `lower()` folds ASCII only. The code already restricts `func.lower()` to ASCII `code`; do not "simplify" any Cyrillic search to SQL `lower()`/`ILIKE` — it would diverge from SQLite.
- **`op.batch_alter_table` on `operations`/`cash_movements`.** Batch = move-and-copy = drops triggers (Phase 25 memory + `0004`/`0017` warnings). Never batch the ledger tables on either dialect.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PG connection driver | Raw libpq bindings / custom pool | `psycopg` (v3) + SQLAlchemy `postgresql+psycopg://` | Official, pooled, SQLAlchemy-integrated. |
| Case-insensitive Cyrillic match | SQL `LOWER()`/`ILIKE`/`citext`/collation tricks | Existing Python `str.lower()` shadow column + `.contains()` | Already works identically on both dialects; changing it *introduces* divergence. |
| Append-only enforcement | App-layer "read-only" checks | DB triggers (`RAISE(ABORT)` / `RAISE EXCEPTION`) | SRV-02 requires the guarantee at the database, independent of caller. |
| Ephemeral PG for tests | Hand-rolled install/teardown scripts | GitHub Actions `services: postgres` with `pg_isready` health check | Standard, disposable, health-gated. `[CITED: GitHub Actions postgres service-container docs]` |

**Key insight:** The codebase was written *for* this moment — the hard portability decisions (integer money, UUID text PKs, ISO text time, Python-folded search, dual-dialect partial index, no batch on ledger tables) are already made. This phase is trigger-DDL branching + engine/env/CI plumbing, not a redesign.

## Common Pitfalls

### Pitfall 1: Migration 0001 crashes on PG before anything else runs
**What goes wrong:** `alembic upgrade head` against empty PG fails at `0001` with a syntax error on `SELECT RAISE(ABORT, …)`.
**Why:** `RAISE(ABORT, …)` is SQLite trigger-body syntax; PG has no such function.
**How to avoid:** Put the `op.get_bind().dialect.name` branch **inside** `0001.upgrade()` (and `0013.upgrade()`), emitting PL/pgSQL on PG.
**Warning signs:** CI job red at the first migration; error mentions `RAISE` or `syntax error at or near`.

### Pitfall 2: Trigger dropped by a future batch migration (still true on PG)
**What goes wrong:** A later batch/table-rebuild silently drops the append-only triggers.
**Why:** Documented in `0001`, `0004`, `0017`, and Phase 25 memory — batch = recreate table = lose triggers.
**How to avoid:** Continue the native-`op.add_column` rule on ledger tables; the CI parity test (trigger-exists + UPDATE/DELETE-rejected) is the regression backstop on both dialects.

### Pitfall 3: PRAGMA statements error on PostgreSQL
**What goes wrong:** The `connect`-event listener runs `PRAGMA journal_mode=WAL` on a PG connection → error.
**Why:** `app/db.py:51` registers the listener unconditionally inside `build_engine`.
**How to avoid:** Register the listener only when `engine.dialect.name == "sqlite"` (Pattern 3). PG needs none of WAL/foreign_keys/busy_timeout (FKs are enforced by default; WAL is SQLite-specific).

### Pitfall 4: `VACUUM INTO` backup path assumes SQLite
**What goes wrong:** If backup ever runs against a PG engine it fails (`VACUUM INTO` is SQLite-only).
**Why:** `app/services/backup.py:44`.
**How to avoid:** Backup is a **client-only** feature (D-08/D-09); the server does not back up via this path. No change required this phase, but do not wire `startup_backup`/`create_backup` to a PG engine. Note for the planner: this is explicitly out of scope for schema parity but should be called out so a future server deployment does not regress.

### Pitfall 5: `render_as_batch=True` left on for PG (low risk, still fix)
**What goes wrong:** In principle batch rendering can wrap ALTERs oddly on non-SQLite.
**Why:** `env.py` sets it unconditionally.
**Reality:** Since **no** migration uses `op.batch_alter_table`, it is currently a no-op at runtime on the existing chain — but gate it to `dialect == "sqlite"` anyway so future autogenerated ALTERs on PG are native. Confidence that it is currently harmless: HIGH; gating it is cleanliness + future-proofing.

### Pitfall 6: ASCII `func.lower(Product.code)` divergence if codes ever hold Cyrillic
**What goes wrong:** `func.lower(Product.code)` (`catalog.py:433,436`) folds ASCII on SQLite but Unicode on PG — divergent *only* for non-ASCII codes.
**Why:** Product codes are ASCII Oriflame codes (design assumption A1 in `catalog.py`).
**How to avoid:** No action; note the assumption. If codes ever become Cyrillic, move code folding to Python like the name search. `[ASSUMED — codes are ASCII; carried over from existing code comment]`

## Code Examples

### Empty-PG migration run + schema/enforcement assertion (CI shape)
```python
# Source: pattern for a new tests/test_pg_parity.py (pytest, skipped unless DATABASE_URL is PG)
import os, pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command

pg_url = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not pg_url.startswith("postgresql"), reason="PG parity test — set TEST_DATABASE_URL"
)

def test_full_history_applies_and_ledger_is_append_only():
    engine = create_engine(pg_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", pg_url)
    command.upgrade(cfg, "head")                      # SRV-01: whole chain on empty PG
    with engine.begin() as c:
        c.execute(text("INSERT INTO products (id, name, quantity, created_at, updated_at) "
                       "VALUES ('p1','Тест',0,'2026-07-18T00:00:00+00:00','2026-07-18T00:00:00+00:00')"))
        c.execute(text("INSERT INTO operations (id,type,product_id,qty_delta,device_id,seq,created_at,created_by) "
                       "VALUES ('o1','receipt','p1',1,'d1',1,'2026-07-18T00:00:00+00:00','seed')"))
    for sql in ("UPDATE operations SET qty_delta=99 WHERE id='o1'",
                "DELETE FROM operations WHERE id='o1'"):
        with pytest.raises(Exception, match="append-only"):   # SRV-02
            with engine.begin() as c:
                c.execute(text(sql))
```

### Cyrillic search parity (no code change — why it already holds)
```python
# app/services/catalog.py:429-441 (existing) — folding in Python, LIKE on shadow col
q_lc = q.strip().lower()                                # Python folds Cyrillic
stmt = base.where(code_prefix | Product.name_lc.contains(q_lc, autoescape=True))
# .contains() → name_lc LIKE '%q_lc%'. name_lc is pre-lowered in Python at write
# time (catalog.py:119,257). lowercase-vs-lowercase LIKE is identical on SQLite & PG.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| psycopg2 (`postgresql+psycopg2://`) | psycopg v3 (`postgresql+psycopg://`) | psycopg 3 GA (2021), first-class in SQLAlchemy 2.0 | Use v3 for a new server target; `[binary]` extra avoids a C toolchain. |
| Separate SQLite/PG migration trees | One history, `op.get_bind().dialect.name` branch | Standard Alembic practice | Satisfies SRV-01 "single migration history". |

**Deprecated/outdated:** psycopg2 for greenfield PG work — maintenance mode; not needed here.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Keep two separate PG triggers (`_no_update`/`_no_delete`) instead of one `UPDATE OR DELETE` trigger, for name parity + Phase 28 relaxation. | Pattern 2 | Low — cosmetic; a combined trigger also satisfies SRV-02 but complicates Phase 28's UPDATE-only relaxation. |
| A2 | Pin an explicit PG major in CI (e.g. `postgres:17`). | Standard Stack | Low — any modern major supports the trigger DDL; unpinned `postgres` floats. |
| A3 | Product codes are ASCII, so `func.lower(code)` folds identically. | Pitfall 6 | Medium if a Cyrillic code is ever entered — search rank on that code could diverge; carried over from existing `catalog.py` A1 comment. |
| A4 | Retrofitting a PG branch into frozen migrations 0001/0013 is consistent with WR-06 (SQLite replay output unchanged). | Anti-Patterns / Pitfall 1 | Medium — the project treats migrations as frozen; needs an explicit decision that "add a dialect branch, SQLite path unchanged" is permitted. **Confirm in discuss-phase.** |
| A5 | Backup (`VACUUM INTO`) stays SQLite/client-only and is out of scope. | Pitfall 4 | Low — server has no file-backup requirement in this phase. |
| A6 | CI is GitHub Actions (repo has a GitHub `origin` remote) rather than another CI. | Validation Architecture | Low — remote is `github.com/viktorplus/myorishop`; if the user prefers local-docker-only, the parity test still runs, just not "in CI". |

## Open Questions

1. **WR-06 vs. editing 0001/0013 (A4).**
   - What we know: The single-history requirement (SRV-01) and the phase brief both mandate a dialect branch inside one migration; on empty PG the chain fails at 0001 unless 0001 itself branches.
   - What's unclear: Whether the project owner accepts modifying the frozen migrations (SQLite output provably unchanged).
   - Recommendation: Adopt in-place dialect branch; the SQLite emitted DDL is byte-for-behavior identical, so deterministic replay on existing SQLite DBs is preserved. Raise explicitly in discuss-phase.

2. **Where the PG URL comes from.**
   - What we know: `env.py` and `app/db.py` both hardcode `sqlite:///`.
   - What's unclear: Config surface — new `settings.database_url` vs. reuse `db_path` + a scheme flag.
   - Recommendation: Add `settings.database_url` (default derived from `db_path`), override via `.env`; both engine and `env.py` read it. Single source of truth.

3. **PG major version to standardize on.**
   - Recommendation: Pin `postgres:17` in CI and document it as the server target; revisit at Phase 28 (hosting).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| psycopg (v3) | PG engine + CI parity test | ✗ (not yet a dependency) | — (3.3.4 on PyPI) | `uv add "psycopg[binary]"` — no fallback; required |
| PostgreSQL server | SRV-01/02 parity proof | ✗ locally (Windows dev host) | — | CI `services: postgres`; local dev can `docker run -e POSTGRES_PASSWORD=… -p 5432:5432 postgres:17` |
| GitHub Actions | "in CI" success wording | ✓ (repo has GitHub `origin`) | — | Local docker + `TEST_DATABASE_URL` marker if CI declined |
| `.github/workflows/` | CI job | ✗ (directory absent) | — | Must be created this phase |
| Docker (local, Windows) | Optional local PG for dev | ? unverified | — | Not blocking — CI is the real target |

**Missing dependencies with no fallback:**
- `psycopg` (must be added), a Postgres instance in CI (must be provisioned via `services:`).

**Missing dependencies with fallback:**
- Local PG on Windows — fall back to CI-only, or a throwaway `docker run postgres:17` for local iteration.

## Validation Architecture

> nyquist_validation is enabled (`.planning/config.json`). This phase's proof *is* validation, so this section is central.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* `[VERIFIED: pyproject.toml]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_pg_parity.py -x` (new file) |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SRV-01 | Full Alembic history applies to empty PG, producing the SQLite schema | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_full_history_applies -x` | ❌ Wave 0 |
| SRV-01 | Cyrillic case-insensitive search returns identical rows on PG and SQLite | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_cyrillic_search_parity -x` | ❌ Wave 0 |
| SRV-02 | UPDATE on `operations` rejected at PG | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_operations_update_rejected -x` | ❌ Wave 0 |
| SRV-02 | DELETE on `operations` rejected at PG | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_operations_delete_rejected -x` | ❌ Wave 0 |
| SRV-02 | UPDATE + DELETE on `cash_movements` rejected at PG | integration (PG) | `uv run pytest tests/test_pg_parity.py::test_cash_movements_immutable -x` | ❌ Wave 0 |
| SRV-02 (regression) | SQLite append-only still holds after trigger-DDL branch edit | unit (SQLite) | `uv run pytest tests/test_pragmas.py -x` | ✅ exists |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_pragmas.py tests/test_ledger.py -x` (SQLite triggers unbroken) + `ruff check`.
- **Per wave merge:** full `uv run pytest` on SQLite; PG parity test on CI (or local docker if available).
- **Phase gate:** CI job green — `alembic upgrade head` on empty PG + all `test_pg_parity.py` assertions pass; full SQLite suite green.

### Wave 0 Gaps
- [ ] `tests/test_pg_parity.py` — SRV-01/SRV-02 assertions; skipped unless `TEST_DATABASE_URL` points at PG.
- [ ] `.github/workflows/ci.yml` (or `pg-parity.yml`) — `services: postgres` job that installs deps (`uv sync`), sets `TEST_DATABASE_URL=postgresql+psycopg://…@localhost:5432/…`, runs the PG parity test, and also runs the full SQLite suite.
- [ ] Dependency: `uv add "psycopg[binary]"`.
- [ ] PG-equivalent trigger DDL constant (mirror of `APPEND_ONLY_TRIGGERS`) for any PG fixture, or rely on `alembic upgrade head` in the PG fixture (preferred — proves the real history).
- [ ] Optional: a shared PG fixture in `conftest.py` (or a new `tests/conftest_pg.py`) that runs migrations once per session against the CI service DB.

*Existing SQLite infrastructure (`conftest.py` fixtures, `test_pragmas.py`, `test_ledger.py`) already covers the SQLite side of parity — no changes beyond confirming they stay green after the migration edits.*

### GitHub Actions service snippet (verified shape)
```yaml
# Source: GitHub Actions "Creating PostgreSQL service containers" docs
services:
  postgres:
    image: postgres:17
    env:
      POSTGRES_PASSWORD: postgres
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```
`[CITED: docs.github.com — Creating PostgreSQL service containers; pg_isready health check is the recommended readiness gate]`

## Security Domain

> security_enforcement enabled. This phase is DB-portability infra; the security-relevant surface is the **integrity guarantee** (append-only ledger) and DB access, not new auth/input paths.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No new auth surface (Phase 25 owns auth). |
| V3 Session Management | no | Unchanged. |
| V4 Access Control | no | Unchanged; role gating stays in the app. |
| V5 Input Validation | partial | Migration/CI SQL uses **bound parameters** already (`sa.text(... :id ...)`); the PG parity test must likewise never f-string user data into SQL. |
| V6 Cryptography | no | No crypto changes. |
| V10 / Data Integrity (append-only ledger) | yes | DB-level triggers on `operations`/`cash_movements` — the SRV-02 control; must be equivalent on PG. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Ledger tampering (post-hoc UPDATE/DELETE of financial/stock rows) | Tampering / Repudiation | `BEFORE UPDATE/DELETE` triggers raising on both dialects (SRV-02) — enforced at DB, caller-independent. |
| SQL injection in migration/test DDL | Tampering | Bound parameters (`op.execute` with SQLAlchemy `text()` + params); no string interpolation of external input. `[VERIFIED: existing migrations use `sa.text(":id")` bind params]` |
| CI secret leakage (DB creds) | Info Disclosure | CI Postgres is throwaway with a non-secret password (`POSTGRES_PASSWORD: postgres`); no production secret in the workflow. |

## Sources

### Primary (HIGH confidence)
- Repo files (VERIFIED by direct read): `app/db.py`, `app/config.py`, `app/models.py`, `alembic/env.py`, `alembic/versions/0001_initial_schema.py`, `0002_catalog_dictionary.py`, `0012_dictionary_name_lc.py`, `0013_cash_movements.py`, `0017_users_and_author_id.py`, `app/services/catalog.py`, `app/services/customers.py`, `app/services/backup.py`, `tests/conftest.py`, `tests/test_pragmas.py`, `pyproject.toml`.
- `docs.sqlalchemy.org/en/20/dialects/postgresql.html` — psycopg v3 dialect, URL `postgresql+psycopg://` (CITED).
- `docs.github.com` — Creating PostgreSQL service containers; `pg_isready` health check (CITED).
- `pip index versions psycopg` → 3.3.4 latest (VERIFIED, 2026-07-18).

### Secondary (MEDIUM confidence)
- Alembic `op.get_bind().dialect.name` dialect-branch pattern — standard Alembic practice (training knowledge, well-established).

### Tertiary (LOW confidence)
- Exact PG major to pin (`postgres:17`) — recommendation only (A2).

## Metadata

**Confidence breakdown:**
- SQLite-coupled surface inventory: HIGH — every file read directly with line numbers.
- Portability of models/queries: HIGH — verified generic types, dual-dialect index, Python-folded search.
- Trigger parity approach: HIGH (SQLite side verified) / MEDIUM (PG PL/pgSQL DDL is standard but not executed this session).
- CI / psycopg: HIGH — driver + service YAML verified against official docs; version verified on PyPI.

**Research date:** 2026-07-18
**Valid until:** 2026-08-17 (stable stack; re-check psycopg/PG major only if the milestone slips materially)
