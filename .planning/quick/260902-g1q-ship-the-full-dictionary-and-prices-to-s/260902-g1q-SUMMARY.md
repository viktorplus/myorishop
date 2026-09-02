---
quick_id: 260902-g1q
subsystem: catalogs / reference data
tags: [dictionary, catalog_prices, import, export, deploy, s1]
requires:
  - app.services.rubrics (resolve_name / resolve_rubric)
  - app.models (Dictionary, CatalogPrice)
provides:
  - scripts/import_catalogs.py --export / --only-missing, rubric+name_lc on every written row
  - scripts/import_prices.py --export / --from-export / --only-missing, lazy openpyxl
  - catalogs/products.json (12 582 codes), catalogs/catalog_prices.json (15 798 rows)
  - deploy/DEPLOY.s1.md §4.1 — the additive backfill sequence for the server
affects:
  - the s1 deploy runbook (an image rebuild is now required to carry the exports)
tech-stack:
  added: []
  patterns:
    - "accumulative export: the target file is merged into, never replaced — it can only grow"
    - "additive import (--only-missing): an existing row is never read from or written to"
    - "lazy openpyxl import so a dev-dependency-free image can still run --from-export"
key-files:
  created:
    - tests/test_import_catalogs.py
    - tests/test_import_prices.py
    - catalogs/products.json
    - catalogs/catalog_prices.json
    - .planning/quick/260902-g1q-ship-the-full-dictionary-and-prices-to-s/260902-g1q-REHEARSAL.md
  modified:
    - scripts/import_catalogs.py
    - scripts/import_prices.py
    - deploy/DEPLOY.s1.md
    - app/__init__.py
decisions:
  - "The export is accumulative, not replacing (SPEC): a code present in the file but absent from the database survives, so a thinned-out local base cannot impoverish the accumulated file."
  - "The additive price filter is CODE-level, not (year, number, code)-level: adding this file's history rows for a code the server already prices from the master list would shadow it in every latest-price lookup."
  - "openpyxl moved to a function-local import — the image is built with `uv sync --frozen --no-dev`, so a module-level import made the script unimportable exactly where --from-export must run."
  - "The rehearsal seeds the 4 hand-typed s1 names on top of the master price list, reproducing s1's exact 6 894 / 6 856 shape (the 6 894 − 6 890 = 4 gap IS those four codes)."
metrics:
  duration: ~55 min
  completed: 2026-09-02
  tasks: 3
  commits: 3
---

# Quick 260902-g1q: полный справочник и цены на s1 — Summary

Оба импортёра расширены на месте так, что полный локальный справочник
(12 582 кода) и полная история цен (15 798 строк) переносятся на s1 через две
компактные закоммиченные выгрузки — строго аддитивно, не трогая ни одной уже
существующей строки на сервере. Заодно закрыт скрытый баг: строки, которые
писал `import_catalogs.py`, не имели ни `rubric`, ни `name_lc` и потому были
невидимы для фильтра по названию.

## Что сделано

### 1. `scripts/import_catalogs.py` (коммит `bbc1910`, версия 1.42)

- `build_dictionary_row()` — общий строитель строки, заполняет `rubric`
  (CAT-06, через `resolve_rubric` по СЫРОМУ имени) и `name_lc` (LIST-02,
  `name.lower()`), имя проходит через `resolve_name` и обрезается до 200.
  Ровно та же логика, что в `import_master_pricelist.build_dictionary_rows`.
- `apply_dictionary_import(session, data, *, only_missing=False)` — цикл
  upsert вынесен из `main()`, транзакцией владеет вызывающий. Путь обновления
  тоже проставляет `name`/`name_lc`/`rubric` (SPEC 1.1). При
  `only_missing=True` существующий код считается в новый счётчик `present` и
  его строка не читается и не пишется вовсе.
- `export_dictionary()` + `--export FILE` — выгрузка в собственный формат
  скрипта (`{code: {"name", "catalogs"}}`), отсортировано по коду, UTF-8, LF.
- `--export` не сочетается с `--only-missing` и с не-дефолтным `--file`
  (usage error), строка `Done. created=… updated=… skipped=…` не изменилась.

### 2. `scripts/import_prices.py` (коммит `0061e79`, версия 1.43)

- `collect_from_xlsx()` — существующий обход книг вынесен как есть; `import
  openpyxl` переехал внутрь функции (dev-зависимость, образ собирается
  `uv sync --frozen --no-dev`).
- `export_prices` / `serialize_export` / `--export FILE` — компактный JSON:
  одна строка = одна запись, 7 полей, порядок `(year, number, code)`.
- `load_export` — валидация ДО любого обращения к БД: не список, не объект,
  не тот набор ключей, не-строковый `code`, не-целые `year`/`number` — каждая
  ошибка называет индекс записи.
- `build_price_rows` / `insert_missing_price_rows` — аддитивная вставка с
  фильтром **по коду**; ничего не удаляет, не обновляет и не коммитит.
- `--only-missing` без `--from-export` отказывается работать (защита от
  скатывания в разрушительный xlsx-путь), `--export` с `--from-export` — тоже.

### 3. Выгрузки и репетиция (коммит `fa8c8d4`)

| Файл | Записей | Размер |
|------|---------|--------|
| `catalogs/products.json` | 12 582 кода | **2 156 801 байт** (2.06 МиБ) |
| `catalogs/catalog_prices.json` | 15 798 строк / 12 372 кода | **3 030 412 байт** (2.89 МиБ) |

Обе не игнорируются ни git, ни docker (`git check-ignore` → exit 1 на обеих;
`.dockerignore` режет только `catalogs/*.pdf` и `catalogs/price_lists/`).
`.gitignore`/`.dockerignore` не менялись.

## Накопительный экспорт (требование SPEC, которого не было в плане)

`--export` **сливается** с целевым файлом, а не замещает его: коды/строки,
которые есть в файле, но которых нет в базе, сохраняются. Реализовано как
`merge_dictionary_export` / `merge_price_export` (ключ цен —
`(year, number, code)`, тот же UNIQUE-кортеж), плюс жёсткая проверка
`after >= before` перед записью. Печатается `было / добавлено / обновлено /
стало`.

Фактический вывод первой выгрузки (файлов не было):

```
Export: E:\dev\myorishop\catalogs\products.json
Было: 0  добавлено: 12582  обновлено: 0  стало: 12582
Entries: 12582  size: 2156801 bytes

Export: E:\dev\myorishop\catalogs\catalog_prices.json
Было: 0  добавлено: 15798  обновлено: 0  стало: 15798
Rows: 15798  codes: 12372  size: 3030412 bytes
```

Тесты на правило: `test_merge_export_keeps_codes_the_database_no_longer_has`,
`test_write_export_into_an_existing_file_preserves_a_foreign_code` (и пара
близнецов в тестах цен) — экспорт в файл с посторонним кодом сохраняет этот
код, а повторный экспорт из ПУСТОЙ базы не уменьшает файл.

## Репетиция на изолированной scratch-базе

Полный протокол — `260902-g1q-REHEARSAL.md`. Коротко:

- жёсткий гейт: `settings.database_url` должен быть ровно
  `sqlite:///<scratch>/myorishop.db`, иначе прогон падает до первой записи;
  один `export MYORISHOP_DATA_DIR` на весь скрипт;
- засев формы s1: мастер-прайс (6 890 / 6 856) + 4 ручных названия = **6 894 /
  6 856** — точная форма сервера (разрыв 6 894 − 6 890 это и есть те четыре кода);
- аддитивная пара команд: `dictionary 6894 → 12582` (**created=5688**, ровно
  разрыв из SPEC), `catalog_prices 6856 → 12372` (inserted 5516);
- **18 PASS**: ни одно существующее название не изменилось, все четыре
  конфликтных кода сохранили новое серверное написание (при том что
  `products.json` предлагает для них СТАРОЕ), `rubric` и `name_lc` заполнены
  на всех 12 582 строках, дублей `(year, number, code)` нет, ожидаемое число
  строк цен посчитано из самого файла, повторный прогон вставляет 0.

База оператора открывалась только на чтение и после всего читается как
12 582 / 15 798. s1 не трогался ни разу. Scratch-каталог удалён.

## Обновление `deploy/DEPLOY.s1.md` (требование SPEC)

Добавлен раздел **4.1 «Полный справочник — обязательные два шага после
мастер-прайса»**: две аддитивные команды в контейнере, явное указание, что
источник — закоммиченные `catalogs/products.json` и
`catalogs/catalog_prices.json`, а НЕ `catalogs/price_lists/` (118 МБ, на
сервере их нет и не будет), предупреждение «только с `--only-missing`» и
блок про обновление самих выгрузок с пояснением про накопительность.

