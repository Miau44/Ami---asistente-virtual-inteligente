"""Dependencias compartidas de FastAPI: rate limiting y autenticacion JWT del dashboard."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

import redis.asyncio as redis
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.exceptions import InvalidCredentialsError, RateLimitExceededError
from app.core.security import decode_token

_bearer_scheme = HTTPBearer(auto_error=False)
_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def rate_limit(
    request: Request,
    x_forwarded_for: Annotated[str | None, Header()] = None,
    limit_per_minute: int = 10,
    scope: str = "default",
) -> None:
    """Rate limit simple de ventana fija por IP/telefono, respaldado en Redis.

    No es exacto (ventana fija, no deslizante) pero es suficiente para controlar abuso
    y costo de LLM en un MVP; documentado como tal en docs/decisiones-tecnicas.md.
    """
    identificador = x_forwarded_for or (request.client.host if request.client else "unknown")
    clave = f"ratelimit:{scope}:{identificador}"

    client = get_redis()
    conteo = await client.incr(clave)
    if conteo == 1:
        await client.expire(clave, 60)

    if conteo > limit_per_minute:
        raise RateLimitExceededError("Demasiadas solicitudes. Intenta de nuevo en un minuto.")


def rate_limiter(scope: str, limit_per_minute: int) -> Callable[..., Coroutine[Any, Any, None]]:
    """Fabrica una dependencia FastAPI de rate limiting para el `scope` y limite dados."""

    async def _dep(
        request: Request, x_forwarded_for: Annotated[str | None, Header()] = None
    ) -> None:
        await rate_limit(request, x_forwarded_for, limit_per_minute=limit_per_minute, scope=scope)

    return _dep


async def get_current_admin_subject(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> str:
    """Valida el JWT de acceso del dashboard y devuelve el subject (username)."""
    if credentials is None:
        raise InvalidCredentialsError("Falta el token de autenticacion")
    payload = decode_token(credentials.credentials, expected_type="access")
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidCredentialsError("Token invalido")
    return subject
