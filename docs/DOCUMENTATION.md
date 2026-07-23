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
server.py         — aiohttp: раздаёт Mini App + API (/api/me, /api/ai/*, /api/history/*, /link, /api/register legacy)
db.py             — пул asyncpg + таблицы users/ai_sessions/link_tokens/start_prompts/chats/chat_messages
config.py         — загрузка env, WEBAPP_VERSION (кэш-бастинг), автоопределение прокси
ai_client.py      — клиент RX Code AI (сессии: create chat, send/stream messages)
link_token.py     — подписанные одноразовые токены deep-link (HMAC на BOT_TOKEN)
webapp/           — Mini App: index.html, style.css, app.js, link.html + картинки:
                    logo.png (экран регистрации), logo_bot.png (фото главного сообщения бота),
                    robot.png (иконка робота у приветствия), logo_tg.png (картинка описания для BotFather)
docs/             — документация: этот файл, RXCODE_AI_API.md, swagger-mi.json
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
  `med_id`, `specialty`, `position`, `created_at`, `updated_at`,
  `last_bot_action_at`, `last_search_at`.
  Регистрация через deep-link заполняет `username` + `full_name`; `specialty`/`position`
  зарезервированы (позже из БД medinternet); `med_id`/`phone`/`email`/`birth_date` — legacy, обычно NULL.
  **Активность:** `last_bot_action_at` обновляется на любое действие в боте
  (aiogram-middleware `ActivityMiddleware` в `bot.py` + открытие Mini App в `/api/me`),
  `last_search_at` — на запрос в поисковике. Обе даты видны в карточке пользователя в CRM.
- **ai_sessions** — `telegram_id` (PK) → `chat_id` (id сессии RX Code AI).
- **link_tokens** — `token` (PK), `used_by`, `used_at` — «погашенные» одноразовые токены регистрации.
- **start_prompts** — `telegram_id` (PK), `chat_id`, `message_id`: id **последнего главного
  сообщения** бота. Нужен, чтобы удалить до-регистрационное главное сообщение после
  регистрации по ссылке (см. §5.1).
- **chats** — история чатов Mini App: `id` (PK), `telegram_id`, `rx_chat_id` (uniq),
  `title` (первый вопрос пользователя), `created_at`. Создаётся лениво при первом
  сохранённом сообщении.
- **chat_messages** — сообщения чатов: `id` (PK), `chat_id` (FK → chats, CASCADE),
  `role` (`user`/`ai`), `content` (markdown), `created_at`.

> Переписку дублируем у себя. При этом у RX Code AI **есть** свой эндпоинт
> `GET /api/chats/{chatId}/messages` (см. [`RXCODE_AI_API.md`](RXCODE_AI_API.md)) —
> при желании историю можно брать оттуда и не хранить у себя.

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
   Затем `_delete_prev_main` удаляет **старое (до-регистрационное) главное сообщение**
   по id из `start_prompts`, чтобы оно не осталось в чате дубликатом.
4. Mini App сам закрывается при уходе в фон (`app.js` `closeAfterSiteVisit`) — пользователь открывает заново.

### 5.2 Навигация в чате бота
`/start` без токена → главное сообщение: фото-баннер `webapp/logo_bot.png` («Мединтернет»
с роботом) + подпись (в слове «Мединтернет» ссылка на сайт) + inline-кнопки:

1. 🤝 **Поделиться с другом** (`nav:partners`)
2. 📖 **Как пользоваться** (`nav:instruction`)
3. 📄 **Политика конфиденциальности** — url на `medinternet.ru`
4. 🔍 **Открыть Mini App** — `web_app`

Нажатие раздела удаляет главное сообщение и шлёт под-сообщение с кнопкой
«← Вернуться» (`nav:home`). Id отправленного главного сообщения запоминается
в `start_prompts` (нужно для §5.1).

- **Поделиться с другом** — приглашение (без реферальной программы, убрана по ТЗ
  от июля 2026) + **5 кнопок**: 🔗 Скопировать ссылку (`CopyTextButton` — копирует
  `t.me/<bot>` в буфер), ✈️ Telegram (`t.me/share/url`), 🔷 MAX
  (`https://max.ru/:share?text=…`), 💬 WhatsApp (`wa.me/?text=`), ← Вернуться.
- **Как пользоваться** — советы по формулировке запросов к поисковику.

Описание в **пустом чате** («Что умеет этот бот?») ставится через `bot.set_my_description`
(в `bot.py`, применяется на каждом деплое). Картинку-логотип над описанием
(`webapp/logo_tg.png`, 640×360) Bot API ставить не умеет — задаётся **вручную в @BotFather**.

### 5.3 ИИ-поиск (RX Code AI)
- Сессионный API: `POST /api/chats {UserId, Channel: michat}` → `chatId`;
  затем `POST /api/chats/{id}/messages` или `.../messages/stream`.
- Авторизация — заголовком **`X-API-Key`** (НЕ `Bearer`!). Канал — **`michat`** (с `telegram` → 404).
- Стриминг: SSE. События: `Action` (статусы RAG), `Text` (куски Markdown) и
  **финальное** событие с `Suggestions` — 3 уточняющих вопроса, которые Mini App
  показывает чипсами под ответом.
- Mini App читает через `/api/ai/message/stream` (SSE-прокси в `server.py`).
  Прокси шлёт **heartbeat `: ping` каждые 2 с** в паузах и отдаёт заголовки
  `no-transform` / `X-Accel-Buffering: no`, чтобы прокси-край Railway не буферизовал поток.
- `ai_sessions` хранит связку `telegram_id → chatId`.
- **Тайминг:** статусы за ~2–5 с, затем пауза 10–28 с (генерация целиком), затем текст.
  Запросы к RX Code обрабатываются **последовательно** — подробности и замеры
  в [`RXCODE_AI_API.md`](RXCODE_AI_API.md).

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

После регистрации доступен только **медицинский поисковик** (вкладок Кабинет/Инфо и
нижней навигации нет — убраны по ТЗ от июля 2026; вместе с ними убран и выход
из аккаунта). Страницы внутри приложения:
- **Поиск** — чат с ИИ. Приветствие показывается с круглой **иконкой робота слева**
  (`robot.png`). Под каждым ответом кнопки: копировать / лайк / дизлайк
  (оценки пока только на клиенте, отправка в API не реализована — эндпоинты
  `like`/`dislike` у RX Code есть, см. [`RXCODE_AI_API.md`](RXCODE_AI_API.md)).
- **Чипсы-подсказки** — последний элемент внутри области сообщений (прокручиваются
  вместе с диалогом, новые сообщения вставляются перед ними). В пустом чате — 3
  статичные подсказки; после каждого ответа — **динамические уточняющие вопросы**
  из поля `Suggestions`. Клик подставляет текст в поле ввода.
- **История** — открывается кнопкой в шапке; список чатов запрашивается ТОЛЬКО по
  нажатию (`/api/history/chats`), не при старте. Название чата = первый вопрос.
  Выбор чата → просмотр переписки (`/api/history/messages`, read-only), «← Назад»
  возвращает к списку. Очистки истории нет.

Скроллбары: у области сообщений — видимый серый ползунок (в светлой теме тоже),
у поля ввода полоса **скрыта** (скролл колесиком/тачем работает).

Кэш-бастинг (Telegram Desktop держит старьё): `config.WEBAPP_VERSION` = timestamp старта
процесса; подставляется в URL кнопок и в ссылки на `style.css`/`app.js`; всё отдаётся с
`Cache-Control: no-store`.

Эндпоинты сервера: `/api/me`, `/api/ai/message`, `/api/ai/message/stream`, `/api/ai/reset`,
`/api/history/chats`, `/api/history/messages`, `/link`, `/api/register` (legacy).
Статика: `/`, `/app.js`, `/style.css`, `/logo.png`, `/robot.png`.
Валидация Telegram initData — HMAC.

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
DELETE FROM chats;              -- история чатов (chat_messages удалятся каскадом)
DELETE FROM ai_sessions;
DELETE FROM link_tokens;
DELETE FROM start_prompts;
DELETE FROM users;              -- после этого все регистрируются заново
```
Одного: `DELETE FROM ai_sessions WHERE telegram_id = <id>; DELETE FROM users WHERE telegram_id = <id>;`
Обязательна только чистка `users`; остальные — для порядка (у `chats` нет FK на `users`,
поэтому история сама не удалится). `DELETE` в Neon необратим.

---

## 10. Грабли (важно помнить)

- **RX Code AI:** авторизация `X-API-Key` (не Bearer), канал `michat` (не telegram),
  `NEURO_API_KEY` обязательно `.strip()` (перенос строки → «Forbidden control character in headers»).
- **asyncpg:** `sslmode`/`channel_binding` в DSN не поддерживаются — вырезаются в `_clean_dsn`.
- **`CREATE TABLE IF NOT EXISTS` НЕ мигрирует существующие таблицы.** Если схема
  изменилась, нужен отдельный `ALTER TABLE … ADD COLUMN IF NOT EXISTS`. На этом уже
  обожглись: таблица `chats` существовала без `rx_chat_id`, из-за чего сохранение
  истории падало, история была пустой, а пользователю после каждого ответа
  показывалась ошибка «Что-то пошло не так».
- **Сохранение истории** обёрнуто в `try/except` — сбой записи не должен ломать ответ.
- **Подпись фото** (главное сообщение бота) — лимит Telegram 1024 символа.
- **Пропорции фото:** слишком широкую картинку (например 4.7:1) Telegram показывает
  с серыми полосами-леттербоксом в тёмной теме. Баннер `logo_bot.png` сделан **2:1**
  на чисто белом фоне.
- **Картинка описания** пустого чата — только через @BotFather, не через Bot API.
- **Neon-роли** — только через SQL Editor (см. §4).
- **Telegram-форматирование** — размеров шрифта нет, только жирный/курсив/ссылки.
- **PowerShell + git commit:** в сообщениях коммита через here-string избегать двойных
  кавычек и токенов вида `/start` (ломают парсинг git / срабатывает песочница).

---

## 11. Что ещё не сделано

- **Лайк/дизлайк не уходят в API** — кнопки работают только визуально. У RX Code есть
  `POST /api/chats/{chatId}/messages/{messageId}/like|dislike`, но для этого нужно
  сохранять `messageId` ответа (сейчас не сохраняем).
- **История дублируется у нас**, хотя RX Code отдаёт её сам
  (`GET /api/chats/{chatId}/messages`).
- **Профиль пользователя** (`specialty`, `position`) не заполняется — ждёт интеграции
  с БД medinternet.
- **MAX-шеринг** (`https://max.ru/:share?text=…`) добавлен по документации MAX,
  но в бою не проверялся.

---

*Документ актуален на июль 2026. Полный справочник по API нейросети —
[`RXCODE_AI_API.md`](RXCODE_AI_API.md), официальная спецификация — [`swagger-mi.json`](swagger-mi.json).*
