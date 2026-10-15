"""Seguridad: JWT para el dashboard, hashing de contrasenas y verificacion de firma Twilio."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.exceptions import InvalidCredentialsError, InvalidWebhookSignatureError

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bool(_pwd_context.verify(plain_password, hashed_password))


def create_token(
    subject: str, token_type: TokenType, extra_claims: dict[str, Any] | None = None
) -> str:
    """Crea un JWT de acceso o refresco firmado con JWT_SECRET_KEY."""
    settings = get_settings()
    now = datetime.now(UTC)
    if token_type == "access":
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    else:
        expire = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    token: str = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decodifica y valida un JWT.

    Lanza InvalidCredentialsError si es invalido, expirado o de tipo incorrecto.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError as exc:
        raise InvalidCredentialsError("Token invalido o expirado") from exc

    if payload.get("type") != expected_type:
        raise InvalidCredentialsError("Tipo de token incorrecto")

    return payload


def verify_twilio_signature(
    auth_token: str, url: str, params: dict[str, str], signature: str
) -> None:
    """Verifica X-Twilio-Signature siguiendo el algoritmo oficial de Twilio.

    https://www.twilio.com/docs/usage/webhooks/webhooks-security
    Lanza InvalidWebhookSignatureError si la firma no coincide.
    """
    data = url
    for key in sorted(params.keys()):
        data += key + params[key]

    computed = base64.b64encode(
        hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")

    if not hmac.compare_digest(computed, signature):
        raise InvalidWebhookSignatureError("Firma de webhook de Twilio invalida")
