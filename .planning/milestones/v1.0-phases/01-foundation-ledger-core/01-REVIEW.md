---
phase: 01-foundation-ledger-core
reviewed: 2026-07-08T13:16:19Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - alembic/env.py
  - alembic/versions/0001_initial_schema.py
  - app/config.py
  - app/core.py
  - app/db.py
  - app/main.py
  - app/models.py
  - app/routes/home.py
  - app/routes/ops.py
  - app/services/ledger.py
  - app/templates/base.html
  - app/templates/pages/home.html
  - app/templates/partials/ledger_rows.html
  - run.bat
  - tests/conftest.py
  - tests/test_ledger.py
  - tests/test_pragmas.py
  - tests/test_smoke.py
  - pyproject.toml
  - alembic.ini
findings:
  critical: 0
  warning: 6
  info: 5
  total: 11
status: findings
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-08T13:16:19Z
**Depth:** standard
**Files Reviewed:** 20
**Status:** findings (0 critical, 6 warnings, 5 info)

## Summary

Reviewed the complete Phase 1 foundation: SQLite engine/PRAGMA setup, SQLAlchemy 2.0 models, Alembic migration 0001 with append-only triggers, the ledger service (single write path), HTMX routes/templates, launcher, and the test suite.

The core invariants hold up under adversarial inspection: append-only enforcement lives in DB triggers (verified single-source DDL shared by migration and test fixtures), money is integer-cents only (metadata-wide Numeric/Float guard in tests), timestamps are tz-aware UTC ISO text that sorts lexicographically, PKs are UUID4 TEXT, autoescape is on with no `| safe`, no raw SQL touches user input, the bind is loopback-only, and no secrets are hardcoded. No critical defects found.

However, three warnings were **confirmed by executing the code** (not just read): the unknown-product guard in `record_operation` is dead code preempted by autoflush; `to_cents` leaks `decimal.InvalidOperation` past its documented ValueError contract; and `to_cents` silently uses banker's rounding for money input. Plus operational gaps in run.bat and a migration-immutability risk.

## Findings Table

| ID | Severity | File | Line | Issue | Status |
|----|----------|------|------|-------|--------|
| WR-01 | Warning | app/services/ledger.py | 61-64 | Unknown-product ValueError guard is unreachable: autoflush in `session.get()` fires FK IntegrityError first (verified by execution) | fixed — product validated before staging the row; regression test added (550fa92) |
| WR-02 | Warning | app/core.py | 33-38 | `to_cents("inf")` / huge exponents raise `decimal.InvalidOperation` instead of documented ValueError (verified by execution) | fixed — whole conversion wrapped, non-finite rejected; tests/test_core.py added (21bddcd) |
| WR-03 | Warning | app/core.py | 38 | `to_cents` rounds with implicit banker's rounding: `"12,505"` → 1250, not 1251 (verified by execution) | fixed — explicit ROUND_HALF_UP, documented in docstring + tests (1d4ec5b) |
| WR-04 | Warning | app/routes/ops.py | 25 | POST /ops with bad `product_id` returns 500 (unhandled service exception), not a 4xx | fixed — ValueError caught, 404 returned; smoke test added (aa49eca) |
| WR-05 | Warning | run.bat | 4-5 | uvicorn starts even when `alembic upgrade head` fails — no errorlevel check | fixed — errorlevel check aborts launch; browser opens only after check (e9ab8fe) |
| WR-06 | Warning | alembic/versions/0001_initial_schema.py | 19-20 | Migration imports mutable app-level constants/functions — breaks migration immutability; import side-effect builds the prod engine | fixed — frozen trigger DDL + seed timestamp inlined, no app imports; APPEND_ONLY_TRIGGERS kept for test fixtures (70c5f4e) |
| IN-01 | Info | app/services/ledger.py | 62-65 | `record_operation` accepts soft-deleted products | skipped — needs a product-deletion semantics decision; defer to Phase 2 soft-delete work |
| IN-02 | Info | app/services/ledger.py | 65 | `product.quantity += qty_delta` is a Python-side read-modify-write, not an atomic SQL update | fixed — SQL-side atomic increment (83c073b) |
| IN-03 | Info | tests/test_smoke.py | 27 | Vacuous assertion: `or "3" in response.text` always passes (timestamps contain "3") | fixed — vacuous or-clause removed (635adf4) |
| IN-04 | Info | app/main.py, app/config.py, app/routes/__init__.py | 9, 14, 8 | All paths are CWD-relative; app misbehaves when launched outside repo root | skipped — low priority for v1; run.bat's `cd /d "%~dp0"` mitigates; revisit if launch outside repo root becomes a use case |
| IN-05 | Info | app/models.py | 51 | `Operation.id` has no default while `Product.id` does — inconsistent convention | fixed — `default=new_id` added (be98ecf) |

