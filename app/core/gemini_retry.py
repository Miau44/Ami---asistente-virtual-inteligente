"""Reintento acotado y fallback entre alias de modelo para llamadas a Gemini.

El nivel gratuito de AI Studio devuelve intermitentemente `503 UNAVAILABLE` ("high
demand") o `429 RESOURCE_EXHAUSTED` de forma transitoria (verificado en vivo durante
el desarrollo: la misma request fallaba y funcionaba segundos despues sin cambiar
nada). Ademas, cada alias de modelo (`gemini-flash-latest`,
`gemini-flash-lite-latest`) tiene su **propio** cupo gratuito diario, independiente
entre si (ver ADR-010 en docs/decisiones-tecnicas.md) — un 429 puede significar
"cuota del dia agotada para este modelo especifico", no un error transitorio.

Por eso hay tres mecanismos, no uno, cada cual acotado (nunca infinito, mismo
criterio que el circuit breaker de integraciones municipales, ADR-005):
1. Reintento corto con backoff para sobrecarga pasajera (503, o 429 que no sea
   especificamente cuota *diaria*) del mismo modelo. Un 429 de cuota diaria
   (identificable por `quotaId` con "PerDay" en el detalle del error) NO se
   reintenta — nunca ayuda, solo agrega latencia antes de cambiar de modelo.
2. Cambio de alias de modelo cuando esos reintentos se agotan y el 429 persiste.
3. Un modelo que se agoto se recuerda en memoria por un rato (cooldown) para que
   las siguientes conversaciones salten directo al fallback en vez de perder
   varios segundos reintentando un modelo que se sabe que va a fallar de nuevo."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from google.genai import errors as genai_errors
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Cuanto tiempo se evita reintentar un modelo que ya devolvio 429 (cuota agotada).
# 30 min es un compromiso: bastante para no martillar un modelo agotado durante una
# demo entera, pero corto para volver a intentarlo por si el cupo era por minuto y
# no por dia (o si Google reasigna cupo). No afecta el cupo real de Google, solo
# evita perder tiempo reintentando localmente.
_COOLDOWN_SECONDS = 1800.0
_modelos_agotados: dict[str, float] = {}


def _en_cooldown(modelo: str) -> bool:
    marca = _modelos_agotados.get(modelo)
    if marca is None:
        return False
    if time.monotonic() - marca >= _COOLDOWN_SECONDS:
        del _modelos_agotados[modelo]
        return False
    return True


def _marcar_agotado(modelo: str) -> None:
    _modelos_agotados[modelo] = time.monotonic()


def _es_cuota_diaria(exc: genai_errors.ClientError) -> bool:
    """True si el 429 es especificamente por cuota *diaria* agotada (Google incluye
    `quotaId` con "PerDay" en `error.details[].violations[]`). Reintentar el mismo
    modelo nunca ayuda en ese caso — solo tiene sentido cambiar de alias. Un 429 sin
    ese detalle (ej. rate limit por minuto) si vale la pena reintentar una vez."""
    detalles = exc.details
    error_obj = detalles.get("error", detalles) if isinstance(detalles, dict) else None
    if not isinstance(error_obj, dict):
        return False
    for item in error_obj.get("details", []):
        if not isinstance(item, dict):
            continue
        for violacion in item.get("violations", []):
            if isinstance(violacion, dict) and "PerDay" in violacion.get("quotaId", ""):
                return True
    return False


def _es_error_transitorio(exc: BaseException) -> bool:
    if isinstance(exc, genai_errors.ServerError):
        return True
    if isinstance(exc, genai_errors.ClientError):
        return exc.code == 429 and not _es_cuota_diaria(exc)
    return False


gemini_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(_es_error_transitorio),
)


def modelos_con_fallback(modelo_principal: str, modelo_fallback: str) -> list[str]:
    """Lista de modelos a intentar en orden, sin duplicar si ambos son el mismo."""
    if modelo_principal == modelo_fallback:
        return [modelo_principal]
    return [modelo_principal, modelo_fallback]


async def generar_con_fallback(modelos: list[str], llamar: Callable[[str], Awaitable[T]]) -> T:
    """Intenta `llamar(modelo)` para cada modelo de la lista, en orden.

    Cada intento por modelo ya pasa por `gemini_retry` (reintentos cortos para
    sobrecarga transitoria). Solo se pasa al siguiente modelo cuando esos
    reintentos se agotan y el error sigue siendo `429` (cuota agotada para ese
    alias especifico, no sobrecarga pasajera); ese modelo queda en cooldown para
    conversaciones futuras. Cualquier otro tipo de error se propaga de inmediato
    sin probar el resto de la lista. Si todos los modelos estan en cooldown, se
    intentan igual en orden (mejor intentar y fallar rapido que no intentar nada)."""
    orden = [m for m in modelos if not _en_cooldown(m)] or modelos
    llamar_con_reintento = gemini_retry(llamar)
    ultimo_error: genai_errors.ClientError | None = None

    for i, modelo in enumerate(orden):
        try:
            return await llamar_con_reintento(modelo)
        except genai_errors.ClientError as exc:
            if exc.code != 429:
                raise
            ultimo_error = exc
            _marcar_agotado(modelo)
            if i < len(orden) - 1:
                logger.warning(
                    "gemini_modelo_agotado_cambiando_fallback",
                    modelo_agotado=modelo,
                    modelo_siguiente=orden[i + 1],
                )

    assert ultimo_error is not None
    raise ultimo_error
