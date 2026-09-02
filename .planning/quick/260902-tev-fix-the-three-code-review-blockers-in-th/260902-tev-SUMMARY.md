---
phase: 260902-tev-fix-the-three-code-review-blockers-in-th
plan: 01
subsystem: import-scripts
tags: [data-safety, rollback, validation, atomic-write]
branch: fix/260902-import-blockers
requires:
  - .planning/quick/260902-m9g-xls-xlsx-catalog-prices/260902-m9g-REVIEW.md
provides:
  - "DictionaryReplaceRefused + guarded apply_master_import(force=) + backup_before_replace"
  - "validate_records over all 7 export fields"
  - "atomic_write, shared by the three accumulative writers"
  - "snapshot_dictionary — a dialect-free pre-delete rollback artifact"
affects:
  - scripts/import_master_pricelist.py
  - scripts/import_prices.py
  - scripts/import_catalogs.py
tech-stack:
  added: []
  patterns:
    - "same-directory temp + os.replace, temp name keeps the destination suffix"
    - "guards raised INSIDE the writer function, not in main(), so every caller is protected"
key-files:
  created: []
  modified:
    - scripts/import_master_pricelist.py
    - scripts/import_prices.py
    - scripts/import_catalogs.py
    - tests/test_import_master_pricelist.py
    - tests/test_import_prices.py
    - tests/test_import_catalogs.py
decisions:
  - "The shrink threshold is 0 %, with no tolerance band: on a clean install the table is empty when this importer runs, so the guard is silent on the happy path; a 20 % band would not catch the real 45 % s1 case anyway."
  - "The refusal message is actionable — two counts, the import_catalogs.py recovery command, then --force last."
  - "The temp file keeps the destination's suffix (catalog_prices.json.gz.tmp.gz) because _open_export keys gzip-vs-plain off the suffix."
  - "Money validation is >= 0, not > 0: export_prices() re-exports whatever the database holds, so a stored zero must still load."
  - "The rollback artifact is a products.json-shaped dump written with pure ORM, not a second backup mechanism: s1 is PostgreSQL, where VACUUM INTO cannot run."
  - "The snapshot is taken in main() inside the session, never inside apply_master_import — that function stays free of filesystem side effects because unit tests call it directly."
metrics:
  duration: "~85 min"
  completed: 2026-09-02
  tasks: 4
  commits: 4
  files: 6
  tests_added: 26
---

# Quick task 260902-tev: three code-review blockers closed

Closed CR-01/CR-02/CR-03 of `260902-m9g-REVIEW.md` — the same class of defect the
m9g task fixed for `catalog_prices`, left open next door — as three independently
revertable commits on `fix/260902-import-blockers`. Nothing else was touched.

## Commits

| # | Blocker | SHA | Revert |
|---|---------|-----|--------|
| 1 | CR-01 — degraded master-price import wipes `dictionary` | `a99a989` | `git revert a99a989` |
| 2 | CR-02 — `.gz` transport validated on 3 of 7 fields | `1481e38` | `git revert 1481e38` |
| 3 | CR-03 — accumulative files truncated before serialization | `aaa6f1b` | `git revert aaa6f1b` |
| 4 | Verifier gap — the rollback promise did not hold on PostgreSQL | `352f51a` | `git revert 352f51a` |

Each commit touches only its own concern's files (2 / 2 / 4 / 2 files).

**Revertability, verified by trial `git revert --no-commit` runs (all aborted, tree
left clean):**

* `a99a989` (CR-01) reverts cleanly on its own — disjoint files.
* `aaa6f1b` (CR-03) reverts cleanly on its own.
* `352f51a` (commit 4) reverts cleanly on its own — it is the tip, and it touches
  only the two `import_master_pricelist` files.
* `1481e38` (CR-02) reverts cleanly **after** CR-03 is reverted (LIFO). Reverting it
  while CR-03 is still on top produces one textual conflict, in the import list of
  `tests/test_import_prices.py`, where CR-03 added `atomic_write` next to CR-02's
  `MAX_NAME`. That is ordinary adjacent-line conflict, not a coupling of the fixes:
  the two changes are in different functions of `scripts/import_prices.py`
  (`validate_records` vs `write_export`/`write_overrides`/`atomic_write`) and it
  resolves by keeping `atomic_write` and dropping `MAX_NAME`.

