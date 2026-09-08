"""Endpoints de autenticacion: registro, inicio de sesion y sesion actual."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser
from app.core.security import create_access_token
from app.schemas.auth import AuthResponse, AuthUser, LoginRequest, RegisterRequest
from app.services.repository import EmailAlreadyUsed
from app.services.store import get_repository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(data: RegisterRequest) -> AuthResponse:
    try:
        user = get_repository().create_user(
            name=data.name.strip(),
            email=str(data.email).strip().lower(),
            password=data.password,
        )
    except EmailAlreadyUsed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese correo ya tiene una cuenta.",
        ) from None

    return AuthResponse(access_token=create_access_token(user.id), user=user)


@router.post("/login", response_model=AuthResponse)
def login(data: LoginRequest) -> AuthResponse:
    user = get_repository().authenticate(
        email=str(data.email).strip().lower(), password=data.password
    )
    # Mismo mensaje para correo inexistente y contrasena incorrecta: decir cual
    # de los dos falla permite averiguar que correos estan registrados.
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contrasena incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthResponse(access_token=create_access_token(user.id), user=user)


@router.get("/me", response_model=AuthUser)
def me(user: CurrentUser) -> AuthUser:
    """Comprueba que el token sigue siendo valido y devuelve el usuario."""
    return user
