# Architecture Research

**Domain:** Integrating four features into an existing append-only, dual-dialect (SQLite + PostgreSQL), UUID-synced FastAPI/SQLAlchemy warehouse ledger
**Researched:** 2026-09-04
**Confidence:** HIGH for everything cited `path:line` (read from the working tree at commit `b4ca98c`); MEDIUM where marked `needs verification`

---

## 0. STOP — the brief's premises are stale

Per CLAUDE.md "Planning from notes", I re-read the code before planning against the notes. **Five of the seven "verified facts about THIS codebase" handed to me are no longer true.** They were true when `.planning/ROADMAP.md:340-345` was written (2026-08-09). Commit `cdcec66 feat(cur): per-warehouse currency (RUB/UAH/EUR)` (2026-08-10) plus 8 further `feat(cur)` commits — quick task `260810-2g3` (11 commits, 45 files, `__version__` 1.17 → 1.28) — shipped most of the currency phase the next day, and `.planning/ROADMAP.md` was never updated. (Independently confirmed by the coordinator mid-task; the findings below were reached by reading the working tree and agree with it.)

| Brief claim | Reality in the working tree | Evidence |
|---|---|---|
| "22 migrations" | **26.** `0023_warehouse_currency`, `0024_cash_movement_currency`, `0025_batch_cost_cents`, `0026_cash_movements_trigger_guards_currency` all exist | `alembic/versions/` |
| "`reports.py`/`dashboard.py`/`finance.py` contain **zero** occurrences of `warehouse`" | All three are currency-scoped. `reports.py:18` imports `Warehouse`; `reports.py:21-38` is a shared `operation_currency_clause()` helper; `dashboard.py:80,105,125,165` all take a `currency` kwarg; `finance.py:203,217` scope balance and history by currency | `app/services/reports.py:18,21-38,46,74`; `app/services/dashboard.py:80,105,125,165`; `app/services/finance.py:203-214,217-263` |
| "`sales.py` has zero occurrences of `warehouse`, so a basket can mix warehouses" | **Already blocked.** `MIXED_CURRENCY_ERROR` is a hard, non-overridable reject before any write | `app/services/sales.py:45-48,199-204` |
| "`format_cents` renders `12,50` with no currency marker anywhere" | `format_money()` and `currency_symbol()` exist and are registered as the Jinja `money` filter. `format_cents` is now *deliberately* the bare-number filter for columns already labelled with a currency | `app/core.py:60-86`; `app/routes/__init__.py:221-227` |
| "The operation timestamp is simultaneously … the sync cursor" | **False for `Operation`/`CashMovement`.** The ledger push cursor is `synced_at IS NULL` (`sync_client.py:281,284`); the pull cursor is `updated_at` on reference kinds and `Sale.created_at` for sales. `Operation.created_at` is **never** a sync cursor | `app/services/sync.py:67-76`; `app/services/sync_client.py:280-285` |
| "`merge.KIND_TO_FIELDS` … likely drops silently — **needs verification**" | **Verified and already pinned by two tests.** See §3 — the answer is "it depends which half is stale", and one half is loud, not silent | `tests/test_merge.py:644-694` |
| "`mobile_products.py` / `mobile_customers.py` each expose one GET; desktop pair at `products.py:262,281`" | **True** (pair is at `:263` GET / `:283` POST) | `app/routes/mobile_products.py:18`; `app/routes/mobile_customers.py:18`; `app/routes/products.py:263,283` |
| "Returns are the existing precedent for a linked, capped compensating write" | **True** | `app/services/returns.py:65-74,117,165` |

**Still genuinely unbuilt:** zero occurrences repo-wide of `business_date`, `reversal`, or `сторно`. Those two features carry the milestone's real weight, and §2 and §4 are where the depth is.

**Consequence for the roadmapper:** the "Per-Warehouse Currency" phase as written in `.planning/ROADMAP.md:327-349` is ~75% already shipped. §5 re-scopes it **from a phase to a finishing plan** and enumerates exactly what remains.

---

## 1. Standard Architecture (the constraints this milestone must fit inside)