## What changed

### CR-01 — `scripts/import_master_pricelist.py` (commit `a99a989`)

* `DictionaryReplaceRefused(RuntimeError)`, mirroring `ShadeNameWouldShrink` in
  `scripts/import_catalogs.py:87`. Raised **inside** `apply_master_import`, before
  `session.query(Dictionary).delete()`, so every caller is protected:
  * empty `collected` → refuse (the degraded-parse wipe);
  * `len(rows) < session.query(Dictionary).count()` and not `force` → refuse.
* `apply_master_import(session, collected, *, force=False)` — keyword-only, so both
  pre-existing call sites keep working unchanged. `build_dictionary_rows` is called
  **once** and the list reused for the insert.
* The 0 %-threshold reasoning (install order from `deploy/DEPLOY.s1.md:73-121`,
  the 6 856-vs-12 582 numbers from `:101-105`, the prose-only warning at `:94-97`)
  is recorded in the function's own docstring so the next reader does not re-open it.
* `backup_before_replace(engine)` — `create_backup` VACUUM INTO snapshot, path
  printed; a printed no-op on a non-SQLite dialect; the exception is **not** caught,
  so a failed snapshot aborts before anything is deleted. Takes the engine and is
  called from `main()` before the session opens, so the two unit tests that call
  `apply_master_import` directly do not spray backups into the developer's
  `data/backups/`.
* `main()`: `--force` (rejected together with `--only-missing`), the sibling
  script's empty-input `sys.exit` guarding **both** modes, and the pre-write half of
  the summary moved ahead of the session. The post-write half stays where it was.

### CR-02 — `scripts/import_prices.py` (commit `1481e38`)

`validate_records()` now covers all seven fields: `name` (None, else `str` no longer
than the existing `MAX_NAME` constant — not a fourth literal `200`) and
`consumer_cents` / `consultant_cents` / `points` (None, else `int`, never `bool`,
never negative). `build_price_rows` carries values verbatim into INTEGER columns, so
this is the last gate before the DB.

### CR-03 — `scripts/import_prices.py`, `scripts/import_catalogs.py` (commit `aaa6f1b`)

`atomic_write(dest, payload, *, newline)` next to `_open_export`: same-directory temp,
`os.replace`, `finally: tmp.unlink(missing_ok=True)`. Reused by
`import_prices.write_export` (with `serialize_export(merged)` evaluated as the
argument, so the ~42 MB string exists before `dest` is touched),
`import_prices.write_overrides` and `import_catalogs.write_export` (cross-script
import, the idiom `import_master_pricelist.py` already uses). Only stdlib `os` was
added — zero new dependencies.

### Commit 4 — a portable `dictionary` snapshot (`352f51a`)

Not part of the original plan: the verifier found that the rollback promise did not
hold where it matters most. `backup_before_replace` is `VACUUM INTO`, i.e. SQLite
only, and s1 runs PostgreSQL (`deploy/DEPLOY.s1.md:26,60`) — so on the server it
printed its skip line and took nothing, leaving a `--force` run with no way back
except the baked `catalogs/products.json`, which does not carry the hand-typed server
names `deploy/DEPLOY.s1.md:94-97` warns about. The dialect gate itself was sanctioned
by the plan and stays.

`snapshot_dictionary(session)` dumps the table through
`import_catalogs.export_dictionary()` — already exactly the `products.json` shape —
into `backups/dictionary-YYYYMMDD-HHMMSS.json`, through the `atomic_write` of the
previous commit. Pure ORM, no dialect anywhere. It prints the path **and** the restore
command (`import_catalogs.py --only-missing --file <snapshot>`), returns None for an
empty table, and catches nothing: no snapshot, no import. It is called from `main()`
inside the session and before `apply_master_import` — deliberately not inside that
function, which stays free of filesystem side effects because unit tests call it
directly on throwaway engines.

The new import edge `import_master_pricelist -> import_catalogs` adds no cycle
(`import_catalogs` imports only `import_prices`), verified by `grep` and by importing
both modules in one interpreter.

## Deviations from Plan

