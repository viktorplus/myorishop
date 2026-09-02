---
phase: 260902-m9g-xls-xlsx-catalog-prices
reviewed: 2026-09-02T12:00:00Z
depth: deep
files_reviewed: 7
files_reviewed_list:
  - app/services/pricing.py
  - scripts/import_prices.py
  - scripts/import_master_pricelist.py
  - scripts/import_catalogs.py
  - tests/test_import_prices.py
  - tests/test_import_master_pricelist.py
  - tests/test_import_catalogs.py
findings:
  critical: 3
  warning: 9
  info: 9
  total: 21
status: issues_found
---

# Quick tasks 260902-m9g + 260902-k2i: Code Review Report

**Reviewed:** 2026-09-02T12:00:00Z
**Depth:** deep
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Проверены изменения двух quick-задач: 260902-m9g («один неудаляющий писатель цен»,
коммиты 25c717f..d6301f1) и 260902-k2i («восстановление типа товара для
shade-only имён», коммиты 1ce0b0a..57830a9). Анализ сквозной: прослежены цепочки
вызовов `scripts/import_master_pricelist.py -> scripts/import_prices.upsert_price_rows`,
`scripts/import_catalogs.py -> app/services/rubrics.is_shade_tail`,
`app/services/pricing.py -> app/routes/{receipts,sales,products,dictionary}.py` и
`app/services/catalog.update_product` (аудируемый путь записи).

Главное заявленное правило задачи m9g — «источник владеет только своими
`(year, number, code)`, таблица `catalog_prices` больше никогда не очищается» —
**выполнено**: `.query(CatalogPrice).delete()` удалён из обоих импортёров,
`upsert_price_rows()` действительно единственный писатель, правило
«входящий None не затирает сохранённое» реализовано симметрично и покрыто тестами
(`tests/test_import_prices.py:562-587`, `tests/test_import_master_pricelist.py:230-253`).

Однако тот же класс дефекта, который задача закрывала для `catalog_prices`,
остался открытым рядом и был **тронут этим же коммитом**: новая функция
`apply_master_import()` по-прежнему стирает всю таблицу `dictionary` и — в
отличие от переписанного `scripts/import_prices.py` — не имеет защиты от пустого
входа (CR-01). Кроме того, единственный транспорт истории цен на сервер
(`catalog_prices.json.gz`) валидируется лишь на 3 поля из 7 (CR-02) и
перезаписывается неатомарно, хотя его контракт — «файл может только расти»
(CR-03). Пассаж переименования карточек товаров из 260902-k2i обходит
единственный аудируемый путь записи `update_product()` (WR-01).

`app/services/pricing.py` содержит только правку docstring — кода там нет,
поведение не изменилось; но объём данных, который эти хелперы читают, вырос
примерно в 35 раз, и это отражено в IN-08.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `apply_master_import()` стирает весь `dictionary` без защиты от пустого входа

**File:** `scripts/import_master_pricelist.py:235-243` (вызов — `scripts/import_master_pricelist.py:298-303`)

**Issue:** Новая функция начинается с `session.query(Dictionary).delete()` и затем
вставляет только то, что собрал `collect_price_rows()`. Если `collected` окажется
пустым словарём, справочник не восстанавливается: `build_dictionary_rows({})`
вернёт **только** override-строки (`sorted(override_only_rows(set()))` — это весь
`RUBRIC_OVERRIDES`, ~1818 записей вида «Не опознан (код 0305)»), после чего
`session.commit()` фиксирует потерю ~13 000 строк, включая имена, набранные
руками на s1.

Вход становится пустым молча и правдоподобно: заголовки на месте (проверка
`missing` пройдена), но каждая строка отбрасывается по `skipped_bad_catalog`,
если формат колонки «Последний каталог» в новой выгрузке изменился
(`parse_last_catalog()` возвращает `None` для «2021», «кат. 17», пустой ячейки и
любого значения с одним числом). Ровно этот сценарий описан как исторический
инцидент в docstring `scripts/import_prices.py:984-988`, и там же в этой задаче
добавлена защита:

