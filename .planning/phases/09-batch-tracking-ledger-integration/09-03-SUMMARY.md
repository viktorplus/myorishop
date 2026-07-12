---
phase: 09-batch-tracking-ledger-integration
plan: 03
subsystem: ui
tags: [htmx, jinja2, fastapi, sqlalchemy, batch-tracking, sales, oversell, picker]

# Dependency graph
requires:
  - phase: 09-batch-tracking-ledger-integration (Plan 01)
    provides: "Batch model, open_batches (D-07 order), record_operation batch_id dual projection, ru_date filter"
provides:
  - "register_sale(batch_ids=...): per-line batch resolution + «Выберите партию.» rejection of empty/foreign batches (LOT-02 service enforcement)"
  - "Per-batch oversell re-key: requested_by_batch vs Batch.quantity, same batch aggregated across lines (D-09/criterion 4)"
  - "non_blank_lines 4th padded batch_ids array (Pitfall 2 structural anti-drift)"
  - "app/templates/partials/batch_picker.html: shared radio batch table (four LOT-02 columns, full-list + selected-only modes, empty state) — reused by Plan 04 writeoff/correction"
  - "GET /sales/batch-pick: server-driven selection re-render + oob batch price (card fallback for legacy NULL price, D-05/D-14)"
  - "sale_row.html always-rendered #batch-wrap-{row} hidden batch_id[] wrapper; delete removes both rows"
  - "sale_lookup price-fill precedence: skip card fill when ≥1 open batch, single-batch D-06 auto-select"
  - "sale_oversell.html batch-scoped copy «Товара не хватает в партии»"
