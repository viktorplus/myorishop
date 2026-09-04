---
phase: 33-back-dated-operations
plan: 12
subsystem: write-surfaces
tags: [jinja, htmx, forms, validation, mobile-wizard, transfers, corrections, russian-ui]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 06
    provides: "parse_op_date + OP_DATE_FORMAT_ERROR/OP_DATE_FUTURE_ERROR, the business_date= kwarg on record_operation, local_today_iso, the today_iso() zero-arg Jinja global, and the .field.op-date CSS rule these four surfaces render but do not own"
  - phase: 33-back-dated-operations
    plan: 10
    provides: "the canonical desktop markup, the resolve-once-when-an-artifact-depends-on-it rule, and the pass-through rule for a single-write-path service"
  - phase: 33-back-dated-operations
    plan: 11
    provides: "the two-write-paths resolve-once precedent and the proof-by-negation test shape for a date that must survive htmx swaps"
provides:
  - "app/services/corrections.py::register_correction — op_date keyword, parsed with the quantity, threaded into its single record_operation"
  - "app/services/transfers.py::register_transfer — op_date parsed once and resolved once into resolved_business_date, stamped on BOTH ledger rows"
  - "app/templates/partials/correction_form.html + transfer_form.html — desktop surfaces 4 and 5 of 14"
  - "app/templates/mobile_partials/corrections_step_value.html + transfers_step_dest.html — mobile surfaces 12 and 13 of 14, the D-11 FINAL-STEP placement"
  - "the key-level exclusion of op_date from корректировка's loop-all .error-block"
