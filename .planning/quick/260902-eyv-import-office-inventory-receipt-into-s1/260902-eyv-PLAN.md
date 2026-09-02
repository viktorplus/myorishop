---
quick_id: 260902-eyv
type: execute
autonomous: true
files_modified:
  - scripts/import_inventory_receipt.py
  - tests/test_import_inventory_receipt.py
  - app/__init__.py
must_haves:
  truths:
    - "Запуск `uv run python scripts/import_inventory_receipt.py` без флагов печатает план прихода и НЕ пишет в базу ничего: products/batches/operations после сухого прогона имеют ровно те же счётчики, что и до него."
    - "Сухой прогон на локальной базе находит склад «офис» по имени «Офис» (регистр не важен, только активные склады) и печатает: 414 строк прочитано, 1 пропущена (строка 313, код «???»), 413 к оприходованию, 332 новых карточки товара, 44 кода без цены в catalog_prices."
    - "Повторяющиеся внутри файла пары (код + срок) в сухом прогоне считаются один раз как новая партия, остальные — как доливы, поэтому числа сухого прогона совпадают с тем, что реально сделал бы --apply."
    - "Строка, для которой в складе назначения уже есть партия того же товара с тем же сроком (включая случай «срок пустой» = NULL), идёт доливом в эту партию; если срок другой — заводится новая партия; товара нет в базе — карточка создаётся сервисом."
    - "Для кода, у которого уже есть активная карточка товара, цены НЕ передаются: после импорта в журнале нет ни одной операции price_change, cost_cents/sale_cents карточки не изменились."
    - "Код без строки в catalog_prices импортируется с пустыми ценами: products.cost_cents/sale_cents и batches.price_cents/cost_cents остаются NULL, а не 0."
    - "Полка строки попадает в location новой партии и дописывается в comment существующей партии при доливе, без дублирования уже присутствующей пометки."
    - "Ошибка валидации от register_receipt останавливает импорт с указанием номера строки CSV и текста ошибки; уже записанные строки не откатываются, скрипт печатает, сколько строк успело записаться, и выходит с ненулевым кодом."
    - "Скрипт не делает ни одного прямого INSERT в products/batches/operations — единственная прямая запись в базу это batch.comment на пути долива."
  artifacts:
    - path: "scripts/import_inventory_receipt.py"
      provides: "Диалект-независимый импорт описи как прихода; сухой прогон по умолчанию, запись только по --apply"
      min_lines: 150
    - path: "tests/test_import_inventory_receipt.py"
      provides: "Исполняемый контракт правил 1-7 из SPEC на временных CSV (никогда не читает реальный reports/*.csv)"
      min_lines: 180
    - path: "app/__init__.py"
      provides: "__version__ = \"1.39\""
      contains: "1.39"
  key_links:
    - from: "scripts/import_inventory_receipt.py"
      to: "app.services.receipts.register_receipt"
      via: "единственный разрешённый путь записи прихода"
      pattern: "register_receipt\\("
    - from: "scripts/import_inventory_receipt.py"
      to: "app.services.batches.active_warehouses"
      via: "поиск склада назначения по имени (Python-side casefold)"
      pattern: "active_warehouses\\("
    - from: "scripts/import_inventory_receipt.py"
      to: "app.services.pricing.latest_price_for_code"
      via: "ДЦ/ПЦ для новых карточек"
      pattern: "latest_price_for_code\\("
    - from: "scripts/import_inventory_receipt.py"
      to: "app.core.format_cents"
      via: "cents -> строка с запятой, которую принимает to_cents"
      pattern: "format_cents\\("
---

<objective>
Опись склада «Офис» (`reports/оприходование-офис-2026-08-31.csv`, 414 строк
данных) нужно оприходовать как приход — не как инвентаризацию: всё, что уже
лежит на складе, остаётся, опись добавляется сверху. Утверждённые оператором
правила лежат в `260902-eyv-SPEC.md` и являются источником истины — этот план
их не пересматривает и не смягчает.

