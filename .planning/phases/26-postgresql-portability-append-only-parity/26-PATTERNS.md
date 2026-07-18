# Phase 26: PostgreSQL Portability & Append-Only Parity - Pattern Map

**Mapped:** 2026-07-18
**Files analyzed:** 9 (7 modified, 2 created)
**Analogs found:** 9 / 9 (edit-in-place files are their own analog)

> This phase is **edit-heavy on existing files**. For every modified file the "analog" is the current file itself — the excerpts below capture the exact pattern that must be **preserved/branched** (SQLite output byte-for-behavior unchanged; PG branch added alongside). Two files are genuinely new (`tests/test_pg_parity.py`, `.github/workflows/*.yml`) and borrow their shape from existing tests + RESEARCH snippets.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `alembic/versions/0001_initial_schema.py` (modify) | migration | transform (DDL) | itself (lines 38-49, 94-96, 124-126) | edit-in-place |
| `alembic/versions/0013_cash_movements.py` (modify) | migration | transform (DDL) | itself (lines 37-48, 80-81, 84-86) | edit-in-place |
| `alembic/env.py` (modify) | config | transform (DDL) | itself (lines 19, 48, 72) | edit-in-place |
| `app/db.py` (modify) | config/engine | request-response (connect) | itself (lines 46-63; constant 22-43) | edit-in-place |
| `app/config.py` (modify) | config | — | itself (lines 22, 45-59) | edit-in-place |
| `pyproject.toml` (modify) | config | — | itself (lines 5-16) | edit-in-place |
| `tests/test_pg_parity.py` (create) | test | integration (PG) | `tests/test_pragmas.py` + RESEARCH §Code Examples | role-match |
| `.github/workflows/*.yml` (create) | config (CI) | — | none in repo (`.github/` absent) — RESEARCH §Validation Architecture YAML | no analog |
| `tests/conftest.py` (optional PG fixture) | test | integration (PG) | itself (lines 22-32 `engine` fixture) | edit-in-place |

## Pattern Assignments

### `alembic/versions/0001_initial_schema.py` (migration, DDL transform)

**Analog:** itself — this is the migration that crashes FIRST on empty PG (Pitfall 1).

**Current frozen SQLite trigger DDL constant** (lines 38-49) — KEEP the SQLite path emitting exactly this; add a PG branch alongside:
```python
_APPEND_ONLY_TRIGGERS: tuple[str, str] = (
    """
    CREATE TRIGGER operations_no_update
    BEFORE UPDATE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
    """
    CREATE TRIGGER operations_no_delete
    BEFORE DELETE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
)
```

**Current unconditional emit** (lines 94-96) — this is the exact spot to insert the `op.get_bind().dialect.name` branch:
```python
    # FND-01: append-only enforcement at the DATABASE level (frozen DDL copy).
    for stmt in _APPEND_ONLY_TRIGGERS:
        op.execute(stmt)
```

**Current downgrade** (lines 124-126) — `DROP TRIGGER IF EXISTS` works on both dialects, but the PG trigger function needs its own `DROP FUNCTION IF EXISTS operations_append_only()` added to the PG branch:
```python
def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS operations_no_update")
    op.execute("DROP TRIGGER IF EXISTS operations_no_delete")
    ...
```

**PG-equivalent DDL to add** (from RESEARCH Pattern 1, keep trigger NAMES identical for parity with `test_pragmas.py`):
```python
_PG_OPERATIONS_DDL = (
    """CREATE OR REPLACE FUNCTION operations_append_only()
       RETURNS trigger LANGUAGE plpgsql AS $$
       BEGIN RAISE EXCEPTION 'operations ledger is append-only'; END; $$""",
    """CREATE TRIGGER operations_no_update BEFORE UPDATE ON operations
       FOR EACH ROW EXECUTE FUNCTION operations_append_only()""",
    """CREATE TRIGGER operations_no_delete BEFORE DELETE ON operations
       FOR EACH ROW EXECUTE FUNCTION operations_append_only()""",
)
```

**Anti-pattern (from RESEARCH):** Do NOT change the SQLite-emitted statements (WR-06 deterministic replay). Do NOT append a new "fix triggers" migration — the chain dies at `0001` on PG before any later revision runs. The branch MUST live inside `0001.upgrade()`.

---

### `alembic/versions/0013_cash_movements.py` (migration, DDL transform)

**Analog:** itself + the `0001` pattern applied identically.

