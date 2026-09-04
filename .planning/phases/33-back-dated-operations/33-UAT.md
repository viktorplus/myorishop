---
status: partial
phase: 33-back-dated-operations
source: [33-VERIFICATION.md]
started: 2026-09-04T16:29:34Z
updated: 2026-09-04T19:20:00Z
---

## Current Test

[testing paused — 1 item outstanding]

## Tests

**CORRECTION (2026-09-04, second session): B-1 … B-7 WERE run automatically and
all seven passed.** The earlier note below was wrong about the cause, and the
wrong cause led to writing off seven runnable checks as human-only.

*What the earlier note claimed:* the Claude-in-Chrome extension has no site
permission for `localhost` / `127.0.0.1`.

*What was actually true:* **two Chrome browsers were connected to the account,
and the tooling was driving the wrong one.** Re-measured this session — the
first navigation to `http://127.0.0.1:8000/` returned `ERR_CONNECTION_REFUSED`
(read out of the error page's own text), not a permission error. After listing
the connected browsers and selecting "Browser 1" (deviceId `8cc4cfbe…`), the
very same tooling rendered the app's login page on the first try. Nothing about
site permissions was ever the problem.

*A second stale fact in the earlier note:* it named PID **39100** on port 8000
as "the operator's own instance". Port 8000 does hold a `uvicorn` process, but
it answers `404 {"detail":...}` on both `/` and `/login` — it is NOT MyOriShop.
No MyOriShop instance was running locally at all. It was neither started,
stopped nor restarted.

**How B-1 … B-7 were actually run.** Own isolated instance, port **8137**,
server PID **36160**, `MYORISHOP_DATA_DIR` in a scratch directory,
`BACKUP_ON_STARTUP=false`, `SYNC_SERVER_URL=""`. Its database is a **copy** of
the operator's real `data/myorishop.db` (71 MB) — the original was never opened
by this instance. Version banner read **MyOriShop 1.101**, i.e. the phase-33
code.

Two by-products worth keeping:

- migration **`0026 → 0027` ran cleanly on a copy of the operator's real
  local database** (it was still on `0026`);
- the operator's local DB holds `products: 0`, `batches: 0`, `operations: 0`,
  `sales: 0` but a full `dictionary` (12 582 rows) — the business data lives on
  s1, not locally. Test fixtures for these runs were therefore created fresh
  through the real UI.

The operator performed exactly one action: typing their own password into the
login form (`POST /login → 303` confirmed in the server log). No credential was
ever handled by the tooling.

**Sources.** Items 1–7 are the B-1 … B-7 rows of `33-UI-SPEC.md` § Verification
the executor must run. Their Russian wording below is verbatim from
`33-ROLLOUT.md` § Browser checks, which is where the Russian text of those same
rows lives — the UI-SPEC table itself is written in English. Item 8 is gap 1 of
`33-ROLLOUT.md` § Executed rollout. This file and `33-ROLLOUT.md` record the
same eight items and must not drift apart.

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
result: pass
observed: |
  Ran on `/receipts/new` (the GET page; bare `/receipts` is POST-only). Form
  filled valid, then `op_date` set to 2026-09-05 so the date was the ONLY
  invalid field — verified, not assumed: `form.elements` filtered by
  `!checkValidity()` returned exactly `[op_date]`, with
  `validity.rangeOverflow === true` against `max="2026-09-04"`.
  Clicking the real «Сохранить приход» button produced the native bubble
  «Максимальное значение должно быть 04.09.2026.» anchored to the date field.
  Request suppression confirmed from BOTH sides: the tab's network log held no
  request to `/receipts`, and `grep -c "POST /receipts"` over the server's own
  access log returned **0**. The only outbound call was the code-autocomplete
  `GET /receipts/lookup … → 204`.
evidence: screenshot-1788548697865-6.jpg

### 2. B-2 — Server guard renders inside the swapped mobile step, where `max` is inert
steps: `/m/receipts`, шаг 4: поставьте дату в шапке на завтра, нажмите «Сохранить приход».
expected: Запрос УХОДИТ, и в ответе первой строкой подменённого шага, прямо под всё ещё заполненным полем даты, появляется «Дата операции не может быть в будущем.»
why_human: The server half is test-proven (VA-14, 5 passed); the rendered placement of the error inside the swapped mobile step is not.
result: pass
observed: |
  The premise of this check was confirmed structurally before testing it: the
  mobile `op_date` DOES carry `max="2026-09-04"`, but it lives OUTSIDE
  `#wizard-step` (`!d.closest('#wizard-step')` → true) — in the persistent
  shell. The step-4 button therefore submits a form that does not contain the
  date input, so the browser never validates it. That is exactly the hole the
  server guard has to close.
  Walked the real wizard 1 → 2 → 3 → 4 (product 1276 from the dictionary,
  qty 3), set the header date to 2026-09-05, pressed «Сохранить приход».
  Request DID go out: `POST /m/receipts → 422` in the server log. The message
  «Дата операции не может быть в будущем.» rendered as the FIRST line of the
  swapped step, directly under the date field, which still showed 05.09.2026;
  step 4 kept every entered value. Nothing was written — `operations` stayed
  at 0.
evidence: screenshot-1788548850207-7.jpg

### 3. B-3 — The typed date survives the mobile basket round-trip
steps: `/m/sales`: поставьте дату, добавьте товар, вернитесь в корзину, добавьте второй.
expected: Дата осталась той, что вы поставили, и НЕ сбросилась на сегодня.
why_human: htmx swap/round-trip persistence of a field inside the persistent wizard shell; the tests assert the template renders it, not that a real multi-swap session preserves it.
result: pass
observed: |
  Date deliberately set to 2026-09-03 (yesterday) so a silent reset to today
  would be unmissable. Walked the full round-trip the check describes:
  step 1 → 2 → 3 → корзина → «Добавить товар» → step 1 → 2 → 3 → корзина.
  The header date read `2026-09-03` after every one of those swaps, and the
  basket ended with two lines (two «Удалить» buttons). No reset to today.
evidence: screenshot-1788549117136-9.jpg

### 4. B-4 — Two cash date fields, correct label association
steps: `/finance` и `/m/finance`.
expected: Два поля даты; клик по каждой подписи ставит фокус в СВОЁ поле (id `withdraw-op-date` и `deposit-op-date`).
why_human: `<label for>` focus association is a browser behaviour.
result: pass
observed: |
  Both `/finance` and `/m/finance` render exactly two operation-date fields,
  `withdraw-op-date` and `deposit-op-date`, each carrying `max="2026-09-04"`,
  each id appearing exactly once in the document (checked for duplicates —
  a duplicate id is the classic way this association silently breaks).
  Clicking each «Дата операции» label moved `document.activeElement` to ITS
  OWN field on both pages (4 of 4 assertions true). The page's other two date
  inputs (`from` / `to`) are the report-period filters, correctly without
  `max`.

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
result: pass
observed: |
  **No horizontal scrollbar at 1024 px. The fix was NOT applied**, per the
  do_not_fix instruction above.
  The browser window was maximised and `resize_window` could not shrink it
  (reported success, `innerWidth` stayed 1920), so the measurement was taken in
  a same-origin iframe of width exactly 1024 px loading `/history` — a real
  1024-CSS-pixel layout, not an estimate. Inside it:
  `documentElement.scrollWidth === clientWidth === 1024` → overflow 0 px.
  The code-level risk is confirmed real but does not bite: `.filter-bar`
  computes to `display:flex`, **`flex-wrap: nowrap`**, `gap:16px`, and does now
  hold **4** `<select>` children. They occupy 828 px + 3 × 16 px of gaps =
  **876 px of the 960 px** container — about 84 px of headroom.
  So D-21 stays deferred on a measurement rather than on a guess. The headroom
  is real but not generous: a fifth filter, or an option longer than «Сначала
  новые (по умолчанию)», would consume it.
  Also checked in passing (CLAUDE.md standing check): all four filter selects
  render non-empty — `type` 10 options, `sort` 2, `author` 5, `dated` 3.
evidence: screenshot-1788548977274-8.jpg

### 6. B-6 — Nothing changed visually before any back-dated operation exists
steps: `/history` и `/m/history` ДО того, как появится хоть одна операция задним числом.
expected: Каждая ячейка «Когда» и каждая шапка мобильной карточки выглядят ровно как раньше — одна строка `дд.мм.гггг чч:мм`, без пометки.
why_human: Visual byte-identity of the untouched path — DATE-07's visible half. The template guard is verified in code (the `r.is_backdated` false branch), but the rendered result was never observed.
result: pass
observed: |
  Checked at the DOM level rather than by eye, which is stricter than the
  wording asks. For a same-day operation the desktop «Когда» cell's `innerHTML`
  is exactly `04.09.2026 22:08` with `children.length === 0` — no wrapper, no
  `<span>`, no badge, nothing to render differently than before. The mobile
  card header is `<p class="muted">04.09.2026 22:08 · Приход</p>` — one line,
  no marker.
  Confirmed from the other direction too, after a back-dated operation existed:
  that row's cell becomes
  `03.09.2026<br><span class="muted">задним числом · внесено 04.09.2026 22:12</span>`
  (`children.length === 2`) while the same-day rows in the very same table stay
  at `children.length === 0`. The untouched path really is untouched.
  One false alarm worth recording so it is not re-raised: a naive text search
  for «задним числом» matches the page even with no back-dated data — the
  string is in the new `dated` filter's option list («Все» / «Только задним
  числом» / «Только в день операции»), not in any row.