Ручной ввод 413 строк через форму прихода нереален, а прямой INSERT в
`products`/`batches`/`operations` запрещён архитектурой: журнал append-only,
`Product.quantity`/`Batch.quantity` — кэшированные проекции
`SUM(operations.qty_delta)`, которые поддерживает только
`app.services.ledger.record_operation`. Поэтому нужен скрипт, который читает
CSV и вызывает `app.services.receipts.register_receipt` построчно — ровно то,
что сделал бы оператор в форме.

Ключевая опасность: `--apply` необратим (журнал append-only, повторный запуск
добавит количество второй раз). Поэтому режим по умолчанию — сухой прогон,
который ничего не пишет и печатает предсказание, совпадающее с тем, что сделал
бы `--apply`.

Purpose: оператор получает 2204 шт. на складе «Офис» одним прогоном, с
партиями, разложенными по срокам годности и полкам, без задвоения существующих
остатков и без перетирания цен уже заведённых карточек.

Output: `scripts/import_inventory_receipt.py` (сухой прогон по умолчанию,
`--apply` / `--file` / `--warehouse`), `tests/test_import_inventory_receipt.py`
(9 тестов на временных CSV), бамп `__version__` 1.38 -> 1.39.

**Границы этой задачи:** скрипт НЕ запускается с `--apply` ни против
`data/myorishop.db`, ни против s1. Доказательство корректности — юнит-тесты
плюс сухой прогон против локальной базы. Развёртывания на s1 в этой задаче нет.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@.planning/quick/260902-eyv-import-office-inventory-receipt-into-s1/260902-eyv-SPEC.md
@app/models.py
@app/core.py
@app/services/receipts.py
@app/services/ledger.py
@app/services/batches.py
@app/services/pricing.py
@scripts/reset_business_data.py
@scripts/load_test_data.py
@tests/conftest.py
@tests/test_reset_business_data.py
</context>

<interfaces>
Всё ниже проверено чтением кода — не перепроверять, не «уточнять» гуглом.

**Путь записи (единственный разрешённый):**
```
app.services.receipts.register_receipt(
    session, *, code, name, qty_raw, cost_raw, sale_raw,
    warehouse_id, batch_choice, expiry_raw="", location_raw="", comment_raw="",
) -> tuple[dict | None, dict[str, str]]
```
- успех: `({"product": Product, "operation": Operation, "batch": Batch}, {})`;
  ошибка: `(None, {"поле": "русское сообщение"})` и НИЧЕГО не записано.
- `batch_choice` = `"new"` (создать партию) или `<batch.id>` (долив).
- сама коммитит транзакцию (`session.commit()` внутри) — после успешного
  вызова следующий `resolve` уже видит созданную карточку/партию в базе.
- `expiry_raw` парсится ТОЛЬКО на пути `"new"`; на пути долива игнорируется.
- `location_raw`/`comment_raw` применяются ТОЛЬКО на пути `"new"` — на пути
  долива молча игнорируются (receipts.py:202-234). Это и есть причина
  правила 3 в SPEC.
- для существующей карточки непустые `cost_raw`/`sale_raw` пишут операцию
  `price_change` и ПЕРЕТИРАЮТ цену карточки (receipts.py:168-194). Пустая
  строка -> `None` -> цена карточки не трогается (PD-8).
- имя обязательно всегда (валидация на receipts.py:107 идёт до поиска
  карточки), хотя для существующей карточки оно затем игнорируется (PD-9).

**Чтение:**
- `app.services.batches.active_warehouses(session) -> list[Warehouse]` —
  только `deleted_at IS NULL`, отсортированы по имени.
- `app.services.pricing.latest_price_for_code(session, code) -> CatalogPrice | None`
  — поля `consultant_cents` (ДЦ) и `consumer_cents` (ПЦ), оба nullable.
