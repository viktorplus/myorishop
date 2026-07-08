# Phase 3: Goods Receipt & Backup - Research

**Researched:** 2026-07-08
**Domain:** FastAPI/HTMX form flows on the existing ledger + SQLite VACUUM INTO backup/restore
**Confidence:** HIGH (codebase-grounded findings verified locally; external claims cited from official docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Receipt Entry Flow
- **D-01:** One receipt entry = one product line = one ledger `receipt` operation (qty_delta > 0). No multi-line receipt documents in v1 — fast repeat entry replaces them.
- **D-02:** Page `/receipts/new`: fields code, name (auto-filled), quantity, cost price, catalog price, sale price. After successful save the form clears and focus returns to the code field ("save & add next" loop) — minimal clicks for a box of many items.
- **D-03:** Name auto-fills from the dictionary via the existing HTMX lookup pattern (GET /dictionary/lookup, 204 pattern, ~300ms debounce) — RCP-02. If the code matches an existing product, its current name/prices pre-fill the form.
- **D-04:** Recent receipts visible on the receipts page (last N entries partial) so the operator sees what was just entered.

#### Unknown Product Handling
- **D-05:** Receipt for a code with no product card auto-creates the product (code, name from dictionary or typed, entered prices) in the same transaction — no separate "create product first" detour. Auto-creation records `product_created` op per Phase 2 conventions.

#### Price Capture & Card Update
- **D-06:** The `receipt` operation snapshots entered unit_cost_cents and prices (payload carries catalog/sale prices) — success criterion 3.
- **D-07:** Entered prices also update the product card (cost/sale/catalog) via the existing `price_change` operations in the same transaction, so the card always reflects the latest intake prices while history is preserved (CAT-04 machinery reused).

#### Backup & Restore (BCK-01)
- **D-08:** Backup method: `VACUUM INTO 'backups/myorishop-YYYYMMDD-HHMMSS.db'` — WAL-safe, produces a compact standalone copy.
- **D-09:** Automatic backup on app startup (before serving requests, skipped if DB missing/empty) + manual "Backup now" button on a simple /backup page showing existing backups.
- **D-10:** Retention: keep the most recent 30 backups; older ones deleted automatically after a successful new backup.
- **D-11:** Restore: documented procedure + `restore.bat`/script that copies a chosen backup over the live DB while the app is stopped. Restore must be verified at least once (automated test restoring a backup into a temp path and reading data back).

### Claude's Discretion
- Exact backup page layout, filename format details, empty-state texts
- Migration needs (likely none beyond possible indexes), template structure
- Whether recent-receipts list is a dedicated page or a partial under the form

### Deferred Ideas (OUT OF SCOPE)
- Multi-line receipt documents (batch header grouping lines) — revisit if single-line loop proves slow
- Scheduled/periodic backups while app runs (startup + manual is enough for one operator)
- Off-machine backup copies (cloud/USB sync) — v2 concern
- CSV export — Phase 6 (BCK-02)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RCP-01 | Register a goods receipt by product code with quantity, cost price, catalog price, and sale price; stock increases accordingly | `record_operation` single write path already accepts type `receipt` with qty_delta and cost/price columns [VERIFIED: codebase `app/services/ledger.py`, `app/models.py:34`]; transaction pattern (stage-then-single-commit, `commit=False`) proven in `update_product` |
| RCP-02 | Product name auto-fills from the dictionary during receipt entry | `GET /dictionary/lookup` + `partials/name_input.html` + swap-time guard pattern already shipped in Phase 2 [VERIFIED: codebase `app/routes/dictionary.py`, `app/templates/pages/product_form.html`]; reuse as-is, add product-prices pre-fill per D-03 (see Pattern 2) |
| BCK-01 | Database backed up automatically via VACUUM INTO; user can restore from a backup | VACUUM INTO semantics verified [CITED: sqlite.org/lang_vacuum.html]; SQLAlchemy AUTOCOMMIT execution pattern verified [CITED: docs.sqlalchemy.org sqlite dialect + sqlalchemy discussion #6959]; restore -wal/-shm hazard verified [CITED: sqlite.org/howtocorrupt.html §1.2, §1.4]; local SQLite 3.50.4 supports VACUUM INTO [VERIFIED: local probe `sqlite3.sqlite_version`] |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- Stack locked: Python 3.13, FastAPI 0.139, SQLAlchemy 2.0 (declarative `Mapped[]` style), SQLite, Jinja2, htmx 2.0.10 vendored — no CDN, fully offline
- Money as integer minor units (`*_cents`); never FLOAT/REAL for money
- Portable SQL only — no SQLite-specific SQL in queries (VACUUM INTO is the sanctioned, decision-locked exception for the backup utility; it lives in a backup service, not in business queries)
- Timezone-aware UTC timestamps everywhere; SQLite stores as text
- WAL + foreign_keys=ON pragmas per connection (already implemented in `app/db.py`)
- Append-only operations ledger — never UPDATE/DELETE its rows (DB triggers enforce)
- UUID String(36) PKs on all tables; `uuid4` via `app.core.new_id`
- Backups = copy `.db` file while app closed or WAL-safe method — "worth a one-click Backup button early" (this phase delivers exactly that)
- No auth in v1; no Docker; no PyInstaller; `run.bat` is the deployment story
- Sync `Session` + plain `def` endpoints — no async SQLAlchemy
- Tests: pytest + httpx TestClient; lint: ruff (`ruff check`, `ruff format`)
- UI text Russian; code/comments/commits English
- Do not commit unless asked (GSD `commit_docs: true` governs planning docs)

## Summary

Phase 3 is two nearly independent tracks. **Track A (receipts)** is almost pure reuse: the ledger service (`record_operation`) already accepts the `receipt` operation type, the catalog service already implements product auto-creation (`create_product`) and per-field `price_change` audit ops with the `commit=False` stage-then-single-commit pattern, and the dictionary lookup endpoint plus `name_input.html` partial deliver RCP-02 unchanged. The only new engineering is a `receipts` service that composes these pieces into one transaction (auto-create → price updates → receipt op → single commit) and an HTMX "save & add next" form loop. **Track B (backup)** is small but has three sharp edges verified this session: (1) VACUUM INTO cannot run inside a transaction, so it must execute on an `isolation_level="AUTOCOMMIT"` connection via `exec_driver_sql` with the filename passed as a bound parameter; (2) the FastAPI startup hook must use the `lifespan` context manager (`on_event` is deprecated) — and because `tests/conftest.py` enters `TestClient(app)` as a context manager, lifespan WILL run during tests, so the startup backup must be gated by a settings flag to keep test runs from writing into the real `backups/` folder; (3) restore-by-copy corrupts the database if stale `-wal`/`-shm` files survive next to the replaced file, so `restore.bat` must delete them — sqlite.org documents this exact failure mode.

No new packages, no schema migrations, and no new architectural concepts are required. Everything is stdlib + existing dependencies on top of established Phase 1–2 patterns.

**Primary recommendation:** Plan two plans/waves — receipts (service + route + templates + tests) and backup (service + lifespan + /backup page + restore.bat + restore test) — reusing `record_operation`/`create_product` verbatim and executing VACUUM INTO only through an AUTOCOMMIT connection with a parameter-bound target path.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Receipt validation + transaction (auto-create, price_change ops, receipt op) | API/Backend (`app/services/receipts.py`) | — | All writes go through the service layer to the ledger; single-transaction atomicity lives server-side |
| Name/prices auto-fill on code entry | API/Backend (lookup endpoints) | Browser (htmx debounced GET, swap guard) | Server decides fill vs 204 no-op (established D-23 pattern); browser only triggers and swaps |
| Save-and-next form loop (clear + refocus) | Browser (htmx swap + focus) | API/Backend (returns fresh form partial + OOB recent list) | Focus/reset is inherently client-side; server renders the fresh state |
| Recent receipts list | API/Backend (query + partial render) | — | Read of `operations` joined to `products`, rendered server-side |
| Backup creation (VACUUM INTO) + retention pruning | Database/Storage via API/Backend service | — | SQLite command executed over the app engine; file pruning is local filesystem |
| Automatic startup backup | API/Backend (FastAPI lifespan) | — | Runs before serving requests per D-09 |
| Restore | OS/filesystem (`restore.bat`, app stopped) | — | Live process must not hold the DB during file replacement; deliberately NOT a web endpoint |

## Standard Stack

### Core

No new libraries. The phase is implemented entirely with the already-installed stack:

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 (stdlib, via SQLAlchemy) | SQLite 3.50.4 bundled with Python 3.13.13 | `VACUUM INTO` backup | [VERIFIED: local probe] — VACUUM INTO requires SQLite ≥3.27 [ASSUMED — version threshold from training knowledge; moot given 3.50.4 locally] |
| SQLAlchemy | 2.0.* (installed) | AUTOCOMMIT connection for VACUUM; existing ORM | [VERIFIED: codebase `pyproject.toml`] |
| FastAPI | 0.139.* (installed) | `lifespan` startup hook, /receipts + /backup routes | [CITED: fastapi.tiangolo.com/advanced/events/] |
| pathlib / shutil / os (stdlib) | 3.13 | Backup dir listing, retention pruning, restore test file copy | stdlib |
| htmx | 2.0.10 vendored (installed) | Save-and-next loop, OOB recent-list update | [VERIFIED: codebase `app/static/`] |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest + httpx TestClient | 9.1.* / 0.28.* (installed) | Receipt flow tests, backup + restore verification test | Existing fixtures in `tests/conftest.py` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| VACUUM INTO | `sqlite3.Connection.backup()` API | Also WAL-safe, but D-08 locks VACUUM INTO; VACUUM INTO additionally compacts the file |
| lifespan startup backup | backup call in `run.bat` before `alembic upgrade head` | run.bat call would also protect against a bad migration; lifespan satisfies D-09 as locked. Recommendation: implement lifespan per D-09; a pre-migration `uv run python -m ...` call in run.bat is an optional discretion-level addition (see Open Question 3) |
| restore.bat file copy | web-based restore endpoint | Rejected: app holds the DB open; restore must happen with the app stopped (D-11), and a web restore adds a path-traversal surface for zero benefit |

**Installation:** none — `uv sync` already provides everything.

## Package Legitimacy Audit

No new external packages are installed in this phase. All functionality uses the Python standard library and dependencies already present in `pyproject.toml` (verified in Phase 1–2).

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
RECEIPT FLOW (Track A)
Operator (browser)
  │ types code
  ├─ htmx GET /receipts/lookup?code=…&name=…   (debounce 300ms, hx-sync replace)
  │        │
  │        ▼
  │   receipts route ──► dictionary.lookup(code) ──► known code? render name fragment
  │                 └──► catalog: active product by code? ALSO pre-fill prices (D-03)
  │                 └──► nothing known / name already typed ──► 204 (no swap)
  │ submits form
  └─ htmx POST /receipts (code, name, qty, cost, catalog, sale)
           │
           ▼
     receipts service (ONE transaction, all commit=False, single commit):
       1. validate (qty>0 int, money via to_cents, code/name required)
       2. product by code?
            no  ──► stage Product + product_created op   (reuse catalog pattern, D-05)
            yes ──► for each changed price: price_change op (reuse D-07 / CAT-04)
       3. record_operation(type="receipt", qty_delta=+qty,
            unit_cost_cents, unit_price_cents=sale, payload={catalog_cents}) (D-06)
       4. session.commit()  ──► products.quantity += qty (inside record_operation)
           │
           ▼
     response 200: fresh empty form partial (+ hx-swap-oob recent-receipts rows)
     response 422: form partial with errors + entered values preserved

BACKUP FLOW (Track B)
app start (lifespan, before serving)          /backup page "Backup now" (POST)
        │                                             │
        └──────────────► backup service ◄─────────────┘
                           │  engine.connect().execution_options(
                           │      isolation_level="AUTOCOMMIT")
                           │  exec_driver_sql("VACUUM INTO ?", (path,))
                           ▼
                 backups/myorishop-YYYYMMDD-HHMMSS.db  (standalone, no -wal/-shm)
                           │ on success: prune to newest 30 (D-10)
                           │ on failure: delete partial target file
RESTORE (app STOPPED)
  restore.bat <backup-file>:
    copy backup ──► data/myorishop.db
    del data/myorishop.db-wal, data/myorishop.db-shm   (corruption guard)
```

### Recommended Project Structure

```
app/
├── routes/
│   ├── receipts.py        # GET /receipts/new, GET /receipts/lookup, POST /receipts
│   └── backup.py          # GET /backup, POST /backup
├── services/
│   ├── receipts.py        # register_receipt(...) — the one transaction; recent_receipts(...)
│   └── backup.py          # create_backup(engine, dir), prune_backups(dir, keep=30), list_backups(dir)
├── templates/
│   ├── pages/
│   │   ├── receipt_form.html   # extends base; includes form partial + recent partial
│   │   └── backup.html         # backup list + "Backup now" + restore instructions (RU)
│   └── partials/
│       ├── receipt_form.html   # the form itself (swapped whole on success/error)
│       └── receipt_rows.html   # recent receipts (also used for hx-swap-oob)
├── main.py                # + lifespan: startup backup (gated), + routers, + nav link in base.html
restore.bat                # documented restore procedure (D-11)
tests/
├── test_receipts.py
└── test_backup.py         # includes the restore-verification test
```

(Exact naming is planner's discretion; `receipt_form` page vs partial split follows the Phase 2 `name_input.html` single-source pattern.)

### Pattern 1: One-transaction receipt (compose existing services)

**What:** `register_receipt` stages everything with `commit=False` and issues exactly one `session.commit()` — the WR-03 pattern already proven in `update_product` [VERIFIED: codebase `app/services/catalog.py`].
**When to use:** the POST /receipts handler, always.

```python
# Pattern sketch (mirrors app/services/catalog.py update_product, WR-03)
def register_receipt(session, *, code, name, qty_raw, cost_raw, catalog_raw, sale_raw):
    # 1. validate: code/name required, qty positive int, prices via parse_optional_cents
    # 2. product = active product by code (deleted_at IS NULL)
    if product is None:
        product = Product(id=new_id(), code=code, name=name, name_lc=name.lower(), ...)
        session.add(product)
        record_operation(session, type_="product_created", product_id=product.id,
                         qty_delta=0, payload={"code": code, "name": name}, commit=False)
    else:
        # D-07: one price_change op per CHANGED price field, old snapshotted BEFORE mutation
        ...  # reuse the changed_prices loop shape from update_product
    record_operation(session, type_="receipt", product_id=product.id,
                     qty_delta=qty,                      # positive (D-01)
                     unit_cost_cents=cost_cents,         # D-06 snapshot
                     unit_price_cents=sale_cents,        # D-06 snapshot
                     payload={"catalog_cents": catalog_cents},
                     commit=False)
    try:
        session.commit()
    except IntegrityError:          # duplicate-code race, same shape as catalog WR-04
        session.rollback()
        return None, {"code": DUPLICATE_CODE_ERROR}
```

Key facts verified in the codebase: `record_operation` autoflushes the staged Product before its `session.get` validation, updates `products.quantity` SQL-side atomically, rejects soft-deleted products (IN-01 guard), and `OPERATION_TYPES` already contains `"receipt"` — no model change needed [VERIFIED: codebase `app/services/ledger.py`, `app/models.py`].

### Pattern 2: Code lookup that pre-fills name AND prices (D-03)

**What:** The existing `GET /dictionary/lookup` fills only the name from the dictionary table. D-03 additionally requires that a code matching an existing *product* pre-fills name + current prices. Recommended: a receipt-specific lookup endpoint (e.g., `GET /receipts/lookup`) in the receipts router that checks products first, falls back to the dictionary, and returns 204 otherwise — same server-decides contract as Pattern 2/D-23 from Phase 2 [VERIFIED: codebase `app/routes/dictionary.py`].
**When to use:** wired to the code input exactly like `product_form.html` does today (`hx-trigger="input changed delay:300ms"`, `hx-sync="this:replace"`, `hx-include` the guarded fields, swap-time `shouldSwap = false` guard so in-flight responses never destroy operator-typed values) [VERIFIED: codebase `app/templates/pages/product_form.html`].
**Filling multiple fields:** return one fragment wrapping name + the three price inputs (single `hx-target`), or a name fragment plus `hx-swap-oob` price inputs. The wrapper-fragment approach is simpler and keeps the Phase 2 "single source partial" rule (PD-6).

### Pattern 3: Save-and-next loop (D-02)

**What:** POST /receipts returns the form partial: on success a fresh empty form (status 200), on validation failure the form with RU errors and entered values (status 422 — already whitelisted for swapping in the htmx-config meta [VERIFIED: codebase `app/templates/base.html`]). The same response carries the updated recent-receipts rows via `hx-swap-oob` (D-04).
**Focus return:** htmx does not document honoring `autofocus` in swapped content [CITED: htmx.org/docs — reset via `hx-on::after-request`/swap patterns documented; autofocus behavior not documented]. Use an explicit focus hook on the swapped-in form, e.g. `hx-on::htmx:load="document.getElementById('code').focus()"` on the fresh form partial (or `hx-on::after-settle` on a stable wrapper). Keep `autofocus` on the code input too for initial page load (matches `product_form.html`). Manual UAT must confirm focus lands on the code field after save.

### Pattern 4: VACUUM INTO via SQLAlchemy (D-08)

**What:** VACUUM cannot run inside a transaction and SQLAlchemy connections are transactional by default — use AUTOCOMMIT isolation and a bound parameter for the filename.

```python
# Source: sqlite.org/lang_vacuum.html + docs.sqlalchemy.org (sqlite dialect)
#         + github.com/sqlalchemy/sqlalchemy/discussions/6959
from pathlib import Path
from app.core import ...  # timestamp helper

def create_backup(engine, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"myorishop-{stamp}.db"   # YYYYMMDD-HHMMSS
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Bound parameter: no path-quoting/injection issues on Windows paths
            conn.exec_driver_sql("VACUUM INTO ?", (str(target),))
    except Exception:
        target.unlink(missing_ok=True)   # interrupted VACUUM INTO leaves a corrupt file
        raise
    return target
```

Verified facts [CITED: sqlite.org/lang_vacuum.html]:
- filename may be any SQL expression → parameter binding is legal;
- target must not already exist (or must be empty) or the command fails — timestamped names avoid this; still catch and clean up;
- output is a consistent snapshot, safe to take while the app is running under WAL;
- an interrupted VACUUM INTO can leave a corrupt output file → delete target on failure.

### Pattern 5: FastAPI lifespan startup backup (D-09)

```python
# Source: fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.backup_on_startup and Path(settings.db_path).exists() and db_has_data():
        create_backup(engine, Path(settings.backup_dir))
        prune_backups(Path(settings.backup_dir), keep=30)
    yield

app = FastAPI(title="MyOriShop", lifespan=lifespan)
```

`@app.on_event("startup")` is deprecated; passing `lifespan` disables any `on_event` handlers [CITED: fastapi.tiangolo.com/advanced/events/]. The backup call is sync — fine to call directly in the lifespan body before `yield` (runs once before serving; blocking a not-yet-serving app is exactly what D-09 wants).

**Settings additions** (`app/config.py`): `backup_dir: str = "backups"`, `backup_on_startup: bool = True`, `backup_keep: int = 30`. The boolean gate exists specifically for tests (see Pitfall 1).

### Pattern 6: restore.bat (D-11)

```bat
@echo off
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: restore.bat backups\myorishop-YYYYMMDD-HHMMSS.db
  dir /b backups
  pause & exit /b 1
)
rem The app MUST be stopped before restoring.
copy /y "%~1" data\myorishop.db
del /q data\myorishop.db-wal 2>nul
del /q data\myorishop.db-shm 2>nul
echo Restore complete. Start the app with run.bat.
pause
```

Deleting `-wal`/`-shm` is mandatory: overwriting a database file without removing its stale WAL/journal is a documented corruption vector — SQLite would replay the OLD wal into the NEW file [CITED: sqlite.org/howtocorrupt.html §1.2, §1.4]. VACUUM INTO output is standalone (fresh file, no sidecar files), which is why it is the safe backup format here.

### Anti-Patterns to Avoid

- **Bypassing `record_operation`:** never insert Operation rows or touch `products.quantity` anywhere else — the append-only triggers and IN-01/IN-02 guards live in the single write path [VERIFIED: codebase].
- **f-string path interpolation into VACUUM INTO:** Windows backslashes + quotes break the SQL; use the bound parameter form.
- **Web-endpoint restore or user-supplied backup filenames:** restore happens app-stopped via script; the /backup page only lists server-enumerated files and never accepts a path parameter (no traversal surface).
- **`session.execute("VACUUM INTO ...")` on a normal Session/connection:** fails with "cannot VACUUM from within a transaction" [CITED: sqlalchemy discussion #6959].
- **Editing product name/code from the receipt form for existing products:** receipt updates prices only (D-07); name field is autofill/informational once the product exists (see Open Question 1).
- **Negative or zero quantity receipts:** D-01 locks qty_delta > 0; corrections are Phase 5 (OPS-03).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Consistent live-DB backup | manual file copy of a WAL-mode DB while app runs | `VACUUM INTO` (locked D-08) | copying db+wal+shm mid-write is a documented corruption vector [CITED: sqlite.org/howtocorrupt.html §1.1–1.2] |
| Money parsing | new qty/price parsers | `app.core.to_cents` (comma+dot, ROUND_HALF_UP) + `catalog.parse_optional_cents` | already handles RU comma, inf/nan, error shape [VERIFIED: codebase] |
| Product auto-create + audit | fresh create logic in receipts | `catalog.create_product` shape (or extract shared helper) | duplicate-code race handling (WR-04 partial unique index + IntegrityError translation) already solved [VERIFIED: codebase] |
| Price history on intake | custom price log | existing `price_change` op machinery (D-07 explicitly reuses CAT-04) | one op per changed field, old value snapshotted pre-mutation (Pitfall 7 of Phase 2) [VERIFIED: codebase] |
| Name autofill | new JS | Phase 2 lookup pattern: debounced hx-get, 204 no-op, swap-time guard | shipped and UAT-passed in Phase 2 [VERIFIED: codebase] |
| Startup hook | custom "run once" flags, threading | FastAPI `lifespan` | official, runs before serving, testable via TestClient context manager [CITED: fastapi docs] |

**Key insight:** this phase's receipt track is composition, not construction — every risky sub-problem (atomic multi-op transactions, duplicate races, Cyrillic-safe fields, money parsing) was solved in Phases 1–2; re-solving any of them locally would fork behavior.

## Common Pitfalls

### Pitfall 1: Startup backup fires during pytest runs
**What goes wrong:** `tests/conftest.py` uses `with TestClient(app)` — the context-manager form runs lifespan [CITED: fastapi docs] — so every test using the `client` fixture would VACUUM the developer's real `data/myorishop.db` into `backups/`, churning retention and slowing tests.
**Why it happens:** lifespan uses the module-level `app.db.engine`/settings, not the overridden test session.
**How to avoid:** gate on `settings.backup_on_startup` and disable it in tests (env var / monkeypatch in the `client` fixture, e.g. set `BACKUP_ON_STARTUP=false` before `app.main` import, or monkeypatch settings). Also keep the "skip if DB missing/empty" guard (D-09).
**Warning signs:** `backups/` files appearing after `uv run pytest`.

### Pitfall 2: "cannot VACUUM from within a transaction"
**What goes wrong:** running VACUUM INTO through a normal Session or `engine.begin()` fails.
**Why it happens:** SQLAlchemy wraps statements in a transaction; SQLite forbids VACUUM inside one [CITED: sqlite.org/lang_vacuum.html; sqlalchemy discussion #6959].
**How to avoid:** `engine.connect().execution_options(isolation_level="AUTOCOMMIT")` + `exec_driver_sql("VACUUM INTO ?", (path,))`.
**Warning signs:** OperationalError naming VACUUM in the message.

### Pitfall 3: Stale -wal/-shm after restore corrupts the restored DB
**What goes wrong:** copying a backup over `data/myorishop.db` while old `myorishop.db-wal`/`-shm` files remain → SQLite replays the old WAL into the new file on next open.
**Why it happens:** WAL sidecar files belong to the *previous* database generation [CITED: sqlite.org/howtocorrupt.html §1.4].
**How to avoid:** restore.bat deletes both sidecar files after the copy; procedure requires the app stopped.
**Warning signs:** "database disk image is malformed" or resurrected/lost rows after restore.

### Pitfall 4: VACUUM INTO target already exists / partial file on failure
**What goes wrong:** command fails if the target exists and is non-empty; an interrupted run leaves a corrupt file that later looks like a valid backup.
**How to avoid:** timestamped filename (`YYYYMMDD-HHMMSS` sorts lexicographically = chronologically, matching the project's ISO-sorting convention); wrap in try/except and `unlink(missing_ok=True)` the target on any failure before re-raising [CITED: sqlite.org/lang_vacuum.html].
**Warning signs:** 0-byte or undersized files in `backups/`.

### Pitfall 5: Receipt for a soft-deleted product's code
**What goes wrong:** an active-product lookup by code misses a soft-deleted product; auto-create then makes a NEW product with the same code — legal (partial unique index allows it) but potentially surprising; conversely, passing the soft-deleted product's id to `record_operation` raises the IN-01 rejection.
**How to avoid:** the receipt service must query `deleted_at IS NULL` products only (same as `create_product`'s duplicate check) and let auto-create proceed — that matches Phase 2 semantics (deleted products may share codes). Add a test for this path.
**Warning signs:** ValueError "product is deleted" bubbling to the route.

### Pitfall 6: Focus/clear loop breaking the fast-entry core value
**What goes wrong:** relying on `autofocus` inside swapped content — behavior undocumented in htmx [CITED: htmx.org/docs]; focus stays on the submit button and the operator has to click for every box item.
**How to avoid:** explicit `document.getElementById('code').focus()` via `hx-on::htmx:load` on the fresh form partial (or after-settle on wrapper); manual verification step in the plan (UI hint = yes for this phase).
**Warning signs:** UAT: after save, typing does nothing until a click.

### Pitfall 7: Lookup response overwrites operator-typed values
**What goes wrong:** the debounced lookup returns after the operator already typed a name/prices, clobbering their input.
**How to avoid:** replicate the Phase 2 swap-time guard (`hx-on::before-swap` checking non-empty fields → `shouldSwap = false`) and the server-side 204-when-name-present contract [VERIFIED: codebase `product_form.html`, `routes/dictionary.py`].
**Warning signs:** typed prices vanish ~300ms after typing a known code.

### Pitfall 8: run.bat migration ordering vs startup backup
**What goes wrong:** `run.bat` runs `alembic upgrade head` BEFORE uvicorn starts, so the lifespan backup captures the DB *after* migrations — a botched future migration is not protected by the startup backup.
**How to avoid:** this phase needs no migration, so risk is zero now; note the ordering in the backup page docs. Optional discretion-level hardening: add a backup invocation in run.bat before alembic (see Open Question 3).
**Warning signs:** none in this phase.

## Code Examples

### Recent receipts query (D-04)

```python
# Reuses ordering convention from ledger_view / price_history (created_at desc, seq desc)
from sqlalchemy import select
from app.models import Operation, Product

def recent_receipts(session, limit: int = 10):
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(Operation.type == "receipt")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
```

### Retention pruning (D-10)

```python
def prune_backups(backup_dir: Path, keep: int = 30) -> None:
    files = sorted(backup_dir.glob("myorishop-*.db"))  # timestamp names sort chronologically
    for old in files[:-keep]:
        old.unlink()
```

Called only AFTER a successful `create_backup` (D-10: "older ones deleted automatically after a successful new backup").

### Restore verification test (D-11 — "restore verified at least once")

```python
def test_backup_and_restore_roundtrip(tmp_path, engine, session, product):
    # 1. write real data through the sanctioned path
    record_operation(session, type_="receipt", product_id=product.id,
                     qty_delta=5, unit_cost_cents=1000)
    # 2. backup the live engine
    backup_file = create_backup(engine, tmp_path / "backups")
    # 3. "restore": copy backup to a fresh live path (simulates restore.bat copy step)
    restored_path = tmp_path / "restored.db"
    shutil.copyfile(backup_file, restored_path)
    # 4. open restored DB with the production engine factory and read data back
    restored_engine = build_engine(str(restored_path))
    with sessionmaker(bind=restored_engine)() as restored_session:
        assert restored_session.get(Product, product.id).quantity == 5
        assert compute_stock(restored_session, product.id) == 5
```

`build_engine` re-applies WAL + foreign_keys pragmas on the restored copy [VERIFIED: codebase `app/db.py`]. Note: append-only triggers live in the DB file itself (created by migration/fixture), so they survive the VACUUM copy — VACUUM INTO preserves schema objects including triggers [ASSUMED — standard VACUUM behavior; the test can assert it by attempting an UPDATE on operations in the restored DB].

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `@app.on_event("startup")` | `lifespan` asynccontextmanager | FastAPI ~0.93+, on_event now deprecated | startup backup must use lifespan [CITED: fastapi docs] |
| copy .db file for backup | `VACUUM INTO` / backup API for live WAL DBs | SQLite 3.27 (2019) [ASSUMED: version date] | safe hot backup, already a locked decision |
| htmx `hx-on:htmx:after-request` (1.x colon syntax) | `hx-on::after-request` double-colon shorthand in htmx 2 | htmx 2.0 | use the 2.x syntax with the vendored 2.0.10 file |

**Deprecated/outdated:** nothing else relevant; stack pinned by CLAUDE.md is current.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | VACUUM INTO minimum SQLite version is 3.27 (2019) | Standard Stack / State of the Art | None — local runtime is 3.50.4 [VERIFIED: local probe] |
| A2 | VACUUM INTO preserves triggers/schema objects in the output file | Code Examples | Restore could silently lose append-only enforcement; mitigated by asserting trigger behavior in the restore test |
| A3 | Prices on the receipt form are optional (empty → NULL), mirroring CAT-01 field optionality, while quantity is required > 0 | Pattern 1 | If user expects all four prices mandatory, add required-validation — one-line change; flagged as Open Question 2 |

## Open Questions

1. **Existing product + operator edits the name field during receipt — what happens?**
   - What we know: D-07 says receipts update *prices* on the card; D-03 pre-fills name from the product; Phase 2 has `product_edited` ops for name changes.
   - What's unclear: whether a name typed over the pre-fill should rename the product.
   - Recommendation: ignore name changes for existing products in v1 (receipt touches prices only); renames go through /products/{id}/edit. Simplest, no surprise renames from autofill races.
2. **Are cost/catalog/sale prices required on a receipt?**
   - What we know: RCP-01 lists all four fields; product card prices are optional (CAT-01); `parse_optional_cents` exists.
   - Recommendation: quantity required (> 0 integer); prices optional (empty → NULL, no price_change op for empty fields). Keeps fast entry fast and matches card optionality. Planner may tighten to "cost required" if profit math needs it later (SAL-05 snapshots at sale time anyway).
3. **Pre-migration backup in run.bat?**
   - What we know: run.bat migrates before uvicorn starts; lifespan backup therefore runs post-migration (Pitfall 8). D-09 locks startup backup; it does not forbid an additional call.
   - Recommendation: implement lifespan per D-09 now; optionally expose `uv run python -m app.services.backup` and call it in run.bat before alembic — cheap insurance, Claude's-discretion scope. Not required for BCK-01.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | runtime | ✓ | 3.13.13 [VERIFIED: local probe] | — |
| SQLite (stdlib sqlite3) | VACUUM INTO | ✓ | 3.50.4 (≥3.27 needed) [VERIFIED: local probe] | — |
| uv | run/test commands | ✓ | 0.11.11 [VERIFIED: local probe] | pip + venv |
| Windows cmd (restore.bat) | D-11 restore script | ✓ | Windows 11 [VERIFIED: env] | — |
| All Python deps | app | ✓ | pinned in pyproject.toml, installed (tests pass in Phase 2) | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** none needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* (installed, dev group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=.) |
| Quick run command | `uv run pytest tests/test_receipts.py tests/test_backup.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RCP-01 | receipt increases stock; op row carries qty/cost/price; auto-create for unknown code; price_change ops for existing product; one-transaction atomicity; validation errors (qty ≤ 0, bad money) | unit + integration (TestClient) | `uv run pytest tests/test_receipts.py -x` | ❌ Wave 0 |
| RCP-02 | lookup endpoint returns name fragment for known code, 204 for unknown/name-present; product code pre-fills prices | integration (TestClient) | `uv run pytest tests/test_receipts.py -x -k lookup` | ❌ Wave 0 |
| BCK-01 | create_backup produces openable snapshot; failure cleans partial file; retention keeps 30; startup gate flag; restore roundtrip reads data back | unit (tmp_path engines) | `uv run pytest tests/test_backup.py -x` | ❌ Wave 0 |
| RCP-01/02 UX | form clears + focus returns to code field after save (D-02) | manual-only — DOM focus not testable via TestClient | human verification (phase UAT, ui hint = yes) | n/a |
| BCK-01 script | restore.bat end-to-end on Windows | manual-only — batch script replaces live file with app stopped | human verification once (D-11 also covered by automated roundtrip test) | n/a |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_receipts.py tests/test_backup.py -x -q` (plus `uv run ruff check .`)
- **Per wave merge:** `uv run pytest -q`
- **Phase gate:** full suite green + ruff clean before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_receipts.py` — covers RCP-01, RCP-02
- [ ] `tests/test_backup.py` — covers BCK-01 (backup, retention, restore roundtrip)
- [ ] conftest addition: disable `backup_on_startup` for the `client` fixture (Pitfall 1)

## Security Domain

### Applicable ASVS Categories (L1)

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | single local operator, no auth in v1 (locked project decision) |
| V3 Session Management | no | no sessions in v1 |
| V4 Access Control | no | localhost-only, single user; uvicorn bound to 127.0.0.1 [VERIFIED: codebase run.bat] |
| V5 Input Validation | yes | server-side: `to_cents` for money, strict positive-int parse for quantity, code/name strip+required; RU error messages; 422 responses. Jinja2 autoescape on, no `|safe` (Phase 2 convention) |
| V6 Cryptography | no | none needed |
| V12 Files & Resources | yes | backup filenames generated server-side only; /backup page never accepts a path/filename parameter (no traversal); restore only via offline script; `backups/` git-ignored (`*.db` already ignored [VERIFIED: codebase .gitignore] — add explicit `backups/` entry per CONTEXT) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via VACUUM INTO path | Tampering | bound parameter (`exec_driver_sql("VACUUM INTO ?", (path,))`), never f-string |
| Path traversal on backup listing/restore | Information Disclosure / Tampering | list only server-enumerated `backups/*.db`; no user-supplied paths in any endpoint |
| Ledger tampering | Tampering / Repudiation | append-only DB triggers + single write path (existing, do not bypass) |
| XSS via product names in recent-receipts partial | Tampering | Jinja2 autoescape (existing convention: no `|safe`, no HTML built in Python) |
| Backup file exposure | Information Disclosure | local folder only, offline app; never serve backup files over HTTP for download in v1 |

## Sources

### Primary (verified via local tools)
- Codebase: `app/services/ledger.py`, `app/services/catalog.py`, `app/services/dictionary.py`, `app/routes/dictionary.py`, `app/db.py`, `app/core.py`, `app/config.py`, `app/main.py`, `app/models.py`, `tests/conftest.py`, `app/templates/*`, `pyproject.toml`, `run.bat`, `.gitignore` — read this session
- Local probes: Python 3.13.13, SQLite 3.50.4, uv 0.11.11

### Secondary (official docs, MEDIUM per confidence seam)
- https://sqlite.org/lang_vacuum.html — VACUUM INTO transaction restriction, target-must-not-exist, filename-as-expression, snapshot consistency, interrupted-write corruption
- https://sqlite.org/howtocorrupt.html — §1.2/§1.4 stale journal/WAL corruption on file replacement
- https://fastapi.tiangolo.com/advanced/events/ — lifespan pattern, on_event deprecation, TestClient context-manager caveat
- https://htmx.org/docs/ — hx-on::after-request reset pattern, hx-swap-oob, autofocus behavior undocumented

### Tertiary (websearch, cross-checked)
- https://github.com/sqlalchemy/sqlalchemy/discussions/6959 + https://docs.sqlalchemy.org/en/20/dialects/sqlite.html — AUTOCOMMIT isolation for VACUUM via SQLAlchemy

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; versions verified locally
- Architecture (receipts): HIGH — pure composition of code read and verified this session
- Architecture (backup): MEDIUM-HIGH — mechanics cited from official SQLite/FastAPI docs; AUTOCOMMIT pattern cross-checked (websearch + official dialect docs); the lifespan-in-tests pitfall verified against conftest.py
- Pitfalls: HIGH for codebase-derived (1, 5, 7, 8); MEDIUM for doc-cited (2, 3, 4, 6)

**Research date:** 2026-07-08
**Valid until:** 2026-08-08 (stable stack, pinned versions)
