"""Async SQLAlchemy engine and session."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


engine = None
async_session_maker = None


def init_engine(url: str | None = None):
    """Initialise (or re-initialise) the global engine."""
    global engine, async_session_maker
    if url:
        engine = create_async_engine(url, echo=False)
    else:
        engine = _make_engine()
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async session."""
    if async_session_maker is None:
        init_engine()
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
