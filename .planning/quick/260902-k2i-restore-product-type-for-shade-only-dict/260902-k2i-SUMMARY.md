---
quick_id: 260902-k2i
status: complete
date: 2026-09-02
version: 1.48 -> 1.52
commits:
  - 19ba85a feat(dict) restore series product type for shade-only price-list rows
  - a7515d9 feat(dict) surgical --restore-shade-names update for existing rows
  - c49f26f fix(dict) match the shade of ANY variant and restore in-place overrides
  - 1ce0b0a data(dict) restore product type on 607 shade-only dictionary names
key-files:
  created: []
  modified:
    - app/services/rubrics.py
    - app/services/rubric_overrides.json
    - scripts/import_prices.py
    - scripts/import_catalogs.py
    - tests/test_rubrics.py
    - tests/test_import_prices.py
    - tests/test_import_catalogs.py
    - catalogs/products.json
    - app/__init__.py
---

# Quick task 260902-k2i: Restore the product type on shade-only dictionary names

607 справочник rows carried nothing but a colour («Фарфоровый»). The product type
is now inherited from the series header of the 232 readable Oriflame price lists,
so those rows name a product again and are findable by name.

## Counts

| | |
|---|---|
| Price lists scanned | **233** (118 `.xls` + 115 `.xlsx`) |
| Unreadable | **1** — `12-2013.xls` (`IndexError`, the known corrupt file) |
| Shade codes found in the archive | **2 690** |
| …present in `products.json` | 2 690 (absent: 0) |
| …rejected, the name already carries a product type | 2 083 |
| …rejected, longer than 200 chars | 0 |
| Shade rows dropped for lack of a series type | 0 |
| **SELECTED (records restored)** | **607** — exactly the SPEC's number |
|  → name-only rewrite of an existing override | 552 |
|  → appended as a new override | 55 |
| `rubric_overrides.json` | 1 818 → **1 873** |
| Dictionary rows updated | **607** |
| Dictionary row count | 12 582 → **12 582** (the mode cannot insert) |
| `products.json` | 12 582 codes, **607 names changed**, +607/−607 lines |
| Names that got shorter | **0** |
| Rubrics improved | 19 (all of them newly appended codes) |

## The five «Офис» inventory codes, before → after

| Code | Before | After |
|---|---|---|
| 32287 | Слоновая кость | Ультрастойкая корректирующая тональная основа spf 30 the one everlasting - слоновая кость |
| 33155 | Фарфоровый | Увлажняющая тональная основа the one aqua boost - фарфоровый |
| 33157 | Розовый нюд | Увлажняющая тональная основа the one aqua boost - розовый нюд |
| 33158 | Слоновая кость | Увлажняющая тональная основа the one aqua boost - слоновая кость |
| 33159 | Естественный беж | Увлажняющая тональная основа the one aqua boost - естественный беж |

Real-path check through `app.services.dictionary.list_entries` against the live
database: searching «aqua boost» now returns the whole 33154–33159 series (7 rows);
before, only the header row 33154 could match. `name_lc`, `rubric` and `catalogs`
are all correct on the updated rows.

## Deviations from the plan — READ THIS

Two rules in the PLAN produced **23** restored names instead of 607. Both were
defects, both were measured against the real archive before anything was written,
and both are fixed in commit `c49f26f`.

### 1. [Rule 1 — Bug] Detection compared against ONE «best» variant

The plan had `build_shade_overrides` build the restored name with
`pick_full_name(counter)` — the single longest-type variant — and then test the
предикат against it. This is precisely the methodology the SPEC forbids by name
(«Осторожно с методикой подсчёта»): one code is a series header in one price list
and a shade row in another, so the best variant's shade is often not the shade the
справочник kept.

| Rule | Codes selected |
|---|---|
| Best-variant only (the plan as written) | 337 |
| **Shade of AT LEAST ONE variant (the SPEC's rule)** | **607** |

Fix: new `restore_full_name(counter, current)` filters the variants down to those
whose shade IS the current name, then applies the normalisation rule (longest type,
ties → most frequent) among those. Restoring from a shade-matched variant is also
what guarantees the new name ends with the old one, so a name can never shrink or
lose its colour. Pinned by `test_restore_full_name_matches_the_shade_of_any_variant_not_the_best_one`.

### 2. [Rule 1 — Bug] «Skip codes that already have an override» excluded 552 of the 607

The plan required the write to be a **pure append** and the selection to skip any
code already present in `rubric_overrides.json`. Measured against the real data,
that assumption is false:

- **552 of the 607** already have an override entry **whose `name` is that very
  bare shade** — earlier quick tasks (260721-oti, 260902-1d1 and friends) wrote
  them that way.
- All five «Офис» codes are in that group, which is why the first run printed
  «— not selected —» for every one of them.
- `resolve_name` makes the override win everywhere, so leaving those entries alone
  would not merely skip them: the restoration would be **silently undone on the
  next import**. There is no other mechanism — the override is the name.

The SPEC's *goal* («вся работа этой задачи — исправление 607 названий», with the
five «Офис» codes as its worked example) and its *mechanism assumption*
(«существующие 1 818 не трогаем») cannot both hold. The goal was taken as
authoritative, and the narrowest possible mechanism was used — the same
name-field-only merge quick task 260721-oti already used on this file:

- not one existing key **moves** (verified: first 1 818 keys identical in order);
- not one existing **`conf`** or **`rubric`** changes (verified: 0 changed);
- only **`name`** is replaced, and only where `is_shade_tail(old, new)` holds —
  i.e. the old name was exactly the bare shade and the new one is strictly longer
  and ends with it (verified: 0 exceptions, 0 shortened);
- byte form preserved: `indent=1`, CRLF, no trailing newline;
- the 55 genuinely new codes are appended in sorted order, after everything.

The resulting diff is `+827 / −552` lines: 552 rewritten `name` lines plus 55 new
entries × 5 lines. Nothing else in the file moved.

**This is the one thing to review.** If in-place correction of those 552 entries is
not wanted, revert `1ce0b0a` — but the task then restores only 55 names and none of
the five «Офис» codes.

### 3. [Rule 3 — Blocking] `plan_shade_name_updates` resolves through the passed table

The plan specified `new = resolve_name(code, row.name)[:200]`. `resolve_name` reads
the module-level `RUBRIC_OVERRIDES`, so an injected test overrides dict would never
supply a name and every such test would plan nothing. The function applies
`resolve_name`'s rule to the table it is given instead (override name wins when
non-empty). Behaviour on the production path is identical.

### 4. Commit count and version numbers

The plan called for three commits ending at `1.51`. The rule correction above is
shipped code, not data, so it is its own commit — four commits, `1.48 → 1.52`.

## Verification

- `uv run pytest tests/test_import_prices.py tests/test_rubrics.py tests/test_import_catalogs.py`
  → **61 passed**.
- `uv run --with xlrd pytest tests/test_import_prices.py -q -rs` → the real-archive
  proof **RUNS** (not skipped) against `01-2018.xls` + `01-2019.xlsx` and rebuilds
  33155–33159. Without xlrd it skips, and the plain suite shows the skip.
- `uv run ruff check` clean on all touched files. The 14 pre-existing `E501`s in
  `app/services/rubrics.py` are unchanged — verified identical at `HEAD` before the
  task, and my additions add none.
- No dialect-specific SQL in `import_catalogs.py` (comment-stripped grep gate).
- Overrides file: 1 818 pre-existing keys keep value-position, `conf`, `rubric`;
  0 shortened names; CRLF/indent=1/no trailing newline; every rubric in `RUBRICS`.
- `products.json`: same 12 582 codes, 607 changed, 0 shortened, 0 `catalogs` touched.
- Second run of `--restore-shade-names` plans **0**; second run of `--restore-shades`
  selects **0**.
- **Full `uv run pytest`: 1 406 passed, 13 skipped, 3 failed.**

### The 3 failures (pre-existing, NOT this task)

```
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru
FAILED tests/test_sync_ui.py::test_lock_hit_returns_locked_partial
```

Documented as the `sync_client._run_lock` race held by the lifespan auto-sync
thread. Run in isolation they still fail but with a **different** subset
(`test_not_configured_run_is_a_noop` appears instead of
`test_sync_run_returns_oob_partial`), which confirms the nondeterminism rather than
a regression. The brief expected 4; the count varies 3–4 for that reason. Nothing
in this task touches the sync path. Not fixed, per instruction.

## Safety

- Database snapshot taken BEFORE the first write (WAL was 0 bytes, so the copy is
  complete):
  `C:\Users\Admin\AppData\Local\Temp\claude\E--dev-myorishop\635c65c2-c1d9-49f2-8da8-e4f133d0981c\scratchpad\myorishop-before-k2i.db`
  (11 137 024 bytes, 12 582 dictionary rows).
- Nothing was run against s1. No server was started, stopped or killed.
- No new runtime dependency. `xlrd` was reached only through
  `uv run --with xlrd`; it is in neither `pyproject.toml` nor `uv.lock`, and an AST
  test now pins that neither `xlrd` nor `openpyxl` is imported at module level.
- `reports/shade_names.json` (the 607 selected entries), plus the scratch
  `reports/anyvariant.json` and `reports/restored_all.json` from the diagnosis, are
  left on disk **uncommitted**. `reports/` is untracked but NOT gitignored — do not
  `git add .` in this repo without checking.

## Hand-off to the orchestrator (do NOT run from this task)

**1 — s1 needs an image rebuild, not just `git pull`.** `rubric_overrides.json` and
`catalogs/products.json` are COPY-baked into the `ori-app` image, not volume-mounted
(see `deploy/DEPLOY.s1.md` and the s1-image-baked-code memory note):

```bash
ssh root@s1
cd /opt/ori && git pull
docker compose up -d --build ori-app
```

**2 — then, inside the container, dry run first:**

```bash
docker compose exec ori-app python scripts/import_catalogs.py --restore-shade-names
docker compose exec ori-app python scripts/import_catalogs.py --restore-shade-names --apply
docker compose exec ori-app python scripts/import_catalogs.py --restore-shade-names   # must plan 0
```

Expected: `Planned name restorations: 607` (fewer if the server dictionary is a
thinner subset — it plans only rows it actually has), `Dictionary: N -> N`
unchanged, the 4 hand-written server names untouched (they cannot satisfy
`is_shade_tail`), and the third command a no-op.

**3 — never run `import_catalogs.py --file …` or `import_master_pricelist.py`
without `--only-missing` on s1.** A full replace still erases the hand-written
names. `--restore-shade-names` is the only supported way to change an existing name
there: it updates and cannot insert, `--only-missing` inserts and cannot update.

**4 — expected sync side effect, and it is the wanted one.** `dictionary` is a pull
kind upserted BY CODE (quick 260721-ebn), server-wins — so once s1 is updated the
restored names propagate to every client on the next sync.

**5 — `catalogs/price_lists/` still holds 118 `.xls` files the price import cannot
read** (its glob is `*.xlsx`-only). This task added the reader but deliberately did
not rewire the price path; feeding those into `catalog_prices` is a separate task,
related to `.planning/todos/pending/2026-08-31-price-lists-backfill.md`.

## Observations, not acted on

- **33154 keeps the abbreviated spelling** «Увлажняющая тон. основа the one aqua
  boost - ванильный». It is the series *header*, not a shade row, so it already
  carries a product type and is out of scope by the SPEC's «не менять названия, где
  тип товара уже есть». Its siblings now read «тональная основа» while it reads
  «тон. основа» — cosmetically inconsistent, correct by the rule.
- **A Latin `C` leads «Cтойкая краска для волос»** in ~10 restored names. That is
  the spelling in the source price list, carried verbatim. Not introduced here; a
  cleanup would be its own task.
- The 5 codes that exist in the price lists but not in the справочник (`0`, `1`,
  `2`, `3`, `4` — promo text in the code column) were **not** added, per the SPEC.

## Self-Check: PASSED

- `app/services/rubric_overrides.json` — FOUND, 1 873 entries
- `catalogs/products.json` — FOUND, 12 582 codes
- `scripts/import_prices.py::restore_shades` / `restore_full_name` — FOUND
- `scripts/import_catalogs.py::restore_shade_names` / `apply_shade_name_updates` — FOUND
- `app/services/rubrics.py::is_shade_tail` — FOUND
- Commits `19ba85a`, `a7515d9`, `c49f26f`, `1ce0b0a` — all FOUND in `git log`
- `app/__init__.py` — `__version__ = "1.52"`
- Working tree clean apart from untracked files
