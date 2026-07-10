"""arq-воркер: отправляет по одному сообщению с троттлингом.

Запуск:  arq app.queue.worker.WorkerSettings
"""
import asyncio
import logging

from app import bot_client, db
from app.config import SEND_RATE_PER_SEC
from app.queue.tasks import redis_settings

logger = logging.getLogger(__name__)

# Пауза между отправками, чтобы не превышать лимит Bot API (~30/сек)
_DELAY = 1.0 / SEND_RATE_PER_SEC


async def send_message_task(ctx, broadcast_id: str, telegram_id: int, text: str) -> str:
    """Отправляет одно сообщение и логирует результат."""
    status = await bot_client.send(telegram_id, text)
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
