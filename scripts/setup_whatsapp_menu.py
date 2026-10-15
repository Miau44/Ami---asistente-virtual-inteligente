"""Crea (o re-crea) el Content Template de Twilio para el menu de botones rapidos de
WhatsApp (twilio/quick-reply): "Borrar historial" y "Ver mis tramites".

Uso:
    python -m scripts.setup_whatsapp_menu

Imprime el ContentSid (HXxxx...) que hay que pegar en TWILIO_MENU_CONTENT_SID del
.env. Es un paso de configuracion unico (como app.ingestion.ingest_normativa), no se
corre en cada arranque del backend.

Nota: los botones de "quick reply" se envian como mensaje de sesion (dentro de la
ventana de 24h de una conversacion iniciada por el ciudadano), por lo que NO requieren
aprobacion de plantilla de Meta/WhatsApp para este uso — esa aprobacion solo aplica a
plantillas usadas para reenganchar a un ciudadano fuera de esa ventana (ver
docs/decisiones-tecnicas.md)."""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

_CONTENT_API_URL = "https://content.twilio.com/v1/Content"


def crear_menu() -> str:
    settings = get_settings()
    payload = {
        "friendly_name": "ami_copiloto_menu_v1",
        "language": "es",
        "types": {
            "twilio/quick-reply": {
                "body": "Que te gustaria hacer?",
                "actions": [
                    {"title": "Borrar historial", "id": "borrar_historial"},
                    {"title": "Ver mis tramites", "id": "ver_tramites"},
                ],
            }
        },
    }
    response = httpx.post(
        _CONTENT_API_URL,
        json=payload,
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        timeout=20,
    )
    response.raise_for_status()
    content_sid: str = response.json()["sid"]
    return content_sid


if __name__ == "__main__":
    configure_logging()
    sid = crear_menu()
    print(f"TWILIO_MENU_CONTENT_SID={sid}")
    print("Pega esa linea en tu .env para activar el menu de botones.")
