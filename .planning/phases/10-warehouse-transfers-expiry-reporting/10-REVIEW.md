---
phase: 10-warehouse-transfers-expiry-reporting
reviewed: 2026-07-12T00:00:00Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - app/models.py
  - app/services/ledger.py
  - app/services/transfers.py
  - tests/test_transfers.py
  - app/templates/pages/transfer_form.html
  - app/templates/partials/transfer_form.html
  - app/templates/partials/transfer_lookup.html
  - app/templates/partials/transfer_batch_wrap.html
  - app/templates/partials/transfer_oversell.html
  - app/templates/partials/transfer_rows.html
  - app/routes/transfers.py
  - app/main.py
  - app/templates/base.html
  - app/services/batches.py
  - app/routes/reports.py
  - app/templates/pages/reports_expiry.html
  - app/templates/pages/reports_landing.html
  - tests/test_batches.py
  - tests/test_reports.py
findings:
  critical: 0
  warning: 2
  info: 2
  total: 4
status: issues_found
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-12T00:00:00Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Reviewed the WH-03 transfer feature (`app/services/transfers.py`, `app/routes/transfers.py`, transfer templates, `tests/test_transfers.py`) and the LOT-06 expiry report (`expiring_batches()` in `app/services/batches.py`, `/reports/expiry` route + template) at standard depth, including the single-write-path (`record_operation`) and model changes they depend on.

The core write path is sound: `register_transfer` validates code/qty/batch-ownership/destination-warehouse before any write, stages both `transfer` ledger rows with `commit=False` and a single `session.commit()`, and the mandatory-batch / ownership guards in `record_operation` correctly reject cross-product batch tampering. I traced the SQL-expression increment + `session.add(dest)`-before-`record_operation` ordering (the "Pitfall 2" comment) empirically against the pinned SQLAlchemy 2.0.51 and confirmed `Session.get()` does autoflush a pending, explicitly-keyed row in this version, so that pattern is safe as written.

Two real (if modest-impact, single-operator-app) defects were found in `app/routes/transfers.py`, both classified Warning. Two additional Info-level consistency/quality observations are noted below. No Critical/blocker-level issues were found.

## Warnings

### WR-01: Unvalidated cross-product batch echoed back into the form on error/oversell/exception

**File:** `app/routes/transfers.py:130, 150-151, 166-167, 177-178`
**Issue:** `transfers_create()` resolves `selected_batch = session.get(Batch, batch_id.strip())` directly from the raw client-submitted `batch_id`, with **no ownership check against `code`/`product`**, and then echoes it into the re-rendered form on every failure path (validation errors, oversell warning, and the generic-exception branch) via `"selected_batch": selected_batch` / `_dest_warehouses(session, selected_batch)`.

This is inconsistent with the ownership re-validation this same phase documents and enforces elsewhere: `register_transfer()` itself rejects a `batch_id` that "belongs to another product" (`T-09-01`), and `GET /transfers/batch-pick` explicitly re-validates `candidate.product_id == product.id` before echoing a picked batch (lines 93-96). The POST handler's error-render path skips that check entirely.

Concretely: submit `code=<product A's code>` with `batch_id=<a batch belonging to product B>`. `register_transfer` correctly rejects the write (`errors["batch"]` set, zero ops written — covered by `test_reject_tampered_ids`), but the 422 response still renders product B's batch (price, expiry, remaining quantity, location, comment — see `partials/batch_picker.html:51-60`) inside product A's transfer form, because `selected_batch` was fetched without the ownership check.

Note: this exact pattern (unvalidated `session.get(Batch, batch_id)` used only for echo) is copied verbatim from `app/routes/writeoffs.py:123`, so it is a pre-existing, systemic pattern rather than something newly invented in this phase — but it is still present, unaddressed, in the reviewed file, and no test in `tests/test_transfers.py` catches the leaked/mismatched echo (`test_reject_tampered_ids` only asserts `errors`/no writes, never inspects the rendered batch table).

