---
phase: 33-back-dated-operations
plan: 05
subsystem: schema
tags: [alembic, sqlite, postgresql, triggers, append-only, timezone, backfill, lockstep, sqlalchemy]

# Dependency graph
requires:
  - phase: 33-back-dated-operations
    plan: 01
    provides: "push_schema_ok / the HTTP 409 push gate — without it these four columns entering merge.KIND_TO_FIELDS would be a silent-loss window"
  - phase: 33-back-dated-operations
    plan: 03
    provides: "alembic_engine + run_alembic + VA-5/VA-6/VA-7 — the tripwires this migration ships INTO"
  - phase: 33-back-dated-operations
    plan: 04
    provides: "33-ROLLOUT.md — the measured _DISPLAY_TZ literal and s1's alembic current = 0026"
provides:
  - "operations.business_date / cash_movements.business_date — nullable String(10), the operator's LOCAL calendar day"
  - "operations.reverses_op_id / cash_movements.reverses_movement_id — nullable String(36), ship UNUSED but trigger-guarded"
  - "alembic/versions/0027_ledger_business_date_and_reversal_links.py — add_column x4 -> tz-correct backfill -> trigger rewrite, mirrored downgrade"
  - "app/db.py::APPEND_ONLY_TRIGGERS v4 — both *_no_update triggers guard all four new columns"
  - "a timezone-correct business_date on every pre-existing ledger row"
affects: [33-06, 33-07, 33-15, phase-34-reversal, sync, alembic, merge]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A migration that must ADD a column to an append-only table writes add_column -> backfill -> trigger rewrite, in that order: the value-based WHEN guard is blind to a column it does not enumerate, so the backfill passes through the OLD trigger and the NEW trigger seals it afterwards"
    - "A ledger column ships with NO column-level value of any kind (neither Python-side nor DDL) whenever a NULL from an older client is a meaningful sentinel — SQLAlchemy substitutes the Python-side value for a None-valued key, and a ClauseElement DDL value flips Alembic into batch-recreate"
    - "downgrade() restores the previous trigger DDL BEFORE dropping the columns those triggers name — both SQLite and PostgreSQL refuse the DROP COLUMN otherwise"
    - "The measured deployment timezone is a file-local literal in the migration, never an import of app.config (WR-06) — the 0024 _DEFAULT_CURRENCY precedent"

key-files:
  created:
    - alembic/versions/0027_ledger_business_date_and_reversal_links.py
  modified:
    - app/models.py
    - app/db.py
    - tests/test_append_only_cursor.py
    - app/__init__.py

key-decisions:
  - "33-05 (LOCKED constraint 4): all five artifacts landed in ONE commit (615be81) — migration, app/db.py::APPEND_ONLY_TRIGGERS, both IMMUTABLE_* frozensets, the four model columns, plus the version bump. Migration 0026 exists solely because this lockstep was missed once, for cash_movements.currency."
  - "33-05 (column shape, V1/VA-3): all four columns are nullable and carry NO column-level value of ANY kind. A Python-side value would be substituted for a None-valued key and destroy DATE-08's NULL sentinel; a ClauseElement DDL value would flip Alembic's requires_recreate_in_batch to True and strip all four triggers on the way UP. This INVERTS what research/ARCHITECTURE.md assumed."
  - "33-05 (LOCKED constraint 3, executed): upgrade() order is add_column -> tz-correct backfill -> trigger rewrite. The mechanism is not luck: the pre-0027 guard is a VALUE-based FOR EACH ROW WHEN over an EXPLICIT column enumeration, so an UPDATE of a column it does not name evaluates the WHEN to false and succeeds for 100% of rows."
  - "33-05 (LOCKED constraint 7, executed): downgrade() restores the pre-0027 triggers FIRST, then drops the columns with plain op.drop_column. batch_alter_table appears in NO executable line of 0027 — only in comments, where it names the 0024 defect so the next author does not copy its shape."
  - "33-05 (DATE-07): the backfill converts created_at through ZoneInfo('Europe/Moscow') in Python, never a naive 10-character UTC cut. Executed: a 2026-08-31T21:30:00+00:00 row backfills to 2026-09-01, while a 09:00Z control row stays 2026-08-31. created_at itself is byte-unchanged (DATE-04)."
  - "33-05: DATE-03/04/07/08 are NOT marked complete — this plan delivers only their schema half. The read-time COALESCE bucketing (33-06) and the byte-identity proof VA-9 (33-07) are what finish them; marking them here would have made REQUIREMENTS.md's traceability table lie."
  - "33-05: the two reversal-link columns get an ORM ForeignKey but NO native FK constraint (the shipped sale_id/batch_id/author_id precedent), so a reversal whose target has not arrived yet renders as a dangling link instead of rolling back an entire push (Phase 34 LOCKED constraint 4)."

