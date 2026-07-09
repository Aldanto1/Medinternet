"""Клиент к нейросети через OpenRouter (OpenAI-совместимый API).

Временное решение (Вариант Б): бот ходит напрямую в модель через OpenRouter.
Позже будет заменён на клиент RXCode AI (с медицинским RAG).

OpenRouter не хранит контекст — историю диалога ведём на своей стороне
(см. таблицу ai_conversations в db.py) и передаём её списком messages.
"""
import logging

import aiohttp

from config import NEURO_API_URL, NEURO_API_KEY, NEURO_MODEL, PROXY_URL

logger = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=120)

# Системная инструкция для модели
SYSTEM_PROMPT = (
    "Ты — медицинский ИИ-ассистент для врачей сервиса Medinternet. "
    "Отвечай на русском языке, профессионально, структурированно и по существу. "
    "Если вопрос выходит за рамки медицины, вежливо сообщи об этом. "
    "Не ставь окончательный диагноз вместо врача — помогай информацией и рассуждением."
)


class AIError(Exception):
    """Ошибка обращения к нейросети."""


def is_configured() -> bool:
    """True, если заданы адрес и ключ API нейросети."""
    return bool(NEURO_API_URL and NEURO_API_KEY)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {NEURO_API_KEY}",
        "Content-Type": "application/json",
        # Необязательные заголовки для статистики OpenRouter
        "X-Title": "Medinternet Bot",
    }


async def chat_completion(messages: list) -> str:
    """Отправляет историю сообщений в модель и возвращает текст ответа.

    messages — список вида [{"role": "system"|"user"|"assistant", "content": "..."}].
    """
    url = f"{NEURO_API_URL}/chat/completions"
    payload = {"model": NEURO_MODEL, "messages": messages}

    async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
        # PROXY_URL задан только локально (обход геоблокировки); на хостинге он пустой
        async with session.post(url, json=payload, headers=_headers(), proxy=PROXY_URL) as resp:
            text = await resp.text()
            if resp.status == 401:
                raise AIError("Неверный ключ OpenRouter (401)")
            if resp.status == 402:
                raise AIError("Недостаточно средств на балансе OpenRouter (402)")
            if resp.status == 429:
                raise AIError("Слишком много запросов, попробуйте позже (429)")
            if resp.status != 200:
                raise AIError(f"OpenRouter HTTP {resp.status}: {text[:200]}")
            try:
                data = await resp.json()
            except aiohttp.ContentTypeError:
                raise AIError("Некорректный ответ OpenRouter")

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise AIError("В ответе OpenRouter нет текста")
