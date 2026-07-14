# Architecture Research

**Domain:** Касса / Финансы module integration into an existing append-only Operation-ledger app (MyOriShop, v1.3)
**Researched:** 2026-07-14
**Confidence:** HIGH — based on direct inspection of the current codebase (`app/models.py`, `app/services/ledger.py`, `app/services/sales.py`, `app/services/writeoffs.py`, `app/services/operations.py`, `app/routes/sales.py`, `alembic/versions/0001_initial_schema.py`, `app/db.py`, `app/config.py`, `app/core.py`, `app/main.py`, `app/templates/base.html`), not external ecosystem research. This is a project-specific integration design, not a generic domain survey; it supersedes the v1.0/v1.1-era architecture research previously in this file.

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  ROUTES (thin) — app/routes/*.py                                     │
│  ┌───────────┐  ┌────────────┐  ┌───────────┐  ┌──────────────┐     │
│  │ sales.py  │  │writeoffs.py│  │  ...       │  │  finance.py  │ NEW │
│  └─────┬─────┘  └─────┬──────┘  └─────┬──────┘  └──────┬───────┘     │
│        │              │               │                │             │
├────────┴──────────────┴───────────────┴────────────────┴─────────────┤
│  SERVICES (fat, all writes here) — app/services/*.py                 │
│  ┌───────────┐  ┌────────────┐         ┌──────────────────────┐     │
│  │ sales.py  │──┼──calls────▶│         │   finance.py    NEW  │     │
│  │register_  │  │            │         │ record_cash_movement │     │
│  │  sale()   │  │            │         │ register_manual_debit│     │
│  └─────┬─────┘  └────────────┘         │ compute_balance()     │     │
│        │ calls                          └──────────┬────────────┘    │
│        ▼                                            │                 │
│  ┌─────────────────────┐                            │                 │
│  │  ledger.py           │                           │                 │
│  │ record_operation()   │◀── single write path      │                 │
│  │  (stock/Operation)   │    for STOCK only          │                 │
│  └──────────┬────────────┘                           │                 │
├─────────────┴───────────────────────────────────────┴─────────────────┤
│  MODELS / TABLES — app/models.py                                      │
│  ┌───────────┐  ┌──────────┐  ┌─────────┐  ┌────────────────────┐    │
│  │ operations │  │  sales   │  │ products│  │ cash_movements NEW │    │
│  │(append-only│  │ (header) │  │ batches │  │  (append-only,     │    │
│  │ trigger-   │  │          │  │         │  │   trigger-guarded, │    │
│  │ guarded)   │  │          │  │         │  │   sale_id FK)      │    │
│  └────────────┘  └──────────┘  └─────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

**Core decision:** Cash movements are a **new, parallel append-only ledger table** (`cash_movements` / `CashMovement`), not new `type` values inside the existing `operations` table. See "Anti-Pattern 1" below for why reuse was rejected.

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|-----------------|--------|
| `CashMovement` model (`app/models.py`) | One append-only row per cash event: auto-credit from a sale, or manual debit with mandatory category/note. Mirrors `Operation`'s sync-ready shape (UUID PK, `device_id`+`seq`, `created_at`/`created_by`). | **New** |
| `app/services/finance.py` | Single write path for `cash_movements` (mirrors `ledger.record_operation`): `record_cash_movement()`, `register_manual_debit()` (validation + category allow-list, mirrors `writeoffs.register_writeoff`), `compute_balance()` (live SUM, mirrors `ledger.compute_stock`), `recent_cash_movements()` / a history view (mirrors `operations.history_view`). | **New** |
| `app/services/sales.py` (`register_sale`) | Unchanged responsibility (basket write), **plus one new call**: after the per-line `record_operation` loop and before the final `session.commit()`, call `finance.record_cash_movement(session, ..., commit=False)` with the already-computed `total_cents`. | **Modified** |
| `app/routes/finance.py` | Thin routes: `GET /finance` (balance + history), `GET/POST /finance/debit` (manual debit form), mirrors `app/routes/writeoffs.py` shape. | **New** |
| `app/templates/pages/finance.html`, `partials/finance_*.html` | Финансы dashboard (balance, history list) + debit form partial, following the existing `pages/` + `partials/` split. | **New** |
| `app/templates/base.html` | Add one `<nav>` link: `Финансы`. | **Modified** |
| `app/main.py` | `app.include_router(finance.router)`. | **Modified** |
| `alembic/versions/00XX_cash_movements.py` | New table + append-only triggers (`cash_movements_no_update`/`_no_delete`), mirroring migration 0001's `operations` triggers. | **New** |
| `app/routes/mobile_sales.py` etc. | **No change.** Mobile already calls `sales.register_sale()` unchanged (Phase 11 pattern) — the cash credit fires automatically for every mobile sale with zero mobile-side wiring. | **Untouched** |

## Recommended Project Structure

```
app/
├── models.py                    # + CashMovement class, + CASH_CATEGORIES dict
├── services/
│   ├── ledger.py                # UNCHANGED — stays product/stock-only
│   ├── sales.py                 # register_sale(): + one call into finance.py
│   ├── writeoffs.py             # UNCHANGED (pattern reference only)
│   └── finance.py               # NEW — record_cash_movement, register_manual_debit,
│                                 #        compute_balance, recent_cash_movements/history_view
├── routes/
│   └── finance.py               # NEW — GET /finance, GET/POST /finance/debit
├── templates/
│   ├── base.html                # + nav link
│   ├── pages/
│   │   └── finance.html         # NEW — balance + debit form + history table
│   └── partials/
│       └── finance_history.html # NEW — history rows (HTMX swap target after a debit)
alembic/versions/
└── 00XX_cash_movements.py       # NEW — table + append-only triggers
tests/
└── test_finance.py              # NEW — mirrors test_ledger.py / writeoff tests
```

### Structure Rationale

- **`app/services/finance.py` is a sibling of `ledger.py`, not a submodule of it.** `ledger.py`'s docstring is explicit: it is "the SINGLE write path for **stock changes**" and every function in it (`record_operation`, `compute_stock`, `rebuild_stock`) is keyed on `Product`/`Batch` quantity projections. Cash has no stock dimension, so it gets its own single-write-path function rather than a special case bolted onto `record_operation`.
- **`sales.py` calls `finance.py` directly (a plain Python function call in the same module-level transaction), not the other way around.** Sales is the only current cash-generating event; finance must never need to know how a sale was built.

## Architectural Patterns

### Pattern 1: Parallel append-only ledger table, sized to its own domain

**What:** `CashMovement` copies `Operation`'s proven sync-ready shape (UUID PK, `device_id` + `seq` with `UniqueConstraint(device_id, seq)`, `created_at`/`created_by` stamped from `settings`, DB-level `BEFORE UPDATE`/`BEFORE DELETE` triggers that `RAISE(ABORT, ...)`) but drops everything that is stock-specific (`product_id NOT NULL`, `batch_id`, `qty_delta`, the `STOCK_AFFECTING_TYPES` guard).

**When to use:** Any new "kind of event" that needs the same append-only/audit/future-sync guarantees as `operations` but has a genuinely different shape (no product, no quantity). This is the same reasoning that already produced two separate header/detail pairs in this codebase (`Sale` + `sale`-type `Operation` rows) rather than cramming sale headers into `operations`.

**Trade-offs:**
- Correct: no `product_id` schema compromise, no sentinel/dummy product, no special-casing in `record_operation`'s `STOCK_AFFECTING_TYPES`/batch-mandatory logic.
- Correct: `/history` (the existing operations view) stays exactly what it is today — a stock/product ledger — and Финансы gets its own history view. No risk of a cash row confusing a stock report that does `SUM(qty_delta)` or joins `Product`.
- Cost: two append-only tables to keep append-only (two migrations with triggers, two "single write path" functions) instead of one. Judged worth it: the alternative (nullable `product_id`) would weaken an invariant every existing stock service currently relies on (`session.get(Product, product_id)` + `product.deleted_at` guard runs unconditionally in `record_operation`).

**Example (model, mirrors `Operation`):**
```python
CASH_CATEGORIES = {
    "sale": "Продажа",              # system-generated only, never operator-chosen
    "supplier": "Оплата поставщику",
    "salary": "Зарплата",
    "other": "Прочее",
}

class CashMovement(Base):
    """Append-only cash ledger row: auto-credit from a sale, or manual debit.

    Mirrors Operation's sync-ready shape. amount_cents is SIGNED (positive =
    приход, negative = расход) — same convention as Operation.qty_delta.
    Immutability enforced by DB triggers (mirrors operations_no_update/_no_delete).
    """

    __tablename__ = "cash_movements"
    __table_args__ = (UniqueConstraint("device_id", "seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # CASH_CATEGORIES key
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # signed
    note: Mapped[str | None] = mapped_column(String(300))
    # Set at INSERT time only (mirrors Operation.sale_id); NULL for manual debits.
    sale_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales.id", name="fk_cash_movements_sale_id_sales"), index=True
    )
    device_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    synced_at: Mapped[str | None] = mapped_column(String(32))
```

### Pattern 2: Same-transaction hook — sales.py calls finance.py, not the route

**What:** `register_sale()` already builds the whole basket as one atomic transaction: every `record_operation(..., commit=False)` call is staged, and a single `session.commit()` at the end closes it (WR-03 in the existing docstring). The cash credit is added to the SAME transaction: one more `commit=False`-staged write, placed right after the line loop, right before that existing `session.commit()`.

**When to use:** Any time a new side effect must be guaranteed to happen if-and-only-if the triggering write succeeds (no cash credit for a rolled-back sale; no sale considered final if the credit fails). This is the correct level — the route (`app/routes/sales.py::sale_create`) must **not** be the one calling `finance.py`, or a future second entry point into `register_sale()` (there already are two: desktop `sale_create` and every mobile sale route) would silently skip the credit.

**Trade-offs:**
- Correct: atomicity for free — the existing `try/except (IntegrityError, ValueError): session.rollback()` around the write loop already wraps the new call.
- Correct: zero mobile-side changes — mobile already calls `register_sale()` unchanged (Phase 11 pattern), so mobile sales credit the till automatically.
- Cost: creates a same-package dependency `sales.py → finance.py` (an import). Acceptable: it is a plain intra-service call, same shape as `sales.py`'s existing dependency on `ledger.py` and `dictionary.py`.

**Example (the one-line integration point, inside `register_sale`'s existing try block):**
```python
    try:
        for line in resolved:
            ...
            record_operation(session, type_="sale", ..., commit=False)
            total_cents += qty * price_cents

        # NEW — same transaction, same total_cents already being accumulated above.
        finance.record_cash_movement(
            session,
            category="sale",
            amount_cents=total_cents,   # positive = credit
            sale_id=header.id,
            commit=False,
        )

        session.commit()   # unchanged — closes BOTH the sale and the cash credit
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"basket": SAVE_ROLLBACK}
```
A zero-total basket cannot reach this point (`register_sale` already rejects an empty basket and requires `price_cents` on every line), so `record_cash_movement` never needs to special-case `amount_cents == 0`; if it ever did, skip the insert (an audit-log row that credits nothing has no value) rather than writing a no-op row.

### Pattern 3: Live-summed balance, no cached field

**What:** `compute_balance()` is `SELECT COALESCE(SUM(amount_cents), 0) FROM cash_movements` — no cached balance column anywhere, not on a settings row, not on a singleton "account" row.

**When to use / why here specifically:** The existing codebase DOES cache a projection — `Product.quantity` and `Batch.quantity` are `SUM(qty_delta)` caches, kept in sync inside `record_operation`'s single write path, with a `rebuild_stock()` repair function for drift. That cache exists for a concrete reason stated in the code itself: stock quantity is read **inside the write-path oversell check**, once per batch, on every sale/writeoff/transfer/correction — a hot path that runs before every stock-affecting write. Cash balance has no equivalent hot path: nothing in this milestone's requirements gates a write on "is there enough cash" (unlike oversell, which gates on "is there enough stock"). Balance is a **read-only display value** on the Финансы page. A live `SUM()` is simpler, has zero drift risk by construction (nothing to keep in sync, nothing to repair), and the table it sums will always be far smaller than `operations` (cash rows are one-per-sale plus occasional manual debits, vs. one-or-more `operations` rows per sale line) — this is a strictly easier case than `compute_stock`, which already does the equivalent live `SUM()` on a bigger table and is called from live UI paths (`ledger_view`, `/history`).

**Trade-offs:**
- Correct: simplest correct answer for an append-only design — the balance is always, by definition, correct; there is nothing to reconcile.
- Correct: no new "single write path must also update the cache" discipline to enforce for a second table.
- Cost: if `cash_movements` ever grows to the point a live SUM is measurably slow (would take tens of thousands of rows for a single operator — not expected within this app's realistic lifetime), add an index on `created_at` (cheap) before reaching for a cached column; only add a cached `balance_cents` field later if profiling actually shows a problem, using the exact `Product.quantity` pattern (SQL-side atomic increment inside `record_cash_movement`, plus a `rebuild_balance()` repair function mirroring `rebuild_stock()`) — do not build that machinery speculatively now.

**Example:**
```python
def compute_balance(session: Session) -> int:
    """Live-recomputed cash balance (mirrors ledger.compute_stock)."""
    return session.scalar(
        select(func.coalesce(func.sum(CashMovement.amount_cents), 0))
    )
```

## Data Flow

### Key Data Flows

1. **Auto-credit on sale:** `POST /sales` → `routes/sales.py::sale_create` → `services/sales.py::register_sale()` → per-line `ledger.record_operation(commit=False)` loop → **`services/finance.py::record_cash_movement(category="sale", amount_cents=total_cents, sale_id=header.id, commit=False)`** → one `session.commit()` closes `Sale` + N `Operation` rows + 1 `CashMovement` row atomically. Mobile sales (`routes/mobile_sales.py`) hit the identical path — no separate wiring needed.
2. **Manual debit:** `GET /finance/debit` (form) → `POST /finance/debit` → `routes/finance.py` → `services/finance.py::register_manual_debit(category, note, amount)` — validates `category` against the `CASH_CATEGORIES` allow-list server-side (mirrors `writeoffs.register_writeoff`'s `reason_code not in WRITEOFF_REASONS` check) and requires a non-blank `note`/reason before any write (mirrors write-off's `REASON_ERROR` pattern) → `record_cash_movement(category=..., amount_cents=-amount, sale_id=None, commit=True)`.
3. **Финансы dashboard read:** `GET /finance` → `services/finance.py::compute_balance()` (live SUM) + a history view (mirrors `services/operations.py::history_view` — paginated, newest-first, reuse `app/services/pagination.py`'s `LIST_PAGE_SIZE` helper already shared by every other list page).

## Scaling Considerations

Not applicable in the usual sense — this is a single-operator, single-device, local SQLite app (per `CLAUDE.md` constraints: "Users: 1 operator in year one"). The only "scale" axis that matters here is table growth over years of daily use, and cash-movement rows are strictly fewer than `operations` rows (one credit per sale basket vs. one-or-more `operations` rows per basket), so anything acceptable for `operations`/`/history` today (proven at the dictionary's 6,856-row scale per Phase 14) is acceptable for `cash_movements`.

## Anti-Patterns

### Anti-Pattern 1: Reusing `operations` with `cash_in`/`cash_out` types

**What people do:** Add `"cash_in"`/`"cash_out"` to `OPERATION_TYPES` and write cash movements as `Operation` rows, reusing `record_operation`.

**Why it's wrong:** `Operation.product_id` is `nullable=False` with a hard FK to `products.id`, and `record_operation()` unconditionally does `session.get(Product, product_id)` + rejects soft-deleted products before any write. A cash movement has no product. The only ways to force it through are (a) make `product_id` nullable — weakens an invariant every other write path relies on and every existing report/join (`compute_stock`, `history_view`, `recent_sales`, `recent_writeoffs`) assumes holds — or (b) invent a sentinel "cash" `Product` row — which then shows up in product lists, stock reports, low-stock/stale-product reports, and CSV exports, none of which should ever mention cash. Either path also forces special-casing `STOCK_AFFECTING_TYPES`/mandatory-`batch_id` logic for a type that has no stock dimension at all.

**Do this instead:** A dedicated `CashMovement` table (Pattern 1 above) that copies the sync-ready shape without inheriting the stock-specific constraints.

### Anti-Pattern 2: Building a cached balance field before it's needed

**What people do:** Add a `settings.cash_balance_cents` field or a singleton `CashAccount.balance_cents` row and update it inside `record_cash_movement`, "because `Product.quantity` does it that way."

**Why it's wrong:** `Product.quantity` is cached because it is read inside a write-path validation loop (the oversell check) on every stock-affecting write — a hot path. No such hot path exists for cash balance in this milestone's requirements. A cache with no consumer that needs it is pure drift risk (a second thing that must stay in sync, a second thing `rebuild_stock`-style repair logic would eventually need) for zero benefit.

**Do this instead:** Live `SUM(amount_cents)` (Pattern 3). Revisit only if profiling later shows it's actually slow.

### Anti-Pattern 3: Calling `finance.py` from the sales *route* instead of the sales *service*

**What people do:** Leave `services/sales.py::register_sale()` untouched and instead call `finance.record_cash_movement()` from `routes/sales.py::sale_create()`, after `register_sale()` returns successfully.

**Why it's wrong:** There are already two callers of `register_sale()` in this codebase — desktop (`routes/sales.py`) and mobile (`routes/mobile_sales.py`) — and Phase 11 explicitly made mobile reuse the service "unchanged... no service-layer duplication" specifically so business rules have one source of truth. Putting the cash-credit call in the desktop route only credits desktop sales; mobile sales would silently never touch the till. It also breaks the atomicity guarantee (Pattern 2) — a credit issued after `register_sale()` already committed is a separate transaction that can succeed even if something downstream fails, or vice versa.

**Do this instead:** The call lives inside `services/sales.py::register_sale()`, in the same transaction as the ledger writes (Pattern 2), so every current and future caller of `register_sale()` gets the credit for free.

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `services/sales.py` → `services/finance.py` | Direct Python function call (`finance.record_cash_movement(session, ..., commit=False)`), same SQLAlchemy `Session`, same transaction | The only production integration point for auto-credit. Mirrors the existing `sales.py → ledger.py` and `sales.py → dictionary.py` intra-service call pattern already in the codebase — no new architectural shape introduced. |
| `services/writeoffs.py` (pattern reference) → `services/finance.py` (category/note validation shape) | Not a runtime call — a **pattern to mirror**, not a dependency | `register_manual_debit()`'s "required category from an allow-list dict + optional free-text note, both server-validated, both stored on the row" shape should copy `register_writeoff()`'s `reason_code`/`note` handling verbatim, including the RU error-message convention (`"Выберите ..."` for a missing category). |
| `routes/mobile_sales.py`, other mobile routes → `services/sales.py` | Unchanged — mobile already calls the same `register_sale()` | No new mobile-side finance wiring needed for the auto-credit in this milestone. `PROJECT.md`'s v1.3 target features list a desktop "Финансы" UI section only; mobile Финансы CRUD parity is already tracked separately under the v2.0 "Mobile CRUD parity" deferred item — do not build mobile Финансы screens in this milestone. |
| `app/routes/__init__.py` (shared `templates`) → `partials/finance_*.html` | Jinja2 filters/globals already registered (`cents`, `local_dt`, `ru_date`) are reusable as-is for money/date rendering on the new templates | Add `CASH_CATEGORIES` to `templates.env.globals` alongside the existing `WRITEOFF_REASONS`/`OPERATION_TYPE_LABELS` globals, for the debit-form `<select>` and the history category label. |

## Build Order

Dependency-ordered — each step only needs what came before it, matching this codebase's own phase-ordering convention (schema → service → route → template):

1. **Migration + model.** `alembic/versions/00XX_cash_movements.py`: create `cash_movements` table (mirror the `operations` table's column/index shape where relevant) + the two append-only triggers (mirror `operations_no_update`/`operations_no_delete` from migration 0001, renamed `cash_movements_no_update`/`cash_movements_no_delete`). Add the `CashMovement` model + `CASH_CATEGORIES` dict to `app/models.py`. Nothing downstream can be written or tested without this.
2. **`app/services/finance.py`.** `record_cash_movement()` (single write path, mirrors `ledger.record_operation`'s `commit` param and `device_id`/`seq` stamping via a `next_seq`-equivalent), `compute_balance()`, `register_manual_debit()` (validation, mirrors `writeoffs.register_writeoff`), a history/read view (mirrors `services/operations.py::history_view`, reusing `services/pagination.py`). Unit-testable in isolation before anything calls it.
3. **Wire `services/sales.py`.** Add the `finance` import and the one `record_cash_movement(..., commit=False)` call inside `register_sale()`'s existing try block (Pattern 2). This is the only change to an existing file's write path. Verify with a test that a rolled-back sale (bad line, oversell-blocked, `IntegrityError`) produces **zero** `cash_movements` rows, and a committed sale produces exactly one, with `amount_cents == total_cents` and `sale_id == header.id`.
4. **`app/routes/finance.py`.** Thin routes only, mirroring `routes/writeoffs.py`'s shape: `GET /finance` (dashboard), `GET /finance/debit` + `POST /finance/debit` (manual debit form + submit, HTMX partial re-render on validation error, same as every other form in this codebase).
5. **Templates.** `pages/finance.html` (balance display + debit form + history table) and `partials/finance_history.html` (the HTMX swap target after a successful/failed debit submit). Add `CASH_CATEGORIES` to `templates.env.globals` (`app/routes/__init__.py`).
6. **Register.** `app.include_router(finance.router)` in `app/main.py`; add the `Финансы` link to `app/templates/base.html`'s `<nav>` (desktop only — see Integration Points on mobile scope).
7. **Tests.** `tests/test_finance.py` for the service layer (mirrors `tests/test_ledger.py`'s shape: append-only trigger enforcement, `compute_balance` correctness, category validation), plus an assertion inside the existing sales test suite that a successful sale credits the till by exactly the sale total.

## Sources

- Direct inspection, this repository (`E:\dev\myorishop`): `app/models.py`, `app/services/ledger.py`, `app/services/sales.py`, `app/services/writeoffs.py`, `app/services/operations.py`, `app/routes/sales.py`, `app/routes/__init__.py`, `app/main.py`, `app/config.py`, `app/core.py`, `app/db.py`, `alembic/versions/0001_initial_schema.py`, `app/templates/base.html`, `.planning/PROJECT.md` (v1.3 milestone scope). No external sources — this is a project-specific integration design derived from the codebase's own established conventions, not a generic ecosystem survey.

---
*Architecture research for: Касса / Финансы module (v1.3 milestone), MyOriShop*
*Researched: 2026-07-14*
