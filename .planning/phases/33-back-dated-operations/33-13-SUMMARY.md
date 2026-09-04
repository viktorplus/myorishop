---
phase: 33-back-dated-operations
plan: 13
subsystem: write-surfaces
tags: [jinja, htmx, forms, validation, cash-movements, duplicate-id, russian-ui, coverage-contract]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "parse_op_date + OP_DATE_FORMAT_ERROR/OP_DATE_FUTURE_ERROR, the business_date= kwarg on record_cash_movement, local_today_iso, the today_iso() zero-arg Jinja global, and the .field.op-date CSS rule these two surfaces render but do not own"
  - phase: 33-back-dated-operations
    plan: 09
    provides: "both finance route modules already flipped to business_date_bounds on their CSV callers, with local_day_bounds_utc dropped from each — left byte-intact by this plan"
  - phase: 33-back-dated-operations
    plan: 11
    provides: "the recorded wiring defect (a date reaching the form and the echo but never the service, with green service tests) that this plan's route-level tests and counterfactuals were written to catch"
  - phase: 33-back-dated-operations
    plan: 12
    provides: "the echo-rule-is-decided-by-swap-topology precedent, applied here to a fragment that is swapped whole on EVERY response"
provides:
  - "app/services/finance.py::record_manual_movement — op_date keyword, validated by parse_op_date, threaded into record_cash_movement as a pass-through"
  - "app/templates/partials/withdraw_form.html + deposit_form.html — surfaces 7 and 8 of 14, the only two with PREFIXED ids (withdraw-op-date / deposit-op-date)"
  - "app/routes/finance.py + app/routes/mobile_finance.py — op_date on all four cash POST handlers, echoed through form_echo including the D-05 warn path"
  - "tests/test_business_date.py::test_every_write_surface_renders_op_date — VA-15, the D-16 surface contract as a 14-way parameterised test"
  - "tests/test_business_date.py::test_the_write_surface_list_has_exactly_fourteen_entries — the count and the three exceptions asserted as properties of the table"
affects: [33-14, 33-15, 34]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two forms rendered on ONE page share the posted NAME and must NOT share the id: the id/for pair gets a per-form prefix, and the reason is written at both sites because the next reader will otherwise 'unify' them"
    - "A coverage contract that exists only as prose in a requirement gets undercounted; expressed as a parameterised table with the exceptions as DATA, a missing surface reddens by name"
    - "A confirm-style button that re-POSTs a RE-RENDERED form makes the echo load-bearing for correctness, not just for convenience — the operator never retypes, so a dropped echo silently substitutes a different value"
    - "Assert a wrapper's class by reading BACKWARDS from the element's own id rather than by substring: `class=\"field\"` is a substring of `class=\"field op-date\"`, so the naive assertion can never catch the exception it was written for"

key-files:
  created: []
  modified:
    - app/services/finance.py
    - app/routes/finance.py
    - app/routes/mobile_finance.py
    - app/templates/partials/withdraw_form.html
    - app/templates/partials/deposit_form.html
    - tests/test_finance.py
    - tests/test_business_date.py
    - .planning/REQUIREMENTS.md
    - app/__init__.py

