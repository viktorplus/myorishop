---
phase: 33-back-dated-operations
plan: 11
subsystem: write-surfaces
tags: [jinja, htmx, forms, validation, mobile-wizard, cash-movements, russian-ui]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "parse_op_date + OP_DATE_FORMAT_ERROR/OP_DATE_FUTURE_ERROR, the business_date= kwarg on BOTH record_operation and record_cash_movement, local_today_iso, the today_iso() zero-arg Jinja global, and the .field.op-date CSS rule these four surfaces render but do not own"
  - phase: 33-back-dated-operations
    plan: 10
    provides: "the canonical desktop/mobile markup, the resolve-the-fallback-ONCE precedent, and the first-element error-emission pattern for a shell-hosted field"
provides:
  - "app/services/sales.py::register_sale — op_date keyword, parsed once, threaded into every record_operation AND record_cash_movement of the basket"
  - "app/services/returns.py::register_return — op_date keyword, parsed once, threaded into record_operation AND record_cash_movement"
  - "app/routes/returns.py::_origin_business_day + app/routes/mobile_returns.py::_origin_business_day — the D-24 origin-sale identification date"
  - "the context key rename origin_created_at -> origin_business_day on both возврат surfaces"
  - "app/templates/partials/sale_form.html + return_form.html — desktop surfaces 2 and 6 of 14"
  - "app/templates/mobile_pages/sales.html + mobile_partials/return_confirm.html — mobile surfaces 10 and 14 of 14"
  - "app/templates/mobile_partials/sale_basket.html — the op_date error as the first element of #wizard-basket, with the id the shell's aria-describedby points at"
