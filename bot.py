import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo

import db
from config import BOT_TOKEN, validate_config, PROXY_URL, WEBAPP_URL
from handlers import router
from server import start_webserver

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


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

    # Поднимаем веб-сервер mini app (в том же процессе)
    runner = await start_webserver()

    # Настраиваем кнопку меню на открытие mini app.
    # Ошибка здесь (например, неверный URL) не должна ронять весь бот.
    if WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Mini App", web_app=WebAppInfo(url=WEBAPP_URL)
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