```python
if not collected:
    sys.exit(f"Collected 0 price rows from {folder} — nothing written")
```

В `scripts/import_master_pricelist.py` симметричной защиты нет, хотя разрушающая
операция здесь сильнее (полное удаление таблицы, а не upsert). Статистика
`skipped_bad_catalog`, по которой оператор мог бы заметить проблему, печатается
на строках 316-322 — **после** `session.commit()`.

**Fix:**

```python
def apply_master_import(session, collected: dict[str, dict]) -> dict[str, int]:
    if not collected:
        raise ValueError("refusing to replace `dictionary` from an empty price list")
    session.query(Dictionary).delete()
    ...
```

и в `main()`, до открытия сессии, — тот же явный выход, что у соседнего скрипта:

```python
collected, stats = collect_price_rows(src)
if not collected:
    sys.exit(
        f"Collected 0 price rows from {src} "
        f"(missing code: {stats['skipped_missing_code']}, "
        f"unparsable catalog: {stats['skipped_bad_catalog']}) — nothing written"
    )
```

Дополнительно стоит завести порог деградации (например, отказ, если
`len(collected)` упал более чем на 20 % относительно текущего `count()` в
`dictionary`) — полное замещение таблицы без него остаётся односторонней
операцией без отката.

### CR-02: `validate_records()` не проверяет денежные поля — в `catalog_prices` может попасть float/строка

**File:** `scripts/import_prices.py:640-657` (потребитель — `scripts/import_prices.py:694-708`, `716-794`)

**Issue:** Docstring обещает «Refuse malformed input loudly», но проверяются
только `code` (строка) и `year`/`number` (int). Поля `consumer_cents`,
`consultant_cents`, `points`, `name` не валидируются вовсе, а `build_price_rows()`
переносит их «verbatim — no coercion» в модель. Для `.gz`-транспорта, который по
docstring является единственным способом доставить историю цен на сервер, это
означает:

* `"consumer_cents": 599.5` -> SQLite сохранит REAL в колонке с INTEGER-аффинити
  (преобразование не lossless), то есть деньги окажутся float — прямой запрет
  проекта («Store prices as `Integer` minor units», CLAUDE.md);
* `"consumer_cents": "не указано"` -> SQLite сохранит TEXT в INTEGER-колонке;
  далее `reference_prices_for_code()` вернёт эту строку в маршруты
  (`app/routes/receipts.py:80`, `app/routes/sales.py:126`), где она попадёт в
  `format_cents()` и уронит страницу;
* тот же мусор через `upsert_price_rows()` перезапишет корректные целые значения
  (`incoming is not None and incoming != old` -> True), то есть повреждение
  распространяется на уже импортированные строки.

На PostgreSQL (заявленная цель миграции) те же данные дадут не тихую порчу, а
отказ транзакции целиком. Тесты закрепляют пробел: параметризация
`tests/test_import_prices.py:111-121` проверяет только `code`/`year`/`number`.

**Fix:**

```python
    for i, record in enumerate(records):
        ...
        for field in ("consumer_cents", "consultant_cents", "points"):
            value = record[field]
            if value is None:
                continue
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                sys.exit(f"{source}: record {i} has a non-integer {field} {value!r}")
        if record["name"] is not None and not isinstance(record["name"], str):
            sys.exit(f"{source}: record {i} has a non-string name {record['name']!r}")
```

и добавить в `tests/test_import_prices.py` кейсы `{**PLAIN_ROW, "consumer_cents": 599.5}`
и `{**PLAIN_ROW, "points": "3"}`.

### CR-03: неатомарная перезапись накопительных файлов — окно, в котором «файл, который может только расти», обнуляется

**File:** `scripts/import_prices.py:842-853`; тот же дефект — `scripts/import_prices.py:538-541` и `scripts/import_catalogs.py:349-360`

**Issue:** `write_export()` открывает целевой файл на запись напрямую:

```python
    with _open_export(dest, "wt", newline="\n") as handle:
        handle.write(serialize_export(merged))
```

