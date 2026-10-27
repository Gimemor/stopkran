"""Pydantic-схемы запросов и ответов."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Side = Literal["for", "against"]


class RequestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    amount: float = Field(gt=0, le=100_000_000)
    reason: str = Field(min_length=3, max_length=1000)
    alternative: str = Field(default="", max_length=800)

    @field_validator("title", "reason", "alternative")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class VoteCreate(BaseModel):
    request_id: int = Field(gt=0)
    side: Side
    comment: str = Field(default="", max_length=300)

    @field_validator("comment")
    @classmethod
    def strip(cls, v: str) -> str:
        return v.strip()


class CommentOut(BaseModel):
    vote: Side
    text: str
    at: datetime


class RequestOut(BaseModel):
    id: int
    owner_id: str
    title: str
    amount: float
    reason: str
    alternative: str
    created_at: datetime
    votes_for: int
    votes_against: int
    comments: list[CommentOut]
    voted_by: dict[str, Side]
    vote_times: list[datetime]


class FeedOut(BaseModel):
    requests: list[RequestOut]


class IdOut(BaseModel):
    id: int


class VoteOut(BaseModel):
    id: int
    side: Side


class HealthOut(BaseModel):
    status: str
    environment: str
    database: bool
    version: str