patterns-established:
  - "The trigger enumeration's column padding is load-bearing: test_declared_constants_match_trigger_ddl asserts f'NEW.{column} ' WITH a trailing space, so a name longer than the current alignment column forces a re-flow of the whole block, never a relaxed assertion"

requirements-completed: []

# Metrics
duration: 30min
completed: 2026-09-04
---

# Phase 33 Plan 05: Ledger business_date and Reversal Links Summary

**All four new ledger columns, the dual-dialect trigger rewrite that guards them, and a timezone-correct backfill that puts a 21:30-UTC row into the NEXT local day landed in a single commit — because a ledger column no trigger enumerates is freely mutable on an already-synced row, and the ledger fails open without saying anything.**

## Performance

- **Duration:** ~30 min (including a 7m23s full-suite run and a 3-cycle real-path migration drive)
- **Tasks:** 3 (two staging tasks + one verify-and-commit task, by design ONE commit)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- **The five-artifact lockstep held.** `git log -1 --name-only` lists the migration,
  `app/models.py`, `app/db.py`, `tests/test_append_only_cursor.py` and `app/__init__.py`
  in the same commit, and `git log --oneline -3` shows no intermediate commit touching a
  subset. VA-5 (`test_alembic_head_triggers_match_app_db`) is what makes that a proof
  rather than a promise: it diffs the WHOLE trigger map produced by `alembic upgrade head`
  against `app/db.py::APPEND_ONLY_TRIGGERS`, so a migration that changed a guard without
  moving the constant reddens.
- **The tz-correct backfill is demonstrated, not asserted.** Driven against a throwaway
  database seeded at revision `0026` with a row at `2026-08-31T21:30:00+00:00`
  (= 00:30 MSK on 1 September) and a control row at `09:00Z` the same day. The late row
  backfilled to `2026-09-01`; the control row to `2026-08-31`. A naive 10-character UTC cut
  would have put both in August — that is exactly the DATE-07 byte-identity failure, and it
  is now impossible by construction. `created_at` came back byte-identical on both rows
  (DATE-04).
- **All four new columns are actually guarded.** Four UPDATE attempts against the migrated
  database — `business_date` and `reverses_op_id` on `operations`, `business_date` and
  `reverses_movement_id` on `cash_movements` — were each ABORTed with `... ledger is
  append-only`, while `UPDATE ... SET synced_at = ...` still succeeded. Both directions
  matter: the guard must close on the new columns without closing on the sync cursor.
- **The downgrade is a real mirror, and the 0024 trap was not re-entered.** `upgrade head →
  downgrade -1 → upgrade head` left exactly four triggers at every step, the four columns
  disappeared and came back, and the backfill re-ran identically. `batch_alter_table`
  appears nowhere in an executable line of `0027`.
- **`cash_movements_no_update`'s alignment was re-flowed rather than the assertion relaxed.**
  `reverses_movement_id` is 20 characters against the block's previous 12-character
  alignment column, so every line of that trigger's `WHEN` clause was re-padded to keep the
  trailing space `test_declared_constants_match_trigger_ddl` asserts on (AP-2). `operations`
  needed no re-flow — `unit_price_cents` (16) already exceeds both new names.
- **Nothing outside the plan's file list was touched.** No route, service, template or
  report changed; `merge.py` is byte-unchanged. The four columns enter the sync wire format
  automatically because `merge.KIND_TO_FIELDS` is mapper-derived — which is precisely why
  plan 33-01's 409 gate had to land first.

## Task Commits

This plan is a deliberate single-commit lockstep (LOCKED ordering constraint 4). Tasks 1
and 2 staged; Task 3 verified and committed.

1. **Tasks 1–3, all five artifacts** — `615be81`
   (`feat(33-05): migration 0027 + the four ledger columns, in one lockstep commit`)

## Files Created/Modified

