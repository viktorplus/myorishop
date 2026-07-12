---
phase: 10-warehouse-transfers-expiry-reporting
verified: 2026-07-12T19:30:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 10: Warehouse Transfers & Expiry Reporting Verification Report

**Phase Goal:** Operators can move stock between warehouses without losing cost/price history, and can see which batches are nearing or past their expiry date
**Requirements:** WH-03 (warehouse transfers), LOT-06 (expiry report)
**Verified:** 2026-07-12T19:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria + PLAN must_haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | "transfer" op type registered in OPERATION_TYPES, OPERATION_TYPE_LABELS («Перемещение»), and STOCK_AFFECTING_TYPES | VERIFIED | `app/models.py:40` (`"transfer"` in `OPERATION_TYPES` tuple), `app/models.py:66` (`"transfer": "Перемещение"`), `app/services/ledger.py:19` (`"transfer"` in `STOCK_AFFECTING_TYPES` frozenset) |
| 2 | register_transfer() writes exactly two `transfer` ledger rows (source -qty, dest +qty) in one transaction via record_operation(commit=False) x2 + one commit | VERIFIED | `app/services/transfers.py:127-147`; `tests/test_transfers.py::test_transfer_writes_two_rows` passes |
| 3 | Destination batch created fresh, copying source's price_cents/expiry/comment/location/name, differing only in warehouse_id, is_legacy=0, new id | VERIFIED | `app/services/transfers.py:113-125` (direct-assignment copy, `price_cents=source.price_cents` — never `or`); `tests/test_transfers.py::test_dest_batch_inherits_history` passes |
| 4 | Product.quantity nets to zero across the pair; rebuild_stock invariant holds | VERIFIED | `tests/test_transfers.py::test_transfer_projections`, `test_rebuild_invariant_after_transfer` pass |
| 5 | Over-transfer (qty > source.quantity) returns oversell payload with ZERO writes unless confirm=="1"; same-warehouse/foreign-warehouse/foreign-batch transfers rejected before any write | VERIFIED | `app/services/transfers.py:76-105`; `test_over_qty_confirm_gate`, `test_reject_same_warehouse`, `test_reject_tampered_ids` pass |
| 6 | Operator can open /transfers, type a code, see open batches (all warehouses) via shared batch_picker.html | VERIFIED | `app/routes/transfers.py` GET /transfers, /transfers/lookup (queries `open_batches` across all warehouses, no `warehouse_id` narrowing); `transfer_batch_wrap.html` includes `batch_picker.html`; `test_transfer_lookup_fills` passes |
| 7 | Picking a source batch reveals dest-warehouse `<select>` excluding source's own warehouse | VERIFIED | `app/routes/transfers.py:_dest_warehouses()` filters `active_warehouses` minus `source.warehouse_id`; `transfer_batch_wrap.html:28-40` renders select only when `selected_batch_id and _wh_list`; `test_transfer_batch_pick_dest_excludes_source` asserts dest select present, source warehouse absent |
| 8 | POST /transfers calls register_transfer; success shows «Перемещение сохранено» + oob recent-list refresh; over-qty shows warn block; validation errors re-render at 422 with selection re-echoed | VERIFIED | `app/routes/transfers.py:110-195`; `test_transfer_post_moves_stock`, `test_transfer_post_oversell_then_confirm` pass; 422 branch re-echoes `selected_batch`/`warehouses` |
| 9 | Completed transfer appears at /history labelled «Перемещение» with both directions (source -qty, dest +qty) | VERIFIED | `test_transfer_in_history` asserts "Перемещение" and "-3" in `/history` response; label auto-flows from `OPERATION_TYPE_LABELS` global |
| 10 | transfers router registered in app/main.py; «Перемещение» nav link in base.html | VERIFIED | `app/main.py:22,52` (`transfers` import + `include_router(transfers.router)`); `app/templates/base.html:25` (`<a href="/transfers"...>Перемещение</a>`) |
| 11 | expiring_batches(session) returns only open (qty>0), non-NULL-expiry batches, joined to Product+Warehouse, earliest-first | VERIFIED | `app/services/batches.py:42-56`; `tests/test_batches.py::test_expiring_batches_filter_and_order` passes |
| 12 | GET /reports/expiry renders read-only page listing product/warehouse/expiry/qty/price/comment, no filters | VERIFIED | `app/routes/reports.py:170-178`; `app/templates/pages/reports_expiry.html` (7-column table, no period_filter include); `test_expiry_report_page` passes |
| 13 | Expired batches (expiry < LOCAL today) flagged «просрочено» but stay in the earliest-first list; empty state renders muted row; reports landing links to it | VERIFIED | `app/routes/reports.py:176` (`ZoneInfo(settings.display_tz)`, not UTC); `reports_expiry.html:28-30`; `reports_landing.html:5` (`/reports/expiry` link); `test_expiry_report_page`, `test_expiry_report_page_empty_state` pass |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/services/transfers.py` | register_transfer() + recent_transfers() | VERIFIED | 166 lines, both functions present, full validation chain, single-write-path via `record_operation` |
| `app/models.py` | "transfer" in OPERATION_TYPES + label | VERIFIED | Confirmed at lines 40, 66 |
| `app/services/ledger.py` | "transfer" in STOCK_AFFECTING_TYPES | VERIFIED | Confirmed at line 19 |
| `tests/test_transfers.py` | WH-03 service + route test suite | VERIFIED | 440 lines, 16 tests (10 service-level + 6 route/integration), all pass |
| `app/routes/transfers.py` | GET /transfers, /lookup, /batch-pick, POST /transfers | VERIFIED | All 4 routes present; literal routes declared before any parameterized route (none added) |
| `app/templates/partials/transfer_form.html` | whole-swapped transfer form | VERIFIED | posts to /transfers, target #transfer-form-wrap, includes batch picker + qty, no reason/note fields |
| `app/main.py` | include_router(transfers.router) | VERIFIED | Confirmed |
| `app/templates/base.html` | «Перемещение» nav link | VERIFIED | Confirmed at line 25 |
| `app/services/batches.py` | expiring_batches() helper | VERIFIED | Lines 42-56, portable ORM `select()`, no SQLite-specific SQL |
| `app/routes/reports.py` | GET /reports/expiry handler | VERIFIED | Lines 170-178 |
| `app/templates/pages/reports_expiry.html` | read-only report + expired marker + empty state | VERIFIED | Contains «просрочено» marker and muted empty-state paragraph |
| `app/templates/pages/reports_landing.html` | «Сроки годности» link | VERIFIED | Confirmed at line 5 |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `transfers.py register_transfer` | `ledger.py record_operation` | two `record_operation(type_="transfer", commit=False)` calls + one commit | WIRED | Confirmed in source, exercised by tests |
| `transfers.py register_transfer` | `models.py Batch` | `dest = Batch(..., price_cents=source.price_cents, ...)` before write | WIRED | Confirmed, `session.add(dest)` precedes both `record_operation` calls (autoflush ordering) |
| `transfers.py register_transfer` | `batches.py active_warehouses` | dest warehouse validated against active ids, != source | WIRED | Confirmed lines 85-90 |
| `routes/transfers.py POST /transfers` | `services/transfers.py register_transfer` | direct call with all form fields | WIRED | Confirmed line 132-140; route test asserts stock actually moves |
| `routes/transfers.py GET /transfers/batch-pick` | `services/batches.py active_warehouses/open_batches` | re-query + `_dest_warehouses()` | WIRED | Confirmed lines 91, 105 |
| `app/main.py` | `routes/transfers.py router` | `include_router(transfers.router)` | WIRED | Confirmed; route tests hit live app via `client` fixture and succeed |
| `routes/reports.py reports_expiry_page` | `services/batches.py expiring_batches` | `context = {"rows": expiring_batches(session), ...}` | WIRED | Confirmed line 177 |
| `templates/pages/reports_expiry.html` | `today` | `{% if row.batch.expiry < today %}` | WIRED | Confirmed line 28; local-date computed via `settings.display_tz`, test confirms marker appears only on past-expiry row |
| `templates/pages/reports_landing.html` | `/reports/expiry` | landing link | WIRED | Confirmed line 5 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `transfer_rows.html` (`recent-transfers`) | `transfers` | `recent_transfers(session)` — real DB query joined to Operation/Product, filtered `type=="transfer" AND qty_delta<0` | Yes | FLOWING |
| `reports_expiry.html` | `rows` | `expiring_batches(session)` — real DB query joined to Batch/Product/Warehouse with `quantity>0` and `expiry.is_not(None)` filters | Yes | FLOWING |
| `transfer_batch_wrap.html` dest select | `warehouses` | `_dest_warehouses()` — real `active_warehouses(session)` query filtered by source warehouse id | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full suite passes | `uv run pytest -q` | 358 passed, 3 warnings, 54.84s | PASS |
| Phase-specific suites pass | `uv run pytest tests/test_transfers.py tests/test_batches.py tests/test_reports.py -q` | 73 passed | PASS |
| Ruff clean on touched files | `uv run ruff check app/services/transfers.py app/routes/transfers.py app/services/batches.py app/routes/reports.py tests/test_transfers.py` | All checks passed! | PASS |
| Named test: transfer writes real Batch.quantity changes | `test_transfer_post_moves_stock` asserts `source.quantity == 5` after transferring 3 of 8, and a new dest batch with `quantity == 3` exists in the target warehouse | Confirmed via source read | PASS |
| No Alembic migration added this phase (as claimed) | `git log --oneline -- alembic/versions/` | Last migration is 0009 (phase 9); no phase-10 migration file exists | PASS |

### Probe Execution

No probes declared for this phase (no `scripts/*/tests/probe-*.sh` referenced in PLAN/SUMMARY files; not a migration/CLI tooling phase). Step 7c: SKIPPED (no probes declared).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| WH-03 | 10-01, 10-02 | Warehouse transfers with preserved cost/price history | SATISFIED | Full service + route + UI + tests, all passing |
| LOT-06 | 10-03 | Expiry report, read-only, earliest-first, expired flagged | SATISFIED | Full helper + route + template + tests, all passing |

No orphaned requirements — REQUIREMENTS.md/PLAN frontmatter requirements fully accounted for.

### Anti-Patterns Found

None. Scanned all phase-touched files (`app/services/transfers.py`, `app/routes/transfers.py`, `app/services/batches.py`, `app/routes/reports.py`, all six transfer templates, `reports_expiry.html`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|placeholder|not yet implemented|coming soon` — zero matches.

### Human Verification Required

None. All truths were verifiable via static analysis, automated tests, and direct source inspection. The plans' own `<verification>` sections listed human-check items (visual confirmation of the dest-select exclusion, oversell flow, expiry marker appearance) as deferred to end-of-phase per `human_verify_mode=end-of-phase`, but every one of those behaviors is also covered by an automated route/integration test that exercises the same code path (e.g., `test_transfer_batch_pick_dest_excludes_source` asserts the exact HTML exclusion the human check would eyeball; `test_expiry_report_page` asserts the exact marker placement). No behavior remains that only a human can confirm.

### Gaps Summary

No gaps found. Both WH-03 and LOT-06 are delivered end-to-end: service logic, route wiring, templates, navigation, and test coverage all verified directly against the codebase (not inferred from SUMMARY.md claims). The full 358-test suite passes, phase-specific ruff checks are clean, no debt markers exist in touched files, and no Alembic migration was introduced (consistent with the "no schema change needed" claim, confirmed against `operations.type` being an unconstrained `String(20)` and the destination batch being an ordinary `batches` row).

---
*Verified: 2026-07-12T19:30:00Z*
*Verifier: Claude (gsd-verifier)*
