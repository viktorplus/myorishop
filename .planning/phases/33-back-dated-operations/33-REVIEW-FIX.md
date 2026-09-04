---
phase: 33-back-dated-operations
fixed_at: 2026-09-04T21:20:00Z
review_path: .planning/phases/33-back-dated-operations/33-REVIEW.md
iteration: 1
fix_scope: critical_warning
findings_in_scope: 9
fixed: 7
partial: 1
skipped: 1
status: partial
suite: 1728 passed, 16 skipped, 0 failed
version: 1.101 -> 1.110
---

# Phase 33: Code Review Fix Report

**Fixed at:** 2026-09-04
**Source review:** `.planning/phases/33-back-dated-operations/33-REVIEW.md`
**Iteration:** 1
**Base commit:** `ebca32b` → **head after fixes:** `12c1611`

**Summary:**

- Findings in scope: 9 (CR-01, WR-01..WR-08 — IN-01..IN-06 out of scope, untouched)
- Fixed: 7
- Partially fixed: 1 (WR-05 — documented, behaviour deliberately unchanged)
- Skipped: 1 (WR-01 — needs an operator decision, see below)

**Verification actually run** (not inferred):

- `python -m pytest -q` on the full suite, in the isolated worktree, after all
  fixes: **1728 passed, 16 skipped, 0 failed** (511 s).
- The 4 deterministic `tests/test_sync_ui.py` failures named in the task brief
  **did not reproduce** in this run. `pytest-randomly` is not installed, so the
  order was the plain collection order. They are not fixed by anything here —
  nothing in this change touches `sync_client._run_lock` or the lifespan
  auto-sync thread — so treat their absence as an ordering/environment
  artifact, not as a repair.
- `ruff check` on the 14 touched files: **1 error before, 1 error after** — the
  same pre-existing `UP028` in `app/services/merge.py::serialize_exchange`.
  No new lint findings. (Project-wide `ruff check` reports 60 errors and
  `ruff format --check` wants to reformat 96 files at `ebca32b`; neither is a
  gate this repo passes today, and neither was touched.)
- Every fix was re-read after editing and syntax-checked with `ast.parse`.

---

## Fixed Issues

### CR-01: `business_date` inserted verbatim from the sync wire, rendered by a raising filter

**Commits:** `a471ca6`, plus `1d3bd4d` (test-fixture correction, see note)
**Files:** `app/services/merge.py`, `app/core.py`, `tests/test_business_date.py`

Applied both layers the review asked for, not one:

1. `parse_exchange` now rejects any date-only column that is not a **canonical**
   ISO `yyyy-mm-dd` string, in the loop beside the existing money check and
   before any DB touch. Implemented as `_DATE_FIELDS` ∩ `KIND_TO_FIELDS[kind]`
   so it auto-tracks the schema, with `_is_iso_date` doing a `fromisoformat` →
   `isoformat()` round trip. `NULL` stays legal — it is DATE-08's «written by a
   pre-0027 client» sentinel, and rejecting it would cut un-upgraded clients off
   the sync.
2. `format_ru_date` renders an unrecognised value as-is instead of raising,
   under the same «display code must never blow up on stored data» rule
   `currency_symbol` already states three functions above it.

**Deviation from the suggested patch (deliberate):** the review's snippet
accepts anything `date.fromisoformat` parses. On Python 3.11+ that includes the
ISO *basic* format `"20260904"`, which would be stored in a shape no read-side
comparison expects — every period predicate compares `business_date` as a
string. The round-trip check refuses it.

**Note on `1d3bd4d`:** my first version of the display test asserted
`format_ru_date("20260904") == "20260904"`. It failed on execution, correctly —
`date.fromisoformat` understands that value, so the filter renders it. Corrected
to `"04.09.2026"` and the asymmetry is now asserted explicitly: **strict in,
lenient out**. Recorded here rather than amended away because the executed run
is the evidence.

**Tests added:** 26. `parse_exchange` refusal for 9 bad values × both ledger
kinds (`"не дата"`, `"2026/09/04"`, `"04.09.2026"`, `"20260904"`,
`"2026-13-45"`, a full timestamp, `12345`, `True`, a 4 KB string); acceptance of
ISO and `None`; `format_ru_date` returning rather than raising.

### WR-02: `push_schema_ok` raised `TypeError` (raw 500) on a non-string `schema_version`

**Commit:** `3d73b07`
**Files:** `app/services/merge.py`, `app/services/sync.py`, `tests/test_sync_schema_gate.py`

