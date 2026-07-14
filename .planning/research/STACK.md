# Stack Research

**Domain:** Cash-balance / money-movement ledger ("Касса" / "Финансы" module) — v1.3 milestone
**Researched:** 2026-07-14
**Confidence:** HIGH

> Scope note: this file is scoped to the v1.3 milestone (auto-credit on sale, debit with
> mandatory reason/category, movement history, current balance, a dedicated "Финансы" UI
> section). The full base stack rationale (FastAPI/SQLAlchemy/SQLite/HTMX/Jinja2/uv/Alembic,
> versions, "what not to use") is preserved verbatim in the project's `CLAUDE.md` "Technology
> Stack" section and is not repeated here — it is unchanged and not re-researched per milestone
> instructions. This file supersedes the v1.1-scoped `STACK.md` that previously occupied this
> path (that content is preserved in git history / `.planning/research/.cache/`).

## Bottom Line

**No new runtime dependency is needed.** A cash-balance ledger is a smaller, simpler version of
a pattern this codebase already runs in production: the append-only `operations` table plus
`record_operation()`'s "SQL-side atomic increment in the same transaction, recompute-from-ledger
as the repair path" design (`app/services/ledger.py`, `app/services/stock.py`). The existing
FastAPI / SQLAlchemy 2.0 / SQLite (WAL) / Alembic / Jinja2 / HTMX stack fully covers it. Money
stays integer minor units (cents) — no `Decimal`/`Numeric` column, no money or accounting
library, no new locking or scheduling library, no charting library (not in this milestone's
target features).

## Recommended Stack (unchanged — reused, not added)

### Core Technologies

