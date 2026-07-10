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
from aiogram.types import BufferedInputFile

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


async def _do_send_media(telegram_id, kind, caption, file_id, data, filename):
    """Реально отправляет фото/документ. Возвращает file_id загруженного файла."""
    media = file_id or BufferedInputFile(data, filename=filename or "file")
    if kind == "photo":
        msg = await _bot.send_photo(telegram_id, media, caption=caption)
        return msg.photo[-1].file_id if msg.photo else None
    msg = await _bot.send_document(telegram_id, media, caption=caption)
    return msg.document.file_id if msg.document else None


async def send_media(
    telegram_id: int,
    kind: str,
    caption: str | None,
    *,
    file_id: str | None = None,
    data: bytes | None = None,
    filename: str | None = None,
) -> tuple[str, str | None]:
    """Отправляет фото ('photo') или документ ('document').

    Если задан file_id — шлём по нему (без повторной загрузки в Telegram).
    Иначе загружаем data и возвращаем полученный file_id для переиспользования.
    Возвращает (status, file_id|None), status ∈ 'sent'/'blocked'/'failed'.
    """
    assert _bot is not None, "bot_client.init() ещё не вызван"
    caption = caption or None
    try:
        new_id = await _do_send_media(telegram_id, kind, caption, file_id, data, filename)
        return "sent", (None if file_id else new_id)
    except TelegramForbiddenError:
        return "blocked", None
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            new_id = await _do_send_media(telegram_id, kind, caption, file_id, data, filename)
            return "sent", (None if file_id else new_id)
        except Exception as e2:
            logger.warning("Повторная отправка media %s не удалась: %s", telegram_id, e2)
            return "failed", None
    except TelegramBadRequest as e:
        logger.warning("BadRequest media для %s: %s", telegram_id, e)
        return "failed", None
    except Exception as e:
        logger.warning("Ошибка отправки media %s: %s", telegram_id, e)
        return "failed", None
