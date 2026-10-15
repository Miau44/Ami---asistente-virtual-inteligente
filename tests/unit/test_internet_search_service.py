"""Tests unitarios de InternetSearchService (tool buscar_en_internet depende de el)."""

from __future__ import annotations

import httpx
import pytest

from app.services.internet_search_service import InternetSearchService


@pytest.mark.asyncio
async def test_sin_api_key_devuelve_no_encontrado_sin_llamar_a_la_red() -> None:
    service = InternetSearchService()
    service._api_key = ""  # simula TAVILY_API_KEY vacio sin depender del .env de test

    resultado = await service.buscar("requisitos NIT Bolivia")

    assert resultado == {
        "encontrado": False,
        "resultados": [],
        "mensaje": "La busqueda en internet no esta configurada.",
    }


@pytest.mark.asyncio
async def test_buscar_devuelve_resultados_normalizados(monkeypatch: pytest.MonkeyPatch) -> None:
    service = InternetSearchService()
    service._api_key = "fake-key"

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "answer": "resumen de prueba",
                "results": [
                    {
                        "title": "Titulo",
                        "url": "https://lapaz.bo/algo",
                        "content": "contenido" * 100,
                    }
                ],
            }

    class _FakeAsyncClient:
        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    resultado = await service.buscar("requisitos NIT Bolivia")

    assert resultado["encontrado"] is True
    assert resultado["resumen"] == "resumen de prueba"
    assert resultado["resultados"] == [
        {
            "titulo": "Titulo",
            "url": "https://lapaz.bo/algo",
            "extracto": ("contenido" * 100)[:500],
        }
    ]


@pytest.mark.asyncio
async def test_buscar_sin_resultados_devuelve_no_encontrado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InternetSearchService()
    service._api_key = "fake-key"

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"answer": None, "results": []}

    class _FakeAsyncClient:
        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> _FakeResponse:
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    resultado = await service.buscar("algo muy raro que no existe")

    assert resultado["encontrado"] is False
    assert resultado["resultados"] == []


@pytest.mark.asyncio
async def test_buscar_ante_error_de_red_devuelve_no_encontrado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = InternetSearchService()
    service._api_key = "fake-key"

    class _FakeAsyncClient:
        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> None:
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: _FakeAsyncClient())

    resultado = await service.buscar("requisitos NIT Bolivia")

    assert resultado["encontrado"] is False
