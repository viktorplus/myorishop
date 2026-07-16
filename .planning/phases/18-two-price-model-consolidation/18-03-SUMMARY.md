---
phase: 18-two-price-model-consolidation
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, jinja2, htmx, receipts]

# Dependency graph
requires: []
provides:
  - "Receipt slice (service + both routes + desktop/mobile templates) free of the catalog price field"
  - "register_receipt() no longer accepts catalog_raw and no longer writes payload.catalog_cents to the ledger"
  - "Both receipt routes (desktop + mobile wizard) free of the catalog Form param (Pitfall 1 fully swept)"
affects: [18-04, 18-07, 18-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "D-04: stop WRITING a retired ledger payload field going forward; never mutate/delete historical op rows that still carry it"
    - "Twin EMPTY_MONEY/RECEIPT_EMPTY_MONEY test fixtures when two service functions in the same test file diverge on accepted kwargs"

key-files:
  created: []
  modified:
    - app/services/receipts.py
    - app/routes/receipts.py
    - app/routes/mobile_receipts.py
    - app/templates/partials/receipt_form.html
    - app/templates/partials/receipt_rows.html
    - app/templates/mobile_partials/receipts_step_details.html
    - app/templates/mobile_partials/receipts_step_batch.html
    - app/templates/mobile_partials/receipts_step_confirm.html
    - tests/test_receipts.py
    - tests/test_mobile_receipts.py
    - tests/test_batches.py

key-decisions:
  - "New receipts stop writing payload.catalog_cents to the append-only ledger entirely (no payload kwarg at all), rather than writing an empty/null payload — simpler and still satisfies D-04 (8 historical payloads untouched)."
  - "lookup_prefill()'s product-source prices dict drops the 'catalog' key; its catalog-source (Dictionary/CatalogPrice) branch keeps its own 'catalog' key untouched since routes no longer read it and it's unrelated legacy source-matching logic outside this plan's scope."

patterns-established: []

requirements-completed: [PROD-05]

# Metrics
duration: 25min
completed: 2026-07-16
---

# Phase 18 Plan 03: Remove Catalog Price from Receipts Summary

**Catalog price field (`catalog`/`catalog_cents`) removed from the entire goods-receipt slice — desktop form, both receipt routes, and all 3 mobile wizard steps — while the append-only ledger's 8 historical receipt payloads and the D-15 receipt→card write-back stay untouched.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-16T11:05:19+02:00 (first task commit)
- **Completed:** 2026-07-16T11:24:53+02:00 (last task commit)
- **Tasks:** 3/3
- **Files modified:** 11 (8 declared in the plan + 3 test-file fixes for stray/dependent callers)

## Accomplishments
- `register_receipt()` no longer parses `catalog_raw`/writes `catalog_cents` anywhere — new receipts write no `payload.catalog_cents` to the ledger at all; the D-15 cost/sale card write-back is unchanged.
- Both receipt routes (`app/routes/receipts.py` desktop + `app/routes/mobile_receipts.py`'s entire 4-step wizard, 12 sites across 5 endpoints) are free of the `catalog` Form param — the mobile wizard surface CONTEXT.md had originally missed (Pitfall 1) is fully swept.
- Desktop form, receipt history table, and all 3 mobile wizard step templates no longer render/thread a catalog field; `price_history.html:22`'s catalog_cents audit-label branch is preserved verbatim (D-04).

## Task Commits

Each task was committed atomically:

1. **Task 1: Stop the receipt service parsing/writing catalog_cents** - `da44efd` (feat)
2. **Task 2: Drop the catalog Form param from both receipt routes** - `4117d43` (feat)
3. **Task 3: Remove the catalog field/column from the receipt templates** - `133b67b` (feat)

**Plan metadata:** (this commit, following this summary)

## Files Created/Modified
- `app/services/receipts.py` - `register_receipt()` drops `catalog_raw`; no more `catalog_cents` parse, product-create kwarg, price-sync dict entry, ledger payload, or lookup_prefill product-source key
- `app/routes/receipts.py` - `catalog` Form param removed from `GET /receipts/lookup` and `POST /receipts`; typed/fill_fields lists shrink to cost/sale
- `app/routes/mobile_receipts.py` - `catalog: str = Form("")` removed from all 5 wizard endpoints; `resolved_catalog`/`final_catalog` threading removed
- `app/templates/partials/receipt_form.html` - catalog `{% with %}` price block, `[name='catalog']` hx-include fragment, and dead `catalog-wrap` guard entry removed
- `app/templates/partials/receipt_rows.html` - «Каталог» history column removed
- `app/templates/mobile_partials/receipts_step_details.html`, `receipts_step_batch.html`, `receipts_step_confirm.html` - catalog input/hidden fields removed, cost/sale siblings kept
- `tests/test_receipts.py` - register_receipt callers stop passing `catalog_raw` (new `RECEIPT_EMPTY_MONEY` twin of `EMPTY_MONEY`, which stays for `create_product`); payload/prices/template assertions updated
- `tests/test_mobile_receipts.py` - wizard step assertions updated to stop asserting the removed catalog hidden input
- `tests/test_batches.py` - one stray `register_receipt(..., catalog_raw="")` call fixed (see Deviations)

## Decisions Made
- New receipts write **no** `payload` at all on the ledger `receipt` op (rather than an explicit `payload={"catalog_cents": None}`) — simplest way to satisfy "stop writing catalog_cents" while historical payloads with the key stay untouched (append-only, trigger-enforced).
- `lookup_prefill()`'s catalog-source (Dictionary/CatalogPrice) branch keeps its own internal `"catalog"` key in the returned `prices` dict — it's dead now that routes never read it, but touching that branch was out of this plan's declared scope (only the product-source branch was named in `<read_first>`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed a stray `register_receipt(..., catalog_raw="")` call in tests/test_batches.py**
- **Found during:** Task 3 verification (full `uv run pytest -q` run across the whole suite)
- **Issue:** `test_register_receipt_autogenerates_batch_name` (not in this plan's declared `<files>` for any task) called `register_receipt()` with `catalog_raw=""` twice — Task 1's signature change broke it with a `TypeError`.
- **Fix:** Removed the `catalog_raw=""` kwarg from both calls, mirroring every other register_receipt call site fixed in Task 1.
- **Files modified:** `tests/test_batches.py`
- **Verification:** `uv run pytest -q` — full 682-test suite green.
- **Committed in:** `133b67b` (Task 3 commit)

**2. [Rule 1 - Bug] Removed the dead `'catalog-wrap'` entry from receipt_form.html's oob-before-swap guard**
- **Found during:** Task 3 (template sweep)
- **Issue:** The `hx-on::oob-before-swap` JS guard listed `'catalog-wrap'` alongside `'cost-wrap'`/`'sale-wrap'` — after removing the catalog field this referenced a DOM id that no longer exists, a latent broken-guard bug (not directly enumerated in the plan's `<read_first>` line list, but on the same line block being edited).
- **Fix:** Dropped `'catalog-wrap'` from the array literal.
- **Files modified:** `app/templates/partials/receipt_form.html`
- **Verification:** `uv run pytest tests/test_receipts.py -q` green; manual read of the swap-guard logic confirms cost/sale guards are unaffected.
- **Committed in:** `133b67b` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes were direct fallout of the catalog-field removal (Task 1's signature change and Task 3's template sweep respectively); no scope creep beyond making the removal internally consistent.

## Issues Encountered
- A full-repo `ruff check .` surfaced one pre-existing, unrelated F401 (`tests/test_mobile_receipts.py:16` imports `add_entry` but never calls it) that predates this plan (confirmed via `git show 8a9a42e:tests/test_mobile_receipts.py`). Per the SCOPE BOUNDARY rule this was logged to `deferred-items.md` rather than fixed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `Product.catalog_cents` (the model column) is untouched, as required — Plan 18-04 removes it once every other reader/writer across the codebase is gone.
- The receipt slice is now a clean starting point for 18-04's migration: no receipt code path reads or writes `catalog_cents` anymore.
- No blockers.

## Known Stubs

None.

## Threat Flags

None — this plan only shrinks existing trust-boundary surface (fewer Form params); it introduces no new endpoints, auth paths, or schema changes.

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*
