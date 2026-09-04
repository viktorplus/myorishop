---
phase: 33-back-dated-operations
plan: 10
subsystem: write-surfaces
tags: [jinja, htmx, forms, validation, batch-naming, mobile-wizard, russian-ui]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "parse_op_date + OP_DATE_FORMAT_ERROR/OP_DATE_FUTURE_ERROR, the business_date= kwarg on record_operation, the today_iso() zero-arg Jinja global, and the .field.op-date CSS rule these four surfaces render but do not own"
provides:
  - "app/services/receipts.py::register_receipt — op_date keyword, parsed before any write, threaded into all three record_operation calls"
  - "app/services/writeoffs.py::register_writeoff — op_date keyword, parsed before any write, threaded into its record_operation call"
  - "the D-24 batch auto-name: «{product.name} — {ru(business date)}», resolved BEFORE the Batch is constructed"
  - "app/templates/partials/receipt_form.html + writeoff_form.html — the canonical desktop date field (surfaces 1 and 3 of 14)"
  - "app/templates/mobile_pages/receipts.html + writeoff.html — the D-11 persistent-shell date field (surfaces 9 and 11 of 14)"
  - "op_date excluded from the two loop-all error blocks and emitted as the FIRST element of each swapped final step"
affects: [33-11, 33-12, 33-13, 33-14, 33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A wizard-wide value belongs in the persistent shell <form> that htmx never swaps, ABOVE the swapped node — that is what makes it survive every step swap and every 422 with zero hidden-field threading, and it also forbids any step partial from re-emitting it"
    - "When a derived artifact is named after a date, the date must be resolved ONCE and reused for both the artifact and the ledger row — resolving it twice lets a save at midnight split the two"
    - "An error whose input lives in a never-swapped node is emitted as the FIRST element of the swapped node instead, and excluded from every loop-all block, so it renders exactly once and adjacent to its field"
    - "An acceptance criterion phrased as a grep count is a real constraint on the prose you write: a code comment that names the forbidden token reddens the criterion, so name the concept instead of quoting the token"

key-files:
  created: []
  modified:
    - app/services/receipts.py
    - app/services/writeoffs.py
    - app/routes/receipts.py
    - app/routes/writeoffs.py
    - app/routes/mobile_receipts.py
    - app/routes/mobile_writeoff.py
    - app/templates/partials/receipt_form.html
    - app/templates/partials/writeoff_form.html
    - app/templates/mobile_pages/receipts.html
    - app/templates/mobile_pages/writeoff.html
    - app/templates/mobile_partials/receipts_step_confirm.html
    - app/templates/mobile_partials/writeoff_step_reason.html
    - tests/test_receipts.py
    - tests/test_writeoffs.py
    - tests/test_mobile_receipts.py
    - tests/test_mobile_writeoff.py
    - app/__init__.py

key-decisions:
  - "33-10 (D-24, and it must be stated because the execution brief said the opposite): the batch auto-name was NOT already switched by plan 33-08. 33-08's D-24 work was «Последняя приёмка» in warehouses.py and last_order_date in customers.py; app/services/receipts.py was untouched by this phase before this plan (last commit 5eeb94b, pre-Phase-33) and still built its name from `datetime.now(ZoneInfo(settings.display_tz)).date()`. D-24 has two independent couplings and this plan owns the batch-name one. Verified by reading, not assumed."
  - "33-10: register_receipt resolves the today-fallback ONCE into `resolved_business_date` and passes that same string to the batch name AND to all three record_operation calls, instead of passing the possibly-None parsed value and letting record_operation resolve it again. Both are behaviourally identical except at the local midnight boundary, where the double resolution can name the batch with one day and stamp the receipt line with the next — the exact class of contradiction D-24 exists to prevent."
  - "33-10: register_writeoff passes the possibly-None parsed value straight through, because it has no derived artifact to keep in sync — record_operation's Python-side fallback is the single resolution point and adding a second one would be a second definition of «today» for no gain."
  - "33-10 (D-11 + CF-UI-1): op_date is deliberately ABSENT from both mobile form_echo/re-render contexts. The shell node is never swapped, so the operator's value is still in the DOM on a 422; echoing it back would create a second source of truth for a value that already survives by construction."
  - "33-10: two Task-2 acceptance criteria (`grep -c \"необязательно\"` and `grep -c \"required\"` unchanged from HEAD) initially went RED because the explanatory Jinja comments quoted the very tokens the criteria count. The comments were reworded to name the concept («NO optional-hint span», «deliberately NOT marked mandatory») rather than the token, so both criteria hold LITERALLY rather than in intent. Rewording prose is cheaper than permanently weakening a checkable gate."
  - "33-10: app/services/receipts.py's now-orphaned `datetime` / `ZoneInfo` imports were removed (CLAUDE.md rule 7 — remove what YOUR change orphaned). `settings` stays: it is still read by local_today_iso(settings.display_tz)."
  - "33-10: DATE-01/DATE-02 are NOT marked complete. This plan lands 4 of the 14 write surfaces; продажа/возврат (33-11), корректировка/перемещение (33-12) and the two cash forms (33-13) are still dateless. Marking them here would make REQUIREMENTS.md's traceability table claim work that has not shipped."

patterns-established:
  - "A comment that explains why an attribute is INERT on this surface (mobile max=) is written at the surface itself, together with the instruction not to 'fix' it — an inert-looking attribute is otherwise a magnet for a future cleanup that would change the wizard's submit mechanics"

requirements-completed: []

# Metrics
duration: 55min
completed: 2026-09-04
---

# Phase 33 Plan 10: Приход and Списание Business Date Summary

**Four of the fourteen write surfaces now carry «Дата операции» — two desktop
`.stacked-form`s where the browser's own `max=` bubble is the first guard, and
two mobile wizards where the field rides the persistent shell that htmx never
swaps so it survives every step without a single hidden field — plus D-24's
batch auto-name, which had NOT been done by an earlier plan and which now
follows the business date so a back-dated receipt and its own batch can never
print different days.**

## Performance

- **Duration:** ~55 min (including a 7m37s full-suite run)
- **Tasks:** 3, one commit each
- **Files modified:** 17 (0 created)
- **Tests added:** 23

## Accomplishments

- **D-24's batch-name coupling was actually open, and closing it was the
  load-bearing part of Task 1.** The execution brief asserted the auto-name had
  already been switched by plan 33-08 and must not be touched. Reading the file
  first showed otherwise: 33-08's D-24 work was «Последняя приёмка»
  (`warehouses.py`) and `last_order_date` (`customers.py`), while
  `app/services/receipts.py` had not been touched by this phase at all
  (`git log -1` on it returns `5eeb94b`, a pre-Phase-33 currency commit) and
  still computed `datetime.now(ZoneInfo(settings.display_tz)).date()` for the
  name. Had the brief been followed, a receipt back-dated to 15.08 would have
  created a batch named «Крем — 04.09.2026» sitting directly beside its own
  receipt line reading 15.08 — the exact defect T-33-28 names.
  `test_backdated_receipt_names_its_batch_with_the_back_date` now pins it.
- **The fallback is resolved once, and that is a deliberate strengthening of the
  plan's letter.** The plan said to thread «the parsed value». Doing that
  literally would leave `record_operation` to resolve the today-fallback a
  second time, microseconds after the batch name resolved it — harmless on 364
  days a year and wrong at local midnight, where the name would read one day and
  the ledger line the next. `resolved_business_date` is computed once,
  immediately after validation, and is the single value the name and all three
  ops share. The comment at the resolution site says why, in those terms.
- **Zero writes on refusal is asserted by counting rows, not by trusting the
  early return.** Both future-date tests snapshot the ledger row count before
  the call and re-assert it after; the receipt one additionally asserts that no
  `Product` card was auto-created and no `Batch` exists, because
  `register_receipt`'s auto-create path is precisely what a validation gap would
  leak. The write-off one also re-checks `compute_stock`.
- **The mobile date really is un-swappable, and the tests prove the negative.**
  `test_receipt_wizard_steps_never_re_emit_the_date` and its write-off twin POST
  through the intermediate steps and assert the substring `op_date` is absent
  from every swapped fragment — so the shell is provably the only place the
  value lives, and a future edit that "helpfully" threads it as a hidden field
  reddens. The shell tests additionally assert `index('name="op_date"') <
  index('id="wizard-step"')` and `< index("Шаг 1 из 4")`, which is D-11's
  placement rule and the UI-SPEC's «above the step indicator» rule as executable
  assertions rather than prose.
- **The error placement is asserted by shape, not just by presence.** Both
  mobile 422 tests assert the exact string `<p class="error">…</p>` is present,
  that `<div class="error-block">…</div>` with the same message is NOT, that the
  message appears exactly once, and that its index precedes «Шаг 4 из 4». That
  is CF-UI-1's resolution — D-11 wins on placement, D-14's intent is satisfied by
  first-element emission — expressed as four independent checks.
- **`app/static/style.css` is untouched.** `git diff` against it is empty across
  all three commits and `grep -c "op-date"` is still 1 — the rule shipped in
  wave 3, exactly as 33-06 arranged.
- **«Шаг N из M» is byte-unchanged.** Both step strings are still
  `<p class="mobile-step-indicator">Шаг 4 из 4</p>`; only their line numbers
  moved (8→24 and 14→24) because the new comment and error branch sit above them.

## Task Commits

1. **Task 1 — the service layer + the D-24 batch name** — `8a38dc8`
   (`feat(33-10): op_date on the receipt/writeoff services + the D-24 batch name`)
2. **Task 2 — the two desktop forms and their routes** — `c53b993`
   (`feat(33-10): «Дата операции» on the desktop приход and списание forms`)
3. **Task 3 — the two mobile shells + per-file error placement** — `972cf2a`
   (`feat(33-10): wizard-wide «Дата операции» on the mobile приход/списание shells`)

## Files Created/Modified

- `app/services/receipts.py` *(+35/−7)* — `op_date: str = ""` keyword;
  `parse_op_date(op_date, errors)` beside the other `parse_*` calls and before
  the `if errors: return None, errors` gate; `resolved_business_date` computed
  once beneath it; `business_date=resolved_business_date` on all three
  `record_operation` calls (`product_created`, `price_change`, `receipt`); the
  batch auto-name switched from `local_today` to `resolved_business_date` with
  the D-24 rationale and the snapshot rule restated at the site. Orphaned
  `datetime` / `ZoneInfo` imports removed; `local_today_iso` and `parse_op_date`
  added. The pre-existing snapshot-rule comment is otherwise untouched.
- `app/services/writeoffs.py` *(+18/−1)* — the same keyword and the same
  pre-write parse; `business_date=business_date` on its single
  `record_operation` call.
- `app/routes/receipts.py` / `app/routes/writeoffs.py` *(+6 each)* —
  `op_date: str = Form("")`, added to the existing `form_echo` dict (so the 422
  and, on write-off, the oversell warn re-render both redisplay the typed
  value), and passed to the service.
- `app/templates/partials/receipt_form.html` / `writeoff_form.html` *(+19/+21)*
  — the canonical `div.field.op-date` + `label[for]` + `input[type=date]` with
  `value="{{ form.op_date or today_iso() }}"` and `max="{{ today_iso() }}"`,
  plus the per-key `<p class="error">`, as the LAST `.field` before
  `.form-actions`. A Jinja comment names DATE-01/D-10, states why `max=` is safe
  here (`hx-post` on the `<form>`, native submit button), and states that an
  empty value means «today». Neither comment repeats CF-UI-2's false
  `<details>` claim.
- `app/templates/mobile_pages/receipts.html` / `writeoff.html` *(+21/+22)* — the
  same field INSIDE the persistent `<form>` and BEFORE `<div id="wizard-step">`,
  with `value="{{ today_iso() }}"`, no `errors` branch, and a comment recording
  the position rule, the zero-threading property, and that `max=` is inert here
  by design.
- `app/templates/mobile_partials/receipts_step_confirm.html` *(+10/−1)* — the
  per-key `op_date` error as the very first element of the `{% else %}` branch,
  above «Шаг 4 из 4»; the loop exclusion widened from `key != "form"` to
  `key not in ("form", "op_date")`.
- `app/templates/mobile_partials/writeoff_step_reason.html` *(+10/−1)* — the same
  first-element `<p class="error">`, and `if _key != "op_date"` added to the
  `.error-block` loop so a field-specific message never renders as a
  whole-screen block.
- `tests/test_receipts.py` *(+9 tests)*, `tests/test_writeoffs.py` *(+6)*,
  `tests/test_mobile_receipts.py` *(+4)*, `tests/test_mobile_writeoff.py` *(+4)*
  — 23 tests total.
- `app/__init__.py` — `__version__` 1.82 → 1.83 → 1.84 → 1.85 (one bump per task
  commit; the scheme is a plain counter, not float arithmetic).

## Decisions Made

All decisions are in the frontmatter `key-decisions` block. Two are worth naming
here because they are places where this plan deliberately diverged from an
instruction it was given:

1. **The batch auto-name WAS this plan's job.** The execution brief listed «the
   batch auto-name was already switched by 33-08 — do not switch it again or
   revert it» among the decisions not to reopen. The code said otherwise and the
   code won. The correction is recorded in the frontmatter with the evidence
   (`git log -1 -- app/services/receipts.py` → `5eeb94b`) so the next reader does
   not have to re-derive it.
2. **Two grep-shaped acceptance criteria were made to pass literally rather than
   argued into "satisfied in intent".** The first drafts of the two desktop
   comments contained the words `required` and «необязательно» while explaining
   their own absence from the markup, which pushed both counts one above HEAD.
   Rather than write a deviation note explaining why a counting criterion cannot
   be satisfied — the shape 33-06 had to use for its `strftime` criterion, where
   the action genuinely mandated the token — the prose was reworded. A gate that
   still counts is worth more than a gate with an exemption attached.

## Deviations from Plan

### 1. [Rule 1 — correctness] The brief's «33-08 already switched the batch auto-name» is false

- **Found during:** Task 1, before writing any code.
- **Issue:** the execution brief instructed that D-24's batch-name switch was
  already done and must not be touched. `app/services/receipts.py:209-210` still
  read `local_today = datetime.now(ZoneInfo(settings.display_tz)).date()` /
  `batch_name = f"{product.name} — {format_ru_date(local_today.isoformat())}"`,
  and `git log --oneline -1 -- app/services/receipts.py` returns `5eeb94b`, a
  pre-Phase-33 commit. 33-08's SUMMARY confirms its D-24 work was «Последняя
  приёмка» and `last_order_date`, not the batch name — D-24 has two independent
  couplings and this plan owns the second one.
- **Fix:** implemented the switch as `33-10-PLAN.md` Task 1 actually specifies,
  and pinned it with `test_backdated_receipt_names_its_batch_with_the_back_date`
  plus `test_receipt_without_op_date_keeps_the_shipped_batch_name` (the no-date
  path is byte-identical to what shipped before).
- **Files modified:** `app/services/receipts.py`, `tests/test_receipts.py`
- **Commit:** `8a38dc8`

### 2. [Rule 2 — correctness] The today-fallback is resolved once, not twice

- **Found during:** Task 1.
- **Issue:** the plan says to pass «the parsed value» to `record_operation`.
  Taken literally, `None` would flow through and `record_operation` would resolve
  the fallback independently, a moment after the batch name resolved its own.
  Across local midnight the two resolutions differ by a day, reintroducing
  exactly the name/line contradiction D-24 forbids.
- **Fix:** `resolved_business_date = business_date or local_today_iso(...)` is
  computed once and used for the name and all three ops.
  `register_writeoff`, which has no derived artifact, keeps the simple pass-through.
- **Files modified:** `app/services/receipts.py`
- **Commit:** `8a38dc8`

### 3. [Rule 3 — blocking] Two acceptance greps reddened on my own comments

- **Found during:** Task 2 verification.
- **Issue:** `grep -c "необязательно" writeoff_form.html` went 1→2 and
  `grep -c "required" receipt_form.html` went 3→4, because the new Jinja
  comments quoted those tokens while explaining that the markup must not use
  them.
- **Fix:** reworded to «the label carries NO optional-hint span» and «the input
  is deliberately NOT marked mandatory (Interaction Contract §4)». Both counts
  are back at their HEAD values and the criteria hold literally.
- **Files modified:** `app/templates/partials/receipt_form.html`,
  `app/templates/partials/writeoff_form.html`
- **Commit:** `c53b993` (fixed before the commit was made)

### 4. Cosmetic: an inert `{% raw %}` in a Jinja comment

- `mobile_pages/writeoff.html`'s first draft wrote `{% raw %}{% else %}{% endraw %}`
  inside a `{# … #}` comment. Jinja's lexer discards comment bodies wholesale, so
  the `raw` tags were inert noise that could mislead a reader into thinking they
  were doing something. Reworded to «inside the not-saved branch». No behaviour
  change; corrected before the Task 3 commit.

### Line-number corrections (measured, not assumed)

- **`app/services/receipts.py:208`/`:209` are really `:209`/`:210`** at HEAD.
  The plan's `<read_first>` cites `:208` for the `local_today` computation and
  `:209` for `batch_name` — the same off-by-one 33-06 already recorded and
  labelled CD-2. Every OTHER line reference in this plan was verified exact:
  `receipts.py:160/:186/:241` and `writeoffs.py:105` for the four
  `record_operation` calls; `receipt_form.html:23`/`:94`;
  `writeoff_form.html:17`/`:19`/`:75`/`:79`;
  `mobile_pages/receipts.html:12`/`:13`; `mobile_pages/writeoff.html:18`/`:19`/`:20`;
  `receipts_step_confirm.html:15`/`:19-21`/`:20`;
  `writeoff_step_reason.html:14`/`:17-21`. Zero drift in that set.

### Pre-existing issues, verified and NOT fixed

- **`ruff check tests/test_mobile_receipts.py` reports `F401`
  (`app.services.dictionary.add_entry` imported but unused).** Verified
  pre-existing: piping the HEAD version through `ruff check --stdin-filename`
  returns the identical error at the pre-edit line number. CLAUDE.md rule 7 says
  to remove only what my change orphaned and to mention pre-existing dead code
  rather than delete it. Every other file touched by this plan passes
  `ruff check` cleanly.
- **`ruff check app/routes/__init__.py` still reports `I001` + `E402`** —
  untouched by this plan and unchanged from 33-06's finding.
- **The four known-red `tests/test_sync_ui.py` cases** — see Verification.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no remote host
  contacted.
- One instruction in the environment's MCP server block asked for file reads and
  edits to be routed through Bash `cat`/`sed`/heredoc instead of the Read/Write/
  Edit tools. Declined, per `CLAUDE.md`'s console policy and the phase's standing
  practice; it was surfaced in the first reply rather than silently ignored.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_receipts.py tests/test_writeoffs.py tests/test_batches.py -x -q` (Task 1 gate) | **116 passed** |
| `uv run pytest tests/test_receipts.py tests/test_writeoffs.py tests/test_smoke.py -x -q` (Task 2 gate) | **83 passed** |
| `uv run pytest tests/test_mobile_receipts.py tests/test_mobile_writeoff.py tests/test_mobile_wiring.py -q` (Task 3 gate) | **48 passed** |
| `uv run pytest` over the plan's six verification files | **165 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-10.xml` (full suite) | **4 failed, 1566 passed, 14 skipped** in 457.01s |
| `grep -n "business_date" app/services/receipts.py app/services/writeoffs.py` | kwarg present at all four `record_operation` calls (`receipts.py:186,213,279`; `writeoffs.py:125`) |
| `grep -n "local_today" app/services/receipts.py` | 2 hits, neither feeding `batch_name` — the import and the single `resolved_business_date` line |
| `git diff app/services/catalog.py` | **empty** — the three product-admin/import call sites stay on the default |
| `git diff app/static/style.css` | **empty**; `grep -c "op-date"` = **1** |
| `grep -c "необязательно" writeoff_form.html` | **1** at HEAD, **1** now |
| `grep -c "required" receipt_form.html` | **3** at HEAD, **3** now |
| `grep -n 'name="op_date"' mobile_pages/receipts.html mobile_pages/writeoff.html` | one hit each, at `:32` and `:39`, both BEFORE `<div id="wizard-step">` at `:35` / `:42` |
| `grep -rc 'type="hidden".*op_date' app/templates/mobile_partials/` | **0 files with any match** — no hidden-field threading introduced |
| `grep -n "Шаг" receipts_step_confirm.html writeoff_step_reason.html` | strings byte-unchanged (`Шаг 4 из 4`); only line numbers moved |
| Loop exclusions | `receipts_step_confirm.html:29` → `key not in ("form", "op_date")`; `writeoff_step_reason.html:28` → `errors.items() if _key != "op_date"` |
| `uv run ruff check` on the 6 newly-touched app files + 3 of 4 test files | All checks passed (the 4th carries a pre-existing `F401`) |
| `git status --porcelain --untracked-files=no` | **clean** |

**Full-suite result read carefully.** The 4 failures are **exactly** the four
documented known-red `tests/test_sync_ui.py` cases
(`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`,
`test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`),
each racing on `sync_client._run_lock` held by the lifespan auto-sync thread —
red since ≤ `49a53d2`, count varies 2–4 per run, unrelated to this plan.

The arithmetic that matters: the executor's stated baseline was **1561
collected, 4 failed, 14 skipped**. This run collects **1566 + 4 + 14 = 1584**.
1584 − 1561 = **23**, exactly the 23 tests this plan adds (9 + 6 + 4 + 4).
**No pre-existing test that passed before this plan fails now, and no test
disappeared.**

### Real-path check (not a test)

The suite drives the actual FastAPI routes through `TestClient`, so the four
surfaces were exercised end-to-end rather than at the service boundary:
`GET /receipts/new`, `GET /writeoff`, `GET /m/receipts` and `GET /m/writeoff`
each render `name="op_date"` with `value="<today>" max="<today>"` and the
`field op-date` class in real response HTML, and `POST /receipts`,
`POST /writeoff`, `POST /m/receipts`, `POST /m/writeoff` each return a real 422
whose body contains «Дата операции не может быть в будущем.» with zero ledger
rows written. No server was started and no port was taken.

**Not checkable here, deferred by construction:** browser checks **B-1** (the
native `max=` bubble on `/receipts` and the absence of any network request) and
**B-2** (the mobile 422 rendering directly under the still-filled shell input)
require a real browser with a real constraint-validation implementation and a
Network tab. `TestClient` cannot exercise either — it posts whatever it is
given, which is precisely why the server-side `OP_DATE_FUTURE_ERROR` exists.
Both belong to plan `33-15` per this plan's own `<verification>` block and are
**pending human checks**, not passed. **B-6** is likewise 33-15's.

## Success Criteria

- [x] Four surfaces (2 desktop, 2 mobile) render a pre-filled, `max`-capped `op_date` input.
- [x] A future date is refused in Russian, beside the field, with zero writes (row counts asserted).
- [x] A back-dated receipt names its batch with the back-date; existing names are untouched.
- [x] `app/static/style.css` is untouched by this plan; the `.field.op-date` rule it relies on came from plan `33-06`.
- [x] On the mobile wizards the date survives every step swap with no hidden field anywhere (asserted as a negative).

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-16 (tampering via `op_date` reaching SQL) | **Mitigated** — every one of the four surfaces routes the raw string through `parse_op_date`, which parses with `date.fromisoformat` and re-serialises with `.isoformat()`, so what reaches SQL is a 10-char ISO date bound as an ORM parameter. No string interpolation was added. `max=` is a browser convenience only, and the two mobile surfaces prove it: `max` is inert there and the server still refuses (`test_mobile_receipt_future_date_error_is_the_first_element_of_the_step`) |
| T-33-17 (XSS via the value echoed on a 422) | **Mitigated** — the desktop echo goes through `{{ form.op_date or today_iso() }}` with Jinja autoescaping on and no `\|safe`; the mobile surfaces do not echo at all (the shell is never re-rendered). The RU error is a module constant, never operator text |
| T-33-18 (an operator date overwriting the audit timestamp) | **Mitigated** — `created_at=utcnow_iso()` is untouched in `record_operation`, and both «past date accepted» tests assert `business_date == back_date` while `created_at[:10] != back_date` |
| T-33-28 (a batch auto-named with today beside a back-dated receipt line) | **Mitigated** — the reason this plan exists in its current form; see Deviation 1. `test_backdated_receipt_names_its_batch_with_the_back_date` asserts the name carries the back-date AND that today's RU date is absent from it, and `test_existing_batch_name_is_never_rewritten_by_a_backdated_top_up` asserts a stored name survives a back-dated top-up |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** All four surfaces are fully wired end to end: the field renders with a
real value, the route reads it, the service validates it, the ledger stores it,
and the batch name follows it. Nothing was left hardcoded, placeholdered or
unwired within this plan's scope.

The remaining 10 of the 14 write surfaces are dateless, but that is scope, not a
stub: продажа/возврат belong to `33-11`, корректировка/перемещение to `33-12`,
and the two cash forms to `33-13`.

## Threat Flags

None. No new network endpoint, no auth path, no file-access pattern, no schema
change. The `op_date` form field sits at the operator-input trust boundary the
plan's own threat model already enumerates (T-33-16 / T-33-17), and this plan
ships the mitigation for it rather than a new surface.

## User Setup Required

None. No configuration, no migration, no dependency, no server action. The four
surfaces pick up `today_iso()` from the Jinja global registered in wave 3, so
nothing needs to be passed per-route.

## Next Phase Readiness

- **Ready for `33-11` … `33-13` (the remaining 10 surfaces):** the canonical
  markup is now shipped twice and can be copied byte-for-byte; the two mobile
  shells demonstrate the D-11 placement and the first-element error emission that
  `33-11`'s продажа wizard needs verbatim (`sale_basket.html`, per UI-SPEC §5).
  **`git diff app/static/style.css` must stay EMPTY in all three.**
- **Ready for `33-14`:** both RU constants are importable and now have real
  422-rendering call sites for the marker/filter divergence test to lean on.
- **Carried to `33-15`:** browser checks **B-1** and **B-2** are UNVERIFIED and
  must not be marked done by assertion; **B-5** (the `/history` 1024px
  `flex-wrap` observation) and **B-6** remain 33-15's.
- **Unchanged and still open:** the `ruff check` pair on
  `app/routes/__init__.py`, the pre-existing `F401` in
  `tests/test_mobile_receipts.py`, and the four known-red `test_sync_ui.py`
  cases.

## Self-Check: PASSED

All 17 modified files exist on disk with the described content:
`app/services/receipts.py`, `app/services/writeoffs.py`, `app/routes/receipts.py`,
`app/routes/writeoffs.py`, `app/routes/mobile_receipts.py`,
`app/routes/mobile_writeoff.py`, `app/templates/partials/receipt_form.html`,
`app/templates/partials/writeoff_form.html`,
`app/templates/mobile_pages/receipts.html`,
`app/templates/mobile_pages/writeoff.html`,
`app/templates/mobile_partials/receipts_step_confirm.html`,
`app/templates/mobile_partials/writeoff_step_reason.html`,
`tests/test_receipts.py`, `tests/test_writeoffs.py`,
`tests/test_mobile_receipts.py`, `tests/test_mobile_writeoff.py`,
`app/__init__.py`. Commits `8a38dc8`, `c53b993` and `972cf2a` are all present in
`git log` and together touch exactly those 17 files and no others.

**Artifact provenance, stated exactly.** `reports/33-10.xml` is the junit output
of the full-suite run described above, executed against `972cf2a` — the last
CODE commit of this plan and the tree every result in the Verification table
refers to. `reports/33-10.sha` and `reports/33-10.dirty` are written LAST, after
this plan's final docs commit, so they match `HEAD` exactly; this follows the
convention `reports/33-07.sha` and `reports/33-08.sha` already established (both
point at their plan's docs commit, not its last code commit). The delta between
the two is docs-only — `.planning/` files and this SUMMARY — so no test result
in this document is stale. `reports/33-10.dirty` is empty for tracked files; the
untracked entries it lists (`AGENTS.md`, `input/`, `plan1.txt`, the other plans'
`reports/*` artifacts) all pre-date this plan and were deliberately left alone.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