- `app.core.format_cents(cents) -> str` — `1250 -> "12,50"`;
  `app.core.to_cents` (внутри `parse_optional_cents`) принимает запятую.
  Это готовая пара cents -> строка, свой форматтер не писать.

**Модели:**
- `Batch.expiry: str | None` — ISO `yyyy-mm-dd` текстом; в SQLAlchemy сравнение
  с NULL пишется `Batch.expiry.is_(None)`, а `== None` работать не будет.
- `Batch.comment` — `String(200)`, `Batch.location` — `String(100)`.
- `batches` НЕ append-only: триггеры `*_no_update`/`*_no_delete` стоят только
  на `operations` и `cash_movements` (app/db.py `APPEND_ONLY_TRIGGERS`),
  поэтому `batch.comment = ...` — легальная запись.
- `Product.cost_cents`/`sale_cents`, `Batch.price_cents`/`cost_cents` nullable
  — пустая цена допустима моделью.

**Авторство:** `record_operation` берёт автора из `author_fields()`, который вне
HTTP-контекста возвращает `(None, settings.operator_name)` (ledger.py:105-109).
Никакого пользователя подставлять не нужно и нельзя.

**Cyrillic-фолдинг:** SQLite `lower()`/`LIKE` не сворачивает кириллицу (D-27,
повторяется по всему коду). Поэтому поиск склада по имени без учёта регистра
делается ТОЛЬКО в Python поверх `active_warehouses(session)`, никогда через
`func.lower()` в SQL.

**Факты о файле (проверены, не пересчитывать «на всякий случай»):**
- 415 физических строк = 1 заголовок + 414 строк данных;
- заголовок ровно:
  `Полка;Код;Наименование (из справочника);Кол-во;Срок годности;Срок (как в записи);Комментарий;Файл-источник;Проверить`
- пустого кода нет ни в одной строке; единственная пропускаемая строка —
  физическая строка 313 (`59;???;;17;...`), у неё же единственное пустое
  наименование; итого 413 строк к оприходованию;
- строки 338/339 — собственные коды `0001` «Барьер» и `0002` «Соковыжималка»,
  импортируются как обычные строки (правило 6);
- кодировка UTF-8 BOM, разделитель `;`, кавычки экранированы по RFC 4180
  (строка 15: `"...лица "" Шведский spa салон """`) — штатный модуль `csv`
  разбирает это сам;
- `reports/` НЕ в .gitignore, но и НЕ в индексе git — файл untracked. Тесты
  обязаны его игнорировать и работать на своих CSV в `tmp_path`.
</interfaces>

<design>
Читать этот раздел ДО написания кода — здесь зафиксированы решения, которые
иначе будут приняты по-разному в тестах и в скрипте.

**Публичная поверхность модуля** (её фиксируют тесты задачи 1):

```
CSV_DEFAULT = "reports/оприходование-офис-2026-08-31.csv"
WAREHOUSE_DEFAULT = "Офис"
SKIP_CODES = frozenset({"???"})        # плюс пустой код
COMMENT_MAX_LEN = 200                  # = Batch.comment String(200)

@dataclass(frozen=True)
class Row:
    line_no: int          # ФИЗИЧЕСКИЙ номер строки CSV (заголовок = 1)
    shelf: str
    code: str
    name: str
    qty: str
    expiry: str
    skip_reason: str | None   # None = строку берём

@dataclass(frozen=True)
class Decision:
    action: str               # "new_batch" | "topup"
    product_exists: bool
    batch_id: str | None      # None для "new_batch"
    cost_raw: str             # "" если карточка уже есть или цены нет
    sale_raw: str
    shelf_label: str          # "полка 47" или ""
    warnings: list[str]

@dataclass
class Pending:                # предсказание сухого прогона внутри одного файла
    new_codes: set[str]
    new_batches: set[tuple[str, str | None]]   # (code, expiry)

read_rows(path) -> list[Row]
find_warehouse(session, name) -> Warehouse | None
resolve_row(session, row, warehouse_id, pending) -> Decision
run_import(session, rows, warehouse, *, apply) -> dict     # summary
main() -> None
```

