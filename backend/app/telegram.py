"""Проверка Telegram WebApp initData (HMAC-SHA256) и определение пользователя.

Документация: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import Header, HTTPException, status

from .config import get_settings


def verify_init_data(init_data: str, bot_token: str, max_age: int) -> dict:
    """Возвращает распарсенный Telegram user. Бросает ValueError при подделке."""
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN не задан на сервере")

    data = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise ValueError("в initData нет hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("подпись initData неверна")

    if max_age > 0:
        auth_date = int(data.get("auth_date") or 0)
        if not auth_date or time.time() - auth_date > max_age:
            raise ValueError("initData просрочена")

    try:
        return json.loads(data.get("user") or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("user в initData не JSON") from exc


async def current_user(
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
    x_dev_user_id: str | None = Header(default=None, alias="X-Dev-User-Id"),
) -> str:
    """FastAPI-зависимость: id пользователя для owner_id / user_id."""
    settings = get_settings()

    if x_telegram_init_data:
        try:
            user = verify_init_data(
                x_telegram_init_data, settings.telegram_bot_token, settings.telegram_auth_max_age
            )
        except ValueError as exc:
            if settings.dev_allow_unverified:
                # локальная разработка: подписи нет, но нужен стабильный id
                return (x_dev_user_id or "dev_local")[:64]
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=f"initData: {exc}"
            ) from exc

        user_id = user.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="initData без user.id")
        return str(user_id)

    if settings.dev_allow_unverified and x_dev_user_id:
        return x_dev_user_id[:64]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="нет X-Telegram-Init-Data (и DEV_ALLOW_UNVERIFIED выключен)",
    )
