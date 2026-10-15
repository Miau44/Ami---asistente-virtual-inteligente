"""Tests unitarios de seguridad: JWT y verificacion de firma de webhook de Twilio."""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from app.core.exceptions import InvalidCredentialsError, InvalidWebhookSignatureError
from app.core.security import create_token, decode_token, verify_twilio_signature


def test_create_and_decode_access_token_roundtrip() -> None:
    token = create_token(subject="admin", token_type="access")
    payload = decode_token(token, expected_type="access")

    assert payload["sub"] == "admin"
    assert payload["type"] == "access"


def test_decode_token_rejects_wrong_type() -> None:
    token = create_token(subject="admin", token_type="refresh")

    with pytest.raises(InvalidCredentialsError):
        decode_token(token, expected_type="access")


def test_verify_twilio_signature_accepts_valid_signature() -> None:
    auth_token = "test-auth-token"
    url = "https://example.com/api/v1/webhooks/whatsapp"
    params = {"From": "whatsapp:+59170000000", "Body": "hola"}

    data = url
    for key in sorted(params):
        data += key + params[key]
    signature = base64.b64encode(
        hmac.new(auth_token.encode(), data.encode(), hashlib.sha1).digest()
    ).decode()

    verify_twilio_signature(auth_token, url, params, signature)  # no debe lanzar


def test_verify_twilio_signature_rejects_tampered_signature() -> None:
    with pytest.raises(InvalidWebhookSignatureError):
        verify_twilio_signature(
            "test-auth-token",
            "https://example.com/api/v1/webhooks/whatsapp",
            {"Body": "hola"},
            "firma-invalida",
        )