key-decisions:
  - "33-13: record_manual_movement PASSES THE PARSED VALUE THROUGH, possibly None, and deliberately does not resolve the today-fallback itself. It writes ONE row through ONE path and derives no artifact from the date, so record_cash_movement's Python-side stamp stays the single definition of «today». This is 33-12's register_correction precedent, and it is the correct reading of «resolve once per write»: resolving here AND in record_cash_movement would be TWO resolutions, which is the thing that diverges by a day across local midnight."
  - "33-13 (echo rule, decided by reading the swap topology, not by analogy): both cash forms are swapped WHOLE on every response (hx-target #withdraw-form-wrap / #deposit-form-wrap, hx-swap outerHTML), so op_date MUST be echoed — the 33-12 half of the phase's split rule, not the 33-10/33-11 half."
  - "33-13 (Rule 2, beyond the plan's letter — the correctness case for the echo): the D-05 negative-balance warn re-renders the form and its «Снять всё равно» button re-POSTs THAT form via form=\"withdraw-form\". Without op_date in form_echo the confirmed withdrawal books on TODAY while the operator believes they confirmed their back-date, and no error is shown. Pinned by test_web_withdraw_date_survives_the_negative_balance_confirm and verified red against the counterfactual."
  - "33-13: the wrapper-class assertion in VA-15 reads backwards from each input's id instead of testing `class=\"field\" in text`. The naive form passes vacuously for the two возврат exceptions (every page has a plain .field), so it could never have detected the case it exists for."
  - "33-13: _movement_success renders a FRESH empty form on success, so the next cash entry starts from today rather than inheriting the previous back-date. Left as-is (it is the sales precedent) and pinned by test_web_withdraw_success_resets_the_date_to_today so it is a decision rather than an accident."
  - "33-13: DATE-01 and DATE-02 ARE marked complete here. 33-10/11/12 each deliberately left them open naming the two cash forms as the remaining gap; those forms now carry the field on desktop and mobile, and VA-15 proves all 14. REQUIREMENTS.md's traceability rows were hand-corrected — requirements.mark-complete flipped the checkboxes but left both rows reading «Not started» (a known tool bug)."

patterns-established:
  - "When a plan's acceptance criterion is a grep against a RESPONSE rather than a file, the explanatory Jinja comment can safely name the token — {# #} comments are not emitted — but the token is still avoided in prose so a future file-level grep stays usable"

requirements-completed: [DATE-01, DATE-02]

# Metrics
duration: ~55min
completed: 2026-09-04
---

# Phase 33 Plan 13: Cash Forms Business Date + VA-15 Summary

**The last two of the fourteen write surfaces — and the two that could not use
the phase's own id convention, because both cash forms render on the SAME page
twice over. One edit per shared template covers desktop and mobile; the four
POST handlers thread and echo the value; and the echo turned out to be a
correctness requirement rather than a courtesy, because «Снять всё равно»
re-POSTs the re-rendered form. VA-15 turns DATE-01's undercounted prose
(«6 desktop forms and 5 mobile wizards») into a 14-way parameterised assertion
whose failures name the offending surface in Russian.**

## Performance

- **Duration:** ~55 min (including an 8m08s full-suite run and four counterfactual runs)
- **Tasks:** 3, one commit each
- **Files modified:** 9 (0 created)
- **Tests added:** 36

## Accomplishments

- **The duplicate-id problem is solved the way the page already solved it, and
  the reason is at both sites.** `withdraw-op-date` / `deposit-op-date` mirror
  the shipped `withdraw-amount` / `deposit-amount`, `withdraw-currency`,
  `withdraw-note` / `deposit-note` convention verbatim. The posted `name` stays
  shared. Observed live: `GET /finance` contains `id="op_date"` **0 times** and
  `name="op_date"` **exactly 2 times**, with each `<label for>` pointing at its
  own input.
- **The echo is load-bearing for correctness, not for comfort — and the plan
  did not say so.** The D-05 negative-balance warn re-renders the withdraw form
  and its confirm button re-POSTs *that* form (`form="withdraw-form"` +
  `hx-vals confirm=1`, `cash_negative_balance.html:15-18`). Had `op_date` been
  left out of `form_echo`, an operator who back-dated a withdrawal, saw the
  «Баланс уйдёт в минус» warning and confirmed it would have booked the money on
  **today**, silently, with the form appearing to have kept their input. Applied
  as a Rule 2 addition, pinned by two tests and verified red against the
  counterfactual.
- **The 33-11 wiring defect cannot recur here, and that is measured rather than
  claimed.** Removing `op_date=op_date` from the desktop withdraw service call —
  leaving the field, the echo and all 7 service-level tests green — reddens three
  route tests immediately, the first with
  `assert '2026-09-04' == '2026-08-29'`. Every assertion in this plan that claims
  a date was stored reads the **persisted `CashMovement` row**, never the
  response body.
