---
phase: 09-batch-tracking-ledger-integration
reviewed: 2026-07-12T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - alembic/versions/0008_batches.py
  - app/core.py
  - app/models.py
  - app/routes/__init__.py
  - app/routes/corrections.py
  - app/routes/receipts.py
  - app/routes/returns.py
  - app/routes/sales.py
  - app/routes/writeoffs.py
  - app/services/batches.py
  - app/services/corrections.py
  - app/services/ledger.py
  - app/services/operations.py
  - app/services/receipts.py
  - app/services/returns.py
  - app/services/sales.py
  - app/services/writeoffs.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-07-12
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

Phase 9 threads per-batch (lot) tracking through the append-only operation ledger. The core ledger math is sound and was traced end-to-end:

- The dual quantity projection in `record_operation` (SQL-side increment of both `Product.quantity` and `Batch.quantity` in one transaction) is correct.
- The legacy NULL-bucket accounting in `compute_batch_stock` / `rebuild_stock` holds the invariant `Product.quantity == Σ(batch quantities) + uncaptured NULL bucket` across every path I traced, including the tricky case of a stock-≤0-at-migration product that later receives a return (lazy legacy-batch creation) plus fresh receipts. No double-counting.
- The append-only invariant is respected: `batch_id` is added via a native `op.add_column` (preserving the `operations_no_update`/`operations_no_delete` triggers), set at INSERT time only, and batch attribution for legacy rows is resolved at READ time (`history_view` LEFT JOIN) rather than by rewriting ledger rows.
- The D-12 mandatory-batch guard, per-batch oversell/over-removal guards, client-batch ownership re-validation (untrusted `batch_id`), money-as-integer-cents, and portable ORM/SQL (no SQLite-specific constructs) are all present and correct.

The defects below are concentrated in error-path robustness and one inconsistency in input parsing. The most serious is that the receipts POST route — alone among the five write routes — omits the defensive `session.rollback()` before re-querying the session in its `except` handler, which turns a commit-time `OperationalError` into a raw 500, violating the route's own explicit "never a raw 500" contract.

## Critical Issues

### CR-01: Receipts POST route can raise a raw 500 on a commit-time DB error (missing defensive rollback)

**File:** `app/routes/receipts.py:189-199`
**Issue:** `register_receipt` catches only `IntegrityError` around its final `session.commit()` (`app/services/receipts.py:241-245`). A non-integrity commit failure — most realistically SQLite `OperationalError: database is locked` (the engine sets `busy_timeout=5000` in `app/db.py:49`, after which the lock raises) or a WAL/checkpoint error — propagates out. The route's `except Exception` handler then builds its context via `_form_extras(session, code=code, warehouse_id=warehouse_id)`, which immediately issues SELECTs (`active_warehouses`, `open_batches`) on a session whose transaction is now deactivated. In SQLAlchemy 2.0 that query raises `PendingRollbackError`, which is **not** re-caught, producing a raw 500 — exactly what the `# noqa: BLE001 — UI-SPEC: block error, never a raw 500` comment promises will not happen. `get_session` only rolls back on `with`-block exit, which happens *after* the handler has already raised. Every sibling write route (`sales.py`, `writeoffs.py`, `corrections.py`, `returns.py`) calls `session.rollback()` first in its `except` for precisely this reason (see the CR-03 note in `returns.py:117-121`); receipts is the only one missing it, and it is also the heaviest re-querier in its handler.
**Fix:** Roll back before re-querying, mirroring the other four routes:
```python
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        session.rollback()  # CR-03 parity: handler re-queries via _form_extras
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            **_form_extras(session, code=code, warehouse_id=warehouse_id),
        }
        return templates.TemplateResponse(
            request, "partials/receipt_form.html", context, status_code=422
        )
```

## Warnings

### WR-01: Receipt quantity parse missing the `isascii()` guard applied everywhere else