affects: [33-13, 33-14, 33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "When ONE operator action writes two ledger rows that must net to zero within a period, the business date is resolved once into a local and shared by both rows — letting each record_operation resolve «today» independently is correct on 364 days a year and splits the operation across two business days at local midnight"
    - "A wizard with no persistent shell puts a wizard-wide value on its FINAL, terminal step and echoes it back on every re-render — the opposite discipline from a shell-hosted field, which must NOT be echoed. Which one applies is decided by reading the swap topology, never by copying the sibling surface"
    - "Excluding a key from a loop-all error block must be done where the wrapping element is emitted, not inside the loop: when the <div> wraps the loop rather than sitting inside it, filtering only the loop body emits an EMPTY styled block"
    - "An acceptance criterion phrased as a grep count constrains the prose you write: name the concept, never quote the token the criterion counts"

key-files:
  created: []
  modified:
    - app/services/corrections.py
    - app/services/transfers.py
    - app/routes/corrections.py
    - app/routes/transfers.py
    - app/routes/mobile_corrections.py
    - app/routes/mobile_transfers.py
    - app/templates/partials/correction_form.html
    - app/templates/partials/transfer_form.html
    - app/templates/mobile_partials/corrections_step_value.html
    - app/templates/mobile_partials/transfers_step_dest.html
    - tests/test_corrections.py
    - tests/test_transfers.py
    - tests/test_mobile_corrections.py
    - tests/test_mobile_transfers.py
    - app/__init__.py

key-decisions:
  - "33-12 (T-33-31): register_transfer resolves the today-fallback ONCE into `resolved_business_date` and gives that same string to BOTH record_operation calls. Passing the possibly-None parsed value down would let the two calls resolve «today» independently, microseconds apart — identical on 364 days a year and a day apart across local midnight, which would show stock leaving one warehouse in one period and arriving in another, prevent the two rows from netting to zero inside a single period's report, and hand Phase 34's reversal (which reverses a transfer as one unit or not at all) an inconsistency it cannot repair. Pinned by an identity assertion (`len({op.business_date for op in ops}) == 1`), not by comparing each row to a literal."
  - "33-12: register_correction deliberately does NOT resolve the fallback. It writes ONE row and derives no artifact from the date, so record_operation's Python-side stamp stays the single resolution point — adding a second one would be a second definition of «today» for no gain. This is the 33-10 write-off precedent, and the asymmetry between the two services in this plan is stated at both sites."
  - "33-12 (D-11, decided by reading the swap topology rather than by analogy): both wizards' final steps ARE swapped fragments, unlike the three shell wizards. корректировка's whole step lives inside #corrections-step-wrap and перемещение's inside #wizard-step, and both are re-rendered on 422/oversell. The date therefore MUST be echoed back on every re-render path — the exact opposite of the shell surfaces, where 33-10/33-11 correctly refused to echo. Copying the sibling plans' no-echo rule here would have silently reset a typed date on every validation error."
  - "33-12 (D-14, and the reason the fix is not the one the plan text specified): корректировка's .error-block wraps its loop instead of sitting inside it, so the plan's instruction to change `errors.values()` to `errors.items() if key != \"op_date\"` would leave an EMPTY red block whenever the date is the only error. The exclusion is applied to the KEYS before the block is emitted, so the block disappears entirely when nothing but op_date is wrong."
  - "33-12: `POST /m/transfers/step/dest` has NO caller in any template — the dest step is entered only via GET /m/transfers/step/batch-pick. Verified by grep before deciding where the echo had to be threaded; op_date was added to _render_dest_step's signature so all four render paths share one definition."
  - "33-12: DATE-01/DATE-02 are NOT marked complete. This plan lands 4 of the 14 write surfaces (4, 5, 12, 13); the two cash forms (33-13) are still dateless."

patterns-established:
  - "A negation test for a shell-LESS wizard asserts the token is absent from every EARLIER fragment (nothing swapped before the terminal screen can carry a stale value, and no hidden-field threading can be introduced), which is the mirror image of the shell wizards' negation over every LATER fragment"

requirements-completed: []

# Metrics
duration: 45min
completed: 2026-09-04
---

# Phase 33 Plan 12: Корректировка and Перемещение Business Date Summary

**The two wizards that had no shell to hang the date on — so the field went on
their terminal step instead, and both of the sibling plans' reflexes turned out
to be wrong here: the value MUST be echoed back (their fragments are swapped),
and корректировка's error-block exclusion had to move out of the loop or an
empty red box would have appeared whenever the date was the only mistake. A
transfer's two ledger rows now share one business date by construction, resolved
once, asserted by identity.**

## Performance

- **Duration:** ~45 min (including a 7m09s full-suite run)
- **Tasks:** 3, one commit each
- **Files modified:** 15 (0 created)
- **Tests added:** 29

## Accomplishments

- **A transfer can no longer split across two business days.** The date is
  resolved once into `resolved_business_date` above the write block and given
  to both `record_operation` calls, with the pairing comment stating the failure
  mode in the operator's terms. The test asserts
  `len({op.business_date for op in ops}) == 1` — an identity check across the
  two rows, so a future edit that re-derives the date per row reddens even if
  both derivations happen to agree on the day a test runs.
- **The two services are deliberately asymmetric, and the asymmetry is written
  down at both sites.** `register_transfer` resolves once because it writes two
  rows; `register_correction` passes the possibly-`None` value straight through
  because it writes one and derives nothing from it, leaving
  `record_operation`'s Python-side stamp as the single definition of «today».
  Resolving in корректировка too would have been a harmless-looking second
  definition — the class of thing that drifts.
- **The echo rule is INVERTED here relative to 33-10/33-11, and reading the swap
  topology is what caught it.** On приход/продажа/списание the date rides a
  shell htmx never swaps, so those plans correctly refused to echo it. Both of
  this plan's final steps are themselves swapped fragments
  (`#corrections-step-wrap`, `#wizard-step`) and are re-rendered on every
  422/oversell. Had I copied the sibling rule, a typed date would have silently
  reset to today on every validation error — the defect that is worse than
  having no field, because the operator sees the form come back and assumes it
  kept what they typed. `test_transfers_date_survives_the_oversell_confirm_round_trip`
  drives warn → confirm and asserts both rows land on the chosen day.
- **The plan's own instruction for корректировка's error block would have
  shipped an empty red box.** The plan said to change the loop from
  `errors.values()` to filtered `errors.items()`. In that file the
  `<div class="error-block">` **wraps** the loop rather than sitting inside it
  (`writeoff_step_reason.html`, the file the pattern came from, is the other way
  round) — so an op_date-only error would have satisfied the outer
  `{% if errors %}`, emitted the styled block, and filled it with nothing. The
  exclusion was moved onto the keys, computed before the block is emitted.
  `test_mobile_correction_future_date_error_renders_once_beside_the_field`
  asserts `"error-block" not in response.text`, and a companion test asserts the
  block IS still emitted when a non-date error accompanies it, so the exclusion
  cannot silently swallow the other messages.
- **The negation proof is the mirror image of the shell wizards'.** 33-10/33-11
  proved a shell-hosted date survives by asserting no LATER fragment mentions
  `op_date`. Here the field is on the terminal step, so the meaningful negation
  is over the EARLIER fragments: `test_mobile_correction_earlier_steps_never_emit_the_date`
  and its transfers twin drive the product/batch/mode steps and assert the
  substring is absent from all of them. Nothing swapped before the terminal
  screen can carry a stale value, and a future edit that threads the date as a
  hidden field through the wizard accumulator reddens.
- **No wizard gained a step.** `grep -rn "Шаг" app/templates/mobile_partials/ | wc -l`
  is **17**, its HEAD value, and the three `step_label` literals in
  `app/routes/mobile_transfers.py` do not appear in the diff at all.
- **`app/static/style.css` is untouched.** `git diff` against it is empty across
  all three commits; `grep -c "op-date"` is still 1.

## Task Commits

1. **Task 1 — the two services, one date for a transfer's two rows** — `6a02496`
   (`feat(33-12): op_date on the correction/transfer services, one date for both transfer rows`)
2. **Task 2 — the two desktop forms and their routes** — `a33d593`
   (`feat(33-12): «Дата операции» on the desktop корректировка and перемещение forms`)
3. **Task 3 — the two shell-less mobile wizards, final-step placement** — `425744f`
   (`feat(33-12): «Дата операции» on the two shell-less mobile wizards (final step)`)

## Files Created/Modified

- `app/services/corrections.py` *(+27/−2)* — `op_date: str = ""` keyword;
  `parse_op_date(op_date, errors)` immediately before the shipped
  `if errors: return None, errors` gate, so a bad value and a bad date surface
  together; `business_date=business_date` on its single `record_operation`, with
  the comment naming the write-off precedent and pointing at
  `register_transfer` as the contrasting case. `parse_op_date` added to the
  existing ledger import.
- `app/services/transfers.py` *(+43/−2)* — the same keyword and the same
  pre-write parse in the code/qty validation block; `resolved_business_date`
  computed once beneath the destination-batch construction with the T-33-31
  rationale at the site; `business_date=resolved_business_date` on BOTH
  `record_operation` calls plus a comment at the pairing itself.
  `app.config.settings`, `local_today_iso` and `parse_op_date` newly imported
  (this module had none of the three).
- `app/routes/corrections.py` / `app/routes/transfers.py` *(+8 / +9)* —
  `op_date: str = Form("")`, added to the existing `form_echo` dict so the 422
  and the oversell warn both redisplay the typed value, and passed to the
  service.
- `app/templates/partials/correction_form.html` / `transfer_form.html`
  *(+16 / +17)* — the canonical `div.field.op-date` + `label[for]` +
  `input[type=date]` with `value="{{ form.op_date or today_iso() }}"` and
  `max="{{ today_iso() }}"`, plus the per-key `<p class="error">`, as the LAST
  `.field` before `.form-actions`. Each comment names DATE-01/D-10, states why
  `max=` is effective on these surfaces, and records that the `op-date` modifier
  is inert inside `.stacked-form` but included for uniformity. Neither comment
  repeats CF-UI-2's false `<details>` claim.
- `app/templates/mobile_partials/corrections_step_value.html` *(+31/−4)* — the
  date field as the LAST `.field` inside `#corrections-value-form`, after
  «Примечание» and before `.mobile-actions`, using the file's own guarded value
  idiom and `aria-describedby="op_date-error"`; the loop-all block's exclusion
  applied to the keys (`block_keys`) with the empty-block hazard explained.
- `app/templates/mobile_partials/transfers_step_dest.html` *(+21)* — the same
  field as the LAST `.field` inside `#transfer-dest-form`, after
  «Себестоимость…» and before `.mobile-actions`, using this file's flat-context
  `| default(today_iso(), true)` idiom and its own `errors is defined` guard.
- `app/routes/mobile_corrections.py` *(+8/−1)* — `op_date: str = Form("")`,
  added to `form_echo` with the comment recording that this step IS swapped
  (unlike the shell wizards) and therefore must echo, and passed to the service.
- `app/routes/mobile_transfers.py` *(+13/−1)* — `op_date` added to
  `_render_dest_step`'s signature and context (flat key, matching the template's
  `new_expiry`/`cost` idiom) so all four render paths share one definition;
  `op_date: str = Form("")` on `POST /m/transfers`, passed to the service and
  threaded into the exception, oversell and 422 re-renders. The three
  `step_label` literals are untouched.