None for tasks 1-3 — the plan executed exactly as written. Nothing outside `scripts/`
and `tests/` was touched, `app/__init__.py` `__version__` was not bumped, and every
WARNING/INFO finding of the review was left alone.

Commit 4 was added on the coordinator's instruction after the verifier found the
PostgreSQL gap; it follows the same rules (test-first, one atomic commit, full suite
as the gate). Two small judgement calls inside it, both stated rather than assumed:

* The snapshot call sits after **both** pre-counts (`before_dict`, `before_cp`) rather
  than immediately after `before_dict`, so the two counts stay adjacent as a pair. The
  substantive requirement — inside the session, before `apply_master_import` — holds,
  and an ast test pins the call order.
* No same-second collision counter (the `PD-11` loop of `app/services/backup.py:37-41`)
  was added: the brief named `:35`, the timestamp style, and this importer takes
  seconds per run, so two snapshots in one second is not a reachable state.

## Verification

**Test-first, per task.** Each RED step was observed before its fix:

* CR-01: `ImportError: cannot import name 'DictionaryReplaceRefused'`. The print-order
  tripwire was additionally proven RED against the pre-fix script text
  (`git show HEAD:scripts/import_master_pricelist.py`): `stats_line=319`,
  `session_block=298`, `backup_calls=[]` — statistics printed 21 lines after the
  session block, and no snapshot call existed at all.
* CR-02: the 7 new parametrize cases failed with `Failed: DID NOT RAISE SystemExit`,
  while `test_validate_records_accepts_a_stored_zero_and_a_null` passed from the start.
* CR-03: `ImportError: cannot import name 'atomic_write'` and, in
  `tests/test_import_catalogs.py`, `AssertionError: the writer never went through
  _open_export`.
* Commit 4: `ImportError: cannot import name 'snapshot_dictionary'`. One of the five
  new tests then failed on its own bug — `tmp_path` also holds the `session` fixture's
  `test.db`, so the "empty dictionary writes nothing" assertion was tightened from
  `iterdir() == []` to `glob("dictionary-*.json") == []`.

**Full suite (the gate), observed counts:**

| Run | Result |
|-----|--------|
| Baseline (before any change) | `4 failed, 1425 passed, 13 skipped` in 393 s |
| After CR-01 | `3 failed, 1433 passed, 13 skipped` in 382 s |
| After CR-02 | `4 failed, 1440 passed, 13 skipped` in 385 s |
| After CR-03 | `3 failed, 1446 passed, 13 skipped` in 383 s |
| After commit 4 | `3 failed, 1451 passed, 13 skipped` in 400 s |

Every failure in every run is in `tests/test_sync_ui.py` (`sync_client._run_lock` held
by the lifespan auto-sync thread) — the known pre-existing set, which is
non-deterministically 3 or 4 of the same 4 tests. No fifth failure appeared at any
point. `+26` tests collected across the four commits (8 + 8 + 5 + 5).

**Lint:** `uv run ruff check` on the six touched files reports the same 3 pre-existing
`E501`s in `scripts/import_master_pricelist.py` (lines 3, 137, 144 — review IN-07) and
nothing else. Confirmed identical against the HEAD copy of the file before the change:
`Found 3 errors` both times. No new findings.

**Real path exercised, not just the suite.** Against a throwaway database
(`MYORISHOP_DATA_DIR` pointed at a scratch dir + `alembic upgrade head`), so the
operator's `data/myorishop.db` was never opened:

1. Header drift (`«Последний каталог»` renamed in a copy of the real xlsx):
   `Missing expected column(s) ['Последний каталог'] … sheet 'Прайс-лист'`, exit 1,
   no session opened.
2. The historical incident (all 6 856 «Последний каталог» values reshaped to a bare
   `2021`): `Collected 0 price rows … (missing code: 0, unparsable catalog: 6856) —
   nothing written`, exit 1, in **both** the full-replace and the `--only-missing` mode.
3. `--force --only-missing` → `--force is meaningless with --only-missing; that mode
   deletes nothing`, exit 1.
4. Happy path on the empty throwaway DB: the six pre-write statistics lines and
   `Rollback snapshot: …\livecheck\backups\myorishop-20260902-200102.db` printed
   **before** `Dictionary: 0 -> 6890`; the snapshot file exists on disk (249 856 bytes).
