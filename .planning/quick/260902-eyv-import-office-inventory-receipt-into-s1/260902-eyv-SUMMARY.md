---
phase: quick-260902-eyv
plan: import-office-inventory-receipt-into-s1
subsystem: scripts
tags: [python, sqlalchemy, csv, receipts, batches]

# Dependency graph
requires:
  - phase: phase-09
    provides: app.services.receipts.register_receipt (batch birth path, single write path)
  - phase: quick-260721-fu0
    provides: scripts/reset_business_data.py dialect-aware script shape (_target_label, dialect guard)
  - phase: quick-260902-1d1
    provides: the corrected reports/оприходование-офис-2026-08-31.csv (names + codes filled)
provides:
  - scripts/import_inventory_receipt.py (dry-run-by-default inventory-as-receipt importer)
  - read_rows / split_note / find_warehouse / resolve_row / run_import public surface
  - tests/test_import_inventory_receipt.py (executable contract for SPEC rules 1-7)
affects: [receipts, batches, products, catalog-prices]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Year-month batch key: Batch.expiry.like('YYYY-MM-%') (portable on SQLite and PostgreSQL) instead of a day-exact equality, so «2018-01-14» in the ledger and «2018-01-31» in the sheet resolve to one lot"
    - "One read-only resolve_row() shared by the dry run and --apply, so the printed prediction and the actual write cannot diverge (D-1)"
    - "Run-scoped Pending: dry run remembers predicted cards/batches; --apply remembers only condition-marker batches (the DB is the truth for everything else)"

key-files:
  created:
    - scripts/import_inventory_receipt.py
    - tests/test_import_inventory_receipt.py
  modified:
    - app/__init__.py

key-decisions:
  - "SPEC beats PLAN where they disagree: the batch key is code + YEAR-MONTH of the expiry + condition marker, not code + exact expiry date"
  - "Placement is parsed out of the «Комментарий» column (SPEC rule 3), not built as f'полка {Полка}' as the plan's D-5 said — 2 rows are placed «под зеркалом», which the plan's formula would have written as «полка под зеркалом»"
  - "A condition-marker row may only top up a batch this very run created (same code + month + marker); pre-existing batches are excluded from its lookup, and those marker batches are excluded from the ordinary month lookup, so dry run and --apply agree row for row"
  - "batch.expiry is normalised to the sheet's shape (last day of month) on top-up, alongside the shelf-into-comment write — the only two direct DB writes in the script"

patterns-established:
  - "Untracked-input scripts get a test suite that never reads the real input file: every test writes its own CSV into tmp_path"

requirements-completed: []

# Metrics
duration: ~55min
completed: 2026-09-02
---

# Quick Task 260902-eyv: Import Office Inventory Receipt Into s1 Summary

**`scripts/import_inventory_receipt.py` turns the 414-row office inventory sheet into goods receipts through `register_receipt` only, keying batches by code + year-month + condition marker, with a read-only dry run as the default mode and `--apply` as the single opt-in to write.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 3 completed
- **Files modified:** 3 (2 created, 1 modified)

## Accomplishments

- The sheet is imported as an ADDITION, not a stock-take: every row goes through `app.services.receipts.register_receipt`; there is not a single direct `session.add` / `Product(` / `Batch(` / `Operation(` / `record_operation(` in the script (grep gate returns 0).
- Batch identity follows the updated SPEC: **code + year-month of the expiry + condition marker**. A ledger batch dated `2018-01-14` and a sheet row dated `2018-01-31` are one lot; the touched batch's expiry is then normalised to the sheet's shape.
- A non-empty leftover in «Комментарий» after the placement is a **condition marker** and always forces a fresh batch — but two rows carrying the same code + month + marker still land in one batch. An existing batch's own note (e.g. «Срока на упаковке нет») never blocks a top-up, because the marker is read from the incoming row only.
- The shelf is written to `location` on a new batch and appended to `batch.comment` on a top-up (which `register_receipt` ignores), compared by `"; "`-separated parts so «полка 4» is never treated as already present inside «полка 47».
- Prices travel only for codes with no active card, so no `price_change` op can overwrite an operator's own price with a catalog one; a code missing from `catalog_prices` stays NULL, never 0.
- Dry run is the default and is read-only; `--apply` is the only way to write, and the run prints an explicit non-idempotence warning.
- `__version__` bumped 1.40 → 1.41.

