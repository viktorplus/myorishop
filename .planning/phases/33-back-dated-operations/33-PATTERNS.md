# Phase 33: Back-Dated Operations — Pattern Map

**Mapped:** 2026-09-04
**Repo state:** `fba02f2`, branch `main`, alembic head `0026`
**Files analyzed:** 4 genuinely new + ~40 modified (existing idioms)
**Analogs found:** 4/4 new files, 7/7 service-layer changes, 4/4 template shapes

> **What this document is.** Every file this phase touches except four ALREADY EXISTS and
> already has a shipped idiom. `33-CONTEXT.md` and `33-RESEARCH.md` name the analogs by
> `file:line` but do not extract the code. This file extracts it, verbatim, so the executor
> can copy a shape without re-opening six files.
>
> **What this document is NOT.** It proposes no design change, no alternative, no refactor.
> Where an excerpt is an ANTI-pattern it is labelled loudly (§D).

---

## File Classification

### A. Genuinely new files (4)

| New file | Role | Data flow | Closest analog | Match |
|---|---|---|---|---|
| `alembic/versions/0027_*.py` | migration | schema + batch transform | `alembic/versions/0026_cash_movements_trigger_guards_currency.py` (trigger rewrite), `0024_cash_movement_currency.py` (backfill shape; **its `downgrade()` is an anti-pattern**), `0018_sync_cursor_trigger_relaxation.py` (first occurrence of the ritual) | exact |
| `tests/test_migrations.py` | test | file-I/O + schema introspection | `tests/test_append_only_cursor.py` (the two tripwires + the frozenset constants); `tests/conftest.py::engine` (the fixture the new one must sit BESIDE) | role-match |
| `tests/test_business_date.py` | test | CRUD + render assertions | `tests/test_core.py:108-150` (tz fixture idiom); `tests/test_receipts.py:441-445` (markup-assertion idiom) | role-match |
| `tests/test_sync_schema_gate.py` | test | request-response (integration) | `tests/test_sync_api.py:115-122` (push-with-token idiom); `tests/test_merge.py:32-67` (`record_line` / `build_ndjson`, incl. the `schema_version` header key); `tests/conftest.py:262+` (`sync_driver_pair`) | exact |

### B. Modified files — service layer (7 change classes)

| Change | Role | Data flow | Analog | Match |
|---|---|---|---|---|
| `business_date_bounds` in `app/core.py` | utility | transform | `app/core.py:108-126 local_day_bounds_utc` | exact |
| `business_date_expr` | utility | transform | `app/services/reports.py:21-38 operation_currency_clause` | role-match |
| `parse_op_date` + 2 RU constants | service | validation | `app/services/receipts.py:43,46-66 parse_optional_expiry` | exact |
| `push_schema_ok` | service | request-response | `app/services/sync.py:225-235 current_schema_version` (sibling), `app/services/offline.py:61-71 schema_version_ok` (**read-only**, D-02) | exact |
| The 409 route gate | route | request-response | `app/routes/offline.py:232-243` + `app/routes/sync.py:51-54` | exact |
| `format_sync_message` + 1 branch | service | transform | `app/services/sync_client.py:186-209`; branch point `:377-379` | exact |
| `record_operation` / `record_cash_movement` kwarg | service | CRUD | `app/services/ledger.py:37-49`, `app/services/finance.py:48-57` | exact |

### C. Modified files — templates (3 representative shapes + the filter select)

| Change | Analog |
|---|---|
| desktop ledger form + inline error | `app/templates/partials/receipt_form.html:23,32-44` |
| mobile SHELL wizard vs FINAL-STEP form (the D-11 split) | `mobile_pages/receipts.html:12-16` vs `mobile_partials/corrections_step_value.html:13-17,21-46` |
| «Когда» cell, both layouts + muted second line | `partials/history_rows.html:125`, `:240`, `:132-147`; `mobile_partials/history_cards.html:31` |
| the fourth `.filter-bar` select | `partials/history_rows.html:27-35` |

---

## Pattern Assignments

### A1. `alembic/versions/0027_*.py` (migration, schema + batch transform)

**Analog 1 — the dual-dialect trigger-rewrite ritual: `alembic/versions/0026_cash_movements_trigger_guards_currency.py`**

Module preamble (`0026:1-40`) — note the four things it always states: the lockstep rule, why the old migration is NOT edited retroactively, the per-dialect null-safety, and WR-06:

```python
"""cash_movements_no_update: guard the new currency column (CUR-02)

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-10

LOCKSTEP RULE fix: migration 0024 added `cash_movements.currency` but did not
update the `cash_movements_no_update` append-only trigger created by 0018 to
guard it ...

Migration 0018 itself is NOT edited retroactively (already-applied
migrations are historical fact) — this migration re-applies its exact
DROP/CREATE technique with `currency` added to the WHEN clause. ...
`app.db.APPEND_ONLY_TRIGGERS` ... and
`tests/test_append_only_cursor.py::IMMUTABLE_CASH_COLUMNS` move together
with this file in the same commit (LOCKSTEP RULE, per 0018's docstring).

Null-safety per dialect, same as 0018: SQLite uses `IS NOT`; PostgreSQL uses
`IS DISTINCT FROM`. ...

Immutability rule (WR-06): this file never imports application modules —
stdlib + sqlalchemy + alembic.op only. All DDL below is a literal string
constant; no value is ever interpolated into SQL.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None
```

`_SQLITE_DDL` — `IS NOT` branch (`0026:42-58`). **Copy the DROP-then-CREATE tuple shape exactly**:

```python
_SQLITE_DDL: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS cash_movements_no_update",
    """
    CREATE TRIGGER cash_movements_no_update
    BEFORE UPDATE ON cash_movements
    FOR EACH ROW WHEN
         NEW.id           IS NOT OLD.id
      OR NEW.category     IS NOT OLD.category
      OR NEW.amount_cents IS NOT OLD.amount_cents
      OR NEW.currency     IS NOT OLD.currency
      OR NEW.note         IS NOT OLD.note
      OR NEW.sale_id      IS NOT OLD.sale_id
      OR NEW.author_id    IS NOT OLD.author_id
      OR NEW.device_id    IS NOT OLD.device_id
      OR NEW.seq          IS NOT OLD.seq
      OR NEW.created_at   IS NOT OLD.created_at
      OR NEW.created_by   IS NOT OLD.created_by
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
)
```

`_PG_DDL` — `IS DISTINCT FROM` branch (`0026:60-76`). Note: PG re-uses the PL/pgSQL function created by `0013`, never re-creates it; and the DROP carries `ON cash_movements`:

```python
_PG_DDL: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements",
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       FOR EACH ROW WHEN (
            NEW.id           IS DISTINCT FROM OLD.id
         OR NEW.category     IS DISTINCT FROM OLD.category
         OR NEW.amount_cents IS DISTINCT FROM OLD.amount_cents
         OR NEW.currency     IS DISTINCT FROM OLD.currency
         OR NEW.note         IS DISTINCT FROM OLD.note
         OR NEW.sale_id      IS DISTINCT FROM OLD.sale_id
         OR NEW.author_id    IS DISTINCT FROM OLD.author_id
         OR NEW.device_id    IS DISTINCT FROM OLD.device_id
         OR NEW.seq          IS DISTINCT FROM OLD.seq
         OR NEW.created_at   IS DISTINCT FROM OLD.created_at
         OR NEW.created_by   IS DISTINCT FROM OLD.created_by
       ) EXECUTE FUNCTION cash_movements_append_only()""",
)
```

Both `downgrade()` halves — `0026:78-116` declares a *separate pair* of constants holding the
**pre-`0026` enumeration** (`currency` absent), with the section comment kept:

```python
# --- downgrade: restore the 0018/0024-era guard (no currency column) -------

_SQLITE_DOWNGRADE_DDL: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS cash_movements_no_update",
    """
    CREATE TRIGGER cash_movements_no_update
    BEFORE UPDATE ON cash_movements
    FOR EACH ROW WHEN
         NEW.id           IS NOT OLD.id
      OR NEW.category     IS NOT OLD.category
      ...           (currency omitted)
    BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END
    """,
)

_PG_DOWNGRADE_DDL: tuple[str, ...] = (
    "DROP TRIGGER IF EXISTS cash_movements_no_update ON cash_movements",
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       FOR EACH ROW WHEN (
            NEW.id           IS DISTINCT FROM OLD.id
         ...           (currency omitted)
       ) EXECUTE FUNCTION cash_movements_append_only()""",
)
```

The dialect dispatch (`0026:119-132`) — **the exact `if/else` to copy**, including the `# sqlite`
comment on the else:

```python
def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_DDL:
            op.execute(stmt)
    else:  # sqlite
        for stmt in _SQLITE_DDL:
            op.execute(stmt)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for stmt in _PG_DOWNGRADE_DDL:
            op.execute(stmt)
    else:  # sqlite
        for stmt in _SQLITE_DOWNGRADE_DDL:
            op.execute(stmt)
```

**Analog 2 — the same ritual's first occurrence: `alembic/versions/0018_sync_cursor_trigger_relaxation.py`**

Structure is identical (`_SQLITE_DDL` `:68`, `_PG_DDL` `:110`, `_SQLITE_DOWNGRADE_DDL` `:149`,
`_PG_DOWNGRADE_DDL` `:164`, `upgrade()` `:174`, `downgrade()` `:183`). Two facts in its docstring
that `0027` must carry forward because `operations_no_update` is being rewritten this time:

```
Value-based `WHEN` rather than `UPDATE OF`: `UPDATE OF col` fires on the
MENTION of a column in the SET clause, so it would reject the harmless
no-op `SET synced_at = ..., qty_delta = qty_delta` ...            (0018:25-29)

PostgreSQL `json` trap: `operations.payload` is `sa.JSON()`, which maps to
PostgreSQL's `json` type, and `json` has NO equality operator — an
uncast `NEW.payload IS DISTINCT FROM OLD.payload` fails with
`operator does not exist: json = json`. The PG guard therefore compares
`NEW.payload::text IS DISTINCT FROM OLD.payload::text`.                (0018:35-40)
```

> ⚠ **The `payload::text` cast is live for `0027`.** `0026` only touched `cash_movements`, which
> has no JSON column. `0027` rewrites `operations_no_update`, so its `_PG_DDL` **must** carry
> `NEW.payload::text IS DISTINCT FROM OLD.payload::text` — copy that line from `0018:110+`, not
> from `0026`.

**Analog 3 — the backfill shape: `alembic/versions/0024_cash_movement_currency.py:30,43-47`**

Copy the *migration-local literal constant* (never an app import — WR-06) and the explicit-intent
`op.execute` backfill:

```python
_DEFAULT_CURRENCY = "RUB"
...
    # Explicit backfill: server_default covers the ALTER itself, but state this
    # outright so the intent survives a future default change.
    op.execute(
        f"UPDATE cash_movements SET currency = '{_DEFAULT_CURRENCY}' WHERE currency IS NULL"
    )
```

Per `33-RESEARCH.md` Pattern 3, `0027`'s backfill is **not** a bare SQL `UPDATE`: it is a Python
loop converting `created_at` through `ZoneInfo(<tz literal declared in this file>)`. What `0024`
supplies is the *constant-declaration* convention (`_DEFAULT_CURRENCY = "RUB"` instead of
`from app.core import DEFAULT_CURRENCY`) — that is the shape `0027`'s `display_tz` literal copies.
`0024`'s `upgrade()` also demonstrates why the shipped `upgrade()` side survived batch mode: its
`server_default` is the **plain string** `"RUB"`, not a `ClauseElement`.

---

### A2. `tests/test_migrations.py` (test, schema introspection)

**Analog — `tests/test_append_only_cursor.py`.**

The frozenset constants (`:40-73`) — these are the two the phase EXTENDS (`business_date` /
`reverses_operation_id` into the operation set, `business_date` / `reverses_movement_id` into the
cash set). Header comment at `:37-38` is load-bearing:

```python
# --- The column enumeration the triggers claim to cover --------------------
# Must equal each model's columns MINUS the sync cursor `synced_at`.

IMMUTABLE_OPERATION_COLUMNS: frozenset[str] = frozenset(
    {
        "id", "type", "product_id", "qty_delta", "unit_cost_cents",
        "unit_price_cents", "payload", "sale_id", "batch_id", "author_id",
        "device_id", "seq", "created_at", "created_by",
    }
)

IMMUTABLE_CASH_COLUMNS: frozenset[str] = frozenset(
    {
        "id", "category", "amount_cents", "currency", "note", "sale_id",
        "author_id", "device_id", "seq", "created_at", "created_by",
    }
)
```

Tripwire 1 — `test_trigger_column_list_matches_schema` (`:246-258`), models ↔ constants:

```python
def test_trigger_column_list_matches_schema():
    """A new ledger column must fail loudly instead of escaping the trigger.

    The guard enumerates columns by name, so a column added to the model
    without a matching trigger update would be mutable — a silent fail-open.
    This asserts the enumeration is exactly "every column except the sync
    cursor", which is the invariant the triggers encode.
    """
    op_columns = {c.key for c in Operation.__mapper__.columns} - {"synced_at"}
    assert op_columns == IMMUTABLE_OPERATION_COLUMNS, _DRIFT_HINT

    cash_columns = {c.key for c in CashMovement.__mapper__.columns} - {"synced_at"}
    assert cash_columns == IMMUTABLE_CASH_COLUMNS, _DRIFT_HINT
```

Tripwire 2 — `test_declared_constants_match_trigger_ddl` (`:261-290`), constants ↔ `app/db.py`:

```python
    ddl = {
        "operations": next(
            t for t in APPEND_ONLY_TRIGGERS if "CREATE TRIGGER operations_no_update" in t
        ),
        "cash_movements": next(
            t
            for t in APPEND_ONLY_TRIGGERS
            if "CREATE TRIGGER cash_movements_no_update" in t
        ),
    }

    for column in IMMUTABLE_OPERATION_COLUMNS:
        assert f"NEW.{column} " in ddl["operations"], (
            f"operations_no_update does not guard {column!r}. {_DRIFT_HINT}"
        )
    for column in IMMUTABLE_CASH_COLUMNS:
        assert f"NEW.{column} " in ddl["cash_movements"], (
            f"cash_movements_no_update does not guard {column!r}. {_DRIFT_HINT}"
        )

    # The cursor itself must NOT be guarded, or the stamp would be rejected.
    assert "NEW.synced_at" not in ddl["operations"]
    assert "NEW.synced_at" not in ddl["cash_movements"]
```

**The DDL the new columns are inserted into — `app/db.py:37-85` (`APPEND_ONLY_TRIGGERS`).** Note
the alignment column and the header comment block at `:16-37` (which itself must gain a `v4` line
naming `0027`):

```python
APPEND_ONLY_TRIGGERS: tuple[str, ...] = (
    """
    CREATE TRIGGER operations_no_update
    BEFORE UPDATE ON operations
    FOR EACH ROW WHEN
         NEW.id               IS NOT OLD.id
      OR NEW.type             IS NOT OLD.type
      OR NEW.product_id       IS NOT OLD.product_id
      OR NEW.qty_delta        IS NOT OLD.qty_delta
      OR NEW.unit_cost_cents  IS NOT OLD.unit_cost_cents
      OR NEW.unit_price_cents IS NOT OLD.unit_price_cents
      OR NEW.payload          IS NOT OLD.payload
      ...
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
    """
    CREATE TRIGGER operations_no_delete
    BEFORE DELETE ON operations
    BEGIN SELECT RAISE(ABORT, 'operations ledger is append-only'); END
    """,
    ... (cash_movements_no_update, cash_movements_no_delete)
)
```

**The fixture the new `alembic_engine` must sit BESIDE, never replace — `tests/conftest.py:22-32`:**

```python
@pytest.fixture()
def engine(tmp_path):
    """File-based SQLite engine with PRAGMA listener and append-only triggers."""
    engine = build_engine(str(tmp_path / "test.db"))
    # Test-fixture-only exception to the Alembic rule: create schema directly.
    Base.metadata.create_all(engine)
    with engine.connect() as connection:
        for statement in APPEND_ONLY_TRIGGERS:
            connection.exec_driver_sql(statement)
        connection.commit()
    return engine
```

and the server-DB twin inside `sync_driver_pair` (`tests/conftest.py:293-298`):

```python
    # A SEPARATE server database so a push crosses a real boundary.
    server_engine = build_engine(str(tmp_path / "server.db"))
    Base.metadata.create_all(server_engine)
    with server_engine.connect() as connection:
        for statement in APPEND_ONLY_TRIGGERS:
            connection.exec_driver_sql(statement)
        connection.commit()
```

> **14 fixtures transitively depend on `engine`** (`session :36`, `product :43`, `warehouse :57`,
> `batch :66`, `stocked_product :80`, `customer :118`, `client :133`, `anon_client :191`,
> `device_client :221`, `sync_driver_pair :262`, `login :349`, `past_sale :367`,
> `mobile_client_factory :435`). `alembic_engine` goes in `tests/test_migrations.py`, not in
> `conftest.py`'s `engine` chain (V3).

Drafted test bodies for `test_alembic_head_triggers_match_app_db`,
`test_downgrade_upgrade_roundtrip_preserves_triggers` and `test_revision_ids_are_fixed_width` are
already written out in `33-RESEARCH.md` § *How the load-bearing tests are actually constructed* —
copy them from there rather than re-deriving.

---

### A3. `tests/test_business_date.py` (test, transform + render)

**Analog 1 — the tz-fixture idiom: `tests/test_core.py:108-150`** (four dedicated
`local_day_bounds_utc` tests). Note: literal ISO strings + an explicit tz name argument, no
`freezegun`, and the docstring names the decision ID it pins:

```python
def test_local_day_bounds_utc_single_day_moscow():
    """D-02: single-day bounds are local midnight-to-midnight, converted to UTC.

    Moscow is UTC+3 with no DST, so local midnight of 2026-07-10 is
    2026-07-09T21:00:00+00:00, and the (half-open) upper bound is local
    midnight of the day AFTER, 2026-07-10T21:00:00+00:00.
    """
    start_iso, end_iso = local_day_bounds_utc(date(2026, 7, 10), date(2026, 7, 10), "Europe/Moscow")
    assert start_iso == "2026-07-09T21:00:00+00:00"
    assert end_iso == "2026-07-10T21:00:00+00:00"


def test_local_day_bounds_utc_evening_sale_within_local_day():
    """D-02: 23:30 local time on 2026-07-10 (20:30 UTC) is WITHIN that day's bounds."""
    start_iso, end_iso = local_day_bounds_utc(date(2026, 7, 10), date(2026, 7, 10), "Europe/Moscow")
    evening_sale_utc = "2026-07-10T20:30:00+00:00"
    assert start_iso <= evening_sale_utc < end_iso


def test_local_day_bounds_utc_next_local_day_excluded():
    """D-02: 00:30 local on 2026-07-11 (21:30 UTC the 10th) belongs to July 11, NOT July 10."""
    ...
    assert not (start_iso <= next_local_day_sale_utc < end_iso)
```

**These four tests must stay green untouched** — 36 test call sites across 6 files build
`created_at` fixtures with the helper (`33-RESEARCH.md` CD-10).

**Analog 2 — the markup-assertion idiom (VA-15, «every write surface renders `op_date`»):
`tests/test_receipts.py:441-445`.** Plain substring assertions against `response.text`, one per
fact — no HTML parser:

```python
    assert "Приход товара" in response.text
    assert "Сохранить приход" in response.text
    assert 'id="code"' in response.text
    assert "autofocus" in response.text
    assert 'name="qty"' in response.text
```

For the 14 surfaces this becomes `assert 'name="op_date"' in response.text` plus
`assert f'value="{today}"' in response.text`, driven off the `client` / `mobile_client_factory`
fixtures.

---

### A4. `tests/test_sync_schema_gate.py` (test, request-response)

**Analog 1 — NDJSON batch construction, incl. the `schema_version` header key:
`tests/test_merge.py:32-67`.** This is where the gate's tests inject an explicit
`schema_version` (D-03: `current_schema_version` returns `""` under `create_all`, so the escape
hatch would otherwise make every gate assertion vacuous):

