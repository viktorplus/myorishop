---
quick_id: 260907-wvy
type: execute
mode: quick
wave: 1
depends_on: []
files_modified:
  - app/static/public/report-office-receipt-2026-09-07.html
  - app/routes/public_pages.py
  - app/services/security.py
  - app/__init__.py
  - tests/test_public_page.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Аноним (без сессии) открывает /code/report/office-receipt-2026-09-07 и получает 200 + text/html, а не 303 на /login"
    - "Опубликованный HTML побайтово совпадает с исходником из scratchpad"
    - "Страница сохраняет собственную двойную палитру: светлая обёртка соседей в неё не попала"
    - "Соседние пути под /code/report/ по-прежнему уводят анонима с логин-редиректом"
    - "Четыре существующие публичные страницы продолжают отдаваться без изменений"
  artifacts:
    - path: "app/static/public/report-office-receipt-2026-09-07.html"
      provides: "Сам отчёт — готовый standalone-документ"
      sha256: "c3515a3d6bed0d5eda278b6dcd90f0111f512c64938be42b8e575161336accc1"
      size_bytes: 32009
    - path: "app/routes/public_pages.py"
      provides: "Пятая пара констант + роут"
      contains: "RECEIPT_SEP07_PATH"
    - path: "app/services/security.py"
      provides: "Путь в PUBLIC_PATHS (exact-match)"
      contains: "/code/report/office-receipt-2026-09-07"
    - path: "app/__init__.py"
      provides: "Бамп версии"
      contains: "1.133"
    - path: "tests/test_public_page.py"
      provides: "Покрытие пятой страницы"
      contains: "RECEIPT_SEP07_PATH"
  key_links:
    - from: "app/routes/public_pages.py::RECEIPT_SEP07_PATH"
      to: "app/services/security.py::PUBLIC_PATHS"
      via: "одна и та же строка пути, посимвольно"
      pattern: "/code/report/office-receipt-2026-09-07"
    - from: "app/routes/public_pages.py::public_office_receipt_report_sep07"
      to: "app/static/public/report-office-receipt-2026-09-07.html"
      via: "FileResponse(RECEIPT_SEP07_FILE)"
      pattern: "FileResponse\\(RECEIPT_SEP07_FILE"
---

<objective>
Опубликовать отчёт по приходу 1735 шт на склад «Офис» от 07.09.2026 как ПЯТУЮ
публичную страницу в уже существующем механизме `app/routes/public_pages.py`.

Purpose: claude.ai в России не открывается — владельцу нужен тот же документ по
ссылке на собственном домене ori.viktorplus.com.

Output: статический HTML в `app/static/public/`, пара констант + роут, путь в
`PUBLIC_PATHS`, бамп версии и тест на анонимный доступ.

Никакого нового механизма: пятая страница делается ровно так же, как четвёртая
(`RECEIPT_PATH` / `RECEIPT_FILE`, строки ~58-68). Четыре соседние страницы не
трогаются.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@./CLAUDE.md
@app/routes/public_pages.py
@app/services/security.py
@app/__init__.py
@tests/test_public_page.py
</context>

<facts_verified_at_plan_time>
Проверено чтением файлов и командами на момент планирования — на это можно
опираться, не перепроверяя заново (но см. Task 1 про фактическую версию):

- Исходник: `C:\Users\Admin\AppData\Local\Temp\claude\E--dev-myorishop\0809a767-5a14-4b03-bec1-ad1cefb91478\scratchpad\prihod-0709.html`
  — существует, 32009 байт, sha256 `c3515a3d6bed0d5eda278b6dcd90f0111f512c64938be42b8e575161336accc1`.
  Обратите внимание на **заглавную `E--dev-myorishop`** в пути (не `e--`).
- В исходнике УЖЕ есть `<!doctype html>`, `<html lang="ru">`, `<head>` с charset /
  viewport / `<title>`, заканчивается на `</html>`. Обёртку добавлять НЕ надо.
- Ровно один `<title>`; `@media (prefers-color-scheme: dark)` — 1 шт;
  `:root[data-theme="dark"]` — 1 шт; `color-scheme:light` — 0; `background:#faf9f5` — 0;
  `__FRAME` / `frame-runtime` — 0 (рантайм-обёртка claude.ai уже срезана).
- `<title>` = `Приход на склад Офис, 7 сентября 2026` — **БЕЗ «ёлочек»**.
  `<h1>` = `Приход на склад «Офис», 7 сентября 2026` — **С «ёлочками»**.
  Это ровно та же асимметрия, что у четвёртой страницы (её тест бьёт по `<h1>`,
  а не по `<title>`) — не «опечатка», не «исправлять».
