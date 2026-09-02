---
phase: 260902-tev-fix-the-three-code-review-blockers-in-th
verified: 2026-09-02T21:15:00Z
status: human_needed
score: 10/10 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Решить, приемлем ли LIFO-порядок откатов: `git revert 1481e38` поверх aaa6f1b даёт один текстовый конфликт в списке импортов tests/test_import_prices.py:29. Подтверждено: конфликт ограничен ИМЕННО этой строкой, изменения в scripts/import_prices.py откатываются чисто и в одиночку."
    expected: "Либо принять как есть (откат по LIFO или ручное разрешение одной строки), либо запросить rebase, разводящий строки импорта."
    why_human: "Это компромисс между «одна строка в тесте» и буквой must-have «revertable on its own». Решение о переписывании истории ветки — за человеком."
  - test: "Решить, приемлемо ли, что на s1 (PostgreSQL, deploy/DEPLOY.s1.md:26,60) `backup_before_replace` печатает пропуск и НЕ делает снимок, поэтому запуск `import_master_pricelist.py --force` удаляет 12 582 строки dictionary без снимка данных."
    expected: "Либо принять (защита на s1 = сам отказ DictionaryReplaceRefused + запечённый catalogs/products.json), либо добавить не-SQLite путь снимка (pg_dump / CREATE TABLE AS) до удаления."
    why_human: "Диалектный пропуск прямо санкционирован планом, но затрагивает вторую половину требования пользователя («без восстановимого снимка или нетронутого оригинала»): products.json НЕ содержит имён, вписанных на сервере руками — а DEPLOY.s1.md:94-97 предупреждает именно о них."
  - test: "Ручной прогон плана (verification §4) на реальном xlsx и реальной БД — исполнитель заявляет 6 сценариев (дрейф заголовка, 6856 unparsable, --force+--only-missing, happy path со снимком 249 856 байт, сценарий s1 12582 -> 6890, экспорт .gz/products.json)."
    expected: "Наблюдаемый вывод совпадает с заявленным в SUMMARY."
    why_human: "Требует архива catalogs/price_lists/ (118 МБ, вне git) и загруженной БД; здесь не воспроизводится. Контракты покрыты тестами на синтетических данных."
---

# Quick task 260902-tev: отчёт верификации

**Цель задачи:** закрыть CR-01/CR-02/CR-03 из `260902-m9g-REVIEW.md` безопасно и с
возможностью отката на ДВУХ уровнях — git (один независимо откатываемый коммит на
блокер) и данные (ни одной разрушающей операции без восстановимого снимка или
нетронутого оригинала).
**Проверено:** 2026-09-02T21:15:00Z
**Статус:** human_needed
**Повторная верификация:** нет — первичная.

## Достижение цели

### Observable Truths

