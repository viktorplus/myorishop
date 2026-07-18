# Pitfalls Research

**Domain:** Local-first SQLite app gaining client↔central-server sync (online + USB), a central PostgreSQL server, and mandatory auth/roles
**Researched:** 2026-07-18
**Confidence:** HIGH (codebase-grounded) / MEDIUM (sync-design recommendations = practitioner consensus)

> Scope note: these pitfalls are tied to THIS app's real structures — the append-only `operations` ledger written only through `record_operation()`, the sibling append-only `cash_movements` ledger, the derived `Product.quantity`/`Batch.quantity` caches, the Python-computed Cyrillic `name_lc`/`search_lc` shadow columns, the mirrored desktop (`/...`) + mobile (`/m/...`) route trees, and the CSV export / VACUUM-INTO backup endpoints. Generic "use HTTPS" advice is omitted.

---

## Critical Pitfalls

### Pitfall 1: Replaying synced ledger rows THROUGH `record_operation()` — double-counting stock

**What goes wrong:**
When a batch of foreign operations arrives (from the server online, or from a USB exchange file), the obvious-looking way to apply them is to loop and call `record_operation(...)` for each. That silently corrupts everything: `record_operation()` is not a neutral inserter — it (a) mints a fresh `id=new_id()`, (b) re-stamps `device_id=settings.device_id` and a fresh local `seq` via `next_seq()`, (c) stamps `created_by=settings.operator_name` and a new `created_at`, and (d) does the non-idempotent cache increment `product.quantity = Product.quantity + qty_delta` (plus the batch cache). So a foreign op gets a new identity (defeating dedup-by-UUID), loses its origin author/device/time, and inflates the local stock cache. Re-running the same sync (a retry after a dropped connection) does it again.

**Why it happens:**
`record_operation()` is documented as "the ONLY sanctioned write path" (FND-01), so a developer reasonably assumes sync must go through it too. But that rule is about *local UI writes*, not *merge/replay*.

**How to avoid:**
Add a separate merge path (e.g. `apply_remote_operation()` / bulk insert) that inserts rows **verbatim** — preserving the origin `id`, `device_id`, `seq`, `created_at`, `created_by` — using `INSERT ... ON CONFLICT (id) DO NOTHING` (Postgres) / `INSERT OR IGNORE` semantics keyed on the UUID PK so re-applying is a no-op. Do **not** touch `Product.quantity`/`Batch.quantity` during the merge; instead call the already-existing `rebuild_stock(session)` once after all rows are applied. Make the whole merge idempotent by UUID PK. The UUID PKs and `synced_at` cursor were seeded from v1.0 precisely for this — use them.

**Warning signs:**
Stock cache drifts upward after every sync; the same logical sale appears twice in `/history` with different IDs; `rebuild_stock()` raises `stock invariant violated`; retrying an interrupted sync changes balances.

**Phase to address:** Sync foundation phase (the merge/apply engine), before any transport work.

---

### Pitfall 2: Forgetting to recompute the derived caches after a merge — stock/balance disagree with the ledger

**What goes wrong:**
`Product.quantity` and `Batch.quantity` are caches — "a projection of SUM(operations.qty_delta), always recomputable". After merging remote ledger rows, if you don't recompute them, the dashboard, product list, oversell guard, and stock-valuation report all show pre-sync numbers while the ledger already holds the new rows. Worse, if you *did* increment during merge (Pitfall 1) AND recompute, you'll have double-applied.

**Why it happens:**
The cache is invisible in day-to-day code (reads just use `product.quantity`); nothing in the current single-device code ever needed a rebuild after a bulk insert.

**How to avoid:**
Treat cache recompute as a mandatory, atomic final step of every merge (both transports). Call `rebuild_stock(session)` — it already recomputes every `Product.quantity` and `Batch.quantity` from the ledger AND asserts the invariant per product. The cash balance is even simpler: it is deliberately NOT cached (`D-00b: balance is always a live SUM(amount_cents)`), so merging `cash_movements` needs no balance rebuild — but confirm no one later "optimizes" it into a cached column. Run the merge + rebuild in one transaction so a crash can't leave applied rows with a stale cache.

**Warning signs:**
`compute_stock()` ≠ `product.quantity` after sync; the "expiring soon" / low-stock reports lag; `rebuild_stock` raising is actually the *good* case (it caught the drift) — silent drift is the dangerous one.

**Phase to address:** Sync foundation phase (merge engine), same transaction as the apply step.

