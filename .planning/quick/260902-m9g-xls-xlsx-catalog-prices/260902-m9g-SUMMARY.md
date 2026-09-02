---
phase: quick/260902-m9g
plan: 01
subsystem: database
tags: [sqlite, sqlalchemy, gzip, xlrd, openpyxl, catalog-prices, import]

# Dependency graph
requires:
  - phase: quick/260902-g1q
    provides: the accumulative JSON export transport (merge_price_export / write_export)
  - phase: quick/260902-k2i
    provides: read_workbook_sheets() / price_list_files() — the both-extension readers
provides:
  - "upsert_price_rows(): the ONE no-delete writer for catalog_prices, shared by all three import paths"
  - "collect_prices_from_sheets() / collect_from_archive(): the both-extension archive walk with a named-failure report"
  - "gzip transport: catalogs/catalog_prices.json.gz (239 184 rows, 5 020 082 bytes) replaces catalog_prices.json"
  - "catalog_prices is a real price history: 239 184 rows / 12 446 codes / 233 346 with bonus points"
affects: [deploy, catalogs, pricing, sync]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ownership by UNIQUE key: a source owns its own (year, number, code) triples, never the whole table"
    - "Symmetric merge: an incoming None never overwrites a stored value"
    - "gzip-by-suffix transport via a single _open_export() dispatch"

key-files:
  created:
    - catalogs/catalog_prices.json.gz
  modified:
    - scripts/import_prices.py
    - scripts/import_master_pricelist.py
    - app/services/pricing.py
    - tests/test_import_prices.py
    - tests/test_import_master_pricelist.py
    - deploy/DEPLOY.s1.md
    - app/__init__.py

key-decisions:
  - "One writer with one implementation: import_master_pricelist imports upsert_price_rows from import_prices rather than growing a second copy of the rule"
  - "An incoming None never overwrites a stored value — symmetric, so neither the master snapshot nor the archive can impoverish the other"
  - "no_price_column reports «yielded no price row at all», not «no sheet has a ПЦ header» — the real archive defeats the header predicate"
  - "The server price command drops --only-missing on purpose: it filters by CODE, so with it the server would keep receiving the old snapshot"
  - "catalog_prices.json deleted only after BOTH the superset proof and the at-scale round-trip passed"

patterns-established:
  - "Tripwire test: the removed table-wide delete call is grepped for in both scripts, with the needle composed from parts"
  - "Invariant proof by set arithmetic against a before-snapshot, not by eye"

requirements-completed: [PRICE-01, PRICE-02, PRICE-03, PRICE-04, PRICE-05, PRICE-06, PRICE-07]

# Metrics
duration: ~75min
completed: 2026-09-02
---

# Quick task 260902-m9g: xls/xlsx catalog prices Summary

**`catalog_prices` is a real price history now — 15 798 → 239 184 rows over 12 446 codes with bonus points on 233 346 of them — because a source owns its own `(year, number, code)` triples instead of deleting the whole table, and because the price path finally reads `.xls` as well as `.xlsx`.**

## Performance

- **Tasks:** 3 of 3
- **Files modified:** 7 (+1 created, 1 deleted)
- **Duration:** ~75 min (three full-suite runs at ~6.5 min each dominate it)

## Task Commits

1. **Task 1: RED — pin the ownership rule, the both-extension walk and the gz transport as tests** — `25c717f` (test)
2. **Task 2: GREEN — one no-delete writer, both extensions, gzip transport** — `53ac157` (feat)
3. **Task 3: run the real import, prove the invariants, ship the .gz and the runbook** — `a12f211` (feat)

Working tree after `a12f211`: clean for tracked files (`git status --porcelain --untracked-files=no` empty).

## Observed output

Everything below is pasted from the run, not paraphrased.

### The archive walk (PRICE-02)

Second run shown, because it carries the corrected `no_price_column` report; the
first run's file/catalog/code/row counts were identical.

```
WARNING *** File is truncated, or OLE2 MSAT is corrupt!!
INFO: Trying to access sector 1782 but only 1663 available
Files: 233  catalogs: 227  codes: 11557
Collected rows: 237913
Unparsable filename (3): ['oriflame_prices_compact.xlsx', 'oriflame_prices_with_calculations.xlsx', 'oriflame_prices_with_calculations_fixed.xlsx']
Unreadable (1): ['12-2013.xls (IndexError)']
No price column (2): ['04-2024.xls', '05-2024.xls']
Inserted: 0  updated: 0  unchanged: 237913
CatalogPrice: 239184 -> 239184
```

