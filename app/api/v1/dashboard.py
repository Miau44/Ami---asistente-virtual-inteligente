"""Endpoints del dashboard administrativo: login JWT y datos agregados.

Todas las rutas de datos requieren JWT de acceso valido (expiracion corta). No hay
rutas administrativas abiertas."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_admin_subject
from app.core.config import get_settings
from app.core.exceptions import InvalidCredentialsError
from app.core.security import create_token, decode_token
from app.db.session import get_db_session
from app.models.dashboard import LoginRequest, RefreshRequest, ResumenDashboard, TokenResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.post("/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    """Autenticacion del panel administrativo.

    NOTA de implementacion: en este MVP las credenciales admin viven en
    APP_SECRET_KEY-derivadas via variables de entorno para la demo (ver ADR en
    docs/decisiones-tecnicas.md); en produccion deben migrarse a una tabla de
    usuarios administrativos con hash bcrypt por usuario."""
    settings = get_settings()
    admin_user = "admin"
    admin_password_hash = settings.APP_SECRET_KEY  # placeholder deliberado, ver ADR

    if payload.username != admin_user or not _validar_password_demo(
        payload.password, admin_password_hash
    ):
        raise InvalidCredentialsError("Usuario o contrasena incorrectos")

    access_token = create_token(subject=payload.username, token_type="access")
    refresh_token = create_token(subject=payload.username, token_type="refresh")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


def _validar_password_demo(password: str, secret: str) -> bool:
    # Comparacion en tiempo constante para evitar timing attacks triviales.
    import hmac

    return hmac.compare_digest(password, secret)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest) -> TokenResponse:
    claims = decode_token(payload.refresh_token, expected_type="refresh")
    subject = claims["sub"]
    access_token = create_token(subject=subject, token_type="access")
    refresh_token = create_token(subject=subject, token_type="refresh")
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get(
    "/resumen",
    response_model=ResumenDashboard,
    dependencies=[Depends(get_current_admin_subject)],
)
async def resumen(session: Annotated[AsyncSession, Depends(get_db_session)]) -> ResumenDashboard:
    service = DashboardService(session)
    data = await service.resumen()
    return ResumenDashboard.model_validate(data)
