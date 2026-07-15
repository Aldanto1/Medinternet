from aiogram import Router
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

import db
import link_token
from config import WEBAPP_URL, webapp_url

router = Router()


def _miniapp_keyboard() -> InlineKeyboardMarkup | None:
    """Кнопка открытия mini app (если задан WEBAPP_URL)."""
    url = webapp_url()
    if not url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Mini App", web_app=WebAppInfo(url=url))]
        ]
    )


_ABOUT = (
    "Я — бот <b>Мединтернет</b> с медицинским поисковиком: это ИИ, созданный "
    "специально для врачей и работников аптек (совместно с Сеченовским Университетом).\n\n"
    "<b>Что умеет медицинский поисковик:</b>\n"
    "• отвечает на вопросы о препаратах, болезнях и схемах лечения;\n"
    "• ищет по классификациям МКБ-10 и АТХ;\n"
    "• анализирует научные исследования и клинические случаи;\n"
    "• даёт структурированные ответы со ссылками на проверенные источники."
)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    """Обработчик /start. С deep-link токеном — регистрация, иначе — приветствие."""
    token = (command.args or "").strip()
    if token:
        await _register_via_link(message, token)
        return

    kb = _miniapp_keyboard()
    greeting = f"👋 Здравствуйте, <b>{message.from_user.full_name}</b>!\n\n"

    if await db.user_exists(message.from_user.id):
        await message.answer(
            greeting + _ABOUT + "\n\nОткройте <b>Mini App</b>, чтобы начать работу.",
            reply_markup=kb,
        )
        return

    await message.answer(
        greeting + _ABOUT + (
            "\n\nЧтобы получить доступ, зайдите в свой личный кабинет на "
            "<b>medinternet.ru</b> и перейдите по ссылке для регистрации в Telegram."
        ),
        reply_markup=kb,
    )


async def _register_via_link(message: Message, token: str) -> None:
    """Регистрация по одноразовой подписанной ссылке из личного кабинета."""
    user_id = message.from_user.id
    kb = _miniapp_keyboard()

    if await db.user_exists(user_id):
        await message.answer(
            "Вы уже зарегистрированы ✅\nОткройте <b>Mini App</b>, чтобы начать.",
            reply_markup=kb,
        )
        return

    if not link_token.verify_link_token(token) or not await db.claim_link_token(token, user_id):
        await message.answer(
            "⚠️ Ссылка недействительна или уже использована.\n"
            "Получите новую в личном кабинете на <b>medinternet.ru</b>."
        )
        return

    await db.register_user(user_id, message.from_user.username)
    await message.answer(
        "🎉 <b>Регистрация успешна!</b>\n"
        "Все функции доступны. Откройте <b>Mini App</b>, чтобы начать работу.",
        reply_markup=kb,
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(
        "📋 <b>Доступные команды:</b>\n\n"
        "/start — Начать работу с ботом\n"
        "/help — Показать это сообщение\n"
    )