- `alembic/versions/0027_ledger_business_date_and_reversal_links.py` *(created, 392 lines)* —
  `revision = "0027"`, `down_revision = "0026"`. A module docstring carrying the LOCKSTEP
  RULE, the no-retroactive-edits rule, the named-and-out-of-scope `0024.downgrade()` defect,
  the per-dialect null-safety, the PostgreSQL `json` cast requirement, WR-06, and the
  accepted fleet-divergence note. `_DISPLAY_TZ = "Europe/Moscow"` as a file-local literal.
  `_SQLITE_DDL` / `_PG_DDL` (both `*_no_update` triggers) and a separate
  `_SQLITE_DOWNGRADE_DDL` / `_PG_DOWNGRADE_DDL` pair holding the pre-`0027` enumerations.
  `upgrade()` opens with a comment block stating the locked internal order and why.
- `app/models.py` *(+34)* — `Operation.reverses_op_id` (after `batch_id`),
  `Operation.business_date` (after `created_at`), `CashMovement.reverses_movement_id`
  (after `sale_id`), `CashMovement.business_date` (after `created_at`). Each `business_date`
  carries a comment naming DATE-08 and why it is never defaulted; each `reverses_*_id`
  carries one saying it ships unused and trigger-guarded in Phase 33 and is first WRITTEN in
  Phase 34.
- `app/db.py` *(+22 / −11)* — `APPEND_ONLY_TRIGGERS` extended: `reverses_op_id` and
  `business_date` in `operations_no_update`, `reverses_movement_id` and `business_date` in
  `cash_movements_no_update`, the latter block re-padded. A **v4** entry added to the running
  version log naming `0027` and the four columns; the header's migration list now names
  `0027` alongside `0001/0013`, `0018` and `0026`. The two `*_no_delete` triggers are
  untouched and `NEW.synced_at` appears nowhere (`grep -c` = 0).
- `tests/test_append_only_cursor.py` *(+4)* — `IMMUTABLE_OPERATION_COLUMNS` gained
  `business_date` and `reverses_op_id`; `IMMUTABLE_CASH_COLUMNS` gained `business_date` and
  `reverses_movement_id`. Neither tripwire was edited.
- `app/__init__.py` — `__version__` 1.72 → 1.73 (one bump on the single commit).

## Decisions Made

All decisions are in the frontmatter `key-decisions` block. Two are worth naming here
because they are places where this plan knowingly departs from a written premise:

1. **No column default of any kind — the inverse of what `research/ARCHITECTURE.md` assumed.**
   That document claimed an explicit `None` in the insert dict beats a column default. The
   executed VA-3 finding (33-03) is the opposite: SQLAlchemy 2.0.51 REMOVES a `None`-valued
   key from the emitted INSERT and substitutes the Python-side value. A default would
   therefore have converted a pre-`0027` client's deliberate NULL into a date and quietly
   destroyed DATE-08's sentinel. `CashMovement.currency` is consequently NOT a live bug and
   was not "fixed".
2. **DATE-03/04/07/08 stay unmarked in REQUIREMENTS.md.** The plan's frontmatter lists them,
   but this plan delivers only their schema half: DATE-03's period bucketing is plan 33-06,
   DATE-07's byte-identity proof is VA-9 in plan 33-07, and DATE-08's read-time COALESCE is
   33-06. Marking them complete here would have made the traceability table claim work that
   does not exist yet. SYNC-12 and SYNC-13 were already `[x]` from 33-03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `ruff check` rewrote the migration's import block and `timezone.utc`**

- **Found during:** Task 2 verification.
- **Issue:** the file as first written used `from datetime import datetime, timezone` +
  `timezone.utc`, and grouped `sqlalchemy` and `alembic` in one import block (mirroring
  `0024`). Ruff flagged both: `UP017` wants the `datetime.UTC` alias, and `I001` splits the
  block because this repo has a local `alembic/` directory, so `alembic` classifies as
  first-party while `sqlalchemy` does not (the same split 33-03 hit in `tests/conftest.py`).
- **Fix:** `ruff check --fix` on that file only. Behaviour is unchanged — re-ran the full
  real-path migration drive afterwards and it passed identically.
- **Files modified:** `alembic/versions/0027_ledger_business_date_and_reversal_links.py`
- **Commit:** `615be81`

### Acceptance criteria read literally vs. read for intent

