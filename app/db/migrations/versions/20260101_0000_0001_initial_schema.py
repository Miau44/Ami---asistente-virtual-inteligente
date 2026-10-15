"""initial schema: ciudadanos, tramites, documentos_validados, recordatorios,
conversaciones, mensajes, fuentes_normativa

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ciudadanos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telefono_whatsapp", sa.String(32), nullable=False, unique=True),
        sa.Column("nombre", sa.String(200), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_ciudadanos_telefono_whatsapp", "ciudadanos", ["telefono_whatsapp"])

    estado_tramite = postgresql.ENUM(
        "iniciado",
        "en_revision",
        "observado",
        "aprobado",
        "rechazado",
        "vencido",
        name="estado_tramite",
    )
    # No se llama a .create() manualmente: op.create_table crea el tipo ENUM
    # automaticamente como parte del DDL de la tabla (CREATE TYPE + CREATE TABLE).
    # Crearlo aqui ademas del create_table produce DuplicateObjectError en Postgres.

    op.create_table(
        "tramites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ciudadano_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ciudadanos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo_tramite", sa.String(120), nullable=False),
        sa.Column("sistema_origen", sa.String(50), nullable=False),
        sa.Column("codigo_externo", sa.String(100), nullable=True),
        sa.Column("estado", estado_tramite, nullable=False, server_default="iniciado"),
        sa.Column("metadata_tramite", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tramites_ciudadano_id", "tramites", ["ciudadano_id"])

    resultado_validacion = postgresql.ENUM(
        "aprobado", "observado", "rechazado", name="resultado_validacion"
    )

    op.create_table(
        "documentos_validados",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tramite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tramites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tipo_documento", sa.String(120), nullable=False),
        sa.Column("resultado", resultado_validacion, nullable=False),
        sa.Column("observaciones", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_documentos_validados_tramite_id", "documentos_validados", ["tramite_id"])

    estado_recordatorio = postgresql.ENUM(
        "pendiente", "enviado", "cancelado", name="estado_recordatorio"
    )

    op.create_table(
        "recordatorios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ciudadano_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ciudadanos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tramite_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tramites.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("mensaje", sa.String(1000), nullable=False),
        sa.Column("fecha_programada", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", estado_recordatorio, nullable=False, server_default="pendiente"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_recordatorios_ciudadano_id", "recordatorios", ["ciudadano_id"])
    op.create_index(
        "ix_recordatorios_idempotency_key", "recordatorios", ["idempotency_key"], unique=True
    )

    op.create_table(
        "conversaciones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "ciudadano_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ciudadanos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("activa", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_conversaciones_ciudadano_id", "conversaciones", ["ciudadano_id"])

    rol_mensaje = postgresql.ENUM("ciudadano", "agente", "sistema", name="rol_mensaje")

    op.create_table(
        "mensajes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversacion_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversaciones.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rol", rol_mensaje, nullable=False),
        sa.Column("contenido", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_mensajes_conversacion_id", "mensajes", ["conversacion_id"])

    op.create_table(
        "fuentes_normativa",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("numero_norma", sa.String(100), nullable=True),
        sa.Column("fecha_vigencia", sa.Date, nullable=False),
        sa.Column("url_fuente", sa.String(500), nullable=True),
        sa.Column("chroma_collection", sa.String(120), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("fuentes_normativa")
    op.drop_table("mensajes")
    op.execute("DROP TYPE IF EXISTS rol_mensaje")
    op.drop_table("conversaciones")
    op.drop_table("recordatorios")
    op.execute("DROP TYPE IF EXISTS estado_recordatorio")
    op.drop_table("documentos_validados")
    op.execute("DROP TYPE IF EXISTS resultado_validacion")
    op.drop_table("tramites")
    op.execute("DROP TYPE IF EXISTS estado_tramite")
    op.drop_table("ciudadanos")