**D-1. Одна функция разрешения для обоих режимов.** `resolve_row` — read-only,
её вызывают и сухой прогон, и `--apply`. Расхождение «предсказали одно,
записали другое» структурно невозможно.

**D-2. Предсказание повторов внутри файла.** В сухом прогоне `run_import` после
каждой строки дописывает `pending.new_codes`/`pending.new_batches`; `resolve_row`
считает код существующим, если он есть в базе ИЛИ в `pending.new_codes`, и
считает партию существующей, если она есть в базе ИЛИ пара (код, срок) есть в
`pending.new_batches`. В режиме `--apply` `pending` создаётся пустым и НИКОГДА
не пополняется: `register_receipt` коммитит сам, поэтому истина — база.
Без этого сухой прогон насчитал бы ~413 новых карточек вместо 332.

**D-3. Поиск партии-цели.** Прямой запрос, НЕ `open_batches` (та фильтрует
`quantity > 0` и на партии с нулевым остатком завела бы дубль):
```
select(Batch).where(
    Batch.product_id == product.id,
    Batch.warehouse_id == warehouse_id,
    Batch.expiry.is_(None) if expiry is None else Batch.expiry == expiry,
).order_by(Batch.created_at.asc())
```
Берём первую (самую старую) — детерминированный выбор при нескольких
совпадениях; порядок повторяет тай-брейк `open_batches`.
Если найденная партия имеет `is_legacy == 1`, поведение НЕ меняем (SPEC
такого исключения не вводит), но добавляем предупреждение в
`Decision.warnings`: `«строка N: долив в legacy-партию <id> (остаток до
внедрения партий)»`. Оператор увидит это в сухом прогоне и решит сам.

**D-4. Цены (правило 4).** Если карточка кода уже существует (в базе или в
`pending.new_codes`) -> `cost_raw = sale_raw = ""`. Иначе
`latest_price_for_code`: `consultant_cents -> cost_raw`,
`consumer_cents -> sale_raw`, каждое через `format_cents`, `None -> ""`.
Счётчик «без цены» считает РАЗЛИЧНЫЕ новые коды, у которых обе строки пустые.

**D-5. Полка (правило 3).** `shelf_label = f"полка {row.shelf.strip()}"`, а при
пустой полке — `""`. Путь `"new"`: передаём в `location_raw`. Путь долива:
после успешного `register_receipt` дописываем в `batch.comment` и коммитим
отдельным `session.commit()`.
Проверка «не дублируя»: разбить существующий `batch.comment` по `"; "`,
сравнить `strip()`-нутые части на РАВЕНСТВО с `shelf_label`. Подстрокой не
проверять — «полка 4» является подстрокой «полка 47».
Склейка: `batch.comment = shelf_label`, если было пусто, иначе
`f"{existing}; {shelf_label}"`. Если результат длиннее `COMMENT_MAX_LEN` —
НЕ писать, а добавить предупреждение `«строка N: comment партии <id>
переполнен, полка не дописана»` (на PostgreSQL String(200) жёсткий).

**D-6. Что НЕ передаём.** `comment_raw` в `register_receipt` не передаётся
никогда (SPEC его не требует; колонка «Комментарий» в CSV дублирует полку либо
содержит пометки составителя). `expiry_raw` передаём всегда как есть — на пути
долива сервис его игнорирует, и это согласовано, потому что срок уже
использован для выбора партии.

**D-7. Остановка на ошибке.** `run_import` НЕ вызывает `sys.exit`. При
`(None, errors)` от `register_receipt` он заполняет в summary
`stopped_at_line`/`error` и возвращается; уже записанные строки не
откатываются (журнал append-only). Код возврата выбирает `main()`.