`open("wt")` (и `gzip.open("wt")`) **усекает файл в момент открытия**, а
`serialize_export(merged)` вычисляется уже после этого — она строит список из
230 000 `json.dumps(...)` и склеивает строку ~41.7 МБ. Любое исключение в этот
момент (MemoryError, ENOSPC, прерывание процесса, для `.gz` — незавершённый
поток deflate) оставляет на диске пустой или битый файл, а прежнее содержимое
уже уничтожено. Для `.gz` это финально: при следующем запуске `load_export()`
корректно завершится с «Export file is not a readable gzip», но восстановить
нечего.

Это ломает именно тот инвариант, ради которого написаны `merge_price_export()` и
проверка `if stats["after"] < stats["before"]`: логическая защита от усечения
есть, физической — нет. Файл накопительный, то есть содержит строки, которых нет
в локальной БД (выгрузки с других машин), — они невосстановимы. Тот же паттерн в
`write_overrides()` (`app/services/rubric_overrides.json` — отслеживаемый в git
файл, читаемый приложением при импорте `app/services/rubrics.py`) и в
`scripts/import_catalogs.write_export()` (`catalogs/products.json`).

**Fix:** писать во временный файл в том же каталоге и заменять через
`os.replace()` (атомарно и на Windows, и на POSIX):

```python
import os
from tempfile import NamedTemporaryFile

def _atomic_write(dest: Path, payload: str, *, newline: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        with _open_export(tmp, "wt", newline=newline) as handle:
            handle.write(payload)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
```

и вызывать `_atomic_write(dest, serialize_export(merged), newline="\n")` —
сериализация завершается до того, как что-либо касается `dest`.

## Warnings

### WR-01: переименование карточек товаров идёт мимо единственного аудируемого пути записи

**File:** `scripts/import_catalogs.py:262-286` (вызов — `scripts/import_catalogs.py:398-400`)

**Issue:** `apply_product_name_updates()` мутирует `Product.name` / `Product.name_lc`
напрямую. В приложении единственный путь изменения карточки —
`app/services/catalog.py:162-300` `update_product()`, docstring которого прямо
говорит: «Update a product; audit every change through the single write path»,
и D-30 требует одну операцию `product_edited` со списком изменённых неценовых
полей. Скрипт не пишет ни одной записи в append-only журнал операций, хотя
предназначен для неконтролируемого запуска на боевом s1 и меняет
пользовательскую сущность (не helper-таблицу D-24). После прогона в истории не
будет ни следа того, что имена карточек изменились, и откатить точечно нечего.

Прецедент в этом же каталоге обратный: `scripts/import_inventory_receipt.py:56`
работает через сервис `register_receipt`, а не через прямую запись в модель.

Риска расхождения при синхронизации нет (сервер authoritative, клиентские копии
дискардятся в `merge._upsert_reference`), и `Product.updated_at` обновится
благодаря `onupdate` — проблема именно в отсутствии аудита.

**Fix:** записывать операцию для каждой переименованной карточки в той же
транзакции, например переиспользовав существующий писатель журнала:

```python
from app.services.operations import record_operation  # проверить точное имя/сигнатуру

        product.name = new
        product.name_lc = new.lower()
        record_operation(
            session,
            kind="product_edited",
            product_id=product.id,
            payload={"fields": ["name"], "old": item["old"], "new": new,
                     "source": "import_catalogs --restore-shade-names"},
            commit=False,
        )
```

Если сознательно решено журнал не трогать, это должно быть зафиксировано как
явное решение в docstring режима, а не оставаться умолчанием.

### WR-02: два источника с разной семантикой цены пишут в один и тот же triple — побеждает тот, кто запустился последним

**File:** `scripts/import_master_pricelist.py:208-227` и `scripts/import_prices.py:716-794`

**Issue:** Мастер-прайс кладёт **текущие** ДЦ/ПЦ в triple
`(year, number)` из колонки «Последний каталог» (docstring, строки 9-11), а архив
кладёт в тот же triple **историческую** цену того выпуска каталога. Правило
слияния — «поле меняется, если входящее не None и отличается» — не различает
источники, поэтому для кода, чей последний каталог 17-2021, значение
`consumer_cents` зависит от того, что запускали последним:
`import_master_pricelist.py` (сегодняшняя цена) или
`import_prices.py --from-export` (цена 2021 года).

