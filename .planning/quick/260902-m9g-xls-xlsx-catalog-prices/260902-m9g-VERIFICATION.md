---
phase: quick/260902-m9g-xls-xlsx-catalog-prices
verified: 2026-09-02T00:00:00Z
status: human_needed
score: 7/7 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  previous_score: n/a
human_verification:
  - test: "Open /catalogs/2025-01 in the operator's own running instance at localhost:8000 (do NOT start a second server) and look at the ПЦ / ДЦ columns."
    expected: "All three products (46684 «БУТЫЛКА ДЛЯ ВОДЫ», 547189 «НАБОР \"СОЛНЕЧНОЕ НАСТРОЕНИЕ\"», 47634 «ПОДУШКА ДЛЯ НОГ С МИШКОЙ») show real prices instead of «—»."
    why_human: "Browser rendering. The data path is fully proven headlessly (prices_for_catalog(2025,1) 0 -> 941 rows, 3/3 products resolve, template pages/catalog_detail.html:35 reads prices.get(entry.code)), but the rendered page itself was never opened. Declared as <human-check> in the PLAN."
---

# Quick task 260902-m9g: xls/xlsx catalog prices — Verification Report

**Task goal:** Импортировать полный архив прайс-листов (.xls + .xlsx) в `catalog_prices`, и убрать причину, по которой архив и снимок мастер-прайса затирали друг друга.
**Verified:** 2026-09-02
**Status:** human_needed (7/7 code-verifiable must-haves VERIFIED; 1 browser check outstanding)
**Re-verification:** No — initial verification
**Commits inspected:** `25c717f`, `53ac157`, `a12f211` (all present in `git log`, branch `main`, tracked tree clean)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | **PRICE-01** — neither importer deletes the whole `catalog_prices` table; each owns only its own `(year, number, code)` triples | ✓ VERIFIED | Repo-wide grep for `.delete()` in `scripts/` returns exactly two hits: `import_master_pricelist.py:241` (`session.query(Dictionary).delete()` — deliberately kept) and `reset_business_data.py:85` (generic wipe tool; it does not import `CatalogPrice` at all). All three former sites are gone: `_run_from_export` now calls `upsert_price_rows` (diff at `scripts/import_prices.py`, the two removed lines `deleted = session.query(CatalogPrice).delete()` / `bulk_save_objects` are visible as `-` in `git diff 25c717f~1..HEAD`); archive `main()` calls `upsert_price_rows` (`scripts/import_prices.py:992`); `apply_master_import` calls it too (`scripts/import_master_pricelist.py:243`). Tripwire test `test_neither_importer_deletes_the_whole_price_table` (`tests/test_import_prices.py:699`) greps both sources with a needle composed from parts — passes. |
| 2 | **PRICE-02** — the archive walk reads BOTH extensions, survives the corrupt `12-2013.xls` by naming it, and names the 2 no-price-column files and the 3 unparsable filenames | ✓ VERIFIED — re-run independently | I re-ran `collect_from_archive(price_list_files(catalogs/price_lists))` myself, read-only, no database touched (`uv run --with xlrd`): `Files: 233  catalogs: 227  codes: 11557`, `Collected rows: 237913`, `Unparsable filename (3): ['oriflame_prices_compact.xlsx', 'oriflame_prices_with_calculations.xlsx', 'oriflame_prices_with_calculations_fixed.xlsx']`, `Unreadable (1): ['12-2013.xls (IndexError)']`, `No price column (2): ['04-2024.xls', '05-2024.xls']`. Every SPEC figure reproduced exactly, independently of the executor. `parse_catalog` strips `\.xlsx?$` (`scripts/import_prices.py:111`). No new reader: `collect_from_archive` calls the pre-existing `read_workbook_sheets` (`:250`). |
| 3 | **PRICE-03** — `--dir` defaults to the archive, `--price-dir` is gone, a 0-row walk writes nothing | ✓ VERIFIED | `DEFAULT_PRICE_DIR = "catalogs/price_lists"` (`scripts/import_prices.py:92`), used as the `--dir` default (`:903`) and for `--restore-shades` too (`:947`). No `--price-dir` anywhere in `main()`. `if not collected: sys.exit(f"Collected 0 price rows from {folder} — nothing written")` (`:987-988`), placed BEFORE the `SessionLocal()` block. |
| 4 | **PRICE-04** — `--only-missing` still filters by CODE; `insert_missing_price_rows` unchanged in meaning; its test still passes | ✓ VERIFIED | `git diff 25c717f~1..HEAD -- scripts/import_prices.py` shows the `insert_missing_price_rows` body as pure context (no `+`/`-` lines inside it). Body still `existing = {code for code in session.scalars(select(CatalogPrice.code).distinct())}` → filter by code (`:805-806`). `test_insert_missing_price_rows_filters_by_code_and_is_idempotent` run individually by me: `1 passed` (as part of a 4-test run, all passed). |
| 5 | **PRICE-05** — `.gz` transport works both ways; the new file is a proven superset of the removed `.json` and round-trips at scale | ✓ VERIFIED — proven independently, stronger than the SUMMARY's claim | I decompressed `catalogs/catalog_prices.json.gz` and compared it field-by-field against `data/myorishop.db` (read-only): GZ `rows=239184 codes=12446 points_not_null=233346`; DB distinct triples `239184`; **GZ triples missing from DB: 0; DB triples missing from GZ: 0; field mismatches DB vs GZ: 0.** Every record carries exactly the 7 EXPORT_KEYS. I then recovered the deleted old file from git (`git show 25c717f~1:catalogs/catalog_prices.json` → `rows=15798 triples=15798 codes=12372`): **OLD triples missing from NEW .gz: 0**, and **0 old values were overwritten with NULL** in the new file. `_open_export` (`:660-673`) dispatches on the `.gz` suffix and forwards `encoding` and `newline` to both branches; `load_export` catches `gzip.BadGzipFile`/`EOFError` (`:689`). |
| 6 | **PRICE-07** — >230 000 rows over ≥12 372 codes with points on >200 000; no code lost a price; no latest issue regressed; a second run inserts 0 and updates 0 | ✓ VERIFIED — queried both databases myself | Read-only sqlite comparison of `data/myorishop.db` against the pre-task backup `scratchpad/myorishop-before-260902-m9g.db`: `AFTER rows=239184 codes=12446 points_not_null=233346` / `BEFORE rows=15798 codes=12372 points_not_null=0`; **codes lost: 0**; **codes that had a price before and have none now: 0**; **latest issue moved BACKWARD: 0**; latest issue moved FORWARD: 1746. Every number matches the SUMMARY exactly. Idempotency proven without writing: my read-only walk showed a second run **would insert 0 and update 0** against the current DB. |
| 7 | **PRICE-06** — `/catalogs/{issue}` for a pre-2026 issue shows real prices; DEPLOY.s1.md §4/§4.1 describe the new non-destructive order and the `.json.gz` file | ✓ VERIFIED (data + docs); render pending human | Data path, queried directly on both DBs: `prices_for_catalog(2025,1)` rows **0 → 941**; `products_in_catalog('2025-01')` = 3 (`46684`, `47634`, `547189`) in both, priced **0/3 → 3/3**. The executor's PRICE-06 proof is real. Route wiring `app/routes/catalogs.py:114` → `prices_for_catalog`; template `pages/catalog_detail.html:35` renders `prices.get(entry.code)` or `—`. DEPLOY.s1.md §4/§4.1 verified line by line below. |

