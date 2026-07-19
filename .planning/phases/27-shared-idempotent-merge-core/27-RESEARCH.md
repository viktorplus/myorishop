# Phase 27: Shared Idempotent Merge Core - Research

**Researched:** 2026-07-19
**Domain:** Deterministic set-union-by-UUID merge of append-only ledgers, server-authoritative reference-data conflict resolution, derived-state recompute, portable (SQLite↔PostgreSQL) pure-function engine + NDJSON exchange format
**Confidence:** HIGH (engine is grounded almost entirely in the existing, fully-inspected codebase; the one external fact — SQLAlchemy upsert portability — is verified against SQLAlchemy 2.0 docs)

> **No `27-CONTEXT.md` exists** in the phase directory — this phase has NOT been through `/gsd-discuss-phase` yet. There are no locked user decisions to honor. The three roadmap-flagged design decisions (per-table conflict rule, `Product.code` collision rule, tombstone propagation) are resolved below with concrete recommendations that the discuss/plan step must confirm before they become locked. Every recommendation is tagged so the planner can see what still needs user sign-off.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SYNC-02 | Merge append-only ledgers by UUID with idempotent replay — re-syncing/re-uploading the same data twice changes nothing | §"Idempotency mechanism" (portable insert-if-new by UUID PK, no dialect `on_conflict`), §"Merge engine signatures", §Validation "Idempotency dimension" (merge-twice==once) |
| SYNC-03 | After any merge, derived stock quantities and cash balances are recomputed so counts stay correct | §"Derived-state recompute" — reuse existing `ledger.rebuild_stock()` for `Product.quantity`/`Batch.quantity`; cash balance is already a live `SUM` (`finance.compute_balance`), so it needs no stored recompute |
| SYNC-04 | Online sync + offline self-upload use ONE exchange format and ONE server-side merge engine | §"Pure-function boundary" — one `app/services/merge.py` module of pure functions taking a `Session`; Phase 28 (HTTP) and Phase 30 (upload file) are thin callers; §"NDJSON exchange format" is the single wire schema |
| SYNC-05 | Server is source of truth for mutable reference data incl. duplicate `Product.code` on two devices | §"Conflict resolution policy" (per-table table), §"Decision 1/2/3" comparison tables with concrete recommendations |

**Depends on:** Phase 26 (PG portability + append-only parity — the merge engine inherits the dual-dialect trigger guarantee and the `settings.database_url` single-engine surface). No transport yet (Phase 28+).
</phase_requirements>

## Summary

Phase 27 builds the milestone's correctness core as a **pure-function module** — proposed `app/services/merge.py` — with **no HTTP and no file I/O**. It receives an already-parsed batch of records and a `Session`, and it does three things in one transaction: (1) **upsert reference data** by UUID (insert-if-new, server-authoritative on conflict), (2) **append ledger rows** (operations + cash movements) idempotently keyed by their UUID primary key, and (3) **recompute derived state** from the ledger. The codebase was written *for* this moment: ledger rows already have UUID text PKs, a `UNIQUE(device_id, seq)` natural key, integer-cents money, ISO-8601 UTC text timestamps, and — critically — **derived stock is already a pure `SUM(qty_delta)` recompute** (`app/services/ledger.py::rebuild_stock`, `compute_stock`, `compute_batch_stock`) and **cash balance is already a cacheless live `SUM(amount_cents)`** (`app/services/finance.py::compute_balance`). The hard architectural decisions (append-only ledger, no stored cash cache, UUID everywhere) are done.

The single genuinely hard external fact is idempotent-insert portability: SQLAlchemy's `on_conflict_do_nothing()` is **dialect-specific** (you must import it from `sqlalchemy.dialects.postgresql` *or* `sqlalchemy.dialects.sqlite` — there is no portable generic form), and the project forbids SQLite-specific SQL. The portable, project-idiomatic replacement is **pre-select the existing UUIDs (`WHERE id IN (...)`), filter them out, then bulk-insert the remainder** — a set-difference in Python, expressed in portable Core/ORM. Because stock and cash are recomputed as commutative sums over the whole ledger after every merge, **cross-device ordering and causality do not matter for correctness** — this is why the milestone's own requirements call sync "set-union-by-UUID + recompute" and explicitly exclude CRDTs/vector clocks.

The three flagged design decisions resolve cleanly once you notice the sync topology (SYNC-01): **clients push only their two ledgers up and pull server-authoritative reference data down.** Reference rows therefore only travel up as *new* rows their ledger references (FK targets); edits to already-shared rows are owned by the server. That gives **Decision 1 = "insert-if-new; server-wins-on-existing, row-level"**, **Decision 2 = "rename the losing new `Product.code`, keep its UUID so its ledger rows stay valid"**, and **Decision 3 = "`deleted_at` is the tombstone carried inline on the reference record; never resurrect or delete a server row from client input."**

