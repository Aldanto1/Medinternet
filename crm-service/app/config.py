"""Конфигурация CRM-сервиса из переменных окружения (crm-service/.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Neon (read-only роль для чтения users + запись в схему crm)
CRM_DB_URL = os.getenv("CRM_DB_URL")

# Токен ОСНОВНОГО бота — им и только им можно слать сообщения пользователям
MAIN_BOT_TOKEN = os.getenv("MAIN_BOT_TOKEN")

# JWT-аутентификация специалистов
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "12"))

# Учётные данные специалиста (MVP: сверяем с .env, без хеширования)
CRM_LOGIN_EMAIL = os.getenv("CRM_LOGIN_EMAIL")
CRM_LOGIN_PASSWORD = os.getenv("CRM_LOGIN_PASSWORD")

# Очередь arq на Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Троттлинг рассылки (сообщений в секунду; лимит Bot API ~30/сек)
SEND_RATE_PER_SEC = float(os.getenv("SEND_RATE_PER_SEC", "25"))

# HTTP-сервер API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("PORT") or os.getenv("API_PORT") or "8090")


def validate(require_all: bool = True) -> None:
    """Проверяет обязательные переменные. На шаге 1 нужен только CRM_DB_URL."""
    missing = []
    if not CRM_DB_URL:
        missing.append("CRM_DB_URL")
    if require_all:
        for name, val in [
            ("MAIN_BOT_TOKEN", MAIN_BOT_TOKEN),
            ("JWT_SECRET", JWT_SECRET),
            ("CRM_LOGIN_EMAIL", CRM_LOGIN_EMAIL),
            ("CRM_LOGIN_PASSWORD", CRM_LOGIN_PASSWORD),
        ]:
            if not val:
                missing.append(name)
    if missing:
        raise ValueError(
            f"Отсутствуют переменные окружения: {', '.join(missing)}. "
            f"Заполните {ENV_PATH}"
        )
