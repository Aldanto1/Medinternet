"""POST /api/segments/preview — количество получателей по фильтру (без списка)."""
from aiohttp import web

from app import db


async def preview(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Неверный запрос"}, status=400)

    filters = data.get("filters") or {}
    count = await db.count_users(filters)
    return web.json_response({"ok": True, "count": count})


async def suggest_emails(request: web.Request) -> web.Response:
    """GET /api/segments/emails?q=... — подсказки email для автодополнения."""
    query = (request.query.get("q") or "").strip()
    if not query:
        return web.json_response({"ok": True, "emails": []})
    emails = await db.search_emails(query, limit=10)
    return web.json_response({"ok": True, "emails": emails})
