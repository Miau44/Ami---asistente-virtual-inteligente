"""Punto unico de importacion de todos los modelos ORM, para que Base.metadata los
conozca (requerido por Alembic autogenerate). Deliberadamente separado de
app/db/base.py: si Base importara los modelos y un modelo fuera el primer punto de
entrada al paquete (ej. un servicio que hace `from app.db.models.ciudadano import
Ciudadano` antes que nada mas haya tocado app.db), se produce un import circular
(ciudadano -> base -> ciudadano, a medias inicializado)."""

from __future__ import annotations

from app.db.models.ciudadano import Ciudadano
from app.db.models.conversacion import Conversacion, Mensaje
from app.db.models.documento_validado import DocumentoValidado
from app.db.models.fuente_normativa import FuenteNormativa
from app.db.models.recordatorio import Recordatorio
from app.db.models.tramite import Tramite

__all__ = [
    "Ciudadano",
    "Conversacion",
    "Mensaje",
    "DocumentoValidado",
    "FuenteNormativa",
    "Recordatorio",
    "Tramite",
]
