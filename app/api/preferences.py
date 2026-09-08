"""Endpoints de las preferencias de accesibilidad. Requieren autenticacion."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.preferences import Preferences, PreferencesUpdate
from app.services.store import get_repository

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=Preferences)
def get_preferences(user: CurrentUser) -> Preferences:
    return get_repository().get_preferences(user.id)


@router.put("", response_model=Preferences)
def update_preferences(data: PreferencesUpdate, user: CurrentUser) -> Preferences:
    return get_repository().update_preferences(
        user.id, Preferences(**data.model_dump())
    )
