# Phase 15: Cash Ledger Foundation - Research

**Researched:** 2026-07-14
**Domain:** Second append-only ledger (`cash_movements`) grafted onto an existing FastAPI/SQLAlchemy 2.0/SQLite append-only stock-ledger app
**Confidence:** HIGH (all claims grounded in direct inspection of this repository; no external research needed per CONTEXT.md)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-00a:** Separate `cash_movements` table — NOT reusing `operations` (which has a NOT-NULL `product_id` FK and mandatory `batch_id`). Sync-ready shape copied from `Operation`: UUID PK, signed `amount_cents`, `device_id`/`seq`, `created_at`/`created_by`, nullable `sale_id` FK. Append-only BEFORE UPDATE/DELETE `RAISE(ABORT,…)` triggers mirroring `alembic/versions/0001_initial_schema.py`.
- **D-00b:** New `app/services/finance.py` — sibling to `ledger.py`, the SINGLE write path for `cash_movements`. Balance = live `SUM(amount_cents)` (no cache at this scale). Money stays Integer cents; no Decimal/money/accounting lib.
- **D-00c:** Wiring is at the SERVICE layer, inside the existing transactions — `register_sale` calls finance with `commit=False` before its trailing `session.commit()`; `register_return` does the symmetric debit inside its own commit. Never from the route layer (desktop + mobile callers both get it for free). Sale credit and return debit MUST ship together this phase.
- **D-00d:** Return debit is computed INDEPENDENTLY — `qty_returned ×` the origin sale op's frozen `unit_price_cents` (mirrors D-06/D-07 in `returns.py`), never reconciled against the prior credit row.
- **D-01:** Phase 15 shows the balance ONLY — one prominent current-balance figure, no movement list. Full history lands in Phase 16.
- **D-02:** Entry appears in BOTH places: desktop top nav (`base.html`, alongside Отчёты/Экспорт) AND a tile in the mobile hub (`mobile_pages/home.html`). A mobile-rendered balance page is in scope this phase.
- **D-03:** ONE aggregated `cash_movement` per sale — `amount_cents` = the sale total, linked via `sale_id`. A return likewise writes ONE debit movement.
- **D-04:** Heading «Баланс кассы». Render via `app.core.format_cents` (e.g. `12500` → `125,00`). Zero shows as `0,00`. NO currency symbol.

### Claude's Discretion
- Exact migration number/file name, trigger SQL text, `finance.py` function names (following `ledger.py`/`writeoffs.py` naming), route paths, and page template structure — follow existing conventions.
- Whether the desktop and mobile balance pages share a partial or each render their own — planner's call based on existing base-template patterns.

### Deferred Ideas (OUT OF SCOPE)
- **Movement history list on the Финансы page** → Phase 16 (FIN-07).
- **Manual withdrawals/deposits + negative-balance warn-but-allow** → Phase 16 (FIN-03, FIN-04, FIN-05).
- **Reports, CSV export, profit & stock-valuation dashboard** → Phase 17 (FIN-08…FIN-12).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIN-01 | Касса автоматически пополняется на сумму каждой продажи | `register_sale` already computes `total_cents` (`app/services/sales.py:266`); stage one `finance.record_cash_movement(category="sale", amount_cents=total_cents, sale_id=header.id, commit=False)` before the existing `session.commit()` at `sales.py:269`. Both desktop (`routes/sales.py:357`) and mobile (`routes/mobile_sales.py:316`) call the same service, so both credit automatically. |
| FIN-02 | Касса автоматически списывается при возврате товара (симметрично) | `register_return` copies the frozen `origin.unit_price_cents` (`app/services/returns.py:156`); compute the debit as `qty × origin.unit_price_cents` and write `finance.record_cash_movement(category="return", amount_cents=-debit, sale_id=origin.sale_id, commit=False)` inside the same transaction. Requires flipping the current `record_operation(..., commit=True)` at `returns.py:151-162` to `commit=False` + a trailing `session.commit()`. |
| FIN-06 | Отдельный раздел UI «Финансы» с текущим балансом кассы | New `GET /finance` route (mirror `routes/writeoffs.py`) + `pages/finance.html` showing `finance.compute_balance()` rendered via the `cents` Jinja filter; nav link in `base.html` and a mobile tile + `GET /m/finance` route (D-02). |
</phase_requirements>

## Summary

This is not a greenfield feature. The repository already solved this exact class of problem for stock: an append-only `operations` table written through a single-write-path function (`ledger.record_operation`), with DB-level immutability triggers, a sync-ready row shape (UUID PK, `device_id`/`seq`, `created_at`/`created_by`), and a live-`SUM()` recompute (`compute_stock`). Phase 15 clones that proven pattern into a **parallel** `cash_movements` table + a sibling `finance.py` service, and wires exactly two call sites (`register_sale` credit, `register_return` debit) inside their existing transactions. No new dependency, no new architectural shape.

