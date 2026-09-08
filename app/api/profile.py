"""Endpoints del perfil. Requieren autenticacion."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.schemas.profile import Profile, ProfileUpdate
from app.services.repository import EmailAlreadyUsed
from app.services.store import get_repository

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("", response_model=Profile)
def get_profile(user: CurrentUser) -> Profile:
    return get_repository().get_profile(user.id)


@router.put("", response_model=Profile)
def update_profile(data: ProfileUpdate, user: CurrentUser) -> Profile:
    try:
        return get_repository().update_profile(
            user.id, name=data.name.strip(), email=str(data.email).strip().lower()
        )
    except EmailAlreadyUsed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese correo ya tiene una cuenta.",
        ) from None
