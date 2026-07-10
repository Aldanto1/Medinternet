from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

import db
from config import WEBAPP_URL

router = Router()


def _miniapp_keyboard() -> InlineKeyboardMarkup | None:
    """Кнопка открытия mini app (если задан WEBAPP_URL)."""
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Mini App", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    kb = _miniapp_keyboard()
    greeting = f"👋 Здравствуйте, <b>{message.from_user.full_name}</b>!\n\n"

    # Уже зарегистрирован — просто приглашаем в Mini App
    if await db.user_exists(message.from_user.id):
        await message.answer(
            greeting + "Откройте наш Mini App для использования медицинского поисковика.",
            reply_markup=kb,
        )
        return

    # Не зарегистрирован — приглашаем пройти регистрацию и запоминаем это сообщение,
    # чтобы удалить его после успешной регистрации.
    if kb:
        text = greeting + (
            "Для пользования нашим <b>медицинским поисковиком</b> "
            "откройте «Мини Апп» и пройдите регистрацию."
        )
    else:
        text = greeting + "Используйте /help для просмотра доступных команд."

    sent = await message.answer(text, reply_markup=kb)
    await db.set_start_prompt(message.from_user.id, message.chat.id, sent.message_id)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(
        "📋 <b>Доступные команды:</b>\n\n"
        "/start — Начать работу с ботом\n"
        "/help — Показать это сообщение\n"
    )
