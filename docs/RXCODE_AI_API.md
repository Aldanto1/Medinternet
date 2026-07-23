# RX Code AI API — справочник

Медицинская нейросеть с RAG, на которой работает поисковик в Mini App.
Машиночитаемая спецификация: [`swagger-mi.json`](swagger-mi.json) (Swagger 2.0,
«RXCode AI API» v1.0, контакт: Vitaly Zhukov, v.zhukov@rxcode.ru).

Наш клиент — [`ai_client.py`](../ai_client.py).

---

## Подключение

| Параметр | Значение |
|---|---|
| Базовый адрес | `NEURO_API_URL`, прод: `https://qa.rxcode.pro` — **без** `/api` в конце |
| Авторизация | заголовок **`X-API-Key: <ключ>`** |
| Канал | `NEURO_CHANNEL`, у нас **`michat`** |

> ⚠️ **Расхождение со спецификацией.** В swagger указана схема `Bearer`
> (`apiKey` в заголовке `Authorization`), но фактически рабочий вариант —
> **`X-API-Key`** (проверено: все варианты `Authorization` давали 401).
>
> ⚠️ Канал **`michat`**. С `telegram` эндпоинт отвечает 404.
>
> ⚠️ Ключ обязательно `.strip()` — перенос строки при вставке в переменные
> окружения ломает заголовок («Forbidden control character detected in headers»).

---

## Эндпоинты

### Сессии чата

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/chats` | Создать сессию |
| `GET` | `/api/chats?userId=<id>` | Список сессий пользователя |
| `PATCH` | `/api/chats/{id}` | Задать название чата (`{"Title": "..."}`) |

**Создание сессии** (используем):
```http
POST /api/chats
{ "UserId": "<telegram_id>", "Channel": "michat" }   → 200 { "SessionId": "<uuid>" }
```
Оба поля обязательны.

### Сообщения

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/chats/{chatId}/messages` | Отправить вопрос, получить полный ответ |
| `POST` | `/api/chats/{chatId}/messages/stream` | То же, но потоком (используем) |
| `GET` | `/api/chats/{chatId}/messages` | **Получить переписку чата** |
| `GET` | `/api/chats/{chatId}/messages/count` | Число сообщений |
| `POST` | `/api/chats/{chatId}/messages/{messageId}/like` | Лайк ответа (используем) |
| `POST` | `/api/chats/{chatId}/messages/{messageId}/dislike` | Дизлайк ответа (используем) |

> **Оценки:** тело запроса не нужно. Фактически отвечает **`201 Created`** с пустым
> телом (в swagger заявлен `200` с `PostMessageResponse`) — поэтому в коде успехом
> считается любой `2xx`. `messageId` берём из поля `Id` финального события стрима.
> Эндпоинта «снять оценку» нет.

**Запрос:** `{ "Message": "<вопрос>", "RemovePersonalData": true|null }` (`Message` обязателен).

**Ответ (не-стрим)** — `PostMessageResponse`:
```json
{
  "SummaryHTML": "<h2>…</h2>",          // ответ в HTML
  "Summary": "## …",                     // ответ в Markdown  (используем)
  "Notes": "примечание",
  "Sources": [ { "Title": "…", "Url": "https://…" } ]
}
```

**Ответ (стрим)** — SSE, строки `data: {…}`:
- `{"Action": "Ищу данные в базе знаний"}` — статусы обработки (обычно 5 штук);
- `{"Text": "кусок ответа"}` — куски Markdown, ~100–140 штук;
- **финальное событие** — `{Id, Summary, Verified, RAG, Notes, Sources, Suggestions}`:
  - **`Id`** — идентификатор ответа, нужен для лайка/дизлайка;
  - **`Suggestions`** — список из 3 уточняющих вопросов (показываем их
    чипсами-подсказками под ответом).

### Прочее

| Метод | Путь | Назначение |
|---|---|---|
| `POST` | `/api/chats/completion` | Разовый ответ без сессии (`Message`, `Context[]`, `ChannelId`) |
| `POST` | `/api/chats/completion/stream` | То же потоком |
| `GET` | `/api/health` | Состояние сервиса (`Healthy`, `Database`, `OpenRouter`) |

### Коды ошибок
`400` Bad Request, `404` Not Found — тело `{ "Message": "…" }` (`ErrorDetails`).
У нас `404` на отправке сообщения трактуется как «сессия истекла» → создаём
новую и повторяем один раз (`ai_client.SessionNotFound`).

---

## Модели (кратко)

- **`ChatMessageItem`** — `Id`, `Direction` (0 — пользователь, 1 — ИИ), `Text`,
  `Question`, `Notes`, `Sources[]`, `Created`, `Rate`, `RagBased`.
- **`SessionItem`** — `SessionId`, `Channel`, `Created`.
- **`PostMessageResponseSource`** — `Title`, `Url`.
- **`HealthStatus`** — `Healthy`, `Database`, `OpenRouter` (каждый — `{Ok, Error}`).

---

## Замеренное поведение (наши тесты, июль 2026)

- **Тайминг ответа:** статусы RAG приходят за ~2–5 с, затем **пауза 10–28 с**
  (генерация ответа целиком), затем текст ~8 с кусками. То есть задержка до
  первого слова — это генерация на стороне RX Code, не наш баг.
- **Параллелизм:** запросы обрабатываются **последовательно**. Два одновременных
  запроса: второй не начинал генерацию, пока не завершился первый
  (первый текст на 18 с, у второго — на 39 с). Актуально для QA-инстанса.
- Из-за этого при одновременной отправке на сайт и в бот бот «думает» дольше —
  он стоит в очереди за запросом сайта.

---

## Что API умеет, но мы пока не используем

Может пригодиться:

1. **`GET /api/chats/{chatId}/messages`** — RX Code **отдаёт переписку чата**.
   Сейчас мы дублируем историю у себя в таблицах `chats`/`chat_messages`
   (см. [`DOCUMENTATION.md`](DOCUMENTATION.md)) — при желании историю можно тянуть из API.
2. **`PATCH /api/chats/{id}`** — название чата на стороне RX Code (у нас название
   берётся из первого вопроса пользователя).
3. **`GET /api/chats?userId=`** — список сессий пользователя.
4. **`GET /api/chats/{chatId}/messages/count`** — число сообщений в чате.

> ⚠️ **`GET /api/health` на QA-инстансе отвечает `404`** — эндпоинт из спецификации
> там не развёрнут, для мониторинга не годится (проверено).
