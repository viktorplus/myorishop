---
phase: 33-back-dated-operations
plan: 06
subsystem: core-primitives
tags: [timezone, sqlalchemy, jinja, validation, css, coalesce, portable-orm]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 05
    provides: "operations.business_date / cash_movements.business_date — the nullable, default-less String(10) columns these four primitives read and write, plus migration 0027's tz-correct backfill"
provides:
  - "app/core.py::business_date_bounds — date-only ISO bounds with a CLOSED [start_day, end_day] contract"
  - "app/core.py::local_today_iso — the ONE definition of «today», shared by the Jinja global and the server-side future check"
  - "app/services/reports.py::business_date_expr — func.coalesce(model.business_date, func.substr(model.created_at, 1, 10))"
  - "app/routes/__init__.py — today_iso() registered as a zero-arg callable Jinja global"
  - "app/services/ledger.py::parse_op_date + OP_DATE_FORMAT_ERROR + OP_DATE_FUTURE_ERROR"
  - "business_date keyword on record_operation and record_cash_movement, stamped in Python"
  - "app/static/style.css::.field.op-date — the single CSS declaration this phase adds"
affects: [33-07, 33-08, 33-09, 33-10, 33-11, 33-12, 33-13, 33-14, 33-15]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A date-only column gets its OWN bounds helper beside the timestamp one, never a flag on it: comparing a String(10) date against UTC timestamp bounds is a lexicographic accident that holds only at positive UTC offsets and drops rows at UTC+0 and every negative offset"
    - "A read expression over a nullable column with a meaningful NULL sentinel is ONE shared COALESCE helper parameterised by the model class, mirroring operation_currency_clause"
    - "«Today» in a template is a ZERO-ARG CALLABLE Jinja global, never a registered value (stale for the whole process) and never a per-context kwarg (one missed route silently renders value=\"\")"
    - "A default that must NOT apply to the bulk sync path is stamped in Python inside the single write path, never as a column default= — merge's session.execute(insert(model), rows) bypasses the function and must land the genuine NULL"

key-files:
  created:
    - tests/test_business_date.py
  modified:
    - app/core.py
    - app/services/reports.py
    - app/routes/__init__.py
    - app/services/ledger.py
    - app/services/finance.py
    - app/static/style.css
    - app/__init__.py

key-decisions:
  - "33-06 (LOCKED constraint 6): business_date_bounds is a SIBLING of local_day_bounds_utc, not an overload. The latter is byte-unchanged apart from one added docstring line; its half-open contract and its 36 created_at-fixture call sites are untouched, and a dedicated test pins that."
  - "33-06 (the bounds contract, stated in the docstring FIRST): CLOSED [start_day, end_day]. Every predicate the later plans switch reads >= start AND <= end. One predicate keeping < is a silent one-day off-by-one across nine reports."
  - "33-06 (Pitfall 14, sharpened and now pinned by a test): the old bounds accept a date-only value at Europe/Moscow purely as a lexicographic accident and REJECT it at America/New_York and at plain UTC. The test asserts the exact baseline [True, False, False], so a future refactor that 'fixes' the accident reddens instead of silently changing behaviour."
  - "33-06 (DATE-08): the fallback on both write paths is stamped in PYTHON (`business_date or local_today_iso(...)`), never as a column default. merge._ledger_row builds its dict with data.get(column), so a pre-0027 client's record arrives as None and must land NULL. A column default would substitute a date and destroy the sentinel. Pinned by test_merge_inserted_row_keeps_null_business_date."
  - "33-06 (D-15): today_iso is a zero-arg CALLABLE global delegating to local_today_iso — so the pre-filled value= and parse_op_date's future check can never disagree, and no route can forget to pass it."
  - "33-06 (W-6): the .field.op-date rule lands HERE, in wave 3, not in plan 33-10. It must exist before any wave-4 template renders class=\"field op-date\". Plans 33-10 … 33-13 must keep `git diff app/static/style.css` EMPTY."
  - "33-06: requirements DATE-01..04/08 are NOT marked complete — this plan ships primitives with zero call sites. No form renders the field, no report is switched, no reader calls business_date_expr yet. Marking them here would make REQUIREMENTS.md's traceability table claim work that lands in waves 4-6."
  - "33-06: the four inlined local-today sites are NOT refactored (additive-change rule). They are recorded as named debt inside local_today_iso's own docstring, with the warning that converging them must not shift parse_op_date's future check."

patterns-established:
  - "A helper whose whole reason to exist is a rejected alternative states the executed counter-example IN the docstring, with real numbers, not a reference to a research file the next reader will not open"

