"""Schemas del webhook entrante de WhatsApp (formato Twilio)."""

from __future__ import annotations

from pydantic import Field

from app.models.common import ApiModel


class TwilioWhatsAppWebhook(ApiModel):
    """Subconjunto de campos que Twilio envia como application/x-www-form-urlencoded."""

    MessageSid: str
    From: str = Field(..., description="Numero de WhatsApp emisor, formato whatsapp:+591...")
    To: str
    Body: str = Field(default="", max_length=4096)
    NumMedia: int = Field(default=0, ge=0)
    MediaUrl0: str | None = None
    MediaContentType0: str | None = None