- **`grep -n "batch_alter_table" alembic/versions/0027_*.py returns nothing`** — it returns
  **four hits, all of them comment or docstring lines** (`:29`, `:36`, `:334`, `:381`). This
  is not a miss: the same task's `<action>` explicitly REQUIRES the docstring to name the
  `0024.downgrade()` `batch_alter_table` defect so the next author does not copy its shape,
  which makes the criterion as literally written unsatisfiable. The criterion's intent — no
  executable line uses it — holds, and is independently pinned by VA-6.

**Total deviations:** 1 mechanical fix + 1 criterion read for intent. Neither changed the
plan's design, scope or assertions.

## Issues Encountered

- **`ruff format --check` reports `app/models.py` and `tests/test_append_only_cursor.py`
  would be reformatted.** Verified PRE-EXISTING: piping the HEAD versions of both files
  through `ruff format --check --stdin-filename` returns the same result, and
  `ruff format --diff` shows the three hunks it wants are all in code this plan never
  touched (`SyncState.auto_interval_seconds`, two `text(...)` call sites, one generator
  expression). This matches 33-03's finding that `ruff format` is not the gate this phase
  uses; `ruff check` is, and it passes on all four touched files. Not fixed — out of scope,
  and reformatting shared files mid-phase would collide with the plans still to run.
- **Nothing else.** No blocker, no architectural question, no fix-attempt loop.

## Verification

| Check | Result |
|-------|--------|
| `uv run pytest tests/test_append_only_cursor.py -x -q` (Task 1 gate) | **16 passed** — both tripwires green after the frozenset + padding edits |
| `uv run pytest tests/test_migrations.py tests/test_append_only_cursor.py -x -q` (Task 2 gate) | **19 passed** — VA-5, VA-6, VA-7 green with `0027` in the chain |
| `uv run pytest tests/test_append_only_cursor.py tests/test_migrations.py tests/test_merge.py tests/test_sync_schema_gate.py -x -q` (Task 3 gate) | **65 passed** |
| `uv run pytest tests/ -q --junitxml=reports/33-05.xml` (full suite) | **3 failed, 1504 passed, 14 skipped** in 443.44s |
| `uv run alembic heads` | **`0027 (head)`** |
| `uv run ruff check` on all four touched code files | All checks passed |
| `git log -1 --name-only` | the migration + `app/models.py` + `app/db.py` + `tests/test_append_only_cursor.py` + `app/__init__.py`, ONE commit |
| `git log --oneline -3` | `615be81` then `9a51aed`/`7d362dd` (33-04) — no intermediate subset commit |
| `grep -nE "server_default\|default=" 0027_*.py` | **(none)** |
| `grep -nE "^from app\|^import app\|from app\." 0027_*.py` (WR-06) | **(none)** |
| `grep -n "substr" 0027_*.py` | **(none)** |
| `grep -c "payload::text" 0027_*.py` | **3** (`_PG_DDL` + `_PG_DOWNGRADE_DDL`) |
| `grep -n "batch_alter_table" 0027_*.py` | 4 hits, **all comment/docstring** — see the criterion note above |
| `grep -c "NEW.synced_at" app/db.py` | **0** |
| `grep -rn "reverses_operation_id" app/ tests/` | **(none)** — the column is `reverses_op_id` |
| `python -c "... all(f'NEW.{c} ' in ddl ...)"` for the three new names | **OK** — the trailing space survived the re-flow |
| `git status --porcelain` (tracked files) | **clean** after the commit |

**Full-suite result read carefully:** the plan text and the executor brief disagree on the
baseline (four known-red vs. `2 failed, 1505 passed`), because the count varies run to run.
The invariant that matters holds: **1504 + 3 = 1507 non-skipped tests, exactly the same
total as 33-03's `1505 + 2 = 1507`** — this plan adds no test, so the total must not move,
and it did not. All three failures (`test_sync_run_returns_oob_partial`,
`test_offline_run_returns_200_ru`, `test_lock_hit_returns_locked_partial`) are a SUBSET of
the documented known-red four in `tests/test_sync_ui.py`, and each fails on
`sync_client._run_lock.acquire(blocking=False)` being False — the lifespan auto-sync thread
holding the lock, red since ≤ `49a53d2`. **No new failure; no test that passed before this
plan fails now.**

### Real-path check (not a test)

