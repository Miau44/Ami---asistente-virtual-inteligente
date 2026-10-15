"""Factory que selecciona la implementacion mock o real de cada integracion municipal
segun configuracion (ESITRAM_MODE / IGOB_MODE). La capa de negocio siempre depende de
MunicipalAPIClient (interfaz), nunca de una implementacion concreta."""

from __future__ import annotations

from app.core.config import get_settings
from app.integrations.base import MunicipalAPIClient
from app.integrations.esitram_client import ESitramClient
from app.integrations.esitram_mock import ESitramMockClient
from app.integrations.igob_client import IgobClient
from app.integrations.igob_mock import IgobMockClient


def get_esitram_client() -> MunicipalAPIClient:
    settings = get_settings()
    if settings.ESITRAM_MODE == "real":
        return ESitramClient()
    return ESitramMockClient()


def get_igob_client() -> MunicipalAPIClient:
    settings = get_settings()
    if settings.IGOB_MODE == "real":
        return IgobClient()
    return IgobMockClient()