```python
def record_line(kind: str, **fields) -> dict:
    """Build one NDJSON record dict: a ``kind`` discriminator + explicit fields."""
    return {"kind": kind, **fields}


def record_from_orm(kind: str, obj, **overrides) -> dict:
    """Build a record dict from an ORM row's mapper columns, plus any overrides."""
    data = {column.key: getattr(obj, column.key) for column in obj.__mapper__.columns}
    data.update(overrides)
    return {"kind": kind, **data}


def build_ndjson(*, header_overrides: dict | None = None, records: list[dict]) -> list[str]:
    """Return NDJSON lines (header first, then one line per record dict).

    ``header_overrides`` patches the default header envelope
    (e.g. ``{"format_version": 999}`` for the rejection tests).
    """
    header = {
        "kind": "header",
        "format_version": merge.FORMAT_VERSION,
        "schema_version": "0017",
        "source_device_id": "device-A",
        "generated_at": "2026-07-19T10:00:00+00:00",
        "counts": {},
    }
    if header_overrides:
        header.update(header_overrides)
    lines = [json.dumps(header, ensure_ascii=False)]
    lines.extend(json.dumps(rec, ensure_ascii=False) for rec in records)
    return lines
```

→ the client-ahead case is `build_ndjson(header_overrides={"schema_version": "0028"}, ...)`;
the client-behind case is `{"schema_version": "0026"}`.

**Analog 2 — how a push is issued and asserted: `tests/test_sync_api.py:115-122`:**

```python
def test_push_with_valid_token(device_client, product, batch):
    body = _ndjson([_op("op-1", product_id=product.id, batch_id=batch.id, seq=1)])
    resp = device_client.client.post(
        "/api/sync/push", content=body, headers=_bearer(device_client.plaintext)
    )
    assert resp.status_code == 200
    assert resp.json()["operations_inserted"] == 1
```

**Analog 3 — the cross-boundary driver (for VA-2, «rows stay unsynced»):
`tests/conftest.py:262-284 sync_driver_pair`** yields `(client, server_session, plaintext)`; the
LOCAL client DB is the standard `session`/`engine`, a SEPARATE server DB backs the in-process app
over an `httpx.ASGITransport` bridge, so a push genuinely crosses the boundary. VA-2 asserts
`Operation.synced_at IS NULL` on the CLIENT session after the 409.

---

### B1. `business_date_bounds` — the SHAPE it copies

**Analog: `app/core.py:108-126 local_day_bounds_utc`** (this function is **not** modified and
**not** deleted; it only gains one docstring line saying it is now the `created_at`-only helper):

```python
def local_day_bounds_utc(start_day: date, end_day: date, tz_name: str) -> tuple[str, str]:
    """UTC ISO bounds for the LOCAL half-open range [start_day, end_day] inclusive.

    end_day is the LAST included local calendar day; the returned upper
    bound is local midnight of the day AFTER end_day, converted to UTC —
    so callers filter created_at >= start AND created_at < end (never a
    closed range, which would double-count a row landing exactly on a
    UTC-midnight boundary). This is the ONLY sanctioned way to turn a
    local calendar day/range into a UTC filter range (D-02): never slice
    the UTC created_at string by date directly, or an evening sale near
    local midnight shifts into the wrong day's report.
    """
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(start_day, time.min, tzinfo=tz)
    end_local = datetime.combine(end_day, time.min, tzinfo=tz) + timedelta(days=1)
    return (
        start_local.astimezone(UTC).isoformat(timespec="seconds"),
        end_local.astimezone(UTC).isoformat(timespec="seconds"),
    )
```

**The half-open contract is the thing to copy consciously, not mechanically.** This returns
`[start, end)`. `business_date_bounds` compares date strings and is naturally **closed**
`[start_day, end_day]` — Pitfall D. Whichever the plan picks, the docstring must say which, and all
14 switched call sites must follow it. The drafted docstring is in `33-RESEARCH.md` Pattern 1.

Also copy the two adjacent render filters, because every reader switched from a timestamp to a
`String(10)` column must switch filter too (`app/core.py:89-105`):

```python
def format_ru_date(iso: str | None) -> str:
    """Render a stored ISO date ('2026-07-12') as RU display 'dd.mm.yyyy'. ..."""
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return d.strftime("%d.%m.%Y")


def iso_to_local(iso_str: str, tz_name: str) -> str:
    """Convert a UTC ISO-8601 string to local display time: '08.07.2026 15:00'."""
    moment = datetime.fromisoformat(iso_str)
    return moment.astimezone(ZoneInfo(tz_name)).strftime("%d.%m.%Y %H:%M")
```

### B2. `business_date_expr` — the COALESCE discipline

**Analog: `app/services/reports.py:21-38 operation_currency_clause`.** Copy the docstring
*structure*: name the nullable column, name the fallback and why it is that value, name the join
discipline callers must obey, and end with «ONE shared helper, never re-implemented inline».

```python
def operation_currency_clause(currency: str):
    """LOCKED decision: the shared currency predicate for Operation-based reports.

    `Operation.batch_id` is nullable (pre-Phase-9 legacy rows, which predate
    any warehouse/currency concept). Currency resolves via
    `Operation.batch_id -> Batch.warehouse_id -> Warehouse.currency`, falling
    back to `DEFAULT_CURRENCY` (RUB) when `batch_id IS NULL` — matching
    migration 0023's backfill (every pre-existing row has always been RUB).

    Callers MUST reach this predicate through an OUTER join chain
    (`.outerjoin(Batch, Operation.batch_id == Batch.id)
    .outerjoin(Warehouse, Batch.warehouse_id == Warehouse.id)`) — an INNER
    join would silently DROP legacy rows from every currency's report
    instead of counting the NULL ones under RUB, which is a
    data-loss-shaped bug. This is ONE shared helper, never re-implemented
    inline per report.
    """
    return func.coalesce(Warehouse.currency, DEFAULT_CURRENCY) == currency
```

Target shape (`33-RESEARCH.md` Pattern 2):
`func.coalesce(Model.business_date, func.substr(Model.created_at, 1, 10))`.

### B3. `parse_op_date` + the two RU constants

**Analog: `app/services/receipts.py:43,46-66 parse_optional_expiry`.** Constant sits with the other
RU error constants directly above the function; the docstring names the requirement, states the
empty-value rule, and states *why* the browser's ISO guarantee is re-checked server-side:

```python
WAREHOUSE_ERROR = "Выберите склад."
# D-01: the chooser demands an explicit top-up-or-new decision.
BATCH_CHOICE_ERROR = "Выберите партию для пополнения или «Новая партия»."
EXPIRY_ERROR = "Укажите срок годности в формате ГГГГ-ММ-ДД."


def parse_optional_expiry(
    raw: str, errors: dict[str, str], key: str = "expiry"
) -> str | None:
    """Validate an optional ISO expiry (LOT-03), mirroring parse_optional_cents.

    Empty (after strip) -> None: expiry is optional. Otherwise the value must
    be an ISO yyyy-mm-dd date — which `<input type="date">` always posts,
    regardless of locale — normalized via `date.fromisoformat`. Form values
    are untrusted (V5), so the browser's ISO guarantee is re-checked
    server-side: any other input sets the RU error under `key` and returns
    None (nothing is written).
    """
    s = raw.strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s).isoformat()
    except ValueError:
        errors[key] = EXPIRY_ERROR
        return None
```