Это видно пользователю: `latest_price_for_code()` -> `reference_prices_for_code()`
подставляет ДЦ/ПЦ в форму нового товара и в приёмку
(`app/routes/receipts.py:80,140`, `app/routes/products.py:160,203,277`,
`app/services/receipts.py:289`). Порядок запуска импортёров нигде не
зафиксирован, то есть подставляемая цена недетерминирована между машинами.

**Fix:** либо не позволять мастер-прайсу занимать «чужой» исторический triple
(писать его в отдельный синтетический выпуск, например `(9999, 0)`, и учитывать
это в сортировке `latest_price_for_code`), либо добавить в `catalog_prices`
колонку-источник и правило приоритета в `upsert_price_rows()` вместо
«последний победил». Как минимум — зафиксировать обязательный порядок запуска в
docstring обоих скриптов и в `docs/`.

### WR-03: дубликаты выпусков схлопываются по порядку сортировки имени — побеждает резервная копия / `_calc`

**File:** `scripts/import_prices.py:244-261` (сортировка — `scripts/import_prices.py:322-335`)

**Issue:** `collect_from_archive()` пишет `collected[(year, number, code)] = data`
без проверки, было ли значение занято, а файлы обходятся в порядке
`sorted(key=lambda p: p.name)`. Для пары `01-2026.xls` / `01-2026_ (1).xls`
побеждает второй (`'.'` = 0x2E < `'_'` = 0x5F), для `03_2024.xls` /
`03_2024_calc.xls` — второй. То есть при коллизии выигрывает не канонический
файл, а копия или калькуляторный вариант, где цены могли быть изменены рукой.
Docstring сам называет суффиксы `_calc` и `(1)` как реальные, а отчёт
(`report`) о коллизиях ничего не сообщает — расхождение цен между копиями
пройдёт молча.

*Needs verification:* содержимое `_calc`-файлов отличается от канонических — это
проверяется на машине с архивом (`catalogs/price_lists/`), здесь архива нет.

**Fix:** предпочитать канонический файл и сообщать о конфликтах:

```python
    report["duplicate_issue"] = []
    ...
        for code, data in priced.items():
            key = (year, number, code)
            if key in collected and collected[key] != data:
                report["duplicate_issue"].append(f"{path.name} -> {year}-{number} {code}")
                continue          # первый (канонический) файл выигрывает
            collected[key] = data
```

и/или явно исключать `_calc`/`(N)` в `price_list_files()`.

### WR-04: строки с текстовой или отсутствующей ПЦ отбрасываются молча, без счётчика

**File:** `scripts/import_prices.py:181-211` (правило — `scripts/import_prices.py:199-201`, `164-171`)

**Issue:** `_cents()` принимает только `int`/`float`; ячейка, сохранённая в Excel
как текст («599», «599,00»), даёт `None`, и вся строка отбрасывается как
«section header / blank row». Никакого счётчика нет: `report` называет файл,
только если он не дал **ни одной** строки (`no_price_column`). Файл со
смешанным форматированием потеряет часть кодов без единого следа в выводе, а
именно полнота архива — цель этой задачи.

**Fix:** принимать числовые строки и считать отбракованные строки:

```python
def _cents(value) -> int | None:
    if isinstance(value, str):
        value = value.strip().replace("\xa0", "").replace(" ", "")
        if not value:
            return None
    elif not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        cents = to_cents(str(value))
    except ValueError:
        return None
    return cents if cents > 0 else None
```

и возвращать из `collect_prices_from_sheets()` число строк с кодом, но без цены,
складывая его в `report["rows_without_price"]`.

### WR-05: входной пакет не дедуплицируется по triple — IntegrityError вместо внятной ошибки

**File:** `scripts/import_prices.py:761-794` и `scripts/import_prices.py:797-809`

