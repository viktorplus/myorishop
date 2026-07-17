---
phase: 22-sales-page-rebuild
plan: 05
subsystem: ui
tags: [fastapi, jinja2, htmx, sales, customers]

# Dependency graph
requires:
  - phase: 22-01
    provides: xfail-marked regression tests for SALE-03/04/05/06 and D-01..D-12, and the shipped customer_picker.html search-row contract this plan reuses
affects: [22-03 (recent_sales customer column, wave 3, same test file), 22-04, 22-06, 22-07]
provides:
  - "_CUSTOMER_MODES allow-list + _customer_context() shared builder in app/routes/sales.py"
  - "GET /sales/customer-mode endpoint, declared before POST /sales"
  - "3-way radio customer header (Новый/Существующий/Без покупателя (розница)) in sale_customer.html"
  - "D-10 guard on POST /sales blocking a silent walk-in when new-customer fields are typed but not saved"
  - "D-12 fix: all five sale_customer.html render paths resolve `selected` server-side"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stateful radio mode-swap: one hx-get on a fieldset with hx-include=\"#customer-header input\", server re-renders the active mode and echoes the other two modes as hidden inputs (form=\"sale-form\" throughout) so state round-trips indefinitely"
    - "Shared context builder (_customer_context) merged first, caller's own errors/lines/focus_code keys follow, so the builder's absence of an errors key never clobbers a caller's real errors"

key-files:
  created: []
  modified:
    - app/routes/sales.py
    - app/templates/partials/sale_customer.html
    - tests/test_sales.py

key-decisions:
  - "customer_id_keep is a caller-supplied top-level context key, separate from _customer_context's own resolved customer_id — the raw pre-resolution id must survive a switch away from existing mode, but _customer_context's returned customer_id is empty whenever mode != existing"
  - "Gave form=\"sale-form\" to every input inside #customer-header (mode radios, new-customer fields, and their inactive-echo hidden twins), not just #customer-id-input, so the D-10 guard actually receives customer_mode/name/surname/consultant_number on a real browser basket submit, not only on a raw-POST test"
  - "sale_customer_create's 3 branches also route through _customer_context (mode \"new\" on failure so typed fields stay visible, mode \"existing\" on success so the new chip shows) — this was implicit in Task 1/3's text but not explicitly enumerated in the plan's five-path list"

requirements-completed: [SALE-03, SALE-04, SALE-05, SALE-06]

# Metrics
duration: ~35min
completed: 2026-07-17
---

# Phase 22 Plan 05: Sale Customer Header Rebuild Summary

**Restructured the sale-form customer header into an explicit 3-way radio (Новый/Существующий/Без покупателя), added a shared `_customer_context()` builder used by all five render paths, and closed two verified defects — D-10 (silent walk-in on unsaved new-customer fields) and D-12 (chip disappearing on a 422/oversell re-render).**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3/3 completed
- **Files modified:** 3 (`app/routes/sales.py`, `app/templates/partials/sale_customer.html`, `tests/test_sales.py`)

## Accomplishments

- `_CUSTOMER_MODES` allow-list + `_customer_context()` shared builder, plus a new literal `GET /sales/customer-mode` endpoint declared before `POST /sales`
- `sale_customer.html` restructured into a `fieldset`+`legend` radio group (Новый/Существующий/Без покупателя (розница)) with `hx-include="#customer-header input"` mandatory on the radio's `hx-get`, resolving the D-03 state-preservation contract — every mode's typed values survive an arbitrary number of switches
- D-10 guard on `POST /sales`: `customer_mode=="new"` + empty `customer_id` + any of the 3 fields non-blank now returns 422 with a message naming the exact "Добавить покупателя" button, instead of silently writing a walk-in sale
- D-12 fix: all five `sale_customer.html` render paths (`sale_new_page`, `sale_create`'s exception/oversell-or-below_minimum/validation-errors branches, and the success branch) merge `_customer_context(...)` so `selected` resolves server-side on every path — the chip no longer disappears on a 422/oversell re-render while the hidden `customer_id` input still carries it
- 8 of this plan's 10-slot xfail budget removed (5 `customer_mode` tests + `new_customer_field_set_is_exactly_three` in Task 2; `chip_survives_422_rerender` + `new_customer_requires_button_returns_422` in Task 3) — the other 2 the plan originally budgeted for (`test_web_sale_picker_data_attrs`, `test_web_sale_new_customer_blank_fields_still_walks_in`) had already lost their markers in 22-01 per documented deviations there, so `tests/test_sales.py -q` now reports exactly 3 xfailed (22-03's `recent_sales` trio, wave 3) — the correct wave-2 end state