The first run (same command, before the reporting fix):

```
Files: 233  catalogs: 227  codes: 11557
Collected rows: 237913
Inserted: 223386  updated: 14527  unchanged: 0
CatalogPrice: 15798 -> 239184
```

Every SPEC number is reproduced exactly: 233 files, 227 catalogs, 11 557 codes,
237 913 rows, 223 386 inserted.

### The seed step (PRICE-01)

`uv run python scripts/import_prices.py --from-export catalogs/catalog_prices.json`,
run BEFORE the archive walk so the later superset proof is structural rather
than lucky:

```
Source: E:\dev\myorishop\catalogs\catalog_prices.json  (15798 rows, 12372 codes)
Mode: upsert (a source owns its own (year, number, code) triples; nothing removed)
Inserted: 0  updated: 0  unchanged: 15798
CatalogPrice: 15798 -> 15798
```

### The invariants (PRICE-07)

```
BEFORE  rows=15798  codes=12372  points_not_null=0
AFTER   rows=239184  codes=12446  points_not_null=233346
Codes before: 12372  after: 12446  lost: 0  gained: 74
Latest issue moved FORWARD (allowed, expected): 1746
Latest issue moved BACKWARD (failure): 0
Codes that had a price before and have none now (failure): 0
CHECK PASSED: no code lost, no price lost, no issue regressed.
```

Against the plan's thresholds: rows 239 184 > 230 000; codes 12 446 ≥ 12 372;
non-NULL points 233 346 > 200 000. The 74 gained codes and the 233 346 points
are the SPEC's own measured figures, reproduced.

**Stated SPEC deviation (as the plan required).** The SPEC line
«`latest_price_for_code()` для нескольких кодов возвращает то же самое до и
после (последний выпуск не должен уехать назад)» contradicts itself once the
archive lands: the archive holds issues NEWER than the master snapshot's
«Последний каталог» for 1 746 codes, so "the same before and after" cannot hold
while the parenthetical does. The parenthetical is the operative rule and is
what the check enforces — backward movement is a failure (0 observed), forward
movement is expected and is REPORTED (1 746) rather than asserted away.

### The export and the two proofs (PRICE-05)

```
Export: E:\dev\myorishop\catalogs\catalog_prices.json.gz
Было: 0  добавлено: 239184  обновлено: 0  стало: 239184
Rows: 239184  codes: 12446  size: 5020082 bytes
```

5 020 082 bytes = 4.79 MiB (the SPEC estimated ~4.7 MB), first two bytes `1f 8b`.

Superset proof — the old file's triples against the new file's:

```
OLD catalogs/catalog_prices.json: 15798 triples
NEW catalogs/catalog_prices.json.gz: 239184 triples
Triples of OLD missing from NEW: 0
SUPERSET PROVEN: the new file loses nothing.
```

Round-trip at scale — `--from-export catalogs/catalog_prices.json.gz` into a
throwaway EMPTY SQLite database (`DATABASE_URL` override, schema via
`Base.metadata.create_all`), never touching `data/myorishop.db`:

```
Schema created on: sqlite:///.../scratchpad/roundtrip.db
Snapshot (empty):   rows=0       codes=0      points_not_null=0
Source: E:\dev\myorishop\catalogs\catalog_prices.json.gz  (239184 rows, 12446 codes)
Mode: upsert (a source owns its own (year, number, code) triples; nothing removed)
Inserted: 239184  updated: 0  unchanged: 0
CatalogPrice: 0 -> 239184
Snapshot (after):   rows=239184  codes=12446  points_not_null=233346
```

**The two triples side by side:**

| Measured on | rows | distinct codes | non-NULL points |
|---|---|---|---|
| real DB after the archive walk (step 4) | 239 184 | 12 446 | 233 346 |
| throwaway DB from the `.gz` (step 5b)   | 239 184 | 12 446 | 233 346 |

Identical. Only after BOTH proofs was `git rm catalogs/catalog_prices.json` run.

Ignore gates: `git check-ignore` says the `.gz` is tracked; `.dockerignore`
carries no `*.gz` rule, so it reaches the image.

### The backup (step 1)

