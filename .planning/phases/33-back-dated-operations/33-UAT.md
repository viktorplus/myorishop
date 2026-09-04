---
status: testing
phase: 33-back-dated-operations
source: [33-VERIFICATION.md]
started: 2026-09-04T16:29:34Z
updated: 2026-09-04T16:29:34Z
---

## Current Test

number: 1
name: B-1 — Native browser bubble on a future date, desktop `/receipts`
expected: |
  Откройте `/receipts`, поставьте «Дата операции» на завтра, нажмите
  «Сохранить приход».
  Ожидается: всплывающая подсказка самого браузера, и во вкладке Network
  запрос НЕ уходит.
awaiting: user response

## Tests

**Why none of B-1 … B-7 was run automatically.** Not an application fault, and
not an inference — the blocker was measured. The Claude-in-Chrome extension has
no site permission for `localhost` / `127.0.0.1`, so every navigation to the app
returned a browser error page («Frame with ID 0 is showing error page» on both
`http://localhost:8123/setup` and `http://127.0.0.1:8123/setup`). Against that
same isolated instance (port **8123**, PID **20880**, isolated SQLite DB in a
scratch directory, `BACKUP_ON_STARTUP=false`, sync disabled):

- `alembic upgrade head` built its database cleanly through `0001 → 0027`;
- `curl` returned **303** on `/` (redirect to `/setup`) and **200** on `/setup`;
- the same browser tooling screenshotted `https://example.com` successfully in
  the same session.

So the app answered; the browser tooling could not reach it. The operator's own
instance on port 8000 (PID 39100) was never started, stopped or restarted.

**Sources.** Items 1–7 are the B-1 … B-7 rows of `33-UI-SPEC.md` § Verification
the executor must run. Their Russian wording below is verbatim from
`33-ROLLOUT.md` § Browser checks, which is where the Russian text of those same
rows lives — the UI-SPEC table itself is written in English. Item 8 is gap 1 of
`33-ROLLOUT.md` § Executed rollout. This file and `33-ROLLOUT.md` record the
same eight items and must not drift apart.

### 1. B-1 — Native browser bubble on a future date, desktop
steps: Откройте `/receipts`, поставьте «Дата операции» на завтра, нажмите «Сохранить приход».
expected: Всплывающая подсказка самого браузера, и во вкладке Network запрос НЕ уходит.
why_human: Browser-rendered constraint UI (`max=` + htmx 2.0.10 `checkValidity`) has no server-side observable.
result: [pending]

### 2. B-2 — Server guard renders inside the swapped mobile step, where `max` is inert
steps: `/m/receipts`, шаг 4: поставьте дату в шапке на завтра, нажмите «Сохранить приход».
expected: Запрос УХОДИТ, и в ответе первой строкой подменённого шага, прямо под всё ещё заполненным полем даты, появляется «Дата операции не может быть в будущем.»
why_human: The server half is test-proven (VA-14, 5 passed); the rendered placement of the error inside the swapped mobile step is not.
result: [pending]

### 3. B-3 — The typed date survives the mobile basket round-trip
steps: `/m/sales`: поставьте дату, добавьте товар, вернитесь в корзину, добавьте второй.
expected: Дата осталась той, что вы поставили, и НЕ сбросилась на сегодня.
why_human: htmx swap/round-trip persistence of a field inside the persistent wizard shell; the tests assert the template renders it, not that a real multi-swap session preserves it.
result: [pending]

### 4. B-4 — Two cash date fields, correct label association
steps: `/finance` и `/m/finance`.
expected: Два поля даты; клик по каждой подписи ставит фокус в СВОЁ поле (id `withdraw-op-date` и `deposit-op-date`).
why_human: `<label for>` focus association is a browser behaviour.
result: [pending]