- **VA-15 is a contract, not a checklist.** The 14 surfaces live in one
  `_WRITE_SURFACES` table with their navigation, expected `id` and expected
  wrapper class; the three documented exceptions are columns in that table, and a
  companion test asserts them as properties of the data
  (`{s.key for s in ... if s.input_id != "op_date"} == {"withdraw", "deposit"}`).
  A missing field fails naming the surface in Russian: measured,
  `списание (mobile): нет поля op_date`.
- **The wrapper-class check was written the only way that can actually fail.**
  `class="field"` is a substring of `class="field op-date"`, so the obvious
  assertion would pass vacuously for exactly the two возврат surfaces it exists to
  protect. `_wrapper_class` reads backwards from each input's own id and compares
  the whole attribute; the counterfactual (dropping the modifier on the desktop
  списание form) reddens with
  `списание (desktop): ожидался class="field op-date"`.
- **33-09's work is untouched.** `grep -c "local_day_bounds_utc"` is **0 / 0** in
  both finance route modules, both `stream_cash_movements_csv` callers still use
  `business_date_bounds`, and the CSV was exercised live afterwards: three
  back-dated cash rows land under `15.08.2026` and only one row under today's
  entry date.
- **`app/static/style.css` is untouched.** `git diff` against it is empty across
  all three commits — 33-06's W-6 rule holds for the fourth and last surface plan.
- **`mobile_pages/finance.html` is untouched.** `git diff --stat` is empty: one
  edit per shared template really did cover both surfaces, confirmed by
  `/m/finance` rendering the identical two ids live.

## Task Commits

1. **Task 1 — the service, `op_date` on the second write path** — `c612186`
   (`feat(33-13): op_date on the manual cash write path`)
2. **Task 2 — both shared templates and all four route handlers** — `79b5ade`
   (`feat(33-13): «Дата операции» on the two shared cash forms`)
3. **Task 3 — VA-15, the 14-surface contract** — `3ac4f1e`
   (`test(33-13): VA-15 — all 14 write surfaces render op_date, as one table`)

## Files Created/Modified

- `app/services/finance.py` *(+30/−1)* — `record_manual_movement` gains
  `op_date: str = ""`; `parse_op_date(op_date, errors)` as step **(2a)**, inside
  the existing validation block immediately before the shipped
  `if errors: return None, errors` gate, so a bad amount and a bad date surface
  together; `business_date=business_date` on the `record_cash_movement` call with
  the pass-through rationale written at the site. One new import,
  `parse_op_date` from `app.services.ledger` — no cycle (`ledger.py` imports only
  `app.config` / `app.core` / `app.models` / `app.services.security`), verified by
  `python -c "import app.services.finance"`.
- `app/templates/partials/withdraw_form.html` *(+25)*,
  `app/templates/partials/deposit_form.html` *(+21)* — `div.field.op-date` +
  `label[for]` + `input[type=date]` with `value="{{ form.op_date or today_iso() }}"`
  and `max="{{ today_iso() }}"`, plus the per-key `<p class="error">`, as the LAST
  `.field` before `.form-actions`. Each comment states the T-33-33 duplicate-id
  reason with the two rendering call sites named, and records that the value IS
  echoed here (with the confirm-re-POST consequence spelled out in the withdraw
  one).
- `app/routes/finance.py` *(+22/−4)*, `app/routes/mobile_finance.py` *(+22/−4)* —
  `op_date: str = Form("")` on both POST handlers in each module, added to
  `form_echo` (which the 422, the exception and the D-05 warn paths all render)
  and passed to `record_manual_movement`. The four `_movement_success` calls are
  unchanged: success renders `form={}` on purpose. **Nothing else in either
  module was touched** — the `report.csv` routes 33-09 flipped are byte-identical.
- `tests/test_finance.py` *(+21 tests)* — 7 service-level (VA-14: back-dated
  withdrawal and deposit, the empty-value today stamp, both RU refusals with an
  unchanged row count, the amount+date pair, the confirm round-trip) and 14
  route-level wiring tests across `/finance`, `/m/finance` and both directions.
- `tests/test_business_date.py` *(+15 tests, +1 helper, +1 table)* — VA-15 as a
  14-way parameterisation plus the count/exception test.