```
Backup: E:\dev\myorishop\data\backups\myorishop-20260902-143846.db
Size: 10526720 bytes
```

Taken with the app's own `create_backup()` (VACUUM INTO, WAL-safe, taken while
the operator's server was running and never touching it). The orchestrator's
pre-made copy at `scratchpad/myorishop-before-260902-m9g.db` is the second
line of defence.

### The user-visible fix (PRICE-06)

Substituted issue, and why: the SPEC asks for a 2020 issue, but
`/catalogs/{url_code}` is served by `get_catalog()`, which requires a PDF on
disk, and only `2025-01`..`2026-09` PDFs exist on this machine — a 2020 URL
404s. The plan proposed `2025-03`; that issue turned out to show no gain (see
below), so the reported proof is **`2025-01`**, a pre-2026 issue where the dash
genuinely became a price.

`/catalogs/2025-01`, through the exact calls the route makes:

```
get_catalog('2025-01') -> {'year': 2025, 'number': 1, 'filename': '2025-01.pdf', ...}
products_in_catalog('2025-01'): 3
prices_for_catalog(2025, 1) rows -- BEFORE: 0   AFTER: 941
products resolving to a price -- BEFORE: 0/3   AFTER: 3/3
  46684: name='БУТЫЛКА ДЛЯ ВОДЫ' PC=99900 OP=32100 BB=10
  547189: name='НАБОР "СОЛНЕЧНОЕ НАСТРОЕНИЕ"' PC=49900 OP=32000 BB=5
  47634: name='ПОДУШКА ДЛЯ НОГ С МИШКОЙ' PC=249900 OP=80200 BB=25
```

For the plan's suggested `2025-03`: `prices_for_catalog(2025, 3)` went from 12
rows to 880, but all 12 products the page lists already had a price, so the page
itself is unchanged — hence the substitution.

**PENDING HUMAN CHECK:** open `/catalogs/2025-01` in the operator's own running
instance at localhost:8000 and confirm the price column shows real prices. No
second server was started (the operator's own instance reads this database);
nothing else in this task depends on that check.

## Finding worth acting on (not fixed here — out of scope)

The `/catalogs/{issue}` page lists products from `Dictionary.catalogs`, which
the master price list collapses to a SINGLE issue per code («Последний
каталог»). So the page's product list is thin by construction, and — since the
master snapshot always had a row for exactly those triples — most issues gain
nothing visibly even though `prices_for_catalog` coverage exploded. Measured
across every issue with a PDF (products / priced before → after):

```
2025-01     3    0 ->  3      2025-17   827  827 -> 827
2025-02     2    0 ->  2      2026-03    14    0 ->   9
2025-03    12   12 -> 12      2026-05    12    0 ->   6
2025-16    95   95 -> 95      2026-08    23    1 ->  18
                              2026-09    25    4 ->  19
```

The remaining bottleneck for that page is `Dictionary.catalogs`, not
`catalog_prices`. The data to widen it now exists (227 issues in
`catalog_prices`); wiring it is a separate task, deliberately not started here —
the SPEC's boundary says `Dictionary` is not to be touched at all.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] `no_price_column` never fired on the real archive**
- **Found during:** Task 3 (step 3, the first real archive walk)
- **Issue:** The plan expects `04-2024.xls` and `05-2024.xls` to be NAMED as
  having no price column. They were not. My first predicate was «no sheet
  carries a ПЦ header», and both files ship an EMPTY `КАЛЬКУЛЯТОР` template
  sheet that does carry `КОД … ББ ОП ДЦ ПЦ`, next to the real price sheet whose
  header is `КОД … ББ ОП ДЦ` with no `ПЦ`. The header predicate therefore
  passed while the file contributed zero rows — silently unreported, which is
  precisely the failure the report exists to prevent.
- **Fix:** The report now names a workbook that **yielded no price row at all**,
  which is both the operative meaning of PRICE-02 and strictly more robust (it
  catches a file that contributes nothing for any reason).
- **Files modified:** `scripts/import_prices.py`, `tests/test_import_prices.py`
- **Verification:** The real archive shape (`CALCULATOR_SHEET` +
  `NO_CONSUMER_SHEET`, transcribed from the probe output of the two files) is
  pinned as a test; the second archive run reports
  `No price column (2): ['04-2024.xls', '05-2024.xls']`. Row totals are
  unaffected — 237 913 both before and after the fix, matching the SPEC.
- **Committed in:** `a12f211` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug).
**Impact on plan:** None on scope or data. The fix makes the walk's report
honest, which is the requirement PRICE-02 actually states.