Every recommendation below is grounded in a symbol I verified by reading the file. The four in-repo research documents (`SUMMARY.md`, `ARCHITECTURE.md`, `PITFALLS.md`) converge on one verdict — do NOT reuse `operations` for cash — and CONTEXT.md has locked that plus seven other decisions. This RESEARCH.md translates those decisions into a concrete, symbol-level build map a planner can task against.

**Primary recommendation:** Copy the `Operation`/`ledger.py`/`record_operation` triad into `CashMovement`/`finance.py`/`record_cash_movement`, drop the stock-specific columns (`product_id`, `batch_id`, `qty_delta`), keep everything else identical, and hook it into `register_sale` and `register_return` in the same transaction as the existing writes. Ship the credit and debit together.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Persist a cash event (append-only) | Database / Storage (`cash_movements` + triggers) | Service (`finance.record_cash_movement`) | Immutability is a DB-level guarantee (triggers); the single-write-path service is the only sanctioned insert path, mirroring `operations`/`ledger.py`. |
| Auto-credit on sale | Service (`sales.register_sale`) | Service (`finance.py`) | Business rule; must be in the service so both desktop and mobile callers get it (Anti-Pattern 3). Never the route. |
| Auto-debit on return | Service (`returns.register_return`) | Service (`finance.py`) | Symmetric obligation to the credit; same transaction as the `return` op. |
| Compute current balance | Service (`finance.compute_balance`) | Database (live `SUM`) | Read-only display value, no hot-path consumer → live SUM, no cache (Pitfall 4 / Pattern 3). |
| Render «Баланс кассы» | Frontend Server (Jinja2 templates) | Service (read) | Server-rendered HTMX page; money via the existing `cents` filter. |
| Nav entry (desktop + mobile) | Frontend Server (`base.html`, `mobile_pages/home.html`) | — | Static template edits (D-02). |

## Standard Stack

No new packages. This phase uses only what is already installed and verified in `CLAUDE.md`. There is nothing to `npm/pip install`.

### Core (reused, unchanged)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.51 | New `CashMovement` mapped class (`Mapped[]`/`mapped_column()`), same declarative style as `Operation` | `[VERIFIED: CLAUDE.md + app/models.py:240 Operation]` — repo-wide convention |
| Alembic | 1.18.5 | One new migration `0013` adding `cash_movements` + two append-only triggers | `[VERIFIED: alembic/versions/0012_dictionary_name_lc.py:23 down_revision chain]` |
| SQLite (stdlib) | bundled | Storage; WAL + `foreign_keys=ON` + `busy_timeout=5000` already configured per connection | `[VERIFIED: app/db.py:41-52 set_sqlite_pragma]` |
| FastAPI + Jinja2 + HTMX | 0.139.0 / 3.1.6 / 2.0.10 | Thin `/finance` + `/m/finance` routes, `pages/finance.html` | `[VERIFIED: app/routes/writeoffs.py, app/routes/__init__.py:9]` |

### Package Legitimacy Audit

Not applicable — this phase installs **zero** external packages. All code builds on already-present, already-verified dependencies (see `CLAUDE.md` Technology Stack, all pinned versions verified against PyPI on 2026-07-08). No SLOP/SUS risk surface.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
  POST /sales  (desktop)          POST /m/sales (mobile)          POST /returns / /m/returns
       │                                │                               │
       ▼                                ▼                               ▼
  routes/sales.py               routes/mobile_sales.py          routes/returns.py / mobile_returns.py
       └───────────────┬────────────────┘                             │
                       ▼                                              ▼
        services/sales.py :: register_sale()          services/returns.py :: register_return()
         ├─ loop: ledger.record_operation(commit=False)  ├─ ledger.record_operation(commit=False)  ← CHANGE from commit=True
         ├─ total_cents accumulated                       ├─ debit = qty × origin.unit_price_cents
         ├─ finance.record_cash_movement(                 ├─ finance.record_cash_movement(
         │     category="sale",                           │     category="return",
         │     amount_cents=+total_cents,                 │     amount_cents=-debit,
         │     sale_id=header.id, commit=False)  ← NEW    │     sale_id=origin.sale_id, commit=False)  ← NEW
         └─ session.commit()  (one transaction)           └─ session.commit()  (one transaction)
                       │                                              │
                       ▼                                              ▼
                    ┌─────────────────────────────────────────────────────┐
                    │  cash_movements  (append-only, trigger-guarded)       │
                    │  id, category, amount_cents(signed), note,            │
                    │  sale_id FK→sales.id, device_id, seq, created_at,     │
                    │  created_by, synced_at                                │
                    └─────────────────────────────────────────────────────┘
                                            ▲
                                            │  SELECT COALESCE(SUM(amount_cents),0)
   GET /finance  ──▶ routes/finance.py ──▶ finance.compute_balance() ──▶ pages/finance.html «Баланс кассы»
   GET /m/finance ─▶ mobile route      ──▶ finance.compute_balance() ──▶ mobile_pages/finance.html
