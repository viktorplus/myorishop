---
phase: 09-batch-tracking-ledger-integration
plan: 02
subsystem: receipts
tags: [receipts, batches, htmx, warehouse, expiry, resolve-or-create, tdd]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration
    plan: 01
    provides: "Batch model, app/services/batches.py (open_batches, active_warehouses), batch-aware record_operation(batch_id=...), ru_date filter"
  - phase: 08-warehouses
    provides: "warehouses table + frozen DEFAULT_WAREHOUSE_ID seed"
provides:
  - "register_receipt(warehouse_id, batch_choice, expiry_raw, location_raw, comment_raw): resolve-or-create Batch in the same transaction (D-01/D-02)"
  - "parse_optional_expiry(raw, errors, key): optional ISO date validation (LOT-03)"
  - "GET /receipts/batches chooser endpoint (top-up radios + new-batch path + zero-warehouses blocking hint)"
  - "receipt_batch_chooser.html partial + warehouse select + #batch-chooser in receipt_form.html"
  - "server-side warehouse/batch ownership re-validation (Pitfall 10, T-09-04/T-09-05)"
affects: [sales, writeoffs, corrections, returns, batch-picker-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Resolve-or-create the batch in the SAME transaction as the product auto-create (mirror of D-05)"
    - "New batch snapshots the entered «Цена продажи» into Batch.price_cents; top-up never rewrites the frozen price (D-02)"
    - "Server-decides-fill HTMX chooser: warehouse-change swap + code-lookup oob refresh, inner-content partial"
    - "Hidden+disabled toggling for the new-batch fields (single-colon hx-on:change; a disabled input never submits)"

key-files:
  created:
    - "app/templates/partials/receipt_batch_chooser.html"
  modified:
    - "app/services/receipts.py"
    - "app/routes/receipts.py"
    - "app/templates/partials/receipt_form.html"
    - "app/templates/partials/receipt_lookup.html"
    - "tests/test_receipts.py"

key-decisions:
  - "warehouse_id/batch_choice are REQUIRED params on register_receipt; expiry/location/comment default to '' — receipts now always supply a batch (batch_id still optional at the write path until Plan 05)"
  - "The POST route's Form-field pass-through moved into Task 1 (blocking coupling: the new required signature breaks the caller and the whole-file green gate)"
  - "Default-warehouse preselect: DEFAULT_WAREHOUSE_ID if active, else first active alphabetically, else '' (RESEARCH Open Q2)"
  - "Chooser oob refresh on /receipts/lookup only for source == 'product' (keeps the dictionary-fallback 'no oob' contract intact)"

requirements-completed: [WH-02, LOT-01, LOT-03, LOT-04]

# Metrics
duration: 15 min
completed: 2026-07-12
---

# Phase 9 Plan 02: Receipt Batch Birth Path Summary

**The goods-receipt flow is now the batch birth path (D-01/D-02): a required «Склад» select, an HTMX resolve-or-create chooser (top up an open batch vs a new batch with expiry/location/comment), a sale-price snapshot into `Batch.price_cents`, and server-side warehouse/ownership re-validation — full 288-test suite green.**

## Performance

- **Duration:** 15 min
- **Start:** 2026-07-12T09:59:06Z
- **End:** 2026-07-12T10:14:51Z
- **Tasks:** 2 (Task 1 TDD RED→GREEN; Task 2 route/templates + route tests)
- **Files:** 6 (1 created, 5 modified)

## Accomplishments

- **`parse_optional_expiry`** — mirrors `parse_optional_cents`: empty → None (optional, LOT-03), valid ISO normalizes via `date.fromisoformat`, malformed → RU error under the given key. Untrusted-form re-validation (V5).
- **`register_receipt` is batch-aware** — new params `warehouse_id`, `batch_choice`, `expiry_raw`, `location_raw`, `comment_raw`. It resolves-or-creates the `Batch` in the same transaction as the product auto-create: a new batch snapshots the entered «Цена продажи» plus optional expiry/location/comment (WH-02/LOT-03/LOT-04); a top-up increments the chosen batch's quantity and leaves its frozen `price_cents` untouched (D-02). The receipt op now threads `batch_id` (D-11 dual projection).
- **Defense in depth** — server-side active-warehouse re-check (zero-warehouse blocking state re-enforced on POST even for a stale form, T-09-05) and batch ownership re-validation (`batch.product_id == product.id and batch.warehouse_id == warehouse_id`, Pitfall 10 / T-09-04) with zero writes on reject.
- **`GET /receipts/batches` chooser endpoint** + `receipt_batch_chooser.html`: top-up radios per open batch (D-07 order, money via `| cents`, expiry via `ru_date`, location `.muted`), a «Новая партия» radio revealing the three new-batch fields (hidden+disabled toggling), and a zero-warehouses blocking `.error-block` linking to `/warehouses`.
- **`receipt_form.html`** gains the required «Склад» select (default-warehouse preselect) and the `#batch-chooser` div; the code input's `hx-include` grew to carry `[name='warehouse_id']`, and `/receipts/lookup` oob-refreshes the chooser for an existing product.

## Task Commits

1. **Task 1 (TDD): register_receipt resolve-or-create + parse_optional_expiry**
   - `3615221` (test, RED) → `0b96e87` (feat, GREEN)
2. **Task 2: /receipts/batches chooser, warehouse select, new-batch fields**
   - `7a8255f` (feat)

## Files Created/Modified

- `app/services/receipts.py` — `parse_optional_expiry`; `register_receipt` batch resolve-or-create + warehouse/expiry validation; new RU error constants; returns `{"product", "operation", "batch"}`.
- `app/routes/receipts.py` — `GET /receipts/batches`; POST `/receipts` Form fields + `_form_extras`/`_chooser_context`/`_preselect_warehouse_id` helpers; `/receipts/lookup` gains `warehouse_id` + oob chooser refresh.
- `app/templates/partials/receipt_batch_chooser.html` (new) — top-up-vs-new radios, new-batch fields, zero-warehouses blocking hint.
- `app/templates/partials/receipt_form.html` — «Склад» select + `#batch-chooser` + grown code `hx-include`.
- `app/templates/partials/receipt_lookup.html` — oob `#batch-chooser` refresh for `source == "product"`.
- `tests/test_receipts.py` — every `register_receipt` call updated; new batch/expiry/ownership/zero-warehouse service tests + chooser/warehouse/zero route tests.

## Decisions Made

- **Route Form-field pass-through belongs to Task 1, not Task 2.** Task 1's `verify` gate requires the whole `tests/test_receipts.py` green, but making `warehouse_id`/`batch_choice` required on `register_receipt` breaks the POST route (the caller) and its web tests. Adding the Form fields + pass-through in Task 1 is the minimal fix that keeps the file green at the Task-1 boundary (RESEARCH Pitfall 1: never split a signature change from its callers). Task 2 then adds the chooser endpoint, templates, and route-level chooser tests. Documented as a Rule 3 deviation below.
- **Default-warehouse preselect** — `DEFAULT_WAREHOUSE_ID` if active, else first active alphabetically (`active_warehouses` is name-ordered), else `""` (RESEARCH Open Q2).
- **Chooser oob only for existing products** — `/receipts/lookup` refreshes `#batch-chooser` oob only when `source == "product"`, preserving the dictionary-fallback "no oob" contract (`test_web_lookup_dictionary_fallback_name_only`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Moved the POST-route Form fields into Task 1**
- **Found during:** Task 1 (whole-file `verify` gate)
- **Issue:** The plan lists `app/routes/receipts.py` under Task 2 only, but making `warehouse_id`/`batch_choice` required on `register_receipt` (Task 1) breaks the existing POST route call and the web POST tests, so `uv run pytest tests/test_receipts.py -x -q` could not pass at the Task-1 boundary.
- **Fix:** Added the five Form fields (`warehouse_id`, `batch_choice`, `expiry`, `location`, `comment`) and their pass-through to the POST route in Task 1; the web POST tests seed a `warehouse` fixture and post the new fields. Task 2 kept its chooser endpoint / template / route-test scope.
- **Files modified:** app/routes/receipts.py, tests/test_receipts.py
- **Verification:** `uv run pytest tests/test_receipts.py -x -q` → 31 passed at the Task-1 boundary.
- **Committed in:** `0b96e87` (Task 1 GREEN)

**2. [Rule 3 - Blocking] Updated the `test_web_lookup_form_wiring` hx-include assertion**
- **Found during:** Task 2
- **Issue:** Growing the code input's `hx-include` to add `[name='warehouse_id']` (a Task 2 requirement) broke the exact-string assertion in `test_web_lookup_form_wiring`.
- **Fix:** Updated the expected include string to the grown value.
- **Files modified:** tests/test_receipts.py
- **Verification:** `uv run pytest tests/test_receipts.py -k "lookup" -q` green.
- **Committed in:** `7a8255f` (Task 2)

---

**Total deviations:** 2 auto-fixed (both Rule 3 blocking-coupling: a required-signature change and a grown hx-include forced adjacent caller/test updates). **Impact:** production behaviour matches the plan's D-01/D-02 contract exactly; the only cross-task shift is that the POST route's Form fields landed one task earlier than the file list implied, which is required for the atomic green-at-each-boundary invariant.

## Known Stubs

None — the chooser, warehouse select, and new-batch fields are fully wired and exercised by tests. `Batch.price_cents` is snapshotted from the entered sale price on the new-batch path (NULL only for legacy batches, per Plan 01 D-14).

## Threat Flags

None — no new network trust boundaries beyond the planned `GET /receipts/batches` (read-only chooser render) and the extended POST. The threat_model mitigations are all implemented: T-09-04 (batch product+warehouse ownership re-validation), T-09-05 (server-side active-warehouse re-check + `date.fromisoformat` expiry validation), T-09-06 (batch comment/location rendered via Jinja autoescape only, never `|safe`).

## Issues Encountered

None. Full suite `uv run pytest -q` → 288 passed. The two suite warnings (test_backup `StarletteDeprecationWarning`, test_returns `SAWarning`) are pre-existing and unrelated to this plan.

## Next Phase Readiness

- Receipts create real batches with warehouse/expiry/price/location/comment — Plans 03-04 pickers (sale/writeoff/correction) now have open batches to select. Ready for Plan 09-03.
- Plan 05 still flips the mandatory D-12 guard (batch_id required for stock-affecting types) once every operation service passes a batch.

## Self-Check: PASSED

- All 6 key files present on disk (verified with `[ -f ]`).
- All 3 task commits present in `git log` (1 RED test + 2 feat).
- `uv run pytest tests/test_receipts.py -q` → 34 passed; `uv run pytest -q` → 288 passed; `ruff check` clean on all plan files.

---
*Phase: 09-batch-tracking-ledger-integration*
*Completed: 2026-07-12*
