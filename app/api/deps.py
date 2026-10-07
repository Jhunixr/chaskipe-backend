"""Dependencias compartidas de la API: usuario autenticado."""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.schemas.auth import AuthUser
from app.services.store import get_repository

# auto_error=False para poder devolver siempre el mismo 401 con cabecera
# WWW-Authenticate, en vez de un 403 cuando falta la cabecera.
_bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="No autenticado",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthUser:
    """
    Usuario dueno del token. Lanza 401 si falta, es invalido, caduco, o si la
    cuenta ya no existe (token valido de un usuario borrado).
    """
    if creds is None:
        raise _UNAUTHORIZED

    user_id = decode_access_token(creds.credentials)
    if user_id is None:
        raise _UNAUTHORIZED

    user = get_repository().get_user(user_id)
    if user is None:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[AuthUser, Depends(current_user)]


def optional_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthUser | None:
    """
    Usuario si hay un token valido; None si no hay token. Un token invalido
    sigue siendo 401: la app debe saber que su sesion caduco.
    """
    if creds is None:
        return None
    return current_user(creds)


OptionalUser = Annotated[AuthUser | None, Depends(optional_user)]
