# Stack Research

**Domain:** Local-first warehouse inventory (FastAPI + SQLAlchemy + SQLite/PostgreSQL + HTMX), milestone v5.0
**Researched:** 2026-09-04
**Confidence:** HIGH

## Verdict

**No new runtime dependencies. No new dev dependencies. No version bumps.**

All four v5.0 features (back-dated operations, per-warehouse currency, one-tap reversal, mobile card editing) are buildable with the exact `pyproject.toml` that is locked today. Every capability they need — ISO date storage, currency-aware money rendering, dual-dialect migrations on a trigger-guarded append-only table, deterministic "today" in tests — already exists in this repo as a working, tested precedent. The research work below is mostly about **naming those precedents so each phase reuses them instead of reaching for a library.**

---

## Ground truth first: what is already shipped

The v5.0 milestone context and `.planning/ROADMAP.md:327-349` / `OPEN-WORK-AUDIT-2026-09-04.md` are **stale on currency and on the migration count**. Verified by reading the code and `git log` on 2026-09-04:

| Claim in the planning notes | Reality in the code | Evidence |
|---|---|---|
| "22 alembic migrations" | **26** migrations, head is `0026` | `ls alembic/versions` |
| Phase 999.1 (currency) is BACKLOG, not started | Schema + core helpers **already shipped** 2026-08-10 | commit `cdcec66` `feat(cur): per-warehouse currency (RUB/UAH/EUR)`, ancestor of HEAD (`git merge-base --is-ancestor` → YES) |
| "`format_cents` renders `12,50` with no currency symbol anywhere" | `CURRENCIES`, `DEFAULT_CURRENCY`, `currency_symbol()`, `format_money()` exist | `app/core.py:56-86` |
| "money render needs a currency-aware filter" | The `money` Jinja filter **is registered** | `app/routes/__init__.py:227` |
| `Warehouse.currency` does not exist | Exists, `String(3)` NOT NULL, backfilled `RUB` | `app/models.py:214-220`, migration `0023` |
| — | `CashMovement.currency` also exists, plus its append-only trigger guard | `app/models.py:524-527`, migrations `0024`, `0026` |

What is genuinely still **open** on currency, measured in the code:

- **Render adoption:** 42 template files still use the bare `|cents` filter; exactly **1** uses `|money`. The filter exists; almost nothing calls it.
- **Warehouse dimension in reports:** unchanged — `services/reports.py`, `services/dashboard.py`, `services/finance.py` still have no warehouse concept.
- **Basket currency mixing:** unchanged — `services/sales.py` still has no warehouse concept.

Truly not started (**zero** occurrences of `business_date`, `reversal`, `storno`, `сторно` in `app/`):

- Back-dated operations — no column, no service argument.
- One-tap reversal — nothing.

**Consequence for the roadmap:** Phase 2 (currency) is materially smaller than the audit estimated — it is a *render-adoption + report-dimension* phase, not a schema phase. Re-scope it before planning. Confidence: HIGH (read from code, not from notes).

---

## Recommended Stack

### Core Technologies (all already installed — no change)

| Technology | Version | Purpose in v5.0 | Why it is sufficient |
|------------|---------|-----------------|----------------------|
| Python stdlib `datetime.date` | 3.13 | Parse/validate/format the operator-supplied business date | `date.fromisoformat()` validates and `strftime("%d.%m.%Y")` renders; both already used by `format_ru_date` (`app/core.py:89-99`). No date library adds anything here. Confidence: HIGH |
| SQLAlchemy `String(10)` ISO text | 2.0.51 (locked) | Storage type for the business date | The project's established date convention: `Batch.expiry` (`app/models.py:266`) and `ActiveCatalog.close_date` (`:243`) are both `String(10)`. Fixed-width zero-padded ISO-8601 sorts lexicographically == chronologically on both dialects. Confidence: HIGH |
| Alembic | 1.18.5 (locked) | The business-date column + trigger-guard migrations | Ships everything needed; the dual-dialect trigger pattern is already written twice in this repo (`0018`, `0026`). Confidence: HIGH |
| `app.core.format_money` / `currency_symbol` | in-repo | Currency-aware money render | Hand-rolled, 8 lines, already registered as the `money` Jinja filter. Confidence: HIGH |
| pytest + `monkeypatch` | 9.1.1 (locked) | Deterministic "today" for period/boundary tests | The repo already has two proven idioms (below). Confidence: HIGH |
| httpx `TestClient` | 0.28.x (locked) | Route-level tests for the new mobile edit pairs and the storno control | Unchanged from every prior phase. Confidence: HIGH |
| `<input type="date">` (native HTML) | — | Business-date entry, desktop + mobile | Always posts ISO `yyyy-mm-dd` regardless of browser locale — already relied on for `Batch.expiry` (`app/models.py:264-265`). No JS date picker, no client-side date library, no CDN. Confidence: HIGH |

