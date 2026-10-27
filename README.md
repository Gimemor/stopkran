# Стоп-кран

Telegram Mini App: анонимный «суд» над импульсными покупками.
Фронтенд — один статический `index.html`, бэкенд — FastAPI + SQLAlchemy, БД — Postgres
(локально в Docker, в проде — Supabase).

```
index.html  ──HTTP──▶  FastAPI (backend/)  ──asyncpg──▶  Postgres
  (только URL API)      секреты в .env       SQLAlchemy
```

В браузере нет ни одного секрета: ни ключей, ни пароля БД, ни токена бота.

## Быстрый старт

```powershell
.\run.ps1            # Windows / PowerShell
```
```bash
./run.sh             # macOS / Linux / Git Bash
```

Поднимает Postgres + pgAdmin + FastAPI, ждёт готовности БД и печатает адреса:

| Сервис | Адрес | Логин |
|---|---|---|
| API / Swagger | http://localhost:8000/docs | — |
| Лента (JSON) | http://localhost:8000/api/feed | — |
| pgAdmin | http://localhost:5050 | `admin@example.com` / `admin` |
| Postgres | `localhost:5432` | `stopkran` / `stopkran`, db `stopkran` |

Схема и демо-данные применяются автоматически при **первом** старте контейнера.

```powershell
.\run.ps1 -Logs       # логи API
.\run.ps1 -Down       # остановить (данные сохраняются)
.\run.ps1 -Reset      # снести volume → чистая БД
.\run.ps1 -NoPgAdmin  # без pgAdmin
```

Фронтенд открывайте через локальный сервер, не `file://` (иначе CORS блокирует запросы):

```bash
npx --yes serve -l 5500 .
# → http://localhost:5500
```

## Структура

```
index.html                 фронтенд (статика, без сборки)
run.ps1 / run.sh           запуск локальной среды
docker-compose.yml         postgres + pgadmin + api
.devcontainer/             dev container (та же среда)
pgadmin/servers.json       пред-настроенный сервер в pgAdmin
backend/
  app/
    main.py                FastAPI app, CORS, lifespan
    api.py                 GET /api/feed, POST /api/requests, POST /api/votes
    config.py              pydantic-settings, читает .env
    db.py                  async engine (asyncpg), pooler-safe
    models.py              ORM: requests, votes
    schemas.py             Pydantic v2
    telegram.py            проверка initData (HMAC-SHA256)
    bot.py                 вебхук бота: /start, inline-режим, статус
    set_webhook.py         регистрация вебхука (python -m app.set_webhook)
    init_db.py             create_all для разработки
  db/init/                 SQL, применяемый при инициализации volume
    001-schema.sql         таблицы (локальный Postgres)
    002-demo-data.sql      демо-заявки и голоса
  schema.sql               DDL для Supabase (с RLS-политиками)
  Dockerfile               python:3.12-slim, non-root, healthcheck
  .env.example             шаблон (коммитится)
  .env                     секреты (gitignored)
  fly.toml                 деплой на Fly.io
```

## API

| Метод | Путь | Описание |
|---|---|---|
| `GET` | `/api/health` | статус + доступность БД |
| `GET` | `/api/feed` | лента с агрегатами голосов |
| `POST` | `/api/requests` | создать заявку → `{id}` |
| `POST` | `/api/votes` | голос; `409`, если уже голосовал |
| `POST` | `/api/telegram/webhook` | апдейты от Telegram (secret token в заголовке) |
| `GET` | `/api/telegram/status` | настроен ли бот (без раскрытия токена) |
| `GET` | `/docs` | Swagger UI |

Авторизация: заголовок `X-Telegram-Init-Data` (проверяется HMAC-SHA256 с токеном бота).
Для локальной разработки — `X-Dev-User-Id`, пока `DEV_ALLOW_UNVERIFIED=true`.

## Переменные окружения (`backend/.env`)

| Переменная | По умолчанию (локально) | Прод |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://stopkran:stopkran@db:5432/stopkran` | pooler Supabase |
| `DB_SSL` | `false` | `true` |
| `TELEGRAM_BOT_TOKEN` | пусто | токен @BotFather |
| `TELEGRAM_AUTH_MAX_AGE` | `86400` | `86400` |
| `DEV_ALLOW_UNVERIFIED` | `true` | **`false`** |
| `MINI_APP_URL` | пусто | HTTPS-адрес Mini App |
| `TELEGRAM_WEBHOOK_SECRET` | случайная строка | та же при `set_webhook` |
| `FREE_LIMIT` | `0` (без лимита) | `3` |
| `CORS_ORIGINS` | localhost | точный origin фронтенда |
| `ENVIRONMENT`, `PORT` | `dev`, `8000` | `production` |

