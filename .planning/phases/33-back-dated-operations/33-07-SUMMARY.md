---
phase: 33-back-dated-operations
plan: 07
subsystem: period-reports
tags: [reports, finance, dashboard, timezone, sqlalchemy, migration, coalesce, portable-orm]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "business_date_bounds (CLOSED date-only bounds), business_date_expr (the COALESCE read expression), and the business_date keyword on both write paths"
  - phase: 33-back-dated-operations
    plan: 05
    provides: "migration 0027 and its tz-correct backfill — the thing VA-9 runs for real"
provides:
  - "app/services/reports.py — sales_profit_report / writeoff_report / top_selling_products bucket by business_date_expr(Operation) over a CLOSED range"
  - "app/services/finance_reports.py — cash_expense_total / cash_flow_report bucket by business_date_expr(CashMovement), moved as one unit"
  - "app/services/dashboard.py::period_metrics — today/week/month tiles follow the business date (body only; signature unchanged)"
  - "tests/test_business_date.py::test_sales_profit_byte_identical_across_migration — the DATE-07 proof, with a counterfactual naive-backfill divergence check"
  - "tests/test_reports.py::_local_day_of + business_date= on both seeding helpers — the fixture idiom waves 5-6 should copy"
affects: [33-08, 33-09, 33-10, 33-11, 33-12, 33-13, 33-14, 33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A period predicate and the call site that produces its bounds are ONE unit and must land in ONE commit — a date-only column compared against UTC timestamp bounds passes at Europe/Moscow by lexicographic accident and drops every row at UTC and any negative offset"
    - "A test fixture that seeds a past created_at must also seed the tz-correct business_date of that timestamp; otherwise record_operation's Python-side default stamps TODAY and the fixture silently lands in today's bucket"
    - "«Byte-identical across a migration» is ONE deterministic test (build at N-1, seed, migrate, compare), plus a counterfactual run under the WRONG rule asserted to DIVERGE — without the counterfactual the equality only proves that two identical rules agree"
    - "When a mapped class is ahead of the revision under test, take both reads after the migration and PIN the soundness of that with a raw column-by-column snapshot equality across it, rather than assuming the migration was additive"

key-files:
  created: []
  modified:
    - app/services/reports.py
    - app/routes/reports.py
    - app/services/finance_reports.py
    - app/routes/finance.py
    - app/routes/mobile_finance.py
    - app/services/dashboard.py
    - tests/test_reports.py
    - tests/test_finance_reports.py
    - tests/test_dashboard.py
    - tests/test_business_date.py
    - tests/test_attribution.py
    - app/__init__.py

key-decisions:
  - "33-07 (D-25, and the SUMMARY is required to say it): D-25 NARROWS ROADMAP success criterion 2. That criterion names «the stock and write-off reports»; only writeoff_report switches. stale_products stays on func.max(Operation.created_at) BY DECISION, not by omission, and app/templates/pages/reports_products.html is untouched (cancelled edit). Now pinned by a test, not only by a comment."
  - "33-07 (T-33-20, overrides the plan's commit granularity): Tasks 1 and 2 shipped in ONE commit. They are not separably committable — app/routes/finance.py::_metrics_context builds a single bounds pair feeding BOTH families, and cash_flow_report/cash_expense_total are pinned to each other by the D-05 reconciliation invariant. Every possible split leaves a commit with a RED suite and a half-switched predicate."
  - "33-07 (the plan's own T-33-20 rule, applied AGAINST the plan's letter): app/routes/finance.py:379 and app/routes/mobile_finance.py:377 were NOT switched. They feed export_service.stream_cash_movements_csv, which still filters CashMovement.created_at — 33-09 owns that predicate. Switching them here is a demonstrated break, not a theoretical one: it reddens two existing route tests."
  - "33-07: the existing test fixtures could NOT stay unchanged (the plan's acceptance criterion assumed otherwise). record_operation/record_cash_movement stamp business_date = TODAY by default, so every historical fixture would have landed in today's bucket. The seeding helpers now derive the tz-correct local day of their own created_at — exactly what migration 0027 backfills — which preserves each test's original meaning including the local-midnight straddle cases."
  - "33-07: the two *_half_open_bounds tests in test_finance_reports.py were RENAMED to *_closed_bounds and re-pointed at the new contract, keeping the same seeding instants and the same outcome but for the correct reason, and gaining last-day-inclusive assertions (Pitfall D)."
  - "33-07: tests/test_attribution.py was touched although it is outside the plan's file list. Leaving it would have made it pass at Europe/Moscow purely by the lexicographic accident and fail on any UTC CI runner — a regression introduced by this plan's switch, so fixing it is Rule 1, not scope creep."

patterns-established:
  - "A counterfactual assertion beside an equality assertion: run the same code under the rule you claim is wrong and assert it produces a DIFFERENT answer, so the equality cannot be satisfied vacuously"

requirements-completed: [DATE-03, DATE-07]

# Metrics
duration: ~95min
completed: 2026-09-04
---

# Phase 33 Plan 07: Period Reports on the Business Date Summary

**Six period reports — sales/profit, write-offs, top-selling, cash-expense, cash-flow and the dashboard tiles — now bucket a back-dated row by the day the goods actually moved, over a CLOSED inclusive range; `stale_products` provably does not; and a fixed past period's `sales_profit_report` is proven byte-identical across the real `0027` migration by a test that also runs the wrong rule and asserts it diverges.**

## Performance

- **Duration:** ~95 min (including two full-suite runs at ~6m45s each)
- **Tasks:** 3 planned, 2 commits (Tasks 1+2 are not separably committable — see Deviations)
- **Files modified:** 12

## Accomplishments

- **The switch is complete and mechanical.** Five predicates moved from
  `created_at` timestamp comparisons to `business_date_expr(M)` with the
  CLOSED contract, and every `< end_iso` became `<= end_day`. Seven bounds
  call sites moved to `business_date_bounds` in the same commit. `grep` for
  `<` against a period upper bound in the switched functions returns nothing.
- **The predicate/bounds pairing was enforced against the plan's own letter
  where the two conflicted.** The plan listed the two CSV routes among the
  sites to switch; they feed `stream_cash_movements_csv`, whose predicate is
  still `CashMovement.created_at` and belongs to plan 33-09. Switching them
  is not a theoretical half-switch — it reddens
  `test_web_finance_report_csv_streams_period_scoped_csv` and its mobile twin
  immediately, which is how it was caught. They stay put, each carrying a
  comment naming 33-09 as the plan that must flip them in the same commit as
  `export.py:211-212`.
- **D-25 is now a test, not a comment.**
  `test_stale_products_is_not_switched_to_business_date` records a sale
  entered TODAY but back-dated a year and asserts the product is NOT stale —
  the exact opposite of what a business-date bucket would say. A future sweep
  that "finishes the job" reddens instead of silently changing the meaning of
  «сколько не продавался».
- **VA-9 has teeth.** The byte-identity assertion alone would pass against a
  naive `substr(created_at, 1, 10)` backfill unless a fixture actually moves
  under it, so the test additionally recomputes the same report under exactly
  that counterfactual and asserts divergence. Measured: **13 units under the
  naive cut against the correct 6**, and it diverges in BOTH directions — the
  naive cut drops the straddling row (local Sep 1, UTC Aug 31) and pulls in a
  next-local-day row (local Sep 2, UTC Sep 1).
- **The "before" read was made sound rather than assumed.** The mapped
  `Operation` class names `business_date` and `reverses_op_id`, so an ORM
  entity load against a 0026 schema dies with `no such column` before it can
  aggregate anything — the plan's literal four-step shape cannot execute. Both
  reads therefore happen after the migration, and a raw column-by-column,
  row-by-row snapshot of the 0026 column set is asserted **byte-identical
  across the migration** to prove that legitimate. That is a stronger DATE-04
  statement than the plan asked for: it proves both that the source data did
  not move and that the aggregate did not.
- **The reconciliation invariant is pinned over a deliberately awkward row
  mix.** `cash_flow_report(...)["expense_total_cents"] == cash_expense_total(...)`
  is asserted over on-time, back-dated, income, and NULL-`business_date` rows
  across a multi-day range whose LAST day carries the back-dated row — so the
  assertion exercises the closed bound, DATE-08 and the pairing at once.
- **Every fixture helper now models a post-backfill row.** `_local_day_of`
  (three test modules) derives the tz-correct local day of the fixture's own
  `created_at` — the same conversion migration 0027 performs — so historical
  fixtures keep the period they always meant, including the local-midnight
  straddle cases that would break under a `[:10]` shortcut.

## Task Commits

1. **Tasks 1 + 2 — the switch (5 predicates, 7 bounds sites, 9 tests)** — `fece0e4`
   (`feat(33-07): switch six period reports to the business date, in one pass`)
2. **Task 3 — VA-9 / VA-10 / VA-12** — `1073142`
   (`test(33-07): VA-9 byte-identity across the real 0027 migration`)

## Files Created/Modified

- `app/services/reports.py` — three period predicates switched; three
  docstrings restated in terms of the CLOSED business-date contract.
  `stale_products` gains a 7-line D-25 comment above `last_sale` and **not one
  executable line changed inside it** (verified by reading the diff hunk).
- `app/routes/reports.py` — import swapped to `business_date_bounds`; the
  three call sites collapsed from 3-line to 1-line calls (the `display_tz`
  argument disappears because no conversion happens). `settings` is still used
  by four other lines, so the module import stays.
- `app/services/finance_reports.py` — both cash predicates switched; imports
  `business_date_expr` from `app.services.reports` (no cycle: that module
  imports only `app.config`, `app.core`, `app.models`). Both docstrings now
  cross-reference each other's pairing.
- `app/routes/finance.py`, `app/routes/mobile_finance.py` — two bounds sites
  each switched; **the CSV site in each is deliberately NOT switched** and
  carries a comment naming 33-09. Both modules therefore import BOTH helpers.
- `app/services/dashboard.py` — import and the single body line at
  `period_metrics`. Signature unchanged, `tz_name` retained, `:41`, `:60-72`
  and the recent-N feed at `:156` untouched.
- `tests/test_reports.py` *(+6 tests)* — `_local_day_of`; `business_date=` on
  both seeding helpers; 12 bounds sites re-pointed; VA-13 pairs for all three
  reports (per-reason for write-offs, ranking for top-selling), a
  last-day-inclusive guard, a DATE-08 row, and the D-25 pin.
- `tests/test_finance_reports.py` *(+2 tests)* — `_local_day_of`; the two
  `*_half_open_bounds` tests renamed and re-pointed to the closed contract
  with last-day assertions added; the back-dated pair; the reconciliation pin
  over mixed rows.
- `tests/test_dashboard.py` *(+1 test)* — `_local_day_of` on all three
  seeders; a back-dated sale AND cash movement asserted into the right
  day/week/month bucket and out of their entry day.
- `tests/test_business_date.py` *(+3 tests)* — VA-9 with its counterfactual,
  VA-10's second half (migration 0027 loaded by path, pinned at a positive
  offset, a negative one and UTC), and VA-12.
