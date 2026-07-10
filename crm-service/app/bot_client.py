"""Обёртка над aiogram Bot для отправки сообщений токеном основного бота.

Возвращает статус доставки: "sent" / "blocked" / "failed".
Отдельного Telegram-бота не создаём — используем токен основного (MAIN_BOT_TOKEN).
"""
import asyncio
import logging

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramBadRequest,
)

from app.config import MAIN_BOT_TOKEN

logger = logging.getLogger(__name__)

_bot: Bot | None = None


def init() -> None:
    global _bot
    _bot = Bot(
        token=MAIN_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def close() -> None:
    if _bot is not None:
        await _bot.session.close()


async def send(telegram_id: int, text: str) -> str:
    """Отправляет сообщение. Возвращает 'sent' / 'blocked' / 'failed'."""
    assert _bot is not None, "bot_client.init() ещё не вызван"
    try:
        await _bot.send_message(telegram_id, text)
        return "sent"
    except TelegramForbiddenError:
        # Пользователь заблокировал бота (403 bot was blocked by the user)
        return "blocked"
    except TelegramRetryAfter as e:
        # Флуд-контроль: ждём и пробуем ещё один раз
        await asyncio.sleep(e.retry_after)
        try:
            await _bot.send_message(telegram_id, text)
            return "sent"
        except TelegramForbiddenError:
            return "blocked"
        except Exception as e2:
            logger.warning("Повторная отправка %s не удалась: %s", telegram_id, e2)
            return "failed"
    except TelegramBadRequest as e:
        # Неверный chat_id, пользователь не начинал диалог и т.п.
        logger.warning("BadRequest для %s: %s", telegram_id, e)
        return "failed"
    except Exception as e:
        logger.warning("Ошибка отправки %s: %s", telegram_id, e)
        return "failed"