affects: [33-12, 33-13, 33-14, 33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "When ONE operator action writes through TWO independent write paths, the today-fallback must be resolved once into a local and shared — letting each path resolve «today» on its own is correct on 364 days a year and splits the operation across two business days at local midnight"
    - "A wizard-wide value belongs in the persistent shell <form> htmx never swaps; the proof that it survives is a NEGATIVE assertion that no swapped fragment mentions the field at all, which also forbids any future hidden-field threading"
    - "A context key whose VALUE changes meaning (timestamp -> business date) is renamed in the same commit; leaving it called origin_created_at would be a name that actively lies to the next reader"
    - "An acceptance criterion phrased as a grep count constrains the prose you write: name the concept, never quote the token the criterion counts"

key-files:
  created: []
  modified:
    - app/services/sales.py
    - app/services/returns.py
    - app/routes/sales.py
    - app/routes/returns.py
    - app/routes/mobile_sales.py
    - app/routes/mobile_returns.py
    - app/templates/partials/sale_form.html
    - app/templates/partials/return_form.html
    - app/templates/mobile_pages/sales.html
    - app/templates/mobile_partials/sale_basket.html
    - app/templates/mobile_partials/return_confirm.html
    - tests/test_sales.py
    - tests/test_returns.py
    - tests/test_mobile_sales.py
    - tests/test_mobile_returns.py
    - app/__init__.py

key-decisions:
  - "33-11 (D-24, verified by reading the code rather than assumed): the «Возврат из продажи от …» label was still on `origin.created_at` rendered through `| local_dt` on BOTH surfaces at HEAD. The execution brief told me to check rather than assume, and the check found the coupling genuinely open. It now resolves `origin.business_date or origin.created_at[:10]` in a named helper on each route module and renders through `| ru_date`."
  - "33-11: the context key `origin_created_at` was RENAMED to `origin_business_day` on both возврат surfaces. The value stopped being a timestamp, so the old name would have been a lie; no test referenced it and `_empty_context` already passed None, so the rename is contained to 2 route modules + 2 templates."
  - "33-11 (DATE-03/T-33-29): both services resolve the today-fallback ONCE into `resolved_business_date` and give that same string to every write path. Passing the possibly-None parsed value down instead would let record_operation and record_cash_movement each resolve «today» independently — the sale's N ledger rows and its single cash credit could then land on different business days across local midnight, which is exactly the report contradiction DATE-03 exists to prevent."
  - "33-11 (D-11): on the mobile sale the date rides `<form id=\"sale-wizard-form\">` ABOVE `#wizard-step`, and the proof is a negative test — `test_sale_wizard_steps_never_re_emit_the_date` asserts the substring `op_date` is absent from every swapped fragment, so nothing htmx puts into the step region can reset it, and a future edit that threads it as a hidden field reddens."
  - "33-11: on the DESKTOP sale the echo rides `form.op_date`, per the UI-SPEC surface-inventory row 2. `form` on that template is the customer-header echo dict built by `_customer_context`; a `form_echo = {**new_customer_form, \"op_date\": op_date}` dict is passed at the four re-render sites and `{}` on success, so a saved sale starts the next basket from today. sale_customer.html reads only its own three named keys and never iterates the dict, so the extra key is inert there."
  - "33-11: on both возврат surfaces the echo is the FLAT `op_date` context key, matching those templates' own `{{ remaining }}` idiom, because they have no `form` dict at all."
  - "33-11: `errors` is validated in returns.py AFTER the shipped origin -> qty -> cap sequence, so that precedence is byte-unchanged; in sales.py it is validated WITH the per-line errors, so a basket with both a bad line and a bad date surfaces both in one 422 (pinned by test_sale_op_date_error_rides_alongside_the_per_line_errors)."
  - "33-11: DATE-01/DATE-02 are NOT marked complete. This plan lands 4 of the 14 write surfaces (2, 6, 10, 14); корректировка/перемещение (33-12) and the two cash forms (33-13) are still dateless."

patterns-established:
  - "A shared test helper that builds a fixture-like origin row (_make_sale) gains an optional business_date defaulting to None — record_operation's own default — so every existing caller is byte-unchanged and only the D-24 tests opt in"

requirements-completed: []

# Metrics
duration: 70min
completed: 2026-09-04
---

# Phase 33 Plan 11: Продажа and Возврат Business Date Summary

**Four more of the fourteen write surfaces carry «Дата операции» — and the two
that would otherwise have shipped broken are the reason this plan existed:
mobile возврат, which had no field at all while its desktop twin did, and the
mobile sale basket, where a date typed on the Корзина screen would have silently
snapped back to today on the next «Добавить товар». Both services now resolve
«today» exactly once and stamp that one value on the ledger rows AND on the cash
movement, and «Возврат из продажи от …» — a D-24 coupling that was still open —
now names the origin sale's business date on both surfaces.**

## Performance

- **Duration:** ~70 min (including an 8m22s full-suite run)
- **Tasks:** 3, one commit each
- **Files modified:** 16 (0 created)
- **Tests added:** 26

## Accomplishments

- **D-24's return-label coupling was genuinely open, and I checked instead of
  assuming.** The brief warned that an earlier executor had been told a D-24
  coupling was already done when it was not, and instructed me to read the code.
  At HEAD both `app/routes/returns.py:75,152` and
  `app/routes/mobile_returns.py:80,156` still passed `origin.created_at`, and
  both templates still rendered it through `| local_dt`. A sale back-dated to
  15.08 was therefore labelled with the day it was typed in. Both now resolve
  `origin.business_date or origin.created_at[:10]` through a named
  `_origin_business_day` helper and render through `| ru_date` — `local_dt` on a
  10-char date builds a naive datetime and prints a bogus time.
  `test_web_return_label_names_the_origin_sales_business_date` and its mobile
  twin pin it, and a DATE-08 test pins the NULL fallback.
- **The trap the plan was written to avoid is closed structurally, not by
  care.** The mobile sale's date lives on `<form id="sale-wizard-form">` above
  `#wizard-step`. The assertion is not "it looks right": it is
  `resp.text.index('name="op_date"') < resp.text.index('id="wizard-step"')`, plus
  a negative — `test_sale_wizard_steps_never_re_emit_the_date` drives the product
  step, the qty/price step and basket-add and asserts the substring `op_date` is
  absent from all three swapped fragments. Since no fragment can carry it,
  nothing htmx swaps into the step region can overwrite the shell's input, and a
  later "helpful" hidden field reddens the test.
  `test_sale_date_survives_the_basket_product_round_trip` then drives the actual
  round-trip — add line 1, «Добавить товар» back to the product step, add line 2,
  finalize — and asserts BOTH sale rows and the cash credit carry the back-date.
- **One resolution, one date, two write paths.** A sale writes N `Operation`
  rows through `record_operation` and one aggregated credit through
  `record_cash_movement`; a return writes one op and one debit. Passing the
  possibly-`None` parsed value to each would let all of them resolve «today»
  independently, microseconds apart — identical on 364 days a year and a day
  apart at local midnight, which would put the goods on one business day and the
  money on the next and make the sales-profit report and the cash-flow report
  disagree about the same operation (T-33-29). Both services compute
  `resolved_business_date` once and share it; the tests assert the equality by
  identity (`{op.business_date for op in ops} == {movement.business_date}`), not
  by comparing each to a literal.
- **Zero writes on refusal is asserted by counting BOTH tables.** Every
  future-date test snapshots the `Operation` count AND the `CashMovement` count
  before the call and re-asserts both after; the sale one additionally asserts no
  `Sale` header was created and that `compute_stock` is unchanged, because the
  header is added to the session before the write loop and a validation gap
  there would leak an orphan.
- **The mobile error placement is asserted by shape, not presence.**
  `test_mobile_sale_future_date_error_is_the_first_element_of_the_basket` asserts
  the exact string `<p class="error" id="op_date-error">…</p>` is present, that a
  `<div class="error-block">` with the same message is NOT, that the message
  appears exactly once, and that its index precedes «Корзина». That is CF-UI-1's
  resolution expressed as four independent checks.
- **`app/static/style.css` is untouched.** `git diff` against it is empty across
  all three commits — the `.field.op-date` rule shipped in wave 3, exactly as
  33-06 arranged.
- **«Шаг N из M» and «Корзина» are byte-unchanged.** The diff of
  `sale_basket.html` contains no step-indicator line; only its position moved
  down by the comment and error branch above it.

## Task Commits

1. **Task 1 — the two services, both write paths each** — `54ead6f`
   (`feat(33-11): op_date on the sale/return services, one date for goods and money`)
2. **Task 2 — the two desktop forms, their routes, and the D-24 label** — `caae2c9`
   (`feat(33-11): «Дата операции» on the desktop продажа/возврат forms + the D-24 label`)
3. **Task 3 — the mobile sale shell, mobile возврат, and the mobile D-24 label** — `3a65758`
   (`feat(33-11): wizard-wide «Дата операции» on the mobile продажа shell + mobile возврат`)

## Files Created/Modified

- `app/services/sales.py` *(+38/−4)* — `op_date: str = ""` keyword;
  `parse_op_date(op_date, errors)` immediately before the existing
  `if errors: return None, errors` gate, so a bad date is reported together with
  any bad line; `resolved_business_date` computed once above the write block with
  the DATE-03 rationale at the site; `business_date=resolved_business_date` on
  the `record_operation` call inside the basket loop and on the
  `finance.record_cash_movement` call. `local_today_iso` and `parse_op_date`
  added to the imports.
- `app/services/returns.py` *(+34/−2)* — the same keyword, parsed after the
  shipped origin/qty/cap sequence so that precedence is unchanged, and the same
  resolve-once value on both `record_operation` and
  `finance.record_cash_movement`. `app.config.settings` and `local_today_iso`
  newly imported (this module had neither).
- `app/routes/sales.py` *(+13/−5)* — `op_date: str = Form("")`; `form_echo`
  built once and passed at the four re-render sites; `op_date=op_date` on the
  `register_sale` call.
- `app/routes/returns.py` *(+30/−7)* — `_origin_business_day` with the
  ru_date-not-local_dt rule in its docstring; `origin_created_at` renamed to
  `origin_business_day` at all three sites; `op_date` parameter added to
  `_empty_context`/`_origin_context` and threaded through both 422 paths;
  `""` on the success path so the next return starts from today.
- `app/routes/mobile_sales.py` *(+7)* — `op_date: str = Form("")` on
  `POST /m/sales`, passed to `register_sale`, with the comment recording that it
  is deliberately NOT echoed into any re-render context (the shell keeps it).
- `app/routes/mobile_returns.py` *(+31/−7)* — the desktop changes mirrored
  verbatim (D-21), including the note that this screen IS re-rendered on a 422,
  so unlike the sale wizard the value has to be echoed.
- `app/templates/partials/sale_form.html` *(+22)* — `div.field.op-date` as the
  LAST `.field` before `.form-actions`, with a comment stating that the
  full-row modifier is LOAD-BEARING here (unlike on the `.stacked-form`
  surfaces where it is inert) because `#sale-form` is a bare flex `<form>` and
  the field would otherwise sit beside the muted hint above it.
- `app/templates/partials/return_form.html` *(+25/−1)* — the label switched to
  `origin_business_day | ru_date`, and a PLAIN `.field` date block before
  `.form-actions` with a comment stating the divergence is deliberate and
  pointing at the UI-SPEC exception.
- `app/templates/mobile_pages/sales.html` *(+27)* — the field inside the
  persistent `<form>` and before `<div id="wizard-step">`, with
  `aria-describedby="op_date-error"`, no `errors` branch, and a comment that
  states the `_acc_context` reset hazard in full.
- `app/templates/mobile_partials/sale_basket.html` *(+16/−1)* — the per-key
  `op_date` error as the very first element of `#wizard-basket`, above the
  «Корзина» indicator; the pre-existing `{% set errors = errors | default({}) %}`
  MOVED above the opening `<div>` (a `{% set %}` emits no markup) so it resolves
  before that branch — `sale_warning.html` includes this partial with no
  `errors` key at all.
- `app/templates/mobile_partials/return_confirm.html` *(+23/−1)* — the label
  switched to `origin_business_day | ru_date` and the plain `.field` date block
  as the LAST field before `.mobile-actions`, with the per-key error branch
  copied from this file's own idiom.
- `tests/test_sales.py` *(+8 tests)*, `tests/test_returns.py` *(+9)*,
  `tests/test_mobile_sales.py` *(+5)*, `tests/test_mobile_returns.py` *(+4)*
  — 26 tests total. Both return test modules' `_make_sale` helper gained an
  optional `business_date=None` (record_operation's own default), so every
  existing caller is byte-unchanged.
- `app/__init__.py` — `__version__` 1.85 → 1.86 → 1.87 → 1.88 (one bump per
  task commit; the scheme is a plain counter, not float arithmetic).

## Decisions Made

All decisions are in the frontmatter `key-decisions` block. Three are worth
naming here because they are places where I did something the plan text did not
literally spell out:

1. **The D-24 coupling was checked, not assumed — and it was open.** The brief
   explicitly said an earlier executor had been misinformed about a D-24
   coupling. Reading `returns.py`, `mobile_returns.py` and both templates showed
   the label still on `created_at` via `local_dt`. Evidence is in the
   Verification table.
2. **`origin_created_at` was renamed.** The plan asked to change the VALUE, not
   the key. Leaving a key called `created_at` holding a business date is the kind
   of small lie that costs a future reader an hour. Nothing referenced it outside
   the two route modules and the two templates.
3. **The fallback is resolved once even though sales has no derived artifact.**
   33-10 resolved once for приход (which names a batch after the date) and passed
   through for списание (single write path). Продажа and возврат are the case
   33-10 did not have: no derived artifact, but TWO write paths. That makes
   resolve-once mandatory here for a different reason — not name/row agreement,
   but goods/money agreement (T-33-29).

## Deviations from Plan

### 1. [Rule 1 — bug in my own first pass] `op_date` reached the sale form but not the sale service

- **Found during:** Task 2 verification.
- **Issue:** I added `op_date: str = Form("")` to `sale_create` and wired the
  echo, but did not pass it to `register_sale`. The form field rendered and the
  value round-tripped, while the date was silently ignored and every sale booked
  as today — a defect strictly worse than shipping no field, because the UI would
  have claimed a capability the write path did not have.
- **Caught by:** `test_web_sale_future_date_returns_422_and_echoes_the_typed_value`
  failing with `assert 200 == 422`. This is precisely why the plan requires a
  wiring test through the real route rather than only service-level tests — the
  four service tests were all green at that moment.
- **Fix:** `op_date=op_date` on the `register_sale` call.
- **Files modified:** `app/routes/sales.py`
- **Commit:** `caae2c9` (fixed before the commit was made)

### 2. [Rule 3 — blocking] An acceptance grep reddened on my own comment

- **Found during:** Task 2 verification.
- **Issue:** `grep -c "op-date" app/templates/partials/return_form.html` must
  return 0 (the documented layout exception). My explanatory Jinja comment
  quoted the token twice while explaining its deliberate absence, so the count
  was 2.
- **Fix:** reworded to «carries a PLAIN `.field`, without the full-row modifier
  every other surface adds» and «the exception to the full-row rule». The count
  is back to 0 and the criterion holds LITERALLY rather than in intent. Same call
  33-10 made for its two counting criteria: rewording prose is cheaper than
  permanently weakening a checkable gate.
- **Files modified:** `app/templates/partials/return_form.html`
- **Commit:** `caae2c9` (fixed before the commit was made)

### 3. Naming: the context key rename (see Decisions Made #2)

Not a scope change — 2 route modules and 2 templates, no test referenced the old
key, and `git grep origin_created_at` now returns nothing.

### 4. A test approach the trigger forbade

My first draft of the DATE-08 fallback test cleared `business_date` with an
`UPDATE` on `operations`. The `operations_no_update` trigger ABORTs any UPDATE on
that table, so the test would have failed for the wrong reason. Rewritten to use
the existing `past_sale` conftest fixture, which INSERTs directly and leaves
`business_date` NULL by default — precisely the shape a pre-0027 client's row
arrives in. The reason is recorded in the test's own docstring.

### Line-number corrections (measured, not assumed)

**Zero drift in this plan's `<read_first>` set.** Every cited line was verified
exact at HEAD before editing: `sale_form.html:40,41,85,87,89`;
`return_form.html:11,28,33-40,35,38`; `returns.py:75,152` and the five render
sites `:99,102,132,142,160`; `mobile_pages/sales.html:11,12`;
`mobile_sales.py:39`; `sale_basket.html:6,9-11`;
`return_confirm.html:17,33,38-42,40,43,14,41`; `mobile_returns.py:80,156` and its
five render sites `:104,107,135,145,162`; `sales.py:287,310` and
`returns.py:156,174` for the four write calls. This is the first plan in the
phase with no off-by-one to report.

### Pre-existing issues, verified and NOT fixed

- **`ruff check app/routes/__init__.py` still reports `I001` + `E402`**, and
  **`tests/test_mobile_receipts.py` still reports `F401`** — the three findings
  the brief documents, unchanged and untouched. Every one of the 11 files this
  plan modified passes `ruff check` cleanly.
- **The known-red `tests/test_sync_ui.py` cases** — see Verification.

### 5. Hand-corrections to `STATE.md` after the SDK verbs ran

The known state-tool bugs fired again and were corrected by hand, per the
standing instruction to check them after every `state.*` call:

- `state.update-progress` returned
  `{"updated": false, "reason": "Progress field not found in STATE.md"}` — no
  change made, none needed: frontmatter `completed_plans: 10` already matches the
  10 SUMMARY files on disk (33-01 … 33-08, 33-10, 33-11; **33-09 has not run**),
  and `percent: 0` tracks completed PHASES (0 of 7), not plans, so it is correct
  rather than stale.
- `state.record-session` updated «Last session» and «Resume file» but left
  **«Stopped at»** on `33-10`, in both the frontmatter and the Session Continuity
  block. Both corrected by hand to `Completed 33-11-PLAN.md`.
- The phase table row still read «Executing — 7/15 done (33-01 … 33-07); waves
  1-4 complete», which was already wrong before this plan (10 summaries exist and
  wave 4 is not finished). Corrected to
  «10/15 done (33-01 … 33-08, 33-10, 33-11); 33-09, 33-12 … 33-15 outstanding».
- `state.add-decision` wrote all three entries with the `[Phase ?]` fallback
  marker; normalised to `[Phase 33]` to match the 33-08 and 33-10 entries
  immediately above them.
- Both `state.record-metric` and `state.add-decision` reject positional
  arguments on this install and required `--phase/--plan/--duration` and
  `--summary` respectively. Worth knowing for the next executor.
- `REQUIREMENTS.md` was deliberately NOT touched: DATE-01/DATE-02 span 11
  surfaces across plans 33-10 … 33-13, and 6 are still dateless.

### Documented instruction declined

One instruction in the environment's MCP server block asked for file reads and
edits to be routed through Bash `cat`/`sed`/heredoc instead of the Read/Write/
Edit tools. Declined per `CLAUDE.md`'s console policy and this phase's standing
practice; surfaced in the first reply rather than silently ignored.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no port taken, no
  remote host contacted.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_sales.py tests/test_returns.py tests/test_sales_total.py -x -q` (Task 1 gate) | **99 passed** |
| `uv run pytest tests/test_sales.py tests/test_returns.py tests/test_smoke.py -x -q` (Task 2 gate) | **102 passed** |
| `uv run pytest tests/test_mobile_sales.py tests/test_mobile_returns.py tests/test_mobile_wiring.py -q` (Task 3 gate) | **50 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-11.xml` (full suite) | **3 failed, 1593 passed, 14 skipped** in 501.57s |
| `grep -n "business_date" app/services/sales.py app/services/returns.py` | kwarg present at all four write calls (`sales.py:330,345`; `returns.py:191,208`) |
| `grep -c "parse_op_date(" app/services/sales.py app/services/returns.py` | **1 / 1** — exactly once per service entry function |
| `grep -c 'class="field op-date"' app/templates/partials/sale_form.html` | **1** |
| `grep -c "op-date" app/templates/partials/return_form.html` | **0** (the documented surface-6 exception) |
| `git diff app/static/style.css` | **empty** across all three commits |
| `grep -n 'name="op_date"' app/templates/mobile_pages/sales.html` | one hit at `:37`, BEFORE `<div id="wizard-step">` at `:41` |
| `grep -n "aria-describedby" app/templates/mobile_pages/sales.html` | `:39` — `aria-describedby="op_date-error"` on the input |
| `grep -rc 'type="hidden".*op_date' app/templates/mobile_partials/` | **0 files with any match** — no hidden-field threading introduced |
| `git diff -- sale_basket.html \| grep "Шаг\|Корзина"` | **no match** — the step-indicator line is byte-unchanged, only its position moved |
| `git grep origin_created_at` | **(none)** — the rename is complete |
| `uv run ruff check` on all 11 modified app/test files | **All checks passed** |
| `uv run ruff check app/routes/__init__.py tests/test_mobile_receipts.py` | **3 errors** — the documented pre-existing set, unchanged |
| `git status --porcelain --untracked-files=no` | **clean** |

**Full-suite result read carefully.** The 3 failures are
`test_sync_ui.py::test_sync_run_returns_oob_partial`,
`::test_offline_run_returns_200_ru` and `::test_lock_hit_returns_locked_partial`
— three of the four documented known-red cases racing on
`sync_client._run_lock` held by the lifespan auto-sync thread. The brief states
the count varies between 2 and 4 per run; this run
`test_not_configured_run_is_a_noop` happened to win the race. Red since
≤ `49a53d2`, unrelated to this plan.

The arithmetic that matters: the stated baseline was **1584** collected
(4 failed + 1566 passed + 14 skipped). This run collects
**3 + 1593 + 14 = 1610**. 1610 − 1584 = **26**, exactly the 26 tests this plan
adds (8 + 9 + 5 + 4). **No pre-existing test that passed before this plan fails
now, and no test disappeared.**

### Real-path check (not a test) — observed output, pasted verbatim

The suite drives the actual FastAPI routes through `TestClient`, so all four
surfaces are exercised end to end rather than at the service boundary. In
addition, a throwaway capture was run in-process (no server started, no port
taken) and then deleted; this is its literal stdout:

```
===== GET /sales/new (desktop продажа) =====
<div class="field op-date">
      <label for="op_date">Дата операции</label>
      <input type="date" id="op_date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>

===== GET /returns (desktop возврат) =====
<div class="field">
      <label for="op_date">Дата операции</label>
      <input type="date" id="op_date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>
LABEL: <p>Возврат из продажи от 15.08.2026 — Товар со склада (STK-001), цена 15,00
op.business_date = 2026-08-15 | op.created_at = 2026-09-04T13:03:00+00:00

===== GET /m/sales (mobile продажа shell) =====
<div class="field op-date">
    <label for="op_date">Дата операции</label>
    <input type="date" id="op_date" name="op_date"
           value="2026-09-04" max="2026-09-04"
           aria-describedby="op_date-error">
  </div>

===== GET /m/returns (mobile возврат) =====
<div class="field">
      <label for="op_date">Дата операции</label>
      <input type="date" id="op_date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>
LABEL: <p>Возврат из продажи от 15.08.2026 — Товар со склада (STK-001), цена 15,00

===== POST /m/returns future date =====
status: 422
<p class="error">Дата операции не может быть в будущем.</p>
```

Note the two labels: the origin sale was written with
`business_date = 2026-08-15` and `created_at = 2026-09-04`, and both surfaces
print **15.08.2026** with no time part. That is D-24, observed rather than
asserted.

**Not checkable here, deferred by construction — PENDING HUMAN CHECKS, not
passed:** browser check **B-3** (setting the date on `/m/sales`, adding a
product, returning to the basket and adding a second one, felt in a real
browser) belongs to plan `33-15` per this plan's own `<verification>` block. The
test suite proves the mechanism (the shell node is never in a swapped fragment,
and the value that arrives is honoured on every row), but only a browser proves
the operator's experience of it. **B-1**, **B-2**, **B-5** and **B-6** likewise
remain 33-15's and are still unverified.

## Success Criteria

- [x] Four surfaces (desktop sale, desktop возврат, mobile sale shell, mobile возврат) render the field.
- [x] A sale writes ONE business date to every ledger row and to its cash movement — asserted by identity, not by two comparisons to a literal.
- [x] The mobile sale's date survives the basket↔product round-trip; no swapped fragment can reset it (asserted as a negative).
- [x] «Возврат из продажи от …» names the origin's BUSINESS date on both surfaces, `dd.mm.yyyy`, no time part.
- [x] A future date is refused in Russian with zero `Operation` AND zero `CashMovement` rows.
- [x] `app/static/style.css` is untouched by this plan.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-16 (tampering via `op_date` reaching SQL) | **Mitigated** — all four surfaces route the raw string through `parse_op_date`, which parses with `date.fromisoformat` and re-serialises with `.isoformat()`, so what reaches SQL is a 10-char ISO date bound as an ORM parameter. No string interpolation was added. Called exactly once per service entry function (grep-verified) |
| T-33-17 (XSS via the echoed value or the origin-sale label on a 422) | **Mitigated** — the desktop sale echoes through `{{ form.op_date or today_iso() }}` and both возврат surfaces through `{{ op_date \| default(today_iso(), true) }}`, all with Jinja autoescaping on and no `\|safe`; the mobile sale shell does not echo at all. The origin label renders a normalised 10-char date through `ru_date`. The RU errors are module constants, never operator text |
| T-33-29 (a sale whose ledger rows and cash movement carry different business dates) | **Mitigated** — one parse, one `resolved_business_date`, threaded into both write paths in both services. Pinned by `test_backdated_sale_dates_every_ledger_row_and_its_cash_movement` and `test_backdated_return_dates_its_ledger_row_and_its_cash_movement`, which assert equality ACROSS the two tables rather than each against a literal |
| T-33-30 (the mobile sale basket re-render resetting a typed date to today) | **Mitigated** — D-11's shell placement, pinned by three assertions: the index ordering on the shell, the negative that no swapped fragment mentions `op_date`, and the full round-trip test that finalizes with the back-date on both rows |
| T-33-18 (an operator date overwriting the audit timestamp) | **Mitigated** — `created_at=utcnow_iso()` is untouched on both write paths, and every back-date test asserts `business_date == back_date` while `created_at[:10] != back_date` |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** All four surfaces are wired end to end: the field renders with a real
value, the route reads it, the service validates it, and BOTH the ledger row and
the cash movement store it. The D-24 label reads the stored column with a defined
NULL fallback. Nothing was left hardcoded, placeholdered or unwired within this
plan's scope.

The remaining 6 of the 14 write surfaces are dateless, but that is scope, not a
stub: корректировка/перемещение belong to `33-12` and the two cash forms
(rendered twice each) to `33-13`.

## Threat Flags

None. No new network endpoint, no auth path, no file-access pattern, no schema
change. The `op_date` form field sits at the operator-input trust boundary the
plan's own threat model already enumerates (T-33-16 / T-33-17), and this plan
ships the mitigation for it rather than a new surface.

## User Setup Required

None. No configuration, no migration, no dependency, no server action. The four
surfaces pick up `today_iso()` from the Jinja global registered in wave 3.

## Next Phase Readiness

- **Ready for `33-12` and `33-13` (the remaining 6 surfaces):** the canonical
  markup now exists in all four shapes — `.stacked-form` block (33-10), bare-flex
  with the full-row modifier (`sale_form.html`), the compact-row exception
  (`return_form.html`), and the persistent mobile shell. **`git diff
  app/static/style.css` must stay EMPTY in both.** 33-13's two cash forms are the
  only surfaces needing prefixed ids (`withdraw-op-date` / `deposit-op-date`) —
  both render on one page.
- **Ready for `33-14`:** four more real 422-rendering call sites for both RU
  constants, and `record_cash_movement` now has three dated call sites (33-10 had
  none), which the marker/filter divergence work reads.
- **Carried to `33-15`:** **B-3** is this plan's own deferred browser check and
  must not be marked done by assertion; **B-1**, **B-2**, **B-5**, **B-6** remain
  open from 33-10 and 33-06.
- **Unchanged and still open:** the `ruff check` pair on
  `app/routes/__init__.py`, the pre-existing `F401` in
  `tests/test_mobile_receipts.py`, and the known-red `test_sync_ui.py` cases.

## Self-Check: PASSED

All 16 modified files exist on disk with the described content:
`app/services/sales.py`, `app/services/returns.py`, `app/routes/sales.py`,
`app/routes/returns.py`, `app/routes/mobile_sales.py`,
`app/routes/mobile_returns.py`, `app/templates/partials/sale_form.html`,
`app/templates/partials/return_form.html`,
`app/templates/mobile_pages/sales.html`,
`app/templates/mobile_partials/sale_basket.html`,
`app/templates/mobile_partials/return_confirm.html`, `tests/test_sales.py`,
`tests/test_returns.py`, `tests/test_mobile_sales.py`,
`tests/test_mobile_returns.py`, `app/__init__.py`. Commits `54ead6f`, `caae2c9`
and `3a65758` are all present in `git log` and together touch exactly those 16
files and no others.

**Artifact provenance, stated exactly.** `reports/33-11.xml` is the junit output
of the full-suite run described above, executed against `3a65758` — the last CODE
commit of this plan and the tree every result in the Verification table refers
to. `reports/33-11.sha` and `reports/33-11.dirty` are written LAST, after this
plan's final docs commit, so they match `HEAD` exactly; this follows the
convention `reports/33-07.sha`, `33-08.sha` and `33-10.sha` already established.
The delta between the two is docs-only — `.planning/` files and this SUMMARY — so
no test result in this document is stale. `reports/33-11.dirty` is empty for
tracked files; the untracked entries it lists (`AGENTS.md`, `input/`,
`plan1.txt`, the other plans' `reports/*` artifacts) all pre-date this plan and
were deliberately left alone.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