Хост `db` работает внутри Docker. Если запускаете `uvicorn` на хосте — замените на
`localhost` (см. комментарий в `.env`).

### Supabase вместо локальной БД

`backend/schema.sql` содержит DDL с RLS. Для контейнеров нужен **pooler**
(Dashboard → Connect → Transaction pooler): прямой хост `db.<ref>.supabase.co`
отдаёт только IPv6. `db.py` уже отключает prepared statements — пулеру это нужно.

## Запуск

### Dev container

VS Code → **Reopen in Container** — используется тот же `docker-compose.yml`,
порт 8000 проброшен, `uvicorn --reload` смотрит на смонтированный код.

### Docker Compose

```bash
docker compose up -d --build
docker compose logs -f api
docker compose down -v      # снести вместе с данными
```

### Без Docker

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m app.init_db       # если БД ещё пустая
uvicorn app.main:app --reload
```

## Telegram Mini App

Бот — точка входа и шаринг. Лента работает и без него.
Токен лежит **только** в `backend/.env` (`TELEGRAM_BOT_TOKEN`), на фронтенд не попадает.

1. `TELEGRAM_BOT_TOKEN` — от [@BotFather](https://t.me/BotFather) (`/newbot`, затем `/token`).
2. `MINI_APP_URL` — **HTTPS**-адрес, где лежит `index.html`. Telegram не принимает `http`
   и `localhost`. Для локальной проверки:
   ```bash
   npx --yes serve -l 5500 .
   cloudflared tunnel --url http://localhost:5500
   # → https://<random>.trycloudflare.com  (вставьте в MINI_APP_URL)
   ```
3. Перезапустите api и зарегистрируйте вебхук (публичный HTTPS-адрес **API**, не фронтенда):
   ```bash
   docker compose exec api python -m app.set_webhook https://<public-host>
   # снять: ... python -m app.set_webhook --delete
   ```
4. В @BotFather: **Bot Settings → Menu Button** → тот же `MINI_APP_URL`.
   Для кнопки «Поделиться» включите inline-режим: `/setinline` (сейчас у бота он выключен).

Проверка конфигурации:

```bash
curl http://localhost:8000/api/telegram/status
# {"bot_configured":true,"mini_app_url_set":false,"webhook_secret_set":true,"init_data_verification":false}
```

`init_data_verification: false` — потому что `DEV_ALLOW_UNVERIFIED=true` (браузер без подписи).
С токеном и `DEV_ALLOW_UNVERIFIED=false` бэкенд принимает **только** подписанный `initData`:
`X-Telegram-Init-Data` проверяется HMAC-SHA256 по токену бота + `auth_date`.

## Деплой

Образ универсальный (`backend/Dockerfile`), слушает `$PORT`.

**Fly.io** (конфиг готов):
```bash
cd backend
fly launch --no-deploy
fly secrets import < .env       # DATABASE_URL, TELEGRAM_BOT_TOKEN, ...
fly deploy
```

**Google Cloud Run:**
```bash
gcloud run deploy stopkran-api \
  --source backend --region europe-west1 --allow-unauthenticated \
  --set-env-vars ENVIRONMENT=production,DEV_ALLOW_UNVERIFIED=false
```

**Railway / Render / Koyeb:** подключите репозиторий, укажите Dockerfile `backend/Dockerfile`,
добавьте переменные из `.env`. Render free tier засыпает — вебхуки Telegram будут теряться.

Затем на фронтенде поменяйте одну строку:

```js
API_BASE: "https://stopkran-api.fly.dev"
```

и в BotFather → **Bot Settings → Menu Button** укажите URL, где лежит `index.html` (нужен HTTPS).

## Что осталось за рамками

- **Pro / платежи** — локальный флаг в `localStorage`; нужен Telegram Stars invoice + серверная выдача.
- **Follow-up через 24 часа** — таймер живёт в браузере (`localStorage`), бот не пишет. Нужен cron + `sendMessage`.
- **`X-Dev-User-Id`** — только для dev; в проде `DEV_ALLOW_UNVERIFIED=false`.
- **Демо-данные** из `002-demo-data.sql` — удалите файл перед первым стартом, если нужна пустая лента.
