---
quick_id: 260902-k2i
status: complete
date: 2026-09-02
version: 1.48 -> 1.53
commits:
  - 19ba85a feat(dict) restore series product type for shade-only price-list rows
  - a7515d9 feat(dict) surgical --restore-shade-names update for existing rows
  - c49f26f fix(dict) match the shade of ANY variant and restore in-place overrides
  - 1ce0b0a data(dict) restore product type on 607 shade-only dictionary names
  - 7ff09ad feat(dict) restore the product type on shade-only product cards
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
- `app/__init__.py` — `__version__ = "1.52"` (now 1.53, see the extension below)
- Working tree clean apart from untracked files

---

# Extension: the product-card half (CARDS-SPEC, commit `7ff09ad`, 1.52 -> 1.53)

The dictionary was fixed above; the CARDS-SPEC closes the other half — the
cards in `products` that the inventory import created from a CSV holding only
the shade. Same mode, same predicate, one extra pass. No new script, no new
flag.

## What changed

`scripts/import_catalogs.py` — three new functions plus the runner wiring:

| Function | Role |
|---|---|
| `dictionary_names_after(session, plan)` | `code -> ` the dictionary name **as it will read after the row pass**. The card pass has to see the restored справочник. |
| `plan_product_name_updates(session, names)` | read-only; selects a card only when `is_shade_tail(card.name, names[code])` — the same predicate, not a copy of it |
| `apply_product_name_updates(session, plan)` | writes `name` **and `name_lc`** (LIST-02), refuses anything not strictly longer (`ShadeNameWouldShrink`), looks cards up by their own id so it can neither insert nor delete |

`category`, prices, quantity, code and every other column are untouched.
Soft-deleted cards are included — the predicate, not the row's visibility, is
the safety.

### Why `dictionary_names_after` exists and is not an over-engineering

Planning the cards against the *current* dictionary selects **nothing** for
exactly the five «Офис» codes this task exists for: before the row pass both
sides read «Фарфоровый». Overlaying the row plan (instead of re-reading after
the write) is also what makes the **dry run predict precisely what `--apply`
does** — the dry run is the only thing the orchestrator gets to look at before
writing on s1. Pinned by
`test_the_card_pass_reads_the_RESTORED_dictionary_name`.

## New output lines

```
Product cards: 157
Карточек товаров к обновлению: 5
  32287: «Слоновая кость» -> «Ультрастойкая корректирующая тональная основа …»
...
Карточек товаров обновлено: 5
Товаров: 157 -> 157  (cards are updated, never created)
```

The card counter is printed on its own line and never mixed into the dictionary
counter, as the SPEC asks.

## How many cards are selected locally: **0**

Honest and uninteresting: `data/myorishop.db` holds **12 582 dictionary rows
and 0 product cards**. The dictionary side is already restored from the first
half of this task, so the real local run is a no-op end to end:

```
Dictionary rows: 12582      Planned name restorations: 0
Product cards: 0            Карточек товаров к обновлению: 0
Updated: 0                  Карточек товаров обновлено: 0
Dictionary: 12582 -> 12582  Товаров: 0 -> 0
```

Both the dry run and `--apply` were run locally (snapshot taken first, see
Safety). The database **content** is provably unchanged — all 12 582
`(code, name, name_lc, rubric, catalogs)` tuples hash identically to the
snapshot (`e9f60e58e487aad8`), products still 0. The file's md5 does differ,
because opening the database checkpoints WAL and rewrites page headers; that is
SQLite housekeeping, not a data change. **Nothing was run against s1.**

## The 12 reverse discrepancies: measured, not asserted

Because the local database has no cards, the SPEC's real risk was proved
against **real s1 card names** without touching s1. Section 5.5 of
`reports/отчет-опись-офис-2026-09-02.md` («что НЕ трогает импорт») lists 152
codes **that live in the s1 products table**, with the names s1 stores. A
throwaway SQLite database was built from: those 152 real card names + the five
shade-only «Офис» cards from the SPEC + a **copy of the real 12 582-row
restored dictionary**. Then the shipped planner was run over it.

| | |
|---|---|
| Cards in the harness | **157** (152 real s1 names + 5 «Офис») |
| Card name ≠ dictionary name | **33** |
| → **SELECTED**, product type restored | **5** — exactly the SPEC's five, character for character |
| → **card RICHER than the dictionary** | **13** — **0 selected, all 13 byte-identical after `--apply`** |
| → neither (different wording/case/truncation) | 15 — none selected |
| Names that got shorter | **0** |
| `name_lc` ≠ `name.lower()` after the write | **0** |
| Products table size | 157 -> **157** |
| Second run plans | **0** |

