---
phase: 09-batch-tracking-ledger-integration
verified: 2026-07-12T00:00:00Z
status: human_needed
score: 5/5 roadmap success criteria verified in code
overrides_applied: 0
human_verification:
  - test: "Receipt for a product with existing batches: enter its code, pick a warehouse, confirm the chooser lists «Пополнить партию» radios per open batch AND a «Новая партия» radio, and that the new-batch fields (срок/место/комментарий) appear only when «Новая партия» is selected (hx-on:change disabled-toggle idiom runs in-browser only)."
    expected: "Chooser forces an explicit top-up/new choice; new-batch fields hide/show and disabled inputs never submit on top-up."
    why_human: "Client-side hx-on:change DOM toggling + disabled-input submit behavior only observable in a real browser; TestClient asserts server HTML but not the live JS toggle."
  - test: "Sale of a 2-batch product: type the code, confirm the inline picker shows exactly four columns (Цена, Срок годности, Остаток, Комментарий) in earliest-expiry-first / NULL-last order, and that picking a batch fills the line price with the batch price and the hint «Цена подставлена из партии — можно изменить»."
    expected: "Four-column picker in D-07 order; picked batch price lands via hx-swap-oob; hint shown."
    why_human: "Real-time oob price swap and visual column rendering are browser-only; the price-fill precedence (skip card fill when batches exist) needs a live htmx round-trip to confirm the input is not blocked."
  - test: "Single-batch product at sale time auto-selects the only batch (pre-checked, highlighted) with the note «Партия выбрана автоматически — единственная», and the selection remains changeable."
    expected: "Auto-selected highlighted radio + muted note; still changeable."
    why_human: "Visual highlight (selected-batch tint) and auto-check state are browser-rendered."
  - test: "Per-batch oversell across sale/write-off/correction: pick a batch whose remaining is smaller than another batch of the same product, request more than that batch holds without confirming — confirm the warning is scoped to the picked batch's remaining (not the product total) and that «...всё равно» (confirm=1) then writes."
    expected: "Warn shows batch-scoped available; zero writes until confirm=1; confirm=1 commits."
    why_human: "Warn-but-allow confirm flow is an interactive two-step submit; visual warning copy and the confirm re-POST need human exercise (logic is unit-tested, UX flow is not)."
  - test: "Basket array-drift: add three sale lines, pick a distinct batch on each, delete the MIDDLE line, submit — confirm each remaining line's op is attributed to its own picked batch (and that a 422 re-render keeps every pick)."
    expected: "Deleting a middle row removes both its <tr>s; remaining lines keep correct batch attribution; picks survive a 422."
    why_human: "The delete-both-rows JS and hidden-array index alignment execute in the browser DOM; the drift guard is unit-tested at the service level but the live DOM removal path is browser-only."
  - test: "/history after migration: confirm a pre-Phase-9 (NULL batch_id) stock op renders the muted «До внедрения партий» second line, a batched op renders «Партия: {срок}{ — comment}», and price-change/product rows show no batch second line; confirm a return of a legacy sale shows «Возврат в партию: Остаток до внедрения партий»."
    expected: "Legacy label on pre-migration stock ops; batch line on batched ops; no line on audit rows; legacy return label read-only."
    why_human: "Visual read-time rendering of the muted second line and the read-only return label; requires migrated real data to confirm legacy attribution appears without a ledger rewrite."
---

# Phase 09: Batch Tracking & Ledger Integration Verification Report

**Phase Goal:** Stock is tracked at the batch level (per warehouse, expiry, price, comment) and every stock-affecting operation requires the operator to pick a specific batch.
**Verified:** 2026-07-12
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A product code can have multiple batches, each with warehouse, optional location, optional expiry, price, optional comment | ✓ VERIFIED | `Batch` model (`app/models.py:140-173`): `warehouse_id`, `location` (WH-02), `expiry` (LOT-03), `price_cents`, `comment` (LOT-04), no `deleted_at`. Born via `register_receipt` new-batch path (`app/services/receipts.py:201-213`) snapshotting sale price into `price_cents`. |
| 2 | At sale time the operator sees matching batches (price, expiry, remaining, comment) and must pick one before the line is added | ✓ VERIFIED | `batch_picker.html` renders exactly four columns (Цена/Срок годности/Остаток/Комментарий, location echoed in comment cell). `register_sale` (`sales.py:156-164`) rejects an empty/foreign batch per line with «Выберите партию.»; `record_operation` D-12 guard is the backstop. |
| 3 | Write-off, return, and stock-correction forms also require picking the specific batch | ✓ VERIFIED | `register_writeoff` (`writeoffs.py:86-88`) and `register_correction` (`corrections.py:72-74`) reject a missing/foreign batch. Return inherits the origin op's batch (`returns.py:88-113`, `_resolve_or_create_return_batch_id`) — no re-ask (D-08). |
| 4 | Over-removal warnings are scoped to the batch's remaining, not the product total | ✓ VERIFIED | Sales per-batch re-key `requested_by_batch` vs `Batch.quantity` (`sales.py:186-204`); write-off `qty > batch.quantity` (`writeoffs.py:92`); correction `-qty_delta > batch.quantity` (`corrections.py:107`). Same batch on two lines aggregated (Pitfall 8). |
| 5 | Existing v1.0 stock and sales history remain intact after migration; legacy ops show as a default legacy batch; totals/reports balance | ✓ VERIFIED | Migration 0008 seeds one legacy batch per SUM>0 product from the **ledger SUM** in plain SQL (`0008_batches.py:92-116`), not the cache. `/history` renders «До внедрения партий» at read time via LEFT OUTER JOIN (`operations.py:33-38`, `history_rows.html:29-39`) — no ledger rewrite. `rebuild_stock` invariant holds (legacy batch absorbs the NULL bucket, `ledger.py:139-197`). |

