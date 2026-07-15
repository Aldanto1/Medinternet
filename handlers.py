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
)

import db
import link_token
from config import WEBAPP_URL, webapp_url

router = Router()

SITE_URL = "https://medinternet.ru/"
SUPPORT_URL = "https://t.me/traderx_p2p"
AGREEMENT_URL = "https://medinternet.ru/"
LOGO_PATH = Path(__file__).resolve().parent / "webapp" / "logo.png"
# Кэш file_id логотипа: первую отправку грузим файлом, дальше — по id (без повторной загрузки).
_logo_file_id: str | None = None


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
    f'Я — бот <a href="{SITE_URL}"><b>Мединтернет</b></a>, медицинский ИИ-поисковик '
    "для врачей и фармацевтов (совместно с Сеченовским Университетом).\n\n"
    "Отвечаю на вопросы о препаратах, болезнях и схемах лечения, "
    "ищу по МКБ-10 и АТХ, даю ответы со ссылками на источники."
)

_PARTNERS_TEXT = (
    "🤝 <b>Партнёрам</b>\n\n"
    "Приглашайте коллег в Мединтернет и получайте <b>дни подписки бесплатно</b>!\n\n"
    "• За каждого друга, который зарегистрируется по вашей ссылке, "
    "вы получаете бонусные дни доступа к медицинскому поисковику.\n"
    "• Чем больше коллег присоединится — тем дольше пользуетесь всеми функциями бесплатно.\n\n"
    "Отправьте приглашение удобным способом:"
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

_HELP_TEXT = (
    "🙋 <b>Помощь</b>\n\n"
    "Помогите нам стать лучше и найдите ответы на свои вопросы.\n\n"
    "Оставьте отзыв, напишите в поддержку или ознакомьтесь "
    "с пользовательским соглашением."
)

_TARIFF_TEXT = (
    "💳 <b>Ваш тариф: Обычный</b>\n\n"
    "Сейчас вам доступен базовый доступ к медицинскому поисковику.\n\n"
    "<b>Тариф Плюс:</b>\n"
    "• больше запросов к поисковику;\n"
    "• приоритетная обработка вопросов;\n"
    "• ранний доступ к новым возможностям.\n\n"
    "Выберите период подписки:"
)


def _main_keyboard() -> InlineKeyboardMarkup:
    """Навигация под главным сообщением."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤝 Партнёрам", callback_data="nav:partners"),
                InlineKeyboardButton(text="💳 Мой тариф", callback_data="nav:tariff"),
            ],
            [
                InlineKeyboardButton(text="📖 Инструкция", callback_data="nav:instruction"),
                InlineKeyboardButton(text="❓ Помощь", callback_data="nav:help"),
            ],
        ]
    )


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


def _help_keyboard() -> InlineKeyboardMarkup:
    """Кнопки раздела «Помощь»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Оставить отзыв", callback_data="help:feedback")],
            [InlineKeyboardButton(text="💬 Написать в поддержку", url=SUPPORT_URL)],
            [InlineKeyboardButton(text="📄 Пользовательское соглашение", url=AGREEMENT_URL)],
            [InlineKeyboardButton(text="← Вернуться", callback_data="nav:home")],
        ]
    )


def _tariff_keyboard() -> InlineKeyboardMarkup:
    """Кнопки раздела «Мой тариф»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Плюс на неделю", callback_data="tariff:week")],
            [InlineKeyboardButton(text="⭐ Плюс на месяц", callback_data="tariff:month")],
            [InlineKeyboardButton(text="⭐ Плюс на год", callback_data="tariff:year")],
            [InlineKeyboardButton(text="← Вернуться", callback_data="nav:home")],
        ]
    )


async def _main_caption(user, user_id: int) -> str:
    """Подпись главного сообщения (зависит от того, зарегистрирован ли пользователь)."""
    greeting = f"👋 Здравствуйте, <b>{user.full_name}</b>!\n\n"
    if await db.user_exists(user_id):
        tail = (
            "\n\n✅ Вы зарегистрированы. Медицинский поисковик доступен через "
            "кнопку меню слева от поля ввода."
        )
    else:
        tail = (
            "\n\nЧтобы получить доступ, зайдите в свой личный кабинет на "
            "<b>Мединтернет</b> и перейдите по ссылке для регистрации в Telegram."
        )
    return greeting + _ABOUT + tail


async def _send_main(message: Message, user, user_id: int) -> None:
    """Отправляет главное сообщение: логотип + приветствие + навигация."""
    global _logo_file_id
    caption = await _main_caption(user, user_id)
    photo = _logo_file_id or FSInputFile(LOGO_PATH)
    msg = await message.answer_photo(photo, caption=caption, reply_markup=_main_keyboard())
    if _logo_file_id is None and msg.photo:
        _logo_file_id = msg.photo[-1].file_id


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


# ---------- Навигация по кнопкам главного меню ----------


@router.callback_query(F.data == "nav:home")
async def cb_home(callback: CallbackQuery):
    """Возврат к главному сообщению."""
    await callback.answer()
    await _safe_delete(callback.message)
    await _send_main(callback.message, callback.from_user, callback.from_user.id)


@router.callback_query(F.data == "nav:partners")
async def cb_partners(callback: CallbackQuery):
    """Партнёрская программа с кнопками шеринга."""
    await callback.answer()
    await _safe_delete(callback.message)
    me = await callback.bot.me()
    await callback.message.answer(_PARTNERS_TEXT, reply_markup=_partners_keyboard(me.username))


@router.callback_query(F.data == "nav:instruction")
async def cb_instruction(callback: CallbackQuery):
    """Инструкция — как пользоваться поисковиком."""
    await callback.answer()
    await _safe_delete(callback.message)
    await callback.message.answer(_INSTRUCTION_TEXT, reply_markup=_back_keyboard())


@router.callback_query(F.data == "nav:help")
async def cb_help(callback: CallbackQuery):
    """Раздел «Помощь»: отзыв, поддержка, соглашение."""
    await callback.answer()
    await _safe_delete(callback.message)
    await callback.message.answer(_HELP_TEXT, reply_markup=_help_keyboard())


@router.callback_query(F.data == "nav:tariff")
async def cb_tariff(callback: CallbackQuery):
    """Раздел «Мой тариф»: текущий тариф и подписки Плюс."""
    await callback.answer()
    await _safe_delete(callback.message)
    await callback.message.answer(_TARIFF_TEXT, reply_markup=_tariff_keyboard())


@router.callback_query(F.data.in_({"tariff:week", "tariff:month", "tariff:year", "help:feedback"}))
async def cb_soon(callback: CallbackQuery):
    """Заглушки для кнопок, детали которых опишем позже (цены, форма отзыва)."""
    await callback.answer("Скоро будет доступно 🔧", show_alert=True)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(
        "📋 <b>Доступные команды:</b>\n\n"
        "/start — Начать работу с ботом\n"
        "/help — Показать это сообщение\n"
    )