```

### Recommended Project Structure
```
app/
├── models.py                     # + CashMovement class, + CASH_CATEGORIES dict
├── db.py                         # APPEND_ONLY_TRIGGERS: add 2 cash triggers (see Pitfall 3 below)
├── services/
│   ├── ledger.py                 # UNCHANGED — stays product/stock-only
│   ├── sales.py                  # register_sale(): + one finance call before commit
│   ├── returns.py                # register_return(): flip to staged write + finance debit
│   └── finance.py                # NEW — record_cash_movement, next_seq, compute_balance
├── routes/
│   ├── __init__.py               # (optional) + CASH_CATEGORIES global if template needs it
│   ├── finance.py                # NEW — GET /finance
│   └── mobile_finance.py         # NEW — GET /m/finance
├── templates/
│   ├── base.html                 # + «Финансы» nav link
│   ├── mobile_pages/home.html    # + «Финансы» tile
│   ├── pages/finance.html        # NEW — «Баланс кассы» figure
│   └── mobile_pages/finance.html # NEW — mobile balance (may share a partial)
├── main.py                       # + include_router(finance.router), include_router(mobile_finance.router)
alembic/versions/
└── 0013_cash_movements.py        # NEW — table + append-only triggers (revises 0012)
tests/
└── test_finance.py               # NEW — mirrors test_ledger.py
```

### Pattern 1: Parallel append-only ledger table (mirror `Operation`)
**What:** `CashMovement` copies `Operation`'s sync-ready shape but drops `product_id`, `batch_id`, `qty_delta`.
**When to use:** A new "kind of event" needing the same append-only/audit/sync guarantees but a different shape.
**Example (grounded in `app/models.py:240-275 Operation`):**
```python
# app/models.py — near the other type→label dicts (models.py:49 WRITEOFF_REASONS)
CASH_CATEGORIES = {
    "sale": "Продажа",     # system-generated credit (register_sale)
    "return": "Возврат",   # system-generated debit  (register_return)
    # supplier/salary/other/correction → Phase 16 manual movements (DEFERRED)
}

