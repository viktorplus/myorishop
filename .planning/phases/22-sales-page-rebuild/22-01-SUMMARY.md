---
phase: 22-sales-page-rebuild
plan: 01
subsystem: testing
tags: [pytest, xfail, fastapi, jinja2, sqlalchemy, sales, customers]

# Dependency graph
requires: []
provides:
  - "13 tests in tests/test_sales.py pinning the SALE-03/04/05/06/07 markup/behavior contract"
  - "SALE-01 basket-table regression guard (extended test_web_sale_page_renders_form)"
  - "11 strict-xfail markers as the retirement checklist for 22-05 (wave 2) and 22-03 (wave 3)"
affects: [22-03, 22-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Order-independent HTML attribute assertions (_input_tag/_input_value/_tag_by_id helpers) instead of fixed 'name=\"X\" value=\"Y\"' substring checks"
    - "Strict xfail as a retirement checklist: an unremoved marker XPASSes and fails the suite, so a later wave cannot silently skip implementing the pinned contract"

key-files:
  created: [".planning/phases/22-sales-page-rebuild/deferred-items.md"]
  modified: ["tests/test_sales.py"]

key-decisions:
  - "Reclassified 2 of the plan's 13 planned strict-xfail tests (test_web_sale_picker_data_attrs, test_web_sale_new_customer_blank_fields_still_walks_in) to plain regression guards because they already pass against currently shipped code; strict-xfail on a passing test XPASSes and fails the suite"
  - "Fixed 3 pre-existing ruff-format violations inside tests/test_sales.py (unrelated record_operation() call sites) so this plan's own file passes ruff format --check cleanly, per Task 3's explicit acceptance criterion"
  - "Logged the separate 50-file repo-wide ruff format debt (and 9 ruff check errors) as out of scope in deferred-items.md — none of those files were touched by this plan"

patterns-established:
  - "_input_tag(html, name) / _input_value(html, name) / _tag_by_id(html, id) test helpers for order-independent HTML attribute assertions — reusable by 22-05/22-03/22-06/22-07"

requirements-completed: [SALE-01, SALE-03, SALE-04, SALE-05, SALE-06, SALE-07]

# Metrics
duration: ~55min
completed: 2026-07-17
---

# Phase 22 Plan 01: Wave-0 Sales Test Coverage Summary

**13 tests added to tests/test_sales.py pinning the customer-selector (SALE-03..06) and recent-sales customer-column (SALE-07) contract as strict xfail, plus a SALE-01 basket-table regression guard — full suite stays green at 810 passed / 11 xfailed (808 baseline + 2 tests that already passed).**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3 completed
- **Files modified:** 2 (`tests/test_sales.py`, new `.planning/phases/22-sales-page-rebuild/deferred-items.md`)

## Accomplishments

- 5 strict-xfail tests pin the SALE-03/06 customer-mode radio group contract: default-checked state, the "new" 3-field block, the D-03 round-trip that must preserve both modes' typed values across a switch, the allow-list fallback for an unknown `customer_mode` value with no raw echo (T-22-01), and the anon block's zero-visible-inputs contract (SALE-06).
- 5 tests pin the SALE-04/05 chip/picker/D-10-guard contract: the D-12 chip-survives-422 regression (a verified live defect), the picker's `data-id`/`data-name`/`data-surname` + HTML-escaping contract (T-22-02), D-07's exactly-3-fields cap, and both sides of the D-10 "must click Добавить покупателя" guard (422 + zero writes on the positive case, still-walks-in on the negative case).
- 3 strict-xfail tests pin SALE-07: the recent-sales «Покупатель» column with the buyer's full name, the D-06 muted «Розница» walk-in label with no `None` leak, and a service-level test guarding the future `recent_sales` outerjoin against silently becoming an inner join and dropping walk-in rows.
- Extended the existing `test_web_sale_page_renders_form` (not a new test) with the SALE-01 regression guard: asserts the four basket-table headers and the four array-named inputs (`code[]`/`qty[]`/`price[]`/`batch_id[]`) so a later wave cannot "rebuild" the already-shipped table.
- Full suite verified green: `tests/test_sales.py` → 57 passed, 11 xfailed; full repo suite → 810 passed, 11 xfailed, 0 failed (808 baseline + 2 non-xfail regression guards this plan added).

## Task Commits

All three tasks land in a single commit because they share one declared file (`files_modified: tests/test_sales.py` in the plan frontmatter) with interleaved shared infrastructure (imports, helper functions used by all three tasks' tests) — a clean per-task hunk split was not possible without `git stash`, which is prohibited in worktree execution (cross-worktree `refs/stash` contamination risk, #3542).

1. **Tasks 1–3: Wave-0 red-side coverage for SALE-03..07 + SALE-01 guard** - `ef3eefe` (test)

**Plan metadata:** pending (this summary + STATE update, per worktree mode)

## Files Created/Modified

- `tests/test_sales.py` - +13 tests (11 strict-xfail, 2 plain), 3 new order-independent HTML-assertion helpers (`_input_tag`, `_input_value`, `_tag_by_id`), extended `test_web_sale_page_renders_form` with the SALE-01 regression guard
- `.planning/phases/22-sales-page-rebuild/deferred-items.md` - new: logs the pre-existing repo-wide ruff format/check debt (50 files, out of scope for this plan)

## Decisions Made

- **Kept `test_web_sale_picker_data_attrs` and `test_web_sale_new_customer_blank_fields_still_walks_in` as plain (non-xfail) tests instead of strict-xfail as literally instructed by the plan.** Both were verified via `uv run pytest` to XPASS against current shipped code before any implementation work — the picker markup (`customer_picker.html`) already implements the full `data-id`/`data-name`/`data-surname` + escaping contract, and `customer_id=""` already produces a walk-in sale regardless of the not-yet-wired `customer_mode` param. A strict-xfail on an already-passing assertion converts an XPASS into a hard test failure, which directly violates this plan's own top-level truth ("the full suite stays green — new tests land as strict xfail, not as red failures"). Full reasoning is documented inline in each test's docstring for the benefit of whoever implements 22-05.
- **Fixed 3 pre-existing ruff-format violations inside `tests/test_sales.py`** (multi-line `record_operation(...)` calls in `_two_batches`/`_batch`/`test_foreign_batch_id_rejected_zero_writes`, unrelated to this plan's own additions) via `uv run ruff format tests/test_sales.py`, because Task 3's acceptance criterion explicitly requires `ruff format --check tests/test_sales.py` to pass on this exact file.
- **Did not run `ruff format`/`ruff check` fixes repo-wide.** The full-repo verification command (`uv run ruff check . && uv run ruff format --check .`) surfaces 9 pre-existing lint errors and 50 files needing reformatting, none in any file this plan touched. Per the executor Scope Boundary rule, these are logged to `deferred-items.md` and left unfixed.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reclassified 2 tests from strict-xfail to plain regression guards**
- **Found during:** Task 2 verification (`uv run pytest tests/test_sales.py -k "chip_survives_422 or picker_data_attrs or new_customer" -rxX`)
- **Issue:** `test_web_sale_picker_data_attrs` and `test_web_sale_new_customer_blank_fields_still_walks_in`, as literally specified by the plan (strict-xfail), XPASSed against current shipped code — an XPASS under `strict=True` is a hard test failure, breaking the plan's own acceptance criteria ("5 XFAIL, 0 XPASS") and top-level truth ("suite stays green"). The plan's own action text for the second test explicitly predicted this exact risk ("the test would pass for the wrong reason") yet still instructed strict-xfail.
- **Fix:** Removed the `@pytest.mark.xfail(...)` decorator from both tests, keeping every substantive assertion from the plan's spec intact; documented the reclassification inline in each test's docstring.
- **Files modified:** `tests/test_sales.py`
- **Verification:** `uv run pytest tests/test_sales.py -k "chip_survives_422 or picker_data_attrs or new_customer" -rxX` → 2 passed, 3 xfailed, 0 failed, 0 xpassed.
- **Committed in:** `ef3eefe`

**2. [Rule 3 - Blocking] Fixed pre-existing ruff-format debt inside this plan's own file**
- **Found during:** Task 3 verification (`uv run ruff format --check tests/test_sales.py`)
- **Issue:** 3 pre-existing multi-line `record_operation(...)` call sites in `tests/test_sales.py` (unrelated to this plan's changes) did not match the project's ruff-format style, causing the acceptance criterion's `ruff format --check` to fail on this file.
- **Fix:** Ran `uv run ruff format tests/test_sales.py`, which reformatted those 3 pre-existing call sites plus one line of this plan's own new code (`row_tag = re.search(...)`); re-ran the full test file and full suite afterward to confirm no behavior change.
- **Files modified:** `tests/test_sales.py`
- **Verification:** `uv run ruff check tests/test_sales.py && uv run ruff format --check tests/test_sales.py` → clean; `uv run pytest tests/test_sales.py -q` → 57 passed, 11 xfailed (unchanged from before the format fix).
- **Committed in:** `ef3eefe`

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues preventing the plan's own stated acceptance criteria from being met)
**Impact on plan:** Both fixes were necessary to satisfy the plan's own truths ("suite stays green", "ruff format --check passes"). No scope creep — every substantive assertion the plan specified for the 2 reclassified tests is still present; only the xfail marker was removed.

## Issues Encountered

- The full-repo `uv run ruff check . && uv run ruff format --check .` verification command (listed in the plan's `<verification>` block) surfaces pre-existing debt across 50 files and 9 lint errors, none in any file this plan modified. Logged to `.planning/phases/22-sales-page-rebuild/deferred-items.md` as out of scope per the executor's Scope Boundary rule rather than fixed, since fixing it would touch dozens of files outside this plan's declared `files_modified: [tests/test_sales.py]`.

## Known Stubs

None — this plan is test-authorship only; no application code was added or stubbed.

## Threat Flags

None — this plan adds test coverage only, touching no new network endpoints, auth paths, file access patterns, or schema. The 4 threat-register entries in the plan (T-22-01, T-22-02, T-22-04, T-22-SC) are all mitigated by tests written here, targeting application code that lands in 22-05.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Wave 0 (this plan + 22-02) is now complete for `tests/test_sales.py`'s share of the retirement ledger: 11 strict-xfail markers exist (5 SALE-03/06, 3 SALE-04/05 — 2 were reclassified as always-passing per the deviation above, 3 SALE-07), ready for 22-05 (wave 2, removes the 8 SALE-03/04/05/06 markers this plan actually left as xfail) and 22-03 (wave 3, removes the 3 SALE-07 markers).
- **Correction for 22-VALIDATION.md's retirement ledger:** the table states "10 by 22-05 (wave 2)" for `test_sales.py` markers, assuming all 5 of Task 2's tests would be strict-xfail. Since 2 of those 5 already pass today (documented above), the actual count 22-05 needs to un-xfail is **8**, not 10 (5 from Task 1 + 3 from Task 2's remaining xfail tests: `test_web_sale_chip_survives_422_rerender`, `test_web_sale_new_customer_field_set_is_exactly_three`, `test_web_sale_new_customer_requires_button_returns_422`). 22-03 (wave 3) is unaffected — still 3 markers to retire.
- The SALE-01 regression guard is green and will fail loudly if a later wave restructures the basket table's headers or array-named inputs.
- `_input_tag`/`_input_value`/`_tag_by_id` helpers in `tests/test_sales.py` are available for reuse by 22-05 when it turns these tests green (order-independent attribute assertions matching the exact markup contract in 22-UI-SPEC.md Interaction 1-9).

---
*Phase: 22-sales-page-rebuild*
*Completed: 2026-07-17*