**Current frozen SQLite trigger DDL** (lines 37-48) and unconditional emit (lines 80-81):
```python
_CASH_APPEND_ONLY_TRIGGERS: tuple[str, str] = (
    """
    CREATE TRIGGER cash_movements_no_update
    BEFORE UPDATE ON cash_movements
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
    """
    CREATE TRIGGER cash_movements_no_delete
    BEFORE DELETE ON cash_movements
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
)
# ...
    for stmt in _CASH_APPEND_ONLY_TRIGGERS:
        op.execute(stmt)
```

**Downgrade** (lines 84-86): mirror the `0001` treatment — add `DROP FUNCTION IF EXISTS cash_movements_append_only()` in the PG branch. Message string is `'cash ledger is append-only'` (note: different wording than operations — preserve exactly for the `match="append-only"` test assertions, both contain the substring `append-only`).

---

### `alembic/env.py` (config, DDL transform)

**Analog:** itself. Three coupling points.

**Hardcoded SQLite URL** (line 19) — replace with a config-driven URL (RESEARCH OQ2 recommendation: add `settings.database_url`, default derived from `db_path`):
```python
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.db_path}")
```

**Unconditional `render_as_batch=True`** — appears TWICE, offline (line 48) and online (line 72):
```python
# offline (line 43-49):
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-safe (move-and-copy) migrations
    )
# online (line 69-73):
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite-safe (move-and-copy) migrations
        )
```
Gate both: `render_as_batch = <dialect> == "sqlite"`. Offline mode has no connection — derive dialect from the URL scheme; online mode: `connection.dialect.name == "sqlite"` (Pattern 3 / Pitfall 5, currently harmless but gate for cleanliness).

**Note:** line 12 `Path(settings.db_path).parent.mkdir(...)` is SQLite-file-only prep — guard so it does not run (or is harmless) when the URL is `postgresql+psycopg://`.

---

### `app/db.py` (config/engine, connect request-response)

**Analog:** itself.

**Current engine builder** (lines 46-63) — IMPORTANT: signature takes `db_path: str`, NOT a URL. Planner must decide: change signature to `build_engine(url: str)` (RESEARCH Pattern 3) and update the single caller on line 66 (`engine = build_engine(settings.db_path)`) plus `tests/conftest.py:25`:
```python
def build_engine(db_path: str) -> Engine:
    """Create a sync SQLite engine with per-connection PRAGMAs (D-14)."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        # sqlite3 ignores PRAGMA foreign_keys while autocommit=False.
        autocommit = dbapi_connection.autocommit
        dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()
        dbapi_connection.autocommit = autocommit

    return engine
```

**Branch to apply** (RESEARCH Pattern 3 / Pitfall 3): create the engine from a URL; register the `connect` listener (WAL/foreign_keys/busy_timeout PRAGMAs) **only** when `engine.dialect.name == "sqlite"` — PRAGMA statements error on PG. The `Path(...).mkdir` parent-dir creation is also SQLite-only (guard it).

**Callers to update** if signature changes: `app/db.py:66` and `tests/conftest.py:25`. Keeping a `db_path`-taking wrapper that internally builds the SQLite URL is a lower-blast-radius alternative — planner's call.

**`APPEND_ONLY_TRIGGERS` constant** (lines 22-43): used by the test-fixture path only. RESEARCH says leave it for the SQLite suite; the PG parity test proves triggers via real `alembic upgrade head`, not this constant.

---

### `app/config.py` (config)

**Analog:** itself (existing `db_path` field, line 22, and `model_validator`, lines 45-59).

**Current field pattern** (line 22) — add a sibling `database_url` field following the same `.env`-overridable style (`SettingsConfigDict(env_file=".env")` is already configured on line 20):
```python
    db_path: str = "data/myorishop.db"
```
RESEARCH OQ2 recommendation: `database_url` default derived from `db_path` (e.g. computed in the existing `_resolve_local_identity` `@model_validator(mode="after")` on lines 45-59, or a new validator) so a `.env` `DATABASE_URL=postgresql+psycopg://…` wins and both `env.py` and `app/db.py` read one source of truth. Preserve the "env value left untouched, only default replaced" idiom already used for `secret_key`/`device_id`.

---

### `pyproject.toml` (config)

**Analog:** itself (lines 5-16 `dependencies`, minor-pin style `==X.Y.*`).

Add `psycopg` to `[project].dependencies` matching the existing pin style:
```python
dependencies = [
    "alembic==1.18.*",
    ...
    "sqlalchemy==2.0.*",
    "psycopg[binary]==3.3.*",   # ADD — PG driver, prebuilt libpq wheels (RESEARCH Standard Stack)
    ...
]
```
Install via `uv add "psycopg[binary]"`. Version verified 3.3.4 latest (RESEARCH). `[binary]` extra avoids a local C toolchain in CI/dev.

