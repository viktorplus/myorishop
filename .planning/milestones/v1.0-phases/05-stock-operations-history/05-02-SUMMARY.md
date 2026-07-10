---
phase: 05-stock-operations-history
plan: 02
subsystem: inventory
tags: [fastapi, htmx, jinja2, sqlalchemy, sqlite, ru-labels]

# Dependency graph
requires:
  - phase: 05-stock-operations-history (05-01)
    provides: WRITEOFF_REASONS + OPERATION_TYPE_LABELS constants (Jinja globals), tests/test_writeoffs.py RED contract
  - phase: 03-goods-receipt-backup
    provides: receipt_form.html / receipt_lookup.html / name_input.html templates, receipts.lookup_prefill, the 204 code->name autofill pattern, save-and-next form ergonomics
  - phase: 04-sales-customers
    provides: sale_oversell.html destructive warn-but-allow pattern (SAL-04), register_sale rollback/try-except shape
provides:
  - app/services/writeoffs.py - register_writeoff() (validation + oversell + single-write-path commit) and recent_writeoffs()
  - app/routes/writeoffs.py - GET /writeoff, GET /writeoff/lookup, POST /writeoff
  - Five write-off templates (page + 4 partials) - form, lookup fill, oversell warning, recent-operations table
  - app.include_router(writeoffs.router) wired in app/main.py
  - OPS-01 fully functional: operator can write off stock by code with a required reason + optional note
affects: [05-03-returns, 05-04-corrections, 05-05-history, 06-reports]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Write-off mirrors the receipt/sale save-and-next form almost verbatim (focus-back hx-on::load hook, 204 lookup, typed-name swap guard, oob recent-list refresh) - the third phase to reuse this exact shape"
    - "Oversell warn-but-allow (SAL-04) generalizes beyond sales: the same .error-block + button.danger + hx-vals confirm=1 re-POST pattern now covers write-off too, with zero new CSS"

key-files:
  created:
    - app/services/writeoffs.py
    - app/routes/writeoffs.py
    - app/templates/pages/writeoff_form.html
    - app/templates/partials/writeoff_form.html
    - app/templates/partials/writeoff_lookup.html
    - app/templates/partials/writeoff_oversell.html
    - app/templates/partials/writeoff_rows.html
  modified:
    - app/main.py

key-decisions:
  - "register_writeoff never auto-creates a product (unlike register_receipt) - an unknown code is always an error directing the operator to receipt the product first (D-04)"
  - "The service's `name` parameter is accepted for form-echo symmetry with receipts/sales but is never used to rename or create a product - write-off has no auto-create path"
  - "Empty note is valid (note.strip() may be '') per D-01 - the hybrid reason model requires only the category, not the free-text note"

patterns-established:
  - "Server-side allow-list validation for reason_code (WRITEOFF_REASONS) - the <select> is never trusted, matching V5"

requirements-completed: [OPS-01]

# Metrics
duration: 13min
completed: 2026-07-09
---

# Phase 5 Plan 2: Write-off Slice Summary