requirements-completed: []

# Metrics
duration: 35min
completed: 2026-09-04
---

# Phase 33 Plan 06: Shared Business-Date Primitives Summary

**Four primitives every wave-4-to-6 plan depends on — a CLOSED date-only bounds helper beside an untouched half-open sibling, one COALESCE read expression that keeps a pre-0027 client's row visible instead of vanishing it, one un-forgettable definition of «сегодня», and the `business_date` keyword on both sanctioned write paths with its fallback deliberately in Python so the bulk sync path still lands a genuine NULL.**

## Performance

- **Duration:** ~35 min (including a 6m33s full-suite run)
- **Tasks:** 3, one commit each
- **Files modified:** 8 (1 created, 7 modified)

## Accomplishments

- **`business_date_bounds` ships with its rejected alternative demonstrated in its
  own docstring, and the demonstration is a live test.** The docstring carries the
  three executed lines — Europe/Moscow accepts `'2026-09-01'` by lexicographic
  accident, America/New_York and plain UTC both DROP the row — and
  `test_business_date_bounds_ignores_timezone` asserts that exact
  `[True, False, False]` baseline against `local_day_bounds_utc`. Pitfall 14 is
  therefore not a note anyone has to trust: a refactor that changes it reddens.
  UTC is in the list on purpose (a UTC-only CI runner would otherwise be the
  thing that catches this, in production).
- **The CLOSED contract is stated before it is used.** The docstring opens with
  "the range is closed / inclusive on both ends", says callers filter `>= start`
  AND `<= end` — never `<` — and names the consequence of getting one predicate
  wrong. `test_business_date_bounds_is_closed_inclusive` pins the last day of the
  range being included.
- **`local_day_bounds_utc` really is untouched.** Its body is unchanged; the only
  edit is one added docstring paragraph naming it the `created_at`-only helper
  and pointing at the sibling. `git diff --stat tests/test_core.py` across all
  three commits is empty, and `test_local_day_bounds_utc_still_half_open` is a
  standing guard that the old contract did not move under the phase.
- **`business_date_expr` is parameterised by the model class**, so `Operation` and
  `CashMovement` share one expression across the five service modules that will
  call it, and it renders as portable `substr(...)` on both dialects (verified by
  compiling both). Its docstring names the two-format asymmetry explicitly — the
  READ fallback is a UTC prefix and is knowingly NOT tz-correct, while migration
  0027's backfill MUST be — so nobody "unifies" the two rules later.
- **`today_iso()` is a callable, and the reason is written down.** Registered
  beside `nav_section` / `batch_identity_label`, delegating to `local_today_iso`.
  That single delegation is what makes the pre-filled `value=` and
  `parse_op_date`'s future check structurally incapable of disagreeing — the
  23:30-local trap D-15 warns about.
- **The Python-side stamp is the load-bearing choice, and it is proven end to
  end.** `test_merge_inserted_row_keeps_null_business_date` pushes a wire record
  with the `business_date` key ABSENT through `apply_merge` and asserts the row
  lands `business_date IS NULL`, while
  `test_record_operation_stamps_local_today_by_default` asserts an interactively
  written row gets today's LOCAL day — and specifically that it equals the local
  day of its own `created_at`, not that timestamp's UTC prefix.
- **Two distinct Russian errors, byte-checked against the contract.** Both
  constants were compared to `33-UI-SPEC.md` § Copywriting Contract by literal
  equality in a runtime assert, not by eye.
- **The single CSS declaration landed in wave 3, ahead of every surface plan.**
  `grep -c "op-date" app/static/style.css` is 1; the diff is the comment plus
  `flex-basis: 100%` and nothing else — no colour, border, background, font-size
  or margin.

## Task Commits

1. **Task 1 — `business_date_bounds` + `local_today_iso`** — `faf33af`
   (`feat(33-06): business_date_bounds + local_today_iso in app/core.py`)
2. **Task 2 — `business_date_expr`, the `today_iso` global, the CSS rule** — `6411377`
   (`feat(33-06): business_date_expr, the today_iso Jinja global, one CSS rule`)
3. **Task 3 — `parse_op_date`, the two RU constants, the `business_date` kwarg** — `fc27ec3`
   (`feat(33-06): parse_op_date + two RU errors + business_date on both write paths`)

## Files Created/Modified