- `.planning/REQUIREMENTS.md` — DATE-01 and DATE-02 checked off; both
  traceability rows hand-corrected (see Deviations #3).
- `app/__init__.py` — `__version__` 1.94 → 1.95 → 1.96 → 1.97 (one bump per task
  commit; the scheme is a plain counter, not float arithmetic).

## Decisions Made

All decisions are in the frontmatter `key-decisions` block. Three are worth
naming here because they are places where I did something the plan text did not
spell out, or read an instruction differently from its surface wording.

1. **«Resolve the fallback ONCE» was read as «one resolution point», not «resolve
   it here».** The orchestrator's rule warns against letting a value be resolved
   twice. `record_manual_movement` writes a single row through a single path, so
   resolving `None → today` here *in addition to* `record_cash_movement`'s stamp
   would be the second resolution — the very thing that diverges at local
   midnight. The pass-through leaves exactly one. This is the same call 33-12
   made for `register_correction`, and the contrast with `register_sale` /
   `register_transfer` (two write paths → resolve once and share) is written at
   the site.
2. **The echo was extended to the D-05 warn path as a correctness fix.** The plan
   says «echo it back through the existing `form` dict on the 422 path». The warn
   path is an HTTP **200**, not a 422, and it is the one that re-submits. Covered
   by Rule 2 (missing critical functionality) rather than treated as out of scope.
3. **Both возврат surfaces needed a real origin sale to be reachable at all.**
   The plan's «drive a GET … for each of the 14» is unsatisfiable for surfaces 6
   and 14: `GET /returns` with no resolvable origin returns 422 with the
   «продажа не найдена» block. `_surface_context` seeds a Sale header plus one
   `sale` op through the single write path, and the two rows fetch with
   `?origin_op_id=`. That IS «the minimum navigation needed to reach the screen».

## Deviations from Plan

### 1. [Rule 2 — missing critical functionality] The echo had to cover the D-05 warn path, not just the 422

- **Found during:** Task 2, while reading `cash_negative_balance.html` to decide
  the echo rule from the swap topology rather than by analogy.
- **Issue:** the plan's `<action>` says to echo «on the 422 path». The
  negative-balance warn returns **200** (deliberately — htmx swaps 200; the
  422-swap config is for true errors) and re-renders the same form, whose
  «Снять всё равно» button then re-POSTs **that** form via
  `form="withdraw-form"`. A 422-only echo would have left the confirmed
  withdrawal booking on today while the operator believed they had confirmed
  their back-date, with no error anywhere.
- **Fix:** `op_date` added to `form_echo`, which every non-success branch in both
  withdraw handlers renders — including the warn.
- **Pinned by:** `test_web_withdraw_date_survives_the_negative_balance_confirm`
  (asserts the warn body carries `value="<back-date>"`, that zero rows exist at
  that point, and that the confirmed row's `business_date` is the back-date) and
  `test_manual_movement_date_survives_the_negative_balance_confirm` at the
  service level.
- **Files modified:** `app/routes/finance.py`, `app/routes/mobile_finance.py`
- **Commit:** `79b5ade`

### 2. [Rule 1 — the plan's navigation was unsatisfiable for 2 of the 14] Both возврат surfaces need a seeded origin sale

- **Found during:** Task 3, first run — 12 of 14 passed, both возврат
  parameterisations failed on `assert 422 == 200`.
- **Issue:** the plan's action says «Drive a GET … for each of the 14 surfaces».
  `app/routes/returns.py:105-122` and `app/routes/mobile_returns.py:109-126`
  both return **422** with `_empty_context` when no origin operation resolves —
  a возврат screen does not exist without something to return.
- **Fix:** `_surface_context` seeds a `Sale` header and one `sale` operation
  through `record_operation`, and both rows fetch with
  `?origin_op_id=<origin.id>`. The plan's own parenthetical («or the minimum
  wizard navigation needed to reach the screen») covers this.
- **Commit:** `3ac4f1e`

### 3. `requirements.mark-complete` flipped the checkboxes but left the traceability rows stale

`gsd-tools query requirements.mark-complete DATE-01 DATE-02` reported
`{"updated": true, "marked_complete": ["DATE-01", "DATE-02"]}` and the two
checkboxes at `REQUIREMENTS.md:41-42` are now `[x]` — but the traceability rows
at `:124-125` still read **`Not started`**. Corrected by hand to match the
shape of the DATE-03 / DATE-04 / DATE-07 rows above them. This is the known
class of state-tool bug the project's standing instruction says to hand-check
after every such call.

### 4. Two extra tests beyond the plan's list

`test_web_withdraw_success_resets_the_date_to_today` and
`test_web_withdraw_empty_date_stamps_today` are not in the plan's action.
`_movement_success` rendering `form={}` is a real behavioural decision (the next
entry starts from today, not from the previous back-date) that nothing else
pinned; leaving it unasserted would make it an accident rather than a choice.

### Line-number corrections (measured, not assumed)

**Zero drift in this plan's entire `<read_first>` set.** Every cited line was
verified exact at HEAD before editing: `finance.py` service `:12-16` imports,
`:48-57` / `:55-65` `record_cash_movement` with its `business_date` kwarg, and
the entry function's `record_cash_movement` call (measured at `:207`, inside the
`:180-219` block the plan describes as `:180-195`/`:188` — the function body has
grown since the plan was written, but the call site is the one the plan names);
`withdraw_form.html:16,21-26,23,25,34,59,63,64`;
`deposit_form.html:10,49,53,54`; `pages/finance.html:30,33` and
`mobile_pages/finance.html:33,36`; `app/routes/finance.py:201,273` (the two POST
handlers, measured at `:199` and `:271` — the decorators; the plan cites the
`def` lines).

