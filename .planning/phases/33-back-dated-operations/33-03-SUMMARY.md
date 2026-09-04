---
phase: 33-back-dated-operations
plan: 03
subsystem: sync
tags: [alembic, sqlite, triggers, pytest, fixtures, sqlalchemy, ndjson, schema-skew]

# Dependency graph
requires:
  - phase: 28-sync-server
    provides: "the append-only trigger chain (0018) these tests execute for the first time"
  - phase: 33-back-dated-operations
    plan: 01
    provides: "push_schema_ok, whose lexicographic comparison test_revision_ids_are_fixed_width is the declared tripwire for"
provides:
  - "tests/conftest.py::alembic_engine — the suite's ONLY database built by `alembic upgrade head`"
  - "tests/conftest.py::run_alembic — factory fixture exposing the in-process Alembic driver"
  - "tests/test_migrations.py — VA-5 (app/db.py <-> migrations trigger diff), VA-6 (downgrade round trip), VA-7 (fixed-width revision ids)"
  - "tests/test_merge.py::test_missing_column_lands_default — VA-3, the SQLAlchemy default-substitution pin"
  - "tests/test_merge.py::test_unknown_field_is_dropped — VA-4, the drop-not-reject pin"
affects: [33-04-migration-0027, 33-07, sync, alembic]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A SECOND schema build path (Alembic) added BESIDE create_all, never replacing it — the 14 fixtures depending on `engine` keep their build path byte-identical"
    - "In-process Alembic driving: retarget the `settings` singleton (not just the Config object) because alembic/env.py:22 overwrites sqlalchemy.url, and restore every global in a `finally` since pytest is one process"
    - "Expose a conftest helper by factory FIXTURE rather than cross-module import, so the consuming test file imports nothing from the fixture module"
    - "Whole-map trigger comparison (name -> normalised DDL), not a name set: a trigger guarding the wrong column list is the failure mode that matters"

key-files:
  created:
    - tests/test_migrations.py
  modified:
    - tests/conftest.py
    - tests/test_merge.py
    - app/__init__.py

key-decisions:
  - "33-03 (D-04): VA-7 asserts the SHAPE of every revision/down_revision literal with an anchored multiline regex rather than parsing the chain. push_schema_ok compares ids lexicographically, so `9`, `0027a` or `abc123` would silently make the 409 gate meaningless — the regex is the only thing in the repo enforcing that precondition."
  - "33-03: `alembic_engine` and `run_alembic` live in tests/conftest.py, NOT inside tests/test_migrations.py as 33-VALIDATION.md suggested. Plan 33-07's VA-9 (byte-identity across the migration) needs the same fixture, and a cross-test-file import would require making tests/ an importable package. The V3 constraint the validation doc actually protects — do not re-point tests/conftest.py::engine — is honoured exactly (git diff is +92/-0)."
  - "33-03: `run_alembic` is a factory FIXTURE wrapping a module-level `_run_alembic`, because the plan's own acceptance criterion `grep -c conftest tests/test_migrations.py == 0` is unsatisfiable with any import spelling. Same shape as the existing `login` / `past_sale` / `mobile_client_factory` factory fixtures. See Deviations."
  - "33-03: fixing alembic/versions/0024_cash_movement_currency.py is explicitly OUT OF SCOPE (LOCKED constraint 5 — an applied migration is historical fact). Its defect is named in VA-6's docstring and pinned by the round trip instead."
  - "33-03 (SYNC-12): both merge tests are PINNING tests, not fixes. app/services/merge.py is byte-unchanged. Adding a `None`-filter to `_ledger_row` would be a second mechanism (CLAUDE.md PC-6) AND would break DATE-08 by suppressing the deliberate NULL a pre-update client must produce (AP-3) — that negative rule is written into both docstrings so a later reader cannot 'fix' it by accident."
  - "33-03 (VA-4): the test asserts the unknown field is DROPPED behind a success. .planning/ROADMAP.md:320 and 33-CONTEXT.md:555-556 state this expectation BACKWARDS ('assert reject-not-drop'); execution disproved it and the docstring says so outright."

