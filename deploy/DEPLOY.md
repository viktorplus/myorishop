# MyOriShop — развёртывание на сервере (runbook)

Пошаговая инструкция для развёртывания приложения на чистом сервере
**Ubuntu 24.04 LTS** у любого провайдера. Все команды — универсальные; документ
намеренно НЕ выбирает за вас провайдера, тариф и домен.

Проза — по-русски (для оператора), команды, пути, имена переменных и файлов —
латиницей.

---

## Что нужно решить до начала

Этот документ сознательно НЕ принимает три решения — они остаются за вами (OQ-1):

1. **Провайдер VPS.** Подойдёт любой mainstream-провайдер с Ubuntu 24.04.
2. **Размер тарифа.** Для одного продавца с 1–3 устройствами достаточно самого
   младшего тарифа уровня **1 vCPU / 2 GB RAM**. Больше не нужно.
3. **Домен.** Проще всего — **поддомен домена, которым вы уже владеете**
   (например `shop.ваш-домен`), тогда не нужна новая регистрация.

Дальше runbook исходит из того, что сервер — это один Ubuntu 24.04-хост, а
PostgreSQL стоит на том же хосте (managed-БД на этом масштабе часто дороже
самого VPS). Docker на сервере не используется.

---

## 1. Prerequisites

- Сервер **Ubuntu 24.04 LTS**.
- Пользователь с `sudo` (не root) для установки.
- **DNS-запись A/AAAA вашего домена уже указывает на IP сервера** — это
  обязательное условие: без неё выпуск TLS-сертификата (раздел 7) не пройдёт.

```bash
sudo apt update && sudo apt upgrade -y
```

---

## 2. PostgreSQL 17

Установите PostgreSQL 17 из пакетов дистрибутива/PGDG прямо на VPS (без Docker,
без managed-инстанса):

```bash
sudo apt install -y postgresql-17
```

Создайте базу и роль (пароль придумайте надёжный, никуда его не публикуйте):

```bash
sudo -u postgres createuser --pwprompt myorishop
sudo -u postgres createdb --owner=myorishop myorishop
```

**PostgreSQL должен слушать только localhost.** По умолчанию так и есть —
проверьте, что порт 5432 не виден снаружи:

```bash
sudo ss -ltnp | grep 5432    # адрес должен быть 127.0.0.1:5432 (или ::1), не публичный
```

Если в `/etc/postgresql/17/main/postgresql.conf` стоит
`listen_addresses = '*'` — верните `localhost` и перезапустите
`sudo systemctl restart postgresql`.

---

## 3. Пользователь приложения и код

Создайте отдельного системного пользователя `myorishop` (приложение никогда не
работает под root):

```bash
sudo useradd --system --create-home --home-dir /srv/myorishop --shell /bin/bash myorishop
sudo -u myorishop git clone <URL-репозитория> /srv/myorishop
```

Установите `uv` и зависимости от имени сервисного пользователя:

```bash
sudo -u myorishop sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u myorishop sh -c 'cd /srv/myorishop && uv sync'
```

---

## 4. Файл окружения `/etc/myorishop.env`

Все секреты и настройки хоста живут ТОЛЬКО в этом файле — он никогда не
попадает в git. Создайте его и задайте четыре переменные:

- `DATABASE_URL` — строка подключения к локальному PostgreSQL, формат
  `postgresql+psycopg://myorishop:<пароль>@127.0.0.1:5432/myorishop`
- `SECRET_KEY` — ключ подписи session-cookie, сгенерированный **один раз на
  сервере**
- `SESSION_HTTPS_ONLY=true` — флаг `Secure` для cookie на публичном HTTPS-домене
- `BACKUP_ON_STARTUP=false` — SQLite-бэкап при старте на PostgreSQL бессмыслен

```bash
umask 077
sudo tee /etc/myorishop.env >/dev/null <<'ENV'
DATABASE_URL=postgresql+psycopg://myorishop:CHANGE_ME@127.0.0.1:5432/myorishop
SECRET_KEY=CHANGE_ME
SESSION_HTTPS_ONLY=true
BACKUP_ON_STARTUP=false
ENV
sudo chmod 600 /etc/myorishop.env
sudo chown myorishop:myorishop /etc/myorishop.env
```

Сгенерируйте `SECRET_KEY` прямо на сервере и впишите его в файл, **не выводя в
историю shell и не логируя**:

```bash
python3 -c 'import secrets; print(secrets.token_hex(32))'
```

Важно: этот файл нигде не коммитится; `SECRET_KEY` генерируется один раз и
никогда не печатается в лог или историю команд; **ротация `SECRET_KEY`
разлогинивает все браузерные сессии** (все cookie становятся невалидными).

---

## 5. Миграции

`uv run alembic upgrade head` запускается **автоматически** через
`ExecStartPre` в systemd-юните — так же, как это делает `run.bat` на клиенте.
Первый запуск на пустой базе PostgreSQL применяет всю историю миграций до
`0019` включительно. **Провалившаяся миграция не даёт сервису стартовать** — это
задумано: лучше не подняться, чем работать на полу-обновлённой схеме.