**Score:** 5/5 roadmap criteria verified in code. All 5 plans' frontmatter must-haves also confirmed present and substantive (see below).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py` | Batch model + Operation.batch_id | ✓ VERIFIED | `class Batch` with all columns, no `deleted_at`; `Operation.batch_id` nullable FK `fk_operations_batch_id_batches`, indexed |
| `alembic/versions/0008_batches.py` | batches table, operations.batch_id, legacy seed | ✓ VERIFIED | Native `op.add_column` (no batch mode); legacy seed from ledger SUM; downgrade reverses cleanly |
| `app/services/batches.py` | open_batches (D-07), legacy_batch, active_warehouses | ✓ VERIFIED | `nullslast(expiry.asc()), created_at.asc()`; quantity>0 filter; optional warehouse narrow |
| `app/services/ledger.py` | dual projection + D-12 mandatory guard | ✓ VERIFIED | `STOCK_AFFECTING_TYPES` frozenset; mandatory guard + ownership + batch-less audit reject; `batch.quantity = Batch.quantity + qty_delta` SQL-side |
| `app/services/receipts.py` | resolve-or-create + parse_optional_expiry | ✓ VERIFIED | new/top-up paths; server-side product+warehouse re-validation; price snapshot only on new batch |
| `app/services/sales.py` | 4th batch array + per-line resolve + per-batch oversell | ✓ VERIFIED | `non_blank_lines` pads `batch_ids` to len(codes); `requested_by_batch` re-key |
| `app/services/writeoffs.py` / `corrections.py` | scalar batch_id + batch-scoped checks | ✓ VERIFIED | correction count diff `counted - batch.quantity` (Pitfall 7); over-removal warn-but-allow |
| `app/services/returns.py` | batch inheritance + legacy lazy-create | ✓ VERIFIED | origin.batch_id or legacy_batch, lazy-creates frozen D-14 legacy batch when absent |
| `app/services/operations.py` | history_view outerjoin Batch | ✓ VERIFIED | `select(Operation, Product, Batch).outerjoin(Batch, ...)`; `"batch"` row key |
| `batch_picker.html` + form partials | shared picker, choosers, oversell partials, read-only return line | ✓ VERIFIED | 4-column picker; receipt chooser; writeoff/correction/return forms embed picker or read-only line |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `receipts.py register_receipt` | `record_operation batch_id` | `batch_id=batch.id` on receipt op | ✓ WIRED |
| `routes/receipts.py /receipts/batches` | `batches.py open_batches` | `open_batches(session, product.id, warehouse_id)` | ✓ WIRED |
| `sales.py register_sale` | `Batch.quantity` per-batch oversell | `requested_by_batch` vs `Batch.quantity` | ✓ WIRED |
| `batch_picker.html radio` | `/sales/batch-pick` | hx-get + hx-target `#batch-wrap-{row}` | ✓ WIRED |
| `corrections.py register_correction` | `Batch.quantity` | `qty_delta = counted - batch.quantity` | ✓ WIRED |
| `returns.py register_return` | `origin.batch_id / legacy_batch` | `_resolve_or_create_return_batch_id` | ✓ WIRED |
| `operations.py history_view` | `Batch` | `outerjoin(Batch, Operation.batch_id == Batch.id)` | ✓ WIRED |
| `ledger.py record_operation` | `Batch.quantity` | `Batch.quantity + qty_delta` same transaction | ✓ WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite | `uv run pytest -q` | 326 passed, 2 warnings, 48s | ✓ PASS |
| Migration replay: legacy seed from ledger SUM, triggers survive, UPDATE aborts | `test_migration_0008_seeds_legacy_batches_and_preserves_triggers` | qty==7 (ledger, not cache); 2 triggers; UPDATE ABORTs «append-only» | ✓ PASS |
| Migration reversible | `test_migration_0008_downgrade_reverses_cleanly` | batches dropped, batch_id dropped, 2 triggers survive round-trip | ✓ PASS |
| Dual projection | `test_record_operation_dual_projection` | product.quantity==5 and batch.quantity==5 | ✓ PASS |
| D-12 mandatory guard + ownership | `test_record_operation_batch_guard_is_mandatory`, `_rejects_foreign_batch` | ValueError raised | ✓ PASS |
| rebuild_stock invariant (legacy NULL bucket) | `test_rebuild_stock_invariant_holds_for_legacy_null_bucket` | no raise on consistent, raise on corrupted | ✓ PASS |