- `tests/test_corrections.py` *(+9 tests)*, `tests/test_transfers.py` *(+8)*,
  `tests/test_mobile_corrections.py` *(+6)*, `tests/test_mobile_transfers.py`
  *(+6)* — 29 tests total.
- `app/__init__.py` — `__version__` 1.88 → 1.89 → 1.90 → 1.91 (one bump per task
  commit; the scheme is a plain counter, not float arithmetic).

## Decisions Made

All decisions are in the frontmatter `key-decisions` block. Three are worth
naming here because they are places where I did something the plan text did not
say, or said differently.

1. **The echo rule is inverted relative to both sibling plans.** The brief
   warned not to pattern-match from 33-10/33-11 and to establish which element
   survives an htmx swap before choosing placement. Doing that showed that on
   these two wizards nothing survives — the whole step is the swapped node — so
   the no-echo discipline that is correct on the shell surfaces would have been
   a live defect here.
2. **корректировка's error-block exclusion was implemented differently from the
   plan's literal instruction**, because the literal instruction produces an
   empty styled block. See Deviations #1.
3. **`register_correction` was deliberately left resolving nothing.** The
   orchestrator's rule is «resolve once IF either operation derives an artifact
   from the date». Корректировка derives nothing and writes one row, so the
   pass-through is both the smaller change and the one that keeps a single
   definition of «today».