**File:** `app/services/receipts.py:107`
**Issue:** `qty = int(qty_text) if qty_text.isdigit() else 0` uses `str.isdigit()` alone. `str.isdigit()` returns `True` for non-ASCII digit characters (e.g. superscript `'²'`, `U+00B2`) that `int()` cannot parse — `int('²')` raises `ValueError`. This line is not wrapped in a `try`, so the raise propagates out of `register_receipt` and is only caught by the route's generic `except Exception`, surfacing the generic `SAVE_FAILED_ERROR` instead of the intended field-level `QTY_ERROR`. Every other quantity parse in the phase was explicitly hardened against exactly this — `sales.py:121`, `writeoffs.py:64`, `corrections.py:83,91`, `returns.py:135` all guard with `qty_text.isascii() and qty_text.isdigit()` and cite the "WR-01" rationale. Receipts was missed.
**Fix:**
```python
    qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
```

### WR-02: `record_operation` enforces batch presence but not the qty_delta ↔ audit-type invariant

**File:** `app/services/ledger.py:86-124`
**Issue:** The D-12 guard requires `batch_id` for `STOCK_AFFECTING_TYPES` and forbids it for audit types, but nothing enforces the corollary the docstring asserts as fact ("Audit types (qty_delta==0) stay batch-less"). A caller passing an audit type (`price_change`, `product_created`, `product_edited`) with a non-zero `qty_delta` is accepted: `batch` stays `None`, the batch guard passes, and `product.quantity = Product.quantity + qty_delta` still executes — moving stock into the untracked NULL bucket with no lot attribution. No current caller does this (all audit callers pass `qty_delta=0`), so it is latent, but the module bills itself as "the single-write-path enforcement backstop for … all current and future callers", and this is the one invariant it does not actually backstop.
**Fix:** Add a symmetric guard alongside the existing batch check:
```python
    if type_ not in STOCK_AFFECTING_TYPES and qty_delta != 0:
        raise ValueError(f"{type_!r} operations must be qty_delta==0 (audit-only)")
```

### WR-03: `register_sale` line-array `zip(strict=False)` silently drops misaligned lines

**File:** `app/services/sales.py:74-78`
**Issue:** `non_blank_lines` zips `codes`, `qtys`, `prices` with `strict=False`, so if a crafted/edited POST sends arrays of differing lengths (e.g. 3 codes but 2 prices), the extra entries are silently truncated rather than validated. `batch_ids` is defensively padded to `len(codes)`, but the three primary arrays are not length-checked against each other, so a line the operator believes they submitted can vanish with no error. The browser form keeps the arrays aligned, so this is form-tamper/robustness only, not an everyday path — hence a warning rather than blocker.
**Fix:** Reject ragged input explicitly (or pad symmetrically) before zipping, e.g. raise/return a basket-level error when `len(codes) != len(qtys) != len(prices)`.

## Info

### IN-01: Frozen legacy literals duplicated across three files (drift risk)

**File:** `alembic/versions/0008_batches.py:46-47`, `app/services/returns.py:35-36`, `app/routes/receipts.py:23`
**Issue:** `DEFAULT_WAREHOUSE_ID` (`00000000-0000-4000-8000-000000000010`) and the legacy comment string `"Остаток до внедрения партий"` are re-declared as frozen copies in the migration, the returns service, and the receipts route. The duplication is *deliberate and documented* (WR-06: migrations must never import app modules; the return-path copy must match the seed contract exactly), so this is not a defect — but three independent literals for one contract value are a future-drift hazard if the seed contract ever changes.
**Fix:** Acceptable as-is given the migration-immutability rule. If desired, the two app-layer copies (`returns.py`, `receipts.py`) could share one app-level constant while the migration keeps its frozen copy.

### IN-02: `_ROW_ID_RE` is looser than a UUID4 shape

**File:** `app/routes/sales.py:31`
**Issue:** `re.compile(r"[0-9a-fA-F-]{1,36}")` (used with `fullmatch`) admits values that are not valid UUID4s (e.g. all-dashes, arbitrary hex length ≤36). Because it is echoed into an `hx-on::load` JS-evaluated attribute, the security-relevant property is that the charset excludes quotes/angle-brackets/whitespace — which it does, so no injection is possible. Pre-existing (CR-01/T-09-10 precedent); noted only for completeness.
**Fix:** Optional — tighten to the exact UUID4 pattern if strictness is desired; no security impact as-is.

---

_Reviewed: 2026-07-12_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