- `app/__init__.py` сейчас реально `__version__ = "1.132"`.
- Фикстура `anon_client` живёт в `tests/conftest.py:294`, гоняет НАСТОЯЩИЙ
  `auth_guard` без override — то есть тест на 200 действительно доказывает
  публичность, а не отключённую защиту.
- ruff: `line-length = 100`, `select = ["E", "F", "I", "UP", "B"]` — **`I` включён**,
  значит порядок имён в импорт-блоке теста проверяется линтером.
- Существующий тест `test_neighbouring_paths_stay_behind_the_login` уже стоит
  сторожем на `/code/report/other` — новый путь с ним не конфликтует.
</facts_verified_at_plan_time>

<tasks>

<task type="auto">
  <name>Task 1: Положить HTML и доказать побайтовое совпадение</name>
  <files>app/static/public/report-office-receipt-2026-09-07.html</files>
  <action>
Скопировать исходник в `app/static/public/report-office-receipt-2026-09-07.html`
файловой операцией (`cp`), БЕЗ чтения-и-перезаписи содержимого: любой цикл
read → write рискует нормализовать переводы строк или BOM, а требование —
байт в байт.

Исходный путь (заглавная `E--` в сегменте проекта):
`C:/Users/Admin/AppData/Local/Temp/claude/E--dev-myorishop/0809a767-5a14-4b03-bec1-ad1cefb91478/scratchpad/prihod-0709.html`

Содержимое НЕ править вообще. В частности НЕ дописывать на `body`
`color-scheme:light`, `background` или `font`: страница сама объявляет светлую и
тёмную палитры через CSS-переменные (`:root`, `@media (prefers-color-scheme: dark)`,
`:root[data-theme="dark"]`) — ровно как четвёртая страница. Шапка первых трёх
страниц устроена иначе и сюда не переносится: она сломает тёмную тему.

Заодно ПРОЧИТАТЬ фактическое значение `__version__` в `app/__init__.py` и
запомнить его для Task 3 (ожидается 1.132 → бампим до 1.133; если там другое —
бампим на единицу от фактического, а не вслепую до 1.133).
  </action>
  <verify>
    <automated>cmp "C:/Users/Admin/AppData/Local/Temp/claude/E--dev-myorishop/0809a767-5a14-4b03-bec1-ad1cefb91478/scratchpad/prihod-0709.html" app/static/public/report-office-receipt-2026-09-07.html && sha256sum app/static/public/report-office-receipt-2026-09-07.html | grep -q c3515a3d6bed0d5eda278b6dcd90f0111f512c64938be42b8e575161336accc1 && echo BYTE_IDENTICAL_OK</automated>
  </verify>
  <done>
Файл существует, 32009 байт, `cmp` молчит, sha256 совпадает с
`c3515a3d6bed0d5eda278b6dcd90f0111f512c64938be42b8e575161336accc1`.
Фактическая текущая версия из `app/__init__.py` зафиксирована для Task 3.
  </done>
</task>

<task type="auto">
  <name>Task 2: Пятая пара констант, роут и путь в PUBLIC_PATHS</name>
  <files>app/routes/public_pages.py, app/services/security.py</files>
  <action>
**`app/routes/public_pages.py`** — дописать В КОНЕЦ файла, строго по образцу
четвёртой страницы (строки ~58-68). Ничего выше не трогать.

Комментарий на русском в стиле соседних, по смыслу: отчёт по приходу 1735 шт на
склад «Офис» 07.09.2026; режим тот же — статический файл, никаких запросов к
базе и никаких параметров запроса.

Константы (имена именно такие — они отличимы от `RECEIPT_*` четвёртой страницы и
чисто сортируются в импорт-блоке теста):
- `RECEIPT_SEP07_PATH = "/code/report/office-receipt-2026-09-07"`
- `RECEIPT_SEP07_FILE = Path("app/static/public/report-office-receipt-2026-09-07.html")`

Роут — точная копия формы четвёртого: декоратор
`@router.get(RECEIPT_SEP07_PATH, include_in_schema=False)`, функция
`public_office_receipt_report_sep07` (имя `public_office_receipt_report` уже
занято четвёртой страницей — переиспользование молча затрёт её роут-функцию),
внутри та же проверка `if not RECEIPT_SEP07_FILE.is_file(): raise HTTPException(status_code=404, detail="page not found")`
и `return FileResponse(RECEIPT_SEP07_FILE, media_type="text/html; charset=utf-8")`.
Новых импортов не требуется — `Path`, `HTTPException`, `FileResponse` уже импортированы.

