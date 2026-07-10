"""Постановка задач рассылки в очередь arq + хранение полезной нагрузки в Redis.

crm-api и crm-worker — разные процессы, поэтому текст и файл рассылки передаются
через Redis по ключам crm:bc:{id}:*, а в очередь кладётся только (broadcast_id, telegram_id).
"""
import json

from arq import create_pool
from arq.connections import RedisSettings

from app.config import REDIS_URL

# Сколько храним полезную нагрузку рассылки в Redis (сек)
PAYLOAD_TTL = 6 * 3600


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(REDIS_URL)


async def get_redis():
    """Пул подключений к Redis для постановки задач (используется в API)."""
    return await create_pool(redis_settings())


def _key(broadcast_id: str, suffix: str) -> str:
    return f"crm:bc:{broadcast_id}:{suffix}"


def _decode(value):
    return value.decode() if isinstance(value, (bytes, bytearray)) else value


async def store_broadcast_payload(redis, broadcast_id, caption, kind, filename, data) -> None:
    """Сохраняет текст (caption), тип (kind: text/photo/document) и файл рассылки."""
    meta = json.dumps({"caption": caption, "kind": kind, "filename": filename})
    await redis.set(_key(broadcast_id, "meta"), meta, ex=PAYLOAD_TTL)
    if data is not None:
        await redis.set(_key(broadcast_id, "data"), data, ex=PAYLOAD_TTL)


async def get_broadcast_meta(redis, broadcast_id):
    raw = await redis.get(_key(broadcast_id, "meta"))
    if raw is None:
        return None
    return json.loads(_decode(raw))


async def get_broadcast_data(redis, broadcast_id):
    """Байты файла рассылки (или None)."""
    return await redis.get(_key(broadcast_id, "data"))


async def get_broadcast_file_id(redis, broadcast_id):
    return _decode(await redis.get(_key(broadcast_id, "file_id")))


async def set_broadcast_file_id(redis, broadcast_id, file_id) -> None:
    await redis.set(_key(broadcast_id, "file_id"), file_id, ex=PAYLOAD_TTL)


async def enqueue_broadcast(redis, broadcast_id: str, telegram_ids: list[int]) -> None:
    """Кладёт по задаче на каждого получателя (нагрузка уже в Redis)."""
    for telegram_id in telegram_ids:
        await redis.enqueue_job("send_message_task", broadcast_id, telegram_id)