Second constant-naming precedent (`app/services/active_catalog.py:18-21`) — the comment citing the
UI-SPEC copywriting contract by section name is part of the idiom:

```python
# Copy taken verbatim from 23-UI-SPEC.md's Copywriting Contract, "Error
# state — catalog form (D-02)".
NUMBER_TOO_LONG_ERROR = "Слишком длинный номер каталога."
CLOSE_DATE_ERROR = "Проверьте дату закрытия каталога."
```

`parse_op_date` differs from `parse_optional_expiry` in exactly one place: it needs a **second**
branch for the future check (`OP_DATE_FUTURE_ERROR`) after `date.fromisoformat` succeeds.

### B4. `push_schema_ok` in `app/services/sync.py`

**Sibling it sits directly under — `app/services/sync.py:225-235`:**

```python
def current_schema_version(session: Session) -> str:
    """The live Alembic revision, or "" when the schema was built by create_all.

    Derived from the DB (never a hardcoded revision) so Phase 30's OFF-07
    schema-version gate reads a truthful value. Test fixtures build the schema
    with ``Base.metadata.create_all`` and therefore have no ``alembic_version``
    table, so ``get_current_revision`` returns None — ``parse_exchange`` accepts an
    empty ``schema_version``, so the "" fallback is safe.
    """
    context = MigrationContext.configure(session.connection())
    return context.get_current_revision() or ""
```

**Predicate shape to mirror — `app/services/offline.py:61-71 schema_version_ok`. READ ONLY;
D-02 forbids modifying it:**

```python
def schema_version_ok(header_schema: str, server_schema: str) -> bool:
    """Return whether a bundle's schema version is acceptable to ingest (D-09).

    Skips the gate (True) when `server_schema` is empty — create_all fixtures have
    no `alembic_version` table, so `current_schema_version` returns "" (Pitfall 7).
    Otherwise requires an exact match, so a bundle built on a different migration
    head is rejected before any merge.
    """
    if server_schema == "":
        return True
    return header_schema == server_schema
```

The differences `push_schema_ok` must introduce (D-01/D-03): the escape hatch is on **both** sides
(`if not server_schema or not client_schema: return True`), and the comparison is
**asymmetric** (`client_schema <= server_schema`), not exact-match.

### B5. The 409 route gate

**Analog — `app/routes/offline.py:232-243`** (⚠ CONTEXT cites `:228-243`; `:228-230` is the payload
digest check, the gate itself starts at `:232` — see §Drift):

```python
    # (5) Schema gate (D-09): exact-match at the route layer, naming BOTH versions;
    # an empty server schema (create_all fixture) skips the gate (Pitfall 7).
    server_schema = current_schema_version(session)
    file_schema = header.get("schema_version", "")
    if not offline_service.schema_version_ok(file_schema, server_schema):
        return _result(
            request,
            "incompatible",
            status=409,
            file_ver=file_schema,
            server_ver=server_schema,
        )
```

**The four RU constants the fifth one joins — `app/routes/sync.py:50-54`.** Note the section
comment naming the UI-SPEC contract and the «HTML-free» rule:

```python
# RU error messages (UI-SPEC Copywriting Contract). HTML-free.
PAYLOAD_TOO_LARGE_ERROR = "Слишком большой объём данных."
RATE_LIMITED_ERROR = "Слишком много запросов. Попробуйте позже."
MALFORMED_BATCH_ERROR = "Некорректный формат данных."
INVALID_CURSOR_ERROR = "Некорректная метка синхронизации."
```

**The exact insertion point — `app/routes/sync.py:108-121`.** The gate lands between step (4)
(`parse_exchange`) and step (5) (the owned transaction), per D-05, and follows the same
`raise HTTPException(status_code=..., detail=<RU constant>)` idiom:

```python
    # (4) Parse OUTSIDE the transaction — parse_exchange validates before any DB
    # touch by design. Never echo the raw exception text (it can quote attacker
    # input) back to the client (V7).
    try:
        batch = parse_exchange(lines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=MALFORMED_BATCH_ERROR) from exc

    # (5) The route owns the ONE transaction: apply_merge never commits, so a
    # mid-batch failure rolls the WHOLE batch back (all-or-nothing). ...
    session.rollback()
    with session.begin():
        report = apply_merge(session, batch, server_now=utcnow_iso())
```

### B6. `format_sync_message` gaining one branch

**Analog — `app/services/sync_client.py:186-209`.** The new `schema_mismatch` branch is one more
`elif` in this chain, above the final `else`:

```python
    status = result.status
    if status == "ok":
        if result.pushed == 0 and result.pulled == 0:
            message = "Синхронизировано, изменений нет"
        else:
            message = (
                f"Синхронизировано: отправлено {result.pushed}, "
                f"получено {result.pulled}"
            )
    elif status == "partial":
        message = (
            f"Синхронизировано частично: отправлено {result.pushed} "
            f"из {result.pushed_total}"
        )
    elif status == "offline":
        message = "Нет связи с сервером"
    elif status == "locked":
        # D-09: a manual click landed while a tick is already running.
        message = "Синхронизация уже выполняется"
    elif status == "not_configured":
        # SRV-03: blank server URL / token — a fresh install is a no-op.
        message = "Синхронизация не настроена"
    else:
        # `error` and any unexpected status collapse to the generic D-12 error.
        message = "Ошибка сервера, попробуйте позже"
```

Its docstring tail (`:182-184`) is the constraint the new branch must honour — **fixed strings +
integer counts only**, never server bytes:

```
    T-29-07 / V7: ONLY these fixed strings + integer counts ever cross this
    boundary — raw server error bytes and the sync token can never be interpolated.
```

**The branch point — `app/services/sync_client.py:376-382`.** The 409 test goes inside the existing
`except httpx.HTTPStatusError`, and the comment at `:378` is already the SYNC-11 guarantee in
prose:

```python
        response.raise_for_status()
    except httpx.HTTPStatusError:
        # A non-2xx: rows stay unsynced (Pitfall 3), retried next sync.
        return SyncResult(status="error", pushed=0, pushed_total=pushed_total)
    except httpx.HTTPError:
        # Offline / timeout / transport error: never raised out (SYNC-06).
        return SyncResult(status="offline", pushed=0, pushed_total=pushed_total)

    # Stamp synced_at ONLY after the 2xx (migration 0018 permits SET synced_at).
    stamp = utcnow_iso()
```

**D-09's back-off site — `app/main.py:71-103 _auto_sync_iteration`.** The interval is read at the
TOP (`:86-87`) and returned at the BOTTOM (`:103`); D-09's ~4 lines re-read
`sync_state.last_status` before that `return interval`:

```python
    interval = DEFAULT_INTERVAL_SECONDS
    try:
        with SessionLocal() as session:
            enabled, interval = sync_client.read_autosync_config(session)
        if enabled:
            await anyio.to_thread.run_sync(
                sync_client.run_sync_tick, abandon_on_cancel=False
            )
    except Exception:
        # D-08: offline / transport / transient DB error → silently skip.
        pass
    return interval
```