**`app/services/security.py`** — добавить `"/code/report/office-receipt-2026-09-07"`
пятым элементом в множество `PUBLIC_PATHS` (строки 41-50), после
`"/code/artifact/143c5a2c-d93f-4361-ae44-0059c828962a"`. Множество EXACT-match,
не префиксное — добавляется именно полная строка пути, без слэша на конце.
Комментарий над `PUBLIC_PATHS` уже описывает механизм, править его не нужно.

**САМОЕ ХРУПКОЕ МЕСТО ЭТОЙ ЗАДАЧИ:** строка пути дублируется в двух файлах и
связана только текстуально. Разойдутся на один символ — роут будет существовать,
но `auth_guard` уведёт анонима на `/login`, и страница «просто не откроется» без
внятной ошибки. Сверить оба вхождения посимвольно (см. verify).
  </action>
  <verify>
    <automated>test "$(grep -c '/code/report/office-receipt-2026-09-07' app/routes/public_pages.py app/services/security.py | grep -c ':1$')" = 2 && uv run python -c "from app.routes.public_pages import RECEIPT_SEP07_PATH; from app.services.security import PUBLIC_PATHS; assert RECEIPT_SEP07_PATH in PUBLIC_PATHS, 'path mismatch between route and PUBLIC_PATHS'; print('PATH_LINK_OK')"</automated>
  </verify>
  <done>
Путь встречается ровно по одному разу в каждом из двух файлов, и рантайм-проверка
подтверждает `RECEIPT_SEP07_PATH in PUBLIC_PATHS`. Четыре прежние пары констант и
роута не изменены.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Тесты на пятую страницу, бамп версии, гейты</name>
  <files>tests/test_public_page.py, app/__init__.py</files>
  <behavior>
Два теста — тем же способом, каким покрыта четвёртая страница:

- `test_office_receipt_sep07_is_served_to_anonymous_visitor`: `anon_client.get(RECEIPT_SEP07_PATH)`
  → 200, `content-type` начинается с `text/html`, и в теле есть
  `Приход на склад «Офис», 7 сентября 2026` (это текст `<h1>`, С «ёлочками»;
  в `<title>` их нет — бить надо по `<h1>`, как это делает тест четвёртой страницы).
- `test_office_receipt_sep07_keeps_its_own_dark_theme`: читает `RECEIPT_SEP07_FILE`
  и проверяет ровно те же тематические маркеры, что стоят на четвёртой странице:
  начинается с `<!doctype html>`, `rstrip()` заканчивается на `</html>`,
  `html.count("<title>") == 1`, есть `@media (prefers-color-scheme: dark)`,
  есть `:root[data-theme="dark"]`, НЕТ `color-scheme:light`, НЕТ `background:#faf9f5`.

Все шесть маркеров сверены с реальным файлом на этапе планирования — тесты должны
пройти сразу; красный тест здесь означает, что Task 1 испортил файл при копировании.
  </behavior>
  <action>
Расширить `tests/test_public_page.py`, ничего в нём не удаляя и не переписывая.

Добавить `RECEIPT_SEP07_FILE` и `RECEIPT_SEP07_PATH` в существующий импорт-блок
`from app.routes.public_pages import (...)`. Ruff гоняет `I` (isort), поэтому
порядок обязан остаться алфавитным: `ARTIFACT_FILE, ARTIFACT_PATH, RECEIPT_FILE,
RECEIPT_PATH, RECEIPT_SEP07_FILE, RECEIPT_SEP07_PATH, REPORT_FILE, REPORT_PATH,
UNKNOWN_FILE, UNKNOWN_PATH`.

Дописать два теста из `<behavior>` в конец файла, рядом с тестами четвёртой
страницы, в том же стиле (докстрока на русском у второго — как у соседа).

`app/__init__.py`: поднять `__version__` на единицу от значения, прочитанного в
Task 1 (ожидаемо `"1.132"` → `"1.133"`). Комментарий над строкой не трогать.

Затем прогнать гейты (команды — в `<verify>`). Известные ПРЕДСУЩЕСТВУЮЩИЕ
проблемы НЕ чинить, но обязательно назвать в SUMMARY:
- плавающие падения `tests/test_sync_ui.py` — гонка за `sync_client._run_lock` с
  потоком автосинка, воспроизводится и без этой задачи;
- ~32 нарушения ruff в файлах, которых задача не касается — поэтому `ruff check`
  запускается на ИЗМЕНЁННЫХ файлах, а не на всём дереве.