- `tests/test_attribution.py` — 2 lines: the bounds helper, with a comment
  explaining the UTC-runner failure mode it prevents.
- `app/__init__.py` — `__version__` 1.76 → 1.77 → 1.78 (one bump per commit).

## D-25 narrows ROADMAP success criterion 2

**Stated here because the plan requires it, and because a verifier reading
only `.planning/ROADMAP.md` would otherwise mark a correct implementation as
failing.**

`.planning/ROADMAP.md:304` (success criterion 2) lists «the stock and
write-off reports» among the surfaces that must bucket by the business date.
Of the two reports that criterion names, **only `writeoff_report` switches.**
`stale_products` (`app/services/reports.py`, `last_sale =
func.max(Operation.created_at)`) **deliberately stays on `created_at`** — it
answers «how long since this product last moved», a question about real
elapsed time, not about the operator's bookkeeping period. A back-dated entry
made today must not make a product look freshly sold a month ago.

`33-CONTEXT.md:326-334` is newer than `.planning/ROADMAP.md` and is the
binding contract where the two disagree; `33-ROLLOUT.md` § Scope notes records
the same. This plan required proving it untouched, and does so three ways: the
diff shows no executable change inside the function, the coupled template edit
at `reports_products.html:32` was never made, and
`test_stale_products_is_not_switched_to_business_date` now fails if anyone
switches it later.

