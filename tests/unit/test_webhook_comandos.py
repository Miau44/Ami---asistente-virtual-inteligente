"""Tests unitarios de las partes deterministicas del webhook de WhatsApp (comandos
de "borrar historial" / "ver tramites" / "menu") que no requieren DB ni HTTP.

Nota: app/api/v1/webhooks.py usa AsyncSessionLocal() directamente en vez de la
dependencia inyectable get_db_session (a diferencia de las demas rutas), por lo que
el override de sesion de tests/conftest.py no le aplica — un test de integracion end
to end de este endpoint requeriria refactorizarlo para inyectar la sesion, fuera de
alcance aqui. Estos tests cubren la logica pura que si se puede aislar."""

from __future__ import annotations

import uuid

from app.api.v1.webhooks import (
    _COMANDO_BORRAR_HISTORIAL,
    _COMANDO_MENU,
    _COMANDO_VER_TRAMITES,
    _formatear_tramites,
)
from app.db.models.tramite import EstadoTramite, Tramite


def _tramite(estado: EstadoTramite, codigo_externo: str | None = "ESITRAM-TEST-0001") -> Tramite:
    return Tramite(
        id=uuid.uuid4(),
        ciudadano_id=uuid.uuid4(),
        tipo_tramite="licencia_funcionamiento",
        sistema_origen="esitram",
        codigo_externo=codigo_externo,
        estado=estado,
        metadata_tramite={},
    )


def test_comandos_reconocen_variantes_con_y_sin_pronombre() -> None:
    assert "borrar historial" in _COMANDO_BORRAR_HISTORIAL
    assert "borrar mi historial" in _COMANDO_BORRAR_HISTORIAL
    assert "ver tramites" in _COMANDO_VER_TRAMITES
    assert "ver historial de consultas" in _COMANDO_VER_TRAMITES
    assert "menu" in _COMANDO_MENU
    assert "ayuda" in _COMANDO_MENU


def test_formatear_tramites_sin_tramites() -> None:
    resultado = _formatear_tramites([])
    assert "ningun tramite" in resultado


def test_formatear_tramites_incluye_codigo_y_estado_legible() -> None:
    tramite = _tramite(EstadoTramite.EN_REVISION)
    resultado = _formatear_tramites([tramite])

    assert "ESITRAM-TEST-0001" in resultado
    assert "en revision" in resultado
    assert "Licencia Funcionamiento" in resultado


def test_formatear_tramites_sin_codigo_externo_avisa_pendiente() -> None:
    tramite = _tramite(EstadoTramite.INICIADO, codigo_externo=None)
    resultado = _formatear_tramites([tramite])

    assert "sin codigo asignado" in resultado


def test_formatear_tramites_lista_varios() -> None:
    tramites = [
        _tramite(EstadoTramite.APROBADO),
        _tramite(EstadoTramite.RECHAZADO, "ESITRAM-TEST-0002"),
    ]
    resultado = _formatear_tramites(tramites)

    assert "ESITRAM-TEST-0001" in resultado
    assert "ESITRAM-TEST-0002" in resultado