**D-8. Печать цели.** Печатать `f"PostgreSQL: {engine.url.host}/{engine.url.database}"`
либо `f"SQLite file: {settings.db_path}"`. `engine.url` целиком не печатать
никогда — там пароль. Это осознанное 4-строчное повторение приватного
`_target_label` из `reset_business_data.py`: импортировать приватное имя из
соседнего скрипта или выносить его в общий модуль (рефакторинг shipped-кода)
хуже, чем повторить четыре строки; несущая часть — запрет печати пароля.

**D-9. Неподдерживаемый диалект.** Как в `reset_business_data.py`:
`engine.dialect.name` вне `("sqlite", "postgresql")` -> `RuntimeError`.
Никакого SQLite-специфичного SQL в скрипте нет вообще.

**Формат вывода сухого прогона** (фиксируется здесь, не импровизировать):
```
Целевая база: SQLite file: <путь>
Файл: <путь к csv>
Склад назначения: «офис»
Режим: СУХОЙ ПРОГОН — записи не будет.

Прочитано строк: 414
Пропущено: 1 (строка 313: код «???»)
К оприходованию: 413 строк, 2204 шт.

Новых карточек товара: 332
Новых партий: <N>
Доливов в существующие партии: <M>
Кодов без цены в catalog_prices: 44

ВНИМАНИЕ: импорт НЕ идемпотентен — повторный запуск с --apply добавит
количество ещё раз.

Предупреждения:
  <строки warnings, блок печатается только если они есть>
```
</design>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: RED — исполняемый контракт импортёра на временных CSV</name>
  <files>tests/test_import_inventory_receipt.py</files>
  <behavior>
    Все 9 тестов работают на фикстурах `session`/`warehouse` из
    tests/conftest.py и на CSV, который тест сам пишет в `tmp_path`
    (`encoding="utf-8-sig"`, разделитель `;`, заголовок — ровно тот, что
    указан в `<interfaces>`). Реальный `reports/оприходование-офис-*.csv`
    не читается ни одним тестом: он untracked, в CI его нет.

    Хелпер `_write_csv(tmp_path, rows)` принимает список кортежей
    `(shelf, code, name, qty, expiry)` и дописывает 4 пустые хвостовые
    колонки, чтобы ширина совпадала с реальным файлом.

    1. test_sentinel_and_empty_codes_are_skipped — CSV из 3 строк: обычная,
       `???` с пустым именем, с пустым кодом. `read_rows` возвращает 3 `Row`,
       у двух последних `skip_reason` не None, у первой None; `line_no` равны
       2, 3, 4 (заголовок = 1).
    2. test_new_code_creates_card_batch_and_receipt — пустая база + фикстура
       `warehouse`. Одна строка (полка 47, код 32503, кол-во 2, срок пустой).
       После `run_import(..., apply=True)`: ровно 1 `Product` с этим кодом,
       ровно 1 `Batch` в этом складе с `location == "полка 47"` и
       `expiry is None`, `batch.quantity == 2`, `product.quantity == 2`,
       ровно 1 операция типа `receipt`.
    3. test_same_expiry_tops_up_the_existing_batch — две строки одного кода с
       ОДИНАКОВЫМ сроком `2021-02-28`, обе по 1 шт. Итог: ровно 1 `Batch`,
       `batch.quantity == 2`, 2 операции `receipt`, обе с этим `batch_id`.
    4. test_different_expiry_creates_a_second_batch — две строки одного кода
       со сроками `2021-02-28` и `2021-08-31`. Итог: ровно 2 `Batch` у этого
       товара, у каждой quantity == 1, `Product.quantity == 2`, карточка
       создана один раз (ровно 1 операция `product_created`).
    5. test_shelf_is_appended_to_comment_on_topup_without_duplicating — три
       строки одного кода с одним сроком: полки 47, 47 и 4. После импорта
       `batch.comment` содержит «полка 47» ровно один раз и «полка 4» ровно
       один раз (проверять по split("; "), а не подстрокой), а `location`
       партии остался «полка 47» от рождения.
    6. test_missing_catalog_price_leaves_prices_null — `catalog_prices` пуст.
       После импорта `product.cost_cents is None`, `product.sale_cents is None`,
       `batch.price_cents is None`, `batch.cost_cents is None` (не 0), и в
       summary `codes_without_price == 1`.
    7. test_existing_card_price_is_never_overwritten — заранее создать
       `Product(code=..., cost_cents=100, sale_cents=200)` и `CatalogPrice`
       того же кода с ДРУГИМИ `consultant_cents`/`consumer_cents`. После
       импорта: цены карточки не изменились И в журнале НОЛЬ операций
       `price_change`. Плюс зеркальный случай: для НОВОГО кода с
       `CatalogPrice(consultant_cents=12345, consumer_cents=45600)` карточка
       получает ровно эти cents (проверка, что `format_cents` -> `to_cents`
       ходит без потерь через запятую).
    8. test_warehouse_lookup_is_case_insensitive_and_active_only — склад с
       именем «офис» находится по «Офис» и по «  ОФИС  »; склад с
       `deleted_at` не находится; несуществующее имя -> `None`.
    9. test_dry_run_writes_nothing_and_predicts_intra_file_repeats — две
       строки НОВОГО кода с одинаковым сроком плюс одна строка того же кода
       с другим сроком. `run_import(..., apply=False)` возвращает
       `new_products == 1`, `new_batches == 2`, `topups == 1`, а счётчики
       `Product`/`Batch`/`Operation` в базе остаются 0.
  </behavior>
  <action>