## Deviations from Plan

### 1. [Rule 3 — blocking] Tasks 1 and 2 shipped in ONE commit

- **Found during:** Task 1, at the pre-commit regression check.
- **Issue:** The plan says "each task committed individually". These two
  cannot be. `app/routes/finance.py::_metrics_context` builds a SINGLE bounds
  pair that feeds `sales_profit_report` (Task 1) **and** `cash_expense_total`
  (Task 2), and `cash_flow_report`/`cash_expense_total` are pinned to each
  other by the D-05 reconciliation invariant. Committing Task 1 alone leaves
  `dashboard.period_metrics` and both finance routes passing UTC timestamp
  bounds into a switched predicate — the exact T-33-20 half-switch — and it is
  not merely latent: the dashboard and finance suites go RED at that commit.
  No reordering produces a coherent split; every arrangement breaks either the
  bounds pairing or the reconciliation invariant.
- **Fix:** One commit for the switch, one for the tests. The plan's own
  objective ("a predicate and the call site that produces its bounds MUST move
  together") is treated as outranking its commit-granularity instruction.
- **Commit:** `fece0e4`

### 2. [Rule 1 — bug in the plan's instruction] The two CSV bounds sites were NOT switched

- **Found during:** Task 2.
- **Issue:** The plan lists `finance.py:376` and `mobile_finance.py:377` among
  the sites to switch. Both feed `export_service.stream_cash_movements_csv`,
  which filters `CashMovement.created_at >= start AND < end`. Handing it
  date-only bounds is the T-33-20 half-switch in its purest form. This is
  **demonstrated, not predicted**: switching them makes
  `test_web_finance_report_csv_streams_period_scoped_csv` and
  `test_web_mobile_finance_report_csv` fail immediately, because
  `'2026-07-10T10:00:00+00:00' < '2026-07-10'` is false.
- **Fix:** Left on `local_day_bounds_utc`, each with a comment naming plan
  33-09 as the owner of `export.py:211-212` and stating that both lines must
  flip in that same commit.
- **Consequence for this plan's acceptance criteria:**
  `grep -c "local_day_bounds_utc" app/routes/finance.py` returns **2**, not 0
  (import + the CSV site); same for `mobile_finance.py`.
  `app/services/dashboard.py` returns **0** as specified.
- **Hand-off to 33-09 — the one thing that must not be lost:** 33-09's plan
  text (`33-09-PLAN.md:102`) asserts these bounds "were switched to
  `business_date_bounds` by plan 33-07". **They were not.** 33-09 must switch
  `app/routes/finance.py:379` and `app/routes/mobile_finance.py:377` in the
  same commit as `export.py:211-212`. This will not be missed silently: if
  33-09 switches only the predicate, the same two route tests go red.

### 3. [Rule 3 — blocking] The pre-existing test fixtures could not stay unchanged

- **Found during:** Task 1, first test run.
- **Issue:** The plan's acceptance criterion says the suite must be green
  "including the pre-existing tests unchanged". That is not achievable.
  `record_operation` / `record_cash_movement` stamp
  `business_date = local_today_iso(...)` by default (33-06's DATE-08 design),
  so every fixture with a historical `created_at` carries **today's** business
  date and lands in today's bucket once the predicates switch. Separately, the
  bounds those tests build are UTC timestamps, which a date-only column only
  "matches" at Europe/Moscow by the documented lexicographic accident.
- **Fix:** Each seeding helper now stamps the **tz-correct local day of its
  own `created_at`** — precisely what migration 0027 backfills for a
  pre-existing row — so every test keeps its original meaning, including
  `test_sales_report_excludes_outside_period`, whose 20:59:59 / 21:00:00 UTC
  pair still straddles local midnight and still yields the same assertion. The
  report-side bounds moved to `business_date_bounds`. Five tests that called
  `record_operation` / `record_cash_movement` directly got an explicit
  `business_date=`.
- **Files modified:** `tests/test_reports.py`, `tests/test_finance_reports.py`,
  `tests/test_dashboard.py`

### 4. [Rule 1] `tests/test_attribution.py` fixed, though outside the plan's file list

- **Issue:** It calls `sales_profit_report` with `local_day_bounds_utc` bounds
  over `_seed_sale_op` rows whose `business_date` is NULL. After the switch it
  passes at Europe/Moscow purely by the lexicographic accident and DROPS every
  row at UTC — i.e. it would go red on a UTC CI runner. That is a regression
  introduced by this plan.
- **Fix:** 2 lines (import + call site), with a comment naming the failure mode.

### 5. VA-9's four-step shape had to be restructured to be executable

- **Issue:** The plan's step 2 ("seed at 0026 and record `before =
  sales_profit_report(...)`") cannot run: `sales_profit_report` does
  `select(Operation, Product)`, and the mapped class names `business_date` and
  `reverses_op_id`, which do not exist at revision 0026 —
  `OperationalError: no such column: operations.reverses_op_id`.
- **Fix:** The seed still happens at 0026 (asserted via `PRAGMA table_info`),
  so the business dates genuinely come from the migration's backfill and not
  from a write-time stamp. Both reads happen after the migration, and the
  soundness of that is **asserted, not assumed**: the raw 0026 column set is
  snapshotted before and after and compared row-by-row for byte-identity
  (which is itself the DATE-04 claim). The "before" read then runs the REAL
  `sales_profit_report` body with `business_date_expr` monkeypatched back to
  `Operation.created_at` and the original UTC bounds.
- **Residual caveat, stated in the test docstring:** the old predicate's upper
  bound was `<` and the new one is `<=`. No fixture sits exactly on `end_iso`
  (the nearest is 30 minutes past it), so the two comparisons select the same
  rows and the equality is about bucketing, not about the bound change.

### 6. Whole-dict comparison uses a documented projection

`by_product[i]["product"]` holds a live ORM instance and the two reports are
necessarily read through different Sessions, so those are distinct objects for
the same row. `_comparable()` replaces that ONE value with `product.id` and
compares everything else — `totals`, `cost_unknown_count`, and every
per-product `qty`/`revenue_cents`/`cost_cents`/`profit_cents` — verbatim. The
per-line breakdown the plan cares about is fully compared.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no remote host
  contacted.
- Three mechanical fixture problems surfaced and were fixed inside their own
  task: `products` has NOT NULL `created_at`/`updated_at` (solved by seeding
  products through the ORM, which is exact because `products` is unchanged
  between 0026 and head); `next_seq` counts `Operation.seq` and cannot supply
  a `CashMovement.seq`; and a NULL `business_date` row must be INSERTed that
  way, because the `cash_movements` append-only trigger ABORTs the UPDATE —
  which is itself a nice confirmation of 33-06's "stamp in Python, never a
  column default" reasoning.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_reports.py -q` (Task 1 gate) | **50 passed** |
| `uv run pytest tests/test_dashboard.py tests/test_finance.py tests/test_finance_reports.py tests/test_reports.py -q` (Task 2 gate) | **194 passed** |
| `uv run pytest tests/test_business_date.py -q` (Task 3 gate) | **20 passed** |
| `uv run pytest tests/test_business_date.py -k timezone -q` (VA-10) | **3 passed** — Europe/Moscow, America/New_York and UTC all exercised |
| `uv run pytest tests/ -q --junitxml=reports/33-07.xml` (full suite) | **3 failed, 1533 passed, 14 skipped** in 404.02s |
| Test-count arithmetic | 33-06 baseline **1524** non-skipped (1520+4); this run **1536** (1533+3); this plan adds **12** (6+2+1 in the switch commit, 3 in the test commit). 1524 + 12 = 1536 exactly — **no pre-existing test that passed before this plan fails now, and none disappeared** |
| `grep -c "local_day_bounds_utc" app/routes/reports.py` | **0** |
| `grep -c "local_day_bounds_utc" app/services/dashboard.py` | **0** |
| `grep -c "local_day_bounds_utc" app/routes/finance.py` / `mobile_finance.py` | **2 / 2** — import + the CSV site, deliberate (Deviation 2) |
| `git diff` hunk inside `stale_products` | **comment only** — `last_sale = func.max(Operation.created_at)` and every line below it byte-unchanged |
| `git diff --stat app/templates/pages/reports_products.html` | **empty** — D-25's cancelled edit was never made |
| `git diff --stat app/static/style.css` | **empty** — 33-06's W-6 rule for every wave-4+ plan holds |
| Every switched comparison against `end_iso` | **`<=`** — five predicates, ten comparison lines, no `<` survives |
| `uv run ruff check` on the 4 new/changed test files + `reports.py`, `finance_reports.py`, `dashboard.py`, `routes/reports.py` | **All checks passed** |
| `uv run ruff check app/routes/finance.py app/routes/mobile_finance.py` | **11 E501**, all PRE-EXISTING — the identical 6 + 5 are returned by piping the HEAD version through `ruff check --stdin-filename`. Not introduced here, not fixed here |
| `git diff --diff-filter=D` on both commits | **empty** — nothing deleted |
| `git status --porcelain` (tracked files) | **clean** |

**Full-suite result read carefully.** The 3 failures are three of the four
documented known-red `tests/test_sync_ui.py` cases
(`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`,
`test_lock_hit_returns_locked_partial`), each failing on
`sync_client._run_lock` being held by the lifespan auto-sync thread — red
since ≤ `49a53d2`, count varies 2–4 per run, unrelated to this plan.

### Real-path check (not a test)

A green suite is not evidence the pages work. Driven **in-process** against
the real FastAPI app, real Jinja templates and a throwaway SQLite file under
the scratchpad — **no server started, no port taken, no remote host touched**.
One sale, one write-off and one cash movement, all entered TODAY with
`business_date = 2026-06-15`. All 21 checks PASS:

| Route | Observed |
|-------|----------|
| `GET /reports/sales?from=2026-06-15&to=2026-06-15` | 200; product `RP-001` present; revenue `60,00` rendered; currency `<option value="RUB">` present (non-empty select) |
| `GET /reports/sales?from=2026-07-01&to=2026-07-31` | 200; `RP-001` **absent** — it does not leak into an unrelated period |
| `GET /reports/writeoffs?…06-15` | 200; the per-reason line «Повреждён» + «Списания по причинам» present; the July period renders «За выбранный период списаний не было.» |
| `GET /reports/products?…06-15` | 200; top-selling half lists `RP-001`; the stale half still renders (D-25 untouched) |
| `GET /finance/report?…06-15` | 200; «Аренда» and «Расход» sections render the back-dated movement |
| `GET /finance/metrics?…06-15` | 200; expense tile shows `25,00` |
| `GET /m/finance/report?…06-15` | 200; mobile parity — same movement |
| `GET /finance/report.csv?…06-15` | 200; `25,00` **absent** — and `GET /finance/report.csv` (today) **contains** it. This is Deviation 2 observed live: the CSV still buckets by ENTRY date, exactly as documented, and 33-09 closes it |
| `GET /` | 200; dashboard renders with the switched `period_metrics` |

**Not checkable here:** no template renders `class="field op-date"` yet, so
`33-UI-SPEC.md`'s browser checks B-1…B-7 still have nothing to exercise —
they belong to plans `33-10` … `33-14`. Nothing in this plan changed a
template.

## Success Criteria

- [x] Sales-profit, write-off, top-selling, cash-expense, cash-flow and the dashboard all bucket by the business date, with a closed inclusive range.
- [x] A fixed past period's `sales_profit_report` is byte-identical before and after `0027` (DATE-07) — and the counterfactual naive backfill is asserted to DIVERGE, so the equality is not vacuous.
- [x] A NULL-business-date row still appears (DATE-08) — pinned at the report layer for sales and top-selling, and inside the cash reconciliation test for both cash predicates.
- [x] `stale_products` and `reports_products.html` are provably untouched (D-25), now by test as well as by diff.
- [x] The SUMMARY states that D-25 narrows ROADMAP success criterion 2 (own section above).

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-16 (SQL injection via a period bound) | **Mitigated** — `business_date_bounds` takes parsed `date` objects and returns `.isoformat()` strings; the routes parse the form dates through `_resolve_period` before the call, and every value reaches SQL as a bound ORM parameter. No string interpolation was added anywhere in this plan |
| T-33-20 (half-switched family) | **Mitigated, and enforced beyond the plan's letter** — predicate and bounds move in one commit; `cash_expense_total`/`cash_flow_report` move in the same edit and are pinned by `test_cash_flow_and_expense_total_reconcile_over_mixed_rows`; the two CSV sites were held back precisely BECAUSE switching them would have created this exact defect |
| T-33-21 (a period report silently dropping an un-upgraded client's rows) | **Mitigated** — `business_date_expr`'s COALESCE fallback, pinned by `test_null_business_date_still_reported` (VA-12) and by the NULL row inside the reconciliation test |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** Every predicate this plan owns is switched and reachable from a real
route (verified live, table above). The one deliberately unswitched pair —
the CSV bounds sites — is not a stub: it is a correct, coherent,
currently-shipping behaviour (bucket the cash CSV by entry date) that plan
33-09 changes on purpose, and it is documented at both call sites, in
Deviation 2, and in the hand-off note below.

## Threat Flags

None. No new network endpoint, no new auth path, no file-access pattern, no
schema change. The only trust boundary touched is the operator-chosen period
already enumerated as T-33-16, and this plan narrows it (parsed `date` objects
in, ISO strings out) rather than widening it.

## User Setup Required

None. No configuration, no migration to run by hand, no dependency, no server
action.

## Next Phase Readiness

- **BLOCKING hand-off to 33-09:** its plan text claims 33-07 already switched
  `app/routes/finance.py:379` and `app/routes/mobile_finance.py:377`. **It did
  not** (Deviation 2). 33-09 must flip those two lines in the same commit as
  `export.py:211-212`. Both call sites carry a comment saying so, and the two
  route tests go red if it is missed — so the failure mode is loud.
- **Ready for 33-08** (`customers.py`, `history.py`, `mobile_history.py` — the
  three modules that may still name `local_day_bounds_utc` in `app/`): the
  fixture idiom it will need is already in place. Copy `_local_day_of` and the
  `business_date=` keyword on the seeding helpers; without them every
  historical fixture silently lands in TODAY's bucket.
- **Ready for 33-10 … 33-14** (the write surfaces): unaffected by this plan,
  and `git diff app/static/style.css` is still empty as 33-06 requires.
- **Unchanged and still open:** the four known-red `tests/test_sync_ui.py`
  cases (pre-existing), the `ruff check` pair on `app/routes/__init__.py`
  (pre-existing, deliberately not fixed), the 11 pre-existing E501s in the two
  finance route modules, the PostgreSQL CI parity run (plan `33-15`), and the
  production rollout (`33-ROLLOUT.md`, human-owned).
- **Note for `33-15` Task 4:** `tests/test_business_date.py`'s module
  docstring contains the string "freezegun" (in the sentence stating the rule
  that it is NOT used). The literal
  `grep -c "freezegun\|time_machine\|time-machine"` acceptance check therefore
  returns 1, not 0. Same shape as 33-06's documented
  `strftime`-in-a-docstring note: no import exists, no dependency was added,
  `pyproject.toml` is untouched.

## Self-Check: PASSED

All twelve modified files exist on disk with the described content. Commits
`fece0e4` and `1073142` are both present in `git log`, together touch exactly
those twelve files plus nothing else, and neither deletes a tracked file
(`git diff --diff-filter=D` empty on both).

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
