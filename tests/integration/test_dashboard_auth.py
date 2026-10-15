"""Tests de integracion: autenticacion JWT del dashboard y proteccion de rutas admin."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_resumen_dashboard_sin_token_devuelve_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/dashboard/resumen")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_con_credenciales_invalidas_devuelve_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/dashboard/auth/login",
        json={"username": "admin", "password": "credencial-incorrecta"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_webhook_whatsapp_sin_firma_devuelve_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/webhooks/whatsapp",
        data={"From": "whatsapp:+59170000000", "Body": "hola", "MessageSid": "SM123"},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "invalid_webhook_signature"
