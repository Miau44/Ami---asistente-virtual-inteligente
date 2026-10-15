"""Engine y sesion async de SQLAlchemy 2.0, mas la dependencia de FastAPI para inyectarla."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=False)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia FastAPI: entrega una sesion por request y la cierra al final."""
    async with AsyncSessionLocal() as session:
        yield session