Создать `tests/test_import_inventory_receipt.py` по контракту выше.

Модуль `scripts.import_inventory_receipt` импортировать ВНУТРИ тел тестов
(`from scripts.import_inventory_receipt import read_rows, run_import, ...`),
а не на уровне модуля — идиома RED-скаффолдов проекта (30-01/31-01/32-01):
сбор всего набора тестов остаётся зелёным, пока падают только эти тесты.
`scripts/` не пакет и `__init__.py` не заводить — `tests/test_reset_business_data.py`
уже импортирует `scripts.reset_business_data` этим же способом.

Модульная докстрока: одна фраза о том, что это исполняемый контракт правил
1-7 из `260902-eyv-SPEC.md`, и явное «реальный CSV из reports/ не читается».

Коммит: `test(quick-260902-eyv): failing contract for the office-inventory importer`.
НЕ пушить — в этом коммите тесты красные по построению.
  </action>
  <verify>
    <automated>uv run pytest tests/test_import_inventory_receipt.py -q 2>&1 | tail -20  # ожидаемо 9 failed (ModuleNotFoundError внутри тел тестов), 0 errors на этапе collection</automated>
    <automated>uv run pytest -q --collect-only 2>&1 | tail -3  # сбор всего набора не сломан</automated>
  </verify>
  <done>9 тестов существуют и падают по причине отсутствия
  `scripts/import_inventory_receipt.py`, а не по синтаксису/фикстурам; сбор
  остального набора зелёный; коммит сделан, пуша нет.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: GREEN — scripts/import_inventory_receipt.py + бамп версии</name>
  <files>scripts/import_inventory_receipt.py, app/__init__.py</files>
  <behavior>
    Все 9 тестов задачи 1 зелёные без правок самих тестов. Если тест кажется
    неверным — не править тест молча: сверить с `260902-eyv-SPEC.md` и, если
    расхождение реальное, сообщить о нём, а не подгонять контракт под код.
  </behavior>
  <action>
Создать `scripts/import_inventory_receipt.py` строго по разделу `<design>`:
публичная поверхность, D-1..D-9, формат вывода — всё оттуда, ничего не
изобретать заново.