| Technology | Version (pinned, unchanged) | Purpose for v1.3 | Why no change needed |
|------------|------|---------|-----------------|
| SQLAlchemy | 2.0.* (2.0.51 validated) | New `cash_movements` table + service functions | Same 2.0 declarative style (`Mapped[]`/`mapped_column()`) already used for `Operation`, `Batch`, etc. — a new mapped class, nothing exotic |
| Alembic | 1.18.* (1.18.5 validated) | Migration adding `cash_movements` (+ append-only triggers) | Already the sole schema-change tool; `render_as_batch=True` already configured for SQLite |
| SQLite + WAL + `busy_timeout` (`app/db.py`, unchanged) | bundled, already configured: `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, per-connection | Durable storage + concurrency safety for a value read often (dashboard) and written on every sale | This is already the correct configuration for "many readers, one occasional writer" — see Concurrency section below. No new PRAGMA needed. |
| FastAPI + Jinja2 3.1.6 + HTMX 2.0.10 (vendored) | 0.139.*/3.1.6/2.0.10 | New "Финансы" section: balance display, debit-entry form (reason/category), movement history list | Same server-rendered + `hx-get`/`hx-post` partial-swap pattern used by every other module (sales, receipts, history) — a balance number, a form, and a list need no new frontend primitive |

### Supporting Libraries

**None required.** Specifically considered and rejected:

| Considered | Verdict | Reason |
|------------|---------|--------|
| `py-moneyed` / `python-money` or any currency-aware `Money` value-object library | Not needed | Project is explicitly single-currency (CLAUDE.md constraint); the whole app already stores money as `Integer` cents columns with plain Python arithmetic. A money library would introduce a second, inconsistent money representation next to every existing `*_cents` column. |
| `Decimal`/`Numeric` columns (stdlib `decimal` is free, but not needed) | Not needed | Integer cents + integer arithmetic (`+`, `-`, `SUM()`) is exact for this use case — amounts are always already whole cents, no rounding step ever occurs. Switching representations for one new table would break the established `Integer`-cents convention used everywhere else. |
| `sqlalchemy-continuum` / `sqlalchemy-history` or any generic audit-trail library | Not needed | The app already hand-rolls immutable history via `CREATE TRIGGER ... BEFORE UPDATE/DELETE ... RAISE(ABORT, ...)` (`alembic/versions/0001_initial_schema.py`) plus a single-write-path service function (`record_operation`). A generic library would duplicate and could conflict with this already-battle-tested mechanism. |
| `filelock` / `portalocker` or any app-level locking library | Not needed | SQLite's WAL mode already serializes writers itself (one writer at a time; readers never block/are never blocked). Single Uvicorn process, single local operator — no multi-process writer scenario exists to guard against. The existing `busy_timeout=5000` already handles the rare same-instant double-write case (see Concurrency section). |
| Chart.js / ApexCharts or any client-side charting library | Not needed this milestone | Target features are balance + reason-coded movement history, not trend charts. Adding one would also add an offline-vendoring burden (same CDN-ban reasoning as HTMX) for something not requested. Revisit only if a future milestone explicitly asks for charts. |
| Celery / APScheduler or any background-job library | Not needed | Balance is computed synchronously (`SUM` on read) or updated synchronously in the same DB transaction as the ledger insert (mirrors `Product.quantity`). No async/scheduled work is involved. |

### Development Tools

No changes. Same `uv` / `ruff` / `pytest` workflow as every prior milestone.

## Installation

```bash
# No new packages. Existing environment is sufficient:
uv sync
```

No `uv add` is required for this milestone.

## Schema & Integration Design (the actual work, not a library choice)

This is what "no new dependency" cashes out to concretely, so the roadmap can plan phases
against it.

### 1. Don't reuse the `operations` table — add a sibling `cash_movements` table

`Operation.product_id` is `nullable=False` with a hard FK to `products`, and
`STOCK_AFFECTING_TYPES` logic in `app/services/ledger.py` requires a mandatory `batch_id` for
every stock-affecting row. A cash movement for "оплата заказа поставщику" or "зарплата" has no
product and no batch — forcing it through `operations` would mean relaxing NOT-NULL/FK
invariants that `record_operation`, the batch-ownership guard, and `STOCK_AFFECTING_TYPES` all
currently depend on. A dedicated `cash_movements` table keeps both ledgers' invariants
independently reasoned-about — the same tradeoff the codebase already made keeping `Sale`
headers separate from `Operation` lines.

Mirror the existing `Operation` shape:
- `id` (UUID `String(36)` PK, matching every other table)
- `type` discriminator (e.g. `sale_credit`, `expense_supplier`, `expense_salary`,
  `expense_other`, `correction`)
- `amount_cents` (signed `Integer` — credit positive, debit negative; same signed-delta
  convention as `Operation.qty_delta`)
- `reason` (text — the mandatory justification for debits: "pay supplier order" / "salary" /
  "other" + comment; nullable only for `sale_credit` rows, which are self-explanatory via
  `sale_id`)
- `sale_id` (nullable FK -> `sales.id` — links an auto-credit row back to its `Sale`, same
  nullable-link precedent as `Operation.sale_id`)
- `device_id` + per-device `seq` (future-sync provenance, same precedent as `Operation`)
- `created_at` / `created_by` (same audit convention as `Operation`)

Reuse the exact append-only trigger pattern from `alembic/versions/0001_initial_schema.py`
(`CREATE TRIGGER cash_movements_no_update` / `cash_movements_no_delete`, `BEFORE
UPDATE`/`DELETE ... RAISE(ABORT, ...)`), created via **native** DDL in the new migration (not
`batch_alter_table`, which is irrelevant here since this is a brand-new table, not an
`ALTER` on an existing triggered table).

### 2. Auto-credit on sale: same transaction as the sale's `Operation` rows

`register_sale` (`app/services/sales.py`) already writes N `Operation` rows in one DB
transaction via `record_operation(..., commit=False)` and a single trailing `session.commit()`
(the WR-03 pattern documented in `ledger.py`). Add the cash-credit insert as one more
`commit=False` call inside that same transaction (a new `record_cash_movement()` function in a
new `app/services/cash.py`), so a crash mid-sale can never leave stock debited but cash
uncredited, or vice versa — the same all-or-nothing guarantee the ledger already gives stock,
batches, and sales.

### 3. Balance: compute from the ledger; never trust a bare mutable counter without a recompute path

Follow the exact precedent of `compute_stock()`/`rebuild_stock()` in `app/services/stock.py` —
the ledger (`SUM(cash_movements.amount_cents)`) is the ground truth, not a cache. Two valid
implementations; pick based on read frequency once the dashboard exists:

- **Recommended to start:** compute the balance with
  `select(func.coalesce(func.sum(CashMovement.amount_cents), 0))` on every dashboard read. At
  single-operator local-app volume (low thousands of rows/year) this is sub-millisecond — no
  caching needed, and there is zero drift risk because there is no cache to drift.
- **If a cached counter is ever wanted later** (e.g. a `balance_cents` column on a new one-row
  `cash_account` table, updated via the same SQL-side atomic
  `UPDATE ... SET balance_cents = balance_cents + ?` technique `record_operation` already uses
  for `Product.quantity` — the project's documented `IN-02` "no stale-ORM-value window"
  pattern): pair it with a `compute_cash_balance()` recompute function as the audit/repair path,
  exactly mirroring `rebuild_stock()`. Never add a cached counter without its recompute-and-assert
  counterpart — that pairing, not the cache itself, is what keeps the number trustworthy.

### 4. "Финансы" UI section

Pure read/write-side, no new pattern: a balance display (server-rendered from the compute
function above), a debit-entry form (`hx-post`, category `<select>` + mandatory reason/comment
field, following the same warn-or-reject validation shape already used by
`app/services/sales.py`'s oversell/min-price checks), and a movement-history list — same
pagination/filter/sort helper already shared across every other list page
(`app/services/pagination.py`, delivered in Phase 14). No new frontend primitive is required.

## Concurrency: does SQLite need anything new for a value read often and written on every sale?

**No.** The existing `app/db.py` configuration is already the correct setup and already covers
this feature:

- SQLite WAL mode allows unlimited concurrent **readers** and exactly **one writer** at a time;
  readers never block the writer and the writer never blocks readers (readers see the
  last-committed snapshot). A "Финансы" dashboard polling/refreshing the balance will never be
  blocked by, or block, a sale being recorded.
- Writes are still fully serialized (WAL does not give true multi-writer concurrency) — but this
  app runs one local Uvicorn process for one operator, so there is no realistic multi-writer
  contention to design around.
- `PRAGMA busy_timeout=5000` (already set, per-connection) is exactly the community-recommended
  mitigation (5-10s) for the one edge case that matters — two write transactions landing at the
  same instant — letting the second writer wait briefly instead of immediately failing with
  `SQLITE_BUSY`/"database is locked".
- The one real discipline to carry over (already practiced in `record_operation`): keep the
  ledger-insert + balance-update in a **single short transaction**, and avoid "read-then-write"
  transaction upgrades — SQLite's deferred-BEGIN-then-upgrade-to-write is the actual common cause
  of `SQLITE_BUSY` under contention per current SQLite concurrency guidance.
  `record_operation`'s `commit=False`/single-trailing-`commit()` shape already does this
  correctly, and `record_cash_movement()` should follow the identical shape.

No new PRAGMA, no application-level lock, and no queueing library is warranted for a
single-operator local app.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| Plain `Integer` cents, no money library | `Decimal`/`Numeric` columns via a dedicated money library | If the project ever needs true multi-currency with exchange-rate math (planned for out-of-scope v2.0) — even then, prefer stdlib `decimal.Decimal` for conversion math over a third-party money library, keeping storage as integer minor units per currency. |
| Balance computed from `SUM(cash_movements.amount_cents)` on read | Cached `balance_cents` counter, atomically incremented (mirrors `Product.quantity`) | Once/if the "Финансы" dashboard is hit frequently enough that a `SUM()` over a large table becomes measurably slow — unlikely at this app's scale; the upgrade path already exists in this codebase (`Product.quantity` + `compute_stock`/`rebuild_stock`) if needed later. |
| New sibling `cash_movements` table | Extend `operations` table with new `type` values | Only if `Operation.product_id`/`batch_id` were made nullable app-wide — not recommended, since `STOCK_AFFECTING_TYPES` and the batch-ownership guard in `record_operation` assume every row is product-scoped. Would require touching and re-verifying every existing caller for no real benefit. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| `FLOAT`/`REAL` for `cash_movements.amount_cents` | SQLite has no true DECIMAL; floats corrupt money math (already a documented project-wide "What NOT to Use") | `Integer` minor units, exactly like every existing `*_cents` column |
| A generic Python accounting/double-entry-bookkeeping library | Overkill for "one balance, credits from sales, debits with a reason code" — adds a foreign data model and learning surface for a beginner project that doesn't need double-entry accounting | The existing single-table append-only ledger pattern (`Operation`-style), applied to `cash_movements` |
| A caching/memoization library for the balance number | Not a caching problem — the ledger table is small and `SUM()` is cheap at this scale; caching before there's a measured performance issue adds an invalidation-correctness risk, the exact class of bug `compute_stock`/`rebuild_stock` exists to guard against | Compute-on-read (`SUM`) first; add the atomic-increment + recompute pair later only if actually needed |
| Reusing `operations.product_id` as nullable to shoehorn cash rows in | Breaks invariants several existing guards depend on (see Schema & Integration Design §1) | A dedicated `cash_movements` table |
| `filelock`/`portalocker` or any app-level write lock | SQLite's own WAL single-writer model + `busy_timeout=5000` already handle this; adding a second locking layer is redundant and can itself introduce deadlock risk | Rely on the existing `app/db.py` PRAGMAs, keep transactions short |

## Stack Patterns by Variant

**If the "Финансы" dashboard later needs trend charts or export:**
- Reuse the existing CSV export pattern (`app/services/export.py`) for a `cash_movements` CSV —
  same BOM + `;` delimiter + formula-injection-escape convention already used for
  products/sales/customers exports. No new export library.
- Only add a charting library at that point, and vendor it locally (same offline-first rule as
  HTMX) rather than pulling from a CDN.

**If v2.0 multi-currency lands later:**
- Add a `currency` column to `cash_movements` (and every other money table) rather than
  switching representation; keep amounts as integer minor units per currency. This is a schema
  change, not a stack change — no money library is required even then.

**If v2.0 multi-operator sync lands later:**
- `cash_movements.device_id`/`seq` (already planned into the schema above) carry across devices
  exactly like every other UUID-keyed, device-scoped table in this codebase — no rework needed
  specifically for cash.

## Version Compatibility

No new packages, so no new compatibility matrix entries. This feature is fully covered by the
existing pins already recorded in `CLAUDE.md`:

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| sqlalchemy 2.0.51 | alembic 1.18.5 | Unchanged; a new `cash_movements` table + its two append-only triggers use the same patterns already exercised by `operations` in `0001` |
| fastapi 0.139.* / jinja2 3.1.6 / htmx 2.0.10 (vendored) | new "Финансы" routes/templates | No htmx feature beyond `hx-post`/`hx-get`/`hx-target`/`hx-swap`, already exercised throughout the app, is required |

## Sources

- Direct inspection of the existing codebase (`app/db.py`, `app/models.py`,
  `app/services/ledger.py`, `app/services/stock.py`, `app/services/sales.py`,
  `alembic/versions/0001_initial_schema.py`) — HIGH confidence, ground truth for what already
  exists and what conventions/invariants a new module must match.
- `E:\dev\myorishop\CLAUDE.md` — prior validated stack research (versions, integer-cents rule,
  WAL/busy_timeout/foreign_keys rationale, "no async needed for single-user SQLite" rationale).
  HIGH confidence (already-verified project research, dated 2026-07-08).
- `.planning/PROJECT.md` — v1.3 milestone scope and target features (auto-credit on sale, debit
  with mandatory reason/category, movement history, balance, "Финансы" UI section). HIGH
  confidence (first-party project doc).
- [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) —
  confirms WAL = one writer at a time, readers never block the writer, `busy_timeout` (5-10s
  recommended) as the standard mitigation, and "read-then-write transaction upgrade" as the
  common real cause of `SQLITE_BUSY`. MEDIUM confidence (community technical blog, cross-checked
  against SQLite's own documented WAL semantics).
- [What to do about SQLITE_BUSY errors despite setting a timeout](https://berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout/) —
  corroborates `busy_timeout` as a per-connection setting and the single-writer WAL model. MEDIUM
  confidence.
- [Precision Matters: Why Using Cents Instead of Floating Point for Transaction Amounts is Crucial](https://www.hackerone.com/blog/precision-matters-why-using-cents-instead-floating-point-transaction-amounts-crucial)
  and [Still Using Python float for Money? Here's Why That's Dangerous](https://medium.com/the-pythonworld/still-using-python-float-for-money-heres-why-that-s-dangerous-c761b994c526) —
  corroborate integer-minor-units as standard practitioner choice for transactional money
  storage, consistent with the project's already-established rule. MEDIUM confidence.
- No external package research beyond the concurrency/money-handling sanity checks above was
  needed: the conclusion — zero new runtime dependencies — makes version verification of a *new*
  package moot. The already-pinned technologies named in this doc are carried over unchanged
  from `CLAUDE.md` and were not re-verified per milestone instructions ("DO NOT re-research the
  existing stack").

---
*Stack research for: MyOriShop v1.3 — Финансы / Касса*
*Researched: 2026-07-14*
