"""Рассылка: постановка в очередь (с текстом и/или файлом) и статус."""
import json
import uuid

from aiohttp import web

from app import db
from app.queue.tasks import enqueue_broadcast, store_broadcast_payload

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


async def create_broadcast(request: web.Request) -> web.Response:
    """POST /api/broadcast (multipart/form-data): filters + text + необязательный file."""
    post = await request.post()

    try:
        filters = json.loads(post.get("filters") or "{}")
    except (json.JSONDecodeError, TypeError):
        filters = {}
    text = (post.get("text") or "").strip()

    # Необязательный файл
    kind, filename, data = "text", None, None
    file_field = post.get("file")
    if file_field is not None and hasattr(file_field, "file"):
        data = file_field.file.read()
        if data:
            filename = file_field.filename or "file"
            ctype = (file_field.content_type or "").lower()
            kind = "photo" if ctype in _IMAGE_TYPES else "document"
        else:
            data = None

    if not text and data is None:
        return web.json_response(
            {"ok": False, "error": "Добавьте текст или прикрепите файл"}, status=400
        )

    telegram_ids = await db.get_telegram_ids(filters)
    if not telegram_ids:
        return web.json_response(
            {"ok": False, "error": "Под фильтр не попал ни один получатель"}, status=400
        )

    broadcast_id = uuid.uuid4().hex
    redis = request.app["redis"]
    await store_broadcast_payload(redis, broadcast_id, text, kind, filename, data)
    await db.create_pending_logs(broadcast_id, telegram_ids)
    await enqueue_broadcast(redis, broadcast_id, telegram_ids)

    return web.json_response(
        {"ok": True, "broadcast_id": broadcast_id, "queued": len(telegram_ids)}
    )


async def broadcast_status(request: web.Request) -> web.Response:
    """GET /api/broadcast/{id}/status — счётчики sent/failed/blocked/pending."""
    broadcast_id = request.match_info["id"]
    counts = await db.get_broadcast_status(broadcast_id)
    return web.json_response({"ok": True, "broadcast_id": broadcast_id, **counts})