affects: [writeoffs, corrections, batch-picker-ui, plan-09-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural parallel-array alignment: hidden batch_id[] always rendered per line, padded to len(codes) before zip — array can never drift (Pitfall 2)"
    - "Server-driven radio selection: /sales/batch-pick re-renders the whole wrapper so radio + highlight + hidden input never disagree (RESEARCH Pattern 3)"
    - "Price-fill precedence: exactly one server-side fill source per line (skip card fill when open batches exist), typed-value oob guard unchanged (Pitfall 4)"
    - "Reusable partial via parameterized context (batch_input_name/pick_url defaults) for Plan 04 scalar-batch reuse"

key-files:
  created:
    - "app/templates/partials/batch_picker.html"
    - "app/templates/partials/sale_batch_pick.html"
  modified:
    - "app/services/sales.py"
    - "app/routes/sales.py"
    - "app/templates/partials/sale_row.html"
    - "app/templates/partials/sale_lookup.html"
    - "app/templates/partials/sale_form.html"
    - "app/templates/partials/sale_oversell.html"
    - "app/static/style.css"
    - "tests/test_sales.py"
    - "tests/test_customers.py"

key-decisions:
  - "register_sale enforces LOT-02 unconditionally (no None-escape) — the minimal batch_id[] route forwarding moved into Task 1 so the whole test_sales.py gate stays green (documented deviation)"
  - "Added sale_batch_pick.html (extra partial, filename discretion per UI-SPEC) to render the batch-pick round-trip (wrapper tr + oob price) reusing batch_picker.html"
  - "batch_picker.html owns the hidden batch_id[] input (artifact contract «contains batch_id[]»); input name parameterized for Plan 04 scalar reuse"

patterns-established:
  - "Pitfall 2: batch_id[] hidden input structurally per-line + padded before zip; delete removes both <tr>s"
  - "Pitfall 3: _build_lines echoes batch_id + selected_batch through all three re-render branches"
  - "Pitfall 4: single server-side price-fill source per line; batch pick is sole source when open batches exist"

requirements-completed: [LOT-02, LOT-04, WH-02]

# Metrics
duration: 24 min
completed: 2026-07-12
---

# Phase 9 Plan 03: Sale-Time Batch Picker & Per-Batch Oversell Summary

**Sale lines now require a visibly-picked batch (four-column inline picker, D-07 order, single-batch auto-select), priced from the batch, with oversell scoped to that batch's remaining quantity — all on a structurally drift-proof batch_id[] parallel array.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-12T10:00:52Z
- **Completed:** 2026-07-12T10:25:17Z
- **Tasks:** 3 (Task 1 TDD: RED → GREEN)
- **Files modified:** 11 (2 created, 9 modified)

## Accomplishments
- `register_sale` resolves and requires a batch per line, rejecting an empty/unknown/foreign batch with «Выберите партию.» at the service level (LOT-02); per-batch oversell re-keyed from product to `Batch.quantity` with same-batch aggregation across lines (D-09/criterion 4, Pitfall 8).
- Shared `batch_picker.html` renders the four LOT-02 columns (price, expiry, remaining qty, comment — WH-02 location echoed inside the comment cell, no warehouse column) in D-07 order, with full-list + selected-only modes, D-06 auto-select note, and the «Нет партий с остатком.» empty state.
- `GET /sales/batch-pick` re-renders the whole wrapper row (selected radio, highlight, hidden `batch_id[]`) plus an oob batch-price fill (card fallback for legacy NULL price, D-14); `/sales/lookup` skips the card fill when open batches exist and auto-selects a single batch (Pitfall 4).
- Structural anti-drift: the hidden `batch_id[]` input is always rendered per line and padded to `len(codes)` before zipping; «Удалить строку» removes both `<tr>`s; a 422/warn re-render re-echoes each picked batch (Pitfall 2/3).
- `sale_oversell.html` re-worded to batch scope («Товара не хватает в партии»), reusing the existing `.error-block` + `confirm=1` warn-but-allow shell.

## Task Commits

1. **Task 1: register_sale per-line batch resolution + per-batch oversell re-key** (TDD)
   - `db8ba16` (test RED) → `3f8450b` (feat GREEN)
2. **Task 2: batch_picker.html + /sales/batch-pick + wrapper row + price precedence**
   - `8e253fe` (feat)
3. **Task 3: per-batch oversell warning copy in sale_oversell.html**
   - `082e043` (feat)

## Files Created/Modified
- `app/services/sales.py` — `non_blank_lines` 4th padded `batch_ids`; `register_sale(batch_ids=...)` per-line resolution + `requested_by_batch` oversell re-key + `batch_id` in the write loop; `BATCH_REQUIRED_ERROR`.
- `app/routes/sales.py` — `batch_id[]` Form param forwarded to `register_sale`; `_build_lines(session, ..., batch_ids)` batch echo; new `GET /sales/batch-pick`; `sale_lookup` price precedence + oob picker.
- `app/templates/partials/batch_picker.html` (new) — shared radio table + hidden `batch_id[]`.
- `app/templates/partials/sale_batch_pick.html` (new) — batch-pick response (wrapper tr + oob price).
- `app/templates/partials/sale_row.html` — always-rendered `#batch-wrap-{row}` wrapper; both-row delete handler.
- `app/templates/partials/sale_lookup.html` — oob picker + skip-card-fill logic.
- `app/templates/partials/sale_form.html` — forwards batch vars into the row `{% with %}` blocks.
- `app/templates/partials/sale_oversell.html` — batch-scoped copy.
- `app/static/style.css` — two `.batch-picker` rules (existing `#e8effd` tint).
- `tests/test_sales.py` — service batch tests + picker/batch_pick/drift/echo/autoselect route tests.
- `tests/test_customers.py` — batch-wired its `register_sale` seeds (signature sweep).

## Decisions Made
- **Unconditional service-level LOT-02 enforcement.** `register_sale` always requires a batch (no None-escape). To keep Task 1's gate (whole `test_sales.py` green) satisfiable, the minimal `batch_id[]` route forwarding was pulled into Task 1 rather than deferred to Task 2 (see deviations).
- **Added `sale_batch_pick.html`.** The batch-pick round-trip needs a template whose main swap is the wrapper `<tr>` plus an oob price `<td>`; UI-SPEC grants filename discretion, so a dedicated single-purpose partial (reusing `batch_picker.html`) was cleaner than overloading `sale_lookup.html`.
- **Hidden `batch_id[]` lives in `batch_picker.html`** to satisfy the artifact contract («contains batch_id[]») and keep the input, radio state, and highlight in one reusable unit; the input name is parameterized (`batch_input_name`, default `batch_id[]`) for Plan 04's scalar `batch_id` reuse.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Minimal route forwarding of batch_id[] moved into Task 1**
- **Found during:** Task 1 (acceptance gate: whole `tests/test_sales.py` green)
- **Issue:** Making `register_sale` require a batch breaks every existing route POST test unless `sale_create` forwards `batch_id[]`. The plan scoped route changes to Task 2, but Task 1's acceptance is the whole test file passing.
- **Fix:** Added `batch_id: list[str] = Form([], alias="batch_id[]")` + `batch_ids=batch_id` forwarding to `sale_create` (and a 4-tuple unpack fix in `_build_lines`) in Task 1; the full picker/`_build_lines` echo landed in Task 2 as planned.
- **Files modified:** app/routes/sales.py
- **Verification:** `uv run pytest tests/test_sales.py -x -q` → 36 passed after Task 1 GREEN.
- **Committed in:** `3f8450b` (Task 1 GREEN)

**2. [Rule 1 - Bug] Batch-wired test_customers.py register_sale seeds**
- **Found during:** Task 1 (full-suite run)
- **Issue:** `test_customers.py` seeds linked sales via `register_sale` without a batch; the new LOT-02 enforcement turned its 3 purchase-history tests red (out-of-file but directly caused by the signature change — RESEARCH flagged this signature sweep).
- **Fix:** Added an `open_batches`-based `_only_batch` helper and passed `batch_ids=[...]` to the 3 seeds.
- **Files modified:** tests/test_customers.py
- **Verification:** `uv run pytest tests/test_customers.py -q` → all pass; full suite 291 passed.
- **Committed in:** `3f8450b` (Task 1 GREEN)

**3. [Rule 3 - Blocking] Added sale_batch_pick.html partial**
- **Found during:** Task 2 (batch-pick endpoint response)
- **Issue:** The plan listed only `batch_picker.html` as new, but the batch-pick response needs a `<tr>` wrapper (main swap) + oob price `<td>` — not renderable by `batch_picker.html` alone.
- **Fix:** Created `sale_batch_pick.html` (reuses `batch_picker.html`); filenames are executor discretion per UI-SPEC.
- **Files modified:** app/templates/partials/sale_batch_pick.html (new)
- **Verification:** `test_web_sale_batch_pick_selects_and_fills_batch_price` passes.
- **Committed in:** `8e253fe` (Task 2)

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug/signature-sweep).
**Impact on plan:** All fixes were required to keep the task-boundary test gates green and to render the endpoint; production behaviour matches the plan and the D-04..D-09 contracts exactly. No scope creep.