## Warnings

### WR-01: Unknown-product guard in record_operation is dead code (validation after `session.add`)

**File:** `app/services/ledger.py:61-64`
**Issue:** The guard added as deviation #4 in 01-03-SUMMARY ("prevents an opaque AttributeError") does not do what the summary claims. `session.add(op)` runs *before* `session.get(Product, product_id)`; `Session.get()` autoflushes the pending Operation row, and with `PRAGMA foreign_keys=ON` the INSERT fails on the FK constraint before the `if product is None` branch can ever execute. Verified by execution:

```
record_operation(session, product_id="no-such-id", ...)
-> sqlalchemy.exc.IntegrityError (raised as a result of Query-invoked autoflush)
```

The `ValueError(f"unknown product: ...")` path is unreachable in any environment with FK enforcement on (which is every environment here — the PRAGMA listener applies to all connections). The data is still protected (transaction rolls back), so this is not a corruption risk, but the validation is illusory and the actual failure mode differs from what callers were told to expect.
**Fix:** Validate the product before staging the operation row:

```python
product = session.get(Product, product_id)
if product is None:
    raise ValueError(f"unknown product: {product_id!r}")
op = Operation(...)
session.add(op)
product.quantity += qty_delta
session.commit()
```

### WR-02: `to_cents` leaks `decimal.InvalidOperation` past its documented ValueError contract

**File:** `app/core.py:33-38`
**Issue:** The docstring promises "Raises ValueError on garbage", and app/core.py is declared "the ONLY sanctioned conversion point" for money — so future phases will call it and catch `ValueError`. But the `try/except InvalidOperation` wraps only `Decimal(text)` construction. Inputs that `Decimal()` accepts but `quantize()` rejects escape unwrapped. Verified by execution:

```
to_cents('inf')     -> decimal.InvalidOperation  (contract VIOLATED)
to_cents('1e100000') -> decimal.InvalidOperation (contract VIOLATED)
to_cents('nan')     -> ValueError (only by luck: int(Decimal('NaN')) raises ValueError)
```

A Phase 2 price form that types the field as `str` and calls `to_cents` inside `except ValueError` will 500 on `"inf"` instead of showing a validation message.
**Fix:** Wrap the whole conversion and reject non-finite values:

```python
try:
    amount = Decimal(text)
    if not amount.is_finite():
        raise InvalidOperation
    return int(amount.quantize(_CENTS) * 100)
except (InvalidOperation, ValueError) as exc:
    raise ValueError(f"invalid money value: {value!r}") from exc
```

### WR-03: `to_cents` silently uses banker's rounding for money input

**File:** `app/core.py:38`
**Issue:** `amount.quantize(_CENTS)` uses the default `ROUND_HALF_EVEN`. Verified by execution: `to_cents("12,505")` returns **1250**, not 1251. An operator entering a half-cent price gets it rounded down or up depending on the parity of the preceding digit — surprising and undocumented for a retail-money helper whose stated purpose is "cents rendered only via helper / never float". This is the sanctioned conversion point for all future price entry, so the rounding policy must be a deliberate, documented choice — most retail contexts expect HALF_UP.
**Fix:** `amount.quantize(_CENTS, rounding=ROUND_HALF_UP)` (import `ROUND_HALF_UP` from `decimal`), or reject >2 decimal places outright as invalid input. Document the choice in the docstring either way.

