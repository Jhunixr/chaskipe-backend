"""Endpoints del historial de traducciones. Requieren autenticacion."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser
from app.schemas.history import HistoryEntry, HistoryEntryCreate
from app.services.store import get_repository

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[HistoryEntry])
def list_history(
    user: CurrentUser,
    limit: int | None = Query(default=None, ge=1, le=200),
) -> list[HistoryEntry]:
    return get_repository().list_history(user.id, limit=limit)


@router.post("", response_model=HistoryEntry, status_code=status.HTTP_201_CREATED)
def add_history(data: HistoryEntryCreate, user: CurrentUser) -> HistoryEntry:
    return get_repository().add_history(user.id, data)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(entry_id: str, user: CurrentUser) -> None:
    # Devuelve False tanto si no existe como si pertenece a otra persona: no
    # se distingue para no revelar que ids existen.
    if not get_repository().delete_history(user.id, entry_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entrada de historial no encontrada",
        )


@router.delete("", status_code=status.HTTP_200_OK)
def clear_history(user: CurrentUser) -> dict[str, int]:
    return {"deleted": get_repository().clear_history(user.id)}