`parse_exchange` coerces a non-string `schema_version` to `""` at the parse
boundary; `push_schema_ok` now takes `object` and fails **closed** on anything
that is not a pair of strings, so no direct caller can reintroduce the
`TypeError`. `""` is the existing D-03 both-sides escape hatch, so an untyped
header is treated exactly like one that omits the field — that is why the
end-to-end test asserts **200, not 409**. The behaviour is deliberate and is
stated in the test docstring; the property under test is that a hand-built
header cannot take the endpoint down.

**Tests added:** 12 (predicate totality over 6 untyped values on both sides,
parse-boundary coercion over 5, one route-level end-to-end).

### WR-03: the 409 schema-gate detail reflected client-controlled bytes

**Commit:** `df7f337`
**Files:** `app/routes/sync.py`, `tests/test_sync_schema_gate.py`

The client half of the detail is now echoed only when it matches
`_REVISION_ID_RE` (`\d{4}` — the same fixed-width invariant `push_schema_ok`'s
lexicographic comparison rests on), and is replaced by `UNKNOWN_SCHEMA_LABEL`
(`"?"`) otherwise. The in-code comment that claimed «never submitted bytes» now
describes what the code actually does. A well-formed ahead revision (`"0028"`)
is still named in full, so the message an operator actually hits did not get
worse — the pre-existing `test_ahead_client_push_returns_409` still passes
unmodified.

**Test added:** 1 — a 4 KB junk version yields 409 with the junk absent from the
response and zero rows in the ledger.

### WR-04: `_is_backdated` read a naive `created_at` as server-local time

**Commit:** `9fc0b19`
**Files:** `app/services/operations.py`, `tests/test_history.py`

Applied migration 0027's `_local_business_date` rule character for character —
`if moment.tzinfo is None: moment = moment.replace(tzinfo=UTC)`. The two rules
have to agree, because the backfill's entire correctness argument is
`business_date == local_day(created_at)` for every historical row.

**Scope addition beyond the suggested patch:** 0027 also falls back to
`created_at[:10]` on an unparseable timestamp, and `_is_backdated` did not —
`datetime.fromisoformat` would raise and 500 `/history` for *every* row. Since
`created_at` is merged verbatim too (`_LEDGER_REQUIRED` only checks
`is not None`) and the ledger is append-only, that is the same unrepairable-row
shape as CR-01. Added, so the two functions now genuinely agree on every input.

**Tests added:** 2. Note the first is only *discriminating* on a machine whose OS
zone is not UTC (on a UTC host the old and new code agree); it asserts the
correct answer either way.

### WR-06: `register_receipt`'s quantity guard was missing `isascii()`

**Commit:** `781b8b7`
**Files:** `app/services/receipts.py`, `tests/test_receipts.py`

Now `qty_text.isascii() and qty_text.isdigit()`, matching `writeoffs.py:71`,
`transfers.py:84`, `sales.py:148`, `returns.py:144`.

**Test added:** 1 — `qty_raw="²"` returns `QTY_ERROR` with nothing written.

### WR-07: `register_sale` could raise `StopIteration` on an unresolvable warehouse

**Commit:** `e918fa7`
**Files:** `app/services/sales.py`, `tests/test_sales.py`

Empty `basket_currencies` now returns the existing `SAVE_ROLLBACK` basket error
instead of falling into `next(iter(set()))`.

**Test added:** 1 — and it really reproduces the shape rather than mocking it:
the batch is orphaned onto a non-existent warehouse id on a **separate SQLite
connection with `PRAGMA foreign_keys=OFF`**, because the ORM path cannot produce
that row. Confirmed passing.

### WR-08: the downgrade trigger DDL was asserted against nothing

**Commit:** `99522b1`
**File:** `tests/test_migrations.py`

`test_downgrade_upgrade_roundtrip_preserves_triggers` now snapshots the
**downgraded** state before re-upgrading and asserts it in both directions: the
four 0027 columns (`business_date`, `reverses_op_id`, `reverses_movement_id`)
are gone from the guards, and the pre-0027 columns are still named — including
`NEW.currency`, the exact column 0026 had to add after 0024 left it silently
mutable. The re-upgraded state is then compared as a whole name → DDL map
against `APPEND_ONLY_TRIGGERS` (shared `_declared_triggers()` helper, also used
by the sibling test). Confirmed passing.

---

## Partially Fixed

### WR-05: «Только в день операции» silently omits normal rows in the UTC-straddle window