| # | Truth | Статус | Доказательство |
|---|-------|--------|----------------|
| 1 | Деградировавший разбор (все строки нечитаемы) не пишет; сохранённые строки dictionary остаются | ✓ VERIFIED | `scripts/import_master_pricelist.py:297-301` — `if not collected: raise DictionaryReplaceRefused` ДО `session.query(Dictionary).delete()` (строка 311). Тест `tests/test_import_master_pricelist.py:294-306` проверяет и исключение, и что строка `555555` на месте |
| 2 | Сжимающая замена отвергается без `--force`; сообщение называет оба числа, команду восстановления и `--force` | ✓ VERIFIED | Код `:304-310` формирует «stored {before} -> about to write {len(rows)}» + `scripts/import_catalogs.py --only-missing --file catalogs/products.json` + «pass --force only if…». Тест `:308-338` ассертит все четыре подстроки и что count не изменился |
| 3 | Порог 0 %, без полосы допуска; на чистой установке guard молчит | ✓ VERIFIED | Условие ровно `len(rows) < before` (`:304`) — никакого коэффициента. Обоснование (порядок установки, 6 856 против 12 582) записано в docstring `:283-295` |
| 4 | Оператор видит «unparsable catalog: N» и путь VACUUM INTO снимка ДО первого удаления; на PostgreSQL — печатный no-op, не падение | ✓ VERIFIED | `main()`: печать статистики `:393-401`, `backup_before_replace(engine)` `:403`, и только потом `with SessionLocal()` `:405`. Диалектный гейт `:263-268`. AST-tripwire `tests/…:415-438` пинит порядок; тест `:375-383` пинит no-op + непустой stdout |
| 5 | Несостоявшийся снимок прерывает импорт: исключение выходит наружу, ничего не удалено | ✓ VERIFIED | В `backup_before_replace` нет ни одного `try/except` (`:248-271`); `create_backup` сам делает `unlink(missing_ok=True)` и `raise` (`app/services/backup.py:42-47`). Тест `:386-403` |
| 6 | float / строка / bool / отрицательное в деньгах, не-строка и имя > 200 символов отвергаются по индексу записи и значению | ✓ VERIFIED | `scripts/import_prices.py:657-675`. Проверяются все 7 ключей `EXPORT_KEYS` (`:105-107`): code, year, number, name, consumer_cents, consultant_cents, points. 7 новых кейсов parametrize `tests/test_import_prices.py:127-133` (включая `consultant_cents: "не указано"`) |
| 7 | Сохранённые 0 и None по-прежнему загружаются (контракт `>= 0`, не `> 0`) | ✓ VERIFIED | `:672-674` — `if value is None: continue`, отказ только при `value < 0`. Тест `:146-162` вызывает `validate_records` напрямую с `consumer_cents=0, points=0, consultant_cents=None, name=None` |
| 8 | Сбой при записи любого из трёх накопительных файлов оставляет прежний файл байт-в-байт и не оставляет temp | ✓ VERIFIED | `atomic_write` `:695-722`: payload — аргумент, temp в том же каталоге, `os.replace`, `finally: tmp.unlink(missing_ok=True)`. Тесты `:777-787` (байтовое равенство + отсутствие `*.tmp*`) и `:790-805` (падение `serialize_export` — старый файл жив) |
| 9 | Байты трёх писателей не изменились: LF-JSON по записи в строке, gzip для `.gz`, CRLF без хвостового перевода для rubric_overrides.json | ✓ VERIFIED | Имя temp сохраняет суффикс: `dest.with_name(dest.name + ".tmp" + dest.suffix)` (`:715`), поэтому ветка gzip в `_open_export` (`:690`) продолжает работать. Старые байтовые тесты (`test_write_overrides_reproduces_the_files_byte_form`, `test_the_export_round_trips_through_a_gz_with_no_loss`, twin в import_catalogs) прошли без правок; новый `:758-774` проверяет `1f 8b` и «нет одиночного LF» |
| 10 | Каждый блокер — один коммит, откатываемый в одиночку | ⚠️ VERIFIED с оговоркой | См. раздел «Целостность отката» — a99a989 и aaa6f1b откатываются в одиночку; 1481e38 конфликтует ровно одной строкой в списке импортов теста |

**Score:** 10/10 (truth 10 — с оговоркой, вынесенной на решение человека)

### Required Artifacts

| Артефакт | Ожидалось | Статус | Детали |
|----------|-----------|--------|--------|
| `scripts/import_master_pricelist.py` | `DictionaryReplaceRefused` + `apply_master_import(force=)` + `backup_before_replace` + `--force` | ✓ VERIFIED | Класс `:63`, guard-и `:297-310`, helper `:248-271`, флаг `:340-344` + foot-gun guard `:349-350` |
| `scripts/import_prices.py` | `atomic_write` + валидация всех 7 полей | ✓ VERIFIED | `atomic_write` `:695` (рядом с `_open_export` `:679`), `import os` `:72`, валидация `:657-675` |
| `scripts/import_catalogs.py` | `write_export` через общий `atomic_write` | ✓ VERIFIED | `from scripts.import_prices import atomic_write  # noqa: E402` `:81`; вызов `:359` |
| `tests/test_import_master_pricelist.py` | 6 тестов CR-01 | ✓ VERIFIED | `:294`, `:308`, `:341`, `:363`, `:375`, `:386`, `:415` — 7 функций, `import ast` `:16`, `SCRIPT` `:41` |
| `tests/test_import_prices.py` | кейсы CR-02 + контракт CR-03 | ✓ VERIFIED | 7 кейсов parametrize `:127-133`, `:146`, `:758`, `:777`, `:790`, `:823` |
| `tests/test_import_catalogs.py` | доказательство, что `write_export` не открывает назначение | ✓ VERIFIED | `:212-244`, включая «the file stays key-sorted» |

Уровень 4 (данные реально текут) для этих артефактов проверен исполнением тестов,
а не только чтением: см. «Behavioral Spot-Checks».

### Key Link Verification

