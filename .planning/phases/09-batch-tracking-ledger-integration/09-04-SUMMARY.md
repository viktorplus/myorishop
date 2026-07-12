---
phase: 09-batch-tracking-ledger-integration
plan: 04
subsystem: ui
tags: [htmx, jinja2, fastapi, sqlalchemy, batch-tracking, writeoff, correction, oversell, picker]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration (Plan 01)
    provides: "Batch model, open_batches (D-07 order), record_operation batch_id dual projection + ownership guard"
  - phase: 09-batch-tracking-ledger-integration (Plan 03)
    provides: "shared app/templates/partials/batch_picker.html (parameterized batch_input_name/pick_url for scalar reuse)"
provides:
  - "register_writeoff(batch_id): resolves + rejects missing/foreign batch (LOT-05); oversell warn re-scoped from product.quantity to Batch.quantity (D-09/criterion 4); batch_id threaded into the writeoff op"
  - "register_correction(batch_id, confirm): batch resolution/rejection (LOT-05); count-mode diff against Batch.quantity not product total (Pitfall 7/T-09-13); new per-batch over-removal warn-but-allow gate (-qty_delta > batch.quantity, criterion 4); batch_id threaded into the correction op"
  - "GET /writeoff/batch-pick + GET /corrections/batch-pick: server-driven scalar-batch selection re-render (ownership re-checked, T-09-08); correction pick oob-refreshes «Остаток в партии: {qty}»"
  - "writeoff_batch_wrap.html / correction_batch_wrap.html: single-line scalar-batch wrappers reusing batch_picker.html; correction_batch_pick.html (wrapper + oob hint); correction_oversell.html «В партии не хватает остатка» warn partial"
  - "writeoff_oversell.html re-worded to batch scope «Товара не хватает в партии»"
