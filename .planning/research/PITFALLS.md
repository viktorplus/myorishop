# Pitfalls Research

**Domain:** Local-first inventory & sales tracking app (FastAPI + HTMX + SQLite, solo beginner developer)
**Researched:** 2026-07-08
**Confidence:** MEDIUM-HIGH (SQLite behavior from official docs = HIGH; design pitfalls cross-verified across multiple community/vendor sources = MEDIUM)

## Critical Pitfalls

### Pitfall 1: Stock count drift — mutable quantity column as the source of truth

**What goes wrong:**
`product.quantity` is updated in place on every sale/receipt (`quantity = quantity - 2`). Over months, the number diverges from reality: a crashed request, a double-submitted form, a bug in one code path (e.g., returns update quantity but forget history), and there is no way to know what the number *should* be. The core value of this app ("stock counts always correct") is lost silently.

**Why it happens:**
Storing a plain quantity column is the intuitive first design. The drift is a classic denormalization update anomaly: the derived value and the underlying transactions go out of sync, and nothing detects it.

**How to avoid:**
Make an append-only `stock_movements` ledger the source of truth. Every operation — receipt, sale, write-off, return, correction — inserts a signed movement row (+qty / -qty) inside the same transaction as the business record. Current stock = `SUM(movements)` per product. A cached `quantity` column is fine as an optimization *only if* there is a "recompute from ledger" command that can rebuild and verify it. Physical inventory count = a correction movement, not an overwrite.

**Warning signs:**
- Any `UPDATE products SET quantity = ...` outside a single well-tested function
- An operation type (return, write-off) that touches quantity without writing a history row
- No reconciliation check ("does SUM(movements) equal the displayed stock?")

**Phase to address:**
Foundation/schema phase (ledger table exists before any operation is built); every subsequent operation phase must write to it.

---

### Pitfall 2: Floating-point money math

**What goes wrong:**
Prices and costs stored as `float`/`REAL` accumulate binary rounding errors (0.1 + 0.2 = 0.30000000000000004). Profit reports drift by cents, totals don't match line items, and the errors compound silently — floats never raise an error, they just look wrong on the report.

**Why it happens:**
Two traps stack for this stack specifically: (1) beginners reach for `float` by default; (2) **SQLite has no real DECIMAL type** — a column declared `NUMERIC(10,2)` stores REAL under type affinity, and SQLAlchemy's `Numeric` on SQLite explicitly warns that Decimal is not supported natively and round-trips through float.

**How to avoid:**
Store all money as **integer minor units (cents/kopecks)** in `Integer` columns. Convert to `decimal.Decimal` at the edges (parsing form input, rendering, report math). Never `float()` a money value anywhere. One helper module (`money.py`) with `to_cents()` / `format_money()` keeps this consistent.

**Warning signs:**
- `Float` or `Numeric` column types in SQLAlchemy models for price/cost fields
- SQLAlchemy warning "does not support Decimal objects natively" in logs
- Report total differs from the sum of visible rows by a cent

**Phase to address:**
Foundation/schema phase — this is a day-one column-type decision; migrating money columns later touches every table and every calculation.

---

### Pitfall 3: Destructive edits — no true audit trail

**What goes wrong:**
Sales, receipts, and product prices are edited or deleted in place. History requirements ("price change history preserved", "who did what and when") become impossible to satisfy: yesterday's report changes retroactively, a mistyped sale is deleted and the stock ledger no longer explains the current count, and there is no record that anything happened.

**Why it happens:**
CRUD-style "Edit" and "Delete" buttons are the path of least resistance, and with one operator it feels harmless. The cost only appears months later when a report disagrees with memory.

**How to avoid:**
Operations are **append-only**. Fixing a mistake = a compensating operation (cancel/storno that reverses the movement, then a new correct entry), both logged. Product *card* fields (name, category) may be edited, but price changes append to a `price_history` table, and each sale/receipt snapshots the prices it used (see Pitfall 9). Every operation row carries `created_at` (UTC) and operation type.

**Warning signs:**
- `DELETE FROM sales` or an "edit sale" form that mutates the original row
- Price history table planned "for later" while receipts already change `product.cost`
- Report for a past period changes after unrelated edits