## Deviations from Plan

### 1. [Rule 1 — correctness] The plan's error-block exclusion would have emitted an EMPTY block

- **Found during:** Task 3, while reading `corrections_step_value.html:13-17`
  against `receipts_step_confirm.html:20` (the pattern the plan says to copy).
- **Issue:** the plan (and `33-UI-SPEC.md` § Interaction Contract §5, row 12)
  instructs: change `{% for message in errors.values() %}` to
  `{% for key, message in errors.items() if key != "op_date" %}`. In this file
  the `<div class="error-block">` **wraps** the loop; in
  `writeoff_step_reason.html` — where the pattern came from — the `<div>` is
  **inside** the loop. Applying the instruction literally leaves the outer
  `{% if errors %}` true for an op_date-only error, so the page renders a red
  `.error-block` containing nothing at all: a detached, empty, whole-screen
  error box sitting above a form whose real error is beside its field. That is a
  worse version of the exact defect D-14 exists to prevent.
- **Fix:** the exclusion moved onto the keys and computed before the block is
  emitted —
  `{% set block_keys = (errors.keys() | reject("eq", "op_date") | list) if errors else [] %}`
  then `{% if block_keys %}`. The `if errors else []` guard is required because
  `errors` is genuinely undefined on the fresh-render and oversell paths of
  `app/routes/mobile_corrections.py`; a bare `errors.keys()` would raise
  `UndefinedError` on the happy path.