Можно прогнать вручную для проверки:

```bash
sudo -u myorishop sh -c 'cd /srv/myorishop && set -a && . /etc/myorishop.env && set +a && uv run alembic upgrade head'
```

---

## 6. systemd

Установите юнит приложения:

```bash
sudo cp /srv/myorishop/deploy/myorishop.service /etc/systemd/system/myorishop.service
sudo systemctl daemon-reload
sudo systemctl enable --now myorishop
journalctl -u myorishop -f      # смотрим, что старт и миграции прошли
```

---

## 7. Обратный прокси и TLS

Установите Caddy (автоматический HTTPS — выпуск и продление сертификата):

```bash
sudo apt install -y caddy
sudo cp /srv/myorishop/deploy/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/shop.example.com/ВАШ-ДОМЕН/' /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Два незыблемых правила:

- **TLS завершается ТОЛЬКО на прокси.** uvicorn остаётся на `127.0.0.1:8000` и
  никогда не слушает публичный интерфейс и не терминирует TLS сам.
- Выпуск сертификата сработает, только если DNS-запись домена уже указывает на
  этот сервер (см. Prerequisites).

(Альтернатива: если на VPS уже стоит nginx — используйте `nginx + certbot` с
`proxy_pass http://127.0.0.1:8000;` и `client_max_body_size 32m;`. Настройка
nginx в этот runbook не входит — выберите один прокси.)

---

## 8. Firewall

Откройте наружу только 22/80/443. PostgreSQL не должен быть доступен из
интернета никогда:

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 9. Резервные копии (pg_dump)

Клиентский SQLite-бэкап `VACUUM INTO` на сервере **не применяется** — он
SQLite-only и пропускается защитой по диалекту (`engine.dialect.name != "sqlite"`),
добавленной в Plan 06 Task 1. На сервере бэкапы делает `pg_dump` по расписанию:

```bash
sudo cp /srv/myorishop/deploy/myorishop-pgbackup.service /etc/systemd/system/
sudo cp /srv/myorishop/deploy/myorishop-pgbackup.timer   /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now myorishop-pgbackup.timer
systemctl list-timers | grep myorishop      # проверяем, что следующий запуск запланирован
```

Хранятся последние 30 дней (как `backup_keep: 30` на клиенте). **Копия на том же
диске — это не бэкап**: настройте выгрузку дампов на другой хост/в объектное
хранилище отдельно.

---

## 10. Пост-развёрточный чек-лист

Пройдите по пунктам после первого старта:

1. `/` отдаёт desktop-интерфейс по HTTPS.
2. `/m/` отдаёт мобильный интерфейс с **того же** сервера (SRV-04).
3. session-cookie несёт флаг `Secure` (проверьте в DevTools браузера или через
   заголовок `set-cookie`).
4. Администратор заводит первый device-token на `/settings/devices` и копирует
   открытый токен **один раз** (повторно он не показывается).
5. `POST /api/sync/push` без токена возвращает **401**.
6. `POST /api/sync/push` с валидным токеном (`Authorization: Bearer <token>`)
   возвращает **200**.

---

## 11. Мобильный интерфейс — только на сервере (SRV-04)

Мобильный интерфейс — **серверный, а не устанавливаемое приложение**. Одно
приложение (один процесс, один объект FastAPI) обслуживает оба дерева: desktop
на `/` и mobile на `/m/`. Нет мобильного установщика, нет service worker, нет
offline-кэша и нет локальной мобильной БД — мобильные пользователи всегда
работают против сервера онлайн.

Отдельно: `run.bat` на клиенте намеренно слушает `127.0.0.1` и **его нельзя**
менять на публичный адрес, «чтобы дотянуться до телефона по локальной сети» —
телефон ходит на сервер, а не на клиентский ПК. Это ограничение зафиксировано
проверкой `tests/test_sync_api.py::test_both_uis_one_app`.

---

## 12. Обновление работающего сервера

```bash
sudo -u myorishop sh -c 'cd /srv/myorishop && git pull && uv sync'
sudo systemctl restart myorishop      # миграции прогонятся через ExecStartPre
```

Откат — переключиться на предыдущий коммит и перезапустить сервис. **Внимание:**
миграция `0018` переписывает append-only-триггеры, поэтому откат ниже неё нельзя
делать голым возвратом кода — используйте `alembic downgrade`, иначе схема и код
разъедутся.

---

## 13. Troubleshooting

- **401 на sync-запрос, который нёс токен** — токен отозван или неверный.
  Проверьте `/settings/devices`, при необходимости заведите новый.
- **303-редирект на `/login` на sync-запрос** — обход session-guard для
  `/api/sync/` не сработал (потерян/опечатан префикс). Sync-дерево не должно
  проходить через cookie-guard.
- **Сервис не стартует** — почти всегда провал миграции в `ExecStartPre`.
  Смотрите `journalctl -u myorishop`.
- **Сертификат не выпускается** — DNS-запись домена ещё не указывает на этот
  сервер. Дождитесь распространения DNS и `sudo systemctl reload caddy`.