---

### Pitfall 3: `device_id` and `created_by` are static config defaults — colliding sequences and forged authorship across operators

**What goes wrong:**
Today `settings.device_id` defaults to the literal `"device-01"` and `settings.operator_name` to `"operator"`, and `record_operation()` stamps both from config. Ship two clients without changing `.env` and **every** client emits `device_id="device-01"`. The `UNIQUE(device_id, seq)` constraint on both `operations` and `cash_movements` then collides the moment the server (or a peer) holds rows from two devices: device A's `(device-01, 5)` and device B's `(device-01, 5)` are the same key → merge insert fails or, if the constraint is dropped, two distinct ops become indistinguishable and one is silently lost. Separately, with mandatory login, `created_by` must be the logged-in user, not a process-wide config string — otherwise the audit trail attributes every operator's actions to the same name.

**Why it happens:**
In a single-device app a constant device id and operator name were correct and cheap. Sync makes device identity a hard requirement, and auth makes per-user attribution a hard requirement, but the config-default seam still "works" (no error) until a second device exists.

**How to avoid:**
- Generate a persistent, unique `device_id` (UUID) per client install on first run, store it in the DB (a one-row settings/identity table), never in shared code or a copied `.env`. Verify uniqueness server-side on first sync.
- Make `created_by` come from the authenticated session/user at write time, threaded into `record_operation()` — not read from `settings`. Keep a `user_id` (UUID) in addition to a display name so a renamed user stays linkable.
- Keep the server as a **preserver, not a re-stamper**: it must store each row's origin `device_id`+`seq` unchanged; never regenerate `seq` server-side.

**Warning signs:**
Two installs show the same `device_id` in `/history` or the operations table; `UNIQUE(device_id, seq)` violations on the very first multi-device sync; every ledger row's `created_by` is the same string.

**Phase to address:** Sync foundation phase (device identity) + Auth phase (per-user `created_by`). Do device identity FIRST — the auth phase depends on stable identity.

---

### Pitfall 4: The two append-only ledgers (`operations` + `cash_movements`) synced inconsistently — stock and cash disagree

**What goes wrong:**
A sale writes to BOTH ledgers in the same local transaction: a `sale` row in `operations` (stock down) and a `sale`-category row in `cash_movements` (balance up); a return writes symmetric rows to both. But the two tables have **independent** `(device_id, seq)` counters and are separate append-only logs. If the sync engine ships/merges `operations` and `cash_movements` as two independent streams, a transport interruption or a partial-batch bug can land the stock side of a sale without the cash side (or vice-versa). Result: the product shows sold but the cash balance never rose — the exact "profit figures wrong / data lost" failure the Core Value forbids.

**Why it happens:**
The ledgers were built as siblings with mirrored shapes, which invites treating them as two symmetric-but-separate sync jobs. Their *transactional coupling* (a sale = rows in both) lives only in the local write services, not in the schema.

**How to avoid:**
Sync both ledgers inside one atomic merge transaction and commit them together — never "operations succeeded, cash pending". For USB, put both tables in the same exchange file and apply them all-or-nothing. Add a post-merge reconciliation check: for every `sale_id`, the `operations` sale rows and the `cash_movements` sale row must both be present (or both absent). Because both are append-only and keyed by UUID, the reconciliation is a cheap join, run right after `rebuild_stock`.

**Warning signs:**
Cash-flow report income ≠ sum of synced sales; a `sale_id` present in `operations` with no matching `cash_movements` row after sync; balance and stock-valuation reports that were consistent locally diverge post-sync.

**Phase to address:** Sync foundation phase (merge engine covers both ledgers atomically) + a reconciliation check in the same phase.

---

### Pitfall 5: Interrupted / partial USB transfer leaving a half-applied batch

**What goes wrong:**
The USB path reads an exchange file and applies rows. If it applies row-by-row with intermediate commits (or writes the stock cache incrementally), a pulled drive / crash / malformed tail record leaves the DB with some rows applied, the caches partially updated, and no clean way to know where it stopped. Re-importing the same file then risks either duplicating (if not keyed by UUID) or, if the importer "resumes" heuristically, skipping rows.

**Why it happens:**
Large files invite streaming/chunked application "to save memory"; the append-only insert feels safe to do incrementally because each row is immutable.

