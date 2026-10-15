"""Script de datos ficticios para demo: crea ciudadanos, tramites y una fuente
normativa de ejemplo. Uso: python -m scripts.seed_data

Escenario de demo: Daniela Choque quiere abrir "ElectroHogar Sopocachi", una
tienda de electrodomesticos en la zona de Sopocachi, y tramita su licencia de
funcionamiento. Los IDs son fijos (no uuid4 aleatorio) para que la demo del
dashboard (ver ami-copiloto-dashboard/docs/demo-sopocachi.md) pueda
referenciarlos directamente sin tener que consultar psql o logs. Como
`demo_reset.sh` corre `docker compose down -v` antes de sembrar, reusar estos
IDs en cada reset es seguro."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta

from app.core.logging import configure_logging, get_logger
from app.db.models.ciudadano import Ciudadano
from app.db.models.fuente_normativa import FuenteNormativa
from app.db.models.recordatorio import EstadoRecordatorio, Recordatorio
from app.db.models.tramite import EstadoTramite, Tramite
from app.db.session import AsyncSessionLocal

logger = get_logger(__name__)

# IDs fijos para la demo "ElectroHogar Sopocachi" — ver docstring del modulo.
CIUDADANO_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
TRAMITE_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
FUENTE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
RECORDATORIO_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        ciudadano = Ciudadano(
            id=CIUDADANO_ID,
            telefono_whatsapp="whatsapp:+59170112233",
            nombre="Daniela Choque",
        )
        session.add(ciudadano)
        await session.flush()

        tramite = Tramite(
            id=TRAMITE_ID,
            ciudadano_id=ciudadano.id,
            tipo_tramite="licencia_funcionamiento",
            sistema_origen="esitram",
            codigo_externo="ESITRAM-DEMO-SOPOCACHI-0001",
            estado=EstadoTramite.EN_REVISION,
            metadata_tramite={
                "actividad_economica": "venta de electrodomesticos",
                "nombre_comercial": "ElectroHogar Sopocachi",
                "zona": "Sopocachi",
                "direccion": "Av. 20 de Octubre esq. Belisario Salinas, Sopocachi, La Paz",
            },
        )
        session.add(tramite)

        fuente = FuenteNormativa(
            id=FUENTE_ID,
            titulo="Ordenanza Municipal 123/2024 - Licencias de Funcionamiento",
            numero_norma="OM 123/2024",
            fecha_vigencia=date(2024, 1, 15),
            url_fuente="https://lapaz.bo/normativa/om-123-2024",
            chroma_collection="normativa_municipal",
        )
        session.add(fuente)

        recordatorio = Recordatorio(
            id=RECORDATORIO_ID,
            ciudadano_id=ciudadano.id,
            tramite_id=tramite.id,
            idempotency_key=f"{ciudadano.id}:{tramite.id}:seed-demo",
            mensaje=(
                "Recuerda completar el croquis de ubicacion de ElectroHogar Sopocachi "
                "para avanzar tu licencia de funcionamiento."
            ),
            fecha_programada=datetime.now(UTC) + timedelta(days=1),
            estado=EstadoRecordatorio.PENDIENTE,
        )
        session.add(recordatorio)

        await session.commit()
        logger.info(
            "seed_data_creado",
            ciudadano_id=str(ciudadano.id),
            tramite_id=str(tramite.id),
            recordatorio_id=str(recordatorio.id),
        )


if __name__ == "__main__":
    configure_logging()
    asyncio.run(seed())