**Phase to address:**
Operations phase (sales/write-off/return/correction) — the cancel-by-compensation flow must be designed with the operations themselves, not bolted on.

---

### Pitfall 4: Schema choices that block future sync

**What goes wrong:**
Auto-increment integer primary keys are exposed as the identity of products, sales, and operations. When multi-operator sync arrives (explicit future goal), two offline devices both create "sale #482" and IDs collide; merging requires renumbering every foreign key — effectively a rewrite.

**Why it happens:**
Auto-increment is SQLAlchemy's default and works perfectly for a single local DB, so nothing hurts until sync starts. Sequential IDs need a single authority to hand out numbers, which doesn't exist offline.

**How to avoid:**
Don't build sync — just don't block it:
- Business entities and operations get a globally unique ID: UUIDv4 stored as TEXT (or UUIDv7/ULID for index locality). Keeping an internal integer rowid alongside is fine; the UUID is what would sync.
- Every operation row: UTC timestamp + operation type + payload — this *is* the event log the project already planned.
- No cross-table logic that depends on ID ordering.

**Warning signs:**
- Foreign keys and URLs referencing `sale.id = 17`-style integers with no UUID column anywhere
- Operation log missing timestamps or stored as free text
- Any design discussion resolving to "we'll renumber when we sync"

**Phase to address:**
Foundation/schema phase. Cost is near zero on day one, very high after data exists.

---

### Pitfall 5: No backups, or backups made by copying the live DB file

**What goes wrong:**
Total data loss — the single failure mode this project cannot tolerate. Two variants: (a) no backup at all and the laptop dies; (b) a "backup" made by copying `app.db` while the app runs in WAL mode, which silently omits recent transactions living in `app.db-wal` (and a stale `-wal` next to a restored file can corrupt the database).

**Why it happens:**
SQLite's single-file simplicity makes `copy app.db backup/` look obviously correct. The WAL sidecar files are invisible until they matter.

**How to avoid:**
Use SQLite's supported hot-backup mechanisms: `VACUUM INTO 'backup-YYYY-MM-DD.db'` (one SQL statement, ideal here) or Python's `sqlite3.Connection.backup()`. Automate it: backup on app start or daily, keep N rotated copies, ideally to a second disk/USB/cloud folder. **Test a restore once** before trusting it. On restore, ensure no stale `-wal`/`-shm` files sit next to the restored file.

**Warning signs:**
- Backup script uses `shutil.copy` / file copy on a running app
- `-wal` file present and larger than 0 bytes at "backup" time
- Nobody has ever opened a backup file to check it's valid

**Phase to address:**
Must ship in the first usable release (foundation or first "daily use" phase) — real data entry starts immediately since there's no import.

---

### Pitfall 6: SQLite concurrency misuse — "database is locked" and lost updates

**What goes wrong:**
Two flavors:
1. `sqlite3.OperationalError: database is locked` under FastAPI when two requests write concurrently (HTMX fires requests eagerly; default busy timeout is **zero**, so contention fails instantly).
2. Read-modify-write race: code reads stock, checks it, then writes the decrement in separate steps; a double-click submits two sales and both pass the check — a lost update and wrong stock.

**Why it happens:**
SQLite allows many readers but exactly one writer. Defaults are unforgiving: rollback journal mode, no busy timeout. Beginners also hold transactions open across slow work.