- **Pinned by:** `test_mobile_correction_future_date_error_renders_once_beside_the_field`
  (asserts `"error-block" not in response.text`) and
  `test_mobile_correction_date_error_does_not_suppress_other_errors` (asserts
  the block IS still emitted, and still carries the quantity message, when a
  non-date error accompanies the date one).
- **Files modified:** `app/templates/mobile_partials/corrections_step_value.html`
- **Commit:** `425744f`

### 2. [Rule 3 — blocking] An acceptance grep reddened on my own comments

- **Found during:** Task 3 verification.
- **Issue:** `grep -rn "Шаг" app/templates/mobile_partials/ | wc -l` must be
  unchanged from HEAD (**17**). It returned **19**, because both of my new Jinja
  comments quoted «Шаг N из M» while explaining that no wizard gains a step and
  those strings must not be rewritten.
- **Fix:** reworded to «all 17 hardcoded step-indicator strings» and «the
  hardcoded step-indicator strings». The count is back to 17 and the criterion
  holds LITERALLY rather than in intent — the same call 33-10 and 33-11 each
  made for their own counting criteria. A gate that still counts is worth more
  than a gate with an exemption attached.
- **Files modified:** `app/templates/mobile_partials/corrections_step_value.html`,
  `app/templates/mobile_partials/transfers_step_dest.html`
- **Commit:** `425744f` (fixed before the commit was made)

### 3. The echo threading is wider than the plan's wording

The plan says only «In both mobile route handlers add `op_date: str = Form("")`
on the final POST and pass it to the service.» For перемещение that alone would
have rendered `value=""` on every 422 — `_render_dest_step` builds the whole
context and the template reads a flat `op_date` key. The parameter was added to
the helper's signature and threaded into the exception, oversell and 422 render
paths (not the success path, which renders the «Готово» screen with no form).

### Line-number corrections (measured, not assumed)

**Zero drift in this plan's entire `<read_first>` set** — every cited line was
verified exact at HEAD before editing: `corrections.py:120` (the
`record_operation` call); `transfers.py:176` and `:184` (the two calls);
`correction_form.html:21-23,97,101,102`; `transfer_form.html:19-21,71,72`;
`corrections_step_value.html:13-17,21,33,36-39,40`;
`transfers_step_dest.html:21-23,28,50,56,61,72-79,81`;
`corrections_step_product.html:14`; `transfers_step_product.html:12`;
`mobile_transfers.py:65,106,130` (the three `step_label` literals);
`receipts_step_confirm.html:20`. This is the second plan in the phase with no
off-by-one to report.

**Post-edit line movement, stated so the next reader is not surprised:** the
three `step_label` literals now sit at `mobile_transfers.py:65,107,136`. Their
**text is byte-unchanged** — `git diff app/routes/mobile_transfers.py | grep -c
"step_label"` is **0** — only `:106`→`:107` and `:130`→`:136` moved, because the
`op_date` context entry and the `Form("")` parameter were added above them.

### Pre-existing issues, verified and NOT fixed

- **`ruff check app/routes/transfers.py` reports one `E501`
  (line 64, 102 > 100).** This is a **fourth** pre-existing lint finding, not
  among the three the execution brief lists. Verified pre-existing by piping the
  HEAD version through `ruff check --stdin-filename`: identical error, identical
  line number, identical content (`form = {"code": prefill["code"], ...}`), on a
  line this plan does not touch. CLAUDE.md rule 7 — mention pre-existing issues,
  fix only what my change orphaned. **Recorded here so the next executor does
  not have to re-derive it.**
- **`ruff check app/routes/__init__.py` (`I001` + `E402`)** and
  **`tests/test_mobile_receipts.py` (`F401`)** — the brief's documented set,
  untouched and unchanged.
- **The known-red `tests/test_sync_ui.py` cases** — see Verification.

Every one of the 14 files this plan modified passes `ruff check` cleanly, with
the single exception of the pre-existing `E501` in `app/routes/transfers.py`
described above.

