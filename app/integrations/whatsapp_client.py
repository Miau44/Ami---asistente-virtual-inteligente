"""Cliente de envio saliente de mensajes de WhatsApp via Twilio.

Usado por el orquestador del agente (respuestas conversacionales), el manejo de
comandos deterministicos del webhook (borrar historial / ver tramites, ver
app/api/v1/webhooks.py) y por el motor de proactividad (avisos de vencimiento /
cambio de estado)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.exceptions import MunicipalAPIUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)

_TWILIO_API_BASE = "https://api.twilio.com/2010-04-01"


class WhatsAppClient:
    """Envia mensajes salientes de WhatsApp usando la API de Twilio."""

    def __init__(self) -> None:
        settings = get_settings()
        self._account_sid = settings.TWILIO_ACCOUNT_SID
        self._auth_token = settings.TWILIO_AUTH_TOKEN
        self._from_number = settings.TWILIO_WHATSAPP_NUMBER

    async def enviar_mensaje(self, to_number: str, body: str) -> str:
        """Envia un mensaje de texto libre."""
        return await self._enviar(to_number, {"Body": body})

    async def enviar_menu(self, to_number: str, content_sid: str) -> str:
        """Envia un mensaje interactivo (Content Template de Twilio, ej.
        twilio/quick-reply) referenciado por su ContentSid — ver
        scripts/setup_whatsapp_menu.py para como se crea ese template."""
        return await self._enviar(to_number, {"ContentSid": content_sid})

    async def _enviar(self, to_number: str, campos: dict[str, str]) -> str:
        """Devuelve el SID del mensaje creado por Twilio."""
        url = f"{_TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        payload = {
            "From": self._from_number,
            "To": to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}",
            **campos,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    url, data=payload, auth=(self._account_sid, self._auth_token)
                )
                response.raise_for_status()
                sid: str = response.json().get("sid", "")
                logger.info("whatsapp_message_sent", to_masked=_mask_phone(to_number))
                return sid
        except (httpx.TimeoutException, httpx.HTTPError) as exc:
            logger.warning("whatsapp_send_failed", error_type=type(exc).__name__)
            raise MunicipalAPIUnavailableError(
                "No se pudo enviar el mensaje de WhatsApp en este momento."
            ) from exc


def _mask_phone(phone: str) -> str:
    """Enmascara un numero de telefono para logging (solo ultimos 4 digitos visibles)."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) <= 4:
        return "***"
    return f"***{digits[-4:]}"
