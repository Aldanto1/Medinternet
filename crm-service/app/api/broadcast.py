"""Рассылка: постановка в очередь и статус."""
import uuid

from aiohttp import web

from app import db
from app.queue.tasks import enqueue_broadcast


async def create_broadcast(request: web.Request) -> web.Response:
    """POST /api/broadcast — фильтры + текст → задачи в очередь arq."""
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Неверный запрос"}, status=400)

    filters = data.get("filters") or {}
    text = (data.get("text") or "").strip()
    if not text:
        return web.json_response({"ok": False, "error": "Пустой текст рассылки"}, status=400)

    telegram_ids = await db.get_telegram_ids(filters)
    if not telegram_ids:
        return web.json_response(
            {"ok": False, "error": "Под фильтр не попал ни один получатель"}, status=400
        )

    broadcast_id = uuid.uuid4().hex
    await db.create_pending_logs(broadcast_id, telegram_ids)
    await enqueue_broadcast(request.app["redis"], broadcast_id, telegram_ids, text)

    return web.json_response(
        {"ok": True, "broadcast_id": broadcast_id, "queued": len(telegram_ids)}
    )


async def broadcast_status(request: web.Request) -> web.Response:
    """GET /api/broadcast/{id}/status — счётчики sent/failed/blocked/pending."""
    broadcast_id = request.match_info["id"]
    counts = await db.get_broadcast_status(broadcast_id)
    return web.json_response({"ok": True, "broadcast_id": broadcast_id, **counts})
