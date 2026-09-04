---
phase: 33-back-dated-operations
plan: 08
subsystem: history-customers-warehouses
tags: [history, customers, warehouses, pagination, jinja, coalesce, portable-orm, ordering]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "business_date_bounds (CLOSED date-only bounds), business_date_expr (the COALESCE read expression), and the business_date keyword on record_operation"
  - phase: 33-back-dated-operations
    plan: 07
    provides: "the switch idiom itself — predicate and bounds in one commit, and the fixture rule that a historical created_at needs an explicit business_date"
provides:
  - "app/services/operations.py::history_view — the period predicate on business_date_expr(Operation), applied to BOTH stmt and count_stmt"
  - "app/routes/history.py + app/routes/mobile_history.py — bounds from business_date_bounds; no app/ history module names local_day_bounds_utc any more"
  - "app/services/customers.py::_spend_stmt — net spend bucketed by the business date over a CLOSED range"
  - "app/services/customers.py::last_order_date(session, customer_id) — SIGNATURE CHANGED: a self-contained MAX(business_date_expr(Operation)), no longer a pure function over purchase_history"
  - "app/services/warehouses.py — «Последняя приёмка» as MAX(business_date_expr(Operation))"
  - "tests/test_history.py::test_recent_feeds_still_order_by_created_at — VA-17, the standing guard that display order did NOT move"
  - "tests/conftest.py::past_sale — optional business_date= kwarg (default None, preserving the DATE-08 NULL path)"
