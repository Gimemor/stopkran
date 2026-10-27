"""Async SQLAlchemy engine/session.

Поддерживает два типа подключения к Supabase:
  * прямое  — db.<ref>.supabase.co:5432 (только IPv6)
  * пулер   — aws-0-<region>.pooler.supabase.com:6543 (IPv4, нужен контейнерам)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings

# Параметры, которые понимает libpq, но не понимает asyncpg.
_LIBPQ_ONLY = {"sslmode", "pgbouncer", "connection_limit", "pool_mode"}


def normalize_url(raw: str) -> str:
    """postgres://... -> postgresql+asyncpg://..., выкидываем libpq-параметры."""
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://") :]
    elif raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://") :]

    parts = urlsplit(raw)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in _LIBPQ_ONLY]
    return urlunsplit(parts._replace(query=urlencode(query)))


settings = get_settings()

engine = create_async_engine(
    normalize_url(settings.database_url),
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    connect_args={
        # Supabase требует TLS
        "ssl": "require" if settings.db_ssl else False,
        # transaction-пулер (pgbouncer) не умеет prepared statements
        "statement_cache_size": 0,
    },
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
