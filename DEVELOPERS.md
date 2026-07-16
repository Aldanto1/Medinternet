# Мединтернет — документация для разработчиков

Медицинский ИИ-поисковик для врачей и фармацевтов в виде Telegram-бота с Mini App
(совместно с Сеченовским Университетом). Плюс отдельный CRM-сервис для рассылок.

- **Бот:** `@medinternet_bot` (прод), `@medinternetDev_bot` (локальная разработка/тесты)
- **Репозиторий:** GitHub `Aldanto1/Medinternet`
- **Хостинг:** Railway (проект `truthful-illumination`), auto-deploy при `git push` в `main`
- **БД:** Neon (serverless PostgreSQL), база `neondb`

---

## 1. Архитектура

Три компонента:

1. **Бот + веб-сервер Mini App** — один процесс (`bot.py`): aiogram 3 (long-polling) и
   aiohttp-сервер (отдаёт Mini App и API) поднимаются вместе.
2. **Telegram Mini App** — статика в `webapp/` (HTML/CSS/JS + Telegram WebApp SDK),
   раздаётся тем же aiohttp-сервером.
3. **CRM-сервис рассылок** — отдельный сервис в `crm-service/` (aiohttp API + веб-панель,
   arq-воркер на Redis, отправка токеном основного бота).

### Стек
Python 3.11+, aiogram 3.29, aiohttp, asyncpg (Neon), arq + Redis (очередь CRM),
PyJWT (вход в CRM), RX Code AI API (медицинский RAG).

---

## 2. Структура репозитория

```
bot.py            — точка входа: polling + веб-сервер, установка кнопки меню и описания бота
handlers.py       — /start, deep-link регистрация, навигация по inline-кнопкам, /help
server.py         — aiohttp: раздаёт Mini App + API (/api/me, /api/ai/*, /link, /api/register legacy)
db.py             — пул asyncpg + таблицы users/ai_sessions/link_tokens/start_prompts
config.py         — загрузка env, WEBAPP_VERSION (кэш-бастинг), автоопределение прокси
ai_client.py      — клиент RX Code AI (сессии: create chat, send/stream messages)
link_token.py     — подписанные одноразовые токены deep-link (HMAC на BOT_TOKEN)
webapp/           — Mini App: index.html, style.css, app.js, link.html, logo.png, logo_tg.png
env/.env          — секреты (в .gitignore)
.claude/launch.json — конфиги локального запуска (bot-local, webapp-static, crm-web-static)

crm-service/
  app/main.py         — aiohttp API + раздача панели
  app/db.py           — доступ к Neon (read-only public.users, запись в схему crm)
  app/api/            — auth.py, segments.py, broadcast.py, middleware.py
  app/queue/          — tasks.py, worker.py (arq)
  app/bot_client.py   — отправка сообщений токеном основного бота
  app/web/            — панель: index.html, panel.js, panel.css
  tests/              — pytest
```

---

## 3. Переменные окружения

Секреты **только** в `env/.env` (локально, в `.gitignore`) и в переменных Railway.
В `.env.example` — только плейсхолдеры, никогда не коммитить реальные значения.

### Бот (`env/.env` / Railway service «Medinternet»)
| Переменная | Назначение |
|---|---|
| `BOT_TOKEN` | токен бота |
| `DATABASE_URL` | Neon, роль `neondb_owner` (полный доступ) |
| `WEBAPP_URL` | публичный HTTPS-адрес Mini App (без него кнопки Mini App не появятся) |
| `NEURO_API_URL` | базовый адрес RX Code AI **без** `/api` в конце (прод: `https://qa.rxcode.pro`) |
| `NEURO_API_KEY` | ключ RX Code AI (код делает `.strip()` — перенос строки ломает заголовок) |
| `NEURO_CHANNEL` | канал RX Code AI, по умолчанию `michat` |
| `PROXY_URL` | SOCKS/HTTP-прокси для обхода блокировок (локально; на Railway пусто) |
| `PORT` | порт веб-сервера (Railway задаёт сам; локально 8080) |