**How to avoid:**
Apply an exchange file as a single all-or-nothing transaction: begin, `INSERT OR IGNORE` all ledger rows (dedup by UUID), merge mutable master rows, `rebuild_stock`, then one commit. If anything raises, roll back to the pre-import state (and the startup VACUUM-INTO backup is the outer safety net). Record an idempotency marker (file hash / export batch UUID) so a re-import of the identical file is a proven no-op, not a guess. Validate the entire file (schema version, integrity) BEFORE opening the write transaction.

**Warning signs:**
`rebuild_stock` raises after a USB import; row counts don't match the file's declared count; a second import of the same file changes anything.

**Phase to address:** Offline/USB sync phase — but it reuses the same idempotent merge engine and single-transaction rule as Pitfall 1/2, so build that engine first.

---

### Pitfall 6: Only `operations`/`cash_movements` merge cleanly — the MUTABLE master tables (products, customers, warehouses, batches, dictionary) have no conflict story

**What goes wrong:**
The "append-only ledger is the sync foundation" narrative is true for stock and cash — those are commutative (a merge is just the union of immutable rows; final stock = SUM of deltas regardless of order). But the app also has **mutable, updated-in-place** tables: `Product` (name/prices/thresholds/`deleted_at`, `updated_at`), `Customer` (+ contacts), `Warehouse`, `Batch` (price/location/comment/quantity), `Dictionary`, `ActiveCatalog`, `Sale` headers. Two operators editing the same product on different devices, or one editing while another soft-deletes, is a real conflict the ledger merge does nothing for. Naively "last-write-wins by `updated_at`" is unreliable because `updated_at` is a wall-clock string from each client (see Pitfall 7). And `Product.code`'s partial unique index (`uq_products_code_active`) will be **violated** when two devices independently create the same product code and both sync to the server.

**Why it happens:**
The project decisions repeatedly emphasize the append-only ledger as "the sync foundation", which is easy to over-generalize into "everything syncs cleanly". The mutable catalog/customer half was never designed for merge.

**How to avoid:**
Decide an explicit policy per mutable table before writing merge code: e.g. last-write-wins keyed on a monotonic per-row version or a server-authoritative timestamp (not a client clock); soft-delete (`deleted_at`) as a tombstone that propagates rather than a hard delete; and a defined resolution for `Product.code` collisions (server rejects/renames the loser, or codes become globally coordinated). Consider making the central server the source of truth for master data (clients pull), while ledgers flow client→server. Keep `Batch.quantity`/`Product.quantity` OUT of the synced master data — they're caches, rebuilt locally.

**Warning signs:**
`uq_products_code_active` violations on sync; a product edit made on the phone silently reverts after a desktop sync; a soft-deleted customer reappears; two "same" products with different UUIDs.

**Phase to address:** Sync foundation / data-model phase — this needs an explicit design decision and likely its own sub-phase; it is the most underestimated part of the milestone.

---

### Pitfall 7: Trusting client wall-clock time for ordering or conflict resolution

**What goes wrong:**
`created_at`/`updated_at` are UTC ISO **text** strings stamped from each client's local clock (`utcnow_iso()`). Clients are offline PCs whose clocks can be minutes-to-days off. Any logic that orders cross-device events by `created_at`, or resolves a master-data conflict by "newer timestamp wins", will make wrong decisions when a clock is skewed. For stock/cash totals this is harmless (sums are order-independent), but for the history *display order*, "last edit wins", and any future "who was first" logic it matters.

**Why it happens:**
ISO text timestamps sort lexicographically == chronologically within one device, so they look like a global clock; they aren't.

