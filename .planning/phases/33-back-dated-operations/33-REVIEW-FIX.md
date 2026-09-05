---
phase: 33-back-dated-operations
fixed_at: 2026-09-05T00:00:00Z
review_path: .planning/phases/33-back-dated-operations/33-REVIEW.md
iteration: 2
fix_scope: all
findings_in_scope: 18
fixed: 13
partial: 1
skipped: 4
status: partial
suite: 1784 passed, 16 skipped, 0 failed
version: 1.110 -> 1.124
---

# Phase 33: Code Review Fix Report

**Fixed at:** 2026-09-05
**Source review:** `.planning/phases/33-back-dated-operations/33-REVIEW.md` (iteration 2)
**Iteration:** 2
**Base commit:** `db12d31` → **head after fixes:** `43c2925`

---

## Iteration 1 recap (do not lose this)

Iteration 1 ran with `fix_scope: critical_warning` — 9 findings in scope, **7 fixed,
1 partial, 1 skipped**, `1.101 → 1.110`, head `12c1611`, report committed as `208bf45`.

| Prior finding | Outcome in iteration 1 |
|---|---|
| CR-01 wire `business_date` + `format_ru_date` | fixed (`a471ca6`, `1d3bd4d`) |
| WR-02 `push_schema_ok` TypeError | fixed (`3d73b07`) — see WR-02 below for what the fix broke |
| WR-03 409 echo | fixed (`df7f337`) |
| WR-04 naive `created_at` in `_is_backdated` | fixed (`9fc0b19`) |
| WR-06 `isascii()` in `register_receipt` | fixed (`781b8b7`) |
| WR-07 `StopIteration` in `register_sale` | fixed (`e918fa7`) |
| WR-08 downgrade trigger DDL asserted | fixed (`99522b1`) |
| WR-05 dated-filter trade-off | **partial** (`12c1611`) — documentation only, behaviour deliberately unchanged; re-raised this iteration as WR-09 |
| WR-01 `parse_op_date` past bound | **skipped** — needs an operator decision (floor value + a third RU string) |

IN-01..IN-06 were declared out of scope in iteration 1. **They are in scope now**
(`fix_scope: all`), and the iteration-2 review added IN-07 and IN-08.

---

## Summary — iteration 2

