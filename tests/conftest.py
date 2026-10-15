"""Fixtures compartidas: cliente HTTP de test, base de datos de test (SQLite en
memoria via aiosqlite) y mocks de integraciones municipales."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.db.models  # noqa: F401 - registra todos los modelos en Base.metadata
from app.api.v1 import deps as api_deps
from app.db.base import Base
from app.db.models.ciudadano import Ciudadano
from app.db.session import get_db_session
from app.integrations.esitram_mock import ESitramMockClient
from app.main import app


class _FakeRedis:
    """Redis en memoria minimo (solo incr/expire) para no depender de un Redis real
    en la suite de tests: el rate limiting es una preocupacion de infraestructura,
    no de logica de negocio, y no aporta valor testearlo contra un Redis de verdad."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, seconds: int) -> None:
        return None


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    fake = _FakeRedis()
    monkeypatch.setattr(api_deps, "get_redis", lambda: fake)
    return fake


@pytest_asyncio.fixture
async def test_engine() -> AsyncIterator[object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: object) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)  # type: ignore[arg-type]
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine: object) -> AsyncIterator[AsyncClient]:
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)  # type: ignore[arg-type]

    async def _override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def esitram_mock_client() -> ESitramMockClient:
    return ESitramMockClient()


@pytest_asyncio.fixture
async def ciudadano_demo(db_session: AsyncSession) -> Ciudadano:
    ciudadano = Ciudadano(id=uuid.uuid4(), telefono_whatsapp="whatsapp:+59170000000", nombre="Demo")
    db_session.add(ciudadano)
    await db_session.commit()
    await db_session.refresh(ciudadano)
    return ciudadano