**Issue:** `upsert_price_rows()` относит запись к `fresh`, если её triple нет в
снимке `stored`. Две записи с одинаковым `(year, number, code)` в одном
`records` обе попадут в `fresh` и обе будут вставлены -> нарушение
`uq_catalog_prices_year_number_code` -> `IntegrityError` с трейсбеком и откатом
всей транзакции (для 230 000 строк — потеря всего прогона). Тот же путь у
`insert_missing_price_rows()`. Файл, собранный `write_export()`, дубликатов не
содержит, но `--from-export` принимает любой файл, а `validate_records()` этот
инвариант не проверяет.

**Fix:** дедуплицировать в `validate_records()` (последняя запись выигрывает, как
и в остальном коде) либо явно отказывать:

```python
    seen: dict[tuple, int] = {}
    for i, record in enumerate(records):
        ...
        key = (record["year"], record["number"], record["code"])
        if key in seen:
            sys.exit(f"{source}: record {i} duplicates record {seen[key]} for triple {key}")
        seen[key] = i
```

### WR-06: `collect_price_rows()` — StopIteration на пустом листе и утечка дескриптора на `sys.exit`

**File:** `scripts/import_master_pricelist.py:95-108` (и `143`)

**Issue:** Три дефекта в одной функции:
1. `header_row = next(ws.iter_rows(values_only=True, max_row=1))` на пустом листе
   бросает `StopIteration` — сырой трейсбек вместо сообщения в стиле остальных
   проверок;
2. оба `sys.exit(...)` (строки 97 и 108) происходят при открытом
   `openpyxl.load_workbook(..., read_only=True)`; `wb.close()` есть только на
   строке 143, то есть на путях ошибки дескриптор файла не закрывается (на
   Windows это блокирует последующее переименование/удаление файла);
3. статистика пропусков печатается в `main()` уже после `session.commit()`
   (строки 316-322) — оператор узнаёт о деградации после записи (см. также CR-01).

**Fix:**

```python
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    try:
        if SHEET_NAME not in wb.sheetnames:
            sys.exit(f"Sheet {SHEET_NAME!r} not found in {src} (sheets: {wb.sheetnames})")
        ws = wb[SHEET_NAME]
        header_row = next(ws.iter_rows(values_only=True, max_row=1), None)
        if header_row is None:
            sys.exit(f"Sheet {SHEET_NAME!r} in {src} is empty")
        ...
    finally:
        wb.close()
```

и печатать статистику до `commit()` (или считать её частью защиты из CR-01).

### WR-07: `load_export()` ловит не все реальные отказы транспорта

**File:** `scripts/import_prices.py:676-691`

**Issue:** Перехвачены `json.JSONDecodeError`, `gzip.BadGzipFile`, `EOFError`.
Не перехвачены `UnicodeDecodeError` (файл `.json`, оказавшийся бинарным — самый
вероятный вид повреждения при передаче) и `OSError` (нет прав, оборванный
сетевой диск). Docstring обещает, что «4.7 MB arriving over the wire» упадёт
громко и по имени, — для этих двух случаев обещание не выполняется, будет сырой
трейсбек.

**Fix:**

```python
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        sys.exit(f"Export file is not valid UTF-8 JSON: {path} ({exc})")
    except (gzip.BadGzipFile, EOFError) as exc:
        sys.exit(f"Export file is not a readable gzip: {path} ({exc.__class__.__name__}: {exc})")
    except OSError as exc:
        sys.exit(f"Export file cannot be read: {path} ({exc})")
```

### WR-08: тест-ловушка на «не удалять таблицу цен» ловит одну строковую форму из многих

**File:** `tests/test_import_prices.py:699-712`

**Issue:** Гейт, который должен предотвратить регрессию главного правила задачи,
ищет ровно `.query(CatalogPrice).delete()`. Мимо него молча проходят
`session.execute(delete(CatalogPrice))` (идиома SQLAlchemy 2.0, которую проект
предпочитает — см. `select()` во всех новых функциях),
`session.query(CatalogPrice).filter(...).delete()`, `Base.metadata` truncate и
любой `DELETE` через `text()`. Кроме того, `_uncommented()` убирает только
строки-комментарии `#`, но не docstring-и, поэтому гейт хрупок в обе стороны.

