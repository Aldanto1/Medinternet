"""Работа с базой данных Neon (PostgreSQL) через asyncpg."""
import re

import asyncpg

from config import DATABASE_URL

_pool: asyncpg.Pool | None = None


def _clean_dsn(url: str) -> str:
    """asyncpg не понимает libpq-параметры sslmode/channel_binding в строке
    подключения — убираем их, а SSL включаем отдельным аргументом."""
    return re.sub(r"[?&](sslmode|channel_binding)=[^&]*", "", url)


async def init() -> None:
    """Создаёт пул соединений и таблицу users, если её ещё нет."""
    global _pool
    _pool = await asyncpg.create_pool(
        _clean_dsn(DATABASE_URL),
        ssl="require",
        min_size=1,
        max_size=5,
    )
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id BIGINT PRIMARY KEY,
                username    TEXT,
                full_name   TEXT NOT NULL,
                phone       TEXT,
                email       TEXT,
                birth_date  DATE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )


async def close() -> None:
    """Закрывает пул соединений."""
    if _pool is not None:
        await _pool.close()


async def upsert_user(
    telegram_id: int,
    username: str | None,
    full_name: str,
    phone: str | None,
    email: str | None,
    birth_date=None,
) -> None:
    """Создаёт или обновляет запись пользователя по telegram_id."""
    assert _pool is not None, "db.init() ещё не вызван"
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, phone, email, birth_date)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username   = EXCLUDED.username,
                full_name  = EXCLUDED.full_name,
                phone      = EXCLUDED.phone,
                email      = EXCLUDED.email,
                birth_date = EXCLUDED.birth_date,
                updated_at = now()
            """,
            telegram_id,
            username,
            full_name,
            phone,
            email,
            birth_date,
        )


async def get_user(telegram_id: int):
    """Возвращает запись пользователя или None."""
    assert _pool is not None, "db.init() ещё не вызван"
    async with _pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM users WHERE telegram_id = $1", telegram_id
        )