### Supporting Libraries

**None.** This section is intentionally empty. See "What NOT to Use" for why each candidate was rejected.

### Development Tools

| Tool | Change | Notes |
|------|--------|-------|
| Ruff 0.15.x | none | — |
| uv 0.11.x | none | `uv sync` output is unchanged by this milestone |
| GitHub Actions CI | none | `.github/workflows/ci.yml` already runs the suite twice: SQLite (no `DATABASE_URL`) and PostgreSQL 17 service container (`DATABASE_URL=postgresql+psycopg://...`). Every dual-dialect claim below is enforceable there today. Confidence: HIGH |

## Installation

```bash
# Nothing to install. The locked dependency set is unchanged:
uv sync
```

If a phase plan proposes `uv add <anything>` for these four features, treat it as a scope error and reject it.

---

## Question 1 — Date handling: `String(10)` ISO text vs `sqlalchemy.Date`

**Recommendation: `String(10)` ISO text. `sqlalchemy.Date` would break sync. Confidence: HIGH (verified by executing code, below).**

### Why `sa.Date` is disqualified — two hard failures, both proven

**Failure 1 — it breaks the sync wire format.**
`app/services/sync.py:106` and `app/services/sync_client.py:330` build each record as
`data = {field: getattr(row, field) for field in merge.KIND_TO_FIELDS[kind]}`
and `app/services/merge.py:568` serializes it with `json.dumps(...)` — **no `default=` encoder**. `KIND_TO_FIELDS` is derived from the model mapper columns (`merge.py:80-83`), so a new column joins the wire format automatically. A `sa.Date` column yields a `datetime.date` object:

```
json.dumps(date) -> TypeError Object of type date is not JSON serializable
```

(executed locally, 2026-09-04). Adopting `sa.Date` therefore forces a custom JSON encoder *and* a matching decoder in the merge path — new machinery in the most safety-critical module in the project, for zero gain. A `String(10)` value is already a JSON string.

**Failure 2 — it fails asymmetrically across the two dialects, i.e. it breaks on the client and passes on the server.**
Executed locally against SQLAlchemy 2.0.51:

```
sqlite  Date bind '2026-09-04'      -> TypeError: SQLite Date type only accepts Python date objects as input.
sqlite  Date bind date(2026,9,4)    -> '2026-09-04'
pg      Date bind_processor          -> None      (raw value handed to psycopg; PG casts the string)
```