**Primary recommendation:** Create `app/services/merge.py` exposing `parse_exchange(lines) -> ExchangeBatch`, `serialize_exchange(records) -> Iterator[str]`, and `apply_merge(session, batch, *, server_now) -> MergeReport` — pure functions, caller owns the transaction (all-or-nothing). Idempotency is per-UUID insert-if-new via a portable pre-select set-difference (never dialect `on_conflict`, never SQLite `INSERT OR IGNORE`). Reference conflicts resolve server-authoritative row-level; `Product.code` collisions rename the incoming loser. Post-merge, call a non-committing variant of `rebuild_stock()`; cash needs no recompute. Prove it with a `tests/test_merge.py` suite that runs on SQLite and re-runs its idempotency + collision core against PostgreSQL in CI.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Parse/serialize NDJSON exchange format | Pure service (`app/services/merge.py`) | — | Format logic is pure data transformation; no HTTP/file dependency so both transports reuse it (SYNC-04) |
| Idempotent ledger append (by UUID) | Pure service (`merge.apply_merge`) | DB `UNIQUE(device_id, seq)` + UUID PK | Insert-only; the DB unique constraints are the loud backstop; append-only triggers already permit INSERT |
| Reference-data conflict resolution | Pure service (`merge.apply_merge`) | DB `uq_products_code_active` partial index | Policy lives in one place; the partial unique index is the collision backstop (SYNC-05) |
| Derived stock recompute | Existing `ledger.rebuild_stock` / `compute_stock` / `compute_batch_stock` | — | Already pure ledger→cache recompute; reuse, do not reinvent (SYNC-03) |
| Derived cash balance | Existing `finance.compute_balance` | — | Already a live `SUM`, never stored — SYNC-03 is automatic for cash |
| Transaction / all-or-nothing boundary | Caller (Phase 28 endpoint / Phase 30 upload handler) | `merge.apply_merge` (no internal commit) | Keeps the engine pure and lets the caller own atomicity (mirrors `record_operation(commit=False)` idiom) |
| Append-only enforcement (INSERT-only path) | Database triggers (Phase 26, both dialects) | — | The engine never UPDATEs/DELETEs a ledger row, so it never trips the trigger and needs no relaxation (that is Phase 28's `synced_at` cursor) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `json` (stdlib) | 3.13 | NDJSON line encode/decode | NDJSON is one JSON object per line; stdlib `json.dumps`/`json.loads` is the whole requirement. No parser dependency. `[VERIFIED: stdlib]` |
| Python `dataclasses` (stdlib) | 3.13 | `ExchangeBatch`, `MergeReport`, record structs | Pure, typed, zero-dependency value objects for the pure-function signatures. `[VERIFIED: stdlib]` |
| SQLAlchemy | 2.0.* (installed) | Portable ORM for insert-if-new + reference upsert + recompute | Already the ORM; `select(...).where(id.in_(...))` + bulk insert is fully portable. `[VERIFIED: pyproject.toml]` |
| Existing `ledger.py` / `finance.py` recompute | in-repo | `rebuild_stock`, `compute_stock`, `compute_batch_stock`, `compute_balance` | The SYNC-03 recompute already exists and is ledger-derived; reuse. `[VERIFIED: app/services/ledger.py, app/services/finance.py]` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `hashlib` (stdlib) | 3.13 | Optional integrity checksum of the NDJSON body | Only if the plan pulls forward OFF-07's checksum; otherwise defer to Phase 30. `[VERIFIED: stdlib]` |

**No new third-party packages are required for this phase.** Everything is stdlib + the already-installed SQLAlchemy + existing in-repo recompute functions.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| NDJSON (one JSON object per line) | A single JSON array; or msgpack; or CSV | NDJSON streams line-by-line (huge uploads never need full-document parse), is human-diffable/debuggable, and Phase 30's "HTML file opened in a browser" can embed and re-emit it with `JSON.parse` per line. A single JSON array forces whole-document buffering; msgpack/CSV lose readability and self-description. Choose NDJSON. `[ASSUMED — confirm in discuss-phase]` |
| Portable pre-select set-difference insert | `sqlalchemy.dialects.{postgresql,sqlite}.insert(...).on_conflict_do_nothing()` | `on_conflict_do_nothing` is **dialect-specific** (separate imports, no generic form) and SQLite-specific SQL is project-forbidden. Pre-select is portable, one engine, one code path. `[CITED: docs.sqlalchemy.org/en/20/dialects/postgresql.html + /dialects/sqlite.html]` |
| Full recompute via `rebuild_stock` | Incremental recompute (only touched products/batches) | Full recompute is O(ledger) but the data scale is one reseller + a handful of operators; it is simpler, provably idempotent, and `rebuild_stock` already **asserts the invariant** (a free merge self-check). Incremental is premature optimization with a correctness-bug surface. Choose full recompute. |

## Package Legitimacy Audit

> **Not applicable — this phase installs NO external packages.** The engine is stdlib (`json`, `dataclasses`, `hashlib`) + already-installed SQLAlchemy + in-repo recompute functions. No `uv add`, no registry lookup, no slopsquat surface.

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

## Existing Code Surfaces (grounded — cite paths/symbols)

Every claim below was verified by direct read.

| Surface | File / symbol | What it gives the merge engine |
|---------|---------------|--------------------------------|
| Operation ledger row | `app/models.py::Operation` (L333-374) | UUID PK `id` (String(36)); `type`, `product_id` (FK, NOT NULL), `qty_delta` (signed int), `unit_cost_cents`/`unit_price_cents`, `payload` (JSON), `sale_id`/`batch_id`/`author_id` (nullable FKs), `device_id`, `seq`, `created_at`, `created_by`, `synced_at`. `__table_args__ = UniqueConstraint("device_id","seq")` (L337). |
| Cash ledger row | `app/models.py::CashMovement` (L464-503) | UUID PK; `category`, `amount_cents` (signed int), `note`, `sale_id`/`author_id` (nullable FKs), `device_id`, `seq`, `created_at`, `created_by`, `synced_at`. Same `UNIQUE(device_id,seq)` (L476). No cached balance by design. |
| Stock recompute | `app/services/ledger.py::compute_stock` (L139), `compute_batch_stock` (L148), `rebuild_stock` (L171) | `rebuild_stock` recomputes every `Product.quantity` and `Batch.quantity` from `SUM(qty_delta)`, handles the legacy NULL-`batch_id` bucket, and **raises `ValueError` on any invariant mismatch** — then `session.commit()`. This is the SYNC-03 recompute, ready-made. |
| Cash recompute | `app/services/finance.py::compute_balance` (L171) | `SUM(amount_cents)` with no WHERE, no cache. SYNC-03 for cash is automatic (nothing stored to recompute). |
| Single write path (for reference only) | `app/services/ledger.py::record_operation` (L37), `finance.py::record_cash_movement` (L47) | The interactive write path (stamps author via `author_fields()`, computes `next_seq`). The **merge engine does NOT go through these** — it inserts *pre-existing* rows verbatim (preserving origin `id/device_id/seq/author/created_by`), it does not mint new ledger identity. This distinction is central (see Pitfall 1). |
| Reference entities | `Product` (L152, has `deleted_at`, `code`, partial unique index `uq_products_code_active` L158-166), `Warehouse` (L199, has `deleted_at`), `Customer` (L377, **no** `deleted_at`), `Batch` (L241, **no** `deleted_at`, has `quantity` cache), `Dictionary` (L278, unique `code`, **no** `deleted_at`), `CatalogPrice` (L302), `ActiveCatalog` (L220), `Sale` (L438, header), `User` (L506) | Mutable reference/master data. Only `Product` and `Warehouse` are soft-deletable. All have UUID PKs and `updated_at`. |
| Partial unique index | `app/models.py::Product.__table_args__` (L158-166) | `Index("uq_products_code_active", "code", unique=True, sqlite_where=..., postgresql_where="deleted_at IS NULL")` — dual-dialect. This is the DB backstop that will **raise on a cross-device `Product.code` collision** during merge insert (SYNC-05). |
| Interactive duplicate-code check | `app/services/catalog.py::create_product` (L96-101) / `update_product` (L200-209) | `SELECT ... WHERE code == code AND deleted_at IS NULL` then RU error. The merge engine cannot reuse this UX path — it must resolve collisions non-interactively (Decision 2). |
| Append-only DDL | `alembic/versions/0001_*.py`, `0013_*.py` (Phase 26 dialect-branched) | INSERT is permitted; UPDATE/DELETE raise on both dialects. The merge inserts ledger rows only → compatible. |
| Test fixtures | `tests/conftest.py` (`engine`, `session`, `product`, `warehouse`, `batch` fixtures; file-based tmp SQLite + `APPEND_ONLY_TRIGGERS`) | The merge test suite reuses these. `tests/test_pg_parity.py` (Phase 26) is the model for the PG portability slice. |

## Architecture Patterns

### System Architecture Diagram (merge data flow — one call)

```
   Phase 28 HTTP push/pull        Phase 30 self-uploading file
   (token-auth endpoint)          (browser posts embedded NDJSON)
              │                              │
              │   raw NDJSON bytes/text      │   raw NDJSON text
              └──────────────┬───────────────┘
                             ▼
              parse_exchange(lines) -> ExchangeBatch      [PURE, no I/O]
                  · validate format_version               (rejects incompatible)
                  · one dataclass record per line, typed by "kind"
                             │
                             ▼
   caller opens ONE transaction (all-or-nothing)  ── session ──┐
                             ▼                                  │
              apply_merge(session, batch, server_now)  [PURE]   │
                             │                                  │
        ┌────────────────────┼────────────────────┐            │
        ▼                    ▼                    ▼             │
  (1) REFERENCE UPSERTS  (2) LEDGER APPEND   (3) RECOMPUTE      │
   FK-dependency order:  insert-if-new by    rebuild_stock()    │
   warehouses→products   UUID PK (portable   (Product.quantity, │
   →customers→dictionary  pre-select set-    Batch.quantity);   │
   →batches→sales(→users) difference);       cash balance is a  │
   insert-if-new;         operations then     live SUM (nothing │
   server-wins-on-        cash_movements;     stored)           │
   existing (row-level);  verbatim id/        assert invariant  │
   Product.code collision device_id/seq/                        │
   → rename loser         author/created_by                     │
        └────────────────────┼────────────────────┘            │
                             ▼                                  │
                     MergeReport (counts, skips, conflicts)  ───┘
                             │
              caller commits (success) or rolls back (any error)
```

File-to-behavior: the diagram's three stages are one function `apply_merge`; the endpoints/upload-file are the only things touching HTTP/disk.

### Recommended Module Structure
```
app/services/
└── merge.py            # NEW — the whole engine + format (pure functions)
    · FORMAT_VERSION: int = 1
    · RECORD_KINDS = {"header","warehouse","product","customer","dictionary",
                      "batch","sale","operation","cash_movement"}  # user? see OQ-2
    · @dataclass ExchangeRecord / ExchangeBatch / MergeReport / Conflict
    · parse_exchange(lines: Iterable[str]) -> ExchangeBatch
    · serialize_exchange(records: Iterable[ExchangeRecord]) -> Iterator[str]
    · apply_merge(session: Session, batch: ExchangeBatch, *, server_now: str) -> MergeReport
tests/
└── test_merge.py       # NEW — SQLite unit suite (all dimensions below)
   (+ a PG slice, either in test_pg_parity.py or a marked test_merge_pg)
```
No Alembic migration is required — the engine operates entirely on the existing 0001→0017 schema. (An `ingest_batch` table for whole-upload dedup/atomic tracking is a **transport** concern — see Open Question 4 — and belongs to Phase 28/30, not here.)

### Pattern 1: Portable idempotent insert-if-new (the SYNC-02 core)
**What:** Insert only the rows whose UUID is not already present, using a portable set-difference instead of dialect `on_conflict`.
**When:** Every ledger append and every reference insert.
```python
# Source: portable pattern; on_conflict is dialect-specific (see Sources).
def _insert_new(session, model, rows: list[dict]) -> tuple[int, int]:
    """rows are full column dicts keyed incl. 'id'. Returns (inserted, skipped)."""
    if not rows:
        return 0, 0
    incoming_ids = [r["id"] for r in rows]
    existing = set(
        session.scalars(select(model.id).where(model.id.in_(incoming_ids))).all()
    )
    new_rows = [r for r in rows if r["id"] not in existing]
    if new_rows:
        session.execute(insert(model), new_rows)   # generic Core insert — portable
    return len(new_rows), len(rows) - len(new_rows)
```
`incoming_ids` may need chunking (SQLite caps `IN (...)` at ~999 params; PostgreSQL is generous) — chunk at e.g. 500 for portability. Re-running the same batch finds every id in `existing` → `inserted == 0` → true no-op (idempotency proven).

### Pattern 2: Reference upsert — insert-if-new, server-wins-on-existing (Decision 1)
**What:** New UUID → insert verbatim (incl. `deleted_at`). Existing UUID → **do nothing** (server row is authoritative, row-level).
```python
def _upsert_reference(session, model, rows: list[dict]) -> RefResult:
    incoming_ids = [r["id"] for r in rows]
    existing = set(session.scalars(select(model.id).where(model.id.in_(incoming_ids))))
    to_insert = [r for r in rows if r["id"] not in existing]
    skipped = [r for r in rows if r["id"] in existing]   # server wins → discard
    # (Product gets the extra code-collision pass below before insert)
    session.execute(insert(model), to_insert)
    return RefResult(inserted=len(to_insert), server_wins=len(skipped))
```
Row-level (not field-level) resolution is deliberate: it is deterministic, cannot produce a half-merged row, and matches SYNC-05's literal "resolve to the server's version." Clients converge on the next pull (Phase 29).

### Pattern 3: `Product.code` cross-device collision — rename the loser (Decision 2)
**What:** An incoming *new* product (new UUID) whose `code` equals an existing **active** product's `code` (different UUID) cannot be inserted as-is (the partial unique index would raise). Insert it with a mutated `code`, keep its UUID.
```python
def _resolve_code_collisions(session, product_rows: list[dict], conflicts: list) -> None:
    for row in product_rows:               # only rows heading for INSERT
        if row.get("deleted_at") is not None or not row.get("code"):
            continue                        # deleted or code-less → no active-code clash
        clash = session.scalar(
            select(Product.id).where(
                Product.code == row["code"], Product.deleted_at.is_(None)
            )
        )
        if clash and clash != row["id"]:
            original = row["code"]
            row["code"] = _suffix_code(original, row["id"])   # e.g. "12345~a1b2"
            conflicts.append(Conflict(
                kind="product_code", product_id=row["id"],
                original_code=original, resolved_code=row["code"], incumbent_id=clash,
            ))
```
`_suffix_code` appends a short deterministic marker derived from the losing UUID, truncating the base so the result fits `String(20)` (Oriflame codes are short ASCII, A1). The **incumbent** (already on the server) always keeps the clean code; the **incoming** row loses — deterministic because online sync and offline upload each process one source at a time, so there is always a clear incumbent. The loser keeps its UUID, so all its `operations`/`batches` rows (which reference `product_id`, not `code`) stay valid. The collision is returned in `MergeReport.conflicts` for an admin "resolve duplicate codes" surface (Phase 28/29 UI). See Decision 2 table for the alternatives weighed.

### Pattern 4: Post-merge recompute (SYNC-03) — reuse `rebuild_stock`
**What:** After all inserts, recompute cached projections from the ledger.
```python
# rebuild_stock already recomputes Product.quantity + Batch.quantity from
# SUM(qty_delta), handles the legacy NULL-batch bucket, and asserts the
# invariant. It currently ends with session.commit(); the merge wants the
# caller to own the transaction, so extract a `recompute_derived(session)`
# that does the two recompute passes + invariant assert WITHOUT committing,
# and have the existing rebuild_stock() call it then commit (no behavior change
# for existing callers).
recompute_derived(session)     # Product.quantity, Batch.quantity
# cash: nothing to do — compute_balance() is a live SUM (finance.py:171)
```
Full recompute is order-independent (sums are commutative), so multi-device merges are correct regardless of line order — the causality-free property that lets this whole design stay simple.

### Anti-Patterns to Avoid
- **Routing merge inserts through `record_operation`/`record_cash_movement`.** Those mint *new* identity (`new_id()`, `next_seq()`, `author_fields()` from the local contextvar). The merge must preserve the **origin** `id/device_id/seq/author_id/created_by` verbatim (SYNC-02). Insert the rows directly.
- **Dialect `on_conflict_do_nothing` / SQLite `INSERT OR IGNORE`.** Dialect-locked and project-forbidden. Use the Pattern 1 set-difference.
- **Stamping `synced_at` during merge.** The append-only trigger blocks *all* ledger UPDATEs until Phase 28 relaxes it column-scoped. The engine inserts only; the `synced_at` cursor is Phase 28's job. Do not touch it here.
- **Updating an existing reference row from client input** (field-level merge). Server-authoritative = server wins; never overwrite a server row's fields, never resurrect (`deleted_at`→NULL) or delete it based on a client record.
- **Committing inside `apply_merge`.** Breaks all-or-nothing composition (OFF-05) and couples the pure engine to transaction policy. Caller commits.
- **Incremental "only-touched-product" recompute.** Premature; drops the free invariant self-check; introduces a correctness-bug surface.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stock recompute from ledger | A new merge-specific stock summer | `ledger.compute_stock`/`compute_batch_stock`/`rebuild_stock` (extract a non-committing `recompute_derived`) | Already ledger-derived, legacy-bucket-aware, invariant-asserting. `[VERIFIED]` |
| Cash balance after merge | A cash cache + recompute-and-store step | `finance.compute_balance` (live `SUM`) | Cash is deliberately cacheless (D-00b) — SYNC-03 is automatic. `[VERIFIED]` |
| Idempotent insert | Custom "SELECT then INSERT per row" loops, or dialect `on_conflict` | Pattern 1 bulk pre-select set-difference | One portable code path; single round-trip per table; no dialect fork. `[CITED: SQLAlchemy dialect docs]` |
| Duplicate-code detection | Re-implement `catalog.py` UX validation | The `uq_products_code_active` partial index (backstop) + Pattern 3 (policy) | The index already exists on both dialects and *will* raise; the engine only needs the non-interactive resolution. `[VERIFIED]` |
| NDJSON parse/emit | A hand-written tokenizer | stdlib `json.loads`/`json.dumps` per line | NDJSON is literally line-delimited JSON. `[VERIFIED]` |
| Per-device ordering / causality | Vector clocks / Lamport timestamps / CRDT | Nothing — recompute makes order irrelevant | Requirements explicitly exclude CRDTs; sums are commutative. `[VERIFIED: REQUIREMENTS.md Out of Scope]` |

**Key insight:** The correctness of this phase is *recompute-from-ledger*, and that recompute already exists and already self-asserts. The new code is thin: a portable insert-if-new, a reference-upsert policy, a code-collision rename, and a line format. Everything hard was pre-decided by the append-only + no-cache + UUID conventions.

## Design Decisions (roadmap-flagged — RESOLVED with recommendations)

> These three are the milestone's top open design decisions. Each is resolved below with a comparison table and a single recommendation. **All three are `[ASSUMED]` pending discuss/plan confirmation** — they are defensible defaults, not locked user choices.

### Decision 1 — Per-table server-authoritative resolution rule

**Sync topology grounding (SYNC-01):** clients *push their two ledgers up* and *pull server-authoritative reference data down*. So reference rows travel **up only as new rows** (FK targets their ledger needs); edits to already-shared rows are owned by the server (the mobile UI is server-only, so admin edits land on the server directly).

**Recommended policy (all mutable tables): "insert-if-new; server-wins-on-existing, row-level."**

| Table | New UUID (not on server) | Existing UUID (already on server) | Notes |
|-------|--------------------------|-----------------------------------|-------|
| `products` | INSERT verbatim (incl. `deleted_at`), after code-collision pass (Decision 2) | Discard incoming; server row wins | FK target of `operations` |
| `warehouses` | INSERT verbatim (incl. `deleted_at`) | Discard incoming; server wins | FK target of `batches` |
| `customers` | INSERT verbatim (no `deleted_at` — none exists) | Discard incoming; server wins | FK target of `sales` |
| `dictionary` | INSERT verbatim (unique `code` — see note) | Discard incoming; server wins | Helper only; `code` is `unique=True` globally → possible collision (OQ-3) |
| `batches` | INSERT verbatim (no `deleted_at`; `quantity` recomputed post-merge) | Discard incoming; server wins | FK target of `operations.batch_id`; parent `product`/`warehouse` must precede |
| `sales` (header) | INSERT verbatim | Discard incoming; server wins | FK target of `operations.sale_id`/`cash_movements.sale_id`; immutable-by-convention |
| `catalog_prices`, `active_catalog` | INSERT-if-new (helper data) | Server wins | Not in SYNC-05's named list; sync only if the transport carries them (OQ-3) |
| `users` | See Open Question 2 | Server wins | `author_id` FK target; sensitive (password hashes) — provisioning is arguably Phase 28 |

**Why row-level, not field-level:** deterministic, no half-merged rows, matches SYNC-05's wording, and there is no requirement for concurrent field merges at this scale.

**Alternatives considered:**

| Option | Behavior | Verdict |
|--------|----------|---------|
| Row-level server-wins (recommended) | Existing UUID → server row untouched | ✅ Simple, deterministic, requirement-literal |
| Field-level last-write-wins by `updated_at` | Merge non-null fields, newest `updated_at` per field | ❌ Complexity + half-merged rows; needs per-field timestamps the schema lacks |
| Client-wins / true LWW row-level by `updated_at` | Whichever `updated_at` is newer wins | ❌ Contradicts "server is source of truth" (SYNC-05) and the operator's server-authoritative revision |

### Decision 2 — Duplicate `Product.code` created on two devices

Two devices independently create a product with the **same `code`** but **different UUIDs**. Both are new rows; the partial unique index `uq_products_code_active` blocks the second active insert.

| Option | What happens to the loser | Ledger rows referencing the loser | Verdict |
|--------|---------------------------|-----------------------------------|---------|
| (a) Reject the loser | Not inserted | **Orphaned** — their `product_id` FK dangles → those operations can't insert → **data loss** | ❌ Violates "never lose data" |
| (b) **Rename the loser (recommended)** | Inserted with a mutated `code` (deterministic suffix), UUID unchanged | Stay valid (reference `product_id`, not `code`) | ✅ No data loss; admin reconciles later |
| (c) Globally coordinated codes | Prevent collisions by namespacing codes per device | Codes are meaningful Oriflame catalog numbers shown to the operator — can't namespace | ❌ Breaks the domain meaning of `code` |
| (b′) Null the loser's `code` | Inserted with `code=NULL` (NULLs don't collide in a unique index on either dialect), UUID unchanged | Stay valid | ✅ works, but loses the code info the admin needs to reconcile |

