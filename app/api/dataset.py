"""
Dataset de senas: subir muestras grabadas en la app y descargarlas para
entrenar. Solo landmarks (coordenadas), nunca video.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status

from app.api.deps import CurrentUser
from app.core.config import settings
from app.schemas.signs import DatasetSampleIn, DatasetSampleStored, DatasetSummary
from app.services import dataset_store
from app.services.store import get_repository

router = APIRouter(prefix="/dataset", tags=["dataset"])


def _limit_size(content_length: Annotated[int | None, Header()] = None) -> None:
    """Rechaza muestras enormes antes de validarlas (el proxy pone el limite duro)."""
    if content_length is not None and content_length > settings.max_sample_bytes:
        raise HTTPException(413, "Muestra demasiado grande")


@router.post(
    "/samples",
    response_model=DatasetSampleStored,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_limit_size)],
)
def upload_sample(sample: DatasetSampleIn, user: CurrentUser) -> DatasetSampleStored:
    """
    Guarda una grabacion (formato de `ai/data/DATASET_FORMAT.md`).

    Requiere sesion: asi cada muestra tiene a alguien responsable de su
    consentimiento. Rechaza muestras sin consentimiento o de una etiqueta que
    no esta en el vocabulario.
    """
    if not sample.consent:
        raise HTTPException(
            422,
            "Sin consentimiento explicito la muestra no se guarda.",
        )
    repo = get_repository()
    if repo.get_sign(sample.label) is None:
        raise HTTPException(
            422,
            f"La etiqueta {sample.label} no esta en el vocabulario.",
        )
    if not any(frame.hands for frame in sample.frames):
        raise HTTPException(
            422, "La grabacion no tiene ninguna mano."
        )

    stored = dataset_store.save_sample(sample)
    notes = sample.notes.strip()
    notes = f"[usuario {user.id}] {notes}".strip()
    try:
        repo.add_sample(stored, consent=True, notes=notes)
    except Exception:
        dataset_store.discard_sample(stored)
        raise
    return stored


@router.get("/summary", response_model=DatasetSummary)
def summary() -> DatasetSummary:
    """Muestras por sena: sirve para saber que falta grabar."""
    return get_repository().dataset_summary()


@router.get("/export", response_class=Response)
def export(x_admin_token: Annotated[str | None, Header()] = None) -> Response:
    """
    Zip con todas las muestras, listo para descomprimir en `ai/data/raw/`.
    Requiere la cabecera `X-Admin-Token` (= CHASKIPE_ADMIN_TOKEN).
    """
    expected = settings.admin_token
    if not expected or not x_admin_token or not secrets.compare_digest(
        x_admin_token, expected
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No autorizado")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=dataset_store.export_zip(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="chaskipe-dataset-{stamp}.zip"'},
    )