## Task Commits

1. **Task 1 (RED): executable contract on temporary CSVs** — `75cc6b8` (test) — 20 tests, all failing on the missing module, suite collection green (1366 collected).
2. **Task 2 (GREEN): scripts/import_inventory_receipt.py + version bump** — `06a27e6` (feat) — 20 passed, ruff clean, direct-write gate 0.
3. **Task 3: full suite + dry run against the real sheet** — verification only, no code change needed.

Pushed to `origin/main` (`d36efcd..06a27e6`). No deploy to s1 (out of scope by the plan).

## Files Created/Modified

- `scripts/import_inventory_receipt.py` — the importer. Public surface: `CSV_DEFAULT`, `WAREHOUSE_DEFAULT`, `SKIP_CODES`, `COMMENT_MAX_LEN`, `Row`, `Decision`, `Pending`, `split_note`, `read_rows`, `find_warehouse`, `resolve_row`, `run_import`, `main`.
- `tests/test_import_inventory_receipt.py` — 20 tests, every one on a CSV written into `tmp_path`; the real `reports/оприходование-офис-2026-08-31.csv` is never opened by a test.
- `app/__init__.py` — `__version__` "1.40" → "1.41".

## Dry run against the real sheet (full output, verbatim)

Local `data/myorishop.db` is empty of business data (`products` 0, `batches` 0, `operations` 0), so all matching in this run is intra-file.

**1. Default invocation (`--warehouse Офис`) — exercises the active-only rule:**

```
$ uv run python scripts/import_inventory_receipt.py
Целевая база: SQLite file: E:\dev\myorishop\data\myorishop.db
Файл: reports\оприходование-офис-2026-08-31.csv
Не найден активный склад «Офис».
exit=1
```

The local warehouse named «офис» exists but is **soft-deleted** (`deleted_at = 2026-07-12T12:22:26+00:00`), so the active-only lookup correctly refuses it and the script exits non-zero without touching anything. (On s1 «Офис» is active — this is a local-data fact, not a script defect. See Deviations.)

**2. Dry run against the one active local warehouse:**

```
$ uv run python scripts/import_inventory_receipt.py --warehouse "Склад по умолчанию"
Целевая база: SQLite file: E:\dev\myorishop\data\myorishop.db
Файл: reports\оприходование-офис-2026-08-31.csv
Склад назначения: «Склад по умолчанию»
Режим: СУХОЙ ПРОГОН — записи не будет.

Прочитано строк: 414
Пропущено: 1 (строка 313: код «???»)
К оприходованию: 413 строк, 2204 шт.

Новых карточек товара: 332
Новых партий: 397
Доливов в существующие партии: 16
Строк с признаком состояния (долив запрещён): 0
Кодов без цены в catalog_prices: 44

ВНИМАНИЕ: импорт НЕ идемпотентен — повторный запуск с --apply добавит
количество ещё раз.
exit=0
```

No «Предупреждения» block appeared — no multi-batch-per-month ambiguity, no legacy batch, no overlong comment.

**3. Case- and whitespace-insensitive warehouse lookup (rule 7), proven live:**

```
$ uv run python scripts/import_inventory_receipt.py --warehouse "  СКЛАД ПО УМОЛЧАНИЮ  "
Целевая база: SQLite file: E:\dev\myorishop\data\myorishop.db
Файл: reports\оприходование-офис-2026-08-31.csv
Склад назначения: «Склад по умолчанию»
Режим: СУХОЙ ПРОГОН — записи не будет.
...
```

### Numbers cross-checked independently

Every hard number was recomputed from the CSV by a separate throwaway script (own `csv.DictReader` pass + `latest_price_for_code` per code) before the importer was run, and all of them agree:

| Fact | Independent recount | Script output |
|---|---|---|
| data rows | 414 | 414 |
| skipped | 1 — physical line 313, code «???» | 1 (строка 313: код «???») |
| to receipt | 413 | 413 |
| total quantity | 2204 | 2204 |
| unique codes / new cards | 332 | 332 |
| unique (code, year-month) | 397 | 397 new batches |
| top-ups | 413 − 397 = 16 | 16 |
| codes with no catalog price | 44 | 44 |

`новых партий + доливов = 397 + 16 = 413` ✓. The SPEC's soft number **2204 шт. matches exactly — no discrepancy to report.** Also confirmed: in this file every expiry is already the last day of its month, so year-month matching and day-exact matching give the identical 397 (unique `(code, exact expiry)` is also 397) — the year-month rule changes nothing for THIS file and exists for the s1 ledger, where expiries are stored as `…-14` / `…-18`.

### The dry run wrote nothing

Same read-only count query before and after all three invocations:

```
before: products 0  batches 0  operations 0  dictionary 12582  catalog_prices 15798  warehouses 2
after:  products 0  batches 0  operations 0  dictionary 12582  catalog_prices 15798  warehouses 2
```

**`--apply` не запускался** — ни против `data/myorishop.db`, ни против s1, ни разу.

## Verification

**Per module:**
- `uv run pytest tests/test_import_inventory_receipt.py -q` → **20 passed** (RED stage: 20 failed, 0 collection errors)
- `uv run ruff check scripts/import_inventory_receipt.py tests/test_import_inventory_receipt.py` → All checks passed
- direct-write gate `grep -v '^\s*#' scripts/import_inventory_receipt.py | grep -c -E 'session\.add\(|record_operation\(|Operation\(|Product\(|Batch\('` → **0**
- `grep -c 'register_receipt(' scripts/import_inventory_receipt.py` → 1 (the single call site)
- `grep -c '1.41' app/__init__.py` → 1

**Full suite (post-task gate):**

```
uv run pytest -q --junitxml=reports/quick-260902-eyv.xml
...
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial - assert 'Син...
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru - assert 'Нет с...
FAILED tests/test_sync_ui.py::test_not_configured_run_is_a_noop - assert 'Син...
FAILED tests/test_sync_ui.py::test_lock_hit_returns_locked_partial - assert F...
4 failed, 1350 passed, 12 skipped, 3 warnings in 376.19s (0:06:16)
```

The 4 failures are the known, pre-existing `sync_client._run_lock` failures (the lifespan auto-sync thread holds the lock during the full-suite run) — named in full above, unrelated to this task, deliberately not fixed:

1. `tests/test_sync_ui.py::test_sync_run_returns_oob_partial`
2. `tests/test_sync_ui.py::test_offline_run_returns_200_ru`
3. `tests/test_sync_ui.py::test_not_configured_run_is_a_noop`
4. `tests/test_sync_ui.py::test_lock_hit_returns_locked_partial`

**Artifacts:**
- `reports/quick-260902-eyv.xml` (junit, full suite)
- `reports/quick-260902-eyv.sha` → `06a27e64c1786f73d8b3a375b50124779812b488`
- `reports/quick-260902-eyv.dirty` → no tracked-file modifications; only pre-existing untracked paths (`reports/`, `input/`, `AGENTS.md`, `plan1.txt`, unrelated `.planning/` dirs) plus this task's planning docs, which the orchestrator commits.

## Deviations from Plan

### SPEC-driven (the SPEC was updated after the plan was written and takes priority)

**1. [SPEC rule 2.1] Batch key is code + YEAR-MONTH, not code + exact date**
- **Found during:** Task 1 (writing the contract)
- **Change:** `_month_batches` matches `Batch.expiry LIKE 'YYYY-MM-%'` (or `IS NULL`), takes the earliest expiry, warns when more than one batch shares the month, and normalises the matched batch's expiry to the sheet's value after a successful top-up. The plan's `Batch.expiry == expiry` equality was replaced.
- **Files:** `scripts/import_inventory_receipt.py`, `tests/test_import_inventory_receipt.py`
- **Commits:** `75cc6b8`, `06a27e6`