**Commit:** `12c1611` — **documentation only, no behaviour change**
**File:** `app/services/operations.py`

The finding's core complaint («the other filter has the mirror-image defect and
it is not stated») is closed: `_is_backdated`'s docstring now has an «ACCEPTED
CONSEQUENCE — BOTH DIRECTIONS» block spelling out that «Только задним числом»
**over**-includes while «Только в день операции» **under**-includes, that the
pair is an approximation rather than a partition, and that at Europe/Moscow the
affected set is every row entered between 00:00 and 03:00 local. The
`history_view` branch carries a pointer to it.

**What was NOT done, and why:** both of the review's remedies are operator
decisions, not local edits.

- *Relabel the filter* — the option copy **«Только в день операции»** is a row in
  the locked table at `33-UI-SPEC.md` § Copywriting Contract, which also carries
  an explicit «Copy that must NOT be written» clause. Rewording it is a spec
  change.
- *Widen the predicate* — the review's own snippet notes it «changes the
  `backdated`/`same_day` complementarity», i.e. a row could satisfy both
  filters. It would also redden
  `test_backdated_filter_and_marker_diverge_only_on_utc_straddle`, which pins
  today's behaviour deliberately.

The review says «pick the approach with the operator». I did not pick one.

---

## Skipped Issues

### WR-01: `parse_op_date` bounds the future but not the past

**File:** `app/services/ledger.py:62-73`
**Reason:** cannot be fixed without a design decision — **the value and the copy
are both operator policy.**

Two blockers, either one sufficient:

1. **The floor value is a business rule.** The review itself writes
   `_OP_DATE_FLOOR_DAYS = 3650  # ~10 years; pick with the operator`. Any number
   I pick silently defines what the operator is allowed to enter, and the ledger
   is append-only, so a too-tight floor is a hard block with no workaround until
   Phase 34 ships сторно.
2. **The fix requires new operator-facing copy that no spec contains.** The
   suggested `OP_DATE_TOO_OLD_ERROR` would be a **third** RU error message for
   this field. `app/services/ledger.py:25-30` states the two existing messages
   are «taken verbatim from 33-UI-SPEC.md's Copywriting Contract», which lists
   exactly two error states for the date field («malformed» and «future») and
   adds a «Copy that must NOT be written» clause. Inventing a third string is a
   spec change, not a code fix.

The template half (`min=` on the 14 `<input type="date">` surfaces, via a
`min_op_date_iso()` Jinja global mirroring the existing `today_iso()`) is
mechanical and low-risk, but it is meaningless without the server-side floor —
`min=` is a browser hint, and this field is already re-validated server-side
precisely because form values are untrusted. Shipping the hint alone would look
like the hole was closed. Left entirely.

**The underlying risk is real and remains open:** a mistyped year such as
`0226-09-04` is accepted, written, invisible to every period report, and
uncorrectable until Phase 34. **Recommended next step:** ask the operator for
the oldest date they must be able to enter, then land the floor + the third
error string + `min=` as one small change with the spec updated alongside.

---

## Out of scope (untouched, as instructed)

IN-01 (`local_day_bounds_utc` docstring note), IN-02 (unreachable
`POST /m/transfers/step/dest`), IN-03 (DB-level `CHECK` on `business_date` —
note it is the defence-in-depth backstop *behind* CR-01's parse gate, and would
need its own revision), IN-04 (invalid `op_date` echoed into
`<input type="date">`), IN-05 (`getattr` dispatch in the Alembic test helper),
IN-06 (four near-identical period resolvers).

---

## Process notes

- Ran in an isolated `git worktree` on a temp branch, fast-forwarded into `main`
  on completion; the recovery sentinel was written after `worktree add` and
  removed after `worktree remove`. No orphan worktree or branch remains.
- `git add` was used with explicit paths only — the 51 untracked files
  (`reports/`, `input/`, `AGENTS.md`, `plan1.txt`) were never staged.
- `__version__` bumped once per fix commit: **1.101 → 1.110**.
- The project's mandatory `robust-console-commands` skill could not be invoked —
  no Skill/SlashCommand tool is exposed in this agent context. Console use was
  kept to single-purpose commands. Flagging rather than silently bypassing.
- One incident worth remembering: a `sed -i` on `app/__init__.py` rewrote the
  file's line endings (LF vs the repo's CRLF working copy). The committed diff
  was verified to be the single version line and nothing else, and all later
  edits used the Edit tool. **Do not use `sed -i` on this repo.**

---

_Fixed: 2026-09-04_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