**Fix:**
```python
# app/routes/transfers.py, transfers_create()
selected_batch = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
if selected_batch is not None and selected_batch.product_id != <resolved product id for `code`>:
    selected_batch = None
```
(Requires resolving the product for `code` once at the top of the handler — mirrors the ownership check already done inside `register_transfer` and in `transfers_batch_pick`.)

### WR-02: Success message echoes the raw, unnormalized `qty` form string instead of the actual transferred quantity

**File:** `app/routes/transfers.py:190`
**Issue:** On success, the confirmation banner is built as:
```python
"saved": {"name": result["product"].name, "qty": qty},
```
where `qty` is the *raw* `Form("")` string exactly as submitted (not stripped, not parsed to `int`). The analogous write-off handler (`app/routes/writeoffs.py:184`) instead uses the actual persisted delta: `"qty": -result["operation"].qty_delta`.

Because `register_transfer`'s own qty parsing (`qty_text = qty_raw.strip(); qty = int(qty_text)`) happens inside the service and is never surfaced back to the route, a submission like `qty="007"` or `qty=" 5 "` (leading zeros / stray whitespace preserved by a client, e.g. autofill or a scripted POST) renders as `Перемещение сохранено: <name> — 007 шт.` or with stray whitespace, even though the actual ledger write correctly used the parsed integer `7`/`5`. No existing test exercises a non-canonical qty string, so this gap isn't caught (`test_transfer_post_moves_stock` et al. always POST clean digit strings).

**Fix:** Have `register_transfer` return the parsed integer qty in its result dict (e.g. `{"product": product, "source": source, "dest": dest, "qty": qty}`) and use that in the route:
```python
"saved": {"name": result["product"].name, "qty": result["qty"]},
```

## Info

### IN-01: `expiring_batches()` does not exclude soft-deleted products, unlike its stated analog

**File:** `app/services/batches.py:42-56`
**Issue:** `expiring_batches()` (backing `/reports/expiry`) joins `Batch`→`Product`→`Warehouse` and filters only `Batch.quantity > 0, Batch.expiry.is_not(None)` — it never checks `Product.deleted_at`. Its documented analog, `/reports/stock` (`reports_stock_page`), explicitly excludes soft-deleted products via `low_stock_products()`/`all_active_products()`. As written, a batch of physical stock belonging to a soft-deleted (discontinued) product will still surface on the expiry report under that product's name/code.

This may well be intentional (the physical stock still exists and still expires regardless of the product's catalog status, so the operator may need to see it to write it off) — but it's an inconsistency with the sibling "current stock" report worth confirming as a deliberate decision rather than an oversight, since no test (`tests/test_reports.py`, `tests/test_batches.py`) exercises a soft-deleted product's batch through `expiring_batches()`/`/reports/expiry` either way.

**Fix:** If active-only was intended, add `.where(Product.deleted_at.is_(None))` to the query in `expiring_batches()`. If showing discontinued-product stock is intended, add a regression test pinning that behavior (mirroring the Pitfall-5-style tests already present for the sales/write-off reports) so it doesn't drift later.

### IN-02: Duplicate `SAVE_FAILED_ERROR` constant name, different RU text, in service vs. route module

**File:** `app/services/transfers.py:28`, `app/routes/transfers.py:23`
**Issue:** Both modules define a module-level `SAVE_FAILED_ERROR` constant with the *same name* but *different Russian text*:
- service: `"Не удалось сохранить. Попробуйте ещё раз."`
- route: `"Не удалось сохранить. Проверьте данные и попробуйте ещё раз."`

Each is used for a distinct failure path (service-level `IntegrityError`/`ValueError` inside `register_transfer`'s try/except vs. the route's outer generic-`Exception` handler), so today's behavior is deliberate, not broken — and this duplication is itself copied from the equivalent `writeoffs.py` service/route pair. Still, identically-named constants with diverging values across two files reviewers/maintainers will naturally assume are the same is a maintainability trap (a future edit to one is easy to assume also updates the other).

**Fix:** Rename one (e.g. `TRANSFER_WRITE_FAILED_ERROR` in the service vs. `TRANSFER_ROUTE_FAILED_ERROR` in the route), or consolidate to a single shared constant if the distinct wording isn't load-bearing.

---

_Reviewed: 2026-07-12T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
