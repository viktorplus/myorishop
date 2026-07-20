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

Скрипт делает full-replace обеих таблиц в одной транзакции; можно перезапускать.
**`scripts/seed_demo_data.py` на сервере НЕ запускаем** — это тестовые данные.

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
