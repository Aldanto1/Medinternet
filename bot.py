import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo

import db
from config import BOT_TOKEN, validate_config, PROXY_URL, WEBAPP_URL, webapp_url
from handlers import router
from server import start_webserver

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# Описание бота — показывается по центру пустого чата (под заголовком
# «Что умеет этот бот?») до нажатия СТАРТ. Лимит Telegram — 512 символов.
# Фото-логотип над описанием ставится вручную в @BotFather (Bot API не умеет).
BOT_DESCRIPTION = (
    "Мединтернет — это медицинский ИИ-поисковик для врачей и фармацевтов, "
    "созданный совместно с Сеченовским Университетом. Отвечает на вопросы "
    "о препаратах, болезнях и схемах лечения, ищет по МКБ-10 и АТХ и даёт "
    "ответы со ссылками на проверенные источники."
)


async def main():
    """Запуск бота."""
    # Проверяем конфигурацию
    validate_config()

    # Инициализация базы данных (пул + таблица users)
    await db.init()
    logger.info("База данных подключена")

    # Настройка сессии с прокси при наличии
    session = None
    if PROXY_URL:
        logger.info(f"Подключение через прокси: {PROXY_URL}")
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=PROXY_URL)

    # Инициализация бота и диспетчера
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Подключаем роутер с хэндлерами
    dp.include_router(router)

    # Поднимаем веб-сервер mini app (в том же процессе), передаём бота
    # для уведомлений после регистрации и его username для deep-link страницы
    me = await bot.get_me()
    runner = await start_webserver(bot, me.username)

    # Описание для пустого чата («Что умеет этот бот?»). Не критично при ошибке.
    try:
        await bot.set_my_description(description=BOT_DESCRIPTION)
        logger.info("Описание бота обновлено")
    except Exception as e:
        logger.warning(f"Не удалось установить описание бота: {e}")

    # Настраиваем кнопку меню на открытие mini app.
    # Ошибка здесь (например, неверный URL) не должна ронять весь бот.
    if WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Mini App", web_app=WebAppInfo(url=webapp_url())
                )
            )
            logger.info(f"Mini app доступен по адресу: {WEBAPP_URL}")
        except Exception as e:
            logger.warning(
                f"Не удалось установить кнопку меню (WEBAPP_URL={WEBAPP_URL!r}): {e}. "
                "Проверьте, что адрес начинается с https://"
            )
    else:
        logger.warning(
            "WEBAPP_URL не задан — кнопка регистрации не появится. "
            "Укажите публичный HTTPS-адрес в переменных окружения"
        )

    logger.info("Бот запускается...")

    # Удаляем вебхук (на случай, если был установлен) и запускаем polling
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