### 7. B-7 — CSV column contract in a real downloaded file
steps: Выгрузите `sales.csv` и `cash_movements.csv` после того, как появится хотя бы одна операция задним числом.
expected: Одна новая колонка, заголовок «Внесено» — последний; первая колонка не убывает сверху вниз; `Код` / `Цена` / `Сумма` на прежних местах.
why_human: Spreadsheet-consumer contract. The writers are test-pinned, but the real downloaded file was never opened.
result: pass
observed: |
  Both files were fetched from the running app over the logged-in session and
  read as text — i.e. the exact bytes the endpoints serve. (Deliberately not a
  browser download: the byte stream is what the contract is about, and this
  avoids dropping files into the operator's Downloads folder.) Routes are
  `/export/sales.csv` and `/finance/report.csv` — note the cash dump is NOT
  under `/export`.

  `sales.csv` header:
  `Когда;Код;Товар;Кол-во;Цена;Себестоимость;Валюта;Покупатель;Кто;Внесено`
  `cash_movements` header:
  `Когда;Категория;Валюта;Комментарий;Сумма;Внесено`

  - **One new column, «Внесено» last** — true in both files.
  - **Prior columns unmoved** — verified against git rather than by eye.
    At `3a9c19c` (parent of the first phase-33 commit) the headers were
    `Когда, Код, Товар, Кол-во, Цена, Себестоимость, Валюта, Покупатель, Кто`
    (9) and `Когда, Категория, Валюта, Комментарий, Сумма` (5). Today's are
    those same lists in the same order with one name appended. `Код`, `Цена`
    and `Сумма` keep their positions.
  - **First column non-decreasing top-to-bottom** — true in both, and tested on
    real multi-date data, not a single row: sales rows read `03.09.2026` then
    `04.09.2026`; cash rows read `03.09.2026`, `03.09.2026`, `04.09.2026`.

  Fixtures for this were created through the real UI: a back-dated sale
  (03.09), a same-day sale (04.09), a back-dated deposit (03.09) and a same-day
  withdrawal (04.09).
carry_forward: |
  Not a defect — an accepted cost of D-23 that a spreadsheet consumer will meet,
  so it is recorded here rather than left in a code comment: column 1's value
  TYPE narrows from `dd.mm.yyyy HH:MM` to `dd.mm.yyyy`. The clock time is not
  lost, it reappears verbatim in «Внесено». A formula reading column 1 as a
  datetime now receives a date. Column POSITIONS are what stayed stable.

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
result: blocked
blocked_by: physical-device
reason: |
  Needs a real client device still on schema `0026` presenting its own valid
  device token against live s1. Not runnable here on either half: the
  developer token must not be used (local dev rows would land in the
  production database), and the tooling is not permitted to authenticate to
  the production site — `https://ori.viktorplus.com` was reachable this
  session but served the login form.
  Incidental observation while confirming that: the s1 banner reads
  **MyOriShop 1.100** while local HEAD is **1.101** — worth a glance before
  the push test, since this item is about a version/schema skew.
  Still the sole blocker on the client release tag.

## Summary

total: 8
passed: 7
issues: 0
pending: 0
skipped: 0
blocked: 1

All seven browser checks (B-1 … B-7) passed. The single outstanding item is 8,
blocked on hardware/credentials that do not exist in this environment, and it
is the one thing still holding the client release tag.

Environment used, for anyone re-running these: own instance on port **8137**
(PID 36160), scratch data dir, database a copy of the operator's real local
`myorishop.db`, app version **1.101**. Nothing was written to the operator's
own data, and no pre-existing process was started, stopped or restarted.

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