So a query written as `.where(Operation.business_date >= "2026-09-01")` — the natural thing to write, and the shape every existing report filter already uses against `created_at` — **works on PostgreSQL (s1) and raises `TypeError` on SQLite (every operator's machine)**. That is the worst possible failure mode for this project: green on the server, red on the client, and only at runtime. `String(10)` has no bind processor on either dialect and behaves identically.

### What does *not* break with `String(10)`

- **Sorting.** ISO-8601 `yyyy-mm-dd` is fixed-width and zero-padded, so byte order == chronological order. SQLite compares TEXT with BINARY collation; PostgreSQL uses the database collation, but with the hyphens at identical offsets and only ASCII digits varying, every collation (including punctuation-ignoring glibc/ICU ones) reduces to the same digit-by-digit comparison. The project already bets on this for `created_at` (`String(32)` ISO, `app/core.py:20-25`) and it has been running on PostgreSQL in production on s1 since 2026-07-20. Confidence: HIGH.
- **Filtering by period.** Business-date filters are pure string range comparisons: `business_date >= '2026-09-01' AND business_date <= '2026-09-30'`. No SQL date function on either dialect, so nothing dialect-specific enters the query. Portable ORM only, as the project rule requires.
- **Grouping by month.** Prefer Python-side grouping over a dict key (the established precedent — Key Decision "Python-side category grouping instead of a SQL NULL-ordering trick"). If SQL-side grouping is ever needed, `sqlalchemy.func.substr(col, 1, 7)` renders identically on both dialects. Do **not** reach for `strftime` (SQLite-only) or `date_trunc` (PostgreSQL-only).

### What *does* need care with `String(10)` (flag for the phase plan)

- **Validate on the way in, once.** `date.fromisoformat()` in the parse layer, then store the canonical string. Never trust the posted value: `<input type="date">` posts ISO, but a crafted POST does not. The precedent is `to_cents` (`app/core.py:28-46`) — a single sanctioned conversion point that raises `ValueError`. Add `to_business_date(raw) -> str` next to it, not a new module.
- **Do not double-shift timezones.** This is the biggest correctness trap in Phase 1. Today every period report converts a local calendar range into UTC bounds via `local_day_bounds_utc` (`app/core.py:108-126`) and filters `created_at`. A business date is **already a local calendar date** — it must be compared directly against the requested local day range, with **no** `local_day_bounds_utc` call. Running a business-date filter through the UTC-bounds helper would shift every report by up to a day. Expect a phase decision recording that `local_day_bounds_utc` stays for `created_at`-based surfaces (audit/sync) and is *not* used for business-date surfaces.
- **Bound the range.** `String(10)` accepts `'9999-12-31'`. Add a sanity range check (e.g. not before the first operation, not more than N days in the future) in the same parse helper.

### Does the project need a date library?

**No.** `arrow`, `pendulum`, `python-dateutil` and `whenever` all exist to solve parsing of ambiguous formats, timezone arithmetic, and relative-delta math. This milestone does none of that: the input is ISO, the storage is ISO, the display is `dd.mm.yyyy` via a 5-line existing helper, and the only arithmetic is `timedelta(days=1)` which stdlib already does in `local_day_bounds_utc`. Adding one would be a new concept for a learning developer and a new artifact in the offline Windows bundle, for zero capability. Confidence: HIGH.

---

## Question 2 — Currency: babel vs the existing hand-rolled formatter

**Recommendation: keep the hand-rolled `format_money`. Do not add babel. Confidence: HIGH.**

The formatter already exists and is registered (`app/core.py:79-86`, `app/routes/__init__.py:227`). The remaining work is *adoption* (42 templates on `|cents`, 1 on `|money`) plus deciding per surface whether the column is already currency-labelled — which is a template-editing job, not a library job.

### Why babel is the wrong call here

| Factor | Effect |
|---|---|
| **Size** | babel **2.18.0** ships a **10,196,845-byte wheel** (~9.7 MiB, verified against `https://pypi.org/pypi/babel/json` on 2026-09-04) — it bundles the entire CLDR locale database. The v4.0 deliverable is a self-contained Windows onedir with a bundled Python runtime, downloaded and signature-verified on every self-update. Nearly 10 MiB of CLDR for three fixed symbols is the single largest addition anyone could make to that archive. |
| **It would change existing output** | CLDR `ru` currency formatting produces a *narrow no-break space* group separator and a NBSP before the symbol (`1 234,56 ₽`), not the app's current `1234,56 ₽`. Swapping formatters would silently alter the rendering in all 42 `|cents` surfaces and break the existing display assertions. That is a UI rewrite disguised as a dependency. |
| **No locale problem to solve** | The UI is single-language Russian, the decimal separator is already a comma by deliberate convention (`to_cents` accepts `,`, `format_cents` emits `,`), and the currency set is a **closed three-element dict** (`CURRENCIES` in `app/core.py:60-64`). There is no runtime locale negotiation and never will be. |
| **Beginner-friendliness** | `format_money` is readable in one glance. babel introduces `Locale`, `format_currency`, CLDR pattern strings, and a decimal/precision model that must be reconciled with the project's integer-cents rule. |
| **Integer cents** | babel's `format_currency` takes a `Decimal`/float amount. Every call site would need a cents→Decimal conversion — reintroducing a decimal boundary the project deliberately removed. |

For completeness, verified so the roadmap need not re-check: **babel 2.18.0, `requires_python >=3.8`, wheel published 2026-02-01, 10,196,845 bytes** (source: `https://pypi.org/pypi/babel/json`, fetched 2026-09-04, HIGH).

### Currency work that is real, and needs no library

1. **Decide the render rule per surface and apply it.** `format_cents` = bare number for a column already labelled with a currency; `format_money` = standalone amount. That rule is already written in the `format_money` docstring — the phase just has to execute it across desktop + mobile templates.
2. **Give reports a warehouse/currency dimension.** `reports.py` / `dashboard.py` / `finance.py` reach a warehouse only via `Batch.warehouse_id` (`app/models.py:262`). This is ORM join work.
3. **Block cross-currency baskets** in `services/sales.py`.
4. **`needs verification` (carried from the audit, still unresolved):** what a new-schema client pushing `currency` to an old-schema server does. `KIND_TO_FIELDS` is derived from *the receiving side's* model columns (`merge.py:80-83`), so an unknown field is most likely dropped silently. Smallest check: build an `ExchangeRecord` whose `data` contains a key absent from `KIND_TO_FIELDS[kind]` and assert the documented behaviour in `tests/test_merge*.py`. No library involved. Note this now applies to `business_date` too — the same test covers both.

---

## Question 3 — Alembic on both dialects: NOT NULL + backfill on a trigger-guarded append-only table

**Recommendation: follow migrations `0017`, `0024` and `0026` verbatim. No Alembic upgrade, no new tooling. Confidence: HIGH.**

This exact problem has been solved in this repo three times and the reasoning is written into the migration docstrings. The rules, in order:

### Rule 1 — NEVER use `batch_alter_table` on `operations` or `cash_movements`

Migration `0017`'s docstring states it outright:

> a batch (move-and-copy) migration on `operations` or `cash_movements` DROPS their append-only triggers (`operations_no_update`/`operations_no_delete`, ...). `author_id` is therefore added with a NATIVE `op.add_column` — NEVER an Alembic batch/move-and-copy rebuild.

Why this is not paranoia: Alembic's batch docs state batch mode does the move-and-copy "if SQLite is in use, and if there are migration directives other than `Operations.add_column()` present". So a *pure* add_column inside a batch block happens to emit a plain ALTER — but the moment anyone adds a second directive to that block, the table is silently rebuilt and the append-only triggers vanish with the dropped original. Alembic's batch documentation says nothing about preserving triggers (it documents constraint and FK handling only), because it does not preserve them. The repo's rule removes the footgun entirely. `render_as_batch=True` in `env.py` only affects *autogenerated* output — it does not force hand-written `op.add_column` into batch mode.

### Rule 2 — the backfill UPDATE must happen BEFORE the trigger learns the new column

The `*_no_update` triggers are **value-based and column-scoped** (`app/db.py:39-56`, migration `0018`): they `RAISE(ABORT)` only when a column *in the enumerated WHEN list* actually changes. This creates a precise, ordered window:

1. `op.add_column("operations", sa.Column("business_date", sa.String(10), nullable=True))` — native, no batch.
2. `op.execute("UPDATE operations SET business_date = substr(created_at, 1, 10) WHERE business_date IS NULL")` — **succeeds**, because `business_date` is not yet in the trigger's WHEN list, so no guarded column changes value. This is exactly the trick migration `0024` used for `cash_movements.currency`.
3. A **later** migration adds `business_date` to the WHEN clause of `operations_no_update`, per-dialect, by DROP + CREATE — the technique of `0026`.

Reverse that order and the backfill hits `RAISE(ABORT, 'operations ledger is append-only')` on SQLite and the PL/pgSQL guard on PostgreSQL. Steps 2 and 3 may live in one migration file provided the UPDATE precedes the trigger rebuild, but two files (backfill, then guard) matches the `0024`→`0026` precedent and is easier to review.

Note on the backfill expression: `substr(created_at, 1, 10)` renders identically on SQLite and PostgreSQL. Do **not** use `date(created_at)` (SQLite) or `created_at::date` (PostgreSQL) — both are dialect-specific. Also note `created_at` is a **UTC** ISO string, so `substr(...,1,10)` is the UTC calendar day; if the operator's timezone makes that the wrong default for historical rows, that is a product decision to record in the phase, not a technical one (a per-row timezone shift in SQL is not portable — do it in Python with a one-off script if it matters, or accept UTC for legacy rows and document it).

### Rule 3 — the LOCKSTEP RULE is mandatory and already has a tripwire

Three artifacts must move in the **same commit**:

- the migration that changes the trigger DDL (production path),
- `app.db.APPEND_ONLY_TRIGGERS` (the fixture path — `tests/conftest.py` builds test DBs from `Base.metadata.create_all` + this constant, **never** via Alembic),
- `tests/test_append_only_cursor.py::IMMUTABLE_OPERATION_COLUMNS`.

`test_trigger_column_list_matches_schema` and `test_declared_constants_match_trigger_ddl` already exist and will turn a drift into a loud red test. This is precisely how the `0024` oversight was caught and fixed by `0026`.

### Rule 4 — dialect-specific null-safety in the trigger, per `0018`

- SQLite: `NEW.col IS NOT OLD.col` (`IS DISTINCT FROM` only landed in SQLite 3.39).
- PostgreSQL: `NEW.col IS DISTINCT FROM OLD.col`, dispatched on `op.get_bind().dialect.name`.
- The `operations.payload` JSON trap documented in `0018` still applies: PostgreSQL `json` has no equality operator, so the PG guard compares `NEW.payload::text IS DISTINCT FROM OLD.payload::text`. A `String(10)` business date needs no cast — another point against `sa.Date`, whose PG `date` type would be fine but whose SQLite side is a string anyway.

### Rule 5 — NOT NULL at the DB level: don't chase it on SQLite

SQLite's documented `ALTER TABLE ADD COLUMN` restrictions (sqlite.org/lang_altertable.html, verified 2026-09-04):

> * The column may not have a default value of CURRENT_TIME, CURRENT_DATE, CURRENT_TIMESTAMP, **or an expression in parentheses**.
> * If a NOT NULL constraint is specified, then the column must have a default value other than NULL.

So a NOT NULL `business_date` on SQLite requires a **constant** default — it cannot be derived from `created_at` in the ALTER. Two options:

- **Recommended:** add the column nullable at the DB level, backfill, and declare it `nullable=False` **on the ORM model**, with `record_operation` always supplying a value (it is the single sanctioned write path, so the invariant is enforced at the one choke point that matters). Retrofitting a true `SET NOT NULL` on SQLite requires a table rebuild — which drops the append-only triggers. **Not worth it.** PostgreSQL could take `ALTER COLUMN ... SET NOT NULL` cheaply, but a per-dialect nullability divergence is worse than a uniformly nullable column.
- **Alternative:** NOT NULL with a constant `server_default` (the `0024` currency approach). Valid when a constant default is semantically right; for a business date it is not — there is no sensible constant.

Also relevant if a FK is ever wanted for the reversal link: `0004`/`0008`/`0017` all establish that new columns on ledger tables are **bare** (no DB-level FK) because Alembic's SQLite dialect raises `NotImplementedError` on ALTER-in constraints; the ORM `ForeignKey` gives insert ordering and PostgreSQL portability. For the storno link, the cheapest option is no new column at all: `Operation.payload` is `sa.JSON` (`app/models.py:374`) and is already in the immutable trigger list — the reversed-operation id can live there, exactly as the write-off `reason_code` does. Whether a first-class indexed `reverses_op_id` column is worth its own migration is a phase decision; the payload route requires **no schema change and no trigger change at all**.

### Alembic 1.18.x version notes

- Locked: **alembic 1.18.5** (`uv.lock:10-11`), released 2026-06-25. Latest on PyPI: **1.19.1**, released 2026-08-08 (verified at `https://pypi.org/project/alembic/`, 2026-09-04).
  *(Caveat: `https://pypi.org/pypi/alembic/json` returned a stale `1.17.1` on the same day. The project page and the changelog agree on 1.19.1; treat the `/json` reading as unreliable. Smallest check: `uv run python -c "import alembic; print(alembic.__version__)"` for the installed version, `uv pip index versions alembic` for the latest.)*
- **No known 1.18.x gotcha applies to this pattern.** The 1.18.x changelog entries are `inline_references` on `add_column` (1.18.2/1.18.5), a revert of automatic inline `PRIMARY KEY` on `add_column` (1.18.4 — 1.18.5 has the safe behaviour), and a `server_default` typing fix. None touch batch mode, SQLite ALTER, or triggers.
- **Do not upgrade to 1.19.x during this milestone.** 1.19.0 makes autogenerate detect added/removed named CHECK constraints by default, and 1.19.1 fixes a false-detection bug in it. That is new autogenerate noise against a 26-migration history for zero benefit here. Upgrade deliberately, in its own change, with a clean `alembic revision --autogenerate` diff review.

---

## Question 4 — Testing: does this need freezegun or time-machine?

**Recommendation: no. The repo already has two working deterministic-time idioms. Confidence: HIGH.**

Verified in the existing suite:

- **Idiom A — patch the conversion point.** `monkeypatch.setattr(ledger_module, "utcnow_iso", lambda: iso)` / `monkeypatch.setattr(finance_module, "utcnow_iso", lambda: iso)`. Used in `tests/test_reports.py`, `test_dashboard.py`, `test_finance_reports.py`, `test_sales.py`, `test_receipts.py`, `test_returns.py`, `test_export.py` (20+ call sites). Works because `app/core.utcnow_iso` is the *single* sanctioned timestamp source.
- **Idiom B — a frozen `datetime` subclass** for modules that call `datetime.now(tz)` directly: `tests/test_dashboard.py:95-107` builds `type("Frozen", (_FrozenDatetime,), {"_fixed": fixed})` and `monkeypatch.setattr(dashboard, "datetime", frozen)`.

Business-date tests barely need either: a business date is an **explicit input**, so a period-boundary test just passes `business_date="2026-08-31"` and asserts which bucket the row lands in. Only the *default* ("business date defaults to today when the operator leaves it blank") needs a frozen clock — Idiom A covers it, since the default is derived from the same single timestamp source.

For a currency-filtered report test, nothing new at all: seed two warehouses with different currencies and assert the report never sums across them.

Why not to add either library, for the record (versions verified 2026-09-04 so nobody re-litigates this):

| Candidate | Version | Why rejected |
|---|---|---|
| **freezegun** | **1.5.5** (`requires_python >=3.8`, released 2025-08-09; source: `https://pypi.org/pypi/freezegun/json`) | Patches `datetime`/`time` **globally and process-wide**, including inside SQLAlchemy, httpx, uvicorn and any background thread. This app runs an auto-sync thread in its lifespan (see the known `sync_client._run_lock` test interference in MEMORY) — global clock patching is exactly the kind of cross-test coupling that produced those 4 pre-existing failures. The targeted monkeypatch has no blast radius. |
| **time-machine** | **3.5.0** (`requires_python >=3.10`; source: `https://pypi.org/pypi/time-machine/json`) | Faster than freezegun, but ships **compiled C extension wheels** (per-CPython-ABI: cp310…cp315, platform-tagged). That is a binary artifact to resolve for the bundled 3.13 embeddable runtime and CI on two dialects, in exchange for solving a problem the repo has already solved in pure Python. Same global-patching blast radius as freezegun. |

Existing dev group (`pytest 9.1.1`, `ruff 0.15.*`, `openpyxl>=3.1.5`) stays exactly as is.

---

## Alternatives Considered

| Recommended | Alternative | When the alternative would be right |
|-------------|-------------|-------------------------------------|
| `String(10)` ISO business date | `sqlalchemy.Date` | If the app ever needed SQL-side date arithmetic (`business_date + interval`, `age()`, date bucketing in SQL) **and** dropped either SQLite or the JSON sync wire. Neither is on the horizon. |
| `String(10)` business date | Reuse `created_at`, shift it | Never. `created_at` is the sync cursor, the ordering key and the audit trail; overwriting it is the one thing every planning note forbids. |
| Hand-rolled `format_money` | babel `format_currency` | If the UI ever became multi-language with locale negotiation, or the currency set became open-ended. Neither is in scope; `CURRENCIES` is a closed 3-element dict by design. |
| Reversal link in `Operation.payload` (JSON) | A first-class `reverses_op_id` column + index | Choose the column if История must *query* "is this operation already reversed?" for many rows at once (a payload JSON scan is not indexable portably). Choose payload if the link is display-only. This is a Phase 3 planning decision — both are cheap, but the column drags in the full `0017`+`0026` migration ritual (native add_column, backfill-free, trigger WHEN-list update, LOCKSTEP). |
| Targeted `monkeypatch` of `utcnow_iso` | freezegun / time-machine | If the code ever called `datetime.now()` from dozens of scattered places. It does not — `utcnow_iso` is the single sanctioned source (`app/core.py:20`). |
| Python-side period grouping | `func.substr(col,1,7)` in SQL | Acceptable and portable if a report ever grows too large to group in Python. Both dialects render `substr` identically. Never `strftime` or `date_trunc`. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **babel** | ~9.7 MiB CLDR wheel inside a signature-verified offline Windows self-update archive; would change existing `12,50` output to CLDR's NBSP-separated form across 42 templates; requires a cents→Decimal boundary the project deliberately removed | `app.core.format_money` (already written and registered as the `money` filter) |
| **py-moneyed / money / forex-python / any FX library** | The milestone's defining constraint is **no conversion, no rates, no cross-currency totals**. An FX library exists to do the one thing that must not exist | `Warehouse.currency` + `CashMovement.currency` (already shipped) + a mandatory single-currency report filter |
| **`sqlalchemy.Date` / `sa.DateTime` for the business date** | `json.dumps(date)` → `TypeError` breaks the NDJSON sync wire (`merge.py:568`, no `default=` encoder); and `Date` binds raise `TypeError` on SQLite for string params while PostgreSQL accepts them — a client-only runtime failure | `String(10)` ISO text, matching `Batch.expiry` and `ActiveCatalog.close_date` |
| **arrow / pendulum / python-dateutil / whenever** | Nothing in scope needs flexible parsing, relative deltas or timezone arithmetic beyond the `timedelta(days=1)` already in `local_day_bounds_utc` | stdlib `datetime.date`, `date.fromisoformat`, existing `format_ru_date` |
| **freezegun / time-machine** | Global process-wide clock patching next to a lifespan auto-sync thread (known source of cross-test interference here); time-machine additionally adds per-ABI compiled wheels to a bundled-runtime distribution | `monkeypatch.setattr(module, "utcnow_iso", ...)` (Idiom A) or the frozen-`datetime` subclass (Idiom B) |
| **`op.batch_alter_table` on `operations` / `cash_movements`** | Move-and-copy drops the append-only triggers; Alembic does not restore them and does not document them at all | Native `op.add_column` — the explicit `0017` rule |
| **Backfilling with `date(created_at)` or `created_at::date`** | Dialect-specific SQL; breaks the "portable ORM only" rule on one of the two dialects | `substr(created_at, 1, 10)` (identical on both) |
| **Backfill UPDATE *after* extending the trigger WHEN list** | `RAISE(ABORT, 'operations ledger is append-only')` / PL/pgSQL guard fires and the migration fails | Backfill first, extend the guard second (the `0024`→`0026` order) |
| **Upgrading Alembic to 1.19.x mid-milestone** | 1.19.0 turns on CHECK-constraint autogenerate detection by default — new diff noise against 26 existing migrations, for no benefit to these four features | Stay on the locked 1.18.5; upgrade later as its own reviewed change |
| **A JS date picker / flatpickr / any client-side date lib** | The app must work offline with no CDN; native `<input type="date">` already posts ISO and is already used for `Batch.expiry` | `<input type="date">` |
| **`Intl.NumberFormat` client-side money rendering** | Splits money formatting across a server filter and a browser API, diverging desktop/mobile/CSV output; also an offline-consistency risk | The server-side `money` Jinja filter, everywhere |
| **A second validation path for the mobile edit routes** | Directly contradicts the standing Key Decision ("mobile flow reuses existing services unchanged — new templates/routes only") | Reuse `app/routes/products.py` / `customers.py` services; mirror the `/m/batches/{id}/edit` precedent from quick task `260813-i28` |
| **Any new dependency for mobile card editing (Phase 4)** | It is templates + routes over existing services. Zero new capability required | Nothing |

---

## Stack Patterns by Variant

**If the phase adds a column to `operations` or `cash_movements`:**
- Native `op.add_column`, nullable, no DB-level FK.
- Backfill with a portable `substr`/constant UPDATE **before** touching the trigger.
- Second step: DROP+CREATE the `*_no_update` trigger per dialect (`IS NOT` for SQLite, `IS DISTINCT FROM` for PostgreSQL, `::text` cast for the `payload` JSON column).
- Same commit: `app/db.py::APPEND_ONLY_TRIGGERS` + `tests/test_append_only_cursor.py::IMMUTABLE_*_COLUMNS`. The two tripwire tests will catch you if you forget.
- Migration files import stdlib + `sqlalchemy` + `alembic.op` only (WR-06 immutability rule) — never an application module.

**If the phase adds a column that crosses the sync wire (both `business_date` and any storno link do):**
- The value must be JSON-native: `str`, `int`, `None`, or a JSON-able dict. No `date`, no `Decimal`, no `datetime`.
- `KIND_TO_FIELDS` picks it up automatically — no merge code change.
- Add the old-schema-server test noted under Question 2; it now covers `currency` and `business_date` in one go.

**If the phase touches money rendering:**
- `|cents` = bare number inside a column already labelled with a currency.
- `|money` = standalone amount where the reader must know the currency.
- Both desktop and mobile templates, in the same plan — the project's repeated lesson (v1.3 Финансы, v2.0 mobile parity) is that mobile lags one plan behind and gets found in UAT.

**If a report gains a currency filter:**
- The filter is on the **warehouse** dimension; currency is derived from it. `Batch.warehouse_id` is the only join path from stock/sales to a warehouse.
- The filter must be **mandatory** — a report with no warehouse selected must not render a total, or the cross-currency sum the milestone forbids reappears by default.

---

## Version Compatibility

| Package | Version (locked) | Compatible with | Notes |
|---------|------------------|-----------------|-------|
| alembic | 1.18.5 | sqlalchemy 2.0.51 | Batch mode + `render_as_batch=True` unchanged; latest upstream is 1.19.1 — **do not bump this milestone** |
| sqlalchemy | 2.0.51 | Python 3.13, psycopg 3.3.x | `String(10)` has no bind processor on either dialect; `sa.Date` does on SQLite (rejects `str`) and does not on PostgreSQL |
| psycopg[binary] | 3.3.x | PostgreSQL 17 (CI service image) | Unchanged |
| pytest | 9.1.1 | Python 3.13, httpx 0.28.x | `monkeypatch` covers all deterministic-time needs |
| Python | 3.13 | stdlib `datetime`, `zoneinfo`, `tzdata>=2026.2` | `tzdata` is already an explicit dependency (needed on Windows) — the business-date work adds no timezone surface, it *removes* one |

---

## Sources

- `E:\dev\myorishop\app\core.py`, `app\models.py`, `app\db.py`, `app\routes\__init__.py`, `app\services\merge.py`, `app\services\sync.py`, `app\services\sync_client.py`, `alembic\versions\0017,0018,0024,0026`, `tests\test_append_only_cursor.py`, `tests\test_dashboard.py`, `uv.lock`, `.github\workflows\ci.yml` — read 2026-09-04 (HIGH; primary evidence for every "already exists" and "already solved" claim)
- `git log --oneline -- app/core.py` + `git merge-base --is-ancestor cdcec66 HEAD` — proved the currency feature is already merged (HIGH)
- Locally executed against the project's own env (SQLAlchemy 2.0.51): SQLite `Date` bind raises `TypeError: SQLite Date type only accepts Python date objects as input.`; PostgreSQL `Date.bind_processor` is `None`; `json.dumps(date)` raises `TypeError` (HIGH — executed, not inferred)
- `https://pypi.org/pypi/babel/json` — babel 2.18.0, `requires_python >=3.8`, wheel 10,196,845 bytes, uploaded 2026-02-01 (HIGH)
- `https://pypi.org/pypi/freezegun/json` — freezegun 1.5.5, `>=3.8`, 2025-08-09 (HIGH)
- `https://pypi.org/pypi/time-machine/json` — time-machine 3.5.0, `>=3.10`, ships cp310–cp315 platform wheels (HIGH)
- `https://pypi.org/project/alembic/` — latest 1.19.1, 2026-08-08 (MEDIUM-HIGH; `https://pypi.org/pypi/alembic/json` disagreed with a stale 1.17.1 on the same day — the project page matches the changelog, so the `/json` reading is the outlier)
- `https://alembic.sqlalchemy.org/en/latest/changelog.html` — 1.18.2/1.18.4/1.18.5/1.19.0/1.19.1 entries; none affect batch mode, SQLite ALTER or triggers (HIGH)
- `https://alembic.sqlalchemy.org/en/latest/batch.html` — move-and-copy is used on SQLite "if there are migration directives other than `Operations.add_column()` present"; triggers/views are not mentioned as preserved (HIGH for the quoted rule, HIGH for trigger loss via the repo's own `0017` docstring which records it as observed behaviour)
- `https://www.sqlite.org/lang_altertable.html` — ADD COLUMN restrictions: NOT NULL requires a non-NULL default; no `CURRENT_DATE` and no parenthesised expression as a default (HIGH)
- `https://docs.sqlalchemy.org/en/20/dialects/sqlite.html` — SQLite DATE stored as ISO string; the page does **not** document the bind-processor `TypeError`, which is why it was verified by execution instead (MEDIUM for the page, HIGH for the executed result)

**Tooling note:** `gsd-tools query research-plan` and `gsd-tools query classify-confidence` are **not available** in the installed gsd-tools build (`Unknown command`), so the provider/caching seam could not be used. Sources were fetched directly from PyPI JSON, the official docs, and the repository itself; confidence tiers are assigned by source authority (executed-in-repo and official docs = HIGH, single web page contradicted by another = MEDIUM-HIGH).

## Open items carried forward

- `needs verification` — behaviour when a **new-schema client pushes an unknown field to an old-schema server**. Now covers both `currency` and `business_date`. Smallest check: unit-test `apply_merge` with an `ExchangeRecord` whose `data` carries a key absent from `KIND_TO_FIELDS[kind]`; assert it is dropped rather than raising.
- `needs verification` — whether `alembic` 1.19.1 is still the newest at planning time. Smallest check: `uv pip index versions alembic`.
- **Re-scope Phase 2 before planning it.** The currency schema, core helpers, `money` filter, warehouse form field and cash-movement trigger guard are already merged (`cdcec66`, migrations 0023–0026). The remaining work is render adoption (42 `|cents` templates), the warehouse dimension in three report services, and the basket mixing block. `.planning/ROADMAP.md:327-349` and `OPEN-WORK-AUDIT-2026-09-04.md` §999.1 both describe this phase as unstarted and should be corrected.

---
*Stack research for: v5.0 Corrections, Dates & Currency (back-dated operations, per-warehouse currency, one-tap reversal, mobile card editing)*
*Researched: 2026-09-04*