**Fix:** проверять AST на любой вызов `.delete()`/`delete(...)`, где встречается
имя `CatalogPrice`, а не подстроку:

```python
def _delete_calls(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            src = ast.unparse(node)
            if "CatalogPrice" in src and (".delete()" in src or src.startswith("delete(")):
                hits.append(src)
    return hits

for script in (SCRIPT, MASTER_SCRIPT):
    assert _delete_calls(script) == [], script.name
```

Аналогичный гейт стоит завести и для `Dictionary` в
`scripts/import_master_pricelist.py`, но там удаление намеренное — гейт должен
проверять наличие защиты из CR-01, а не отсутствие вызова.

### WR-09: основной путь `import_catalogs.py` не валидирует форму `products.json`, хотя путь экспорта валидирует

**File:** `scripts/import_catalogs.py:457-462` (сравнить с `scripts/import_catalogs.py:303-313`)

**Issue:** `data = json.loads(src.read_text(encoding="utf-8"))` используется сразу:
`len(data)`, затем `data.items()` и `payload.get("name")`. Для JSON-массива,
строки или словаря со строковыми значениями это `AttributeError`/`TypeError` с
трейсбеком. Соседняя `read_previous_export()` ровно эти проверки делает и
отказывается перезаписывать файл с внятным сообщением — асимметрия
несогласованна, а входной файл приходит по сети/из чужой машины наравне с
экспортом.

**Fix:**

```python
    data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        sys.exit(f"Source is not a JSON object: {src}")
    bad = [c for c, p in data.items() if not isinstance(p, dict)]
    if bad:
        sys.exit(f"{src}: {len(bad)} entries are not objects (first: {bad[:3]})")
```

## Info

### IN-01: `price_history_for_code()` — мёртвый экспорт

**File:** `app/services/pricing.py:79-90`
**Issue:** Функция не вызывается ни одним маршрутом и ни одним сервисом (только
`tests/test_pricing_feature.py:61`); docstring этой задачи сам это фиксирует
(«still called by no route»). Мёртвый код, который теперь ещё и возвращает
200+ строк вместо одной.
**Fix:** удалить вместе с тестом или задокументировать как публичный API для
карточки товара с указанием, когда он будет подключён.

### IN-02: `build_catalog_price_rows()` после рефакторинга используется только тестами

**File:** `scripts/import_master_pricelist.py:230-232`
**Issue:** Продуктовый путь перешёл на `build_catalog_price_records()` +
`upsert_price_rows()`; обёртка осталась живой только из-за
`tests/test_import_master_pricelist.py:94-127`. Тест проверяет форму, которую
продакшн больше не использует.
**Fix:** переписать тест на `build_catalog_price_records()` и удалить обёртку.

### IN-03: магические числа вместо констант

**File:** `scripts/import_prices.py:139` (`rows[:8]`), `scripts/import_prices.py:203` (`[:200]` при наличии `MAX_NAME = 200`), `scripts/import_prices.py:716` (`chunk: int = 5000`), `scripts/import_master_pricelist.py:131,171,189` (`[:200]`)
**Issue:** Длина имени продублирована литералом `200` в четырёх местах при
существующей константе `MAX_NAME`; глубина поиска заголовка `8` не объяснена.
**Fix:** использовать `MAX_NAME` везде, вынести `_HEADER_SCAN_ROWS = 8`.

### IN-04: guard-и по имени файла обходятся передачей значения по умолчанию

**File:** `scripts/import_catalogs.py:438-439` и `scripts/import_catalogs.py:449`
**Issue:** `if args.file != DEFAULT_FILE: sys.exit(...)` не срабатывает, если
пользователь явно напишет `--file catalogs/products.json`. Защита проверяет
строку, а не факт «аргумент задан».
**Fix:** `parser.add_argument("--file", default=None, ...)` и проверять
`args.file is not None`, подставляя `DEFAULT_FILE` уже после guard-ов.

