---
phase: 33-back-dated-operations
plan: 09
subsystem: csv-export
tags: [export, csv, finance, coalesce, portable-orm, order-by, date-08]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "business_date_bounds (CLOSED date-only bounds) and business_date_expr (the COALESCE read expression) — both consumed verbatim, neither modified"
  - phase: 33-back-dated-operations
    plan: 07
    provides: "the BLOCKING hand-off recorded as its Deviation 2 — the two stream_cash_movements_csv bounds sites it deliberately did NOT switch"
provides:
  - "app/services/export.py::stream_cash_movements_csv — row set selected by business_date_expr(CashMovement) over the CLOSED range; params renamed start_iso/end_iso -> start_day/end_day"
  - "app/services/export.py — both dated dumps ordered (business date, created_at, seq); «Когда» carries the business date; a new LAST column «Внесено» carries the entry timestamp"
  - "app/routes/finance.py + app/routes/mobile_finance.py — the last two local_day_bounds_utc sites in app/ removed; both CSV routes now on business_date_bounds"
  - "tests/test_export.py — 7 new tests pinning the CSV contract, incl. test_csv_first_column_non_decreasing which covers BOTH ORDER BY edits and was verified non-vacuous against two counterfactuals"
affects: [33-13, 33-14, 33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A CSV whose row set is period-scoped must render, order and filter on the SAME date expression — a headline date column that can contradict the file's own period is a repudiation defect, not a cosmetic one"
    - "When a column's meaning changes but its position must not, append the displaced value as the LAST column and record the accepted cost (value TYPE narrows) as a comment above the header list — an existing spreadsheet formula over the middle columns keeps working"
    - "A single «column 1 is non-decreasing» assertion can cover several ORDER BY edits at once, but only if it is run against the counterfactual for EACH edit separately — otherwise one edit's coverage is an accident of the other's"
    - "A parameter renamed from *_iso to *_day is the cheapest possible guard against Pitfall 14: the type change (UTC timestamp -> date-only ISO) becomes visible at the call site instead of silently passing"

key-files:
  created: []
  modified:
    - app/services/export.py
    - app/routes/finance.py
    - app/routes/mobile_finance.py
    - tests/test_export.py
    - tests/test_finance_reports.py
    - app/__init__.py

key-decisions:
  - "33-09 (the orchestrator's verified correction, applied): 33-09-PLAN.md:102's claim that plan 33-07 already switched app/routes/finance.py:379 and app/routes/mobile_finance.py:377 to business_date_bounds is FALSE. Verified against the live code before editing — both still called local_day_bounds_utc, each carrying 33-07's hand-off comment. Both were switched in the SAME commit as export.py's predicate; neither file appears in the plan's files_modified, which is a planning gap, not a licence to skip the work."
  - "33-09 (CD-9, executed and PROVEN non-vacuous): export.py:214's ORDER BY switched alongside :135. Verified by two counterfactual runs — reverting BOTH clauses reddens test_csv_first_column_non_decreasing, and reverting ONLY the CD-9 one reddens it too. The edit D-23 never enumerated is therefore genuinely covered, not covered by accident through its sales twin."
  - "33-09 (Rule 1, against the plan's letter): the plan says the five local_day_bounds_utc call sites in tests/test_export.py «BUILD created_at values and must stay as they are». That is true of exactly ONE of them (:182). The other four passed the helper's output as the export PERIOD, which the switched predicate turns into a guaranteed-empty file. Four were re-pointed at business_date_bounds; the one that really builds a created_at kept the helper."
  - "33-09: test_cash_movements_csv_half_open_period_and_order RENAMED to *_closed_period_and_order and re-pointed at the CLOSED contract, keeping its two seeding INSTANTS unchanged (local 2026-07-10 00:00 and local 2026-07-11 00:00). The same two rows, the same outcome, for the correct reason — mirroring what 33-07 did to test_finance_reports.py's two *_half_open_bounds tests."
  - "33-09: stream_cash_movements_csv's parameters renamed start_iso/end_iso -> start_day/end_day. Both call sites are positional, so nothing broke, and the name now states the type. Leaving *_iso on a date-only value is exactly the confusion Pitfall 14 documents."
  - "33-09 (D-23's accepted cost, written into the code): column 1's value TYPE narrows from dd.mm.yyyy HH:MM to dd.mm.yyyy and the HH:MM reappears verbatim in «Внесено». Column positions 1..N do NOT shift, pinned by test_csv_vnesyeno_column_is_last against HEAD-recorded header constants."
  - "33-09: NO requirement is marked complete, although the plan's frontmatter names DATE-03 and DATE-05. DATE-03 was already marked complete by 33-07/33-08. DATE-05 («История AND the CSV exports show both dates whenever they differ») is owned by TWO plans — 33-14-PLAN.md's frontmatter also lists it, and it carries the История half (the «задним числом» marker). This plan delivers only the CSV half; marking DATE-05 here would make REQUIREMENTS.md's traceability table claim work that lands in 33-14. Same call 33-05 and 33-06 made."
  - "33-09 (DATE-08): the render fallback is created_at[:10], the UTC prefix, DELIBERATELY — it is the value func.coalesce(business_date, substr(created_at,1,10)) selected the row by, so column 1 cannot contradict the file's own period. test_csv_null_business_date_falls_back_to_utc_prefix seeds a 21:30 UTC row whose Europe/Moscow day is the NEXT one and pins the UTC day, so the asymmetry with migration 0027's tz-correct backfill cannot be «unified» silently."

patterns-established:
  - "Rename a bounds parameter when its TYPE changes, even when every call site is positional — the name is the only place the half-switch is visible at review time"

requirements-completed: []

# Metrics
duration: ~50min
completed: 2026-09-04
---

# Phase 33 Plan 09: Business-Date CSV Export Summary

**Both dated CSV dumps now state when it HAPPENED first and when it was ENTERED last — `cash_movements.csv` selects, orders and renders its rows through one and the same `business_date_expr`, `sales.csv` orders by it, and the two route callers 33-07 handed over were flipped in the same commit so the file's headline date column can never contradict the period it was selected for.**

## Performance

- **Duration:** ~50 min (including a 7m20s full-suite run and two counterfactual runs)
- **Tasks:** 3, one commit each
- **Files modified:** 6

## Accomplishments

- **The plan's factual error was caught before it could do damage, because
  the code was read instead of the artifact.** `33-09-PLAN.md:102` states
  that the two `stream_cash_movements_csv` bounds sites "were switched to
  `business_date_bounds` by plan 33-07". They were not — 33-07 recorded that
  as its Deviation 2 and a BLOCKING hand-off, and both call sites still read
  `local_day_bounds_utc(...)` with a comment naming this plan as the owner.
  Both were switched **in the same commit** as the predicate. Splitting them
  would have left an intermediate commit where the CSV body and the CSV's own
  row filter disagree about which date they mean — the T-33-20 half-switch,
  which "works" at Europe/Moscow by lexicographic accident and drops **every**
  row at UTC and any negative offset.
- **CD-9 is not just done, it is proven to be load-bearing.** The plan
  authorised switching `export.py:214`'s `ORDER BY` alongside `:135`, and
  `test_csv_first_column_non_decreasing` was written to cover both. That
  single assertion could easily have been satisfied by the sales half alone,
  so it was run against **two** counterfactuals: with both clauses reverted it
  fails, and with **only** the CD-9 one reverted it fails too (measured:
  `[2026-06-20, 2026-06-10, 2026-06-15]`). The cheap assertion really does
  cover the edit D-23 forgot to enumerate.
- **Every diff hunk in `export.py` lands inside the two dated writers.**
  `stream_products_csv` (no date column) and `stream_customers_csv` (its
  «Создан» is `Customer.created_at` on a table that gains no `business_date`)
  are untouched — verified by reading the hunk headers, and pinned by
  `test_products_and_customers_csv_unchanged` against HEAD-recorded header
  constants.
- **The accepted cost is written into the code, not just into a plan file.**
  A comment above each header list states that column 1's value TYPE narrows
  from `dd.mm.yyyy HH:MM` to `dd.mm.yyyy`, that the `HH:MM` reappears verbatim
  in «Внесено», and that positions 1..N do NOT shift so an operator's existing
  spreadsheet formula over `Код` / `Цена` / `Сумма` keeps working. The test
  asserts those three indexes **by name**, not only by slice equality.
- **`app/` no longer names `local_day_bounds_utc` anywhere outside its own
  definition.** `grep -c` returns **0** for both finance route modules (33-07
  measured 2 / 2, the import plus the CSV site); the now-unused import was
  dropped from each.
- **DATE-08 is pinned at the sharpest possible point.** The NULL-business-date
  fixture's `created_at` is `2026-05-20T21:30:00+00:00`, whose Europe/Moscow
  day is `2026-05-21`. The test asserts that value is **NOT** what column 1
  renders — it renders the UTC prefix `20.05.2026`, matching the COALESCE the
  row was selected by. Anyone "unifying" the read fallback with migration
  0027's tz-correct backfill reddens immediately.

## Task Commits

1. **Task 1 — the predicate, both ORDER BY clauses, and BOTH route callers** — `b322aec`
   (`feat(33-09): select and order both CSV dumps by the business date`)
2. **Task 2 — «Когда» becomes the business date, «Внесено» appended last** — `5459b31`
   (`feat(33-09): «Когда» becomes the business date, «Внесено» appended last`)
3. **Task 3 — the seven pinning tests** — `2309d92`
   (`test(33-09): pin the CSV contract, incl. the ORDER BY D-23 never enumerated`)

## Files Created/Modified

- `app/services/export.py` *(+59/−12)* — `stream_cash_movements_csv`'s
  predicate switched to `business_date_expr(CashMovement)` with `>= start_day`
  AND `<= end_day`; its parameters renamed `start_iso`/`end_iso` →
  `start_day`/`end_day`; its docstring and the module-level T-06-09 paragraph
  restated in terms of the new bound. Both `ORDER BY` clauses became the
  three-part deterministic order. Column 1 of both dated writers renders
  `format_ru_date(business_date or created_at[:10])`; a new LAST column
  «Внесено» renders `iso_to_local(created_at, display_tz)`. One new import
  each: `business_date_expr` (from `app.services.reports` — no cycle, that
  module imports only `app.config` / `app.core` / `app.models`) and
  `format_ru_date`.
- `app/routes/finance.py`, `app/routes/mobile_finance.py` — the CSV bounds
  site in each flipped to `business_date_bounds`, 33-07's hand-off comment
  replaced by one stating the pair is now one unit, and the orphaned
  `local_day_bounds_utc` import dropped.
- `tests/test_export.py` *(+7 tests, 4 fixture sites re-pointed, 1 renamed)* —
  `_local_day_of` copied from the wave-4 idiom; four period-bounds sites moved
  to `business_date_bounds` with a tz-correct `business_date=` on each fixture
  row; `*_half_open_period_and_order` renamed and re-pointed at the closed
  contract; both header assertions extended.
- `tests/test_finance_reports.py` — the two route CSV tests 33-07 predicted
  would go red got the tz-correct `business_date=` on their fixture row, and
  their header assertions were tightened from what had become a proper prefix
  back to the FULL header line.
- `app/__init__.py` — `__version__` 1.91 → 1.92 → 1.93 → 1.94 (one bump per
  task commit; the scheme is a plain counter, not float arithmetic).

## Deviations from Plan

### 1. [Rule 1 — the plan's `read_first` was factually wrong] Both route callers switched here, and they are not in `files_modified`

- **Found during:** Task 1, before the first edit — the orchestrator flagged
  it and the live code was read to confirm.
- **Issue:** `33-09-PLAN.md:102` asserts the two callers "were switched to
  `business_date_bounds` by plan 33-07". Measured at HEAD before editing:
  `app/routes/finance.py:379` and `app/routes/mobile_finance.py:377` both
  still called `local_day_bounds_utc`, each under a comment from 33-07 naming
  this plan as the owner. Neither file appears in this plan's
  `files_modified`.
- **Fix:** Both switched in commit `b322aec`, the same commit as
  `export.py`'s predicate, together with the orphaned import in each. The two
  route tests 33-07 named (`test_web_finance_report_csv_streams_period_scoped_csv`
  and `test_web_mobile_finance_report_csv`) were updated in that same commit —
  expected, not a regression.
- **Files modified beyond the plan's list:** `app/routes/finance.py`,
  `app/routes/mobile_finance.py`, `tests/test_finance_reports.py`.
- **Commit:** `b322aec`

### 2. [Rule 1 — the plan's acceptance criterion was unsatisfiable] Four of the five `local_day_bounds_utc` sites in `tests/test_export.py` HAD to move

- **Found during:** Task 1.
- **Issue:** The plan's `<action>` and its acceptance criterion both say the
  five `local_day_bounds_utc` call sites "BUILD `created_at` values and must
  stay as they are". Read at HEAD, that is true of exactly **one** of them
  (`:182`). At `:111`, `:150`, `:164` and `:333` the helper's output is passed
  as the export **PERIOD**, i.e. straight into the predicate this plan
  switches — after which a UTC timestamp is compared against a date-only
  column and the file comes back empty at any non-positive UTC offset. The
  criterion as written cannot hold together with the change the same plan
  mandates.
- **Fix:** Those four moved to `business_date_bounds`, and each fixture row
  gained the tz-correct `business_date=_local_day_of(created_at)` — the wave-4
  idiom 33-07 established, without which `record_cash_movement` stamps TODAY
  and the row silently leaves the 2026-07-10 period. `:182` kept the helper,
  because there it genuinely builds two `created_at` instants.
- **Commit:** `b322aec`

### 3. `test_cash_movements_csv_half_open_period_and_order` renamed and re-pointed

- **Issue:** Its name and its assertion comment both describe the OLD
  half-open timestamp contract ("the `end_iso` row is excluded because the
  upper bound is exclusive"). Under the closed date-only contract that
  sentence is wrong even though the assertion still passes.
- **Fix:** Renamed to `test_cash_movements_csv_closed_period_and_order`,
  re-pointed at `business_date_bounds`, and given a docstring stating what it
  now exercises: **the last day of the range is INCLUDED, the next local day
  is not**. The two seeding instants are unchanged, and two new asserts pin
  the fixture's own premise so the outcome cannot be satisfied for the wrong
  reason if the tz conversion ever moves. Same shape as 33-07's
  `*_half_open_bounds` → `*_closed_bounds` treatment.

### 4. Parameters renamed `start_iso`/`end_iso` → `start_day`/`end_day`

Not asked for by the plan. Both call sites are positional so nothing broke,
and leaving `_iso` on a value that is now a 10-character date is precisely
the confusion Pitfall 14 exists to document. Under CLAUDE.md's
smallest-change rule this is on the path of the task: the parameter IS the
thing whose type changed.

### 5. The two route CSV header assertions were tightened

`assert "Когда;Категория;Валюта;Комментарий;Сумма" in text` still passes after
«Внесено» is appended — it has silently become an assertion about a *prefix*
of the header line. Both were extended to the full line so they keep pinning
what they were written to pin.

## Acceptance criteria read literally vs. read for intent

- **`grep -c "Внесено" app/services/export.py` returns 5, not 2.** Two are the
  header entries (`:158`, `:255`); the other three are inside the comments the
  same task's `<action>` REQUIRES ("Write that accepted cost as a comment above
  each header list", "Append a NEW LAST column with the header «Внесено»"). The
  criterion as literally written is unsatisfiable by the code the action
  mandates. Its intent holds: `grep -n '"Внесено"'` returns exactly the two
  header entries. Identical in shape to 33-06's documented
  `strftime`-in-a-docstring note and 33-07's `freezegun` note.
- **`git diff tests/test_export.py` DOES modify four of the five
  `local_day_bounds_utc` call sites** — see Deviation 2. The criterion assumed
  a false premise about what those five lines do.

### 6. No requirement marked complete, though the plan names two

`33-09-PLAN.md`'s frontmatter says `requirements: [DATE-03, DATE-05]`.
**DATE-03** is already `[x]` in `REQUIREMENTS.md` (33-07 + 33-08). **DATE-05**
reads «История **and** the CSV exports show both dates whenever they differ»,
and `33-14-PLAN.md`'s frontmatter lists it too — 33-14 carries the История
half (the «задним числом» marker). This plan delivers only the CSV half, so
marking DATE-05 complete here would make the traceability table claim work
that has not landed. Left `[ ]` for 33-14 to close, following the precedent
33-05 and 33-06 both set.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no port taken,
  no remote host contacted.
- One mechanical fixture problem: a NULL-`business_date` cash movement cannot
  be produced through `record_cash_movement` (it stamps today's local day in
  Python) nor patched afterwards (the `cash_movements_no_update` trigger
  ABORTs the UPDATE), so `_insert_pre_0027_movement` INSERTs it directly under
  a distinct `device_id` to stay clear of the per-device `(device_id, seq)`
  unique constraint. This is the same finding 33-07 recorded, and it is itself
  a confirmation of 33-06's "stamp in Python, never a column default" design.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_export.py -q` (Task 3 gate) | **23 passed** (16 pre-existing + 7 new) |
| `uv run pytest tests/test_export.py tests/test_finance_reports.py -q` (Tasks 1 & 2 gates) | **61 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-09.xml` (full suite) | **4 failed, 1628 passed, 14 skipped** in 440.85s |
| Test-count arithmetic | Baseline at plan start **1625** non-skipped (1622+3); this run **1632** (1628+4); this plan adds **7**. 1625 + 7 = 1632 exactly — **no pre-existing test that passed before this plan fails now, and none disappeared** |
| Counterfactual A — both `ORDER BY` clauses reverted | **RED**: `column 1 is not non-decreasing: [2026-06-20, 2026-06-10, 2026-06-15]` |
| Counterfactual B — **only** the CD-9 clause at `:214` reverted | **RED**, same message — the CD-9 edit is genuinely covered, not covered by accident |
| `grep -n "order_by" app/services/export.py` | `business_date_expr(Operation)` at `:139` and `business_day` at `:250`; the two undated writers keep `Product.name_lc` / `Customer.search_lc` |
| Cash-movement predicate upper bound | **`<=`** — the CLOSED contract, no `<` survives |
| `grep -c "local_day_bounds_utc" app/routes/finance.py app/routes/mobile_finance.py` | **0 / 0** (33-07 measured 2 / 2) |
| `git diff -U0 app/services/export.py` hunk headers | every hunk inside `stream_sales_csv` / `stream_cash_movements_csv` plus the import line — **no hunk touches `stream_products_csv` or `stream_customers_csv`** |
| `grep -n '"Внесено"' app/services/export.py` | `:158`, `:255` — exactly one header entry per dated writer, LAST in each |
| `uv run ruff check` on `app/services/export.py`, `tests/test_finance_reports.py` | **All checks passed** |
| `uv run ruff check app/routes/finance.py app/routes/mobile_finance.py` | **11 E501** (6 + 5) — the identical pre-existing set 33-07 measured; none on a line this plan wrote |
| `uv run ruff check tests/test_export.py` | **1 E501** at `:333`, the pre-existing `test_sales_csv_roundtrip` docstring |
| `git diff --diff-filter=D` on all three commits | **empty** — nothing deleted |
| `git status --porcelain` (tracked files) | **clean** |
| `git diff --stat app/static/style.css` | **empty** — 33-06's W-6 rule holds |

**Full-suite result read carefully.** The 4 failures are **exactly** the four
documented known-red `tests/test_sync_ui.py` cases
(`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`,
`test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`),
each failing on `sync_client._run_lock` being held by the lifespan auto-sync
thread — red since ≤ `49a53d2`, count varies 2–4 per run, unrelated to this
plan.

### Real-path check (not a test)

A green suite is not evidence the export works. Driven **in-process** against
the real FastAPI app, real routes and a throwaway SQLite file under the
scratchpad — **no server started, no port taken, no remote host touched.** Two
sales and two cash movements, all entered TODAY (`04.09.2026 16:55`) and
back-dated to `2026-06-20` and `2026-06-15`, seeded in an order that
contradicts their business dates. **All 20 checks PASS:**

| Route | Observed |
|-------|----------|
| `GET /export/sales.csv` | 200; header `Когда;Код;Товар;Кол-во;Цена;Себестоимость;Валюта;Покупатель;Кто;Внесено` — 10 columns, «Внесено» last, `Код` at index 1 and `Цена` at index 4; rows `15.06.2026 … 04.09.2026 16:55` then `20.06.2026 … 04.09.2026 16:55` — **non-decreasing despite the reversed seeding order**, column 1 day-only, the `HH:MM` intact in the last cell |
| `GET /finance/report.csv?from=2026-06-15&to=2026-06-20` | 200; header `Когда;Категория;Валюта;Комментарий;Сумма;Внесено` — 6 columns, `Сумма` still at index 4; both back-dated rows present and non-decreasing |
| `GET /finance/report.csv?from=2026-09-04&to=2026-09-04` (the ENTRY day) | 200; **0 data rows** — the row set really follows the business date. This is the exact inverse of what 33-07 observed live and documented as the open gap ("the CSV still buckets by ENTRY date … 33-09 closes it"). Closed. |
| `GET /m/finance/report.csv?…` | 200; **byte-identical to the desktop CSV** |
| `GET /export/products.csv` | 200; header `Код;Название;Категория;Закупка;Продажа;Остаток;Удалён` — no «Внесено» |
| `GET /export/customers.csv` | 200; header `Имя;Фамилия;Номер консультанта;Создан` — no «Внесено» |

**Not checkable here:** nothing in this plan renders a template, so
`33-UI-SPEC.md`'s browser checks B-1…B-6 are untouched by it. **B-7** (open a
real export in a spreadsheet after a back-dated row exists) is a human check
owned by plan `33-15`; everything it asserts about column count, header
position and ordering is observed above at the byte level, but the
"does Excel open it correctly" half is not runnable here.

## Success Criteria

- [x] `cash_movements.csv` selects rows by the business date and orders by it.
- [x] Both files show the business date in «Когда» and the entry timestamp in a new last «Внесено».
- [x] `stream_products_csv` and `stream_customers_csv` are byte-unchanged.
- [x] Both `stream_cash_movements_csv` callers switched in the SAME commit as the export change, with their tests updated.
- [x] `export.py:214`'s `ORDER BY` switched alongside `:135` — and proven load-bearing by its own counterfactual.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-25 (CSV formula injection through a cell) | **Accept, unchanged** — every free-text cell still goes through `_csv_safe`, and the two columns this plan touches are machine-rendered dates (`format_ru_date` / `iso_to_local`) which cannot carry a leading `=`, `+`, `-` or `@`. `test_cash_movements_csv_escapes_formula_injection_note` and `test_sales_csv_roundtrip`'s `'=cmd Тестова` assertion both still pass |
| T-33-26 (an export whose headline date column contradicts its own period) | **Mitigated** — column 1, the row-set predicate and both `ORDER BY` clauses use the SAME `business_date_expr`, and the render's NULL fallback (`created_at[:10]`) is byte-identical to the query's COALESCE fallback. Pinned by `test_csv_null_business_date_falls_back_to_utc_prefix`, which asserts the UTC day and explicitly asserts the tz-correct local day is NOT used |
| T-33-27 (a dump that reads as unsorted by its own first column) | **Mitigated, and proven** — both `ORDER BY` clauses switched, pinned by `test_csv_first_column_non_decreasing`, which was run against a per-edit counterfactual so neither clause's coverage rests on the other's |
| T-33-16 (SQL injection via a period bound) | **Mitigated** — `business_date_bounds` takes parsed `date` objects from `_resolve_period` and returns `.isoformat()` strings; both reach SQL as bound ORM parameters. No string interpolation was added |
| T-33-20 (half-switched family) | **Mitigated** — predicate and both bounds call sites in ONE commit; this is the specific defect 33-07 held these two lines back to avoid |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** Every line this plan owns is switched and reachable from a real
route — all six routes exercised live in the table above. Nothing was left
hardcoded, placeholdered or unwired.

## Threat Flags

None. No new network endpoint, no new auth path, no new file-access pattern,
no schema change. The one trust boundary touched (stored ledger text → a
spreadsheet host) is T-33-25, already enumerated, and this plan narrows the
crossing surface rather than widening it: the column whose value changed now
carries a machine-rendered date instead of free text.

## User Setup Required

None. No configuration, no migration to run by hand, no dependency, no server
action.

## Next Phase Readiness

- **33-07's BLOCKING hand-off is CLOSED.** `app/routes/finance.py` and
  `app/routes/mobile_finance.py` no longer name `local_day_bounds_utc` at all,
  and the behaviour 33-07 observed live as the open gap (the cash CSV bucketing
  by ENTRY date) is observed inverted above.
- **For 33-13** (`app/services/finance.py` + the withdraw/deposit forms + the
  `op_date` field): this plan touched `app/routes/finance.py` and
  `app/routes/mobile_finance.py` **only** at the `report.csv` route in each.
  The cash write forms, `_movement_success`, and every other line in both
  modules are byte-unchanged, so 33-13's edits do not collide. Note that both
  modules' `from app.core import ...` line changed — rebase, do not assume.
- **For 33-15's manual check B-7:** the byte-level half is already observed
  (10 sales columns / 6 cash columns, «Внесено» last, `Код`/`Цена`/`Сумма` at
  their original indexes, column 1 non-decreasing). What remains for a human
  is opening the file in a real spreadsheet.
- **Unchanged and still open:** the four known-red `tests/test_sync_ui.py`
  cases (pre-existing), the `I001`/`E402` pair on `app/routes/__init__.py`, the
  11 pre-existing E501s in the two finance route modules and the 1 in
  `tests/test_export.py` (all deliberately not fixed), the PostgreSQL CI parity
  run (plan `33-15`), and the production rollout (`33-ROLLOUT.md`, human-owned).
  `business_date_expr` renders as portable `substr(...)` on both dialects, so
  this plan adds no new PostgreSQL risk to that run.

## Self-Check: PASSED

All six modified files exist on disk with the described content. Commits
`b322aec`, `5459b31` and `2309d92` are all present in `git log`, together
touch exactly those six files and nothing else, and none deletes a tracked
file (`git diff --diff-filter=D` empty on all three).

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