- Findings in scope: **18** (CR-01, WR-01..WR-09, IN-01..IN-08)
- Fixed: **13**
- Partially fixed: **1** (IN-08 — documented in code, the decision itself is Phase 34's)
- Skipped: **4** (WR-01, WR-09, IN-03, IN-06)

Iteration 2 is the first pass where the Info tier was actually worked, so 8 of the
13 fixes are IN-* items.

### Verification actually run (not inferred)

- **Full suite**, in the isolated worktree, after every fix:
  **1784 passed, 16 skipped, 0 failed** (575 s / 9m35s).
  Iteration 1's baseline was 1728 passed; the delta is exactly the **56 tests added
  here** (CR-01 28, WR-03 9, WR-04 1, WR-05 2, WR-06 1, IN-02 1, IN-04 13, IN-07 1).
- The **4 known-flaky `tests/test_sync_ui.py` failures** named in the brief
  **did not reproduce**, exactly as in iteration 1. Nothing here touches
  `sync_client._run_lock` or the lifespan auto-sync thread, so treat their absence
  as an ordering/environment artefact, not as a repair.
- **`ruff check` on all 21 touched `.py` files: 4 errors before, 4 errors after —
  the same four, byte for byte.** Baseline measured by running ruff against the
  clean `db12d31` checkout in the main repo, not inferred:
  - `app/routes/__init__.py:3 I001` (import block unsorted — pre-existing)
  - `app/routes/__init__.py:192 E402` (module-level import not at top — pre-existing)
  - `app/services/merge.py UP028` (`yield` over `for` — pre-existing)
  - `tests/test_export.py:333 E501` (102-char docstring — pre-existing)
  No new lint findings. Project-wide `ruff check` / `ruff format --check` are not
  gates this repo passes today and were not touched.
- Every fix was re-read after editing, syntax-checked, and its own test module run
  before the commit.
- **IN-08's claim was verified by execution**, not asserted: compiled
  `CreateTable` for both ledger tables against the SQLite dialect and confirmed
  both reversal ForeignKeys appear in the `create_all` DDL while `0027:343,346`
  add plain `sa.Column`s.

### Pending human checks (NOT verified here)

1. **WR-08 (`.filter-bar` `flex-wrap`)** — there is no browser in this
   environment. The `needs verification` carried from `33-CONTEXT.md`
   § Deferred Ideas is still open: **open `/history` at 1024 px and confirm
   there is no horizontal scrollbar and no clipped fourth `<select>`.** The CSS
   change is one purely-additive line, but nobody has looked at the result.
2. **CR-01's `created_at` intake gate against a REAL client push.** The gate was
   proven by unit tests over 8 bad and 4 good shapes, and every shipped client
   stamps `created_at` via `utcnow_iso()` (full ISO-8601 with a `+00:00` offset),
   which the gate accepts. That was established by READING the write path, not by
   pushing from a real `0027` client. Worth one live push before the client
   release tag — which is the same gate the phase's UAT is already blocked on.
3. **WR-05's behaviour change** (the warehouse lookup moved inside `if debit:`)
   is a semantic change, not just a guard. It is covered by two new tests, but a
   human should confirm the intent: a zero-price return no longer resolves a
   warehouse currency at all.

---

## Fixed Issues

### CR-01: `| local_dt` raised on a wire-supplied `created_at` and read a naive one in the OS zone

**Commit:** `8f6ee9e`
**Files:** `app/core.py`, `app/services/merge.py`, `tests/test_business_date.py`

Applied both of iteration 1's rules to the sibling column, as the review asked.

*Layer 1 — the wire.* `parse_exchange` now checks the SHAPE of a ledger
`created_at`, not just its presence. `_LEDGER_REQUIRED` only asserted
`is not None`, `_ledger_row` copies the value verbatim into the bulk INSERT, and
the append-only triggers then make the row unrepairable by the application.
`_is_iso_timestamp` requires three properties, each load-bearing:

- it parses (`_is_backdated` and `iso_to_local` both call `fromisoformat`);
- it carries a time part — a bare `"2026-09-04"` in a timestamp column renders a
  fabricated 00:00 and sorts before every real timestamp of that day, and the
  sync cursor orders by this column;
- `value[:10]` is a **canonical** ISO date, because every read-side fallback for
  a NULL `business_date` is the literal slice `created_at[:10]`. Without this,
  `"20260904T100000+0000"` (which `fromisoformat` accepts on 3.11+) slices to
  `"20260904"` and poisons every period comparison — the same value
  `_is_iso_date` already refuses for `business_date`.

**A naive timestamp is deliberately ACCEPTED.** All three readers treat one as
UTC, so refusing it would turn a whole push into a 400 over a value the readers
handle correctly.

*Layer 2 — display.* `iso_to_local` no longer raises and reads a naive value as
UTC instead of in the machine's OS zone. It renders the same column, on the same
rows, on the same pages as `format_ru_date`: `/history`, `/m/history`, the home
page, the customer purchase tab and both CSV exports, none of which has a `try`.

**Tests added:** 28.

### WR-02: the schema gate's two halves cancel — prose said fail-closed, composition failed open

**Commit:** `a892a73` — **documentation only, no behaviour change**
**Files:** `app/services/sync.py`, `tests/test_sync_schema_gate.py`

`push_schema_ok`'s docstring claimed a non-string version «is refused (False),
which is the fail-closed direction». That was false for every path that exists:
`app/routes/sync.py` is the sole production caller and can only pass
`batch.schema_version`, which `parse_exchange` has already coerced to `""` — so
an untyped header is ACCEPTED via the D-03 hatch. Corrected the prose, not the
code: the fail-closed direction means raising inside `parse_exchange`, which
turns a malformed header into `400 MALFORMED_BATCH_ERROR` — a behaviour change
nobody asked for.

**Deviation from the suggested patch, stated:** the review proposed deleting the
`isinstance` branch as dead code. **Kept**, and relabelled as an explicit crash
backstop for a future DIRECT caller. Without it the predicate is no longer total
(`5 <= "0027"` raises past the falsy hatch) — the exact 500 iteration 1's fix
existed to close. Two lines of dead-but-honest defence beat re-opening it in
Phase 34.

Both schema-gate tests now say which layer they pin: the predicate test states it
describes a direct caller only, and the end-to-end test states the composed
answer is 200-and-merged plus what to change if the fail-closed direction is ever
taken.

### WR-03: the date gate covered `business_date` but not `Batch.expiry`

**Commit:** `c2df0b6`
**Files:** `app/services/merge.py`, `tests/test_business_date.py`

`_DATE_FIELDS`' own comment said «add the next date-only column here when one
appears». That column shipped in Phase 9. Added `expiry`; `_date_fields()`
already intersects with `KIND_TO_FIELDS[kind]`, so nothing else changed.

Empty string is deliberately **not** special-cased, and this was checked rather
than assumed: `parse_optional_expiry`, `batches.update_batch` and
`transfers.register_transfer` all store `None` for «no expiry», and `0008`'s
legacy backfill inserts a literal NULL — so no existing row can carry `""` and
be refused by the new gate.

**Tests added:** 9.

### WR-04: CSV column 1 was a stored-bytes pass-through outside `_csv_safe`

**Commit:** `9e86506`
**Files:** `app/services/export.py`, `tests/test_export.py`

**Scope beyond the review's two lines, and why:** this iteration's CR-01 fix gave
`iso_to_local` the same never-raises/pass-through contract `format_ru_date` has,
so the «Внесено» columns and `customers.csv`'s «Создан» acquired the identical
property in the same commit. Wrapping only the two named cells would have left
the same hole one column to the right — introduced by this iteration, not by
Phase 33. **Five cells wrapped.** A well-formed date or timestamp never starts
with `=`, `+`, `-` or `@`, so no existing byte of output changes.

**Left alone deliberately, reported instead** (CLAUDE.md additive-change rule):
`op.created_by` (sales.csv column 9) is also unwrapped and IS wire-supplied free
text — `merge._LEDGER_REQUIRED` carries it verbatim. Pre-existing and unrelated
to the date change. The `format_cents` money columns stay unwrapped on purpose: a
negative amount legitimately starts with `-` and wrapping those WOULD change
output.

**Test added:** 1 — a stored `business_date` of `=HYPERLINK(...)` comes back from
the real `/export/sales.csv` route apostrophe-prefixed.

### WR-05: `register_return` dereferenced `batch`/`warehouse` with no None guard

**Commit:** `9517ed1`
**Files:** `app/services/returns.py`, `tests/test_returns.py`

`AttributeError` is in neither `except` clause, so it escaped into the routes'
blanket `except Exception` — the operator got «Не удалось сохранить» by accident
rather than by design, and the log got a stack trace for a data shape the code
knows about.

The lookup also **moved inside the `if debit:` guard**, which closes the review's
second observation: it was resolved unconditionally, so a return of a zero-price
sale would have failed over a currency it never reads.

**Tests added:** 2, using the `PRAGMA foreign_keys=OFF` orphan idiom from
`test_sales.py`'s WR-07 test because the ORM path cannot produce the shape.

### WR-06: `register_transfer` dereferenced `source_warehouse` with no None guard

**Commit:** `16254c6`
**Files:** `app/services/transfers.py`, `tests/test_transfers.py`

Same shape, same precondition. `dest_warehouse` is safe (its id is checked
against `active_ids`); `source.warehouse_id` never was. Reuses the field and
message the ownership check twelve lines above already uses —
`{"batch": BATCH_REQUIRED_ERROR}` — rather than inventing a third RU string for a
state the operator fixes the same way.

**Test added:** 1.

### WR-07: the revision-id tripwire could not see the filenames it exists to catch

**Commit:** `1571fd0`
**File:** `tests/test_migrations.py`

`[0-9]*.py` excluded exactly the Alembic-default `<hexrev>_<slug>.py` shape the
test's docstring names as its failure case, and the `>= 26` floor still passed
because the numbered files are all there. Now globs `*.py` and the floor is the
real count, 27.

### WR-08: `.filter-bar` had no `flex-wrap` and this phase added a fourth `<select>`

**Commit:** `bd6d0b1`
**File:** `app/static/style.css`

One additive line, matching `.toolbar` at the top of the same file. **Not
verified in a browser — see Pending human checks above.**

### IN-01: `local_day_bounds_utc` has no `app/` caller and the docstring did not say so

**Commit:** `dd6b9fd`
**File:** `app/core.py`

Re-grepped rather than copied. The live callers are `tests/test_core.py`,
`test_export.py`, `test_dashboard.py`, `test_attribution.py`,
`test_business_date.py`. **`33-CONTEXT.md` also named `test_finance_reports.py`
and `test_reports.py`; they no longer reference it** — the note says so
explicitly so the list is not re-copied stale, the same trap `local_today_iso`'s
docstring already warns about.

### IN-02: `POST /m/transfers/step/dest` would have dropped a typed date

**Commit:** `9c891ef`
**Files:** `app/routes/mobile_transfers.py`, `tests/test_mobile_transfers.py`

Took the *thread it* option, not the *delete it* one: deleting a live route with
three tests is a refactor decision, and CLAUDE.md puts that behind an explicit
scope from the user. It was the ONE `_render_dest_step` caller that neither took
nor threaded `op_date`, so wiring it up later would have silently reset a
back-date to today — on the exact screen D-11 puts the transfer wizard's date
field on. The docstring now states the route is unreachable and why it is kept.

**Test added:** 1 (a tripwire, not a live-path regression test).

### IN-04: an invalid `op_date` was echoed into `<input type="date">`, blanking it

**Commit:** `30d19e9`
**Files:** `app/core.py`, `app/routes/__init__.py`, 11 templates,
`tests/test_core.py`, `tests/test_finance.py`

**The review's suggested patch is wrong, and this is the one deviation worth
reading.** It proposed `value="{{ today_iso() if errors.op_date else ... }}"`.
Both date errors write `errors["op_date"]`, so keying on it would ALSO stop
echoing a legitimately typed FUTURE date — which the review's own note says must
be unaffected, and which route tests pin
(`test_web_withdraw_future_date_returns_422_and_echoes_the_typed_value` and
siblings). Keyed on the **value's shape** instead: canonical ISO in → echoed
verbatim; anything an `<input type="date">` cannot render → today.

Implemented as `core.date_input_value` + one Jinja global `op_date_value`,
registered beside the existing `today_iso` callable, rather than the same
conditional pasted into 11 templates — the rule then cannot drift between
surfaces. The round trip through `date.isoformat` mirrors `merge._is_iso_date`
for the same reason: `"20260904"` parses but still renders as an empty input.

11 templates converted. The three mobile shell wizards keep
`value="{{ today_iso() }}"` — that shell is never re-rendered, so it has nothing
to echo.

**Tests added:** 13.

### IN-05: unbounded `getattr` dispatch in the Alembic test helper

**Commit:** `54ffbc6`
**File:** `tests/conftest.py`

Two-entry allow-list. **One detail the review's snippet did not have:** the
lookup is resolved BEFORE `settings.database_url` and `DATABASE_URL` are
retargeted. Their restore lives in the `finally` of the call below, so raising
inside that block — as a bare dict-index would — would leave the app's real
engine pointed at the test database for every later test. That is exactly the
leak the helper's own docstring says the `finally` exists to prevent.

### IN-07: `\d` matches non-ASCII digits, so the 409 detail could echo them

**Commit:** `254305c`
**Files:** `app/routes/sync.py`, `tests/test_migrations.py`,
`tests/test_sync_schema_gate.py`

`[0-9]{4}` in both places. In the test the consequence is sharper than in the
route: a revision id written in Arabic-Indic digits would have PASSED the
fixed-width tripwire and then sorted nowhere near its ASCII neighbours under
`push_schema_ok`'s lexicographic `<=`.

**Test added:** 1 — a push carrying `"١٢٣٤"` gets a 409 whose detail contains
`"?"` and none of those four characters.

---

## Partially Fixed

### IN-08: `reverses_*_id` carry an ORM `ForeignKey` migration 0027 does not create

**Commit:** `43c2925` — **documentation only**
**File:** `app/models.py`

The divergence was **verified by execution**, not assumed (see Verification
above): `create_all` emits both reversal FKs, `0027:343,346` add plain columns,
and `app/db.py:128` sets `PRAGMA foreign_keys=ON`. So a Phase-34 test pushing a
reversal whose target has not arrived will raise `IntegrityError` in the suite
while succeeding in production.

**What was NOT done:** the review says «pick one before building a test around
the dangling-link behaviour». Neither option is a review fix — dropping the ORM
ForeignKey loses merge insert-ordering, and adding the real FK needs a follow-up
revision against a live production database. The divergence is in the false-RED
direction (the safer one) and follows the pre-existing
`sale_id`/`batch_id`/`author_id` precedent, so nothing is changed. It is
documented where a Phase-34 author will actually hit it — in `models.py` beside
the two columns — instead of only in a review artefact.

---

## Skipped Issues

### WR-01: `parse_op_date` bounds the future but not the past

**File:** `app/services/ledger.py:62-73`
**Reason:** unchanged from iteration 1 — **the floor value and the copy are both
operator policy**, and the review agrees («still blocked on the same two
decisions»).

1. The floor is a business rule. Any number picked here silently defines what the
   operator may enter, and the ledger is append-only, so a too-tight floor is a
   hard block with no workaround until Phase 34 ships сторно.
2. It needs a **third** RU error string for this field.
   `33-UI-SPEC.md` § Copywriting Contract lists exactly two error states for the
   date field and carries an explicit «Copy that must NOT be written» clause.

The `min=` template half alone was deliberately not shipped: it is a browser hint
on a field that is re-validated server-side precisely because form values are
untrusted, so shipping it would make the hole look closed.

**Still open and still real:** `"0226-09-04" > "2026-09-05"` is `False`, so a
mistyped year is accepted, written, invisible to every period report, and
uncorrectable until Phase 34. **Next step:** ask the operator for the oldest
enterable date, then land floor + string + `min=` as one change with the spec
updated alongside.

### WR-09: «Только в день операции» under-includes in the UTC-straddle window

**File:** `app/services/operations.py`
**Reason:** unchanged from iteration 1's WR-05 — **an operator/spec decision, and
the review explicitly says «do not close it by editing the docstring again».**

Both remedies are spec changes, not local edits:

- *Relabel* — «Только в день операции» is a row in the locked
  `33-UI-SPEC.md` § Copywriting Contract table.
- *Widen the predicate* — breaks `backdated`/`same_day` complementarity and
  reddens
  `test_backdated_filter_and_marker_diverge_only_on_utc_straddle`, which pins
  today's behaviour on purpose.

The documentation half was already closed in iteration 1 (`12c1611`). **Next
step:** ask the operator which answer they want, in the same pass as WR-01 —
both are copy + spec changes to the same UI-SPEC.

### IN-03: no DB-level shape constraint on `business_date` / `created_at`

**Files:** `app/models.py`, `alembic/versions/0027…py`
**Reason:** **needs a NEW migration against a live production database, and it
cannot be written safely from here.** Four separate blockers, any one sufficient:

1. `0027` is LIVE on s1 and on client installs and must not be edited — so this
   needs revision `0028`, which drags in the phase's LOCKED five-artifact
   lockstep and its server→client rollout ordering.
2. A `CHECK` constraint on SQLite cannot be added without
   `op.batch_alter_table`, and **Pitfall 3 says a batch operation other than
   `add_column` recreates the table and DROPS ALL FOUR append-only triggers** —
   the exact failure `0024` caused and `0026` had to repair. The ledger would
   come back unguarded and silent.
3. The `GLOB` pattern in the review's snippet is SQLite-specific. Production is
   PostgreSQL, where the same check is a `~` regex — so it needs the dual-dialect
   branch, and CLAUDE.md forbids dialect-specific SQL without one.
4. On PostgreSQL, adding a `CHECK` **fails outright if any existing row violates
   it** — and IN-03's own text says a pre-0027 row may already carry a poisoned
   `business_date` from the `created_at[:10]` backfill. That data cannot be
   inspected from this environment, and V4 («run against a copy of the s1 dump»)
   was never carried out for this.

**What is closed anyway:** the intake is now gated on **all three** date/timestamp
columns — `business_date` (iteration 1), `expiry` (WR-03) and `created_at`
(CR-01) — and both display filters are total. So nothing new can be poisoned via
the wire, and a poisoned row degrades one cell rather than 500-ing a page.

**What is NOT closed:** a row poisoned BEFORE 0027 ran cannot be repaired by
intake validation, and CR-01 notes it would make every future push containing it
fail with `400 MALFORMED_BATCH_ERROR`. **Next step:** one revision `0028` that
(a) repairs poisoned `business_date`/`created_at` rows found on the s1 dump and
(b) adds the dual-dialect CHECK — planned deliberately, with V4 executed against
a real dump first, and `add_column`-only discipline for the trigger rebuild.

### IN-06: four near-identical period resolvers

**Files:** `app/routes/reports.py`, `history.py`, `mobile_history.py`,
`finance.py` + `mobile_finance.py`, `app/services/dashboard.py`
**Reason:** **refactor-mode work, and CLAUDE.md requires an explicit scope from
the user before it starts.** The review itself frames it as scheduling («worth
scheduling a shared `period.py` helper before the next phase touches period
logic»), not as a defect — the duplication predates this phase, each copy is
documented as intentional, and consolidating five callers of Monday-start-week /
calendar-month arithmetic into one helper is a behaviour-preserving refactor that
needs its own blast-radius map and its own commit series.

**Next step:** schedule `app/services/period.py` before the next phase that
touches period logic — Phase 34 does touch reports, so this is the natural
moment to ask for the scope.

---

## Process notes

- Ran in an isolated `git worktree` on a temp branch
  (`gsd-reviewfix/33-…`), fast-forwarded into `main` on completion. The recovery
  sentinel was written after `worktree add` and removed after `worktree remove`;
  no orphan worktree or branch remains.
- `git add` used explicit paths only — the 51 untracked files (`reports/`,
  `input/`, `AGENTS.md`, `plan1.txt`) were never staged.
- `__version__` bumped once per fix commit: **1.110 → 1.124** — 14 commits
  (`8f6ee9e` CR-01, `a892a73` WR-02, `c2df0b6` WR-03, `9e86506` WR-04,
  `9517ed1` WR-05, `16254c6` WR-06, `1571fd0` WR-07, `bd6d0b1` WR-08,
  `dd6b9fd` IN-01, `9c891ef` IN-02, `30d19e9` IN-04, `54ffbc6` IN-05,
  `254305c` IN-07, `43c2925` IN-08).
- **`sed -i` was not used on any repo file** (iteration 1 recorded that it rewrote
  line endings). All edits went through the Edit/Write tools; commit messages went
  through `git commit -F`.
- **One incident, recorded rather than hidden:** while measuring the ruff
  baseline I ran `git stash -u && git checkout db12d31 -- .` inside the worktree,
  which reverted the working tree mid-run and invalidated a full-suite run that
  was executing at the time. Recovered with `git reset --hard HEAD` (all 13 fixes
  were already committed, so nothing was lost), dropped only my own stash entry —
  the three pre-existing stashes from other agent worktrees were left untouched —
  and re-ran the full suite cleanly. The baseline was then measured the correct
  way: by running ruff against the untouched `db12d31` checkout in the main repo.
  The 1784-passed figure quoted above is from the clean re-run.
- The project's mandatory `robust-console-commands` skill could not be invoked —
  no Skill/SlashCommand tool is exposed in this agent context. Console use was
  kept to single-purpose commands. Flagging rather than silently bypassing.

---

_Fixed: 2026-09-05_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
