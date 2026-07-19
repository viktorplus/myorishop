---
phase: 27-shared-idempotent-merge-core
reviewed: 2026-07-19T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - app/services/merge.py
  - app/services/ledger.py
  - tests/test_merge.py
  - tests/test_merge_pg.py
  - .github/workflows/ci.yml
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 27: Code Review Report

**Reviewed:** 2026-07-19
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Reviewed the shared idempotent merge core (`app/services/merge.py`), the
`recompute_derived` addition in `app/services/ledger.py`, and the two test
modules plus CI wiring. The engine correctly satisfies the primary invariants I
was asked to weigh: `apply_merge` never commits/rolls back (caller owns the
transaction), the idempotency probe is a portable pre-select set-difference with
no dialect SQL, ledger provenance is carried verbatim, `synced_at` is forced
null and never read from the wire, and row-level server-wins is honored for
existing reference UUIDs (no overwrite/resurrect/delete).

However, the code-collision resolver only compares incoming rows against the
**database**, never against the **other new rows in the same batch**. Two new
active products carrying the same `code` (a canonical cross-device scenario —
the exact reason DD-2 exists) both survive the resolver unrenamed and hit the
`uq_products_code_active` partial unique index, throwing `IntegrityError` and
forcing a full-batch rollback. That is a silent sync failure on legitimate input
(BLOCKER). Three robustness/validation gaps and two informational notes follow.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Intra-batch `Product.code` collision is never resolved → whole-batch rollback

**File:** `app/services/merge.py:321-356` (`_resolve_code_collisions`), reached via `app/services/merge.py:382-383` (`_upsert_reference`)

**Issue:** `_resolve_code_collisions` renames a losing product only when it finds
an **existing active incumbent in the DB** with a different UUID:

```python
clash = session.scalar(
    select(Product.id).where(Product.code == code, Product.deleted_at.is_(None))
)
if clash is not None and clash != row["id"]:
    row["code"] = _suffix_code(code, row["id"])
```

It never compares the incoming `new_rows` against each other. When a single
batch contains two (or more) NEW products with distinct UUIDs but the same active
`code` and **no active incumbent exists in the DB**, every row probes the DB,
finds nothing, and none are renamed. `_upsert_reference` then bulk-inserts all of
them, violating the `uq_products_code_active` partial unique index
(`app/models.py:158-166`). The resulting `IntegrityError` propagates out of
`apply_merge` and the caller rolls the entire batch back — the whole upload is
silently rejected even though DD-2's stated policy is "rename the loser."

This is a first-class multi-operator scenario: two devices each mint a product
with code `"12345"` locally (each legal under its own local unique index), and an
aggregated payload merges both. The engine is documented as "the ONE correctness
core" for both later transports, so this gap is not transport-specific. From the
operator's perspective it is data loss (their sync never lands). Note the test
suite only exercises the incumbent-in-DB path (`test_product_code_collision_renamed`),
so this case is untested.

**Fix:** Resolve collisions among the incoming batch too — track codes already
claimed within this merge and rename subsequent duplicates deterministically by
their own UUID (order the losers deterministically, e.g. by `id`, so replay is
stable):

```python
def _resolve_code_collisions(session, product_rows, conflicts):
    claimed: dict[str, str] = {}  # active code -> winning row id (first by id)
    for row in sorted(product_rows, key=lambda r: r["id"]):
        code = row.get("code")
        if row.get("deleted_at") is not None or not code:
            continue
        db_clash = session.scalar(
            select(Product.id).where(Product.code == code, Product.deleted_at.is_(None))
        )
        intra = claimed.get(code)
        incumbent = db_clash if (db_clash and db_clash != row["id"]) else intra
        if incumbent is not None and incumbent != row["id"]:
            row["code"] = _suffix_code(code, row["id"])
            conflicts.append(Conflict("product_code", row["id"], code, row["code"], incumbent))
        else:
            claimed[code] = row["id"]
```

Add a regression test that merges two new active products sharing one code with an
empty DB and asserts both insert with distinct codes.

## Warnings

### WR-01: Money validation only rejects `float`, letting non-int types reach an integer column

**File:** `app/services/merge.py:195-198`

**Issue:** The money guard rejects `float` only:

```python
for money_key in _money_fields(kind):
    if isinstance(data.get(money_key), float):
        raise ValueError(f"money field {money_key!r} must be int cents, not float")
```

A JSON string (`"cost_cents": "500"`) or any other non-int passes the check and
is written into an `Integer` column. On SQLite (dynamic typing / type affinity) a
non-numeric string is stored verbatim as text, silently corrupting the "money is
integer cents" invariant and diverging from PostgreSQL (which would raise). The
stated invariant is "integer cents only," but the validation enforces only "not
float." Booleans (`True`/`False`) also slip through as `1`/`0`.

**Fix:** Assert the value is an `int` (excluding `bool`) when present:

```python
value = data.get(money_key)
if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
    raise ValueError(f"money field {money_key!r} must be int cents")
```

### WR-02: Duplicate origin UUID within one batch is not deduplicated → whole-batch rollback

**File:** `app/services/merge.py:245-281` (`_partition_new` / `_insert_new`), same for `_upsert_reference`

**Issue:** `_partition_new` computes `existing` from the DB only and keeps every
incoming row whose id is not already persisted. If the same batch carries two
records of the same kind with the **same** `id` (e.g. a duplicated NDJSON line),
both are classified "new" and passed to `session.execute(insert(model), new_rows)`,
producing a duplicate-PK `IntegrityError` and a full rollback. The engine's
idempotency contract is about replaying a batch, but an internally duplicated
batch is a plausible malformed input that fails loudly for the whole payload
rather than being deduped or reported.

**Fix:** Deduplicate incoming rows by `id` before partitioning (keep first
occurrence), so an intra-batch duplicate is skipped like a replayed one:

```python
seen: set = set()
deduped = [r for r in rows if not (r["id"] in seen or seen.add(r["id"]))]
```

### WR-03: `_suffix_code` uses only 4 hex chars of the UUID — collision-prone rename

**File:** `app/services/merge.py:302-318`

**Issue:** The rename suffix is `"~"` plus the first 4 hex characters
(`_CODE_SUFFIX_HEX_LEN = 4`, ~16 bits) of the losing UUID. Two different losing
products that share the same base `code` and happen to share the same first 4 hex
digits produce an identical `resolved_code`. Combined with CR-01/WR-02 that is
another route to a `uq_products_code_active` violation and full rollback; even
standalone it makes the "deterministic, non-colliding rename" claim in the
docstring overstated. 16 bits gives a birthday-collision risk well within a busy
catalog.

**Fix:** Widen the suffix (e.g. 8 hex chars) within the `String(20)` budget, and/or
disambiguate against already-claimed renamed codes in the same pass (see CR-01
fix), appending more UUID hex until unique.

## Info

### IN-01: `serialize_exchange` round-trip is not truly field-for-field identity

**File:** `app/services/merge.py:466-480` (docstring) vs `app/services/merge.py:200-202`

**Issue:** The docstring asserts `parse_exchange(serialize_exchange(R)).records == R`
"field-for-field." That holds only when every record already has `synced_at`
either absent or `None` and carries no float money: `parse_exchange` forces
`synced_at` to `None` (correctly) and rejects float money. A record list with a
non-null `synced_at` would not round-trip identically. The tests only use
`synced_at=None`, so the claim is currently true for tested data but the
docstring overclaims for the general case.

**Fix:** Tighten the docstring to state the normalization (`synced_at` is nulled;
money must be int), so callers do not rely on strict identity.

### IN-02: PG portability test seeds with dialect-specific `ON CONFLICT DO NOTHING`

**File:** `tests/test_merge_pg.py:65-70`

**Issue:** `_SEED_INCUMBENT` uses raw `INSERT ... ON CONFLICT DO NOTHING`, a
PostgreSQL-specific clause, inside the very module whose purpose is proving the
engine avoids dialect-specific upserts. This is only test seed data (guarded to
run on PG), and the comment acknowledges it, so it is not an engine leak — but it
is mildly self-contradictory and could instead seed via a portable
"select-then-insert" or an ORM `merge`/`get`-guarded add for consistency with the
engine's own portability discipline.

**Fix:** Optional — replace the raw `ON CONFLICT` seed with a portable
existence-checked insert to keep the portability suite free of dialect SQL.

---

_Reviewed: 2026-07-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
