"""Точка входа FastAPI."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .api import router
from .bot import router as bot_router
from .config import get_settings
from .db import engine

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

# Авторизация идёт заголовком (X-Telegram-Init-Data), не cookie,
# поэтому credentials не нужны.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(bot_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs", "health": "/api/health"}


def _frontend_file() -> Path:
    if not settings.frontend_dir:
        raise HTTPException(status_code=404, detail="FRONTEND_DIR не задан")
    index = (Path(settings.frontend_dir) / "index.html").resolve()
    if not index.is_file():
        raise HTTPException(status_code=404, detail=f"index.html не найден: {index}")
    return index


# Mini App тем же origin, что и API: один туннель, CORS не нужен.
# Отдаём ровно один файл — папку целиком не раздаём (там .env).
@app.get("/mini", include_in_schema=False)
@app.get("/mini/", include_in_schema=False)
async def mini_app() -> FileResponse:
    return FileResponse(_frontend_file(), media_type="text/html; charset=utf-8")
