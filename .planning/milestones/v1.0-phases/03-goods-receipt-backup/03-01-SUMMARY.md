---
phase: 03-goods-receipt-backup
plan: 01
subsystem: inventory
tags: [fastapi, sqlalchemy, htmx, jinja2, ledger, receipts]

# Dependency graph
requires:
  - phase: 01-foundation-ledger-core
    provides: record_operation single write path, append-only operations ledger, money/UUID/UTC helpers
  - phase: 02-catalog-dictionary-search
    provides: catalog service (parse_optional_cents, duplicate-code handling, soft delete), name_input partial, htmx 422 config
provides:
  - register_receipt one-transaction write (validate -> auto-create -> receipt op -> single commit)
  - recent_receipts read helper (last 10, newest first)
  - GET /receipts/new page + POST /receipts save-and-next form loop (200 fresh form / 422 echo)
  - receipt form partials (receipt_form, per-field receipt_price_inputs, receipt_rows with hx-swap-oob)
  - nav link «Приход»
affects: [03-02 lookup+price-sync, 03-03 backup, 04-sales, 06-reports]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Save-and-next HTMX loop: POST returns the whole form partial (outerHTML swap) with hx-on::load focus hook"
    - "Per-field oob-capable fragment (receipt_price_inputs.html) for future lookup fills (PD-10)"
    - "Recent-list partial with stable id + conditional hx-swap-oob riding on the POST success response"

key-files:
  created:
    - app/services/receipts.py
    - app/routes/receipts.py
    - app/templates/pages/receipt_form.html
    - app/templates/partials/receipt_form.html
    - app/templates/partials/receipt_price_inputs.html
    - app/templates/partials/receipt_rows.html
    - tests/test_receipts.py
  modified:
    - app/main.py
    - app/templates/base.html

key-decisions:
  - "recent_receipts implemented in Task 2 instead of Task 3: the RED test module imports it at module level, so Task 2's -k filtered run could not collect without it"
  - "Quantity validated via str.isdigit() + int > 0 — rejects '', '0', '-2', 'abc', '1.5' with one RU message (D-01 strict positive integer)"
  - "Typed name ignored for existing products — renames only via /products/{id}/edit (RESEARCH Open Question 1 / PD-9 preview)"

patterns-established:
  - "Receipt op payload carries catalog_cents (D-06); unit_cost/unit_price live in op columns"
  - "include_oob_rows flag in form-partial context controls whether the oob recent list rides along (True only on POST success)"

requirements-completed: [RCP-01]

# Metrics
duration: 8min
completed: 2026-07-09
---

# Phase 3 Plan 01: Goods Receipt Entry Loop Summary

**Save-and-next goods receipt entry at /receipts/new: one immutable ledger receipt op per save, product auto-creation for unknown codes in the same transaction, and a last-10 receipts list refreshed out-of-band**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-09T05:43:26Z
- **Completed:** 2026-07-09T05:51:57Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments
- `register_receipt`: single-transaction write composing Phase 1–2 machinery — validation (RU errors, zero writes on failure), active-only product lookup, auto-create with `product_created` op (D-05), receipt op with price snapshot (D-01/D-06), exactly one `session.commit()` (WR-03), IntegrityError race translated to the shared RU duplicate-code error (WR-04)
- Save-and-next loop (D-02): POST /receipts returns a fresh form partial with «Приход сохранён: … — N шт.» and an explicit `hx-on::load` focus hook back to «Код» (autofocus does not fire in swapped content — Pitfall 6)
- Recent receipts (D-04): last 10, newest first (`created_at desc, seq desc`), rendered under the form and refreshed via `hx-swap-oob` on every successful save; RU empty state per UI-SPEC
- 15-test RCP-01 executable contract (service transaction, validation, soft-delete edge, web response shapes, oob refresh, nav)
- Prices optional (PD-8): empty strings → NULL op columns and NULL `payload.catalog_cents`; product card prices untouched for existing products (card sync is Plan 03-02)

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests — receipt transaction, validation, save-and-next shape, recent list (RED)** - `f86005f` (test)
2. **Task 2: Receipt service + routes + form page (GREEN core)** - `55686ff` (feat)
3. **Task 3: Recent receipts partial + hx-swap-oob refresh + nav link** - `ec5e49c` (feat)