### Requirements Coverage

All 6 declared requirement IDs map to Phase 9 in REQUIREMENTS.md; none orphaned.

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|-------------|--------|----------|
| WH-02 | 02, 03 | Optional free-text storage-location tag per batch | ✓ SATISFIED | `Batch.location`; stored via receipt new-batch; echoed in picker comment cell |
| LOT-01 | 01, 02 | Multiple batches per code, each with expiry/price/warehouse/comment | ✓ SATISFIED | `Batch` model + receipt birth path |
| LOT-02 | 03 | Sale-time picker (price/expiry/remaining/comment), manual pick | ✓ SATISFIED | `batch_picker.html` + `register_sale` batch requirement |
| LOT-03 | 01, 02 | Optional expiry per batch | ✓ SATISFIED | `Batch.expiry`; `parse_optional_expiry` ISO validation |
| LOT-04 | 01, 02, 03 | Optional comment per batch, shown in picker | ✓ SATISFIED | `Batch.comment`; rendered in picker |
| LOT-05 | 04, 05 | Write-off/return/correction require batch selection | ✓ SATISFIED | writeoff/correction batch guard; return via inheritance; D-12 write-path backstop |

### Append-Only Ledger Invariant

✓ HOLDS. Migration 0008 uses native `op.add_column` (no Alembic batch/move-and-copy), so `operations_no_update` / `operations_no_delete` triggers survive (asserted: trigger count == 2 and `UPDATE operations` aborts, post-upgrade and post-downgrade round-trip). `batch_id` is set at INSERT time only via the single write path `record_operation`; `Batch.quantity` is a recomputable cache incremented in the same transaction — no operations row is ever mutated. Legacy attribution is resolved display-side (read-time LEFT OUTER JOIN), never by rewriting ledger rows.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/routes/receipts.py` | 189-199 | `except Exception:` block calls `_form_extras(session, ...)` (re-queries the session) with NO preceding `session.rollback()`, unlike the sibling writeoffs.py:139 and returns.py which do roll back | ⚠️ Warning (advisory, from 09-REVIEW.md Critical) | On a commit-time `OperationalError` the session would be in a failed-transaction state and the re-query could raise, surfacing a raw 500 instead of the RU block error. Edge-case only (DB-level commit failure); happy path and all validation/oversell paths are unaffected and tested. |

No debt markers (TODO/FIXME/XXX/HACK/PLACEHOLDER) in any phase source file.

### Human Verification Required

Automated verification is complete and green: the goal's server-side enforcement (batch-required write path, per-batch oversell, migration integrity, legacy attribution) is fully implemented and unit/route tested (326 passed). The items below are browser-only HTMX/UX behaviors the plans designated as UAT gates — they cannot be verified by grep or TestClient because they depend on live client-side JS (hx-on:change toggles, oob swaps, DOM row deletion) and visual rendering.

1. **Receipt chooser top-up/new toggle** — new-batch fields hide/show via `hx-on:change` + disabled-input idiom in a real browser (UAT gate 1).
2. **Sale 2-batch picker** — four columns in D-07 order + oob batch-price fill lands (UAT gates 2-3).
3. **Single-batch auto-select** — pre-checked, highlighted, «выбрана автоматически» note (UAT gate 4).
4. **Per-batch oversell warn-but-allow** — batch-scoped copy + confirm=1 two-step flow across sale/write-off/correction (UAT gates 5-6).
5. **Basket array-drift on middle-row delete** — both `<tr>`s removed, attribution preserved, 422 keeps picks (UAT gate for Pitfall 2/3).
6. **/history legacy attribution** — «До внедрения партий» on pre-migration ops, batch line on batched ops, read-only legacy return label (UAT gates 7-8).

### Gaps Summary

No blocking gaps. All five ROADMAP success criteria are achieved in the codebase, all six requirement IDs are satisfied, the migration is reversible, the append-only ledger invariant holds, and the full suite passes (326). One advisory Warning (receipts route missing a defensive `session.rollback()` on the commit-failure path) is carried from 09-REVIEW.md — real but edge-case, not goal-blocking. Status is `human_needed` solely because six browser-only UAT interactions remain for a human to confirm; the server-side goal enforcement is otherwise fully verified.

---

_Verified: 2026-07-12_
_Verifier: Claude (gsd-verifier)_
