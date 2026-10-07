"""Vocabulario de senas de la LSP (catalogo publico)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.signs import Sign
from app.services.store import get_repository

router = APIRouter(prefix="/signs", tags=["signs"])


@router.get("", response_model=list[Sign])
def list_signs() -> list[Sign]:
    """Senas activas. `validated=false` = la app debe mostrarla como DEMO."""
    return get_repository().list_signs()


@router.get("/{label}", response_model=Sign)
def get_sign(label: str) -> Sign:
    sign = get_repository().get_sign(label.upper())
    if sign is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sena no encontrada")
    return sign