| From | To | Via | Статус |
|------|----|-----|--------|
| `apply_master_import` | `session.query(Dictionary).delete()` | `raise DictionaryReplaceRefused` до удаления | ✓ WIRED — оба guard-а на строках 297 и 304, delete на 311 |
| `backup_before_replace` | `app.services.backup.create_backup` | гейт `engine.dialect.name == "sqlite"`, исключение не глотается | ✓ WIRED — `:263-271`, импорт `:52`; `create_backup` действительно выполняет `VACUUM INTO` (`app/services/backup.py:44`) |
| `import_prices.write_export` | `atomic_write` | `serialize_export(merged)` как аргумент | ✓ WIRED — `:900` |
| `import_prices.write_overrides` | `atomic_write` | `newline="\r\n"`, без хвостового перевода | ✓ WIRED — `:541` |
| `import_catalogs.write_export` | `scripts.import_prices.atomic_write` | кросс-скриптовый импорт | ✓ WIRED — `:81`, `:359` |
| `validate_records` | `build_price_rows -> upsert_price_rows` | контракт `.gz` до касания БД | ✓ WIRED — все 7 полей закрыты до `build_price_rows` |

Контрольная проверка на «остатки»: `grep '"wt"'` по `scripts/` находит запись
только внутри `atomic_write` (`:717`). Ни один писатель больше не открывает
назначение напрямую.

### Behavioral Spot-Checks

| Поведение | Команда | Результат | Статус |
|-----------|---------|-----------|--------|
| Все три файла тестов зелёные | `uv run pytest tests/test_import_prices.py tests/test_import_catalogs.py tests/test_import_master_pricelist.py -q` | `96 passed, 1 skipped in 12.00s` | ✓ PASS |
| Нет новых замечаний линтера | `uv run ruff check` по шести затронутым файлам | `Found 3 errors` — E501 в `import_master_pricelist.py:3,137,144`, все вне тронутых hunk-ов (диффы начинаются со строки 45 и с 232), т.е. pre-existing IN-07 | ✓ PASS |

Полный прогон набора не повторялся по указанию заказчика (4 известных падения в
`tests/test_sync_ui.py`).

### Целостность отката (git-уровень)

Проверено неразрушающе, `git show <sha> | git apply -R --check -` (рабочее дерево
не менялось):

| Коммит | Файлы | Откат в одиночку поверх текущего tip |
|--------|-------|--------------------------------------|
| `a99a989` CR-01 | `scripts/import_master_pricelist.py`, `tests/test_import_master_pricelist.py` | ✓ применяется (exit 0) |
| `1481e38` CR-02 | `scripts/import_prices.py`, `tests/test_import_prices.py` | ⚠️ конфликт, см. ниже |
| `aaa6f1b` CR-03 | `scripts/import_catalogs.py`, `scripts/import_prices.py`, оба теста | ✓ применяется (exit 0) |

**Асимметрия CR-02 ПОДТВЕРЖДЕНА и ограничена именно списком импортов:**

* `git show 1481e38 -- scripts/import_prices.py | git apply -R --check -` → **exit 0**.
  Продуктовый код CR-02 откатывается чисто и в одиночку.
* Падает единственный hunk `tests/test_import_prices.py:29` — строка `MAX_NAME,`
  в списке импортов, куда CR-03 (`aaa6f1b`, hunk `@@ -30,6 +30,7 @@`) добавил
  соседнюю `atomic_write,`.
* Остальные hunk-и CR-03 в этом файле — `@@ -741,3 +742,94 @@`, то есть дописка в
  конец файла; в `scripts/import_prices.py` CR-03 трогает строки 69, 538, 692, 894,
  а CR-02 — только `validate_records` (657-675). Пересечений в коде нет.

Пересечения файлов между CR-01 и остальными нет вовсе. `app/__init__.py`
(`__version__`) не тронут ни одним из трёх коммитов — как и требовал план.

### Целостность отката (уровень данных)

| Разрушающая операция | Путь назад | Статус |
|----------------------|------------|--------|
| `dictionary` wholesale replace, SQLite | `VACUUM INTO` снимок в `settings.backup_dir`, путь напечатан ДО удаления; несостоявшийся снимок прерывает импорт | ✓ есть |
| `dictionary` wholesale replace, PostgreSQL (s1) | Снимка НЕТ — печатный пропуск. Остаются: отказ `DictionaryReplaceRefused` (для сценария s1 он и сработает: 12 582 -> 6 890) и запечённый `catalogs/products.json` | ⚠️ частично — см. human_verification #2 |
| Перезапись `catalog_prices.json.gz` / `products.json` / `rubric_overrides.json` | Оригинал не открывается вообще до `os.replace`; на любом исключении файл остаётся байт-в-байт | ✓ есть |

### Anti-Patterns Found