affects: [33-09, 33-10, 33-11, 33-12, 33-13, 33-14, 33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A paginated read carries its period predicate TWICE — on the row query and on the count query. They are one edit, and the only assertion that catches a half-switch is an explicit `len(rows) == total` over a filtered period; every other test reads one or the other"
    - "When a displayed value is derived by INDEXING an ordered list, switching the displayed FIELD is not enough — the ordering decides which row is read. Either the ordering moves too or the value gets its own aggregate. Here D-22 forbids moving the ordering, so the value got its own MAX()"
    - "A comment that instructs the opposite of the new truth is worse than no comment. Switching a cell's type means rewriting its render comment in the same commit, not leaving it to mislead"
    - "A route-level assertion is the only thing that proves the ROUTE hands the switched predicate the matching bounds — a service test supplies its own bounds and can never catch that pairing break, which is silent (200, empty page, no error)"

key-files:
  created: []
  modified:
    - app/services/operations.py
    - app/routes/history.py
    - app/routes/mobile_history.py
    - app/services/customers.py
    - app/routes/customers.py
    - app/templates/partials/customer_insights.html
    - app/services/warehouses.py
    - app/templates/partials/warehouse_rows.html
    - tests/test_history.py
    - tests/test_customers.py
    - tests/test_warehouses.py
    - tests/conftest.py
    - app/__init__.py

key-decisions:
  - "33-08 (D-24, and it must be stated because it contradicts a shipped document): switching «Последняя приёмка» to the business date DELIBERATELY OVERRIDES .planning/research/ARCHITECTURE.md:195, where open operator decision #5 was decided the other way. 33-CONTEXT.md is newer and binding. The override is named in a comment at the call site so the next reader does not restore the older advice."
  - "33-08 (D-24 + D-22, the coupling the plan called out and it is real): last_order_date's SIGNATURE changed from last_order_date(history) to last_order_date(session, customer_id). Switching only the DISPLAYED field would have shown the business date of the latest-ENTERED row, because purchase_history is ordered created_at DESC and D-22 keeps it that way. The function now runs its own MAX(business_date_expr(Operation)) and purchase_history's ordering is byte-unchanged. app/routes/customers.py was updated for the new signature — it is outside the plan's file list and the change was unavoidable."
  - "33-08 (D-22/DATE-04): _SORT_MAP and _DEFAULT_ORDER are byte-unchanged and no business-date sort option was added. The diff inside app/services/operations.py touching them is comment-only. VA-17 asserts BOTH the feeds' behaviour and the literal HEAD values of the two tuples, so a later sweep reddens instead of silently changing what «recent» means."
  - "33-08: history_view's kwargs are still named start_iso/end_iso although they now carry date-only days. Renaming them would churn two routes and every call site in tests while plan 33-14 is queued against the same three modules; the docstring states the new contract and warns that a full timestamp silently drops rows. Additive-change rule."
  - "33-08: tests/conftest.py::past_sale gained an optional business_date= (default None). CLAUDE.md's reuse audit points at extending the existing helper rather than duplicating 25 lines of it in test_customers.py. The None default is load-bearing — 33-07's test_null_business_date_still_reported depends on this helper leaving the column NULL, so the DATE-08 path stays under test."
  - "33-08: a 4th commit adds the /history route-level date-filter guard. /history had NO route-level date test at all, so nothing proved the ROUTE passes business_date_bounds output rather than the old UTC pair — a break that returns 200 with an empty page."

patterns-established:
  - "Pin an ordering by asserting its literal rendered form (`str(clause) == 'operations.created_at DESC'`) alongside the behaviour it produces — the behavioural assertion alone can be satisfied by an accidental tie-break"

requirements-completed: [DATE-03, DATE-04]

# Metrics
duration: ~60min
completed: 2026-09-04
---

# Phase 33 Plan 08: История, Customer Spend and «Последняя приёмка» on the Business Date Summary

**История's date filter, its paginated total, customer month/quarter/year spend, «Последний заказ» and «Последняя приёмка» all bucket by the day the goods actually moved — while display ORDER provably did not move anywhere, pinned by a test that asserts both the «recent N» feeds' behaviour and the literal text of `_SORT_MAP` / `_DEFAULT_ORDER`.**

## Performance

- **Duration:** ~60 min (including two full-suite runs at ~7 min each)
- **Tasks:** 3, plus one follow-up test commit — 4 commits
- **Files modified:** 13 (0 created)

## Accomplishments

- **The `history_view` half-switch is closed and pinned by the only assertion
  that can catch it.** The period predicate exists twice — on `stmt` and on
  `count_stmt` — and both moved in one edit, built from a single `period`
  tuple so they physically cannot drift.
  `test_history_period_count_agrees_with_its_own_rows` seeds three rows inside
  the period and one on each side of it, then asserts `total == 3` **and**
  `len(rows) == total`. Every other history test reads `rows` or `total`,
  never both; a `count_stmt` left on `created_at` would return `total == 0`
  beside three rendered rows and no existing test would notice.
- **VA-17 pins display order two ways, not one.** A writeoff entered LAST but
  back-dated to 2020-01-01 is asserted first in `ledger_view` (the real
  «recent N» feed — 33-CONTEXT cites `ledger.py:234`, which is a `.limit(1)`;
  the feed is the `.limit(50)` order_by below it), in
  `dashboard.recent_operations` and in `writeoffs.recent_writeoffs`. The same
  test then asserts the literal rendered form of both order tuples
  (`"operations.created_at DESC"`, `"operations.seq DESC"`) and that
  `set(_SORT_MAP) == {"oldest"}`, so «nobody added a business-date sort
  option» is a checked fact rather than a diff review.
- **The `last_order_date` coupling was a real defect in waiting, and it is now
  a test.** `test_last_order_is_the_latest_purchase_not_the_latest_entered_row`
  seeds a genuine 2026-03-01 purchase plus a row entered now and back-dated to
  2020, asserts `purchase_history[0]` IS the 2020 row (D-22 untouched), and
  asserts the label still reads `2026-03-01`. Re-rendering the old
  `history[0]` shape would have made «Последний заказ» say 2020.
- **Both retyped cells are verified as RENDERED HTML, not as service return
  values.** `| local_dt` on a date-only string does not raise — it builds a
  naive datetime and confidently prints a fabricated `00:00`. Two route-level
  tests therefore assert the rendered cell matches `dd.mm.yyyy` and contains
  no `:`; a service assertion cannot see that failure mode at all.
- **The misleading comment was rewritten, not left behind.**
  `warehouse_rows.html` carried four lines explicitly instructing «this is a
  full ISO timestamp, use `local_dt` not `ru_date`». It now states the
  opposite with the reason, names D-24, and keeps the old `local_dt`
  precedents valid for genuine timestamps.
- **The ARCHITECTURE.md override is recorded where it will be read.**
  `.planning/research/ARCHITECTURE.md:195` says to leave «Последняя приёмка»
  on `created_at`; D-24 decided otherwise. The reversal is named in a comment
  at the call site, not only in this SUMMARY.
- **/history gained its first route-level date-filter test.** Nothing
  previously exercised `?from=&to=` end to end, so the predicate/bounds
  pairing at the route was unverified — and that break is silent (HTTP 200,
  empty page, no error).

## Task Commits

1. **Task 1 — `history_view` (both predicates), both route bounds sites, VA-17** — `a7d0885`
   (`feat(33-08): /history filters by the business date, in both stmt and count_stmt`)
2. **Task 2 — customer spend + `last_order_date` recomputed** — `a2b92e1`
   (`feat(33-08): customer spend on the business date, «Последний заказ» recomputed`)
3. **Task 3 — «Последняя приёмка» + its rewritten comment** — `0d667f2`
   (`feat(33-08): «Последняя приёмка» on the business date, and its comment fixed`)
4. **Follow-up — the /history route-level guard** — `de0688e`
   (`test(33-08): route-level guard that /history?from=&to= reaches the new predicate`)

## Files Created/Modified

- `app/services/operations.py` *(+27/−6)* — imports `business_date_expr`; the
  period predicate built ONCE as a `period` tuple and applied to `stmt` and
  `count_stmt`, with the T-33-22 warning inline. A comment above `_SORT_MAP`
  names D-22/DATE-04 and points at the test that reddens. `history_view`'s
  docstring states that `start_iso`/`end_iso` are now date-only days and that a
  full timestamp silently drops rows. `_SORT_MAP` / `_DEFAULT_ORDER` bodies
  byte-unchanged.
- `app/routes/history.py`, `app/routes/mobile_history.py` *(+8/−2 and +5/−4)* —
  import and bounds call site each moved to `business_date_bounds`; the
  `display_tz` argument disappears (nothing left to convert). `qs_parts` is
  untouched — the `dated` key is plan 33-14's.
- `app/services/customers.py` *(+59/−34)* — `_spend_stmt` renamed its bounds
  params to `start_day`/`end_day` and switched to
  `business_date_expr(Operation) >= / <=`; both bounds call sites
  (`spend_totals`, `spend_view`) moved to `business_date_bounds` in the same
  commit. `last_order_date` rewritten as
  `select(func.max(business_date_expr(Operation))).join(Sale)...`, with the
  D-22 coupling spelled out in the docstring. **`purchase_history`'s
  `created_at DESC, seq DESC` ordering is byte-unchanged** (verified by
  grepping the diff for `created_at.desc` — no hit).
- `app/routes/customers.py` *(+6/−3)* — the new `last_order_date(session,
  customer_id)` call. Outside the plan's file list; unavoidable given the
  signature change (Deviation 1).
- `app/templates/partials/customer_insights.html` *(+9/−1)* — `| local_dt` →
  `| ru_date` plus the reason. Line 12 no longer matches `local_dt`; the two
  remaining matches are inside the explanatory comment.
- `app/services/warehouses.py` *(+18/−2)* — `func.max(Operation.created_at)` →
  `func.max(business_date_expr(Operation))`, with the D-24 / ARCHITECTURE.md
  override named. No cycle: `reports.py` imports only `app.config`,
  `app.core`, `app.models`.
- `app/templates/partials/warehouse_rows.html` *(+13/−5)* — the render switched
  to `| ru_date` and the four-line comment above it **rewritten** (it used to
  instruct the exact opposite).
- `tests/test_history.py` *(+178/−11)* — 5 new tests plus one renamed/re-pointed
  (`..._excludes_outside_half_open_window` → `..._uses_closed_business_date_bounds`,
  same instants, same outcome, now with a last-day-inclusive assertion). A
  `_backdated_correction` helper writes through the single write path.
- `tests/test_customers.py` *(+118/−17)* — 4 new tests; the two `last_order_*`
  tests re-pointed at the new signature and return type; the portability guard
  fed date-only bounds with a note that `substr` is ANSI and deliberately not
  on the banned list.
- `tests/test_warehouses.py` *(+69/−5)* — 2 new tests; the grouped-outerjoin
  MAX assertion re-pointed to `"2026-02-01"`.
- `tests/conftest.py` *(+12)* — `past_sale` gains optional `business_date=`
  (default None), with the reason the default is load-bearing.
- `app/__init__.py` — `__version__` 1.78 → 1.79 → 1.80 → 1.81 → 1.82 (one bump
  per commit).

## Deviations from Plan

### 1. [Rule 3 — blocking] `last_order_date`'s signature changed, so `app/routes/customers.py` had to change too

- **Found during:** Task 2, writing the function.
- **Issue:** The plan mandates replacing the body with a self-contained
  `select(func.max(business_date_expr(Operation)))`. That query needs a
  `Session` and a `customer_id`; the old function was pure and took an
  already-loaded `history` list. `app/routes/customers.py:200` is its only
  production caller and is **not** in the plan's `files_modified`.
- **Fix:** Signature is now `last_order_date(session, customer_id)`; the route
  passes `(session, customer_id)`, and the stale «reuses the already-loaded
  history — never a seventh query» comment there was replaced with the D-24
  reasoning. The two `last_order_*` tests were re-pointed. There is no version
  of this task that keeps the route file untouched.
- **Commit:** `a2b92e1`

### 2. [Rule 3 — blocking] `tests/conftest.py::past_sale` gained an optional `business_date=`

- **Found during:** Task 2, seeding the D-24 coupling test.
- **Issue:** The new tests need a sale row entered NOW but attributed to an
  older day. `past_sale` inserts directly (it must — the
  `operations_no_update` trigger ABORTs any later UPDATE, so a business date
  can only be set at INSERT time) and had no way to set the column.
  `record_operation` is not an alternative here: a `sale` is stock-affecting,
  so it would demand a batch and would move the stock projections the fixture
  deliberately does not touch.
- **Fix:** One optional keyword, defaulting to `None`. CLAUDE.md's reuse audit
  points at extending the existing helper rather than duplicating ~25 lines of
  it locally. **The `None` default is deliberate and load-bearing**: a direct
  INSERT with a NULL business date is exactly the shape a pre-0027 client's row
  arrives in, and 33-07's `test_null_business_date_still_reported` depends on
  this helper leaving the column NULL. The fixture docstring says so.
  `tests/conftest.py` is outside the plan's file list; all five modules that
  use `past_sale` were re-run green.
- **Commit:** `a2b92e1`

### 3. Two pre-existing tests could not stay unchanged (same shape as 33-07's Deviation 3)

- `tests/test_history.py::test_history_date_range_excludes_outside_half_open_window`
  passed UTC timestamp bounds straight into `history_view`. Under the switched
  predicate `'2026-07-10' >= '2026-07-10T00:00:00+00:00'` is FALSE, so the row
  it asserts IN would have been dropped. Renamed to
  `test_history_date_range_uses_closed_business_date_bounds`, same seeding
  instants, same in/out outcome, now via `business_date_bounds` and with a
  last-day-inclusive assertion added (Pitfall D).
- `tests/test_warehouses.py::test_list_warehouses_last_receipt_date_uses_grouped_outerjoin`
  asserted `row.last_receipt == "2026-02-01T00:00:00Z"`. The value is a
  date now: `"2026-02-01"`. The grouped-outerjoin MAX behaviour the test
  actually guards is unchanged.

### 4. A 4th commit was added for the /history route-level guard

- **Issue:** `/history` had **no** route-level date-filter test. Every
  service-level test supplies its own bounds, so nothing proved the ROUTE
  hands `history_view` `business_date_bounds` output rather than the old UTC
  pair. That break is silent: HTTP 200, an empty table, no error anywhere —
  precisely the failure mode 33-07 hit live on the two CSV routes.
- **Fix:** `test_web_history_period_filter_selects_by_the_business_date`,
  scoped to `<td>{code}</td>` row markup (the «Товар» `<select>` lists every
  product's code regardless of the active filter — the CR-01 trap
  `test_web_history_filters` already documents, and which this test hit on its
  first run).
- **Commit:** `de0688e`

### 5. Two acceptance criteria read for intent, not by their literal grep

- **`grep -n "local_dt" app/templates/partials/customer_insights.html` no
  longer matches line 12** — satisfied literally (line 12 is now blank; the
  render moved to line 20 and uses `ru_date`). The file still contains two
  `local_dt` occurrences at `:17` and `:18`, both inside the comment that
  explains *why* `local_dt` is now wrong. Same for
  `warehouse_rows.html`: line 75 no longer matches, the render is at `:83`
  with `ru_date`, and the two matches at `:78`/`:80` are the rewritten warning
  the plan's own `<action>` REQUIRED to be written.
- **`grep -rn "local_day_bounds_utc" app/` returns NOTHING** — it returns
  **7 hits**, none of them this plan's. Three are in `app/core.py` (the helper's
  own definition and two references inside `business_date_bounds`' docstring —
  the plan's own verification says the helper must still exist). Four are
  `app/routes/finance.py:17,379` and `app/routes/mobile_finance.py:22,377`,
  which **33-07 documented as deliberately NOT switched** (its Deviation 2:
  they feed `export_service.stream_cash_movements_csv`, whose predicate is
  still `CashMovement.created_at`; plan **33-09** owns both). This plan's own
  targets are all at 0: `app/routes/history.py`, `app/routes/mobile_history.py`
  and `app/services/customers.py`.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no remote host
  contacted, no file deleted.
- One mechanical surprise, caught by its own test on the first run: the
  route-level history assertion false-negatived on the `<select>` option text
  before it was scoped to `<td>` row markup.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_history.py tests/test_mobile_history.py -q` (Task 1 gate) | **32 passed** (33 after the 4th commit) |
| `uv run pytest tests/test_customers.py tests/test_mobile_customers.py -q` (Task 2 gate) | **81 passed** |
| `uv run pytest tests/test_warehouses.py -q` (Task 3 gate) | **54 passed** |
| `uv run pytest tests/test_business_date.py tests/test_reports.py tests/test_attribution.py tests/test_history.py tests/test_finance_reports.py tests/test_dashboard.py -q` (conftest blast radius) | **162 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-08.xml` (full suite) | **4 failed, 1543 passed, 14 skipped** in 418.91s |
| Test-count arithmetic | 33-07 baseline **1536** non-skipped (1533+3); this run **1547** (1543+4); this plan adds **11** (4+4+2+1). 1536 + 11 = 1547 exactly — **no pre-existing test that passed before this plan fails now, and none disappeared** |
| `grep -c "local_day_bounds_utc" app/routes/history.py app/routes/mobile_history.py app/services/customers.py` | **0 / 0 / 0** |
| `git diff` inside `app/services/operations.py` touching `_SORT_MAP` / `_DEFAULT_ORDER` | **comment lines only** — grep of the diff for `created_at.(asc\|desc)` returns nothing |
| `git diff` of `app/services/customers.py` for `created_at.desc` | **no hit** — `purchase_history`'s ordering at `:352` is byte-unchanged |
| `git diff --stat b5d2f57..HEAD -- app/static/style.css` | **empty** — 33-06's W-6 rule for every wave-4+ plan holds |
| `git diff --stat b5d2f57..HEAD -- app/services/reports.py app/templates/pages/reports_products.html` | **empty** — D-25's `stale_products` and its cancelled template edit untouched |
| `git diff --diff-filter=D --name-only b5d2f57..HEAD` | **empty** — nothing deleted |
| `uv run ruff check` on all 9 changed `app/` + `tests/` Python files | **All checks passed** |
| `git status --porcelain` (tracked files) | **clean** |
| `reports/33-08.xml` / `.sha` / `.dirty` | written; sha `de0688ec33c78251fa96816c5399b77248b1b564` |

**Full-suite result read carefully.** The 4 failures are **exactly** the four
documented known-red `tests/test_sync_ui.py` cases
(`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`,
`test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`),
each failing on `sync_client._run_lock` being held by the lifespan auto-sync
thread — red since ≤ `49a53d2`, count varies 2–4 per run, unrelated to this
plan. The orchestrator's stated baseline was 3 of them; this run drew 4.

### Real-path check (not a test — but committed as tests)

A green service suite is not evidence the pages work, and for the two retyped
cells it is specifically blind: `| local_dt` on a date-only string does not
raise, it prints a fabricated time. Both checks therefore go through the REAL
route, the REAL Jinja template and the real `client` fixture, and are
permanent:

| Surface | Observed |
|---------|----------|
| `GET /history?from=2026-07-10&to=2026-07-10` | 200; `<td>STK-001</td>` present exactly once — the row entered today, back-dated to 2026-07-10 |
| `GET /history?from=2026-08-01&to=2026-08-31` | 200; the same cell absent — it does not leak into a neighbouring period |
| `GET /customers/{id}` (latest purchase 2026-06-15, latest ENTERED row back-dated to 2020) | 200; «Последний заказ: **15.06.2026**» — the latest PURCHASE, `ru_date`-formatted, no `:` time separator, no `2020` |
| `GET /warehouses` (receipt entered today, business date 2026-04-07) | 200; the «Последняя приёмка» cell renders **`07.04.2026`**, matches `\d{2}\.\d{2}\.\d{4}`, contains no `:` |

**Not checkable here:** no template renders `class="field op-date"` yet, so
`33-UI-SPEC.md`'s browser checks B-1…B-7 still have nothing to exercise —
they belong to plans `33-10` … `33-14`. No production/remote surface was
touched; no server was started and no port was taken.

## Success Criteria

- [x] История's date filter, its count, customer spend, «Последний заказ» and «Последняя приёмка» all bucket by / display the business date.
- [x] `_SORT_MAP`, `_DEFAULT_ORDER`, `purchase_history`'s ordering and every «recent N» feed are unchanged and pinned by VA-17.
- [x] No `app/` history or customer module calls `local_day_bounds_utc`; `app/core.py` still defines it (and the two finance CSV sites remain 33-09's, per 33-07's documented hand-off).
- [x] The `len(rows) == total` assertion exists and passes for a filtered period.
- [x] Both retyped cells render `dd.mm.yyyy` with no time part, asserted through the real route.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-16 (SQL injection via a period bound) | **Mitigated** — `_resolve_history_period` / `_period_starts` produce parsed `date` objects, `business_date_bounds` re-serialises them with `.isoformat()`, and every value reaches SQL as a bound ORM parameter. No string interpolation was added anywhere in this plan; a malformed `?from=` still falls back to today with an inline RU error, never a 500 |
| T-33-22 (`stmt` switched, `count_stmt` not) | **Mitigated** — both predicates are built from ONE `period` tuple in a single edit, and pinned by `test_history_period_count_agrees_with_its_own_rows` (`total == 3` AND `len(rows) == total`) |
| T-33-23 (a just-entered back-dated row vanishing from the «recent N» feed) | **Mitigated** — VA-17 asserts a row back-dated to 2020 is still first in `ledger_view`, `recent_operations` and `recent_writeoffs`, and that both order tuples still hold their literal HEAD values |
| T-33-24 (a date-only string rendered through `local_dt` printing a fabricated time) | **Mitigated** — both switched cells moved to `\| ru_date`, the misleading `warehouse_rows.html` comment was rewritten rather than left, and two ROUTE-level tests assert the rendered cells match `\d{2}\.\d{2}\.\d{4}` with no `:` |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** Every predicate and every cell this plan owns is switched, wired and
reachable from a real route (verified live, table above). Nothing was left
hardcoded, placeholdered or unwired within this plan's scope.

The `dated` filter parameter, the `business_day` / `is_backdated` row-dict keys
and the «задним числом» marker are **not** stubs here — they are plan 33-14's
scope by explicit boundary, and this plan deliberately did not pre-empt them.

## Threat Flags

None. No new network endpoint, no new auth path, no file-access pattern, no
schema change. The only trust boundary touched is the operator-chosen period
already enumerated as T-33-16, and this plan narrows it (parsed `date` objects
in, 10-character ISO strings out) rather than widening it.

## User Setup Required

None. No configuration, no migration to run by hand, no dependency, no server
action.

## Next Phase Readiness

- **Hand-off to 33-14 (it edits the same three História modules after this
  plan):** the period predicate is done and must not be re-touched. `qs_parts`
  in both route modules is deliberately untouched, so the `dated` key lands
  cleanly. `history_view`'s row dicts still carry exactly
  `op / product / batch / warehouse / customer / author` — the `business_day`
  and `is_backdated` keys are 33-14's to add. Note the kwargs are still named
  `start_iso`/`end_iso` although they now carry date-only days.
- **Hand-off to 33-09, repeated because 33-07 flagged it as BLOCKING and this
  plan did not change it:** `app/routes/finance.py:379` and
  `app/routes/mobile_finance.py:377` were **not** switched by 33-07, contrary
  to what `33-09-PLAN.md:102` asserts. 33-09 must flip them in the same commit
  as `export.py:211-212`, or two route tests go red.
- **Note for anyone touching customers:** `last_order_date`'s signature is now
  `(session, customer_id)`. It is not a pure function any more.
- **Note for `33-15` Task 4:** `.planning/research/ARCHITECTURE.md:195` is now
  stale — it advises leaving «Последняя приёмка» on `created_at`, which D-24
  reversed and this plan implemented. Worth a line in `33-ROLLOUT.md` § Backlog
  beside 33-06's four unconverged inlined local-today sites.
- **Unchanged and still open:** the four known-red `tests/test_sync_ui.py`
  cases (pre-existing), the `ruff check` pair on `app/routes/__init__.py`
  (pre-existing, deliberately not fixed), the 11 pre-existing E501s in the two
  finance route modules, the PostgreSQL CI parity run (plan `33-15`), and the
  production rollout (`33-ROLLOUT.md`, human-owned).

## Self-Check: PASSED

All thirteen modified files exist on disk with the described content. Commits
`a7d0885`, `a2b92e1`, `0d667f2` and `de0688e` are all present in `git log`,
together touch exactly those thirteen files and no others, and none deletes a
tracked file (`git diff --diff-filter=D --name-only b5d2f57..HEAD` is empty).
`reports/33-08.xml`, `reports/33-08.sha` and `reports/33-08.dirty` were written
from the final run at `de0688e`, and the tracked working tree is clean.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
