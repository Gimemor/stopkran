"""Создать таблицы по ORM-моделям (для локальной разработки).

Для Supabase правильнее выполнить backend/schema.sql в SQL Editor.
Запуск: python -m app.init_db
"""

from __future__ import annotations

import asyncio

from .db import engine
from .models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("schema ready")


if __name__ == "__main__":
    asyncio.run(main())