- `app/core.py` *(+67)* — `business_date_bounds(start_day, end_day)` returning
  `(start_day.isoformat(), end_day.isoformat())` with the CLOSED contract and the
  three executed Pitfall-14 lines in its docstring; `local_today_iso(tz_name)`
  with the four inlined local-today sites named as debt. One added docstring
  paragraph on `local_day_bounds_utc`; its body untouched. No new import (the
  module already had `datetime` and `ZoneInfo`).
- `app/services/reports.py` *(+39)* — `business_date_expr(model)` beside
  `operation_currency_clause`, copying its docstring discipline (name the
  nullable column, the fallback and why it is that value, the caller
  discipline, ending «never re-implemented inline»). A comment records the
  home-placement rationale: this module imports only `app.config`, `app.core`
  and `app.models`, so the five consuming services import it without a cycle,
  and `app/core.py` is not the home because it imports no SQLAlchemy.
- `app/routes/__init__.py` *(+11)* — `local_today_iso` added to the existing
  `app.core` import; `templates.env.globals["today_iso"]` registered as a
  zero-arg lambda in the same block, with the comment explaining why a callable
  and not a value or a per-context kwarg.
- `app/services/ledger.py` *(+70/−2)* — the two RU constants with the
  UI-SPEC-citing comment in `active_catalog.py:18-21`'s style; `parse_op_date`
  beneath them, mirroring `parse_optional_expiry` and adding exactly one branch
  (the future check); `record_operation` gains keyword-only
  `business_date: str | None = None` and stamps
  `business_date or local_today_iso(settings.display_tz)` beside an untouched
  `created_at=utcnow_iso()`. `date` and `local_today_iso` added to the imports.
- `app/services/finance.py` *(+19/−2)* — the identical keyword and the identical
  stamp on `record_cash_movement`, importing only `local_today_iso`.
- `app/static/style.css` *(+12)* — `.field.op-date { flex-basis: 100%; }` plus
  its DATE-01/D-10 comment, appended at the tail where the file's later-phase
  blocks (Plan 05, Phase 21) already live.
- `tests/test_business_date.py` *(created, 310 lines)* — 17 tests: 6 on the
  bounds/today helpers, VA-11, 6 on `parse_op_date`, 3 on the two write paths,
  1 on the merge path.
- `app/__init__.py` — `__version__` 1.73 → 1.74 → 1.75 → 1.76 (one bump per
  task commit).

## Decisions Made

All decisions are in the frontmatter `key-decisions` block. Two are worth naming
here because they are places where this plan deliberately did LESS than a
literal reading would permit:

1. **The four inlined local-today sites were not converged.** `local_today_iso`
   is the first shared helper for an expression that already appears four times
   (`app/services/receipts.py:209`, `app/routes/mobile_reports.py:21`,
   `app/services/customers.py:443,465`). CLAUDE.md's reuse audit requires
   naming them; the additive-change rule forbids refactoring them inside this
   task. They are recorded as debt in the helper's own docstring — where the
   next author will actually be standing — together with the warning that
   converging them must not shift `parse_op_date`'s future check, since a shift
   at the day boundary silently turns valid dates into refusals. Plan `33-15`
   Task 4 mirrors the line into `33-ROLLOUT.md` § Backlog.
2. **No requirement was marked complete.** This plan ships primitives with zero
   call sites: no form renders the field, no report is switched, nothing calls
   `business_date_expr` yet. Following 33-05's precedent, marking DATE-01..04/08
   here would make the traceability table claim work that lands in waves 4-6.

## Deviations from Plan

**None affecting design, scope or assertions.** Three small factual corrections
were applied to written references, and two acceptance criteria are satisfied in
intent rather than by their literal grep.

### Line-number corrections (measured, not assumed)

- **`app/services/receipts.py:208` is actually `:209`.** The plan text and
  `33-UI-SPEC.md` § Interaction Contract §1 both cite `:208` for the first
  inlined local-today site; `grep -n` puts
  `local_today = datetime.now(ZoneInfo(settings.display_tz)).date()` on line
  **209**. The docstring records the measured number. The other three
  (`mobile_reports.py:21`, `customers.py:443`, `customers.py:465`) matched
  exactly.

### Acceptance criteria read literally vs. read for intent

- **`grep -n "strftime\|date_trunc\|::date" app/services/reports.py` returns
  nothing new** — it returns **two hits, both inside the new docstring**
  (`:73`, `:74`), because the same task's `<action>` REQUIRES the docstring to
  say *«Never reach for `strftime`, `date_trunc`, `::date` or `SUBSTRING(...)`»*.
  The criterion as literally written is therefore unsatisfiable by the code the
  action mandates. Its intent — no executable line uses a dialect-specific date
  function — holds: the only executable construct added is
  `func.coalesce(..., func.substr(...))`. Identical in shape to 33-05's
  `batch_alter_table` note.