## Known Stubs
None — every artifact is wired and exercised by tests. The receipt-side batch birth (Batch.price_cents/location population) is Plan 02's scope; the picker reads whatever those fields hold and falls back correctly for legacy NULL price (D-14).

## Threat Flags
None — no new trust boundaries beyond the plan's `<threat_model>`. T-09-07 (structural batch_id[] alignment + pad), T-09-08 (server-side ownership re-check in register_sale and /sales/batch-pick), T-09-10 (`_ROW_ID_RE` validation on /sales/batch-pick), and T-09-11 (Jinja autoescape on batch comment/location, no `|safe`) are all implemented.

## Issues Encountered
None beyond the deviations above. Two pre-existing SAWarnings in `tests/test_returns.py` (unrelated to this plan) remain; the full suite is green (291 passed).

## Next Phase Readiness
- Sale flow requires a visibly-picked, batch-priced line with per-batch oversell — ROADMAP criteria 2 (sale) and 4 (sale oversell) met.
- `batch_picker.html` is self-contained and reusable (parameterized input name + pick url) — ready for Plan 04's write-off/correction reuse.
- Plan 05 still owns the mandatory `record_operation` D-12 guard flip once every operation service passes a batch.

## Self-Check: PASSED
- Both created files present on disk (`batch_picker.html`, `sale_batch_pick.html`) via `[ -f ]`.
- All 4 task commits present in `git log` (1 RED test + 3 feat).
- `uv run pytest -q` → 291 passed; `ruff check app/ tests/test_sales.py tests/test_customers.py` clean. Acceptance greps: `batch_id[]` in picker, `/sales/batch-pick` in routes, `requested_by_batch` in service, exactly two `.batch-picker` CSS rules (`#e8effd` only).

---
*Phase: 09-batch-tracking-ledger-integration*
*Completed: 2026-07-12*