The suite proves the triggers survive; it does not prove the backfill produces the RIGHT
date. Driven directly against a throwaway SQLite database (temp dir, own process, repo
untouched, no server started), seeded at revision `0026` so the rows genuinely predate the
column:

```
at 0026, triggers      : ['cash_movements_no_delete', 'cash_movements_no_update', 'operations_no_delete', 'operations_no_update']
after head, triggers   : ['cash_movements_no_delete', 'cash_movements_no_update', 'operations_no_delete', 'operations_no_update']
  operations row       : ('op-late', '2026-08-31T21:30:00+00:00', '2026-09-01', None)
  operations row       : ('op-noon', '2026-08-31T09:00:00+00:00', '2026-08-31', None)
  cash row             : ('cm-late', '2026-08-31T21:30:00+00:00', '2026-09-01', None)
coverage (total, filled): (2, 2)
  REJECTED             : business_date = '1999-01-01' ...        -> operations ledger is append-only
  REJECTED             : reverses_op_id = 'op-noon' ...          -> operations ledger is append-only
  REJECTED             : business_date = '1999-01-01' ...        -> cash ledger is append-only
  REJECTED             : reverses_movement_id = 'x' ...          -> cash ledger is append-only
  synced_at stamp        : allowed
after downgrade -1     : ['cash_movements_no_delete', 'cash_movements_no_update', 'operations_no_delete', 'operations_no_update']
  ops columns          : [... 'created_by', 'synced_at', 'sale_id', 'batch_id', 'author_id']   <- business_date/reverses_op_id gone
  cash columns         : [... 'created_by', 'synced_at', 'author_id', 'currency']              <- both new columns gone
after upgrade head     : ['cash_movements_no_delete', 'cash_movements_no_update', 'operations_no_delete', 'operations_no_update']
  re-backfilled        : {'op-late': '2026-09-01', 'op-noon': '2026-08-31'}

ALL CHECKS PASSED
```

`op-late` at `21:30Z` is `00:30` on the following day in `Europe/Moscow`, so its business
date is `2026-09-01` — a naive prefix cut would have said `2026-08-31` and moved that sale
into the wrong month. `coverage (2, 2)` is the local equivalent of `33-ROLLOUT.md` §5's
`total == filled` smoke assertion.

## PostgreSQL: proven design, UNPROVEN locally

**Recorded, not skipped.** The PostgreSQL half of BOTH the trigger rewrite (`_PG_DDL` /
`_PG_DOWNGRADE_DDL`) and the backfill has **not been executed on this machine**: there is no
PostgreSQL instance here, and starting or installing one to work around that is forbidden
(CLAUDE.md — never start a service you did not start, no unrequested infrastructure). No
database was started, stopped or installed.

- **The command that proves it:** `uv run pytest tests/test_pg_parity.py -q` with
  `DATABASE_URL` pointing at the `postgres:17` CI service. `tests/test_pg_parity.py` skips
  at module level unless `DATABASE_URL` is a PostgreSQL URL, which is why it is silent
  locally rather than red.
- **Where it runs:** the existing pg-parity CI job. That run is a **phase gate carried by
  plan 33-15** — this plan does not close it.
- **What is at stake if it fails:** the PG branch is where `NEW.payload::text` lives (an
  uncast comparison raises `operator does not exist: json = json`) and where
  `EXECUTE FUNCTION operations_append_only()` reuses the `0001`/`0013` PL/pgSQL functions.
  Both were copied from `0018`, which has run on the production server, so the risk is
  transcription rather than design.
- **The other half of the same gap:** the production rollout itself
  (`33-ROLLOUT.md` §3–§5) — migrate + redeploy with `--build`, run the three read-only smoke
  SELECTs, verify the skew window, and only THEN cut the client release tag. Not started;
  human-owned.

## Success Criteria

- [x] Four nullable, default-less ledger columns exist on both tables.
- [x] Every pre-existing row gets a timezone-correct `business_date`; `created_at` untouched (DATE-04).
- [x] All four columns guarded by both `*_no_update` triggers — SQLite executed, PostgreSQL written and CI-gated.
- [x] `downgrade -1 → upgrade head` preserves exactly four triggers.
- [x] All five lockstep artifacts landed in ONE commit (`615be81`).

## Threat Model Coverage

