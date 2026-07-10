---
phase: 03-goods-receipt-backup
plan: 02
subsystem: inventory
tags: [fastapi, sqlalchemy, htmx, jinja2, ledger, receipts, lookup]

# Dependency graph
requires:
  - phase: 02-catalog-dictionary-search
    provides: dictionary lookup 204 contract (D-23), name_input partial, price_change op machinery (CAT-04), _PRICE_FIELDS
  - plan: 03-01
    provides: register_receipt one-transaction write, receipt form partials, per-field oob-capable receipt_price_inputs.html
provides:
  - lookup_prefill(session, code) read helper — active product first, dictionary fallback, else None
  - GET /receipts/lookup — server decides fill vs 204; typed price fields excluded from fill (PD-10)
  - receipt_lookup.html fragment — name main-swap + per-field oob price fills via shared partials
  - price sync inside register_receipt — one price_change op per changed non-empty field (D-07)
  - parametrized hint in name_input.html (backward compatible)
affects: [03-03 backup, 04-sales, 06-reports]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-field hx-swap-oob fill: lookup response main-swaps #name-wrap and carries oob price fragments ONLY for fields that arrived empty (PD-10)"
    - "hx-on::oob-before-swap guard: in-flight oob fills discarded when the target field has operator input"
    - "Jinja default(...,true) hint parametrization keeps a shared partial backward compatible across callers"

key-files:
  created:
    - app/templates/partials/receipt_lookup.html
  modified:
    - app/services/receipts.py
    - app/routes/receipts.py
    - app/templates/partials/name_input.html
    - app/templates/partials/receipt_form.html
    - tests/test_receipts.py

key-decisions:
  - "_PRICE_FIELDS imported from app.services.catalog (plan offered import-or-mirror; import keeps one source of truth)"
  - "Dictionary-source lookup passes hint='' — name_input.html's default filter supplies the dictionary wording, so the fragment has one hint mechanism"
  - "oob-before-swap guard derives the input id from the wrap id (replace('-wrap','')) — one guard covers all three price fields"

patterns-established:
  - "Lookup fill fragments render through the SAME partials the form uses (name_input.html, receipt_price_inputs.html) — fragment and form markup can never drift (PD-6/PD-10)"

requirements-completed: [RCP-02]

# Metrics
duration: 10min
completed: 2026-07-09
---

# Phase 3 Plan 02: Receipt Lookup Pre-fill & Card Price Sync Summary

**Typing a code on /receipts/new auto-fills the name (dictionary) or name + empty price fields (existing card) via a 204-contract lookup, and saving a receipt for an existing product updates the card prices through price_change ops in the same transaction**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-09T05:58:11Z
- **Completed:** 2026-07-09T06:08:33Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- `lookup_prefill`: read-only pre-fill — active product first (name + current card prices), dictionary fallback (name only), unknown/soft-deleted code → None; zero session writes (T-3-05 gate holds)
- `GET /receipts/lookup` (D-03/RCP-02): server decides — typed name → 204; product match → name main-swap + oob fills ONLY for price fields that arrived empty after strip (PD-10); dictionary match → name only; unknown → 204
- Price sync in `register_receipt` (D-07): one price_change op per changed non-empty field, old value snapshotted before mutation, payload identical to catalog.update_product ({field, old_cents, new_cents}); empty inputs never clear card prices (PD-8); typed name never renames (PD-9); everything still lands in the single commit (WR-03)
- receipt_lookup.html renders through the same name_input.html / receipt_price_inputs.html partials the form uses — no duplicated field markup; card hint «Данные подставлены из карточки товара — новые цены обновят карточку.»
- Form wiring: debounced hx-get (300ms, hx-sync this:replace, hx-include name+prices) plus TWO swap-time guards (before-swap for #name-wrap, oob-before-swap for the three price wraps) — in-flight responses never destroy operator input
- 9-test RCP-02/D-07 executable contract ("lookup"/"price_sync" -k selectors); /dictionary/lookup and the product form untouched (test_dictionary.py green)

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests — lookup fill/204 branches + card price sync (RED)** - `dfc03b4` (test)
2. **Task 2: Card price sync inside register_receipt (GREEN price_sync)** - `11fa0c4` (feat)
3. **Task 3: /receipts/lookup endpoint + fill fragments + form wiring (GREEN lookup)** - `e6f67be` (feat)

## Files Created/Modified
- `app/services/receipts.py` - lookup_prefill read helper + D-07 price-sync branch in register_receipt
- `app/routes/receipts.py` - GET /receipts/lookup (204 contract, fill_fields = empty-after-strip subset)
- `app/templates/partials/receipt_lookup.html` - NEW lookup response fragment (name main-swap + oob price fills)
- `app/templates/partials/name_input.html` - hint parametrized via default filter, backward compatible
- `app/templates/partials/receipt_form.html` - lookup wiring on code input + before-swap/oob-before-swap guards
- `tests/test_receipts.py` - 9 new tests (3 price_sync service, 6 lookup web)

## Decisions Made
- `_PRICE_FIELDS` imported from app.services.catalog rather than mirrored locally — single source of truth, ruff clean
- Dictionary-source lookup sends `hint=""` and lets name_input.html's `default(..., true)` supply the dictionary wording — one hint mechanism, existing callers unchanged
- oob-before-swap guard computes the input id from the wrap id — one expression guards cost/sale/catalog uniformly

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## Known Stubs
None — lookup, price sync and guards are fully wired; nothing renders placeholder data.

## Threat Flags
None — new surface (GET /receipts/lookup trust boundary, stored names echoed into fragments) is exactly the plan's threat model; T-3-05 (routes write-free grep gate), T-3-06 (no `| safe`, autoescaped attributes only) and T-3-07 (204 on typed name + typed-field exclusion + swap guards) all verified by tests and grep gates.

## Authentication Gates
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Wave 2 sibling Plan 03-03 (backup) has zero file overlap with this plan — safe to merge/execute independently
- Human verify (end-of-phase): type a known product code on /receipts/new → after ~300ms name + empty prices fill with the card hint; type your own price first, then the code → your price survives (Pitfall 7 — swap guards not testable via TestClient)
- Phase 4 sales flow can rely on cards reflecting the latest intake prices (D-07 live)

## TDD Gate Compliance
Task 1 (tdd="true"): RED commit `dfc03b4` (test) — group selector `-k "lookup or price_sync"` failed (7/9 failing) before GREEN commits `11fa0c4`/`e6f67be` (feat). Two RED tests (empty-fields, name-ignored) passed at RED time by design: they codify Plan 03-01 baseline behavior as regression guards against the new price-sync branch, per the plan's own group-level RED gate (`test $? -ne 0`). Gate sequence satisfied.

## Self-Check: PASSED

- All 6 created/modified files exist on disk (verified with file checks)
- All 3 task commits found in git log (dfc03b4, 11fa0c4, e6f67be)
- Full suite: 98 passed; ruff clean
- Grep gates: routes write-free, no "| safe", receipt_lookup.html renders via name_input.html + receipt_price_inputs.html, single session.commit() in receipts service

---
*Phase: 03-goods-receipt-backup*
*Completed: 2026-07-09*
