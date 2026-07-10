"""Постановка задач рассылки в очередь arq."""
from arq import create_pool
from arq.connections import RedisSettings

from app.config import REDIS_URL


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(REDIS_URL)


async def get_redis():
    """Пул подключений к Redis для постановки задач (используется в API)."""
    return await create_pool(redis_settings())


async def enqueue_broadcast(redis, broadcast_id: str, telegram_ids: list[int], text: str) -> None:
    """Кладёт по задаче на каждого получателя пачкой."""
    for telegram_id in telegram_ids:
        await redis.enqueue_job("send_message_task", broadcast_id, telegram_id, text)