Шапка модуля — как в `scripts/reset_business_data.py`:
`sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` перед
импортами `app.*`, импорты после него с `# noqa: E402`. Докстрока: что делает,
как запускать, что режим по умолчанию — сухой прогон, и что импорт НЕ
идемпотентен.

CLI (`argparse`): `--apply` (store_true), `--file` (default `CSV_DEFAULT`),
`--warehouse` (default `WAREHOUSE_DEFAULT`). Больше флагов не добавлять.

`read_rows`: `open(path, encoding="utf-8-sig", newline="")` + `csv.DictReader(f, delimiter=";")`.
Проверить, что в заголовке присутствуют все 5 используемых колонок
(`Полка`, `Код`, `Наименование (из справочника)`, `Кол-во`, `Срок годности`);
если нет — `RuntimeError` с внятным русским текстом, перечисляющим недостающие.
`line_no` считать через `enumerate(reader, start=2)` (заголовок = строка 1).
`skip_reason` заполнять для пустого кода и для кода из `SKIP_CODES`.

`main()`:
1. напечатать цель (D-8), путь файла, режим;
2. файла нет -> русское сообщение + `sys.exit(1)`;
3. диалект вне sqlite/postgresql -> `RuntimeError` (D-9);
4. склад не найден -> `Не найден активный склад «<имя>».` + `sys.exit(1)`;
5. вызвать `run_import`, напечатать сводку в формате из `<design>`;
6. при `summary["error"]` напечатать
   `Строка {stopped_at_line} (код {code}): {error}` и
   `Остановлено. Записано строк: {rows_written}.`, затем `sys.exit(1)`;
7. иначе `sys.exit(0)`.

Жёсткие запреты в этом файле: ни одного `session.add(...)`, ни одного вызова
конструкторов `Product(`/`Batch(`/`Operation(`, ни одного `record_operation(`.
Единственные записи — `register_receipt(...)` и присваивание `batch.comment`
с последующим `session.commit()`.

Бампнуть `app/__init__.py`: `__version__ = "1.38"` -> `"1.39"` (в этом же
коммите, по требованию задачи).

Коммит: `feat(quick-260902-eyv): import the office inventory as a receipt (dry-run by default)`.
Всё ещё не пушить.
  </action>
  <verify>
    <automated>uv run pytest tests/test_import_inventory_receipt.py -q 2>&1 | tail -5  # 9 passed</automated>
    <automated>grep -v '^\s*#' scripts/import_inventory_receipt.py | grep -c -E 'session\.add\(|record_operation\(|Operation\(|Product\(|Batch\('  # ожидается 0 (grep вернёт код 1 — это и есть успех гейта)</automated>
    <automated>grep -c 'register_receipt(' scripts/import_inventory_receipt.py  # >= 1</automated>
    <automated>grep -c '1.39' app/__init__.py  # 1</automated>
    <automated>uv run ruff check scripts/import_inventory_receipt.py tests/test_import_inventory_receipt.py</automated>
  </verify>
  <done>9 тестов зелёные; в скрипте нет прямых записей в модели; версия 1.39;
  ruff чистый; коммит сделан.</done>
</task>

<task type="auto">
  <name>Task 3: Полный прогон тестов + сухой прогон против реальной описи</name>
  <files>(проверка; правки только если что-то красное)</files>
  <action>
1. `uv run pytest` целиком. Ожидаемо: всё зелёное, КРОМЕ 4 известных падений
   в `tests/test_sync_ui.py` (детерминированные, причина —
   `sync_client._run_lock`, удерживаемый lifespan-потоком авто-синка;
   существуют задолго до этой задачи). Их НЕ чинить, но перечислить поимённо
   в отчёте. Любое ДРУГОЕ падение — регрессия этой задачи, чинить.

2. Сухой прогон против реальной описи и локальной базы (read-only, без
   `--apply`):
   `uv run python scripts/import_inventory_receipt.py`
   Это заодно проверяет регистронезависимый поиск склада: локально склад
   называется «офис», а значение по умолчанию — «Офис».

