# CRM-сервис рассылок (Medinternet)

Отдельный сервис для сегментированных рассылок пользователям бота. Специалист
входит по логину/паролю в веб-панель, выбирает сегмент (фильтры), пишет сообщение
и отправляет. Рассылка идёт **токеном основного бота** через очередь с троттлингом.

## Архитектура

```
Веб-панель ──HTTP──> crm-api (aiohttp) ──ставит задачи──> Redis (arq) ──> crm-worker
                          │                                                    │
                          └── читает public.users (read-only)                 └── шлёт сообщения
                              пишет в схему crm                                    токеном бота,
                                                                                   пишет статусы в crm
```

- **crm-api** — REST API + веб-панель.
- **crm-worker** — arq-воркер, отправляет по одному сообщению с паузой (≤25/сек).
- **Redis** — очередь arq.
- **Neon** — та же БД, что у бота. `users` читается по **read-only роли**; служебные
  данные пишутся в отдельную схему `crm` (таблицы основного бота на запись не трогаем).

## Подготовка (один раз)

### 1. Схема и роль в Neon
Выполни в SQL-редакторе Neon (под ролью-владельцем БД):

```sql
-- migrations/001_crm_schema.sql — создаёт схему crm и таблицы
-- migrations/002_crm_role.sql   — создаёт роль crm_reader (задай пароль!)
```

Порядок: сначала `001`, потом `002`. В `002` замени `ЗАМЕНИ_НА_ПАРОЛЬ` на свой пароль.
Затем собери строку подключения для `CRM_DB_URL` (роль `crm_reader`, тот же host, что
у бота, с `?sslmode=require`).

### 2. `.env`
Скопируй `.env.example` в `.env` и заполни:

| Переменная         | Значение                                                        |
|--------------------|-----------------------------------------------------------------|
| `CRM_DB_URL`       | Строка Neon под ролью `crm_reader`                             |
| `MAIN_BOT_TOKEN`   | Токен основного бота (тот же, что у бота)                        |
| `JWT_SECRET`       | Длинная случайная строка                                        |
| `CRM_LOGIN_EMAIL`  | Email специалиста для входа                                     |
| `CRM_LOGIN_PASSWORD`| Пароль специалиста                                             |
| `REDIS_URL`        | Адрес Redis (локально `redis://redis:6379` через compose)       |

## Локальный запуск

```bash
docker-compose up --build
```

Поднимутся Redis + crm-api + crm-worker. Панель: **http://localhost:8090**

> ⚠️ Реальная отправка в Telegram из РФ напрямую заблокирована. Локально воркер
> отправку не выполнит (сообщения залогируются как `failed`). Полноценная отправка
> работает на Railway (зарубежный IP). Логику API/очереди локально проверять можно.

## Эндпоинты (для curl/Postman)

```bash
# 1. Логин → получить токен
curl -X POST http://localhost:8090/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@medinternet.ru","password":"..."}'

# 2. Превью сегмента (только количество)
curl -X POST http://localhost:8090/api/segments/preview \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"filters":{"created_from":"2026-01-01","has_email":true}}'

# 3. Запустить рассылку (multipart: фильтры + текст + необязательный файл)
curl -X POST http://localhost:8090/api/broadcast \
  -H "Authorization: Bearer <TOKEN>" \
  -F 'filters={"has_email":true}' \
  -F 'text=Здравствуйте! ...' \
  -F 'file=@/path/to/photo.jpg'   # необязательно; фото → как фото, иначе документ

# 4. Статус рассылки
curl http://localhost:8090/api/broadcast/<BROADCAST_ID>/status \
  -H "Authorization: Bearer <TOKEN>"
```

## Фильтры сегмента

| Фильтр                       | Поле в `users`     | Статус     |
|------------------------------|--------------------|------------|
| `created_from` / `created_to`| `created_at`       | работает   |
| `has_email` (true/false)     | `email`            | работает   |
| `has_phone` (true/false)     | `phone`            | работает   |
| `last_active_at_*`           | —                  | заглушка   |
| `tag` / `status`             | —                  | заглушка   |

Заблокировавшие бота (схема `crm.blocked_users`) автоматически исключаются из выборки.

### Как добавить фильтр по активности
В таблице `users` нет `last_active_at`. Чтобы включить фильтр:
1. `ALTER TABLE users ADD COLUMN last_active_at timestamptz;`
2. В основном боте обновлять это поле при активности пользователя.
3. В `app/db.py` → `build_where` добавить условие по `last_active_at` (параметризованно).

## Деплой на Railway

Два отдельных сервиса в том же проекте, оба из подпапки `crm-service/`:

| Сервис       | Start Command                              |
|--------------|--------------------------------------------|
| `crm-api`    | `python -m app.main`                       |
| `crm-worker` | `arq app.queue.worker.WorkerSettings`      |

1. Добавь в проект **Redis** (Railway → New → Database → Redis) — он даст `REDIS_URL`.
2. Создай два сервиса из репозитория, Root Directory = `crm-service`.
3. В каждом задай переменные из таблицы `.env` выше (`REDIS_URL` — из Redis-сервиса).
4. У `crm-api` сгенерируй домен (Settings → Networking) — это адрес панели.

## Тесты

```bash
python -m pytest
```

Проверяют построение SQL-фильтра и логику постановки/обработки задач (с моком бота).

## Безопасность

- Секреты только в `.env` (в `.gitignore`), не в коде.
- `/api/segments/preview` и `/api/broadcast` — под JWT.
- Роль `crm_reader` физически не имеет прав на запись в `users`.
- `preview` возвращает только количество — защита от случайной рассылки на всю базу.