### IN-05: мелкие несоответствия стиля записи

**File:** `scripts/import_prices.py:805` и `scripts/import_prices.py:595-598`
**Issue:** `{code for code in session.scalars(...)}` — тождественное включение
(достаточно `set(...)`). Файл `--report` пишется без `newline="\n"`, тогда как
для экспортов LF задан явно «так, чтобы байты совпадали на Windows и Linux» —
отчёт получит CRLF на Windows.
**Fix:** `existing = set(session.scalars(...))`; при записи отчёта передать
`newline="\n"` через `Path.open`, а не `write_text`.

### IN-06: пересчитанная рубрика для существующей override-записи молча теряется, но попадает в отчёт

**File:** `scripts/import_prices.py:497-512` (сравнить с `scripts/import_prices.py:515-529`)
**Issue:** Если `prior` существует, но его `rubric` не входит в `RUBRICS`, ветка
`else` считает новую рубрику и увеличивает `stats["updated"]`; `merge_overrides()`
при этом по контракту меняет **только** `name`, поэтому новая рубрика
отбрасывается. Гистограмма «Rubrics: …» (строка 590) печатает значения из
`fresh`, то есть для таких кодов сообщает не то, что записано в файл.
**Fix:** либо считать рубрику только для новых кодов, либо строить гистограмму по
`merged`, а не по `fresh`.

### IN-07: длинные строки и нечитаемый вложенный тернарник

**File:** `scripts/import_master_pricelist.py:124`, `:131`, `:3`, `:294`
**Issue:** Четыре строки длиннее 100 символов при `line-length = 100` в
`pyproject.toml` (`[tool.ruff]`, правило E501 входит в выбранный набор `E`).
Строка 124 — тернарник с двойным индексированием по русскому ключу, читается с
трудом.
*Needs verification:* в `app/` уже есть 33 строки длиннее 100 символов, то есть
`ruff check` может быть красным по всему репозиторию; проверить одной командой —
`uv run ruff check scripts/ app/`.
**Fix:**

```python
        raw_catalog = row[colmap["Последний каталог"]] if colmap["Последний каталог"] < len(row) else None
        cat = parse_last_catalog(raw_catalog)
```

вынести доступ к ячейке в маленький хелпер (как `_cell()` в
`scripts/import_prices.py:174-178`) — заодно уйдёт четырёхкратное дублирование
паттерна `row[colmap[X]] if colmap[X] < len(row) else None`.

### IN-08: чтение справочника стало на два порядка тяжелее — та же реализация на 35-кратном объёме

**File:** `app/services/pricing.py:38-62` (вызов — `app/routes/dictionary.py:50`)
**Issue:** `latest_prices_for_codes()` загружает **все** исторические строки для
кодов страницы и оставляет по одной; после этой задачи в таблице не 6856 строк, а
230 000+ (об этом прямо сказано в новом docstring: «These helpers never changed;
only the data they read did»). Для страницы из 50 кодов это до нескольких тысяч
ORM-объектов на один рендер вместо 50.
Формально производительность вне рамок v1-ревью — фиксируется потому, что рост
объёма данных вызван именно этим изменением.
**Fix:** оставить выбор последнего выпуска базе — например, коррелированный
подзапрос по `max(year, number)` или оконная функция (портируемо и в SQLite 3.25+,
и в PostgreSQL).

### IN-09: тихие приведения типов в парсере строк прайса

**File:** `scripts/import_prices.py:208` и `scripts/import_prices.py:164-171`
**Issue:** `int(points)` молча отбрасывает дробную часть (ББ «3.5» станет 3);
`isinstance(value, (int, float))` пропускает `bool` (`True` -> 1 балл), поскольку
`bool` — подкласс `int`.
**Fix:** `if isinstance(points, bool) or not isinstance(points, (int, float)): ...`
и округлять явно (`round()`), либо отбрасывать нецелые значения в отчёт.

---

_Reviewed: 2026-09-02T12:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: deep_
