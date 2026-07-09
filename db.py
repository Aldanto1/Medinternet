"""Работа с базой данных Neon (PostgreSQL) через asyncpg."""
import json
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
        # История диалога с нейросетью (OpenRouter не хранит контекст на своей стороне).
        # messages — JSON-массив [{"role","content"}, ...] в виде текста.
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_conversations (
                telegram_id BIGINT PRIMARY KEY,
                messages    TEXT NOT NULL DEFAULT '[]',
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


async def user_exists(telegram_id: int) -> bool:
    """True, если пользователь уже прошёл регистрацию."""
    assert _pool is not None, "db.init() ещё не вызван"
    async with _pool.acquire() as conn:
        row = await conn.fetchval(
            "SELECT 1 FROM users WHERE telegram_id = $1", telegram_id
        )
        return row is not None


async def get_conversation(telegram_id: int) -> list:
    """Возвращает историю диалога пользователя (список messages) или []."""
    assert _pool is not None, "db.init() ещё не вызван"
    async with _pool.acquire() as conn:
        raw = await conn.fetchval(
            "SELECT messages FROM ai_conversations WHERE telegram_id = $1", telegram_id
        )
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


async def save_conversation(telegram_id: int, messages: list) -> None:
    """Сохраняет историю диалога пользователя."""
    assert _pool is not None, "db.init() ещё не вызван"
    payload = json.dumps(messages, ensure_ascii=False)
    async with _pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO ai_conversations (telegram_id, messages)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id) DO UPDATE SET
                messages   = EXCLUDED.messages,
                updated_at = now()
            """,
            telegram_id,
            payload,
        )


async def clear_conversation(telegram_id: int) -> None:
    """Очищает историю диалога, чтобы начать новый разговор."""
    assert _pool is not None, "db.init() ещё не вызван"
    async with _pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM ai_conversations WHERE telegram_id = $1", telegram_id
        )
