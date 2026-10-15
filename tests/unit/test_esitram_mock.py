"""Tests unitarios del cliente mock de e-SITRAM (tool check_procedure_status depende de el)."""

from __future__ import annotations

import pytest

from app.integrations.esitram_mock import ESitramMockClient


@pytest.mark.asyncio
async def test_iniciar_tramite_genera_codigo_externo() -> None:
    client = ESitramMockClient()
    resultado = await client.iniciar_tramite("licencia_funcionamiento", {})

    assert resultado["estado"] == "iniciado"
    assert resultado["codigo_externo"].startswith("ESITRAM-MOCK-")


@pytest.mark.asyncio
async def test_consultar_estado_tramite_es_deterministico() -> None:
    client = ESitramMockClient()
    primera = await client.consultar_estado_tramite("ABC123")
    segunda = await client.consultar_estado_tramite("ABC123")

    assert primera["estado"] == segunda["estado"]


@pytest.mark.asyncio
async def test_listar_requisitos_conocidos() -> None:
    client = ESitramMockClient()
    requisitos = await client.listar_requisitos("licencia_funcionamiento")

    assert "NIT valido" in requisitos
