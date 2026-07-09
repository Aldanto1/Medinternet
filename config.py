import os
from pathlib import Path
from dotenv import load_dotenv

try:
    import winreg  # только Windows; на Linux-хостинге модуля нет
except ImportError:
    winreg = None

# Загружаем переменные из env/.env
ENV_PATH = Path(__file__).resolve().parent / "env" / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Telegram Bot
BOT_TOKEN = os.getenv("BOT_TOKEN")

# База данных (Neon / PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")

# Mini App (веб-приложение)
# Публичный HTTPS-адрес, по которому Telegram открывает mini app
# (например, ссылка от cloudflared-туннеля). Без него кнопка регистрации не покажется.
WEBAPP_URL = os.getenv("WEBAPP_URL")
# Адрес и порт веб-сервера mini app.
# На облачном хостинге платформа задаёт порт через переменную PORT,
# а слушать нужно на 0.0.0.0. Локально по умолчанию тоже подходит.
WEBAPP_HOST = os.getenv("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT = int(os.getenv("PORT") or os.getenv("WEBAPP_PORT") or "8080")

# API сервера
API_SERVER_URL = os.getenv("API_SERVER_URL")
API_SERVER_KEY = os.getenv("API_SERVER_KEY")


def get_windows_socks_proxy():
    """Автоматически считывает настройки прокси из реестра Windows."""
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as key:
            enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
            if enabled:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
                # Формат может быть: "socks=127.0.0.1:10808", "http://127.0.0.1:8080" или "127.0.0.1:8080"
                if "socks=" in server:
                    addr = server.split("socks=")[-1].strip()
                    return f"socks5://{addr}"
                elif server and "=" not in server:
                    if "://" in server:
                        return server
                    return f"http://{server}"
    except Exception:
        pass
    return None


# Прокси для обхода блокировок Telegram API (по умолчанию берется из системы)
PROXY_URL = os.getenv("PROXY_URL") or get_windows_socks_proxy()


def validate_config():
    """Проверяет, что все обязательные переменные заданы."""
    missing = []
    if not BOT_TOKEN or BOT_TOKEN == "your_bot_token_here":
        missing.append("BOT_TOKEN")
    if not DATABASE_URL:
        missing.append("DATABASE_URL")
    if missing:
        raise ValueError(
            f"Отсутствуют обязательные переменные окружения: {', '.join(missing)}.\n"
            f"Заполните файл: {ENV_PATH}"
        )