## Files Created/Modified
- `app/services/receipts.py` - register_receipt (one-transaction write) + recent_receipts; QTY_ERROR constant
- `app/routes/receipts.py` - thin routes GET /receipts/new, POST /receipts (200/422 form partial)
- `app/templates/pages/receipt_form.html` - page: h1 «Приход товара» + form partial + recent list
- `app/templates/partials/receipt_form.html` - swappable form with stable #receipt-form-wrap, success line, focus hook, conditional oob rows
- `app/templates/partials/receipt_price_inputs.html` - single-source per-field price fragment (oob-capable for 03-02)
- `app/templates/partials/receipt_rows.html` - #recent-receipts table with RU headers, cents/local_dt filters
- `app/main.py` - receipts router registered
- `app/templates/base.html` - nav «Приход» between «Товары» and «Справочник»
- `tests/test_receipts.py` - 15-test RCP-01 contract

## Decisions Made
- recent_receipts moved into Task 2 (see Deviations) — test module imports both service functions at module level
- Quantity parse: `qty_raw.strip().isdigit() and int(...) > 0` — one strict rule, one RU message
- Existing product's typed name is silently ignored (no rename through receipts) per plan note on RESEARCH Open Question 1

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] recent_receipts implemented in Task 2 instead of Task 3**
- **Found during:** Task 2 (GREEN core verification)
- **Issue:** tests/test_receipts.py imports `recent_receipts` at module level (per plan Task 1 spec), so pytest collection failed with ImportError, blocking the Task 2 verify command `pytest -k "not recent and not nav"`
- **Fix:** Added the full `recent_receipts` implementation (plan Task 3 item 1, verbatim spec) to app/services/receipts.py during Task 2
- **Files modified:** app/services/receipts.py
- **Verification:** Tests 1–10 collected and passed; test 11 passed after Task 3 wiring
- **Committed in:** 55686ff (Task 2 commit)

**2. [Rule 1 - Bug] ruff E501 line-length violations in the RED test file**
- **Found during:** Task 2 (ruff gate)
- **Issue:** 4 lines in tests/test_receipts.py (written in Task 1) exceeded 100 chars
- **Fix:** Extracted long RU assertion strings to variables; reflowed two data dicts
- **Files modified:** tests/test_receipts.py
- **Verification:** `uv run ruff check .` clean; tests still pass
- **Committed in:** 55686ff (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug/lint)
**Impact on plan:** Both fixes required to satisfy the plan's own verify gates. No scope creep — recent_receipts is verbatim plan Task 3 spec, just landed one commit earlier.

## Issues Encountered
None

## Known Stubs
None — the lookup wiring (`hx-get` on the code input) and card price sync are intentionally absent per plan scope; Plan 03-02 (wave 2) adds them.

## Threat Flags
None — new surface (POST /receipts trust boundary, stored names echoed into HTML) is exactly the plan's threat model; T-3-01/T-3-02/T-3-03 mitigations verified by tests and grep gates (no `| safe`, routes write-free, single write path).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ready for Plan 03-02 (lookup pre-fill + card price sync): receipt_price_inputs.html is per-field and oob-capable; route-order comment reserves /receipts/lookup
- Human verify (end-of-phase): confirm cursor lands in «Код» after save without a click (DOM focus not testable via TestClient)

## TDD Gate Compliance
Task 1 (tdd="true"): RED commit `f86005f` (test) confirmed failing before GREEN commit `55686ff` (feat). Gate sequence satisfied.

## Self-Check: PASSED

- All 7 created files exist on disk (verified with file checks)
- All 3 task commits found in git log (f86005f, 55686ff, ec5e49c)
- tests/test_receipts.py is 328 lines (min_lines 120 satisfied)
- Full suite: 89 passed; ruff clean; grep gates: single session.commit(), routes write-free, no "| safe"

---
*Phase: 03-goods-receipt-backup*
*Completed: 2026-07-09*
