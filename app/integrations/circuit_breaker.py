"""Circuit breaker minimalista en memoria para clientes de integraciones municipales.

Si una integracion falla repetidamente, el circuito se "abre" y las siguientes
llamadas fallan rapido (sin golpear la red) durante un periodo de enfriamiento, en
vez de acumular timeouts. Esto permite al agente degradar elegantemente en lugar de
colgarse esperando un sistema municipal caido.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.core.exceptions import MunicipalAPIUnavailableError


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_timeout_seconds: float = 30.0
    _failure_count: int = field(default=0, init=False)
    _opened_at: float | None = field(default=None, init=False)

    def _is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.reset_timeout_seconds:
            # Ventana de enfriamiento cumplida: permite un intento de prueba (half-open).
            self._opened_at = None
            self._failure_count = 0
            return False
        return True

    def before_call(self, integration_name: str) -> None:
        if self._is_open():
            raise MunicipalAPIUnavailableError(
                f"{integration_name} no disponible temporalmente (circuito abierto)."
            )

    def record_success(self) -> None:
        self._failure_count = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._opened_at = time.monotonic()