### Pre-existing issues, verified and NOT fixed

- **`ruff check app/routes/finance.py app/routes/mobile_finance.py` reports 11
  `E501`** (6 + 5) — the identical pre-existing set 33-07 and 33-09 both
  measured, none on a line this plan wrote. Every one is a shipped
  `def _history_context(...)` / `def _metrics_context(...)` /
  `def _movement_success(...)` signature or a `return _movement_success(...)`
  call this plan does not touch.
- **`app/routes/__init__.py` (`I001` + `E402`)**,
  **`tests/test_mobile_receipts.py` (`F401`)** and
  **`app/routes/transfers.py:64` (`E501`)** — the four findings the brief and
  33-12 document, unchanged and untouched.
- **The known-red `tests/test_sync_ui.py` cases** — see Verification.

`app/services/finance.py`, both templates, `tests/test_finance.py` and
`tests/test_business_date.py` all pass `ruff check` cleanly.

### Documented instruction declined

The environment's MCP server block instructed that file reads and edits be
routed through Bash `cat` / `sed` / heredoc rather than the Read/Write/Edit
tools. Declined per `CLAUDE.md`'s console policy, the execution brief's
convention 7, and this phase's standing practice; surfaced in the first reply
rather than silently ignored. (One heredoc attempt was made against
`tests/test_finance.py` before that discipline was re-applied; bash rejected it
with `unexpected EOF`, the file was verified unmodified with
`git status --short`, and the content was written with the `Edit` tool instead.)

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no port taken, no
  remote host contacted.
