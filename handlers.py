from pathlib import Path
from urllib.parse import quote

from aiogram import Router, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    FSInputFile,
    LinkPreviewOptions,
)

import db
import link_token
from config import WEBAPP_URL, webapp_url

router = Router()

SITE_URL = "https://medinternet.ru/"
LOGO_PATH = Path(__file__).resolve().parent / "webapp" / "logo_bot.png"
# Кэш file_id логотипа: первую отправку грузим файлом, дальше — по id (без повторной загрузки).
_logo_file_id: str | None = None


_ABOUT = (
    f'Я — бот <a href="{SITE_URL}"><b>Мединтернет</b></a>, медицинский ИИ-поисковик '
    "для врачей и фармацевтов (совместно с Сеченовским Университетом).\n\n"
    "Отвечаю на вопросы о препаратах, болезнях и схемах лечения, "
    "ищу по МКБ-10 и АТХ, даю ответы со ссылками на источники."
)

_INSTRUCTION_TEXT = (
    "📖 <b>Как задавать вопросы поисковику</b>\n\n"
    "Чтобы получать максимально точные ответы, следуйте рекомендациям:\n\n"
    "<b>1. Будьте конкретны</b>\n"
    "Указывайте возраст, сопутствующие болезни, принимаемые лекарства.\n"
    "✗ «Что делать при высоком давлении?»\n"
    "✓ «Препараты первой линии при гипертоническом кризе у пациента 60 лет с СД 2 типа?»\n\n"
    "<b>2. Используйте терминологию</b>\n"
    "Поисковик понимает аббревиатуры и стандарты (ESC, NIH, ICD-11).\n\n"
    "<b>3. Просите источники</b>\n"
    "Уточняйте: «Какие рекомендации WHO?», «Есть ли мета-анализы?».\n\n"
    "<b>4. Разбивайте сложные запросы</b>\n"
    "Пошаговые вопросы дают более структурированные ответы.\n\n"
    "<b>5. Уточняйте контекст</b>\n"
    "«У пациента ХБП 3 стадии, как это влияет?», «Какие исключения при беременности?».\n\n"
    "<b>6. Проверяйте противоречия</b>\n"
    "Если ответ вызывает сомнения: «Это противоречит данным ABCD-2023. Объясните расхождение?»"
)


def _partners_text(bot_username: str) -> str:
    """Текст раздела «Поделиться с другом» (в слове «Мединтернетом» — ссылка на бота)."""
    bot_link = f"https://t.me/{bot_username}"
    return (
        "🤝 <b>Поделиться с другом</b>\n\n"
        f'Поделитесь <a href="{bot_link}">Мединтернетом</a> со своими знакомыми '
        "и коллегами — медицинский ИИ-поисковик поможет им быстро находить "
        "ответы на профессиональные вопросы.\n\n"
        "Отправьте приглашение удобным способом:"
    )


def _main_keyboard() -> InlineKeyboardMarkup:
    """Навигация под главным сообщением + большая кнопка открытия Mini App."""
    rows = [
        [InlineKeyboardButton(text="🤝 Поделиться с другом", callback_data="nav:partners")],
        [InlineKeyboardButton(text="📖 Как пользоваться", callback_data="nav:instruction")],
    ]
    url = webapp_url()
    if url:
        rows.append(
            [InlineKeyboardButton(text="🔍 Открыть Mini App", web_app=WebAppInfo(url=url))]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _registered_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура сообщения об успешной регистрации: Mini App + Главная."""
    rows = []
    url = webapp_url()
    if url:
        rows.append(
            [InlineKeyboardButton(text="🔍 Открыть Mini App", web_app=WebAppInfo(url=url))]
        )
    rows.append([InlineKeyboardButton(text="🏠 Главная", callback_data="nav:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата к главному сообщению."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="← Вернуться", callback_data="nav:home")]
        ]
    )


def _partners_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Кнопки шеринга приглашения + возврат."""
    bot_link = f"https://t.me/{bot_username}"
    invite = "Присоединяйтесь к Мединтернету — медицинскому ИИ-поисковику для врачей и фармацевтов:"
    tg_share = f"https://t.me/share/url?url={quote(bot_link)}&text={quote(invite)}"
    wa_share = f"https://wa.me/?text={quote(invite + ' ' + bot_link)}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📨 Отправить в Telegram", url=tg_share)],
            [InlineKeyboardButton(text="💬 Отправить в WhatsApp", url=wa_share)],
            [InlineKeyboardButton(text="← Вернуться", callback_data="nav:home")],
        ]
    )