### WR-04: POST /ops returns 500 for a bad product_id (unhandled service exception)

**File:** `app/routes/ops.py:25`
**Issue:** `record_operation` raises `ValueError` or (per WR-01, in practice) `IntegrityError` when `product_id` doesn't exist. Neither is handled in the route, so FastAPI returns a raw 500 with a server-side traceback in the log. The plan's stated input-validation story ("typed Form fields → 422 before any business code") covers `qty_delta` type garbage only — it does not cover a stale/tampered `product_id` (e.g., a browser tab left open across a product deletion in Phase 2). HTMX will swap an error page fragment or nothing into `#ledger`.
**Fix:** Catch the domain error in the route and return a 4xx:

```python
try:
    record_operation(session, type_="correction", product_id=product_id, qty_delta=qty_delta)
except (ValueError, IntegrityError):
    session.rollback()
    raise HTTPException(status_code=404, detail="unknown product")
```
(With WR-01 fixed, catching `ValueError` alone suffices.)

### WR-05: run.bat starts the server even when the migration fails

**File:** `run.bat:4-5`
**Issue:** There is no errorlevel check after `uv run alembic upgrade head`. If the migration fails (locked DB file, corrupted DB, future bad revision), uvicorn starts anyway against a wrong-schema database, and the browser (opened unconditionally on a 2-second timer, line 3) shows opaque 500s. For a project whose Phase 1 goal is "getting this schema right", serving on top of a failed migration is the exact failure the launcher should prevent.
**Fix:**

```bat
uv run alembic upgrade head
if errorlevel 1 (
  echo Migration failed - server not started.
  pause
  exit /b 1
)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```
(Moving the browser-open `start` after the errorlevel check also stops the browser from opening onto a dead port when migration fails.)

### WR-06: Migration 0001 depends on mutable app code (`APPEND_ONLY_TRIGGERS`, `utcnow_iso`)

**File:** `alembic/versions/0001_initial_schema.py:19-20`
**Issue:** Migrations must be frozen snapshots: replaying the chain on a fresh DB must produce the same history forever. Migration 0001 executes `app.db.APPEND_ONLY_TRIGGERS` — a constant the project's own docs plan to change ("v2 sync relaxes the UPDATE trigger with a WHEN clause in a new migration", 01-02-SUMMARY). If that constant is edited in place, a fresh install replaying 0001 creates the v2 trigger while a v1-era DB migrated in sequence has a different intermediate history; any v2 migration that drops/recreates triggers by name may then behave differently across the two paths. Additionally, `from app.db import ...` executes `engine = build_engine(settings.db_path)` at import time as a side effect — the migration process builds a second engine (and `mkdir`s the data dir) pointing at the same file it is migrating.
**Fix:** Inline the two trigger DDL strings and the seed timestamp literal into the migration file (migrations may *duplicate* app constants; they must not *reference* them). Keep `APPEND_ONLY_TRIGGERS` in `app.db` for the test fixture. If single-sourcing is kept deliberately, add a hard rule to the v2 plan: never edit `APPEND_ONLY_TRIGGERS` in place — new trigger DDL goes into the new migration only.

## Info

### IN-01: `record_operation` accepts operations against soft-deleted products

**File:** `app/services/ledger.py:62-65`
**Issue:** The single write path checks existence but not `deleted_at IS NULL`. Once Phase 2 introduces soft deletion, a stale form or bad caller can append ledger rows to a deleted product; `ledger_view` will then show `product=None` while operations keep accumulating.
**Fix:** Decide now: either reject (`if product.deleted_at is not None: raise ValueError`) or explicitly document that the ledger accepts deleted products (e.g., for returns). Doing neither leaves the invariant undefined for Phase 2.

### IN-02: Cached-quantity update is a Python-side read-modify-write