- **`grep -n "today_iso" app/routes/__init__.py` shows the global registered as
  a callable in the block at `:193-231`** — it is registered at `:242`, because
  the block itself moved down by 11 lines when this plan appended to it (and by
  1 more from the added import). It IS the same registration block, immediately
  after `batch_identity_label`, which is what the criterion means.

### Pre-existing issue, verified and NOT fixed

- **`uv run ruff check app/routes/__init__.py` reports 2 errors (`I001`
  unsorted import block, `E402` module-level import not at top).** Verified
  PRE-EXISTING: piping the HEAD version of the file through
  `ruff check --stdin-filename` returns the **same two errors**. `E402` is the
  deliberate `from app import __version__` placed after `templates` to avoid a
  circular import; `I001` is a pre-existing classification quirk of this repo's
  local `alembic/` directory. Fixing them would reorganise a shared file's whole
  import block mid-phase and collide with the plans still to run — out of scope,
  same call 33-05 made for `ruff format`. All six other touched files pass
  `ruff check` cleanly.

## Issues Encountered

- **Nothing blocking.** No architectural question, no fix-attempt loop, no
  package install, no server or container started or stopped.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_business_date.py tests/test_core.py -x -q` (Task 1 gate) | **38 passed** |
| `uv run pytest tests/test_business_date.py tests/test_reports.py tests/test_smoke.py -x -q` (Task 2 gate) | **53 passed** |
| `uv run pytest tests/test_business_date.py tests/test_ledger.py tests/test_finance.py tests/test_merge.py -x -q` (Task 3 gate) | **156 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-06.xml` (full suite) | **4 failed, 1520 passed, 14 skipped** in 393.13s |
| `git diff --stat HEAD~3 HEAD -- tests/test_core.py` | **empty** — the file was not touched |
| `git diff --stat app/services/receipts.py app/routes/mobile_reports.py app/services/customers.py` | **empty** — the four inlined sites are unchanged |
| `python -c "from app.services.reports import business_date_expr"` + compile on both models | `coalesce(operations.business_date, substr(operations.created_at, :substr_1, :substr_2))` and the `cash_movements` twin — portable `substr`, no dialect function |
| `templates.env.globals["today_iso"]()` called live | `2026-09-04` — the global renders, zero-arg |
| `grep -c "op-date" app/static/style.css` | **1** |
| `grep -n "date_only\|column=" app/core.py` (AP-4) | **(none)** |
| `grep -n "created_at=utcnow_iso()" app/services/ledger.py app/services/finance.py` | both present and untouched (`ledger.py:183`, `finance.py:106`) |
| `grep -n "default=" app/models.py \| grep business_date` | **(none)** — the stamp is in Python, not on the column |
| `grep -c "business_date" app/services/sync.py app/services/sync_client.py app/routes/sync.py` | **0 / 0 / 0** (VA-11 green) |
| Byte-equality of both RU constants vs `33-UI-SPEC.md` § Copywriting Contract | **MATCH** (runtime assert, not visual) |
| `uv run ruff check` on the 6 newly-clean touched files | All checks passed |
| `git status --porcelain` (tracked files) | **clean** |

**Full-suite result read carefully.** The 4 failures are **exactly** the four
documented known-red `tests/test_sync_ui.py` cases
(`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`,
`test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`),
each failing on `sync_client._run_lock` being held by the lifespan auto-sync
thread — red since ≤ `49a53d2`, count varies 2–4 per run.

The arithmetic that matters: baseline was **1507** non-skipped (33-05 recorded
1504 + 3); this run is **1520 + 4 = 1524**; this plan adds **17** tests, and
1507 + 17 = 1524 exactly. **No pre-existing test that passed before this plan
fails now, and no test disappeared.**

### Real-path check (not a test)

The suite proves the primitives compute; it does not prove the Jinja global is
reachable from the real template environment. Driven in-process against the
actual `app.routes.templates` object (no server started, no port taken):
`templates.env.globals["today_iso"]()` returns `2026-09-04`, today's local day
at `Europe/Moscow`. `tests/test_smoke.py` (53 passed with `test_reports.py`)
independently confirms every page still renders with the new global registered.

**Not checkable here, deferred by construction:** the field itself does not
render on any surface yet — no template references `class="field op-date"`
until wave 4 — so `33-UI-SPEC.md`'s browser checks B-1…B-7 have nothing to
exercise. They belong to plans `33-10` … `33-14`.

## Success Criteria