patterns-established:
  - "Any future migration is covered automatically: VA-7's glob and VA-5/VA-6's `upgrade head` pick up 0027+ with no test edit"
  - "A test that pins an executed finding carries the finding's mechanism in its docstring (module, line, and the library behaviour), so the test survives as documentation when the code is re-read"

requirements-completed: [SYNC-12, SYNC-13]

# Metrics
duration: 22min
completed: 2026-09-04
---

# Phase 33 Plan 03: Migration Tripwires and Schema-Skew Pins Summary

**Nothing in this repo has ever compared `app/db.py`'s append-only trigger DDL against what `alembic upgrade head` actually builds — the exact drift migration 0026 had to patch after the fact — so the suite now owns an Alembic-built database and five tests that close that gap and freeze the two executed schema-skew behaviours before migration 0027 ships into them.**

## Performance

- **Duration:** ~22 min (09:29Z → 09:51Z, including a 7m47s full-suite run)
- **Tasks:** 3
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- **The `app/db.py` ↔ migrations hole is closed.** `tests/test_append_only_cursor.py`
  compares models ↔ its own frozen column sets (`:246-258`) and those sets ↔ `app/db.py`
  DDL (`:261-290`); every fixture builds schema from `create_all`. The migration chain —
  the thing production runs — was compared against nothing. `test_alembic_head_triggers_match_app_db`
  is now the single check spanning that boundary, and it compares the WHOLE map
  (name → normalised DDL), so a trigger present under the right name but guarding the
  wrong column list fails too. That is precisely the 0024→0026 defect class.
- **The downgrade round trip is pinned, and the pin is demonstrably not vacuous.** VA-6 was
  verified against the real defect on a throwaway database (output below): `downgrade 0023`
  leaves only `operations_no_delete` / `operations_no_update` — both `cash_movements`
  guards are gone and nothing says a word. The `-1` round trip legitimately keeps four; the
  same assertion reports two on the destructive path.
- **`push_schema_ok`'s hidden precondition is now enforced.** Plans 33-01 and 33-02 both
  closed with "note for 33-03: the lexicographic comparison is a live dependency on
  `test_revision_ids_are_fixed_width`". It exists now, over all 26 revision files, and picks
  up 0027+ through the glob with no edit.
- **SYNC-12 needed no code, and that is now written down where it will be read.** Both new
  merge tests carry the mechanism and the negative rule in their docstrings, so the next
  person to look at `_ledger_row` finds the reason NOT to add a `None`-filter attached to a
  failing-if-removed test rather than buried in a planning document.
- **Zero production code touched.** `git diff --stat 1563b2d^..HEAD` is three test files plus
  the mandated `app/__init__.py` version bump. `app/services/merge.py` is byte-unchanged.

## Task Commits

Each task was committed atomically:

1. **Task 1: `alembic_engine` fixture beside conftest's `engine`** — `1563b2d` (test)
2. **Task 2: `tests/test_migrations.py` — VA-5, VA-6, VA-7** — `1412788` (test)
3. **Task 3: VA-3 and VA-4 in `tests/test_merge.py`** — `d548d9d` (test)

## Files Created/Modified

- `tests/conftest.py` *(+92 / −0, purely additive)* — a section comment stating the
  "beside, never instead of" relationship, `_REPO_ROOT`, the module-level `_run_alembic`
  driver, the `run_alembic` factory fixture, and `alembic_engine`. Placed immediately after
  `engine` and before `session`. `engine` (`:22-33`) and the `sync_driver_pair` server-DB
  block are untouched; `grep -c "Base.metadata.create_all"` is still exactly 2.
- `tests/test_migrations.py` *(created, 133 lines)* — three tests, no new dependency
  (`pathlib`, `re`, `sqlalchemy.text` and the two fixtures only). `grep -c conftest` is 0.
