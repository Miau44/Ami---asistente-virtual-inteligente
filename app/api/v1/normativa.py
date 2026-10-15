"""GET /api/v1/normativa/buscar - busqueda semantica sobre normativa oficial (RAG)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import rate_limiter
from app.models.common import FuenteCitada
from app.models.normativa import BusquedaNormativaResponse, FragmentoNormativa
from app.services.rag_service import RagService

router = APIRouter(prefix="/normativa", tags=["normativa"])


@router.get(
    "/buscar",
    response_model=BusquedaNormativaResponse,
    dependencies=[Depends(rate_limiter(scope="normativa_buscar", limit_per_minute=30))],
)
async def buscar_normativa(
    consulta: Annotated[str, Query(min_length=3, max_length=500)],
    top_k: Annotated[int, Query(ge=1, le=20)] = 5,
) -> BusquedaNormativaResponse:
    rag_service = RagService()
    fragmentos = rag_service.buscar(consulta, top_k=top_k)

    if not fragmentos:
        return BusquedaNormativaResponse(
            consulta=consulta,
            encontrado=False,
            fragmentos=[],
            mensaje="No se encontro informacion oficial relevante para esta consulta.",
        )

    return BusquedaNormativaResponse(
        consulta=consulta,
        encontrado=True,
        fragmentos=[
            FragmentoNormativa(
                texto=f["texto"],
                similitud=f["similitud"],
                fuente=FuenteCitada(
                    titulo=f["metadata"].get("titulo", ""),
                    numero_norma=f["metadata"].get("numero_norma") or None,
                    fecha_vigencia=f["metadata"].get("fecha_vigencia", ""),
                    url_fuente=f["metadata"].get("url_fuente") or None,
                ),
            )
            for f in fragmentos
        ],
    )
