"""Excepciones de dominio y sus exception handlers para FastAPI.

Mantener toda excepcion de negocio aqui evita que las capas de servicio dependan
de HTTPException de FastAPI (violaria la separacion api -> services).
"""

from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AmiCopilotoError(Exception):
    """Excepcion base de dominio."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    error_code: str = "ami_error"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidWebhookSignatureError(AmiCopilotoError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "invalid_webhook_signature"


class InvalidCredentialsError(AmiCopilotoError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "invalid_credentials"


class NotFoundError(AmiCopilotoError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not_found"


class RateLimitExceededError(AmiCopilotoError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"


class MunicipalAPIUnavailableError(AmiCopilotoError):
    """El sistema municipal (e-SITRAM / iGOB / Gestion Documental) no respondio a tiempo."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "municipal_api_unavailable"


class DocumentValidationError(AmiCopilotoError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    error_code = "document_validation_error"


async def ami_copiloto_error_handler(request: Request, exc: AmiCopilotoError) -> JSONResponse:
    logger.warning("domain_error", error_code=exc.error_code, path=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error_code": exc.error_code, "message": exc.message},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error_code": "internal_error", "message": "Error interno del servidor"},
    )