**How to avoid:**
- On every connection (SQLAlchemy `connect` event): `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, and `PRAGMA foreign_keys=ON` (FK enforcement is **off by default** in SQLite).
- Run uvicorn with a single worker process (multiple workers = multiple writer processes fighting).
- Keep write transactions short: begin → insert operation + movement → commit. No I/O inside.
- Make the stock check-and-decrement atomic in one transaction; add a double-submit guard in the UI (disable button / `hx-disable`).

**Warning signs:**
- "database is locked" in logs, even rarely
- Duplicate sale rows seconds apart with identical contents
- FK violations silently not enforced (orphan rows appear)

**Phase to address:**
Foundation phase (engine setup + PRAGMAs is ~10 lines); atomic decrement in the sales phase.

---

### Pitfall 7: Timezone and date-boundary bugs in reports

**What goes wrong:**
"Today's sales" report misses evening sales or shows tomorrow's: timestamps stored in UTC are grouped by UTC calendar date, but the operator's business day ends at local midnight. Worse in this codebase's stack: mixing naive and aware Python datetimes, and SQLite storing datetimes as strings whose format silently determines comparison behavior.

**Why it happens:**
"Store UTC" is correct advice for *storage*, but reports need grouping by *local* day, and the conversion step is easy to skip when developer timezone == server timezone == user timezone (it works until it doesn't — DST shift or future multi-country sync).

**How to avoid:**
- Store all timestamps as **UTC, timezone-aware**, in one consistent format (ISO 8601 or epoch seconds).
- One app setting: operator timezone (e.g., `Europe/...`). All report period boundaries computed as local-day start/end → converted to UTC for the query `WHERE ts >= :start AND ts < :end` (half-open interval, never `BETWEEN` on dates).
- Test a report with a sale inserted at 23:30 local time.

**Warning signs:**
- `datetime.now()` (naive) anywhere instead of `datetime.now(timezone.utc)`
- SQL grouping by `date(timestamp)` directly on stored UTC values
- A sale visibly "moves" between two daily reports

**Phase to address:**
Storage convention in foundation phase; boundary conversion logic in the reports phase.

---

### Pitfall 8: Over-engineering sync (or its scaffolding) too early

**What goes wrong:**
The solo beginner developer spends weeks on CRDT libraries, sync protocols, conflict-resolution frameworks, or a client/server split — before a single sale has been recorded. The MVP never ships. Community experience is consistent: CRDTs and sync engines carry production-grade complexity comparable to hand-built conflict resolution, and are unjustifiable for a single-operator app.

**Why it happens:**
Sync is in the long-term vision (agent.md section 8), so it feels responsible to "build for it now". Local-first content online skews toward sophisticated multi-device tooling.

**How to avoid:**
The full sync budget for v1 is the passive schema hygiene from Pitfall 4 (UUIDs, UTC timestamps, append-only operation log). Zero sync code, zero CRDT libraries, zero server components. Revisit at the sync milestone with real usage data.

**Warning signs:**
- Any dependency with "sync", "replication", or "CRDT" in the name in requirements.txt for v1
- Designing conflict resolution for conflicts that cannot yet occur (one operator!)
- Foundation phase lasting more than a couple of weeks

**Phase to address:**
Roadmap-level decision: explicitly scope sync out of every v1 phase; keep only the schema hygiene items.

---

### Pitfall 9: Profit computed from *current* prices instead of snapshotted ones

**What goes wrong:**
Profit report joins sales to `products` and uses `product.cost_price` — the *current* cost. When the next receipt arrives at a new cost (routine for Oriflame catalog cycles), all historical profit silently changes. Same for sale price: the requirement allows a custom price per sale, so the product's list price is not what was charged.

**Why it happens:**
Normalization instinct: "don't duplicate the price, it's already on the product." But price-at-time-of-sale is a historical fact, not a redundant copy — this is the accounting matching principle (COGS must reflect cost at the time revenue occurred).

**How to avoid:**
Each sale line stores its own `unit_price_cents` and `unit_cost_cents` copied at the moment of sale; each receipt stores its own cost and prices. Profit = SUM over sale lines only — no join to current product prices. Weighted-average cost is sufficient for v1 (FIFO batch costing is already deferred in PROJECT.md).

**Warning signs:**
- Sales table has `product_id` and `quantity` but no price/cost columns
- Profit report SQL joins `products` for any money field
- Historical report changes after entering a new receipt

**Phase to address:**
Sales phase (schema of the sale line) and receipts phase; verify in the reports phase that no report reads current product prices for historical rows.

---

### Pitfall 10: Oversell handling — silent negative stock or hard blocking

**What goes wrong:**
Either extreme breaks the workflow. Silent: selling 5 when 3 are on hand drives stock negative with no signal, and drift begins. Hard block: the operator *did* physically sell the item (count was wrong in the app), the app refuses, so she records it "later" — and never does. Lost sale record, lost customer history.

**Why it happens:**
Developers model the database, not the counter: in reality the physical shelf is the truth and the app is the map.

**How to avoid:**
Warn-and-allow (matches the stated requirement): show a prominent warning "only 3 in stock", require confirmation, record the sale, let stock go negative, and surface negative-stock products on the dashboard/low-stock report as "needs correction". Correction is then an explicit logged operation.

**Warning signs:**
- Validation that returns HTTP 400 on insufficient stock with no override path
- Negative quantities that appear nowhere in any report
- Operator keeps a paper notebook "for the ones the app rejected"

**Phase to address:**
Sales phase (confirm-flow UX) + reports phase (negative/low-stock visibility).

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `Float`/`Numeric` columns for money | Zero conversion code | Every report subtly wrong; full-column migration + recompute later | Never |
| Mutable `product.quantity` with no movement ledger | Simplest possible schema | Undetectable drift; no audit; blocks sync | Never (ledger is cheap on day one) |
| `Base.metadata.create_all()` instead of Alembic migrations | No migration tooling to learn | First schema change on a live DB with real data = manual surgery or data loss | OK for the very first phase; add Alembic before real daily data entry |
| Editable/deletable operation rows | Easy mistake fixing | Audit trail and historical reports become fiction | Never for operations; fine for product card text fields |
| Skipping backup automation ("I'll copy the file sometimes") | Saves an afternoon | Total data loss of hand-entered data (no import exists to recover from) | Never past the first usable release |
| Business logic inline in FastAPI route handlers | Fast to write | Stock math duplicated across sale/return/write-off routes drifts apart | OK in phase 1–2; extract a service layer when the second operation type appears |
| No tests at all | Ship faster | Stock/profit math regressions found by the operator, not the developer | Acceptable to skip UI tests; never skip tests for money math and stock movement functions |

## Integration Gotchas

Common mistakes when connecting stack components (this is a local app — "integrations" are stack seams).

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| SQLAlchemy + SQLite | Assuming `Numeric` gives exact decimals | Integer cents columns; `Decimal` in Python only |
| SQLAlchemy + SQLite | Forgetting PRAGMAs are **per-connection** | Set WAL, `busy_timeout`, `foreign_keys=ON` in a `connect` event listener, not once at startup |
| SQLite | Believing FKs are enforced by declaring them | `PRAGMA foreign_keys=ON` on every connection — off by default |
| FastAPI + uvicorn | Running `--workers 4` "for performance" | Single worker; SQLite has one writer and one user anyway |
| HTMX forms | Double-click submits two sales | Disable submit button during request (`hx-disable-elt` / `hx-indicator`); atomic server-side transaction |
| HTMX + server rendering | Returning full pages to fragment requests (or vice versa) — UI silently nests | Decide per-endpoint: fragment vs full page; check `HX-Request` header for shared routes |
| Alembic + SQLite | Using `ALTER COLUMN`-style migrations SQLite can't execute | Enable Alembic batch mode (`render_as_batch=True`) from the start |

## Performance Traps

Patterns that work at small scale but fail as usage grows. **Reality check: one operator, thousands of operations/year — SQLite handles this scale trivially. Do not over-optimize.**

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Recomputing `SUM(movements)` per product on the catalog list page, per row | Catalog page slows as history grows | One grouped query (or cached quantity column reconciled against ledger) | ~10k+ movements with per-row queries; a single grouped SUM stays fast for years |
| N+1 queries in reports (loop over sales, query product each time) | Monthly report takes seconds | JOINs / `selectinload`; snapshotted prices remove most joins anyway | Few thousand sales |
| `LIKE '%term%'` search with no index on a growing catalog | Autocomplete lag while typing | Index on product code; prefix search (`term%`) for codes; catalog is small (~thousands of SKUs) so this holds | Only at 100k+ products — effectively never here |
| Unbounded "all history" pages | Operation log page grows forever | Paginate history views from the start (HTMX makes this easy) | ~5–10k rows rendered |

## Security Mistakes

Domain-specific issues beyond generic web security — this is a localhost, single-user app, so the real risks are data exposure, not intrusion.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Binding uvicorn to `0.0.0.0` "so it works on my phone too" | Whole customer database + sales history readable by anyone on the Wi-Fi network (no auth in v1) | Bind to `127.0.0.1` explicitly; LAN access is a future milestone with auth |
| Backups with customer PII (names, consultant numbers, purchase history) synced to cloud folders unencrypted | Customer data leak | Keep backups local/USB, or encrypt (zip with password at minimum) before cloud upload |
| Raw SQL with f-strings for search/report filters | SQL injection — even single-user, a pasted product name with a quote corrupts queries | SQLAlchemy parameters everywhere; no string-built SQL |
| Secrets/config hardcoded when sync server arrives later | Credentials in git history | `.env` + environment variables convention from day one (costs nothing now) |

## UX Pitfalls

Common user experience mistakes in this domain (fast-entry operator tools).

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Hard-blocking sales on insufficient stock | Operator can't record what physically happened; keeps paper notes; data becomes incomplete | Warn-and-confirm, allow negative stock, flag for correction (Pitfall 10) |
| Requiring optional fields (customer, category, prices) | Every sale takes 30s instead of 5s; operator abandons the app | Spec says most fields optional — enforce that; only code+quantity required for a sale |
| No keyboard-first flow (mouse-driven forms) | Slow entry during busy periods | Autofocus code field, Enter-to-advance, autocomplete from dictionary, form resets to code field after save |
| Mistakes are unfixable (append-only misread as "no corrections") | Fear of the app; wrong data left in place | Visible "Cancel operation" that creates the compensating entry — append-only under the hood, forgiving on the surface |
| No feedback after save | Operator re-submits, duplicating sales | Instant HTMX confirmation with the saved operation summary + new stock level |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Sales flow:** Often missing the compensating cancel operation — verify a mistaken sale can be reversed and both entries appear in the audit log
- [ ] **Stock movements:** Often missing write-off/return/correction wiring — verify *every* operation type creates a movement row and `SUM(movements)` matches displayed stock
- [ ] **Money math:** Often missing edge rounding — verify profit on a multi-line report equals the sum of line profits to the cent
- [ ] **Backups:** Often missing the restore path — verify a backup file actually opens and contains today's operations (test once, for real)
- [ ] **Reports:** Often missing the midnight boundary — verify a 23:30 local-time sale lands in the correct daily report
- [ ] **Price history:** Often missing snapshotting — verify entering a new receipt at a new cost does NOT change last month's profit report
- [ ] **Concurrency setup:** Often missing per-connection PRAGMAs — verify WAL mode and `foreign_keys=ON` are active on a live connection, not just written in a setup script
- [ ] **Product edit:** Often missing history isolation — verify renaming a product doesn't rewrite what old sales receipts display (or that this is an accepted tradeoff)

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Stock drift discovered | LOW (if ledger exists) / HIGH (if not) | With ledger: recompute from movements, insert correction ops after physical count. Without: full physical inventory + start a ledger from that snapshot |
| Float money columns in production | MEDIUM | Add integer-cents columns, backfill with careful rounding, switch reads, drop old columns via Alembic batch migration; re-verify historical reports |
| Auto-increment IDs blocking sync | MEDIUM | Add UUID column to each syncable table, backfill, add unique index; integers stay as internal keys |
| Missing audit trail (destructive edits happened) | HIGH — history is unrecoverable | Accept the gap; enforce append-only from a cut-off date; note the cut-off in reports |
| Data loss, no backup | UNRECOVERABLE for lost data | Re-enter from physical count + memory; institute automated backups immediately |
| Corrupt DB from bad file-copy restore | LOW–MEDIUM | Delete stale `-wal`/`-shm`, try `PRAGMA integrity_check`, `.recover` if needed; restore from a proper `VACUUM INTO` backup |
| Timezone-shifted reports | LOW | Fix boundary conversion; historical UTC data is intact — only queries change |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls (topical phases — actual numbering set by the roadmap).

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Stock drift (no ledger) | Foundation/schema | `SUM(movements)` equals displayed stock after a scripted sequence of all operation types |
| Float money | Foundation/schema | No `Float`/`Numeric` money columns in models; cent-exact report totals in tests |
| Sync-blocking schema | Foundation/schema | Every business table has UUID + UTC `created_at`; operations append-only |
| SQLite concurrency setup | Foundation/schema | PRAGMAs asserted in a test on a live connection; single-worker run command documented |
| No/naive backups | Foundation or first daily-use release | Automated `VACUUM INTO` backup exists; one restore performed successfully |
| Destructive edits / audit trail | Operations (sales, write-off, return, correction) | Cancel = compensating op; original rows immutable |
| Profit from current prices | Sales & receipts | Sale lines carry snapshotted price+cost; new receipt doesn't alter past reports |
| Oversell handling | Sales (UX) + Reports | Warn-confirm flow works; negative stock surfaces in low-stock report |
| Timezone/date boundaries | Reports (storage convention set in Foundation) | 23:30 local sale appears in correct daily report; half-open interval queries |
| Over-engineering sync | Roadmap scope (all v1 phases) | requirements.txt contains no sync/CRDT dependencies; no server components in v1 |

## Sources

- SQLite official docs (HIGH): [Write-Ahead Logging](https://sqlite.org/wal.html), [Temporary Files Used By SQLite](https://sqlite.org/tempfiles.html), [SQLite Forum — WAL single writer & busy_timeout](https://sqlite.org/forum/info/c4af81286f802c247df65eb528162538359d74237ca1ec9547f6319aa113ef80), [SQLite Forum — .dump on active WAL DB](https://sqlite.org/forum/info/bfa64b55aca38e00c254d4ba9541fc7ef296452d5ae920ef9c68d079184b042c)
- SQLite concurrency in Python apps (MEDIUM, cross-verified): [SQLite concurrent writes and "database is locked" errors](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/), [Abilian — preventing "database is locked"](https://lab.abilian.com/Tech/Databases%20&%20Persistence/sqlite/How%20to%20prevent%20the%20%22SQLite%20database%20is%20locked%22%20error/)
- Backups in practice (MEDIUM): [Vaultwarden discussion — backing up SQLite properly](https://github.com/dani-garcia/vaultwarden/discussions/1613), [Vaultwarden — restore & stale WAL corruption](https://github.com/dani-garcia/vaultwarden/discussions/6104), [Backing up SQLite on Ubuntu](https://oneuptime.com/blog/post/2026-03-02-how-to-back-up-sqlite-databases-on-ubuntu/view)
- Money as integers/Decimal (MEDIUM-HIGH, industry consensus): [Modern Treasury — Floats Don't Work For Storing Cents](https://www.moderntreasury.com/journal/floats-dont-work-for-storing-cents), [LearnPython — Count Money Exactly in Python](https://learnpython.com/blog/count-money-python/)
- Ledger vs mutable quantity, denormalization drift (MEDIUM): [AccountingTools — Inventory ledger](https://www.accountingtools.com/articles/what-is-an-inventory-ledger.html), [Rafael Rampineli — Denormalization: performance or long-term trap](https://rafaelrampineli.medium.com/denormalization-a-solution-for-performance-or-a-long-term-trap-6b9af5b5b831)
- ID strategy for offline/sync (MEDIUM): [PowerSync — Sequential ID Mapping](https://docs.powersync.com/client-sdks/advanced/sequential-id-mapping), [Bytebase — UUID vs auto-increment](https://www.bytebase.com/blog/choose-primary-key-uuid-or-auto-increment/)
- Local-first complexity / CRDT reality check (MEDIUM): [RxDB — Downsides of Offline First](https://rxdb.info/downsides-of-offline-first.html), [RxDB — Local-first future & limitations](https://rxdb.info/articles/local-first-future.html)
- COGS / cost snapshotting (MEDIUM): [NetSuite — Cost of Goods Sold](https://www.netsuite.com/portal/resource/articles/financial-management/cost-of-goods-sold-cogs.shtml), [QuickBooks — FIFO inventory cost accounting](https://quickbooks.intuit.com/learn-support/en-us/help-article/inventory-management/fifo-used-inventory-cost-accounting/L1x3hkunE_US_en_US)
- Timezone/report boundaries (MEDIUM): [Square community — daily report past-midnight sales](https://community.squareup.com/t5/Archived-Discussions-Read-Only/How-do-I-change-the-daily-sales-reports-if-my-close-of-day-is/td-p/30387), [DEV — handling date/time to avoid timezone bugs](https://dev.to/kcsujeet/how-to-handle-date-and-time-correctly-to-avoid-timezone-bugs-4o03)

---
*Pitfalls research for: local-first inventory & sales app (FastAPI + HTMX + SQLite)*
*Researched: 2026-07-08*