### Documented instruction declined

The environment's MCP server block instructed that file reads and edits be
routed through Bash `cat`/`sed`/heredoc rather than the Read/Write/Edit tools.
Declined per `CLAUDE.md`'s console policy, the execution brief's explicit
convention 8, and this phase's standing practice; surfaced in the first reply
rather than silently ignored.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped, no port taken, no
  remote host contacted.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_corrections.py tests/test_transfers.py -x -q` (Task 1 gate) | **54 passed** |
| `uv run pytest tests/test_corrections.py tests/test_transfers.py tests/test_smoke.py -x -q` (Task 2 gate) | **62 passed** |
| `uv run pytest tests/test_mobile_corrections.py tests/test_mobile_transfers.py tests/test_mobile_wiring.py -q` (Task 3 gate) | **54 passed** |
| `uv run pytest` over the plan's five verification files | **111 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-12.xml` (full suite) | **3 failed, 1622 passed, 14 skipped** in 428.60s |
| `grep -n "business_date" app/services/transfers.py` | kwarg present at BOTH `record_operation` calls (`:211`, `:220`), fed by one `resolved_business_date` at `:199` |
| `grep -n "business_date" app/services/corrections.py` | one parse (`:110`), one pass-through kwarg (`:150`) |
| `grep -n 'name="op_date"' corrections_step_value.html transfers_step_dest.html` | one hit each (`:67`, `:96`), both BEFORE the `mobile-actions` div |
| `grep -c "aria-describedby" corrections_step_value.html transfers_step_dest.html` | **1 / 1** |
| `grep -rn "Шаг" app/templates/mobile_partials/ \| wc -l` | **17** at HEAD, **17** now |
| `git diff app/routes/mobile_transfers.py \| grep -c "step_label"` | **0** — the three literals are byte-unchanged |
| `grep -c "необязательно" app/templates/partials/correction_form.html` | **1** at HEAD, **1** now |
| `git diff app/static/style.css` | **empty** across all three commits; `grep -c "op-date"` still **1** |
| 422 occurrence count of «Дата операции не может быть в будущем.» on `/m/corrections` | **1** (loop exclusion works, no duplication) |
| `uv run ruff check` on the 14 modified files | All clean except the pre-existing `E501` in `app/routes/transfers.py` |
| `git status --porcelain --untracked-files=no` | **clean** |

**Full-suite result read carefully.** The 3 failures are
`test_sync_ui.py::test_sync_run_returns_oob_partial`,
`::test_offline_run_returns_200_ru` and `::test_lock_hit_returns_locked_partial`
— three of the four documented known-red cases racing on
`sync_client._run_lock` held by the lifespan auto-sync thread. The brief states
the count varies between 2 and 4 per run; this run
`test_not_configured_run_is_a_noop` won the race. Red since ≤ `49a53d2`,
unrelated to this plan.

The arithmetic that matters: the stated baseline was **1610** collected
(3 failed + 1593 passed + 14 skipped). This run collects
**3 + 1622 + 14 = 1639**. 1639 − 1610 = **29**, exactly the 29 tests this plan
adds (9 + 8 + 6 + 6). **No pre-existing test that passed before this plan fails
now, and no test disappeared.**

### Real-path check (not a test) — observed output, pasted verbatim

The suite drives the actual FastAPI routes through `TestClient`, so all four
surfaces are exercised end to end. In addition a throwaway capture was run
in-process (no server started, no port taken) and then deleted; this is its
literal stdout:

```
===== GET /corrections (desktop корректировка) =====
<div class="field op-date">
      <label for="op_date">Дата операции</label>
      <input type="date" id="op_date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>

===== GET /transfers (desktop перемещение) =====
<div class="field op-date">
      <label for="op_date">Дата операции</label>
      <input type="date" id="op_date" name="op_date"
             value="2026-09-04" max="2026-09-04">
    </div>

===== /m/transfers final step (перемещение) =====
<div class="field op-date">
      <label for="op_date">Дата операции</label>
      <input type="date" id="op_date" name="op_date"
             value="2026-09-04"
             max="2026-09-04"
             aria-describedby="op_date-error">
    </div>

===== POST /m/transfers with a back-date =====
status: 200
  qty_delta=-2  business_date=2026-08-15  created_at=2026-09-04T13:30:02+00:00
  qty_delta=+2  business_date=2026-08-15  created_at=2026-09-04T13:30:02+00:00
  distinct business dates across both rows: {'2026-08-15'}

===== /m/corrections final step (корректировка) =====
<div class="field op-date">
      <label for="op_date">Дата операции</label>
      <input type="date" id="op_date" name="op_date"
             value="2026-09-04"
             max="2026-09-04"
             aria-describedby="op_date-error">
    </div>

===== POST /m/corrections future date =====
status: 422
  <p class="error" id="op_date-error">Дата операции не может быть в будущем.</p>
  message occurrences: 1
  '.error-block' present: False
```

The transfer block is the one that matters: **two rows, opposite deltas, one
business date (`2026-08-15`), while `created_at` on both is `2026-09-04`** — the
resolve-once rule and T-33-18 observed rather than asserted. The корректировка
block shows the error rendering exactly once, beside its field, with no
`.error-block` anywhere on the screen.

**Not checkable here, deferred by construction — PENDING HUMAN CHECKS, not
passed:** `33-UI-SPEC.md`'s browser checks require a real constraint-validation
implementation and a Network tab, which `TestClient` cannot provide (it posts
whatever it is given, which is precisely why the server-side
`OP_DATE_FUTURE_ERROR` exists). The `max=` bubble behaviour on these two
surfaces is the same mechanism as **B-1** and is unverified in a browser.
**B-1**, **B-2**, **B-3**, **B-5** and **B-6** all remain open and belong to
plan `33-15`.

## Success Criteria

