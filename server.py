"""Веб-сервер mini app: отдаёт страницу регистрации и принимает данные."""
import hashlib
import hmac
import json
import logging
from datetime import date
from pathlib import Path
from urllib.parse import parse_qsl

from aiohttp import web
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

import ai_client
import db
import link_token
from config import BOT_TOKEN, WEBAPP_HOST, WEBAPP_PORT, WEBAPP_URL, WEBAPP_VERSION, webapp_url

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

    # Регистрация по MedID — число от 1 до 6 цифр (1..999999)
    med_raw = str(body.get("med_id") or "").strip()
    if not med_raw.isdigit() or not (1 <= len(med_raw) <= 6):
        return web.json_response(
            {"ok": False, "error": "MedinternetID — это число от 1 до 6 цифр"}, status=400
        )
    med_id = int(med_raw)
    if med_id < 1:
        return web.json_response({"ok": False, "error": "Неверный MedinternetID"}, status=400)

    was_registered = await db.user_exists(tg_id)
    await db.upsert_user(
        telegram_id=tg_id,
        med_id=med_id,
        username=tg_user.get("username"),
    )
    logger.info("Зарегистрирован пользователь %s (MedID %s)", tg_id, med_id)

    # Только при ПЕРВОЙ регистрации: удаляем стартовое приглашение и шлём поздравление
    if not was_registered:
        await _notify_registered(request.app.get("bot"), tg_id)

    return web.json_response({"ok": True})


_CONGRATS = (
    "🎉 Поздравляем с успешной регистрацией!\n"
    "Откройте наш Mini App для использования медицинского поисковика."
)


def _miniapp_kb() -> InlineKeyboardMarkup | None:
    url = webapp_url()
    if not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Mini App", web_app=WebAppInfo(url=url))]
        ]
    )


async def _notify_registered(bot, tg_id: int) -> None:
    """Удаляет стартовое сообщение и отправляет поздравление после регистрации."""
    if bot is None:
        return
    prompt = await db.get_start_prompt(tg_id)
    if prompt:
        try:
            await bot.delete_message(prompt["chat_id"], prompt["message_id"])
        except Exception as e:
            # Сообщение старше 48ч или уже удалено — не критично
            logger.info("Не удалось удалить стартовое сообщение %s: %s", tg_id, e)
        await db.delete_start_prompt(tg_id)
    try:
        await bot.send_message(tg_id, _CONGRATS, reply_markup=_miniapp_kb())
    except Exception as e:
        logger.warning("Не удалось отправить поздравление %s: %s", tg_id, e)


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
    """Статус пользователя: регистрация, доступность ИИ и данные профиля."""
    tg_user, _body, err = await _authenticated_user(request)
    if err is not None:
        return err

    row = await db.get_user(tg_user["id"])
    profile = None
    if row is not None:
        created = row["created_at"]
        profile = {
            "full_name": row["full_name"],
            "specialty": row["specialty"],
            "position": row["position"],
            "created_at": created.isoformat() if created else None,
            "tariff": "Обычный",
        }

    return web.json_response({
        "ok": True,
        "registered": row is not None,
        "ai_enabled": ai_client.is_configured(),
        "user": profile,
    })


async def handle_ai_message(request: web.Request) -> web.Response:
    """Отправляет вопрос пользователя в RX Code AI и возвращает ответ."""
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
    try:
        chat_id = await db.get_ai_chat_id(tg_id)
        if not chat_id:
            chat_id = await ai_client.create_session(tg_id)
            await db.set_ai_chat_id(tg_id, chat_id)
        try:
            answer = await ai_client.send_message(chat_id, message)
        except ai_client.SessionNotFound:
            # Сессия истекла — создаём новую и повторяем один раз
            chat_id = await ai_client.create_session(tg_id)
            await db.set_ai_chat_id(tg_id, chat_id)
            answer = await ai_client.send_message(chat_id, message)
    except ai_client.AIError as e:
        logger.warning("Ошибка RX Code AI: %s", e)
        return web.json_response(
            {"ok": False, "error": "Нейросеть недоступна, попробуйте позже"}, status=502
        )

    return web.json_response({
        "ok": True,
        "answer_html": answer["html"],
        "answer_md": answer["markdown"],
        "sources": answer["sources"],
    })