**How to avoid:**
Rely on the commutative ledger for correctness (totals don't need ordering). For per-device causal ordering use `(device_id, seq)`, which is monotonic per device. For master-data conflict resolution, prefer a server-assigned timestamp/version at sync time (the server has one clock) over client `created_at`. Don't build a global total order out of client wall-clocks; if display needs a global feed, sort by server-received time or accept approximate ordering.

**Warning signs:**
History feed rows interleave in impossible order after sync; a stale edit wins because a device's clock is fast; "days until catalog closes" or period reports shift when a client's clock is wrong.

**Phase to address:** Sync foundation phase (define ordering/conflict rules) — cross-cutting; document the rule once.

---

### Pitfall 8: Relaxing the append-only UPDATE trigger too broadly for the sync cursor — reopening the ledger to tampering

**What goes wrong:**
Sync needs to stamp `synced_at` on rows already written — but `synced_at` lives on `operations`/`cash_movements`, and those tables carry `operations_no_update` / `cash_movements_no_update` triggers that `RAISE(ABORT)` on ANY update. `app/db.py` explicitly anticipates this: "the v2 sync milestone relaxes the UPDATE trigger with a WHEN clause in a NEW migration". The pitfall is relaxing it wrong — dropping the trigger entirely, or a `WHEN` that permits updating more than `synced_at`. That converts the immutable audit ledger (the whole integrity story, and the reason merges are safe) into a mutable table a bug — or a compromised sync endpoint — could use to rewrite `qty_delta`, `amount_cents`, prices, or authorship after the fact.

**Why it happens:**
The simplest way to make `UPDATE operations SET synced_at=... ` work is to drop the trigger. It "works" and tests pass.

**How to avoid:**
Write the relaxation as a **column-scoped** trigger: allow the UPDATE only when nothing but `synced_at` changes (e.g. abort `WHEN OLD.qty_delta IS NOT NEW.qty_delta OR OLD.amount_cents IS NOT NEW.amount_cents OR ...` — reject if any immutable column differs). Do it in a NEW Alembic migration (never edit the frozen `APPEND_ONLY_TRIGGERS` DDL semantics in place — migration 0001 froze its own copy; the constant is for test fixtures). Mirror the equivalent guard on PostgreSQL (a `BEFORE UPDATE` trigger/rule, since Postgres has no SQLite trigger syntax — see Pitfall 11). Consider tracking sync progress in a **separate** cursor table instead of mutating ledger rows at all, which sidesteps the trigger entirely.

**Warning signs:**
The migration drops rather than replaces the trigger; a test proves `synced_at` updates but no test proves `qty_delta`/`amount_cents` updates still ABORT; the Postgres side has no equivalent trigger.

**Phase to address:** Sync foundation phase (the `synced_at` cursor design) — with an explicit "immutable columns still rejected" test on BOTH SQLite and PostgreSQL.

---

### Pitfall 9: Adding auth but leaving the parallel MOBILE route tree (or export/backup) unguarded — role escalation & data leak

**What goes wrong:**
The app has ~40 routers in two near-mirrored trees: desktop (`sales`, `receipts`, `finance`, `export`, `backup`, `settings`, ...) and mobile (`mobile_sales`, `mobile_receipts`, `mobile_finance`, `mobile_reports`, ...). Auth/role gating added only to the desktop tree leaves every `/m/...` endpoint open — an operator (or an unauthenticated request) can drive receipts/sales/finance through the mobile routes even if the desktop equivalents are locked. The same asymmetry hits the two high-value data endpoints: `export` (full products/sales/customers/cash CSV dumps — every row, no filter) and `backup` (VACUUM-INTO of the entire DB). If those aren't restricted to the administrator role, an operator can exfiltrate the whole dataset. The mobile home even exposes report/finance tiles.

**Why it happens:**
The desktop and mobile trees were deliberately built as separate routers reusing the same services; a guard added as a per-router dependency is easy to wire into one include-list and forget the other. There is currently **zero** auth middleware in `main.py`, so "protected" is not the default — every new route is public unless explicitly gated.

**How to avoid:**
Enforce auth as a global default (app-level dependency / middleware) so routes are closed unless opted-out (the login page itself), rather than opt-in per router. Define the role→route matrix once and assert it in tests that enumerate EVERY router in `main.py` (both trees) — a test that fails when a new unguarded router is added. Put `export` and `backup` behind the administrator role explicitly. Map the admin/operator split from PROJECT.md: admin = users/warehouses/dictionaries/settings/reports; operator = receipts/sales/write-offs/cash — and apply it identically to `/x` and `/m/x`.

**Warning signs:**
A `/m/...` endpoint returns data without a session; `curl` to `/export/...` or `/backup/...` succeeds unauthenticated or as an operator; a new mobile router added without a corresponding auth test; the role check exists on `sales.py` but not `mobile_sales.py`.

**Phase to address:** Auth & roles phase — with a "every router is gated" enumeration test as an exit criterion.

---

### Pitfall 10: Storing passwords wrong / session fixation / no CSRF on the all-HTMX POST forms

**What goes wrong:**
This is the app's *first ever* security boundary — there is no auth code to copy patterns from. Three concrete traps: (1) storing passwords as plaintext or a fast/unsalted hash (MD5/SHA-256) instead of a slow salted KDF; (2) session fixation — reusing the pre-login session identifier after authentication, letting an attacker fix a victim's session; (3) no CSRF protection — the entire UI is HTMX `hx-post` form submissions, and once auth is a cookie session, any external page can forge state-changing POSTs (create sale, withdraw cash, delete product) against the server unless CSRF is handled.

**Why it happens:**
"Single local user, no auth" was the v1 assumption; the team has never shipped login here, so defaults (a hand-rolled cookie, a plain hash) are tempting.

**How to avoid:**
Hash with a modern KDF (argon2id or bcrypt) via a maintained library; never invent crypto. Use a vetted session mechanism (signed/rotated session cookie, e.g. Starlette `SessionMiddleware` or `fastapi-users` per the CLAUDE.md "add session-cookie auth then" note) and **rotate the session id on login** to kill fixation. Set cookies `HttpOnly`, `Secure` (server is over the internet now), `SameSite=Lax/Strict`. Add CSRF tokens to HTMX POSTs (hidden field or `hx-headers` with a per-session token validated server-side); `SameSite` cookies help but are not sufficient alone. Verify these on BOTH route trees (Pitfall 9).

**Warning signs:**
Passwords readable in the DB; login doesn't change the session cookie value; a cross-site form can POST to a state-changing endpoint; CSRF token absent from `hx-post` forms.

**Phase to address:** Auth & roles phase.

---

### Pitfall 11: SQLite→PostgreSQL portability traps that only bite once the real server exists

**What goes wrong:**
The models were written "sync-ready" and mostly portable, but several things behave differently on a live PostgreSQL server and won't surface until then:
- **`render_as_batch=True` is SQLite-only.** Alembic's batch mode (rebuild-table-to-ALTER) is required for SQLite and *wrong* for PostgreSQL, which supports real `ALTER`. Running batch migrations against Postgres, or maintaining one migration that assumes batch, breaks. The Alembic `env.py` must set `render_as_batch` conditionally on dialect.
- **Cyrillic `name_lc`/`search_lc` shadow columns.** These exist because "SQLite `lower()`/`LIKE` cannot fold Cyrillic", so they're computed in Python (`str.lower()`) and matched with `LIKE`. PostgreSQL *can* case-fold Cyrillic (`ILIKE`, `lower()` under a UTF-8 collation). If any Postgres-side code path switches to `ILIKE`/`lower()` on `name` directly, it returns different matches than the Python-computed shadow, causing search inconsistency between client (SQLite+shadow) and server. Keep the shadow-column approach uniform on both DBs, or fully commit to server-side collation — don't mix.
- **Boolean-ish `is_legacy`** is an `Integer` 0/1. Fine as Integer on Postgres, but if anyone remaps it to `Boolean`, SQLite's 0/1 and Postgres `true/false` diverge in comparisons.
- **Timestamps are TEXT ISO** and queries compare them as strings (`created_at >= start_iso`). If a Postgres column is ever declared `timestamptz`, string comparison and lexicographic ordering break. Keep them TEXT, or convert every comparison.
- **`JSON` columns** (`payload`, `catalogs`): SQLite stores JSON as TEXT; Postgres has native `json`/`jsonb` with different query operators. Currently read only in Python — safe — but any server-side `payload->>'reason_code'` query is non-portable.
- **Partial unique index** (`uq_products_code_active`) already ships both `sqlite_where` and `postgresql_where` — good; keep that pattern for any new partial index.
- **Money is integer cents** everywhere (good, portable); never let a Postgres migration turn a cents column into `Numeric`/`float`.
- **SQLite-specific SQL** (`INSERT OR IGNORE`, `INSERT OR REPLACE`, `strftime`) that a merge/import path might introduce is non-portable — express portably or dialect-branch.

**Why it happens:**
SQLite is famously permissive (dynamic typing, ignores lengths, no real ALTER). Code that "works" on SQLite can rely on that permissiveness; Postgres is strict and rejects or behaves differently.

**How to avoid:**
Stand up a real PostgreSQL instance in CI and run the *same* Alembic history + a subset of tests against it early — don't wait for deployment. Make `render_as_batch` dialect-conditional in `env.py`. Add a cross-DB search test proving Cyrillic case-insensitive search returns identical results on SQLite and Postgres. Keep timestamps TEXT and money integer. Audit for any raw SQLite-specific constructs.

**Warning signs:**
Migrations run on SQLite but fail on Postgres; Cyrillic search matches differ between client and server; length overflows appear only on Postgres (SQLite ignored `String(n)`); `ILIKE` sneaks into a query.

**Phase to address:** Central PostgreSQL server phase — with a Postgres-in-CI gate before the server ships.

---

### Pitfall 12: Untrusted exchange file — tampering, forged rows, and schema-version drift

**What goes wrong:**
The USB exchange file crosses a trust boundary: it can be edited, corrupted, or crafted. Two distinct risks. (1) **Tampering / forged rows:** a hand-edited file could inject ledger rows with a forged `device_id`/`created_by` (impersonating another operator), negative or absurd `qty_delta`/`amount_cents`, or a `batch_id` belonging to another product — and if the merge path is a raw bulk insert (correctly bypassing `record_operation()` per Pitfall 1), it also bypasses `record_operation()`'s ownership/validation guards (soft-deleted-product rejection, batch-belongs-to-product check, category allow-lists). Formula-injection also re-enters if exchange data is ever re-exported to CSV without `_csv_safe`. (2) **Schema-version drift:** a client on app v3.0 and a server/peer on v3.1 have different columns/tables; a file from the newer version imported by the older (or vice-versa) can fail hard, or worse, silently drop columns and apply a subtly wrong subset.

**Why it happens:**
Offline/USB feels "internal" and trusted, so validation is skipped; and both ends' schema is assumed identical because they're "the same app".

**How to avoid:**
- Treat the file as untrusted input: sign it (HMAC/asymmetric) or at minimum checksum + validate on import; reject on signature/integrity failure before opening the write transaction.
- Re-run the same server-side allow-lists and ownership/sanity checks on merged rows that `record_operation()` does inline — validate `qty_delta` sign vs type, `category` ∈ `CASH_CATEGORIES`, `type` ∈ `OPERATION_TYPES`, batch-belongs-to-product, product not soft-deleted — even on the bulk path. Reject/quarantine violating rows rather than trusting the file.
- Bind rows to their authenticated origin: on the online path the server authenticates the device/user, so `created_by`/`device_id` are trustworthy; for USB, carry a signed manifest identifying the exporting device/user and reject rows whose claimed origin doesn't match.
- Stamp every exchange file with an explicit **schema/app version** in a header/manifest; on import, refuse (with a clear operator message) if the versions are incompatible, and define a forward/backward-compat rule. Never silently drop unknown columns.
- Keep `_csv_safe` on any path that re-emits imported free-text to CSV.

**Warning signs:**
Import accepts a file with a mismatched version header; a merged op has a `created_by` that never authenticated; negative `qty_delta` on a `receipt` slips in; a batch_id references another product; imported text later opens as an Excel formula.

**Phase to address:** Offline/USB sync phase (file format, signing, version header, validation) — the validation logic is shared with the online merge path.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reuse `record_operation()` to apply synced rows | No new code path | Double-counted stock, lost origin identity, non-idempotent retries (Pitfall 1) | **Never** — build a dedicated verbatim merge path |
| Drop the append-only UPDATE trigger to write `synced_at` | Cursor works immediately | Ledger becomes mutable; integrity & tamper-resistance gone (Pitfall 8) | **Never** — use a column-scoped trigger or a separate cursor table |
| Gate auth per-router, opt-in | Small, incremental | A forgotten mobile/export router stays public (Pitfall 9) | Only if a test enumerates every router and fails on a gap |
| Keep `device_id`/`created_by` from static config | Zero change to the write path | Seq collisions across devices; unattributable audit trail (Pitfall 3) | **Never** once a 2nd device or 2nd user exists |
| Ship both sync transports before proving the merge engine | Feature-complete sooner | Two half-tested integration paths over the riskiest code in project history | Never — build & prove the shared idempotent merge engine first, then layer transports |
| Sync master tables as last-write-wins on client `updated_at` | Simple to code | Skewed clocks corrupt edits; code collisions (Pitfall 6/7) | Only with a server-authoritative version/timestamp and a defined code-collision rule |
| Test only on SQLite | Fast local CI | Postgres-only failures found in production (Pitfall 11) | Never for this milestone — add Postgres to CI |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Central PostgreSQL | Assuming SQLite-passing migrations/queries "just work"; `render_as_batch` on Postgres | Postgres in CI; dialect-conditional batch mode; portable ORM constructs only |
| Online sync transport | Non-idempotent retry after a dropped HTTP connection double-applies a batch | Idempotent merge keyed on UUID PK + an export-batch id; safe to re-send |
| USB exchange file | Trusting the file; applying row-by-row with commits | Sign/validate + version header; single all-or-nothing transaction; re-run write-path validations |
| Dual ledgers (operations + cash) | Syncing them as two independent streams | One atomic merge covering both + a `sale_id` reconciliation check |
| Cache columns | Shipping `Product.quantity`/`Batch.quantity` in the sync payload | Never sync caches; `rebuild_stock()` after every merge |
| Session cookies + HTMX | No CSRF token on `hx-post`; non-rotating session id | CSRF token via `hx-headers`/hidden field; rotate session on login; `HttpOnly`/`Secure`/`SameSite` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `rebuild_stock()` full-table recompute on every sync | Sync slows as ledger grows (re-sums every product & batch) | Incremental recompute of only touched products/batches, or accept full rebuild while row counts are small | Tens of thousands of ledger rows across multi-year multi-operator history |
| `next_seq()` = `SELECT max(seq)` per insert | Fine single-writer; contention if the server ever writes ledger rows itself | Server preserves origin seq (never generates); keep local single-writer assumption | Only if the server starts minting its own ledger rows concurrently |
| Full-table CSV export / VACUUM-INTO backup over the network | Large dumps block; memory spikes | Already streamed (good); keep streaming; gate by role; consider server-side scheduled backups | Large multi-operator dataset pulled synchronously |
| Sending the entire ledger every sync | Sync time grows unbounded | Use the `synced_at` cursor to send only unsynced rows (delta sync) | Immediately at scale — cursor is why `synced_at` exists |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Plaintext / fast-hash passwords | Credential theft on server compromise | argon2id/bcrypt via a maintained lib |
| No CSRF on HTMX POST forms | Forged sales/withdrawals/deletes | Per-session CSRF token validated server-side + `SameSite` cookies |
| Session not rotated on login | Session fixation | Regenerate session id at authentication |
| Export/backup endpoints not role-gated | Operator exfiltrates full dataset (all customers, sales, cash) | Administrator-only; enumeration test over both route trees |
| Mobile route tree unguarded | Role escalation via `/m/...` bypass | Global auth default; role matrix asserted for every router |
| Bulk-merge path skips write-path validations | Forged/absurd ledger rows enter via sync/USB | Re-run allow-lists + ownership + sign checks on merged rows |
| Relaxed append-only trigger too broad | Post-hoc rewrite of qty/amount/author | Column-scoped trigger; test immutables still ABORT |
| Trusting `created_by`/`device_id` from an exchange file | Impersonation of another operator | Bind to authenticated origin / signed manifest |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent sync failure | Operator believes data is safe; it isn't (violates Core Value) | Explicit sync status/last-synced time; loud, actionable errors in Russian |
| Version-mismatch import fails cryptically | Operator can't tell why USB sync did nothing | Clear Russian message naming the version gap and next step |
| Login/roles added with English UI strings | Inconsistent with the Russian UI | All auth/role prompts and errors in Russian (per project convention) |
| Conflict silently resolved (edit reverts) | Operator's product/customer edit vanishes with no notice | Surface conflicts or make server-authoritative resolution predictable & visible |

## "Looks Done But Isn't" Checklist

- [ ] **Sync merge:** Often missing idempotency — verify re-sending/re-importing the same batch changes nothing (UUID-PK dedup).
- [ ] **Cache after merge:** Often missing the `rebuild_stock()` call — verify `compute_stock()` == `product.quantity` for every product post-sync.
- [ ] **Dual ledgers:** Often missing cash↔stock atomicity — verify every synced `sale_id` has rows in BOTH ledgers.
- [ ] **Auth coverage:** Often missing the mobile tree / export / backup — verify a test enumerates every router in `main.py` and asserts its required role.
- [ ] **Append-only after relax:** Often missing the immutability test — verify updating `qty_delta`/`amount_cents` still ABORTs while `synced_at` updates succeed, on SQLite AND Postgres.
- [ ] **Postgres parity:** Often missing a real Postgres run — verify the full Alembic history + Cyrillic search tests pass on Postgres in CI.
- [ ] **Device identity:** Often missing per-install uniqueness — verify two fresh installs get distinct `device_id`s and don't collide on `UNIQUE(device_id, seq)`.
- [ ] **Exchange file:** Often missing a version header + signature — verify a tampered or version-mismatched file is rejected before any write.
- [ ] **Master-data conflicts:** Often missing entirely — verify a defined outcome for concurrent product edits and duplicate `code` creation across devices.
- [ ] **CSRF:** Often missing on HTMX — verify a state-changing `hx-post` without a valid token is rejected.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Double-counted stock after bad merge (P1/P2) | LOW | Ledger is intact & append-only — run `rebuild_stock()` to recompute caches from truth |
| Half-applied USB import (P5) | LOW–MEDIUM | Roll back the merge transaction; restore from the startup VACUUM-INTO backup; re-import validated file |
| Ledger tampered via over-broad trigger (P8) | HIGH | Hard to detect/undo post-hoc — restore from backup; re-scope trigger; add immutability tests; audit affected rows |
| Duplicate product codes merged (P6) | MEDIUM | Define winner, re-point ledger `product_id`s (append-only correction rows, not deletes), rebuild caches |
| Data leak via unguarded export/mobile route (P9) | HIGH | Rotate credentials/secrets; add gating + enumeration test; assess exposure — leaked data can't be un-leaked |
| Plaintext passwords discovered (P10) | MEDIUM | Force reset all passwords; migrate to argon2id; invalidate sessions |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase (area) | Verification |
|---------|-------------------------|--------------|
| P1 Replay via `record_operation()` | Sync foundation (merge engine) | Re-applying a batch is a no-op; origin id/device/seq/author preserved |
| P2 Caches not recomputed | Sync foundation (merge engine) | `compute_stock()` == cache for all products after sync |
| P3 Static `device_id`/`created_by` | Sync foundation (device identity) + Auth (per-user author) | Distinct per-install device_id; `created_by` = session user |
| P4 Dual-ledger inconsistency | Sync foundation (atomic dual merge) | Every synced `sale_id` present in both ledgers |
| P5 Partial USB apply | Offline/USB sync | Single-transaction import; interrupted import leaves no trace |
| P6 Mutable master conflicts | Sync foundation (data-model design) | Defined resolution for concurrent edits + `code` collisions |
| P7 Clock trust | Sync foundation (ordering rules) | Correctness independent of client clocks; documented rule |
| P8 Over-broad trigger relax | Sync foundation (`synced_at` cursor) | Immutable columns still ABORT on SQLite & Postgres |
| P9 Unguarded mobile/export/backup | Auth & roles | Enumeration test gates every router in both trees |
| P10 Password/CSRF/session | Auth & roles | argon2id hashing; session rotation; CSRF on HTMX POSTs |
| P11 SQLite→Postgres portability | Central PostgreSQL server | Full Alembic history + Cyrillic search pass on Postgres in CI |
| P12 Untrusted exchange file | Offline/USB sync | Signed + version-headed file; validations re-run on merge |

## Sources

- Codebase (HIGH): `app/services/ledger.py` (`record_operation`, `next_seq`, `rebuild_stock`, `compute_stock`), `app/models.py` (UUID PKs, `device_id`/`seq` UNIQUE, `synced_at`, `name_lc`/`search_lc`, integer-cents, `is_legacy`, JSON columns, `uq_products_code_active` dual `sqlite_where`/`postgresql_where`), `app/db.py` (`APPEND_ONLY_TRIGGERS` + the explicit "v2 sync relaxes the UPDATE trigger with a WHEN clause" note, PRAGMA setup), `app/config.py` (static `device_id`/`operator_name` defaults), `app/main.py` (no auth middleware; ~40 routers across desktop + mobile trees), `app/services/export.py` (`_csv_safe` formula-injection guard, full-table dumps, BOM-once).
- Project context (HIGH): `.planning/PROJECT.md` — v3.0 milestone scope, admin/operator role split, "append-only ledger is the sync foundation" decisions (D-05..D-11), "both transports = maximum-scope, highest-risk" note.
- `CLAUDE.md` (HIGH): Stack Patterns by Variant (UUID-for-sync, WAL/foreign_keys pragmas, `render_as_batch` SQLite-only, TEXT UTC timestamps, integer cents, "add session-cookie auth then"), What NOT to Use (no SQLite-specific SQL, no float money).
- Practitioner consensus / official docs knowledge (MEDIUM–HIGH): idempotent-merge-by-UUID and delta-sync-cursor patterns; last-write-wins vs. server-authoritative conflict resolution; OWASP session-fixation/CSRF guidance; argon2id/bcrypt for password storage; SQLAlchemy SQLite-dialect FK-pragma and Alembic batch-mode documentation.

---
*Pitfalls research for: adding client-server sync + central PostgreSQL + auth/roles to a mature local-first SQLite app (MyOriShop v3.0)*
*Researched: 2026-07-18*