### B7. `record_operation` / `record_cash_movement` — the kwarg-with-default

**`app/services/ledger.py:37-49` (signature) and `:123` (the stamp):**

```python
def record_operation(
    session: Session,
    *,
    type_: str,
    product_id: str,
    qty_delta: int,
    unit_cost_cents: int | None = None,
    unit_price_cents: int | None = None,
    payload: dict | None = None,
    sale_id: str | None = None,
    batch_id: str | None = None,
    commit: bool = True,
) -> Operation:
    """Append one immutable ledger row and update the cached stock projection.

    This is the ONLY sanctioned write path for operations and
    products.quantity (FND-01). Audit fields are stamped from settings
    (FND-03, D-17). Everything happens in one transaction (D-09).
```

```python
        sale_id=sale_id,
        batch_id=batch_id,
        author_id=author_id,
        device_id=settings.device_id,
        seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(),
        created_by=created_by,
    )
    session.add(op)
```

The new keyword is `business_date: str | None = None`, inserted keyword-only among the other
defaulted optionals and threaded into the `Operation(...)` constructor beside `created_at`.
**`created_at=utcnow_iso()` is not touched** (DATE-04).

**`app/services/finance.py:48-57`** — same shape, and `currency: str = DEFAULT_CURRENCY` is the
in-file precedent for a defaulted keyword added by a later phase:

```python
def record_cash_movement(
    session: Session,
    *,
    category: str,
    amount_cents: int,
    currency: str = DEFAULT_CURRENCY,
    sale_id: str | None = None,
    note: str | None = None,
    commit: bool = True,
) -> CashMovement:
    """Append one immutable cash_movements row.

    This is the ONLY sanctioned write path for cash_movements (D-00b).
```

Call sites (all verified exact by `33-RESEARCH.md`): `record_operation` × 12
(`catalog.py:137,279,288` stay on the default; `corrections.py:120`, `receipts.py:160,186,241`,
`returns.py:156`, `sales.py:287`, `transfers.py:176,184`, `writeoffs.py:105` = the 9 real ones);
`record_cash_movement` × 3 (`finance.py:188`, `returns.py:174`, `sales.py:310`).

---

### C1. Desktop ledger form — the uniform inline-error idiom

**`app/templates/partials/receipt_form.html:23-44`.** `<form>` opens at `:23` with `hx-post` at
`:24`; the field shape the date input copies is `:32-44` — `<div class="field">` + block
`<label for>` + `<input>` + `{% if errors.X %}<p class="error">…</p>{% endif %}`:

```html
  <form class="stacked-form"
        hx-post="/receipts"
        hx-target="#receipt-form-wrap"
        hx-swap="outerHTML"
        hx-disabled-elt="find button"
        hx-on::before-swap="..."
        hx-on::oob-before-swap="...">
    <div class="field">
      <label for="code">Код</label>
      {# D-03/RCP-02: debounced lookup — the server decides fill vs 204. #}
      <input type="text" id="code" name="code" value="{{ form.code or '' }}" required autofocus
             hx-get="/receipts/lookup" ...>
      {% if errors.code %}<p class="error">{{ errors.code }}</p>{% endif %}
    </div>
```

The date field is inserted as the LAST `.field` before `.form-actions` (`:94`) on this and the
other 7 desktop/cash surfaces. Exact markup is already written in `33-UI-SPEC.md`
§ *Canonical markup*.

### C2. Mobile SHELL wizard vs FINAL-STEP form — the two idioms D-11 splits between

**SHELL (приход/продажа/списание) — `app/templates/mobile_pages/receipts.html:1-17`.** The
`<form>` at `:12` wraps `#wizard-step` and is never swapped; the date input goes immediately after
it opens, before `<div id="wizard-step">` (`:13`). The header comment already documents the
carry-forward property D-11 exploits:

```html
{# Приход wizard, step 1 «Товар» (UI-01, Phase 11 Plan 03). Full-page load —
   every subsequent step is a partial swapped into #wizard-step via htmx,
   inside this SAME persistent <form> (RESEARCH Pattern 1: hidden-field
   carry-forward, no server-side wizard session). ... #}
{% extends "mobile_base.html" %}
{% block content %}
<h1>Приход</h1>
<form id="receipt-form" hx-target="#wizard-step" hx-swap="innerHTML">
<div id="wizard-step">
  {% include "mobile_partials/receipts_step_product.html" %}
</div>
</form>
{% endblock %}
```

**FINAL-STEP (корректировка/перемещение) — `app/templates/mobile_partials/corrections_step_value.html`.**
No shell; a per-step `<form>` at `:21`. The date field goes after «Примечание» (`:36-39`) and
before `<div class="mobile-actions">` (`:40`). Note the **loop-all `.error-block` at `:13-17`** —
this is the D-14 non-uniform case: the `op_date` error must be excluded from this loop and rendered
per-key under the input instead. Note also the guarded value idiom at `:33`
(`form.value if form is defined and form.value else ''`), which the date input's `value=` mirrors:

```html
  {% if errors %}
  <div class="error-block">
    {% for message in errors.values() %}<p>{{ message }}</p>{% endfor %}
  </div>
  {% endif %}
  ...
  <form class="stacked-form" id="corrections-value-form"
        hx-post="/m/corrections"
        hx-target="#corrections-step-wrap"
        hx-swap="outerHTML"
        hx-disabled-elt="find button">
    <input type="hidden" name="code" value="{{ code }}">
    ...
    <div class="field">
      <label for="value">{% if mode == "count" %}Фактический остаток{% else %}Изменение (+ или −){% endif %}</label>
      <input type="text" id="value" name="value" inputmode="numeric"
             value="{{ form.value if form is defined and form.value else '' }}">
      <span class="muted">Остаток в партии: {{ ... }}</span>
    </div>
    <div class="field">
      <label for="note">Примечание <span class="muted">(необязательно)</span></label>
      <input type="text" id="note" name="note" value="{{ form.note if form is defined and form.note else '' }}">
    </div>
    <div class="mobile-actions">
      <button type="button" class="secondary" ...>Назад</button>
      <button type="submit">Сохранить корректировку</button>
    </div>
  </form>
```

The exclusion pattern to copy for the loop is `receipts_step_confirm.html:20`, which already
excludes the `form` key from its per-key render.

### C3. The «Когда» cell — both desktop layouts + the mobile card

**Generic 10-column layout — `app/templates/partials/history_rows.html:125`:**

```html
        <td>{{ r.op.created_at | local_dt }}</td>
```

**Per-type narrowed layout — `app/templates/partials/history_rows.html:240`** (byte-identical
line, which is why D-18's shape works in both without colspan churn — `colspan="10"` at `:118` and
`{{ 3 + columns|length + 1 }}` at `:233` stay untouched):

```html
        <td>{{ r.op.created_at | local_dt }}</td>
```