**File:** `app/services/ledger.py:65`
**Issue:** `product.quantity += qty_delta` reads a possibly-stale ORM value. Under WAL, a concurrent second request fails with `SQLITE_BUSY_SNAPSHOT` (→ 500) rather than losing the update, and the `hx-disabled-elt` guard plus single operator make this unlikely — so no corruption, only a rough edge.
**Fix:** `product.quantity = Product.quantity + qty_delta` emits an atomic `UPDATE ... SET quantity = quantity + ?` and removes the staleness window entirely.

### IN-03: Vacuous assertion in smoke test

**File:** `tests/test_smoke.py:27`
**Issue:** `assert ">3<" in response.text or "3" in response.text` — the second clause matches any "3" anywhere (timestamps like "2026-07-08 13:03" always contain one), so the assertion can never fail and the "updated stock is rendered" claim is untested.
**Fix:** Drop the `or` clause: `assert ">3<" in response.text` (the partial renders `<strong>3</strong>` and `<td>3</td>`), or assert on `"Пересчёт по журналу: <strong>3</strong>"`.

### IN-04: All runtime paths are CWD-relative

**File:** `app/main.py:9`, `app/config.py:14`, `app/routes/__init__.py:8`
**Issue:** `app/static`, `app/templates`, `data/myorishop.db`, and `.env` all resolve against the current working directory. run.bat's `cd /d "%~dp0"` covers the happy path, but `uv run uvicorn app.main:app` from any other directory either crashes at import (`StaticFiles` checks the directory) or silently creates a stray `data/` with an empty DB elsewhere.
**Fix:** Anchor paths to the package: `BASE_DIR = Path(__file__).resolve().parent` in config and derive `db_path`, template and static dirs from it (low priority for v1; the launcher mitigates).

### IN-05: `Operation.id` lacks the `default=new_id` that `Product.id` has

**File:** `app/models.py:51`
**Issue:** Inconsistent convention: `Product.id` defaults to `new_id`, `Operation.id` must be passed explicitly. Today `record_operation` always supplies it, and NOT NULL catches omissions loudly — but the asymmetry invites a future caller to assume the default exists.
**Fix:** Add `default=new_id` to `Operation.id` for consistency (record_operation's explicit `id=new_id()` remains fine).

## Verified Non-Issues (adversarial checks that passed)

- **Append-only enforcement:** triggers exist in both migration and test-fixture paths from the single DDL source; UPDATE/DELETE rejection covered by tests at the DB level, not the ORM level.
- **PRAGMA listener:** applied per pooled connection with the autocommit save/restore dance; asserted on a live pooled connection in test_pragmas. `busy_timeout=5000` consistent between code and test.
- **Naming convention vs migration names:** `pk_products`, `pk_operations`, `fk_operations_product_id_products`, `uq_operations_device_id`, `ix_operations_product_id` in migration 0001 all match what `NAMING_CONVENTION` generates — batch migrations will be able to target them.
- **Timestamp ordering:** `utcnow_iso()` always emits a `+00:00` offset with fixed-width fields, so `ORDER BY created_at DESC` on TEXT is chronologically correct; same-second ties are broken by `seq DESC` (valid for the single-device v1).
- **XSS:** Starlette's `Jinja2Templates` autoescapes by default; no `| safe` anywhere; both user-influenced values in templates (`product.name`, `created_by`) are escaped.
- **Injection:** no raw SQL with interpolated input anywhere in app code; `text()` appears only in tests with constant strings.
- **Threading:** SQLAlchemy's pysqlite dialect uses `check_same_thread=False` with QueuePool for file DBs, so FastAPI's threadpool `def` endpoints are safe; confirmed indirectly by the green TestClient suite.
- **Auth intentionally absent, loopback-only bind:** by design per project context; run.bat hard-codes `--host 127.0.0.1`, no `0.0.0.0` anywhere.
- **No secrets:** config holds only local paths and display identity; `.env` is gitignored.

---

_Reviewed: 2026-07-08T13:16:19Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
