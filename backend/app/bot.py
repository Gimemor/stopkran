"""Telegram-бот: вебхук, /start с кнопкой Mini App, inline-режим для «Поделиться».

Бот не обязателен для работы ленты — он нужен только для точки входа
и шаринга. Токен читается из .env, на фронтенд не попадает никогда.
"""

from __future__ import annotations

import hmac
import logging

import httpx
from fastapi import APIRouter, Body, Header, HTTPException

from .config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
settings = get_settings()

_API = "https://api.telegram.org/bot{token}/{method}"


async def call(method: str, payload: dict) -> dict | None:
    """Вызов Bot API. Возвращает None, если токен не задан."""
    token = settings.telegram_bot_token
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN не задан — %s пропущен", method)
        return None

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(_API.format(token=token, method=method), json=payload)

    try:
        data = response.json()
    except ValueError:
        logger.error("Telegram %s: не-JSON ответ %s", method, response.status_code)
        return None

    if not data.get("ok"):
        logger.error("Telegram %s: %s", method, data)
    return data


def _open_button() -> dict | None:
    """Inline-кнопка, открывающая Mini App. Telegram требует HTTPS."""
    url = settings.mini_app_url.strip()
    if not url.startswith("https://"):
        return None
    return {"inline_keyboard": [[{"text": "🛑 Открыть Стоп-кран", "web_app": {"url": url}}]]}


async def send_welcome(chat_id: int, name: str) -> None:
    markup = _open_button()
    if markup is None:
        await call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    f"Привет, {name}! Я «Стоп-кран» — помогаю не покупать импульсивно.\n\n"
                    "Чтобы получить кнопку запуска, задайте MINI_APP_URL (https://…) "
                    "в backend/.env и перезапустите сервис."
                ),
            },
        )
        return

    await call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": (
                f"Привет, {name}! Опиши покупку, которую обдумываешь, — "
                "другие анонимно скажут, стоит ли брать."
            ),
            "reply_markup": markup,
        },
    )


async def answer_inline(inline_query_id: str, text: str) -> None:
    """Результат для inline-режима (кнопка «Поделиться» на карточке)."""
    text = (text or "Стоп-кран: стоит ли это покупать?").strip()[:512]
    result: dict = {
        "type": "article",
        "id": "stopkran-share",
        "title": "Отправить в чат",
        "description": text[:100],
        "input_message_content": {"message_text": text},
    }
    url = settings.mini_app_url.strip()
    if url.startswith("https://"):
        result["reply_markup"] = {
            "inline_keyboard": [[{"text": "Открыть Стоп-кран", "url": url}]]
        }

    await call(
        "answerInlineQuery",
        {"inline_query_id": inline_query_id, "results": [result], "cache_time": 0},
    )


@router.post("/webhook", include_in_schema=False)
async def webhook(
    update: dict = Body(...),
    secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
) -> dict:
    # Telegram присылает этот заголовок, если secret_token задан при setWebhook
    if settings.telegram_webhook_secret:
        if not hmac.compare_digest(secret or "", settings.telegram_webhook_secret):
            raise HTTPException(status_code=403, detail="bad secret token")

    message = update.get("message")
    if message:
        chat_id = (message.get("chat") or {}).get("id")
        text = (message.get("text") or "").strip()
        if chat_id and text.startswith("/start"):
            name = (message.get("from") or {}).get("first_name") or "друг"
            await send_welcome(chat_id, name)

    inline_query = update.get("inline_query")
    if inline_query and inline_query.get("id"):
        await answer_inline(inline_query["id"], inline_query.get("query") or "")

    return {"ok": True}


@router.get("/status")
async def status() -> dict:
    """Диагностика без раскрытия токена."""
    return {
        "bot_configured": bool(settings.telegram_bot_token),
        "mini_app_url_set": settings.mini_app_url.startswith("https://"),
        "webhook_secret_set": bool(settings.telegram_webhook_secret),
        "init_data_verification": bool(settings.telegram_bot_token) and not settings.dev_allow_unverified,
    }