## Task Commits

Each task was committed atomically:

1. **Task 1: `_CUSTOMER_MODES`, `_customer_context`, `GET /sales/customer-mode`** - `f627d38` (feat)
2. **Task 2: Restructure `sale_customer.html` into 3 radio-driven modes** - `46260ae` (feat)
3. **Task 3: Route every `sale_create` branch through `_customer_context`; add D-10 guard** - `677878a` (feat)

## Files Created/Modified

- `app/routes/sales.py` - `_CUSTOMER_MODES`, `_customer_context()`, `GET /sales/customer-mode`, D-10 guard on `sale_create`, all five render paths + `sale_customer_create`'s three branches merged through the shared builder
- `app/templates/partials/sale_customer.html` - restructured into 3 radio-driven modes with `form="sale-form"` on every input (active + inactive-echo) so mode/typed-fields reach `POST /sales`
- `tests/test_sales.py` - removed 8 `@pytest.mark.xfail` marker lines this plan owns (marker lines only, no test body edits)

## Decisions Made

- **`customer_id_keep` is caller-supplied, not part of `_customer_context`'s return contract.** `_customer_context`'s own `customer_id` key is the RESOLVED id (empty whenever `mode != "existing"`) — correct for `#customer-id-input`, but wrong for the inactive-mode hidden echo, which must carry the raw pre-resolution id forward so a later switch back to "existing" can still resolve it. Each caller computes `raw_id` and adds `"customer_id_keep": raw_id` alongside `_customer_context`'s spread. This is a deliberate deviation from `22-RESEARCH.md`'s Pattern-1 sketch, which used `{{ customer_id or '' }}` for the inactive echo — that would have silently lost the "existing" mode's pick on the very first switch away from it, which is exactly the D-03 defect this plan exists to close.
- **`form="sale-form"` on every `#customer-header` input, not just the ones `sale_create` explicitly reads.** `22-RESEARCH.md` Pitfall 5 calls this "either is fine" (echo-only fields are ignored by `sale_create` if unrecognized); this plan chose the more complete/consistent option so the mode radios and the "new" mode's active fields — which `sale_create`'s new D-10 guard genuinely needs — actually reach the server on a real browser submit, not only in a raw-POST test.
- **`sale_customer_create`'s three branches also route through `_customer_context`.** The plan's Task 3 explicitly lists "Also merge it into `sale_customer_create`'s paths" without enumerating them; implemented as mode `"new"` on both failure branches (typed fields stay visible) and mode `"existing"` on the success branch (the newly-created customer shows as the selected chip, replacing the old behavior of just returning `{"selected": customer, ...}` with no mode).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_customer_context`'s inactive-mode hidden echo would have lost the "existing" pick on the first switch**
- **Found during:** Task 2 (writing the template against Task 1's endpoint)
- **Issue:** `22-RESEARCH.md`'s Pattern-1 sketch template used `{{ customer_id or '' }}` for the `customer_id_keep` hidden echo, but `_customer_context`'s `customer_id` return key is always `""` when `mode != "existing"` (by the plan's own Task 1 spec) — so switching away from "existing" would always echo an empty `customer_id_keep`, contradicting the D-03 round-trip test.
- **Fix:** `sale_customer_mode` (and every other caller) now separately passes a caller-computed `customer_id_keep` (the raw pre-resolution id) as a sibling context key, and the template reads `{{ customer_id_keep | default('') }}` for the inactive echo instead of reusing `_customer_context`'s resolved `customer_id`.
- **Files modified:** `app/routes/sales.py`, `app/templates/partials/sale_customer.html`
- **Verification:** `test_web_sale_customer_mode_roundtrip_preserves_both_modes` passes (`uv run pytest tests/test_sales.py -k customer_mode_roundtrip -x`)
- **Committed in:** `46260ae` (Task 2 commit)

**2. [Rule 1 - Bug] Task 1's own generic-exception fallback still hand-wrote a literal `"customer_id": ""` context dict**
- **Found during:** Task 3 verification (`grep -c '"customer_id": ""' app/routes/sales.py` returned 1, not 0)
- **Issue:** `sale_customer_mode`'s `except Exception` fallback (added in Task 1) built its 422 context by hand instead of going through `_customer_context`, tripping the plan's own D-12 tripwire grep even though this endpoint isn't one of the "five render paths" the criterion names.
- **Fix:** Replaced the hand-built dict with `{**_customer_context(session, "existing", "", {}), "customer_id_keep": "", "errors": {...}}`, matching every other caller.
- **Files modified:** `app/routes/sales.py`
- **Verification:** `grep -c '"customer_id": customer_id\|"customer_id": ""' app/routes/sales.py` returns 0/0
- **Committed in:** `677878a` (Task 3 commit)

**3. [Rule 1 - Bug] Two source comments contained the literal tripwire substrings, tripping the plan's own acceptance grep**
- **Found during:** Task 3 verification
- **Issue:** Two docstring/inline comments referenced the exact strings `"customer_id": customer_id` and (transitively) `"customer_id": ""` while explaining what NOT to write, which made `grep -c '"customer_id": customer_id' app/routes/sales.py` return 2 instead of 0 even though no code matched.
- **Fix:** Reworded both comments to describe the anti-pattern without reproducing its literal text (e.g. "a bare customer-id-only literal" instead of quoting the dict entry).
- **Files modified:** `app/routes/sales.py`
- **Verification:** `grep -c '"customer_id": customer_id' app/routes/sales.py` returns 0
- **Committed in:** `677878a` (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs discovered while implementing/verifying this plan's own acceptance criteria)
**Impact on plan:** All three fixes were necessary for the plan's own stated D-03/D-12 correctness contracts and acceptance criteria to actually hold; no scope creep beyond this plan's `files_modified`.

## Issues Encountered

None beyond the auto-fixed items above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `tests/test_sales.py -q` reports 0 failed, exactly 3 xfailed (the `recent_sales` trio owned by 22-03, wave 3), 0 xpassed — the correct wave-2 end state per this plan's "Test-file ownership" note. 22-03 (wave 3) is expected to remove those last 3 markers.
- Full suite: `uv run pytest -q` → 836 passed, 13 xfailed, 0 failed (13 xfailed includes this plan's remaining 3 plus other phases' unrelated legitimate xfails).
- `app/services/sales.py` (`register_sale`) is untouched, per D-10's explicit constraint — `POST /sales/customer` remains the sole customer-creation path.
- Criterion-5 guardrail tests (oversell, below-minimum, both-warnings-stack, missing-batch-pick, batch-pick-re-echo) pass unedited.
- Mobile customer-header parity (D-04, `mobile_partials/sale_customer.html`) is explicitly out of this plan's scope (not in `files_modified`) — expected to land in a later wave-2/3 plan per the phase's plan split.
- Repo-wide `ruff check .` / `ruff format --check .` pre-existing debt (9 lint errors, 47 unformatted files, none in this plan's 3 files) logged in `deferred-items.md`, consistent with 22-01/22-02's prior entries — not this plan's responsibility to fix.

## Self-Check: PASSED

All created/modified files confirmed present on disk; all 4 commit hashes
(`f627d38`, `46260ae`, `677878a`, `84d1310`) confirmed present in `git log`.

---
*Phase: 22-sales-page-rebuild*
*Completed: 2026-07-17*