- `tests/test_merge.py` *(+99)* — `test_missing_column_lands_default` and
  `test_unknown_field_is_dropped`, placed in the existing "under-migrated server" section
  they mirror. Both reuse the shipped `record_from_orm` / `_cash` / `build_ndjson` /
  `_apply` helpers; no new helper was introduced.
- `app/__init__.py` — `__version__` 1.69 → 1.72 (one bump per completed-task commit).

## Decisions Made

All decisions are in the frontmatter `key-decisions` block. Two are worth naming here
because they are places where this plan knowingly departs from a written premise:

1. **VA-4 asserts DROP, not reject.** `.planning/ROADMAP.md:320` and `33-CONTEXT.md:555-556`
   phrase the check as "assert reject-not-drop". That is backwards: `parse_exchange` keeps
   every non-`kind` key (`merge.py:189`) and `_ledger_row` projects it away through the
   receiver's `KIND_TO_FIELDS` (`merge.py:460`), so the merge reports a plain success. The
   test pins the real behaviour and its docstring says the ROADMAP wording is backwards, so
   the next reader does not "fix" `merge.py` to satisfy a false expectation.
2. **The 0024 defect is documented, not repaired.** An applied migration is historical fact
   (LOCKED constraint 5). VA-6 is the guard from now on.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `run_alembic` exposed as a factory fixture, not by import**

- **Found during:** Task 2, writing the round-trip test.
- **Issue:** The plan specifies `run_alembic` as a *module-level helper* in `tests/conftest.py`
  AND an acceptance criterion that `grep -c "conftest" tests/test_migrations.py` returns 0.
  Those are mutually exclusive — `tests/` has no `__init__.py`, so the only way to reach a
  module-level name is `from conftest import run_alembic`, and every spelling of that import
  contains the token.
- **Fix:** the module-level implementation is `_run_alembic` (still a module-level helper with
  the specified `(db_url, *args) -> None` signature, and still what `alembic_engine` calls
  internally); a one-line `run_alembic` fixture returns it, so tests receive it by injection.
  This is the file's own established idiom — `login`, `past_sale` and `mobile_client_factory`
  are all factory fixtures returning callables.
- **Files modified:** `tests/conftest.py`
- **Commit:** `1563b2d`

**2. [Rule 3 - Blocking] `settings.database_url` retargeted, not just `sqlalchemy.url`**

- **Found during:** Task 1.
- **Issue:** the plan's action says to set `sqlalchemy.url` on the Config object. That alone
  does nothing: `alembic/env.py:22` UNCONDITIONALLY overwrites it with
  `settings.database_url`, so every `run_alembic` call would have migrated the developer's
  real `data/myorishop.db`. Setting the `DATABASE_URL` env var alone is equally useless —
  `app.config.settings` is a module-level singleton already instantiated when pytest imports
  the app, so it never re-reads the environment.
- **Fix:** `_run_alembic` sets the Config option (kept — it is the correct Alembic idiom and
  the comment names the override), AND retargets `settings.database_url` and `DATABASE_URL`,
  restoring both in a `finally`. Without the restore, one migration test would redirect the
  app's engine for every test that ran after it in the same process.
- **Files modified:** `tests/conftest.py`
- **Commit:** `1563b2d`

**3. [Rule 1 - Bug] Import order in the new helper**

- **Found during:** Task 1 verification. Ruff classifies `alembic` as first-party (the repo
  has a local `alembic/` directory) but `alembic.config` as third-party, so the two imports
  belong in different blocks — the same split the shipped `tests/test_merge.py` already has.
  Reordered; `ruff check` clean.
- **Commit:** `1563b2d`