Коммит один на всю задачу (пятая страница — одна логическая единица, и бамп
версии тоже один). НЕ коммитить docs-артефакты (PLAN.md / SUMMARY.md / STATE.md)
— их коммитит оркестратор. Деплой на s1 и живую проверку в браузере в эту задачу
НЕ включать — это делает оркестратор после коммита.
  </action>
  <verify>
    <automated>uv run pytest tests/test_public_page.py -q && uv run ruff check app/routes/public_pages.py app/services/security.py app/__init__.py tests/test_public_page.py && uv run pytest tests/ -q</automated>
  </verify>
  <done>
`tests/test_public_page.py` зелёный целиком (старые тесты четырёх страниц + два
новых). `ruff check` на четырёх изменённых файлах — чисто. Полный прогон
`uv run pytest tests/ -q` выполнен, и любые падения в нём атрибутированы:
либо предсуществующий `test_sync_ui.py`, либо регрессия от этой задачи (тогда
чинить). Версия поднята на единицу. Сделан один коммит без docs-артефактов.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| аноним из интернета → `auth_guard` | Задача НАМЕРЕННО расширяет дырку в deny-by-default гварде на один путь |
| роут → файловая система | `FileResponse` читает файл с диска по пути из константы |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-Q-01 | Information disclosure | `PUBLIC_PATHS` + новая страница | accept | Публикация — сам смысл задачи и прямая просьба владельца. Ограничения риска: страница статическая, без запросов к базе и без параметров запроса, содержит только тот отчёт, который уже был расшарен через claude.ai. Ничего, кроме этого документа, путь не отдаёт. |
| T-Q-02 | Elevation of privilege | `auth_guard` шаг (2) | mitigate | `PUBLIC_PATHS` — множество EXACT-match, добавляется полная строка без завершающего слэша, поэтому соседние пути не открываются. Регресс-сторож уже стоит: `test_neighbouring_paths_stay_behind_the_login` бьёт по `/code/report/` и `/code/report/other`. |
| T-Q-03 | Tampering | `FileResponse(RECEIPT_SEP07_FILE)` | mitigate | Путь к файлу — константа модуля; ни один сегмент не собирается из пользовательского ввода, у роута нет ни path-, ни query-параметров, поэтому обхода каталога не существует. Отсутствие файла даёт 404, а не трассировку. |
| T-Q-04 | Tampering | целостность публикуемого документа | mitigate | Копирование проверяется `cmp` + фиксированным sha256 в Task 1 — подмена или порча при копировании валит гейт. |
| T-Q-SC | Tampering | цепочка поставок | n/a | Задача не ставит и не обновляет ни одного пакета (npm/pip/cargo): изменяются только четыре файла приложения плюс один статический HTML. Гейт легитимности пакетов неприменим. |
</threat_model>

<verification>
1. `cmp` исходника и опубликованного файла — молчит; sha256 совпадает.
2. `RECEIPT_SEP07_PATH in PUBLIC_PATHS` — истинно в рантайме (не «на глаз»).
3. `uv run pytest tests/test_public_page.py -q` — зелёный, включая старые тесты
   четырёх страниц (доказательство, что соседи не сломаны).
4. `uv run ruff check` на четырёх изменённых файлах — чисто.
5. `uv run pytest tests/ -q` — прогнан; падения атрибутированы (предсуществующие
   vs регрессия).
6. `__version__` поднят на единицу от фактического.
</verification>

<success_criteria>
- Аноним получает 200 + `text/html` на `/code/report/office-receipt-2026-09-07`.
- Опубликованный HTML побайтово равен исходнику (sha256 `c3515a3d…accc1`).
- Тёмная тема страницы не испорчена светлой обёрткой соседей.
- Соседние пути под `/code/report/` остаются за логином.
- Четыре существующие публичные страницы отдаются как прежде.
- Один коммит, без docs-артефактов; деплой и живая проверка оставлены оркестратору.
</success_criteria>

<output>
Create `.planning/quick/260907-wvy-publish-office-receipt-report-2026-09-07/260907-wvy-SUMMARY.md` when done.

Обязательно указать в SUMMARY:
- предсуществующие плавающие падения `tests/test_sync_ui.py` (гонка за
  `sync_client._run_lock`) — не чинились, не относятся к задаче;
- ~32 предсуществующих нарушения ruff в незатронутых файлах — не чинились;
- страница тянет шрифты с `fonts.googleapis.com` (2 ссылки) — ровно как уже
  опубликованная четвёртая страница, поэтому это не регрессия; но без интернета
  она деградирует на системные шрифты. Названо как факт, менять не просили.
</output>