### System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  ROUTES  (thin; untrusted input validated here, never in templates)  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ desktop  │ │  mobile  │ │ /history │ │ /reports │ │ /api/sync/*│  │
│  │ /products│ │  /m/*    │ │          │ │ /finance │ │            │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘  │
├───────┴────────────┴────────────┴────────────┴─────────────┴─────────┤
│  SERVICES  ("fat services", D-11: ALL business rules live here)      │
│  ┌────────────────────────┐  ┌────────────────────────────────────┐  │
│  │ WRITE (2 choke points) │  │ READ (period-scoped aggregations)  │  │
│  │ ledger.record_operation│  │ reports / dashboard / finance_     │  │
│  │ finance.record_cash_   │  │ reports / operations.history_view  │  │
│  │            movement    │  │ customers.spend_totals / export    │  │
│  │  ▲ receipts  ▲ sales   │  └────────────────────────────────────┘  │
│  │  ▲ writeoffs ▲ returns │  ┌────────────────────────────────────┐  │
│  │  ▲ transfers ▲ correct.│  │ merge.apply_merge (PURE, no commit)│  │
│  └────────────────────────┘  └────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│  DATA                                                                │
│  ┌────────────┐ ┌────────────┐ ┌──────────────┐ ┌─────────────────┐  │
│  │ operations │ │cash_movemen│ │ batches ──►  │ │ products/sales/ │  │
│  │ APPEND-ONLY│ │ APPEND-ONLY│ │ warehouses   │ │ customers/dict  │  │
│  │ (triggers) │ │ (triggers) │ │ (.currency)  │ │ (soft-delete)   │  │
│  │ +payload   │ │ NO payload │ │              │ │                 │  │
│  └────────────┘ └────────────┘ └──────────────┘ └─────────────────┘  │
│         SQLite (local client, WAL)  ║  PostgreSQL (s1 server)        │
└──────────────────────────────────────────────────────────────────────┘
```

### Component responsibilities relevant to v5.0

| Component | Responsibility it owns today | Why v5.0 touches it |
|---|---|---|
| `ledger.record_operation` (`app/services/ledger.py:37-136`) | Sole write path for `operations` + `products.quantity` + `batches.quantity`; stamps `created_at`/`created_by`/`author_id`/`device_id`/`seq`; enforces the D-12 mandatory-batch guard and the IN-01 soft-delete guard | Gains one optional `business_date` kwarg; reversal calls it with inverted `qty_delta` |
| `finance.record_cash_movement` (`app/services/finance.py:48-98`) | Sole write path for `cash_movements`; already currency-aware | Gains `business_date`; reversal calls it with negated `amount_cents` |
| `merge.KIND_TO_FIELDS` (`app/services/merge.py:80-83`) | Derives the wire field set from `model.__mapper__.columns` — auto-tracks the schema | Every new column changes the wire format implicitly; §3 |
| `app.db.APPEND_ONLY_TRIGGERS` (`app/db.py:37-85`) | Live trigger DDL for test fixtures (`create_all`, never Alembic) | **Enumerates columns by name.** A new ledger column not added here + in a migration is silently mutable (fail-open) |
| `reports.operation_currency_clause` (`app/services/reports.py:21-38`) | The ONE shared currency predicate; outer-join + `COALESCE(Warehouse.currency, RUB)` for legacy NULL-batch rows | The exact pattern `business_date` must copy for its own NULL fallback |
| `operations.history_view` (`app/services/operations.py:52-195`) | The `/history` read; already outer-joins `Batch` → `Warehouse`, so `row.warehouse.currency` is available with **zero query change** | Hosts the reversal control, the currency-aware money render, and the business-date filter/order |

### Non-negotiables every proposal below respects

1. **No UPDATE, no DELETE on `operations` or `cash_movements`.** Triggers `ABORT` (`app/db.py:37-85`). The only relaxation is `synced_at`, deliberately absent from the `WHEN` clause (`tests/test_append_only_cursor.py:288-290`).
2. **Two write choke points only.** Nothing new inserts ledger rows directly.
3. **Portable ORM constructs only.** No dialect SQL, no raw SQL (`app/services/merge.py:294`).
4. **Migrations never import app code** (WR-06, `alembic/versions/0026_...py:27-29`). Frozen literals are re-declared, as `app/services/returns.py:34-37` already does.
5. **Money is integer minor units.** No float, no Decimal storage, no FX conversion anywhere (`app/core.py:56-59`).

---

## 2. Feature 1 — Back-dated operations

### 2.1 Where the column lives

**New columns (2):**

| Table | Column | Type | Nullable | Rationale |
|---|---|---|---|---|
| `operations` | `business_date` | `String(10)` — local ISO `yyyy-mm-dd` | **Yes** (§3 forces this) | Every period-scoped stock/profit report reads `operations` |
| `cash_movements` | `business_date` | `String(10)` | **Yes** | `cash_expense_total` and `cash_flow_report` filter `CashMovement.created_at` (`finance_reports.py:33-34,126-127`); if cash does not move with operations, `dashboard.period_metrics` computes net profit from two different date semantics (`dashboard.py:96-97`) |

**No column on `Sale`.** `Sale` carries no money and no quantity; every period figure comes from `Operation` rows. Adding one would also collide with `Sale.created_at` being a genuine pull cursor (`app/services/sync.py:76`).

**No column on `Batch`/`Product`.** Not period-scoped.

### 2.2 Why `String(10)` local date, not a mirrored UTC timestamp

The tempting minimal change is `business_date: String(32)` holding a UTC ISO timestamp defaulting to `created_at`, because then every existing filter (`>= start_iso AND < end_iso`) works by swapping the column name and nothing else changes.

**Reject it.** A business date is a *calendar day in the operator's locale*, not an instant. Storing an instant means:
- back-dating requires synthesizing a fake time-of-day (local midnight → UTC), and
- if `settings.display_tz` (`app/config.py:76`, default `Europe/Moscow`) ever changes, every historical back-dated row silently shifts a day.

`String(10)` is timezone-immune and matches the shipped precedent for a stored calendar day: `Batch.expiry` is `String(10)` ISO (`app/models.py:264-266`), rendered by `format_ru_date` (`app/core.py:89-99`).

**Cost of the choice:** period filters change shape from half-open UTC timestamps to an inclusive date range. Routes already hold the `date` objects they need — `_resolve_period` returns `from_date`/`to_date` before converting (`app/routes/reports.py:108-113`; `app/routes/history.py:99-103`) — so the route diff is *smaller*, not larger: pass `period["from_date"].isoformat()` instead of calling `local_day_bounds_utc`.

**Add ONE new shared helper** next to `local_day_bounds_utc` in `app/core.py`, so there is still exactly one sanctioned way to build a period filter (the D-02 discipline in `app/core.py:108-119`):

```python
def business_date_bounds(start_day: date, end_day: date) -> tuple[str, str]:
    """Inclusive ISO date bounds for a business-date period filter.

    Twin of local_day_bounds_utc, for the business-date columns. No tz math:
    business_date is ALREADY a local calendar day. Callers filter
    business_date >= start AND business_date <= end (CLOSED, unlike the
    half-open UTC form — a date has no midnight-boundary ambiguity).
    """
    return start_day.isoformat(), end_day.isoformat()
```

### 2.3 The shared read expression (copy `operation_currency_clause`)

Old clients will push ledger rows with no `business_date` (§3). Reports must never drop those rows. Add ONE shared helper in `app/services/reports.py`, mirroring `operation_currency_clause` (`reports.py:21-38`) exactly in spirit:

```python
def business_date_expr(model):
    """LOCKED: the shared business-date expression for period reports.

    business_date is nullable ONLY because a client on an older build can push a
    ledger row without it (see merge.KIND_TO_FIELDS). Every locally written row
    is stamped by record_operation / record_cash_movement, so NULL is a
    transient cross-version state, never a normal one. Falls back to the UTC
    calendar day of created_at via func.substr — portable on SQLite AND
    PostgreSQL, no dialect SQL. This is ONE helper, never re-implemented inline.

    Known, accepted skew: the fallback is the UTC day, not the local day, so a
    row from an un-upgraded client created near local midnight can land one day
    off. Upgrading that client fixes it; back-filled and locally written rows
    are always correct.
    """
    return func.coalesce(model.business_date, func.substr(model.created_at, 1, 10))
```

### 2.4 Flow through `record_operation` — the audit timestamp is untouched

```python
def record_operation(session, *, type_, product_id, qty_delta, ...,
                     business_date: str | None = None, commit=True):
    ...
    op = Operation(
        ...,
        created_at=utcnow_iso(),          # UNCHANGED — audit stamp
        business_date=business_date or datetime.now(ZoneInfo(settings.display_tz)).date().isoformat(),
        ...
    )
```

- `created_at` (`ledger.py:123`) is **not** read, not derived from, not affected.
- `seq` / `device_id` (`ledger.py:121-122`) untouched — the append-only identity and the `UNIQUE(device_id, seq)` backstop are unaffected.
- `synced_at` untouched — the actual sync cursor.
- The default is **today's local calendar date**, not `created_at[:10]`, because `created_at` is UTC and reports are local (the exact bug `local_day_bounds_utc` was written to prevent, `app/core.py:114-118`).
- Validation of an operator-supplied date belongs in the **service layer**, never the route (house rule, `finance.py:112-116`): reject a non-ISO string and reject a future date. A future business date on a stock operation has no meaning and would corrupt "today" tiles.

`record_cash_movement` (`finance.py:48-98`) takes the identical kwarg with the identical default.

### 2.5 Exact call sites that must switch from the technical timestamp

**MUST switch to `business_date_expr(...)`** — these define *which period a number belongs to*:

| # | Site | What it is |
|---|---|---|
| 1 | `app/services/reports.py:72-73` | `sales_profit_report` period bounds — revenue/cost/profit |
| 2 | `app/services/reports.py:145-146` | `writeoff_report` period bounds |
| 3 | `app/services/reports.py:201-202` | `top_selling_products` period bounds |
| 4 | `app/services/reports.py:224` | `stale_products` — `func.max(Operation.created_at)` drives "days since last sale" |
| 5 | `app/services/finance_reports.py:33-34` | `cash_expense_total` — the expense half of net profit |
| 6 | `app/services/finance_reports.py:126-127` | `cash_flow_report` — must move with #5 or the D-05 reconciliation invariant (`finance_reports.py:115-118`) breaks |
| 7 | `app/services/customers.py:415-416` | `_spend_stmt` — month/quarter/year customer spend (CUST-07) |
| 8 | `app/services/operations.py:151-154` | `history_view` date-range filter (HIST-02) |
| 9 | `app/services/export.py:211-212` | period-scoped cash CSV export |

`app/services/dashboard.py:96-97` needs no edit — `period_metrics` delegates to #1 and #5. But its callers must switch from `local_day_bounds_utc` to `business_date_bounds`, so its signature changes from `(start_iso, end_iso)` to `(start_day, end_day)`.

**MUST NOT switch — display order and audit only:**

| Site | Why it stays `created_at` |
|---|---|
| `app/services/operations.py:30-32` | `_SORT_MAP` / `_DEFAULT_ORDER`. Recommendation: make it `(business_date desc, created_at desc, seq desc)` so a back-dated row sorts into its business period, with `created_at`+`seq` as the stable tiebreaker. Do **not** drop `created_at`/`seq` — `seq` is per-device and cannot order across devices alone. |
| `finance.py:21`, `dashboard.py:156`, `sales.py:374`, `receipts.py:309`, `writeoffs.py:127`, `transfers.py:210`, `catalog.py:351`, `customers.py:352`, `ledger.py:239`, `routes/returns.py:49`, `routes/mobile_returns.py:54` | "Recent N" feeds — these answer *"what did I just enter?"*, which is the technical timestamp by definition. Changing them would make a just-entered back-dated row vanish from the recent list. |
| `app/services/warehouses.py:100` | "last receipt date" per warehouse — arguably business, arguably technical. **Operator decision needed.** Default to leaving it. |
| `app/services/sync.py:67-76`, `app/services/sync_client.py:280-285` | Sync cursors. Never touch. |
| `app/services/export.py:135` | Full-dump ordering, not a period filter. |

### 2.6 Backfill of existing rows — the riskiest single step

A naive `UPDATE operations SET business_date = substr(created_at, 1, 10)` shifts history. `created_at` is UTC; today's reports bucket by *local* day via `local_day_bounds_utc`. At `Europe/Moscow` (UTC+3), a row stamped `2026-09-04T22:30:00+00:00` currently reports as **2026-09-05** but would backfill as **2026-09-04**. Every past-period report number would silently change.

**Do this instead** (all stdlib, satisfies WR-06):

```python
# alembic/versions/00NN_business_date.py — NO app imports.
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# FROZEN literal, deliberately duplicated from app/config.py:76 rather than
# imported (WR-06; same technique as app/services/returns.py:34-37).
_DEFAULT_TZ = "Europe/Moscow"

def upgrade():
    op.add_column("operations", sa.Column("business_date", sa.String(10), nullable=True))
    op.add_column("cash_movements", sa.Column("business_date", sa.String(10), nullable=True))
    tz = ZoneInfo(os.environ.get("DISPLAY_TZ", _DEFAULT_TZ))
    conn = op.get_bind()
    for table in ("operations", "cash_movements"):
        rows = conn.execute(sa.text(f"SELECT id, created_at FROM {table}")).fetchall()
        for row_id, created_at in rows:
            local_day = datetime.fromisoformat(created_at).astimezone(tz).date().isoformat()
            conn.execute(
                sa.text(f"UPDATE {table} SET business_date = :d WHERE id = :i"),
                {"d": local_day, "i": row_id},
            )
    # THEN drop/create the triggers with business_date in the WHEN clause (§2.7).
```

Two hazards to plan for:

1. **Ordering vs. the append-only triggers.** The trigger `WHEN` clause only lists the *old* columns (`app/db.py:41-56`), so an UPDATE that changes only `business_date` does **not** trip it — the same relaxation that lets `synced_at` be stamped (`alembic/versions/0018_sync_cursor_trigger_relaxation.py`, referenced at `app/db.py:31-36`). **Back-fill BEFORE re-creating the trigger with `business_date` in its `WHEN` clause**, or every UPDATE aborts. `needs verification` — smallest check: run the migration against a copy of the s1 dump and assert rows-updated == rows-total.
2. **Regression gate.** Before/after the migration, `sales_profit_report` for a fixed past period must return byte-identical totals. Make this an explicit success criterion, not a hope.

**Volume:** one reseller's ledger; the row-by-row Python loop is acceptable. If it is not, the fallback is a set-based `UPDATE` per distinct UTC offset — messier and DST-fragile. Prefer the loop.

### 2.7 Trigger lockstep — mandatory, or the ledger fails open

**(Coordinator trap #1, verified.)** Adding a ledger column without updating the trigger makes it **freely mutable**. The trigger bodies enumerate columns by name: `app/db.py:41-56` (`operations_no_update`) and `:64-78` (`cash_movements_no_update`). The project already has the tripwire: `tests/test_append_only_cursor.py:246-258` asserts `{Operation columns} - {synced_at} == IMMUTABLE_OPERATION_COLUMNS`, and `:261-290` asserts the constants match the DDL. The failure message is explicit about the consequence — "a column not named in the trigger's WHEN clause can be changed FREELY — the ledger silently fails open" (`tests/test_append_only_cursor.py:236-243`).

**Migration `0026` exists solely because migration `0024` missed this for `currency`** — stated in its own docstring: "migration 0024 added `cash_movements.currency` but did not update the `cash_movements_no_update` append-only trigger … Without this, `currency` would be silently mutable on an already-synced cash row (a fail-open in the append-only ledger invariant)" (`alembic/versions/0026_cash_movements_trigger_guards_currency.py:7-13`).

Every ledger-column migration must ship, **in one commit** (`app/db.py:24-29` LOCKSTEP RULE):

1. `alembic/versions/00NN_...` — `add_column`s, backfill, then DROP/CREATE **both** `*_no_update` triggers with the new columns, **with separate SQLite (`IS NOT`) and PostgreSQL (`IS DISTINCT FROM`) DDL** — copy `alembic/versions/0026_...py:40-116` verbatim as the template, including both `downgrade()` halves. Do **not** retroactively edit 0018/0026 (already-applied migrations are historical fact, `0026:14-16`).
2. `app/db.py::APPEND_ONLY_TRIGGERS` — add the new `NEW.<col>` lines to both `*_no_update` bodies.
3. `tests/test_append_only_cursor.py` — extend `IMMUTABLE_OPERATION_COLUMNS` (`:40-57`) and `IMMUTABLE_CASH_COLUMNS` (`:59-73`).

---

## 3. Sync impact of the schema changes — the `needs verification` item, resolved

`merge.KIND_TO_FIELDS` (`merge.py:80-83`) is a comprehension over `model.__mapper__.columns` **of the process that is running**. Both directions of the wire funnel through it:

- emit: `sync_client.collect_push_records._emit` → `{field: getattr(row, field) for field in merge.KIND_TO_FIELDS[kind]}` (`sync_client.py:330`)
- ingest: `merge._ledger_row` → `{column: data.get(column) for column in KIND_TO_FIELDS[kind]}` (`merge.py:460`); `merge._reference_row` is identical (`merge.py:314`)

`parse_exchange` does **not** filter by `KIND_TO_FIELDS` — it keeps every non-`kind` key (`merge.py:189`) and only rejects unknown *kinds*, non-int `*_cents`, missing ledger provenance, and duplicate ids (`merge.py:186-218`). So an unknown extra field survives parsing and is discarded at `_ledger_row`.

That produces **three distinct failure modes**, not one:

| Case | What happens | Loud or silent? | Pinned by |
|---|---|---|---|
| **A. Server code OLD, DB OLD** (a genuinely un-upgraded server binary) — new client pushes `business_date` | Server's `KIND_TO_FIELDS` has no `business_date`; `_ledger_row` drops the key. The op inserts with everything else intact. **Business date is silently lost, forever, with no error on either side.** | **SILENT DATA LOSS** | Nothing. In-process tests cannot reproduce it — `tests/test_merge.py:648-652` explains exactly why: there is only ever one `app.models` per process |
| **B. Server code NEW, DB OLD** (`git pull` without `alembic upgrade`, or a half-applied self-update) | `_ledger_row` builds `business_date`; the INSERT hits a non-existent column → `OperationalError` → the route's single transaction rolls the whole batch back (`app/routes/sync.py:120-122`) | **LOUD, all-or-nothing** | `tests/test_merge.py:662-674` and `:677-694` pin this exact contract for `cash_movements.currency` and `batches.cost_cents` |
| **C. Client code OLD, server NEW** — old client pushes a row with no `business_date` | `_ledger_row` fills `business_date: None`. Explicit `None` in the dict → SQLAlchemy binds NULL; the `server_default` does **not** apply. If the column is **nullable**, the row lands with NULL and `business_date_expr`'s COALESCE covers it. If **NOT NULL**, `IntegrityError` → whole batch rolls back → **that client can never sync again until upgraded** | Nullable: benign. NOT NULL: **hard, permanent sync break** | — |

**Design conclusions, both binding:**

1. **`business_date` MUST be nullable**, with the read-time `COALESCE` of §2.3. This is not a style preference; a NOT NULL column turns every un-upgraded client into a bricked sync peer (case C). NOT NULL + `server_default` does **not** save you, because the value is explicitly present as `None` in the insert dict.
2. **Case A is unfixable at the merge layer** and must be closed at the transport layer. The offline path already has an exact-match schema gate (`app/routes/offline.py:232-240` → `app/services/offline.py:61-69`). **`POST /api/sync/push` has NO schema gate at all** (`app/routes/sync.py:66-133` — the whole handler is rate-limit → size cap → decode → `parse_exchange` → `apply_merge`). Recommended: have the push route compare the batch header's `schema_version` (already carried, `merge.py:575`; already emitted by the client, `sync_client.py:363`) against `current_schema_version(session)` (`app/services/sync.py:225-235`) using the existing `offline.schema_version_ok` helper, and return a 409 with an RU message. A ~6-line change reusing two shipped functions that converts case A from silent loss into a loud, actionable refusal.

### 3.1 A pre-existing bug this analysis exposes

`CashMovement.currency` is **`nullable=False`** (`app/models.py:526-528`). By case C, an old-code client pushing a cash movement to today's server sends `currency: None` → `IntegrityError` → the entire push batch rolls back, permanently, for that client.

`needs verification` — smallest check: a test mirroring `tests/test_merge.py:662`, but inverted, on a current-schema session:

```python
def test_push_cash_movement_without_currency_to_current_db(session):
    record = _cash("cm-old", amount_cents=100, seq=1)
    record.pop("currency", None)
    _apply(session, [record])   # observe: IntegrityError, or a landed row?
```

If it raises, the fix is to make `merge._ledger_row` drop `None` values for columns that have a `server_default` — one line in one shared function. Route this to the roadmapper as a **Phase 0 / pre-work item**, because the `business_date` column definition depends on knowing whether "explicit None" or "server default" wins here.

---

## 4. Feature 2 — Reversal (storno)

### 4.1 Where the link lives: a column. For cash, there is no alternative.

**(Coordinator trap #2, verified.)** `payload` exists on `Operation` only (`app/models.py:374`). `CashMovement` has **no `payload` column** — its docstring says so explicitly: it "drops every stock-specific column (product_id, qty_delta, unit_cost_cents, unit_price_cents, **payload**, batch_id)" (`app/models.py:496-499`), and the column list at `:518-548` confirms it (id, category, amount_cents, currency, note, sale_id, author_id, device_id, seq, created_at, created_by, synced_at). **So a cash-reversal link cannot be a payload field. It must be a real column.**

| Option | Verdict |
|---|---|
| `Operation.payload["reverses_op_id"]` | **Rejected.** Zero migration, and there is a precedent (`returns.py:165` writes `payload={"origin_op_id": ...}`) — but (a) it is *structurally impossible* for cash, so it would force two different link mechanisms for one feature; and (b) the house rule reads `payload` in **Python**, never in SQL (`reports.py:153` does `(op.payload or {}).get("reason_code")`). The double-reversal guard needs `WHERE reverses_op_id = :id`, which against a `JSON` column means a dialect-generated, unindexable JSON-path expression or a full-table Python scan. |
| Abuse `CashMovement.note` (`String(300)`) to hold the origin id | **Rejected.** `note` is an operator-facing display field rendered in cash history (`partials/cash_history_rows.html`). Overloading it makes the link unqueryable and visible as noise. |
| Separate `reversals` table | **Rejected.** It would need its own `kind` in `RECORD_KINDS`/`KIND_TO_MODEL`/`_REFERENCE_INSERT_ORDER` (`merge.py:50-76,250-257`), its own FK ordering, idempotency semantics and trigger story — far more surface than a nullable column, for the same information. |
| **Nullable self-referencing column on each ledger table** | **Recommended.** Indexed equality, portable, one mechanism for both tables, and it mirrors `Operation.sale_id`/`batch_id`/`author_id` exactly (`models.py:379-398` — bare native column in the migration, `ForeignKey` only in the ORM for insert ordering + PG portability). Nullable, so §3 case C is benign. |

**New columns (2 more):** `operations.reverses_op_id` → `operations.id` (indexed, nullable) and `cash_movements.reverses_movement_id` → `cash_movements.id` (indexed, nullable). Both go through the §2.7 lockstep.

### 4.2 The reversal row is the SAME type with inverted values

Do **not** invent a `reversal` operation type or a `reversal` cash category. `OPERATION_TYPES` (`models.py:35-45`) is consumed by `history_view`'s membership guard (`operations.py:122`), `HISTORY_TYPE_COLUMNS` (`operations.py:41-49`, with an `assert` at `:49`), `STOCK_AFFECTING_TYPES` (`ledger.py:19-21`), and `OPERATION_TYPE_LABELS`. A new type would need entries in all of them and would still not net out of any existing aggregate.

**Writing the same type with inverted `qty_delta` and inverted money makes every existing report self-correct with zero query changes:**

- `sales_profit_report` (`reports.py:88-108`) — the reversing row's `-op.qty_delta` and negated `unit_price_cents` cancel the origin's contribution.
- `writeoff_report` (`reports.py:150-155`) — `qty = -op.qty_delta` nets the reason group to zero.
- `compute_stock` / `compute_batch_stock` (`ledger.py:139-168`) — pure `SUM(qty_delta)`, self-correcting.
- `cash_flow_report` (`finance_reports.py:123-131`) — reusing the **original category** (not a new one) keeps `CASH_BUCKETS` membership intact and preserves the D-05 reconciliation invariant (`finance_reports.py:115-118`).

### 4.3 Per-type reversal contract

New service `app/services/reversals.py`. All writes go through `record_operation` / `record_cash_movement` with `commit=False` + one closing `session.commit()` (the WR-03 pattern, `sales.py:282-320`). Returns the house `(result, errors)` tuple.

| Origin type | Compensating write | Notes |
|---|---|---|
| `receipt` | one `receipt` op, `qty_delta = -origin.qty_delta`, same `batch_id`, same `unit_cost_cents`/`unit_price_cents`, `reverses_op_id = origin.id` | Guard: `batch.quantity >= origin.qty_delta` |
| `writeoff` | one `writeoff` op, `qty_delta = -origin.qty_delta`, same `batch_id`, `payload` copied from the origin | Increases stock; no stock guard needed |
| `correction` | one `correction` op, inverted `qty_delta` | Negative origin → adds stock (no guard); positive origin → guard as for `receipt` |
| `transfer` | **two** ops in ONE transaction: `+N` on the source batch, `-N` on the dest batch, each carrying its own `reverses_op_id` pointing at its own counterpart | See §4.5 — the hard case |
| `sale` / `return` | **Not reversible.** `returns.register_return` (`returns.py:117-198`) already owns this, with a cap (`returnable_qty`, `:65-74`) and a symmetric cash debit (`:169-181`). A second mechanism would double-handle cash. Hide the History control for these two types. |
| `price_change`, `product_created`, `product_edited` | **Not reversible.** `qty_delta == 0` audit rows; nothing to compensate |
| manual `cash_movement` (`sale_id IS NULL`) | one movement, `amount_cents = -origin.amount_cents`, **same `category`**, **same `currency`**, `note` = a fixed RU storno string, `reverses_movement_id = origin.id` | Reuse the warn-but-allow negative-balance gate shape from `finance.py:171-184`, scoped to `origin.currency` |
| auto `cash_movement` (`sale_id IS NOT NULL`) | **Not reversible.** Owned by the sale/return write paths (`sales.py:310-317`, `returns.py:174-181`). Reversing it directly desynchronizes cash from the ledger |

### 4.4 Guards, all expressed as reads (no UPDATE anywhere)

```python
REVERSIBLE_TYPES = frozenset({"receipt", "writeoff", "correction", "transfer"})

# 1. Type allow-list — mirrors history_view's OPERATION_TYPES membership guard.
if origin.type not in REVERSIBLE_TYPES: refuse

# 2. Not a reversal itself (no reversal-of-a-reversal chains).
if origin.reverses_op_id is not None: refuse

# 3. Not already reversed — ONE indexed equality, no JSON, no scan.
already = session.scalar(
    select(func.count()).select_from(Operation).where(Operation.reverses_op_id == origin.id)
)
if already: refuse  # ALREADY_REVERSED_ERROR

# 4. Stock still present (only when the reversal REMOVES stock).
#    Batch.quantity is the cached projection every other guard already trusts
#    (sales.py:235, writeoffs.py:97, transfers.py:142).
if origin.qty_delta > 0 and batch.quantity < origin.qty_delta:
    refuse  # RU message naming the remaining quantity, per returns._over_cap_error
```

Guard 4 is a **hard refusal, never `confirm=1`-overridable** — same discipline as `MIXED_CURRENCY_ERROR` (`sales.py:202-203`), not the warn-but-allow oversell pattern. Reversing stock that has already been sold would drive the batch negative and silently corrupt the profit already booked against it.

Guard 3 has a race window (two tabs). It is not closable by `UNIQUE(reverses_op_id)`, because that column legitimately repeats across a transfer's two rows. Mitigation: accept the window (single operator, WAL-serialized writes) and let guard 4 catch the second attempt. Document it.

`record_operation`'s IN-01 soft-delete guard (`ledger.py:86-87`) raises `ValueError` — catch it and return an RU message, exactly as `returns.py:185-189` does.

### 4.5 The transfer case is genuinely hard — flag it for its own plan

A transfer writes **two** `transfer` ops (`transfers.py:176-191`) with **no link between them**. There is no group id, no shared payload key. `/history` shows a transfer as its outbound row (`transfers.py:209` filters `qty_delta < 0`). To reverse "the transfer", the service must find the sibling.

The only reliable handle in existing data: both rows are written in one transaction on one device, and `next_seq` = `max(seq) + 1` with autoflush ensuring the first is visible to the second (`ledger.py:24-34` docstring, `:122`). So **the sibling is `(device_id == origin.device_id, seq == origin.seq + 1)`**, verifiable by asserting `type == "transfer"`, matching `product_id`, and `qty_delta == -origin.qty_delta`.

Recommendation:
- **New transfers:** stamp `payload={"transfer_group_id": <uuid>}` on both rows. `payload` exists on `Operation` (`models.py:374`) and is already a synced column carried verbatim — **zero schema change**. Future reversals resolve the pair trivially.
- **Historical transfers:** use the `seq ± 1` probe with a hard "exactly one match, all three assertions pass" requirement; otherwise refuse with an RU message telling the operator to compensate manually. Do not guess.

This is the one part of the reversal feature that can quietly produce a wrong result, and it deserves an explicit success criterion.

### 4.6 Rendering «сторно операции X» in История

`history_view` (`operations.py:93-116`) already selects six entities. Adding a self-outerjoin for the origin is safe (`reverses_op_id` → at most one origin, no fan-out). The *other* direction — "has this row been reversed?", which drives whether the control is shown — should **not** be a join. Do one batched probe over the page's ids after `rows` is materialized (`operations.py:170`):

```python
page_ids = [op.id for op, *_ in rows]
reversed_ids = set(session.scalars(
    select(Operation.reverses_op_id).where(Operation.reverses_op_id.in_(page_ids))
).all())
```

One extra query per page, portable, no fan-out, comfortably under SQLite's ~999 bound-param cap (page size 20, `pagination.LIST_PAGE_SIZE`).

Surfaces: `app/templates/partials/history_rows.html` (desktop) and `app/templates/mobile_partials/history_cards.html` (mobile). The control is a POST behind the CSRF token already carried on `base.html`'s `hx-headers` (mechanism documented at `app/routes/sync.py:212-213`), with a confirm step.

### 4.7 Does the reversal carry the ORIGINAL's business date? — CONFIRMED, with the reasoning

The coordinator relays a claim from another researcher: *a reversal should carry the original operation's business date, which makes back-dating a hard prerequisite for storno.* Tested against this codebase:

**The existing precedent points the other way, and that is correct — because it is a different kind of event.** `returns.register_return` copies the origin's **frozen money** (`unit_price_cents`/`unit_cost_cents`, `returns.py:161-162`, decision D-07) but takes a **fresh** `created_at` from `record_operation`. It does not inherit the origin's time. That is right for a return: a customer physically bringing goods back today *is a new business event that happened today*.

**A storno is not a new business event — it is an assertion that the origin never happened.** The decisive argument is arithmetic, from §4.2: the compensating row nets out the origin *only inside a report period that contains both rows*. If the operator stornos a receipt that was back-dated to last month and the storno lands on today, then:
- last month's `sales_profit_report` / `cash_flow_report` stays wrong **forever**, and
- this month's numbers acquire a phantom movement that never happened here.

That is precisely the drift this milestone exists to eliminate. So:

> **Decision: a reversal inherits `origin.business_date` by default.** `created_at` is still stamped fresh (it is the audit record of *when the operator issued the storno* — that information must not be lost). The operator may override the business date only if the write form exposes it; the default must be the origin's.

**Consequence for ordering — the claim is CONFIRMED and it is a hard, not soft, prerequisite:**

- The reversal service cannot inherit a field that does not exist, so `operations.business_date` and `cash_movements.business_date` must be in the schema first (Phase 1 below).
- Stronger: the *readers* must be switched too (Phase 2). If reports still filter on `created_at` while the storno carries an inherited `business_date`, the storno lands in today's report by `created_at` and the origin's period is still never corrected — the feature would ship visibly broken.
- **This kills the alternative of shipping reversal before back-dating.** It also removes the previously-open question about which date a storno should carry.

---

## 5. Feature 3 — Currency: RE-SCOPED from a phase to a finishing plan

**Explicit re-scope.** `.planning/ROADMAP.md:327-349` describes currency as "a full phase, not a field addition". That was true on 2026-08-09 and is not true now. The data model, the write-path guards, the report scoping and the render *mechanism* are all shipped. **What remains is a finishing plan: one template sweep plus four service kwargs.** It has no schema work, no migration, and therefore no ordering claim over anything else in the milestone.

Shipped (do not re-plan): `Warehouse.currency` + `CashMovement.currency` + `Batch.cost_cents` (migrations 0023/0024/0025/0026); `CURRENCIES`/`DEFAULT_CURRENCY`/`currency_symbol`/`format_money` (`core.py:56-86`); the `money` Jinja filter + `CURRENCIES` global (`routes/__init__.py:221-227`); currency-scoped `sales_profit_report`, `cash_expense_total`, `cash_flow_report`, `stock_valuation`, `compute_balance`, `cash_history_view`, `dashboard_context`; the mixed-currency basket reject (`sales.py:199-204`); the cross-currency transfer cost requirement (`transfers.py:104-125`); the «Валюта» CSV column (`export.py:128,144,216`); currency switchers on `/reports/sales`, `/finance` and Главная.

### 5.1 Gap A — the money render was never applied (the big one)

`format_money` is registered as `money` but is used in **exactly one template**: `app/templates/partials/cash_balance.html`. There are **103 remaining `| cents` renders across 42 templates**.

**Answer to "how should `format_cents` become currency-aware without touching every call site": it should not.** `format_cents` has no way to know which currency the number is in, and defaulting it would *silently mislabel* amounts — strictly worse than no symbol. The two-filter split already in the codebase is correct and self-documenting (`core.py:79-86`). What is missing is the per-surface decision, which needs a rule, not a mechanism:

> **Rule:** `| cents` is correct only where the surrounding page is already scoped to one currency by a mandatory filter that is visible on screen. Everywhere an amount can sit next to an amount from a different warehouse, use `| money(<that row's currency>)`.

Applying the rule — the three classes, with the **specific templates** in each:

**Class 1 — correct by design, leave `| cents` (~45 renders, 9 templates).** The page carries `currency` in context and shows a switcher:
`partials/dashboard_tiles.html` (12), `mobile_pages/home.html` (13), `partials/sales_report_results.html` (6), `partials/finance_tiles.html` (5), `partials/cash_flow_report.html` (4), `pages/home.html` (2), `partials/cash_history_rows.html` (1), `partials/cash_negative_balance.html` (1), `mobile_partials/cash_history_cards.html` (1).
Action: verify the currency label is actually visible on each page; no filter change.

**Class 2 — GENUINE GAPS, must switch to `| money(...)` (~50 renders, 29 templates).** An amount stands alone and the operator cannot tell its currency:

| Surface group | Templates | Renders |
|---|---|---|
| История (highest-value fix — every currency interleaves here today) | `partials/history_rows.html` (5), `mobile_partials/history_cards.html` (4) | 9 |
| Batch pickers | `partials/batch_picker.html` (1), `partials/sale_batch_pick.html` (1), `partials/receipt_batch_chooser.html` (1), `mobile_partials/batch_card_picker.html` (1), `mobile_partials/receipts_step_batch.html` (1), `mobile_partials/transfers_step_batch.html` (1) | 6 |
| Product / batch cards | `pages/product_form.html` (5), `partials/product_rows.html` (2), `pages/batch_form.html` (2), `mobile_pages/batch_edit.html` (2), `mobile_partials/search_product_detail.html` (2) | 13 |
| Customer views (cross-currency by construction) | `partials/customer_insights.html` (4), `partials/purchase_history.html` (2) | 6 |
| Sale / return flows | `partials/sale_form.html` (1), `partials/sale_lookup.html` (1), `partials/sale_price_warning.html` (1), `partials/return_form.html` (1), `mobile_partials/sale_step_product.html` (1), `mobile_partials/sale_step_qty_price.html` (1), `mobile_partials/sale_warning.html` (1), `mobile_partials/return_confirm.html` (1) | 8 |
| Recent feeds | `partials/recent_sales.html` (2), `partials/receipt_rows.html` (2) | 4 |
| Other | `pages/categories.html` (2), `partials/price_history.html` (1), `pages/reports_expiry.html` (1), `mobile_pages/reports_expiry.html` (1) | 5 |

**Class 3 — catalog reference prices, leave `| cents` (~7 renders, 4 templates).** Oriflame list prices with no warehouse dimension: `partials/dictionary_rows.html` (2), `pages/catalog_detail.html` (2), `partials/product_price_autofill.html` (2), `partials/receipt_lookup.html` (1). Label the column once as the catalog reference price.

**Where each row's currency comes from — mostly free:**
- История: `history_view` already outer-joins `Batch` → `Warehouse` (`operations.py:96,102`) and returns `"warehouse"` in every row dict (`operations.py:177`). Use `row.warehouse.currency if row.warehouse else DEFAULT_CURRENCY` — the same fallback rule as `operation_currency_clause` (`reports.py:26-38`). **Zero query changes.**
- Batch pickers / batch cards: the batch is in hand; `Batch.warehouse_id` is NOT NULL (`models.py:263`), so a `Warehouse` lookup always resolves. Some picker services may not currently load it — `needs verification` per template.
- Product cards: `Product.cost_cents`/`sale_cents` are card-level, not warehouse-level, so they have **no currency**. **Operator decision needed:** label them as `DEFAULT_CURRENCY` reference prices, or drop the symbol and label the field. Do not guess.

**Ship a tripwire, not just a sweep:** a test asserting no template in the Class-2 list contains `| cents`. Otherwise this regresses the first time someone adds a row.

### 5.2 Gap B — read surfaces that still sum across currencies

| Site | What it sums | Fix |
|---|---|---|
| `app/services/customers.py:407,415-416` (`_spend_stmt` → `spend_totals`, `spend_view`) | Customer month/quarter/year spend, `SUM(-qty_delta * unit_price_cents)` across **all** currencies | Add a `currency` kwarg + the outer-join chain + `operation_currency_clause` (`reports.py:21-38`). The single most misleading number left in the app. |
| `app/services/customers.py:352` + `partials/purchase_history.html` | Purchase history rows | Render with `| money(...)` per row (needs the warehouse join) |
| `app/services/reports.py:127-171` (`writeoff_report`) | Quantities only, but the template may show cost | Add the `currency` kwarg for consistency |
| `app/services/reports.py:186-209` (`top_selling_products`) | Units only — no money | Optional; add for filter consistency |
| `app/services/operations.py:52-195` (`history_view`) | **No currency scoping at all.** RUB, UAH and EUR rows interleave with no marker | Preferred: rely on the per-row `| money(...)` marker from §5.1 so the operator still sees everything in one list. An optional `currency` filter kwarg is a nice-to-have on top. |

### 5.3 Gap C — where the mandatory currency filter belongs (already answered by shipped code)

**Route-level allow-list → service kwarg. Never the template.** The shipped pattern:

```python
def _clean_query_currency(raw: str) -> str:
    return raw if raw in CURRENCIES else DEFAULT_CURRENCY
```

…appears **five times, verbatim**: `app/routes/reports.py:33-36`, `app/routes/home.py:22-27`, `app/routes/finance.py:46-51`, `app/routes/mobile_home.py:21-26`, `app/routes/mobile_finance.py:50-55`. The service then re-normalizes independently for *form* input (`app/services/finance.py:140-144`, `warehouses._clean_currency`).

**Recommendation:** collapse the five copies into one helper in `app/core.py`, beside `CURRENCIES`. Every new currency-scoped surface (§5.2) would otherwise make it a sixth and seventh copy — a textbook "second mechanism for a job the project already solves". Keep the service-layer normalization separate: it handles blank-means-default for form input, a different contract.

### 5.4 Gap D — mixed-warehouse basket: nothing to build, one thing to check

`register_sale` rejects it before any write (`sales.py:199-204`), non-overridable, verified live in the quick task (20/20 scenarios, `260810-2g3-SUMMARY.md:87-89`). The error lands under the `"basket"` key. **`needs verification`:** does the *mobile* sale wizard render `errors.basket`? Smallest check: POST a two-warehouse basket to the mobile sale finalize endpoint and assert the Russian message appears in the response body.

---

## 6. Feature 4 — Mobile editing

The smallest feature by far. The precedent is exact and shipped: `app/routes/mobile_batches.py:19` (`GET /m/batches/{id}/edit`) + `:36` (`POST /m/batches/{id}`), which imports `update_batch` from the shared service and adds **no** second validation path.

**New components (routes + templates only, zero service changes):**

| New route | Mirrors | Calls (unchanged service) |
|---|---|---|
| `GET /m/products/{id}/edit` | `app/routes/products.py:263` | `catalog.get_product` + `catalog.category_options` |
| `POST /m/products/{id}` | `app/routes/products.py:283` | `catalog.update_product` (`app/services/catalog.py:162`) |
| `GET /m/customers/{id}/edit` | `app/routes/customers.py:207` | the customer read used there |
| `POST /m/customers/{id}` | `app/routes/customers.py:225` | `customers.update_customer` (imported at `app/routes/customers.py:21`) |

New templates: `mobile_pages/product_edit.html`, `mobile_pages/customer_edit.html`.
Entry points: a link on `mobile_partials/search_product_detail.html` (whose header comment currently declares itself read-only) and on the `mobile_pages/customers.html` cards.

**Why this must go last:** `update_product` writes `price_change` and `product_edited` ledger rows through `record_operation` (`catalog.py:281,290`), so the mobile form inherits whatever `business_date` contract Phase 1 lands. And the product edit form renders five money fields (`pages/product_form.html`, Class 2 above), so it needs §5.1's render decision settled first — otherwise it ships with the wrong render and gets redone.

Follow `mobile_batches.py`'s module shape rather than bolting POST handlers onto `mobile_products.py`/`mobile_customers.py`, whose docstrings declare a "one plain full-page GET, no HX-partial branch" contract.

---

## 7. New vs. modified — the explicit split

### NEW components

| Component | File | Feature |
|---|---|---|
| `business_date_bounds()` | `app/core.py` (beside `local_day_bounds_utc:108`) | Back-dating |
| `business_date_expr(model)` | `app/services/reports.py` (beside `operation_currency_clause:21`) | Back-dating |
| Migration: 2 × `business_date` + 2 × `reverses_*_id` + tz-correct backfill + trigger v4 (both dialects, both `downgrade()` halves) | `alembic/versions/00NN_*.py` | Back-dating + reversal |
| `reversals.py` — per-type reversal service | `app/services/reversals.py` | Reversal |
| Reversal routes (desktop + mobile) | `app/routes/reversals.py`, `app/routes/mobile_reversals.py` | Reversal |
| 4 mobile edit routes + 2 templates | new module(s) following `mobile_batches.py` | Mobile editing |
| Shared `clean_currency()` (collapsing 5 copies) | `app/core.py` | Currency (cleanup) |
| Push-route schema gate | `app/routes/sync.py` (reusing `offline.schema_version_ok`) | Sync safety |
| Class-2 `| cents` tripwire test | `tests/` | Currency |

### MODIFIED components

| File | Change |
|---|---|
| `app/models.py:348-403` (`Operation`), `:493-548` (`CashMovement`) | +2 columns each |
| `app/db.py:37-85` | `NEW.business_date` / `NEW.reverses_*_id` in both `*_no_update` bodies (LOCKSTEP) |
| `tests/test_append_only_cursor.py:40-73` | Both `IMMUTABLE_*_COLUMNS` frozensets |
| `app/services/ledger.py:37-136` | +`business_date` kwarg, stamped at `:110-125` |
| `app/services/finance.py:48-98` | +`business_date` kwarg |
| `app/services/reports.py:72,145,201,224` | Period filters → `business_date_expr`; +`currency` kwarg on `writeoff_report` |
| `app/services/finance_reports.py:33,126` | Period filters → `business_date_expr` (must move together, D-05 invariant) |
| `app/services/customers.py:352,407,415` | Period filter → `business_date_expr`; **+ currency scoping** |
| `app/services/operations.py:30-32,151-154,171-184` | Order, date filter, reversal-state per row |
| `app/services/dashboard.py:75-122` | Signature: `start_iso/end_iso` → `start_day/end_day` |
| `app/services/export.py:211-212` | Period filter |
| `app/services/transfers.py:176-191` | `payload={"transfer_group_id": ...}` on both rows |
| Write services offering a date field: `receipts.py`, `writeoffs.py`, `corrections.py`, `transfers.py`, `sales.py` | Pass `business_date` through to `record_operation` |
| `app/routes/reports.py`, `history.py`, `finance.py`, `home.py`, `mobile_*` | Pass dates instead of UTC bounds; date input on write forms; collapse `_clean_query_currency` |
| 29 templates (Class 2, §5.1) | `| cents` → `| money(...)` |
| `partials/history_rows.html`, `mobile_partials/history_cards.html` | Reversal control + «сторно операции X» + currency marker + business-date column |

---

## 8. Data flow changes

### Write flow (back-dated + reversal)

```
Operator picks a date (defaults to today, local)
   ↓
Route: parse Form(date) — pass the raw string through, do NOT validate here
   ↓
Service (receipts/writeoffs/corrections/transfers/sales/reversals):
   validate ISO + reject future  →  errors dict, ZERO writes on failure
   reversals ONLY: business_date defaults to origin.business_date (§4.7)
   ↓
record_operation(..., business_date=<local ISO date>)
   created_at = utcnow_iso()          ← audit, UNCHANGED (when the storno was issued)
   business_date = supplied/inherited ← NEW, reports read this
   seq / device_id / synced_at        ← UNCHANGED (sync identity)
   ↓
ONE session.commit()  (WR-03: staged with commit=False, one close)
```

### Read flow (period reports)

```
Route: _resolve_period → (from_date, to_date) as date objects   [already exists]
   ↓
business_date_bounds(from_date, to_date) → ('2026-09-01', '2026-09-04')
   ↓                              [replaces local_day_bounds_utc for reports ONLY]
Service: .where(business_date_expr(Operation).between(start, end),
                operation_currency_clause(currency))
   ↓                              [both shared helpers, never inlined]
Numbers land in the period the operation ACTUALLY happened, in ONE currency —
and a storno lands in the SAME period as the row it cancels (§4.7)
```

### Sync flow (unchanged mechanically, new failure surface)

```
Client: synced_at IS NULL → collect_push_records → KIND_TO_FIELDS projection
   ↓ NDJSON + header{format_version, schema_version, payload_sha256}
Server: [NEW] schema_version gate → 409 on mismatch    ← closes §3 case A
   ↓ parse_exchange (no DB touch) → apply_merge (never commits)
   ↓ _ledger_row: {col: data.get(col) for col in SERVER's KIND_TO_FIELDS}
Route owns the ONE transaction → all-or-nothing rollback
```

---

## 9. Anti-patterns to avoid (project-specific)

**1. Adding a ledger column without the trigger.** The trigger enumerates columns by name (`app/db.py:41-56,64-78`); an unlisted column is freely mutable — the ledger fails *open*, silently. Migration `0026` exists solely because `0024` did this (`0026:7-13`). `tests/test_append_only_cursor.py:246` is the tripwire; do not let it be the discovery mechanism.

**2. Making the new ledger columns `NOT NULL`.** §3 case C: an old client's push sends explicit `None`, `server_default` does not apply, `IntegrityError` rolls back the whole batch — permanently, for that client. `CashMovement.currency` may already have this bug (`models.py:526`).

**3. Reusing `created_at` for the business date, or vice versa.** `created_at` is the audit stamp *and* the tie-broken display order. `business_date` is a report dimension. Conflating them is exactly the bug this milestone exists to fix.

**4. Putting the cash-reversal link in `payload` or `note`.** `CashMovement` has **no `payload` column** (`models.py:496-499`, column list `:518-548`), and `note` is an operator-facing display field. Use a real column.

**5. Inventing a `reversal` operation type or cash category.** A new type needs entries in `OPERATION_TYPES`, `HISTORY_TYPE_COLUMNS` (with its `assert` at `operations.py:49`), `STOCK_AFFECTING_TYPES` and `OPERATION_TYPE_LABELS` — and *still* would not net out of any aggregate. Same type + inverted values makes every existing report self-correct for free. A new cash category breaks `CASH_BUCKETS` membership and the D-05 reconciliation invariant.

**6. Letting a storno land on today when it cancels a back-dated row.** §4.7: the origin's period stays wrong forever and today acquires a phantom movement.

**7. Making `format_cents` currency-aware.** It cannot know the currency. A default would mislabel amounts silently — worse than no symbol. Choose per surface, per §5.1's rule.

**8. Reversing a sale.** `returns.py` owns it, with a cap and a symmetric cash debit. A second path double-handles cash.

**9. Filtering on `payload` in SQL.** The house pattern reads `payload` in Python (`reports.py:153`). Use a real column for anything that needs a `WHERE`.

**10. Backfilling `business_date` as `substr(created_at, 1, 10)`.** That is the UTC day; reports bucket by the local day. Every past-period number would silently shift.

**11. Re-planning the currency phase from `.planning/ROADMAP.md:327-349`.** ~75% is shipped; §5 is a finishing plan, not a phase.

**12. Copying `_clean_query_currency` a sixth time.** It is already duplicated five times verbatim.

---

## 10. Build order — challenged and revised

### The proposed order

1. Back-dated operations → 2. Currency → 3. Reversal → 4. Mobile editing

### What the code says

**Dependency 1 (real, and it reorders things):** `business_date` and `reverses_*_id` are both nullable columns on the **same two append-only tables**. Each needs a migration, a DROP/CREATE of both `*_no_update` triggers in **two dialects** with matching `downgrade()` halves, a lockstep edit to `app/db.py::APPEND_ONLY_TRIGGERS`, edits to both `IMMUTABLE_*_COLUMNS` frozensets, and — across a fleet of self-updating v4.0 clients — a **window during which some peers are on the old schema** (§3). Doing this twice pays the highest-risk cost twice and opens two skew windows.

**Dependency 2 (real, and now HARD — §4.7):** a storno must carry the origin's business date, and reports must already read that column, or the feature ships visibly broken. **Reversal cannot precede back-dating — schema *or* readers.** Confirmed against the codebase; this also retires the previously-open "which date does a storno carry" question.

**Dependency 3 (real):** the reversal control, the История currency marker, and the business-date filter/order **all** modify `history_view` (`operations.py`), `history.py`, `history_rows.html` and `history_cards.html`. Splitting them across three non-adjacent phases means editing the same four files three times.

**Dependency 4 (real):** mobile edit forms render money (`pages/product_form.html`, Class 2) and write ledger rows via `update_product` → `record_operation` (`catalog.py:281,290`). It genuinely must come last. **Confirmed.**

**Dependency 5 (does NOT hold as stated):** "Currency must precede Reversal because История must render sums with a currency." The currency data model is shipped; only the render remains, and the render is independent of the reversal *logic*. What is true is the weaker, template-level Dependency 3.

**Dependency 6 (does NOT hold):** "Back-dating first because it is a ledger schema change every report reads." True in spirit — but the *currency* phase is no longer a schema change at all, so it has no ordering claim left of its own.

### Recommended order

| # | Phase | Why here |
|---|---|---|
| **0** | **Sync-skew hardening** (small) — resolve the §3.1 `nullable`/`server_default` question with the inverted merge test; add the `schema_version` gate to `POST /api/sync/push` reusing `offline.schema_version_ok` | Everything after adds ledger columns. The answer **determines the column definitions** in Phase 1; doing it later risks a corrective migration. ~1 plan. |
| **1** | **Ledger schema: `business_date` + `reverses_*_id`, ONE migration, ONE trigger rewrite** — columns, tz-correct backfill, trigger v4 (2 dialects), `APPEND_ONLY_TRIGGERS`, both `IMMUTABLE_*` constants, `record_operation`/`record_cash_movement` kwargs, `business_date_bounds` + `business_date_expr`. The reversal columns land **unused but guarded**. | Pays the trigger/migration/skew cost **once**. The project's own "schema before its readers" rule (v1.1 Phase 9, v2.0 Phase 18) applied to both schema changes at once. |
| **2** | **Back-dating readers + UI** — switch the 9 period call sites, `_DEFAULT_ORDER`, `dashboard` signatures, routes, and the date input on every write form (desktop + mobile) | Pure consumer of Phase 1. The backfill regression gate (§2.6) is this phase's hard success criterion. Reversal (Phase 4) depends on this being done, per §4.7. |
| **3** | **Currency finishing plan** (not a phase) — the Class-2 `| money(...)` sweep + tripwire test, currency-scope `customers.spend_totals`/`purchase_history`/`writeoff_report`, currency marker in История, collapse the 5 `_clean_query_currency` copies | No schema work. Must precede Phase 5 (mobile forms render money) and is best adjacent to Phase 4 (both edit the История templates). Could be run in parallel with Phase 2 by a second executor — the file scopes are disjoint except for the История templates, so **do not** parallelize those two. |
| **4** | **Reversal** — `reversals.py`, per-type contract, four guards, business-date inheritance, transfer sibling resolution + `transfer_group_id` on new transfers, desktop + mobile История controls, «сторно операции X» | Columns exist (1); business date flows and is read (2, hard prerequisite per §4.7); История already renders currency (3), so its templates are edited once more, not three times. |
| **5** | **Mobile editing** | Unchanged from the proposal — last, against the finished feature set, with the money render settled. v1.1 UI-01 precedent. |

### If the roadmapper wants to keep four phases

Merge 0 into 1, and treat 3 as a plan inside another phase rather than a phase of its own. The **two changes that must not be dropped**: (a) land `reverses_*_id` in the same migration as `business_date`; (b) keep reversal strictly after the back-dating *readers*, not merely after the schema. Everything else in this reordering is optimization; those two are correctness.

---

## 11. Open questions for the operator (do not guess)

1. **Product card prices have no warehouse, so no currency.** Label them as reference prices in `DEFAULT_CURRENCY`, or render without a symbol under a labelled field? (`pages/product_form.html`, `partials/product_rows.html`)
2. **Warehouse "last receipt date"** (`warehouses.py:100`) — technical or business date?
3. **Should История gain a currency *filter*, or only per-row currency *markers*?** The marker alone keeps everything visible in one list; a filter matches the "mandatory currency filter" rule stated for reports.
4. **May the operator override a storno's inherited business date?** §4.7 fixes the *default* (inherit). Whether the reversal form exposes an editable date at all is a UX decision.

*(The earlier question "which business date does a reversal carry?" is now decided in §4.7 — inherit the origin's — and is no longer open.)*

## 12. Anything I could not verify

| Item | `needs verification` — smallest check |
|---|---|
| Explicit `None` vs `server_default` in `session.execute(insert(model), rows)` (§3.1) | The inverted merge test in §3.1 — 6 lines |
| Backfill UPDATE not tripping the pre-rewrite trigger (§2.6) | Run the migration against a copy of the s1 dump; assert rows-updated == rows-total |
| Mobile sale wizard renders `errors.basket` (§5.4) | POST a two-warehouse basket to the mobile finalize endpoint; grep the response for `MIXED_CURRENCY_ERROR` |
| Which batch-picker services already load `Warehouse` (§5.1) | Per-template read of the six picker partials + their route context builders |
| Historical transfer pairs really are `seq`-adjacent in production data (§4.5) | `SELECT device_id, seq, qty_delta FROM operations WHERE type='transfer' ORDER BY device_id, seq` on the s1 dump; assert every row pairs with `seq±1` |
| Deployment state of the currency commits on s1 | I ran no shell this session (the mandatory `robust-console-commands` skill is unavailable to this agent), so `git log` and `alembic current` on s1 were not executed. Working-tree evidence is unambiguous; the coordinator independently confirmed `cdcec66` is an ancestor of HEAD. Server migration state is still unverified. |

---

## Sources

- Working tree at `E:\dev\myorishop`, branch `main`, commit `b4ca98c` — every `path:line` above was read directly (HIGH)
- `.planning/quick/260810-2g3-currency-correctness-part-2-per-currency/260810-2g3-SUMMARY.md` — the shipped currency scope, its 5 locked decisions, and its 20/20 live-HTTP verification (HIGH)
- Coordinator's mid-task correction (2026-09-04) — `cdcec66` ancestry and the 8 follow-on `feat(cur)` commits; independently consistent with the working-tree evidence (HIGH)
- `.planning/ROADMAP.md:327-410` — the four backlog entries, now partly stale (documented in §0)
- `.planning/PROJECT.md` — milestone scoping, key decisions, phase-ordering precedents (v1.1 Phase 9, v2.0 Phase 18, v1.1 UI-01)
- `tests/test_merge.py:644-694`, `tests/test_append_only_cursor.py:37-290` — the pinned contracts this design must not break (HIGH)

---
*Architecture research for: v5.0 Corrections, Dates & Currency — integration into an existing append-only synced ledger*
*Researched: 2026-09-04*
