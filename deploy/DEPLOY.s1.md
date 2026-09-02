# MyOriShop — развёртывание на сервере s1 (Docker + общий Caddy)

Этот runbook — для сервера **s1**, где уже работает Docker и один общий Caddy
(контейнер `caddy` на сети `wgdashboard_default`), фронтящий все проекты.
Отличается от `deploy/DEPLOY.md` (тот — под чистый хост без Docker, свой Caddy,
systemd; на s1 он НЕ применяется).

Схема повторяет проект `build-or-kill` (`bok-app` + `bok-db`) на этом же сервере.
Домен: **ori.viktorplus.com** (DNS уже указывает на s1).

Проза — по-русски; команды, пути и переменные — латиницей.

---

## Что попадает на сервер, а что нет

- **Код приложения** (`app/`, `alembic/`, `scripts/`, мастер-xlsx справочника) —
  через `git clone`.
- **НЕ попадает** твоя тестовая база: `data/myorishop.db`, `backups/`, `.env` —
  все они в `.gitignore` (git их не несёт) и продублированы в `.dockerignore`
  (локальная сборка их тоже не берёт). Так что «чистить тестовую базу перед
  стартом» не нужно — на сервере база создаётся с нуля.

## Что такое «чистая база» здесь

Сервер стартует с **пустого тома PostgreSQL**. При старте контейнера
`alembic upgrade head` строит схему и засевает только структурный минимум:

- один склад «Склад по умолчанию» (миграция 0007) — нужен приложению;
- один пустой placeholder-товар «Демо-товар», qty 0 (миграция 0001).

Никаких тестовых товаров/складов/продаж из `seed_demo_data.py` там нет —
этот скрипт на сервере **не запускается**.

Полностью пересоздать базу (если понадобится): `docker compose ... down -v`
стирает том БД, следующий `up` поднимает чистую.

---

## 1. Код на сервер

```bash
ssh s1
sudo mkdir -p /opt/myorishop && sudo chown "$USER" /opt/myorishop
git clone <URL-репозитория> /opt/myorishop
cd /opt/myorishop
```

## 2. Секреты — `/opt/myorishop/.env.production`

```bash
umask 077
cp .env.production.example .env.production
# сгенерируй SECRET_KEY на сервере и впиши в файл:
python3 -c 'import secrets; print(secrets.token_hex(32))'
nano .env.production   # заполни POSTGRES_PASSWORD (в двух местах) и SECRET_KEY
chmod 600 .env.production
```

`DATABASE_URL` уже указывает на `ori-db:5432`; пароль в нём ДОЛЖЕН совпадать с
`POSTGRES_PASSWORD`. Файл никуда не коммитится.

## 3. Сборка и запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml logs -f ori-app   # ждём, что миграции прошли и uvicorn слушает
```

Миграции гоняются автоматически в entrypoint (fail-closed: провал миграции = сервис
не поднимается). На этом шаге в БД уже есть схема + склад по умолчанию.

## 4. Справочник (часть дистрибутива) — загрузить один раз

Справочник — это helper-таблицы `dictionary` + `catalog_prices` (D-24, ledger не
трогают). Грузится из `catalogs/oriflame_prices_with_calculations_fixed.xlsx`
внутри контейнера. `openpyxl` — dev-зависимость (в образ не вошла), поэтому
подтягиваем её эфемерно через `uv run --with`:

```bash
docker compose -f docker-compose.prod.yml exec ori-app \
  uv run --with openpyxl python scripts/import_master_pricelist.py