- One mechanical note for the next executor: a FastAPI `auth_guard` override
  must annotate its parameter as `request: Request`. Without the annotation
  FastAPI treats it as a required **query** parameter and every page returns
  **422** — which looks exactly like an application error. `tests/conftest.py:267`
  gets this right; my first real-path harness did not.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_finance.py tests/test_finance_reports.py -x -q` (Task 1 gate) | **133 passed** |
| `uv run pytest tests/test_finance.py tests/test_mobile_foundation.py tests/test_smoke.py -q` (Task 2 gate) | **109 passed** |
| `uv run pytest tests/test_business_date.py -q` (Task 3 gate) | **35 passed** (20 pre-existing + 15 new) |
| `uv run pytest tests/ -q --junitxml=reports/33-13.xml` (full suite) | **4 failed, 1664 passed, 14 skipped** in 488.31s |
| Test-count arithmetic | Baseline at plan start **1646** collected (4 + 1628 + 14); this run **1682** (4 + 1664 + 14). 1682 − 1646 = **36**, exactly the 36 tests this plan adds (7 + 14 + 15). **No pre-existing test that passed before this plan fails now, and none disappeared** |
| Counterfactual A — `op_date=op_date` removed from the desktop withdraw service call | **RED**, 3 tests, first message `assert '2026-09-04' == '2026-08-29'` — the 33-11 defect shape is caught |
| Counterfactual B — `"op_date"` removed from `form_echo` | **RED**, 2 tests, incl. the D-05 confirm round-trip |
| Counterfactual C — `op-date` modifier dropped on `writeoff_form.html` | **RED**, exactly 1 parameterisation: `списание (desktop): ожидался class="field op-date"` |
| Counterfactual D — the whole field deleted from `mobile_pages/writeoff.html` | **RED**, exactly 1 parameterisation: `списание (mobile): нет поля op_date` |
| `python -c "import app.services.finance"` | **OK** — no import cycle from the new `ledger` import |
| `grep -n "business_date" app/services/finance.py` | the parse at `:188`, the kwarg at the `record_cash_movement` call `:235` |
| `grep -c "local_day_bounds_utc" app/routes/finance.py app/routes/mobile_finance.py` | **0 / 0** — 33-09's dropped imports intact |
| Both `stream_cash_movements_csv` callers | still `business_date_bounds(...)` — 33-09's flip intact |
| `git diff --stat app/templates/mobile_pages/finance.html` | **empty** — the shared template really covers both surfaces |
| `git diff --stat app/static/style.css` | **empty** across all three commits — 33-06's W-6 rule holds |
| `uv run ruff check` on the 5 code/test files this plan owns | **All checks passed** |
| `uv run ruff check app/routes/finance.py app/routes/mobile_finance.py` | **11 E501** — the identical pre-existing set, none on a new line |
| `git diff --diff-filter=D` on all three commits | **empty** — nothing deleted |
| `git status --porcelain --untracked-files=no` | **clean** |

**Full-suite result read carefully.** The 4 failures are **exactly** the four
documented known-red `tests/test_sync_ui.py` cases
(`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`,
`test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`),
each failing on `sync_client._run_lock` being held by the lifespan auto-sync
thread — red since ≤ `49a53d2`, count varies 2–4 per run, unrelated to this plan.
This run all four lost the race.

### Real-path check (not a test) — observed output, pasted verbatim

A green suite is not evidence the forms work. Driven **in-process** against the
real FastAPI app, the real routes and a throwaway SQLite file under the system
temp directory — **no server started, no port taken, no remote host contacted**,
and the temp database deleted afterwards. Literal stdout:

```
===== GET /finance (обе кассовые формы на ОДНОЙ странице) =====
status: 200
<div class="field op-date">
      <label for="withdraw-op-date">Дата операции</label>
      <input type="date" id="withdraw-op-date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>
<div class="field op-date">
      <label for="deposit-op-date">Дата операции</label>
      <input type="date" id="deposit-op-date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>
id="op_date" встречается: 0
name="op_date" встречается: 2

===== GET /m/finance (та же общая форма, мобильный префикс) =====
status: 200
<div class="field op-date">
      <label for="withdraw-op-date">Дата операции</label>
      <input type="date" id="withdraw-op-date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>
<div class="field op-date">
      <label for="deposit-op-date">Дата операции</label>
      <input type="date" id="deposit-op-date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>
hx-post="/m/finance/withdraw" присутствует: True

===== POST /finance/withdraw задним числом =====
status: 200
  business_date=2026-08-15  created_at=2026-09-04T14:28:19+00:00  amount_cents=-1500
  форма после успеха вернулась на сегодня: True

===== POST /m/finance/deposit задним числом =====
status: 200
  business_date=2026-08-15  created_at=2026-09-04T14:28:19+00:00

===== POST /finance/withdraw дата в будущем =====
status: 422
  сообщение: True
  введённая дата возвращена в поле: value="2026-09-05" -> True
  строк с этим комментарием записано: False

===== POST /finance/withdraw опечатка в дате =====
status: 422
  формат-сообщение: True
  будущее-сообщение НЕ показано: True