class CashMovement(Base):
    """Append-only cash ledger row (mirrors Operation). amount_cents is SIGNED
    (positive = приход, negative = расход). Immutability enforced by DB triggers."""
    __tablename__ = "cash_movements"
    __table_args__ = (UniqueConstraint("device_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(20), nullable=False)   # CASH_CATEGORIES key
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    note: Mapped[str | None] = mapped_column(String(300))
    sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", name="fk_cash_movements_sale_id_sales"), index=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)  # UTC ISO text
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    synced_at: Mapped[str | None] = mapped_column(String(32))
```
`[VERIFIED: app/models.py:240-275 Operation shape, :244 UniqueConstraint(device_id, seq), :259 sale_id FK naming convention]`
Note: the `NAMING_CONVENTION` at `app/models.py:24` auto-names the PK/UQ/IX; the explicit FK `name=` matches the existing `Operation.sale_id` precedent at `models.py:259-261`.

### Pattern 2: Single write path — `finance.record_cash_movement` (mirror `ledger.record_operation`)
**What:** The ONLY function that inserts `cash_movements` rows. Stamps audit fields from `settings`, computes `seq` via a `next_seq`-equivalent, honors a `commit` flag.
**Example (grounded in `app/services/ledger.py:23-129`):**
```python
# app/services/finance.py  (sibling of ledger.py, NOT a submodule)
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import settings
from app.core import new_id, utcnow_iso
from app.models import CASH_CATEGORIES, CashMovement

def next_seq(session: Session, device_id: str) -> int:
    """Next per-device seq for cash_movements (mirrors ledger.next_seq)."""
    current = session.scalar(
        select(func.max(CashMovement.seq)).where(CashMovement.device_id == device_id)
    )
    return (current or 0) + 1

def record_cash_movement(
    session: Session, *, category: str, amount_cents: int,
    sale_id: str | None = None, note: str | None = None, commit: bool = True,
) -> CashMovement:
    """The ONLY sanctioned write path for cash_movements (mirrors record_operation)."""
    if category not in CASH_CATEGORIES:
        raise ValueError(f"unknown cash category: {category!r}")
    mv = CashMovement(
        id=new_id(), category=category, amount_cents=amount_cents,
        sale_id=sale_id, note=note,
        device_id=settings.device_id, seq=next_seq(session, settings.device_id),
        created_at=utcnow_iso(), created_by=settings.operator_name,
    )
    session.add(mv)
    if commit:
        session.commit()
    return mv

def compute_balance(session: Session) -> int:
    """Live-recomputed cash balance (mirrors ledger.compute_stock)."""
    return session.scalar(
        select(func.coalesce(func.sum(CashMovement.amount_cents), 0))
    )
```
`[VERIFIED: app/services/ledger.py:23-33 next_seq, :104-129 record_operation add+commit, :132-138 compute_stock; app/core.py:15 new_id, :20 utcnow_iso; app/config settings.device_id/operator_name used at ledger.py:114-117]`

### Pattern 3: Sale credit hook (mirror the WR-03 staged-write discipline)
**Where:** inside `register_sale`'s existing `try` block, after the line loop, before `session.commit()`.
`[VERIFIED: app/services/sales.py:250-269 — total_cents accrues at :266, single session.commit() at :269, inside try at :250 that already catches (IntegrityError, ValueError) at :270]`
```python
    try:
        for line in resolved:
            ...
            record_operation(session, type_="sale", ..., commit=False)
            total_cents += qty * price_cents
        # NEW — same transaction, same total_cents.
        finance.record_cash_movement(
            session, category="sale", amount_cents=total_cents,
            sale_id=header.id, commit=False,
        )
        session.commit()   # unchanged — closes Sale + N Operation + 1 CashMovement atomically
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"basket": SAVE_ROLLBACK}
```
A zero-total basket cannot reach here — `register_sale` rejects an empty basket (`sales.py:108`) and requires a positive per-line price (`sales.py:129`).

### Pattern 4: Return debit hook — compute INDEPENDENTLY (D-00d / Pitfall 3)
**Where:** inside `register_return`'s existing `try` block. The current code calls `record_operation(..., commit=True)` at `returns.py:151-162` — this must become a **staged** write so cash + stock commit together.
`[VERIFIED: app/services/returns.py:147-170 — record_operation currently commit=True at :162; origin.unit_price_cents frozen copy at :156; qty validated positive at :135-137; remaining cap at :141-145]`
```python
    try:
        batch_id = _resolve_or_create_return_batch_id(session, origin)
        op = record_operation(
            session, type_="return", product_id=origin.product_id, qty_delta=qty,
            unit_price_cents=origin.unit_price_cents,  # D-07 frozen copy
            unit_cost_cents=origin.unit_cost_cents,
            sale_id=origin.sale_id, batch_id=batch_id,
            payload={"origin_op_id": origin.id},
            commit=False,                              # CHANGED from commit=True
        )
        # NEW — debit computed FRESH from the return's own qty × frozen price (Pitfall 3),
        # never looked up/reconciled against the prior sale-credit row.
        debit = qty * (origin.unit_price_cents or 0)
        if debit:
            finance.record_cash_movement(
                session, category="return", amount_cents=-debit,
                sale_id=origin.sale_id, commit=False,
            )
        session.commit()                               # NEW — one commit closes both writes
    except ValueError:
        session.rollback()
        return None, {"form": PRODUCT_UNAVAILABLE_ERROR}
    except IntegrityError:
        session.rollback()
        return None, {"form": SAVE_FAILED_ERROR}
```
Note the `(origin.unit_price_cents or 0)` guard: real sale ops always carry a price (required at `sales.py:129`), but a defensive `0` keeps a hypothetical NULL-priced legacy origin from raising. `register_return` handles ONE origin line per call, so each return call writes ONE debit — consistent with D-03 ("a return writes ONE debit movement").

### Anti-Patterns to Avoid
- **Reuse `operations` with `cash_in`/`cash_out` types** — `Operation.product_id` is NOT NULL (`models.py:248`) and `record_operation` unconditionally does `session.get(Product, ...)` + soft-delete guard (`ledger.py:79-86`) + mandatory-batch guard (`ledger.py:93-95`). Cash has no product/batch. Rejected by all research and locked out by D-00a.
- **Cache a `balance_cents` column** — no hot-path consumer exists (unlike the oversell check that forces `Product.quantity` to be cached). Live `SUM` has zero drift risk. Locked by D-00b.
- **Call `finance.py` from the sales/returns ROUTE** — there are two callers each (desktop + mobile, verified below); a route-level call credits only one. Locked by D-00c.
- **Match the return debit against the original credit row** — fragile (legacy sales, partial returns). Compute independently. Locked by D-00d.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-device sequence number | A global counter or `len()+1` | `next_seq()` mirroring `ledger.py:23` | UNIQUE(device_id, seq) is the sync backstop; single-writer + WAL serializes |
| Money formatting | `f"{x/100:.2f}"` or a new filter | `app.core.format_cents` via the registered `cents` Jinja filter | `[VERIFIED: app/core.py:49, app/routes/__init__.py:12]` — one sanctioned display point, comma separator, sign-aware |
| UUID / UTC timestamp | `uuid`/`datetime` inline | `app.core.new_id` / `utcnow_iso` | `[VERIFIED: app/core.py:15,20]` — the only sanctioned conversion points |
| Append-only enforcement | App-layer "don't update" checks | DB `BEFORE UPDATE/DELETE ... RAISE(ABORT,...)` triggers | `[VERIFIED: app/db.py:22-33, alembic/0001:38-49]` — DB-level guarantee, cannot be bypassed by a code path |
| Balance recompute | A running `+=` total | `compute_balance()` = live `SUM` | Mirrors `compute_stock` (`ledger.py:132`); always correct by construction |

**Key insight:** Every helper this phase needs already exists one file away. The work is *cloning a proven shape*, not inventing anything.

## Runtime State Inventory

This is an additive-schema phase (new table, new rows), not a rename/migration — most categories are N/A. One item is load-bearing:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | No pre-existing `cash_movements` data. Balance starts at 0 by design (Phase 15 has no opening-balance entry — that's Phase 16, DEFERRED). | None. Historical sales *before* this phase generate no retroactive credits — acceptable per scope. |
| Live service config | None — fully local, no external services. | None. |
| OS-registered state | None. | None — verified: no scheduler/daemon references cash. |
| Secrets/env vars | None — `settings.device_id`/`settings.operator_name` reused verbatim as audit sources. | None. |
| Build artifacts | **`app.db.APPEND_ONLY_TRIGGERS`** (`app/db.py:22`) is the LIVE trigger source that `tests/conftest.py:25` loops over to install triggers on the test-fixture DB (`Base.metadata.create_all` path). If the two new `cash_movements` triggers are added ONLY to migration 0013, the pytest `session`/`engine` fixture will NOT have them and append-only tests on cash will silently pass writes. | **Add the two `cash_movements` triggers to `APPEND_ONLY_TRIGGERS` in `app/db.py` AND freeze a copy in migration 0013.** Retype the tuple annotation from `tuple[str, str]` to `tuple[str, ...]`. |

## Common Pitfalls

### Pitfall 1: Adding cash triggers only to the migration, not to `app/db.py`
**What goes wrong:** Test fixtures build the schema via `Base.metadata.create_all` + the `APPEND_ONLY_TRIGGERS` loop (`conftest.py:24-27`), NOT via Alembic. Cash append-only tests would run against a table with no triggers and give false green.
**How to avoid:** Extend `app/db.py:APPEND_ONLY_TRIGGERS` with `cash_movements_no_update`/`cash_movements_no_delete` and freeze the identical DDL in migration 0013 (`WR-06`: migrations never import app code — duplicate, don't reference). `[VERIFIED: app/db.py:22-33, tests/conftest.py:24-27, alembic/0001:38-49,95-96]`
**Warning signs:** A `test_finance.py` UPDATE-is-rejected test that passes even when triggers are missing from the fixture.

### Pitfall 2: Leaving `register_return`'s `record_operation` at `commit=True`
**What goes wrong:** If the `return` op commits on its own (current `returns.py:162`) and the cash debit is a separate `session.commit()`, a failure between them leaves stock returned but the till un-debited (or vice versa) — non-atomic.
**How to avoid:** Flip `record_operation(..., commit=True)` → `commit=False`, add the finance debit with `commit=False`, and add ONE trailing `session.commit()` inside the try (Pattern 4). The existing `except (ValueError, IntegrityError): session.rollback()` (`returns.py:163-170`) already wraps it.
**Warning signs:** Two `session.commit()` calls in `register_return`; a return that leaves a `return` op with no matching debit.

### Pitfall 3: Crediting/debiting from the ROUTE instead of the SERVICE
**What goes wrong:** Mobile sales (`routes/mobile_sales.py:316`) and mobile returns (`routes/mobile_returns.py:121`) call the SAME services as desktop. A route-level finance call would skip the till for one channel entirely.
**How to avoid:** Both hooks live inside `register_sale`/`register_return`. `[VERIFIED: routes/sales.py:357, routes/mobile_sales.py:316 both call register_sale; routes/returns.py:116, routes/mobile_returns.py:121 both call register_return]`
**Warning signs:** `import finance` appearing in any `routes/*.py`.

### Pitfall 4: Balance/profit conflation in UI copy
**What goes wrong:** PITFALLS.md #9 warns operators may read «баланс кассы» as profit. D-04 has LOCKED the heading as «Баланс кассы» (not the research's suggested «Наличные в кассе»).
**How to avoid:** Honor D-04 verbatim. If desired, the planner may add a one-line clarifying subtext, but the heading text is fixed. Zero renders as `0,00` (`format_cents(0)` → `"0,00"`, verified at `core.py:49-53`).

### Pitfall 5: Category value for the return debit
**What goes wrong:** The debit needs a `category` that passes the `CASH_CATEGORIES` allow-list in `record_cash_movement`. Using `"sale"` for a debit is misleading for the Phase 16 history view.
**How to avoid:** Add a `"return"` key to `CASH_CATEGORIES` (recommended above). This is Claude's discretion per CONTEXT, but a distinct category keeps future history/reporting clean. `[ASSUMED — see Assumptions Log A1]`

## Code Examples

### Migration (grounded in `alembic/0001` + `0012`)
```python
# alembic/versions/0013_cash_movements.py
revision = "0013"
down_revision = "0012"   # [VERIFIED: 0012 is current head]

_CASH_TRIGGERS = (
    """CREATE TRIGGER cash_movements_no_update BEFORE UPDATE ON cash_movements
       BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END""",
    """CREATE TRIGGER cash_movements_no_delete BEFORE DELETE ON cash_movements
       BEGIN SELECT RAISE(ABORT, 'cash ledger is append-only'); END""",
)

def upgrade() -> None:
    op.create_table(
        "cash_movements",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("sale_id", sa.String(36), nullable=True),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column("synced_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cash_movements")),
        sa.ForeignKeyConstraint(["sale_id"], ["sales.id"],
            name=op.f("fk_cash_movements_sale_id_sales")),
        sa.UniqueConstraint("device_id", "seq", name=op.f("uq_cash_movements_device_id")),
    )
    op.create_index(op.f("ix_cash_movements_sale_id"), "cash_movements", ["sale_id"])
    for stmt in _CASH_TRIGGERS:
        op.execute(stmt)

def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS cash_movements_no_update")
    op.execute("DROP TRIGGER IF EXISTS cash_movements_no_delete")
    op.drop_index(op.f("ix_cash_movements_sale_id"), table_name="cash_movements")
    op.drop_table("cash_movements")
```
Plain `op.create_table` — NO batch mode needed (batch mode is only for ALTER on existing tables; this is a fresh CREATE, exactly like `operations` in 0001). `[VERIFIED: alembic/0001:56-96 create_table + trigger loop; 0012:29 plain add_column comment confirms batch only for ALTER]`

### Route (grounded in `routes/writeoffs.py` + `mobile_reports.py`)
```python
# app/routes/finance.py
@router.get("/finance")
def finance_page(request: Request, session: Session = Depends(get_session)):
    context = {"balance_cents": compute_balance(session)}
    return templates.TemplateResponse(request, "pages/finance.html", context)

# app/routes/mobile_finance.py  (mirror mobile_reports.py:17 — /m/ prefix)
@router.get("/m/finance")
def mobile_finance_page(request: Request, session: Session = Depends(get_session)):
    context = {"balance_cents": compute_balance(session)}
    return templates.TemplateResponse(request, "mobile_pages/finance.html", context)
```
Register both in `app/main.py` `include_router` list (`main.py:53-79`). `[VERIFIED: routes/writeoffs.py:25-33 GET page shape; routes/mobile_reports.py:17-23 /m/ prefix; main.py:63,70 include_router pattern]`

### Template money rendering
```html
<!-- pages/finance.html -->
<h1>Баланс кассы</h1>
<p class="cash-balance">{{ balance_cents | cents }}</p>
```
`{{ 12500 | cents }}` → `125,00`; `{{ 0 | cents }}` → `0,00`. `[VERIFIED: app/routes/__init__.py:12 templates.env.filters["cents"] = format_cents]`

### Nav edits
- Desktop: add to `base.html` nav (`base.html:26-42`), after `/reports`/`/export` per D-02:
  `<a href="/finance"{% if request.url.path.startswith("/finance") %} class="active"{% endif %}>Финансы</a>`
- Mobile: add a tile to `mobile_pages/home.html` (`home.html:5-14`):
  `<a class="mobile-tile" href="/m/finance">Финансы</a>`
`[VERIFIED: base.html:37-38 Отчёты/Экспорт links; mobile_pages/home.html:5-14 tile grid]`

## Validation Architecture

Nyquist validation is **enabled** (`config.json:24 "nyquist_validation": true`). This section maps each success criterion to an automated pytest assertion.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (per `CLAUDE.md`; `[VERIFIED: tests/ dir with 39 test files, tests/conftest.py fixtures]`) |
| Config file | none dedicated — fixtures in `tests/conftest.py`; run via `uv run` per `CLAUDE.md` |
| Quick run command | `uv run pytest tests/test_finance.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FIN-01 | A committed sale writes exactly ONE `cash_movements` row with `amount_cents == total_cents`, `category=="sale"`, `sale_id==header.id`; balance rises by the sale total | integration | `uv run pytest tests/test_sales.py -k credit` | ❌ Wave 0 (add assertion to existing test_sales.py) |
| FIN-01 | A rolled-back sale (oversell-confirmed-off / bad line / IntegrityError) writes ZERO cash rows | integration | `uv run pytest tests/test_sales.py -k rollback` | ❌ Wave 0 |
| FIN-02 | Sell then FULLY return → balance returns to the pre-sale value; debit == `qty × origin.unit_price_cents`, `category=="return"`, negative sign | integration | `uv run pytest tests/test_returns.py -k debit` | ❌ Wave 0 (add to test_returns.py) |
| FIN-02 | Partial return debits only the returned qty × frozen price (independent computation, not matched to the credit) | integration | `uv run pytest tests/test_returns.py -k partial` | ❌ Wave 0 |
| FIN-02 | Return op + cash debit are ONE transaction — a forced failure leaves zero of both | integration | `uv run pytest tests/test_returns.py -k atomic` | ❌ Wave 0 |
| FIN-06 | `compute_balance` on empty ledger returns 0; sum of mixed credit/debit rows correct | unit | `uv run pytest tests/test_finance.py -k balance` | ❌ Wave 0 |
| FIN-06 | UPDATE and DELETE on `cash_movements` both ABORT with "append-only" (both via fixture triggers) | unit | `uv run pytest tests/test_finance.py -k append_only` | ❌ Wave 0 |
| FIN-06 | `record_cash_movement` stamps `created_by`/`device_id`, increments `seq`, rejects unknown category | unit | `uv run pytest tests/test_finance.py -k contract` | ❌ Wave 0 |
| FIN-06 | Balance renders via `cents` filter (`0`→`0,00`, `12500`→`125,00`) | route/e2e | `uv run pytest tests/test_finance.py -k page` (TestClient GET /finance, assert markup) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_finance.py -x`
- **Per wave merge:** `uv run pytest tests/test_finance.py tests/test_sales.py tests/test_returns.py`
- **Phase gate:** `uv run pytest` full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_finance.py` — NEW; mirror `tests/test_ledger.py` structure: append-only UPDATE/DELETE rejection (`test_ledger.py:57-79`), `compute_balance` correctness, audit-fields/seq (`test_ledger.py:127-141`), unknown-category ValueError, GET /finance page render.
- [ ] `tests/test_sales.py` — add: sale credits till by exact `total_cents`; rolled-back sale writes zero cash rows.
- [ ] `tests/test_returns.py` — add: full return restores pre-sale balance; partial return debits independently; atomicity.
- [ ] `tests/conftest.py` — no new fixture strictly required (`session`, `product`, `batch`, `stocked_product`, `customer` cover it); a small `cash_movements`-count helper may be inlined per-test. The `APPEND_ONLY_TRIGGERS` loop (`conftest.py:24-27`) will auto-install the two cash triggers ONCE they are added to `app/db.py` (see Runtime State Inventory).
- [ ] Framework install: none — pytest already present.

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1` (`config.json:46-47`). This is a local, offline, single-operator app with no auth — "security" here means preserving the integrity guarantees the ledger depends on.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single local operator, no auth in v1 (`CLAUDE.md`) |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | No multi-user access model in v1 |
| V5 Input Validation | partial | Phase 15 has NO new user-entered numeric input (balance is display-only; credit/debit are system-generated from already-validated sale/return flows). The only server-side allow-list is `category ∈ CASH_CATEGORIES` in `record_cash_movement` — enforce it (mirrors `writeoffs.py:69` reason-code check). Manual-debit input validation lands in Phase 16. |
| V6 Cryptography | no | No secrets/crypto in this phase |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Ledger row tampering (edit/delete a past cash movement) | Tampering | DB-level `BEFORE UPDATE/DELETE RAISE(ABORT)` triggers (`app/db.py` + migration 0013) — no app route may UPDATE/DELETE a movement |
| Injecting an out-of-allow-list category | Tampering | Server-side `category not in CASH_CATEGORIES` guard in `record_cash_movement` (mirrors `writeoffs.py:69`) |
| Free-text `note` rendered unescaped (future history/CSV) | Injection | Jinja2 autoescape (default) + reuse `export.py` CSV-safety convention later — no unescaped path introduced this phase (no note is user-entered in Phase 15) |
| Duplicate sale submission double-crediting the till | (pre-existing app-wide gap, PITFALLS #5) | Out of scope for Phase 15; flag as a known deferred item — a UI submit-guard/idempotency key is a separate concern. `[ASSUMED — A2]` |

## State of the Art

Not applicable — no external technology moved. This phase is an internal integration against a stable, in-repo pattern (append-only ledger) already shipped across Phases 1–14. No deprecated approaches to migrate off.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Adding a distinct `"return"` category to `CASH_CATEGORIES` (vs. reusing `"sale"` with a negative amount) is the cleaner choice | Pitfall 5 / Pattern 1 | Low — CONTEXT marks category naming as Claude's discretion; either works. A distinct category only benefits the Phase 16 history/report view. Planner may decide. |
| A2 | Duplicate-sale idempotency remains OUT of scope for Phase 15 (UI submit-guard deferred) | Security Domain | Low — consistent with SUMMARY.md "Gaps" and the phase's balance-only scope; but if the user wants a submit-guard now, it must be added to the plan explicitly. |
| A3 | Historical (pre-Phase-15) sales generate no retroactive cash credits; balance legitimately starts at 0 | Runtime State Inventory | Low — matches D-01 (no opening balance until Phase 16). Operator with existing cash-on-hand sees 0 until Phase 16 — acceptable per locked scope. |

**Note:** A1 and A2 need only light confirmation; none block planning. A3 is a direct consequence of locked decisions.

## Open Questions

1. **Should the return debit be one lump per return call, or split per sale line?**
   - What we know: `register_return` processes ONE origin `sale` op (one product line) per call (`returns.py:116-176`); D-03 says "a return writes ONE debit movement."
   - What's unclear: nothing material — one call = one line = one debit is internally consistent. A multi-line sale returned line-by-line produces multiple debit rows, each independently computed, summing to the credit when fully returned.
   - Recommendation: One debit per `register_return` call (Pattern 4). No further decision needed.

2. **Desktop vs mobile balance page: shared partial or two templates?**
   - What we know: D-02 requires both; CONTEXT leaves the structure to the planner.
   - Recommendation: Two thin routes (`/finance`, `/m/finance`) both calling `compute_balance`; templates may share a `partials/cash_balance.html` figure fragment or each inline it. Low stakes — either is fine.

## Environment Availability

Skipped — no external dependencies. Phase 15 is code + one additive migration against the already-present Python/SQLAlchemy/SQLite/pytest toolchain. `[VERIFIED: no new package; all tooling in CLAUDE.md already installed and used by 39 existing test files]`

## Project Constraints (from CLAUDE.md)

- Money as **Integer cents** only — never Float/Numeric. `amount_cents: Integer`, verified by the frozen conventions test (`test_ledger.py:110-120` asserts every `*_cents` column is Integer across all tables — `CashMovement.amount_cents` will be checked automatically).
- **Portable SQLAlchemy ORM only** — no SQLite-specific SQL in queries; `compute_balance` uses portable `func.coalesce`/`func.sum`. Triggers are raw SQLite DDL but that is confined to migration + `app/db.py` (same as `operations`, acceptable precedent).
- **Sync-ready shape** — UUID PK, `device_id`/`seq` with `UniqueConstraint`, timezone-aware UTC `created_at`, `synced_at` cursor. `CashMovement` copies all of these from `Operation`.
- **WAL + `foreign_keys=ON` + `busy_timeout`** — already applied per connection (`app/db.py:41-52`); the new `sale_id` FK is enforced.
- **Sync `Session` + `def` endpoints** — no async. Followed.
- **Smallest safe change** — `ledger.py` stays UNCHANGED; `sales.py`/`returns.py` get minimal additive edits (one call + one commit-flag flip), not rewrites.
- **GSD workflow** — implementation must proceed through the planned phase (this RESEARCH.md feeds the planner).

## Sources

### Primary (HIGH confidence — direct code inspection, this repository)
- `app/models.py` — `Operation` (:240-275), `Sale` (:299-315), `WRITEOFF_REASONS` (:49), `NAMING_CONVENTION` (:24), `Base` (:73)
- `app/services/ledger.py` — `next_seq` (:23), `record_operation` (:36-129), `compute_stock` (:132), `rebuild_stock` (:164)
- `app/services/sales.py` — `register_sale` (:81-278), `total_cents` (:266), commit (:269), try/except (:250-272)
- `app/services/returns.py` — `register_return` (:116-176), frozen `unit_price_cents` (:156), `record_operation(commit=True)` (:151-162)
- `app/services/writeoffs.py` — service+category-validation shape (`register_writeoff` :32, reason allow-list :69)
- `app/core.py` — `format_cents` (:49), `new_id` (:15), `utcnow_iso` (:20), `to_cents` (:28)
- `app/db.py` — `APPEND_ONLY_TRIGGERS` (:22-33), `set_sqlite_pragma` (:41-52)
- `alembic/versions/0001_initial_schema.py` — table + trigger template (:38-96); `0012` — current head, chain (:23-25)
- `app/routes/__init__.py` — `cents` filter + template globals (:9-18); `app/routes/writeoffs.py` — route shape; `app/routes/mobile_reports.py` — `/m/` prefix; `app/main.py` — `include_router` list (:53-79)
- `app/templates/base.html` (nav :26-42), `app/templates/mobile_pages/home.html` (tiles :5-14)
- `tests/conftest.py` — fixtures + trigger-install loop (:24-27); `tests/test_ledger.py` — append-only/audit test patterns; `tests/test_returns.py` — `_make_sale` helper
- `.planning/config.json` — workflow flags; `.planning/REQUIREMENTS.md` — FIN-01/02/06 (:12-17)
- `.planning/research/{SUMMARY,ARCHITECTURE,PITFALLS}.md` — in-repo architectural verdict (HIGH confidence, codebase-grounded)

### Secondary / Tertiary
- None — CONTEXT.md confirms this phase needs no external research.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new packages; every symbol verified in-repo.
- Architecture: HIGH — direct clone of an already-shipped, 14-phase-proven pattern; all decisions locked in CONTEXT.
- Pitfalls: HIGH — each read directly from the code path it concerns (conftest trigger loop, returns commit flag, dual desktop/mobile callers).

**Research date:** 2026-07-14
**Valid until:** stable — internal integration, no external version drift. Re-verify only if `ledger.py`/`sales.py`/`returns.py`/`db.py`/`conftest.py` change before planning.