```

Две таблицы обрабатываются ПО-РАЗНОМУ, и это существенно (quick-задача
260902-m9g). `dictionary` по-прежнему перезаписывается целиком. `catalog_prices`
теперь только **upsert**: скрипт владеет своими тройками
`(year, number, code)` и ничем больше, поэтому история цен из архива прайсов
переживает повторный запуск. Раньше он стирал таблицу целиком, и два импортёра
затирали работу друг друга. Скрипт идемпотентен, можно перезапускать.

**`scripts/seed_demo_data.py` на сервере НЕ запускаем** — это тестовые данные.

> ⚠️ **На живом сервере — только с `--only-missing`.** Предупреждение
> остаётся в силе и после 260902-m9g: `dictionary` этот скрипт всё так же
> удаляет и пересобирает целиком, а там лежат названия, вписанные на сервере
> руками. Неразрушающим стал только ценовой путь, не справочниковый.

### 4.1. Полный справочник — обязательные два шага после мастер-прайса

Мастер-прайс покрывает только **6 856 кодов** и даёт по одной строке цены на
код («Последний каталог») — это снимок, а не история. Полный справочник —
**12 582 кода**; полная история цен — **239 184 строки** по **12 446 кодам**,
из них у **233 346** заполнены бонусные баллы (ББ). Без двух команд ниже на
сервере останется выжимка, а не справочник.

Источник — закоммиченные выгрузки `catalogs/products.json` и
`catalogs/catalog_prices.json.gz` (обе `COPY`-запечены в образ). Это НЕ
`catalogs/price_lists/` — тот архив на 118 МБ (233 файла, `.xls` + `.xlsx`)
намеренно отрезан `.gitignore` и `.dockerignore`, на сервере его нет и не будет.
Поэтому история цен едет на сервер только этим файлом; в JSON она весит 41.7 МБ,
в gzip — **4.8 МБ**, и `--export` / `--from-export` жмут и разжимают её
прозрачно по суффиксу `.gz`.

```bash
docker compose -f docker-compose.prod.yml exec ori-app \
  python scripts/import_catalogs.py --only-missing --file catalogs/products.json

docker compose -f docker-compose.prod.yml exec ori-app \
  python scripts/import_prices.py --from-export catalogs/catalog_prices.json.gz
```

`uv run --with openpyxl` здесь не нужен: openpyxl импортируется лениво и на
этих путях не используется. Обе команды аддитивны и идемпотентны — повторный
запуск вставляет и обновляет 0 строк.

Ценовая команда идёт БЕЗ `--only-missing` — и это осознанно. Раньше без него
`--from-export` сначала удалял все строки `catalog_prices`, поэтому флаг был
техникой безопасности; теперь путь неразрушающий (upsert по тройке
`(year, number, code)`, входящий `NULL` никогда не затирает уже записанное), а
`--only-missing` фильтрует по КОДУ — то есть для кода, уже известного из
мастер-прайса, не вставит НИ ОДНОЙ исторической строки. С ним на сервер приедет
та же выжимка, что и раньше. Флаг никуда не делся и по-прежнему означает
«только отсутствующие коды», но механизмом безопасности он больше не является.

> ⚠️ **`import_catalogs.py` — только с `--only-missing`.** Дефолтный путь
> перезаписывает названия, а это стёрло бы названия, вписанные на сервере
> руками (правило «побеждает последнее написание»). Для
> `import_master_pricelist.py` (§4) предупреждение тоже остаётся в силе.

Обновить сами выгрузки (локально, после правок справочника):

```bash
uv run python scripts/import_catalogs.py --export catalogs/products.json
uv run python scripts/import_prices.py --export catalogs/catalog_prices.json.gz
```

Пересобрать саму историю цен из архива прайсов (локально; `xlrd` не является
зависимостью проекта и подтягивается эфемерно — он нужен для 118 файлов `.xls`):

```bash
uv run --with xlrd python scripts/import_prices.py
```

Выгрузка **накопительная**: коды, которые есть в файле, но которых нет в
текущей базе, сохраняются — файл может только расти. Печатает
`было / добавлено / обновлено / стало`.

> ⚠️ **При ОБНОВЛЕНИИ справочника** (изменился мастер-xlsx или `app/services/rubric_overrides.json`): код и data-файлы `COPY`-запечены в образ `ori-app`, а не смонтированы томом — одного `git pull` мало. Сначала пересобери образ `docker compose -f docker-compose.prod.yml up -d --build`, дождись health и только потом запускай импорт выше, иначе контейнер перельёт СТАРЫЕ данные.

## 5. Caddy — маршрут для домена

Добавь блок из `deploy/Caddyfile.ori-block` в общий Caddyfile и перезагрузи Caddy:

```bash
sudo sh -c 'cat /opt/myorishop/deploy/Caddyfile.ori-block >> /opt/wgdashboard/Caddyfile'
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

