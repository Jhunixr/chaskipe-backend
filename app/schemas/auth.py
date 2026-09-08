"""Esquemas de autenticacion."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

# Minimo razonable sin caer en reglas que empujan a contrasenas peores
# (una frase larga es mas segura que "Abc1!").
MIN_PASSWORD = 8


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthUser(BaseModel):
    """Usuario devuelto tras autenticarse. Nunca incluye la contrasena."""

    id: int
    name: str
    email: EmailStr


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUser
