# Репетиция аддитивной заливки на изолированной scratch-базе

Прогон выполнен **на выброшенной базе**, воспроизводящей форму s1. База
оператора `data/myorishop.db` открывалась только на чтение (для `--export`),
s1 не трогался вообще — ни чтения, ни записи, ни одного сетевого вызова.

Изоляция: один `export MYORISHOP_DATA_DIR=<scratch>/data` в начале скрипта,
унаследованный всеми дочерними процессами, плюс жёсткий гейт перед каждым
пишущим шагом.

```
GATE OK: every mutating step below targets the scratch database only
expected: sqlite:///…\scratchpad\rehearsal\data\myorishop.db
actual  : sqlite:///…\scratchpad\rehearsal\data\myorishop.db
```

## Как засеяна форма s1

| Шаг | Результат |
|-----|-----------|
| `alembic upgrade head` | схема до 0026 |
| `scripts/import_master_pricelist.py` (full replace — безопасен ТОЛЬКО здесь) | dictionary 0 → 6 890, catalog_prices 0 → 6 856 |
| 4 названия, вписанные руками на s1 (34473, 31833, 41652, 30464) | dictionary 6 890 → **6 894** |

Разрыв 6 894 − 6 890 = 4 — это ровно те четыре кода из SPEC §3: их нет ни в
одном прайс-листе, они были вписаны через `/dictionary/missing` в августе
(quick 260814-je0). Итог засева — **6 894 / 6 856**, то есть форма s1 один в один.

## Счётчики до и после

| Таблица | До (форма s1) | После | Дельта |
|---------|---------------|-------|--------|
| `dictionary` | 6 894 | **12 582** | +5 688 |
| `catalog_prices` | 6 856 | **12 372** | +5 516 |

`+5 688` совпадает с разрывом, посчитанным в SPEC, до единицы.

Вывод команд:

```
Source: catalogs/products.json  (12582 entries)
Done. created=5688 updated=0 skipped=0
Mode: --only-missing (additive, nothing existing touched); already present: 6894
Dictionary: 6894 -> 12582

Source: catalogs/catalog_prices.json  (15798 rows, 12372 codes)
Mode: --only-missing (additive, nothing deleted)
Inserted: 5516 (skipped, code already present: 10282)
CatalogPrice: 6856 -> 12372
```

## Проверки

```
PASS: dictionary 6890 -> 12582 (= the 12582 codes of catalogs/products.json)
PASS: all 6894 pre-existing dictionary names are byte-identical after --only-missing (0 overwritten)
PASS: conflict code 34473: products.json offers the older spelling «Туалетная вода sunkiss garden»
PASS: conflict code 34473 kept the newer hand-typed name «Женская туалетная вода Sunkiss Garden объем 50 мл»
PASS: conflict code 31833: products.json offers the older spelling «Туалетная вода david beckham classic»
PASS: conflict code 31833 kept the newer hand-typed name «Мужская туалетная вода David Beckham Classic 60 мл»
PASS: conflict code 41652: products.json offers the older spelling «Женская туалетная вода full moon»
PASS: conflict code 41652 kept the newer hand-typed name «Туалетная вода Full Moon [Фул Мун] Орифлейм Oriflame 30 мл»
PASS: conflict code 30464: products.json offers the older spelling «Туалетная вода kick off»
PASS: conflict code 30464 kept the newer hand-typed name «Туалетна вода Kick Off 30мл Oriflame мужская»
PASS: rubric is filled on all 12582 dictionary rows
PASS: name_lc == name.lower() on all 12582 dictionary rows
PASS: no duplicate (year, number, code) in catalog_prices
PASS: all 6856 pre-existing price rows are still there
PASS: catalog_prices 6856 -> 12372 (= 6856 + the export rows whose code the server lacked, computed not hardcoded)
PASS: second run changed nothing: dictionary 12582, catalog_prices 12372
PASS: second import_catalogs --only-missing created 0 rows
PASS: second import_prices --only-missing inserted 0 rows
```

Ожидаемое число строк `catalog_prices` считалось из самого
`catalogs/catalog_prices.json` (6 856 + строки с кодами, которых у сервера
нет), а не задавалось константой.

Первая строка PASS печатает «6890» — это счётчик, снятый до досева четырёх
ручных названий; фактический старт репетиции 6 894, как в таблице выше.

## Идемпотентность

Обе команды прогнаны второй раз: `created=0`, `Inserted: 0`, счётчики не
изменились (12 582 / 12 372). Повторный запуск безопасен.

## Точная последовательность для s1

На сервере эти же две команды выполняются **внутри контейнера**, после
пересборки образа (`catalogs/*.json` `COPY`-запечены в образ — одного
`git pull` мало):

```bash
docker compose -f docker-compose.prod.yml up -d --build

docker compose -f docker-compose.prod.yml exec ori-app \
  python scripts/import_catalogs.py --only-missing --file catalogs/products.json

docker compose -f docker-compose.prod.yml exec ori-app \
  python scripts/import_prices.py --from-export catalogs/catalog_prices.json --only-missing
```

`uv run --with openpyxl` здесь НЕ нужен: openpyxl импортируется лениво и на
этих двух путях не используется вовсе.

⚠ Обе команды обязаны идти с `--only-missing`. Без него `--from-export`
удаляет все существующие строки, а дефолтный путь `import_catalogs.py`
перезаписывает названия — на сервере это стёрло бы четыре ручных названия и
все коды вне мастер-прайса.

Scratch-каталог удалён после прогона.