**Score:** 7/7 truths verified.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `scripts/import_prices.py` | `upsert_price_rows`, both-extension walk, gz-aware export | ✓ VERIFIED | `upsert_price_rows` at `:716` — one bulk key SELECT (`:747-758`), chunked `bulk_save_objects` + `session.execute(update(CatalogPrice), batch)` (`:786-793`), never commits, never deletes. `collect_prices_from_sheets` (`:181`) pure, `collect_from_archive` (`:214`) the loop, `_open_export` (`:660`). |
| `scripts/import_master_pricelist.py` | dictionary replaced wholesale, prices only upserted | ✓ VERIFIED | `apply_master_import` (`:235-243`): `session.query(Dictionary).delete()` **kept** at `:241`, then `upsert_price_rows(...)`. `build_catalog_price_rows` (`:230`) is a one-line delegation — no second implementation. |
| `catalogs/catalog_prices.json.gz` | the full price history transport | ✓ VERIFIED | Exists, 5 020 082 bytes, `git ls-files` tracks it, `git check-ignore` exit 1 (not ignored), `.dockerignore` has no `*.gz` rule and cuts only `catalogs/*.pdf` + `catalogs/price_lists/`. |
| `catalogs/catalog_prices.json` | removed | ✓ VERIFIED | Absent from the working tree AND from `git ls-files catalogs/` (only the `.gz` is listed). Diff shows `15800 ----` deletions. |
| `tests/test_import_prices.py` | contract for upsert / walk / gz | ✓ VERIFIED | 9 new tests appended (`:531`-`:711`), **0 deleted lines** in the diff. |
| `tests/test_import_master_pricelist.py` | contract that master import no longer annihilates the archive | ✓ VERIFIED | 3 new tests appended (`:196`, `:230`, `:256`), **0 deleted lines**. |
| `deploy/DEPLOY.s1.md` | rewritten §4 / §4.1 | ✓ VERIFIED | See "Documentation" below. |
| `app/__init__.py` | version 1.55 | ✓ VERIFIED | `__version__ = "1.55"` (`:5`). |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `scripts/import_master_pricelist.py` | `scripts.import_prices.upsert_price_rows` | import — ONE ownership rule, ONE implementation | ✓ WIRED | `from scripts.import_prices import build_price_rows, upsert_price_rows` (`:53`), called at `:243`. |
| `scripts/import_prices.py` archive path | `price_list_files()` / `read_workbook_sheets()` | reuse of existing readers | ✓ WIRED | `price_list_files(folder)` at `:966`; `read_workbook_sheets(path)` at `:250` inside the try/except. No new reader added. |
| `--export` / `--from-export` | `gzip.open` | suffix dispatch | ✓ WIRED | `_open_export` `:672` returns `gzip.open(path, mode, encoding=encoding, newline=newline)`; `write_export` `:848` and `load_export` both route through it. |
| `app/routes/catalogs.py catalog_detail` | `catalog_prices` | `prices_for_catalog(year, number)` | ✓ WIRED | `catalogs.py:24` import, `:114` call; template `:35` renders the value. |