**Total deviations:** 3 (all mechanical; none changed the plan's design, scope or assertions)
**Impact on plan:** None. All `must_haves` truths and artifacts hold as written.

## Issues Encountered

- **`ruff format --check tests/conftest.py` reports 1 file would be reformatted.** The two
  hunks it wants are PRE-EXISTING (`device_client` and `sync_driver_pair`'s `mint_token`
  calls, untouched by this plan) — this file is not ruff-format clean at HEAD. `ruff check`
  is the gate the phase has been using and it passes on all three touched files. Not fixed:
  out of scope, and reformatting a 460-line shared fixture file mid-phase would collide with
  every other plan touching it.
- **`alembic/env.py` calls `fileConfig()` on every `run_alembic` call**, which reconfigures
  logging process-wide with `disable_existing_loggers=True`. Verified harmless here: nothing
  in the suite uses `caplog` (`grep -rln caplog tests/` is empty) and the full run shows no
  new failure. Flagged rather than worked around — a future log-asserting test would need to
  know this.
- **Nothing else.** No blocker, no architectural question, no fix-attempt loop.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_append_only_cursor.py tests/test_pragmas.py -x -q` (Task 1 gate) | **19 passed** — the existing `engine` chain is unaffected |
| `uv run pytest tests/test_migrations.py -q` | **3 passed** — all green at HEAD, which is what makes them a tripwire for 0027 |
| `uv run pytest tests/test_merge.py -k "missing_column or unknown_field_is_dropped" -q` | **2 passed, 37 deselected** |
| `uv run pytest tests/test_merge.py tests/test_merge_pg.py -q` | **39 passed, 2 skipped** (merge_pg skips without `DATABASE_URL`) |
| The five VA nodeids run explicitly by nodeid | **5 passed** — every one collects and passes |
| `uv run pytest tests/ -q --junitxml=reports/33-03.xml` (full suite) | **2 failed, 1505 passed, 14 skipped** in 467.24s |
| `git diff --numstat tests/conftest.py` (Task 1) | `92  0` — additive only, zero deletions |
| `grep -c "Base.metadata.create_all" tests/conftest.py` | **2** — unchanged from HEAD |
| `grep -n "def engine" / "def alembic_engine" tests/conftest.py` | `:26` / `:103` — the new fixture is after the old one |
| `grep -c "conftest" tests/test_migrations.py` | **0** |
| `grep -c "0024\|requires_recreate_in_batch" tests/test_migrations.py` | 4 — VA-6's docstring names both |
| `grep -c "AP-3" tests/test_merge.py` | **2** — one per new docstring |
| `git diff --stat app/services/merge.py` | empty — SYNC-12 is a pinning test, not a fix |
| `git diff --stat 1563b2d^..HEAD` | `app/__init__.py`, `tests/conftest.py`, `tests/test_merge.py`, `tests/test_migrations.py` only |
| `uv run ruff check` on all three touched files | All checks passed |

**Full-suite result read carefully:** the baseline after 33-02 was `4 failed, 1498 passed,
14 skipped`. This run is `2 failed, 1505 passed`. 1498 + 5 new tests = 1503, plus 2 of the
4 known-red cases happening to pass this time = 1505. The 2 remaining failures
(`test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`) are a SUBSET
of the documented known-red four in `tests/test_sync_ui.py` — a timing race on
`sync_client._run_lock`, held by the app-lifespan auto-sync thread under the `client`
fixture, which is why the count varies between 2 and 4 between runs. **No new failure, and
no test that passed before this plan fails now.**

### Real-path check (not a test)

VA-6 is only meaningful if its assertion can actually fire. Driven directly against a
throwaway SQLite database (read-only w.r.t. the repo, temp dir, own process):

```
after upgrade head           : ['cash_movements_no_delete', 'cash_movements_no_update', 'operations_no_delete', 'operations_no_update']
after downgrade -1  (0025)   : ['cash_movements_no_delete', 'cash_movements_no_update', 'operations_no_delete', 'operations_no_update']
after upgrade head           : ['cash_movements_no_delete', 'cash_movements_no_update', 'operations_no_delete', 'operations_no_update']
after downgrade 0023  (0024!): ['operations_no_delete', 'operations_no_update']
```

The last line is the executed defect, reproduced: `0024.downgrade()`'s
`op.batch_alter_table(...).drop_column(...)` triggers Alembic 1.18.5's move-and-copy table
rebuild (`SQLiteImpl.requires_recreate_in_batch` is True for everything except `add_column`,
`create_index`, `drop_index`), SQLite drops the table's triggers with the table, and Alembic
does not put them back. VA-6's green result on the `-1` path is therefore a real pass, not a
vacuous one.

## Success Criteria

- [x] VA-5, VA-6, VA-7 (`tests/test_migrations.py`) and VA-3, VA-4 (`tests/test_merge.py`)
      are green.
- [x] `tests/conftest.py::engine` and `sync_driver_pair`'s server DB still build via
      `Base.metadata.create_all`; no existing fixture was re-pointed or shadowed (+92/−0).
- [x] `app/services/merge.py` is byte-unchanged.

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-07 (tampering: a ledger column escaping the trigger enumeration is freely mutable, failing OPEN) | Mitigated — VA-5 diffs the Alembic-built triggers against `app/db.py::APPEND_ONLY_TRIGGERS` as a whole map, closing the one boundary the two shipped tripwires cannot see |
| T-33-08 (tampering: a downgrade that silently drops all four triggers) | Mitigated — VA-6, with the 0024 defect named in the docstring and reproduced above; fixing 0024 stays out of scope (LOCKED constraint 5) |
| T-33-09 (spoofing: a non-fixed-width revision id makes `push_schema_ok`'s ordering meaningless, letting an ahead client through the gate) | Mitigated — VA-7, a regex tripwire over all 26 revision files, automatic for 0027+ |
| T-33-SC (supply chain) | Vacuous — no package installed, `pyproject.toml` untouched |

## Known Stubs

None. Nothing was left hardcoded, placeholdered or unwired. Every test asserts against a
real database or the real `alembic/versions/` directory.

## Threat Flags

None — no new network endpoint, auth path, file access pattern or schema change. This plan
adds tests and one test fixture; it touches no production code path.

## User Setup Required

None.

## Next Phase Readiness

- **Ready:** LOCKED ordering constraint 1 is satisfied — migration 0027 now ships into a
  suite that can already prove it. VA-5 will red if 0027 changes a trigger without moving
  `app/db.py::APPEND_ONLY_TRIGGERS` in the same commit; VA-6 will red if 0027's `downgrade()`
  uses a batch operation that strips the guards (the 0024 trap, which 0027 must not repeat
  — its four new columns should be added with `add_column`, the one batch op that does NOT
  recreate the table); VA-7 will red if 0027's revision id is not the literal `"0027"`.
- **Ready:** plan 33-01's `push_schema_ok` no longer has an unenforced precondition. If
  `test_revision_ids_are_fixed_width` is ever relaxed, that predicate must switch to a parsed
  comparison in the same commit.
- **Ready for 33-07:** `alembic_engine` and `run_alembic` are in the shared fixture module
  exactly so VA-9 (byte-identity across the migration) can reuse them without a cross-file
  import.
- **Still blocked:** wave 2 remains gated on the human-only plan 33-04 inputs, both already
  measured read-only on s1 and carried forward unchanged for a third plan:
  **`alembic current` = `0026 (head)`** and the effective **`DISPLAY_TZ` = `Europe/Moscow`**,
  supplied by the `app/config.py:76` fallback — there is no `DISPLAY_TZ` line in
  `.env.production` and the container env value is empty. That is the literal to bake into
  migration `0027`'s backfill.
- **Carry forward for 33-04:** the new columns must be nullable with NO column default. VA-3
  proves why: SQLAlchemy drops a `None`-valued key and substitutes the default, so a column
  default would silently convert a pre-update client's deliberate NULL into a value and break
  DATE-08's read-time COALESCE bucketing (AP-3).

## Self-Check: PASSED

All four claimed files exist on disk (`tests/conftest.py`, `tests/test_migrations.py`,
`tests/test_merge.py`, `app/__init__.py`); all three task commits (`1563b2d`, `1412788`,
`d548d9d`) are present in `git log`.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
