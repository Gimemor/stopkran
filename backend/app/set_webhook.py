"""Регистрация вебхука бота.

    python -m app.set_webhook https://<публичный-хост>
    python -m app.set_webhook --delete

Публичный хост должен быть HTTPS (Telegram не принимает http).
Локально: `cloudflared tunnel --url http://localhost:8000`.
"""

from __future__ import annotations

import asyncio
import sys

from .bot import call
from .config import get_settings


async def main(argv: list[str]) -> int:
    settings = get_settings()

    if not settings.telegram_bot_token:
        print("TELEGRAM_BOT_TOKEN не задан в backend/.env")
        return 1

    if "--delete" in argv:
        print(await call("deleteWebhook", {"drop_pending_updates": False}))
        return 0

    args = [a for a in argv[1:] if not a.startswith("-")]
    if not args:
        print("usage: python -m app.set_webhook https://<public-host> [--delete]")
        return 1

    url = args[0].rstrip("/") + "/api/telegram/webhook"
    payload: dict = {
        "url": url,
        "allowed_updates": ["message", "inline_query"],
        "drop_pending_updates": True,
    }
    if settings.telegram_webhook_secret:
        payload["secret_token"] = settings.telegram_webhook_secret

    result = await call("setWebhook", payload)
    print(f"webhook → {url}")
    print(result)
    return 0 if result and result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv)))