---

### `tests/test_pg_parity.py` (test, PG integration — NEW)

**Analog:** `tests/test_pragmas.py` (assertion structure + trigger-name frozenset) and RESEARCH §Code Examples.

**Trigger-name assertion pattern to reuse** (`test_pragmas.py:11-18, 42-44`):
```python
APPEND_ONLY_TRIGGER_NAMES = frozenset({
    "operations_no_update", "operations_no_delete",
    "cash_movements_no_update", "cash_movements_no_delete",
})
```

**Append-only rejection assertion pattern** (`test_pragmas.py:64-68`) — note SQLite raises `IntegrityError`; on PG the driver raises a different exception, so the parity test matches on the message substring per RESEARCH:
```python
with pytest.raises(IntegrityError, match="append-only"):   # SQLite version
    with engine.begin() as connection:
        connection.exec_driver_sql("UPDATE operations SET ... WHERE id = 'op-1'")
```

**New PG test shape** (RESEARCH §Code Examples, verbatim guidance): skip unless `TEST_DATABASE_URL` is PG; run `command.upgrade(cfg, "head")` against empty PG (SRV-01); INSERT a product + operation, then assert UPDATE and DELETE both `pytest.raises(Exception, match="append-only")` on `operations` and `cash_movements` (SRV-02). Also add `test_cyrillic_search_parity` (SRV-01). Use bound params / no f-string interpolation of external data (Security V5).

Test map (RESEARCH §Phase Requirements → Test Map): `test_full_history_applies`, `test_cyrillic_search_parity`, `test_operations_update_rejected`, `test_operations_delete_rejected`, `test_cash_movements_immutable`.

---

### `.github/workflows/*.yml` (config CI — NEW, no repo analog)

**Analog:** none — `.github/` does not exist. Use RESEARCH §Validation Architecture verified YAML.

`services: postgres` (image `postgres:17`, `POSTGRES_PASSWORD: postgres`, port 5432, `pg_isready` health check). Job steps: `uv sync`, set `TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/postgres`, run `uv run pytest tests/test_pg_parity.py`, and also run the full SQLite suite `uv run pytest`. Non-secret throwaway password only (Security: no production secret in workflow).

---

## Shared Patterns

### Dialect branch hook (migrations)
**Source:** RESEARCH Pattern 1 — `op.get_bind().dialect.name`
**Apply to:** `0001_initial_schema.py`, `0013_cash_movements.py`
```python
if op.get_bind().dialect.name == "postgresql":
    for stmt in _PG_...DDL: op.execute(stmt)
else:  # sqlite — output unchanged from today
    for stmt in _..._TRIGGERS: op.execute(stmt)
```
Keep trigger NAMES (`*_no_update` / `*_no_delete`) identical across dialects so `tests/test_pragmas.py` name assertions and Phase 28's relaxation target the same names.

### Dialect branch hook (engine/env)
**Source:** RESEARCH Pattern 3 — `engine.dialect.name` / `connection.dialect.name`
**Apply to:** `app/db.py` (connect-listener + mkdir), `alembic/env.py` (`render_as_batch`, mkdir)
Register SQLite-only side effects (PRAGMAs, parent-dir mkdir, batch rendering) only when dialect is `sqlite`.

### Single config source of truth for the DB URL
**Source:** RESEARCH OQ2 — new `settings.database_url`
**Apply to:** `app/config.py` (define), `alembic/env.py` (read), `app/db.py` (read)
Default derived from `db_path` → `sqlite:///…`; `.env` `DATABASE_URL` overrides with `postgresql+psycopg://…`. Both migrations and the app engine read the same setting so they never diverge.

### Append-only enforcement lives in the DB
**Source:** `0001`/`0013` triggers, `app/db.py:22-43`
**Apply to:** all ledger-table work (`operations`, `cash_movements`)
Hard `RAISE(ABORT …)` (SQLite) / `RAISE EXCEPTION` (PG) — never app-layer checks (SRV-02). Never `op.batch_alter_table` on ledger tables (batch = rebuild = drops triggers; Pitfall 2).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.github/workflows/*.yml` | config (CI) | — | `.github/` absent — no CI exists in repo yet; use RESEARCH's verified GitHub Actions `services: postgres` YAML |

## Metadata

**Analog search scope:** `app/db.py`, `app/config.py`, `alembic/env.py`, `alembic/versions/0001_*`, `alembic/versions/0013_*`, `tests/conftest.py`, `tests/test_pragmas.py`, `app/services/catalog.py`, `pyproject.toml`
**Files scanned:** 9 (all directly read with line numbers)
**Pattern extraction date:** 2026-07-18
