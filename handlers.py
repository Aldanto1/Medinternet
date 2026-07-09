from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

from config import WEBAPP_URL

router = Router()


def _registration_keyboard() -> InlineKeyboardMarkup | None:
    """Кнопка открытия mini app с регистрацией (если задан WEBAPP_URL)."""
    if not WEBAPP_URL:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Регистрация", web_app=WebAppInfo(url=WEBAPP_URL))]
        ]
    )


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    kb = _registration_keyboard()
    text = (
        f"👋 Здравствуйте, <b>{message.from_user.full_name}</b>!\n\n"
        "Я — бот <b>Medinternet</b>.\n"
    )
    if kb:
        text += "Нажмите кнопку ниже, чтобы пройти регистрацию."
    else:
        text += "Используйте /help для просмотра доступных команд."
    await message.answer(text, reply_markup=kb)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(
        "📋 <b>Доступные команды:</b>\n\n"
        "/start — Начать работу с ботом\n"
        "/help — Показать это сообщение\n"
    )