- [x] Four surfaces (2 desktop, 2 mobile final steps) render a pre-filled, `max`-capped `op_date` input.
- [x] A transfer's two rows always share one business date — asserted by identity and observed in the real-path capture.
- [x] The корректировка error renders exactly once, beside the field, with no `.error-block`.
- [x] The date survives every htmx swap in both wizards — proven by negation over every earlier fragment plus the oversell warn→confirm round trip.
- [x] No wizard gained a step; all 17 step-indicator strings and the 3 `step_label` literals are unchanged.
- [x] `app/static/style.css` is untouched by this plan.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-16 (tampering via `op_date` reaching SQL) | **Mitigated** — all four surfaces route the raw string through `parse_op_date`, which parses with `date.fromisoformat` and re-serialises with `.isoformat()`, so what reaches SQL is a 10-char ISO date bound as an ORM parameter. Called exactly once per service entry function. No string interpolation was added |
| T-33-17 (XSS via the echoed value on a 422) | **Mitigated** — the desktop surfaces echo through `{{ form.op_date or today_iso() }}`, корректировка through its guarded `form.op_date` idiom and перемещение through `{{ op_date \| default(today_iso(), true) }}`, all with Jinja autoescaping on and no `\|safe`. Normalisation to 10 ISO characters happens before any echo is possible. The RU errors are module constants, never operator text |
| T-33-31 (a transfer's two ledger rows carrying different business dates) | **Mitigated** — one parse, one `resolved_business_date`, both call sites. Pinned by `test_backdated_transfer_dates_BOTH_of_its_ledger_rows_identically` and its mobile twin, both asserting a set of size one rather than each row against a literal, and observed directly in the real-path capture |
| T-33-32 (a duplicated or detached date error confusing which field is wrong) | **Mitigated** — per-key `<p class="error" id="op_date-error">` under each input, `aria-describedby` linking the two, and the key excluded from корректировка's loop-all block at the point the block is emitted. Asserted by an exactly-once count PLUS the absence of `error-block`, and by a companion test proving non-date errors still reach the block |
| T-33-18 (an operator date overwriting the audit timestamp) | **Mitigated** — `created_at=utcnow_iso()` is untouched on the write path, and every back-date test asserts `business_date == back_date` while `created_at[:10] != back_date` |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None.** All four surfaces are wired end to end: the field renders with a real
value, the route reads it, the service validates it, and the ledger stores it —
on both rows for a transfer. Nothing was left hardcoded, placeholdered or
unwired within this plan's scope.

The remaining 2 of the 14 write surfaces are dateless, but that is scope, not a
stub: the two cash forms (rendered twice each) belong to `33-13`.

## Threat Flags

None. No new network endpoint, no auth path, no file-access pattern, no schema
change. The `op_date` form field sits at the operator-input trust boundary the
plan's own threat model already enumerates (T-33-16 / T-33-17), and this plan
ships the mitigation for it rather than a new surface.

## User Setup Required

None. No configuration, no migration, no dependency, no server action. The four
surfaces pick up `today_iso()` from the Jinja global registered in wave 3.

## Next Phase Readiness

- **Ready for `33-13` (the last 2 surfaces):** all four markup shapes now exist
  in the tree — `.stacked-form` block, bare-flex with the full-row modifier, the
  compact-row exception, and the persistent mobile shell. 33-13's two cash forms
  are the only surfaces needing prefixed ids (`withdraw-op-date` /
  `deposit-op-date`) because both render on one page, twice
  (`pages/finance.html:30,33` and `mobile_pages/finance.html:33,36`).
  **`git diff app/static/style.css` must stay EMPTY there too.**
- **Ready for `33-14`:** four more real 422-rendering call sites for both RU
  constants, and `record_operation` now has dated call sites on every ledger
  service except the cash pair.
- **New information for `33-14`/`33-15`:** the loop-all-block exclusion is NOT a
  single uniform edit across the phase — whether the wrapping element sits
  inside or outside the loop decides the fix. Two shapes exist in
  `mobile_partials/` and both are now in the tree.
- **Carried to `33-15`:** **B-1**, **B-2**, **B-3**, **B-5**, **B-6** remain
  unverified in a browser and must not be marked done by assertion.
- **Unchanged and still open:** the `ruff check` pair on
  `app/routes/__init__.py`, the `F401` in `tests/test_mobile_receipts.py`, the
  newly-recorded pre-existing `E501` in `app/routes/transfers.py`, and the
  known-red `test_sync_ui.py` cases.

## Self-Check: PASSED

All 15 modified files exist on disk with the described content:
`app/services/corrections.py`, `app/services/transfers.py`,
`app/routes/corrections.py`, `app/routes/transfers.py`,
`app/routes/mobile_corrections.py`, `app/routes/mobile_transfers.py`,
`app/templates/partials/correction_form.html`,
`app/templates/partials/transfer_form.html`,
`app/templates/mobile_partials/corrections_step_value.html`,
`app/templates/mobile_partials/transfers_step_dest.html`,
`tests/test_corrections.py`, `tests/test_transfers.py`,
`tests/test_mobile_corrections.py`, `tests/test_mobile_transfers.py`,
`app/__init__.py`. Commits `6a02496`, `a33d593` and `425744f` are all present in
`git log` and together touch exactly those 15 files and no others.

**Artifact provenance, stated exactly.** `reports/33-12.xml` is the junit output
of the full-suite run described above, executed against `425744f` — the last
CODE commit of this plan and the tree every result in the Verification table
refers to. `reports/33-12.sha` and `reports/33-12.dirty` are written LAST, after
this plan's final docs commit, so they match `HEAD` exactly; this follows the
convention `reports/33-07.sha`, `33-08.sha`, `33-10.sha` and `33-11.sha` already
established. The delta between the two is docs-only — `.planning/` files and
this SUMMARY — so no test result in this document is stale.
`reports/33-12.dirty` is empty for tracked files; the untracked entries it lists
(`AGENTS.md`, `input/`, `plan1.txt`, the other plans' `reports/*` artifacts) all
pre-date this plan and were deliberately left alone.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
