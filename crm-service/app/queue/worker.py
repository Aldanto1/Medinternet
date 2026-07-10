"""arq-воркер: отправляет по одному сообщению (текст или медиа) с троттлингом.

Запуск:  arq app.queue.worker.WorkerSettings
"""
import asyncio
import logging

from app import bot_client, db
from app.config import SEND_RATE_PER_SEC
from app.queue.tasks import (
    redis_settings,
    get_broadcast_meta,
    get_broadcast_data,
    get_broadcast_file_id,
    set_broadcast_file_id,
)

logger = logging.getLogger(__name__)

# Пауза между отправками, чтобы не превышать лимит Bot API (~30/сек)
_DELAY = 1.0 / SEND_RATE_PER_SEC


async def send_message_task(ctx, broadcast_id: str, telegram_id: int) -> str:
    """Отправляет одному получателю текст или медиа из Redis, логирует результат."""
    redis = ctx["redis"]
    meta = await get_broadcast_meta(redis, broadcast_id)

    if meta is None:
        # Нагрузка истекла в Redis — отправить нечего
        await db.update_log_status(broadcast_id, telegram_id, "failed")
        await asyncio.sleep(_DELAY)
        return "failed"

    caption = meta.get("caption") or ""
    kind = meta.get("kind") or "text"

    if kind == "text":
        status = await bot_client.send(telegram_id, caption)
    else:
        # Медиа: если file_id уже получен на первой отправке — переиспользуем его,
        # иначе загружаем файл и кэшируем полученный file_id для остальных.
        file_id = await get_broadcast_file_id(redis, broadcast_id)
        data = None if file_id else await get_broadcast_data(redis, broadcast_id)
        status, new_file_id = await bot_client.send_media(
            telegram_id, kind, caption,
            file_id=file_id, data=data, filename=meta.get("filename"),
        )
        if new_file_id:
            await set_broadcast_file_id(redis, broadcast_id, new_file_id)

    if status == "blocked":
        await db.mark_blocked(telegram_id)
    await db.update_log_status(broadcast_id, telegram_id, status)
    # Троттлинг: задачи идут последовательно (max_jobs=1), пауза держит темп
    await asyncio.sleep(_DELAY)
    return status


async def startup(ctx) -> None:
    await db.init()
    bot_client.init()
    logger.info("CRM worker запущен")


async def shutdown(ctx) -> None:
    await bot_client.close()
    await db.close()


class WorkerSettings:
    functions = [send_message_task]
    redis_settings = redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    # Последовательная обработка + пауза = гарантированный темп ≤ SEND_RATE_PER_SEC
    max_jobs = 1