**The muted-second-line precedent D-18 copies — `history_rows.html:132-147`** (the D-15 batch
attribution in the «Товар» cell). Copy the whitespace-control (`{%- … -%}`), the `<br><span
class="muted">` shape, and the comment style that names the decision and the read-time-only rule:

```html
        {# D-15: muted batch attribution as a SECOND line in the «Товар» cell — no
           extra column. Stock-affecting op with a batch -> «Партия: …»; with NULL
           batch_id (pre-Phase-9) -> the legacy label «До внедрения партий» (read-time
           only, the ledger is never rewritten); audit types -> no second line. Batch
           comment is untrusted stored text (T-05-18): autoescape only, never |safe. #}
        <td>{{ r.product.name }}
          {%- if r.op.type not in ("price_change", "product_created", "product_edited") %}
          <br><span class="muted">
            {%- if r.batch -%}
            Партия: {% if r.batch.expiry %}{{ r.batch.expiry | ru_date }}{% else %}без срока{% endif %}{% if r.batch.comment %} — {{ r.batch.comment }}{% endif %}
            {%- else -%}
            До внедрения партий
            {%- endif -%}
          </span>
          {%- endif -%}
        </td>
```

**Mobile card header — `app/templates/mobile_partials/history_cards.html:31`.** D-21's sibling
muted `<p>` goes directly under this line; `:33-35` shows the existing sibling-`<p class="muted">`
shape to copy:

```html
<div class="mobile-card">
  <p class="muted">{{ r.op.created_at | local_dt }} · {{ OPERATION_TYPE_LABELS.get(r.op.type, r.op.type) }}</p>
  <p><strong>{{ r.product.name }} ({{ r.product.code }})</strong></p>
  {%- if columns %}
  {%- if "expiry" in columns %}
  <p class="muted">Срок: {% if r.batch and r.batch.expiry %}{{ r.batch.expiry | ru_date }}{% ... %}</p>
  {%- endif %}
```

> **Filter reminder (`33-CONTEXT.md` §Reusable Assets):** any cell switched from a timestamp to the
> `String(10)` business date MUST switch `| local_dt` → `| ru_date`, or `iso_to_local("2026-09-01")`
> builds a naive datetime and renders a bogus time.

### C4. The fourth `.filter-bar` select — six htmx attributes, verbatim

**`app/templates/partials/history_rows.html:27-35`** (the `type` select; `sort` at `:39-45` and
`author` at `:54-62` are byte-identical in their attribute block). The new
`<select name="dated">` copies this exactly, changing only `id`/`name`/`<option>`s:

```html
    <div class="field">
      <label for="type">Тип операции</label>
      <select id="type" name="type"
              hx-get="/history" hx-trigger="change"
              hx-include="#history-rows input, #history-rows select"
              hx-target="#history-rows" hx-swap="outerHTML" hx-push-url="true">
        <option value=""{% if not type_filter %} selected{% endif %}>Все типы</option>
        {% for t, label in OPERATION_TYPE_LABELS.items() %}
        <option value="{{ t }}"{% if t == type_filter %} selected{% endif %}>{{ label }}</option>
        {% endfor %}
      </select>
    </div>
```

`.filter-bar` closes at `:64`; the new select is the fourth `<div class="field">` inside it.

---

## Shared Patterns

### S1. The five-artifact lockstep — ONE commit, always

**Source:** `app/db.py:16-37` (comment block) + `alembic/versions/0026_*.py:6-24` +
`tests/test_append_only_cursor.py:15-22`.
**Apply to:** the migration, `app/models.py`, `app/db.py`, `tests/test_append_only_cursor.py`.

```
# LOCKSTEP RULE — this constant and migration 0018 must ALWAYS move together.
# tests/conftest.py builds every test DB from Base.metadata.create_all plus
# this constant, never via Alembic; if the two drift, the whole suite tests
# the old triggers while production runs the new ones. Any future change to
# these triggers needs a NEW migration and a matching edit here in the SAME
# commit.                                                     (app/db.py:24-29)
```

The five artifacts: (1) the model columns, (2) `app/db.py::APPEND_ONLY_TRIGGERS`, (3) the
migration's `_SQLITE_DDL`/`_PG_DDL`, (4) `IMMUTABLE_OPERATION_COLUMNS`, (5)
`IMMUTABLE_CASH_COLUMNS`. `app/db.py:16-22` also carries the running version log
(«FROZEN v1 copies … frozen v2 copy … frozen v3 copy») — `0027` adds a **v4** entry there.

### S2. WR-06 — migrations never import app code

**Source:** `alembic/versions/0026_*.py:27-29`, `alembic/versions/0024_*.py:30`, `app/db.py:20-22`.
**Apply to:** `alembic/versions/0027_*.py` only.

```
Immutability rule (WR-06): this file never imports application modules —
stdlib + sqlalchemy + alembic.op only. All DDL below is a literal string
constant; no value is ever interpolated into SQL.
```

Consequence for `0027`: the backfill's timezone is a **file-local literal** the way
`_DEFAULT_CURRENCY = "RUB"` is (`0024:30`), not `from app.config import settings`. That makes V14
(what `display_tz` s1 actually sets) an input to the migration's **source text**.

### S3. Service-layer RU error constants, module-top, cited to a UI-SPEC

**Source:** `app/services/receipts.py:40-43`, `app/services/active_catalog.py:18-21`,
`app/routes/sync.py:50-54`.
**Apply to:** `OP_DATE_FORMAT_ERROR`, `OP_DATE_FUTURE_ERROR` (service layer),
`SCHEMA_AHEAD_ERROR` (route layer).
Constants sit at module top, are plain RU strings with no HTML, and carry a one-line comment naming
the decision ID or the UI-SPEC section they were copied from.

### S4. Docstrings cite the decision ID they encode

Every analog above does it: `"""LOCKED decision: …"""` (`reports.py:22`),
`"""Validate an optional ISO expiry (LOT-03) …"""` (`receipts.py:49`),
`"""…(D-02): never slice the UTC created_at string…"""` (`core.py:113-119`),
`"""D-02: single-day bounds are…"""` (`test_core.py:109`). New code copies this — the phase's
decision IDs are `D-01 … D-25`, requirements `SYNC-10..13` / `DATE-01..08`.

---

## D. ANTI-PATTERNS — do NOT copy these

### AP-1 ⛔ `0024.downgrade()` — the batch-mode drop that eats the cash ledger

**Source: `alembic/versions/0024_cash_movement_currency.py:50-52`. This is live, shipped, and
broken. DO NOT COPY IT.**

```python
def downgrade() -> None:
    with op.batch_alter_table("cash_movements") as batch_op:
        batch_op.drop_column("currency")          # ⛔ ANTI-PATTERN
```

**What it does.** `33-RESEARCH.md` executed `alembic downgrade 0026 → 0023` against a scratch DB
built by `alembic upgrade head` and observed:

```
triggers after downgrade 0026->0023: ['operations_no_delete', 'operations_no_update']
```

