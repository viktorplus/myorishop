# Phase 27: Shared Idempotent Merge Core - Pattern Map

**Mapped:** 2026-07-19
**Files analyzed:** 3 new/modified (1 new service, 1 new test, 1 modified service) + 2 optional PG/CI touch-points
**Analogs found:** 3 / 3 (every new file has a strong in-repo analog)

> No `27-CONTEXT.md` exists — file list extracted from `27-RESEARCH.md` (§"Recommended Module Structure", §"Wave 0 Gaps", §"Pure-function signatures"). All analogs below were verified by direct read with line numbers.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/merge.py` (NEW) | service (pure-function engine) | transform + batch (set-union-by-UUID, portable insert-if-new, recompute) | `app/services/ledger.py` + `app/services/finance.py` | role-match (service, single-write-path idiom); no existing *bulk/merge* service — engine shape is new |
| `app/services/ledger.py` (MODIFIED — extract non-committing `recompute_derived(session)`) | service (recompute) | batch/transform (ledger→cache SUM recompute) | itself: `rebuild_stock` (L171-206) | exact (behavior-preserving extraction) |
| `tests/test_merge.py` (NEW — SQLite dimensions) | test | request-response / transform assertions | `tests/test_pg_parity.py` + existing `tests/conftest.py` fixtures | role-match (test module + shared fixtures) |
| `tests/test_merge_pg.py` (NEW, or extend `tests/test_pg_parity.py`) | test (PG portability slice) | batch/transform | `tests/test_pg_parity.py` | exact (skipif-on-dialect harness) |
| `.github/workflows/ci.yml` `pg-parity` job (MODIFIED — add merge PG invocation) | config (CI) | — | existing `pg-parity` job (Phase 26) | role-match |

**No Alembic migration** (RESEARCH A8 / Open Q4): the engine runs on the existing 0001→0017 schema. Do not create one; `ingest_batch` is a Phase 28/30 transport concern.

## Shared Conventions (apply to every new symbol in `merge.py`)

Grounded in `app/services/ledger.py`, `app/services/finance.py`, `app/core.py`, `CLAUDE.md`:

- **Imports:** `from sqlalchemy import func, select` (+ `insert` for the bulk path); `from sqlalchemy.orm import Session`. Models from `app.models`; helpers from `app.core` (`new_id`, `utcnow_iso`). See `ledger.py:8-13`, `finance.py:8-16`.
- **`Session` is the first positional arg**, business args keyword-only after `*` — `record_operation(session, *, type_, ...)` (`ledger.py:37-49`), `record_cash_movement(session, *, category, ...)` (`finance.py:47-55`). `apply_merge(session, batch, *, server_now)` follows this.
- **`commit` is the caller's job for staged work.** Existing pattern: `commit: bool = True` flag, and the multi-write caller passes `commit=False` then commits once (`ledger.py:48,134-135`; `finance.py:54,88-89`, WR-03). The merge engine goes further — `apply_merge` **never** commits (RESEARCH Pitfall 5). Model the all-or-nothing caller on `finance.record_manual_movement`'s `try/except → session.rollback()` (`finance.py:156-166`).
- **Money is signed integer cents only** — never Float/Numeric (`models.py:483`, `CLAUDE.md`). Carry `*_cents` verbatim.
- **Timestamps are ISO-8601 UTC text** via `utcnow_iso()` (`core.py:20-25`); `server_now` is such a string. UUID PKs are 36-char strings via `new_id()` (`core.py:15-17`).
- **Portable ORM/Core only** — no `sqlalchemy.dialects.*` import, no raw SQLite SQL (`CLAUDE.md` "What NOT to Use"; `finance.cash_history_view` docstring L197 "Portable ORM only"). This is the load-bearing rule for Pattern 1 below.
- **RU error strings, no HTML**, defined as module constants when user-facing (`finance.py:25-28`). Merge-internal `ValueError`s use English like `ledger.py:76,82` (`f"unknown product: {product_id!r}"`).

## Pattern Assignments

### `app/services/merge.py` (service, transform+batch) — NEW

**Analogs:** `app/services/ledger.py` (single-write-path service shape, recompute reuse), `app/services/finance.py` (keyword-only signature + rollback caller), `app/core.py` (id/time helpers).

**Module docstring + imports pattern** — copy the header style of `ledger.py:1-13` / `finance.py:1-16` (docstring states the single responsibility + the governing decisions, then stdlib/SQLA/app imports grouped):
```python
from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.core import new_id, utcnow_iso
from app.models import Batch, CashMovement, Customer, Dictionary, Operation, Product, Sale, Warehouse
```

**Pure-function signatures** — RESEARCH §"Pure-function signatures" (L384-431) is the authoritative shape; dataclasses `ExchangeRecord/ExchangeBatch/Conflict/MergeReport`, `parse_exchange`, `serialize_exchange`, `apply_merge(session, batch, *, server_now)`. Keyword-only `*` mirrors `ledger.record_operation` (`ledger.py:37-49`).

**Pattern 1 — portable insert-if-new (SYNC-02 core).** No analog for the *bulk* insert exists in-repo (all existing writes are one-row `session.add`), so this is genuinely new code — but it must use the same portable `select(...).where(col.in_(...))` idiom already pervasive here. The existing `select(func.max(...))`/`select(func.coalesce(func.sum(...)))` calls (`ledger.py:31-34,141-145,156-168`; `finance.py:41-44,177`) are the portability precedent. RESEARCH Pattern 1 (L153-168):
```python
def _insert_new(session, model, rows: list[dict]) -> tuple[int, int]:
    if not rows:
        return 0, 0
    incoming_ids = [r["id"] for r in rows]
    existing = set(session.scalars(select(model.id).where(model.id.in_(incoming_ids))).all())
    new_rows = [r for r in rows if r["id"] not in existing]
    if new_rows:
        session.execute(insert(model), new_rows)   # generic Core insert — portable
    return len(new_rows), len(rows) - len(new_rows)