### CRM (`crm-service/.env` / Railway services «crm-api», «crm-worker»)
| Переменная | Назначение |
|---|---|
| `CRM_DB_URL` | Neon, роль `crm_reader` (только чтение public.users) |
| `MAIN_BOT_TOKEN` | токен основного бота = `${{Medinternet.BOT_TOKEN}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `JWT_SECRET` | подпись JWT для входа сотрудника |
| `CRM_LOGIN_EMAIL` / `CRM_LOGIN_PASSWORD` | учётка входа в панель |

---

## 4. База данных (Neon, `neondb`)

### Таблицы `public`
- **users** — `telegram_id` (PK), `username`, `full_name`, `phone`, `email`, `birth_date`,
  `med_id`, `specialty`, `position`, `created_at`, `updated_at`.
  Регистрация через deep-link заполняет `username` + `full_name`; `specialty`/`position`
  зарезервированы (позже из БД medinternet); `med_id`/`phone`/`email`/`birth_date` — legacy, обычно NULL.
- **ai_sessions** — `telegram_id` (PK) → `chat_id` (id сессии RX Code AI).
- **link_tokens** — `token` (PK), `used_by`, `used_at` — «погашенные» одноразовые токены регистрации.
- **start_prompts** — служебные записи стартовых сообщений.

### Схема `crm` (данные CRM-сервиса)
- **blocked_users** — кто заблокировал бота (исключаются из рассылок).
- **broadcast_log** — статусы доставки по каждой рассылке.

### Роли
- `neondb_owner` — бот, полный доступ (`DATABASE_URL`).
- `crm_reader` — CRM: только SELECT на `public.users`, чтение/запись в схему `crm` (без DELETE).

> ⚠️ Роли в Neon создавать **только через SQL Editor**, НЕ через консоль Neon — консольные
> роли попадают в `neon_superuser` (полный доступ), и их потом нельзя понизить/удалить.

Особенность asyncpg: не понимает `sslmode`/`channel_binding` в DSN — `db._clean_dsn()`
их вырезает, SSL включается отдельно (`ssl="require"`).

---

## 5. Ключевые потоки

### 5.1 Регистрация (deep-link с подписанным токеном)
1. Незарегистрированный открывает Mini App → экран регистрации со ссылкой на сайт;
   в главном сообщении бота — «Для регистрации следуйте инструкции в мини-аппе».
2. Тап по ссылке → страница `/link` (`webapp/link.html`, прототип личного кабинета сайта).
   Сервер (`server.handle_link`) на **каждый заход** генерирует свежий подписанный
   одноразовый токен и подставляет кнопку `t.me/<bot>?start=<token>`.
3. Тап по кнопке → `/start` с токеном → `handlers._register_via_link`:
   `link_token.verify_link_token` (HMAC на `BOT_TOKEN`) + `db.claim_link_token`
   (атомарная одноразовость через `INSERT ... ON CONFLICT DO NOTHING`) →
   `db.register_user` (сохраняет `username` + `full_name`) →
   короткое «🎉 Регистрация успешна» + кнопки «Открыть Mini App» и «🏠 Главная».
4. Mini App сам закрывается при уходе в фон (`app.js` `closeAfterSiteVisit`) — пользователь открывает заново.

### 5.2 Навигация в чате бота
`/start` без токена → главное сообщение: фото-логотип + подпись (в слове «Мединтернет»
ссылка на сайт) + inline-навигация 2×2 (Партнёрам / Мой тариф / Инструкция / Помощь) +
большая кнопка «🔍 Открыть Mini App» (web_app). Нажатие раздела удаляет главное сообщение
и шлёт под-сообщение с кнопкой «← Вернуться» (`nav:home`).
- **Партнёрам** — реф-питч + шеринг (Telegram/WhatsApp). Реф-трекинг ещё НЕ реализован.
- **Инструкция** — советы «как пользоваться» (те же, что в Mini App).
- **Помощь** — Оставить отзыв (заглушка), Написать в поддержку (`@traderx_p2p`),
  Пользовательское соглашение (сайт).
- **Мой тариф** — текущий тариф + подписки Плюс на неделю/месяц/год (заглушки, цены позже).

Описание в **пустом чате** («Что умеет этот бот?») ставится через `bot.set_my_description`
(в `bot.py`, применяется на каждом деплое). Картинку-логотип над описанием
(`webapp/logo_tg.png`, 640×360) Bot API ставить не умеет — задаётся **вручную в @BotFather**.

### 5.3 ИИ-поиск (RX Code AI)
- Сессионный API: `POST /api/chats {UserId, Channel: michat}` → `chatId`;
  затем `POST /api/chats/{id}/messages` или `.../messages/stream`.
- Авторизация — заголовком **`X-API-Key`** (НЕ `Bearer`!). Канал — **`michat`** (с `telegram` → 404).
- Стриминг: SSE (события Action/Text). Mini App читает через `/api/ai/message/stream`
  (SSE-прокси в `server.py`), рендерит ответ постепенно.
- `ai_sessions` хранит связку `telegram_id → chatId`.

### 5.4 CRM-рассылки
Панель: вход (email/пароль → JWT) → **Получатели** (по Telegram ID + ник: поиск,
кнопка «Список», клик по пользователю → карточка со всей информацией) → конструктор
сообщения (блоки title/subtitle/text/link) + прикрепление файла → отправка → статус (поллинг).
- Адресация по `telegram_id` (фильтр `tg_ids`); `med_ids` — legacy.
- Воркер: `max_jobs=1` + `sleep(1/25)` (троттлинг Telegram). Заблокировавшие бота
  (`TelegramForbiddenError`) → `crm.blocked_users`, исключаются.
- Файл рассылки грузится в Telegram один раз, дальше переиспользуется `file_id`.
- Telegram НЕ умеет размеры шрифта — заголовки только жирные.

---

## 6. Mini App

Дизайн повторяет `medinternet.ru`: шрифт **IBM Plex Sans** (грузится не-блокирующе),
акцент бирюза `#00AAB0`, фон дымчатый `#F1F3F2`, белые карточки `border-radius: 16px`,
кнопки-пилюли `50px`. Токены — в `:root` в `style.css`. Есть светлая/тёмная тема (переключатель).

