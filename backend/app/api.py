"""HTTP API: лента, заявки, голоса."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_session
from .models import Request, Vote
from .schemas import (
    CommentOut,
    FeedOut,
    HealthOut,
    IdOut,
    RequestCreate,
    RequestOut,
    VoteCreate,
    VoteOut,
)
from .telegram import current_user

router = APIRouter(prefix="/api")
settings = get_settings()

FEED_LIMIT = 200
COMMENTS_PER_REQUEST = 3


@router.get("/health", response_model=HealthOut)
async def health(session: AsyncSession = Depends(get_session)) -> HealthOut:
    db_ok = True
    try:
        await session.execute(select(1))
    except Exception:  # noqa: BLE001 - healthcheck не должен падать
        db_ok = False
    return HealthOut(
        status="ok", environment=settings.environment, database=db_ok, version="1.0.0"
    )


@router.get("/feed", response_model=FeedOut)
async def feed(session: AsyncSession = Depends(get_session)) -> FeedOut:
    rows = (
        (
            await session.execute(
                select(Request).order_by(Request.created_at.desc()).limit(FEED_LIMIT)
            )
        )
        .scalars()
        .all()
    )

    votes: list[Vote] = []
    if rows:
        votes = (
            (
                await session.execute(
                    select(Vote)
                    .where(Vote.request_id.in_([r.id for r in rows]))
                    .order_by(Vote.created_at)
                )
            )
            .scalars()
            .all()
        )

    by_request: dict[int, list[Vote]] = defaultdict(list)
    for vote in votes:
        by_request[vote.request_id].append(vote)

    out: list[RequestOut] = []
    for row in rows:
        own = by_request.get(row.id, [])
        voted_by = {str(v.user_id): v.side for v in own}
        comments = [
            CommentOut(vote=v.side, text=v.comment, at=v.created_at)
            for v in own
            if v.comment
        ][-COMMENTS_PER_REQUEST:]
        out.append(
            RequestOut(
                id=row.id,
                owner_id=str(row.owner_id),
                title=row.title,
                amount=float(row.amount),
                reason=row.reason,
                alternative=row.alternative or "",
                created_at=row.created_at,
                votes_for=sum(1 for v in own if v.side == "for"),
                votes_against=sum(1 for v in own if v.side == "against"),
                comments=comments,
                voted_by=voted_by,
                vote_times=[v.created_at for v in own],
            )
        )

    return FeedOut(requests=out)


@router.post("/requests", status_code=status.HTTP_201_CREATED, response_model=IdOut)
async def create_request(
    payload: RequestCreate,
    user_id: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> IdOut:
    if settings.free_limit > 0:
        used = await session.scalar(
            select(func.count()).select_from(Request).where(Request.owner_id == user_id)
        )
        if (used or 0) >= settings.free_limit:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Лимит {settings.free_limit} заявки на бесплатном тарифе",
            )

    request = Request(
        owner_id=user_id,
        title=payload.title,
        amount=payload.amount,
        reason=payload.reason,
        alternative=payload.alternative,
    )
    session.add(request)
    await session.commit()
    return IdOut(id=request.id)


@router.post("/votes", status_code=status.HTTP_201_CREATED, response_model=VoteOut)
async def create_vote(
    payload: VoteCreate,
    user_id: str = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> VoteOut:
    exists = await session.get(Request, payload.request_id)
    if exists is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    vote = Vote(
        request_id=payload.request_id,
        user_id=user_id,
        side=payload.side,
        comment=payload.comment,
    )
    session.add(vote)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Вы уже голосовали") from exc

    return VoteOut(id=vote.id, side=vote.side)