**Recommendation: (b) rename the loser.**
- **Tie-break:** the **incumbent** (row already on the server) keeps the clean code; the **incoming** row is the loser. This is unambiguous because each sync/upload processes one source against the server serially — there is always a single incumbent. (If a future batch could contain two *new* same-code products from different devices in one payload, tie-break deterministically on earlier `created_at`, then smaller UUID string.)
- **Rename scheme:** `_suffix_code(code, uuid)` → base truncated to fit `String(20)` + a short deterministic marker from the losing UUID (e.g. `"12345~a1b2"`). Deterministic so re-merging the same payload renames identically (idempotency-safe).
- **Loser's referencing operations stay valid** because they key on `product_id` (the preserved UUID).
- **Surfacing:** the rename is reported in `MergeReport.conflicts`; Phase 28/29 shows an admin "duplicate codes to reconcile" list. No append-only ledger row is written for the rename (products aren't the ledger; a rename is a plain reference-row mutation).
- `(b′)` null-the-code is the fallback if the operator prefers "blank until reconciled" over a marked code — surface both in discuss-phase.

### Decision 3 — Soft-delete tombstone propagation

**Only `Product` and `Warehouse` have `deleted_at`** (verified: `models.py:196,217`). `Customer`, `Dictionary`, `Batch`, `CatalogPrice`, `ActiveCatalog`, `User` have **no** soft-delete. `Batch` deliberately has none — it "leaves the pickers" when `quantity` hits 0 (derived, `models.py:244`).

**Recommendation: the tombstone is `deleted_at` carried inline on the reference record — no separate tombstone record type.**
- A soft-delete is just the reference row with `deleted_at` set; it rides the normal `product`/`warehouse` record.
- **Insert-if-new:** honor the incoming `deleted_at` (a product created-then-deleted offline arrives already soft-deleted; its ledger history is still inserted).
- **Existing UUID:** server-authoritative (Decision 1) — the server's `deleted_at` wins; **never** resurrect (`deleted_at`→NULL) or newly delete a server row from client input.
- **delete-wins vs edit-wins:** moot under server-authoritative — the server's current state (deleted or not) is truth. On the **down**-sync (Phase 29 pull), the server's `deleted_at` propagates to clients so they converge; that pull is Phase 29, but the format defined here already carries `deleted_at` so no format change is needed later.
- **Tables without `deleted_at`:** no tombstone concept; a batch disappearing is derived from `quantity==0`; dictionary/customer rows are never deleted (matches current app behavior).

**Alternative considered:** a dedicated `{"kind":"tombstone","table":...,"id":...}` record type. ❌ Redundant — `deleted_at` already carries the same information inline, and a separate type invites drift between "row says active, tombstone says deleted." Keep it inline.

## NDJSON Exchange Format (the one wire schema — SYNC-04)

**Shape:** one JSON object per line (`\n`-delimited UTF-8). **Per-line typing** via a `"kind"` discriminator, plus **one header line** first for envelope metadata. Both, not either.

```jsonc
// line 1 — header/envelope (exactly one, first)
{"kind":"header","format_version":1,"schema_version":"0017",
 "source_device_id":"<uuid>","generated_at":"2026-07-19T10:00:00+00:00",
 "counts":{"operation":42,"cash_movement":8,"product":3,"batch":3}}

// reference records (emit before ledger so a naive reader is FK-safe; the
// engine also re-orders internally, so order is not load-bearing)
{"kind":"warehouse","id":"...","name":"...","address":null,"created_at":"...","updated_at":"...","deleted_at":null}
{"kind":"product","id":"...","code":"12345","name":"Крем","name_lc":"крем","category":null,
 "cost_cents":50000,"sale_cents":79900,"min_sale_cents":null,"low_stock_threshold":null,
 "stale_days":null,"quantity":0,"created_at":"...","updated_at":"...","deleted_at":null}
{"kind":"customer","id":"...","name":"...","surname":null,"consultant_number":null,"address":null,"search_lc":"...","created_at":"...","updated_at":"..."}
{"kind":"dictionary","id":"...","code":"12345","name":"...","catalogs":["01_26"],"name_lc":"...","created_at":"...","updated_at":"..."}
{"kind":"batch","id":"...","product_id":"...","warehouse_id":"...","expiry":null,"price_cents":79900,"location":null,"comment":null,"name":"...","quantity":0,"is_legacy":0,"created_at":"...","updated_at":"..."}
{"kind":"sale","id":"...","customer_id":null,"created_at":"...","created_by":"operator","author_id":"...","device_id":"..."}

// ledger records
{"kind":"operation","id":"...","type":"receipt","product_id":"...","qty_delta":10,
 "unit_cost_cents":50000,"unit_price_cents":null,"payload":{"reason_code":null},
 "sale_id":null,"batch_id":"...","author_id":"...","device_id":"...","seq":17,
 "created_at":"...","created_by":"operator","synced_at":null}
{"kind":"cash_movement","id":"...","category":"sale","amount_cents":79900,"note":null,
 "sale_id":"...","author_id":"...","device_id":"...","seq":9,"created_at":"...","created_by":"operator","synced_at":null}
```

**Rules:**
- **Verbatim carriage:** every ledger record carries origin `id`, `device_id`, `seq`, `author_id`, `created_by`, `created_at` unchanged (SYNC-02). Money stays integer cents; timestamps stay ISO-8601 UTC text; `payload`/`catalogs` are nested JSON. No re-minting.
- **`format_version`** (integer, in the header) is what the engine understands; a mismatch is rejected by `parse_exchange` (feeds OFF-07's schema-version check in Phase 30). **`schema_version`** = the current Alembic head revision (`"0017"`), for the OFF-07 compatibility gate.
- **`kind`** per line lets the parser dispatch to the right dataclass/table without whole-document context (streamable).
- **Ordering** in the file is reference-before-ledger as a courtesy, but `apply_merge` buffers by kind and applies in FK order regardless, so a shuffled file still merges correctly (tested — see Validation).
- **`synced_at`** is emitted as `null` from clients; the server never trusts or reads it from the wire (it is server-owned, Phase 28).
- **`quantity`** on `product`/`batch` is carried but **not trusted** — it is recomputed post-merge (Out-of-Scope: "syncing derived stock/batch quantities … risks corruption"). Consider emitting it as `0`/omitting to make the "never trust a synced cache" rule explicit; decide in discuss-phase.

## Common Pitfalls

### Pitfall 1: Merging through the interactive write path (re-minting identity)
**What goes wrong:** Using `record_operation()`/`record_cash_movement()` to insert synced rows assigns a **new** `id`/`seq`/`author` from the local device, destroying idempotency and origin attribution.
**Why:** those functions call `new_id()`, `next_seq(local_device)`, `author_fields()` (contextvar).
**Avoid:** the merge inserts pre-formed rows verbatim (Pattern 1), never via the write path.
**Warning sign:** merged operations show the *server's* device_id or a fresh seq; re-merge duplicates rows.

### Pitfall 2: Using dialect `on_conflict` (portability break)
**What goes wrong:** `sqlite.insert().on_conflict_do_nothing()` compiles only on SQLite; the same code errors on PostgreSQL (and vice-versa), and it violates the "no SQLite-specific SQL" rule.
**Avoid:** portable pre-select set-difference (Pattern 1).
**Warning sign:** an `import` from `sqlalchemy.dialects.sqlite`/`.postgresql` inside `merge.py`.

### Pitfall 3: `IN (...)` parameter limit on SQLite
**What goes wrong:** a large batch's `WHERE id IN (<thousands>)` exceeds SQLite's ~999 bound-parameter limit → `OperationalError`.
**Avoid:** chunk `incoming_ids` (e.g. 500/query) in `_insert_new`/`_upsert_reference`.
**Warning sign:** "too many SQL variables" on SQLite with big uploads; passes on PostgreSQL (hides in dev).

### Pitfall 4: FK-ordering — ledger inserted before its parents
**What goes wrong:** inserting an `operation` before its `product`/`batch`/`sale` exists → FK violation (PostgreSQL enforces FKs always; SQLite enforces them because `PRAGMA foreign_keys=ON`, `db.py:71`).
**Avoid:** `apply_merge` applies reference records in dependency order (warehouses→products→customers→dictionary→batches→sales→[users]) **before** operations→cash_movements, regardless of file order.
**Warning sign:** IntegrityError naming an FK; intermittent, depends on line order.

### Pitfall 5: Committing inside the engine (breaks all-or-nothing)
**What goes wrong:** an internal `session.commit()` half-applies a batch when a later record fails → OFF-05 "no half-applied batch" broken.
**Avoid:** `apply_merge` never commits; the caller wraps the whole call in one transaction and commits once (or rolls back).
**Warning sign:** partial rows survive after a mid-batch exception.

### Pitfall 6: `rebuild_stock` invariant assertion aborting a legitimate merge
**What goes wrong:** `rebuild_stock` raises `ValueError` on a stock-invariant mismatch; if a synced ledger is internally inconsistent (e.g. a batch's parent product missing), the merge aborts.
**Why:** it is a strict self-check (a feature — it catches corrupt input).
**Avoid:** ensure reference/FK completeness before recompute; treat the raise as "reject this batch" (all-or-nothing), and surface a clear error. Consider catching it and returning a failed `MergeReport` rather than propagating raw.
**Warning sign:** merges of otherwise-valid data fail at recompute because a referenced parent wasn't in the batch (couples to Open Question 1).

### Pitfall 7: Re-running with a mutated in-place batch (code-collision non-determinism)
**What goes wrong:** if `_resolve_code_collisions` renamed using a random/time component, a second merge of the same file would rename differently, so "merge-twice" would not be a no-op.
**Avoid:** derive the suffix deterministically from the losing UUID only.
**Warning sign:** idempotency test flakes on the collision case.

## Code Examples

### Pure-function signatures (the SYNC-04 boundary)
```python
# app/services/merge.py  (proposed)
from dataclasses import dataclass, field
from collections.abc import Iterable, Iterator
from sqlalchemy import select, insert
from sqlalchemy.orm import Session

FORMAT_VERSION = 1

@dataclass(frozen=True)
class ExchangeRecord:
    kind: str
    data: dict

@dataclass
class ExchangeBatch:
    format_version: int
    schema_version: str
    source_device_id: str | None
    records: list[ExchangeRecord] = field(default_factory=list)

@dataclass
class Conflict:
    kind: str; product_id: str; original_code: str; resolved_code: str; incumbent_id: str

@dataclass
class MergeReport:
    operations_inserted: int = 0
    operations_skipped: int = 0
    cash_inserted: int = 0
    cash_skipped: int = 0
    reference_inserted: dict[str, int] = field(default_factory=dict)
    reference_server_wins: dict[str, int] = field(default_factory=dict)
    conflicts: list[Conflict] = field(default_factory=list)

def parse_exchange(lines: Iterable[str]) -> ExchangeBatch:
    """Pure: one JSON object per line; first line is the header. Raises
    ValueError on malformed JSON or an unsupported format_version."""

def serialize_exchange(records: Iterable[ExchangeRecord]) -> Iterator[str]:
    """Pure: yields NDJSON lines (header first). Used by the client push /
    the offline export file (Phase 29/30)."""

def apply_merge(session: Session, batch: ExchangeBatch, *, server_now: str) -> MergeReport:
    """Pure w.r.t. HTTP/disk. Stages all reference upserts (FK order),
    then idempotent ledger appends, then recompute_derived(session).
    Does NOT commit — the caller owns the transaction (all-or-nothing)."""
```

### Caller (Phase 28/30 — thin) — atomic all-or-nothing
```python
# Illustrative — NOT built this phase; shows the boundary.
def ingest(session: Session, raw_text: str) -> MergeReport:
    batch = merge.parse_exchange(raw_text.splitlines())      # may raise -> reject
    try:
        report = merge.apply_merge(session, batch, server_now=utcnow_iso())
        session.commit()                                     # all-or-nothing
        return report
    except Exception:
        session.rollback()                                   # no half-applied batch
        raise
```

### Idempotency check (the SYNC-02 proof, test shape)
```python
def test_merge_twice_equals_once(session, batch_ndjson):
    b = merge.parse_exchange(batch_ndjson)
    r1 = merge.apply_merge(session, b, server_now=NOW); session.commit()
    snap = _snapshot(session)                       # rows + stock + balance
    r2 = merge.apply_merge(session, merge.parse_exchange(batch_ndjson), server_now=NOW)
    session.commit()
    assert r2.operations_inserted == 0 and r2.cash_inserted == 0
    assert _snapshot(session) == snap               # nothing changed
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Multi-master conflict resolution via CRDTs/vector clocks | Set-union-by-UUID + full recompute (server-authoritative reference) | This milestone's design (2026-07-18) | No CRDT infra; correctness is a commutative sum, order-free |
| `INSERT OR IGNORE` (SQLite) / `ON CONFLICT` (PG) for dedup | Portable pre-select set-difference | Chosen for one-engine portability | Single code path across both dialects; no dialect fork |
| Stored/synced stock & cash caches | Recompute-from-ledger after every merge; cash always live `SUM` | Established since v1.0 (append-only) | Caches can't be corrupted by a bad sync — they're derived |

**Deprecated/outdated for this project:** dialect `on_conflict_do_nothing` (portability), any cache-shipping in the exchange format (explicitly out of scope).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | NDJSON (per-line `kind` + one header line) is the right exchange format | NDJSON format | Low — well-suited to streaming + Phase 30's HTML file; reversible if discuss prefers a single JSON doc |
| A2 | Decision 1: insert-if-new + server-wins-on-existing, **row-level** | Decision 1 | Medium — if the operator wants client reference edits to propagate up, the policy inverts; grounded in SYNC-01's push/pull split |
| A3 | Decision 2: **rename** the losing `Product.code`, keep UUID | Decision 2 | Medium — alternative is null-the-code; either preserves ledger validity, differs only in admin UX |
| A4 | Decision 2 tie-break: incumbent keeps code (single-source-at-a-time) | Decision 2 | Low — deterministic given serial sync/upload; add created_at/UUID tie-break for same-batch duplicates |
| A5 | Decision 3: tombstone = inline `deleted_at`, no separate record type; only Product/Warehouse | Decision 3 | Low — verified only those two have `deleted_at` |
| A6 | `users` are provisioned by the transport (Phase 28), not this engine; `author_id` targets must exist or be nulled | Open Q 2 | Medium — an absent user FK aborts an operation insert; needs a decision before ledger inserts can carry `author_id` |
| A7 | Full recompute (`rebuild_stock`) every merge, not incremental | Pattern 4 | Low — correct + self-asserting; only a perf question at much larger scale |
| A8 | No Alembic migration needed (engine on existing schema; `ingest_batch` deferred to Phase 28/30) | Module structure / Open Q 4 | Low-Medium — if the plan pulls forward whole-upload dedup/all-or-nothing tracking, a migration appears |
| A9 | Product/Batch `quantity` carried in the wire is ignored (recomputed) | NDJSON format | Low — matches out-of-scope "never sync caches"; may drop the field entirely |

## Open Questions

1. **FK completeness of a push batch (referenced parents must be present).**
   - What we know: `operations.product_id` is NOT NULL; `batch_id`/`sale_id` nullable; every FK is enforced on both dialects. A push must include every reference row its ledger references that the server doesn't already have.
   - What's unclear: does the client always include the full set of referenced products/batches/sales, or does the server pre-seed some? A missing parent aborts the merge (Pitfall 4/6).
   - Recommendation: define the push to include all reference rows referenced by the pushed ledger (insert-if-new makes re-sending harmless). Confirm the client-side selection rule in Phase 29; for Phase 27, test both "complete batch" (succeeds) and "missing parent" (rejected all-or-nothing).

2. **`author_id` → `users` FK across devices (user provisioning).**
   - What we know: `operations.author_id`/`cash_movements.author_id`/`sales.author_id` reference `users.id` (nullable). `created_by` already carries a frozen display-name snapshot, so display attribution survives even if the user row is absent.
   - What's unclear: whether users sync as reference data (insert-if-new, but that ships **password hashes** — a security choice) or whether the engine **nulls `author_id`** when the target user is absent on the server (attribution then relies on `created_by`).
   - Recommendation: for the isolated engine, default to **null `author_id` if the target user is absent** (preserves the insert, keeps display attribution via `created_by`), and flag user provisioning as a Phase 28 decision. Surface the "sync user rows incl. hashes" option explicitly in discuss-phase.

3. **Global-unique reference codes: `dictionary.code` (and `catalog_prices` uniqueness).**
   - What we know: `Dictionary.code` is `unique=True` **globally** (no partial predicate). Two devices creating the same dictionary `code` under different UUIDs collide on insert; `catalog_prices` has `UNIQUE(year,number,code)`.
   - What's unclear: whether dictionary/catalog_prices even travel in the exchange (they are helper data, not in SYNC-05's named list) and, if so, the collision rule.
   - Recommendation: exclude `dictionary`/`catalog_prices`/`active_catalog` from the client push by default (they are admin-managed, flow down only); if included, apply the same insert-if-new + on-unique-collision **skip-and-report** as Decision 2 (there is no ledger FK to a dictionary row, so a skipped duplicate loses nothing). Confirm scope in discuss-phase.

4. **`ingest_batch` / whole-upload atomic tracking (MEMORY note).**
   - What we know: project memory records "UUID merge via separate `ingest_batch`." Per-row UUID idempotency (this phase) already makes "upload the same file twice = no-op." A separate `ingest_batch` table would add whole-upload dedup + an audit of each ingest.
   - What's unclear: whether that table is needed for OFF-05 (all-or-nothing) — which the single-transaction design already provides — or is purely an audit/observability feature.
   - Recommendation: keep it **out of Phase 27** (transport concern); the pure engine gives all-or-nothing via the caller's transaction. Revisit in Phase 28/30. Note it so the planner doesn't accidentally couple the engine to a batch table.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib `json`/`dataclasses`/`hashlib` | Format + engine | ✓ | 3.13 | — |
| SQLAlchemy 2.0 | Portable insert/select/recompute | ✓ | 2.0.* | — |
| SQLite (dev/test + client) | Unit test suite | ✓ | bundled | — |
| PostgreSQL 17 (CI service) | Portability slice of the merge tests | ✓ in CI (Phase 26 `services: postgres`) / ✗ locally on Windows | 17 | Local `docker run postgres:17` or CI-only |
| In-repo `ledger.rebuild_stock` / `finance.compute_balance` | SYNC-03 recompute | ✓ | in-repo | — |

**Missing dependencies with no fallback:** none — this phase adds no external dependency.
**Missing dependencies with fallback:** local PostgreSQL on the Windows dev host — fall back to the CI `pg-parity` job (Phase 26) extended with the merge portability tests.

## Validation Architecture

> `nyquist_validation` is enabled (`.planning/config.json` → `workflow.nyquist_validation: true`). This phase's correctness *is* its deliverable, so validation is central and drives the plan's wave structure.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.* `[VERIFIED: pyproject.toml, existing suite]` |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["."]`) |
| Quick run command | `uv run pytest tests/test_merge.py -x` (new file) |
| Full suite command | `uv run pytest` |
| PG portability slice | `DATABASE_URL=postgresql+psycopg://… uv run pytest tests/test_merge_pg.py -x` (or extend `tests/test_pg_parity.py`), run in the existing CI `pg-parity` job |
| Shared fixtures | reuse `tests/conftest.py` (`engine`, `session`, `product`, `warehouse`, `batch`) |

### Phase Requirements → Test Map
| Req | Behavior | Test Type | Automated Command | File |
|-----|----------|-----------|-------------------|------|
| SYNC-02 | Merge-twice == once (0 new rows, identical stock/cash on 2nd apply) | unit | `pytest tests/test_merge.py::test_merge_twice_equals_once -x` | ❌ Wave 0 |
| SYNC-02 | Verbatim insert preserves `id`/`device_id`/`seq`/`author_id`/`created_by` | unit | `…::test_ledger_row_inserted_verbatim -x` | ❌ Wave 0 |
| SYNC-02 | `UNIQUE(device_id,seq)` + UUID PK both act as idempotency backstops | unit | `…::test_duplicate_uuid_skipped -x` | ❌ Wave 0 |
| SYNC-02 | Order-independence: shuffled NDJSON lines → identical result | unit | `…::test_shuffled_lines_same_result -x` | ❌ Wave 0 |
| SYNC-03 | After merge, `Product.quantity`==`compute_stock`, `Batch.quantity`==`compute_batch_stock` | unit | `…::test_stock_recomputed_after_merge -x` | ❌ Wave 0 |
| SYNC-03 | After merge, `compute_balance` == expected signed sum | unit | `…::test_cash_balance_after_merge -x` | ❌ Wave 0 |
| SYNC-03 | Multi-device merge → stock = sum of both devices' ledgers | unit | `…::test_two_device_stock_union -x` | ❌ Wave 0 |
| SYNC-04 | One `apply_merge` handles both ledgers in one transaction; parse↔serialize round-trip is identity | unit | `…::test_round_trip` / `…::test_single_engine_both_ledgers -x` | ❌ Wave 0 |
| SYNC-04 | Atomic all-or-nothing: bad record mid-batch → full rollback, DB unchanged | unit | `…::test_bad_record_rolls_back -x` | ❌ Wave 0 |
| SYNC-04 | `parse_exchange` rejects unsupported `format_version` / malformed line | unit | `…::test_format_version_rejected` / `…::test_malformed_line_rejected -x` | ❌ Wave 0 |
| SYNC-05 | Existing reference UUID → server row wins (incoming edit discarded) | unit | `…::test_server_wins_on_existing_reference -x` | ❌ Wave 0 |
| SYNC-05 | Duplicate `Product.code` (diff UUID) → loser renamed, keeps UUID, its ops valid, conflict reported | unit | `…::test_product_code_collision_renamed -x` | ❌ Wave 0 |
| SYNC-05 | Incoming tombstone: new product with `deleted_at` inserts soft-deleted; existing server `deleted_at` untouched by client | unit | `…::test_tombstone_inline -x` | ❌ Wave 0 |
| SYNC-02/05 | FK ordering: reference rows applied before ledger regardless of line order; missing parent → rejected all-or-nothing | unit | `…::test_fk_ordering` / `…::test_missing_parent_rejected -x` | ❌ Wave 0 |
| Portability | Idempotency + code-collision core pass on PostgreSQL (portable insert, no dialect `on_conflict`) | integration (PG) | `…test_merge_pg.py -x` (CI `pg-parity`) | ❌ Wave 0 |
| Regression | Existing 982-test SQLite suite stays green (recompute extraction is behavior-preserving) | full | `uv run pytest` | ✅ exists |

### Test Dimensions (how each guarantee is proven)
- **Idempotency:** apply → snapshot(rows+stock+balance) → apply same → assert 0 inserts and byte-identical snapshot (merge-twice==once).
- **Verbatim replay:** assert the inserted `Operation`/`CashMovement` equals origin `id/device_id/seq/author_id/created_by/created_at`.
- **Derived-state correctness:** post-merge, cross-check every cache against its ledger recompute (`compute_stock`/`compute_batch_stock`/`compute_balance`); include a two-device union to prove order-free summation.
- **Conflict resolution:** server-wins-on-existing; `Product.code` collision rename (incumbent keeps code, loser keeps UUID + renamed code + reported); tombstone inline.
- **Atomicity:** a poisoned record mid-batch leaves the DB exactly as before (caller rollback).
- **Format:** parse↔serialize round-trip identity; version + malformed rejection.
- **Portability:** re-run the idempotency + collision core on PostgreSQL in CI to prove the pre-select set-difference (not dialect `on_conflict`) holds on both engines.

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_merge.py tests/test_ledger.py tests/test_finance.py -x` + `ruff check` (recompute + write-path regressions caught immediately).
- **Per wave merge:** full `uv run pytest` on SQLite; the PG merge slice on CI (or local docker).
- **Phase gate:** full SQLite suite green + the CI `pg-parity` job green including the new PG merge tests.

### Wave 0 Gaps
- [ ] `app/services/merge.py` — the engine (does not exist).
- [ ] `tests/test_merge.py` — all SQLite dimensions above.
- [ ] `tests/test_merge_pg.py` (or extend `tests/test_pg_parity.py`) — PG idempotency + collision slice; skipped unless `DATABASE_URL` is PostgreSQL.
- [ ] Extract `recompute_derived(session)` (non-committing) from `ledger.rebuild_stock` so the merge is one transaction (keep `rebuild_stock` behavior identical for existing callers).
- [ ] NDJSON fixtures/factory (a helper that builds valid exchange batches from ORM objects) for the test suite.
- [ ] CI: add the merge PG test invocation to `.github/workflows/ci.yml`'s `pg-parity` job.

*Existing infrastructure (`conftest.py` fixtures, `test_ledger.py`, `test_finance.py`, `test_pg_parity.py`) covers the recompute and portability scaffolding — the new work is the engine + its dimension tests.*

## Security Domain

> `security_enforcement: true`, ASVS level 1. This phase adds no auth/session surface (Phase 25 owns that; Phase 28 owns the sync token). The security-relevant surfaces are **data integrity** (append-only ledger, all-or-nothing), **untrusted-input validation** (the NDJSON payload is attacker-influenced data), and **injection avoidance**.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Sync-endpoint auth is Phase 28 (per-device token, SYNC-09) |
| V3 Session Management | no | Unchanged |
| V4 Access Control | partial | The engine is pure; the *caller* (Phase 28) must gate ingest behind auth/role. Note it for the planner. |
| V5 Input Validation | **yes** | `parse_exchange` validates `format_version`, `kind`, required fields, and types before any DB touch; unknown `kind` rejected; money must be int cents; never `eval`/`f-string` payload into SQL |
| V6 Cryptography | no (this phase) | Integrity checksum/signature is OFF-07 (Phase 30); `hashlib` optional if pulled forward |
| V10 Data Integrity | **yes** | Append-only triggers (INSERT-only merge, both dialects); all-or-nothing transaction; recompute-from-ledger self-check (`rebuild_stock` invariant assert) |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious/oversized NDJSON (parser DoS, type confusion) | Tampering / DoS | Strict per-line `json.loads` + schema validation in `parse_exchange`; reject unknown `kind`/version; (size caps at the transport, Phase 28/30) |
| Forged ledger rows to inflate stock/cash | Tampering / Repudiation | Merge inserts verbatim but recompute is from the ledger; append-only triggers block post-hoc edits; auth/attribution at the transport (author already frozen in `created_by`) |
| Client overwriting server reference data (e.g. re-pricing a product) | Tampering | Server-authoritative row-level resolution — existing rows are never mutated from client input (Decision 1) |
| Cross-device `Product.code` hijack (duplicate code to shadow a product) | Spoofing / Tampering | Incumbent keeps the code; incoming loser renamed + reported (Decision 2) — cannot displace the server's product |
| SQL injection via record fields | Tampering | Portable ORM/Core with **bound parameters only**; never string-interpolate payload into SQL (matches existing `history_view`/catalog discipline) |
| Half-applied upload (interrupted merge) | Integrity | Caller-owned single transaction; `apply_merge` never commits mid-batch (OFF-05) |

## Sources

### Primary (HIGH confidence)
- Repo files (VERIFIED by direct read): `app/models.py`, `app/services/ledger.py`, `app/services/operations.py`, `app/services/finance.py`, `app/services/catalog.py`, `app/config.py`, `app/db.py`, `tests/conftest.py`, `tests/test_pg_parity.py`, `alembic/versions/` (0001…0017), `.planning/config.json`.
- Phase 26 artifacts (VERIFIED): `26-RESEARCH.md`, `26-PATTERNS.md`, `26-01/02/03-SUMMARY.md` — dual-dialect append-only triggers, `settings.database_url` single engine, PG-parity CI.
- Phase 25 `25-RESEARCH.md` (VERIFIED): single write path, `author_id`/`created_by` attribution model, per-install `device_id`.
- `.planning/REQUIREMENTS.md` (SYNC-01..05, OFF-05, Out-of-Scope: "set-union-by-UUID + recompute", "no CRDTs", "never sync caches"), `.planning/ROADMAP.md` (Phase 27 brief + open-decision flag), `.planning/STATE.md`, `CLAUDE.md` (portability, integer-cents, UUID, append-only rules).

### Secondary (MEDIUM confidence, tool-verified)
- SQLAlchemy 2.0 docs — `on_conflict_do_nothing()` is dialect-specific (separate `sqlalchemy.dialects.postgresql` / `sqlalchemy.dialects.sqlite` imports; no generic portable form). `[CITED: docs.sqlalchemy.org/en/20/dialects/postgresql.html, /dialects/sqlite.html; corroborated by SQLAlchemy discussion #9675, #7007]` — the load-bearing basis for the portable pre-select set-difference.

### Tertiary (LOW confidence / to confirm in discuss-phase)
- NDJSON choice, per-table conflict policy, code-collision rename scheme, tombstone-inline, user-provisioning fallback — defensible defaults grounded in the sync topology, but not yet operator-confirmed (see Assumptions Log A1–A9 and Open Questions).

## Metadata

**Confidence breakdown:**
- Existing-code grounding (recompute, models, ledger, constraints): HIGH — every symbol read directly with line numbers.
- Idempotency mechanism / portability: HIGH — SQLAlchemy dialect-specificity verified against official docs; pre-select pattern is standard.
- Conflict policy / format design: MEDIUM — internally consistent and requirement-grounded, but the three flagged decisions await discuss-phase confirmation.
- User-provisioning & FK-completeness edges: MEDIUM — real cross-phase dependencies flagged as Open Questions 1–2.

**Research date:** 2026-07-19
**Valid until:** 2026-08-19 (stable — pure in-repo engine; only re-check if the schema or the append-only trigger contract changes before Phase 28)