3. Сверить напечатанное с независимо установленными фактами. ЖЁСТКИЕ числа —
   расхождение означает баг в скрипте, а не повод подправить ожидание:
   - прочитано строк: 414
   - пропущено: 1, и это физическая строка 313 с кодом «???»
   - к оприходованию: 413
   - новых карточек товара: 332
   - кодов без цены в catalog_prices: 44
   - `новых партий + доливов == 413`
   МЯГКОЕ число: суммарное количество. SPEC называет 2204 шт. Если
   напечатано другое — НЕ трогать скрипт и НЕ подгонять: сообщить о
   расхождении отдельной строкой в отчёте.

4. Убедиться, что сухой прогон ничего не записал: счётчики
   `products`/`batches`/`operations` в локальной базе до и после прогона
   совпадают (снять до и после одним и тем же коротким read-only запросом).

5. Зафиксировать в отчёте полный вывод сухого прогона, включая блок
   «Предупреждения», если он появился (например, доливы в legacy-партии).

6. Пуш: `git push` один раз, в конце, только если полный набор тестов зелёный
   (за вычетом 4 известных). При коммите добавлять ТОЛЬКО
   `scripts/import_inventory_receipt.py`, `tests/test_import_inventory_receipt.py`,
   `app/__init__.py` и файлы `.planning/`. Не делать `git add .` и не
   коммитить `reports/`, `input/`, `plan1.txt` — они untracked намеренно.
   Деплой на s1 в этой задаче НЕ выполняется.
  </action>
  <verify>
    <automated>uv run pytest -q 2>&1 | tail -15</automated>
    <automated>uv run python scripts/import_inventory_receipt.py</automated>
    <automated>git status --porcelain</automated>
  </verify>
  <done>Полный набор зелёный кроме 4 известных падений `test_sync_ui.py`
  (перечислены поимённо); сухой прогон напечатал 414/1/413/332/44 и
  «новых партий + доливов == 413»; счётчики базы до и после прогона
  идентичны; расхождение по сумме количества (если есть) отражено в отчёте;
  `git status` не содержит случайно добавленных файлов; запуск с `--apply`
  не выполнялся.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_import_inventory_receipt.py -q` — 9 passed.
- `uv run pytest -q` — зелёный, кроме 4 известных `tests/test_sync_ui.py`.
- `uv run ruff check scripts/ tests/test_import_inventory_receipt.py` — чисто.
- Гейт «нет прямых записей»:
  `grep -v '^\s*#' scripts/import_inventory_receipt.py | grep -c -E 'session\.add\(|record_operation\(|Operation\(|Product\(|Batch\('`
  возвращает 0 совпадений.
- Сухой прогон против `reports/оприходование-офис-2026-08-31.csv`:
  414 / 1 (строка 313) / 413 / 332 новых карточек / 44 без цены,
  новых партий + доливов == 413, база не изменилась.
- `--apply` не запускался ни разу, ни локально, ни на s1.
</verification>

<success_criteria>
Оператор может одной командой посмотреть, что именно даст импорт описи, и
получить точное предсказание (сколько карточек, партий, доливов, строк без
цены), не рискуя записать что-либо; фактическая запись возможна только
осознанным `--apply`. Правила 1-7 из SPEC закреплены тестами, а не
комментариями. Существующие остатки склада «Офис» не задваиваются и не
затираются: опись добавляется сверху, цены уже заведённых карточек остаются
нетронутыми (ноль операций `price_change`).
</success_criteria>

<output>
Create `.planning/quick/260902-eyv-import-office-inventory-receipt-into-s1/260902-eyv-SUMMARY.md` when done.
Обязательно включить в SUMMARY: полный вывод сухого прогона, поимённый список
4 известных падений `test_sync_ui.py`, и явную строку «--apply не запускался».
</output>