```
Chunk `incoming_ids` at ~500 for SQLite's ~999 param cap (RESEARCH Pitfall 3). **Never** import `sqlalchemy.dialects.*` (RESEARCH Pitfall 2; `CLAUDE.md`).

**Verbatim ledger append (SYNC-02) — do NOT go through `record_operation`.** Contrast is load-bearing: `ledger.record_operation` (`ledger.py:110-125`) mints identity via `new_id()`, `next_seq()`, `author_fields()`. The merge inserts pre-formed rows preserving origin `id/device_id/seq/author_id/created_by/created_at` (RESEARCH Anti-Patterns L222, Pitfall 1). Read the `Operation` column set at `models.py:339-374` and `CashMovement` at `models.py:478-503` to build the row dicts; do NOT set `synced_at` (RESEARCH L224).

**Pattern 2 — reference upsert, server-wins-on-existing (SYNC-05 / Decision 1).** RESEARCH Pattern 2 (L170-181): new UUID → insert verbatim; existing UUID → discard. Same set-difference as Pattern 1. FK-dependency insert order (RESEARCH Pitfall 4, L362): warehouses→products→customers→dictionary→batches→sales→operations→cash_movements. `PRAGMA foreign_keys=ON` is active (`db.py:71`, per RESEARCH) so order is enforced on SQLite too.

**Pattern 3 — `Product.code` collision rename (SYNC-05 / Decision 2).** The interactive duplicate-code check to mirror (but NOT reuse — it raises an RU UX error) is `catalog.create_product` (`catalog.py:96-101`): `select(Product).where(Product.code == code, Product.deleted_at.is_(None))`. The merge does the same probe non-interactively and renames the incoming loser deterministically from its UUID, keeping the UUID so its ledger rows stay valid. RESEARCH Pattern 3 (L187-203). Backstop = partial unique index `uq_products_code_active` (`models.py:158-166`). `code` is `String(20)` (`models.py:169`) — the suffix must fit.

**Pattern 4 — post-merge recompute (SYNC-03).** Call the new `recompute_derived(session)` (see below). Cash needs nothing — `finance.compute_balance` is a live SUM (`finance.py:171-177`). RESEARCH Pattern 4 (L206-218). Catch `rebuild_stock`'s `ValueError` invariant raise and surface as a failed batch (RESEARCH Pitfall 6).

---

### `app/services/ledger.py` (service, recompute) — MODIFIED

**Analog:** itself — `rebuild_stock` (`ledger.py:171-206`).

**Extraction (behavior-preserving).** `rebuild_stock` currently does two recompute passes + invariant assert, then `session.commit()` (`ledger.py:206`). Extract the passes+assert (L180-204) into `recompute_derived(session)` that does **not** commit; have `rebuild_stock` call it then commit — zero behavior change for existing callers. This is the RESEARCH Wave-0 gap (L570) enabling one-transaction merge. Reuses `compute_stock` (L139-145) and `compute_batch_stock` (L148-168) unchanged.

---

### `tests/test_merge.py` (test) — NEW

**Analogs:** `tests/conftest.py` (fixtures), `tests/test_pg_parity.py` (harness style).

**Reuse existing fixtures** (`conftest.py`): `session` (L35-39, file-based tmp SQLite + append-only triggers via the `engine` fixture L22-32), `product` (L42-53), `warehouse` (L56-62), `batch` (L65-76), `customer` (L117-129). Do NOT build a new engine.

**Direct-INSERT-with-explicit-fields precedent** for building verbatim ledger rows in fixtures: `past_sale` (`conftest.py:238-303`) constructs `Sale`+`Operation` directly (bypassing `record_operation`) with explicit `id/device_id/seq/created_at/created_by` — exactly the "verbatim" shape the NDJSON factory needs. Note its stated limitation (does not update projections) — the merge's own `recompute_derived` handles that.

**Test dimensions** are enumerated in RESEARCH §"Phase Requirements → Test Map" (L533-550) and §"Test Dimensions" (L553-559): idempotency (merge-twice==once), verbatim replay, stock/cash recompute cross-check, two-device union, server-wins, code-collision rename, tombstone-inline, FK-ordering/missing-parent, atomic rollback, format version/malformed rejection, round-trip identity.

---

### `tests/test_merge_pg.py` (test, PG slice) — NEW or extend `tests/test_pg_parity.py`

**Analog:** `tests/test_pg_parity.py` (exact).

**Copy the skip-guard** (`test_pg_parity.py:33-37`):
```python
pytestmark = pytest.mark.skipif(
    not settings.database_url.startswith("postgresql"),
    reason="PG parity — set DATABASE_URL to a postgresql+psycopg:// URL",
)
```
**Copy the engine/migrate helpers** `_engine()` (L75-77) and `_upgrade_head()` (L80-86), and the `sessionmaker(bind=engine)` + `try/finally: engine.dispose()` pattern (L110-141). Seed only literal constant strings — never f-string external data (L15-16, Security V5). Run the idempotency + code-collision core here to prove the portable pre-select set-difference holds on PostgreSQL.

## Shared Patterns

### Portable insert / query (no dialect SQL)
**Source:** `app/services/ledger.py:141-145,156-168`, `app/services/finance.py:177`, `app/services/finance.py:197` (docstring rule).
**Apply to:** every insert/select in `merge.py`.
```python
select(func.coalesce(func.sum(Operation.qty_delta), 0)).where(Operation.product_id == product_id)
```
Generic Core `insert(model)` + `select(model.id).where(model.id.in_(ids))` only; no `sqlalchemy.dialects.*`.

### Caller-owned atomic transaction (all-or-nothing)
**Source:** `app/services/finance.py:156-166` (`try/except (IntegrityError, ValueError): session.rollback()`), `ledger.record_operation` `commit` flag (`ledger.py:134-135`).
**Apply to:** the illustrative Phase 28/30 caller and `apply_merge`'s no-commit contract.

### UUID / timestamp / money conventions
**Source:** `app/core.py:15-25` (`new_id`, `utcnow_iso`), `app/models.py:168,483` (String(36) PK, signed Integer cents).
**Apply to:** all record dicts and `server_now`.

### Server-authoritative duplicate-code probe
**Source:** `app/services/catalog.py:96-101` (probe), `app/models.py:158-166` (partial unique index backstop).
**Apply to:** Pattern 3 collision resolution in `merge.py`.

## No Analog Found

| File/symbol | Role | Data Flow | Reason |
|-------------|------|-----------|--------|
| `parse_exchange` / `serialize_exchange` (NDJSON) | service | transform | No line-delimited-JSON exchange format exists in-repo yet; build from stdlib `json` per RESEARCH §NDJSON (L304-341). Dataclass value-objects have no existing analog (repo uses dicts/ORM rows). |
| `_insert_new` bulk set-difference | service | batch | All existing writes are single-row `session.add`; no bulk insert-if-new exists. New code, but constrained to the portable-select idiom above. |

## Metadata

**Analog search scope:** `app/services/`, `app/models.py`, `app/core.py`, `tests/`.
**Files read (verified):** `app/services/ledger.py`, `app/services/finance.py`, `app/services/catalog.py` (L85-124), `app/core.py`, `app/models.py` (L140-320, L320-519), `tests/conftest.py`, `tests/test_pg_parity.py`, `27-RESEARCH.md`, `CLAUDE.md`.
**Pattern extraction date:** 2026-07-19
</content>
</invoke>