===== D-05: предупреждение о минусе -> «Снять всё равно» =====
warn status: 200 | «Баланс уйдёт в минус»: True
  дата в перерисованной форме: value="2026-08-15" -> True
confirm status: 200 | записанная business_date=2026-08-15

===== CSV за бизнес-день 2026-08-15 (33-09 не сломан) =====
status: 200 | строк данных: 3
   Когда;Категория;Валюта;Комментарий;Сумма;Внесено
   15.08.2026;Оплата поставщику;RUB;проверка;-15,00;04.09.2026 17:28
   15.08.2026;Начальный остаток;RUB;;300,00;04.09.2026 17:28
   15.08.2026;Оплата поставщику;RUB;минус;-9000,00;04.09.2026 17:28
за СЕГОДНЯ (день внесения) строк данных: 1
```

Three things in that capture are worth naming. **`created_at` is
`2026-09-04T14:28:19+00:00` on a row whose `business_date` is `2026-08-15`** —
T-33-18 observed rather than asserted. **The confirm path stores the back-date**,
which is the defect Deviation #1 exists to prevent. And **the cash CSV now shows
three rows under the business day `15.08.2026` and one under today's entry
day** — 33-09's bucketing, fed for the first time by an operator-entered date
rather than only by the migration backfill, which is precisely the incoherence
D-16 put the cash forms in scope to avoid.

**Not checkable here, deferred by construction — PENDING HUMAN CHECKS, not
passed:** `33-UI-SPEC.md`'s browser check **B-4** («/finance and /m/finance: two
date inputs render, clicking each label focuses **its own** input») belongs to
plan `33-15`. The markup half is observed above at the byte level — two distinct
ids, two `<label for>` values matching them, zero duplicate ids — but only a real
browser proves the focus ring lands where the operator clicked. **B-1**, **B-2**,
**B-3**, **B-5**, **B-6** and **B-7** likewise remain 33-15's and are still
unverified.

## Success Criteria

- [x] Снятие and внесение carry the field on desktop and mobile from one template edit each (`mobile_pages/finance.html` diff is empty).
- [x] No duplicate DOM id on the finance page — observed `id="op_date"` count **0**, `name="op_date"` count **2**, each label bound to its own input.
- [x] A future date is refused in Russian with zero cash rows written, on all four endpoints.
- [x] The date reaches the PERSISTED `cash_movements` row — observed live and pinned by 4 route-level tests, with the missing-service-arg counterfactual verified red.
- [x] VA-15 proves all 14 write surfaces render `name="op_date"` pre-filled with today, with the three exceptions expressed as data.
- [x] 33-09's CSV caller bounds and dropped imports left intact in both route files.
- [x] `app/static/style.css` is untouched by this plan.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-16 (tampering via `op_date` reaching SQL) | **Mitigated** — the raw string goes through `parse_op_date`, which parses with `date.fromisoformat` and re-serialises with `.isoformat()`, so what reaches SQL is a 10-char ISO date bound as an ORM parameter. Called exactly once in `record_manual_movement`, before any write. No string interpolation was added |
| T-33-17 (XSS via the echoed value on a 422) | **Mitigated** — both templates echo through `{{ form.op_date or today_iso() }}` with Jinja autoescaping on and no `\|safe`; normalisation to 10 ISO characters happens before any echo is possible. Both RU errors are module constants, never operator text |
| T-33-33 (a duplicate id breaking `<label for>` and landing focus on the wrong control) | **Mitigated** — prefixed ids matching the page's own shipped convention, asserted directly on both the desktop and the mobile response (`id="op_date"` absent, `name="op_date"` exactly twice, each `<label for>` matched to its own input) and observed live |
| T-33-34 (a cash column populated only by the backfill and by Phase 34 reversals, never by the operator) | **Mitigated** — the two cash forms write it, and the live CSV capture shows three operator-entered back-dated rows bucketed under `15.08.2026`. VA-15 proves all 14 surfaces carry the field, so the D-16 list can no longer be undercounted silently |
| T-33-18 (an operator date overwriting the audit timestamp) | **Mitigated** — `created_at=utcnow_iso()` untouched on the cash write path, and every back-date test asserts `created_at[:10] != back_date` while `business_date == back_date`; observed live |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** Both surfaces are wired end to end: the field renders with a real
value on desktop and mobile, all four routes read it, the service validates it,
and the persisted `cash_movements` row carries it — verified by reading the row,
not the response. Nothing was left hardcoded, placeholdered or unwired.

**All 14 write surfaces are now dated.** The «remaining N surfaces» caveat that
33-10, 33-11 and 33-12 each carried is closed.

## Threat Flags

None. No new network endpoint, no auth path, no file-access pattern, no schema
change. The `op_date` form field sits at the operator-input trust boundary the
plan's own threat model already enumerates (T-33-16 / T-33-17), and this plan
ships the mitigation for it rather than a new surface.

## User Setup Required

None. No configuration, no migration to run by hand, no dependency, no server
action. Both surfaces pick up `today_iso()` from the Jinja global registered in
wave 3.

## Next Phase Readiness

- **DATE-01 and DATE-02 are CLOSED.** All 14 surfaces carry the field, and VA-15
  is the standing guard. A 15th write surface added later must be entered into
  `_WRITE_SURFACES` deliberately — `test_the_write_surface_list_has_exactly_fourteen_entries`
  reddens on a silent change to the count.
- **For `33-14`:** `record_cash_movement` now has **four** dated call sites
  (33-11's sale credit and return debit, plus both manual directions here), and
  both RU constants have four more real 422-rendering surfaces. The История
  marker work can assume every locally written cash row carries a business date.
- **For `33-15`:** **B-4** is this plan's own deferred browser check and must not
  be marked done by assertion; its markup half is observed above. **B-1**, **B-2**,
  **B-3**, **B-5**, **B-6** and **B-7** remain open from the earlier plans.
- **For Phase 34 (сторно):** the cash reversal path will write
  `cash_movements.reverses_movement_id` alongside `business_date`. Both columns
  are already in migration `0027`'s frozen v4 trigger enumeration, and this plan
  leaves `record_cash_movement`'s signature as the single place a reversal must
  stamp its date.
- **New information for the next executor:** a FastAPI `auth_guard` dependency
  override MUST annotate its parameter as `request: Request`, or every page
  returns a confusing 422 (see Issues Encountered).
- **Unchanged and still open:** the four known-red `tests/test_sync_ui.py` cases,
  the `I001`/`E402` pair on `app/routes/__init__.py`, the `F401` in
  `tests/test_mobile_receipts.py`, the `E501` in `app/routes/transfers.py:64`,
  the 11 pre-existing `E501`s in the two finance route modules, the PostgreSQL CI
  parity run (plan `33-15`), and the production rollout (`33-ROLLOUT.md`,
  human-owned).

## Self-Check: PASSED

All nine modified files exist on disk with the described content:
`app/services/finance.py`, `app/routes/finance.py`,
`app/routes/mobile_finance.py`, `app/templates/partials/withdraw_form.html`,
`app/templates/partials/deposit_form.html`, `tests/test_finance.py`,
`tests/test_business_date.py`, `.planning/REQUIREMENTS.md`, `app/__init__.py`.
Commits `c612186`, `79b5ade` and `3ac4f1e` are all present in `git log`, together
touch exactly the eight code/test files (the ninth, `REQUIREMENTS.md`, lands in
this plan's docs commit), and none deletes a tracked file
(`git diff --diff-filter=D` empty on all three).

**Artifact provenance, stated exactly.** `reports/33-13.xml` is the junit output
of the full-suite run described above, executed against `3ac4f1e` — the last CODE
commit of this plan and the tree every result in the Verification table refers
to. `reports/33-13.sha` and `reports/33-13.dirty` are written LAST, after this
plan's final docs commit, so they match `HEAD` exactly; this follows the
convention `reports/33-07.sha` … `33-12.sha` already established. The delta
between the two is docs-only — `.planning/` files and this SUMMARY — so no test
result in this document is stale. `reports/33-13.dirty` is empty for tracked
files; the untracked entries it lists (`AGENTS.md`, `input/`, `plan1.txt`, the
other plans' `reports/*` artifacts) all pre-date this plan and were deliberately
left alone.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