**Write-off vertical slice (OPS-01): `register_writeoff()` writes one `writeoff` op (qty_delta<0) through `record_operation`, `/writeoff` routes + 5 templates reuse the receipt save-and-next form and the Phase-4 sale oversell warn-but-allow pattern, with a server-side WRITEOFF_REASONS allow-list and no price fields.**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-09T22:30:30Z
- **Completed:** 2026-07-09T22:42:00Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- `app/services/writeoffs.py`: `register_writeoff(session, *, code, name, qty_raw, reason_code, note, confirm="")` validates code/qty/reason_code (server-side `WRITEOFF_REASONS` allow-list, V5/T-05-01), resolves the ACTIVE product by code only (never auto-creates, D-04), runs a warn-but-allow oversell check BEFORE any write (T-05-03, mirrors SAL-04), and writes exactly one `writeoff` op with `qty_delta=-qty` and `payload={"reason_code","note"}` through the single write path `record_operation`. `recent_writeoffs()` mirrors `recent_receipts`.
- Five templates: `pages/writeoff_form.html` (page shell), `partials/writeoff_form.html` (save-and-next stacked form: Код → Название → Количество → required Причина списания `<select>` from the `WRITEOFF_REASONS` Jinja global → optional Примечание → «Списать»; no price fields), `partials/writeoff_lookup.html` (name-only 204-fill fragment), `partials/writeoff_oversell.html` (destructive `.error-block` + `button.danger` «Списать всё равно», reusing `sale_oversell.html`'s shape exactly), `partials/writeoff_rows.html` (recent write-offs table: Когда/Код/Название/Кол-во signed/Причина with the RU label + note).
- `app/routes/writeoffs.py`: `GET /writeoff` (page), `GET /writeoff/lookup` (204 pattern reusing `receipts.lookup_prefill`), `POST /writeoff` (try/except → `logger.exception` + RU 422, T-05-04; oversell branch renders the warning with 0 writes and 200; validation errors → 422; success → fresh form + focus back to «Код» + oob `#recent-writeoffs` refresh). Registered in `app/main.py`.
- `tests/test_writeoffs.py` (the Wave-0 RED contract from 05-01) is now fully GREEN: 4/4 tests pass (`test_stock_and_reason`, `test_reason_allowlist`, `test_web_writeoff_form`, `test_web_writeoff_oversell`).

## Task Commits

Each task was committed atomically:

1. **Task 1: writeoffs service — register_writeoff + recent_writeoffs** - `0ee860f` (feat)
2. **Task 2: write-off templates — form page/partial, lookup, oversell, recent rows** - `3063b06` (feat)
3. **Task 3: /writeoff routes + main.py wiring; web tests GREEN** - `5b8fe28` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `app/services/writeoffs.py` - `register_writeoff()` (validation + oversell + single-write-path commit), `recent_writeoffs()`
- `app/routes/writeoffs.py` - `GET /writeoff`, `GET /writeoff/lookup`, `POST /writeoff`
- `app/templates/pages/writeoff_form.html` - page shell (extends base, h1 «Списание»)
- `app/templates/partials/writeoff_form.html` - the save-and-next form (swapped whole on every response)
- `app/templates/partials/writeoff_lookup.html` - name-only 204-fill fragment
- `app/templates/partials/writeoff_oversell.html` - destructive warn-but-allow block
- `app/templates/partials/writeoff_rows.html` - recent write-offs table
- `app/main.py` - added `writeoffs` import + `app.include_router(writeoffs.router)`

## Decisions Made
- Followed the plan's exact signature `register_writeoff(session, *, code, name, qty_raw, reason_code, note, confirm="")`; `name` is accepted (form-echo symmetry with receipts/sales) but never used — write-off has no auto-create path (D-04), so a typed name is not written anywhere by this service.
- Reused `app.services.receipts.lookup_prefill` directly for the `/writeoff/lookup` 204 pattern rather than duplicating it — write-off only needs the `name` field from its return value (no price fields, D-04).
- `PRODUCT_NOT_FOUND_TMPL` copied verbatim from `sales.py`'s `PRODUCT_NOT_FOUND_TMPL` string («Товар с кодом „{code}“ не найден. Сначала оприходуйте товар.») to match the exact UI-SPEC copy contract.

## Deviations from Plan

None - plan executed exactly as written. One micro-fix during Task 2 verification: an early draft of `writeoff_oversell.html`'s HTML comment used the literal substring `|safe` in prose ("never |safe"), which caused `grep -RL '|safe' app/templates/partials/writeoff_*.html` (the task's own acceptance check) to not list that file even though no `|safe` filter is actually used anywhere. Reworded the comment to avoid the literal substring so the acceptance grep passes cleanly (Rule 1 - the check is testing for actual `|safe` usage, and the false-positive would have hidden a real regression in future edits). No commit boundary — folded into the Task 2 commit `3063b06` since it landed before that commit was made.

## Issues Encountered

None beyond the comment-wording fix above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/writeoff` is reachable and functional end to end; `tests/test_writeoffs.py` is fully GREEN (4/4).
- Full suite green (154 passed) except the three intentionally-RED Wave-0 files (`tests/test_corrections.py`, `tests/test_history.py`, `tests/test_returns.py`) — exactly as designed; those turn GREEN in Waves 3-5 (05-03/04/05).
- No nav link to `/writeoff` was added to `base.html` in this plan — it wasn't in this plan's `files_modified` list (base.html nav wiring is Claude's discretion per D-17 and is not blocking OPS-01's acceptance criteria, which only requires the route/form/service to work). A future plan or the phase's UAT pass may want to add it alongside the other nav entries added across Waves 3-5.
- No blockers for 05-03 (returns): `app/services/sales.py::recent_sales` and the sale-line return entry point are already in place and untouched by this plan.

## TDD Gate Compliance

Task 1 was marked `tdd="true"`, but per the plan's own design the RED test file (`tests/test_writeoffs.py`) was already written and committed in the prior Wave-0 plan (05-01, commit `276d2f9`) — this plan's job was to turn that pre-existing RED contract GREEN, not to author new tests. A single `feat(05-02)` commit (`0ee860f`) implements `register_writeoff`/`recent_writeoffs` against the already-fixed interface; there is no separate `test(...)` commit within this plan because none was needed (RED already existed). This matches the Wave-0/Wave-N split documented in 05-01-SUMMARY.md and is not a gate violation.

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-09*

## Self-Check: PASSED

All 7 created files verified present on disk; all 3 task commits (`0ee860f`, `3063b06`, `5b8fe28`) verified present in git log.