### 5. B-5 — `.filter-bar` overflow at 1024 px — the one with measured teeth
steps: `/history` при ширине окна 1024 px, все четыре фильтра на экране.
expected: Нет горизонтальной полосы прокрутки. Если полоса появилась — только сообщить, не исправлять.
why_human: |
  CSS layout at a specific viewport width. **The risk is code-confirmed, only
  the outcome is unmeasured:** `app/static/style.css:188-193` sets
  `.filter-bar { display:flex; gap:16px }` with **no `flex-wrap`** — unlike
  `.toolbar` at `:72-77` — and this phase added the FOURTH `<select>` to that
  bar (`app/templates/partials/history_rows.html:24-82` now holds four
  `<select>` elements). Four selects inside a 960 px `.container` is an
  estimate, not a measurement, and «Сначала новые (по умолчанию)» is a wide
  option.
do_not_fix: |
  **Recording the observation IS the task. Do NOT apply the one-line
  `flex-wrap: wrap` fix.** It is explicitly deferred by decision D-21 /
  `33-CONTEXT.md` § Deferred Ideas because it touches every `.filter-bar` page,
  and it must not be made on the strength of an estimate. Measure first, report
  the result here, and let a later phase own the fix.
result: [pending]

### 6. B-6 — Nothing changed visually before any back-dated operation exists
steps: `/history` и `/m/history` ДО того, как появится хоть одна операция задним числом.
expected: Каждая ячейка «Когда» и каждая шапка мобильной карточки выглядят ровно как раньше — одна строка `дд.мм.гггг чч:мм`, без пометки.
why_human: Visual byte-identity of the untouched path — DATE-07's visible half. The template guard is verified in code (the `r.is_backdated` false branch), but the rendered result was never observed.
result: [pending]

### 7. B-7 — CSV column contract in a real downloaded file
steps: Выгрузите `sales.csv` и `cash_movements.csv` после того, как появится хотя бы одна операция задним числом.
expected: Одна новая колонка, заголовок «Внесено» — последний; первая колонка не убывает сверху вниз; `Код` / `Цена` / `Сумма` на прежних местах.
why_human: Spreadsheet-consumer contract. The writers are test-pinned, but the real downloaded file was never opened.
result: [pending]

### 8. Живая проверка push от ОТСТАВШЕГО клиента (LOCKED-порядок, шаг 4)
steps: |
  С реального клиента, который ещё на схеме `0026`, с его собственным валидным
  device-токеном, выполните `POST /api/sync/push` на обновлённый s1 (сейчас
  `0027`).
expected: |
  HTTP **200**, строки мержатся (ветка D-01 «принимаем отставшего клиента»), а
  НЕ 409.
why_human: |
  Пока не проверено: нужен реальный клиент с валидным device-токеном на схеме
  `0026`. Токеном разработчика делать это нельзя — тогда локальные dev-данные
  ушли бы в боевую базу. Серверная часть ветки accept-behind уже доказана
  тестами (VA-1, 7 passed); здесь проверяется она же против живого s1.
  Записано как gap 1 в `33-ROLLOUT.md` § Executed rollout.
blocks: |
  **Клиентский релизный тег не выпускать, пока этот пункт не пройден.**
  LOCKED ordering constraint 5 ставит тег строго после того, как шаг 4 пройден;
  шаг 4 проверен наполовину (`/health` 200 и `/api/sync/pull` 401 без токена).
result: [pending]

## Summary

total: 8
passed: 0
issues: 0
pending: 8
skipped: 0
blocked: 0

## Out of scope for this file

`33-VERIFICATION.md` lists a ninth human item — running
`tests/test_pg_parity.py` against a PostgreSQL 17 instance to restore a
**standing** PG regression guard. It is not a UAT item: it is a CI job, not an
operator-observable behaviour, and it is blocked on a pre-existing unrelated
failure (`tests/test_launcher.py::test_parse_pending_rejects_path_traversal`)
that aborts the job before its parity step. The `0027` PostgreSQL branch itself
is already proven — on real PG 17 against a throwaway copy of production plus
the live s1 rollout (`33-ROLLOUT.md` § Executed verification 3). Tracked as
backlog item 4 in `33-ROLLOUT.md`, not here.

## Gaps
