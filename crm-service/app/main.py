"""CRM API + веб-панель (aiohttp)."""
import logging
from pathlib import Path

from aiohttp import web

from app import db
from app.config import API_HOST, API_PORT, validate
from app.api import auth, segments, broadcast
from app.api.middleware import jwt_middleware
from app.queue.tasks import get_redis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent / "web"


async def on_startup(app: web.Application) -> None:
    await db.init()
    app["redis"] = await get_redis()
    logger.info("CRM API запущен на %s:%s", API_HOST, API_PORT)


async def on_cleanup(app: web.Application) -> None:
    redis = app.get("redis")
    if redis is not None:
        await redis.close()
    await db.close()


def _file(name: str):
    async def handler(_request: web.Request) -> web.Response:
        resp = web.FileResponse(WEB_DIR / name)
        # Всегда брать свежую версию панели после деплоя (не кешировать в браузере)
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    return handler


def build_app() -> web.Application:
    # client_max_size — потолок размера загружаемого файла рассылки (20 МБ)
    app = web.Application(middlewares=[jwt_middleware], client_max_size=20 * 1024 * 1024)

    # API
    app.router.add_post("/api/auth/login", auth.login)
    app.router.add_post("/api/segments/preview", segments.preview)
    app.router.add_get("/api/segments/emails", segments.suggest_emails)
    app.router.add_post("/api/broadcast", broadcast.create_broadcast)
    app.router.add_get("/api/broadcast/{id}/status", broadcast.broadcast_status)

    # Веб-панель
    app.router.add_get("/", _file("index.html"))
    app.router.add_get("/panel.js", _file("panel.js"))
    app.router.add_get("/panel.css", _file("panel.css"))

    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


def main() -> None:
    validate(require_all=True)
    web.run_app(build_app(), host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    main()