affects: [returns, plan-09-05, batch-picker-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Scalar-batch reuse of the shared batch_picker.html: single-line forms carry a #batch-wrap-first <div> wrapper (batch_input_name='batch_id', pick_url per form), oob-swapped on lookup and re-rendered whole on radio pick"
    - "Batch-scoped removal gate: over-removal recomputed server-side vs the current Batch.quantity on every POST (confirm never trusted alone, T-09-14)"
    - "Batch-scoped count baseline: qty_delta = counted - batch.quantity so a recount of one batch cannot corrupt a sibling (Pitfall 7)"

key-files:
  created:
    - "app/templates/partials/writeoff_batch_wrap.html"
    - "app/templates/partials/correction_batch_wrap.html"
    - "app/templates/partials/correction_batch_pick.html"
    - "app/templates/partials/correction_oversell.html"
  modified:
    - "app/services/writeoffs.py"
    - "app/routes/writeoffs.py"
    - "app/templates/partials/writeoff_form.html"
    - "app/templates/partials/writeoff_lookup.html"
    - "app/templates/partials/writeoff_oversell.html"
    - "app/services/corrections.py"
    - "app/routes/corrections.py"
    - "app/templates/partials/correction_form.html"
    - "app/templates/partials/correction_lookup.html"
    - "tests/test_writeoffs.py"
    - "tests/test_corrections.py"

key-decisions:
  - "batch_id is a required-in-practice scalar (Form default '') the service rejects with «Выберите партию.» — mirrors register_sale's unconditional LOT enforcement (no None-escape)"
  - "Correction count-mode over-removal is effectively unreachable (counted>=0 ⇒ -qty_delta <= batch.quantity); the new warn-but-allow gate fires on the DELTA path, exactly as the criterion-4 contract intends"
  - "Added per-form batch-pick endpoints (/writeoff/batch-pick, /corrections/batch-pick) + wrapper/pick partials because batch_picker.html hardcodes a server round-trip on radio change via pick_url (executor discretion per UI-SPEC, Plan 03 precedent)"

patterns-established:
  - "Single-line scalar-batch wrapper: #batch-wrap-first <div> rendered from ONE markup source three ways (inline form, oob lookup swap, main batch-pick swap) so radio/highlight/hidden input can never disagree"
  - "Batch-scoped current-qty hint: #current-qty-hint oob-refreshed «Остаток в партии: {qty}» on pick, reset to «—» on a new lookup (Pitfall 7)"

requirements-completed: [LOT-05]

# Metrics
duration: ~15 min
completed: 2026-07-12
---

# Phase 9 Plan 04: Batch-Required Write-off & Correction Summary

**Write-off and stock-correction now require picking a specific batch via the shared scalar picker (LOT-05), with over-removal warnings scoped to the chosen batch's remaining quantity and correction count-mode diffed against that batch (not the product total) — full 309-test suite green.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-12T10:34Z (approx)
- **Completed:** 2026-07-12T10:49:13Z
- **Tasks:** 2 (both TDD: RED → GREEN)
- **Files modified:** 15 (4 created, 11 modified)

## Accomplishments
- `register_writeoff` gained a scalar `batch_id`: it resolves the batch, rejects an empty/unknown/foreign id with «Выберите партию.» (LOT-05/T-09-12) before any write, re-scopes the oversell warn-but-allow from `product.quantity` to the picked `Batch.quantity` (D-09/criterion 4), and threads `batch_id` into the `writeoff` op (dual projection).
- `register_correction` gained `batch_id` + `confirm`: batch resolution/rejection (LOT-05), count-mode baseline re-based to `counted - batch.quantity` (Pitfall 7/T-09-13 — a recount of one batch cannot corrupt a sibling), a new per-batch over-removal warn-but-allow gate (`-qty_delta > batch.quantity`, criterion 4), and `batch_id` threaded into the `correction` op.
- Both single-line forms embed the shared `batch_picker.html` in scalar mode via a `#batch-wrap-first` wrapper; `/writeoff/lookup` and `/corrections/lookup` oob-swap the open-batch list (empty state «Нет партий с остатком.»), and new `/writeoff/batch-pick` + `/corrections/batch-pick` endpoints re-render the wrapper on radio pick with server-side ownership re-checks (T-09-08).
- The correction current-qty hint is now batch-scoped: «Остаток в партии: —» until a batch is picked, then oob-refreshed to «Остаток в партии: {qty}» on `/corrections/batch-pick` (Pitfall 7).
- New `correction_oversell.html` («В партии не хватает остатка» / «{name}: в партии {available}, снимаете {requested}.») reuses the `.error-block` + `confirm=1` shell; `writeoff_oversell.html` re-worded to batch scope («Товара не хватает в партии»).

## Task Commits

Each task was executed TDD (RED test commit → GREEN implementation commit):

1. **Task 1: Write-off scalar batch_id + per-batch over-removal**
   - `56b074b` (test RED) → `f2f8f5e` (feat GREEN)
2. **Task 2: Correction batch_id, batch-scoped count diff, over-removal warn**
   - `958d375` (test RED) → `a6ab89c` (feat GREEN)

## Files Created/Modified
- `app/services/writeoffs.py` — `register_writeoff(..., batch_id="")`; `BATCH_REQUIRED_ERROR`; batch resolve/ownership reject; oversell re-scoped to `Batch.quantity`; `batch_id` in `record_operation`.
- `app/routes/writeoffs.py` — `batch_id` Form field forwarded + `selected_batch` re-echo; batch picker oob on `/writeoff/lookup`; new `GET /writeoff/batch-pick`.
- `app/templates/partials/writeoff_form.html` — embedded `#batch-wrap-first` scalar picker.
- `app/templates/partials/writeoff_lookup.html` — oob batch-wrap swap.
- `app/templates/partials/writeoff_oversell.html` — batch-scoped copy.
- `app/templates/partials/writeoff_batch_wrap.html` (new) — scalar wrapper reusing `batch_picker.html` (also the `/writeoff/batch-pick` response).
- `app/services/corrections.py` — `register_correction(..., batch_id="", confirm="")`; batch resolve/ownership reject; count diff vs `batch.quantity`; per-batch over-removal warn gate; `batch_id` in `record_operation`.
- `app/routes/corrections.py` — `batch_id`/`confirm` Form fields + `selected_batch`/`batch_qty` re-echo; picker oob + hint reset on `/corrections/lookup`; new `GET /corrections/batch-pick`; oversell render branch.
- `app/templates/partials/correction_form.html` — embedded picker + `correction_oversell.html` render + batch-scoped current-qty hint.
- `app/templates/partials/correction_lookup.html` — oob batch-wrap swap + hint reset «Остаток в партии: —».
- `app/templates/partials/correction_batch_wrap.html` (new) — scalar wrapper reusing `batch_picker.html`.
- `app/templates/partials/correction_batch_pick.html` (new) — wrapper main swap + oob current-qty hint.
- `app/templates/partials/correction_oversell.html` (new) — batch-scoped over-removal warning.
- `tests/test_writeoffs.py`, `tests/test_corrections.py` — batch-wired existing calls + missing-batch, foreign-batch, per-batch count-diff, and over-removal warn/confirm tests.

## Decisions Made
- **Scalar `batch_id` is required in practice.** The Form default is `""`; the service rejects an empty/unresolvable/foreign id with «Выберите партию.» (zero writes), mirroring Plan 03's unconditional `register_sale` LOT enforcement.
- **Correction over-removal fires on the delta path.** In count mode `counted >= 0` makes `-qty_delta = batch.quantity - counted <= batch.quantity`, so the new gate is only reachable via a negative delta — exactly the criterion-4 intent.
- **Per-form batch-pick endpoints + wrapper/pick partials** were added because `batch_picker.html` hardcodes a server round-trip on radio change (`hx-get="{{ pick_url }}"`). Filenames are executor discretion per UI-SPEC (Plan 03's `sale_batch_pick.html` precedent).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added per-form batch-pick endpoints + wrapper/pick partials**
- **Found during:** Task 1 & Task 2 (wiring the shared picker into single-line forms)
- **Issue:** The plan's `files_modified` listed only the form/oversell templates, but the shared `batch_picker.html` radio hardcodes `hx-get="{{ pick_url }}"` — a server round-trip is mandatory on every pick. The single-line forms therefore need a pick endpoint and a `#batch-wrap-first` wrapper partial (the sale flow used a `<tr>`; these forms use a `<div>`).
- **Fix:** Added `GET /writeoff/batch-pick` + `GET /corrections/batch-pick` (ownership re-checked, T-09-08) and the wrapper partials `writeoff_batch_wrap.html`, `correction_batch_wrap.html`, `correction_batch_pick.html`. All reuse `batch_picker.html` — no picker markup duplicated.
- **Files modified:** app/routes/writeoffs.py, app/routes/corrections.py, app/templates/partials/writeoff_batch_wrap.html, correction_batch_wrap.html, correction_batch_pick.html
- **Verification:** `test_web_writeoff_lookup_emits_batch_picker` + full suite green (309 passed).
- **Committed in:** `f2f8f5e` (Task 1), `a6ab89c` (Task 2)

**2. [Rule 3 - Blocking] Lint cleanup of the two batch test files**
- **Found during:** Post-GREEN `ruff check` on touched files
- **Issue:** New two-batch seed helpers introduced two `E501` long lines each, and the added imports left the blocks `I001` un-sorted (pre-existing debt Plan 01 flagged for these files).
- **Fix:** Wrapped the `record_operation` seed calls and ran `ruff check --fix` for import sorting on `tests/test_writeoffs.py` + `tests/test_corrections.py`.
- **Files modified:** tests/test_writeoffs.py, tests/test_corrections.py
- **Verification:** `ruff check` clean on all plan files; both test files green (17 passed).
- **Committed in:** `a6ab89c`

---

**Total deviations:** 2 auto-fixed (2 blocking — endpoint/partial plumbing + lint).
**Impact on plan:** Both were required to make the shared picker function on single-line forms and to keep touched files lint-clean; production behaviour matches the plan and the D-04/D-09/Pitfall-7 contracts exactly. No scope creep.

## Known Stubs
None — every artifact is wired and exercised by tests. Batch price/location fields are read-only display (populated by Plan 02's receipt birth path); write-off has no price surface and correction reads only `Batch.quantity`.

## Threat Flags
None — no new trust boundaries beyond the plan's `<threat_model>`. T-09-12 (batch resolve + ownership reject before any write), T-09-13 (count diff vs `batch.quantity`), T-09-14 (over-removal recomputed server-side vs current `Batch.quantity`, confirm never trusted alone), and T-09-15 (Jinja autoescape on batch comment/location via the shared picker, no `|safe`) are all implemented.

## Issues Encountered
None beyond the deviations above. The two pre-existing warnings (`test_returns.py` SAWarning, the httpx TestClient deprecation) are unrelated to this plan; the full suite is green (309 passed).

## Next Phase Readiness
- Every stock-affecting operation except the batch-inheriting return (Plan 05) is now batch-scoped. ROADMAP criterion 3 (write-off + correction require picking the specific batch) and criterion 4 (over-removal warnings scoped to the chosen batch) are met for these two paths.
- Plan 05 still owns the mandatory `record_operation` D-12 guard flip (batch_id required for stock-affecting types + audit-type rejection) once the return path also passes a batch.

## Self-Check: PASSED
- All 4 created files present on disk (`writeoff_batch_wrap.html`, `correction_batch_wrap.html`, `correction_batch_pick.html`, `correction_oversell.html`) via `[ -f ]`.
- All 4 task commits present in `git log` (2 RED test + 2 GREEN feat): `56b074b`, `f2f8f5e`, `958d375`, `a6ab89c`.
- `uv run pytest -q` → 309 passed. Acceptance greps: `counted - batch.quantity` in corrections.py, `batch_id=batch.id` in writeoffs.py, «не хватает остатка» in correction_oversell.html. `ruff check` clean on all plan files.

---
*Phase: 09-batch-tracking-ledger-integration*
*Completed: 2026-07-12*
