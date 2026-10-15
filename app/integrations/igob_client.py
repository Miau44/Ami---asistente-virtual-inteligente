"""Cliente real de iGOB, con el mismo patron de timeout + circuit breaker que e-SITRAM."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import MunicipalAPIUnavailableError
from app.core.logging import get_logger
from app.integrations.base import MunicipalAPIClient
from app.integrations.circuit_breaker import CircuitBreaker

logger = get_logger(__name__)


class IgobClient(MunicipalAPIClient):
    """Cliente HTTP real contra la API publica de iGOB."""

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.IGOB_API_URL
        self._api_key = settings.IGOB_API_KEY
        self._timeout = settings.IGOB_TIMEOUT_SECONDS
        self._breaker = CircuitBreaker()

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        self._breaker.before_call("iGOB")
        headers = {"Authorization": f"Bearer {self._api_key}"}
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=self._timeout) as client:
                response = await client.request(method, path, headers=headers, **kwargs)
                response.raise_for_status()
                self._breaker.record_success()
                result: dict[str, Any] = response.json()
                return result
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            self._breaker.record_failure()
            logger.warning("igob_call_failed", path=path, error_type=type(exc).__name__)
            raise MunicipalAPIUnavailableError(
                "No se pudo consultar iGOB en este momento. Intenta de nuevo mas tarde."
            ) from exc

    async def consultar_estado_tramite(self, codigo_externo: str) -> dict[str, Any]:
        return await self._request("GET", f"/tramites/{codigo_externo}")

    async def iniciar_tramite(self, tipo_tramite: str, datos: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/tramites", json={"tipo": tipo_tramite, **datos})

    async def listar_requisitos(self, tipo_tramite: str) -> list[str]:
        data = await self._request("GET", f"/requisitos/{tipo_tramite}")
        requisitos = data.get("requisitos", [])
        return list(requisitos) if isinstance(requisitos, list) else []
