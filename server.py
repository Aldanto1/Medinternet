"""Веб-сервер mini app: отдаёт страницу регистрации и принимает данные."""
import hashlib
import hmac
import json
import logging
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web

import ai_client
import db
from config import BOT_TOKEN, WEBAPP_HOST, WEBAPP_PORT

logger = logging.getLogger(__name__)

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"


def validate_init_data(init_data: str) -> dict | None:
    """Проверяет подпись Telegram.WebApp.initData.

    Возвращает разобранные поля при валидной подписи, иначе None.
    Алгоритм: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed, received_hash):
        return None
    return parsed


async def handle_register(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return web.json_response({"ok": False, "error": "Неверный формат запроса"}, status=400)

    parsed = validate_init_data(body.get("initData", ""))
    if parsed is None:
        return web.json_response(
            {"ok": False, "error": "Проверка Telegram не пройдена"}, status=403
        )

    try:
        tg_user = json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError:
        tg_user = {}
    tg_id = tg_user.get("id")
    if not tg_id:
        return web.json_response(
            {"ok": False, "error": "Нет данных пользователя Telegram"}, status=400
        )

    full_name = (body.get("full_name") or "").strip()
    phone = (body.get("phone") or "").strip() or None
    email = (body.get("email") or "").strip() or None
    birth_raw = (body.get("birth_date") or "").strip()

    if not full_name:
        return web.json_response({"ok": False, "error": "Укажите ФИО"}, status=400)

    birth_date = None
    if birth_raw:
        try:
            birth_date = date.fromisoformat(birth_raw)
        except ValueError:
            return web.json_response(
                {"ok": False, "error": "Неверная дата рождения"}, status=400
            )

    await db.upsert_user(
        telegram_id=tg_id,
        username=tg_user.get("username"),
        full_name=full_name,
        phone=phone,
        email=email,
        birth_date=birth_date,
    )
    logger.info("Зарегистрирован пользователь %s (%s)", tg_id, full_name)
    return web.json_response({"ok": True})


async def _authenticated_user(request: web.Request):
    """Разбирает и проверяет initData из тела запроса.

    Возвращает (tg_user_dict, None) при успехе или (None, web.Response) с ошибкой.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None, None, web.json_response(
            {"ok": False, "error": "Неверный формат запроса"}, status=400
        )
    parsed = validate_init_data(body.get("initData", ""))
    if parsed is None:
        return None, None, web.json_response(
            {"ok": False, "error": "Проверка Telegram не пройдена"}, status=403
        )
    try:
        tg_user = json.loads(parsed.get("user", "{}"))
    except json.JSONDecodeError:
        tg_user = {}
    if not tg_user.get("id"):
        return None, None, web.json_response(
            {"ok": False, "error": "Нет данных пользователя Telegram"}, status=400
        )
    return tg_user, body, None


async def handle_me(request: web.Request) -> web.Response:
    """Статус пользователя: зарегистрирован ли и доступен ли ИИ-чат."""
    tg_user, _body, err = await _authenticated_user(request)
    if err is not None:
        return err
    registered = await db.user_exists(tg_user["id"])
    return web.json_response(
        {"ok": True, "registered": registered, "ai_enabled": ai_client.is_configured()}
    )


# Сколько последних сообщений диалога держим в контексте (ограничивает расход токенов)
MAX_HISTORY = 20


async def handle_ai_message(request: web.Request) -> web.Response:
    """Отправляет вопрос пользователя в нейросеть с учётом истории диалога."""
    tg_user, body, err = await _authenticated_user(request)
    if err is not None:
        return err

    if not ai_client.is_configured():
        return web.json_response(
            {"ok": False, "error": "Нейросеть не настроена"}, status=503
        )

    message = (body.get("message") or "").strip()
    if not message:
        return web.json_response({"ok": False, "error": "Пустое сообщение"}, status=400)

    tg_id = tg_user["id"]
    history = await db.get_conversation(tg_id)

    messages = (
        [{"role": "system", "content": ai_client.SYSTEM_PROMPT}]
        + history
        + [{"role": "user", "content": message}]
    )

    try:
        reply = await ai_client.chat_completion(messages)
    except ai_client.AIError as e:
        logger.warning("Ошибка нейросети: %s", e)
        return web.json_response(
            {"ok": False, "error": "Нейросеть недоступна, попробуйте позже"}, status=502
        )

    # Дописываем обмен в историю и обрезаем до последних MAX_HISTORY сообщений
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    await db.save_conversation(tg_id, history[-MAX_HISTORY:])

    return web.json_response(
        {"ok": True, "answer_html": None, "answer_md": reply, "sources": []}
    )


async def handle_ai_reset(request: web.Request) -> web.Response:
    """Сбрасывает историю диалога, чтобы начать новый разговор."""
    tg_user, _body, err = await _authenticated_user(request)
    if err is not None:
        return err
    await db.clear_conversation(tg_user["id"])
    return web.json_response({"ok": True})


def _file(name: str):
    async def handler(_request: web.Request) -> web.Response:
        return web.FileResponse(WEBAPP_DIR / name)

    return handler


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", _file("index.html"))
    app.router.add_get("/app.js", _file("app.js"))
    app.router.add_get("/style.css", _file("style.css"))
    app.router.add_post("/api/register", handle_register)
    app.router.add_post("/api/me", handle_me)
    app.router.add_post("/api/ai/message", handle_ai_message)
    app.router.add_post("/api/ai/reset", handle_ai_reset)
    return app


async def start_webserver() -> web.AppRunner:
    """Поднимает веб-сервер на локальном порту и возвращает runner для остановки."""
    runner = web.AppRunner(build_app())
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logger.info("Веб-сервер mini app слушает http://%s:%s", WEBAPP_HOST, WEBAPP_PORT)
    return runner