5. The s1 scenario end to end: loaded the throwaway DB to 12 582 rows with
   `import_catalogs.py --only-missing --file catalogs/products.json`, then re-ran the
   master importer → `DictionaryReplaceRefused: refusing to replace 'dictionary':
   stored 12582 -> about to write 6890. Restore the fuller справочник with
   'scripts/import_catalogs.py --only-missing --file catalogs/products.json'; pass
   --force only if this shrink is a deliberate rebuild`, exit 1. A following
   `--force` run reported `Dictionary: 12582 -> 6890`, which also proves the refused
   run deleted nothing.
6. CR-03 on real data: `--export` of both files into a **non-existent** directory —
   `catalog_prices.json.gz` starts with `1f 8b` (the suffix-preserving temp kept the
   gzip branch), `products.json` is LF-only, `indent=1`, trailing newline, and no
   `*.tmp*` file was left behind. `write_overrides` re-wrote the real tracked
   `app/services/rubric_overrides.json` into a scratch destination:
   **byte-identical, 314 015 == 314 015 bytes**, 1 873 entries, no leftover temp.
7. **The rollback promise, end to end on real data (commit 4).** Reloaded the
   throwaway DB to 12 582 codes, then planted a "hand-typed server name" on code
   34473 via `import_catalogs.py --file`. A `--force` run then printed both
   snapshots and the restore command:
   `Dictionary snapshot (12582 codes): …\backups\dictionary-20260902-202319.json` /
   `  restore with: scripts/import_catalogs.py --only-missing --file …`, followed by
   `Dictionary: 12582 -> 6890`. The artifact is 2 199 742 bytes, LF-only,
   `indent=1`, trailing newline, contains the hand-typed name verbatim, and left no
   `*.tmp*` behind. Running the printed restore command brought the table back to
   **12 582**, and a re-export is the same 2 199 742 bytes — the round trip lost
   nothing, and code 34473 carries its hand-typed name again.

## Known Stubs

None.

## Threat Flags

None — no new network endpoint, auth path or trust boundary was introduced. The only
new CLI surface is `--force` on a local operator-run script (T-TEV-05, accepted in the
plan), and the only new import is stdlib `os` (T-TEV-SC).

## Pending human check

A real PostgreSQL run was NOT exercised here — no server is available in this
environment. What is proven: `snapshot_dictionary` is pure ORM with no dialect
reference, and a unit test monkeypatches `engine.dialect.name` to `"postgresql"`,
asserting in one test that `backup_before_replace` returns None and writes no `.db`
while `snapshot_dictionary` still writes its JSON. The remaining check for a human,
on s1: run the importer against the PostgreSQL deployment and confirm the
`Dictionary snapshot (N codes): …` line appears and the file exists in the container's
backup directory.

## Observations (not fixed — out of scope)

* `DictionaryReplaceRefused` propagates out of `main()` as a traceback rather than a
  one-line `sys.exit` message. This is the plan's contract and matches the sibling
  idiom (`ShadeNameWouldShrink` is uncaught in `import_catalogs.py` too); the message
  itself is the last line of the traceback and the exit code is 1.
* The review's WARNING (WR-01..09) and INFO (IN-01..09) findings remain open by
  instruction, including IN-07's three pre-existing `E501`s in the file this task
  edited.
* `--only-missing` restores codes that were **deleted**; it does not undo names that
  were **overwritten** for codes the master price list also covers. That case is
  served by dropping `--only-missing` (the default `--file` path rewrites every name
  from the snapshot), which the function's docstring states. The printed line keeps
  the safer `--only-missing` form, matching the CR-01 refusal message.

## Self-Check: PASSED

All six modified files exist on disk; all four commit SHAs (`a99a989`, `1481e38`,
`aaa6f1b`, `352f51a`) are present in `git log`. `uv run pytest
tests/test_import_master_pricelist.py tests/test_import_prices.py
tests/test_import_catalogs.py -q` → `101 passed, 1 skipped` after every trial revert
was aborted, confirming the tree is intact.

The only tracked change left in the working tree is ` M .planning/STATE.md`, which
this task did not make and deliberately did not commit or revert.