Вкладки: **Поиск** (чат с ИИ), **Кабинет** (ФИО/специальность/должность — пока пустые,
позже из БД medinternet; данные из `/api/me`), **Инфо**.

Кэш-бастинг (Telegram Desktop держит старьё): `config.WEBAPP_VERSION` = timestamp старта
процесса; подставляется в URL кнопок и в ссылки на `style.css`/`app.js`; всё отдаётся с
`Cache-Control: no-store`.

Эндпоинты сервера: `/api/me`, `/api/ai/message`, `/api/ai/message/stream`, `/api/ai/reset`,
`/link`, `/api/register` (legacy). Валидация Telegram initData — HMAC.

---

## 7. Локальная разработка

```
# venv (Windows)
venv/Scripts/python.exe bot.py          # бот + сервер на :8080 (конфиг bot-local)

# статичный предпросмотр вёрстки (без бэкенда /api)
python -m http.server 5055 --directory webapp
python -m http.server 5056 --directory crm-service/app/web

# тесты CRM
cd crm-service && python -m pytest
```

Конфиги предпросмотра — в `.claude/launch.json`.

> Важно: статичный сервер не отвечает на `POST /api/me` (инициализация Mini App зависает) —
> для полноценной проверки UI запускать реальный сервер бота (`bot-local`, порт 8080).

### Сетевые ограничения (РФ)
Локальная сеть душит туннели и Telegram API. `config.PROXY_URL` берётся из `PROXY_URL`
или автоматически из настроек прокси Windows (SOCKS). Telegram API и отправка рассылок
из РФ-IP заблокированы — прод работает только на Railway (зарубежный IP).

---

## 8. Деплой (Railway, проект `truthful-illumination`)

Auto-deploy при `git push origin main`. Сервисы:
- **Medinternet** — бот (`bot.py`), Root Directory = корень репозитория.
- **crm-api** — `python -m app.main`, Root Directory = `crm-service`
  (домен `crm-api-production-2132.up.railway.app`).
- **crm-worker** — `arq app.queue.worker.WorkerSettings`, Root Directory = `crm-service`.
- **Redis** — очередь arq.

Настройки, задаваемые в @BotFather (НЕ в коде): кнопка «Открыть» в списке чатов
(Main Mini App), картинка описания в пустом чате.

---

## 9. Ручные операции

### Удалить пользователей (Neon SQL Editor, роль `neondb_owner`)
```sql
DELETE FROM ai_sessions;
DELETE FROM link_tokens;
DELETE FROM start_prompts;
DELETE FROM users;              -- после этого все регистрируются заново
```
Одного: `DELETE FROM ai_sessions WHERE telegram_id = <id>; DELETE FROM users WHERE telegram_id = <id>;`
Обязательна только чистка `users`; остальные три — для порядка. `DELETE` в Neon необратим.

---

## 10. Грабли (важно помнить)

- **RX Code AI:** авторизация `X-API-Key` (не Bearer), канал `michat` (не telegram),
  `NEURO_API_KEY` обязательно `.strip()` (перенос строки → «Forbidden control character in headers»).
- **asyncpg:** `sslmode`/`channel_binding` в DSN не поддерживаются — вырезаются в `_clean_dsn`.
- **Подпись фото** (главное сообщение бота) — лимит Telegram 1024 символа.
- **Картинка описания** пустого чата — только через @BotFather, не через Bot API.
- **Neon-роли** — только через SQL Editor (см. §4).
- **Telegram-форматирование** — размеров шрифта нет, только жирный/курсив/ссылки.
- **PowerShell + git commit:** в сообщениях коммита через here-string избегать двойных
  кавычек и токенов вида `/start` (ломают парсинг git / срабатывает песочница).

---

*Документ описывает состояние проекта на момент написания. Реф-трекинг партнёрской
программы, цены подписок Плюс и заполнение профиля из БД medinternet — в планах, ещё не реализованы.*