**2. [SPEC rule 2.2] Condition marker forbids top-ups**
- **Change:** `split_note()` splits «Комментарий» into placement + leftover; a non-empty leftover forces a new batch and is stored in that batch's comment next to the shelf. Two rows with the same code + month + marker still share one batch, via a run-scoped `Pending.condition_batches`; those batches are excluded from the ordinary month lookup (`Pending.condition_batch_ids`) so the dry run and `--apply` predict identically. The `Pending` dataclass therefore has 4 fields, not the plan's 2.
- **Files:** same. **Commits:** `75cc6b8`, `06a27e6`
- **Live effect on this sheet: zero.** All 414 «Комментарий» values are pure placement (`полка NN` ×412, `под зеркалом` ×2), so `Строк с признаком состояния: 0`. The rule is carried for future sheets, as the SPEC asks.

**3. [SPEC] Test list expanded from 9 to 20**
- The SPEC's enumerated test list is longer than the plan's; all of its items are covered, plus the plan's own price/warehouse/dry-run tests and a parametrised `split_note` table.

### Rule 1 (auto-fixed bug in the plan's design)

**4. [Rule 1 — Bug] Placement is parsed from «Комментарий», not built from «Полка»**
- **Found during:** Task 2, while checking the real column values.
- **Issue:** the plan's D-5 said `shelf_label = f"полка {row.shelf.strip()}"`. Two rows (physical lines 220-221) carry `Полка = «под зеркалом»`, which that formula renders as the nonsense «полка под зеркалом». SPEC rule 3 says the placement comes from «Комментарий» anyway.
- **Fix:** `split_note()` reads the placement out of «Комментарий» (`полка NN` / `под зеркалом`, case- and whitespace-tolerant) and falls back to the «Полка» column only when the comment carries no recognisable placement (digits → `полка NN`, otherwise the value verbatim).
- **Files:** `scripts/import_inventory_receipt.py`. **Commit:** `06a27e6`

### Instructed by the orchestrator

**5. Version bumped 1.40 → 1.41** (the plan said 1.38 → 1.39; `app/__init__.py` was already at 1.40).

**6. Docs artifacts (SUMMARY/STATE/PLAN/SPEC) not committed here** — left to the orchestrator, so the plan's Task-3 instruction to include `.planning/` files in the commit was not applied. The two code commits contain only `scripts/`, `tests/` and `app/__init__.py`.

## Issues Encountered

**Stale plan expectation: the local «офис» warehouse is soft-deleted.**
Task 3 of the plan expected the default dry run to find a local warehouse named «офис» (proving the case-insensitive lookup). In `data/myorishop.db` that warehouse carries `deleted_at = 2026-07-12T12:22:26+00:00`, and rule 7 says active warehouses only — so the default invocation correctly fails with `Не найден активный склад «Офис».` and exit 1. Not fixed (un-deleting a warehouse in the operator's database is out of scope and destructive-adjacent); instead the dry run was executed against the one active local warehouse, «Склад по умолчанию», and the case-insensitivity requirement was demonstrated separately with `--warehouse "  СКЛАД ПО УМОЛЧАНИЮ  "` plus a dedicated unit test. Warehouse choice does not affect any printed number here, because the local database holds zero products, batches and operations.

**Console-policy note.** The project's global CLAUDE.md requires invoking the `robust-console-commands` skill before every console call. This subagent has no skill-invocation tool available, so that guard could not be honoured mechanically; all console use was kept read-only or test-only, no process was started, killed or restarted, and no `--apply`/destructive command was run.

## User Setup Required

None for the script itself. To actually import on s1, an operator must:
1. copy `reports/оприходование-офис-2026-08-31.csv` to the server,
2. run the **dry run** there first (`--warehouse Офис`) and read the numbers — they will differ from the local ones, because s1 already holds 178 products / 201 batches and 24 of the sheet's codes overlap existing stock,
3. back up the database, then run once with `--apply`. A second `--apply` would add everything again; there is no undo.

## Self-Check: PASSED

- `scripts/import_inventory_receipt.py` — FOUND
- `tests/test_import_inventory_receipt.py` — FOUND
- `app/__init__.py` contains `1.41` — FOUND
- commit `75cc6b8` — FOUND in `git log`
- commit `06a27e6` — FOUND in `git log`, pushed to `origin/main`
