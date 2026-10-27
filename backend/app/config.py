"""Настройки приложения. Все секреты читаются из окружения / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "stopkran-api"
    environment: str = "dev"
    port: int = 8000

    # --- База данных (Supabase Postgres) ---
    database_url: str
    db_ssl: bool = True
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_auth_max_age: int = 86_400  # сек; 0 = не проверять свежесть
    dev_allow_unverified: bool = True
    # HTTPS-адрес Mini App (кнопка «Открыть» в боте). Пусто = кнопки нет.
    mini_app_url: str = ""
    # Папка с index.html — чтобы отдать фронтенд тем же origin (GET /mini/).
    # Пусто = роут выключен. В docker-compose: FRONTEND_DIR=..
    frontend_dir: str = ""
    # Проверка заголовка X-Telegram-Bot-Api-Secret-Token на вебхуке
    telegram_webhook_secret: str = ""

    # 0 = без лимита. Для прода: 3
    free_limit: int = 0

    cors_origins: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