### Data-Flow Trace (Level 4)

| Artifact | Data variable | Source | Produces real data | Status |
|---|---|---|---|---|
| `pages/catalog_detail.html` | `prices` | `prices_for_catalog(session, 2025, 1)` → `catalog_prices` table | Yes — 941 rows for that issue, 3/3 listed products resolve | ✓ FLOWING |
| `catalogs/catalog_prices.json.gz` | 239 184 records | `export_prices(session)` over the real DB | Yes — field-for-field identical to the DB, 0 mismatches | ✓ FLOWING |
| `upsert_price_rows` | `stored` map | one `select(...)` over `CatalogPrice` | Yes — real query, not a static return | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Importer contracts hold | `uv run pytest tests/test_import_prices.py tests/test_import_master_pricelist.py -q` | `51 passed, 1 skipped in 5.52s` (skip is the pre-existing `importorskip("xlrd")` test) | ✓ PASS |
| PRICE-04 guard + tripwire + lazy-import guard | `uv run pytest ...::test_insert_missing_price_rows_filters_by_code_and_is_idempotent ...::test_neither_importer_deletes_the_whole_price_table ...::test_excel_readers_are_not_imported_at_module_level` | `4 passed` | ✓ PASS |
| Archive walk (independent re-run, read-only) | `uv run --with xlrd python scratchpad/walk.py` | 233/227/11557/237913 + all three named lists exactly as claimed; would-insert 0, would-update 0 | ✓ PASS |
| DB invariants (independent, read-only, vs. backup) | `python scratchpad/verify_db.py` | 239184/12446/233346; 0 lost, 0 backward, 1746 forward | ✓ PASS |
| `.gz` vs DB vs deleted `.json` | `python scratchpad/gzcheck.py` | 0 missing either way, 0 field mismatches, 0 old triples lost, 0 values NULLed | ✓ PASS |
| PRICE-06 coverage | `python scratchpad/price06.py` | `2025-01`: 0 → 941 rows, 0/3 → 3/3 priced | ✓ PASS |
| Full suite | `uv run pytest -q -p no:randomly` | `4 failed, 1425 passed, 13 skipped, 3 warnings in 400.07s` — all 4 in `tests/test_sync_ui.py` | ✓ PASS (known race) |
| Dependency boundary | `git diff 25c717f~1..HEAD -- pyproject.toml uv.lock` | empty; `grep xlrd pyproject.toml uv.lock` → no hits | ✓ PASS |
| Lint | `uv run ruff check` on the 4 clean files | `All checks passed!` | ✓ PASS |

