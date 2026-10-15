"""Tipos de columna compartidos entre dialectos.

JSONVariant compila a JSONB en PostgreSQL (produccion) y a JSON generico en otros
dialectos (SQLite en la suite de tests de integracion), evitando acoplar los modelos
ORM a un dialecto especifico solo para poder testear sin Postgres."""

from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

JSONVariant = JSON().with_variant(JSONB(), "postgresql")
