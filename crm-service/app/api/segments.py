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


async def suggest_med_ids(request: web.Request) -> web.Response:
    """GET /api/segments/med-ids — все MedID; с ?q=цифры — подсказки по вводу."""
    query = (request.query.get("q") or "").strip()
    if query:
        med_ids = await db.search_med_ids(query, limit=15)
    else:
        med_ids = await db.list_med_ids(limit=1000)
    return web.json_response({"ok": True, "med_ids": med_ids})