### Requirements Coverage

| Requirement | Status | Evidence |
|---|---|---|
| PRICE-01 one no-delete writer | ✓ SATISFIED | Truth 1 |
| PRICE-02 both extensions + named failures | ✓ SATISFIED | Truth 2 (re-run independently) |
| PRICE-03 archive default, no `--price-dir`, empty walk aborts | ✓ SATISFIED | Truth 3 |
| PRICE-04 `--only-missing` unchanged | ✓ SATISFIED | Truth 4 |
| PRICE-05 gz transport + superset + round-trip | ✓ SATISFIED | Truth 5 |
| PRICE-06 user-visible fix + runbook | ✓ SATISFIED (data + docs); render pending human | Truth 7 |
| PRICE-07 measured invariants | ✓ SATISFIED | Truth 6 |

No orphaned requirements.

### Explicitly checked negatives (the parent's 11 points)

1. **No whole-table delete survives** — confirmed, all three sites gone, nothing equivalent replaced them (the only remaining `.delete()` in `scripts/` on a price table is none; `reset_business_data.py` is an unrelated confirm-gated wipe tool that never imports `CatalogPrice`).
2. **`session.query(Dictionary).delete()` still present** — `scripts/import_master_pricelist.py:241`. Not removed by accident.
3. **None-overwrite rule** — code at `scripts/import_prices.py:774-780` (`if incoming is not None and incoming != old`), tests in **both** files: `test_upsert_never_overwrites_a_known_value_with_none` (`tests/test_import_prices.py:562`, asserts `points` stays 3 and `name` unchanged) and `test_apply_master_import_does_not_erase_the_bonus_points_of_its_own_triple` (`tests/test_import_master_pricelist.py:230`, asserts `points == 17` while the master price still wins on `consumer_cents`). Both pass.
4. **Database numbers** — independently queried, exact match; no code lost a price, code sets compared directly against the backup.
5. **`.gz` present, `.json` gone from tree and index, not gitignored, not dockerignored** — all confirmed.
6. **`--only-missing` still by CODE, `insert_missing_price_rows` unchanged, test passes** — confirmed via diff and individual test run.
7. **openpyxl/xlrd still lazy, no dependency added** — `import openpyxl` at `:292` and `import xlrd` at `:303`, both inside `read_workbook_sheets` (defined at `:281`); `git diff 25c717f~1..HEAD -- pyproject.toml uv.lock` is empty.
8. **Boundary compliance** — `git diff 25c717f~1..HEAD -- app/services/pricing.py` touches only lines 3–10, entirely inside the module docstring; no `def`, `return` or `select(` line moved. `git diff --stat` for the three commits lists 9 paths only — no model, no Dictionary/Product/Batch/Operation/Sale service. `price_history_for_code` still defined (`app/services/pricing.py:79`) and called by no route (only `tests/test_pricing_feature.py`).
9. **DEPLOY.s1.md** — §4 (lines 85–97): new upsert semantics described AND the `import_master_pricelist.py` `--only-missing` warning **kept** with an explicit "остаётся в силе и после 260902-m9g … `dictionary` этот скрипт всё так же удаляет и пересобирает целиком". §4.1 (lines 99–159): measured numbers **239 184 / 12 446 / 233 346**, transport file `catalogs/catalog_prices.json.gz`, server command without `--only-missing` with the reason spelled out, `--only-missing` documented as still existing and still by-CODE but no longer a safety mechanism, `import_catalogs.py --only-missing` warning **kept** (lines 136–139), image-rebuild warning kept (line 159). Line 110's claim that the archive is cut by `.gitignore` checks out (`.gitignore:26 catalogs/price_lists/`).
10. **Version bump** — `1.55`.
11. **Test-suite honesty** — I ran the full suite myself: `4 failed, 1425 passed, 13 skipped`, all four in `tests/test_sync_ui.py`, matching the report exactly. `git diff --numstat 25c717f~1..HEAD -- tests/` is `88 0` and `203 0` — **pure additions, zero deleted lines**, and only those two test files were touched, so no test was deleted, skipped or weakened. Baseline reconstruction: 1442 tests collected now (`pytest --collect-only -q`), 12 new `def test` lines added ⇒ 1430 pre-task. The junit artifact `reports/260902-m9g.xml` (`tests="1442" failures="4"`) is consistent with my own run.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| — | — | No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` in any of the 7 modified files | — | Clean |
| `scripts/import_master_pricelist.py` | 131, +2 | `E501` line too long (3) | ℹ️ Info | **Pre-existing** — I ran `ruff --isolated --select E501 --line-length 100` against the file as it stood at `25c717f~1` and got the same 3 errors. Correctly left alone and disclosed rather than silently fixed. |

## Human Verification Required

### 1. `/catalogs/2025-01` renders prices

**Test:** In the operator's own already-running instance at `localhost:8000` (do **not** start a second server), open `/catalogs/2025-01` and look at the ПЦ and ДЦ columns.
**Expected:** All three listed products — `46684` «БУТЫЛКА ДЛЯ ВОДЫ», `547189` «НАБОР "СОЛНЕЧНОЕ НАСТРОЕНИЕ"», `47634` «ПОДУШКА ДЛЯ НОГ С МИШКОЙ» — show real prices instead of «—».
**Why human:** Browser rendering. Everything upstream is proven headlessly (941 price rows for the issue, 3/3 products resolve, route and template wiring read), but the rendered page was never opened. This was declared as a `<human-check>` in the PLAN.

## Recorded limitation (not a gap)

`/catalogs/{issue}` lists products from `Dictionary.catalogs`, which the master price list collapses to a single issue per code («Последний каталог»), so the page's PRODUCT list stays narrow even though price COVERAGE grew (e.g. `2025-03`: `prices_for_catalog` 12 → 880 rows, but the page still lists 12 products that were already priced). The SPEC's «Границы» forbids touching `Dictionary` at all, so this is correctly out of scope and is disclosed in the SUMMARY under "Finding worth acting on". The executor's chosen proof issue `2025-01` is the honest one — I re-measured it and it is real (0 → 941 rows, 0/3 → 3/3).

`tests/test_sync_ui.py`'s 4 failures are the documented pre-existing `sync_client._run_lock` race, reproduced in my own full run. Not this task's regression, not counted as a gap.

## Gaps Summary

None. Every code-verifiable must-have was independently re-derived from the codebase, the archive and the database rather than accepted from the SUMMARY — the archive walk, the DB invariants, the `.gz`/DB/old-`.json` set arithmetic, the PRICE-06 coverage numbers and the full test run were all re-executed here and all matched. The single outstanding item is the browser render of `/catalogs/2025-01`, which the PLAN itself deferred to the operator.

---

_Verified: 2026-09-02_
_Verifier: Claude (gsd-verifier)_