Caddy сам выпустит и продлит TLS для `ori.viktorplus.com` (DNS уже указывает на s1).
TLS завершается только на Caddy; `ori-app` слушает 8000 лишь внутри docker-сети,
наружу порт не публикуется.

## 6. Пост-проверка

1. `https://ori.viktorplus.com/` отдаёт desktop-интерфейс (или редирект на /login).
2. `https://ori.viktorplus.com/m/` — мобильный интерфейс с того же сервера (SRV-04).
3. session-cookie несёт флаг `Secure` (DevTools → Application → Cookies).
4. `curl -s -o /dev/null -w "%{http_code}" -X POST https://ori.viktorplus.com/api/sync/push`
   → **401** (без токена).
5. Админ заводит первый device-token на `/settings/devices` и копирует его один раз.

---

## Обновление работающего сервера

```bash
cd /opt/myorishop
git pull
docker compose -f docker-compose.prod.yml up -d --build   # миграции прогонятся в entrypoint
```

Откат ниже миграции 0018 нельзя делать голым возвратом кода (она переписывает
append-only-триггеры) — используй `alembic downgrade`.

## Сброс бизнес-данных до чистого состояния

`scripts/reset_business_data.py` (quick-задача 260721-fu0) — диалект-независимый
скрипт, который удаляет **только** товары/партии/клиентов (+контакты)/продажи/
операции/кассу (`products`, `batches`, `customers`, `customer_contacts`, `sales`,
`operations`, `cash_movements`). НИКОГДА не трогает `warehouses`, `users`,
`device_tokens`, `dictionary`, `catalog_prices`/`active_catalog`, `sync_state` —
то есть склад по умолчанию, все учётные записи пользователей и справочник
Oriflame остаются нетронутыми.

Работает и локально (SQLite), и на сервере (PostgreSQL) — диалект определяется
автоматически из `app.config.settings.database_url`. Не имеет флага
`--force`/`--yes`: скрипт печатает, сколько строк в каждой таблице будет
удалено, и требует вручную ввести слово `УДАЛИТЬ` в интерактивном терминале.
Если stdin не TTY (например, вызов из CI/pipe), скрипт отказывается работать
ещё до первого запроса к БД — случайный неинтерактивный прогон невозможен.

**Локально:**

```bash
uv run python scripts/reset_business_data.py
```

**На сервере (s1):**

```bash
ssh s1
cd /opt/myorishop
docker compose -f docker-compose.prod.yml exec ori-app python scripts/reset_business_data.py
```

`docker compose exec` по умолчанию выделяет псевдо-TTY, когда сама SSH-сессия
интерактивна, — поэтому запрос подтверждения `УДАЛИТЬ` внутри контейнера
отработает так же, как и локально, без дополнительных флагов.

Порядок применения на s1: сначала прогнать локально (проверить на диспозабл-
базе, что поведение ожидаемое), затем повторить то же самое на сервере через
`exec` — обе базы независимы, скрипт не синхронизирует и не переносит данные
между ними, просто одинаково очищает каждую по отдельности.

## Бэкапы

`BACKUP_ON_STARTUP=false` — клиентский SQLite-бэкап на PostgreSQL не применяется.
Серверные бэкапы делай `pg_dump` контейнера `ori-db` по расписанию (host cron/
systemd timer), выгружая дампы на другой хост. Копия на том же диске — не бэкап.

## Troubleshooting

- **ori-app не стартует** — почти всегда провал `alembic upgrade head`.
  `docker compose -f docker-compose.prod.yml logs ori-app`.
- **502 от Caddy** — контейнер `ori-app` не healthy или не в сети
  `wgdashboard_default`. Проверь `docker inspect ori-app` → Networks.
- **Сертификат не выпускается** — DNS ori.viktorplus.com ещё не распространился.
- **401 с валидным токеном** — токен отозван/неверный, заведи новый на
  `/settings/devices`.