Both `cash_movements_no_update` and `cash_movements_no_delete` were **silently destroyed**.
`alembic/env.py:57,85` enables `render_as_batch=True`, and Alembic 1.18.5's
`SQLiteImpl.requires_recreate_in_batch` returns `True` for every batch op except `add_column`,
`create_index` and `drop_index` — so `drop_column` recreates the table and the triggers vanish
with it. This is Pitfall 3, live in HEAD.

**What `0027.downgrade()` must do instead (NC-1 + NC-2):**

1. **FIRST** restore the pre-`0027` trigger DDL — a `_SQLITE_DOWNGRADE_DDL` / `_PG_DOWNGRADE_DDL`
   pair holding the `0026`-era enumeration, exactly the shape at `0026:81-116`.
2. **THEN** `op.drop_column(...)` × 4, **plain — never `batch_alter_table`**.

The order is not optional. Executed:

```
A) drop a trigger-referenced column WITHOUT restoring the trigger first:
   FAILED -> OperationalError error in trigger cm_no_update after drop column: no such column: NEW.business_date
B) restore the old trigger first, then drop:
   OK; triggers still present: ['cm_no_update']
```

**Related guard-rail on the `upgrade()` side:** if a `server_default` is ever added to a new column
it must be a **plain string literal** (as `0024:40` does with `"RUB"`), never `sa.text(...)` /
`sa.func.*` — a `ClauseElement` default flips `requires_recreate_in_batch` to `True` and destroys
all four triggers on the way *up*. Per V1 the four new columns should carry **no** default at all,
so this is a guard-rail, not a plan.

### AP-2 ⛔ Re-flowing the trigger DDL alignment without keeping the trailing space

**Source: `tests/test_append_only_cursor.py:280,284`:**

```python
        assert f"NEW.{column} " in ddl["operations"], (
            f"operations_no_update does not guard {column!r}. {_DRIFT_HINT}"
        )
```

The assertion includes a **trailing space** after the column name. `app/db.py:37-85` column-aligns
the `IS NOT` operators with padding, and adding `business_date` (13 chars) to
`operations_no_update` / `reverses_movement_id` (20 chars) to `cash_movements_no_update` widens
that alignment column. **At least one space must remain after every `NEW.<column>` token in both
`app/db.py` and both migration DDL branches**, or the tripwire reddens for a purely cosmetic
reason — and the "obvious fix" (relaxing the assertion) re-opens the fail-open hole the tripwire
exists to close.

### AP-3 ⛔ Do not "fix" `merge._ledger_row`

`33-RESEARCH.md` CF-2: V1 executed proves `session.execute(insert(model), rows)` already honours
`default=` / `server_default=` and drops `None`-valued keys. Do **not** add
`{k: v for k, v in row.items() if v is not None}` — a second mechanism (CLAUDE.md PC-6) that would
also *break* DATE-08 by suppressing the deliberate NULL a pre-update client must produce.

### AP-4 ⛔ Do not overload `local_day_bounds_utc`

No `date_only: bool` flag, no `column=` parameter. `.planning/research/PITFALLS.md:348` locks the
sibling-helper rule; `app/core.py:108` is not modified beyond one docstring line and not deleted
(36 test call sites across 6 files depend on it).

### AP-5 ⛔ Do not modify `app/services/offline.py:61-71`

D-02. It is locked by 30-UI-SPEC and rendered at `app/templates/offline/result.html:26-29`. Read it
as a shape; write `push_schema_ok` in `app/services/sync.py`.

---

## No Analog Found

None. Every new file has at least a role-match analog in the working tree.

The one thing with **no** in-repo precedent is the *content* of the `alembic_engine` fixture —
invoking Alembic programmatically with `DATABASE_URL` pointed at a `tmp_path` DB. Nothing in
`tests/` builds a schema via Alembic today (V3). The drafted body is in `33-RESEARCH.md`
§ *How the load-bearing tests are actually constructed*; the *surrounding* conventions
(`tmp_path`, `build_engine`, one fixture per file, `pytest.fixture()` with parens) come from
`tests/conftest.py:22-32`.

---

## Analogs named upstream that do not resolve at the stated line

Verified against the working tree at `fba02f2`. All are minor; the code is present, only the line
citation is off.

| Cited as | Actual | Note |
|---|---|---|
| `app/routes/offline.py:228-243` (CONTEXT `:404`, `:351`) — «the 409 schema-refusal precedent» | The gate is **`:232-243`**. `:222-227` is the raw-header peek, `:228-230` is the payload-digest check | Already flagged as CD-7 in `33-RESEARCH.md`; re-confirmed here |
| `tests/conftest.py:292-297` (CONTEXT `:58-59`, `:492`) — the server-DB fixture | **`:293-298`** (`build_engine` at `:293`, `create_all` at `:294`, trigger loop `:295-297`, `commit()` at `:298`) | one-line drift; `33-RESEARCH.md` V3 already states the corrected span |
| `app/static/style.css:304` — `.muted` | Selector `.muted {` is at **`:303`**; `:304` is `color: #6b7280;` | CD-8, cosmetic |
| `app/services/receipts.py:46-65 parse_optional_expiry` | **`:46-66`** (the second `return None` is at `:66`) | CD-4, cosmetic |

Everything else this document cites was opened and confirmed exact: `app/core.py:89-105,108-126`;
`app/services/reports.py:21-38`; `app/services/receipts.py:43`; `app/services/active_catalog.py:21`;
`app/services/sync.py:225-235`; `app/services/offline.py:61-71`; `app/routes/sync.py:51-54,111-114`;
`app/services/sync_client.py:186-209,376-382`; `app/services/ledger.py:37-49,123`;
`app/services/finance.py:48-57`; `app/main.py:71-103`;
`tests/test_append_only_cursor.py:40-73,246-258,261-290` (trailing-space asserts at `:280,284`);
`tests/conftest.py:22-32,262`; `tests/test_core.py:108-150`; `tests/test_merge.py:32-67`;
`tests/test_sync_api.py:115-122`; `app/db.py:37-85`;
`alembic/versions/0018_*.py:68,110,149,164,174,183`; `alembic/versions/0024_*.py:30,33-47,50-52`;
`alembic/versions/0026_*.py:42-58,60-76,78-116,119-132`;
`app/templates/partials/receipt_form.html:23,32-44`;
`app/templates/partials/history_rows.html:27-35,118,125,132-147,233,240`;
`app/templates/mobile_partials/history_cards.html:31`;
`app/templates/mobile_pages/receipts.html:12`;
`app/templates/mobile_partials/corrections_step_value.html:13-17,21,33,36-40`.

---

## Metadata

**Analog search scope:** `alembic/versions/`, `app/core.py`, `app/db.py`, `app/services/`,
`app/routes/`, `app/templates/{partials,mobile_partials,mobile_pages}/`, `tests/`
**Files opened:** 24
**Pattern extraction date:** 2026-09-04
**Read-only:** no source file was modified; this document is the only file written.