- [x] `business_date_bounds` exists with a CLOSED contract stated in its docstring, beside an unmodified `local_day_bounds_utc`.
- [x] `business_date_expr` exists as ONE shared helper with a portable COALESCE fallback.
- [x] `today_iso()` is a zero-arg Jinja global; no per-context threading is required by later plans.
- [x] `.field.op-date` exists in `app/static/style.css` before any template references it, and it is the ONLY CSS this phase adds.
- [x] `parse_op_date` refuses a future date in Russian and a malformed date with a DIFFERENT Russian message, both under `errors["op_date"]`, writing nothing.
- [x] A locally written row always has a business date; a merge-inserted row can still be NULL.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-16 (SQL injection via `op_date`) | **Mitigated** — `parse_op_date` parses with `date.fromisoformat` and re-serialises with `.isoformat()`, so the returned value is a 10-char ISO date by construction; it reaches SQL only as a bound ORM parameter. Nothing in this plan string-interpolates a date. `test_parse_op_date_rejects_malformed` covers four non-ISO shapes including a valid-looking `2026-02-30` |
| T-33-17 (XSS via `op_date` echoed on a 422 re-render) | **Mitigated** — normalisation to 10 ISO characters happens before any echo is possible; Jinja autoescaping is on and no `\|safe` is introduced. The echo surfaces themselves are wave 4 |
| T-33-18 (an operator date overwriting the audit timestamp) | **Mitigated** — `created_at=utcnow_iso()` is byte-unchanged on BOTH write paths (grep-verified), and `test_record_operation_accepts_explicit_business_date` asserts `created_at` is still «now» while `business_date` is 45 days back |
| T-33-19 (the sync queue following the business date) | **Mitigated** — `test_business_date_absent_from_sync_layer` reads all three sync modules as text and reports `path:line` on any hit; all three are 0 |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

**None that block this plan's goal, but the primitives ship with ZERO call
sites, by design.** Nothing renders the date field, no report filters on
`business_date_expr`, no route calls `parse_op_date`, and every
`record_operation` / `record_cash_movement` call site still uses the default.
That is the plan's stated scope — the 12 + 3 call sites are threaded in plans
`33-10` … `33-13`, the report predicates in `33-07` … `33-09`, and the
`.field.op-date` class is first rendered in wave 4. The three product-admin /
import paths at `app/services/catalog.py:137,279,288` stay on the default
forever (no operator date form).

Nothing was left hardcoded, placeholdered or unwired *within* this plan's own
scope.

## Threat Flags

None. No new network endpoint, no auth path, no file-access pattern, no schema
change. `parse_op_date` sits at the operator-input trust boundary the plan's own
threat model already enumerates (T-33-16 / T-33-17), and it is the mitigation,
not a new surface.

## User Setup Required

None. No configuration, no migration, no dependency, no server action.

## Next Phase Readiness

- **Ready for 33-07 … 33-09 (the report predicates):** `business_date_bounds`
  and `business_date_expr` both exist, and the CLOSED contract is written in one
  place. The mechanical rule for the nine switched predicates is
  `created_at >= start_iso` / `created_at < end_iso` →
  `business_date_expr(M) >= start_day` / `business_date_expr(M) <= end_day` —
  **`<` becomes `<=`**. Exactly one predicate keeping `<` is Pitfall D.
- **Ready for 33-10 … 33-13 (the 14 write surfaces):** `today_iso()` is
  callable from any template with no route change, `.field.op-date` already
  exists, and both write paths accept the keyword. **`git diff
  app/static/style.css` must be EMPTY in all four of those plans** — the rule
  is already here.
- **Ready for 33-14:** `parse_op_date`'s two distinct constants are importable
  for the marker/filter divergence test.
- **Unchanged and still open:** the `ruff check` pair on
  `app/routes/__init__.py` (pre-existing, deliberately not fixed), the
  PostgreSQL CI parity run (plan `33-15`), and the production rollout
  (`33-ROLLOUT.md`, human-owned).
- **Carried forward for `33-15` Task 4:** the four unconverged inlined
  local-today sites, to be recorded in `33-ROLLOUT.md` § Backlog raised by this
  phase.

## Self-Check: PASSED

`app/core.py`, `app/services/reports.py`, `app/routes/__init__.py`,
`app/services/ledger.py`, `app/services/finance.py`, `app/static/style.css`,
`app/__init__.py` and `tests/test_business_date.py` all exist on disk with the
described content; commits `faf33af`, `6411377` and `fc27ec3` are all present in
`git log` and together touch exactly those eight files and no other.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
