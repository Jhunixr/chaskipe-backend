"""Esquemas del perfil de usuario (FASE 7)."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class ProfileBase(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr


class ProfileUpdate(ProfileBase):
    """Cuerpo de PUT /profile."""


class Profile(ProfileBase):
    """Perfil devuelto por la API."""