## Issues Encountered

- **Stray database created in the scratchpad.** Running the helper script with
  the CWD set to the scratchpad made `app.config`'s `_DATA_DIR = Path("data")`
  resolve there, creating an empty `data/myorishop.db` plus `secret_key` /
  `device_id`. Removed immediately; every later invocation runs from the repo
  root. No repo file and no real data was touched.
- **`--from-export` step-5b targeting.** `DATABASE_URL` was exported in the
  environment of that one command chain only (the Bash tool does not persist
  shell state between calls), so `data/myorishop.db` could not be reached by it.
  Confirmed by the empty-then-full snapshots of the throwaway file.

## Boundaries honoured

- `app/services/pricing.py`: **docstring only.** The whole diff sits inside the
  module docstring — no `def`, no `return`, no `select(` line moved.
- `price_history_for_code()` remains **dead code — neither deleted nor wired
  up**, per the SPEC boundary. It is still called by no route. Its existence is
  now noted in the pricing.py docstring so the next reader is not misled.
- `Dictionary`, `Product`, `Batch`, `Operation`, `Sale`: untouched.
- `--only-missing` keeps its by-CODE meaning;
  `test_insert_missing_price_rows_filters_by_code_and_is_idempotent` passes
  unchanged (run individually as the plan required: `1 passed`).
- **Zero new dependencies.** `git diff --stat HEAD -- pyproject.toml uv.lock` is
  empty. `gzip` is stdlib; `xlrd` stays ad hoc via `uv run --with xlrd` and is
  never added to the project. `openpyxl` and `xlrd` remain imported INSIDE
  functions — `test_excel_readers_are_not_imported_at_module_level` passes for
  both packages.

## Test results

```
4 failed, 1425 passed, 13 skipped, 3 warnings in 406.98s (0:06:46)
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru
FAILED tests/test_sync_ui.py::test_not_configured_run_is_a_noop
FAILED tests/test_sync_ui.py::test_lock_hit_returns_locked_partial
```

All four failures are the documented pre-existing `tests/test_sync_ui.py` race
on `sync_client._run_lock` (held by the lifespan auto-sync thread). Not caused
by this task, not fixed here, and **the suite is NOT fully green** — the earlier
run in this session produced 3 of the same 4, which is what a race looks like.
Nothing outside `tests/test_sync_ui.py` fails.

The two importer files, in full: `51 passed, 1 skipped`. The skip is
`test_the_two_real_price_lists_rebuild_the_33154_series`, which is
`importorskip("xlrd")` — green when run as `uv run --with xlrd pytest`.

`ruff check` is clean on `scripts/import_prices.py` and `app/services/pricing.py`.
`scripts/import_master_pricelist.py` reports 3 `E501` line-too-long — **all
three pre-date this task** (proved by running ruff on the file as it stood at
`25c717f`: same 3 errors). Left alone per the scope boundary; noted here rather
than silently fixed.

## Evidence artifacts

- `reports/260902-m9g.xml` — junit: `tests="1442" errors="0" failures="4" skipped="13"`
- `reports/260902-m9g.sha` — `a12f211572d2d764f430cd90a4459743a1eabf46`
- `reports/260902-m9g.dirty` — no tracked modifications; the `??` entries are
  pre-existing untracked files (present at session start) plus this plan's own
  `.planning/` directory and the three report files.

## Next readiness

- The server can now receive the full history with a single non-destructive
  command; `deploy/DEPLOY.s1.md` §4/§4.1 carry the measured numbers and both
  surviving warnings. **Nothing was deployed to s1 in this task** — local plus
  docs only, as the plan required.
- Version bumped to `1.55`.
- Open follow-up: widening `Dictionary.catalogs` beyond the single latest issue
  (see "Finding worth acting on").

## Self-Check: PASSED

All 12 claimed files exist on disk; `catalogs/catalog_prices.json` is confirmed
gone; all three commit hashes (`25c717f`, `53ac157`, `a12f211`) exist in
`git log`.

---
*Quick task: 260902-m9g-xls-xlsx-catalog-prices*
*Completed: 2026-09-02*