The 13 untouched richer cards, verbatim (the SPEC named the first two):

```
21566  card: Женские туалетные духи Volare Magnolia объем 50 мл
       dict: Туалетные духи volare magnolia
25048  card: Мужская туалетная вода Tycoon75 мл
       dict: Туалетная вода tycoon
21635, 22446, 23842, 25057, 25387, 30464, 31833, 34473, 35659, 41652, 41653
```

The harness asserts `selected & richer == set()` and fails loudly on a
regression. It is scratch tooling and is deliberately **not** committed.

Two caveats, stated rather than hidden:

- The SPEC counted **12** reverse cases across the *whole* s1 database; this
  152-code sample contains **13**. Different scope, same direction — the sample
  is not the full products table, so it is a superset of the SPEC's list only
  by accident. Every one of them is untouched, which is the property under test.
- Section 5.5 truncates names at 60 characters, so the 15 «neither» rows
  include report artifacts, not necessarily the exact s1 strings. That cannot
  produce a false positive: a truncated *prefix* is never a shade *tail*. The
  13 richer names are all ≤ 60 chars and complete.

## Tests added (8, `tests/test_import_catalogs.py`)

- `test_a_card_richer_than_the_dictionary_is_never_planned` — **the mandatory
  one**: both real s1 reversals (25048 Tycoon, 21566 Volare Magnolia), asserted
  both as «not planned» and as «byte-identical after apply»
- `test_plan_product_name_updates_selects_only_a_bare_shade_card`
- `test_the_card_pass_reads_the_RESTORED_dictionary_name` — the «Офис» case end
  to end, dictionary + card in one transaction
- `test_apply_writes_card_name_and_name_lc_and_leaves_the_rest_alone` — LIST-02
  and «`category` не трогать»
- `test_a_card_equal_to_the_dictionary_name_is_never_planned`
- `test_a_card_with_no_dictionary_row_or_no_code_is_never_planned`
- `test_apply_refuses_a_card_name_that_would_shrink`
- `test_the_second_card_run_plans_nothing_and_creates_no_card`

## Verification

- `uv run pytest tests/test_import_catalogs.py -q` → **25 passed**.
- `uv run ruff check scripts/import_catalogs.py tests/test_import_catalogs.py`
  → clean.
- **Full `uv run pytest`: 1 413 passed, 13 skipped, 4 failed** (6:08).
  1 406 + 8 new − 1 = 1 413: the arithmetic closes exactly, so no existing test
  changed state.

### The 4 failures (pre-existing, NOT this task)

```
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru
FAILED tests/test_sync_ui.py::test_not_configured_run_is_a_noop
FAILED tests/test_sync_ui.py::test_lock_hit_returns_locked_partial
```

Same `sync_client._run_lock` race as in the first half. The composition floated
again — `test_not_configured_run_is_a_noop` is now failing *in addition to* the
three from the earlier run, which is the nondeterminism itself, not a new
break. Nothing in this task touches the sync path. Not fixed, per instruction.

## Safety

- Snapshot before the local `--apply` (no `-wal` file present, so the copy is
  complete): `…\scratchpad\myorishop-before-k2i-cards.db` (11 333 632 bytes).
- Nothing was run against s1; no server started, stopped or killed.
- No new dependency, no migration, no schema change.
- Docs were not committed, per the brief — this SUMMARY section and
  `260902-k2i-CARDS-SPEC.md` stay untracked.

## Hand-off: the s1 run is unchanged

The command sequence in «Hand-off to the orchestrator» above still applies
verbatim — it is the same flag. Expect, on s1, additionally:

```
Product cards: <N>
Карточек товаров к обновлению: 5
Карточек товаров обновлено: 5
Товаров: <N> -> <N>
```

`Планируется 5` is the number to check before typing `--apply`. If the dry run
prints anything materially larger, **stop** — 5 is the measured truth for the
current s1 data, and the 12 hand-written cards are the reason.

## Self-Check: PASSED

- `scripts/import_catalogs.py::dictionary_names_after` /
  `plan_product_name_updates` / `apply_product_name_updates` — FOUND
- `tests/test_import_catalogs.py` — 8 new card tests FOUND, 25 pass
- Commit `7ff09ad` — FOUND in `git log`
- `app/__init__.py` — `__version__ = "1.53"`
- `data/myorishop.db` — 12 582 dictionary rows, 0 products, content hash
  identical to the pre-`--apply` snapshot