| Threat ID | Status |
|-----------|--------|
| T-33-07 (a new ledger column escaping the trigger enumeration is freely mutable — the ledger fails OPEN, silently) | **Mitigated** — all four columns added to both `WHEN` enumerations in both dialect branches, to `app/db.py`, and to both frozensets, in one commit. VA-5 diffs the two; VA-8 diffs constants against models and DDL; four real UPDATE attempts were rejected on a live migrated DB |
| T-33-08 (`downgrade()` destroying the cash guards via a batch-mode recreate) | **Mitigated** — triggers restored first, then plain `op.drop_column`; `batch_alter_table` in no executable line. Pinned by VA-6 and re-proven on the throwaway DB |
| T-33-13 (SQL injection through the backfill) | **Mitigated** — the timezone is a file-local literal; every statement is a module-level literal constant (`_BACKFILL_SELECT` / `_BACKFILL_UPDATE`, not even a table-name f-string); the per-row value goes through `:bd` / `:id` bound parameters |
| T-33-14 (a naive `created_at[:10]` backfill silently moving evening rows into the wrong month) | **Mitigated** — Python conversion through `ZoneInfo(_DISPLAY_TZ)`; demonstrated on a 21:30Z row landing on the NEXT local day. DATE-07's byte-identity proof itself is VA-9, plan 33-07 |
| T-33-15 (`alembic upgrade head` aborting mid-upgrade because the backfill trips its own new trigger) | **Mitigated** — LOCKED internal order written as a comment inside `upgrade()`; executed end-to-end on the throwaway DB with rows present before the migration ran |
| T-33-SC (supply chain) | **Vacuous** — no package installed, `pyproject.toml` untouched |

## Known Stubs

The two `reverses_*_id` columns ship **UNUSED**: nothing writes them, no route, service or
template reads them, and every row this migration produces has them NULL. This is
**deliberate and stated in the plan** — all four columns land in ONE migration so the fleet
sees one dual-dialect trigger rewrite and one schema-skew window instead of two. Phase 34
(one-tap reversal) is the first phase that WRITES them. Both the model comments and the
migration docstring say so at the point a reader will be standing.

No other stub. Nothing was left hardcoded, placeholdered or unwired.

## Threat Flags

None. No new network endpoint, auth path or file-access pattern. The schema change at the
trust boundary (four columns entering `merge.KIND_TO_FIELDS` automatically, since it is
mapper-derived) is not a NEW surface — it is the exact surface the plan's own threat model
enumerates, and it is the reason plan 33-01's HTTP 409 push gate had to land first.

## User Setup Required

None locally. **Server-side, before any client release tag is cut:** follow
`33-ROLLOUT.md` §4 — `docker compose -f docker-compose.prod.yml up -d --build` (the
`--build` is not optional; the image bakes the application code), then the three read-only
smoke SELECTs of §5 expecting `total == filled` on both tables and exactly four trigger
names.

## Next Phase Readiness

- **Ready for 33-06/33-07:** the columns exist and every pre-existing row carries a
  timezone-correct value, so `business_date_expr`'s read-time COALESCE has both a populated
  column and a real NULL sentinel to bucket. The read-time fallback is a UTC-prefix cut of
  `created_at` and must NOT be unified with this migration's tz-correct write-time rule —
  the migration docstring says so at the site.
- **Ready for 33-07 (VA-9):** `alembic_engine` + `run_alembic` still drive the whole chain,
  now including `0027`, so the byte-identity proof across the migration can reuse them.
- **Ready for Phase 34:** both `reverses_*_id` columns exist, are guarded, and are
  documented as write-me-first-in-34.
- **Open, carried:** the PostgreSQL branch (CI, plan 33-15) and the production rollout
  (`33-ROLLOUT.md`, human-owned). Neither is a code defect.
- **Unchanged warning:** `.planning/ROADMAP.md:320` states VA-4's expectation backwards
  ("assert reject-not-drop"); execution disproved it in 33-03 and nothing here changes that.

## Self-Check: PASSED

`alembic/versions/0027_ledger_business_date_and_reversal_links.py`, `app/models.py`,
`app/db.py`, `tests/test_append_only_cursor.py` and `app/__init__.py` all exist on disk;
commit `615be81` is present in `git log` and contains exactly those five files.

---
*Phase: 33-back-dated-operations*
*Completed: 2026-09-04*