async def _main_caption(full_name: str, user_id: int) -> str:
    """Подпись главного сообщения (зависит от того, зарегистрирован ли пользователь)."""
    greeting = f"👋 Здравствуйте, <b>{full_name}</b>!\n\n"
    if await db.user_exists(user_id):
        tail = (
            "\n\n✅ Вы зарегистрированы. Медицинский поисковик доступен через "
            "кнопку меню слева от поля ввода."
        )
    else:
        tail = "\n\nДля регистрации следуйте инструкции в мини-аппе."
    return greeting + _ABOUT + tail


async def send_main_message(bot, chat_id: int, full_name: str, user_id: int) -> None:
    """Отправляет главное сообщение (логотип + приветствие + навигация) в чат.

    Вызывается и из хэндлеров, и с веб-сервера (после выхода из аккаунта)."""
    global _logo_file_id
    caption = await _main_caption(full_name, user_id)
    photo = _logo_file_id or FSInputFile(LOGO_PATH)
    msg = await bot.send_photo(chat_id, photo, caption=caption, reply_markup=_main_keyboard())
    if _logo_file_id is None and msg.photo:
        _logo_file_id = msg.photo[-1].file_id


async def _send_main(message: Message, user, user_id: int) -> None:
    """Отправляет главное сообщение в ответ на сообщение пользователя."""
    await send_main_message(message.bot, message.chat.id, user.full_name, user_id)


async def _safe_delete(message: Message) -> None:
    """Удаляет сообщение, игнорируя ошибки (уже удалено / слишком старое)."""
    try:
        await message.delete()
    except Exception:
        pass


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    """Обработчик /start. С deep-link токеном — регистрация, иначе — главное меню."""
    token = (command.args or "").strip()
    if token:
        await _register_via_link(message, token)
        return

    await _send_main(message, message.from_user, message.from_user.id)


async def _register_via_link(message: Message, token: str) -> None:
    """Регистрация по одноразовой подписанной ссылке из личного кабинета."""
    user_id = message.from_user.id

    if await db.user_exists(user_id):
        await message.answer(
            "Вы уже зарегистрированы ✅", reply_markup=_registered_keyboard()
        )
        return

    if not link_token.verify_link_token(token) or not await db.claim_link_token(token, user_id):
        await message.answer(
            "⚠️ Ссылка недействительна или уже использована.\n"
            "Получите новую в личном кабинете на <b>medinternet.ru</b>."
        )
        return

    await db.register_user(
        user_id, message.from_user.username, message.from_user.full_name
    )
    await message.answer(
        "🎉 <b>Регистрация успешна</b>", reply_markup=_registered_keyboard()
    )


# ---------- Навигация по кнопкам главного меню ----------


@router.callback_query(F.data == "nav:home")
async def cb_home(callback: CallbackQuery):
    """Возврат к главному сообщению."""
    await callback.answer()
    await _safe_delete(callback.message)
    await _send_main(callback.message, callback.from_user, callback.from_user.id)


@router.callback_query(F.data == "nav:partners")
async def cb_partners(callback: CallbackQuery):
    """«Поделиться с другом»: приглашение + кнопки шеринга."""
    await callback.answer()
    await _safe_delete(callback.message)
    me = await callback.bot.me()
    await callback.message.answer(
        _partners_text(me.username),
        reply_markup=_partners_keyboard(me.username),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@router.callback_query(F.data == "nav:instruction")
async def cb_instruction(callback: CallbackQuery):
    """Инструкция — как пользоваться поисковиком."""
    await callback.answer()
    await _safe_delete(callback.message)
    await callback.message.answer(_INSTRUCTION_TEXT, reply_markup=_back_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(
        "📋 <b>Доступные команды:</b>\n\n"
        "/start — Начать работу с ботом\n"
        "/help — Показать это сообщение\n"
    )
