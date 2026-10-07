"""Reportes de reconocimientos fallidos y modelos disponibles."""
from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import OptionalUser
from app.schemas.signs import RecognitionModel, RecognitionReport, RecognitionReportCreate
from app.services.store import get_repository

router = APIRouter(prefix="/recognition", tags=["recognition"])


@router.post(
    "/reports", response_model=RecognitionReport, status_code=status.HTTP_201_CREATED
)
def add_report(data: RecognitionReportCreate, user: OptionalUser) -> RecognitionReport:
    """
    "No era esa sena": la app avisa de un reconocimiento equivocado. Anonimo si
    no hay sesion. No se envia video ni landmarks.
    """
    return get_repository().add_report(user.id if user else None, data)


@router.get("/models", response_model=list[RecognitionModel])
def list_models() -> list[RecognitionModel]:
    return get_repository().list_models()