| Файл | Строка | Паттерн | Severity | Влияние |
|------|--------|---------|----------|---------|
| `scripts/import_master_pricelist.py` | 3, 137, 144 | E501 > 100 символов | ℹ️ Info | Pre-existing (review IN-07), вне тронутых hunk-ов; план явно запретил чинить INFO-находки |
| `scripts/import_prices.py` | 715 | Фиксированное имя temp (`…​.tmp.gz`) | ℹ️ Info | Два параллельных прогона экспорта в один каталог перетрут temp друг друга. Вне рамок плана (сценарий однопользовательский), но стоит знать |
| — | — | TODO / FIXME / XXX / заглушки | — | Не найдено ни одного в шести изменённых файлах |

### Что план обещал, а код не сделал

Ничего. Все пункты `<action>` всех трёх задач присутствуют дословно, включая
мелочи: foot-gun guard `--force` + `--only-missing` (`:349-350`), отказ на пустом
входе в `main()` с обоими счётчиками (`:369-374`), импорт `engine` из `app.db`
(`:50`), `build_dictionary_rows` вызывается ОДИН раз и список переиспользуется
(`:302`, `:312`), `import os` (`:72`), `# noqa: E402` на кросс-скриптовом импорте
(`import_catalogs.py:81`), комментарий про `>= 0` (`:666-669`).

### Что код сделал сверх санкционированного планом

Ничего. Карта hunk-ов трёх коммитов не выходит за пределы функций, названных в
плане; новых зависимостей нет (только stdlib `os`); новых модулей, конфиг-ключей
и флагов сверх `--force` нет. Заявление SUMMARY «Deviations from Plan: None»
подтверждается диффом.

Отдельно: рабочее дерево содержит незакоммиченное изменение `.planning/STATE.md`
(артефакт планирования, не код) — вне трёх коммитов и вне рамок задачи.

### Human Verification Required

#### 1. Принять или отвергнуть LIFO-порядок откатов

**Что сделать:** решить, достаточно ли того, что `1481e38` откатывается либо после
отката `aaa6f1b`, либо с ручным разрешением одной строки импорта.
**Ожидается:** решение «принимаем» (тогда стоит зафиксировать порядок в SUMMARY —
он там уже описан) либо «переписать ветку так, чтобы строки импорта не соседствовали».
**Почему человек:** это компромисс формулировки must-have, а переписывание истории
ветки — решение владельца репозитория.

#### 2. Принять или закрыть отсутствие снимка на PostgreSQL

**Что сделать:** решить, приемлемо ли, что на s1 (`DATABASE_URL` -> `ori-db:5432`,
`deploy/DEPLOY.s1.md:26,60`) `import_master_pricelist.py --force` удалит 12 582
строки `dictionary` без снимка данных.
**Ожидается:** либо «принимаем» (защита на s1 — сам отказ + `products.json`), либо
задача на не-SQLite путь снимка перед удалением.
**Почему человек:** диалектный гейт прямо санкционирован планом, но требование
пользователя было «ни одной разрушающей операции без восстановимого снимка ИЛИ
нетронутого оригинала», а `products.json` не содержит имён, вписанных на сервере
руками — ровно тех, о которых предупреждает `deploy/DEPLOY.s1.md:94-97`.

#### 3. Ручной end-to-end прогон

**Что сделать:** сверить заявленные в SUMMARY 6 сценариев реального прогона.
**Ожидается:** совпадение наблюдаемого вывода с заявленным.
**Почему человек:** нужен архив `catalogs/price_lists/` (118 МБ, вне git) и
загруженная БД; здесь не воспроизводится.

### Gaps Summary

Разрывов, блокирующих цель, нет. Все три дефекта ревью действительно устранены в
коде, а не только в SUMMARY: guard-и CR-01 стоят ВНУТРИ `apply_master_import` и
физически предшествуют `delete()`; `validate_records` закрывает все 7 ключей
`EXPORT_KEYS`, включая bool как подкласс int и отрицательные значения; ни один из
трёх писателей больше не открывает назначение до готовности payload, а имя temp
сохраняет суффикс, поэтому gzip-ветка `_open_export` жива (проверено тестом на
сигнатуру `1f 8b`).

Статус `human_needed`, а не `passed`, из-за трёх пунктов выше: один — формальная
оговорка к «revertable on its own» (подтверждена как ограниченная списком импортов
теста), второй — реальный остаточный риск на PostgreSQL, санкционированный планом,
но не полностью закрывающий формулировку цели, третий — непроверяемый здесь ручной
прогон.

---

_Verified: 2026-09-02T21:15:00Z_
_Verifier: Claude (gsd-verifier)_