async def handle_ai_stream(request: web.Request) -> web.Response:
    """Потоковый ответ RX Code AI (SSE) — текст появляется постепенно."""
    tg_user, body, err = await _authenticated_user(request)
    if err is not None:
        return err
    if not ai_client.is_configured():
        return web.json_response({"ok": False, "error": "Нейросеть не настроена"}, status=503)
    message = (body.get("message") or "").strip()
    if not message:
        return web.json_response({"ok": False, "error": "Пустое сообщение"}, status=400)

    tg_id = tg_user["id"]
    resp = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(request)

    async def emit(obj):
        await resp.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))

    async def run(cid):
        async for kind, value in ai_client.stream_message(cid, message):
            await emit({"kind": kind, "value": value})

    try:
        chat_id = await db.get_ai_chat_id(tg_id)
        if not chat_id:
            chat_id = await ai_client.create_session(tg_id)
            await db.set_ai_chat_id(tg_id, chat_id)
        try:
            await run(chat_id)
        except ai_client.SessionNotFound:
            chat_id = await ai_client.create_session(tg_id)
            await db.set_ai_chat_id(tg_id, chat_id)
            await run(chat_id)
        await emit({"kind": "done"})
    except ai_client.AIError as e:
        logger.warning("Ошибка RX Code AI (stream): %s", e)
        await emit({"kind": "error", "value": "Нейросеть недоступна, попробуйте позже"})
    except Exception as e:
        logger.warning("Ошибка стрима %s: %s", tg_id, e)
        try:
            await emit({"kind": "error", "value": "Что-то пошло не так. Попробуйте позже."})
        except Exception:
            pass
    return resp


async def handle_ai_reset(request: web.Request) -> web.Response:
    """Сбрасывает текущую сессию, чтобы начать новый диалог."""
    tg_user, _body, err = await _authenticated_user(request)
    if err is not None:
        return err
    await db.clear_ai_session(tg_user["id"])
    return web.json_response({"ok": True})


def _file(name: str):
    async def handler(_request: web.Request) -> web.Response:
        resp = web.FileResponse(WEBAPP_DIR / name)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    return handler


# index.html отдаём с подстановкой версии в ссылки на style.css/app.js,
# чтобы Telegram после деплоя гарантированно скачал свежие файлы.
def _render_index() -> str:
    html = (WEBAPP_DIR / "index.html").read_text(encoding="utf-8")
    return (
        html.replace("/style.css", f"/style.css?v={WEBAPP_VERSION}")
            .replace("/app.js", f"/app.js?v={WEBAPP_VERSION}")
    )


async def handle_index(_request: web.Request) -> web.Response:
    return web.Response(
        text=_render_index(),
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


async def handle_link(request: web.Request) -> web.Response:
    """Прототип личного кабинета medinternet.ru: выдаёт свежую одноразовую
    ссылку на бота при каждом заходе (deep-link с подписанным токеном)."""
    username = request.app.get("bot_username") or ""
    token = link_token.make_link_token()
    bot_link = f"https://t.me/{username}?start={token}"
    html = (WEBAPP_DIR / "link.html").read_text(encoding="utf-8")
    return web.Response(
        text=html.replace("{{BOT_LINK}}", bot_link),
        content_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


def build_app(bot=None, bot_username: str = "") -> web.Application:
    app = web.Application()
    app["bot"] = bot  # нужен для уведомлений после регистрации
    app["bot_username"] = bot_username  # для deep-link на странице /link
    app.router.add_get("/", handle_index)
    app.router.add_get("/link", handle_link)
    app.router.add_get("/app.js", _file("app.js"))
    app.router.add_get("/style.css", _file("style.css"))
    app.router.add_get("/logo.png", _file("logo.png"))
    app.router.add_post("/api/register", handle_register)
    app.router.add_post("/api/me", handle_me)
    app.router.add_post("/api/ai/message", handle_ai_message)
    app.router.add_post("/api/ai/message/stream", handle_ai_stream)
    app.router.add_post("/api/ai/reset", handle_ai_reset)
    return app


async def start_webserver(bot=None, bot_username: str = "") -> web.AppRunner:
    """Поднимает веб-сервер на локальном порту и возвращает runner для остановки."""
    runner = web.AppRunner(build_app(bot, bot_username))
    await runner.setup()
    site = web.TCPSite(runner, WEBAPP_HOST, WEBAPP_PORT)
    await site.start()
    logger.info("Веб-сервер mini app слушает http://%s:%s", WEBAPP_HOST, WEBAPP_PORT)
    return runner