## Проверки

- `uv run pytest -q` → **1373 passed, 4 failed, 12 skipped** (420 с).
  Все 4 падения — известные `tests/test_sync_ui.py`
  (`test_sync_run_returns_oob_partial`, `test_offline_run_returns_200_ru`,
  `test_not_configured_run_is_a_noop`, `test_lock_hit_returns_locked_partial`),
  предсуществующие, к задаче не относятся, не чинились. Новых падений нет.
  Артефакты: `reports/quick-260902-g1q.xml` / `.sha` / `.dirty`.
- 23 новых теста (9 + 14), `uv run ruff check` чист на всех четырёх файлах.
- AST-гейты: все требуемые функции есть в обоих скриптах; `openpyxl` не
  импортируется на уровне модуля.
- Диалект-специфичного SQL в обоих скриптах: 0 совпадений
  (`sqlalchemy.dialects` / `INSERT OR` / `on_conflict` / `strftime`) — s1 на
  PostgreSQL.
- `--only-missing` без `--from-export` → non-zero exit с внятным сообщением.
- `app/__init__.py`: 1.41 → 1.42 → 1.43.

## Отклонения от плана

**1. [SPEC > план] Экспорт сделан накопительным.**
План описывал `--export` как простую выгрузку; SPEC (п. 2 «Что из этого
следует») требует слияние с существующим файлом. Реализовано слияние +
печать `было/добавлено/обновлено/стало` + гарантия неуменьшения + 4 теста.

**2. [SPEC > план] Обновлён `deploy/DEPLOY.s1.md`.**
Файла не было в `files_modified` плана; SPEC п. 3 требует раздел 4. Добавлен
подраздел 4.1.

**3. [Rule 2] В репетицию досеяны 4 ручных серверных названия.**
План предлагал засеять только мастер-прайс (6 890 / 6 856) при реальных s1
6 894 / 6 856. Разрыв в 4 строки — ровно те четыре конфликтных кода, которых
нет ни в одном прайс-листе. Без них главное правило SPEC («побеждает
последнее написание») в репетиции не проверялось бы вообще. Досев сделан в
scratch-скрипте, форма стала точной, и добавлены 8 PASS-проверок.

**4. [минор] `read_previous_export` / `write_export` выделены отдельно** от
`_run_export`, чтобы файловый тест накопительности не открывал `SessionLocal`
и не касался рабочей базы.

## Известные заглушки

Нет.

## Что дальше — оператору/оркестратору (НЕ выполнялось)

1. **Нужна пересборка образа, `git pull` мало:** `catalogs/*.json`
   `COPY`-запечены в `ori-app`, поэтому
   `docker compose -f docker-compose.prod.yml up -d --build`.
2. **Аддитивная последовательность в контейнере, в этом порядке:**
   `python scripts/import_catalogs.py --only-missing --file catalogs/products.json`,
   затем `python scripts/import_prices.py --from-export catalogs/catalog_prices.json --only-missing`.
   Ожидаемо: dictionary 6 894 → 12 582 (+5 688), catalog_prices 6 856 → 12 372
   (+5 516). Обе аддитивны и идемпотентны. `uv run --with openpyxl` не нужен.
3. **Никогда без `--only-missing`** против s1 — ни эти две, ни
   `import_master_pricelist.py`.
4. **Ожидаемый и желаемый побочный эффект синка:** клиент тянет строки
   `dictionary` с сервера и апсертит ПО КОДУ (quick 260721-ebn), server-wins —
   после заливки 4 более новых серверных названия заменят локальные старые.
   `catalog_prices` не является sync-kind, JSON-выгрузка — его единственный транспорт.
5. **`30464` сохраняет опечатку «Туалетна вода»** на s1 — вне рамок (SPEC §3).
6. **`catalogs/products.json` снова настоящий бэкап** — перезапускать
   `--export` после правок справочника; выгрузка накопительная, файл только растёт.

## Self-Check: PASSED

Все 8 заявленных файлов на диске, все 3 коммита (`bbc1910`, `0061e79`,
`fa8c8d4`) в истории, `app.__version__ == "1.43"`.
