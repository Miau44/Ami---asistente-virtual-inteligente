"""Tests del fallback entre alias de modelo de Gemini ante cuota agotada (429)."""

from __future__ import annotations

import pytest
from google.genai import errors as genai_errors

from app.core import gemini_retry as gemini_retry_module
from app.core.gemini_retry import generar_con_fallback, modelos_con_fallback


def _client_error(code: int = 429, *, cuota_diaria: bool = False) -> genai_errors.ClientError:
    error: dict[str, object] = {"message": "boom", "status": "X"}
    if cuota_diaria:
        error["details"] = [
            {
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
            }
        ]
    return genai_errors.ClientError(code, {"error": error})


@pytest.fixture(autouse=True)
def _limpiar_cooldown() -> None:
    gemini_retry_module._modelos_agotados.clear()


def test_modelos_con_fallback_deduplica_si_son_iguales() -> None:
    assert modelos_con_fallback("a", "a") == ["a"]
    assert modelos_con_fallback("a", "b") == ["a", "b"]


@pytest.mark.asyncio
async def test_generar_con_fallback_usa_el_primer_modelo_si_funciona() -> None:
    llamadas: list[str] = []

    async def llamar(modelo: str) -> str:
        llamadas.append(modelo)
        return f"respuesta-de-{modelo}"

    resultado = await generar_con_fallback(["principal", "fallback"], llamar)

    assert resultado == "respuesta-de-principal"
    assert llamadas == ["principal"]


@pytest.mark.asyncio
async def test_generar_con_fallback_cambia_de_modelo_ante_cuota_diaria_agotada() -> None:
    """Cuota *diaria* (quotaId con "PerDay") no se reintenta: cambia de modelo de inmediato."""
    llamadas: list[str] = []

    async def llamar(modelo: str) -> str:
        llamadas.append(modelo)
        if modelo == "principal":
            raise _client_error(429, cuota_diaria=True)
        return f"respuesta-de-{modelo}"

    resultado = await generar_con_fallback(["principal", "fallback"], llamar)

    assert resultado == "respuesta-de-fallback"
    assert llamadas == ["principal", "fallback"]


def test_es_error_transitorio_no_reintenta_cuota_diaria_pero_si_otros_429() -> None:
    assert gemini_retry_module._es_error_transitorio(_client_error(429)) is True
    assert gemini_retry_module._es_error_transitorio(_client_error(429, cuota_diaria=True)) is False
    assert gemini_retry_module._es_error_transitorio(_client_error(400)) is False


@pytest.mark.asyncio
async def test_generar_con_fallback_propaga_error_no_429_sin_probar_fallback() -> None:
    llamadas: list[str] = []

    async def llamar(modelo: str) -> str:
        llamadas.append(modelo)
        raise _client_error(400)

    with pytest.raises(genai_errors.ClientError) as exc_info:
        await generar_con_fallback(["principal", "fallback"], llamar)

    assert exc_info.value.code == 400
    assert llamadas == ["principal"]


@pytest.mark.asyncio
async def test_generar_con_fallback_salta_modelo_en_cooldown() -> None:
    llamadas: list[str] = []

    async def agotar_principal(modelo: str) -> str:
        llamadas.append(modelo)
        if modelo == "principal":
            raise _client_error(429, cuota_diaria=True)
        return "ok"

    # Primera llamada: agota "principal" y queda en cooldown.
    await generar_con_fallback(["principal", "fallback"], agotar_principal)
    llamadas.clear()

    # Segunda "conversacion": debe saltar directo a "fallback" sin intentar "principal".
    async def solo_fallback(modelo: str) -> str:
        llamadas.append(modelo)
        return "ok"

    resultado = await generar_con_fallback(["principal", "fallback"], solo_fallback)

    assert resultado == "ok"
    assert llamadas == ["fallback"]
